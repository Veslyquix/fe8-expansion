import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization.game_locales.raw_closure import (
    RawClosureError,
    build_raw_surface_closure,
    canonical_json_bytes,
)


class RawSurfaceClosureTests(unittest.TestCase):
    MAPPING_DIR = ROOT / "texts/locales/mapping"

    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(
            (ROOT / "texts/locales/zh-Hans/raw.json").read_text(encoding="utf-8")
        )
        cls.mapping = json.loads(
            (cls.MAPPING_DIR / "fe8u_target_map.json").read_text(encoding="utf-8")
        )
        cls.decisions = json.loads(
            (cls.MAPPING_DIR / "raw_surface_decisions.json").read_text(
                encoding="utf-8"
            )
        )
        cls.registry = json.loads(
            (ROOT / "texts/expansion/registry.json").read_text(encoding="utf-8")
        )
        cls.catalogs = {
            locale: json.loads(
                (ROOT / f"texts/expansion/catalog.{locale}.json").read_text(
                    encoding="utf-8"
                )
            )
            for locale in ("en", "ja", "zh-Hans")
        }
        cls.closure = build_raw_surface_closure(
            raw_data=cls.raw,
            mapping_data=cls.mapping,
            decisions_data=cls.decisions,
            registry_data=cls.registry,
            catalog_data=cls.catalogs,
            repo_root=ROOT,
        )

    def test_all_143_records_have_one_honest_decision(self):
        summary = self.closure["summary"]
        self.assertEqual(summary["total_count"], 143)
        self.assertEqual(summary["baseline_game_message_count"], 114)
        self.assertEqual(summary["deferred_decision_count"], 29)
        self.assertEqual(summary["game_message_count"], 134)
        self.assertEqual(summary["expansion_message_count"], 2)
        self.assertEqual(summary["non_user_facing_exclusion_count"], 3)
        self.assertEqual(summary["diagnostic_exclusion_count"], 1)
        self.assertEqual(summary["english_fallback_count"], 3)
        self.assertEqual(summary["unresolved_count"], 0)
        self.assertEqual(summary["user_facing_deferred_localized_count"], 22)
        self.assertEqual(
            len({row["import_id"] for row in self.closure["rows"]}), 143
        )

    def test_committed_manifest_matches_deterministic_rebuild(self):
        path = self.MAPPING_DIR / "raw_surface_closure.json"
        self.assertEqual(path.read_bytes(), canonical_json_bytes(self.closure))

    def test_each_deferred_game_message_has_canonical_japanese_payload(self):
        rows = {
            row["target_id"]: row
            for row in self.mapping["rows"]
            if row["source"]["kind"] == "raw"
        }
        for decision in self.decisions["decisions"]:
            if decision["classification"] != "game_message":
                continue
            source = rows[decision["target_id"]]["source"]
            self.assertIn(
                decision["import_id"],
                [source["import_id"], *source.get("alternate_import_ids", [])],
            )
            self.assertEqual(source["regional_sources"]["ja"]["kind"], "literal")
            self.assertTrue(source["regional_sources"]["ja"]["text"])

    def test_expansion_adapters_use_exact_imported_chinese_payloads(self):
        raw_text = {
            row["import_id"]: row["text"] for row in self.raw["records"]
        }
        zh = self.catalogs["zh-Hans"]["strings"]
        for decision in self.decisions["decisions"]:
            if decision["classification"] != "expansion_message":
                continue
            self.assertEqual(
                zh[decision["expansion_key"]],
                raw_text[decision["import_id"]],
            )

        source = (ROOT / "src/menu_def.c").read_text(encoding="utf-8")
        self.assertIn("LocalizedRawUnitActionMenuDraw", source)
        self.assertIn(
            "Text_DrawString(&item->text, ExpansionLocale_ResolveCurrent(msgId));",
            source,
        )
        self.assertNotIn(
            "Text_DrawStringASCII(&item->text, ExpansionLocale_ResolveCurrent(msgId));",
            source,
        )
        self.assertIn("#define LOCALIZED_RAW_UNIT_ACTION_DRAW 0", source)

    def test_class_choice_initializers_are_proven_non_rendered(self):
        source = (ROOT / "src/classchg-menuselect.c").read_text(encoding="utf-8")
        self.assertEqual(source.count("ClassChgMenuItem_OnTextDraw,"), 3)
        self.assertIn(
            "GetStringFromIndex(GetClassData(gparent->jid[pmitem->itemNumber])->nameTextId)",
            source,
        )

    def test_build_timestamp_is_diagnostic_identity_not_translation(self):
        decision = next(
            row
            for row in self.decisions["decisions"]
            if row["import_id"] == "fe8cn.raw.import-0142"
        )
        self.assertEqual(decision["classification"], "diagnostic_exclusion")
        self.assertFalse(decision["user_facing"])
        self.assertIn("diagnostic", decision["rationale"])

    def test_disappearing_call_site_anchor_fails_the_closure(self):
        broken = deepcopy(self.decisions)
        broken["decisions"][0]["call_sites"][0]["anchors"] = [
            "__missing_raw_surface_anchor__"
        ]
        with self.assertRaisesRegex(RawClosureError, "no surviving anchor"):
            build_raw_surface_closure(
                raw_data=self.raw,
                mapping_data=self.mapping,
                decisions_data=broken,
                registry_data=self.registry,
                catalog_data=self.catalogs,
                repo_root=ROOT,
            )

    def test_tampered_literal_context_fails_the_closure(self):
        broken = deepcopy(self.mapping)
        row = next(
            row
            for row in broken["rows"]
            if row.get("source", {})
            .get("regional_sources", {})
            .get("ja", {})
            .get("kind")
            == "literal"
        )
        row["source"]["regional_sources"]["ja"]["provenance"][
            "context_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(
            RawClosureError,
            "literal evidence failed.*context_sha256",
        ):
            build_raw_surface_closure(
                raw_data=self.raw,
                mapping_data=broken,
                decisions_data=self.decisions,
                registry_data=self.registry,
                catalog_data=self.catalogs,
                repo_root=ROOT,
            )

    def test_unproven_goal_literals_are_explicit_fallbacks(self):
        decisions = {
            row["import_id"]: row for row in self.decisions["decisions"]
        }
        for import_id in (
            "fe8cn.raw.import-0139",
            "fe8cn.raw.import-0140",
            "fe8cn.raw.import-0141",
        ):
            decision = decisions[import_id]
            self.assertEqual(decision["classification"], "english_fallback")
            self.assertEqual(
                decision["fallback_reason"],
                "japanese-literal-source-unverified",
            )


if __name__ == "__main__":
    unittest.main()
