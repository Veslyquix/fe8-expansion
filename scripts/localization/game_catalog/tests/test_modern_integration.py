import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
BUILD_ROOT = TEST_DIR / ".modern-identity"


class ModernGameLocalizationIntegrationTests(unittest.TestCase):
    def setUp(self):
        if BUILD_ROOT.exists():
            shutil.rmtree(BUILD_ROOT)
        BUILD_ROOT.mkdir()

    def tearDown(self):
        if BUILD_ROOT.exists():
            shutil.rmtree(BUILD_ROOT)

    def _metadata_for(self, name, cjk_mask=None):
        build_root = BUILD_ROOT / name
        command = [
            "make",
            "--no-print-directory",
            "expansion-modern-game-localization-config-check",
            "MODERN_ROM_SIZE=32M",
            f"MODERN_BUILD_ROOT={build_root}",
        ]
        if cjk_mask is not None:
            command.append(f"MODERN_GAME_LOCALIZATION_CJK_MASK={cjk_mask}")
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        metadata_path = (
            build_root
            / "debug"
            / "aapcs"
            / "generated"
            / "expansion_build_metadata.json"
        )
        self.assertTrue(metadata_path.is_file(), result.stdout)
        return json.loads(metadata_path.read_text(encoding="utf-8")), result.stdout

    def _generated_catalog_for(self, name, cjk_mask):
        build_root = BUILD_ROOT / name
        generated_dir = build_root / "game-localization" / "generated"
        source_path = generated_dir / "game_localization_catalog.c"
        result = subprocess.run(
            [
                "make",
                "--no-print-directory",
                str(source_path),
                "MODERN_ROM_SIZE=32M",
                f"MODERN_BUILD_ROOT={build_root}",
                f"MODERN_GAME_LOCALIZATION_CJK_MASK={cjk_mask}",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        return {
            "source": source_path.read_text(encoding="utf-8"),
            "config": (generated_dir / "localized_game_text_data.h").read_text(
                encoding="utf-8"
            ),
        }

    def test_synthetic_cjk_metadata_and_fingerprint_match_effective_profiles(self):
        english, english_output = self._metadata_for("english")
        ja, ja_output = self._metadata_for("ja", "0x02")
        zh, zh_output = self._metadata_for("zh", "0x04")
        both, both_output = self._metadata_for("both", "0x06")

        self.assertEqual(english["enabled_locales"], ["en"])
        self.assertEqual(english["enabled_locale_mask"], 1)
        self.assertEqual(ja["enabled_locales"], ["en", "ja"])
        self.assertEqual(ja["enabled_locale_mask"], 3)
        self.assertEqual(zh["enabled_locales"], ["en", "zh-Hans"])
        self.assertEqual(zh["enabled_locale_mask"], 5)
        self.assertEqual(both["enabled_locales"], ["en", "ja", "zh-Hans"])
        self.assertEqual(both["enabled_locale_mask"], 7)

        self.assertNotEqual(english["config_fingerprint"], ja["config_fingerprint"])
        self.assertNotEqual(english["config_fingerprint"], zh["config_fingerprint"])
        self.assertNotEqual(english["config_fingerprint"], both["config_fingerprint"])
        self.assertIn(
            f"fingerprint={english['config_fingerprint']} mask=1 locales=en",
            english_output,
        )
        self.assertIn(
            f"fingerprint={ja['config_fingerprint']} mask=3 locales=en,ja",
            ja_output,
        )
        self.assertIn(
            f"fingerprint={zh['config_fingerprint']} mask=5 locales=en,zh-Hans",
            zh_output,
        )
        self.assertIn(
            f"fingerprint={both['config_fingerprint']} mask=7 locales=en,ja,zh-Hans",
            both_output,
        )

    def test_modern_generation_passes_the_selected_catalog_profile(self):
        ja = self._generated_catalog_for("catalog-ja", "0x02")
        zh = self._generated_catalog_for("catalog-zh", "0x04")
        both = self._generated_catalog_for("catalog-both", "0x06")

        self.assertIn("gGameLocalizationEnglishCompressedBlob[]", ja["source"])
        self.assertIn("gGameLocalizationJaCompressedBlob[]", ja["source"])
        self.assertNotIn("gGameLocalizationZhHansCompressedBlob[]", ja["source"])
        self.assertIn("FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES 5328u", ja["config"])
        self.assertIn("gGameLocalizationZhHansCompressedBlob[]", zh["source"])
        self.assertNotIn("gGameLocalizationJaCompressedBlob[]", zh["source"])
        self.assertIn("FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES 4260u", zh["config"])
        self.assertIn("gGameLocalizationEnglishCompressedBlob[]", zh["source"])
        self.assertIn("gGameLocalizationJaCompressedBlob[]", both["source"])
        self.assertIn("gGameLocalizationZhHansCompressedBlob[]", both["source"])
        self.assertEqual(
            ja["source"].count("gGameLocalizationEnglishCompressedBlob[]"), 1
        )
        self.assertEqual(
            both["source"].count("gGameLocalizationEnglishCompressedBlob[]"), 1
        )


if __name__ == "__main__":
    unittest.main()
