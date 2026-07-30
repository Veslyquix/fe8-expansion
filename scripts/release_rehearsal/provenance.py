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
      "path": "src/main.c",            # exact repo-relative tracked path
                                        # (or the single "mgfembp" gitlink
                                        # path) -- never a directory/
                                        # category prefix
      "category": "code",               # "code" | "asset" | "submodule"
      "author": "NOASSERTION",         # or a real, human-recorded name
      "rightsholder": "NOASSERTION",
      "license": "NOASSERTION",
      "redistribution_approved": false,
      "reviewer": null,                # or a real human reviewer identity
      "notes": "free-form factual note",
      "pinned_commit": null            # required, non-null for category "submodule"
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
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Sequence, Tuple

from scripts.release_rehearsal import git_source as gs

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


def load_manifest(path: Path) -> List[Dict]:
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
        if entry["category"] == "submodule" and not entry.get("pinned_commit"):
            raise ProvenanceError(
                f"{path}[{index}] ({entry['path']}): submodule entries must record pinned_commit"
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


# --- Exact per-file generator (issue #9 exact-provenance remediation) ------
#
# `PROVENANCE_ROOT_SEED` is the single, small, human-curated input: one
# entry per reviewable top-level root (the same 46 roots this repository
# already reviewed at category granularity before this change), each
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
    pinned_commit: str | None


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
_NOTE_SUBMODULE_MGFEMBP = (
    "Git submodule pointing at StanHash/mgfembp (FE6 multiboot payload "
    "builder). Pinned to the exact commit this worktree's gitlink "
    "records; not redistributable as part of a source archive until "
    "upstream license/redistribution terms are reviewed and approved."
)

PROVENANCE_ROOT_SEED: Tuple[RootSeed, ...] = (
    RootSeed(".clang-format", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed(".gitattributes", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed(".github", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed(".gitignore", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed(".gitmodules", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("CHANGELOG.md", "code", _NOTE_CODE_RELEASE_TOOLING_IO, None),
    RootSeed("CLAUDE.md", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("CONTRIBUTING.md", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("Makefile", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("README.md", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("asmdiff.sh", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("buddy.yml", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("build_tools.sh", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("changelog_fragments", "code", _NOTE_CODE_RELEASE_TOOLING_IO, None),
    RootSeed("clean_tools.sh", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("compile_flags.txt", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("config", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("config.mk", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("docs", "code", _NOTE_CODE_DOCUMENTATION, None),
    RootSeed("generated_data.mk", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("githooks", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("graphics_file_rules.mk", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("include", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("json_data_rules.mk", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("ldscript.txt", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("linker", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("linker_script_banim.txt", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("linker_script_sound.txt", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("make_tools.mk", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("modern.mk", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("release.mk", "code", _NOTE_CODE_RELEASE_MAKE_TARGETS, None),
    RootSeed("scripts", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("songs.mk", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("src", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("sym_iwram.txt", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("tests", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("tools", "code", _NOTE_CODE_BUILD_TOOLING, None),
    RootSeed("_site", "asset", _NOTE_ASSET, None),
    RootSeed("asm", "asset", _NOTE_ASSET, None),
    RootSeed("banim", "asset", _NOTE_ASSET, None),
    RootSeed("graphics", "asset", _NOTE_ASSET, None),
    RootSeed("preview", "asset", _NOTE_ASSET, None),
    RootSeed("reports", "asset", _NOTE_ASSET, None),
    RootSeed("sound", "asset", _NOTE_ASSET, None),
    RootSeed("texts", "asset", _NOTE_ASSET, None),
    RootSeed("mgfembp", "submodule", _NOTE_SUBMODULE_MGFEMBP, "c87e74dcd6c8878b809e013cd8ff0c52baa75332"),
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
    `generate_exact_entries()` to fan `PROVENANCE_ROOT_SEED`'s small,
    human-curated per-root values out to every exact allowlisted path;
    the generated output is a fully materialized, one-record-per-exact-
    path artifact that is never re-interpreted by directory prefix again
    once committed."""
    return candidate_path == root or candidate_path.startswith(root + "/")


def generate_exact_entries(
    allowlist_paths: Iterable[str], seed: Sequence[RootSeed] = PROVENANCE_ROOT_SEED
) -> List[Dict]:
    """Fans `seed`'s small, human-curated per-root category/notes/
    pinned_commit values out to one exact, fully-materialized provenance
    dict per path in `allowlist_paths`. Every path must match **exactly
    one** seed root: an unassigned path (no root covers it) or an
    ambiguous path (more than one root covers it) is an actionable
    `ProvenanceError` -- this generator never silently skips a path or
    arbitrarily picks a root when more than one matches.

    `author`/`rightsholder`/`license` are always `"NOASSERTION"`,
    `redistribution_approved` is always `False`, and `reviewer` is always
    `None` for every generated entry: this generator only ever proposes
    the same honest, unresolved starting point issue #9 already recorded
    at category granularity -- it never invents a license, an approval,
    or a reviewer for any path, however it was assigned a root."""
    entries: List[Dict] = []
    for path in sorted(set(allowlist_paths)):
        matches = [root_seed for root_seed in seed if _root_covers_path(root_seed.root, path)]
        if not matches:
            raise ProvenanceError(f"generate: {path!r} matches no seed root in PROVENANCE_ROOT_SEED")
        if len(matches) > 1:
            raise ProvenanceError(
                f"generate: {path!r} matches more than one seed root: "
                f"{sorted(root_seed.root for root_seed in matches)}"
            )
        root_seed = matches[0]
        entry: Dict = {
            "path": path,
            "category": root_seed.category,
            "author": "NOASSERTION",
            "rightsholder": "NOASSERTION",
            "license": "NOASSERTION",
            "redistribution_approved": False,
            "reviewer": None,
            "notes": root_seed.notes,
        }
        if root_seed.category == "submodule":
            entry["pinned_commit"] = root_seed.pinned_commit
        entries.append(entry)
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--provenance-dir", type=Path, default=Path("docs/release_data/provenance"))
    common.add_argument("--allowlist", type=Path, default=Path("docs/release_data/source_allowlist.json"))

    sub.add_parser("check", parents=[common], help="report provenance status + exact allowlist coverage")

    gen = sub.add_parser(
        "generate", parents=[common],
        help="fan PROVENANCE_ROOT_SEED out to one exact entry per allowlisted path",
    )
    gen.add_argument("--write", action="store_true", help="write the result into --provenance-dir instead of stdout")

    args = parser.parse_args(argv)

    if args.command == "generate":
        try:
            allowlist_paths = _load_allowlist_paths(args.allowlist)
            entries = generate_exact_entries(allowlist_paths)
        except ProvenanceError as error:
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
        except ProvenanceError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        coverage_reasons = evaluate_coverage(entries, allowlist_paths)
        if coverage_reasons:
            status = "blocked"
            reasons = sorted(set(reasons) | set(coverage_reasons))

    print(f"provenance status: {status}")
    for reason in reasons:
        print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
