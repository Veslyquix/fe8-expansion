"""Tests for scripts/release_rehearsal/action_pins.py (issue #9 mandatory
correction #1: immutable Actions pin inventory)."""

import json
import re
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


class WorkflowExternalOccurrencesTests(unittest.TestCase):
    """`ap.workflow_external_uses`'s old `{action: pin}` dict return
    shape is gone entirely (issue #9 hardening): it silently collapsed
    every occurrence of the same action down to whichever one happened
    to be seen last, which is exactly the "duplicate/conflicting
    occurrence disappears without a trace" defect this rewrite closes.
    `ap.workflow_external_occurrences` returns a flat, ordered list of
    `ap.ActionOccurrence` instead -- one entry per physical occurrence,
    always -- so this test module (like the real implementation) can
    never accidentally lose one."""

    def test_extracts_external_reference(self):
        occurrences = ap.workflow_external_occurrences(GOOD_WORKFLOW)
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0].action, "actions/checkout")
        self.assertEqual(occurrences[0].ref, SHA_A)

    def test_local_action_excluded(self):
        text = GOOD_WORKFLOW + "      - uses: ./.github/actions/local\n"
        occurrences = ap.workflow_external_occurrences(text)
        self.assertFalse(any(o.action == "./.github/actions/local" for o in occurrences))

    def test_unpinned_reference_excluded(self):
        text = GOOD_WORKFLOW + "      - uses: actions/setup-python\n"
        occurrences = ap.workflow_external_occurrences(text)
        self.assertFalse(any(o.action == "actions/setup-python" for o in occurrences))

    def test_every_occurrence_of_a_repeated_action_is_preserved(self):
        """The core occurrence-preservation contract: two separate
        `uses:` occurrences of the *same* action, at two different
        lines, must both come back -- never collapsed into one."""
        text = GOOD_WORKFLOW + f"      - uses: actions/checkout@{SHA_B}\n"
        occurrences = [o for o in ap.workflow_external_occurrences(text) if o.action == "actions/checkout"]
        self.assertEqual(len(occurrences), 2)
        self.assertEqual({o.ref for o in occurrences}, {SHA_A, SHA_B})
        self.assertEqual({o.line for o in occurrences}, {occurrences[0].line, occurrences[1].line})
        self.assertNotEqual(occurrences[0].line, occurrences[1].line)

    def test_flow_mapping_occurrence_is_extracted(self):
        """A `uses:` occurrence hidden inside a flow mapping (the
        original code-review-found bypass -- the old line-anchored
        regex never matched it at all) must be extracted exactly like
        an ordinary block-style one."""
        text = GOOD_WORKFLOW + f"      - {{uses: actions/setup-node@{SHA_B}}}\n"
        occurrences = [o for o in ap.workflow_external_occurrences(text) if o.action == "actions/setup-node"]
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0].ref, SHA_B)

    def test_ambiguous_occurrence_excluded_but_still_reported_by_workflow_guard(self):
        """A *repeated* 'uses' key within the very same flow mapping is
        invalid YAML (a mapping must not repeat a key): the scanner
        keeps the first occurrence as an ordinary, clean, bijection-
        eligible reference, but flags every *repeat* after it
        ('duplicate-key') and excludes only that flagged repeat from
        this module's own per-action bijection view -- it is already
        unconditionally, separately reported, precisely, by
        `workflow_guard.check_uses_pins`, so it must never be silently
        dropped from the *system's* overall result even though this
        module's own view no longer carries it."""
        text = GOOD_WORKFLOW + (
            f"      - {{uses: actions/setup-node@{SHA_A}, uses: actions/setup-node@{SHA_B}}}\n"
        )
        occurrences = [o for o in ap.workflow_external_occurrences(text) if o.action == "actions/setup-node"]
        # only the first (clean) occurrence survives into this module's own view
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0].ref, SHA_A)
        from scripts.release_rehearsal import workflow_guard as wg
        self.assertTrue(any("duplicate" in v.lower() for v in wg.check_uses_pins(text)))


