#!/usr/bin/env python3
"""Deterministic archive and rebuild rehearsal (issue #9).

Builds a canonical, deterministic source-tar rehearsal **twice** into
separate temporary directories, compares their SHA-256 hashes, and always
removes both temporary archives/directories afterwards -- on success or
failure. Never uploads or retains anything, and never extracts an archive
unsafely (see scripts/release_rehearsal/source_guard.py, used here to pre-screen
every path before it is added to the archive).

**Immutable, HEAD-bound archive inputs.** When `root` is a real Git
working tree, every byte that goes into the archive is read exclusively
through Git plumbing (`scripts/release_rehearsal/git_source.py`'s
`git ls-tree`/`git cat-file --batch` wrappers), keyed to an exact,
resolved commit SHA -- **never** by opening the file at its worktree path.
A tracked file edited on disk (or even `git add`ed) without being
committed therefore cannot change one single byte of the archive: the
archive is bound to the commit, not the checkout. Only when `root` has no
`.git` at all (a genuine already-extracted archive/non-git candidate
tree -- the tree *is* the candidate, not a development worktree with
byproducts alongside it) does this fall back to a raw filesystem walk of
exactly the allowlisted entries.

Also rehearses (and, when infeasible, precisely reports the blocker for) a
clean recursive local clone/rebuild, and explicitly documents the
contradiction that a GitHub auto-generated source archive (Constants
"Source code (zip)"/"(tar.gz)") does not include submodule contents and
therefore cannot be the supported complete source artifact for this
repository (which has the `mgfembp` git submodule). The rebuild rehearsal
never describes a rebuild as proved when it was not actually executed --
see `REBUILD_STATUS_*` below.

Deliberately dependency-free (Python stdlib only: tarfile, hashlib,
tempfile, subprocess, shutil).
"""

from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Optional, Tuple

from scripts.release_rehearsal import git_source as gs
from scripts.release_rehearsal import provenance as prov
from scripts.release_rehearsal import source_guard as sg

CANONICAL_MTIME = 0
CANONICAL_UID = 0
CANONICAL_GID = 0
CANONICAL_UNAME = ""
CANONICAL_GNAME = ""
CANONICAL_FILE_MODE = 0o644
CANONICAL_DIR_MODE = 0o755

# Rebuild rehearsal machine states (issue #9 verifier remediation): every
# one of these is a *distinct*, never-conflated outcome -- in particular,
# "verified_success" is only ever returned after `run_build_twice` has
# genuinely executed a build command twice and compared its outputs; nothing
# in this module ever reports success for a rebuild that was not run.
REBUILD_STATUS_NOT_RUN = "not_run"
REBUILD_STATUS_BLOCKED = "blocked"
REBUILD_STATUS_FAILED = "failed"
REBUILD_STATUS_VERIFIED_SUCCESS = "verified_success"
ALL_REBUILD_STATUSES = (
    REBUILD_STATUS_NOT_RUN, REBUILD_STATUS_BLOCKED, REBUILD_STATUS_FAILED,
    REBUILD_STATUS_VERIFIED_SUCCESS,
)

GITHUB_AUTOARCHIVE_SUBMODULE_CONTRADICTION = (
    "GitHub's auto-generated 'Source code (zip)'/'Source code (tar.gz)' "
    "release/repo archives are produced from the tree alone and never "
    "include submodule contents (the 'mgfembp' path stays an empty "
    "directory in that archive, not the pinned "
    "c87e74dcd6c8878b809e013cd8ff0c52baa75332 checkout) -- so that "
    "auto-generated archive can never be the supported, complete source "
    "artifact for this repository. A complete rehearsal/rebuild instead "
    "requires an explicit 'git archive' plus a separately fetched, "
    "license-cleared submodule checkout (or 'git clone --recurse-"
    "submodules'), which this module attempts and reports the precise "
    "blocker for below when unavailable."
)


class ArchiveRehearsalError(ValueError):
    pass


def _filesystem_allowlisted_files(root: Path, allowlist: Iterable[str]) -> List[Path]:
    """Raw filesystem walk fallback for a non-git tree (an extracted
    archive rehearsal or other genuine non-git candidate), after running
    the same hard-deny checks scripts/release_rehearsal/source_guard.py
    applies to a release candidate. Every entry in `allowlist` is matched
    **exactly** (issue #9 verifier remediation): only a real, ordinary
    file whose own path is itself an allowlist entry is ever included --
    there is no directory-entry-expands-to-its-full-contents rule any
    more. A directory that happens to share its name with an allowlist
    entry (e.g. the `mgfembp` submodule mountpoint, whose *contents* are
    never enumerated -- see docs/release_process.md's submodule/
    provenance boundary) contributes nothing here; it is a structural
    parent only, never an authorization prefix for whatever might be
    sitting inside it on disk."""
    files: List[Path] = []
    for entry in sorted(allowlist):
        entry_path = root / entry
        if entry_path.is_file() and not entry_path.is_symlink():
            files.append(entry_path)
    return files


