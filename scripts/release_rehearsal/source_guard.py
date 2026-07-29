#!/usr/bin/env python3
"""Source-release guard (issue #9).

A separate, purpose-built safety checker for a *candidate source-release
tree or archive*: an exact top-level allowlist plus recursive hard-deny
rules for prohibited nested content, unsafe paths, and unsafe non-regular
members. This is deliberately independent of, and does not modify or
weaken, ``scripts/artifact_guard.py`` (which governs ordinary tracked-Git
content review, not release-archive safety) -- see
docs/issue-resolution-policy.md and docs/release_process.md.

Deliberately dependency-free (Python stdlib only).

Exit codes (CLI): 0 clean, 1 hard-deny violation(s) found, 2
invocation/I/O error.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Tuple

MAGIC_READ_BYTES = 192
MAGIC_ELF = b"\x7fELF"
MAGIC_IPS = b"PATCH"
MAGIC_UPS = b"UPS1"
MAGIC_BPS = b"BPS1"
MAGIC_PPF = (b"PPF10", b"PPF20", b"PPF30")
MAGIC_VCDIFF = b"\xD6\xC3\xC4"
GBA_LOGO_PREFIX = bytes.fromhex("24ffae51699aa2213d84820a84e409ad")

PROHIBITED_EXTENSIONS = {
    ".gba", ".elf", ".sav", ".srm", ".sa1", ".sa2",
    ".savestate", ".state", ".gpstate",
    ".ips", ".ups", ".bps", ".ppf", ".xdelta", ".xdelta3", ".vcdiff",
}
PROHIBITED_PATH_SEGMENTS = {
    "dump", "extracted", "extractions", "roms", "saves", "savestates", "build",
}


class SourceGuardError(ValueError):
    pass


Violation = Tuple[str, str]


def _is_gba_header(head: bytes) -> bool:
    return len(head) >= 0xB3 and head[4:20] == GBA_LOGO_PREFIX and head[0xB2] == 0x96


def classify_magic(head: bytes):
    if head.startswith(MAGIC_ELF):
        return "prohibited-magic-elf"
    if head.startswith(MAGIC_IPS):
        return "prohibited-magic-ips-patch"
    if head.startswith(MAGIC_UPS):
        return "prohibited-magic-ups-patch"
    if head.startswith(MAGIC_BPS):
        return "prohibited-magic-bps-patch"
    if any(head.startswith(magic) for magic in MAGIC_PPF):
        return "prohibited-magic-ppf-patch"
    if head.startswith(MAGIC_VCDIFF):
        return "prohibited-magic-vcdiff-patch"
    if _is_gba_header(head):
        return "prohibited-magic-gba-header"
    return None


def classify_path_segments(relpath: str) -> List[str]:
    findings = []
    segments = relpath.lower().split("/")
    if any(segment in PROHIBITED_PATH_SEGMENTS for segment in segments):
        findings.append("prohibited-path-segment")
    if any(segment.startswith("baserom") for segment in segments):
        findings.append("prohibited-baserom-path")
    ext = Path(relpath).suffix.lower()
    if ext in PROHIBITED_EXTENSIONS:
        findings.append("prohibited-extension")
    return findings


def is_unsafe_member_name(name: str) -> bool:
    """True for any absolute path, empty component, NUL byte, backslash
    (Windows-style separator smuggling), or ``..`` traversal component."""
    if not name or "\x00" in name or "\\" in name:
        return True
    if name.startswith("/") or name.startswith("~"):
        return True
    parts = PurePosixPath(name).parts
    if any(part in ("..", "") for part in parts):
        return True
    if PurePosixPath(name).is_absolute():
        return True
    return False


def load_allowlist(path: Path) -> List[str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceGuardError(f"{path}: not valid JSON: {error}") from error
    paths = data.get("paths")
    if not isinstance(paths, list) or not paths:
        raise SourceGuardError(f"{path}: must contain a non-empty 'paths' array")
    return list(paths)


def _top_level_component(relpath: str) -> str:
    return relpath.split("/", 1)[0]


def _hard_deny_check_file(root: Path, full: Path, violations: List[Violation]) -> None:
    rel = full.relative_to(root).as_posix()
    try:
        st = full.lstat()
    except OSError as error:
        violations.append((rel, f"stat-failed:{error}"))
        return
    if stat.S_ISLNK(st.st_mode):
        violations.append((rel, "prohibited-symlink"))
        return
    if stat.S_ISDIR(st.st_mode):
        return
    if not stat.S_ISREG(st.st_mode):
        violations.append((rel, "prohibited-non-regular-file"))
        return
    if st.st_nlink > 1:
        violations.append((rel, "prohibited-hardlink"))
    for rule in classify_path_segments(rel):
        violations.append((rel, rule))
    try:
        with open(full, "rb") as handle:
            head = handle.read(MAGIC_READ_BYTES)
    except OSError as error:
        violations.append((rel, f"read-failed:{error}"))
        return
    magic_rule = classify_magic(head)
    if magic_rule:
        violations.append((rel, magic_rule))


def scan_tree(root: Path, allowlist: Iterable[str], closed_world: bool = True) -> List[Violation]:
    """Recursively scan a real filesystem tree (a checkout or an extracted
    rehearsal archive) for hard-deny violations. Never follows symlinks;
    any symlink, device, FIFO, or socket is itself a violation.

    When `closed_world` is True (the default; used to validate an actual
    release candidate tree, which is expected to contain *exactly* the
    allowlisted top-level entries and nothing else), any top-level entry
    not in `allowlist` is itself reported as a "not-allowlisted" violation.
    When False (used internally by scripts/release_rehearsal/archive_rehearsal.py to
    build an archive out of a live, possibly-messy development worktree
    that may contain gitignored build output alongside the real source),
    only the allowlisted top-level entries -- and their descendants -- are
    walked and hard-deny-checked at all; anything else present in `root`
    is silently irrelevant, since it is never going to be added to the
    archive in the first place."""
    root = Path(root)
    allowlist = set(allowlist)
    violations: List[Violation] = []

    if closed_world:
        top_entries = sorted(p.name for p in root.iterdir())
        for name in top_entries:
            if name == ".git":
                continue
            if name not in allowlist:
                violations.append((name, "not-allowlisted"))
        walk_roots = [root]
    else:
        walk_roots = [root / name for name in sorted(allowlist) if (root / name).exists()]

    for walk_root in walk_roots:
        for dirpath, dirnames, filenames in os.walk(walk_root, followlinks=False):
            dirnames[:] = [d for d in sorted(dirnames) if not (Path(dirpath) == root and d == ".git")]
            for name in sorted(dirnames) + sorted(filenames):
                _hard_deny_check_file(root, Path(dirpath) / name, violations)

    return sorted(set(violations))

def scan_archive_members(tar: "tarfile.TarFile", allowlist: Iterable[str]) -> List[Violation]:
    """Scan a tar archive's members without ever extracting anything to
    disk (uses TarFile.extractfile() for read-only content access only)."""
    allowlist = set(allowlist)
    violations: List[Violation] = []
    for member in tar.getmembers():
        name = member.name
        if is_unsafe_member_name(name):
            violations.append((name, "unsafe-member-name"))
            continue
        if member.issym() or member.islnk():
            violations.append((name, "prohibited-link-member"))
            continue
        if member.ischr() or member.isblk() or member.isfifo() or member.isdev():
            violations.append((name, "prohibited-device-member"))
            continue
        if not (member.isreg() or member.isdir()):
            violations.append((name, "prohibited-non-regular-member"))
            continue
        top = _top_level_component(name)
        if top not in allowlist:
            violations.append((name, "not-allowlisted"))
        if member.isdir():
            continue
        for rule in classify_path_segments(name):
            violations.append((name, rule))
        handle = tar.extractfile(member)
        if handle is None:
            violations.append((name, "unreadable-member"))
            continue
        head = handle.read(MAGIC_READ_BYTES)
        magic_rule = classify_magic(head)
        if magic_rule:
            violations.append((name, magic_rule))
    return sorted(set(violations))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tree", type=Path, help="scan a real filesystem tree")
    group.add_argument("--archive", type=Path, help="scan a tar archive's members")
    parser.add_argument("--allowlist", type=Path, default=Path("docs/release_data/source_allowlist.json"))
    args = parser.parse_args(argv)

    try:
        allowlist = load_allowlist(args.allowlist)
        if args.tree:
            violations = scan_tree(args.tree, allowlist)
        else:
            with tarfile.open(args.archive, "r") as tar:
                violations = scan_archive_members(tar, allowlist)
    except (SourceGuardError, OSError, tarfile.TarError) as error:
        print(f"source_guard: {error}", file=sys.stderr)
        return 2

    for path, rule in violations:
        print(f"{path}: {rule}")
    if violations:
        print(f"source_guard: {len(violations)} finding(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
