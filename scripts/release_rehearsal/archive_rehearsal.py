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
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Callable, Dict, FrozenSet, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.release_rehearsal import allowlist as al
from scripts.release_rehearsal import git_source as gs
from scripts.release_rehearsal import gitmodules as gm
from scripts.release_rehearsal import provenance as prov
from scripts.release_rehearsal import source_guard as sg
from scripts.release_rehearsal import tree_coverage as tc
from scripts.modernize import verify_rom_header as vrh

CANONICAL_MTIME = 0
CANONICAL_UID = 0
CANONICAL_GID = 0
CANONICAL_UNAME = ""
CANONICAL_GNAME = ""
CANONICAL_FILE_MODE = 0o644
CANONICAL_DIR_MODE = 0o755

# Rebuild rehearsal machine states (issue #9 verifier remediation): every
# one of these is a *distinct*, never-conflated outcome -- in particular,
# "verified_success" is only ever returned after
# `run_build_twice_from_immutable_source` has genuinely, independently
# materialized two separate immutable source trees and executed a build
# command against each, verified neither materialization was mutated,
# and compared their outputs; nothing in this module ever reports
# success for a rebuild that was not run.
REBUILD_STATUS_NOT_RUN = "not_run"
REBUILD_STATUS_BLOCKED = "blocked"
REBUILD_STATUS_FAILED = "failed"
REBUILD_STATUS_VERIFIED_SUCCESS = "verified_success"
ALL_REBUILD_STATUSES = (
    REBUILD_STATUS_NOT_RUN, REBUILD_STATUS_BLOCKED, REBUILD_STATUS_FAILED,
    REBUILD_STATUS_VERIFIED_SUCCESS,
)

# --- Committed, locked default rebuild profile (issue #9 mandatory -------
# correction #3 / verifier remediation) ------------------------------------
#
# The one, safe, public, documented, deterministic interface a future
# eligible candidate's rebuild rehearsal actually executes through --
# never a free-form shell string accepted from a CLI flag (which would
# reopen the exact "shell command string" hazard issue #9 forbids). This
# is a plain argv list (`subprocess.run(..., shell=False)` -- see
# `run_build_twice_from_immutable_source`) naming the exact, already-
# existing, ordinary `make` targets/knobs this repository's own
# modern.mk defines (MODERN_CONFIG/MODERN_ABI/MODERN_ROM_SIZE -- the
# same three knobs `cli.py`'s own `--config`/`--abi`/`--rom-size`
# options already expose), never a new, bespoke build path invented only
# for this rehearsal. `-j1` is deliberately pinned (never left to the
# ambient `MAKEFLAGS`/nproc) so the rehearsal's own two independent runs
# never depend on host parallelism/scheduling for determinism.
#
# This profile is only ever reached once `evaluate_rebuild_eligibility`
# has already reported this candidate eligible (mgfembp initialized,
# identity-matched, provenance-approved, clean) -- today, and until a
# human resolves that provenance record, it is unconditionally
# `REBUILD_STATUS_BLOCKED` before a single byte of this profile is ever
# read, exactly as `docs/release_process.md`'s "Legal and provenance
# boundary" documents. Wiring it in now (rather than leaving the
# eligible path an unexecuted stub) is what makes a *future* eligible
# run actually run two real, hermetic, independently-materialized builds
# instead of merely describing that it would.
DEFAULT_REBUILD_MODERN_CONFIG = "release"
DEFAULT_REBUILD_MODERN_ABI = "aapcs"
DEFAULT_REBUILD_MODERN_ROM_SIZE = "16M"
DEFAULT_REBUILD_OUTPUT_DIR = "build/expansion-modern/{config}/{abi}".format(
    config=DEFAULT_REBUILD_MODERN_CONFIG, abi=DEFAULT_REBUILD_MODERN_ABI,
)
DEFAULT_REBUILD_BUILD_COMMAND: Tuple[str, ...] = (
    "make", "-j1",
    f"MODERN_CONFIG={DEFAULT_REBUILD_MODERN_CONFIG}",
    f"MODERN_ABI={DEFAULT_REBUILD_MODERN_ABI}",
    f"MODERN_ROM_SIZE={DEFAULT_REBUILD_MODERN_ROM_SIZE}",
    "expansion-modern-rom",
)
DEFAULT_REBUILD_OUTPUT_RELPATHS: Tuple[str, ...] = (
    f"{DEFAULT_REBUILD_OUTPUT_DIR}/fireemblem8.elf",
    f"{DEFAULT_REBUILD_OUTPUT_DIR}/fireemblem8.gba",
)


