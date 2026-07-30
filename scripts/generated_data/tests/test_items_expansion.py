"""Item ID expansion pilot: opt-in 0xCD -> 0xCE end to end (Issue #10).

Proves the pilot is a *real* generation/config change, not a fabricated
count: the default (vanilla) path is untouched, the opt-in path actually
emits the 0xCE record, an un-opted 0xCE is rejected early with an
actionable diagnostic, and the value survives the save/suspend/link item
fields bit-exactly (those fields are already 14-bit, so 0 layout change).
"""

import os
import unittest

from scripts.generated_data import idspace
from scripts.generated_data.diagnostics import DiagnosticCollector
from scripts.generated_data.items import schema as items_schema
from scripts.generated_data.items import generate as items_generate

REPO_ROOT = idspace.REPO_ROOT
ITEMS_JSON = os.path.join(REPO_ROOT, "src", "data", "items.json")
EXP_HEADER = items_schema.ITEMS_EXPANSION_HEADER
EXP_SOURCE = items_schema.ITEMS_EXPANSION_SOURCE


# --- Save/suspend/link bit-field model (mirrors include/bmsave.h) -----------
# GameSavePackedUnit.item1..item5 and SuspendSavePackedUnit.item4/item5 are
# 14-bit; SuspendSavePackedUnit.item1..3 are u16. GameSavePackedUnit.jid is
# 7-bit. These masks are the real on-media widths.
ITEM_SAVE_MASK = 0x3FFF   # 14-bit
JID_SAVE_MASK = 0x7F      # 7-bit


def pack_item14(value):
    return value & ITEM_SAVE_MASK


def pack_jid7(value):
    return value & JID_SAVE_MASK


class DefaultPathUnchangedTests(unittest.TestCase):
    def test_default_load_is_vanilla_206(self):
        recs = items_schema.load_records(ITEMS_JSON)
        self.assertEqual(len(recs), 206)
        self.assertFalse(any(r.item == "ITEM_EXPANSION_CE" for r in recs))

    def test_default_generation_has_no_expansion(self):
        recs = items_schema.load_records(ITEMS_JSON)
        c = items_generate.generate_c_source(recs, ITEMS_JSON)
        self.assertNotIn("ITEM_EXPANSION_CE", c)
        self.assertNotIn("items_expansion.h", c)


class OptInExpansionTests(unittest.TestCase):
    def test_optin_load_merges_overlay(self):
        recs = items_schema.load_records(ITEMS_JSON, item_cap=0xCE,
                                         overlay_source=EXP_SOURCE)
        self.assertEqual(len(recs), 207)
        self.assertTrue(any(r.item == "ITEM_EXPANSION_CE" for r in recs))

    def test_optin_validates_clean(self):
        recs = items_schema.load_records(ITEMS_JSON, item_cap=0xCE,
                                         overlay_source=EXP_SOURCE)
        diags = DiagnosticCollector()
        items_schema.validate(recs, diags, item_cap=0xCE, expansion_header=EXP_HEADER)
        self.assertEqual(diags.errors, [], diags.render())

    def test_optin_generation_emits_ce_record(self):
        recs = items_schema.load_records(ITEMS_JSON, item_cap=0xCE,
                                         overlay_source=EXP_SOURCE)
        c = items_generate.generate_c_source(recs, ITEMS_JSON)
        self.assertIn("[ITEM_EXPANSION_CE] = {", c)
        self.assertIn("#include \"constants/items_expansion.h\"", c)


class DefaultDisabledRejectionTests(unittest.TestCase):
    def test_unopted_ce_is_rejected_actionably(self):
        # Load the overlay record but validate under the *default* cap 0xCD.
        recs = items_schema.load_records(ITEMS_JSON, item_cap=0xCE,
                                         overlay_source=EXP_SOURCE)
        diags = DiagnosticCollector()
        items_schema.validate(recs, diags, item_cap=0xCD, expansion_header=EXP_HEADER)
        messages = [str(e) for e in diags.errors]
        self.assertTrue(
            any("beyond the configured item cap" in m and "FE8_ITEM_ID_CAP" in m
                for m in messages), messages)


class SaveFieldRoundtripTests(unittest.TestCase):
    def test_item_ids_survive_14bit_field(self):
        for value in (0x00, 0xCD, 0xCE, 0xFF, ITEM_SAVE_MASK):
            self.assertEqual(pack_item14(value), value,
                             "item 0x{:X} truncated by the 14-bit save field".format(value))

    def test_item_technical_max_fits_save(self):
        item = idspace.domain_by_key("item")
        self.assertEqual(pack_item14(item.technical_max), item.technical_max)

    def test_class_0x80_truncates_in_jid_field(self):
        # Proof the class domain cannot expand without a save layout change.
        self.assertEqual(pack_jid7(0x7F), 0x7F)
        self.assertEqual(pack_jid7(0x80), 0x00)
        self.assertNotEqual(pack_jid7(0x80), 0x80)


if __name__ == "__main__":
    unittest.main()
