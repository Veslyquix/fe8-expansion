import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from scripts.localization.game_catalog.build import generate


class RealGenerateTests(unittest.TestCase):
    def _tmpdir(self):
        return tempfile.TemporaryDirectory(dir=TEST_DIR)

    def test_two_generate_runs_are_byte_identical_and_counts_match_committed_map(self):
        with self._tmpdir() as tmp_a, self._tmpdir() as tmp_b:
            out_a = Path(tmp_a)
            out_b = Path(tmp_b)
            written_a = generate(output_dir=out_a)
            written_b = generate(output_dir=out_b)
            for name in written_a:
                self.assertEqual(
                    written_a[name].read_bytes(),
                    written_b[name].read_bytes(),
                    name,
                )

            report = json.loads(written_a["report_json"].read_text(encoding="utf-8"))
            budget = json.loads(written_a["budget_json"].read_text(encoding="utf-8"))
            self.assertEqual(report["mapping_source_counts"]["indexed"], 1472)
            self.assertEqual(report["mapping_source_counts"]["raw"], 114)
            self.assertEqual(report["mapping_source_counts"]["authored"], 0)
            self.assertEqual(report["mapping_source_counts"]["english_fallback"], 1828)
            self.assertEqual(report["mapping_source_counts"]["unresolved"], 0)
            self.assertEqual(report["locales"]["ja"]["present_count"], 1472)
            self.assertEqual(report["locales"]["ja"]["provider_unavailable_count"], 114)
            self.assertEqual(report["locales"]["zh-Hans"]["present_count"], 1586)
            self.assertEqual(report["locales"]["zh-Hans"]["explicit_fallback_count"], 1828)
            self.assertTrue(report["locales"]["ja"]["storage"]["target_fits"])
            self.assertTrue(report["locales"]["zh-Hans"]["storage"]["target_fits"])
            self.assertEqual(report["locales"]["ja"]["storage"]["required_bytes"], 5328)
            self.assertEqual(report["locales"]["zh-Hans"]["storage"]["required_bytes"], 4260)
            self.assertEqual(
                report["locales"]["ja"]["hashes"]["source_framed_sha256"],
                report["locales"]["ja"]["hashes"]["round_trip_framed_sha256"],
            )
            self.assertEqual(
                report["locales"]["zh-Hans"]["hashes"]["source_framed_sha256"],
                report["locales"]["zh-Hans"]["hashes"]["round_trip_framed_sha256"],
            )
            self.assertIn("nodes", report["locales"]["ja"]["huffman"])
            self.assertIn("compressed_blob_hex", report["locales"]["zh-Hans"]["huffman"])
            self.assertIn("codec_budget", budget["locales"]["ja"])
            self.assertIn("codec_budget", budget["locales"]["zh-Hans"])

    def test_generated_c_uses_locale_data_section_and_has_target_entries(self):
        with self._tmpdir() as tmp:
            written = generate(output_dir=Path(tmp))
            source = written["source"].read_text(encoding="utf-8")
            header = written["header"].read_text(encoding="utf-8")
            config_header = written["config_header"].read_text(encoding="utf-8")
            self.assertIn('SECTION(".locale_data")', header)
            self.assertIn("GAME_LOCALIZATION_TARGET_COUNT 3414u", header)
            self.assertIn("FE8_GAME_LOCALIZATION_DATA_PRESENT 1", config_header)
            self.assertIn(
                "FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES 5328u",
                config_header,
            )
            self.assertIn("gGameLocalizationJaEntries[]", source)
            self.assertIn("gGameLocalizationZhHansEntries[]", source)
            self.assertIn("gGameLocalizationCatalogs[GAME_LOCALIZATION_LOCALE_COUNT]", source)
            self.assertIn("gGameLocalizationJaCompressedBlob +", source)

    def test_profile_specific_outputs_exclude_disabled_payloads_and_size_capacity(self):
        with (
            self._tmpdir() as ja_tmp,
            self._tmpdir() as ja_repeat_tmp,
            self._tmpdir() as zh_tmp,
            self._tmpdir() as both_tmp,
        ):
            ja = generate(output_dir=Path(ja_tmp), enabled_locales=("ja",))
            ja_repeat = generate(
                output_dir=Path(ja_repeat_tmp), enabled_locales=("ja",)
            )
            zh = generate(output_dir=Path(zh_tmp), enabled_locales=("zh-Hans",))
            both = generate(
                output_dir=Path(both_tmp), enabled_locales=("ja", "zh-Hans")
            )

            for name in ja:
                self.assertEqual(ja[name].read_bytes(), ja_repeat[name].read_bytes(), name)

            ja_source = ja["source"].read_text(encoding="utf-8")
            zh_source = zh["source"].read_text(encoding="utf-8")
            both_source = both["source"].read_text(encoding="utf-8")
            ja_header = ja["header"].read_text(encoding="utf-8")
            zh_header = zh["header"].read_text(encoding="utf-8")
            ja_config = ja["config_header"].read_text(encoding="utf-8")
            zh_config = zh["config_header"].read_text(encoding="utf-8")

            self.assertIn("gGameLocalizationJaCompressedBlob[]", ja_source)
            self.assertNotIn("gGameLocalizationZhHansCompressedBlob[]", ja_source)
            self.assertIn("gGameLocalizationZhHansCompressedBlob[]", zh_source)
            self.assertNotIn("gGameLocalizationJaCompressedBlob[]", zh_source)
            self.assertIn("gGameLocalizationJaCompressedBlob[]", both_source)
            self.assertIn("gGameLocalizationZhHansCompressedBlob[]", both_source)
            self.assertEqual(ja_source.count(
                "(const struct GameLocalizationLocaleCatalog *)0,"
            ), 1)
            self.assertEqual(zh_source.count(
                "(const struct GameLocalizationLocaleCatalog *)0,"
            ), 1)
            self.assertNotIn(
                "(const struct GameLocalizationLocaleCatalog *)0,", both_source
            )

            self.assertIn("GAME_LOCALIZATION_JA_ENABLED 1u", ja_header)
            self.assertIn("GAME_LOCALIZATION_ZH_HANS_ENABLED 0u", ja_header)
            self.assertNotIn("extern const u32 gGameLocalizationZhHansNodes[];", ja_header)
            self.assertIn("GAME_LOCALIZATION_JA_ENABLED 0u", zh_header)
            self.assertIn("GAME_LOCALIZATION_ZH_HANS_ENABLED 1u", zh_header)
            self.assertNotIn("extern const u32 gGameLocalizationJaNodes[];", zh_header)
            self.assertIn(
                "FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES 5328u", ja_config
            )
            self.assertIn(
                "FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES 4260u", zh_config
            )

            ja_report = json.loads(ja["report_json"].read_text(encoding="utf-8"))
            zh_report = json.loads(zh["report_json"].read_text(encoding="utf-8"))
            both_report = json.loads(
                both["report_json"].read_text(encoding="utf-8")
            )
            ja_budget = json.loads(ja["budget_json"].read_text(encoding="utf-8"))
            zh_budget = json.loads(zh["budget_json"].read_text(encoding="utf-8"))
            both_budget = json.loads(
                both["budget_json"].read_text(encoding="utf-8")
            )

            self.assertEqual(ja_report["enabled_locales"], ["ja"])
            self.assertEqual(set(ja_report["locales"]), {"ja"})
            self.assertEqual(zh_report["enabled_locales"], ["zh-Hans"])
            self.assertEqual(set(zh_report["locales"]), {"zh-Hans"})
            self.assertEqual(
                both_report["enabled_locales"], ["ja", "zh-Hans"]
            )
            self.assertEqual(ja_budget["locales"]["ja"]["max_decoded_bytes"], 5328)
            self.assertEqual(
                zh_budget["locales"]["zh-Hans"]["max_decoded_bytes"], 4260
            )
            self.assertLess(
                ja_budget["totals"]["estimated_total_c_bytes"],
                both_budget["totals"]["estimated_total_c_bytes"],
            )
            self.assertLess(
                zh_budget["totals"]["estimated_total_c_bytes"],
                both_budget["totals"]["estimated_total_c_bytes"],
            )


if __name__ == "__main__":
    unittest.main()
