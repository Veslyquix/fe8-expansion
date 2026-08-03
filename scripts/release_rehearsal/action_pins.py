#!/usr/bin/env python3
"""Immutable GitHub Actions pin inventory + workflow cross-check (issue #9
mandatory correction #1).

`scripts/release_rehearsal/workflow_guard.py`'s `check_uses_pins` already
rejects any external `uses:` reference that is not pinned to an exact,
immutable 40-lowercase-hex commit SHA. That alone proves the *shape* of
the pin is correct; it says nothing about *which* upstream release that
SHA actually corresponds to, or how a human reviewer is meant to update
it later. This module is the separate, factual record of that: a
committed, machine-readable inventory
(``docs/release_data/action_pins.json``) naming, for every external
action a workflow references, the exact action repository, the pinned
commit SHA, the human-readable upstream version that SHA corresponds to,
the exact upstream source reference used to establish that
correspondence, and the update procedure a future maintainer follows to
move the pin forward.

**This inventory is documentation/evidence only -- never an
authorization mechanism.** Nothing in this module grants publication
eligibility; it only ever proves "the pin in the real workflow file and
the pin recorded in this inventory are the same commit, and that commit
is independently, factually documented" -- exactly like every other
release-rehearsal guard, a clean result here is necessary, never
sufficient, for anything.

**How the pinned SHA was actually selected (a one-time, human/agent-time
step -- never re-executed automatically by this checker):** a read-only
``git ls-remote --tags <upstream repo url>`` (or equivalent GitHub REST
API read) against the *official* action repository, cross-checking the
returned commit against the named release tag. This module's own
`check()` function deliberately never shells out to any network command
itself (it only ever reads the two already-committed local files: the
workflow text and this inventory) -- see `docs/release_data/
action_pins.json`'s own `verification_method`/`verified_on` fields for
the exact, recorded evidence of that one-time lookup for each pin.

Deliberately dependency-free (Python stdlib only); never executes or
mutates any GitHub state (no `gh`, no authenticated API call, no local
git remote add/fetch of the upstream action repository).

Exit codes (CLI): 0 clean, 1 pin/inventory finding(s), 2 invocation/I/O or
schema error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from scripts.release_rehearsal import workflow_guard as wg

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_INVENTORY_PATH = Path("docs/release_data/action_pins.json")
DEFAULT_WORKFLOW_KEY = ".github/workflows/release-rehearsal.yml"

REQUIRED_INVENTORY_KEYS = (
    "workflow",
    "action",
    "pinned_sha",
    "human_version",
    "source_url",
    "verification_method",
    "verified_on",
    "update_procedure",
)


class ActionPinError(ValueError):
    """A malformed inventory record, or an I/O/JSON defect -- an
    actionable tooling defect, distinct from a normal "unpinned/
    mismatched action" finding (reported as a string in a list, never
    raised)."""


def load_inventory(path: Path) -> List[Dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ActionPinError(f"{path}: not valid JSON: {error}") from error
    pins = data.get("pins")
    if not isinstance(pins, list) or not pins:
        raise ActionPinError(f"{path}: must contain a non-empty 'pins' array")
    seen_keys = set()
    for index, entry in enumerate(pins):
        if not isinstance(entry, dict):
            raise ActionPinError(f"{path}[{index}]: entry must be a JSON object")
        missing = [
            key for key in REQUIRED_INVENTORY_KEYS
            if not isinstance(entry.get(key), str) or not entry.get(key)
        ]
        if missing:
            raise ActionPinError(
                f"{path}[{index}] ({entry.get('action', '?')!r}): missing/empty required key(s): "
                + ", ".join(missing)
            )
        if not FULL_SHA_RE.fullmatch(entry["pinned_sha"]):
            raise ActionPinError(
                f"{path}[{index}] ({entry['action']}): pinned_sha {entry['pinned_sha']!r} is not "
                "exactly 40 lowercase hex characters"
            )
        if not entry["source_url"].startswith("https://"):
            raise ActionPinError(
                f"{path}[{index}] ({entry['action']}): source_url {entry['source_url']!r} must be "
                "an https:// URL"
            )
        if "occurrence_count" in entry:
            occurrence_count = entry["occurrence_count"]
            if not isinstance(occurrence_count, int) or isinstance(occurrence_count, bool) or occurrence_count < 1:
                raise ActionPinError(
                    f"{path}[{index}] ({entry['action']}): 'occurrence_count' {occurrence_count!r} "
                    "must be a positive integer (the exact number of separate 'uses:' occurrences "
                    "of this action this workflow file actually contains)"
                )
        key = (entry["workflow"], entry["action"])
        if key in seen_keys:
            raise ActionPinError(f"{path}: duplicate inventory entry for workflow/action {key}")
        seen_keys.add(key)
    return pins


@dataclass(frozen=True)
class ActionOccurrence:
    """One individual, external, `@ref`-pinned `uses:` occurrence -- the
    exact `(action, ref, line)` this occurrence recorded, never
    collapsed/overwritten against any other occurrence of the same
    action elsewhere in the same workflow (that collapsing -- a bare
    `{action: pin}` dict silently overwritten key-by-key as each match
    was found -- was itself a code-review-found defect this module used
    to have: a second, differently-pinned occurrence of the same action
    silently replaced the first in that dict, so only the *last*
    occurrence was ever cross-checked and an earlier, conflicting SHA
    (or an earlier, entirely unrecorded duplicate) could vanish without
    a trace). See `workflow_external_occurrences` and
    `check_workflow_against_inventory` below for how every occurrence is
    preserved and truthfully accounted for instead."""

    action: str
    ref: str
    line: int


def workflow_external_occurrences(text: str) -> List[ActionOccurrence]:
    """Every *external*, `@ref`-pinned `uses:` occurrence in `text`,
    preserved individually (never collapsed/keyed by action name -- see
    `ActionOccurrence`'s own docstring for why that matters). Uses the
    single canonical `workflow_guard.extract_uses_occurrences` scanner
    (block style, flow style, quoted or bare keys, all alike) -- there
    is exactly one definition, repository-wide, of what a `uses:`
    reference looks like (issue #9 hardening: this module and
    `workflow_guard` no longer have two divergent regex-based
    extractors). A local action (`wg.is_local_action_reference`) is
    never included (there is nothing to cross-check it against; see
    that function's own docstring); a reference with no `@ref` at all,
    or an occurrence `workflow_guard` itself already flags as
    unsupported/ambiguous (`occ.problem` set -- an anchor, alias, tag,
    template expression, unterminated quote, ambiguous embedded colon,
    or duplicate key), is also excluded here -- both classes are
    already reported, precisely and unconditionally, by
    `workflow_guard.check_uses_pins` itself; this function's own job is
    exact-pin, per-occurrence bijection cross-checking of the
    remaining, cleanly-parsed external references, never re-detecting
    an already-covered malformed/ambiguous-reference class a second
    time under a different message."""
    occurrences: List[ActionOccurrence] = []
    for occ in wg.extract_uses_occurrences(text):
        if occ.problem is not None:
            continue
        action_ref = occ.action_ref
        if wg.is_local_action_reference(action_ref):
            continue
        if "@" not in action_ref:
            continue
        action, _, ref = action_ref.rpartition("@")
        occurrences.append(ActionOccurrence(action=action, ref=ref, line=occ.line))
    return occurrences


def _format_occurrences(occurrences: List[ActionOccurrence]) -> str:
    return ", ".join(f"line {occurrence.line} -> {occurrence.ref!r}" for occurrence in occurrences)


def check_workflow_against_inventory(workflow_key: str, text: str, inventory: List[Dict]) -> List[str]:
    """Exact, occurrence-preserving bijection between `workflow_key`'s
    own external `uses:` occurrences and the inventory row recorded for
    that exact workflow/action pair (`load_inventory` itself already
    enforces at most one inventory row per `(workflow, action)` pair --
    see its own duplicate-key check -- so an inventory row can never
    itself silently overwrite another; the risk this function closes is
    entirely on the *workflow* side: two or more separate `uses:`
    occurrences of the very same action in the very same workflow file,
    which a naive `{action: pin}` dict would silently collapse into
    "whichever occurrence happened to be seen last").

    For every action referenced one or more times in this workflow:

      * if its occurrences disagree on the pinned SHA at all (a
        conflicting duplicate), this is rejected outright -- with every
        occurrence's own line number and SHA named explicitly -- no
        matter what the inventory records for that action; a later
        occurrence that happens to match the inventory can never make
        an earlier, conflicting occurrence pass.
      * otherwise every occurrence shares one identical SHA. That SHA
        must have a matching, identically-pinned inventory row (exactly
        as before); in addition, the row's own (optional, defaulting to
        `1`) `occurrence_count` field must equal the *actual* number of
        occurrences this workflow really has -- so a second (third,
        ...), identically-pinned, but never-truthfully-recorded
        duplicate occurrence can never silently disappear either; it
        must be truthfully counted in the inventory (the smallest
        durable schema change this module needed -- a single optional
        integer field -- rather than a full per-occurrence inventory
        schema, since every occurrence of one action in one workflow is
        already required to share one identical SHA by the check
        immediately above).

    A row recorded for `workflow_key` naming an action no longer
    referenced by this workflow at all is still reported stale, exactly
    as before."""
    reasons: List[str] = []
    occurrences = workflow_external_occurrences(text)
    occurrences_by_action: Dict[str, List[ActionOccurrence]] = {}
    for occurrence in occurrences:
        occurrences_by_action.setdefault(occurrence.action, []).append(occurrence)

    inventory_rows = [row for row in inventory if row["workflow"] == workflow_key]
    inventory_by_action = {row["action"]: row for row in inventory_rows}

    for action, action_occurrences in sorted(occurrences_by_action.items()):
        unique_shas = sorted({occurrence.ref for occurrence in action_occurrences})
        if len(unique_shas) > 1:
            reasons.append(
                f"{workflow_key}: action {action!r} has {len(action_occurrences)} 'uses:' "
                f"occurrences pinned to conflicting SHAs ({_format_occurrences(action_occurrences)}) "
                "-- every occurrence of the same action in the same workflow must pin the "
                "identical immutable SHA; this can never pass no matter what the action-pin "
                "inventory records"
            )
            continue

        sha = unique_shas[0]
        row = inventory_by_action.get(action)
        if row is None:
            reasons.append(
                f"{workflow_key}: '{action}@{sha}' ({len(action_occurrences)} occurrence(s): "
                f"{_format_occurrences(action_occurrences)}) has no matching entry in the "
                f"action-pin inventory ({DEFAULT_INVENTORY_PATH})"
            )
            continue
        if row["pinned_sha"] != sha:
            reasons.append(
                f"{workflow_key}: action-pin inventory records pinned_sha {row['pinned_sha']!r} for "
                f"{action!r}, but the workflow itself actually pins {sha!r} -- these must agree exactly"
            )
            continue

        expected_count = row.get("occurrence_count", 1)
        if expected_count != len(action_occurrences):
            reasons.append(
                f"{workflow_key}: action {action!r} actually occurs {len(action_occurrences)} "
                f"time(s) in this workflow ({_format_occurrences(action_occurrences)}), but the "
                f"action-pin inventory's 'occurrence_count' for {action!r} records "
                f"{expected_count} -- every duplicate occurrence must be truthfully counted in "
                "the inventory, even when every occurrence pins the identical SHA (a same-SHA "
                "duplicate must never silently disappear)"
            )

    for action in sorted(set(inventory_by_action) - set(occurrences_by_action)):
        reasons.append(
            f"{workflow_key}: stale action-pin inventory entry for {action!r} (no longer referenced "
            "by this workflow)"
        )

    return reasons


def check(
    workflow_path: Path,
    inventory_path: Path = DEFAULT_INVENTORY_PATH,
    workflow_key: str = DEFAULT_WORKFLOW_KEY,
) -> List[str]:
    """Full check: (1) every external `uses:` reference in the workflow
    at `workflow_path` is pinned to an exact 40-lowercase-hex SHA
    (`workflow_guard.check_uses_pins`, reused rather than duplicated --
    exactly one implementation of "what a valid pin looks like"); (2) the
    committed inventory at `inventory_path` is itself well-formed; (3) the
    workflow's pins and the inventory's rows for `workflow_key` agree
    exactly, in both directions. Returns a flat, human-readable finding
    list (empty means fully consistent) -- never raises for an ordinary
    "unpinned/mismatched" finding; only raises `ActionPinError` for an
    actual I/O/schema defect in the inventory file itself."""
    try:
        text = Path(workflow_path).read_text(encoding="utf-8")
    except OSError as error:
        raise ActionPinError(f"{workflow_path}: {error}") from error

    reasons = list(wg.check_uses_pins(text))
    inventory = load_inventory(inventory_path)
    reasons += check_workflow_against_inventory(workflow_key, text, inventory)
    return sorted(set(reasons))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", type=Path)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY_PATH)
    parser.add_argument("--workflow-key", default=None, help="key to match in the inventory's 'workflow' field (default: the given workflow path, posix-normalized)")
    args = parser.parse_args(argv)

    workflow_key = args.workflow_key or Path(args.workflow).as_posix()

    try:
        violations = check(args.workflow, args.inventory, workflow_key)
    except ActionPinError as error:
        print(f"action_pins: error: {error}", file=sys.stderr)
        return 2

    for violation in violations:
        print(violation)
    if violations:
        print(f"action_pins: {len(violations)} finding(s)", file=sys.stderr)
        return 1
    print(f"action_pins: {args.workflow} ok (matches {args.inventory})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
