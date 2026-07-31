#!/usr/bin/env python3
"""Exact immutable HEAD tree coverage: included members (+) explicit
export exclusions == the complete tree, disjointly (issue #9 mandatory
correction #2).

`scripts/release_rehearsal/allowlist.py`'s exact per-member allowlist
(``docs/release_data/source_allowlist.json``) already proves "every
tracked blob has its own exact entry, no directory/prefix grant". That,
on its own, still leaves one silent gap an independent review found: the
``mgfembp`` submodule **gitlink** used to sit *inside* that same
allowlist as an ordinary-looking entry, with no explicit, separately
reviewed record of *why* it is excluded from the archive at all (it has
no blob content -- ``archive_rehearsal.py`` has always silently skipped
it via ``not entry.is_gitlink``, but nothing forced that skip to be an
explicit, checked-in, factual decision).

This module is the fix: it defines the two canonical sets directly from
an immutable ``git ls-tree -r <target_sha>`` -- **included** (every blob
entry: modes ``100644``/``100755``/``120000``; see
``git_source.SAFE_BLOB_MODES`` plus symlinks, whose *presence* here is
deliberate -- see ``allowlist.py``'s own docstring) and **excluded**
(every gitlink entry: mode ``160000``, always explicitly recorded in
``docs/release_data/export_exclusions.json`` with its exact immutable
OID/kind and a factual reason) -- and proves their union is *exactly*
the complete tree, with **no overlap**. A brand-new tracked path (of any
kind) that is not already in one of these two canonical, checked-in sets
fails coverage outright; it is never silently absorbed into either side,
and it never merely vanishes from the archive.

Two additional, related, fail-closed checks live here too:

* `check_archive_membership_exact` -- the actual, built archive's member
  set must equal the checked-in included (blob) set exactly -- not a
  subset, not a superset.
* `check_non_git_closed_world` -- the closed-world equivalent for a
  genuine already-extracted candidate tree (no ``.git`` at all): every
  present regular file must be an included member, every included member
  must be present as a real file, and every excluded (gitlink) member
  must be present as an (optionally empty) real directory -- never a
  file, never a symlink, and never simply absent.

Deliberately dependency-free (Python stdlib only); reuses
``scripts/release_rehearsal/git_source.py``'s plumbing wrappers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from scripts.release_rehearsal import git_source as gs

SCHEMA_VERSION = 1
DEFAULT_ALLOWLIST_PATH = Path("docs/release_data/source_allowlist.json")
DEFAULT_EXCLUSIONS_PATH = Path("docs/release_data/export_exclusions.json")

# The only export-exclusion "kind" this module currently models. Issue #9
# mandatory correction #2 is scoped to the one real contradiction this
# repository actually has (the `mgfembp` gitlink); a brand-new exclusion
# kind is deliberately not pre-emptively invented here -- fail closed
# (`ExclusionError`) rather than silently accept an unrecognized kind a
# human has not actually reviewed the meaning of yet.
VALID_EXCLUSION_KINDS = ("gitlink",)

# A small, human-curated seed for `generate_exclusions_document`: the
# factual reason recorded for each known gitlink path. Mirrors
# `provenance.py`'s own `PROVENANCE_ROOT_SEED` pattern -- a new gitlink
# path with no seed entry here is an actionable generation-time error
# (never a silently-invented reason), exactly like a new allowlisted path
# matching no provenance root is.
_EXCLUSION_REASON_SEED: Dict[str, str] = {
    "mgfembp": (
        "Git submodule mountpoint (gitlink) for StanHash/mgfembp (FE6 multiboot "
        "payload builder). A gitlink has no blob content in this repository's own "
        "tree to archive -- its content lives in a separate repository at the "
        "pinned commit. Excluded from the source archive rather than included "
        "because no approved submodule content is present: "
        "docs/release_data/provenance/submodules.json records this submodule as "
        "redistribution_approved: false (unresolved), and this rehearsal never "
        "fetches/initializes it (see docs/release_process.md's Rebuild rehearsal "
        "section). This is the one, explicit, factual export-exclusion this "
        "repository currently has."
    ),
}


class TreeCoverageError(ValueError):
    """A malformed export-exclusions file, or an actionable generation-
    time defect (e.g. a gitlink with no curated reason) -- distinct from
    a normal coverage finding (reported as a string in a list, never
    raised)."""


@dataclass(frozen=True)
class ExclusionEntry:
    path: str
    kind: str
    mode: str
    oid: str
    reason: str


def load_exclusions(path: Path) -> List[ExclusionEntry]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TreeCoverageError(f"{path}: not valid JSON: {error}") from error
    raw_entries = data.get("exclusions")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise TreeCoverageError(f"{path}: must contain a non-empty 'exclusions' array")
    entries: List[ExclusionEntry] = []
    seen_paths = set()
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            raise TreeCoverageError(f"{path}[{index}]: entry must be a JSON object")
        missing = [key for key in ("path", "kind", "mode", "oid", "reason") if not raw.get(key)]
        if missing:
            raise TreeCoverageError(
                f"{path}[{index}] ({raw.get('path', '?')!r}): missing/empty required key(s): "
                + ", ".join(missing)
            )
        if raw["kind"] not in VALID_EXCLUSION_KINDS:
            raise TreeCoverageError(
                f"{path}[{index}] ({raw['path']}): kind {raw['kind']!r} not in {VALID_EXCLUSION_KINDS}"
            )
        if raw["kind"] == "gitlink" and raw["mode"] != gs.MODE_GITLINK:
            raise TreeCoverageError(
                f"{path}[{index}] ({raw['path']}): kind 'gitlink' must record mode {gs.MODE_GITLINK!r}, "
                f"found {raw['mode']!r}"
            )
        if not isinstance(raw["oid"], str) or len(raw["oid"]) != 40 or raw["oid"].lower() != raw["oid"]:
            raise TreeCoverageError(
                f"{path}[{index}] ({raw['path']}): oid {raw['oid']!r} must be exactly 40 lowercase hex characters"
            )
        if raw["path"] in seen_paths:
            raise TreeCoverageError(f"{path}: duplicate exclusion entry for path {raw['path']!r}")
        seen_paths.add(raw["path"])
        entries.append(ExclusionEntry(path=raw["path"], kind=raw["kind"], mode=raw["mode"], oid=raw["oid"], reason=raw["reason"]))
    return entries


def load_exclusion_paths(path: Path) -> List[str]:
    return sorted(entry.path for entry in load_exclusions(path))


def generate_exclusions_document(repo_root: Path, target_sha: str) -> Dict:
    """Deterministically regenerates the export-exclusions document from
    the immutable tree at `target_sha`: every gitlink entry becomes one
    exact exclusion row, with its `mode`/`oid` read directly from Git's
    own tree and its `reason` drawn from the small, human-curated
    `_EXCLUSION_REASON_SEED`. A gitlink path with no seed entry raises
    `TreeCoverageError` -- this generator never invents a reason for a
    submodule/gitlink a human has not actually documented yet."""
    entries = []
    for entry in gs.list_tree(repo_root, target_sha):
        if not entry.is_gitlink:
            continue
        reason = _EXCLUSION_REASON_SEED.get(entry.path)
        if reason is None:
            raise TreeCoverageError(
                f"generate: gitlink {entry.path!r} has no curated reason in "
                "_EXCLUSION_REASON_SEED -- a human must record why this new gitlink "
                "is excluded before this document can be regenerated"
            )
        entries.append({
            "path": entry.path,
            "kind": "gitlink",
            "mode": entry.mode,
            "oid": entry.object_id,
            "reason": reason,
        })
    entries.sort(key=lambda entry: entry["path"])
    if not entries:
        raise TreeCoverageError(
            f"generate: no gitlink entries found at {target_sha!r} -- an export-exclusions "
            "document with zero entries is not a well-formed schema (see load_exclusions); "
            "if this repository genuinely has no more gitlinks, the schema/caller contract "
            "itself needs a deliberate, reviewed change, not a silently-empty file"
        )
    return {
        "_comment": (
            "Explicit export exclusions (issue #9 mandatory correction #2): every entry here "
            "is a tree member intentionally EXCLUDED from the source release archive, with its "
            "exact path, kind, immutable mode/OID (as recorded by 'git ls-tree' at "
            "'generated_from_sha'), and a factual reason. Disjoint union with "
            "docs/release_data/source_allowlist.json's 'paths' MUST equal the complete tree at "
            "that exact SHA -- scripts/release_rehearsal/tree_coverage.py's check_partition() "
            "mechanically enforces this (a new tracked path in neither set fails coverage; an "
            "entry here whose mode/oid no longer matches the live tree is a stale-exclusion "
            "failure). Generated by "
            "'python3 -m scripts.release_rehearsal.tree_coverage generate-exclusions'. This is "
            "a structural/factual record only -- it grants no redistribution approval; see "
            "docs/release_data/provenance/submodules.json and docs/release_process.md."
        ),
        "schema_version": SCHEMA_VERSION,
        "generated_from_sha": target_sha,
        "generator": "python3 -m scripts.release_rehearsal.tree_coverage generate-exclusions",
        "exclusions": entries,
    }


def combined_required_paths(allowlist_paths: Iterable[str], exclusion_paths: Iterable[str]) -> List[str]:
    """The exact union of included (allowlist) and excluded paths -- the
    full set of paths any *other* module (e.g. `provenance.py`'s coverage
    check) must have exactly one record for, since provenance now spans
    both included blobs (with oid/sha256) and excluded gitlinks (with a
    pinned-commit/exclusion record) -- see docs/release_process.md."""
    return sorted(set(allowlist_paths) | set(exclusion_paths))


@dataclass(frozen=True)
class PartitionResult:
    missing_included: List[str]
    stale_included: List[str]
    missing_excluded: List[str]
    stale_excluded: List[str]
    mismatched_excluded: List[str]
    overlap: List[str]
    unaccounted: List[str]
    prefix_exclusions: List[str]

    def is_clean(self) -> bool:
        return not any((
            self.missing_included, self.stale_included, self.missing_excluded,
            self.stale_excluded, self.mismatched_excluded, self.overlap,
            self.unaccounted, self.prefix_exclusions,
        ))

    def reasons(self) -> List[str]:
        reasons: List[str] = []
        reasons += [f"tracked blob missing from the included allowlist: {p}" for p in self.missing_included]
        reasons += [f"stale included-allowlist entry (not a tracked blob): {p}" for p in self.stale_included]
        reasons += [
            f"tracked gitlink missing an explicit export-exclusion record: {p}"
            for p in self.missing_excluded
        ]
        reasons += [
            f"stale export-exclusion entry (not a tracked gitlink): {p}" for p in self.stale_excluded
        ]
        reasons += [f"export-exclusion entry has a stale mode/OID: {p}" for p in self.mismatched_excluded]
        reasons += [f"path listed in BOTH included and excluded sets: {p}" for p in self.overlap]
        reasons += [
            f"tracked path in neither the included allowlist nor the export exclusions: {p}"
            for p in self.unaccounted
        ]
        reasons += [
            f"export-exclusion path is a directory-prefix ancestor of another tracked path "
            f"(broad-prefix exclusions are forbidden): {p}"
            for p in self.prefix_exclusions
        ]
        return sorted(reasons)


def check_partition(
    repo_root: Path,
    allowlist_paths: Iterable[str],
    exclusion_entries: Sequence[ExclusionEntry],
    target_sha: str = "HEAD",
) -> PartitionResult:
    """The core exact-coverage check: reads the complete, immutable tree
    at `target_sha` once (`git ls-tree -r`) and verifies the checked-in
    included (allowlist) and excluded (export-exclusions) sets, together,
    account for it *exactly* -- disjointly. Every tracked path in the
    live tree must be in exactly one of the two sets; every entry in
    either checked-in set must still correspond to a live tracked path of
    the expected kind (blob for included, gitlink for excluded, with the
    excluded entry's own recorded mode/oid matching the live tree's
    exactly -- a changed/stale gitlink pin is reported, never silently
    trusted)."""
    tree = {entry.path: entry for entry in gs.list_tree(repo_root, target_sha)}
    all_paths = set(tree)
    blob_paths = {path for path, entry in tree.items() if not entry.is_gitlink}
    gitlink_paths = {path for path, entry in tree.items() if entry.is_gitlink}

    allowlist_set = set(allowlist_paths)
    exclusion_by_path = {entry.path: entry for entry in exclusion_entries}
    exclusion_set = set(exclusion_by_path)

    overlap = allowlist_set & exclusion_set

    missing_included = blob_paths - allowlist_set
    stale_included = allowlist_set - blob_paths

    missing_excluded = gitlink_paths - exclusion_set
    stale_excluded = exclusion_set - gitlink_paths

    mismatched_excluded = set()
    for path in exclusion_set & gitlink_paths:
        entry = exclusion_by_path[path]
        tree_entry = tree[path]
        if entry.oid != tree_entry.object_id or entry.mode != tree_entry.mode:
            mismatched_excluded.add(path)

    unaccounted = all_paths - (allowlist_set | exclusion_set)

    # Defense-in-depth: an export-exclusion path must be a leaf, never a
    # directory-prefix ancestor of some other tracked path (a real
    # git-tree gitlink never has this shape, but a hand-edited exclusions
    # file could try to claim one; this is checked against the *live*
    # tree, not merely the checked-in sets, so it can never be bypassed
    # by also stale-listing the "child" paths).
    prefix_exclusions = set()
    for excluded_path in exclusion_set:
        prefix = excluded_path + "/"
        if any(other.startswith(prefix) for other in all_paths):
            prefix_exclusions.add(excluded_path)

    return PartitionResult(
        missing_included=sorted(missing_included),
        stale_included=sorted(stale_included),
        missing_excluded=sorted(missing_excluded),
        stale_excluded=sorted(stale_excluded),
        mismatched_excluded=sorted(mismatched_excluded),
        overlap=sorted(overlap),
        unaccounted=sorted(unaccounted),
        prefix_exclusions=sorted(prefix_exclusions),
    )


def check(
    repo_root: Path,
    allowlist_path: Path = DEFAULT_ALLOWLIST_PATH,
    exclusions_path: Path = DEFAULT_EXCLUSIONS_PATH,
    target_sha: str = "HEAD",
) -> List[str]:
    """Convenience wrapper: loads both checked-in files and returns a flat
    human-readable reason list (empty means an exact, disjoint, complete
    partition). Used by `manifest.py` and the standalone CLI below."""
    from scripts.release_rehearsal import allowlist as al  # local import: avoid a cycle at module load

    try:
        allowlist_paths = al.load_allowlist_paths(allowlist_path)
    except al.AllowlistError as error:
        return [str(error)]
    try:
        exclusion_entries = load_exclusions(exclusions_path)
    except TreeCoverageError as error:
        return [str(error)]
    result = check_partition(repo_root, allowlist_paths, exclusion_entries, target_sha)
    return result.reasons()


# --- Archive-member exact equality (issue #9 mandatory correction #2) -----


def check_archive_membership_exact(
    archive_paths: Iterable[str], included_paths: Iterable[str]
) -> Tuple[List[str], List[str]]:
    """`(missing, extra)`: `missing` is an included (allowlist) path that
    did not actually end up in the built archive; `extra` is an archive
    member that is not an included path at all (e.g. a gitlink that
    slipped through, or any other bug). Both must be empty for the
    archive to be accepted -- **candidate archive members MUST equal the
    included regular-file/blob set exactly**, never a subset or
    superset."""
    archive_set = set(archive_paths)
    included_set = set(included_paths)
    missing = sorted(included_set - archive_set)
    extra = sorted(archive_set - included_set)
    return missing, extra


# --- Non-git closed-world exact membership (issue #9 mandatory --------
# correction #2) ------------------------------------------------------


def _present_regular_files(root: Path) -> List[str]:
    root = Path(root)
    present: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirpath_path = Path(dirpath)
        if dirpath_path == root:
            dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            full = dirpath_path / name
            if full.is_symlink():
                continue
            present.append(full.relative_to(root).as_posix())
    return present


@dataclass(frozen=True)
class NonGitCoverageResult:
    missing: List[str]
    extra: List[str]
    unsafe: List[str]

    def is_clean(self) -> bool:
        return not (self.missing or self.extra or self.unsafe)

    def reasons(self) -> List[str]:
        reasons = []
        reasons += [f"included member missing from extracted tree: {p}" for p in self.missing]
        reasons += [f"present file not accounted for by the included/excluded contract: {p}" for p in self.extra]
        reasons += [f"unsafe on-disk shape for a contract path: {p}" for p in self.unsafe]
        return sorted(reasons)


def check_non_git_tree(
    root: Path, allowlist_paths: Iterable[str], exclusion_entries: Sequence[ExclusionEntry],
) -> NonGitCoverageResult:
    """The non-git (genuine extracted archive/candidate tree) analogue of
    `check_partition`, used only when `root` has no `.git` at all. Never
    invokes any git command (there is nothing to invoke it against).
    Reports three independent, actionable buckets:

    * `missing` -- an included path with no on-disk regular-file
      representation, or an excluded (gitlink) path with no on-disk
      directory representation at all;
    * `extra` -- a present regular file whose path is in neither the
      included nor the excluded set (the closed-world "new/unlisted
      file" finding);
    * `unsafe` -- a present path whose on-disk *shape* contradicts the
      contract: an included path materialized as a symlink instead of a
      regular file, or an excluded (gitlink) path materialized as a
      regular file or symlink instead of a plain directory.
    """
    root = Path(root)
    allowlist_set = set(allowlist_paths)
    exclusion_set = {entry.path for entry in exclusion_entries}

    present_files = set(_present_regular_files(root))

    missing: List[str] = []
    unsafe: List[str] = []

    for path in sorted(allowlist_set):
        candidate = root / path
        if candidate.is_symlink():
            unsafe.append(path)
        elif not candidate.is_file():
            missing.append(path)

    for path in sorted(exclusion_set):
        candidate = root / path
        if candidate.is_symlink():
            unsafe.append(path)
        elif candidate.is_file():
            unsafe.append(path)
        elif not candidate.is_dir():
            missing.append(path)

    extra = sorted(present_files - allowlist_set - exclusion_set)

    return NonGitCoverageResult(missing=sorted(missing), extra=extra, unsafe=sorted(unsafe))


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
             "convenience for regenerating the export-exclusions document together "
             "with the allowlist/provenance data for the same in-progress change, "
             "before committing (mirrors scripts/release_rehearsal/allowlist.py's "
             "identical convenience)",
    )

    sub.add_parser("check", parents=[common], help="verify the exact, disjoint, complete tree partition")
    gen = sub.add_parser(
        "generate-exclusions", parents=[common],
        help="print a freshly-generated export-exclusions document",
    )
    gen.add_argument("--write", action="store_true", help="write the result to --exclusions instead of stdout")

    args = parser.parse_args(argv)

    try:
        if args.target_sha == "index":
            target_sha = gs.write_index_tree(args.repo_root)
        else:
            target_sha = gs.resolve_sha(args.repo_root, args.target_sha)
    except gs.GitSourceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.command == "generate-exclusions":
        try:
            document = generate_exclusions_document(args.repo_root, target_sha)
        except TreeCoverageError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        text = json.dumps(document, indent=2) + "\n"
        if args.write:
            args.exclusions.write_text(text, encoding="utf-8")
            print(f"wrote {len(document['exclusions'])} entries to {args.exclusions}", file=sys.stderr)
        else:
            sys.stdout.write(text)
        return 0

    reasons = check(args.repo_root, args.allowlist, args.exclusions, target_sha)
    if reasons:
        for reason in reasons:
            print(f"error: {reason}", file=sys.stderr)
        print(f"tree_coverage: {len(reasons)} inconsistency(ies) against {target_sha}", file=sys.stderr)
        return 1
    print(f"tree_coverage: ok (exact, disjoint, complete partition at {target_sha})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
