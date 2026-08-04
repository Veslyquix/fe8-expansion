"""Regression tests for review finding #4 (HIGH) on issue #2 slice 1:

EXPANSION_SAVE_COMPAT_EPOCH was parsed/validated by config.mk and
scripts/modernize/expansion_config.py, but modern.mk never threaded the
resolved value into MODERN_CFLAGS's -D defines or into
MODERN_COMPILE_SETTINGS (the issue #8 content-addressed recompilation
stamp). This meant a modern build always compiled against
include/expansion_config.h's FE8_EXPANSION_SAVE_COMPAT_EPOCH fallback
(1), regardless of any config.mk/command-line override, and even after
fixing that, changing the override between two builds sharing the same
MODERN_OUTPUT_DIR would not invalidate previously-compiled objects
without a full `make clean`.

These tests run against the real repository root (real config.mk, so
MODERN_EXPANSION_CONFIG_AVAILABLE is true and the resolve block is
reachable), exactly like tests/test_modern_rom_boot.py's
test_clean_succeeds_with_invalid_expansion_config. They use `make -n`
(dry run) and direct file-target builds so they run unconditionally,
without requiring the arm-none-eabi-gcc cross toolchain -- the intent
here is to prove Make's variable/dependency wiring, not to compile real
objects.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class SaveCompatEpochModernBuildTests(unittest.TestCase):

    def make(self, *args, cwd=None):
        return subprocess.run(
            ["make", "--no-print-directory", *args],
            cwd=cwd or ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    @staticmethod
    def _extract_token(stdout: str, key: str) -> str:
        """Pulls the first 'key=value' token's value out of dry-run/-D
        flag text (values may repeat once per translation unit; the first
        occurrence is sufficient since they must all agree)."""
        marker = f"{key}="
        index = stdout.find(marker)
        if index == -1:
            raise AssertionError(f"{marker} not found in: {stdout}")
        rest = stdout[index + len(marker):]
        for terminator in (" ", "'", "\n"):
            cut = rest.find(terminator)
            if cut != -1:
                rest = rest[:cut]
        return rest

    def test_default_epoch_is_wired_into_cflags(self):
        """Without any override, MODERN_CFLAGS must carry
        -DFE8_EXPANSION_SAVE_COMPAT_EPOCH matching config.mk's
        EXPANSION_SAVE_COMPAT_EPOCH default (2, bumped from 1 for issue
        #18 sprint 2's ExpansionUserPrefs sub-record -- see config.mk)
        -- proving the define is present at all, not silently falling
        back to the header's #ifndef default by omission."""
        result = self.make("-n", "expansion-modern-cohort")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("-DFE8_EXPANSION_SAVE_COMPAT_EPOCH=2", result.stdout)

    def test_override_changes_cflags_define_but_not_config_fingerprint(self):
        """Overriding EXPANSION_SAVE_COMPAT_EPOCH on the command line must
        change the compiled -D value, while leaving
        -DFE8_EXPANSION_CONFIG_FINGERPRINT untouched -- the save-compat
        epoch is a distinct compatibility gate from the issue #8 config
        fingerprint (see docs/config_identity.md), so it must never be
        folded into that fingerprint's inputs."""
        baseline = self.make("-n", "expansion-modern-cohort")
        self.assertEqual(baseline.returncode, 0, baseline.stdout)
        baseline_fingerprint = self._extract_token(
            baseline.stdout, "-DFE8_EXPANSION_CONFIG_FINGERPRINT"
        )

        overridden = self.make(
            "-n", "expansion-modern-cohort", "EXPANSION_SAVE_COMPAT_EPOCH=3"
        )
        self.assertEqual(overridden.returncode, 0, overridden.stdout)
        self.assertIn(
            "-DFE8_EXPANSION_SAVE_COMPAT_EPOCH=3", overridden.stdout
        )
        self.assertNotIn(
            "-DFE8_EXPANSION_SAVE_COMPAT_EPOCH=2", overridden.stdout
        )
        overridden_fingerprint = self._extract_token(
            overridden.stdout, "-DFE8_EXPANSION_CONFIG_FINGERPRINT"
        )
        self.assertEqual(baseline_fingerprint, overridden_fingerprint)

    def test_print_target_resolves_epoch_variable(self):
        """modern.mk's MODERN_SAVE_COMPAT_EPOCH variable (parsed from the
        same MODERN_EXPANSION_CONFIG_RESOLVE shell-out as
        MODERN_BUILD_COMMIT/MODERN_CONFIG_FINGERPRINT) must resolve to the
        override, using the pre-existing generic `print-%` debug target
        (Makefile's print-% rule)."""
        result = self.make(
            "print-MODERN_SAVE_COMPAT_EPOCH",
            "expansion-modern-toolchain-check",
            "EXPANSION_SAVE_COMPAT_EPOCH=3",
        )
        # expansion-modern-toolchain-check is expected to fail in this
        # sandbox (no arm-none-eabi-gcc); only the print-% output matters.
        self.assertIn(
            "MODERN_SAVE_COMPAT_EPOCH is a simple variable set to [3]",
            result.stdout,
        )

    def test_compile_settings_stamp_includes_epoch_and_reacts_to_override(
        self,
    ):
        """The issue #8 MODERN_COMPILE_SETTINGS content-addressed stamp
        (a prerequisite of every modern C/data object) must include
        save_compat_epoch, and its content must change when the epoch
        override changes -- this is what forces GNU Make to recompile
        every translation unit observing include/expansion_config.h on
        the next build, without requiring `make clean` first. Also
        reconfirms config_fingerprint is unaffected by the epoch.

        Builds the stamp file's literal path directly (like
        test_modern_build.py's test_compile_settings_stamp_is_inert_
        without_config_mk), listed alongside expansion-modern-toolchain-
        check on the same command line so MAKECMDGOALS contains a real
        modern goal and the config-resolve block activates even though
        the file path itself is not one. A throwaway MODERN_BUILD_ROOT
        (an isolated temporary directory, per this test suite's existing
        convention -- see test_modern_rom_boot.py's
        test_clean_succeeds_with_invalid_expansion_config) keeps this from
        touching the real build/ tree.
        """
        with tempfile.TemporaryDirectory() as temporary:
            build_root = Path(temporary) / "expansion-modern"
            stamp = (
                build_root / "debug" / "aapcs" / "generated"
                / "compile_settings.txt"
            )

            first = self.make(
                str(stamp), "expansion-modern-toolchain-check",
                f"MODERN_BUILD_ROOT={build_root}",
                "EXPANSION_SAVE_COMPAT_EPOCH=1",
            )
            self.assertTrue(stamp.exists(), first.stdout)
            first_lines = stamp.read_text(encoding="utf-8").splitlines()
            self.assertIn("save_compat_epoch=1", first_lines)
            self.assertIn(
                "data_layout_flags=-fno-toplevel-reorder",
                first_lines,
            )
            first_fingerprint = next(
                line for line in first_lines
                if line.startswith("config_fingerprint=")
            )

            second = self.make(
                str(stamp), "expansion-modern-toolchain-check",
                f"MODERN_BUILD_ROOT={build_root}",
                "EXPANSION_SAVE_COMPAT_EPOCH=2",
            )
            self.assertTrue(stamp.exists(), second.stdout)
            second_lines = stamp.read_text(encoding="utf-8").splitlines()
            self.assertIn("save_compat_epoch=2", second_lines)
            self.assertIn(
                "data_layout_flags=-fno-toplevel-reorder",
                second_lines,
            )
            second_fingerprint = next(
                line for line in second_lines
                if line.startswith("config_fingerprint=")
            )

            self.assertEqual(first_fingerprint, second_fingerprint)
            self.assertNotEqual(first_lines, second_lines)


if __name__ == "__main__":
    unittest.main()
