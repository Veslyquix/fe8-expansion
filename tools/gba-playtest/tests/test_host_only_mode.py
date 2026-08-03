"""Regression teeth for the GBA_PLAYTEST_HOST_ONLY host-only contract.

Issue #10 / #13 integrated-harness defect: the host lane used to decide *live
emulator run vs. skip* from whether a git-ignored build artifact happened to
exist in the working tree, so `python3 -m unittest discover -s
tools/gba-playtest/tests` passed on a clean checkout and failed on a worktree
holding a stale (or concurrently rebuilding) ROM -- six release save-compat
fingerprint failures that say nothing about the commit under test. The fix is
tests/host_mode.py: an explicit mode, never artifact timing.

What is proven here:

* strict, explicit env parsing (default off, unknown value refused);
* every Category B (live) TestCase is registered AND guarded, and no
  unregistered live entry point exists in the live modules;
* in host-only mode a live class skips BEFORE any existence probe -- even
  when the artifact materializes exactly when it would be probed, and even
  when it appears between two runs (concurrent build);
* normal mode is unchanged: the same class still probes and still captures;
* a hermetic staged worktree (TemporaryDirectory) holding stale, mismatched
  debug/release/legacy ROM-shaped, ELF and save artifacts at the exact paths
  the suite looks at: host-only skips all nine live classes, exits 0, and
  leaves every staged file byte-, size- and mtime-identical (nothing deleted,
  nothing rewritten), while the same tree in normal mode really opens the
  stale ROM and fails loudly.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
PLAYTEST_DIR = TESTS_DIR.parent
for _extra in (str(PLAYTEST_DIR), str(TESTS_DIR)):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

import gba_playtest  # noqa: E402
import host_mode  # noqa: E402

REPO_ROOT = host_mode.REPO_ROOT

# Stale artifacts staged into the hermetic worktree copy: exactly the paths
# this suite (and modern.mk) look at, including the git-ignored ones a local
# `verify --jobs 2` build gate rewrites underneath a running host gate.
_STAGED_ARTIFACT_RELATIVE_PATHS = (
    "fireemblem8.gba",
    "build/expansion-modern/debug/aapcs/fireemblem8.gba",
    "build/expansion-modern/release/aapcs/fireemblem8.gba",
    "build/expansion-modern/debug/aapcs/fireemblem8.elf",
    "build/expansion-modern/release/aapcs/fireemblem8.elf",
    "build/expansion-modern/debug/aapcs/debugtools-fixtures/debugtools-current.sav",
)

# A repository ROM/ELF path may only be constructed in host_mode.py.
_ROM_PATH_CONSTRUCTION_RE = re.compile(r"REPO_ROOT[^#\n]*fireemblem8\.(gba|elf)")
_HOST_MODE_ROM_USE_RE = re.compile(r"host_mode\.(modern_rom|modern_elf|LIVE_ROMS|LIVE_ARTIFACTS)")


def _run_case(test_class) -> unittest.TestResult:
    """Run one TestCase class in-process and return its raw result."""
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
    result = unittest.TestResult()
    suite.run(result)
    return result


def _host_only(value="1"):
    return mock.patch.dict(os.environ, {host_mode.ENV_VAR: value})


def _normal_mode():
    environ = dict(os.environ)
    environ.pop(host_mode.ENV_VAR, None)
    return mock.patch.dict(os.environ, environ, clear=True)


def _poisoned_capture():
    """Any live capture attempt becomes a loud, attributable failure."""
    return mock.patch.object(
        gba_playtest,
        "capture",
        side_effect=AssertionError(
            "gba_playtest.capture() was reached in host-only mode: a live "
            "ROM integration test is not guarded by tests/host_mode.py"
        ),
    )


def _fingerprint(path: Path):
    stat = path.stat()
    return (
        hashlib.sha256(path.read_bytes()).hexdigest(),
        stat.st_size,
        stat.st_mtime_ns,
    )


class HostOnlyEnvContractTests(unittest.TestCase):
    """The mode is a strict, explicit boolean -- never inferred."""

    def test_unset_defaults_to_normal_mode(self):
        self.assertFalse(host_mode.host_only_enabled({}))

    def test_true_vocabulary_covers_case_and_surrounding_whitespace(self):
        for raw in ("1", "true", "TRUE", "Yes", "on", "  1  "):
            with self.subTest(raw=raw):
                self.assertTrue(
                    host_mode.host_only_enabled({host_mode.ENV_VAR: raw})
                )

    def test_false_vocabulary_keeps_normal_mode(self):
        for raw in ("", "0", "false", "No", "OFF"):
            with self.subTest(raw=raw):
                self.assertFalse(
                    host_mode.host_only_enabled({host_mode.ENV_VAR: raw})
                )

    def test_unrecognized_value_is_refused_never_guessed(self):
        for raw in ("maybe", "2", "host-only", "y"):
            with self.subTest(raw=raw):
                with self.assertRaises(RuntimeError) as ctx:
                    host_mode.host_only_enabled({host_mode.ENV_VAR: raw})
                self.assertIn(host_mode.ENV_VAR, str(ctx.exception))

    def test_guard_skips_only_in_host_only_mode(self):
        with _host_only():
            with self.assertRaises(unittest.SkipTest):
                host_mode.guard("probe")
        with _normal_mode():
            self.assertIsNone(host_mode.guard("probe"))

    def test_skip_reason_names_the_gates_that_own_live_coverage(self):
        reason = host_mode.skip_reason("probe")
        self.assertIn("host-only mode", reason)
        self.assertIn("expansion-modern-linker-check", reason)
        self.assertIn("expansion-modern-itemexpansion-check", reason)


class HostOnlyClassificationTests(unittest.TestCase):
    """Category A vs. Category B is explicit, complete and enforced."""

    def test_every_registered_live_class_exists_and_is_guarded(self):
        for module_name, class_name in host_mode.LIVE_TEST_CLASSES:
            with self.subTest(module=module_name, cls=class_name):
                module = importlib.import_module(module_name)
                test_class = getattr(module, class_name)
                self.assertTrue(issubclass(test_class, unittest.TestCase))
                self.assertTrue(
                    getattr(test_class, "is_live_artifact_testcase", False),
                    f"{module_name}.{class_name} is registered as live but is "
                    f"not decorated with host_mode.live_artifact_testcase",
                )

    def test_registered_live_classes_skip_in_host_only_mode(self):
        for module_name, class_name in host_mode.LIVE_TEST_CLASSES:
            with self.subTest(module=module_name, cls=class_name):
                module = importlib.import_module(module_name)
                test_class = getattr(module, class_name)
                with _host_only(), _poisoned_capture():
                    result = _run_case(test_class)
                self.assertEqual(result.errors, [])
                self.assertEqual(result.failures, [])
                self.assertEqual(result.testsRun, 0)
                self.assertTrue(result.skipped)
                for _test, reason in result.skipped:
                    self.assertIn("host-only mode", reason)

    def test_live_modules_have_no_unregistered_live_entry_point(self):
        """Run EVERY class of the live modules in host-only mode with a
        poisoned capture: an unregistered/unguarded live test would reach
        libmGBA and fail loudly instead of hiding behind an artifact check."""
        registered = {f"{m}.{c}" for m, c in host_mode.LIVE_TEST_CLASSES}
        for module_name in host_mode.LIVE_TEST_MODULES:
            module = importlib.import_module(module_name)
            suite = unittest.defaultTestLoader.loadTestsFromModule(module)
            with _host_only(), _poisoned_capture():
                result = unittest.TestResult()
                suite.run(result)
            with self.subTest(module=module_name):
                # Attribute precisely: only a *poisoned capture* traceback is
                # this contract failing (an unrelated red test in the same
                # module must not be reported here).
                for test, trace in result.errors + result.failures:
                    self.assertNotIn(
                        "was reached in host-only mode", trace,
                        f"{test} reached a live capture in host-only mode: it "
                        f"is a live test that is not guarded by host_mode",
                    )
                for test, reason in result.skipped:
                    if "host-only mode" in reason:
                        self.assertTrue(
                            any(name in str(test) for name in registered),
                            f"{test} skipped as live but is not registered in "
                            f"host_mode.LIVE_TEST_CLASSES",
                        )

    def test_category_a_tests_still_run_in_host_only_mode(self):
        """Pure host/schema classes inside live modules keep running: the fix
        must not degrade into a blanket suite-level skip."""
        cases = (
            ("test_new_game_scenario", "NewGameScenarioFilesTests"),
            ("test_save_load_scenario", "SaveLoadScenarioFilesTests"),
            ("test_tools_scenario", "ToolsReleaseNegativeFilesTests"),
            ("test_savesuspend_resume_scenario", "SavesuspendResumeScenarioFilesTests"),
        )
        for module_name, class_name in cases:
            with self.subTest(module=module_name, cls=class_name):
                module = importlib.import_module(module_name)
                with _host_only(), _poisoned_capture():
                    result = _run_case(getattr(module, class_name))
                self.assertGreater(result.testsRun, 0)
                self.assertEqual(result.errors, [])
                self.assertEqual(result.failures, [])
                self.assertEqual(result.skipped, [])

    def test_repository_rom_paths_are_only_built_in_host_mode(self):
        offenders = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            if path.name in ("host_mode.py", Path(__file__).name):
                continue
            if _ROM_PATH_CONSTRUCTION_RE.search(path.read_text(encoding="utf-8")):
                offenders.append(path.name)
        self.assertEqual(
            offenders, [],
            "repository ROM/ELF paths must come from tests/host_mode.py so a "
            "single contract owns every artifact-dependent test",
        )

    def test_modules_using_repository_roms_are_registered_as_live(self):
        registered_modules = set(host_mode.LIVE_TEST_MODULES)
        for path in sorted(TESTS_DIR.glob("test_*.py")):
            if path.name == Path(__file__).name:
                continue
            if _HOST_MODE_ROM_USE_RE.search(path.read_text(encoding="utf-8")):
                with self.subTest(module=path.stem):
                    self.assertIn(
                        path.stem, registered_modules,
                        f"{path.stem} consumes a repository ROM but is not "
                        f"registered in host_mode.LIVE_TEST_CLASSES",
                    )


class HostOnlyCentralGateTests(unittest.TestCase):
    """The central choke points behave identically for every live test."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="gba-playtest-host-only-")
        self.addCleanup(self._tmpdir.cleanup)
        self.tmp = Path(self._tmpdir.name)

    def _appearing_rom(self, target: Path):
        """A ROM path whose very first existence probe materializes the file,
        modelling a concurrent build finishing mid-run."""
        rom = mock.MagicMock(spec=Path)

        def _exists():
            target.write_bytes(b"CONCURRENTLY-BUILT-ROM")
            return True

        rom.exists.side_effect = _exists
        rom.__str__.return_value = str(target)
        return rom

    def test_require_built_rom_skips_before_probing_in_host_only_mode(self):
        target = self.tmp / "appears.gba"
        rom = self._appearing_rom(target)
        with _host_only():
            with self.assertRaises(unittest.SkipTest):
                host_mode.require_built_rom(rom, "modern debug ROM")
        rom.exists.assert_not_called()
        self.assertFalse(
            target.exists(),
            "host-only mode must not probe the artifact at all",
        )

    def test_require_built_rom_probes_normally_in_normal_mode(self):
        target = self.tmp / "appears.gba"
        rom = self._appearing_rom(target)
        with _normal_mode():
            host_mode.require_built_rom(rom, "modern debug ROM")
        rom.exists.assert_called_once()
        self.assertTrue(target.exists())

    def test_require_built_rom_still_skips_when_absent_in_normal_mode(self):
        missing = self.tmp / "not-built.gba"
        with _normal_mode():
            with self.assertRaises(unittest.SkipTest) as ctx:
                host_mode.require_built_rom(missing, "modern debug ROM")
        self.assertIn("not built", str(ctx.exception))

    def test_capture_live_or_skip_is_defense_in_depth(self):
        rom = self.tmp / "stale.gba"
        rom.write_bytes(b"STALE")
        with _host_only(), _poisoned_capture():
            with self.assertRaises(unittest.SkipTest):
                host_mode.capture_live_or_skip(rom, object(), label="probe")

    def test_backend_unavailable_still_skips_in_normal_mode(self):
        rom = self.tmp / "stale.gba"
        rom.write_bytes(b"STALE")
        error = gba_playtest.PlaytestError("cannot find -lmgba")
        with _normal_mode(), mock.patch.object(
            gba_playtest, "capture", side_effect=error
        ):
            with self.assertRaises(unittest.SkipTest):
                host_mode.capture_live_or_skip(rom, object(), label="probe")

    def test_other_playtest_errors_still_fail_loudly_in_normal_mode(self):
        rom = self.tmp / "stale.gba"
        rom.write_bytes(b"STALE")
        error = gba_playtest.PlaytestError("no mGBA core recognizes ROM")
        with _normal_mode(), mock.patch.object(
            gba_playtest, "capture", side_effect=error
        ):
            with self.assertRaises(gba_playtest.PlaytestError):
                host_mode.capture_live_or_skip(rom, object(), label="probe")


