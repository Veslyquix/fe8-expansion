#!/usr/bin/env python3
"""Source-release provenance manifests (issue #9; exact-provenance
remediation).

Reads factual, generated JSON provenance manifests from
``docs/release_data/provenance/*.json`` and evaluates whether every entry has a
complete provenance record with redistribution permission recorded: a
non-``NOASSERTION`` author, rightsholder, and license, an explicit
``redistribution_approved: true``, and a named human reviewer. This
module never invents or infers any of those facts -- it only reads what a
human has recorded -- and it never selects or adds a root license, and
its own reported status is never a release/publication approval (see
``evaluate()`` below and docs/release_process.md's "Legal and provenance
boundary" section).

**Exact, one-record-per-member coverage (no directory-prefix semantics).**
An independent review found that this module previously treated a single
category-level entry's ``path`` (e.g. ``"src"``) as covering *every*
allowlisted path nested under it -- an exact-or-directory-prefix
"coverage" relationship. That let a brand-new tracked file, once added to
``docs/release_data/source_allowlist.json``, silently inherit an existing
ancestor directory's provenance record with **no dedicated review
decision of its own**. This module now requires a literal, exact,
one-record-per-member bijection instead: `coverage_gaps`,
`find_ghost_entries`, and `evaluate_coverage` below are pure exact-path
set operations -- an entry's ``path`` covers *only* that exact path,
never any descendant. `find_ambiguous_entries` is kept as a defense-in-
depth hygiene guard that flags a leftover, never-legitimate,
category/directory-style entry (see its own docstring) -- it is not
itself how coverage is granted.

Hand-authoring one near-duplicate ``NOASSERTION`` record per individual
tracked file (thousands of them) would be an unreviewable maintenance
hazard on its own, so `generate_exact_entries()`/`PROVENANCE_ROOT_SEED`
below is the single, small, human-curated generator input (one entry per
reviewable top-level root, exactly as before) that mechanically fans
each root's ``category``/``notes`` out to every exact allowlisted path
nested under (or equal to) it, producing the real, checked-in, exact
per-file JSON this module actually validates. **This prefix-based
fan-out is a one-time/as-needed *generation* step a human explicitly
runs and commits (`generate --write`) -- it is never invoked by, or any
part of, the runtime `check`/`evaluate_coverage` validation path**, which
only ever reads the exact records already committed to disk. Adding a
file to the allowlist without also regenerating (and committing) its
provenance entry is exactly the "new allowlisted file has no exact
provenance" failure this module is designed to catch, not something
`check` ever silently repairs or grants on the fly.

Deliberately dependency-free (Python stdlib only, JSON only).

Manifest entry schema::

    {
      "path": "src/main.c",            # exact repo-relative tracked path --
                                        # never a directory/category prefix
      "category": "code",               # "code" | "asset" | "submodule"
      "author": "NOASSERTION",         # or a real, human-recorded name
      "rightsholder": "NOASSERTION",
      "license": "NOASSERTION",
      "redistribution_approved": false,
      "reviewer": null,                # or a real human reviewer identity
      "notes": "free-form factual note",
      "oid": "1f2e3d...",              # exact 40-lowercase-hex Git blob OID --
                                        # required for "code"/"asset"; never
                                        # present for "submodule"
      "sha256": "9c8b7a...",           # exact 64-lowercase-hex SHA-256 of the
                                        # raw blob content -- required for
                                        # "code"/"asset"; never present (must
                                        # be null) for "submodule"
      "pinned_commit": null            # required, non-null for category "submodule";
                                        # the gitlink's own commit OID
    }

Exit codes (CLI): 0 well-formed report (status may be "blocked" or
"mechanically eligible") for `check`, or a successful `generate`; 2
actionable schema/generation error (missing/invalid field, or a path
that cannot be assigned to exactly one seed root -- a defect in the
manifest/seed itself, distinct from an honestly-recorded unresolved
fact).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

from scripts.release_rehearsal import git_source as gs
from scripts.release_rehearsal import gitmodules as gm
from scripts.release_rehearsal import tree_coverage as tc

CATEGORIES = ("code", "asset", "submodule")
UNRESOLVED_MARKERS = ("NOASSERTION", "", None)

REQUIRED_KEYS = (
    "path",
    "category",
    "author",
    "rightsholder",
    "license",
    "redistribution_approved",
    "reviewer",
)


class ProvenanceError(ValueError):
    """A provenance manifest entry (or generator input) is malformed (a
    tooling defect, not an honestly-unresolved fact)."""


_OID_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_manifest(path: Path) -> List[Dict]:
    """Loads and schema-validates one provenance manifest file.

    issue #9 mandatory correction #3 (exact-blob-bound provenance): a
    `"code"`/`"asset"`-category entry must now additionally record its
    exact Git blob `oid` (40-lowercase-hex) and a deterministic SHA-256
    `sha256` (64-lowercase-hex) of the raw blob content -- this binds the
    record to one specific, immutable version of that path's content,
    not merely to the path string. These two fields are schema-validated
    for *shape* only here (well-formed hex, right length); cross-
    checking them against the *actual* live tree/blob content is
    `check_blob_identity()`'s separate job (schema validity is a
    necessary precondition for that cross-check, not a substitute for
    it). A `"submodule"`-category entry never carries `sha256` (a
    gitlink has no blob content to hash at all) -- if present, it must
    be exactly `None`, never a stray/leftover value from before a path
    was reclassified."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProvenanceError(f"{path}: not valid JSON: {error}") from error
    if not isinstance(data, list):
        raise ProvenanceError(f"{path}: manifest must be a JSON array of entries")
    entries = []
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ProvenanceError(f"{path}[{index}]: entry must be a JSON object")
        missing = [key for key in REQUIRED_KEYS if key not in entry]
        if missing:
            raise ProvenanceError(f"{path}[{index}]: missing required key(s): {', '.join(missing)}")
        if entry["category"] not in CATEGORIES:
            raise ProvenanceError(
                f"{path}[{index}] ({entry['path']}): category {entry['category']!r} not in {CATEGORIES}"
            )
        if not isinstance(entry["redistribution_approved"], bool):
            raise ProvenanceError(
                f"{path}[{index}] ({entry['path']}): redistribution_approved must be a real boolean, "
                "never a truthy string"
            )
        if entry["category"] == "submodule":
            if not entry.get("pinned_commit"):
                raise ProvenanceError(
                    f"{path}[{index}] ({entry['path']}): submodule entries must record pinned_commit"
                )
            if entry.get("sha256") is not None:
                raise ProvenanceError(
                    f"{path}[{index}] ({entry['path']}): submodule (gitlink) entries must never "
                    "record a 'sha256' (a gitlink has no blob content) -- found "
                    f"{entry.get('sha256')!r}"
                )
            if not isinstance(entry.get("url"), str) or not entry.get("url"):
                raise ProvenanceError(
                    f"{path}[{index}] ({entry['path']}): submodule entries must record a non-empty "
                    "'url' (issue #9 mandatory correction #4: the three-way .gitmodules/gitlink/"
                    "provenance binding needs a URL to cross-check)"
                )
        else:
            oid = entry.get("oid")
            sha256_value = entry.get("sha256")
            if not isinstance(oid, str) or not _OID_RE.fullmatch(oid):
                raise ProvenanceError(
                    f"{path}[{index}] ({entry['path']}): {entry['category']} entries must record an "
                    f"exact 40-lowercase-hex 'oid', found {oid!r}"
                )
            if not isinstance(sha256_value, str) or not _SHA256_RE.fullmatch(sha256_value):
                raise ProvenanceError(
                    f"{path}[{index}] ({entry['path']}): {entry['category']} entries must record an "
                    f"exact 64-lowercase-hex 'sha256', found {sha256_value!r}"
                )
        entry.setdefault("source_manifest", str(path))
        entries.append(entry)
    return entries


