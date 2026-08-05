"""Focused tests for localization_budget's optional upper-ROM bank report."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import localization_budget as lb  # noqa: E402


def base_map_report():
    return {
        "regions": [
            {
                "name": "rom",
                "capacity_bytes": 0x02000000,
                "occupied_bytes": 0x00100000,
                "free_bytes": 0x01F00000,
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


if __name__ == "__main__":
    unittest.main()