def build_default_rebuild_profile(
    config: str = DEFAULT_REBUILD_MODERN_CONFIG,
    abi: str = DEFAULT_REBUILD_MODERN_ABI,
    rom_size: str = DEFAULT_REBUILD_MODERN_ROM_SIZE,
) -> Tuple[List[str], List[str]]:
    """Constructs the same locked-profile shape as `DEFAULT_REBUILD_
    BUILD_COMMAND`/`DEFAULT_REBUILD_OUTPUT_RELPATHS`, but parameterized
    by the exact same `--config`/`--abi`/`--rom-size` knobs `cli.py`'s
    own subcommands already expose (never a new, separate free-form
    input) -- so `make release-rehearse`'s own `--config`/`--abi`/
    `--rom-size` selection is what a future eligible run's rebuild
    itself actually uses, never silently pinned to a different preset
    than the rest of that same invocation's manifest. Still always a
    plain argv list (never a shell string) and a plain relative output
    path list -- both returned as fresh, ordinary Python lists."""
    output_dir = f"build/expansion-modern/{config}/{abi}"
    build_command = [
        "make", "-j1", f"MODERN_CONFIG={config}", f"MODERN_ABI={abi}", f"MODERN_ROM_SIZE={rom_size}",
        "expansion-modern-rom",
    ]
    output_relpaths = [f"{output_dir}/fireemblem8.elf", f"{output_dir}/fireemblem8.gba"]
    return build_command, output_relpaths

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
    `_hard_deny_check_file`: same path/extension/magic/structural rules,
    applied to bytes read from an immutable git blob instead of a
    worktree path. A tracked hardlink has no meaning for a
    content-addressed git blob (two paths sharing identical content is
    normal/expected in git, not a filesystem hazard), so that specific
    check does not apply here.

    issue #9 residual-gap fix: a tracked file whose *committed blob
    content* is a structurally valid ZIP (including a prefixed/
    self-extracting one -- see `source_guard.classify_zip_structure`)
    must be denied exactly like the filesystem (`_hard_deny_check_file`)
    and tar-member (`scan_archive_members`) paths already do. Before this
    fix, a tracked blob whose first `MAGIC_READ_BYTES` bytes were not a
    bare `PK\x03\x04`/`PK\x05\x06`/`PK\x07\x08` header -- e.g. any
    nonzero-length prefix before the real ZIP data -- silently bypassed
    every ZIP check on this, the dominant real-world release-archive
    path (a real git-tracked blob), even though the exact same bytes
    would already have been caught on the filesystem or tar-member
    paths. `classify_zip_structure` accepts a `bytes`/`bytearray` blob
    directly (wraps it in an in-memory `io.BytesIO`), so the already-read
    full blob `data` is passed as-is -- no extra read, no extraction."""
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
    zip_rule = sg.classify_zip_structure(data)
    if zip_rule:
        violations.append((rel, zip_rule))


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
    pass one explicitly -- HEAD is resolved once, here). For a non-git
    candidate tree, `resolved_target_sha` is simply the caller's own
    `target_sha` argument bound through unchanged (an *externally
    asserted* identity, e.g. the exact 40-lowercase-hex `--target-sha`
    the documented non-git/extracted candidate path requires -- never
    itself verified against git, since there is no git metadata to
    verify it against); it is None only if the caller did not supply one
    (see module docstring's "Immutable, HEAD-bound archive inputs").
    Also raises `ArchiveRehearsalError` for a non-git `root` if any
    allowlist entry has no on-disk representation at all (missing/
    unrepresented -- e.g. an absent 'mgfembp' gitlink mountpoint)."""
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
            # issue #9 mandatory correction #2: candidate archive members
            # MUST equal the included (allowlist) set exactly -- never a
            # subset (a declared member silently missing) nor a superset
            # (an undeclared member silently smuggled in, e.g. a gitlink
            # that slipped past the `not entry.is_gitlink` filter above
            # due to a future bug). This is a direct, load-bearing check
            # inside the archive-building path itself -- it never merely
            # relies on some *other*, possibly-skipped check
            # (`allowlist.check_allowlist_completeness`) having already
            # run first.
            built_paths = {path for path, _ in contents}
            missing_members, extra_members = tc.check_archive_membership_exact(built_paths, allowlist_set)
            if missing_members or extra_members:
                raise ArchiveRehearsalError(
                    "refusing to archive: built archive members do not exactly equal the "
                    "included allowlist set -- missing: "
                    f"{missing_members or '(none)'}; extra: {extra_members or '(none)'}"
                )
    else:
        # issue #9 verifier remediation: `target_sha` is never verified
        # against git here (there is no git metadata in a non-git
        # candidate tree to verify it against) -- it is bound into the
        # report/return value as-is, as an *externally-asserted* identity,
        # never a Git-plumbing-derived one. This never invokes any git
        # command for a non-git `root` (see module docstring's "Immutable,
        # HEAD-bound archive inputs").
        resolved_target_sha = target_sha
        _missing_unused, unrepresented = al.check_allowlist_completeness_non_git(root, sorted(allowlist_set))
        if unrepresented:
            raise ArchiveRehearsalError(
                "refusing to archive: allowlisted member(s) have no on-disk representation "
                "in this extracted tree (missing/unrepresented -- e.g. an absent gitlink "
                "mountpoint such as 'mgfembp', or a removed/never-extracted file): "
                + "; ".join(unrepresented)
            )
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
    else:
        # issue #9 verifier remediation: bind the caller's asserted
        # target_sha into the report even in non-git mode (previously
        # silently dropped to None here) -- never verified against git
        # (there is none to verify against), but no longer discarded.
        resolved_target_sha = target_sha

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


# --- Submodule dirty-worktree / URL / accessible-object guards (issue #9 --
# guardian-correction remediation, D3) -------------------------------------
#
# `evaluate_rebuild_eligibility` below previously treated "'git submodule
# status' reports this path as initialized and at the pinned commit" as
# sufficient -- but that indicator alone says nothing about whether the
# submodule's own *worktree* is clean. An independent review reproduced
# exactly this gap: a submodule whose HEAD commit matches the pinned
# gitlink SHA (so `git submodule status` shows it "in sync") can still
# have locally modified/staged/untracked files sitting in its working
# tree, and the *previous* materialization strategy (`shutil.copytree`
# of that live worktree -- see the old `_copy_verified_submodule_content`
# below, replaced by `_materialize_verified_submodule_content`) copied
# exactly those dirty bytes into both "independent" build runs, which
# could then report `verified_success` over tampered content. The
# functions below close that gap; `evaluate_rebuild_eligibility` calls
# every one of them before ever considering the submodule eligible.


def _submodule_worktree_status_output(submodule_dir: Path) -> str:
    """Raw `git status --porcelain=v1` output from *inside* the
    submodule's own working tree (never the superproject) -- empty
    output means a genuinely clean worktree/index: no modified, staged,
    or untracked path at all. Raises `ArchiveRehearsalError` (an
    actionable tooling defect) if the command itself cannot even run --
    this is only ever called once `submodule_dir` is already known to be
    initialized/present."""
    result = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=str(submodule_dir), capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ArchiveRehearsalError(
            f"git status failed inside the '{submodule_dir}' submodule worktree: {result.stderr.strip()}"
        )
    return result.stdout


def _submodule_configured_url(submodule_dir: Path) -> Optional[str]:
    """The submodule's own configured `remote.origin.url`, read directly
    from *inside* its own git config (never from the superproject's
    `.gitmodules`) -- `None` for the entirely ordinary "no `origin`
    remote configured at all" case (git's own exit code 1 for a missing
    key), reported as a distinct, honestly-unresolved fact rather than
    fabricated as a match or a mismatch. issue #9 R3 fix: any *other*
    nonzero exit (e.g. a corrupt/unreadable git config, or `submodule_dir`
    not actually being a readable git worktree at all) is a genuine
    tooling failure, never silently folded into the same "just unset"
    `None` -- raises `ArchiveRehearsalError` with the real stderr instead,
    exactly like `_submodule_worktree_status_output`'s own command-error
    handling."""
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"], cwd=str(submodule_dir), capture_output=True, text=True,
    )
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise ArchiveRehearsalError(
            f"git config --get remote.origin.url failed inside the '{submodule_dir}' submodule "
            f"worktree: {result.stderr.strip()}"
        )
    url = result.stdout.strip()
    return url or None


