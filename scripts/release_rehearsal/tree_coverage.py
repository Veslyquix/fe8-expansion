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

# The two export-exclusion "kind"s this module currently models. A
# brand-new exclusion kind is deliberately not pre-emptively invented
# here -- fail closed (`TreeCoverageError`) rather than silently accept
# an unrecognized kind a human has not actually reviewed the meaning of
# yet.
#
# * `KIND_GITLINK` -- a real Git gitlink (submodule mountpoint, mode
#   `160000`) with no blob content in this repository's own tree at all;
#   excluded because its content is unresolved/unapproved third-party
#   content (see `docs/release_data/provenance/submodules.json`). A
#   gitlink exclusion still requires its own dedicated legal-review
#   provenance record elsewhere (its content is a separate, independent
#   fact from this structural tree-partition decision) -- see
#   `PROVENANCE_REQUIRED_EXCLUSION_KINDS` below.
# * `KIND_SELF_REFERENTIAL_EVIDENCE` -- an ordinary tracked blob that is
#   deliberately excluded from the archive because it is itself part of
#   the provenance/evidence system and cannot record a live-content-
#   bound identity fact about itself without an unsolvable circular
#   dependency (a "hash quine": the file's own content would need to
#   embed a hash of that same, not-yet-finalized content). Unlike a
#   gitlink exclusion, a self-referential-evidence exclusion's own
#   `reason` field here **is** its complete, sufficient, externally-owned
#   evidence record -- it never requires (and must never receive) a
#   *second*, separate provenance-manifest entry, which would either
#   reproduce the same cycle (if recorded inside the excluded file
#   itself) or merely relocate an empty formality to a different file
#   with no reviewable content of its own. See
#   `SELF_REFERENTIAL_EVIDENCE_PATHS` below for the exact, minimal,
#   human-curated set of paths this applies to. issue #9 R1/R2 fix: this
#   kind is a **curated PATH-ONLY-plus-MODE** exclusion, enforced as a
#   validator invariant (`load_exclusions` AND, independently,
#   `check_partition`) against that exact, hard-coded path set -- never
#   a permissive "any non-gitlink kind" definition -- and its `oid` field
#   is always absent/JSON `null`; a real, stale, or fabricated OID value
#   is a hard, rejected schema error, and no OID is ever cross-checked or
#   claimed as a content-identity fact for this kind (only path, kind,
#   and mode are). This is external rehearsal evidence about this
#   repository's own tooling, never source archive content and never a
#   redistribution/legal authorization of any kind.
KIND_GITLINK = "gitlink"
KIND_SELF_REFERENTIAL_EVIDENCE = "self_referential_evidence"
VALID_EXCLUSION_KINDS = (KIND_GITLINK, KIND_SELF_REFERENTIAL_EVIDENCE)

# Exclusion kinds whose path still requires its own, separate, dedicated
# provenance-manifest legal-review record (i.e. is still part of
# `scripts/release_rehearsal/provenance.py`'s required-coverage set) --
# used by `scripts/release_rehearsal/manifest.py`'s `check_provenance` to
# compute the correct combined-required-paths set for provenance
# coverage, which is deliberately **narrower** than the full tree-
# partition's included+excluded set below (a `KIND_SELF_REFERENTIAL_
# EVIDENCE` path is excluded from the archive, but -- unlike a gitlink --
# never requires or receives its own provenance-manifest entry; see the
# docstring above).
PROVENANCE_REQUIRED_EXCLUSION_KINDS = (KIND_GITLINK,)

