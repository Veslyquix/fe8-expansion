import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization import schema


class LocaleIdStabilityTests(unittest.TestCase):
    def test_locale_ids_locked_order(self):
        self.assertEqual(
            schema.LOCALE_IDS,
            ("en", "ja", "zh-Hans", "fr", "de", "es", "it", "qps-ploc"),
        )

    def test_locale_count_matches_tuple_length(self):
        self.assertEqual(schema.LOCALE_COUNT, len(schema.LOCALE_IDS))

    def test_en_is_index_zero(self):
        self.assertEqual(schema.LOCALE_INDEX["en"], 0)

    def test_pseudo_locale_is_last(self):
        self.assertEqual(schema.LOCALE_INDEX[schema.PSEUDO_LOCALE], schema.LOCALE_COUNT - 1)

    def test_default_locale_is_initially_supported(self):
        self.assertIn(schema.DEFAULT_LOCALE, schema.INITIALLY_SUPPORTED_LOCALES)

    def test_initially_supported_locales_are_exactly_en_and_pseudo(self):
        self.assertEqual(set(schema.INITIALLY_SUPPORTED_LOCALES), {"en", "qps-ploc"})

    def test_configurable_locales_match_the_production_allowlist(self):
        self.assertEqual(schema.CONFIGURABLE_LOCALES, schema.INITIALLY_SUPPORTED_LOCALES)

    def test_every_initially_supported_locale_is_a_stable_id(self):
        for locale in schema.INITIALLY_SUPPORTED_LOCALES:
            self.assertIn(locale, schema.LOCALE_IDS)


class CSyncTests(unittest.TestCase):
    """Cross-checks this module's constants against the hand-written
    include/expansion_locale.h so the two never silently drift apart."""

    HEADER_PATH = ROOT / "include" / "expansion_locale.h"

    def _header_text(self):
        return self.HEADER_PATH.read_text(encoding="utf-8")

    def test_header_locale_count_matches(self):
        text = self._header_text()
        match = re.search(r"#define EXPANSION_LOCALE_COUNT\s+(\d+)", text)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), schema.LOCALE_COUNT)

    def test_header_defines_every_locale_id_in_order(self):
        text = self._header_text()
        expected_macro = {
            "en": "EXPANSION_LOCALE_EN",
            "ja": "EXPANSION_LOCALE_JA",
            "zh-Hans": "EXPANSION_LOCALE_ZH_HANS",
            "fr": "EXPANSION_LOCALE_FR",
            "de": "EXPANSION_LOCALE_DE",
            "es": "EXPANSION_LOCALE_ES",
            "it": "EXPANSION_LOCALE_IT",
            "qps-ploc": "EXPANSION_LOCALE_QPS_PLOC",
        }
        for index, locale in enumerate(schema.LOCALE_IDS):
            macro = expected_macro[locale]
            match = re.search(rf"#define {re.escape(macro)}\s+(\d+)", text)
            self.assertIsNotNone(match, f"missing #define for {macro}")
            self.assertEqual(int(match.group(1)), index)

    def test_scratch_slot_bytes_matches_max_decoded_bytes_max(self):
        text = self._header_text()
        match = re.search(r"#define EXPANSION_LOCALE_SCRATCH_SLOT_BYTES\s+(\d+)", text)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), schema.MAX_DECODED_BYTES_MAX)

    def test_msg_id_invalid_sentinel_matches(self):
        text = self._header_text()
        match = re.search(r"#define EXPANSION_MSG_ID_INVALID\s+0x([0-9A-Fa-f]+)u", text)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1), 16), schema.MSG_ID_INVALID)


class MsgIdContractTests(unittest.TestCase):
    def test_msg_id_invalid_is_0xffff(self):
        self.assertEqual(schema.MSG_ID_INVALID, 0xFFFF)

    def test_msg_id_max_is_one_below_invalid(self):
        self.assertEqual(schema.MSG_ID_MAX, schema.MSG_ID_INVALID - 1)
        self.assertEqual(schema.MSG_ID_MAX, 0xFFFE)

    def test_msg_id_min_is_zero(self):
        self.assertEqual(schema.MSG_ID_MIN, 0)


if __name__ == "__main__":
    unittest.main()
