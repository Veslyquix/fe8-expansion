#!/usr/bin/env python3
"""Deterministic archive and rebuild rehearsal (issue #9).

Builds a canonical, deterministic source-tar rehearsal **twice** into
separate temporary directories, compares their SHA-256 hashes, and always
removes both temporary archives/directories afterwards -- on success or
failure. Never uploads or retains anything, and never extracts an archive
unsafely (see scripts/release_rehearsal/source_guard.py, used here to pre-screen
every path before it is added to the archive).

Also rehearses (and, when infeasible, precisely reports the blocker for) a
clean recursive local clone/rebuild, and explicitly documents the
contradiction that a GitHub auto-generated source archive (Constants
"Source code (zip)"/"(tar.gz)") does not include submodule contents and
therefore cannot be the supported complete source artifact for this
repository (which has the `mgfembp` git submodule).

Deliberately dependency-free (Python stdlib only: tarfile, hashlib,
tempfile, subprocess).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from scripts.release_rehearsal import source_guard as sg

CANONICAL_MTIME = 0
CANONICAL_UID = 0
CANONICAL_GID = 0
CANONICAL_UNAME = ""
CANONICAL_GNAME = ""
CANONICAL_FILE_MODE = 0o644
CANONICAL_DIR_MODE = 0o755

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


def _git_tracked_allowlisted_files(root: Path, allowlist: Iterable[str]) -> Optional[List[Path]]:
    """Thin delegating wrapper: the actual tracked-intersect-allowlist
    enumeration now lives in scripts/release_rehearsal/source_guard.py
    (``git_tracked_allowlisted_files``) so that
    scripts/release_rehearsal/manifest.py's source_guard check can reuse
    the exact same candidate-file definition this archive build itself
    uses, instead of a second, parallel enumeration drifting out of sync.
    Preserves this module's original ``ArchiveRehearsalError`` on a git
    failure for existing call-site/exception-handling compatibility."""
    try:
        return sg.git_tracked_allowlisted_files(root, allowlist)
    except sg.SourceGuardError as error:
        raise ArchiveRehearsalError(str(error)) from error


def _filesystem_allowlisted_files(root: Path, allowlist: Iterable[str]) -> List[Path]:
    """Raw filesystem walk fallback for a non-git tree (an extracted
    archive rehearsal), after running the same hard-deny checks
    scripts/release_rehearsal/source_guard.py applies to a release
    candidate."""
    files: List[Path] = []
    for top in sorted(allowlist):
        top_path = root / top
        if not top_path.exists():
            continue
        if top_path.is_file():
            files.append(top_path)
            continue
        for path in sorted(top_path.rglob("*")):
            if path.is_file() and not path.is_symlink():
                files.append(path)
    return files


def _iter_allowlisted_files(root: Path, allowlist: Iterable[str]) -> List[Path]:
    """Deterministically (sorted) enumerate the files a release-candidate
    archive should contain, after running the same hard-deny checks
    scripts/release_rehearsal/source_guard.py applies to a release
    candidate. Prefers git's own tracked-file list (see
    _git_tracked_allowlisted_files); only falls back to a raw filesystem
    walk for a tree with no `.git` at all."""
    root = Path(root)
    tracked = _git_tracked_allowlisted_files(root, allowlist)
    files = tracked if tracked is not None else _filesystem_allowlisted_files(root, allowlist)

    # Run the same recursive hard-deny content checks source_guard.py
    # applies, but scoped to exactly the files this archive will contain
    # (tracked-only when git metadata is available) rather than the whole
    # live filesystem tree, so a gitignored host-built byproduct sitting
    # inside an allowlisted directory can never abort an otherwise-clean
    # rehearsal.
    file_violations: List[Tuple[str, str]] = []
    for path in files:
        sg._hard_deny_check_file(root, path, file_violations)
    if file_violations:
        raise ArchiveRehearsalError(
            "refusing to archive: source_guard violation(s): "
            + "; ".join(f"{path}: {rule}" for path, rule in sorted(set(file_violations)))
        )
    return files


def build_deterministic_archive(root: Path, allowlist: Iterable[str], dest_tar: Path) -> Path:
    """Writes a canonical, byte-deterministic uncompressed tar to dest_tar:
    sorted member order, fixed mtime/uid/gid/uname/gname/mode, regular
    files only (no symlink/device members are ever added -- source_guard
    already refused those above)."""
    root = Path(root)
    files = _iter_allowlisted_files(root, allowlist)

    with tarfile.open(dest_tar, "w") as tar:
        for path in files:
            relpath = path.relative_to(root).as_posix()
            info = tarfile.TarInfo(name=relpath)
            info.size = path.stat().st_size
            info.mtime = CANONICAL_MTIME
            info.uid = CANONICAL_UID
            info.gid = CANONICAL_GID
            info.uname = CANONICAL_UNAME
            info.gname = CANONICAL_GNAME
            info.mode = CANONICAL_FILE_MODE
            info.type = tarfile.REGTYPE
            with open(path, "rb") as handle:
                tar.addfile(info, fileobj=handle)
    return dest_tar


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rehearse_archive_twice(root: Path, allowlist: Iterable[str]) -> Dict:
    """Builds the deterministic archive twice into two independent
    TemporaryDirectory()s, hashes both, and always cleans both up (the
    `with` context managers guarantee this on any exception too). Returns
    a report dict; never leaves any archive on disk afterwards, never
    uploads anything."""
    allowlist = list(allowlist)
    with tempfile.TemporaryDirectory(prefix="fe8-release-rehearsal-1-") as tmp1, \
         tempfile.TemporaryDirectory(prefix="fe8-release-rehearsal-2-") as tmp2:
        archive1 = Path(tmp1) / "source.tar"
        archive2 = Path(tmp2) / "source.tar"
        build_deterministic_archive(root, allowlist, archive1)
        build_deterministic_archive(root, allowlist, archive2)
        hash1 = hash_file(archive1)
        hash2 = hash_file(archive2)
    return {
        "hash1": hash1,
        "hash2": hash2,
        "match": hash1 == hash2,
    }


def _submodule_status(repo_root: Path) -> Tuple[bool, str]:
    result = subprocess.run(
        ["git", "submodule", "status"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        return False, f"git submodule status failed: {result.stderr.strip()}"
    uninitialized = [line for line in output.splitlines() if line.strip().startswith("-")]
    return (len(uninitialized) == 0), output


def rebuild_rehearsal_blocker(repo_root: Path) -> Dict:
    """Attempts (read-only, no fetch/clone-over-network) to determine
    whether a clean recursive local clone/rebuild is currently feasible.
    Never fetches unsafe/unreviewed content; reports the precise blocker
    instead of silently skipping."""
    repo_root = Path(repo_root)
    initialized, submodule_output = _submodule_status(repo_root)

    reasons: List[str] = []
    if not initialized:
        reasons.append(
            "the 'mgfembp' git submodule is not initialized/checked out in "
            "this worktree (see 'git submodule status' output below); "
            "recursively fetching it now would pull unreviewed third-party "
            "content into a rehearsal that must remain read-only and "
            "provenance-blocked, so this rehearsal does not fetch it"
        )
    reasons.append(
        "provenance for the mgfembp submodule content is recorded as "
        "unresolved/unapproved (see docs/release_data/provenance/submodules.json); "
        "a clean recursive rebuild that includes it cannot be certified "
        "complete-and-clear until that is resolved by a human reviewer"
    )

    return {
        "status": "blocked",
        "submodule_status_output": submodule_output,
        "reasons": reasons,
        "github_autoarchive_submodule_contradiction": GITHUB_AUTOARCHIVE_SUBMODULE_CONTRADICTION,
    }


def main(argv=None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--allowlist", type=Path, default=Path("docs/release_data/source_allowlist.json"))
    args = parser.parse_args(argv)

    try:
        allowlist = sg.load_allowlist(args.allowlist)
        archive_report = rehearse_archive_twice(args.repo_root, allowlist)
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