# The exact, minimal, human-curated set of paths this repository has
# reviewed and determined are genuinely, structurally self-referential
# (see `KIND_SELF_REFERENTIAL_EVIDENCE` above) -- never mechanically
# derived (unlike gitlinks, which `generate_exclusions_document` finds
# directly from the live tree), since "is this file structurally self-
# referential" is a human documentation/design decision, not something
# Git's own tree data encodes. Currently exactly one path:
# `docs/release_data/provenance/code.json` is `scripts/release_rehearsal/
# provenance.py`'s own generated "code"-category manifest, which is what
# *every other* included "code"/"asset" blob's own oid/sha256 provenance
# record actually lives inside (including the record for `assets.json`
# and `submodules.json` themselves) -- a record describing code.json
# *inside* code.json would need to embed a hash of code.json's own
# about-to-be-written content, which is not achievable by ordinary
# regeneration (see the module-level docstring's "hash quine" note).
# `assets.json` and `submodules.json` are themselves ordinary, fully
# *included* blobs (their own oid/sha256 identity lives in code.json, not
# in themselves) -- they carry no such cycle and are never exempted from
# `provenance.check_blob_identity`.
SELF_REFERENTIAL_EVIDENCE_PATHS: FrozenSet[str] = frozenset({
    "docs/release_data/provenance/code.json",
})

# A small, human-curated seed for `generate_exclusions_document`: the
# factual reason recorded for each known gitlink path. Mirrors
# `provenance.py`'s own `PROVENANCE_ROOT_SEED` pattern -- a new gitlink
# path with no seed entry here is an actionable generation-time error
# (never a silently-invented reason), exactly like a new allowlisted path
# matching no provenance root is.
_SELF_REFERENTIAL_EVIDENCE_REASON_SEED: Dict[str, str] = {
    "docs/release_data/provenance/code.json": (
        "scripts/release_rehearsal/provenance.py's own generated 'code'-"
        "category provenance manifest: every OTHER included blob's exact "
        "oid/sha256 identity record (including the records describing "
        "docs/release_data/provenance/assets.json and docs/release_data/"
        "provenance/submodules.json themselves) lives inside this exact "
        "file. A record describing this file's own oid/sha256, written "
        "inside this same file, would necessarily describe this file's "
        "content from *before* the very write that embeds that record -- "
        "there is no ordinary regeneration process that reaches a fixed "
        "point for a file recording a live hash of itself (a 'hash "
        "quine'); searching for one would be absurd for a human-reviewed "
        "provenance ledger. This file is therefore excluded from the "
        "source release archive entirely, so it never requires -- and "
        "must never receive -- its own included-blob oid/sha256 "
        "provenance record. docs/release_data/provenance/assets.json and "
        "docs/release_data/provenance/submodules.json remain fully "
        "*included* (their own oid/sha256 identity, recorded inside this "
        "excluded file, is cross-checked with no exemption at all) -- "
        "only this one genuinely self-referential manifest is excluded. "
        "issue #9 R1/R2 fix: this is a curated PATH-ONLY-plus-MODE "
        "exclusion -- its 'oid' field is always absent/null, never a "
        "live or fabricated content hash, because a file cannot carry an "
        "immutable hash of its own not-yet-finalized content without "
        "exactly the cycle described above; this exclusion record (kind, "
        "mode, and this reason -- deliberately no oid) is this path's "
        "own complete, sufficient, externally-owned rehearsal evidence "
        "-- authored and reviewed here, in export_exclusions.json, "
        "exactly like every fact this repository records about the "
        "excluded mgfembp gitlink lives in provenance/submodules.json "
        "rather than inside mgfembp itself. It is external rehearsal "
        "evidence about this repository's own tooling, never source "
        "archive content and never a redistribution/legal authorization "
        "of any kind. This is a structural/self-reference fix, not a "
        "legal determination: like every other repository-authored "
        "file, this content has no human legal/provenance review "
        "recorded, and this exclusion grants no redistribution "
        "approval."
    ),
}

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
    oid: Optional[str]
    reason: str


