import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization.game_locales.coverage import (
    build_coverage_report,
    load_fe8u_target_ids,
)
from scripts.localization.game_locales.mapping import (
    MappingError,
    validate_mapping_document,
)


def _verified_source_rows():
    verification = {
        "confidence": "high",
        "method": "human-semantic-review",
        "evidence": "fixture evidence",
        "evidence_kind": "fixture",
        "source_table": "fixture table",
        "source_symbol": "gFixture",
        "source_key": "fixture.key",
        "subsystem": "fixture",
        "rationale": "fixture rationale",
    }
    return [
        {
            "target_id": "0x0000",
            "state": "verified",
            "source": {"kind": "indexed", "layout": "FE8J", "id": "0x0000"},
            "verification": verification,
        },
        {
            "target_id": "0x0001",
            "state": "verified",
            "source": {
                "kind": "raw",
                "import_id": "fe8cn.raw.import-0000",
            },
            "verification": verification,
        },
        {
            "target_id": "0x0002",
            "state": "verified",
            "source": {"kind": "authored", "translation_key": "fixture.authored"},
            "verification": verification,
        },
        {
            "target_id": "0x0003",
            "state": "verified",
            "source": {"kind": "english_fallback", "reason": "intentional fixture"},
            "verification": verification,
        },
    ]


class GameLocaleMappingTests(unittest.TestCase):
    CANDIDATE_PATH = (
        ROOT / "texts/locales/mapping/fe8j_to_fe8u.candidates.json"
    )

    def _candidate_data(self):
        return json.loads(self.CANDIDATE_PATH.read_text(encoding="utf-8"))

    def test_fe8u_target_header_has_3414_targets(self):
        target_ids = load_fe8u_target_ids(ROOT / "include/constants/msg.h")
        self.assertEqual(len(target_ids), 3414)
        self.assertEqual(target_ids[-1], 0x0D55)

    def test_seed_is_explicitly_non_authoritative_and_unverified(self):
        data = self._candidate_data()
        mapping = validate_mapping_document(data, target_count=3414)
        self.assertEqual(mapping.authority, "candidate")
        self.assertFalse(mapping.authoritative)
        self.assertFalse(mapping.coverage_eligible)
        self.assertEqual(len(mapping.rows), 2770)
        self.assertTrue(all(row.state == "candidate" for row in mapping.rows))
        self.assertTrue(all(row.verification is None for row in mapping.rows))

    def test_candidate_rows_cannot_claim_authoritative_status(self):
        data = self._candidate_data()
        data["authoritative"] = True
        with self.assertRaisesRegex(MappingError, "authoritative must be false"):
            validate_mapping_document(data, target_count=3414)

    def test_candidate_rows_cannot_claim_verified_state(self):
        data = self._candidate_data()
        data["rows"][0]["state"] = "verified"
        with self.assertRaisesRegex(MappingError, "state must be 'candidate'"):
            validate_mapping_document(data, target_count=3414)

    def test_candidate_source_provenance_hash_is_validated(self):
        data = self._candidate_data()
        data["provenance"]["sha256"] = "not-a-hash"
        with self.assertRaisesRegex(MappingError, "64 lowercase hex digits"):
            validate_mapping_document(data, target_count=3414)

    def test_raw_mapping_identity_is_stable_and_address_free(self):
        data = {
            "schema_version": 2,
            "kind": "fe8u-locale-mapping",
            "locale_ids": ["zh-Hans"],
            "authority": "verified",
            "authoritative": True,
            "note": "raw import fixture",
            "rows": [_verified_source_rows()[1]],
        }
        mapping = validate_mapping_document(data, target_count=2)
        self.assertEqual(
            mapping.rows[0].source["import_id"],
            "fe8cn.raw.import-0000",
        )
        data["rows"][0]["source"]["address"] = "0x08001234"
        with self.assertRaisesRegex(MappingError, "must not use address-derived"):
            validate_mapping_document(data, target_count=2)

    def test_raw_mapping_accepts_authorized_japanese_literal_provenance(self):
        data = {
            "schema_version": 2,
            "kind": "fe8u-locale-mapping",
            "locale_ids": ["ja", "zh-Hans"],
            "authority": "verified",
            "authoritative": True,
            "note": "raw literal fixture",
            "rows": [_verified_source_rows()[1]],
        }
        data["rows"][0]["source"]["regional_sources"] = {
            "ja": {
                "kind": "literal",
                "text": "決定",
                "provenance": {
                    "source_path": "src/classchg-menuconfirm.c",
                    "source_symbol": "MenuItem_PromoSubConfirm[0].name",
                },
            },
            "zh-Hans": {
                "kind": "import",
                "import_id": "fe8cn.raw.import-0000",
            },
        }
        mapping = validate_mapping_document(data, target_count=2)
        self.assertEqual(
            mapping.rows[0].source["regional_sources"]["ja"]["text"],
            "決定",
        )

        del data["rows"][0]["source"]["regional_sources"]["ja"]["provenance"]
        with self.assertRaisesRegex(MappingError, "ja.provenance"):
            validate_mapping_document(data, target_count=2)

    def test_candidate_coverage_is_honestly_unresolved(self):
        mapping = validate_mapping_document(self._candidate_data(), target_count=3414)
        report = build_coverage_report(mapping, range(3414), locale="ja")
        self.assertEqual(report["candidate_rows_ignored"], 2770)
        self.assertEqual(report["summary"]["unresolved"], 3414)
        self.assertEqual(report["summary"]["indexed_source"], 0)
        self.assertTrue(report["rows"][4]["candidate_present"])
        self.assertEqual(report["rows"][4]["classification"], "unresolved")

    def test_verified_mapping_classifies_all_supported_source_kinds(self):
        data = {
            "schema_version": 2,
            "kind": "fe8u-locale-mapping",
            "locale_ids": ["ja"],
            "authority": "verified",
            "authoritative": True,
            "note": "verified fixture",
            "rows": _verified_source_rows(),
        }
        mapping = validate_mapping_document(data, target_count=5)
        report = build_coverage_report(mapping, range(5), locale="ja")
        self.assertEqual(
            [row["classification"] for row in report["rows"]],
            [
                "indexed_source",
                "raw_source",
                "authored_translation",
                "explicit_english_fallback",
                "unresolved",
            ],
        )
        self.assertEqual(report["candidate_rows_ignored"], 0)

    def test_verified_mapping_requires_evidence(self):
        data = {
            "schema_version": 2,
            "kind": "fe8u-locale-mapping",
            "locale_ids": ["ja"],
            "authority": "verified",
            "authoritative": True,
            "note": "verified fixture",
            "rows": _verified_source_rows(),
        }
        broken = deepcopy(data)
        del broken["rows"][0]["verification"]["evidence"]
        with self.assertRaisesRegex(MappingError, "verification.evidence"):
            validate_mapping_document(broken, target_count=5)


if __name__ == "__main__":
    unittest.main()