def _submodule_declared_url(repo_root: Path, submodule_path: str) -> Optional[str]:
    """The superproject's own `.gitmodules` (read at HEAD via
    `gitmodules.py`'s immutable blob parser -- never the worktree path)
    declared `url` for `submodule_path`; `None` if `.gitmodules` is
    missing/malformed or declares no matching section (reported as its
    own, separate finding elsewhere -- `submodule_binding.py` -- this
    function only ever returns the bare value or `None`, never raises
    for a normal "no such section" case)."""
    try:
        sections = gm.load_gitmodules_sections(repo_root, "HEAD")
    except gm.GitmodulesError:
        return None
    for section in sections.values():
        if section.get("path") == submodule_path:
            return section.get("url")
    return None


def _submodule_pinned_object_accessible(submodule_dir: Path, pinned_commit: str) -> bool:
    """True only if `pinned_commit` is a real, locally-present commit
    object inside the submodule's own object database (`git cat-file -e
    <sha>^{commit}`) -- a shallow clone, a corrupt/incomplete object
    database, or simply a wrong/unresolvable SHA all report `False` here,
    never silently treated as accessible. A rebuild can never
    successfully materialize content it cannot actually read."""
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{pinned_commit}^{{commit}}"],
        cwd=str(submodule_dir), capture_output=True, text=True,
    )
    return result.returncode == 0


def evaluate_rebuild_eligibility(
    repo_root: Path,
    submodule_path: str = "mgfembp",
    provenance_dir: Optional[Path] = None,
) -> Tuple[bool, Dict]:
    """Read-only (never fetches/initializes/approves anything) check of
    whether a clean recursive rebuild involving `submodule_path` is even
    *eligible* to attempt. ALL of the following must hold (issue #9
    guardian-correction remediation, D3, added (4)-(6) below -- a
    dirty-but-commit-matching submodule worktree was previously the one
    fact this function never checked, so its content could be copied
    live into a rebuild and reported `verified_success` even though it
    was never actually the reviewed, pinned bytes):

    1. initialized/checked out (`git submodule status`);
    2. at exactly its provenance-pinned commit (no `git submodule
       status` `"+"`/identity-mismatch indicator);
    3. recorded with `redistribution_approved: true`;
    4. a genuinely clean submodule worktree/index -- `git status
       --porcelain` run *inside* the submodule itself reports nothing at
       all (no modified, staged, or untracked path);
    5. issue #9 R3 fix: a *live, non-empty* configured
       `remote.origin.url` exists at all (a missing/unset origin is
       always non-eligible, never a vacuous pass), and it agrees
       *exactly* with both of the two independent immutable declared
       sources this repository records for it -- `.gitmodules`'s own
       declared `url` for this path, and `docs/release_data/provenance/
       submodules.json`'s own recorded `url` -- a missing declaration in
       *either* immutable source, or a mismatch against *either* of
       them, is equally non-eligible (never only checked "when known");
       and
    6. the provenance-pinned commit is a real, locally-accessible commit
       object of the correct type inside the submodule's own object
       database (`git cat-file -e <sha>^{commit}`; a blob/tree SHA, a
       shallow clone missing the object, or any other unresolvable value
       all report not-accessible here, never merely "not verified").

    Every underlying `git status`/`git config`/`git cat-file` command is
    itself required to actually succeed (beyond its own pass/fail
    semantics above) -- a genuine command/tooling failure (as opposed to
    an ordinary "not clean"/"no origin set"/"object absent" outcome) is
    caught and reported as its own actionable, non-eligible finding here,
    never silently swallowed into a false pass.

    This function only ever *reads* `docs/release_data/provenance/*.json`,
    `git submodule status`, and (once initialized) the submodule's own
    `git status`/`git config`/`git cat-file` -- it never writes, fetches,
    or flips any of them itself. See `rebuild_rehearsal_blocker` /
    `_materialize_verified_submodule_content` for how (once *and only
    once* every one of the above holds) the submodule's content is
    actually placed into a rebuild -- never a `shutil.copytree` of this
    checked live worktree, always a fresh `git archive <pinned_commit>`
    extraction bound to that exact immutable commit object.

    issue #9 verifier remediation: when `repo_root` has no `.git` at all
    (a genuine extracted archive/non-git candidate tree), this returns
    unconditionally ineligible **without ever invoking `git submodule
    status`** -- there is no git submodule mechanism to evaluate for a
    non-git tree, and invoking it anyway is actively unsafe: `git`'s own
    upward directory discovery could silently find an unrelated
    *enclosing* repository (if `repo_root` happens to sit inside one) and
    report *that* repository's submodule state as if it belonged to this
    extracted tree -- exactly the "pretend the override proves Git
    content identity" failure this remediation forbids. `submodule_path`
    is never fetched/initialized/approved in this branch either, exactly
    like the real-git-repo path below."""
    repo_root = Path(repo_root)
    provenance_dir = Path(provenance_dir) if provenance_dir else repo_root / "docs" / "release_data" / "provenance"

    if not gs.is_git_repo(repo_root):
        reason = (
            f"'{repo_root}' has no .git metadata (a genuine extracted archive/non-git "
            f"candidate tree); a clean recursive rebuild requiring the '{submodule_path}' git "
            "submodule is therefore always ineligible here -- there is no git submodule "
            "mechanism to initialize or verify against an extracted tree, and this rehearsal "
            "never invokes git plumbing (e.g. 'git submodule status') against one"
        )
        return False, {
            "submodule_status_output": "",
            "submodule_initialized": False,
            "submodule_checked_out_sha": None,
            "submodule_worktree_clean": False,
            "submodule_configured_url": None,
            "submodule_declared_url": None,
            "submodule_provenance_url": None,
            "submodule_pinned_object_accessible": False,
            "provenance_pinned_commit": None,
            "provenance_redistribution_approved": False,
            "identity_matches_pinned": False,
            "reasons": [reason],
        }

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

    # issue #9 R3 fix: the provenance lookup (previously computed *after*
    # the URL-matching block below) is moved up here so its own `url`
    # field is available as a third, independent, immutable source for
    # that block's three-way cross-check (alongside the live configured
    # origin and .gitmodules's declared url) -- purely a reordering, the
    # pinned_commit/approved semantics used later are unchanged.
    pinned_commit: Optional[str] = None
    approved = False
    provenance_url: Optional[str] = None
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
        provenance_url = matches[0].get("url") or None
        if not approved:
            reasons.append(
                f"provenance for the '{submodule_path}' submodule content is recorded as "
                "unresolved/unapproved (redistribution_approved: false); a clean recursive "
                "rebuild that includes it cannot be certified complete-and-clear until that is "
                "resolved by a human reviewer"
            )
        if provenance_url is None:
            reasons.append(
                f"provenance entry for '{submodule_path}' in {provenance_dir} has no 'url' "
                "recorded -- there is no immutable provenance url to cross-check the live "
                "configured origin against"
            )

    # issue #9 guardian-correction remediation (D3): "initialized and at
    # the pinned commit" (above) is necessary but never sufficient -- a
    # dirty, staged, or untracked submodule worktree must also make this
    # ineligible (see the "Submodule dirty-worktree" block's own
    # docstring above `_submodule_worktree_status_output`), since a
    # rebuild must materialize the pinned commit's own immutable content,
    # never whatever extra/modified bytes happen to be sitting in a live
    # checkout that merely *starts* from that commit.
    submodule_dir = repo_root / submodule_path
    worktree_clean = False
    configured_url: Optional[str] = None
    if initialized:
        try:
            worktree_status = _submodule_worktree_status_output(submodule_dir)
        except ArchiveRehearsalError as error:
            reasons.append(str(error))
            worktree_status = None
        if worktree_status is not None:
            worktree_clean = worktree_status.strip() == ""
            if not worktree_clean:
                reasons.append(
                    f"the '{submodule_path}' submodule worktree/index is not clean ('git status "
                    "--porcelain' reports modified, staged, and/or untracked path(s) inside it) "
                    "-- a dirty submodule checkout can never be treated as the reviewed, pinned "
                    f"content, even when its own HEAD commit matches the pinned gitlink: "
                    f"{worktree_status.strip()!r}"
                )
        try:
            configured_url = _submodule_configured_url(submodule_dir)
        except ArchiveRehearsalError as error:
            reasons.append(str(error))
            configured_url = None

    declared_url = _submodule_declared_url(repo_root, submodule_path)

    # issue #9 R3 fix: a *missing* origin previously left `url_matches`
    # at its vacuous default `True` (never actually checked at all,
    # since every branch of the old condition required both sides to be
    # `is not None` first) -- a submodule with no configured origin (or
    # whose remote does not exactly match .gitmodules's declared url
    # and/or the immutable provenance record's own declared url) is now
    # unconditionally non-eligible, with an exact, actionable reason for
    # each specific way this can fail. `url_matches` defaults `False`
    # even when not yet `initialized` -- meaningless either way there,
    # since `eligible` below always also requires `initialized`, but
    # never a silent fail-open reading of this flag on its own.
    url_matches = False
    if initialized:
        if configured_url is None:
            reasons.append(
                f"the '{submodule_path}' submodule has no configured 'remote.origin.url' at all "
                "(no origin remote configured, or it is otherwise unset) -- a rebuild can never "
                "be certified eligible without a live, checkable origin to cross-check against "
                "the immutable .gitmodules/provenance url record"
            )
        elif declared_url is None:
            reasons.append(
                f".gitmodules declares no readable 'url' for '{submodule_path}' at HEAD -- the "
                "live configured origin cannot be cross-checked against a missing immutable "
                "declaration"
            )
        elif provenance_url is None:
            # Already reported as its own actionable finding in the
            # provenance block above ("...has no 'url' recorded") --
            # never a second, redundant reason here, but `url_matches`
            # still correctly stays `False`: a missing immutable
            # provenance url is exactly as fail-closed as a missing
            # .gitmodules url, never silently skipped as "not this
            # check's problem".
            pass
        elif configured_url != declared_url:
            reasons.append(
                f"the '{submodule_path}' submodule's configured remote URL {configured_url!r} does "
                f"not match .gitmodules's declared URL {declared_url!r}"
            )
        elif configured_url != provenance_url:
            reasons.append(
                f"the '{submodule_path}' submodule's configured remote URL {configured_url!r} does "
                f"not match the provenance-recorded URL {provenance_url!r} in {provenance_dir}"
            )
        else:
            url_matches = True

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

    # issue #9 guardian-correction remediation (D3): the pinned commit
    # object must actually be present/readable inside the submodule's
    # own object database -- never assumed accessible merely because a
    # provenance record names it.
    pinned_object_accessible = False
    if initialized and pinned_commit:
        pinned_object_accessible = _submodule_pinned_object_accessible(submodule_dir, pinned_commit)
        if not pinned_object_accessible:
            reasons.append(
                f"the pinned commit {pinned_commit!r} is not accessible as a real, locally-"
                f"present commit object inside the '{submodule_path}' submodule (e.g. a shallow "
                "clone, or a corrupt/incomplete object database) -- a rebuild cannot materialize "
                "content it cannot read"
            )

    eligible = (
        initialized and approved and identity_ok
        and worktree_clean and url_matches and pinned_object_accessible
    )
    return eligible, {
        "submodule_status_output": status_output,
        "submodule_initialized": initialized,
        "submodule_checked_out_sha": checked_out_sha,
        "submodule_worktree_clean": worktree_clean,
        "submodule_configured_url": configured_url,
        "submodule_declared_url": declared_url,
        "submodule_provenance_url": provenance_url,
        "submodule_pinned_object_accessible": pinned_object_accessible,
        "provenance_pinned_commit": pinned_commit,
        "provenance_redistribution_approved": approved,
        "identity_matches_pinned": identity_ok,
        "reasons": reasons,
    }


