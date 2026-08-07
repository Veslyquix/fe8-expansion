import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization.game_locales.parsers import (
    LocaleSourceError,
    parse_fe8cn,
    parse_hash_indexed,
)


class GameLocaleParserTests(unittest.TestCase):
    def test_committed_indexed_sources_have_exact_fe8j_layout(self):
        japanese = parse_hash_indexed(
            (ROOT / "texts/locales/ja/indexed.txt").read_text(encoding="utf-8")
        )
        chinese = parse_hash_indexed(
            (ROOT / "texts/locales/zh-Hans/indexed.txt").read_text(encoding="utf-8")
        )
        self.assertEqual(len(japanese), 3339)
        self.assertEqual(len(chinese), 3339)
        self.assertEqual(japanese[-1].id, 0x0D0A)
        self.assertEqual(chinese[-1].id, 0x0D0A)

    def test_control_only_a_line_is_not_an_indexed_marker(self):
        source = "\n".join(
            (
                "[00]",
                "first",
                "[A]",
                "[01]",
                "second",
                "[08001234]",
                "raw",
                "",
            )
        )
        parsed = parse_fe8cn(source, expected_last_id=1)
        self.assertEqual(parsed.indexed[0].text, "first\n[A]")
        self.assertEqual(parsed.indexed[1].text, "second")

    def test_hash_markers_reject_out_of_order_input(self):
        source = "#0x0000\nzero\n#0x0002\ntwo\n"
        with self.assertRaisesRegex(LocaleSourceError, "expected marker #0x0001"):
            parse_hash_indexed(source, expected_last_id=1)

    def test_hash_markers_reject_malformed_input(self):
        source = "#0x0000\nzero\n#0x001\none\n"
        with self.assertRaisesRegex(LocaleSourceError, "malformed indexed marker"):
            parse_hash_indexed(source, expected_last_id=1)

    def test_cn_markers_reject_out_of_order_input(self):
        source = "[00]\nzero\n[02]\ntwo\n[08001234]\nraw\n"
        with self.assertRaisesRegex(LocaleSourceError, "expected indexed marker"):
            parse_fe8cn(source, expected_last_id=1)

    def test_noncanonical_bare_hex_token_cannot_silently_become_payload(self):
        source = "[00]\nzero\n[0001]\npayload\n[08001234]\nraw\n"
        with self.assertRaisesRegex(
            LocaleSourceError,
            "bare hex tokens cannot be payload",
        ):
            parse_fe8cn(source, expected_last_id=0)

    def test_conflicting_duplicate_raw_addresses_are_rejected(self):
        source = "\n".join(
            (
                "[00]",
                "indexed",
                "[08001234]",
                "first",
                "[08001234]",
                "second",
                "",
            )
        )
        with self.assertRaisesRegex(LocaleSourceError, "conflicting payloads"):
            parse_fe8cn(source, expected_last_id=0)

    def test_committed_raw_records_preserve_duplicate_provenance(self):
        data = json.loads(
            (ROOT / "texts/locales/zh-Hans/raw.json").read_text(encoding="utf-8")
        )
        self.assertEqual(data["record_count"], 152)
        self.assertEqual(data["unique_import_count"], 143)
        self.assertEqual(data["unique_address_count"], 143)
        self.assertEqual(len(data["records"]), 143)
        self.assertTrue(
            all("address" not in record and "key" not in record for record in data["records"])
        )
        duplicates = [
            record
            for record in data["records"]
            if len(record["provenance"]["occurrences"]) > 1
        ]
        self.assertEqual(len(duplicates), 9)
        self.assertTrue(
            all(len(record["provenance"]["occurrences"]) == 2 for record in duplicates)
        )
        self.assertEqual(
            {record["provenance"]["address"] for record in duplicates},
            {
                "0x08AC1A0C",
                "0x08AC1A30",
                "0x08AC1A54",
                "0x08AC1A78",
                "0x08AC1A9C",
                "0x08AC1B0C",
                "0x08AC1B30",
                "0x08AC1B54",
                "0x08AC1B78",
            },
        )
        self.assertEqual(
            [record["import_id"] for record in data["records"]],
            [f"fe8cn.raw.import-{index:04d}" for index in range(143)],
        )

    def test_raw_import_ids_do_not_change_when_addresses_change(self):
        first = parse_fe8cn(
            "[00]\nindexed\n[08001234]\nraw\n",
            expected_last_id=0,
        )
        second = parse_fe8cn(
            "[00]\nindexed\n[08ABCDEF]\nraw\n",
            expected_last_id=0,
        )
        self.assertEqual(first.raw_strings[0].import_id, second.raw_strings[0].import_id)
        self.assertNotEqual(first.raw_strings[0].address, second.raw_strings[0].address)


if __name__ == "__main__":
    unittest.main()