def load_all(provenance_dir: Path) -> List[Dict]:
    provenance_dir = Path(provenance_dir)
    if not provenance_dir.is_dir():
        raise ProvenanceError(f"provenance directory not found: {provenance_dir}")
    entries: List[Dict] = []
    for path in sorted(provenance_dir.glob("*.json")):
        entries.extend(load_manifest(path))
    return entries


def _entry_blocking_reasons(entry: Dict) -> List[str]:
    reasons = []
    label = entry["path"]
    if entry["author"] in UNRESOLVED_MARKERS:
        reasons.append(f"{label}: author is NOASSERTION/unrecorded")
    if entry["rightsholder"] in UNRESOLVED_MARKERS:
        reasons.append(f"{label}: rightsholder is NOASSERTION/unrecorded")
    if entry["license"] in UNRESOLVED_MARKERS:
        reasons.append(f"{label}: license is NOASSERTION/unrecorded")
    if not entry["redistribution_approved"]:
        reasons.append(f"{label}: redistribution_approved is false")
    if not entry["reviewer"]:
        reasons.append(f"{label}: no named reviewer")
    return reasons


def evaluate(entries: List[Dict]) -> Tuple[str, List[str]]:
    """Returns (status, blocking_reasons). status is "blocked" unless every
    entry is fully resolved (author/rightsholder/license recorded,
    redistribution_approved is true, and a reviewer is named), in which
    case it is "mechanically eligible" -- the same neutral vocabulary
    scripts/release_rehearsal/manifest.py's overall candidate status uses,
    deliberately never the bare word "approved": a provenance record
    being fully, honestly recorded is a fact about the record, not a
    release/publication approval, and this status must never be mistaken
    for one."""
    if not entries:
        return "blocked", ["no provenance entries recorded"]
    reasons: List[str] = []
    for entry in entries:
        reasons.extend(_entry_blocking_reasons(entry))
    status = "blocked" if reasons else "mechanically eligible"
    return status, sorted(reasons)


def coverage_gaps(entries: List[Dict], required_paths: List[str]) -> List[str]:
    """Every path in `required_paths` (the exact source allowlist) must
    have its own exact provenance entry. Pure exact-path set membership --
    there is no directory-prefix ancestry/"coverage" relationship any
    more (see module docstring): reports every required path that has
    **no** entry at all sharing that literal, exact path."""
    entry_paths = {entry["path"] for entry in entries}
    return sorted(set(required_paths) - entry_paths)


def find_ghost_entries(entries: List[Dict], required_paths: List[str]) -> List[str]:
    """A "ghost" entry's `path` does not exactly equal any path in
    `required_paths` -- e.g. a stale provenance record left over after a
    file was renamed/removed from the allowlist, **or** a leftover
    directory/category-style entry (e.g. a bare `"src"`) that was never
    itself one of the exact tracked paths. Pure exact-path set
    membership; a directory prefix is never "close enough"."""
    required = set(required_paths)
    return sorted({entry["path"] for entry in entries} - required)