class HostOnlyLiveClassArtifactTimingTests(unittest.TestCase):
    """A real live TestCase family (the save-compat factory) against staged
    artifacts: host-only never probes, normal mode still does."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="gba-playtest-host-only-")
        self.addCleanup(self._tmpdir.cleanup)
        self.tmp = Path(self._tmpdir.name)
        self.module = importlib.import_module("test_save_compat_scenarios")

    def test_live_class_skips_when_the_rom_appears_between_runs(self):
        rom = self.tmp / "fireemblem8.gba"
        test_class = self.module._make_test_class("modern-release", rom)

        with _host_only(), _poisoned_capture():
            absent = _run_case(test_class)
        self.assertEqual(absent.testsRun, 0)
        self.assertTrue(absent.skipped)

        # A concurrent build lands a stale ROM at the expected path mid-run.
        rom.write_bytes(b"STALE-CONCURRENTLY-BUILT-ROM")
        before = _fingerprint(rom)

        with _host_only(), _poisoned_capture():
            present = _run_case(test_class)
        self.assertEqual(present.errors, [])
        self.assertEqual(present.failures, [])
        self.assertEqual(present.testsRun, 0)
        for _test, reason in present.skipped:
            self.assertIn("host-only mode", reason)
        self.assertEqual(
            _fingerprint(rom), before,
            "host-only mode must leave a staged artifact byte-, size- and "
            "mtime-identical",
        )

    def test_normal_mode_still_captures_against_the_same_staged_rom(self):
        rom = self.tmp / "fireemblem8.gba"
        rom.write_bytes(b"STALE-CONCURRENTLY-BUILT-ROM")
        test_class = self.module._make_test_class("modern-release", rom)
        captured = []

        def _fake_capture(rom_path, scenario, sram_image=None, retries=0):
            captured.append(Path(str(rom_path)))
            raise gba_playtest.PlaytestError("no mGBA core recognizes ROM")

        with _normal_mode(), mock.patch.object(
            gba_playtest, "capture", side_effect=_fake_capture
        ):
            result = _run_case(test_class)

        self.assertTrue(captured, "normal mode must still attempt a live capture")
        self.assertEqual(captured[0], rom)
        self.assertTrue(result.errors or result.failures)
        self.assertEqual(
            [reason for _t, reason in result.skipped if "host-only" in reason], []
        )


class HostOnlyStagedWorktreeSubprocessTests(unittest.TestCase):
    """End-to-end: the exact CI host command in a hermetic worktree copy that
    is deliberately full of stale, mismatched artifacts."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="gba-playtest-staged-tree-")
        cls.tree = Path(cls._tmpdir.name)
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        shutil.copytree(
            REPO_ROOT / "tools" / "gba-playtest",
            cls.tree / "tools" / "gba-playtest",
            ignore=ignore,
        )
        shutil.copytree(
            REPO_ROOT / "scripts" / "modernize",
            cls.tree / "scripts" / "modernize",
            ignore=ignore,
        )
        # Issue #18 integration: scripts/modernize/expansion_config.py (and,
        # transitively, save_format_tool.py/sram_fixture.py, which the
        # save/suspend-resume live test classes below import) now imports
        # scripts.localization.schema as the single source of truth for
        # locale ids/counts, so this hermetic staged tree must carry that
        # package too or every live class import fails with
        # ModuleNotFoundError before host-only mode even gets a chance to
        # skip it -- a staged-tree gap, not a real host-only-mode defect.
        shutil.copytree(
            REPO_ROOT / "scripts" / "localization",
            cls.tree / "scripts" / "localization",
            ignore=ignore,
        )
        shutil.copy2(REPO_ROOT / "config.mk", cls.tree / "config.mk")
        cls.staged = []
        for index, relative in enumerate(_STAGED_ARTIFACT_RELATIVE_PATHS):
            path = cls.tree / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            # ROM-shaped (large enough to carry a GBA header) but
            # deliberately mismatched content: if any live test ever ran, it
            # would fail loudly instead of silently passing.
            path.write_bytes((b"STALE-MISMATCHED-ARTIFACT-" + bytes([index])) * 64)
            cls.staged.append(path)

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def _run_live_classes(self, host_only: bool, targets=None):
        environment = dict(os.environ)
        if host_only:
            environment[host_mode.ENV_VAR] = "1"
        else:
            environment.pop(host_mode.ENV_VAR, None)
        if targets is None:
            targets = [f"{m}.{c}" for m, c in host_mode.LIVE_TEST_CLASSES]
        return subprocess.run(
            [sys.executable, "-m", "unittest", "-v"] + list(targets),
            cwd=str(self.tree / "tools" / "gba-playtest" / "tests"),
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_host_only_skips_every_live_class_and_never_touches_an_artifact(self):
        before = {path: _fingerprint(path) for path in self.staged}
        result = self._run_live_classes(host_only=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            f"OK (skipped={len(host_mode.LIVE_TEST_CLASSES)})", result.stdout
        )
        self.assertIn("Ran 0 tests", result.stdout)
        for module_name, class_name in host_mode.LIVE_TEST_CLASSES:
            self.assertIn(f"{module_name}.{class_name}", result.stdout)
        self.assertNotIn("no mGBA core recognizes ROM", result.stdout)
        for path in self.staged:
            self.assertTrue(path.is_file(), f"host-only mode deleted {path}")
            self.assertEqual(
                _fingerprint(path), before[path],
                f"host-only mode modified {path}",
            )

    def test_normal_mode_in_the_same_tree_really_opens_the_stale_rom(self):
        before = {path: _fingerprint(path) for path in self.staged}
        result = self._run_live_classes(
            host_only=False, targets=["test_combat_scenario.CombatRuntimeTests"]
        )
        self.assertNotIn("host-only mode", result.stdout)
        self.assertNotIn("not built", result.stdout)
        # Either the live capture ran against the stale ROM and failed loudly
        # (the normal-mode contract: artifact present -> live run), or this
        # environment has no libmGBA at all and says so explicitly.
        if "libmGBA integration skipped explicitly" in result.stdout:
            self.assertEqual(result.returncode, 0, result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("capture_live_or_skip", result.stdout)
        for path in self.staged:
            self.assertEqual(_fingerprint(path), before[path])


if __name__ == "__main__":
    unittest.main()
