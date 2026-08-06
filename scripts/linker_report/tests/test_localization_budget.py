"""Focused tests for localization_budget's optional upper-ROM bank report."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import localization_budget as lb  # noqa: E402


def base_map_report(rom_capacity=0x02000000):
    return {
        "regions": [
            {
                "name": "rom",
                "origin": 0x08000000,
                "capacity_bytes": rom_capacity,
                "occupied_bytes": 0x00100000,
                "free_bytes": rom_capacity - 0x00100000,
                "overflow": False,
            }
        ],
        "sections": [],
        "pinned_assignments": [],
        "overflow": False,
    }


class LocaleBankBudgetTests(unittest.TestCase):
    def build_report(self, map_report):
        with mock.patch.object(lb, "_nm_sizes", return_value={}):
            return lb.build_report(map_report, "fixture.elf", None)

    def test_old_reports_without_locale_bank_remain_unchanged(self):
        report = self.build_report(base_map_report())
        self.assertNotIn("locale_bank", report)

    def test_empty_16m_locale_bank_has_zero_capacity_and_headroom(self):
        map_report = base_map_report(0x01000000)
        map_report["pinned_assignments"] = [
            {"name": "__locale_bank_start", "address": 0x09000000},
            {"name": "__locale_bank_end", "address": 0x09000000},
        ]
        report = self.build_report(map_report)
        self.assertEqual(
            report["locale_bank"],
            {
                "start_address": 0x09000000,
                "end_address": 0x09000000,
                "limit_address": 0x09000000,
                "capacity_bytes": 0,
                "occupied_bytes": 0,
                "headroom_bytes": 0,
                "overflow": False,
                "section_present": False,
            },
        )

    def test_linker_symbols_report_upper_bank_occupancy_and_headroom(self):
        map_report = base_map_report()
        map_report["pinned_assignments"] = [
            {"name": "__locale_bank_start", "address": 0x09000000},
            {"name": "__locale_bank_end", "address": 0x09001234},
        ]
        report = self.build_report(map_report)
        self.assertEqual(
            report["locale_bank"],
            {
                "start_address": 0x09000000,
                "end_address": 0x09001234,
                "limit_address": 0x0A000000,
                "capacity_bytes": 0x01000000,
                "occupied_bytes": 0x1234,
                "headroom_bytes": 0x01000000 - 0x1234,
                "overflow": False,
                "section_present": False,
            },
        )

    def test_locale_section_is_a_backward_compatible_symbol_fallback(self):
        map_report = base_map_report()
        map_report["sections"] = [
            {
                "name": ".locale_data",
                "address": 0x09000000,
                "size_bytes": 0x200,
            }
        ]
        report = self.build_report(map_report)
        self.assertEqual(report["locale_bank"]["occupied_bytes"], 0x200)
        self.assertEqual(report["locale_bank"]["headroom_bytes"], 0x00FFFE00)
        self.assertTrue(report["locale_bank"]["section_present"])

    def test_iwram_static_headroom_fields_are_preserved(self):
        map_report = base_map_report()
        map_report["regions"].append({
            "name": "iwram",
            "origin": 0x03000000,
            "capacity_bytes": 0x8000,
            "occupied_bytes": 0x6CA8,
            "physical_free_bytes": 0x1358,
            "free_bytes": 0x1158,
            "static_usable_capacity_bytes": 0x7E00,
            "reserved_stack_bytes": 0x200,
            "usable_static_headroom_bytes": 0x1158,
            "minimum_user_stack_margin_bytes": 0x1000,
            "static_growth_headroom_bytes": 0x158,
            "static_overflow": False,
            "stack_margin_violation": False,
            "overflow": False,
        })

        iwram = self.build_report(map_report)["regions_headroom"]["iwram"]
        self.assertEqual(iwram["free_bytes"], 0x1158)
        self.assertEqual(iwram["physical_free_bytes"], 0x1358)
        self.assertEqual(iwram["reserved_stack_bytes"], 0x200)
        self.assertEqual(iwram["usable_static_headroom_bytes"], 0x1158)
        self.assertEqual(iwram["minimum_user_stack_margin_bytes"], 0x1000)
        self.assertEqual(iwram["static_growth_headroom_bytes"], 0x158)


def source_budget(locales):
    return {
        "active_message_count": 32,
        "tombstone_count": 1,
        "locales_generated": list(locales),
        "catalog_string_bytes": {"total": 0},
        "catalog_index_bytes": 0,
        "scratch_budget_bytes": 96,
        "scratch_slot_bytes_used_max": 1,
        "scratch_headroom_bytes": 95,
        "codepoints": {"glyphs_used_count": 0},
    }


INDEX_SYMBOLS = {
    "gExpansionLocaleMsgIds": 64,
    "gExpansionLocaleMsgCount": 2,
    "gExpansionLocaleTombstoneCount": 2,
}
DESCRIPTOR_SYMBOLS = {
    "gExpansionLocaleCatalogs": 96,
    "gExpansionLocalePopulatedCount": 1,
}


class CatalogSymbolBudgetTests(unittest.TestCase):
    def build_report(self, sizes, locales):
        with mock.patch.object(lb, "_nm_sizes", return_value=sizes):
            return lb.build_report(
                base_map_report(), "fixture.elf", source_budget(locales)
            )

    def test_four_locale_arrays_and_descriptor_metadata_counted_once(self):
        sizes = {
            **INDEX_SYMBOLS,
            **DESCRIPTOR_SYMBOLS,
            "gExpansionCatalog_en": 128,
            "gExpansionCatalog_ja": 128,
            "gExpansionCatalog_zh_Hans": 128,
            "gExpansionCatalog_qps_ploc": 128,
        }
        report = self.build_report(
            sizes, ("en", "ja", "zh-Hans", "qps-ploc", "ja")
        )

        self.assertEqual(report["rom_catalog_index"]["total_bytes"], 68)
        self.assertEqual(report["rom_catalog_descriptors"]["total_bytes"], 97)
        self.assertEqual(
            report["rom_catalog_strings"]["symbols"],
            {
                "gExpansionCatalog_en": 128,
                "gExpansionCatalog_ja": 128,
                "gExpansionCatalog_zh_Hans": 128,
                "gExpansionCatalog_qps_ploc": 128,
            },
        )
        self.assertEqual(report["rom_catalog_strings"]["total_bytes"], 512)
        self.assertEqual(report["rom_catalog_strings"]["missing"], [])
        self.assertEqual(report["rom_catalog_strings"]["unexpected"], [])
        self.assertEqual(lb._catalog_symbol_errors(report), [])

    def test_missing_required_generic_symbols_are_actionable(self):
        sizes = {
            **INDEX_SYMBOLS,
            "gExpansionCatalog_en": 128,
            "gExpansionCatalog_ja": 128,
            "gExpansionCatalog_zh_Hans": 128,
            "gExpansionCatalog_qps_ploc": 128,
        }
        report = self.build_report(
            sizes, ("en", "ja", "zh-Hans", "qps-ploc")
        )

        self.assertEqual(
            report["rom_catalog_descriptors"]["missing"],
            [
                "gExpansionLocaleCatalogs",
                "gExpansionLocalePopulatedCount",
            ],
        )
        self.assertEqual(
            lb._catalog_symbol_errors(report),
            [
                "rom_catalog_descriptors missing required symbols: "
                "gExpansionLocaleCatalogs, gExpansionLocalePopulatedCount"
            ],
        )

    def test_old_two_locale_fixture_fails_on_missing_descriptor_metadata(self):
        sizes = {
            **INDEX_SYMBOLS,
            "gExpansionCatalog_en": 112,
            "gExpansionCatalog_qps_ploc": 112,
        }
        report = self.build_report(sizes, ("en", "qps-ploc"))

        self.assertEqual(report["rom_catalog_strings"]["total_bytes"], 224)
        self.assertEqual(report["rom_catalog_strings"]["missing"], [])
        errors = lb._catalog_symbol_errors(report)
        self.assertEqual(len(errors), 1)
        self.assertIn("gExpansionLocaleCatalogs", errors[0])
        self.assertIn("gExpansionLocalePopulatedCount", errors[0])

    def test_catalog_prefix_is_limited_by_generated_locale_allowlist(self):
        sizes = {
            **INDEX_SYMBOLS,
            **DESCRIPTOR_SYMBOLS,
            "gExpansionCatalog_en": 128,
            "gExpansionCatalog_debug": 4096,
        }
        report = self.build_report(sizes, ("en",))

        self.assertEqual(report["rom_catalog_strings"]["total_bytes"], 128)
        self.assertEqual(
            report["rom_catalog_strings"]["unexpected"],
            ["gExpansionCatalog_debug"],
        )
        self.assertIn(
            "outside the generated-locale allowlist",
            lb._catalog_symbol_errors(report)[0],
        )

    def test_explicit_missing_source_budget_fails_before_report_generation(self):
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as raised:
                lb.main(
                    [
                        "--map",
                        "unused.map",
                        "--elf",
                        "unused.elf",
                        "--localization-budget",
                        "missing-budget.json",
                        "--output",
                        "unused-output.json",
                    ]
                )

        self.assertEqual(raised.exception.code, 2)
        self.assertIn(
            "--localization-budget does not exist: missing-budget.json",
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
