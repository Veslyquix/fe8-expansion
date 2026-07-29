#!/usr/bin/env python3
"""Source-release provenance manifests (issue #9).

Reads factual, hand-seeded JSON provenance manifests from
``docs/release_data/provenance/*.json`` and evaluates whether every entry has a
complete provenance record with redistribution permission recorded: a
non-``NOASSERTION`` author, rightsholder, and license, an explicit
``redistribution_approved: true``, and a named human reviewer. This
module never invents or infers any of those facts -- it only reads what a
human has recorded -- and it never selects or adds a root license, and
its own reported status is never a release/publication approval (see
``evaluate()`` below and docs/release_process.md's "Legal and provenance
boundary" section).

Deliberately dependency-free (Python stdlib only, JSON only).

Manifest entry schema::

    {
      "path": "graphics",              # exact repo-relative path/category
      "category": "asset",             # "code" | "asset" | "submodule"
      "author": "NOASSERTION",         # or a real, human-recorded name
      "rightsholder": "NOASSERTION",
      "license": "NOASSERTION",
      "redistribution_approved": false,
      "reviewer": null,                # or a real human reviewer identity
      "notes": "free-form factual note",
      "pinned_commit": null            # required, non-null for category "submodule"
    }

Exit codes (CLI): 0 well-formed report (status may be "blocked" or
"mechanically eligible" -- both are valid, expected outcomes; neither is
itself a release/publication approval), 2 actionable schema error
(missing/invalid field -- a defect in the manifest itself, distinct from
an honestly-recorded unresolved fact).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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
    """A provenance manifest entry is malformed (a tooling defect, not an
    honestly-unresolved fact)."""


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


def _entry_covers_path(entry_path: str, candidate_path: str) -> bool:
    """True if `entry_path` is either exactly `candidate_path`, or a
    directory-prefix ancestor of it (`candidate_path` starts with
    `entry_path + "/"`). This is the exact-or-directory-prefix "coverage"
    relationship every provenance-vs-allowlist check below is built from:
    it is what lets a small number of hand-reviewed, category-level
    provenance entries (e.g. a single "src" entry) legitimately cover
    every one of the many thousands of exact per-file entries in
    docs/release_data/source_allowlist.json (see
    scripts/release_rehearsal/allowlist.py) without hand-authoring a
    separate, near-duplicate provenance record for every single file --
    an "equally strong binding" to a literal one-entry-per-file bijection,
    since `find_ambiguous_entries`/`find_ghost_entries`/`coverage_gaps`
    together guarantee every allowlisted path is covered by *exactly*
    one entry, no entry covers *nothing*, and no two entries overlap."""
    return candidate_path == entry_path or candidate_path.startswith(entry_path + "/")


def coverage_gaps(entries: List[Dict], required_paths: List[str]) -> List[str]:
    """Every path in required_paths (typically the source allowlist) must be
    covered (exactly, or by directory-prefix ancestry -- see
    `_entry_covers_path`) by at least one provenance entry; report exact
    gaps: a required path no entry covers at all."""
    roots = [entry["path"] for entry in entries]
    return sorted(
        candidate for candidate in required_paths
        if not any(_entry_covers_path(root, candidate) for root in roots)
    )


def find_ghost_entries(entries: List[Dict], required_paths: List[str]) -> List[str]:
    """A "ghost" entry covers zero of `required_paths` -- e.g. a stale
    provenance record left behind after the directory/file it described
    was renamed or removed from the allowlist. Every entry must pull its
    weight; an entry that matches nothing is exactly as much a
    consistency defect as a gap is."""
    ghosts = []
    for entry in entries:
        root = entry["path"]
        if not any(_entry_covers_path(root, candidate) for candidate in required_paths):
            ghosts.append(root)
    return sorted(ghosts)


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
    """Two entries whose `path`s are in a directory-ancestor relationship
    (one is a prefix of the other, e.g. "src" and "src/lib") -- a file
    under both could be claimed by either entry, which is exactly the
    "duplicate/ambiguous coverage" issue #9's exact-provenance-binding
    requirement forbids. (An *exact* duplicate path is reported by
    `find_duplicate_entry_paths` instead, so this only reports genuine
    ancestor/descendant overlaps between two distinct path strings.)"""
    roots = sorted({entry["path"] for entry in entries})
    ambiguous = set()
    for index, first in enumerate(roots):
        for second in roots[index + 1:]:
            if _entry_covers_path(first, second) or _entry_covers_path(second, first):
                ambiguous.add(first)
                ambiguous.add(second)
    return sorted(ambiguous)


def evaluate_coverage(entries: List[Dict], required_paths: List[str]) -> List[str]:
    """One combined, human-readable reason list covering every provenance-
    vs-allowlist coverage defect class: exact-duplicate entry paths,
    ambiguous/overlapping entry paths, missing coverage (a gap), and ghost
    entries (covering nothing). An empty return means the coverage is a
    clean bijection (or the "equally strong" exact/prefix-ancestor
    binding this module implements -- see `_entry_covers_path`)."""
    reasons: List[str] = []
    reasons += [f"duplicate provenance entry path: {path}" for path in find_duplicate_entry_paths(entries)]
    reasons += [
        f"ambiguous/overlapping provenance coverage: {path}"
        for path in find_ambiguous_entries(entries)
    ]
    reasons += [f"missing provenance entry for {path}" for path in coverage_gaps(entries, required_paths)]
    reasons += [
        f"ghost provenance entry (covers no allowlisted path): {path}"
        for path in find_ghost_entries(entries, required_paths)
    ]
    return sorted(reasons)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provenance-dir", type=Path, default=Path("docs/release_data/provenance"))
    parser.add_argument("--allowlist", type=Path, default=Path("docs/release_data/source_allowlist.json"))
    args = parser.parse_args(argv)

    try:
        entries = load_all(args.provenance_dir)
    except ProvenanceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    status, reasons = evaluate(entries)

    if args.allowlist.is_file():
        try:
            allowlist = json.loads(args.allowlist.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"error: {args.allowlist}: not valid JSON: {error}", file=sys.stderr)
            return 2
        coverage_reasons = evaluate_coverage(entries, allowlist.get("paths", []))
        if coverage_reasons:
            status = "blocked"
            reasons = sorted(set(reasons) | set(coverage_reasons))

    print(f"provenance status: {status}")
    for reason in reasons:
        print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