def _hard_deny_check_git_entry(
    entry: gs.GitEntry,
    data: bytes,
    violations: List[Tuple[str, str]],
    map_hex_exceptions: FrozenSet[str] = frozenset(),
) -> None:
    """The git-blob-content equivalent of source_guard.py's
    `_hard_deny_check_file`: same path/extension/magic rules, applied to
    bytes read from an immutable git blob instead of a worktree path.
    A tracked hardlink has no meaning for a content-addressed git blob
    (two paths sharing identical content is normal/expected in git, not a
    filesystem hazard), so that specific check does not apply here."""
    rel = entry.path
    if sg.is_unsafe_member_name(rel):
        violations.append((rel, "unsafe-member-name"))
        return
    if entry.is_symlink:
        violations.append((rel, "prohibited-symlink"))
        return
    if not entry.is_safe_blob:
        violations.append((rel, "prohibited-non-regular-file"))
        return
    for rule in sg.classify_path_segments(rel, map_hex_exceptions):
        violations.append((rel, rule))
    magic_rule = sg.classify_magic(data[: sg.MAGIC_READ_BYTES])
    if magic_rule:
        violations.append((rel, magic_rule))


def _resolve_map_hex_exceptions(root: Path, map_hex_exceptions: Optional[FrozenSet[str]]) -> FrozenSet[str]:
    """`None` (the default everywhere below) means "auto-resolve": load
    `docs/release_data/map_hex_exceptions.json` relative to `root` if it
    exists, else fall back to no exceptions at all. This exists so a real
    caller (the CLI, a Makefile target, or a test against this actual
    repository) can never *forget* to thread the exceptions file through
    and thereby spuriously refuse to archive the 12 legitimate synthetic
    `.map`/`.hex` test fixtures -- passing an explicit (possibly empty)
    `frozenset`/set still always wins outright, unchanged, for a
    synthetic/throwaway tree that has no such file at all."""
    if map_hex_exceptions is not None:
        return frozenset(map_hex_exceptions)
    default_path = Path(root) / "docs" / "release_data" / "map_hex_exceptions.json"
    if default_path.is_file():
        return sg.load_map_hex_exceptions(default_path)
    return frozenset()


def _iter_archive_contents(
    root: Path,
    allowlist: Iterable[str],
    target_sha: Optional[str] = None,
    map_hex_exceptions: Optional[FrozenSet[str]] = None,
) -> Tuple[List[Tuple[str, bytes]], Optional[str]]:
    """Resolves the exact, immutable archive content: a sorted list of
    `(relpath, data_bytes)` pairs, after applying every hard-deny rule
    across the *entire* candidate set first (never a partial archive is
    silently produced when only some files violate a rule). Raises
    `ArchiveRehearsalError` (refusing to archive anything at all) if any
    violation is found anywhere.

    Returns `(contents, resolved_target_sha)` -- `resolved_target_sha` is
    the exact commit this content is bound to when `root` is a real git
    repository (always non-None in that case, even if the caller did not
    pass one explicitly -- HEAD is resolved once, here), or None for a
    non-git candidate tree (see module docstring's "Immutable, HEAD-bound
    archive inputs")."""
    root = Path(root)
    allowlist_set = set(allowlist)
    map_hex_exceptions = _resolve_map_hex_exceptions(root, map_hex_exceptions)
    violations: List[Tuple[str, str]] = []
    contents: List[Tuple[str, bytes]] = []
    resolved_target_sha: Optional[str] = None

    if gs.is_git_repo(root):
        try:
            resolved_target_sha = target_sha if target_sha is not None else gs.resolve_sha(root, "HEAD")
            entries = sorted(
                (
                    entry for entry in gs.list_tree(root, resolved_target_sha)
                    if entry.path in allowlist_set and not entry.is_gitlink
                ),
                key=lambda entry: entry.path,
            )
            with gs.GitBatchBlobReader(root) as reader:
                fetched = [(entry, reader.read(entry.object_id)) for entry in entries]
        except gs.GitSourceError as error:
            raise ArchiveRehearsalError(str(error)) from error
        for entry, data in fetched:
            _hard_deny_check_git_entry(entry, data, violations, map_hex_exceptions)
        if not violations:
            contents = [(entry.path, data) for entry, data in fetched]
    else:
        paths = _filesystem_allowlisted_files(root, allowlist_set)
        for path in paths:
            sg._hard_deny_check_file(root, path, violations, map_hex_exceptions)
        if not violations:
            contents = [(path.relative_to(root).as_posix(), path.read_bytes()) for path in paths]

    if violations:
        raise ArchiveRehearsalError(
            "refusing to archive: source_guard violation(s): "
            + "; ".join(f"{path}: {rule}" for path, rule in sorted(set(violations)))
        )
    return contents, resolved_target_sha