def find_duplicate_entry_paths(entries: List[Dict]) -> List[str]:
    """Two (or more) entries recording the exact same `path` -- always a
    defect (ambiguous which record is authoritative), regardless of
    whether their other fields happen to agree."""
    seen = set()
    dupes = set()
    for entry in entries:
        path = entry["path"]
        if path in seen:
            dupes.add(path)
        seen.add(path)
    return sorted(dupes)


def find_ambiguous_entries(entries: List[Dict]) -> List[str]:
    """Defense-in-depth hygiene guard against a leftover category/
    directory-style entry: flags any two *distinct* entry paths where one
    is a strict path-segment-prefix ancestor of the other (e.g. `"src"`
    and `"src/lib.c"`). Under a genuine exact, one-record-per-tracked-
    member data set this can never legitimately happen -- a real Git blob
    path can never simultaneously be a directory prefix of another real
    Git blob path -- so a non-empty result here always means a stray,
    unreviewed category/prefix-style entry was left in place instead of
    being fanned out to exact per-file entries: exactly the "category
    inheritance" issue #9's exact-provenance-binding requirement forbids.
    (An *exact* duplicate path is reported by `find_duplicate_entry_paths`
    instead.)

    Implemented as an O(paths x average-path-depth) ancestor-prefix
    membership check (every proper ancestor directory prefix of each path
    is tested for literal set membership) rather than an O(n^2) pairwise
    comparison, since this data set now has thousands of entries."""
    paths = sorted({entry["path"] for entry in entries})
    path_set = set(paths)
    ambiguous = set()
    for path in paths:
        parts = path.split("/")
        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            if ancestor in path_set:
                ambiguous.add(ancestor)
                ambiguous.add(path)
    return sorted(ambiguous)


def evaluate_coverage(entries: List[Dict], required_paths: List[str]) -> List[str]:
    """One combined, human-readable reason list covering every provenance-
    vs-allowlist coverage defect class: exact-duplicate entry paths,
    leftover ambiguous/category-style entry paths, missing coverage (a
    gap -- an allowlisted path with no entry), and ghost entries (an
    entry whose path is not itself exactly allowlisted). An empty return
    means `entries` and `required_paths` are in an exact, one-record-
    per-member bijection: the same set of paths, each appearing in
    `entries` exactly once, with no entry covering anything by
    directory-prefix inheritance."""
    reasons: List[str] = []
    reasons += [f"duplicate provenance entry path: {path}" for path in find_duplicate_entry_paths(entries)]
    reasons += [
        f"ambiguous/leftover category-style provenance entry: {path}"
        for path in find_ambiguous_entries(entries)
    ]
    reasons += [f"missing provenance entry for {path}" for path in coverage_gaps(entries, required_paths)]
    reasons += [
        f"ghost provenance entry (not an exact allowlisted path): {path}"
        for path in find_ghost_entries(entries, required_paths)
    ]
    return sorted(reasons)


def check_gitlink_pins(entries: List[Dict], repo_root: Path, target_sha: str = "HEAD") -> List[str]:
    """Cross-checks every "submodule"-category provenance entry's declared
    `pinned_commit` against the actual gitlink object id Git's own tree
    records for that exact path at `target_sha` (`git ls-tree`, via
    scripts/release_rehearsal/git_source.py) -- independent of whether the
    submodule is actually initialized/checked out locally. A provenance
    record that merely *claims* a pin is exactly as much an honesty gap as
    an unresolved NOASSERTION fact if the superproject's own tree does not
    actually record that commit; this never trusts the JSON's own say-so
    without cross-checking it against Git itself. Returns an empty list
    when there is no "submodule"-category entry at all (this never itself
    requires a submodule to exist), or when `repo_root` is not a git
    repository at all (nothing to cross-check against; the caller decides
    whether that itself is acceptable for a given candidate tree)."""
    submodule_entries = [entry for entry in entries if entry["category"] == "submodule"]
    if not submodule_entries:
        return []
    if not gs.is_git_repo(repo_root):
        return []
    try:
        tree_entries = {entry.path: entry for entry in gs.list_tree(repo_root, target_sha)}
    except gs.GitSourceError as error:
        return [f"could not cross-check gitlink pin(s) against the git tree at {target_sha!r}: {error}"]
    reasons: List[str] = []
    for entry in submodule_entries:
        path = entry["path"]
        tree_entry = tree_entries.get(path)
        if tree_entry is None or not tree_entry.is_gitlink:
            reasons.append(
                f"{path}: provenance declares category 'submodule' but no gitlink is recorded "
                f"at this exact path in the tree at {target_sha!r}"
            )
            continue
        if entry.get("pinned_commit") != tree_entry.object_id:
            reasons.append(
                f"{path}: provenance pinned_commit {entry.get('pinned_commit')!r} does not match "
                f"the actual gitlink commit {tree_entry.object_id!r} Git's tree records at {target_sha!r}"
            )
    return sorted(reasons)


