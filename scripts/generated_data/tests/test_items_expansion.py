"""Item ID expansion pilot: opt-in 0xCD -> 0xCE end to end (Issue #10),
plus the issue #6 framework-authored CONTENT record that now occupies it.

Proves the pilot is a *real* generation/config change, not a fabricated
count: the default (vanilla) path is untouched, the opt-in path actually
emits the 0xCE record, an un-opted 0xCE is rejected early with an
actionable diagnostic, and the value survives the save/suspend/link item
fields bit-exactly (those fields are already 14-bit, so 0 layout change).

The issue #6 half proves the record is a genuine authored content example
rather than a placeholder: it carries meaningful, bounded, schema-validated
item fields.

It also pins the POLICY invariant this record must never break again: a
framework-authored content record consumes NO shared-message slot. The
global message table (texts/texts.txt -> include/constants/msg.h ->
src/msg_data.c) is Huffman-compressed as one blob, so appending a message
re-encodes it for EVERY build -- including default, content-free ones. The
content example therefore authors no message at all; its original display
text travels the config-gated generated-content path instead (see
scripts/generated_data/items/content_text.py).
"""

import json
import os
import pathlib
import tempfile
import unittest

from scripts.generated_data import idspace
from scripts.generated_data.diagnostics import GeneratedDataError
from scripts.generated_data.diagnostics import DiagnosticCollector
from scripts.generated_data.items import schema as items_schema
from scripts.generated_data.items import generate as items_generate
from scripts.generated_data.items import content_text as items_content_text

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
        self.raw = json.loads(pathlib.Path(EXP_SOURCE).read_text(encoding="utf-8"))
        self.raw_record = self.raw["items"][0]
        self.msg = items_schema.read_msg_constants()

    def test_record_consumes_no_shared_message_slot(self):
        """POLICY: a framework-authored content record must not append to
        the shared, Huffman-compressed global message table -- doing so
        re-encodes the text blob of every build, default ones included."""
        for field in ("nameTextId", "descTextId", "useDescTextId"):
            self.assertNotIn(
                field, self.raw_record,
                "{} points the content record at the shared message table; "
                "author the display text through the config-gated content "
                "text path instead".format(field))
        self.assertEqual(self.record.name_text_id, 0)
        self.assertEqual(self.record.desc_text_id, 0)
        self.assertEqual(self.record.use_desc_text_id, 0)

    def test_no_vanilla_message_is_reused(self):
        """The record must not borrow a vanilla message index either: a
        blank binding is honest, a copied one is copyright reuse."""
        vanilla = {
            value
            for r in self.records if r.item != "ITEM_EXPANSION_CE"
            for value in (r.name_text_id, r.desc_text_id, r.use_desc_text_id)
            if value
        }
        for value in (self.record.name_text_id, self.record.desc_text_id,
                      self.record.use_desc_text_id):
            self.assertNotIn(value, vanilla)

    def test_msg_count_is_the_vanilla_bound(self):
        """Guards the regression directly: the live MSG_COUNT must still be
        the count this branch inherited, i.e. issue #6 added no message."""
        self.assertEqual(items_schema.read_msg_count(), 0x0D56)

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
        self.assertNotIn(".nameTextId", body)
        self.assertNotIn(".descTextId", body)
        self.assertNotIn(".useDescTextId", body)
        self.assertIn(".number = ITEM_EXPANSION_CE,", body)
        self.assertIn(".weaponType = ITYPE_ITEM,", body)
        self.assertIn(".attributes = IA_UNSELLABLE,", body)
        self.assertIn(".maxUses = {},".format(self.record.max_uses), body)
        self.assertIn(".iconId = {},".format(self.record.icon_id), body)

    def test_made_item_packs_authored_uses(self):
        """MakeNewItem(item) = uses<<8 | id (src/bmitem.c), so the authored
        uses count is observable in every runtime item halfword."""
        self.assertEqual((self.record.max_uses << 8) | 0xCE, 0x03CE)


