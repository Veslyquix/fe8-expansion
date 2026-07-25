"""Read-only scan: enumerate unreviewed commits between last_ported and a
caller-selected local upstream ref, with deterministic classification.

Never fetches. Never writes state. Never executes upstream code -- it only
reads commit metadata and changed-path lists via local `git` plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import classify, constants, git_utils


class ScanBoundaryError(RuntimeError):
    """Raised when the last_ported boundary and the selected ref have diverged
    (i.e. last_ported is not an ancestor of the selected ref), which means a
    plain a..b commit range would be misleading. Run `drift` first."""


@dataclass
class CommitReport:
    sha: str
    author_name: str
    author_email: str
    subject: str
    author_date: str
    changed_paths: List[str]
    categories: Dict[str, str]
    category_summary: Dict[str, int]
    risk_flags: List[str]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sha": self.sha,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "subject": self.subject,
            "author_date": self.author_date,
            "changed_paths": self.changed_paths,
            "categories": self.categories,
            "category_summary": self.category_summary,
            "risk_flags": self.risk_flags,
            "status": self.status,
        }


@dataclass
class ScanResult:
    ref: str
    ref_sha: str
    baseline_sha: str
    remote_name: str
    canonical_upstream_url: str
    commits: List[CommitReport] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": constants.STATE_SCHEMA_VERSION,
            "canonical_upstream_url": self.canonical_upstream_url,
            "remote_name": self.remote_name,
            "ref": self.ref,
            "ref_sha": self.ref_sha,
            "baseline_sha": self.baseline_sha,
            "unreviewed_count": len(self.commits),
            "commits": [c.to_dict() for c in self.commits],
        }


def scan(cwd: str, ref: str, state: Dict[str, Any]) -> ScanResult:
    ref_sha = git_utils.resolve_commit_sha(ref, cwd)
    baseline_sha = state["last_ported"]["sha"]

    if baseline_sha != ref_sha and not git_utils.is_ancestor(baseline_sha, ref_sha, cwd):
        raise ScanBoundaryError(
            f"last_ported ({baseline_sha}) is not an ancestor of selected ref "
            f"{ref!r} ({ref_sha}); the two histories have diverged. Run the "
            "`drift` subcommand for a diagnosis before scanning."
        )

    shas = git_utils.rev_list_range(baseline_sha, ref_sha, cwd)
    commits: List[CommitReport] = []
    for sha in shas:
        meta = git_utils.commit_meta(sha, cwd)
        paths = git_utils.changed_paths(sha, cwd)
        record = state["commits"].get(sha, {"status": "pending"})
        commits.append(
            CommitReport(
                sha=meta.sha,
                author_name=meta.author_name,
                author_email=meta.author_email,
                subject=meta.subject,
                author_date=meta.author_date_iso,
                changed_paths=paths,
                categories=classify.classify_paths(paths),
                category_summary=classify.category_summary(paths),
                risk_flags=classify.risk_flags_for_paths(paths),
                status=record.get("status", "pending"),
            )
        )

    return ScanResult(
        ref=ref,
        ref_sha=ref_sha,
        baseline_sha=baseline_sha,
        remote_name=state["remote_name"],
        canonical_upstream_url=state["canonical_upstream_url"],
        commits=commits,
    )


def render_text(result: ScanResult) -> str:
    lines = [
        f"canonical upstream: {result.canonical_upstream_url} (remote {result.remote_name})",
        f"selected ref: {result.ref} @ {result.ref_sha}",
        f"baseline (last_ported): {result.baseline_sha}",
        f"unreviewed commits: {len(result.commits)}",
        "",
    ]
    for c in result.commits:
        lines.append(f"* {c.sha}  [{c.status}]  {c.subject}")
        lines.append(f"    author: {c.author_name} <{c.author_email}>  date: {c.author_date}")
        if c.risk_flags:
            lines.append(f"    risk: {', '.join(c.risk_flags)}")
        lines.append(
            "    paths: "
            + ", ".join(f"{p}[{cat}]" for p, cat in sorted(c.categories.items()))
        )
    return "\n".join(lines) + ("\n" if lines else "")
