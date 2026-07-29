"""Central, explicit host-only mode contract for the tools/gba-playtest suite.

Public contract (the ONLY supported switch, mirrored verbatim by
.github/workflows/build.yml `host-tests` and scripts/upstream_port/verify.py):

    GBA_PLAYTEST_HOST_ONLY=1 python3 -m unittest discover -s tools/gba-playtest/tests -v

Why this module exists (issue #10 / #13 integrated-harness defect): the
ROM-dependent tests in this suite used to decide *live emulator run vs. skip*
purely from whether a build artifact happened to exist in the working tree
(build/expansion-modern/<config>/aapcs/fireemblem8.gba, ./fireemblem8.gba).
build/ is git-ignored and user-owned, so that made the **host** gate a
function of local artifact timing rather than of an explicit mode: a clean CI
checkout skipped, while a local worktree holding a stale (or concurrently
rebuilding) ROM silently ran live captures against it and reported
fingerprint failures that say nothing about the commit under test. `python3
-m scripts.upstream_port verify --jobs 2` makes that strictly worse, because
its later build gates rewrite exactly those artifacts.

Contract:

* Host-only mode is decided ONLY by this environment variable -- never by the
  presence, absence, freshness, mtime or content of any artifact.
* In host-only mode every ROM-dependent / live-integration test raises
  unittest.SkipTest BEFORE it opens, stats, hashes or otherwise touches any
  ROM/ELF/save artifact, even when debug, release and legacy artifacts all
  exist, and even when one appears mid-run because a build is running
  concurrently.
* Normal mode (variable unset, or an explicit false value) keeps the previous
  behavior exactly: artifact present -> live run, artifact absent -> the same
  explicit skip as before.
* Live/runtime coverage is owned by the runtime + build gates
  (`make expansion-modern-linker-check`,
  `make expansion-modern-itemexpansion-check` -- build.yml `build` job and
  the last four of the ten scripts/upstream_port/verify.py gates), never by
  this host lane. Nothing here needs a fingerprint refresh or a `clean`.

Classification of every module under tools/gba-playtest/tests:

  Category A -- host-only safe, always runs (reads no repository ROM/ELF and
  consumes no pre-existing build artifact as an oracle): test_scenario,
  test_serialization, test_diagnostics, test_timeouts, test_retry_policy
  (mocked subprocesses + TemporaryDirectory ROM stubs), test_sram_fixture,
  test_sram_hash_normalization, test_save_compat_gate_safety,
  test_stub_scenarios, test_pointer_oracle_audit, test_baseline_no_autorefresh,
  test_debugtools_registry (real project C sources compiled for the *host*),
  test_backend_integration (libmGBA against a homebrew ROM generated into a
  TemporaryDirectory), test_host_only_mode (this contract) and
  test_debugtools_sram_fixture. The last one is host-only safe but is the one
  Category A module that writes into build/: it regenerates its own
  deterministic debugtools SRAM fixture from source through the
  toolchain-free Make recipe it is testing. That is source-derived and
  mode-independent (identical in host-only and in normal mode); it never
  reads a ROM/ELF and never treats a pre-existing artifact as an oracle.

  Category B -- ROM-dependent live integration, skipped in host-only mode.
  Registered in LIVE_TEST_CLASSES below; test_host_only_mode.py fails if a
  registered class is not guarded, or if a module builds a repository ROM
  path without being registered.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from typing import Mapping, Optional

ENV_VAR = "GBA_PLAYTEST_HOST_ONLY"

# Strict boolean vocabulary. Anything else is an error, never a silent
# fallback to normal (live) mode.
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"", "0", "false", "no", "off"})

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAYTEST_DIR = REPO_ROOT / "tools" / "gba-playtest"
MODERN_BUILD_ROOT = REPO_ROOT / "build" / "expansion-modern"
MODERN_ABI = "aapcs"
MODERN_CONFIGS = ("debug", "release")

if str(PLAYTEST_DIR) not in sys.path:
    sys.path.insert(0, str(PLAYTEST_DIR))

import gba_playtest  # noqa: E402


def modern_rom(config: str) -> Path:
    """Built modern ROM for a config -- the live-integration input."""
    return MODERN_BUILD_ROOT / config / MODERN_ABI / "fireemblem8.gba"


def modern_elf(config: str) -> Path:
    """Built modern ELF for a config. Never read by this suite; listed so the
    host-only regression can prove it is left untouched."""
    return MODERN_BUILD_ROOT / config / MODERN_ABI / "fireemblem8.elf"


LEGACY_ROM = REPO_ROOT / "fireemblem8.gba"

# Single source of truth for the ROM identities the live lane can consume.
# Keys are the fingerprint suffixes used by tools/gba-playtest/fingerprints.
LIVE_ROMS = {
    "legacy": LEGACY_ROM,
    "modern-debug": modern_rom("debug"),
    "modern-release": modern_rom("release"),
}

# Every repository build artifact a host-only run must leave byte-identical.
LIVE_ARTIFACTS = tuple(LIVE_ROMS.values()) + tuple(
    modern_elf(config) for config in MODERN_CONFIGS
)

# Backend/toolchain unavailability diagnostics that mean *this environment
# cannot run libmGBA at all* -- a legitimate, explicit skip in normal mode.
# (clang quotes the missing header, gcc does not.)
BACKEND_UNAVAILABLE_MARKERS = (
    "C compiler ",
    "mgba/core/core.h: No such file",
    "'mgba/core/core.h' file not found",
    "cannot find -lmgba",
    "library not found for -lmgba",
)

# Category B registry: (module name, TestCase class name).
LIVE_TEST_CLASSES = (
    ("test_combat_scenario", "CombatRuntimeTests"),
    ("test_new_game_scenario", "NewGameRuntimeTests"),
    ("test_prep_positive_scenario", "PrepPositiveRuntimeTests"),
    ("test_save_compat_scenarios", "SaveCompatScenarioTests_legacy"),
    ("test_save_compat_scenarios", "SaveCompatScenarioTests_modern_debug"),
    ("test_save_compat_scenarios", "SaveCompatScenarioTests_modern_release"),
    ("test_save_load_scenario", "SaveLoadRuntimeTests"),
    ("test_savesuspend_resume_scenario", "SavesuspendResumeRuntimeTests"),
    ("test_tools_scenario", "ToolsRuntimeTests"),
)

LIVE_TEST_MODULES = tuple(sorted({module for module, _ in LIVE_TEST_CLASSES}))


def host_only_enabled(environ: Optional[Mapping[str, str]] = None) -> bool:
    """Strict parse of GBA_PLAYTEST_HOST_ONLY; default (unset) is off.

    An unrecognized value raises instead of guessing: silently falling back to
    normal mode would re-introduce exactly the artifact-timing-controlled live
    run this contract removes.
    """
    source = os.environ if environ is None else environ
    raw = source.get(ENV_VAR)
    if raw is None:
        return False
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise RuntimeError(
        f"{ENV_VAR}={raw!r} is not a valid boolean. Use one of "
        f"{sorted(TRUE_VALUES)} for host-only mode or {sorted(FALSE_VALUES)} "
        f"for normal mode; an unrecognized value is refused rather than "
        f"silently running live ROM integration."
    )


def skip_reason(what: str) -> str:
    return (
        f"{ENV_VAR}=1 host-only mode: {what} is ROM-dependent live "
        f"integration, skipped before any ROM/ELF/save artifact is touched. "
        f"Live coverage belongs to the runtime/build gates "
        f"(make expansion-modern-linker-check / "
        f"expansion-modern-itemexpansion-check)."
    )


def guard(what: str) -> None:
    """Raise unittest.SkipTest in host-only mode.

    Call this BEFORE any artifact path is opened, stat-ed, hashed or handed to
    libmGBA -- including before any .exists() freshness probe.
    """
    if host_only_enabled():
        raise unittest.SkipTest(skip_reason(what))


def require_built_rom(rom, label: str) -> None:
    """The single place this suite may ask whether a repository ROM exists.

    Host-only mode is checked first, so the artifact is never probed at all;
    otherwise normal-mode behavior is unchanged (explicit skip when the ROM
    has not been built).
    """
    guard(label)
    if not rom.exists():
        raise unittest.SkipTest(f"{label} not built: {rom}")


def capture_live_or_skip(rom, scenario, sram_image=None, *, label: str, retries: int = 0):
    """gba_playtest.capture() against a *repository* ROM.

    Defense in depth: even if a live TestCase were to lose its class
    decorator, reaching a live capture in host-only mode skips instead of
    booting the emulator. Backend/toolchain unavailability keeps its existing
    explicit skip; every other PlaytestError still fails loudly.
    """
    guard(label)
    try:
        if sram_image is None:
            return gba_playtest.capture(rom, scenario, retries=retries)
        return gba_playtest.capture(rom, scenario, sram_image, retries=retries)
    except gba_playtest.PlaytestError as exc:
        if any(marker in str(exc) for marker in BACKEND_UNAVAILABLE_MARKERS):
            raise unittest.SkipTest(
                f"libmGBA integration skipped explicitly: {exc}"
            ) from exc
        raise


def live_artifact_testcase(reason: str):
    """Class decorator marking a TestCase as Category B (live integration).

    The host-only check wraps setUpClass, so it is evaluated at *run* time
    (not import time) and fires before any setUpClass/setUp body can touch an
    artifact.
    """

    def decorate(cls):
        previous_set_up_class = cls.setUpClass

        def _set_up_class(inner_cls):
            guard(reason)
            previous_set_up_class.__func__(inner_cls)

        cls.setUpClass = classmethod(_set_up_class)
        cls.host_only_skip_reason = reason
        cls.is_live_artifact_testcase = True
        return cls

    return decorate
