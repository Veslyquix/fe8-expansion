import json
import re
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

    def _metadata_for(
        self,
        name,
        enabled_locales="en",
        default_locale="en",
        pseudo_locale="0",
    ):
        build_root = BUILD_ROOT / name
        command = [
            "make",
            "--no-print-directory",
            "expansion-modern-game-localization-config-check",
            "MODERN_ROM_SIZE=32M",
            f"MODERN_BUILD_ROOT={build_root}",
            f"EXPANSION_ENABLED_LOCALES={enabled_locales}",
            f"EXPANSION_DEFAULT_LOCALE={default_locale}",
            f"EXPANSION_PSEUDO_LOCALE={pseudo_locale}",
        ]
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

    def _generated_catalog_for(self, name, enabled_locales):
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
                f"EXPANSION_ENABLED_LOCALES={enabled_locales}",
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

    def test_real_cjk_metadata_and_fingerprint_match_effective_profiles(self):
        english, english_output = self._metadata_for("english")
        ja, ja_output = self._metadata_for("ja", "en,ja", default_locale="ja")
        zh, zh_output = self._metadata_for(
            "zh", "en,zh-Hans", default_locale="zh-Hans"
        )
        both, both_output = self._metadata_for("both", "zh-Hans,en,ja")
        with_qps, qps_output = self._metadata_for(
            "both-qps",
            "qps-ploc,zh-Hans,en,ja",
            pseudo_locale="1",
        )

        self.assertEqual(english["enabled_locales"], ["en"])
        self.assertEqual(english["enabled_locale_mask"], 1)
        self.assertEqual(ja["enabled_locales"], ["en", "ja"])
        self.assertEqual(ja["enabled_locale_mask"], 3)
        self.assertEqual(ja["default_locale"], "ja")
        self.assertEqual(ja["default_locale_id"], 1)
        self.assertEqual(zh["enabled_locales"], ["en", "zh-Hans"])
        self.assertEqual(zh["enabled_locale_mask"], 5)
        self.assertEqual(zh["default_locale"], "zh-Hans")
        self.assertEqual(zh["default_locale_id"], 2)
        self.assertEqual(both["enabled_locales"], ["en", "ja", "zh-Hans"])
        self.assertEqual(both["enabled_locale_mask"], 7)
        self.assertEqual(
            with_qps["enabled_locales"],
            ["en", "ja", "zh-Hans", "qps-ploc"],
        )
        self.assertEqual(with_qps["enabled_locale_mask"], 0x87)
        self.assertEqual(with_qps["pseudo_locale_enabled"], 1)

        self.assertNotEqual(english["config_fingerprint"], ja["config_fingerprint"])
        self.assertNotEqual(english["config_fingerprint"], zh["config_fingerprint"])
        self.assertNotEqual(english["config_fingerprint"], both["config_fingerprint"])
        self.assertNotEqual(both["config_fingerprint"], with_qps["config_fingerprint"])
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
        self.assertIn(
            f"fingerprint={with_qps['config_fingerprint']} mask=135 "
            "locales=en,ja,zh-Hans,qps-ploc",
            qps_output,
        )

    def test_modern_generation_passes_the_selected_catalog_profile(self):
        ja = self._generated_catalog_for("catalog-ja", "en,ja")
        zh = self._generated_catalog_for("catalog-zh", "en,zh-Hans")
        both = self._generated_catalog_for(
            "catalog-both", "qps-ploc,zh-Hans,en,ja"
        )

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

    def test_synthetic_identity_override_is_retired(self):
        self.assertFalse(
            (ROOT / "scripts/localization/game_catalog/synthetic_identity.py").exists()
        )
        modern_mk = (ROOT / "modern.mk").read_text(encoding="utf-8")
        self.assertNotIn("MODERN_GAME_LOCALIZATION_CJK_MASK", modern_mk)
        self.assertNotIn("synthetic_identity", modern_mk)

    def test_named_production_profiles_use_32m_and_real_locale_config(self):
        modern_mk = (ROOT / "modern.mk").read_text(encoding="utf-8")
        expected = {
            "expansion-modern-localization-profile-en-ja": (
                "EXPANSION_ENABLED_LOCALES=en,ja",
                "EXPANSION_PSEUDO_LOCALE=1",
            ),
            "expansion-modern-localization-profile-en-zh-hans": (
                "EXPANSION_ENABLED_LOCALES=en,zh-Hans",
                "EXPANSION_PSEUDO_LOCALE=1",
            ),
            "expansion-modern-localization-profile-en-ja-zh-hans": (
                "EXPANSION_ENABLED_LOCALES=en,ja,zh-Hans",
                "EXPANSION_PSEUDO_LOCALE=1",
            ),
            "expansion-modern-localization-profile-en-ja-zh-hans-qps": (
                "EXPANSION_ENABLED_LOCALES=en,ja,zh-Hans,qps-ploc",
                "EXPANSION_PSEUDO_LOCALE=1",
            ),
        }
        for target, (locale_arg, qps_arg) in expected.items():
            with self.subTest(target=target):
                match = re.search(
                    rf"(?m)^{target}:\n(?P<body>(?:\t[^\n]*\n)+)",
                    modern_mk,
                )
                self.assertIsNotNone(match)
                body = match.group("body")
                self.assertIn("MODERN_ROM_SIZE=32M", body)
                self.assertIn(locale_arg, body)
                if target.endswith("-qps"):
                    self.assertIn(qps_arg, body)
                else:
                    self.assertNotIn(qps_arg, body)

    def test_cjk_runtime_gate_checks_all_product_profile_maps(self):
        modern_mk = (ROOT / "modern.mk").read_text(encoding="utf-8")
        match = re.search(
            r"(?m)^expansion-modern-localization-profile-headroom-check:\n"
            r"(?P<body>(?:\t[^\n]*\n)+)",
            modern_mk,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        for profile in (
            "en-ja",
            "en-zh-hans",
            "en-ja-zh-hans",
            "en-ja-zh-hans-qps",
        ):
            with self.subTest(profile=profile):
                self.assertIn(
                    f"expansion-modern-localization-profile-{profile}",
                    body,
                )
        self.assertEqual(body.count("--validate-elf"), 4)
        self.assertEqual(
            body.count("--require-positive-headroom ewram"),
            4,
        )

        cjk_start = modern_mk.index(
            "expansion-modern-localization-runtime-cjk-check:"
        )
        cjk_recipe = modern_mk.index(
            "ifeq ($(MODERN_CONFIG),debug)", cjk_start
        )
        self.assertIn(
            "expansion-modern-localization-profile-headroom-check",
            modern_mk[cjk_start:cjk_recipe],
        )


if __name__ == "__main__":
    unittest.main()
