import shutil
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from scripts.localization.game_catalog.build import build_game_catalog


class FixtureBuildTests(unittest.TestCase):
    def setUp(self):
        self.fixture_dir = Path(__file__).resolve().parent / "fixtures"
        if self.fixture_dir.exists():
            shutil.rmtree(self.fixture_dir)
        self.fixture_dir.mkdir()

        (self.fixture_dir / "textdefs.txt").write_text(
            "[X] = 0\n"
            "[LF] = 1\n"
            "[DashedLine] = 0x7F\n"
            "[TAB] = 0x81, 0x40\n"
            "[LQuote] = 0x93\n"
            "[RQuote] = 0x94\n"
            "[AccentedE] = 0xE9\n",
            encoding="utf-8",
        )
        (self.fixture_dir / "texts.txt").write_text(
            "#0x0\n"
            "English zero[X]\n"
            "## MSG_FIXTURE_ONE\n"
            "[LQuote]English[DashedLine]one[RQuote][X]\n"
            "## MSG_FIXTURE_TWO\n"
            "English[TAB]two[AccentedE][X]\n",
            encoding="utf-8",
        )
        (self.fixture_dir / "ja_indexed.txt").write_text(
            "\n".join(
                (
                    "# fixture ja indexed",
                    "#0x0000",
                    "日[CTRL:0080][CTRL:0020]",
                    "#0x0001",
                    "著者",
                    "#0x0002",
                    "英語fallback対象",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        (self.fixture_dir / "zh_indexed.txt").write_text(
            "\n".join(
                (
                    "# fixture zh indexed",
                    "#0x0000",
                    "中[CTRL:0080][CTRL:0020]",
                    "#0x0001",
                    "作者",
                    "#0x0002",
                    "英语fallback目标",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        (self.fixture_dir / "zh_raw.json").write_text(
            "{\n"
            '  "schema_version": 2,\n'
            '  "locale_id": "zh-Hans",\n'
            '  "source_layout": "FE8CN-raw-address",\n'
            '  "record_count": 1,\n'
            '  "unique_import_count": 1,\n'
            '  "unique_address_count": 1,\n'
            '  "records": [\n'
            '    {\n'
            '      "import_id": "fe8cn.raw.import-0000",\n'
            '      "text": "原始",\n'
            '      "provenance": {"address": "0x00000000", "occurrences": []}\n'
            '    }\n'
            '  ]\n'
            '}\n',
            encoding="utf-8",
        )
        (self.fixture_dir / "mapping.json").write_text(
            "{\n"
            '  "schema_version": 2,\n'
            '  "kind": "fe8u-locale-mapping",\n'
            '  "authority": "verified",\n'
            '  "authoritative": true,\n'
            '  "locale_ids": ["ja", "zh-Hans"],\n'
            '  "note": "fixture",\n'
            '  "rows": [\n'
            '    {\n'
            '      "target_id": "0x0000",\n'
            '      "state": "verified",\n'
            '      "source": {"kind": "indexed", "layout": "FE8J", "id": "0x0000"},\n'
            '      "verification": {\n'
            '        "method": "fixture",\n'
            '        "evidence": "fixture",\n'
            '        "evidence_kind": "fixture",\n'
            '        "source_table": "fixture",\n'
            '        "source_symbol": "fixture",\n'
            '        "source_key": "fixture",\n'
            '        "subsystem": "fixture",\n'
            '        "rationale": "fixture",\n'
            '        "confidence": "high"\n'
            '      }\n'
            '    },\n'
            '    {\n'
            '      "target_id": "0x0001",\n'
            '      "state": "verified",\n'
            '      "source": {\n'
            '        "kind": "raw",\n'
            '        "import_id": "fe8cn.raw.import-0000",\n'
            '        "regional_sources": {\n'
            '          "ja": {"kind": "symbol", "symbol": "fixture"},\n'
            '          "zh-Hans": {"kind": "import", "import_id": "fe8cn.raw.import-0000"}\n'
            '        }\n'
            '      },\n'
            '      "verification": {\n'
            '        "method": "fixture",\n'
            '        "evidence": "fixture",\n'
            '        "evidence_kind": "fixture",\n'
            '        "source_table": "fixture",\n'
            '        "source_symbol": "fixture",\n'
            '        "source_key": "fixture",\n'
            '        "subsystem": "fixture",\n'
            '        "rationale": "fixture",\n'
            '        "confidence": "high"\n'
            '      }\n'
            '    },\n'
            '    {\n'
            '      "target_id": "0x0002",\n'
            '      "state": "verified",\n'
            '      "source": {"kind": "english_fallback", "reason": "not-yet-verified"},\n'
            '      "verification": {\n'
            '        "method": "fixture",\n'
            '        "evidence": "fixture",\n'
            '        "evidence_kind": "fixture",\n'
            '        "source_table": "fixture",\n'
            '        "source_symbol": "fixture",\n'
            '        "source_key": "fixture",\n'
            '        "subsystem": "fixture",\n'
            '        "rationale": "fixture",\n'
            '        "confidence": "explicit"\n'
            '      }\n'
            '    }\n'
            '  ]\n'
            '}\n',
            encoding="utf-8",
        )
        (self.fixture_dir / "msg.h").write_text(
            "#ifndef MSG_H\n#define MSG_H\n#define MSG_COUNT 0x0003\n#endif\n",
            encoding="utf-8",
        )

    def tearDown(self):
        if self.fixture_dir.exists():
            shutil.rmtree(self.fixture_dir)

    def test_fixture_build_preserves_fallback_absence_and_raw_locale_gap(self):
        build = build_game_catalog(
            english_texts_path=self.fixture_dir / "texts.txt",
            english_definitions_path=self.fixture_dir / "textdefs.txt",
            ja_indexed_path=self.fixture_dir / "ja_indexed.txt",
            zh_indexed_path=self.fixture_dir / "zh_indexed.txt",
            zh_raw_path=self.fixture_dir / "zh_raw.json",
            mapping_path=self.fixture_dir / "mapping.json",
            target_header_path=self.fixture_dir / "msg.h",
        )
        ja = build.locale_bundle("ja")
        zh = build.locale_bundle("zh-Hans")

        self.assertEqual(build.english.catalog.decode_entry(0), b"English zero\x00")
        self.assertEqual(
            build.english.catalog.decode_entry(1), b'"English-one"\x00'
        )
        self.assertEqual(
            build.english.catalog.decode_entry(2),
            b"English" + "\u3000".encode("utf-8") + b"twoe\x00",
        )
        self.assertEqual(ja.catalog.decode_entry(0), "日".encode("utf-8") + b"\x80\x20\x00")
        self.assertIsNone(ja.catalog.decode_entry(1))
        self.assertEqual(zh.catalog.decode_entry(1), "原始".encode("utf-8") + b"\x00")
        self.assertIsNone(zh.catalog.decode_entry(2))

        report = build.report
        self.assertEqual(report["mapping_source_counts"]["indexed"], 1)
        self.assertEqual(report["mapping_source_counts"]["raw"], 1)
        self.assertEqual(report["mapping_source_counts"]["english_fallback"], 1)
        self.assertEqual(report["locales"]["ja"]["provider_unavailable_count"], 1)
        self.assertEqual(report["locales"]["zh-Hans"]["provider_counts"]["raw"], 1)
        self.assertEqual(report["locales"]["zh-Hans"]["explicit_fallback_count"], 1)

    def test_fixture_build_emits_authorized_japanese_raw_literal(self):
        mapping = json.loads(
            (self.fixture_dir / "mapping.json").read_text(encoding="utf-8")
        )
        mapping["rows"][1]["source"]["regional_sources"]["ja"] = {
            "kind": "literal",
            "text": "決定",
            "provenance": {
                "source_path": "src/classchg-menuconfirm.c",
                "source_symbol": "MenuItem_PromoSubConfirm[0].name",
            },
        }
        (self.fixture_dir / "mapping.json").write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        build = build_game_catalog(
            english_texts_path=self.fixture_dir / "texts.txt",
            english_definitions_path=self.fixture_dir / "textdefs.txt",
            ja_indexed_path=self.fixture_dir / "ja_indexed.txt",
            zh_indexed_path=self.fixture_dir / "zh_indexed.txt",
            zh_raw_path=self.fixture_dir / "zh_raw.json",
            mapping_path=self.fixture_dir / "mapping.json",
            target_header_path=self.fixture_dir / "msg.h",
        )
        ja = build.locale_bundle("ja")

        self.assertEqual(ja.catalog.decode_entry(1), "決定".encode("utf-8") + b"\x00")
        self.assertEqual(build.report["locales"]["ja"]["provider_counts"]["raw"], 1)
        self.assertEqual(build.report["locales"]["ja"]["provider_unavailable_count"], 0)


if __name__ == "__main__":
    unittest.main()