# Guardian-correction remediation (D2): a fresh, independent review found
# that ALL THREE provenance-manifest files this module writes
# (`write_generated_provenance`) were previously exempted from
# `check_blob_identity` below, on the theory that each is itself a
# tracked "code"-category blob that would need its own provenance
# record. That is only actually true for `docs/release_data/provenance/
# code.json` itself: it is the "code"-category manifest, so a record
# describing code.json's own oid/sha256 would have to live *inside*
# code.json -- a genuine, structural "hash quine" (the record's content
# would need to embed a hash of code.json's own not-yet-finalized
# content, including that very record). `assets.json` and
# `submodules.json`, by contrast, are NOT self-referential at all: their
# own oid/sha256 identity records live inside code.json (a *different*
# file), so there is no cycle, and (before this fix) exempting them let
# a committed, tampered assets.json/submodules.json silently evade
# identity validation entirely -- exactly the defect this fix closes.
#
# The structural fix: `docs/release_data/provenance/code.json` is now an
# explicit, exact export exclusion (`tree_coverage.
# KIND_SELF_REFERENTIAL_EVIDENCE`, `tree_coverage.
# SELF_REFERENTIAL_EVIDENCE_PATHS`) -- it is no longer an *included*
# allowlist member at all, so it never has (and is never generated with)
# its own provenance record in the first place (see `generate_exact_
# entries`'s `all_paths = allowlist_set | exclusion_set` and
# `scripts/release_rehearsal/manifest.py`'s narrower, gitlink-only
# `PROVENANCE_REQUIRED_EXCLUSION_KINDS`-filtered required-coverage set).
# There is therefore nothing left to exempt here at all: `check_blob_
# identity` below cross-checks **every** `"code"`/`"asset"`-category
# entry actually present in the loaded data, unconditionally --
# including `assets.json` and `submodules.json` -- with no path-based
# exemption of any kind. A stray, leftover self-entry for code.json
# (there should never be one after regeneration) would simply be
# reported like any other stale/tampered record by this function, and
# separately flagged as a "ghost" entry by `evaluate_coverage` (its path
# is no longer in the required-coverage set at all).


def check_blob_identity(entries: List[Dict], repo_root: Path, target_sha: str = "HEAD") -> List[str]:
    """Cross-checks every `"code"`/`"asset"`-category provenance entry's
    declared `oid`/`sha256` against the actual, immutable blob Git's own
    tree records for that exact path at `target_sha` -- issue #9
    mandatory correction #3 (exact-blob-bound provenance). This never
    trusts the JSON's own say-so: it re-reads `target_sha`'s tree
    (`git_source.list_tree`) and every referenced blob's *actual* bytes
    (`git_source.GitBatchBlobReader`), independently recomputing SHA-256,
    exactly mirroring `check_gitlink_pins`' "never trust the record,
    cross-check it against Git itself" discipline for gitlink pins.

    A record whose path is not a currently-tracked safe blob at all (a
    gitlink now, or simply gone), or whose `oid` and/or `sha256` no
    longer match the live tree/blob content (the file was edited/
    replaced without regenerating its provenance record), is reported --
    this is precisely how a changed/new blob is required to invalidate
    its old provenance record rather than silently keep "passing" under
    stale identity data. Returns an empty list when there are no
    `"code"`/`"asset"` entries at all, or when `repo_root` is not a git
    repository (nothing to cross-check against; the caller decides
    whether that is itself acceptable for a given candidate tree)."""
    blob_entries = [entry for entry in entries if entry["category"] != "submodule"]
    if not blob_entries:
        return []
    if not gs.is_git_repo(repo_root):
        return []
    try:
        tree_entries = {entry.path: entry for entry in gs.list_tree(repo_root, target_sha)}
    except gs.GitSourceError as error:
        return [f"could not cross-check blob identity against the git tree at {target_sha!r}: {error}"]

    reasons: List[str] = []
    needed_object_ids: Dict[str, str] = {}
    for entry in blob_entries:
        tree_entry = tree_entries.get(entry["path"])
        if tree_entry is None or not tree_entry.is_safe_blob:
            reasons.append(
                f"{entry['path']}: provenance declares category {entry['category']!r} but no safe "
                f"blob is recorded at this exact path in the tree at {target_sha!r} (missing/stale "
                "provenance -- e.g. the path was removed, renamed, or is no longer a regular blob)"
            )
            continue
        if entry.get("oid") != tree_entry.object_id:
            reasons.append(
                f"{entry['path']}: provenance oid {entry.get('oid')!r} does not match the actual "
                f"blob {tree_entry.object_id!r} Git's tree records at {target_sha!r} (the blob "
                "changed since this provenance record was generated -- regenerate it)"
            )
            continue
        needed_object_ids[entry["path"]] = tree_entry.object_id

    if needed_object_ids:
        try:
            with gs.GitBatchBlobReader(repo_root) as reader:
                for path, object_id in needed_object_ids.items():
                    data = reader.read(object_id)
                    actual_sha256 = hashlib.sha256(data).hexdigest()
                    expected = next(e for e in blob_entries if e["path"] == path).get("sha256")
                    if actual_sha256 != expected:
                        reasons.append(
                            f"{path}: provenance sha256 {expected!r} does not match the actual blob "
                            f"content's SHA-256 {actual_sha256!r} at {target_sha!r} (stale/incorrect "
                            "content hash -- regenerate this provenance record)"
                        )
        except gs.GitSourceError as error:
            reasons.append(f"could not read blob content to verify sha256 at {target_sha!r}: {error}")

    return sorted(reasons)


# --- Exact per-file generator (issue #9 exact-provenance remediation) ------
#
# `PROVENANCE_ROOT_SEED` is the single, small, human-curated input: one
# entry per reviewable root. Not every entry is a literal top-level path
# -- `"texts/expansion"` and `"texts/locales"` are exact nested roots, kept
# disjoint from the now-narrowed `"texts/*.txt"` siblings so `_assign_root`
# never sees an overlapping/ambiguous match -- each
# naming the `category`/`notes`/`pinned_commit` every exact allowlisted
# path nested under (or equal to) that root should start out with.
# `generate_exact_entries()` mechanically fans this out to one exact,
# fully-materialized dict per allowlisted path; `main()`'s `generate`
# subcommand is the only thing that ever calls it, and only when a human
# explicitly runs it. Nothing in `check`/`evaluate_coverage` above ever
# calls this generator, and it is never invoked implicitly by
# scripts/release_rehearsal/manifest.py -- release-time validation only
# ever reads the exact records already committed to disk (see module
# docstring).


