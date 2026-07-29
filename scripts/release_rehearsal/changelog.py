#!/usr/bin/env python3
"""Machine changelog fragments (issue #9).

Reads categorized, schema-validated JSON fragments from a fragment
directory (default: ``changelog_fragments/``), aggregates their declared SemVer
impact, and deterministically renders the ``## [Unreleased]`` section of
``CHANGELOG.md``. See docs/release_process.md for the full authoring
contract and docs/public_api_policy.md for what counts as a
major/minor/patch change on this pre-1.0 project.

Deliberately dependency-free (Python stdlib only, JSON only -- no YAML),
matching this repository's existing scripts/modernize/*.py tools.

Fragment schema (one JSON object per file, ``changelog_fragments/<slug>.json``)::

    {
      "issue": 9,                 # int or null
      "category": "added",        # see CATEGORIES below
      "summary": "one-line, present-tense description",
      "semver_impact": "none"     # see IMPACTS below
    }

Exit codes (CLI): 0 success/deterministic report, 2 actionable schema or
staleness error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

CATEGORIES = (
    "added",
    "changed",
    "deprecated",
    "removed",
    "fixed",
    "security",
    "docs",
    "internal",
)
CATEGORY_TITLES = {
    "added": "Added",
    "changed": "Changed",
    "deprecated": "Deprecated",
    "removed": "Removed",
    "fixed": "Fixed",
    "security": "Security",
    "docs": "Docs",
    "internal": "Internal",
}

IMPACTS = ("none", "patch", "minor", "major")
IMPACT_RANK = {name: rank for rank, name in enumerate(IMPACTS)}

FRAGMENT_GLOB = "*.json"
UNRELEASED_BEGIN = "<!-- release-rehearsal:unreleased:begin -->"
UNRELEASED_END = "<!-- release-rehearsal:unreleased:end -->"


class ChangelogError(ValueError):
    """A fragment or the rendered changelog is malformed or stale."""


def load_fragment(path: Path) -> Dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ChangelogError(f"{path}: not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ChangelogError(f"{path}: fragment must be a JSON object")

    missing = [key for key in ("category", "summary", "semver_impact") if key not in data]
    if missing:
        raise ChangelogError(f"{path}: missing required field(s): {', '.join(missing)}")

    category = data["category"]
    if category not in CATEGORIES:
        raise ChangelogError(
            f"{path}: category {category!r} not in {CATEGORIES}"
        )

    summary = data["summary"]
    if not isinstance(summary, str) or not summary.strip():
        raise ChangelogError(f"{path}: summary must be a non-empty string")

    impact = data["semver_impact"]
    if impact not in IMPACTS:
        raise ChangelogError(f"{path}: semver_impact {impact!r} not in {IMPACTS}")

    issue = data.get("issue")
    if issue is not None and not isinstance(issue, int):
        raise ChangelogError(f"{path}: issue must be an integer or null")

    return {
        "path": str(path),
        "category": category,
        "summary": summary.strip(),
        "semver_impact": impact,
        "issue": issue,
    }


def load_fragments(fragment_dir: Path) -> List[Dict]:
    fragment_dir = Path(fragment_dir)
    if not fragment_dir.is_dir():
        raise ChangelogError(f"fragment directory not found: {fragment_dir}")
    paths = sorted(fragment_dir.glob(FRAGMENT_GLOB))
    return [load_fragment(path) for path in paths]


def aggregate_impact(fragments: List[Dict]) -> str:
    if not fragments:
        return "none"
    best = max(fragments, key=lambda fragment: IMPACT_RANK[fragment["semver_impact"]])
    return best["semver_impact"]


def render_unreleased(fragments: List[Dict]) -> str:
    """Deterministically render the Unreleased section body (no heading).

    Ordering is fixed: CATEGORIES order, then by (issue or -1, summary)
    within a category, so re-rendering the same fragment set always
    produces byte-identical output on any host.
    """
    lines: List[str] = []
    by_category: Dict[str, List[Dict]] = {category: [] for category in CATEGORIES}
    for fragment in fragments:
        by_category[fragment["category"]].append(fragment)

    if not fragments:
        lines.append("No unreleased changes.")
        return "\n".join(lines) + "\n"

    for category in CATEGORIES:
        entries = by_category[category]
        if not entries:
            continue
        entries = sorted(entries, key=lambda fragment: (fragment["issue"] or -1, fragment["summary"]))
        lines.append(f"### {CATEGORY_TITLES[category]}")
        lines.append("")
        for fragment in entries:
            suffix = f" (#{fragment['issue']})" if fragment["issue"] is not None else ""
            lines.append(f"- {fragment['summary']}{suffix}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _extract_marked_section(text: str) -> str:
    if UNRELEASED_BEGIN not in text or UNRELEASED_END not in text:
        raise ChangelogError(
            f"CHANGELOG.md is missing the {UNRELEASED_BEGIN!r}/{UNRELEASED_END!r} "
            "markers around its Unreleased section"
        )
    start = text.index(UNRELEASED_BEGIN) + len(UNRELEASED_BEGIN)
    end = text.index(UNRELEASED_END)
    if end < start:
        raise ChangelogError("CHANGELOG.md's Unreleased markers are out of order")
    return text[start:end].strip("\n")


def check(fragment_dir: Path, changelog_path: Path) -> Tuple[bool, List[str], str, str]:
    """Validate fragments and check CHANGELOG.md's Unreleased section is
    byte-identical (modulo surrounding whitespace) to their deterministic
    rendering. Returns (ok, errors, rendered_text, aggregate_impact)."""
    errors: List[str] = []
    fragments: List[Dict] = []
    try:
        fragments = load_fragments(fragment_dir)
    except ChangelogError as error:
        return False, [str(error)], "", "none"

    rendered = render_unreleased(fragments)
    impact = aggregate_impact(fragments)

    changelog_path = Path(changelog_path)
    if not changelog_path.is_file():
        errors.append(f"changelog not found: {changelog_path}")
        return False, errors, rendered, impact

    text = changelog_path.read_text(encoding="utf-8")
    try:
        current = _extract_marked_section(text)
    except ChangelogError as error:
        errors.append(str(error))
        return False, errors, rendered, impact

    if current.strip("\n") != rendered.strip("\n"):
        errors.append(
            f"{changelog_path} Unreleased section is stale: run "
            "'python3 -m scripts.release_rehearsal.changelog render' and update it"
        )

    return (not errors), errors, rendered, impact


def render_full_changelog(text: str, rendered_section: str) -> str:
    before = text[: text.index(UNRELEASED_BEGIN) + len(UNRELEASED_BEGIN)]
    after = text[text.index(UNRELEASED_END):]
    return f"{before}\n{rendered_section.rstrip(chr(10))}\n{after}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--fragment-dir", type=Path, default=Path("changelog_fragments"))
    common.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))

    sub.add_parser("render", parents=[common], help="print the deterministic Unreleased section")
    sub.add_parser("check", parents=[common], help="validate fragments + changelog freshness")
    write_p = sub.add_parser(
        "write", parents=[common], help="rewrite CHANGELOG.md's Unreleased section in place"
    )

    args = parser.parse_args(argv)

    if args.command == "render":
        try:
            fragments = load_fragments(args.fragment_dir)
        except ChangelogError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        sys.stdout.write(render_unreleased(fragments))
        return 0

    if args.command == "write":
        try:
            fragments = load_fragments(args.fragment_dir)
        except ChangelogError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        rendered = render_unreleased(fragments)
        text = args.changelog.read_text(encoding="utf-8")
        args.changelog.write_text(render_full_changelog(text, rendered), encoding="utf-8")
        return 0

    ok, errors, rendered, impact = check(args.fragment_dir, args.changelog)
    if not ok:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"changelog: ok ({len(rendered.splitlines())} rendered line(s), aggregate impact: {impact})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
