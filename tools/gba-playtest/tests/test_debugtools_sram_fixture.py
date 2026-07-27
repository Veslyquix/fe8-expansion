"""CI-follow-up coverage for the debugtools-hub exact-SRAM-hash instability
(issue #11 slice 1 follow-up).

Root cause recap (see docs/debugtools.md and modern.mk's
MODERN_DEBUGTOOLS_SRAM_FIXTURE comment): the debugtools-hub scenarios
assert an EXACT, zero-exclusion-range whole-SRAM `fnv1a64-sram` hash at
their "pre-launch"/"chapter2-interactive-stable" checkpoints. Booting from
genuinely blank SRAM makes ClassifySramSaveCompat() report
SAVE_COMPAT_EMPTY, so EnsureGlobalSaveInfoLoaded() (src/bmsave-lib.c)
calls InitGlobalSaveInfodata() -> BuildCurrentExpansionSaveMeta(), which
stamps that build's live FE8_EXPANSION_BUILD_COMMIT into
ExpansionSaveMeta.buildCommitShort -- changing on every commit and
breaking the exact hash. The fix seeds SRAM via --sram-image with
sram_fixture.py's build_deterministic_current_image(): an already
SAVE_COMPAT_CURRENT image whose only commit-derived diagnostic field is
frozen to a fixed sentinel, so that wipe/stamp path is never taken.

This module covers (host-only, no ROM/libmGBA required):
  1. The fixture CLI (`sram_fixture.py write-deterministic-current`).
  2. That the fixture differs from build_fixture_image(STATE_CURRENT) in
     only the commit-derived byte range, and is itself insensitive to
     which commit built it (the actual invariance property).
  3. That the debugtools-hub scenario/fingerprint files keep the exact
     (zero-exclusion-range) hash policy -- never normalized.
  4. modern.mk's wiring: expansion-modern-debugtools-check passes
     --sram-image pointing at the build-tree fixture target for both
     MODERN_CONFIG=debug and release, while
     expansion-modern-debugtools-timer-check and
     expansion-modern-savefmt-check are left unaffected.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAYTEST_DIR = REPO_ROOT / "tools" / "gba-playtest"
SCENARIOS_DIR = PLAYTEST_DIR / "scenarios"
FINGERPRINTS_DIR = PLAYTEST_DIR / "fingerprints"
MODERNIZE_DIR = REPO_ROOT / "scripts" / "modernize"
MODERNIZE_TESTS_DIR = MODERNIZE_DIR / "tests"
SRAM_FIXTURE_SCRIPT = Path(__file__).resolve().parent / "sram_fixture.py"

for _extra_path in (
    str(PLAYTEST_DIR),
    str(Path(__file__).resolve().parent),
    str(MODERNIZE_DIR),
    str(MODERNIZE_TESTS_DIR),
):
    if _extra_path not in sys.path:
        sys.path.insert(0, _extra_path)

import gba_playtest  # noqa: E402
import modern_mk_query as mmq  # noqa: E402
import save_format_tool as sft  # noqa: E402
import sram_fixture as sf  # noqa: E402
from sram_hash_mirror import compute_sram_hash  # noqa: E402
from test_save_format_tool import make_header, make_image, make_meta  # noqa: E402


class DeterministicCurrentImageTests(unittest.TestCase):
    """Direct coverage of build_deterministic_current_image() /
    write_deterministic_current_fixture()."""

    def test_image_is_exact_0x8000_bytes_and_classifies_current(self):
        image = sf.build_deterministic_current_image()
        self.assertEqual(len(image), sft.SRAM_SIZE)
        epoch = sf.resolve_epoch()
        self.assertEqual(sft.classify_image(image, epoch), sf.STATE_CURRENT)

    def test_build_commit_short_is_the_fixed_sentinel(self):
        image = sf.build_deterministic_current_image()
        offset = sft.META_OFFSET + 0x24  # ExpansionSaveMeta.buildCommitShort
        actual = image[offset:offset + 9]
        self.assertEqual(actual, sf.DETERMINISTIC_BUILD_COMMIT_SHORT)

    def test_differs_from_live_state_current_only_in_commit_dependent_bytes(self):
        """build_fixture_image(STATE_CURRENT) embeds the *live*
        `git rev-parse HEAD`-derived build commit (see
        sft.build_current_expansion_save_meta()); the deterministic
        fixture must be byte-identical to it everywhere except the
        buildCommitShort field and the checksum field whose domain covers
        it (both inside the same 0x2E..0x2E+9-ish metadata window)."""
        live_image = sf.build_fixture_image(sf.STATE_CURRENT)
        deterministic_image = sf.build_deterministic_current_image()
        self.assertEqual(len(live_image), len(deterministic_image))

        differing_offsets = [
            offset
            for offset in range(len(live_image))
            if live_image[offset] != deterministic_image[offset]
        ]
        build_commit_offset = sft.META_OFFSET + 0x24
        checksum_offset = sft.META_OFFSET + 0x2E
        allowed = set(range(build_commit_offset, build_commit_offset + 9)) | set(
            range(checksum_offset, checksum_offset + 2)
        )
        self.assertTrue(differing_offsets, "fixtures should differ in at least the commit field")
        for offset in differing_offsets:
            self.assertIn(
                offset, allowed,
                f"unexpected byte difference at offset 0x{offset:04x} outside "
                "the commit-dependent field/checksum window",
            )

    def test_write_deterministic_current_fixture_creates_exact_size_file(self):
        import tempfile

        with tempfile.TemporaryDirectory(prefix="debugtools-sram-fixture-test-") as temp:
            path = Path(temp) / "nested" / "debugtools-current.sav"
            sf.write_deterministic_current_fixture(path)
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_size, sft.SRAM_SIZE)
            epoch = sf.resolve_epoch()
            self.assertEqual(sft.classify_image(path.read_bytes(), epoch), sf.STATE_CURRENT)


class DeterministicCliTests(unittest.TestCase):
    """Coverage of the `write-deterministic-current` CLI subcommand added
    to sram_fixture.py -- exercised as a subprocess exactly as modern.mk
    invokes it."""

    def test_cli_writes_expected_fixture(self):
        import tempfile

        with tempfile.TemporaryDirectory(prefix="debugtools-sram-cli-test-") as temp:
            output = Path(temp) / "debugtools-current.sav"
            result = subprocess.run(
                [sys.executable, str(SRAM_FIXTURE_SCRIPT), "write-deterministic-current", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SAVE_COMPAT_CURRENT", result.stdout)
            self.assertTrue(output.is_file())
            self.assertEqual(output.stat().st_size, sft.SRAM_SIZE)
            epoch = sf.resolve_epoch()
            self.assertEqual(sft.classify_image(output.read_bytes(), epoch), sf.STATE_CURRENT)

    def test_cli_rejects_unknown_mode(self):
        result = subprocess.run(
            [sys.executable, str(SRAM_FIXTURE_SCRIPT), "not-a-real-mode"],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)


class CommitInvarianceTests(unittest.TestCase):
    """The core property this follow-up exists to guarantee: the exact
    (zero-exclusion-range) whole-SRAM hash of the deterministic fixture
    must not depend on which commit is "live" when it is generated --
    unlike build_fixture_image(STATE_CURRENT), which does (see
    test_sram_hash_normalization.py's BuildCommitDiagnosticStabilityTests
    for that documented, expected, *normalized*-hash-only invariance)."""

    def _image_for_simulated_commit(self, build_commit_short: bytes) -> bytes:
        """Constructs the same shape of image build_deterministic_current_image()
        would for a hypothetical different live commit, but then freezes
        buildCommitShort exactly like the real helper does -- proving the
        freeze, not the input, is what makes the result invariant."""
        epoch = sf.resolve_epoch()
        header = make_header(valid=True)
        meta = make_meta(
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT,
            compat_epoch=epoch,
            build_commit_short=build_commit_short,
        )
        image = bytearray(make_image(header, meta))
        # Mirror build_deterministic_current_image()'s freeze step.
        offset = sft.META_OFFSET + 0x24
        image[offset:offset + 9] = sf.DETERMINISTIC_BUILD_COMMIT_SHORT
        checksum_offset = sft.META_OFFSET
        meta_bytes = bytes(image[checksum_offset:checksum_offset + sft.META_SIZE])
        # Recompute the checksum the same way ExpansionSaveMeta.pack()/
        # computed_checksum() would, using the real classifier's own
        # constant so this doesn't duplicate the algorithm.
        checksum = sft.checksum16(meta_bytes[: sft.META_CHECKSUM_DOMAIN])
        checksum_field_offset = checksum_offset + sft.META_CHECKSUM_DOMAIN
        image[checksum_field_offset:checksum_field_offset + 2] = checksum.to_bytes(2, "little")
        image = bytes(image)
        self.assertEqual(sft.classify_image(image, epoch), sf.STATE_CURRENT)
        return image

    def test_exact_hash_is_invariant_to_simulated_commit_change(self):
        image_a = self._image_for_simulated_commit(b"cafef00d\x00")
        image_b = self._image_for_simulated_commit(b"deadbeef\x00")
        # Both are byte-identical after the freeze step (same input to
        # build_deterministic_current_image() modulo the discarded
        # pre-freeze commit bytes), so the exact hash (no exclude ranges)
        # must match -- this is the guarantee the debugtools-hub exact
        # sram_hash checkpoints depend on.
        self.assertEqual(image_a, image_b)
        self.assertEqual(
            compute_sram_hash(image_a, ()),
            compute_sram_hash(image_b, ()),
        )

class ScenarioExactHashPolicyTests(unittest.TestCase):
    """Requirement: debugtools-hub scenario checkpoints keep the exact
    fnv1a64-sram hash with zero exclusion ranges -- never normalized."""

    def _assert_scenario_has_zero_exclusion_exact_sram_checkpoints(self, scenario_path: Path):
        scenario = gba_playtest.load_scenario(scenario_path)
        sram_checkpoints = [cp for cp in scenario.checkpoints if cp.sram_hash]
        for checkpoint in sram_checkpoints:
            with self.subTest(scenario=scenario_path.name, checkpoint=checkpoint.name):
                self.assertEqual(
                    checkpoint.sram_hash_exclude_ranges, (),
                    "debugtools-hub sram_hash checkpoints must use the exact "
                    "whole-image hash (no exclusion ranges)",
                )
                if checkpoint.expected_sram_hash is not None:
                    self.assertTrue(
                        checkpoint.expected_sram_hash.startswith("fnv1a64-sram:"),
                        "must be the exact algorithm, never 'fnv1a64-sram-normalized:'",
                    )

    def test_debug_scenario_declares_no_exclude_ranges(self):
        self._assert_scenario_has_zero_exclusion_exact_sram_checkpoints(
            SCENARIOS_DIR / "debugtools-hub-modern-debug.json"
        )

    def test_release_scenario_declares_no_exclude_ranges(self):
        self._assert_scenario_has_zero_exclusion_exact_sram_checkpoints(
            SCENARIOS_DIR / "debugtools-hub-modern-release.json"
        )

    def test_debug_scenario_has_at_least_one_sram_hash_checkpoint(self):
        # Sanity check: the scenario file really does exercise the exact-
        # hash path this module is about, so the assertions above aren't
        # vacuously true.
        scenario = gba_playtest.load_scenario(SCENARIOS_DIR / "debugtools-hub-modern-debug.json")
        self.assertTrue(any(cp.sram_hash for cp in scenario.checkpoints))

    def test_debug_fingerprint_hashes_are_exact_not_normalized(self):
        import json

        fingerprint = json.loads(
            (FINGERPRINTS_DIR / "debugtools-hub-modern-debug.json").read_text()
        )
        sram_hashes = [
            checkpoint["sram_hash"]
            for checkpoint in fingerprint["checkpoints"]
            if "sram_hash" in checkpoint
        ]
        self.assertTrue(sram_hashes)
        for value in sram_hashes:
            self.assertTrue(value.startswith("fnv1a64-sram:"))
            self.assertFalse(value.startswith("fnv1a64-sram-normalized:"))


class ModernMkWiringTests(unittest.TestCase):
    """Proves modern.mk's Make-level debugtools wiring **host-only**, by reading
    modern.mk's fully parsed ``make -p`` database via :mod:`modern_mk_query`
    instead of dry-running the modern goals themselves.

    The previous ``make -n expansion-modern-debugtools-check`` approach was not
    host-only: those goals are members of ``MODERN_ALL_SOURCE_GOALS``, so Make
    remade the included per-source ``*.headers.d`` files -- running the
    arm-none-eabi cross compiler through ``expansion-modern-toolchain-check`` --
    *before* honouring ``-n``, which fails on the CI ``host-tests`` lane that,
    by design, ships no cross toolchain (CI run 30243920318). The ``make -p``
    probe query names only an inert non-source goal, so the header-dependency
    ``include`` stays disabled and no compiler is ever needed. See
    :mod:`modern_mk_query` for the full root-cause writeup.

    Assertion semantics are preserved exactly: debug/release
    ``expansion-modern-debugtools-check`` both pass ``--sram-image`` pointing at
    their config-specific ``debugtools-current.sav`` (also wired as a build
    prerequisite); the fixture recipe runs ``sram_fixture.py``; the timer-freeze
    check is never given an sram image / debugtools fixture; and
    ``expansion-modern-savefmt-check`` keeps its own ``savefmt-fixtures`` and
    never references the debugtools fixture.
    """

    _FIXTURE_SUFFIX = "debugtools-fixtures/debugtools-current.sav"

    def _assert_debugtools_check_seeds_config_fixture(self, config: str) -> None:
        database = mmq.query_make_database(config)
        fixture = mmq.variable_value(database, "MODERN_DEBUGTOOLS_SRAM_FIXTURE")
        script = mmq.variable_value(database, "MODERN_DEBUGTOOLS_SRAM_FIXTURE_SCRIPT")

        # Config-specific fixture path, authoritatively expanded by make.
        self.assertEqual(
            fixture,
            f"build/expansion-modern/{config}/aapcs/{self._FIXTURE_SUFFIX}",
        )

        # expansion-modern-debugtools-check passes that fixture as --sram-image
        # and depends on it, so it is generated before the check runs.
        recipe = mmq.rule_recipe(database, "expansion-modern-debugtools-check")
        self.assertIn(
            '--sram-image "$(MODERN_DEBUGTOOLS_SRAM_FIXTURE)"',
            recipe,
            "debugtools-check must seed SRAM from the deterministic fixture",
        )
        self.assertIn(
            fixture,
            mmq.rule_prerequisites(database, "expansion-modern-debugtools-check"),
            "the config-specific fixture must be a build prerequisite",
        )

        # The fixture is produced by sram_fixture.py's write-deterministic-current.
        self.assertEqual(script, "tools/gba-playtest/tests/sram_fixture.py")
        fixture_recipe = mmq.rule_recipe(database, fixture)
        self.assertIn('"$(MODERN_DEBUGTOOLS_SRAM_FIXTURE_SCRIPT)"', fixture_recipe)
        self.assertIn("write-deterministic-current", fixture_recipe)

    def test_debug_debugtools_check_passes_sram_image(self):
        self._assert_debugtools_check_seeds_config_fixture("debug")

    def test_release_debugtools_check_passes_sram_image(self):
        self._assert_debugtools_check_seeds_config_fixture("release")

    def test_debug_timer_check_is_not_given_sram_image(self):
        """The timer-freeze scenario has no sram_hash checkpoints (it never
        observes SRAM), so it deliberately keeps booting from blank SRAM --
        seeding it would only add risk (different boot timing) for no benefit."""
        database = mmq.query_make_database("debug")
        recipe = mmq.rule_recipe(database, "expansion-modern-debugtools-timer-check")
        self.assertNotIn("--sram-image", recipe)
        self.assertNotIn("debugtools-fixtures", recipe)
        self.assertNotIn("MODERN_DEBUGTOOLS_SRAM_FIXTURE", recipe)
        fixture = mmq.variable_value(database, "MODERN_DEBUGTOOLS_SRAM_FIXTURE")
        self.assertNotIn(
            fixture,
            mmq.rule_prerequisites(
                database, "expansion-modern-debugtools-timer-check"
            ),
        )

    def test_savefmt_check_recipe_is_unaffected(self):
        """expansion-modern-savefmt-check must keep using its own
        savefmt-fixtures directory/fixtures (run_save_compat_checks.py), never
        the new debugtools fixture target."""
        database = mmq.query_make_database("debug")
        recipe = mmq.rule_recipe(database, "expansion-modern-savefmt-check")
        self.assertNotIn("debugtools-fixtures", recipe)
        self.assertNotIn("MODERN_DEBUGTOOLS_SRAM_FIXTURE", recipe)
        self.assertIn("$(MODERN_SAVEFMT_FIXTURE_DIR)", recipe)
        self.assertTrue(
            mmq.variable_value(database, "MODERN_SAVEFMT_FIXTURE_DIR").endswith(
                "savefmt-fixtures"
            )
        )


class DebugtoolsWiringToolchainFreeRegressionTests(unittest.TestCase):
    """Regression teeth for the host-only wiring checks (CI run 30243920318).

    Reconstructs the CI ``host-tests`` lane -- a PATH with **no**
    ``arm-none-eabi-gcc`` -- and proves that (a) the four
    :class:`ModernMkWiringTests` pass there, while (b) the old-style
    ``make -n <modern goal>`` dry run they replaced still fails there with the
    exact missing-compiler diagnostic. Guards against anyone reverting the
    checks to a form that needs the cross toolchain.
    """

    def _run_wiring_tests(self, env) -> subprocess.CompletedProcess:
        # Target the wiring class explicitly so this regression never recurses
        # into itself.
        return subprocess.run(
            [
                sys.executable, "-m", "unittest", "-v",
                "test_debugtools_sram_fixture.ModernMkWiringTests",
            ],
            cwd=str(Path(__file__).resolve().parent),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_wiring_checks_are_host_only_without_cross_compiler(self):
        env, bin_dir, tmp_root = mmq.build_toolchain_free_env(REPO_ROOT)
        try:
            # The reconstructed host lane must not resolve the cross compiler.
            self.assertIsNone(
                shutil.which("arm-none-eabi-gcc", path=str(bin_dir)),
                "hermetic host bin unexpectedly exposes arm-none-eabi-gcc",
            )

            # Teeth: on a clean build tree the OLD approach genuinely fails here
            # (the reproduced CI failure). A throwaway empty MODERN_BUILD_ROOT
            # recreates the "no *.headers.d yet" clean checkout without touching
            # this worktree's own build/ artifacts.
            empty_root = tmp_root / "empty-build"
            empty_root.mkdir()
            old_style = subprocess.run(
                [
                    "make", "--no-print-directory", "-n",
                    "MODERN_CONFIG=debug",
                    f"MODERN_BUILD_ROOT={empty_root}",
                    "expansion-modern-debugtools-check",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(
                old_style.returncode,
                0,
                "old-style `make -n <modern goal>` unexpectedly succeeded without "
                "a cross compiler -- the root cause this test documents is gone; "
                "revisit whether the wiring checks may safely name modern goals.",
            )
            self.assertIn("modern compiler not found", old_style.stdout)

            # The fixed, host-only checks must pass in this same toolchain-free env.
            result = self._run_wiring_tests(env)
            self.assertEqual(
                result.returncode,
                0,
                "ModernMkWiringTests must pass without arm-none-eabi-gcc:\n"
                + result.stdout,
            )
            self.assertIn("Ran 4 tests", result.stdout)
            self.assertNotIn("FAILED", result.stdout)
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)


class FixtureDependencyInvalidationTests(unittest.TestCase):
    """Proves MODERN_DEBUGTOOLS_SRAM_FIXTURE's Make prerequisites cover the
    fixture's actual generation logic, not just the entry-point script:
    touching any of sram_fixture.py's real imports
    (save_format_tool.py/expansion_config.py/test_save_format_tool.py) or
    config.mk must invalidate the cached build/ fixture and make
    `make -n` regenerate it; leaving all of them untouched must keep the
    fixture cached (no regeneration recipe printed).

    Uses only mtime manipulation (os.utime) against files already tracked
    unmodified by git (verified in setUp) plus a real, toolchain-free run
    of the fixture's own recipe (a plain python3 script invocation, no
    arm-none-eabi cross compiler needed) -- never a real ROM build. All
    touched mtimes are restored in tearDown so the working tree's file
    timestamps are left as found.
    """

    FIXTURE_RELATIVE_PATH = "build/expansion-modern/debug/aapcs/debugtools-fixtures/debugtools-current.sav"

    DEPENDENCY_RELATIVE_PATHS = (
        "tools/gba-playtest/tests/sram_fixture.py",
        "scripts/modernize/save_format_tool.py",
        "scripts/modernize/expansion_config.py",
        "scripts/modernize/tests/test_save_format_tool.py",
        "config.mk",
    )

    def setUp(self):
        self._fixture_path = REPO_ROOT / self.FIXTURE_RELATIVE_PATH
        self._dependency_paths = [REPO_ROOT / rel for rel in self.DEPENDENCY_RELATIVE_PATHS]
        for path in self._dependency_paths:
            self.assertTrue(path.is_file(), f"expected dependency to exist: {path}")

        # Record original (atime, mtime) for every file this test touches,
        # so tearDown can restore them exactly -- this test only ever
        # changes timestamps, never content, of tracked source files.
        self._original_dependency_stat_times = {
            path: (path.stat().st_atime, path.stat().st_mtime) for path in self._dependency_paths
        }
        self._fixture_existed_before = self._fixture_path.exists()
        self._original_fixture_stat_times = (
            (self._fixture_path.stat().st_atime, self._fixture_path.stat().st_mtime)
            if self._fixture_existed_before
            else None
        )

        # Establish a known-fresh baseline: really run the (toolchain-free)
        # fixture recipe once so the fixture file exists and is newer than
        # every dependency.
        self._build_fixture_for_real()

    def tearDown(self):
        for path, times in self._original_dependency_stat_times.items():
            os.utime(path, times)
        if self._original_fixture_stat_times is not None:
            os.utime(self._fixture_path, self._original_fixture_stat_times)
        elif self._fixture_path.exists() and not self._fixture_existed_before:
            self._fixture_path.unlink()

    def _build_fixture_for_real(self) -> None:
        result = subprocess.run(
            ["make", "--no-print-directory", "MODERN_CONFIG=debug", self.FIXTURE_RELATIVE_PATH],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(self._fixture_path.is_file())

    def _dry_run_regenerates_fixture(self) -> bool:
        result = subprocess.run(
            ["make", "--no-print-directory", "-n", "MODERN_CONFIG=debug", self.FIXTURE_RELATIVE_PATH],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        return "write-deterministic-current" in result.stdout

    def test_fixture_is_cached_when_no_dependency_changed(self):
        self.assertFalse(self._dry_run_regenerates_fixture())

    def test_touching_each_dependency_triggers_regeneration(self):
        for path in self._dependency_paths:
            with self.subTest(dependency=path.relative_to(REPO_ROOT)):
                self._build_fixture_for_real()
                self.assertFalse(self._dry_run_regenerates_fixture())

                future = time.time() + 5
                os.utime(path, (future, future))
                self.assertTrue(
                    self._dry_run_regenerates_fixture(),
                    f"expected touching {path} to invalidate the cached fixture",
                )

                # Restore this dependency's mtime immediately so the next
                # iteration starts from a clean, cached baseline.
                os.utime(path, self._original_dependency_stat_times[path])


if __name__ == "__main__":
    unittest.main()