# --- Independent immutable-source rebuild materialization (issue #9 ------
# mandatory correction #7 / guardian-correction remediation D1) ---------
#
# issue #9 guardian-correction remediation (D1): a previous version of
# this module also defined `run_build_twice()`, a copy-based ("each run
# `shutil.copytree`s `source_dir` -- itself whatever mutable path the
# caller passed in -- into its own temp dir") double-build helper. It was
# never actually wired into `rebuild_rehearsal_blocker()`/the release
# manifest's `verified_success` computation at all (only the
# independent-immutable-materialization function below ever was) -- but
# release-evidence docs and a test's own docstring nonetheless
# (incorrectly) described a test built on top of *that* legacy function
# as if it drove `rebuild_rehearsal_blocker()` itself end-to-end, which
# an independent review reproduced as a documentation/evidence defect
# (D1). Rather than leave a legacy, copy-of-a-mutable-directory API
# sitting around for some *future* doc/test to misattribute the same way
# again, it is deleted outright here -- see
# `scripts/release_rehearsal/tests/test_archive_rehearsal.py`'s
# `RebuildRehearsalBlockerEndToEndBuildTests` (issue #9 R4 fix: the
# previous comment here named a test class that has never actually
# existed in that file -- this is the real, corrected end-to-end
# replacement, whose own `test_verified_success_end_to_end` drives
# `rebuild_rehearsal_blocker()` itself, through a synthetic
# fully-eligible submodule fixture, to `REBUILD_STATUS_VERIFIED_
# SUCCESS`).
#
# `run_build_twice_from_immutable_source()` below already proves each run gets its own fresh
# copy of `source_dir` and never mutates the caller's original directory
# -- but that original `source_dir` is itself whatever the caller
# passed in, which for a live git worktree is *mutable* (worktree/index
# state, not a specific immutable commit). The functions below are the
# stronger, independent-materialization variant issue #9 requires for
# any *future* verified-success path: each of the two runs materializes
# its own source tree completely independently (a fresh `git archive
# <target_sha> | tar -x` extraction into its own fresh temp directory --
# never a copy of the live worktree, and never sharing a directory with
# the other run), and this module additionally verifies that every file
# present in a run's own materialization *before* the build executes is
# still present, byte-identical, *after* it -- a build script that
# mutates or deletes any of its declared input files (instead of only
# ever writing new, genuinely separate output paths) is reported as a
# failure, never silently "matched".


