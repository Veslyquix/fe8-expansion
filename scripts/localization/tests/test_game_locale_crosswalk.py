import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization.game_locales.crosswalk import (
    build_crosswalk_coverage_report,
    build_release_mapping,
    canonical_json_bytes,
    validate_evidence_document,
)
from scripts.localization.game_locales.mapping import validate_mapping_document


class GameLocaleCrosswalkTests(unittest.TestCase):
    MAPPING_DIR = ROOT / "texts/locales/mapping"
    EVIDENCE_PATH = MAPPING_DIR / "fe8u_structural_evidence.json"
    CANDIDATE_PATH = MAPPING_DIR / "fe8j_to_fe8u.candidates.json"
    MAP_PATH = MAPPING_DIR / "fe8u_target_map.json"
    REPORT_PATH = MAPPING_DIR / "fe8u_target_map.coverage.json"

    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(cls.EVIDENCE_PATH.read_text(encoding="utf-8"))
        cls.candidates = json.loads(cls.CANDIDATE_PATH.read_text(encoding="utf-8"))
        cls.mapping_data = json.loads(cls.MAP_PATH.read_text(encoding="utf-8"))
        cls.report = json.loads(cls.REPORT_PATH.read_text(encoding="utf-8"))
        cls.rows = {
            int(row["target_id"], 16): row for row in cls.mapping_data["rows"]
        }

    def test_release_map_has_exactly_3414_unique_resolved_targets(self):
        mapping = validate_mapping_document(self.mapping_data, target_count=3414)
        self.assertTrue(mapping.coverage_eligible)
        self.assertEqual(mapping.locale_ids, ("ja", "zh-Hans"))
        self.assertEqual(len(mapping.rows), 3414)
        self.assertEqual(len({row.target_id for row in mapping.rows}), 3414)
        self.assertEqual(mapping.rows[0].target_id, 0)
        self.assertEqual(mapping.rows[-1].target_id, 0x0D55)
        self.assertEqual(self.report["unresolved_count"], 0)

    def test_low_system_candidate_is_not_blindly_identity_mapped(self):
        row = self.rows[0x0004]
        self.assertEqual(
            row["source"],
            {"kind": "english_fallback", "reason": "not-yet-verified"},
        )
        self.assertTrue(row["verification"]["candidate_seed"]["ignored"])
        self.assertNotEqual(row["source"].get("id"), "0x0004")

    def test_duessel_knoll_tail_uses_structural_support_pair(self):
        for target_id, source_id, rank in (
            (0x0D49, 0x0D08, "C"),
            (0x0D4A, 0x0D09, "B"),
            (0x0D4B, 0x0D0A, "A"),
        ):
            row = self.rows[target_id]
            self.assertEqual(row["source"]["id"], f"0x{source_id:04X}")
            self.assertEqual(row["verification"]["subsystem"], "supports")
            self.assertEqual(
                row["verification"]["source_key"],
                f"CHARACTER_DUESSEL+CHARACTER_KNOLL.{rank}",
            )

    def test_menu_raw_overrides_use_stable_import_ids(self):
        anchors = {
            0x0645: "fe8cn.raw.import-0065",
            0x067A: "fe8cn.raw.import-0023",
            0x0843: "fe8cn.raw.import-0017",
        }
        for target_id, import_id in anchors.items():
            source = self.rows[target_id]["source"]
            self.assertEqual(source["kind"], "raw")
            self.assertEqual(source["import_id"], import_id)
            self.assertNotIn("address", source)
            self.assertEqual(
                source["regional_sources"]["zh-Hans"]["import_id"], import_id
            )

    def test_region_split_menu_target_is_explicit_fallback(self):
        self.assertEqual(
            self.rows[0x0693]["source"],
            {"kind": "english_fallback", "reason": "region-only"},
        )

    def test_candidate_rows_cannot_promote_themselves(self):
        evidence = {
            "fallback_overrides": [],
            "gaps": [],
            "kind": "fe8u-fe8j-structural-evidence",
            "records": [],
            "reference_files": [],
            "schema_version": 1,
            "target_count": 3414,
        }
        mapping = build_release_mapping(
            evidence,
            target_count=3414,
            candidate_data=self.candidates,
        )
        row = mapping["rows"][4]
        self.assertEqual(row["source"]["kind"], "english_fallback")
        self.assertTrue(row["verification"]["candidate_seed"]["ignored"])

    def test_manual_event_raw_opcode_anchors_are_recorded(self):
        for target_id, source_id in ((0x092F, "0x08EF"), (0x093E, "0x08FE")):
            row = self.rows[target_id]
            self.assertEqual(row["source"]["id"], source_id)
            self.assertEqual(
                row["verification"]["evidence_kind"],
                "manual-raw-opcode-review",
            )
            self.assertEqual(row["verification"]["confidence"], "manual")

    def test_battle_table_anchor_uses_keyed_rom_evidence(self):
        row = self.rows[0x0916]
        self.assertEqual(row["source"]["id"], "0x08D6")
        self.assertEqual(row["verification"]["subsystem"], "battle-quotes")
        self.assertEqual(
            row["verification"]["evidence_kind"], "shared-rom-table-key"
        )

    def test_split_merge_scenes_remain_reported_gaps(self):
        gap_keys = {
            gap["source_key"]: gap["reason"] for gap in self.evidence["gaps"]
        }
        self.assertEqual(
            gap_keys["EventScr_Ch14b_BeginningScene"],
            "split-merge-manual-review",
        )
        self.assertEqual(
            gap_keys["EventScr_Ch14b_EndingScene"],
            "split-merge-manual-review",
        )

    def test_evidence_model_requires_structural_fields(self):
        records = validate_evidence_document(self.evidence, target_count=3414)
        self.assertGreater(len(records), 1900)
        self.assertTrue(all(record.source_table for record in records))
        self.assertTrue(all(record.source_symbol for record in records))
        self.assertTrue(all(record.source_key for record in records))
        self.assertTrue(all(record.confidence in ("high", "manual") for record in records))

    def test_coverage_distinguishes_translation_and_fallback(self):
        report = build_crosswalk_coverage_report(
            self.mapping_data, target_count=3414
        )
        self.assertEqual(
            report["translation_coverage"]["count"]
            + report["explicit_fallback_coverage"]["count"],
            3414,
        )
        self.assertEqual(
            len(report["fallback_ids"]),
            report["explicit_fallback_coverage"]["count"],
        )
        self.assertGreater(report["source_kind_counts"]["indexed_source"], 0)
        self.assertGreater(report["source_kind_counts"]["raw_source"], 0)

    def test_structural_subsystem_coverage_is_pinned(self):
        expected_totals = {
            "battle-quotes": 59,
            "chapters": 95,
            "characters": 145,
            "classes": 142,
            "defeat-quotes": 64,
            "events": 258,
            "items": 392,
            "menus": 86,
            "supports": 249,
            "terrain": 65,
            "world-map": 32,
        }
        for subsystem, expected in expected_totals.items():
            self.assertEqual(
                self.report["by_subsystem"][subsystem]["total"],
                expected,
                subsystem,
            )

    def test_committed_outputs_match_deterministic_rebuild(self):
        rebuilt_mapping = build_release_mapping(
            self.evidence,
            target_count=3414,
            candidate_data=self.candidates,
        )
        rebuilt_report = build_crosswalk_coverage_report(
            rebuilt_mapping, target_count=3414
        )
        self.assertEqual(
            self.MAP_PATH.read_bytes(), canonical_json_bytes(rebuilt_mapping)
        )
        self.assertEqual(
            self.REPORT_PATH.read_bytes(), canonical_json_bytes(rebuilt_report)
        )

    def test_check_crosswalk_command_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "scripts.localization.game_locales", "check-crosswalk"],
            cwd=ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("decisions=3414", result.stdout)


if __name__ == "__main__":
    unittest.main()