class HashInPlainScalarBypassRetainedByActionPinsTests(unittest.TestCase):
    """Final-review-found critical bypass (shared with
    `workflow_guard`'s own adversarial coverage): this module consumes
    the very same `workflow_guard.extract_uses_occurrences` scanner via
    `workflow_external_occurrences`, so a `uses:` occurrence hidden
    after a '#'-glued plain scalar (e.g. `name: setup#`) must be
    retained -- with its correct action/ref/line -- here too, never
    silently dropped the way the previous, unconditional '#'-starts-a-
    comment scanning bug would have dropped it."""

    def test_uses_after_hash_glued_plain_scalar_is_retained_with_line(self):
        text = GOOD_WORKFLOW + "      - {name: setup#, uses: evilcorp/upload-secrets@main}\n"
        occurrences = [o for o in ap.workflow_external_occurrences(text) if o.action == "evilcorp/upload-secrets"]
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0].ref, "main")
        self.assertIsInstance(occurrences[0].line, int)
        self.assertGreater(occurrences[0].line, 0)

    def test_uses_after_hash_glued_plain_scalar_reported_as_unmatched_inventory_entry(self):
        """With no matching row in the committed inventory at all, the
        cross-check must report it (via `check_workflow_against_inventory`)
        exactly like any other un-inventoried external action -- it
        must never vanish from the system's overall result just because
        it was preceded by a '#'-containing plain scalar."""
        text = GOOD_WORKFLOW + "      - {name: setup#, uses: evilcorp/upload-secrets@main}\n"
        reasons = ap.check_workflow_against_inventory(
            "workflow.yml", text, [_good_inventory_row(workflow="workflow.yml")]
        )
        self.assertTrue(any("upload-secrets" in r and "no matching entry" in r for r in reasons), reasons)

    def test_immutable_uses_after_hash_glued_plain_scalar_retained_and_matched(self):
        """The mirror-image, non-adversarial case: a correctly pinned
        action after a '#'-containing plain scalar must still be found
        and successfully cross-checked against a matching inventory row."""
        text = GOOD_WORKFLOW + f"      - {{name: setup#, uses: actions/setup-node@{SHA_B}}}\n"
        occurrences = [o for o in ap.workflow_external_occurrences(text) if o.action == "actions/setup-node"]
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0].ref, SHA_B)
        inventory = [
            _good_inventory_row(workflow="workflow.yml"),
            _good_inventory_row(
                workflow="workflow.yml",
                action="actions/setup-node",
                pinned_sha=SHA_B,
                source_url="https://github.com/actions/setup-node/releases/tag/v4.0.0",
            ),
        ]
        reasons = ap.check_workflow_against_inventory("workflow.yml", text, inventory)
        self.assertFalse(any("setup-node" in r for r in reasons), reasons)


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