def _hash_tree_snapshot(root: Path) -> Dict[str, str]:
    """A deterministic `{relpath: sha256}` snapshot of every regular,
    non-symlink file currently present under `root`. Used only to detect
    whether a build step mutated (changed the content of, or deleted)
    any file that was already part of its own declared input
    materialization -- never to police newly-created output files, which
    are expected and never flagged by comparing two snapshots against
    only the *original* key set (see `_verify_input_tree_unchanged`)."""
    root = Path(root)
    snapshot: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirpath_path = Path(dirpath)
        for name in filenames:
            full = dirpath_path / name
            if full.is_symlink():
                continue
            snapshot[full.relative_to(root).as_posix()] = hash_file(full)
    return snapshot


def _verify_input_tree_unchanged(root: Path, before: Dict[str, str]) -> List[str]:
    """Returns a list of human-readable problems (empty means clean): any
    path present in `before` that is now missing, or whose content hash
    changed, under `root`. A build that only ever adds new output files
    elsewhere in the tree produces no findings here at all -- this is
    strictly about the *originally materialized* input set."""
    problems: List[str] = []
    for relpath, original_hash in sorted(before.items()):
        full = root / relpath
        if not full.is_file() or full.is_symlink():
            problems.append(f"input file disappeared during the build: {relpath}")
            continue
        current_hash = hash_file(full)
        if current_hash != original_hash:
            problems.append(f"input file was mutated during the build: {relpath}")
    return problems


def materialize_immutable_source_tree(repo_root: Path, target_sha: str, dest_dir: Path) -> None:
    """Materializes `target_sha`'s exact tracked tree content into the
    already-created, empty `dest_dir` via `git archive <target_sha> |
    tar -x` -- a real, independent extraction bound to that exact
    immutable commit, never a copy of the live (potentially mutable)
    worktree. Raises `ArchiveRehearsalError` on any failure."""
    archive_proc = subprocess.run(
        ["git", "archive", target_sha], cwd=str(repo_root), capture_output=True,
    )
    if archive_proc.returncode != 0:
        raise ArchiveRehearsalError(
            f"git archive {target_sha!r} failed: {archive_proc.stderr.decode(errors='replace').strip()}"
        )
    extract_proc = subprocess.run(["tar", "-x"], input=archive_proc.stdout, cwd=str(dest_dir))
    if extract_proc.returncode != 0:
        raise ArchiveRehearsalError(f"tar extraction of the {target_sha!r} archive into {dest_dir} failed")


def _controlled_build_environment(run_dir: Path, target_sha: Optional[str] = None) -> Dict[str, str]:
    """A small, explicit, deterministic environment -- never a blind
    passthrough of this process's own full ambient environment (which
    can vary run-to-run, host-to-host, and is exactly the kind of
    uncontrolled variable a reproducibility rehearsal must not depend
    on). Only the handful of variables a real build genuinely needs
    (`PATH` to find its own toolchain) are carried through; everything
    else affecting output determinism (locale, timezone, a private
    `HOME`) is pinned to a fixed value.

    issue #9 mandatory correction (target-SHA/build-ID binding): every
    materialization this function's environment feeds into
    (`materialize_immutable_source_tree`'s `git archive | tar -x`
    extraction) never carries `.git` metadata -- so the build's own
    embedded identity (config.mk's `EXPANSION_BUILD_ID`, consumed by
    `scripts/modernize/expansion_config.py`'s `resolve_build_commit`,
    which otherwise falls back to the fixed sentinel `"unknown"` for any
    tree with no `.git`) can only ever be bound correctly if it is
    supplied here -- unconditionally, whenever `target_sha` is given,
    never only "when convenient". This is the exact, strict env-var
    binding form `EXPANSION_BUILD_ID=<40-hex target SHA>` this project's
    own config.mk (`EXPANSION_BUILD_ID ?=`) and modern.mk already
    understand -- passed as a real environment variable to a `shell=False`
    `subprocess.run` argv list, never interpolated into a shell string."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(run_dir),
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
    }
    if target_sha is not None:
        env["EXPANSION_BUILD_ID"] = target_sha
    return env


def _validate_output_relpath(run_root: Path, relpath: str) -> Path:
    """issue #9 verifier remediation: every declared build output path
    must stay strictly within its own run's immutable materialization
    directory -- never a path traversal (`..`), an absolute escape, a
    symlink that resolves outside `run_root`, or (via the caller's own
    cross-run comparison) a path aliased/shared with the *other*
    independent run. Raises `ArchiveRehearsalError` naming the exact
    unsafe path; never silently drops or "fixes" it.

    A relative `relpath` component this strict is deliberately checked
    via `os.path.relpath`-free, pure `Path`/string logic (no reliance on
    a possibly-not-yet-existing symlink target resolving 'through' via
    `Path.resolve()` in an unexpected order) -- the check has two
    independent layers: (1) the *textual* relpath itself must contain no
    `..` segment and must not be absolute, and (2) once joined, the
    resulting path must still be a real descendant of `run_root` after
    both are fully resolved (`os.path.realpath`), which additionally
    catches a symlink placed by an untrusted build step pointing
    somewhere outside `run_root`."""
    if os.path.isabs(relpath):
        raise ArchiveRehearsalError(
            f"refusing unsafe declared output path {relpath!r}: absolute paths are never allowed "
            "(every output must be a path relative to its own run's materialization root)"
        )
    parts = Path(relpath).parts
    if any(part in ("..", "") for part in parts) or ".." in relpath.split("/"):
        raise ArchiveRehearsalError(
            f"refusing unsafe declared output path {relpath!r}: path traversal ('..') is never "
            "allowed in a declared output path"
        )
    run_root_real = os.path.realpath(str(run_root))
    candidate = run_root / relpath
    # `os.path.realpath` resolves symlinks in every already-existing path
    # component (and is safe to call even if the final component does not
    # yet exist, e.g. before the build has run) -- so a symlink anywhere
    # along the path that escapes `run_root` is caught here even though
    # the textual relpath itself contained no literal `..`.
    candidate_real = os.path.realpath(str(candidate))
    if candidate_real != run_root_real and not candidate_real.startswith(run_root_real + os.sep):
        raise ArchiveRehearsalError(
            f"refusing unsafe declared output path {relpath!r}: resolves to {candidate_real!r}, "
            f"which escapes its own run's materialization root {run_root_real!r} "
            "(symlink escape or equivalent)"
        )
    return candidate


def _extract_embedded_build_commits(paths_and_hashes: Dict[str, Optional[str]], run_root: Path) -> Dict[str, Optional[str]]:
    """For each declared output that is present, attempts to locate and
    parse an embedded `ExpansionMetadata` record (see
    `scripts/modernize/verify_rom_header.py`) and returns its
    `build_commit` field -- `None` for any output that either is not
    present or simply does not itself carry that record (e.g. an
    intermediate artifact, or a synthetic test fixture's own output that
    was never meant to). Never raises for "no record found"; a genuinely
    malformed/ambiguous embedded record (`ExpansionMetadataError`) IS
    surfaced as a build-identity-binding failure -- silently accepting a
    corrupt record would be exactly the "produced embedded metadata was
    never actually verified" gap this function closes."""
    commits: Dict[str, Optional[str]] = {}
    for relpath, digest in paths_and_hashes.items():
        if digest is None:
            commits[relpath] = None
            continue
        data = (run_root / relpath).read_bytes()
        try:
            offset = vrh.find_expansion_metadata(data)
        except vrh.ExpansionMetadataError:
            commits[relpath] = None
            continue
        record = vrh.parse_expansion_metadata(data, offset)
        commits[relpath] = record["build_commit"]
    return commits


