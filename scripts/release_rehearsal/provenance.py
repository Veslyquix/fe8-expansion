#!/usr/bin/env python3
"""Source-release provenance manifests (issue #9).

Reads factual, hand-seeded JSON provenance manifests from
``docs/release_data/provenance/*.json`` and evaluates whether every entry has a
complete, approved provenance record: a non-``NOASSERTION`` author,
rightsholder, and license, an explicit ``redistribution_approved: true``,
and a named human reviewer. This module never invents or infers any of
those facts -- it only reads what a human has recorded -- and it never
selects or adds a root license. See docs/release_process.md's "Legal and
provenance boundary" section.

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
"approved" -- both are valid, expected outcomes), 2 actionable schema
error (missing/invalid field -- a defect in the manifest itself, distinct
from an honestly-recorded unresolved fact).
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
    entry is fully resolved and approved, in which case it is "approved"."""
    if not entries:
        return "blocked", ["no provenance entries recorded"]
    reasons: List[str] = []
    for entry in entries:
        reasons.extend(_entry_blocking_reasons(entry))
    status = "blocked" if reasons else "approved"
    return status, sorted(reasons)


def coverage_gaps(entries: List[Dict], required_paths: List[str]) -> List[str]:
    """Every path in required_paths (typically the source allowlist) must be
    covered by at least one provenance entry; report exact gaps."""
    covered = {entry["path"] for entry in entries}
    return sorted(path for path in required_paths if path not in covered)


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
        gaps = coverage_gaps(entries, allowlist.get("paths", []))
        if gaps:
            status = "blocked"
            reasons = sorted(set(reasons) | {f"missing provenance entry for {path}" for path in gaps})

    print(f"provenance status: {status}")
    for reason in reasons:
        print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
