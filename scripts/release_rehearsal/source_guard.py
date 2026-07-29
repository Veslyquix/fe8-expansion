#!/usr/bin/env python3
"""Source-release guard (issue #9).

A separate, purpose-built safety checker for a *candidate source-release
tree or archive*: an exact, deterministic per-member allowlist
(``docs/release_data/source_allowlist.json`` -- every regular tracked file
and the ``mgfembp`` submodule gitlink is individually, explicitly listed;
there is no "top-level directory implies everything under it" rule any
more) plus recursive hard-deny rules for prohibited nested content, unsafe
paths, and unsafe non-regular members. This is deliberately independent
of, and does not modify or weaken, ``scripts/artifact_guard.py`` (which
governs ordinary tracked-Git content review, not release-archive safety)
-- see docs/issue-resolution-policy.md and docs/release_process.md.

``scan_tree(..., closed_world=True)`` is the fail-closed check for an
actual, already-materialized release candidate (a genuine extracted
archive/non-git tree): every top-level entry must be covered by the
allowlist and everything is walked. A *live git development worktree* is
not that -- it routinely contains gitignored/untracked build byproducts
alongside the real source -- so ``scan_source_release_candidate()``
instead evaluates exactly the git-tracked-intersect-allowlist candidate
set that ``scripts/release_rehearsal/archive_rehearsal.py`` itself would
archive (``git_tracked_allowlisted_files()``), applying every hard-deny
rule to that exact set, and transparently falls back to the closed-world
``scan_tree`` check when there is no ``.git`` at all. This is what
``scripts/release_rehearsal/manifest.py``'s source_guard check uses, so a
manifest built against the live worktree is deterministic and
host-state-independent while a manifest built against a genuine extracted
archive still fails closed.

Hard-deny coverage (path/extension and file-magic, independent of each
other -- a misleading extension never hides prohibited content, and a
"safe" extension never excuses prohibited magic bytes):

* object/library/executable/debug-symbol artifacts: ``.o .obj .a .lib
  .so`` (including versioned/shared variants like ``.so.1.2.3``) ``.dll
  .dylib .exe .elf .pdb`` and ``.dSYM`` debug-symbol bundles;
* generic archive/compression containers, including Java/JVM archive
  variants: ``.zip .jar .war .ear .tar .tar.gz .tgz .gz .bz2 .xz .7z
  .rar``;
* GBA ROM/save-state/patch artifacts (pre-existing): ``.gba .elf .sav
  .srm .sa1 .sa2 .savestate .state .gpstate .ips .ups .bps .ppf .xdelta
  .xdelta3 .vcdiff``;
* arbitrary build ``.map``/``.hex`` output -- denied by default; the
  *only* way a ``.map``/``.hex`` path is ever accepted is an exact,
  file-level entry in ``docs/release_data/map_hex_exceptions.json`` with a
  recorded factual rationale (see ``load_map_hex_exceptions`` below) --
  there is no directory-level or extension-level carve-out.

File-magic detection (``classify_magic``) is content-based and applies
regardless of extension or nesting depth, so a prohibited archive/
executable smuggled under an innocuous name or nested arbitrarily deep
inside an otherwise-allowlisted directory is still caught: ELF, PE
(``MZ``)/Mach-O executables, Java ``.class``/Mach-O fat-binary
(``CAFEBABE``), ZIP (including JAR/WAR/EAR, which are ZIP files), Unix
``ar`` (``.a``/``.lib``/``.deb``), gzip, bzip2, xz, 7z, rar, zstd, POSIX/
GNU ``tar`` (``ustar`` magic at offset 257), and the pre-existing GBA ROM
header/patch-format magics.

Deliberately dependency-free (Python stdlib only).

Exit codes (CLI): 0 clean, 1 hard-deny violation(s) found, 2
invocation/I/O error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import FrozenSet, Iterable, List, Optional, Tuple

# 265 bytes is the minimum needed to see a POSIX/GNU tar "ustar" magic
# (offset 257..262); round up generously so future magic additions never
# need to revisit this constant.
MAGIC_READ_BYTES = 512

MAGIC_ELF = b"\x7fELF"
MAGIC_IPS = b"PATCH"
MAGIC_UPS = b"UPS1"
MAGIC_BPS = b"BPS1"
MAGIC_PPF = (b"PPF10", b"PPF20", b"PPF30")
MAGIC_VCDIFF = b"\xD6\xC3\xC4"
GBA_LOGO_PREFIX = bytes.fromhex("24ffae51699aa2213d84820a84e409ad")

# --- Archive/executable magics (issue #9 verifier remediation) -------------
MAGIC_ZIP = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")  # also JAR/WAR/EAR
MAGIC_UNIX_AR = b"!<arch>\n"  # also .deb, .lib import libraries
MAGIC_GZIP = b"\x1f\x8b"
MAGIC_BZIP2 = b"BZh"
MAGIC_XZ = b"\xfd7zXZ\x00"
MAGIC_7Z = b"7z\xbc\xaf\x27\x1c"
MAGIC_RAR = (b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00")
MAGIC_ZSTD = b"\x28\xb5\x2f\xfd"
MAGIC_PE = b"MZ"  # Windows .exe/.dll (DOS/PE header)
MAGIC_MACHO = (
    b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",  # 32/64-bit, big-endian host
    b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",  # 32/64-bit, little-endian host
)
MAGIC_CAFEBABE = b"\xca\xfe\xba\xbe"  # Mach-O fat binary, or Java .class
TAR_USTAR_OFFSET = 257
TAR_USTAR_MAGIC = b"ustar"

PROHIBITED_EXTENSIONS = {
    # GBA ROM / save-state / patch formats (pre-existing).
    ".gba", ".elf", ".sav", ".srm", ".sa1", ".sa2",
    ".savestate", ".state", ".gpstate",
    ".ips", ".ups", ".bps", ".ppf", ".xdelta", ".xdelta3", ".vcdiff",
    # Object/library/executable/debug artifacts.
    ".o", ".obj", ".a", ".lib", ".so", ".dll", ".dylib", ".exe", ".pdb",
    ".dsym",
    # Generic archive/compression containers (incl. Java/JVM variants).
    ".zip", ".jar", ".war", ".ear", ".tar", ".tgz", ".gz", ".bz2", ".xz",
    ".7z", ".rar",
    # Arbitrary build linker-map/hex-dump output -- default-deny; the only
    # carve-out is an exact file-level docs/release_data/map_hex_exceptions.json entry.
    ".map", ".hex",
}
PROHIBITED_PATH_SEGMENTS = {
    "dump", "extracted", "extractions", "roms", "saves", "savestates", "build",
}

# `libfoo.so.1`, `libfoo.so.1.2.3`, etc: a trailing numeric version suffix
# after `.so` is still the same prohibited shared-object artifact even
# though `Path.suffix` alone would only ever see the final `.1`/`.3` part.
_VERSIONED_SHARED_OBJECT_RE = re.compile(r"\.so(\.[0-9]+)+$", re.IGNORECASE)
# A macOS debug-symbol bundle is a *directory* named e.g. "foo.dSYM"; the
# extension check above only catches a literal file named "*.dsym", so
# also match the bundle directory name as a path segment.
_DSYM_SEGMENT_RE = re.compile(r".*\.dsym$", re.IGNORECASE)


class SourceGuardError(ValueError):
    pass


Violation = Tuple[str, str]


def _is_gba_header(head: bytes) -> bool:
    return len(head) >= 0xB3 and head[4:20] == GBA_LOGO_PREFIX and head[0xB2] == 0x96


def _is_tar_magic(head: bytes) -> bool:
    end = TAR_USTAR_OFFSET + len(TAR_USTAR_MAGIC)
    return len(head) >= end and head[TAR_USTAR_OFFSET:end] == TAR_USTAR_MAGIC


def classify_magic(head: bytes):
    """Content-based (never extension-based) classification of the first
    `MAGIC_READ_BYTES` of a file. Every branch here is a *high-confidence*
    signature check (a fixed magic byte sequence at a fixed offset), never
    a heuristic/probabilistic guess -- so this never flags an ordinary
    source text file, and never misses a nested archive/executable smuggled
    under a misleading extension."""
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
    if any(head.startswith(magic) for magic in MAGIC_ZIP):
        return "prohibited-magic-zip-archive"
    if head.startswith(MAGIC_UNIX_AR):
        return "prohibited-magic-unix-ar-archive"
    if head.startswith(MAGIC_GZIP):
        return "prohibited-magic-gzip"
    if head.startswith(MAGIC_BZIP2):
        return "prohibited-magic-bzip2"
    if head.startswith(MAGIC_XZ):
        return "prohibited-magic-xz"
    if head.startswith(MAGIC_7Z):
        return "prohibited-magic-7z"
    if any(head.startswith(magic) for magic in MAGIC_RAR):
        return "prohibited-magic-rar"
    if head.startswith(MAGIC_ZSTD):
        return "prohibited-magic-zstd"
    if head.startswith(MAGIC_CAFEBABE):
        return "prohibited-magic-macho-or-java-class"
    if any(head.startswith(magic) for magic in MAGIC_MACHO):
        return "prohibited-magic-macho-executable"
    if head.startswith(MAGIC_PE):
        return "prohibited-magic-pe-executable"
    if _is_tar_magic(head):
        return "prohibited-magic-tar-archive"
    return None


def classify_path_segments(relpath: str, map_hex_exceptions: FrozenSet[str] = frozenset()) -> List[str]:
    """Path/extension-based classification. `map_hex_exceptions` is the
    exact set of repo-relative paths (matching
    docs/release_data/map_hex_exceptions.json) that are permitted to keep
    a `.map`/`.hex` extension; every other `.map`/`.hex` path -- and every
    path in `map_hex_exceptions` for any *other* prohibited reason -- is
    still denied exactly as before."""
    findings = []
    segments = relpath.lower().split("/")
    if any(segment in PROHIBITED_PATH_SEGMENTS for segment in segments):
        findings.append("prohibited-path-segment")
    if any(segment.startswith("baserom") for segment in segments):
        findings.append("prohibited-baserom-path")
    if any(_DSYM_SEGMENT_RE.match(segment) for segment in segments):
        findings.append("prohibited-debug-symbol-bundle")
    name = PurePosixPath(relpath).name
    if _VERSIONED_SHARED_OBJECT_RE.search(name):
        findings.append("prohibited-versioned-shared-object")
    ext = Path(relpath).suffix.lower()
    if ext in (".map", ".hex"):
        if relpath not in map_hex_exceptions:
            findings.append("prohibited-extension")
    elif ext in PROHIBITED_EXTENSIONS:
        findings.append("prohibited-extension")
    return findings


def is_unsafe_member_name(name: str) -> bool:
    """True for any absolute path, ``..``-traversal component, literal
    ``.`` component, empty component (including a leading/trailing/double
    slash, which all produce one), NUL/other-control-character byte, or
    backslash (Windows-style separator smuggling).

    Deliberately implemented as one uniform "split on '/' and inspect
    every component" rule rather than a growing list of special cases for
    each individual pattern (absolute path, ``a//b``, ``a/./b``, trailing
    slash, ...): every one of those unsafe shapes reduces to either a
    literal ``.``/``..`` component or an *empty* component once the raw
    string (never a library path type that silently normalizes repeated
    slashes away) is split on ``/``, so a single check catches all of
    them, including combinations no one has thought to special-case yet.
    """
    if not isinstance(name, str) or not name:
        return True
    if "\x00" in name or "\\" in name:
        return True
    if any(ord(ch) < 0x20 for ch in name):
        return True
    if name.startswith("~"):
        return True
    parts = name.split("/")
    if any(part in ("..", ".", "") for part in parts):
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


def load_map_hex_exceptions(path: Path) -> FrozenSet[str]:
    """Loads the exact, file-level ``.map``/``.hex`` hard-deny exception
    list (``docs/release_data/map_hex_exceptions.json``). Every entry MUST
    declare a non-empty factual `rationale` string -- this is a schema
    defect (`SourceGuardError`), not merely a missing exception, if it
    does not. Never grants a directory-level or extension-level carve-out:
    only the exact listed `path` strings are ever exempted (see
    `classify_path_segments`)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceGuardError(f"{path}: not valid JSON: {error}") from error
    entries = data.get("exceptions")
    if not isinstance(entries, list):
        raise SourceGuardError(f"{path}: must contain an 'exceptions' array (may be empty)")
    exact_paths: List[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise SourceGuardError(f"{path}[{index}]: entry must be a JSON object")
        entry_path = entry.get("path")
        rationale = entry.get("rationale")
        if not isinstance(entry_path, str) or not entry_path:
            raise SourceGuardError(f"{path}[{index}]: missing/empty 'path'")
        if Path(entry_path).suffix.lower() not in (".map", ".hex"):
            raise SourceGuardError(
                f"{path}[{index}] ({entry_path}): map_hex_exceptions entries must end in "
                "'.map' or '.hex'"
            )
        if not isinstance(rationale, str) or not rationale.strip():
            raise SourceGuardError(
                f"{path}[{index}] ({entry_path}): missing/empty factual 'rationale'"
            )
        exact_paths.append(entry_path)
    if len(exact_paths) != len(set(exact_paths)):
        raise SourceGuardError(f"{path}: duplicate 'path' entries are not allowed")
    return frozenset(exact_paths)


def _top_level_component(relpath: str) -> str:
    return relpath.split("/", 1)[0]


def _hard_deny_check_file(
    root: Path,
    full: Path,
    violations: List[Violation],
    map_hex_exceptions: FrozenSet[str] = frozenset(),
) -> None:
    rel = full.relative_to(root).as_posix()
    if is_unsafe_member_name(rel):
        violations.append((rel, "unsafe-member-name"))
        return
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
    for rule in classify_path_segments(rel, map_hex_exceptions):
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


def scan_tree(
    root: Path,
    allowlist: Iterable[str],
    closed_world: bool = True,
    map_hex_exceptions: FrozenSet[str] = frozenset(),
) -> List[Violation]:
    """Recursively scan a real filesystem tree (a checkout or an extracted
    rehearsal archive) for hard-deny violations. Never follows symlinks;
    any symlink, device, FIFO, or socket is itself a violation.

    `allowlist` may be either the historical top-level-directory-name set
    (each entry a bare top-level path component) or an exact per-member
    (file-level) allowlist -- top-level-entry membership is checked
    against `{entry.split("/", 1)[0] for entry in allowlist}` either way,
    so both shapes keep working for the closed-world top-level check.

    When `closed_world` is True (the default; used to validate an actual
    release candidate tree, which is expected to contain *exactly* the
    allowlisted top-level entries and nothing else), any top-level entry
    not covered by `allowlist` is itself reported as a "not-allowlisted"
    violation. When False (used internally by scripts/release_rehearsal/archive_rehearsal.py to
    build an archive out of a live, possibly-messy development worktree
    that may contain gitignored build output alongside the real source),
    only the allowlisted top-level entries -- and their descendants -- are
    walked and hard-deny-checked at all; anything else present in `root`
    is silently irrelevant, since it is never going to be added to the
    archive in the first place."""
    root = Path(root)
    allowlist = set(allowlist)
    top_level_allowlist = {entry.split("/", 1)[0] for entry in allowlist}
    violations: List[Violation] = []

    if closed_world:
        top_entries = sorted(p.name for p in root.iterdir())
        for name in top_entries:
            if name == ".git":
                continue
            if name not in top_level_allowlist:
                violations.append((name, "not-allowlisted"))
        walk_roots = [root]
    else:
        walk_roots = [root / name for name in sorted(top_level_allowlist) if (root / name).exists()]

    for walk_root in walk_roots:
        for dirpath, dirnames, filenames in os.walk(walk_root, followlinks=False):
            dirnames[:] = [d for d in sorted(dirnames) if not (Path(dirpath) == root and d == ".git")]
            for name in sorted(dirnames) + sorted(filenames):
                _hard_deny_check_file(root, Path(dirpath) / name, violations, map_hex_exceptions)

    return sorted(set(violations))


def git_tracked_allowlisted_files(root: Path, allowlist: Iterable[str]) -> Optional[List[Path]]:
    """When `root` is a real git working tree, enumerate exactly its
    *tracked* files restricted to the allowlist -- never a raw filesystem
    walk. This is deliberately preferred over walking the live filesystem
    whenever git metadata is available: a development worktree routinely
    contains gitignored, host-built byproducts (compiled host tool
    binaries under tools/*/, stale build/ output, a built ROM/ELF, .dep/
    dependency files, etc.) that must never end up in a "source" release
    candidate even though they may sit inside an otherwise-allowlisted
    directory; git itself already knows, precisely and deterministically,
    which files are the actual tracked source.

    `allowlist` is matched *exactly*, one tracked relative path per entry
    (the exact-per-member allowlist -- see
    docs/release_data/source_allowlist.json); a tracked file whose path is
    not itself present in `allowlist` is excluded from the returned list
    exactly like an untracked file would be (this is what makes a new,
    unlisted tracked file invisible to an archive build -- the manifest's
    separate `allowlist_check` module is what turns that into an
    actionable failure instead of a silent omission). Returns None (not a
    list) when `root` has no `.git` (an extracted archive/non-git tree),
    so the caller falls back to a real filesystem walk instead.

    Deliberately still includes a tracked *symlink* (or any other tracked
    non-directory path) in the returned list rather than silently
    dropping it: only an actual real directory on disk (a submodule
    gitlink mountpoint such as "mgfembp", which `git ls-files` also lists
    as its own path) is excluded here, so that a tracked malicious/unsafe
    symlink still reaches the caller's own hard-deny check
    (`_hard_deny_check_file`, which lstat()s -- never follows -- the path
    and flags a symlink as "prohibited-symlink") instead of vanishing
    from the candidate set entirely. Ignoring *untracked* content must
    never become a blind spot for *tracked* content.

    This is the single, shared candidate-enumeration used by both
    scripts/release_rehearsal/archive_rehearsal.py (to build the actual
    release archive) and scan_source_release_candidate() below (so
    scripts/release_rehearsal/manifest.py's source_guard check evaluates
    the exact same tracked-intersect-allowlist set an archive rehearsal
    would build, instead of a second, parallel definition of "the
    candidate")."""
    root = Path(root)
    if not (root / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(root), capture_output=True
    )
    if result.returncode != 0:
        raise SourceGuardError(
            f"git ls-files failed: {result.stderr.decode(errors='replace').strip()}"
        )
    allowlist = set(allowlist)
    files: List[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relpath = raw.decode("utf-8", "surrogateescape")
        if relpath not in allowlist:
            continue
        full = root / relpath
        if full.is_dir() and not full.is_symlink():
            continue
        files.append(full)
    return sorted(files)


def scan_source_release_candidate(
    root: Path,
    allowlist: Iterable[str],
    map_hex_exceptions: FrozenSet[str] = frozenset(),
) -> List[Violation]:
    """Scan the actual source-release *candidate set* for `root`, exactly
    consistent with what scripts/release_rehearsal/archive_rehearsal.py
    would put in the archive -- never a raw closed-world filesystem walk
    of a live, possibly-messy development worktree.

    When `root` is a real git working tree, the candidate set is exactly
    its tracked files intersected with the exact allowlist
    (`git_tracked_allowlisted_files`); every one of those files still gets
    the full recursive hard-deny check (prohibited extension/magic bytes,
    unsafe path segments, symlinks, hardlinks). Gitignored/untracked
    content anywhere in the live worktree (build/ output, .dep/ files, a
    built ROM/ELF, host tool binaries, etc.) can never appear as a
    violation purely because it happens to sit on disk -- it was never
    going to be part of the release in the first place -- so this cannot
    become a blind spot: any *tracked* malicious/unsafe content is still
    denied exactly as before, and nothing gitignored was ever checked by
    the real archive build either.

    When `root` has no `.git` at all (a genuine extracted release archive
    or other non-git candidate tree -- the tree *is* the actual candidate,
    not a development worktree with byproducts alongside it), this falls
    back to the original fail-closed `scan_tree(root, allowlist,
    closed_world=True)` check: every top-level entry must be covered by
    the allowlist and nothing else, and every file anywhere in the tree is
    walked and hard-deny-checked."""
    root = Path(root)
    tracked = git_tracked_allowlisted_files(root, allowlist)
    if tracked is None:
        return scan_tree(root, allowlist, closed_world=True, map_hex_exceptions=map_hex_exceptions)
    violations: List[Violation] = []
    for path in tracked:
        _hard_deny_check_file(root, path, violations, map_hex_exceptions)
    return sorted(set(violations))


def scan_archive_members(
    tar: "tarfile.TarFile",
    allowlist: Iterable[str],
    map_hex_exceptions: FrozenSet[str] = frozenset(),
) -> List[Violation]:
    """Scan a tar archive's members without ever extracting anything to
    disk (uses TarFile.extractfile() for read-only content access only).
    Rejects nested archive content by magic bytes exactly like a real
    filesystem scan does -- a member's *content* is always inspected,
    regardless of its declared name/extension, so a nested archive smuggled
    under an innocuous filename cannot evade detection just because it is
    already inside another archive rather than sitting in a checkout."""
    allowlist = set(allowlist)
    top_level_allowlist = {entry.split("/", 1)[0] for entry in allowlist}
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
        if top not in top_level_allowlist:
            violations.append((name, "not-allowlisted"))
        if member.isdir():
            continue
        for rule in classify_path_segments(name, map_hex_exceptions):
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
    parser.add_argument(
        "--map-hex-exceptions", type=Path,
        default=Path("docs/release_data/map_hex_exceptions.json"),
    )
    args = parser.parse_args(argv)

    try:
        allowlist = load_allowlist(args.allowlist)
        map_hex_exceptions = (
            load_map_hex_exceptions(args.map_hex_exceptions)
            if args.map_hex_exceptions.is_file() else frozenset()
        )
        if args.tree:
            violations = scan_tree(args.tree, allowlist, map_hex_exceptions=map_hex_exceptions)
        else:
            with tarfile.open(args.archive, "r") as tar:
                violations = scan_archive_members(tar, allowlist, map_hex_exceptions=map_hex_exceptions)
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
