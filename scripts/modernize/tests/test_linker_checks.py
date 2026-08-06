"""Tests for modern expansion-linker verification target wiring."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODERN_MK = ROOT / "modern.mk"
EXPANSION_LD = ROOT / "linker" / "expansion.ld"


class LinkerCheckTargetTests(unittest.TestCase):
    PROFILE_SCRATCH = ROOT / "build" / "test-scratch" / "locale-profile-dry-run"

    def tearDown(self):
        shutil.rmtree(self.PROFILE_SCRATCH, ignore_errors=True)

    def make(self, *args):
        overrides = []
        toolchain_root = ROOT / "build" / "toolchain-root" / "usr"
        newlib = toolchain_root / "lib" / "arm-none-eabi" / "newlib"
        if (toolchain_root / "bin" / "arm-none-eabi-gcc").is_file():
            overrides.extend([
                f"MODERN_TOOLCHAIN_ROOT={toolchain_root}",
                f"MODERN_NEWLIB_LIB={newlib}",
            ])
        return subprocess.run(
            ["make", "--no-print-directory", *args, *overrides],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_all_linker_checks_are_modern_goals(self):
        text = MODERN_MK.read_text(encoding="utf-8")
        goals = text.split("MODERN_GOALS :=", 1)[1].split("ifneq", 1)[0]
        for target in (
            "expansion-modern-title-check",
            "expansion-modern-budget-check",
            "expansion-modern-relocs",
            "expansion-modern-overlay-audit",
            "expansion-modern-shifted-check",
            "expansion-modern-linker-check",
        ):
            self.assertIn(target, goals)

    def test_linker_check_dry_run_wires_every_gate(self):
        result = self.make("-n", "expansion-modern-linker-check")
        self.assertEqual(result.returncode, 0, result.stdout[-1000:])
        for expected in (
            "budget.py",
            "modern_emit_relocs.sh",
            "overlay_audit.py",
            "boot.json",
            "title-progression.json",
            "modern_shifted_boot.sh",
            "scan_build_addrs.py",
            "scan_raw_casts.sh",
        ):
            self.assertIn(expected, result.stdout)

    def test_budget_check_requires_elf_identity_and_user_stack_margin(self):
        result = self.make("-n", "expansion-modern-budget-check")
        self.assertEqual(result.returncode, 0, result.stdout[-1000:])
        self.assertIn("--validate-elf", result.stdout)
        self.assertIn("--require-positive-headroom ewram", result.stdout)
        self.assertIn("--require-positive-headroom iwram", result.stdout)

    def test_linker_reserves_nonzero_user_stack_floor(self):
        text = EXPANSION_LD.read_text(encoding="utf-8")
        self.assertIn("__iwram_static_limit = __sp_usr - 0x1000;", text)
        self.assertIn(
            "__iwram_static_end = ADDR(IWRAM) + SIZEOF(IWRAM);", text
        )
        self.assertIn(
            "ASSERT(__iwram_static_end < __sp_usr,", text
        )
        self.assertIn(
            "ASSERT(__iwram_static_end <= __iwram_static_limit,", text
        )

    def test_nonzero_shift_is_forwarded_to_linker(self):
        result = self.make(
            "-n",
            "expansion-modern-elf",
            "MODERN_TEXT_SHIFT=0x40000",
        )
        self.assertEqual(result.returncode, 0, result.stdout[-1000:])
        self.assertIn("--defsym=__text_shift=0x40000", result.stdout)
        self.assertIn("text_shift=0x40000", result.stdout)

    def test_title_fingerprint_is_configuration_specific(self):
        debug = self.make(
            "print-MODERN_TITLE_FINGERPRINT", "MODERN_CONFIG=debug"
        )
        release = self.make(
            "print-MODERN_TITLE_FINGERPRINT", "MODERN_CONFIG=release"
        )
        self.assertIn("title-progression-modern-debug.json", debug.stdout)
        self.assertIn("title-progression-modern-release.json", release.stdout)

    def test_english_and_pseudo_profiles_dry_run_at_16m(self):
        profiles = (
            ("en", "0"),
            ("en,qps-ploc", "1"),
        )
        for index, (locales, pseudo) in enumerate(profiles):
            with self.subTest(locales=locales):
                result = self.make(
                    "-n",
                    "expansion-modern-rom",
                    "MODERN_ROM_SIZE=16M",
                    f"EXPANSION_ENABLED_LOCALES={locales}",
                    f"EXPANSION_PSEUDO_LOCALE={pseudo}",
                    f"MODERN_BUILD_ROOT={self.PROFILE_SCRATCH / str(index)}",
                )
                self.assertEqual(result.returncode, 0, result.stdout[-2000:])

    def test_real_cjk_profiles_fail_fast_at_16m(self):
        for index, locales in enumerate(
            ("en,ja", "en,zh-Hans", "en,ja,zh-Hans")
        ):
            with self.subTest(locales=locales):
                result = self.make(
                    "-n",
                    "expansion-modern-rom",
                    "MODERN_ROM_SIZE=16M",
                    f"EXPANSION_ENABLED_LOCALES={locales}",
                    f"MODERN_BUILD_ROOT={self.PROFILE_SCRATCH / str(index)}",
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not yet populated", result.stdout)

    def test_real_cjk_profiles_fail_fast_at_32m(self):
        for index, locales in enumerate(
            ("en,ja", "en,zh-Hans", "zh-Hans,en,ja")
        ):
            with self.subTest(locales=locales):
                result = self.make(
                    "-n",
                    "expansion-modern-rom",
                    "MODERN_ROM_SIZE=32M",
                    f"EXPANSION_ENABLED_LOCALES={locales}",
                    f"MODERN_BUILD_ROOT={self.PROFILE_SCRATCH / str(index)}",
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not yet populated", result.stdout)

    def test_invalid_default_locale_still_fails_dry_run(self):
        result = self.make(
            "-n",
            "expansion-modern-rom",
            "MODERN_ROM_SIZE=32M",
            "EXPANSION_ENABLED_LOCALES=en",
            "EXPANSION_DEFAULT_LOCALE=qps-ploc",
            f"MODERN_BUILD_ROOT={self.PROFILE_SCRATCH / 'invalid-default'}",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EXPANSION_DEFAULT_LOCALE", result.stdout)


if __name__ == "__main__":
    unittest.main()