def load_exclusions(path: Path) -> List[ExclusionEntry]:
    """issue #9 R1/R2 fix: a `KIND_SELF_REFERENTIAL_EVIDENCE` entry is no
    longer merely *shape*-validated (safe blob mode, well-formed oid) --
    its `path` must be an *exact* member of the small, hard-coded,
    human-curated `SELF_REFERENTIAL_EVIDENCE_PATHS` policy set (no
    prefix/wildcard match of any kind is ever performed), and its `oid`
    must be entirely absent or explicit JSON `null` (never a supplied
    string of any kind, real or fabricated) -- this kind never records
    or claims a live-content-bound OID at all (see the module docstring
    and `SELF_REFERENTIAL_EVIDENCE_PATHS`'s own docstring for the "hash
    quine" rationale this schema now makes structurally impossible to
    misrepresent, rather than merely documenting). An arbitrary tracked
    path claiming this kind (an extra, uncurated self-evidence row) is
    therefore rejected here, at load time, before it can ever reach
    `check_partition`'s own independent, hard-coded-against-the-same-
    policy-set enforcement (see `PartitionResult.invalid_self_
    referential_evidence` below) -- a validator invariant enforced
    twice, not merely a generator convention trusted once.

    A `KIND_GITLINK` entry's `oid` remains exactly as before: mandatory,
    and a well-formed 40-lowercase-hex string (a gitlink's pinned commit
    is a genuine, human-reviewed fact, unlike a self-referential-
    evidence entry's oid, which no longer exists as a field with any
    claimed meaning at all)."""
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
        missing = [key for key in ("path", "kind", "mode", "reason") if not raw.get(key)]
        if missing:
            raise TreeCoverageError(
                f"{path}[{index}] ({raw.get('path', '?')!r}): missing/empty required key(s): "
                + ", ".join(missing)
            )
        if raw["kind"] not in VALID_EXCLUSION_KINDS:
            raise TreeCoverageError(
                f"{path}[{index}] ({raw['path']}): kind {raw['kind']!r} not in {VALID_EXCLUSION_KINDS}"
            )
        if raw["kind"] == KIND_GITLINK:
            if raw["mode"] != gs.MODE_GITLINK:
                raise TreeCoverageError(
                    f"{path}[{index}] ({raw['path']}): kind 'gitlink' must record mode "
                    f"{gs.MODE_GITLINK!r}, found {raw['mode']!r}"
                )
            oid = raw.get("oid")
            if not isinstance(oid, str) or len(oid) != 40 or oid.lower() != oid:
                raise TreeCoverageError(
                    f"{path}[{index}] ({raw['path']}): kind 'gitlink' oid {oid!r} must be exactly "
                    "40 lowercase hex characters"
                )
        elif raw["kind"] == KIND_SELF_REFERENTIAL_EVIDENCE:
            if raw["path"] not in SELF_REFERENTIAL_EVIDENCE_PATHS:
                raise TreeCoverageError(
                    f"{path}[{index}] ({raw['path']}): kind {KIND_SELF_REFERENTIAL_EVIDENCE!r} is only "
                    f"ever valid for the exact, hard-coded, human-curated path(s) "
                    f"{sorted(SELF_REFERENTIAL_EVIDENCE_PATHS)} -- no other tracked path, of any kind, "
                    "may ever be excluded this way (an arbitrary path masquerading as self-referential "
                    "evidence, e.g. to escape ordinary allowlist/archive coverage, is never accepted)"
                )
            if raw["mode"] not in gs.SAFE_BLOB_MODES:
                raise TreeCoverageError(
                    f"{path}[{index}] ({raw['path']}): kind {KIND_SELF_REFERENTIAL_EVIDENCE!r} must "
                    f"record a safe blob mode {gs.SAFE_BLOB_MODES!r}, found {raw['mode']!r}"
                )
            oid = raw.get("oid")
            if oid is not None:
                raise TreeCoverageError(
                    f"{path}[{index}] ({raw['path']}): kind {KIND_SELF_REFERENTIAL_EVIDENCE!r} must "
                    f"omit 'oid' or record it as JSON null, found {oid!r} -- this kind never carries a "
                    "live-content-bound OID (a file cannot record an immutable hash of its own "
                    "not-yet-finalized content without an unsolvable cycle -- see this module's "
                    "docstring), so a supplied/stale/fake oid value is never accepted, and no oid is "
                    "ever cross-checked or claimed as a content-identity fact for this kind"
                )
        if raw["path"] in seen_paths:
            raise TreeCoverageError(f"{path}: duplicate exclusion entry for path {raw['path']!r}")
        seen_paths.add(raw["path"])
        entries.append(ExclusionEntry(
            path=raw["path"], kind=raw["kind"], mode=raw["mode"],
            oid=raw.get("oid"), reason=raw["reason"],
        ))
    return entries


