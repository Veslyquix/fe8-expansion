"""Regression: opt-in item ID expansion must not false-positive the vanilla
round trip (Issue #10 phase 2).

Directly reproduces the original failure -- `FE8_ITEM_ID_CAP=0xCE make ...
generated-data-check` exiting non-zero with

    src/data_items.c:1:1: expected item(s) ['ITEM_EXPANSION_CE'] not found in
    gItemData[] in src/data_items.c

-- and pins the fix: overlay-only expansion IDs are round-trip-verified
separately (they are never in the vanilla hand table), while every one of the
206 vanilla records is still compared field-for-field. No global
--no-roundtrip and no weakening of the existing comparison.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from scripts.generated_data import idspace
from scripts.generated_data.items import schema as items_schema

REPO_ROOT = idspace.REPO_ROOT
ITEMS_JSON = os.path.join(REPO_ROOT, "src", "data", "items.json")
HAND_C = os.path.join(REPO_ROOT, "src", "data_items.c")
EXP_SOURCE = items_schema.ITEMS_EXPANSION_SOURCE


class RoundTripRegressionTests(unittest.TestCase):
    def _optin_records(self):
        return items_schema.load_records(ITEMS_JSON, item_cap=0xCE,
                                         overlay_source=EXP_SOURCE)

    def test_original_failure_is_reproduced_on_the_naive_path(self):
        # The pre-fix behaviour: passing every generated name (incl. the
        # overlay-only ITEM_EXPANSION_CE) straight to the hand-file parser
        # still raises exactly the original diagnostic -- proving this test
        # exercises the real failure surface, not a strawman.
        from scripts.generated_data.items import parser as items_parser
        from scripts.generated_data.diagnostics import GeneratedDataError
        recs = self._optin_records()
        names = [r.item for r in recs]
        with self.assertRaises(GeneratedDataError) as ctx:
            items_parser.parse_hand_written(HAND_C, names)
        self.assertIn("ITEM_EXPANSION_CE", str(ctx.exception))
        self.assertIn("not found in gItemData[]", str(ctx.exception))

    def test_schema_roundtrip_is_clean_with_overlay(self):
        # The fixed schema path: overlay-only records are excluded from the
        # hand round trip, so no error is produced at cap 0xCE.
        recs = self._optin_records()
        errors = items_schema.ItemsTableSchema().round_trip_errors(recs, HAND_C)
        self.assertEqual([str(e) for e in errors], [])

    def test_all_206_vanilla_records_still_compared(self):
        # Guard against silently dropping vanilla records: mutate one vanilla
        # record and require the round trip to catch the drift.
        recs = self._optin_records()
        vanilla = [r for r in recs if r.item != "ITEM_EXPANSION_CE"]
        self.assertEqual(len(vanilla), 206)
        target = next(r for r in recs if r.item == "ITEM_SWORD_IRON")
        original = target.might
        try:
            target.might = original + 7
            errors = items_schema.ItemsTableSchema().round_trip_errors(recs, HAND_C)
            self.assertTrue(
                any("ITEM_SWORD_IRON" in str(e) for e in errors),
                "vanilla record mutation was not caught by the round trip",
            )
        finally:
            target.might = original


class CliCheckRegressionTests(unittest.TestCase):
    def _run_check(self, cap=None):
        env = dict(os.environ)
        env.pop("FE8_ITEM_ID_CAP", None)
        if cap is not None:
            env["FE8_ITEM_ID_CAP"] = cap
        # Isolate the ephemeral C output in a TemporaryDirectory: check
        # self-heals build/generated/data/data_items.c (write-if-changed),
        # so running it here at a non-default cap (0xCE) MUST NOT write the
        # real shared build/ tree -- doing so leaves a 207-record
        # data_items.c behind whose mtime outranks every tracked input, and
        # a later default (0xCD) make would silently link it (the cap stamp
        # still reads 0xCD, so ordinary mtime staleness treats the poisoned
        # file as up to date). The committed-inventory drift check is
        # unaffected by --out-dir (it always reads the real reports/ copy).
        with tempfile.TemporaryDirectory() as out_dir:
            return subprocess.run(
                [sys.executable, "-m", "scripts.generated_data",
                 "check", "--table", "items", "--out-dir", out_dir],
                cwd=REPO_ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )

    def test_default_cap_check_passes(self):
        res = self._run_check()
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("no drift for table 'items' (206 record(s))", res.stdout)

    def test_optin_cap_check_passes_without_hand_file_error(self):
        res = self._run_check(cap="0xCE")
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertNotIn("not found in gItemData", res.stdout)
        # The overlay record is still validated (207 records loaded), it is
        # only excluded from the *hand* round trip.
        self.assertIn("no drift for table 'items' (207 record(s))", res.stdout)


if __name__ == "__main__":
    unittest.main()
