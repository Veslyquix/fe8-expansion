"""Tests for scripts/release_rehearsal/action_pins.py (issue #9 mandatory
correction #1: immutable Actions pin inventory)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import action_pins as ap

SHA_A = "a" * 40
SHA_B = "b" * 40

GOOD_WORKFLOW = f"""\
name: x
on:
  pull_request:
    branches: [ "master" ]
jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{SHA_A} # v7.0.1
        with:
          persist-credentials: false
      - run: make release-check
"""


def _good_inventory_row(**overrides):
    row = {
        "workflow": "workflow.yml",
        "action": "actions/checkout",
        "pinned_sha": SHA_A,
        "human_version": "v7.0.1",
        "source_url": "https://github.com/actions/checkout/releases/tag/v7.0.1",
        "verification_method": "git ls-remote --tags https://github.com/actions/checkout",
        "verified_on": "2026-07-31",
        "update_procedure": "bump the sha, re-verify, update this file",
    }
    row.update(overrides)
    return row


def _write_inventory(dir_path: Path, rows) -> Path:
    path = dir_path / "action_pins.json"
    path.write_text(json.dumps({"schema_version": 1, "pins": rows}), encoding="utf-8")
    return path


class LoadInventoryTests(unittest.TestCase):
    def test_valid_inventory_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_inventory(Path(tmp), [_good_inventory_row()])
            rows = ap.load_inventory(path)
            self.assertEqual(len(rows), 1)

    def test_missing_key_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = _good_inventory_row()
            del row["human_version"]
            path = _write_inventory(Path(tmp), [row])
            with self.assertRaises(ap.ActionPinError) as ctx:
                ap.load_inventory(path)
            self.assertIn("human_version", str(ctx.exception))

    def test_empty_string_field_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_inventory(Path(tmp), [_good_inventory_row(source_url="")])
            with self.assertRaises(ap.ActionPinError):
                ap.load_inventory(path)

    def test_malformed_sha_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_inventory(Path(tmp), [_good_inventory_row(pinned_sha="v7")])
            with self.assertRaises(ap.ActionPinError) as ctx:
                ap.load_inventory(path)
            self.assertIn("40 lowercase hex", str(ctx.exception))

    def test_uppercase_sha_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_inventory(Path(tmp), [_good_inventory_row(pinned_sha="A" * 40)])
            with self.assertRaises(ap.ActionPinError):
                ap.load_inventory(path)

    def test_non_https_source_url_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_inventory(Path(tmp), [_good_inventory_row(source_url="http://example.invalid")])
            with self.assertRaises(ap.ActionPinError):
                ap.load_inventory(path)

    def test_duplicate_workflow_action_pair_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_inventory(Path(tmp), [_good_inventory_row(), _good_inventory_row()])
            with self.assertRaises(ap.ActionPinError) as ctx:
                ap.load_inventory(path)
            self.assertIn("duplicate", str(ctx.exception))

    def test_empty_pins_array_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "action_pins.json"
            path.write_text(json.dumps({"pins": []}), encoding="utf-8")
            with self.assertRaises(ap.ActionPinError):
                ap.load_inventory(path)

    def test_non_json_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "action_pins.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ap.ActionPinError):
                ap.load_inventory(path)


class WorkflowExternalUsesTests(unittest.TestCase):
    def test_extracts_external_reference(self):
        refs = ap.workflow_external_uses(GOOD_WORKFLOW)
        self.assertEqual(refs, {"actions/checkout": SHA_A})

    def test_local_action_excluded(self):
        text = GOOD_WORKFLOW + "      - uses: ./.github/actions/local\n"
        refs = ap.workflow_external_uses(text)
        self.assertNotIn("./.github/actions/local", refs)

    def test_unpinned_reference_excluded(self):
        text = GOOD_WORKFLOW + "      - uses: actions/setup-python\n"
        refs = ap.workflow_external_uses(text)
        self.assertNotIn("actions/setup-python", refs)


class CheckWorkflowAgainstInventoryTests(unittest.TestCase):
    def test_matching_pin_has_no_reasons(self):
        inventory = [_good_inventory_row(workflow="workflow.yml")]
        reasons = ap.check_workflow_against_inventory("workflow.yml", GOOD_WORKFLOW, inventory)
        self.assertEqual(reasons, [])

    def test_missing_inventory_entry_reported(self):
        reasons = ap.check_workflow_against_inventory("workflow.yml", GOOD_WORKFLOW, [])
        self.assertTrue(any("no matching entry" in r for r in reasons))

    def test_mismatched_sha_reported(self):
        inventory = [_good_inventory_row(workflow="workflow.yml", pinned_sha=SHA_B)]
        reasons = ap.check_workflow_against_inventory("workflow.yml", GOOD_WORKFLOW, inventory)
        self.assertTrue(any("does not agree" not in r and "actually pins" in r for r in reasons))

    def test_stale_inventory_entry_reported(self):
        inventory = [
            _good_inventory_row(workflow="workflow.yml"),
            _good_inventory_row(workflow="workflow.yml", action="actions/setup-python", pinned_sha=SHA_B),
        ]
        reasons = ap.check_workflow_against_inventory("workflow.yml", GOOD_WORKFLOW, inventory)
        self.assertTrue(any("stale action-pin inventory entry" in r and "setup-python" in r for r in reasons))

    def test_other_workflows_rows_are_ignored(self):
        inventory = [_good_inventory_row(workflow="other.yml", action="actions/setup-python", pinned_sha=SHA_B)]
        reasons = ap.check_workflow_against_inventory("workflow.yml", GOOD_WORKFLOW, inventory)
        # actions/checkout has no matching row scoped to workflow.yml
        self.assertTrue(any("no matching entry" in r for r in reasons))
        # but the unrelated other.yml row is not flagged as "stale" against this workflow
        self.assertFalse(any("setup-python" in r for r in reasons))


class CheckEndToEndTests(unittest.TestCase):
    def test_clean_pair_has_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workflow_path = tmp_path / "workflow.yml"
            workflow_path.write_text(GOOD_WORKFLOW, encoding="utf-8")
            inventory_path = _write_inventory(tmp_path, [_good_inventory_row(workflow="workflow.yml")])
            self.assertEqual(ap.check(workflow_path, inventory_path, "workflow.yml"), [])

    def test_mutable_tag_and_missing_inventory_both_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workflow_path = tmp_path / "workflow.yml"
            workflow_path.write_text(GOOD_WORKFLOW.replace(f"@{SHA_A}", "@v7"), encoding="utf-8")
            inventory_path = _write_inventory(tmp_path, [_good_inventory_row(workflow="workflow.yml")])
            reasons = ap.check(workflow_path, inventory_path, "workflow.yml")
            self.assertTrue(any("not pinned to an immutable" in r for r in reasons))

    def test_malformed_inventory_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workflow_path = tmp_path / "workflow.yml"
            workflow_path.write_text(GOOD_WORKFLOW, encoding="utf-8")
            inventory_path = tmp_path / "bad.json"
            inventory_path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ap.ActionPinError):
                ap.check(workflow_path, inventory_path, "workflow.yml")


class MainCliTests(unittest.TestCase):
    def test_clean_pair_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workflow_path = tmp_path / "workflow.yml"
            workflow_path.write_text(GOOD_WORKFLOW, encoding="utf-8")
            inventory_path = _write_inventory(tmp_path, [_good_inventory_row(workflow="workflow.yml")])
            code = ap.main([str(workflow_path), "--inventory", str(inventory_path), "--workflow-key", "workflow.yml"])
            self.assertEqual(code, 0)

    def test_finding_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workflow_path = tmp_path / "workflow.yml"
            workflow_path.write_text(GOOD_WORKFLOW.replace(f"@{SHA_A}", "@v7"), encoding="utf-8")
            inventory_path = _write_inventory(tmp_path, [_good_inventory_row(workflow="workflow.yml")])
            code = ap.main([str(workflow_path), "--inventory", str(inventory_path), "--workflow-key", "workflow.yml"])
            self.assertEqual(code, 1)

    def test_missing_workflow_file_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            inventory_path = _write_inventory(tmp_path, [_good_inventory_row(workflow="workflow.yml")])
            code = ap.main([str(tmp_path / "nope.yml"), "--inventory", str(inventory_path)])
            self.assertEqual(code, 2)


class RepositoryStateTests(unittest.TestCase):
    """The real, committed workflow + inventory pair must agree exactly,
    and every external `uses:` reference in the real workflow must be an
    exact 40-lowercase-hex SHA."""

    def test_real_release_rehearsal_workflow_matches_inventory(self):
        workflow_path = ROOT / ".github" / "workflows" / "release-rehearsal.yml"
        inventory_path = ROOT / "docs" / "release_data" / "action_pins.json"
        reasons = ap.check(workflow_path, inventory_path, ap.DEFAULT_WORKFLOW_KEY)
        self.assertEqual(reasons, [])

    def test_inventory_is_well_formed(self):
        inventory_path = ROOT / "docs" / "release_data" / "action_pins.json"
        rows = ap.load_inventory(inventory_path)
        self.assertTrue(rows)

    def test_every_real_workflow_external_action_is_sha_pinned(self):
        workflow_path = ROOT / ".github" / "workflows" / "release-rehearsal.yml"
        text = workflow_path.read_text(encoding="utf-8")
        from scripts.release_rehearsal import workflow_guard as wg
        self.assertEqual(wg.check_uses_pins(text), [])


if __name__ == "__main__":
    unittest.main()