class RootSeed(NamedTuple):
    root: str
    category: str
    notes: str


_NOTE_CODE_BUILD_TOOLING = (
    "Wave 0/issue #9 seed: repository-authored build tooling/config/source "
    "surface (or, for asm/, decompiled disassembly derived from the "
    "original ROM). No human legal/provenance review has been recorded "
    "yet; this manifest records that honestly rather than asserting a "
    "license or clearance."
)
_NOTE_CODE_RELEASE_TOOLING_IO = (
    "Issue #9 release-process tooling output/input surface. No human "
    "legal/provenance review has been recorded yet; kept honestly "
    "unresolved like every other tracked path rather than assumed-clear "
    "because it is new."
)
_NOTE_CODE_DOCUMENTATION = (
    "Wave 0/issue #9 seed: repository-authored documentation. No human "
    "legal/provenance review has been recorded yet; this manifest "
    "records that honestly rather than asserting a license or clearance."
)
_NOTE_CODE_RELEASE_MAKE_TARGETS = (
    "Issue #9 release-process Make targets. No human legal/provenance "
    "review has been recorded yet."
)
_NOTE_ASSET = (
    "Wave 0/issue #9 seed: extracted/derived original-game asset or "
    "generated-report content (graphics/sound/text/animation data, or "
    "GitHub Pages report output). Original Fire Emblem: The Sacred Stones "
    "copyright/trademark ownership is Nintendo/Intelligent Systems and is "
    "NOT asserted or cleared by this repository. No human legal/provenance "
    "review has been recorded yet."
)
_NOTE_TEXTS_EXPANSION_LOCALIZATION = (
    "Issue #9 disclosure-correction seed (issue #18 localization): tracked "
    "localization catalog/source under texts/expansion -- repository-"
    "authored framework message keys and locale catalog content (e.g. "
    "registry.json / catalog.<locale>.json), never extracted or derived "
    "from the original Fire Emblem: The Sacred Stones ROM/game text. This "
    "path previously, inaccurately inherited the general 'texts' root's "
    "original-game-asset note (Nintendo/Intelligent Systems copyright) via "
    "directory-prefix seeding; that note never applied here. Author/"
    "rightsholder/license/redistribution-approval remain exactly as "
    "unresolved as every other tracked path -- this correction states the "
    "provenance *kind* honestly, it does not invent or assert an author, "
    "rightsholder, license, or approval."
)
_NOTE_CJK_FONT_ASSETS = (
    "Issue #18 CJK font asset/provenance surface under fonts/cjk: unmodified "
    "Noto CJK OTF inputs, the vendored OFL-1.1 text, deterministic corpora/"
    "maps/manifests/reports, and third-party notices. Exact upstream commit, "
    "source URLs, licenses, and hashes are recorded in this tree; no human "
    "release/legal approval is inferred from those factual records."
)
_NOTE_GAME_LOCALE_SOURCES = (
    "Issue #18 full-game locale source/provenance surface under texts/locales: "
    "hash-pinned authorized FE8J/FE8CN input snapshots plus deterministic "
    "normalized catalogs, mapping evidence, fallback decisions, and manifests. "
    "Exact source and regeneration facts are documented in "
    "docs/game_locale_sources.md; no human release/legal approval is inferred."
)
_NOTE_SUBMODULE_MGFEMBP = (
    "Git submodule pointing at StanHash/mgfembp (FE6 multiboot payload "
    "builder). An explicit export exclusion (see "
    "docs/release_data/export_exclusions.json and "
    "scripts/release_rehearsal/tree_coverage.py) -- not redistributable as "
    "part of a source archive until upstream license/redistribution terms "
    "are reviewed and approved. `pinned_commit` is always read fresh from "
    "the live gitlink at generation time, never hardcoded here."
)

