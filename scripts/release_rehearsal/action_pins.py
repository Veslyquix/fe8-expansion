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
        key = (entry["workflow"], entry["action"])
        if key in seen_keys:
            raise ActionPinError(f"{path}: duplicate inventory entry for workflow/action {key}")
        seen_keys.add(key)
    return pins


def workflow_external_uses(text: str) -> Dict[str, str]:
    """Every *external* `uses:` reference in `text`, as an exact
    `{action: pinned_sha}` mapping -- a local action
    (`wg.is_local_action_reference`) is never included (there is nothing
    to cross-check it against; see that function's own docstring), and a
    reference with no `@ref` at all is also excluded here (already
    reported, precisely, by `workflow_guard.check_uses_pins` -- this
    function's job is exact-pin cross-checking, not re-detecting an
    already-covered malformed-reference class)."""
    refs: Dict[str, str] = {}
    for match in wg._USES_LINE_RE.finditer(text):
        action_ref = match.group(1)
        if wg.is_local_action_reference(action_ref):
            continue
        if "@" not in action_ref:
            continue
        action, _, pin = action_ref.rpartition("@")
        refs[action] = pin
    return refs


def check_workflow_against_inventory(workflow_key: str, text: str, inventory: List[Dict]) -> List[str]:
    """Exact bijection between `workflow_key`'s own external `uses:`
    references and the inventory rows recorded for that exact workflow
    path: every external reference must have exactly one inventory row
    naming the same action with the identical `pinned_sha` (a workflow
    pin that was hand-edited to some other SHA without updating the
    inventory -- or vice versa -- is caught here, never silently
    tolerated because "some" inventory row happens to exist for that
    action); every inventory row recorded for `workflow_key` must
    correspond to a reference that is actually still present (a stale
    inventory row left behind after an action was removed is reported
    too, exactly like every other exact-bijection check in this release-
    rehearsal system)."""
    reasons: List[str] = []
    workflow_refs = workflow_external_uses(text)
    inventory_rows = [row for row in inventory if row["workflow"] == workflow_key]
    inventory_by_action = {row["action"]: row for row in inventory_rows}

    for action, pin in sorted(workflow_refs.items()):
        row = inventory_by_action.get(action)
        if row is None:
            reasons.append(
                f"{workflow_key}: '{action}@{pin}' has no matching entry in the action-pin "
                f"inventory ({DEFAULT_INVENTORY_PATH})"
            )
            continue
        if row["pinned_sha"] != pin:
            reasons.append(
                f"{workflow_key}: action-pin inventory records pinned_sha {row['pinned_sha']!r} for "
                f"{action!r}, but the workflow itself actually pins {pin!r} -- these must agree exactly"
            )

    for action in sorted(set(inventory_by_action) - set(workflow_refs)):
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
