#!/usr/bin/env python3
"""Exact, deterministic per-member source allowlist (issue #9 verifier
remediation).

``docs/release_data/source_allowlist.json`` used to grant an entire
top-level directory (e.g. ``"src"``) at once -- any file added anywhere
under an allowlisted directory was implicitly included. That is exactly
the "top-level directory allowlisting" the independent verifier flagged:
it cannot express "this specific new tracked file was never reviewed".

This module is the fix: it is the single canonical generator *and*
validator for an exact, file-level allowlist, driven directly by Git's own
tracked-file/gitlink listing (``git ls-files``, ``git ls-tree``) rather
than any second, hand-maintained notion of "the source tree". Every
regular tracked file gets its own exact entry; the ``mgfembp`` submodule
gitlink gets its own single exact entry (its *contents* are never
enumerated -- see docs/release_process.md's submodule/provenance
boundary, unchanged by this module).

``check_allowlist_completeness()`` is the fail-closed gate wired into
``scripts/release_rehearsal/manifest.py``: it is a full bijection check
between "every currently tracked file/gitlink" and "every allowlist
entry" -- a new tracked file with no allowlist entry fails exactly as
loudly as a stale allowlist entry for a file that no longer exists
(``git status``/history cannot silently drift the allowlist out of sync
with reality in either direction).

Deliberately dependency-free (Python stdlib only; reuses
``scripts/release_rehearsal/git_source.py``'s plumbing wrappers rather
than re-invoking git directly).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from scripts.release_rehearsal import git_source as gs
from scripts.release_rehearsal import tree_coverage as tc

SCHEMA_VERSION = 4
DEFAULT_ALLOWLIST_PATH = Path("docs/release_data/source_allowlist.json")
DEFAULT_EXCLUSIONS_PATH = Path("docs/release_data/export_exclusions.json")

# issue #9 guardian-correction remediation (mode binding): the only Git
# blob modes an allowlist entry may ever declare -- a gitlink (`160000`)
# is never a member here at all (see `generate_entries` below), so it is
# deliberately absent from this tuple; an unrecognized/unsupported mode
# (e.g. a raw `040000` tree entry, which should never surface from
# `git ls-tree -r` at all) is a hard, actionable `AllowlistError`.
VALID_ALLOWLIST_MODES = (gs.MODE_REGULAR, gs.MODE_EXECUTABLE, gs.MODE_SYMLINK)


class AllowlistError(ValueError):
    """An actionable schema/consistency defect in the allowlist file
    itself (distinct from a normal "these files are unlisted" finding,
    which is reported as a list of strings, not raised)."""


def generate_entries(
    repo_root: Path, target_sha: str, excluded_blob_paths: Iterable[str] = ()
) -> List[str]:
    """Exact, deterministic (git-tree-ordered) list of every path that
    must appear in the allowlist for `target_sha`: every blob-mode tree
    entry (regular file or executable; a tracked *symlink*, if one is ever
    added, is deliberately still listed here too -- omitting it would only
    hide the problem, and `source_guard.py`'s own hard-deny check is what
    actually rejects it).

    A gitlink (submodule mountpoint, e.g. `mgfembp`) is deliberately
    **excluded** here (schema_version 3 / issue #9 mandatory correction
    #2) -- it has no blob content in this repository's own tree to
    archive at all, and is instead recorded as its own explicit,
    factual export-exclusion entry (exact path, kind, immutable OID, and
    reason) in `docs/release_data/export_exclusions.json` -- see
    `scripts/release_rehearsal/tree_coverage.py`, which mechanically
    proves this allowlist's included paths and that file's excluded
    paths are an exact, disjoint partition of the complete tree (nothing
    is silently absorbed into either side, and nothing is silently
    unaccounted for).

    `excluded_blob_paths` (guardian-correction remediation) additionally
    excludes any ordinary tracked *blob* the caller has declared an
    explicit, non-gitlink export exclusion for (today, exactly
    `docs/release_data/provenance/code.json` -- see
    `tree_coverage.KIND_SELF_REFERENTIAL_EVIDENCE`): such a path is a
    real blob (not a gitlink), but is still never an included allowlist
    member, for the same "this is recorded as its own explicit,
    factual export-exclusion entry" reason as a gitlink -- never a
    silent, unexplained gap."""
    excluded = set(excluded_blob_paths)
    entries = [
        entry.path for entry in gs.list_tree(repo_root, target_sha)
        if not entry.is_gitlink and entry.path not in excluded
    ]
    return sorted(entries)


def generate_modes(
    repo_root: Path, target_sha: str, excluded_blob_paths: Iterable[str] = ()
) -> Dict[str, str]:
    """Exact `{path: git_mode}` map for every path `generate_entries`
    would also return (the same included-blob set, same exclusions) --
    guardian-correction remediation (mode binding): an included path's
    exact Git mode (`100644`/`100755`/`120000`) is bound alongside its
    mere path string, so a committed executable-bit (or other mode)
    change is detected as staleness (see `check_mode_identity`) instead
    of being invisible to this allowlist."""
    excluded = set(excluded_blob_paths)
    return {
        entry.path: entry.mode
        for entry in gs.list_tree(repo_root, target_sha)
        if not entry.is_gitlink and entry.path not in excluded
    }


def generate_allowlist_document(
    repo_root: Path, target_sha: str, excluded_blob_paths: Iterable[str] = ()
) -> Dict:
    entries = generate_entries(repo_root, target_sha, excluded_blob_paths)
    modes = generate_modes(repo_root, target_sha, excluded_blob_paths)
    return {
        "_comment": (
            "Exact, deterministic, per-member source-release allowlist (issue #9 "
            "verifier remediation; schema_version 3 excludes gitlinks -- see "
            "mandatory correction #2; schema_version 4 adds the 'modes' exact-"
            "Git-mode binding -- see guardian-correction remediation). Every "
            "'paths' entry is one exact repo-relative tracked *blob* path "
            "(regular file, executable, or symlink) -- there is "
            "no directory-level/prefix grant, and a gitlink (submodule mountpoint) "
            "is never included here at all; it is instead an explicit export "
            "exclusion -- see docs/release_data/export_exclusions.json and "
            "scripts/release_rehearsal/tree_coverage.py, which proves this "
            "allowlist and that exclusions file are an exact, disjoint partition "
            "of the complete tree. An ordinary tracked blob that is itself "
            "structurally self-referential (currently exactly "
            "docs/release_data/provenance/code.json) is likewise never a 'paths' "
            "member -- it too is an explicit, non-gitlink export exclusion (see "
            "tree_coverage.py's KIND_SELF_REFERENTIAL_EVIDENCE). 'modes' records "
            "every 'paths' entry's own exact Git mode (100644/100755/120000), "
            "cross-checked against the live tree by check_mode_identity() -- a "
            "committed executable-bit (or other mode) change makes this data "
            "stale until regenerated, exactly like a content/path change already "
            "does. The archive itself still always canonicalizes every member's "
            "*written* tar mode to a fixed 0o644 regardless of this recorded Git "
            "mode (see archive_rehearsal.py's CANONICAL_FILE_MODE and "
            "docs/release_process.md's 'Archive member mode policy') -- this "
            "field is a drift-detection/provenance-identity binding, not an "
            "archive-fidelity guarantee. Generated by "
            "'python3 -m scripts.release_rehearsal.allowlist generate'; regenerate "
            "and commit this file whenever a tracked file is added, renamed, "
            "removed, or has its Git mode changed (`make release-check` / "
            "`python3 -m scripts.release_rehearsal.allowlist check` fails "
            "actionably if this file and the actual tracked-file/mode set ever "
            "disagree). This is a "
            "structural membership allowlist only -- see "
            "docs/release_data/provenance/*.json and docs/release_process.md for "
            "the separate, currently-unresolved legal/provenance determination "
            "that independently blocks publication regardless of this allowlist. "
            "'generation_basis_sha' is a documentary record of which commit this "
            "file was last regenerated against ONLY -- it is never read, "
            "compared, or otherwise validated by check()/check_mode_identity() "
            "or any other check in this repository (every check instead always "
            "re-derives its own live target_sha independently); do not mistake "
            "its presence for a validated commit binding of any kind."
        ),
        "schema_version": SCHEMA_VERSION,
        "generation_basis_sha": target_sha,
        "generator": "python3 -m scripts.release_rehearsal.allowlist generate",
        "paths": entries,
        "modes": modes,
    }


def load_allowlist_paths(path: Path) -> List[str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AllowlistError(f"{path}: not valid JSON: {error}") from error
    paths = data.get("paths")
    if not isinstance(paths, list) or not paths:
        raise AllowlistError(f"{path}: must contain a non-empty 'paths' array")
    if len(paths) != len(set(paths)):
        seen = set()
        dupes = sorted({p for p in paths if (p in seen or seen.add(p))})
        raise AllowlistError(f"{path}: duplicate entries: {dupes}")
    return paths


def load_allowlist_modes(path: Path) -> Dict[str, str]:
    """Loads the same allowlist document's mandatory `"modes"` mapping
    (guardian-correction remediation: mode binding; issue #9 R5 fix:
    mode-binding enforcement can no longer be silently disabled by
    deleting this key, or by tampering with `schema_version`, since a
    prior version of this function treated an absent `"modes"` key as
    "an older document that predates mode-binding, so skip validation
    entirely" -- an independent review correctly found that `schema_
    version` itself was never actually checked anywhere, so that silent
    fallback was reachable simply by deleting `"modes"` from the real,
    current, schema_version-4 checked-in document).

    `schema_version` must be present and exactly equal to
    `SCHEMA_VERSION` (an `int`, compared with `!=` so a wrong *type*,
    e.g. the string `"4"`, is rejected exactly like a wrong value) --
    any missing, downgraded, or unknown/future schema_version is a hard
    `AllowlistError` raised *before* any mode checking runs at all. This
    is deliberately not a soft "older document that predates
    mode-binding" fallback: every real, checked-in allowlist document in
    this repository has always been schema_version 4 (mode-binding and
    schema_version were introduced together), so there is no legitimate
    historical document to stay backward-compatible with -- an
    unexpected schema_version here is exclusively evidence of tampering
    or a broken generator, never a benign case to silently accommodate.

    Given a valid, current schema_version, `"modes"` itself is then
    unconditionally mandatory: an entirely absent key is exactly as hard
    an `AllowlistError` as a malformed one. When present, it must be a
    non-empty JSON object mapping an exact path to one of
    `VALID_ALLOWLIST_MODES` -- a malformed shape or an unsupported mode
    value is a hard `AllowlistError`, exactly like a malformed `"paths"`
    array."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise AllowlistError(
            f"{path}: unsupported schema_version {schema_version!r} (expected exactly "
            f"{SCHEMA_VERSION!r}); a missing, downgraded, or unknown/future schema_version is "
            "never silently tolerated, and mode-binding enforcement cannot be disabled this way"
        )
    if "modes" not in data:
        raise AllowlistError(
            f"{path}: schema_version {SCHEMA_VERSION} requires a 'modes' mapping; deleting or "
            "omitting this key does not disable mode-binding enforcement"
        )
    modes = data["modes"]
    if not isinstance(modes, dict) or not modes:
        raise AllowlistError(f"{path}: 'modes' must be a non-empty JSON object mapping path -> Git mode")
    for entry_path, mode in modes.items():
        if not isinstance(mode, str) or mode not in VALID_ALLOWLIST_MODES:
            raise AllowlistError(
                f"{path}: mode {mode!r} for {entry_path!r} is not a supported blob mode "
                f"(expected one of {VALID_ALLOWLIST_MODES})"
            )
    return modes


def check_mode_bijection(
    allowlist_paths: Iterable[str], allowlist_modes: Dict[str, str]
) -> Tuple[List[str], List[str]]:
    """`(missing, extra)`: `missing` is an allowlist path with no
    recorded mode at all; `extra` is a recorded mode for a path that is
    not (or is no longer) an allowlist path. Both must be empty for a
    well-formed, exactly-synchronized `"modes"` mapping."""
    paths_set = set(allowlist_paths)
    modes_set = set(allowlist_modes)
    return sorted(paths_set - modes_set), sorted(modes_set - paths_set)


def check_mode_identity(
    repo_root: Path, allowlist_modes: Dict[str, str], target_sha: str = "HEAD"
) -> List[str]:
    """Cross-checks every declared mode in `allowlist_modes` against the
    actual, live Git mode Git's own tree records for that exact path at
    `target_sha` -- guardian-correction remediation (mode binding),
    mirroring `provenance.check_blob_identity`'s "never trust the
    record, cross-check it against Git itself" discipline. A committed
    executable-bit (or other mode) change, or a path that is no longer a
    live tracked blob at all, is reported -- never silently trusted."""
    tree = {entry.path: entry for entry in gs.list_tree(repo_root, target_sha)}
    reasons: List[str] = []
    for path, declared_mode in sorted(allowlist_modes.items()):
        tree_entry = tree.get(path)
        if tree_entry is None or tree_entry.is_gitlink:
            reasons.append(
                f"{path}: no tracked blob at this exact path in the tree at {target_sha!r} to "
                f"cross-check its declared mode {declared_mode!r} against (missing/stale -- "
                "regenerate the allowlist)"
            )
            continue
        if tree_entry.mode != declared_mode:
            reasons.append(
                f"{path}: declared mode {declared_mode!r} does not match the actual Git mode "
                f"{tree_entry.mode!r} Git's tree records at {target_sha!r} (a committed "
                "executable-bit/mode change -- regenerate the allowlist)"
            )
    return reasons


def check_allowlist_completeness(
    repo_root: Path, allowlist_paths: List[str], target_sha: str = "HEAD",
    excluded_blob_paths: Iterable[str] = (),
) -> Tuple[List[str], List[str]]:
    """Full bijection check between the exact, resolved tracked-*blob*
    set at `target_sha` and `allowlist_paths`. Returns `(missing,
    stale)`:

    * `missing` -- tracked blob paths with **no** allowlist entry at all
      (the literal "a new/unlisted tracked file must fail" case).
    * `stale` -- allowlist entries that do not correspond to any currently
      tracked blob path (a "ghost"/stale entry left behind after a file
      was renamed or deleted -- allowed to drift silently, this would let
      the allowlist quietly grow stale forever and no longer reflect
      reality).

    Both must be empty for a well-formed, exactly-synchronized allowlist.

    A tracked **gitlink** (e.g. the `mgfembp` submodule mountpoint) is
    deliberately excluded from `tracked` here (schema_version 3 / issue
    #9 mandatory correction #2) -- it is never expected to have an
    allowlist entry any more; it instead belongs to the separate,
    explicit export-exclusions set (see
    `scripts/release_rehearsal/tree_coverage.py`'s `check_partition`,
    which is what actually proves *every* tracked path -- blob or
    gitlink -- is accounted for exactly once between this allowlist and
    that exclusions file). `excluded_blob_paths` (guardian-correction
    remediation) additionally excludes any ordinary tracked *blob* the
    caller has declared its own explicit, non-gitlink export exclusion
    for (see `generate_entries`) from `tracked` the same way."""
    excluded = set(excluded_blob_paths)
    tracked = {
        entry.path for entry in gs.list_tree(repo_root, target_sha)
        if not entry.is_gitlink and entry.path not in excluded
    }
    allowlist_set = set(allowlist_paths)
    missing = sorted(tracked - allowlist_set)
    stale = sorted(allowlist_set - tracked)
    return missing, stale


def _present_paths(repo_root: Path) -> List[str]:
    """Every filesystem entry actually present on disk under
    `repo_root`, of **any** kind (regular file, symlink, hardlink,
    device, FIFO, socket, or any other non-regular node; only a genuine,
    non-symlink directory is ever walked through rather than reported)
    -- the non-git equivalent of a tracked-file listing, used **only**
    when `repo_root` has no `.git` metadata at all (`git_source.
    is_git_repo` is False; a genuine extracted archive/non-git candidate
    tree). Never invokes git -- issue #9 verifier remediation: a non-git
    candidate tree must never have git plumbing invoked against it
    (which could otherwise silently walk *upward* to an unrelated
    enclosing repository and report *that* repository's tracked files
    instead of failing closed).

    Guardian-correction remediation (closed-world symlink fix): a
    previous version of this walk (`_present_regular_files`) `continue`d
    straight past any symlink it found, which made a stray, unlisted
    symlink at *any* path completely invisible to `check_allowlist_
    completeness_non_git`'s `missing` accounting below. Nothing is
    skipped by kind any more."""
    repo_root = Path(repo_root)
    present: List[str] = []

    def _walk(dirpath: Path) -> None:
        with os.scandir(dirpath) as it:
            entries = sorted(it, key=lambda e: e.name)
        for entry in entries:
            if dirpath == repo_root and entry.name == ".git":
                continue
            full = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                _walk(full)
                continue
            present.append(full.relative_to(repo_root).as_posix())

    _walk(repo_root)
    return present


def _entry_has_on_disk_representation(repo_root: Path, entry: str) -> bool:
    """True if allowlist entry `entry` corresponds to *some* real,
    non-symlink file or directory in a non-git candidate tree. A
    directory match covers a gitlink-style mountpoint (e.g. the
    "mgfembp" submodule path): a real git-tracked tree always records
    that path as its own tree entry with no blob content at all (see
    git_source.py's MODE_GITLINK), and a genuine extracted archive
    (e.g. GitHub's auto-generated source archive) materializes it as an
    empty directory -- it is never itself required to contain
    anything, exactly like a real gitlink. A symlink at `entry` never
    counts as a representation (consistent with
    `_filesystem_allowlisted_files`, which also never treats a symlink
    as safe content)."""
    candidate = Path(repo_root) / entry
    if candidate.is_symlink():
        return False
    return candidate.is_file() or candidate.is_dir()


def check_allowlist_completeness_non_git(
    repo_root: Path, allowlist_paths: List[str], excluded_blob_paths: Iterable[str] = (),
) -> Tuple[List[str], List[str]]:
    """The non-git analogue of `check_allowlist_completeness`, used
    **only** when `repo_root` has no `.git` at all (a genuine extracted
    archive/non-git candidate tree -- see `git_source.is_git_repo`).
    There is no git-tracked-file notion to consult here at all -- issue
    #9 verifier remediation requires this to closed-world-validate the
    *actual on-disk membership* of the extracted tree against the
    checked-in allowlist instead, and to never invoke git plumbing
    against such a tree (there is nothing to invoke it against, and
    doing so anyway could silently produce a result bound to an
    unrelated enclosing repository rather than this tree). Returns
    `(missing, unrepresented)`:

    * `missing` -- an ordinary regular file physically present in the
      extracted tree whose own exact path has no allowlist entry at all
      (the non-git analogue of "a new/unlisted tracked file").
    * `unrepresented` -- an allowlist entry with **no** on-disk
      representation whatsoever in this extracted tree -- neither as a
      regular file nor (for a gitlink-style entry such as the "mgfembp"
      submodule mountpoint) as a directory. This is the precise
      "missing/unrepresented gitlink/mgfembp" blocker a genuine
      extracted candidate must report rather than silently ignore.

    A directory is never itself required to have its *contents*
    individually re-validated here (mirrors
    scripts/release_rehearsal/source_guard.py's "structural parent
    only, never an authorization prefix" rule) -- only whether the
    allowlisted path itself has *some* real, non-symlink on-disk form.

    `excluded_blob_paths` (guardian-correction remediation) is removed
    from consideration entirely here (neither required present nor ever
    flagged "missing") -- a non-gitlink export exclusion (e.g. the
    self-referential-evidence provenance manifest) is never part of this
    allowlist-bijection contract at all;
    `tree_coverage.check_non_git_tree` is what actually, precisely
    validates such a path's on-disk shape (it must be genuinely absent).
    """
    excluded = set(excluded_blob_paths)
    present_files = set(_present_paths(repo_root)) - excluded
    allowlist_set = set(allowlist_paths)
    missing = sorted(present_files - allowlist_set)
    unrepresented = sorted(
        entry for entry in allowlist_set
        if not _entry_has_on_disk_representation(repo_root, entry)
    )
    return missing, unrepresented


def _load_non_gitlink_exclusion_paths(exclusions_path: Path) -> List[str]:
    """issue #9 closing-round fix: this used to be its own minimal,
    permissive, local JSON reader that accepted *any* exclusion entry
    whose `kind` merely was not the literal string `"gitlink"` -- no
    curated-path check, no `oid` shape check at all. That meant an
    arbitrary tracked path, or a `self_referential_evidence`-kind row
    carrying a fabricated/stale `oid`, could make this allowlist's own
    sub-report (`check()`) come back perfectly clean while
    `tree_coverage.check_partition()`, reading the *exact same file*,
    already rejected it outright -- an asymmetry an independent review
    correctly flagged as a live consumer-side bypass, not merely an
    unused permissive convention.

    This function now does no schema interpretation of its own at all:
    it delegates entirely to `tree_coverage.load_exclusion_paths()`,
    restricted to `tree_coverage.KIND_SELF_REFERENTIAL_EVIDENCE` (the
    only non-`"gitlink"` kind `tree_coverage.VALID_EXCLUSION_KINDS`
    permits at all, so this restriction is exactly equivalent in scope
    to the old "kind != gitlink" filter) -- the same curated
    `SELF_REFERENTIAL_EVIDENCE_PATHS` policy set, the same mandatory
    `oid is None` shape check, and every other `load_exclusions()`
    invariant now apply here identically, not as a second,
    independently-implemented (and, as found, more permissive) reader
    that could silently drift out of sync with the real one.

    Returns `[]` if `exclusions_path` does not exist at all (unchanged
    from before this fix) -- this allowlist has always worked standalone
    without one (a gitlink is already excluded via pure Git-tree data
    alone; only a *non-gitlink* export exclusion, e.g. the
    self-referential-evidence provenance manifest, needs this extra,
    explicit path list, since nothing about its own tree entry otherwise
    distinguishes it from an ordinary included blob). Any schema/
    curated-policy defect `tree_coverage.load_exclusions()` would raise
    (an arbitrary/uncurated path, a fabricated/stale/non-null `oid`, a
    malformed shape, etc.) is re-raised here as an `AllowlistError`, so
    every caller of this function keeps failing exactly the same way it
    always has, just against a strictly correct, shared implementation."""
    path = Path(exclusions_path)
    if not path.is_file():
        return []
    try:
        return tc.load_exclusion_paths(path, kinds=(tc.KIND_SELF_REFERENTIAL_EVIDENCE,))
    except tc.TreeCoverageError as error:
        raise AllowlistError(str(error)) from error


def check(
    repo_root: Path, allowlist_path: Path, target_sha: str = "HEAD",
    exclusions_path: Path = DEFAULT_EXCLUSIONS_PATH,
) -> List[str]:
    """Convenience wrapper returning a flat, human-readable error list
    (empty means fully consistent); used by both the CLI and
    scripts/release_rehearsal/manifest.py.

    Dispatches on whether `repo_root` actually is a git repository
    (`git_source.is_git_repo`) -- issue #9 verifier remediation: a
    non-git candidate tree (a genuine extracted archive) is
    closed-world-validated against on-disk membership
    (`check_allowlist_completeness_non_git`) and never causes a `git`
    invocation at all; only a real git working tree uses
    `check_allowlist_completeness`'s git-tracked-file bijection. A
    well-formed 40-lowercase-hex `target_sha` that does not resolve to a
    real object in an actual git repository still raises
    `git_source.GitSourceError` here (propagated, never swallowed into a
    soft warning): that is an actionable input defect for the CLI's
    single top-level exception boundary to convert into
    `EXIT_TOOLING_ERROR`, not an honestly-recorded business fact.

    Guardian-correction remediation: also cross-checks the allowlist
    document's mandatory `"modes"` mapping (see `load_allowlist_modes`)
    -- issue #9 R5 fix: `schema_version`/`"modes"` are validated (and a
    missing/downgraded/unknown schema_version or a deleted `"modes"` key
    is a hard, actionable finding here, via the `AllowlistError` caught
    below) *before* any mode checking runs, so mode-binding enforcement
    can never be silently disabled -- a bijection check always, plus a
    live Git-mode identity cross-check (`check_mode_identity`) when
    `repo_root` is a real git repository -- and excludes any non-gitlink
    export-exclusion path (see `_load_non_gitlink_exclusion_paths`) from
    the tracked-blob bijection, exactly like a gitlink has always been
    excluded."""
    try:
        allowlist_paths = load_allowlist_paths(allowlist_path)
        allowlist_modes = load_allowlist_modes(allowlist_path)
        excluded_blob_paths = _load_non_gitlink_exclusion_paths(exclusions_path)
    except AllowlistError as error:
        return [str(error)]
    repo_root = Path(repo_root)
    if not gs.is_git_repo(repo_root):
        missing, unrepresented = check_allowlist_completeness_non_git(
            repo_root, allowlist_paths, excluded_blob_paths
        )
        errors = [
            f"file present in extracted tree but missing from allowlist: {path}"
            for path in missing
        ]
        errors += [
            "allowlisted member has no on-disk representation in this extracted tree "
            f"(missing/unrepresented -- e.g. an absent gitlink mountpoint such as "
            f"'mgfembp', or a removed/never-extracted file): {path}"
            for path in unrepresented
        ]
        mode_missing, mode_extra = check_mode_bijection(allowlist_paths, allowlist_modes)
        errors += [f"allowlist path has no recorded 'modes' entry: {path}" for path in mode_missing]
        errors += [
            f"recorded 'modes' entry for a path that is not (or is no longer) an allowlist entry: {path}"
            for path in mode_extra
        ]
        return errors
    missing, stale = check_allowlist_completeness(repo_root, allowlist_paths, target_sha, excluded_blob_paths)
    errors = [f"tracked file missing from allowlist: {path}" for path in missing]
    errors += [f"stale allowlist entry (no longer tracked): {path}" for path in stale]
    mode_missing, mode_extra = check_mode_bijection(allowlist_paths, allowlist_modes)
    errors += [f"allowlist path has no recorded 'modes' entry: {path}" for path in mode_missing]
    errors += [
        f"recorded 'modes' entry for a path that is not (or is no longer) an allowlist entry: {path}"
        for path in mode_extra
    ]
    errors += check_mode_identity(repo_root, allowlist_modes, target_sha)
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo-root", type=Path, default=Path("."))
    common.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST_PATH)
    common.add_argument("--exclusions", type=Path, default=DEFAULT_EXCLUSIONS_PATH)
    common.add_argument(
        "--target-sha", default="HEAD",
        help="a commit-ish (default HEAD), or the literal 'index' to use the "
             "current staged index (via 'git write-tree') -- a development-time "
             "convenience for generating/checking the allowlist before committing",
    )

    sub.add_parser("check", parents=[common], help="verify the checked-in allowlist is exact")
    gen = sub.add_parser("generate", parents=[common], help="print a freshly-generated allowlist document")
    gen.add_argument("--write", action="store_true", help="write the result to --allowlist instead of stdout")

    args = parser.parse_args(argv)

    try:
        if args.target_sha == "index":
            target_sha = gs.write_index_tree(args.repo_root)
        else:
            target_sha = gs.resolve_sha(args.repo_root, args.target_sha)
    except gs.GitSourceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.command == "generate":
        try:
            excluded_blob_paths = _load_non_gitlink_exclusion_paths(args.exclusions)
        except AllowlistError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        document = generate_allowlist_document(args.repo_root, target_sha, excluded_blob_paths)
        text = json.dumps(document, indent=2, sort_keys=False) + "\n"
        if args.write:
            args.allowlist.write_text(text, encoding="utf-8")
            print(f"wrote {len(document['paths'])} entries to {args.allowlist}", file=sys.stderr)
        else:
            sys.stdout.write(text)
        return 0

    errors = check(args.repo_root, args.allowlist, target_sha, args.exclusions)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"allowlist: {len(errors)} inconsistency(ies) against {target_sha}", file=sys.stderr)
        return 1
    print(f"allowlist: ok (exact match against {target_sha})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