def build_deterministic_archive(
    root: Path,
    allowlist: Iterable[str],
    dest_tar: Path,
    target_sha: Optional[str] = None,
    map_hex_exceptions: Optional[FrozenSet[str]] = None,
) -> Path:
    """Writes a canonical, byte-deterministic uncompressed tar to dest_tar:
    sorted member order, fixed mtime/uid/gid/uname/gname/mode, regular
    files only (no symlink/device members are ever added -- source_guard
    already refused those above). Content is immutable/HEAD-bound -- see
    `_iter_archive_contents`."""
    contents, _ = _iter_archive_contents(root, allowlist, target_sha, map_hex_exceptions)
    with tarfile.open(dest_tar, "w") as tar:
        for relpath, data in contents:
            info = tarfile.TarInfo(name=relpath)
            info.size = len(data)
            info.mtime = CANONICAL_MTIME
            info.uid = CANONICAL_UID
            info.gid = CANONICAL_GID
            info.uname = CANONICAL_UNAME
            info.gname = CANONICAL_GNAME
            info.mode = CANONICAL_FILE_MODE
            info.type = tarfile.REGTYPE
            tar.addfile(info, io.BytesIO(data))
    return dest_tar


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rehearse_archive_twice(
    root: Path,
    allowlist: Iterable[str],
    target_sha: Optional[str] = None,
    map_hex_exceptions: Optional[FrozenSet[str]] = None,
) -> Dict:
    """Builds the deterministic archive twice into two independent
    TemporaryDirectory()s, hashes both, and always cleans both up (the
    `with` context managers guarantee this on any exception too). Returns
    a report dict; never leaves any archive on disk afterwards, never
    uploads anything.

    Both builds are bound to the exact same resolved commit SHA (resolved
    **once**, here, before either build runs) so this is a true
    apples-to-apples repeat of "archive this exact commit", not two
    separate HEAD look-ups that could theoretically race against a
    concurrent commit."""
    root = Path(root)
    allowlist = list(allowlist)
    resolved_target_sha: Optional[str] = None
    if gs.is_git_repo(root):
        try:
            resolved_target_sha = target_sha if target_sha is not None else gs.resolve_sha(root, "HEAD")
        except gs.GitSourceError as error:
            raise ArchiveRehearsalError(str(error)) from error

    with tempfile.TemporaryDirectory(prefix="fe8-release-rehearsal-1-") as tmp1, \
         tempfile.TemporaryDirectory(prefix="fe8-release-rehearsal-2-") as tmp2:
        archive1 = Path(tmp1) / "source.tar"
        archive2 = Path(tmp2) / "source.tar"
        build_deterministic_archive(root, allowlist, archive1, resolved_target_sha, map_hex_exceptions)
        build_deterministic_archive(root, allowlist, archive2, resolved_target_sha, map_hex_exceptions)
        hash1 = hash_file(archive1)
        hash2 = hash_file(archive2)
    return {
        "hash1": hash1,
        "hash2": hash2,
        "match": hash1 == hash2,
        "target_sha": resolved_target_sha,
    }


# --- Rebuild rehearsal: eligibility, then (only if eligible) a real,
# executed double-build comparison ------------------------------------------