class OccurrencePreservationTests(unittest.TestCase):
    """Adversarial coverage for issue #9's second code-review finding:
    the action-pin inventory cross-check must never let a workflow
    occurrence silently disappear by dict-overwrite, and must fail
    closed on every conflicting/unrecorded duplicate `uses:` occurrence
    of the same action -- regardless of whether some *other* occurrence
    of that action happens to match the committed inventory."""

    def _two_occurrence_workflow(self, sha_first: str, sha_second: str) -> str:
        return (
            GOOD_WORKFLOW
            + f"      - uses: actions/setup-node@{sha_first}\n"
            + f"      - uses: actions/setup-node@{sha_second}\n"
        )

    def test_conflicting_duplicate_shas_rejected_even_when_one_matches_inventory(self):
        """The exact scenario named by the task: an *earlier* occurrence
        pinned to some conflicting SHA, and a *later* occurrence that
        happens to exactly match the committed inventory row, must
        still never pass -- the conflict itself is the failure,
        independent of which occurrence the inventory happens to
        agree with."""
        text = self._two_occurrence_workflow(SHA_B, SHA_A)  # first=B (conflict), second=A (matches inventory)
        inventory = [
            _good_inventory_row(workflow="workflow.yml"),
            _good_inventory_row(workflow="workflow.yml", action="actions/setup-node", pinned_sha=SHA_A),
        ]
        reasons = ap.check_workflow_against_inventory("workflow.yml", text, inventory)
        self.assertTrue(any("conflicting SHAs" in r and "setup-node" in r for r in reasons), reasons)
        # every occurrence's own line number is named as evidence
        self.assertTrue(any(re.search(r"line \d+ -> '" + SHA_A + r"'", r) for r in reasons), reasons)
        self.assertTrue(any(re.search(r"line \d+ -> '" + SHA_B + r"'", r) for r in reasons), reasons)

    def test_conflicting_shas_reversed_order_still_rejected(self):
        """Order must not matter: the *first* occurrence matching the
        inventory and a *later* one conflicting is exactly as rejected
        as the reverse."""
        text = self._two_occurrence_workflow(SHA_A, SHA_B)
        inventory = [
            _good_inventory_row(workflow="workflow.yml"),
            _good_inventory_row(workflow="workflow.yml", action="actions/setup-node", pinned_sha=SHA_A),
        ]
        reasons = ap.check_workflow_against_inventory("workflow.yml", text, inventory)
        self.assertTrue(any("conflicting SHAs" in r for r in reasons), reasons)

    def test_same_sha_duplicate_occurrence_unrecorded_is_rejected(self):
        """Two occurrences of the same action, both pinned to the
        *identical* SHA -- no conflict -- must still fail closed if the
        inventory's ('occurrence_count'-defaulted-to-1) row does not
        truthfully record that there really are two occurrences. A
        same-SHA duplicate must never silently disappear."""
        text = self._two_occurrence_workflow(SHA_A, SHA_A)
        inventory = [
            _good_inventory_row(workflow="workflow.yml"),
            _good_inventory_row(workflow="workflow.yml", action="actions/setup-node", pinned_sha=SHA_A),
        ]
        reasons = ap.check_workflow_against_inventory("workflow.yml", text, inventory)
        self.assertTrue(
            any("actually occurs 2 time(s)" in r and "occurrence_count" in r for r in reasons), reasons
        )

    def test_same_sha_duplicate_occurrence_explicitly_recorded_passes(self):
        """The same two-identical-SHA-occurrence workflow passes cleanly
        once the inventory truthfully records 'occurrence_count': 2 --
        the smallest durable schema evolution this module needed."""
        text = self._two_occurrence_workflow(SHA_A, SHA_A)
        inventory = [
            _good_inventory_row(workflow="workflow.yml"),
            _good_inventory_row(
                workflow="workflow.yml", action="actions/setup-node", pinned_sha=SHA_A, occurrence_count=2
            ),
        ]
        reasons = ap.check_workflow_against_inventory("workflow.yml", text, inventory)
        self.assertEqual(reasons, [])

    def test_wrong_occurrence_count_still_rejected(self):
        """An inventory row that declares the *wrong* occurrence count
        (here: 3, when the workflow really has 2) must still fail --
        'occurrence_count' is a truthful fact about the workflow, not a
        free-form allowance."""
        text = self._two_occurrence_workflow(SHA_A, SHA_A)
        inventory = [
            _good_inventory_row(workflow="workflow.yml"),
            _good_inventory_row(
                workflow="workflow.yml", action="actions/setup-node", pinned_sha=SHA_A, occurrence_count=3
            ),
        ]
        reasons = ap.check_workflow_against_inventory("workflow.yml", text, inventory)
        self.assertTrue(any("actually occurs 2 time(s)" in r for r in reasons), reasons)

    def test_single_occurrence_default_occurrence_count_still_works(self):
        """The ordinary, single-occurrence case (today's real committed
        inventory's own shape) needs no 'occurrence_count' field at all
        -- it defaults to 1, which is the truth for a single
        occurrence."""
        reasons = ap.check_workflow_against_inventory(
            "workflow.yml", GOOD_WORKFLOW, [_good_inventory_row(workflow="workflow.yml")]
        )
        self.assertEqual(reasons, [])

    def test_unrecorded_single_action_occurrence_reported_with_evidence(self):
        text = GOOD_WORKFLOW + f"      - uses: actions/setup-node@{SHA_B}\n"
        reasons = ap.check_workflow_against_inventory("workflow.yml", text, [_good_inventory_row(workflow="workflow.yml")])
        self.assertTrue(
            any("setup-node" in r and "no matching entry" in r and f"line" in r for r in reasons), reasons
        )

    def test_flow_mapping_duplicate_occurrence_participates_in_bijection(self):
        """A duplicate occurrence hidden inside a flow mapping is exactly
        as subject to the same-SHA-duplicate/'occurrence_count' rule as
        an ordinary block-style one -- the canonical extractor, not the
        surface YAML spelling, is what this module's logic keys off
        of."""
        text = GOOD_WORKFLOW + (
            f"      - {{uses: actions/setup-node@{SHA_A}}}\n"
            f"      - uses: actions/setup-node@{SHA_A}\n"
        )
        inventory = [
            _good_inventory_row(workflow="workflow.yml"),
            _good_inventory_row(workflow="workflow.yml", action="actions/setup-node", pinned_sha=SHA_A),
        ]
        reasons = ap.check_workflow_against_inventory("workflow.yml", text, inventory)
        self.assertTrue(any("actually occurs 2 time(s)" in r for r in reasons), reasons)


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