def load_exclusion_paths(path: Path, kinds: Optional[Iterable[str]] = None) -> List[str]:
    """Every exact exclusion path, optionally filtered to only the given
    `kinds` (default `None` means every kind). Used by
    `scripts/release_rehearsal/manifest.py`'s `check_provenance` with
    `kinds=PROVENANCE_REQUIRED_EXCLUSION_KINDS` to compute the narrower
    "still needs its own separate provenance-manifest record" path set,
    which deliberately excludes a `KIND_SELF_REFERENTIAL_EVIDENCE` path
    (see that constant's docstring above) -- distinct from this tree-
    coverage module's own, broader included+excluded partition (`check_
    partition`/`check_non_git_tree` below), which always accounts for
    every exclusion kind."""
    entries = load_exclusions(path)
    if kinds is not None:
        kind_set = set(kinds)
        entries = [entry for entry in entries if entry.kind in kind_set]
    return sorted(entry.path for entry in entries)


def generate_exclusions_document(repo_root: Path, target_sha: str) -> Dict:
    """Deterministically regenerates the export-exclusions document from
    the immutable tree at `target_sha`: every gitlink entry becomes one
    exact `KIND_GITLINK` exclusion row (mechanically discovered from the
    live tree), and every path in the small, human-curated
    `SELF_REFERENTIAL_EVIDENCE_PATHS` becomes one exact `KIND_SELF_
    REFERENTIAL_EVIDENCE` exclusion row (never mechanically discovered --
    see that constant's own docstring), each with its `mode`/`oid` read
    directly from Git's own tree and its `reason` drawn from the
    matching small, human-curated reason-seed dict. A gitlink path with
    no seed entry, or a `SELF_REFERENTIAL_EVIDENCE_PATHS` path that is
    not actually a live safe blob at `target_sha`, raises
    `TreeCoverageError` -- this generator never invents a reason, nor
    silently drops a path that no longer resolves, for either kind."""
    entries = []
    tree = {entry.path: entry for entry in gs.list_tree(repo_root, target_sha)}
    for entry in tree.values():
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
            "kind": KIND_GITLINK,
            "mode": entry.mode,
            "oid": entry.object_id,
            "reason": reason,
        })
    for path in sorted(SELF_REFERENTIAL_EVIDENCE_PATHS):
        tree_entry = tree.get(path)
        if tree_entry is None:
            # This exact repository-specific path simply does not exist
            # in *this* tree at all (e.g. a generic/synthetic fixture
            # unrelated to this repository's own real layout, or -- in
            # the real repository -- a path not yet created at some
            # historical `target_sha`). Never an error on its own: this
            # generator is reusable against any tree, and the always-run
            # validation path (`check_partition`/`check_non_git_tree`,
            # which reads the *already-committed* export-exclusions file
            # directly rather than calling this generator) is what
            # actually catches a genuine "this got renamed/deleted after
            # being committed as an exclusion" regression (reported as
            # `stale_excluded`) -- this generator only ever silently
            # omits an inapplicable path, it never fabricates one.
            continue
        if not tree_entry.is_safe_blob:
            raise TreeCoverageError(
                f"generate: {path!r} is listed in SELF_REFERENTIAL_EVIDENCE_PATHS but is not a "
                f"live safe blob in the tree at {target_sha!r} (e.g. it is now a gitlink/symlink) "
                "-- a human must resolve this before this document can be regenerated"
            )
        reason = _SELF_REFERENTIAL_EVIDENCE_REASON_SEED.get(path)
        if reason is None:
            raise TreeCoverageError(
                f"generate: {path!r} is listed in SELF_REFERENTIAL_EVIDENCE_PATHS but has no "
                "curated reason in _SELF_REFERENTIAL_EVIDENCE_REASON_SEED"
            )
        entries.append({
            "path": path,
            "kind": KIND_SELF_REFERENTIAL_EVIDENCE,
            "mode": tree_entry.mode,
            # issue #9 R2 fix: this kind never records an 'oid' at all --
            # a file cannot carry an immutable hash of its own
            # not-yet-finalized content without an unsolvable cycle (see
            # this module's docstring). Always exactly `None` (rendered
            # as JSON `null`), never `tree_entry.object_id` -- a live oid
            # here would be stale the instant any other tracked path
            # changes, and `load_exclusions`/`check_partition` never
            # cross-check or claim any content-identity meaning for it.
            "oid": None,
            "reason": reason,
        })
    entries.sort(key=lambda entry: entry["path"])
    if not entries:
        raise TreeCoverageError(
            f"generate: no exclusion entries found at {target_sha!r} -- an export-exclusions "
            "document with zero entries is not a well-formed schema (see load_exclusions); "
            "if this repository genuinely has no more gitlinks or self-referential-evidence "
            "paths, the schema/caller contract itself needs a deliberate, reviewed change, "
            "not a silently-empty file"
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
    invalid_self_referential_evidence: List[str]

    def is_clean(self) -> bool:
        return not any((
            self.missing_included, self.stale_included, self.missing_excluded,
            self.stale_excluded, self.mismatched_excluded, self.overlap,
            self.unaccounted, self.prefix_exclusions, self.invalid_self_referential_evidence,
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
        reasons += [
            f"self_referential_evidence-kind exclusion for a path outside the exact, hard-coded "
            f"curated policy set {sorted(SELF_REFERENTIAL_EVIDENCE_PATHS)} (an arbitrary/extra "
            f"self-evidence row is never accepted, regardless of its mode/oid shape): {p}"
            for p in self.invalid_self_referential_evidence
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
    the expected kind (a `KIND_GITLINK` exclusion must be a live gitlink;
    a `KIND_SELF_REFERENTIAL_EVIDENCE` exclusion must be a live safe blob
    AND an exact member of the hard-coded `SELF_REFERENTIAL_EVIDENCE_
    PATHS` policy set; every other tracked blob must be included), with
    the excluded entry's own recorded mode matching the live tree's
    exactly -- a changed/stale pin, or a path whose live kind no longer
    matches its exclusion's own declared kind, is reported, never
    silently trusted.

    issue #9 R1 fix: this is a *validator invariant*, enforced here
    directly against the hard-coded `SELF_REFERENTIAL_EVIDENCE_PATHS`
    constant -- independently of, and in addition to, `load_exclusions`'s
    own identical check -- so a caller that constructs `ExclusionEntry`
    objects directly (bypassing `load_exclusions` entirely) gets exactly
    the same fail-closed guarantee: an arbitrary tracked path (of any
    kind) can never be moved out of the included allowlist and into a
    `self_referential_evidence`-kind exclusion row to escape coverage,
    no matter how the exclusion entries were constructed. Such a row is
    reported via `invalid_self_referential_evidence` below, and (since it
    is never treated as a legitimate exclusion) its underlying tracked
    blob -- if not otherwise allowlisted -- is *also* independently
    reported via `missing_included`, exactly as if no exclusion row for
    it existed at all."""
    tree = {entry.path: entry for entry in gs.list_tree(repo_root, target_sha)}
    all_paths = set(tree)
    blob_paths = {path for path, entry in tree.items() if not entry.is_gitlink}
    gitlink_paths = {path for path, entry in tree.items() if entry.is_gitlink}

    allowlist_set = set(allowlist_paths)
    exclusion_by_path = {entry.path: entry for entry in exclusion_entries}
    exclusion_set = set(exclusion_by_path)
    exclusion_gitlink_paths = {p for p, e in exclusion_by_path.items() if e.kind == KIND_GITLINK}

    # issue #9 R1 fix: a `self_referential_evidence`-kind exclusion only
    # ever legitimately substitutes for an included-allowlist entry when
    # its path is an *exact* member of the hard-coded curated policy set
    # -- never merely "any kind other than gitlink" (that permissive
    # definition, used previously, is exactly what let an arbitrary
    # tracked path masquerade as this kind and vanish from coverage).
    curated_self_referential_evidence_paths = {
        p for p, e in exclusion_by_path.items()
        if e.kind == KIND_SELF_REFERENTIAL_EVIDENCE and p in SELF_REFERENTIAL_EVIDENCE_PATHS
    }
    invalid_self_referential_evidence = {
        p for p, e in exclusion_by_path.items()
        if e.kind == KIND_SELF_REFERENTIAL_EVIDENCE and p not in SELF_REFERENTIAL_EVIDENCE_PATHS
    }

    overlap = allowlist_set & exclusion_set

    # A *curated* self-referential-evidence exclusion is never required
    # to also be an included allowlist entry -- it is deliberately
    # excluded instead; only a tracked blob that is in *neither* set at
    # all (nor properly, curated-ly excluded) is "missing_included". An
    # *invalid* (uncurated) self-referential-evidence row does **not**
    # count here -- its underlying blob is therefore still independently
    # reported missing_included too, exactly as if that bogus row were
    # never written at all (defense-in-depth alongside `invalid_self_
    # referential_evidence` itself).
    missing_included = blob_paths - allowlist_set - curated_self_referential_evidence_paths
    stale_included = allowlist_set - blob_paths

    # Only a *gitlink*-kind exclusion is required for every live gitlink
    # (a blob-kind exclusion is never a substitute for one, and a live
    # gitlink is never satisfied by anything except a `KIND_GITLINK`
    # exclusion record).
    missing_excluded = gitlink_paths - exclusion_gitlink_paths

    # Every exclusion entry (of either kind) must still correspond to a
    # live tracked path of its own declared kind -- checked per-entry so
    # a kind-mismatch (e.g. a `KIND_GITLINK` exclusion whose path is now
    # an ordinary blob, or vice versa) is caught as precisely as an
    # outright-missing path, never conflated with a simple mode
    # mismatch.
    stale_excluded = set()
    mismatched_excluded = set()
    for path, entry in exclusion_by_path.items():
        tree_entry = tree.get(path)
        expect_gitlink = entry.kind == KIND_GITLINK
        if tree_entry is None or tree_entry.is_gitlink != expect_gitlink:
            stale_excluded.add(path)
            continue
        if entry.mode != tree_entry.mode:
            mismatched_excluded.add(path)
            continue
        # issue #9 R2 fix: only a `KIND_GITLINK` exclusion's `oid` is a
        # genuinely *pinned*, human-reviewed fact (the submodule commit a
        # human chose to point at) -- live drift there (the pin silently
        # moved without this record being regenerated) is exactly the
        # kind of thing that must be reported. A `KIND_SELF_REFERENTIAL_
        # EVIDENCE` exclusion no longer carries an `oid` field with any
        # claimed meaning at all (see `load_exclusions`/`generate_
        # exclusions_document`) -- there is therefore nothing to compare
        # here for that kind; `stale_excluded`/`mismatched_excluded`
        # above still fully, strictly enforce that the path is a live,
        # correctly-kinded, correctly-moded blob.
        if entry.kind == KIND_GITLINK and entry.oid != tree_entry.object_id:
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
        invalid_self_referential_evidence=sorted(invalid_self_referential_evidence),
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


def _present_paths(root: Path) -> List[str]:
    """Every filesystem entry actually present under `root`, of **any**
    kind (regular file, symlink, hardlink, device, FIFO, socket, or any
    other non-regular node) -- a real, non-symlink directory is walked
    through (never itself reported as a leaf) and is the *only* kind
    ever skipped.

    A previous version of this walk (`_present_regular_files`) `continue`d
    straight past any symlink it found, which made a stray, unlisted
    symlink at *any* path completely invisible to both `check_non_git_
    tree`'s `extra`/`missing` accounting below -- neither reported as an
    unaccounted-for "extra" file nor caught by any other check, a
    silent closed-world gap an independent review found. Nothing is
    skipped by kind any more; only a genuine, non-symlink directory is
    ever excluded from the returned leaf list (it is walked through
    instead)."""
    root = Path(root)
    present: List[str] = []

    def _walk(dirpath: Path) -> None:
        with os.scandir(dirpath) as it:
            entries = sorted(it, key=lambda e: e.name)
        for entry in entries:
            if dirpath == root and entry.name == ".git":
                continue
            full = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                _walk(full)
                continue
            present.append(full.relative_to(root).as_posix())

    _walk(root)
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
    Every present filesystem entry, of *any* kind -- regular file,
    symlink, hardlink, device, FIFO, socket -- is enumerated by
    `_present_paths` (never silently skipped by kind); this closes a
    residual gap an independent review found: a stray symlink at a
    path this contract says nothing about used to be invisible to both
    buckets below (neither `extra` nor `unsafe`), because the previous
    enumeration `continue`d straight past any symlink it found. Reports
    three independent, actionable buckets:

    * `missing` -- an included path with no on-disk regular-file
      representation, or a gitlink-kind excluded path with no on-disk
      directory representation at all;
    * `extra` -- a present entry of *any* kind whose path is in neither
      the included nor the excluded set (the closed-world "new/unlisted
      node" finding -- this now also catches a stray symlink/hardlink/
      device/FIFO/socket at an otherwise-unaccounted-for path, never
      only a stray regular file);
    * `unsafe` -- a present path whose on-disk *shape* contradicts the
      contract: an included path materialized as anything other than a
      regular file (symlink, or any other non-regular node), a
      gitlink-kind excluded path materialized as anything other than a
      plain directory, or a non-gitlink (e.g. self-referential-evidence)
      excluded path present *at all* (it was never part of the archive
      in the first place, so it must never be present as anything --
      file, symlink, or directory -- in a genuine extracted candidate).
    """
    root = Path(root)
    allowlist_set = set(allowlist_paths)
    exclusion_by_path = {entry.path: entry for entry in exclusion_entries}
    exclusion_set = set(exclusion_by_path)

    present_paths = set(_present_paths(root))

    missing: List[str] = []
    unsafe: List[str] = []

    for path in sorted(allowlist_set):
        candidate = root / path
        if candidate.is_symlink():
            unsafe.append(path)
        elif not candidate.is_file():
            missing.append(path)

    for path in sorted(exclusion_set):
        entry = exclusion_by_path[path]
        candidate = root / path
        if entry.kind == KIND_GITLINK:
            if candidate.is_symlink():
                unsafe.append(path)
            elif candidate.is_file():
                unsafe.append(path)
            elif not candidate.is_dir():
                missing.append(path)
        else:
            # A non-gitlink (e.g. self-referential-evidence) exclusion
            # was never included in the archive at all -- unlike a
            # gitlink mountpoint, there is no "empty placeholder
            # directory" convention for it either. Any on-disk presence
            # whatsoever (file, symlink, or directory) contradicts the
            # "excluded means absent" contract.
            if candidate.is_symlink() or candidate.exists():
                unsafe.append(path)

    extra = sorted(present_paths - allowlist_set - exclusion_set)

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
