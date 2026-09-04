#!/usr/bin/env python3
"""Minimal, stdlib-only tracked-artifact governance checker.

Reads only immutable Git tree/index metadata and blob bytes via
``git cat-file``; never opens a worktree file for scanned content. Rejects
prohibited artifact classes, symlinks, and unexpected gitlinks; narrowly
permits already-tracked source-asset classes under their existing roots
(structural compatibility only, not a legal/copyright clearance -- see
docs/issue-resolution-policy.md). Not a source-release manifest or a
baseline diff/history engine.

Exit codes: 0 clean, 1 policy findings, 2 invocation/Git error.
"""
import argparse
import re
import subprocess
import sys
from collections import namedtuple

MAGIC_READ_BYTES = 192
MAGIC_ELF = b"\x7fELF"
MAGIC_IPS = b"PATCH"
MAGIC_UPS = b"UPS1"
MAGIC_BPS = b"BPS1"
MAGIC_PPF = (b"PPF10", b"PPF20", b"PPF30")
MAGIC_VCDIFF = b"\xD6\xC3\xC4"
GBA_LOGO_PREFIX = bytes.fromhex("24ffae51699aa2213d84820a84e409ad")

GITLINK_ALLOWED_PATH = "mgfembp"
REGULAR_MODES = ("100644", "100755")

PROHIBITED_EXTENSIONS = {
    ".gba", ".elf",
    ".sav", ".srm", ".sa1", ".sa2",
    ".savestate", ".state", ".gpstate",
    ".ips", ".ups", ".bps", ".ppf", ".xdelta", ".xdelta3", ".vcdiff",
    ".lz", ".4bpp", ".8bpp", ".gbapal",
}
SAVESTATE_SLOT_RE = re.compile(r"\.ss[0-9]$")

PROHIBITED_PATH_SEGMENTS = {
    "dump", "extracted", "extractions", "roms", "saves", "savestates", "build",
}
PROHIBITED_ROOT_ARTIFACTS = {"fireemblem8.map", "fireemblem8_relocs.map", "objects.lst"}

# Existing tracked source assets are narrowly allowed only under known roots.
RESTRICTED_EXTENSIONS = {
    ".png", ".bin", ".agbpal", ".mid", ".pal", ".aif", ".mar", ".pcm",
    ".tmap", ".tsa", ".tmx",
}
GRAPHICS_SOURCE_EXTENSIONS = {".png", ".agbpal", ".pal", ".mar", ".tmap", ".tsa", ".tmx"}
SOUND_SOURCE_EXTENSIONS = {".aif", ".mid", ".pcm"}

Entry = namedtuple("Entry", "mode oid path stage")

class GitError(Exception):
    pass