def _submodule_status_output(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "submodule", "status"], cwd=str(repo_root), capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ArchiveRehearsalError(f"git submodule status failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _parse_submodule_status(status_output: str, submodule_path: str) -> Tuple[Optional[str], str]:
    """Parses one `git submodule status` line for `submodule_path`.
    Returns `(checked_out_sha_or_None, indicator)` where indicator is one
    of ``" "`` (in sync), ``"-"`` (not initialized), ``"+"`` (checked-out
    commit differs from the superproject's recorded gitlink), or ``"U"``
    (merge conflict); `(None, "?")` if `submodule_path` has no status line
    at all (e.g. not a submodule)."""
    for line in status_output.splitlines():
        if not line:
            continue
        indicator = line[0] if line[0] in "-+U" else " "
        body = line[1:] if line[0] in "-+U" else line
        parts = body.split()
        if len(parts) >= 2 and parts[1] == submodule_path:
            return parts[0], indicator
    return None, "?"


def evaluate_rebuild_eligibility(
    repo_root: Path,
    submodule_path: str = "mgfembp",
    provenance_dir: Optional[Path] = None,
) -> Tuple[bool, Dict]:
    """Read-only (never fetches/initializes/approves anything) check of
    whether a clean recursive rebuild involving `submodule_path` is even
    *eligible* to attempt: the submodule must be (1) initialized/checked
    out, (2) at exactly its provenance-pinned commit, and (3) recorded
    with `redistribution_approved: true`. All three must hold -- this
    function only ever *reads* `docs/release_data/provenance/*.json` and
    `git submodule status`; it never writes, fetches, or flips any of
    them itself."""
    repo_root = Path(repo_root)
    provenance_dir = Path(provenance_dir) if provenance_dir else repo_root / "docs" / "release_data" / "provenance"
    status_output = _submodule_status_output(repo_root)
    checked_out_sha, indicator = _parse_submodule_status(status_output, submodule_path)
    initialized = indicator == " " or indicator == "+"

    reasons: List[str] = []
    if not initialized:
        reasons.append(
            f"the '{submodule_path}' git submodule is not initialized/checked out in this "
            f"worktree (see 'git submodule status' output); recursively fetching it now would "
            "pull unreviewed third-party content into a rehearsal that must remain read-only "
            "and provenance-blocked, so this rehearsal does not fetch it"
        )

    pinned_commit: Optional[str] = None
    approved = False
    try:
        entries = prov.load_all(provenance_dir)
    except prov.ProvenanceError:
        entries = []
    matches = [entry for entry in entries if entry.get("path") == submodule_path]
    if not matches:
        reasons.append(f"no provenance entry recorded for '{submodule_path}' in {provenance_dir}")
    else:
        pinned_commit = matches[0].get("pinned_commit")
        approved = bool(matches[0].get("redistribution_approved"))
        if not approved:
            reasons.append(
                f"provenance for the '{submodule_path}' submodule content is recorded as "
                "unresolved/unapproved (redistribution_approved: false); a clean recursive "
                "rebuild that includes it cannot be certified complete-and-clear until that is "
                "resolved by a human reviewer"
            )

    identity_ok = True
    if initialized and pinned_commit and checked_out_sha and checked_out_sha != pinned_commit:
        identity_ok = False
        reasons.append(
            f"'{submodule_path}' checked-out commit {checked_out_sha!r} does not match the "
            f"provenance-pinned commit {pinned_commit!r} -- refusing to treat this as the "
            "reviewed, pinned submodule identity"
        )
    if indicator == "U":
        identity_ok = False
        reasons.append(f"'{submodule_path}' has an unresolved merge conflict in 'git submodule status'")

    eligible = initialized and approved and identity_ok
    return eligible, {
        "submodule_status_output": status_output,
        "submodule_initialized": initialized,
        "submodule_checked_out_sha": checked_out_sha,
        "provenance_pinned_commit": pinned_commit,
        "provenance_redistribution_approved": approved,
        "identity_matches_pinned": identity_ok,
        "reasons": reasons,
    }


def run_build_twice(
    build_command: List[str],
    source_dir: Path,
    output_relpaths: List[str],
    env: Optional[Dict[str, str]] = None,
) -> Dict:
    """The actual, executable "run a build command twice and compare its
    declared outputs" mechanism -- never a mocked boolean. Each run copies
    `source_dir` into its own fresh temporary directory first (so the two
    runs cannot see each other's leftover state or share any mutable
    output directory), then invokes `build_command` via `subprocess.run`
    with that copy as the working directory, then SHA-256-hashes every
    path in `output_relpaths` that exists afterwards. `match` is True only
    if both runs exit `0` and every declared output exists and is
    byte-identical between the two runs."""

    def _one_run() -> Tuple[int, str, str, Dict[str, Optional[str]]]:
        with tempfile.TemporaryDirectory(prefix="fe8-rebuild-run-") as run_dir:
            run_root = Path(run_dir) / "src"
            shutil.copytree(source_dir, run_root)
            result = subprocess.run(
                build_command, cwd=str(run_root), capture_output=True, text=True, env=env,
            )
            hashes: Dict[str, Optional[str]] = {}
            for relpath in output_relpaths:
                out_path = run_root / relpath
                hashes[relpath] = hash_file(out_path) if out_path.is_file() else None
            return result.returncode, result.stdout, result.stderr, hashes

    returncode1, _stdout1, stderr1, hashes1 = _one_run()
    returncode2, _stdout2, stderr2, hashes2 = _one_run()

    outputs_present = (
        bool(output_relpaths)
        and all(value is not None for value in hashes1.values())
        and all(value is not None for value in hashes2.values())
    )
    match = returncode1 == 0 and returncode2 == 0 and outputs_present and hashes1 == hashes2
    return {
        "returncode1": returncode1,
        "returncode2": returncode2,
        "hashes1": hashes1,
        "hashes2": hashes2,
        "outputs_present": outputs_present,
        "match": match,
        "stderr1_tail": stderr1[-2000:],
        "stderr2_tail": stderr2[-2000:],
    }


def rebuild_rehearsal_blocker(
    repo_root: Path,
    attempt_build: bool = True,
    build_command: Optional[List[str]] = None,
    output_relpaths: Optional[List[str]] = None,
) -> Dict:
    """Truthful, machine-distinct rebuild rehearsal report. `status` is
    always exactly one of `ALL_REBUILD_STATUSES`:

    * `"blocked"` -- not even eligible to attempt (submodule uninitialized
      and/or unapproved and/or identity mismatch) -- today's real result
      for this repository, and expected to remain so until a human
      resolves `docs/release_data/provenance/submodules.json`.
    * `"not_run"` -- eligible, but no actual build was executed (either
      the caller passed `attempt_build=False`, or did not supply the
      `build_command`/`output_relpaths` a real attempt requires) --
      distinct from `"blocked"` so a report can never conflate "we
      refused to even try" with "we tried and it worked".
    * `"failed"` -- a build was actually attempted (`run_build_twice`) and
      either run exited non-zero, an output was missing, or the two runs'
      output hashes disagreed.
    * `"verified_success"` -- both runs actually executed, both exited 0,
      and every declared output was present and byte-identical.

    Never fetches/initializes/approves the submodule itself; see
    `evaluate_rebuild_eligibility`."""
    repo_root = Path(repo_root)
    eligible, eligibility_report = evaluate_rebuild_eligibility(repo_root)
    base_report = {
        "submodule_status_output": eligibility_report["submodule_status_output"],
        "eligibility": eligibility_report,
        "github_autoarchive_submodule_contradiction": GITHUB_AUTOARCHIVE_SUBMODULE_CONTRADICTION,
    }

    if not eligible:
        return {"status": REBUILD_STATUS_BLOCKED, "reasons": eligibility_report["reasons"], **base_report}

    if not attempt_build or not build_command or not output_relpaths:
        return {
            "status": REBUILD_STATUS_NOT_RUN,
            "reasons": [
                "eligible (submodule initialized, identity-matched, and provenance-approved), "
                "but no actual rebuild was executed: " + (
                    "the caller explicitly requested attempt_build=False"
                    if not attempt_build else
                    "no explicit --build-command/--output-paths was supplied for the real "
                    "pinned rebuild attempt"
                )
            ],
            **base_report,
        }

    build_result = run_build_twice(build_command, repo_root, output_relpaths)
    status = REBUILD_STATUS_VERIFIED_SUCCESS if build_result["match"] else REBUILD_STATUS_FAILED
    reasons = [] if status == REBUILD_STATUS_VERIFIED_SUCCESS else [
        "the pinned recursive rebuild was executed but did not reproduce verified-identical "
        "outputs twice -- see 'build_result' for the exact returncodes/hashes"
    ]
    return {"status": status, "reasons": reasons, "build_result": build_result, **base_report}


def main(argv=None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--allowlist", type=Path, default=Path("docs/release_data/source_allowlist.json"))
    parser.add_argument(
        "--map-hex-exceptions", type=Path,
        default=Path("docs/release_data/map_hex_exceptions.json"),
    )
    args = parser.parse_args(argv)

    try:
        allowlist = sg.load_allowlist(args.allowlist)
        map_hex_exceptions = (
            sg.load_map_hex_exceptions(args.map_hex_exceptions)
            if args.map_hex_exceptions.is_file() else frozenset()
        )
        archive_report = rehearse_archive_twice(args.repo_root, allowlist, map_hex_exceptions=map_hex_exceptions)
    except (sg.SourceGuardError, ArchiveRehearsalError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    rebuild_report = rebuild_rehearsal_blocker(args.repo_root)

    report = {"archive": archive_report, "rebuild": rebuild_report}
    print(json.dumps(report, indent=2, sort_keys=True))

    if not archive_report["match"]:
        print("error: two rehearsal archive builds produced different hashes", file=sys.stderr)
        return 2

    print("archive rehearsal: two independent builds match (deterministic)", file=sys.stderr)
    print(f"rebuild rehearsal: {rebuild_report['status']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
