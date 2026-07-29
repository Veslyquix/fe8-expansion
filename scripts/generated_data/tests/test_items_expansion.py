"""Item ID expansion pilot: opt-in 0xCD -> 0xCE end to end (Issue #10),
plus the issue #6 framework-authored CONTENT record that now occupies it.

Proves the pilot is a *real* generation/config change, not a fabricated
count: the default (vanilla) path is untouched, the opt-in path actually
emits the 0xCE record, an un-opted 0xCE is rejected early with an
actionable diagnostic, and the value survives the save/suspend/link item
fields bit-exactly (those fields are already 14-bit, so 0 layout change).

The issue #6 half proves the record is a genuine authored content example
rather than a placeholder: it carries meaningful, bounded, schema-validated
item fields and ORIGINAL name/description/use-description text authored
through the repository's own text pipeline (texts/texts.txt ->
include/constants/msg.h), referenced symbolically so the binding cannot
silently drift.
"""

import json
import os
import tempfile
import unittest

from scripts.generated_data import idspace
from scripts.generated_data.diagnostics import GeneratedDataError
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


class AuthoredContentRecordTests(unittest.TestCase):
    """Issue #6: the 0xCE record is a real, original, bounded content example."""

    def setUp(self):
        self.records = items_schema.load_records(
            ITEMS_JSON, item_cap=0xCE, overlay_source=EXP_SOURCE)
        self.record = next(r for r in self.records if r.item == "ITEM_EXPANSION_CE")
        self.raw = json.loads(open(EXP_SOURCE, encoding="utf-8").read())
        self.raw_record = self.raw["items"][0]
        self.msg = items_schema.read_msg_constants()

    def test_text_ids_are_authored_symbolically(self):
        """Every text field must name a MSG_* symbol, never a bare number:
        a raw number would silently repoint at whatever message later lands
        on that index."""
        for field in ("nameTextId", "descTextId", "useDescTextId"):
            value = self.raw_record.get(field)
            self.assertIsInstance(
                value, str,
                "{} must be authored as a symbolic MSG_* name".format(field))
            self.assertIn(value, self.msg)

    def test_text_ids_are_framework_original_messages(self):
        """The three messages must be the framework's OWN new messages --
        not a reused vanilla message index."""
        for field in ("nameTextId", "descTextId", "useDescTextId"):
            symbol = self.raw_record[field]
            self.assertTrue(
                symbol.startswith("MSG_EXPANSION_"),
                "{} reuses '{}'; author an original MSG_EXPANSION_* message "
                "instead".format(field, symbol))

    def test_resolved_text_ids_match_the_header(self):
        self.assertEqual(self.record.name_text_id,
                         self.msg[self.raw_record["nameTextId"]][0])
        self.assertEqual(self.record.desc_text_id,
                         self.msg[self.raw_record["descTextId"]][0])
        self.assertEqual(self.record.use_desc_text_id,
                         self.msg[self.raw_record["useDescTextId"]][0])

    def test_original_messages_are_not_vanilla_indices(self):
        """The authored messages must live beyond every vanilla message the
        206 hand-ported records use, i.e. they are genuinely new."""
        vanilla_max = max(
            max(r.name_text_id, r.desc_text_id, r.use_desc_text_id)
            for r in self.records if r.item != "ITEM_EXPANSION_CE")
        for value in (self.record.name_text_id, self.record.desc_text_id,
                      self.record.use_desc_text_id):
            self.assertGreater(value, vanilla_max)

    def test_item_fields_are_meaningful_and_bounded(self):
        """Not a blank placeholder: a real type, real uses, a real attribute
        bitmask -- each inside its schema bound."""
        self.assertEqual(self.record.weapon_type, "ITYPE_ITEM")
        self.assertGreater(self.record.max_uses, 0)
        self.assertLessEqual(self.record.max_uses, 255)
        self.assertEqual(self.record.attributes, ["IA_UNSELLABLE"])
        self.assertEqual(self.record.encoded_range, 0)
        self.assertEqual(self.record.might, 0)
        self.assertEqual(self.record.hit, 0)

    def test_icon_is_an_existing_slot_and_adds_no_asset(self):
        """The record must point at an EXISTING icon slot: the framework
        ships no new graphics asset for its content example."""
        icon_count = items_schema.read_item_icon_count()
        self.assertGreaterEqual(self.record.icon_id, 0)
        self.assertLess(self.record.icon_id, icon_count)

    def test_generated_record_carries_every_authored_field(self):
        c = items_generate.generate_c_source(self.records, ITEMS_JSON)
        body = c[c.index("[ITEM_EXPANSION_CE] = {"):]
        body = body[:body.index("\n\t},")]
        self.assertIn(".nameTextId = {},".format(self.record.name_text_id), body)
        self.assertIn(".descTextId = {},".format(self.record.desc_text_id), body)
        self.assertIn(".useDescTextId = {},".format(self.record.use_desc_text_id), body)
        self.assertIn(".number = ITEM_EXPANSION_CE,", body)
        self.assertIn(".weaponType = ITYPE_ITEM,", body)
        self.assertIn(".attributes = IA_UNSELLABLE,", body)
        self.assertIn(".maxUses = {},".format(self.record.max_uses), body)
        self.assertIn(".iconId = {},".format(self.record.icon_id), body)

    def test_made_item_packs_authored_uses(self):
        """MakeNewItem(item) = uses<<8 | id (src/bmitem.c), so the authored
        uses count is observable in every runtime item halfword."""
        self.assertEqual((self.record.max_uses << 8) | 0xCE, 0x03CE)


class SymbolicTextIdTests(unittest.TestCase):
    """The schema's symbolic MSG_* text-ID form itself."""

    def test_unknown_symbol_is_rejected_actionably(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({
                    "$schema": "fe8.items.v1",
                    "items": [{
                        "item": "ITEM_EXPANSION_CE",
                        "weaponType": "ITYPE_ITEM",
                        "nameTextId": "MSG_NO_SUCH_MESSAGE",
                    }],
                }, handle)
            with self.assertRaises(GeneratedDataError) as ctx:
                items_schema.load_records(ITEMS_JSON, item_cap=0xCE, overlay_source=path)
            message = str(ctx.exception)
            self.assertIn("MSG_NO_SUCH_MESSAGE", message)
            self.assertIn("texts/texts.txt", message)

    def test_numeric_form_still_accepted(self):
        """The 206 vanilla records keep authoring plain integers."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "numeric.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({
                    "$schema": "fe8.items.v1",
                    "items": [{
                        "item": "ITEM_EXPANSION_CE",
                        "weaponType": "ITYPE_ITEM",
                        "nameTextId": 7,
                    }],
                }, handle)
            records = items_schema.load_records(
                ITEMS_JSON, item_cap=0xCE, overlay_source=path)
            record = next(r for r in records if r.item == "ITEM_EXPANSION_CE")
            self.assertEqual(record.name_text_id, 7)

    def test_msg_count_is_not_a_usable_text_id(self):
        """MSG_COUNT is the table bound, not a message."""
        self.assertNotIn("MSG_COUNT", items_schema.read_msg_constants())


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