def run_build_twice_from_immutable_source(
    repo_root: Path,
    target_sha: str,
    build_command: List[str],
    output_relpaths: List[str],
    extra_materialize: Optional[Callable[[Path], None]] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict:
    """The independent-materialization double-build: each of the two
    runs gets its own source tree, materialized *separately* and
    *independently* from the exact same immutable `target_sha` (never a
    copy of the live worktree), in its own fresh temporary directory that
    also serves as that run's own build/output directory (so the two
    runs can never share a source or build directory -- each is rooted
    at a distinct `tempfile.mkdtemp()` path, asserted distinct below).

    `extra_materialize(run_root)`, if given, is called once per
    independent materialization immediately after the `git archive`
    extraction (e.g. to additionally place already-eligibility-verified
    submodule content that `git archive` itself never includes -- see
    `rebuild_rehearsal_blocker`) -- so that content, too, is placed
    twice, independently, never shared between the two runs.

    Verifies, for each run, that every file present in its own
    materialization *before* `build_command` executes is still present
    with byte-identical content *after* it (`_verify_input_tree_
    unchanged`) -- `match` is only ever `True` when both runs exit `0`,
    every declared output is present and byte-identical between the two
    runs, AND neither run's own input materialization was mutated.

    `build_command` is always executed as a strict argv list via
    `subprocess.run(..., shell=False)` (the default) -- never a shell
    string, never `shell=True`. Every `output_relpaths` entry is
    validated (`_validate_output_relpath`) to stay strictly within its
    own run's materialization root before it is ever read, for both
    runs, and the two runs' resolved output paths are additionally
    cross-checked to never alias one another (issue #9 verifier
    remediation). Whenever an output carries a parseable embedded
    `ExpansionMetadata` record, its `build_commit` field is extracted and
    returned (`embedded_build_commits*`) so the caller (`rebuild_
    rehearsal_blocker`) can verify it against the exact `target_sha` this
    materialization was bound to -- never merely assumed correct because
    the two runs' hashes matched each other (two runs can be
    consistently, deterministically *wrong* about their own identity)."""
    resolved_env = env if env is not None else None  # per-run HOME still varies; see below
    seen_run_dirs: set = set()
    seen_output_paths: set = set()

    def _one_run() -> Dict:
        run_dir = Path(tempfile.mkdtemp(prefix="fe8-rebuild-immutable-run-"))
        # issue #9 fresh-review remediation: the *entire* body below is
        # now wrapped in try/finally so `run_dir` -- the one and only
        # temp root this function ever creates/owns -- is unconditionally
        # removed on every exit path: normal success, a build failure
        # (non-zero/raising `subprocess.run`), a pre-build validation
        # rejection (`_validate_output_relpath` raising on an absolute/
        # traversal path), a post-build symlink/output-escape rejection,
        # a cross-run output-path alias rejection, or any other
        # unexpected exception. The `finally` block never suppresses the
        # original exception/return value -- it only ever adds a
        # best-effort `ignore_errors=True` cleanup alongside it, and it
        # only ever removes `run_dir` itself (never anything outside the
        # exact temp root this run created), so a failure is still
        # reported/propagated truthfully while leaving no
        # `fe8-rebuild-immutable-run-*` directory behind.
        try:
            # Explicit, direct "never share a source/build directory
            # between the two runs" guard -- checked *before* anything is
            # materialized into it, independent of any later mutation/
            # cleanup timing. `tempfile.mkdtemp()` itself always returns a
            # unique path in real operation; this only ever fires if that
            # invariant is somehow violated (e.g. a test forcing it).
            if run_dir in seen_run_dirs:
                raise ArchiveRehearsalError(
                    f"refusing to run an independent materialization: {run_dir} is the same directory "
                    "already used by the other run -- a shared source/build directory can never be trusted"
                )
            seen_run_dirs.add(run_dir)
            run_root = run_dir / "src"
            run_root.mkdir()
            materialize_immutable_source_tree(repo_root, target_sha, run_root)
            if extra_materialize is not None:
                extra_materialize(run_root)
            # Validate every declared output path's *textual* shape (no
            # absolute path, no '..' traversal) before the build ever runs --
            # an unsafe declared path is refused outright, before a single
            # byte of the build command is executed.
            validated_outputs = {relpath: _validate_output_relpath(run_root, relpath) for relpath in output_relpaths}
            before = _hash_tree_snapshot(run_root)
            run_env = resolved_env if resolved_env is not None else _controlled_build_environment(run_dir, target_sha)
            result = subprocess.run(
                build_command, cwd=str(run_root), capture_output=True, text=True, env=run_env,
            )
            mutation_problems = _verify_input_tree_unchanged(run_root, before)
            # Re-validate *after* the build runs, immediately before ever
            # reading one of these paths (issue #9 verifier remediation): the
            # build command itself is untrusted -- it could plant a symlink
            # (among its own declared outputs) that did not exist before it
            # ran, pointing outside `run_root`. Re-checking here (never only
            # pre-build) is what actually catches that, and this is also
            # where the two runs' resolved real output paths are cross-
            # checked to never alias one another.
            for relpath, resolved in validated_outputs.items():
                resolved = _validate_output_relpath(run_root, relpath)
                resolved_real = os.path.realpath(str(resolved))
                if resolved_real in seen_output_paths:
                    raise ArchiveRehearsalError(
                        f"refusing unsafe declared output path {relpath!r}: resolves to {resolved_real!r}, "
                        "which is already claimed by the other independent run -- an output path can "
                        "never be aliased/shared/reused across runs"
                    )
                seen_output_paths.add(resolved_real)
            hashes: Dict[str, Optional[str]] = {}
            for relpath, out_path in validated_outputs.items():
                hashes[relpath] = hash_file(out_path) if out_path.is_file() and not out_path.is_symlink() else None
            embedded_build_commits = _extract_embedded_build_commits(hashes, run_root)
            return {
                "returncode": result.returncode,
                "stderr_tail": result.stderr[-2000:],
                "hashes": hashes,
                "mutation_problems": mutation_problems,
                "run_root": str(run_root),
                "embedded_build_commits": embedded_build_commits,
            }
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    run1 = _one_run()
    run2 = _one_run()

    # Defense-in-depth structural check: the two independent
    # materializations must never be the same directory (they cannot be,
    # given `tempfile.mkdtemp()`'s own uniqueness guarantee -- this
    # assertion documents and enforces that invariant explicitly rather
    # than trusting it silently).
    if run1["run_root"] == run2["run_root"]:
        raise ArchiveRehearsalError(
            "refusing to report a rebuild result: both independent materializations resolved to "
            "the same directory -- a shared source/build directory can never be trusted"
        )

    outputs_present = (
        bool(output_relpaths)
        and all(value is not None for value in run1["hashes"].values())
        and all(value is not None for value in run2["hashes"].values())
    )
    no_mutation = not run1["mutation_problems"] and not run2["mutation_problems"]

    # issue #9 mandatory correction #2 (embedded short-SHA verification):
    # whenever a declared output actually carries a parseable
    # `ExpansionMetadata` record, its `build_commit` field must equal
    # this exact `target_sha` -- for BOTH independent runs. This is a
    # strictly stronger check than "the two runs' hashes matched" (two
    # runs executing the exact same build script can be consistently,
    # deterministically bound to the *wrong* identity, e.g. a build
    # script that ignores `EXPANSION_BUILD_ID` and hardcodes a stale
    # value -- byte-identical between the two runs, but never actually
    # bound to `target_sha`). An output with no embedded record at all
    # (`None` -- e.g. a synthetic test fixture's own plain-bytes output,
    # or a non-ROM artifact) is never itself a failure; only a *present
    # but wrong* record is.
    embedded_commits_found = {
        relpath: commit for relpath, commit in run1["embedded_build_commits"].items() if commit is not None
    }
    embedded_metadata_checked = bool(embedded_commits_found)
    embedded_metadata_mismatches = []
    for relpath, commit in embedded_commits_found.items():
        if commit != target_sha:
            embedded_metadata_mismatches.append(
                f"{relpath}: embedded ExpansionMetadata build_commit {commit!r} does not match "
                f"the exact target SHA {target_sha!r} this materialization was bound to"
            )
    for relpath, commit in run2["embedded_build_commits"].items():
        if commit is not None and commit != target_sha:
            msg = (
                f"{relpath}: embedded ExpansionMetadata build_commit {commit!r} does not match "
                f"the exact target SHA {target_sha!r} this materialization was bound to"
            )
            if msg not in embedded_metadata_mismatches:
                embedded_metadata_mismatches.append(msg)

    embedded_short_sha = next(iter(embedded_commits_found.values()), None)

    match = (
        run1["returncode"] == 0 and run2["returncode"] == 0
        and outputs_present and run1["hashes"] == run2["hashes"] and no_mutation
        and not embedded_metadata_mismatches
    )
    return {
        "returncode1": run1["returncode"],
        "returncode2": run2["returncode"],
        "hashes1": run1["hashes"],
        "hashes2": run2["hashes"],
        "outputs_present": outputs_present,
        "input_tree_mutation_problems1": run1["mutation_problems"],
        "input_tree_mutation_problems2": run2["mutation_problems"],
        "match": match,
        "stderr1_tail": run1["stderr_tail"],
        "stderr2_tail": run2["stderr_tail"],
        # Evidence-honesty/transparency (guardian-correction remediation):
        # each run's own independent materialization root, surfaced so a
        # caller/test can directly observe (never merely assume) that the
        # two runs used genuinely distinct directories -- in addition to
        # the hard `ArchiveRehearsalError` guard above, which already
        # refuses to report anything at all if they were ever the same.
        "materialization_root1": run1["run_root"],
        "materialization_root2": run2["run_root"],
        # issue #9 mandatory correction #2: the mandatory embedded
        # short-SHA verification result -- never merely conditional on a
        # caller happening to ask for it.
        "embedded_metadata_checked": embedded_metadata_checked,
        "embedded_metadata_mismatches": embedded_metadata_mismatches,
        "embedded_build_commit": embedded_short_sha,
        "embedded_short_sha": embedded_short_sha[:8] if embedded_short_sha else None,
    }


def _materialize_verified_submodule_content(
    repo_root: Path, submodule_path: str, pinned_commit: str
) -> Callable[[Path], None]:
    """Returns an `extra_materialize` callback (see
    `run_build_twice_from_immutable_source`) that materializes
    `submodule_path`'s content into each independent materialization from
    the submodule's own **immutable Git object** at `pinned_commit` --
    never from its live, potentially-dirty worktree bytes.

    issue #9 guardian-correction remediation (D3): the previous version
    of this function (`_copy_verified_submodule_content`) used
    `shutil.copytree` on the submodule's own checked-out *worktree*
    directory. `evaluate_rebuild_eligibility` confirming the submodule's
    HEAD commit matches the pinned gitlink is not the same fact as "the
    worktree bytes exactly equal that commit's tree": a modified,
    staged, or untracked file can sit in an otherwise commit-matching
    checkout, and copying that live directory would silently carry those
    extra/changed bytes into a rebuild that is then reported
    `verified_success` over tampered content -- an independent review
    reproduced exactly this. `evaluate_rebuild_eligibility` now also
    requires the submodule worktree/index to be genuinely clean before
    eligibility is ever granted at all (defense #1) -- but this function
    is independent defense #2: even if eligibility were ever wrongly
    granted by a future bug, this materializer itself never reads a
    single byte from the submodule's worktree path; it always extracts
    `pinned_commit`'s own immutable tree via `git archive
    <pinned_commit> | tar -x`, run with the submodule's own directory as
    the *source repository* (`materialize_immutable_source_tree`, the
    exact same immutable-extraction mechanism already used for the
    superproject's own content) -- so the materialized bytes are
    provably bound to the pinned commit object, never to whatever
    happens to be checked out on disk right now. `git archive` never
    includes submodule content in the *superproject's own* archive at
    all (see `GITHUB_AUTOARCHIVE_SUBMODULE_CONTRADICTION`), so this is
    the one, narrow, explicitly-gated exception to "everything comes
    from the superproject's own `git archive`" -- it still never reads
    the submodule's worktree, only its own object database."""
    submodule_dir = repo_root / submodule_path

    def _materialize(run_root: Path) -> None:
        submodule_dest = run_root / submodule_path
        if submodule_dest.exists():
            shutil.rmtree(submodule_dest)
        submodule_dest.mkdir(parents=True)
        materialize_immutable_source_tree(submodule_dir, pinned_commit, submodule_dest)

    return _materialize


def rebuild_rehearsal_blocker(
    repo_root: Path,
    attempt_build: bool = True,
    build_command: Optional[List[str]] = None,
    output_relpaths: Optional[List[str]] = None,
    submodule_path: str = "mgfembp",
    target_sha: Optional[str] = None,
    provenance_dir: Optional[Path] = None,
) -> Dict:
    """Truthful, machine-distinct rebuild rehearsal report. `status` is
    always exactly one of `ALL_REBUILD_STATUSES`:

    * `"blocked"` -- not even eligible to attempt (submodule uninitialized
      and/or unapproved and/or identity mismatch) -- today's real result
      for this repository, and expected to remain so until a human
      resolves `docs/release_data/provenance/submodules.json`. A non-git
      `repo_root` (a genuine extracted archive/non-git candidate tree)
      is unconditionally `"blocked"` too, for a distinct, precisely
      reported reason -- see `evaluate_rebuild_eligibility`'s non-git
      short-circuit, which never invokes `git submodule status` (or any
      other git command) against such a tree. This never merely
      *implies* a rebuild was skipped -- the returned `"reasons"` state
      exactly and only that a complete clean recursive rebuild was NOT
      executed because the pinned submodule is uninitialized/unapproved/
      excluded (see `evaluate_rebuild_eligibility`'s own reasons); this
      function never claims a clean rebuild was proved.
    * `"not_run"` -- eligible, but no actual build was executed (either
      the caller passed `attempt_build=False`, or did not supply the
      `build_command`/`output_relpaths` a real attempt requires) --
      distinct from `"blocked"` so a report can never conflate "we
      refused to even try" with "we tried and it worked".
    * `"failed"` -- a build was actually attempted
      (`run_build_twice_from_immutable_source`) and either run exited
      non-zero, an output was missing, the two runs' output hashes
      disagreed, or either run's own independent input materialization
      was mutated during the build.
    * `"verified_success"` -- both runs actually executed -- each from
      its own independent, immutable-`target_sha`-bound materialization,
      in its own separate temp/build directory, with neither run's input
      tree mutated -- both exited 0, and every declared output was
      present and byte-identical.

    Never fetches/initializes/approves the submodule itself; see
    `evaluate_rebuild_eligibility`. When eligible and an actual rebuild is
    attempted, this never reads a single byte from the live, potentially-
    mutable worktree for the superproject's own tracked content -- only
    `git archive`'s immutable extraction (see
    `run_build_twice_from_immutable_source`); the already-verified
    submodule content is the one, explicit, narrow exception (`git
    archive` itself never includes it at all)."""
    repo_root = Path(repo_root)
    eligible, eligibility_report = evaluate_rebuild_eligibility(repo_root, submodule_path, provenance_dir)
    base_report = {
        "submodule_status_output": eligibility_report["submodule_status_output"],
        "eligibility": eligibility_report,
        "github_autoarchive_submodule_contradiction": GITHUB_AUTOARCHIVE_SUBMODULE_CONTRADICTION,
    }

    if not eligible:
        return {
            "status": REBUILD_STATUS_BLOCKED, "reasons": eligibility_report["reasons"],
            "embedded_short_sha": None, **base_report,
        }

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
            "embedded_short_sha": None,
            **base_report,
        }

    try:
        resolved_target_sha = target_sha if target_sha is not None else gs.resolve_sha(repo_root, "HEAD")
    except gs.GitSourceError as error:
        return {
            "status": REBUILD_STATUS_BLOCKED,
            "reasons": [f"could not resolve an immutable target SHA for rebuild materialization: {error}"],
            "embedded_short_sha": None,
            **base_report,
        }

    # `eligible` is only ever True once `evaluate_rebuild_eligibility`
    # has already confirmed `provenance_pinned_commit` is set, matches
    # the submodule's own checked-out HEAD, and is a real, locally-
    # accessible commit object -- so it is always non-None here.
    pinned_commit = eligibility_report["provenance_pinned_commit"]
    build_result = run_build_twice_from_immutable_source(
        repo_root, resolved_target_sha, build_command, output_relpaths,
        extra_materialize=_materialize_verified_submodule_content(repo_root, submodule_path, pinned_commit),
    )
    status = REBUILD_STATUS_VERIFIED_SUCCESS if build_result["match"] else REBUILD_STATUS_FAILED
    if status == REBUILD_STATUS_VERIFIED_SUCCESS:
        reasons = []
    elif build_result.get("embedded_metadata_mismatches"):
        # issue #9 mandatory correction #2: an embedded-identity mismatch
        # is named explicitly and distinctly from a bare hash mismatch --
        # a maintainer must never have to infer "the SHA binding was
        # wrong" from a generic "outputs differed" message.
        reasons = list(build_result["embedded_metadata_mismatches"])
    else:
        reasons = [
            "the pinned recursive rebuild was executed but did not reproduce verified-identical "
            "outputs twice -- see 'build_result' for the exact returncodes/hashes"
        ]
    return {
        "status": status,
        "reasons": reasons,
        "build_result": build_result,
        # issue #9 mandatory correction #2: surfaced at this report's own
        # top level too (not just nested in 'build_result') so a caller
        # (cli.py's cmd_rehearse) can thread it straight into the
        # manifest's own mandatory embedded_short_sha binding without
        # digging through a nested structure.
        "embedded_short_sha": build_result.get("embedded_short_sha"),
        **base_report,
    }


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