def _run_git(args):
    return subprocess.run(
        ["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

def resolve_commit(revision):
    result = _run_git(["rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"])
    oid = result.stdout.decode().strip()
    if result.returncode != 0 or not oid:
        raise GitError(f"cannot resolve revision to a commit: {revision!r}")
    return oid

def _decode_path(raw):
    return raw.decode("utf-8", "surrogateescape")

def enumerate_revision(commit_oid):
    result = _run_git(["ls-tree", "-r", "-z", commit_oid])
    if result.returncode != 0:
        raise GitError(result.stderr.decode(errors="replace").strip())
    entries = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        meta, _, path = record.partition(b"\t")
        mode, _obj_type, oid = meta.split(b" ")
        entries.append(Entry(mode.decode(), oid.decode(), _decode_path(path), 0))
    return entries

def enumerate_index():
    result = _run_git(["ls-files", "--stage", "-z"])
    if result.returncode != 0:
        raise GitError(result.stderr.decode(errors="replace").strip())
    entries = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        meta, _, path = record.partition(b"\t")
        mode, oid, stage = meta.split(b" ")
        entries.append(Entry(mode.decode(), oid.decode(), _decode_path(path), int(stage)))
    return entries

def _read_exact(stream, size, keep=False):
    chunks = []
    while size:
        chunk = stream.read(min(size, 65536))
        if not chunk:
            raise GitError("short read from git cat-file")
        if keep: chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks)

def read_blob_heads(oids, head_len=MAGIC_READ_BYTES):
    """Read leading bytes per blob via a fail-closed cat-file protocol."""
    if not oids:
        return {}
    if head_len < 0:
        raise GitError("invalid blob prefix length")
    proc = None
    try:
        proc = subprocess.Popen(
            ["git", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        heads = {}
        for requested_oid in oids:
            request = (requested_oid + "\n").encode("ascii")
            if proc.stdin.write(request) != len(request):
                raise GitError("short write to git cat-file")
            proc.stdin.flush()
            header = proc.stdout.readline()
            if not header.endswith(b"\n"):
                raise GitError("missing or unterminated git cat-file header")
            parts = header[:-1].split(b" ")
            if len(parts) != 3:
                raise GitError("malformed git cat-file header")
            oid_raw, object_type, size_raw = parts
            if object_type != b"blob":
                raise GitError("git cat-file returned a non-blob object")
            if oid_raw.decode("ascii") != requested_oid:
                raise GitError("git cat-file returned a mismatched object")
            if not size_raw.isdigit():
                raise GitError("git cat-file returned an invalid object size")
            size = int(size_raw)
            prefix_size = min(head_len, size)
            heads[requested_oid] = _read_exact(proc.stdout, prefix_size, keep=True)
            _read_exact(proc.stdout, size - prefix_size)
            if _read_exact(proc.stdout, 1, keep=True) != b"\n":
                raise GitError("missing git cat-file object separator")
        proc.stdin.close()
        if proc.wait() != 0:
            raise GitError("git cat-file exited unsuccessfully")
        return heads
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as exc:
        raise GitError(f"git cat-file failed: {exc}")
    finally:
        if proc is not None:
            if proc.poll() is None:
                try:
                    proc.kill()
                except OSError:
                    pass
            try:
                proc.wait()
            except (OSError, subprocess.SubprocessError):
                pass

def _extension_of(filename):
    return f".{filename.rsplit('.', 1)[-1]}" if "." in filename else ""

def _is_allowed_source_asset(lower_path, filename, ext):
    if ext == ".bin":
        return lower_path.startswith("graphics/") and (
            filename.endswith(".map.bin") or filename.endswith(".tsa.bin")
        )
    if lower_path.startswith("graphics/") and ext in GRAPHICS_SOURCE_EXTENSIONS:
        return True
    if ext == ".tmx" and lower_path.startswith("scripts/map_gen/chunks/"):
        return True  # FE8_MAPGEN chunk source (scripts/mapgen_build_chunks.py)
    if lower_path.startswith("preview/") and ext == ".png":
        return True
    if lower_path.startswith("sound/") and ext in SOUND_SOURCE_EXTENSIONS:
        return True
    return False

def classify_path(path):
    findings = []
    lower = path.lower()
    segments = lower.split("/")
    filename = segments[-1]

    if "/" not in path and path in PROHIBITED_ROOT_ARTIFACTS:
        findings.append("prohibited-root-build-artifact")

    if any(seg in PROHIBITED_PATH_SEGMENTS for seg in segments):
        findings.append("prohibited-path-segment")
    if any(seg.startswith("baserom") for seg in segments):
        findings.append("prohibited-baserom-path")

    ext = _extension_of(filename)
    if ext in PROHIBITED_EXTENSIONS or SAVESTATE_SLOT_RE.search(filename):
        findings.append("prohibited-extension")
    elif ext in RESTRICTED_EXTENSIONS and not _is_allowed_source_asset(lower, filename, ext):
        findings.append("restricted-extension-outside-allowed-root")
    return findings

def _is_gba_header(head):
    return len(head) >= 0xB3 and head[4:20] == GBA_LOGO_PREFIX and head[0xB2] == 0x96

def classify_magic(head):
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

def scan(entries):
    findings = set()
    content_targets = []
    for entry in entries:
        if entry.stage != 0:
            findings.add((entry.path, "unmerged-index-entry"))
            continue
        if entry.mode == "120000":
            findings.add((entry.path, "prohibited-symlink"))
            continue
        if entry.mode == "160000":
            if entry.path != GITLINK_ALLOWED_PATH:
                findings.add((entry.path, "prohibited-gitlink"))
            continue
        if entry.mode not in REGULAR_MODES:
            findings.add((entry.path, "unexpected-mode"))
            continue
        for rule in classify_path(entry.path):
            findings.add((entry.path, rule))
        content_targets.append(entry)

    heads = read_blob_heads([entry.oid for entry in content_targets])
    for entry in content_targets:
        rule = classify_magic(heads.get(entry.oid, b""))
        if rule:
            findings.add((entry.path, rule))
    return sorted(findings)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--revision", metavar="REV", help="immutable revision to scan, e.g. HEAD")
    group.add_argument("--index", action="store_true", help="scan the Git index instead of a revision")
    args = parser.parse_args(argv)

    try:
        entries = enumerate_index() if args.index else enumerate_revision(resolve_commit(args.revision))
        findings = scan(entries)
    except GitError as exc:
        print(f"artifact_guard: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as exc:
        print(f"artifact_guard: git operation failed: {exc}", file=sys.stderr)
        return 2

    for path, rule in findings:
        print(f"{path}: {rule}")
    if findings:
        print(f"artifact_guard: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