class AuthoringTextTests(unittest.TestCase):
    """The replacement for the removed messages: ORIGINAL literal text,
    authored in the record, generated only into the content profile."""

    def setUp(self):
        self.records = items_schema.load_records(
            ITEMS_JSON, item_cap=0xCE, overlay_source=EXP_SOURCE)
        self.record = next(r for r in self.records if r.item == "ITEM_EXPANSION_CE")
        self.raw_record = json.loads(pathlib.Path(EXP_SOURCE).read_text(encoding="utf-8"))["items"][0]

    def _overlay(self, tmp, record):
        path = os.path.join(tmp, "overlay.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"$schema": "fe8.items.v1", "items": [record]}, handle)
        return path

    def _validate(self, path):
        records = items_schema.load_records(ITEMS_JSON, item_cap=0xCE, overlay_source=path)
        diags = DiagnosticCollector()
        items_schema.validate(records, diags, item_cap=0xCE, expansion_header=EXP_HEADER)
        return [str(e) for e in diags.errors]

    def test_record_authors_original_literal_text(self):
        self.assertEqual(self.record.authoring_name, self.raw_record["authoringName"])
        self.assertTrue(self.record.authoring_name.strip())
        self.assertTrue(self.record.authoring_description)
        self.assertTrue(self.record.authoring_use_description)

    def test_authoring_text_never_reaches_the_item_table(self):
        """gItemData[] must be byte-identical with or without the authoring
        fields: they are content-profile text, not item data."""
        with_text = items_generate.generate_c_source(self.records, ITEMS_JSON)
        stripped = json.loads(pathlib.Path(EXP_SOURCE).read_text(encoding="utf-8"))
        for field in ("authoringName", "authoringDescription", "authoringUseDescription"):
            stripped["items"][0].pop(field)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "no_text.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(stripped, handle)
            without = items_generate.generate_c_source(
                items_schema.load_records(ITEMS_JSON, item_cap=0xCE, overlay_source=path),
                ITEMS_JSON)
        self.assertEqual(with_text, without)
        self.assertNotIn(self.record.authoring_name, with_text)

    def test_vanilla_record_may_not_author_literal_text(self):
        """A vanilla record keeps its vanilla message ID; overriding its name
        with literal text is not an authoring surface this schema offers."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "vanilla.json")
            raw = json.loads(pathlib.Path(ITEMS_JSON).read_text(encoding="utf-8"))
            raw["items"][1]["authoringName"] = "Renamed"
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(raw, handle)
            records = items_schema.load_records(path, item_cap=0xCE, overlay_source=EXP_SOURCE)
            diags = DiagnosticCollector()
            items_schema.validate(records, diags, item_cap=0xCE, expansion_header=EXP_HEADER)
            messages = [str(e) for e in diags.errors]
        self.assertTrue(any("only valid on a framework-authored expansion record" in m
                            for m in messages), messages)

    def test_literal_text_and_message_id_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._overlay(tmp, {
                "item": "ITEM_EXPANSION_CE",
                "weaponType": "ITYPE_ITEM",
                "authoringName": "Both",
                "nameTextId": 7,
            })
            messages = self._validate(path)
        self.assertTrue(any("choose one source of truth" in m for m in messages), messages)

    def test_authoring_text_is_bounded_and_printable_ascii(self):
        with tempfile.TemporaryDirectory() as tmp:
            too_long = self._overlay(tmp, {
                "item": "ITEM_EXPANSION_CE",
                "weaponType": "ITYPE_ITEM",
                "authoringName": "x" * (items_schema.AUTHORING_NAME_MAX_CHARS + 1),
            })
            with self.assertRaises(GeneratedDataError) as ctx:
                items_schema.load_records(ITEMS_JSON, item_cap=0xCE, overlay_source=too_long)
            self.assertIn("the bound is", str(ctx.exception))

            non_ascii = self._overlay(tmp, {
                "item": "ITEM_EXPANSION_CE",
                "weaponType": "ITYPE_ITEM",
                "authoringName": "Caf\u00e9 Charm",
            })
            with self.assertRaises(GeneratedDataError) as ctx:
                items_schema.load_records(ITEMS_JSON, item_cap=0xCE, overlay_source=non_ascii)
            self.assertIn("printable ASCII", str(ctx.exception))

            padded = self._overlay(tmp, {
                "item": "ITEM_EXPANSION_CE",
                "weaponType": "ITYPE_ITEM",
                "authoringName": " Padded ",
            })
            with self.assertRaises(GeneratedDataError) as ctx:
                items_schema.load_records(ITEMS_JSON, item_cap=0xCE, overlay_source=padded)
            self.assertIn("whitespace", str(ctx.exception))


class ContentTextGeneratorTests(unittest.TestCase):
    """scripts/generated_data/items/content_text.py itself."""

    def setUp(self):
        self.records = items_schema.load_records(
            ITEMS_JSON, item_cap=0xCE, overlay_source=EXP_SOURCE)
        self.collected = items_content_text.collect(self.records)

    def test_only_authored_expansion_records_are_collected(self):
        self.assertEqual(len(self.collected), 1)
        symbol, value, record = self.collected[0]
        self.assertEqual(symbol, "ITEM_EXPANSION_CE")
        self.assertEqual(value, 0xCE)
        self.assertEqual(record.authoring_name, "Sample Charm")

    def test_default_cap_collects_nothing(self):
        """No overlay merged at the vanilla cap -> nothing to generate."""
        self.assertEqual(items_content_text.collect(
            items_schema.load_records(ITEMS_JSON)), [])

    def test_header_holds_the_exact_literal_and_capacity(self):
        header = items_content_text.render_header(
            self.collected, "src/data/items_expansion.json")
        self.assertIn('{ ITEM_EXPANSION_CE, "Sample Charm" },', header)
        self.assertIn("#define EXPANSION_CONTENT_TEXT_COUNT 1", header)
        self.assertIn("#define EXPANSION_CONTENT_TEXT_NAME_CAPACITY {}".format(
            len("Sample Charm") + 1), header)
        self.assertIn("AUTO-GENERATED", header)
        self.assertNotIn("//", header)

    def test_catalog_is_honest_about_the_description_boundary(self):
        catalog = json.loads(items_content_text.render_catalog(
            self.collected, "src/data/items_expansion.json"))
        entry = catalog["items"][0]
        self.assertEqual(entry["authoringName"], "Sample Charm")
        self.assertIn("not shown in game", entry["runtimeText"]["description"])
        self.assertIn("GetItemName()", entry["runtimeText"]["name"])

    def test_content_flag_and_cap_dependencies_are_hard_errors(self):
        self.assertEqual(items_content_text.resolve_content_flag("1"), 1)
        self.assertEqual(items_content_text.resolve_content_flag(None, {}), 0)
        with self.assertRaises(GeneratedDataError):
            items_content_text.resolve_content_flag("2")
        with self.assertRaises(GeneratedDataError) as ctx:
            items_content_text.require_cap(idspace.ITEM_DEFAULT_CAP)
        self.assertIn("FE8_ITEM_ID_CAP", str(ctx.exception))


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