PROVENANCE_ROOT_SEED: Tuple[RootSeed, ...] = (
    RootSeed(".clang-format", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed(".gitattributes", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed(".github", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed(".gitignore", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed(".gitmodules", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("CHANGELOG.md", "code", _NOTE_CODE_RELEASE_TOOLING_IO),
    RootSeed("CLAUDE.md", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("CONTRIBUTING.md", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("Makefile", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("README.md", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("asmdiff.sh", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("buddy.yml", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("build_tools.sh", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("cjk_fonts.mk", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("changelog_fragments", "code", _NOTE_CODE_RELEASE_TOOLING_IO),
    RootSeed("clean_tools.sh", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("compile_flags.txt", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("config", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("config.mk", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("docs", "code", _NOTE_CODE_DOCUMENTATION),
    RootSeed("game_localization.mk", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("generated_data.mk", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("githooks", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("graphics_file_rules.mk", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("include", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("json_data_rules.mk", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("ldscript.txt", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("linker", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("linker_script_banim.txt", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("linker_script_sound.txt", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("localization.mk", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("make_tools.mk", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("modern.mk", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("release.mk", "code", _NOTE_CODE_RELEASE_MAKE_TARGETS),
    RootSeed("scripts", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("songs.mk", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("src", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("sym_iwram.txt", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("tests", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("tools", "code", _NOTE_CODE_BUILD_TOOLING),
    RootSeed("_site", "asset", _NOTE_ASSET),
    RootSeed("asm", "asset", _NOTE_ASSET),
    RootSeed("banim", "asset", _NOTE_ASSET),
    RootSeed("fonts", "asset", _NOTE_CJK_FONT_ASSETS),
    RootSeed("graphics", "asset", _NOTE_ASSET),
    RootSeed("preview", "asset", _NOTE_ASSET),
    RootSeed("reports", "asset", _NOTE_ASSET),
    RootSeed("sound", "asset", _NOTE_ASSET),
    # issue #9 disclosure correction: "texts" is no longer a single
    # prefix root -- texts/expansion is repository-authored
    # localization-framework catalog/source (issue #18), never
    # original-game asset content, and must never inherit the
    # original-game-asset note by directory-prefix accident. The two
    # remaining top-level texts/*.txt files (the actual extracted/
    # derived original-game text dumps) are seeded as their own exact,
    # non-prefix roots so no root here overlaps another (an
    # overlapping/ambiguous seed is an actionable _assign_root error,
    # never silently resolved).
    RootSeed("texts/textdefs.txt", "asset", _NOTE_ASSET),
    RootSeed("texts/texts.txt", "asset", _NOTE_ASSET),
    RootSeed("texts/expansion", "asset", _NOTE_TEXTS_EXPANSION_LOCALIZATION),
    RootSeed("texts/locales", "asset", _NOTE_GAME_LOCALE_SOURCES),
    RootSeed("mgfembp", "submodule", _NOTE_SUBMODULE_MGFEMBP),
)

_CATEGORY_FILENAMES = {
    "code": "code.json",
    "asset": "assets.json",
    "submodule": "submodules.json",
}


def _root_covers_path(root: str, candidate_path: str) -> bool:
    """Generator-only helper: true if `candidate_path` is exactly `root`
    or nested under it (`candidate_path` starts with `root + "/"`).
    **Never** used by any validation/coverage function above -- those are
    all pure exact-path set operations. Used exclusively by
    `_assign_root()`/`generate_exact_entries()` to fan
    `PROVENANCE_ROOT_SEED`'s small, human-curated per-root values out to
    every exact allowlisted/excluded path; the generated output is a
    fully materialized, one-record-per-exact-path artifact that is never
    re-interpreted by directory prefix again once committed."""
    return candidate_path == root or candidate_path.startswith(root + "/")


def _assign_root(path: str, seed: Sequence[RootSeed]) -> RootSeed:
    """Pure (no git access) root-assignment lookup: `path` must match
    **exactly one** root in `seed`. An unassigned path (no root covers
    it) or an ambiguous path (more than one root covers it) is an
    actionable `ProvenanceError` -- this never silently skips a path or
    arbitrarily picks a root when more than one matches. Split out from
    `generate_exact_entries()` so the fan-out/ambiguity logic itself
    stays fully unit-testable without any git repository at all."""
    matches = [root_seed for root_seed in seed if _root_covers_path(root_seed.root, path)]
    if not matches:
        raise ProvenanceError(f"generate: {path!r} matches no seed root in PROVENANCE_ROOT_SEED")
    if len(matches) > 1:
        raise ProvenanceError(
            f"generate: {path!r} matches more than one seed root: "
            f"{sorted(root_seed.root for root_seed in matches)}"
        )
    return matches[0]


def _find_gitmodules_url_for_path(repo_root: Path, target_sha: str, path: str) -> str:
    """Reads `.gitmodules` fresh at `target_sha` (never cached/hardcoded --
    issue #9 mandatory correction #4) and returns the exact `url` of the
    single section whose recorded `path` equals `path`. An unresolvable
    URL (no matching section, more than one section claiming the same
    path, or a section missing its own `url`/`path` key) is an
    actionable `ProvenanceError` -- this generator never fabricates or
    guesses a submodule URL."""
    try:
        sections = gm.load_gitmodules_sections(repo_root, target_sha)
    except gm.GitmodulesError as error:
        raise ProvenanceError(f"generate: {error}") from error
    matches = [
        (name, section) for name, section in sections.items()
        if section.get("path") == path
    ]
    if not matches:
        raise ProvenanceError(
            f"generate: {path!r} is assigned the 'submodule' category but no .gitmodules "
            f"section at {target_sha!r} declares this exact path"
        )
    if len(matches) > 1:
        raise ProvenanceError(
            f"generate: {path!r} is declared by more than one .gitmodules section: "
            f"{sorted(name for name, _ in matches)}"
        )
    _name, section = matches[0]
    url = section.get("url")
    if not url:
        raise ProvenanceError(f"generate: .gitmodules section for {path!r} has no 'url'")
    return url


def generate_exact_entries(
    repo_root: Path,
    target_sha: str,
    allowlist_paths: Iterable[str],
    exclusion_paths: Iterable[str] = (),
    seed: Sequence[RootSeed] = PROVENANCE_ROOT_SEED,
) -> List[Dict]:
    """Fans `seed`'s small, human-curated per-root category/notes values
    out to one exact, fully-materialized provenance dict per path in
    `allowlist_paths` (the included set) **and** `exclusion_paths` (the
    explicit export exclusions -- issue #9 mandatory correction #2/#3).
    Every path must match **exactly one** seed root (`_assign_root`).

    Every generated `"code"`/`"asset"` entry is bound to its *exact, live*
    Git blob identity: `oid` is the blob object id and `sha256` is a
    freshly computed SHA-256 of that blob's actual content, both read
    from `target_sha`'s tree via `scripts/release_rehearsal/git_source.py`
    -- never carried over from any previously-committed record. Every
    generated `"submodule"` entry's `pinned_commit` is likewise read
    fresh from the live gitlink, never hardcoded in `seed`. A path
    assigned a `"submodule"`-category root that is not actually a live
    gitlink (or a non-`"submodule"` path that is not actually a live safe
    blob) is an actionable `ProvenanceError` -- this generator never
    fabricates an identity for a path Git's own tree does not actually
    back up.

    `author`/`rightsholder`/`license` are always `"NOASSERTION"`,
    `redistribution_approved` is always `False`, and `reviewer` is always
    `None` for every generated entry: this generator only ever proposes
    the same honest, unresolved starting point -- it never invents a
    license, an approval, or a reviewer for any path, however it was
    assigned a root, and it never preserves a previous approval/reviewer
    fact across a changed or brand-new blob (there is nothing to
    "preserve" -- every field this generator itself controls is always
    freshly and independently recomputed, every single run)."""
    tree = {entry.path: entry for entry in gs.list_tree(repo_root, target_sha)}

    allowlist_set = set(allowlist_paths)
    exclusion_set = set(exclusion_paths)
    all_paths = sorted(allowlist_set | exclusion_set)
    assignments: Dict[str, RootSeed] = {path: _assign_root(path, seed) for path in all_paths}

    # Defensive cross-check (issue #9 mandatory correction #2/#3
    # consistency): a path's seed-assigned category must agree with
    # *which* canonical set it was actually declared in -- a
    # "submodule"-category path must come from `exclusion_paths` (it is
    # never a member of the included allowlist), and every other
    # category must come from `allowlist_paths` (it is never a member of
    # the export exclusions). This never trusts seed/category alone
    # without also confirming the caller declared the path in the
    # matching canonical set.
    for path in all_paths:
        category = assignments[path].category
        if category == "submodule" and path not in exclusion_set:
            raise ProvenanceError(
                f"generate: {path!r} is assigned the 'submodule' category by seed root "
                f"{assignments[path].root!r} but was not declared in exclusion_paths"
            )
        if category != "submodule" and path not in allowlist_set:
            raise ProvenanceError(
                f"generate: {path!r} is assigned category {category!r} by seed root "
                f"{assignments[path].root!r} but was not declared in allowlist_paths"
            )

    entries: List[Dict] = []
    blob_paths: List[str] = []
    for path in all_paths:
        root_seed = assignments[path]
        tree_entry = tree.get(path)
        if root_seed.category == "submodule":
            if tree_entry is None or not tree_entry.is_gitlink:
                raise ProvenanceError(
                    f"generate: {path!r} is assigned the 'submodule' category by seed root "
                    f"{root_seed.root!r} but is not a live gitlink in the tree at {target_sha!r}"
                )
            url = _find_gitmodules_url_for_path(repo_root, target_sha, path)
            entries.append({
                "path": path,
                "category": "submodule",
                "author": "NOASSERTION",
                "rightsholder": "NOASSERTION",
                "license": "NOASSERTION",
                "redistribution_approved": False,
                "reviewer": None,
                "notes": root_seed.notes,
                "pinned_commit": tree_entry.object_id,
                "url": url,
            })
        else:
            if tree_entry is None or not tree_entry.is_safe_blob:
                raise ProvenanceError(
                    f"generate: {path!r} is assigned category {root_seed.category!r} by seed root "
                    f"{root_seed.root!r} but is not a live safe blob in the tree at {target_sha!r}"
                )
            entries.append({
                "path": path,
                "category": root_seed.category,
                "author": "NOASSERTION",
                "rightsholder": "NOASSERTION",
                "license": "NOASSERTION",
                "redistribution_approved": False,
                "reviewer": None,
                "notes": root_seed.notes,
                "oid": tree_entry.object_id,
                "sha256": None,  # filled in below, in one shared blob-reading pass
            })
            blob_paths.append(path)

    if blob_paths:
        by_path = {entry["path"]: entry for entry in entries}
        with gs.GitBatchBlobReader(repo_root) as reader:
            for path in blob_paths:
                object_id = tree[path].object_id
                data = reader.read(object_id)
                by_path[path]["sha256"] = hashlib.sha256(data).hexdigest()

    return entries


def write_generated_provenance(provenance_dir: Path, entries: List[Dict]) -> Dict[str, int]:
    """Writes `entries` (as produced by `generate_exact_entries`) into the
    three canonical per-category files
    (`code.json`/`assets.json`/`submodules.json`) under `provenance_dir`,
    sorted by `path` within each file for a byte-stable, reviewable diff.
    Returns `{filename: entry_count}`."""
    provenance_dir = Path(provenance_dir)
    by_category: Dict[str, List[Dict]] = {category: [] for category in CATEGORIES}
    for entry in entries:
        by_category[entry["category"]].append(entry)
    counts: Dict[str, int] = {}
    for category, filename in _CATEGORY_FILENAMES.items():
        category_entries = sorted(by_category[category], key=lambda entry: entry["path"])
        text = json.dumps(category_entries, indent=2) + "\n"
        (provenance_dir / filename).write_text(text, encoding="utf-8")
        counts[filename] = len(category_entries)
    return counts


def _load_allowlist_paths(allowlist_path: Path) -> List[str]:
    try:
        data = json.loads(Path(allowlist_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProvenanceError(f"{allowlist_path}: not valid JSON: {error}") from error
    paths = data.get("paths")
    if not isinstance(paths, list) or not paths:
        raise ProvenanceError(f"{allowlist_path}: must contain a non-empty 'paths' array")
    return paths


def _load_exclusion_paths(exclusions_path: Path) -> List[str]:
    """issue #9 defense-in-depth fix (final-review follow-up, mirrors
    `allowlist.py`'s own identical `_load_non_gitlink_exclusion_paths`
    closing-round fix): this used to be its own minimal, independent,
    permissive local JSON reader -- it re-implemented (rather than
    reused) `tree_coverage.py`'s exclusion-document schema, accepting
    any entry with a string `path` and merely checking `kind ==
    "gitlink"` as a bare string, with **no** curated-path check, no
    `oid` shape/well-formedness check, no mode check, and no duplicate-
    path check at all. That left this reader "backstopped" only by
    `tree_coverage.check_partition()`/`manifest.py`'s composite report
    catching the same malformed/fabricated/duplicate exclusion row
    separately -- an independent review correctly flagged this as a
    second, permissive parser of the same trust file
    (`docs/release_data/export_exclusions.json`) that could silently
    drift out of sync with the real, strict one, rather than a provable
    single source of truth.

    This function now performs no schema interpretation of its own at
    all: it delegates entirely to `tree_coverage.load_exclusion_paths()`
    restricted to `tree_coverage.PROVENANCE_REQUIRED_EXCLUSION_KINDS`
    (today exactly `(tree_coverage.KIND_GITLINK,)`) -- the same set
    `scripts/release_rehearsal/manifest.py`'s `check_provenance` already
    uses to compute this exact narrower "still needs its own separate
    provenance-manifest record" path set (see that constant's docstring
    in `tree_coverage.py`). An arbitrary/uncurated gitlink path, a
    fabricated/null/mismatched `oid`, a wrong mode, a duplicate entry, or
    a `kind == "self_referential_evidence"` row misusing self-evidence
    semantics now all fail here, at this reader, exactly like they
    already failed `tree_coverage.load_exclusions()` itself -- never
    only at a separate composite backstop.

    Returns `[]` if `exclusions_path` does not exist at all (unchanged
    from before this fix). Any schema/curated-policy defect
    `tree_coverage.load_exclusions()` would raise is re-raised here as a
    `ProvenanceError`, so every caller of this function keeps failing
    exactly the same way it always has, just against a strictly correct,
    shared implementation instead of a second, independently
    (re-)implemented one."""
    path = Path(exclusions_path)
    if not path.is_file():
        return []
    try:
        return tc.load_exclusion_paths(path, kinds=tc.PROVENANCE_REQUIRED_EXCLUSION_KINDS)
    except tc.TreeCoverageError as error:
        raise ProvenanceError(str(error)) from error


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo-root", type=Path, default=Path("."))
    common.add_argument("--provenance-dir", type=Path, default=Path("docs/release_data/provenance"))
    common.add_argument("--allowlist", type=Path, default=Path("docs/release_data/source_allowlist.json"))
    common.add_argument("--exclusions", type=Path, default=Path("docs/release_data/export_exclusions.json"))
    common.add_argument(
        "--target-sha", default="HEAD",
        help="a commit-ish (default HEAD), or the literal 'index' to use the "
             "current staged index (via 'git write-tree') -- a development-time "
             "convenience for checking/generating provenance for an in-progress "
             "change before committing (mirrors allowlist.py/tree_coverage.py's "
             "identical convenience)",
    )

    sub.add_parser("check", parents=[common], help="report provenance status + exact allowlist/exclusions coverage")

    gen = sub.add_parser(
        "generate", parents=[common],
        help="fan PROVENANCE_ROOT_SEED out to one exact, blob-identity-bound entry per allowlisted/excluded path",
    )
    gen.add_argument("--write", action="store_true", help="write the result into --provenance-dir instead of stdout")

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
            allowlist_paths = _load_allowlist_paths(args.allowlist)
            exclusion_paths = _load_exclusion_paths(args.exclusions) if args.exclusions.is_file() else []
            entries = generate_exact_entries(args.repo_root, target_sha, allowlist_paths, exclusion_paths)
        except (ProvenanceError, gs.GitSourceError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if args.write:
            counts = write_generated_provenance(args.provenance_dir, entries)
            for filename, count in sorted(counts.items()):
                print(f"wrote {count} entries to {args.provenance_dir / filename}", file=sys.stderr)
        else:
            sys.stdout.write(json.dumps(entries, indent=2) + "\n")
        return 0

    try:
        entries = load_all(args.provenance_dir)
    except ProvenanceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    status, reasons = evaluate(entries)

    if args.allowlist.is_file():
        try:
            allowlist_paths = _load_allowlist_paths(args.allowlist)
            required_paths = list(allowlist_paths)
            if args.exclusions.is_file():
                exclusion_paths = _load_exclusion_paths(args.exclusions)
                required_paths = sorted(set(allowlist_paths) | set(exclusion_paths))
        except ProvenanceError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        coverage_reasons = evaluate_coverage(entries, required_paths)
        if coverage_reasons:
            status = "blocked"
            reasons = sorted(set(reasons) | set(coverage_reasons))

    pin_reasons = check_gitlink_pins(entries, args.repo_root, target_sha)
    if pin_reasons:
        status = "blocked"
        reasons = sorted(set(reasons) | set(pin_reasons))

    identity_reasons = check_blob_identity(entries, args.repo_root, target_sha)
    if identity_reasons:
        status = "blocked"
        reasons = sorted(set(reasons) | set(identity_reasons))

    print(f"provenance status: {status}")
    for reason in reasons:
        print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
