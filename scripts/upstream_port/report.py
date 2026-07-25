"""Generate review reports and read-only patch files for EXPLICITLY selected
commit SHAs, writing only into a gitignored output directory.

This module never applies, cherry-picks, or merges a patch -- it only reads
local git objects (`git format-patch --stdout`) and writes text files. A SHA
that was not explicitly passed in never gets a patch generated for it, and a
SHA that is not reachable from the allowed upstream ref set is rejected.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from . import classify, constants, git_utils, output_safety


class SelectionError(RuntimeError):
    """Raised when a requested SHA is invalid or outside the allowed range."""


# Re-exported for backwards compatibility: callers/tests that catch
# `report.OutputSafetyError` keep working even though the check itself now
# lives in the shared `output_safety` module (see `ensure_output_dir_ignored`
# below), used by every write path in this package (report *and*
# scan/drift `--output`).
OutputSafetyError = output_safety.OutputSafetyError


@dataclass
class PatchEntry:
    sha: str
    author_name: str
    author_email: str
    subject: str
    author_date: str
    changed_paths: List[str]
    category_summary: Dict[str, int]
    risk_flags: List[str]
    patch_filename: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sha": self.sha,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "subject": self.subject,
            "author_date": self.author_date,
            "changed_paths": self.changed_paths,
            "category_summary": self.category_summary,
            "risk_flags": self.risk_flags,
            "patch_filename": self.patch_filename,
        }


def _allowed_range_tips(cwd: str, remote_name: str, ref: str) -> List[str]:
    """Local refs a selected SHA is allowed to be reachable from: the caller's
    selected ref, plus every remote-tracking ref under the configured remote
    (so a SHA on any known upstream branch -- not just the one being scanned
    right now -- can still be explicitly reported/patched)."""
    tips = set(git_utils.remote_refs(remote_name, cwd))
    try:
        tips.add(git_utils.resolve_commit_sha(ref, cwd))
    except git_utils.GitError:
        pass
    return sorted(tips)


def validate_selection(cwd: str, remote_name: str, ref: str, shas: Sequence[str]) -> List[str]:
    """Validate each requested SHA: must be a full 40-hex commit SHA that
    exists locally, is reachable from the allowed upstream ref set, and is
    NOT a merge commit. Returns the validated list (order preserved) or
    raises SelectionError describing every problem found -- always before
    any output directory is created or any file is written.

    Merge commits are rejected outright rather than represented: `git
    format-patch` silently drops or retargets merge commits (see
    `git_utils.format_patch_text`), so there is no deterministic,
    honestly-labelled, safely hand-appliable single-file patch this tool
    can produce for one. Reviewing a merge commit's actual effect requires
    selecting its non-merge constituent commits individually, or manual
    inspection (`git show <merge-sha>`, `git log --graph`) outside this
    tool.
    """
    if not shas:
        raise SelectionError("no commit SHAs were explicitly selected; refusing to generate anything")

    tips = _allowed_range_tips(cwd, remote_name, ref)
    problems: List[str] = []
    validated: List[str] = []
    for sha in shas:
        if not git_utils.is_full_sha(sha):
            problems.append(f"{sha!r} is not a full 40-hex commit SHA")
            continue
        if not git_utils.object_exists(sha, cwd):
            problems.append(f"{sha} does not exist as a local commit object")
            continue
        reachable = any(git_utils.is_ancestor(sha, tip, cwd) for tip in tips)
        if not reachable:
            problems.append(
                f"{sha} is not reachable from any allowed upstream ref "
                f"({', '.join(tips) or 'none configured'})"
            )
            continue
        if git_utils.is_merge_commit(sha, cwd):
            parents = ", ".join(git_utils.commit_parents(sha, cwd))
            problems.append(
                f"{sha} is a merge commit (parents: {parents}); refusing to "
                "generate a patch for it because no single deterministic, "
                "safely hand-appliable patch that preserves provenance can "
                "be produced for a merge. Select its individual non-merge "
                f"commits instead, or review it manually (`git show {sha}`)."
            )
            continue
        validated.append(sha)

    if problems:
        raise SelectionError("rejected SHA selection:\n  - " + "\n  - ".join(problems))
    return validated


def ensure_output_dir_ignored(cwd: str, out_dir: str) -> str:
    """Validate `out_dir` via the shared `output_safety` write-safety
    contract (containment in the repo root, no symlink anywhere on the
    path, confirmed gitignored) and return the resolved path to use.

    Kept as a thin, named wrapper (rather than inlining the call at each
    call site) so the historical name/signature callers may already depend
    on keeps working, while the actual check lives in exactly one shared
    place.
    """
    return output_safety.validate_output_target(cwd, out_dir, is_dir=True)


def generate(
    cwd: str,
    remote_name: str,
    ref: str,
    shas: Sequence[str],
    out_dir: str,
    canonical_upstream_url: str = constants.CANONICAL_UPSTREAM_URL,
) -> Dict[str, Any]:
    validated = validate_selection(cwd, remote_name, ref, shas)
    out_dir = ensure_output_dir_ignored(cwd, out_dir)
    os.makedirs(out_dir, exist_ok=True)

    entries: List[PatchEntry] = []
    for index, sha in enumerate(validated, start=1):
        meta = git_utils.commit_meta(sha, cwd)
        paths = git_utils.changed_paths(sha, cwd)
        patch_filename = f"{index:04d}-{sha[:12]}.patch"
        patch_text = git_utils.format_patch_text(sha, cwd)
        with open(os.path.join(out_dir, patch_filename), "w", encoding="utf-8") as fh:
            fh.write(patch_text)
        entries.append(
            PatchEntry(
                sha=meta.sha,
                author_name=meta.author_name,
                author_email=meta.author_email,
                subject=meta.subject,
                author_date=meta.author_date_iso,
                changed_paths=paths,
                category_summary=classify.category_summary(paths),
                risk_flags=classify.risk_flags_for_paths(paths),
                patch_filename=patch_filename,
            )
        )

    report = {
        "schema_version": constants.STATE_SCHEMA_VERSION,
        "canonical_upstream_url": canonical_upstream_url,
        "remote_name": remote_name,
        "ref": ref,
        "selected_count": len(entries),
        "entries": [e.to_dict() for e in entries],
    }
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(_render_markdown(report))

    return report


def _render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Upstream port review report",
        "",
        f"- canonical upstream: {report['canonical_upstream_url']}",
        f"- remote: {report['remote_name']}",
        f"- selected ref: {report['ref']}",
        f"- selected commits: {report['selected_count']}",
        "",
        "**This report/patch set is NOT applied automatically.** Review, then "
        "manually apply each patch, then run the `verify` subcommand.",
        "",
    ]
    for entry in report["entries"]:
        lines.append(f"## {entry['sha']}  ({entry['patch_filename']})")
        lines.append(f"- subject: {entry['subject']}")
        lines.append(f"- author: {entry['author_name']} <{entry['author_email']}>")
        lines.append(f"- date: {entry['author_date']}")
        if entry["risk_flags"]:
            lines.append(f"- risk flags: {', '.join(entry['risk_flags'])}")
        lines.append(f"- category summary: {entry['category_summary']}")
        lines.append(f"- changed paths ({len(entry['changed_paths'])}):")
        for path in entry["changed_paths"]:
            lines.append(f"    - {path}")
        lines.append("")
    return "\n".join(lines)
