"""Issue #11 closure: five shipped bounded tools driven LIVE from the map hub.

Scenario:    tools/gba-playtest/scenarios/debugtools-tools-modern-debug.json
Fingerprint: tools/gba-playtest/fingerprints/debugtools-tools-modern-debug.json
Release neg: tools/gba-playtest/scenarios/debugtools-tools-modern-release.json

Boots the debug-only Fast Boot: Chapter 2 map hub, then triggers each of the
five bounded tools from its real hub row and proves an asserted semantic state
effect plus a safe return to the hub -- all through relocation-independent
gDebugToolsProbe / gPlaySt / gBmSt scalars (never a pointer, framebuffer, or
SRAM-hash oracle):

  5 Unit Inspect/Edit -- inspect resolves Eirika (found, 16/16 HP); a separate
    confirm applies Heal-to-Full (unitHealTransactionCount 0 -> 1). Eirika is
    already full HP here, so the byte-exact wounded->full HP mutation is proven
    by the real-source host test (tests/c/debugtools_tools_driver.c); this
    scenario proves the confirmed-transaction postcondition fired live.
  6 Convoy Inspect/Edit -- inspect samples count 0; confirm adds an item
    (convoyAddTransactionCount 0 -> 1); a re-inspect shows the count rose 0 -> 1.
  7 Flag/Chapter -- inspect samples chapterIndex 2 and flag 0; confirm toggles
    the flag 0 -> 1 (debugFlagToggleCount 0 -> 1).
  8 RNG Inspect/Control -- inspect samples seed 0x0000ee77; confirm reseeds
    (rngReseedTransactionCount 0 -> 1); a re-inspect shows the seed changed.
  9 Save Compatibility/State Inspect -- read-only inspect classifies SRAM
    (SAVE_COMPAT_CURRENT, count 0 -> 1); its Back item never mutates (count
    stays 1).

Every submenu returns to the hub (hubOpenCount 2 -> 9), and after the hub
closes the map is still interactive (player cursor moves 0x06 -> 0x07). The
release sibling replays the same input and proves every gDebugToolsProbe field
stays 0 (hub/tools compiled out). Debug-only; probe-only (deterministic).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAYTEST_DIR = REPO_ROOT / "tools" / "gba-playtest"
SCENARIOS_DIR = PLAYTEST_DIR / "scenarios"
FINGERPRINTS_DIR = PLAYTEST_DIR / "fingerprints"
DEBUG_NAME = "debugtools-tools-modern-debug"
RELEASE_NAME = "debugtools-tools-modern-release"
DEBUG_SCENARIO = SCENARIOS_DIR / f"{DEBUG_NAME}.json"
DEBUG_FINGERPRINT = FINGERPRINTS_DIR / f"{DEBUG_NAME}.json"
RELEASE_SCENARIO = SCENARIOS_DIR / f"{RELEASE_NAME}.json"
RELEASE_FINGERPRINT = FINGERPRINTS_DIR / f"{RELEASE_NAME}.json"
DEBUG_ROM = REPO_ROOT / "build" / "expansion-modern" / "debug" / "aapcs" / "fireemblem8.gba"
RELEASE_ROM = REPO_ROOT / "build" / "expansion-modern" / "release" / "aapcs" / "fireemblem8.gba"

# debug gDebugToolsProbe (0x02031818) fields + registry sHubActive + gBmSt cursor
HUB_OPEN = 0x02031818
REG_COUNT = 0x0203181C
U_FOUND = 0x02031868
U_CURHP = 0x0203186C
U_MAXHP = 0x02031870
U_HEALTX = 0x02031874
CV_COUNT = 0x02031878
CV_ADDTX = 0x0203187C
CH_INDEX = 0x02031880
FLG_TX = 0x02031884
FLG_VAL = 0x02031888
RNG_SEED = 0x0203188C
RNG_TX = 0x02031890
SV_STATE = 0x02031894
SV_COUNT = 0x02031898
S_HUB = 0x02031614
CURSOR_X = 0x02021104

_POINTER_RANGES = (
    (0x02000000, 0x0203FFFF),
    (0x03000000, 0x03007FFF),
    (0x08000000, 0x0DFFFFFF),
    (0x0E000000, 0x0E00FFFF),
)

sys.path.insert(0, str(PLAYTEST_DIR))
import gba_playtest  # noqa: E402

_UNAVAILABLE_MARKERS = (
    "C compiler ",
    "mgba/core/core.h: No such file",
    "'mgba/core/core.h' file not found",
    "cannot find -lmgba",
    "library not found for -lmgba",
)


class ToolsScenarioFilesTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(DEBUG_SCENARIO.exists(), f"missing scenario: {DEBUG_SCENARIO}")
        self.scenario = gba_playtest.load_scenario(DEBUG_SCENARIO)

    def _cp(self, name):
        by_name = {c.name: c for c in self.scenario.checkpoints}
        self.assertIn(name, by_name, f"missing checkpoint {name}")
        return {p.address: p.expected for p in by_name[name].probes}

    def test_scenario_parses_enabled_probe_only(self):
        self.assertEqual(self.scenario.name, DEBUG_NAME)
        self.assertFalse(self.scenario.disabled)
        for c in self.scenario.checkpoints:
            self.assertFalse(c.framebuffer, f"{c.name} must be probe-only (no framebuffer)")
            self.assertFalse(c.sram_hash, f"{c.name} must be probe-only (no sram_hash)")
            self.assertTrue(c.probes, f"{c.name} must carry probes")

    def test_checkpoint_names_and_order(self):
        self.assertEqual(
            [c.name for c in self.scenario.checkpoints],
            [
                "hub-open",
                "unit-inspected",
                "unit-heal-confirmed",
                "convoy-inspected",
                "convoy-add-confirmed",
                "convoy-reinspected-count-rose",
                "flag-inspected",
                "flag-toggle-confirmed",
                "rng-inspected",
                "rng-reseed-confirmed",
                "rng-reinspected-seed-changed",
                "save-inspected",
                "save-back-readonly-unchanged",
                "hub-closed-map-interactive",
            ],
        )

    def test_hub_open_registers_all_nine_tools(self):
        c = self._cp("hub-open")
        self.assertEqual(c[HUB_OPEN], "0x00000002")
        self.assertEqual(c[S_HUB], "0x01")
        self.assertEqual(c[REG_COUNT], "0x00000009")
        # every mutating transaction counter starts at zero
        for addr in (U_HEALTX, CV_ADDTX, FLG_TX, RNG_TX, SV_COUNT):
            self.assertEqual(c[addr], "0x00000000")

    def test_unit_inspect_then_confirm(self):
        insp = self._cp("unit-inspected")
        self.assertEqual(insp[U_FOUND], "0x00000001")
        self.assertEqual(insp[U_CURHP], "0x00000010")
        self.assertEqual(insp[U_MAXHP], "0x00000010")
        self.assertEqual(insp[U_HEALTX], "0x00000000")
        self.assertEqual(insp[S_HUB], "0x00", "inspect opens the confirm submenu (hub closed)")
        conf = self._cp("unit-heal-confirmed")
        self.assertEqual(conf[U_HEALTX], "0x00000001", "heal only after explicit confirm")
        self.assertEqual(conf[HUB_OPEN], "0x00000003", "submenu returns safely to the hub")

    def test_convoy_inspect_confirm_then_count_rose(self):
        self.assertEqual(self._cp("convoy-inspected")[CV_COUNT], "0x00000000")
        self.assertEqual(self._cp("convoy-add-confirmed")[CV_ADDTX], "0x00000001")
        rose = self._cp("convoy-reinspected-count-rose")
        self.assertEqual(rose[CV_COUNT], "0x00000001", "re-inspect proves the add's effect")

    def test_flag_inspect_then_toggle(self):
        insp = self._cp("flag-inspected")
        self.assertEqual(insp[CH_INDEX], "0x00000002")
        self.assertEqual(insp[FLG_VAL], "0x00000000")
        conf = self._cp("flag-toggle-confirmed")
        self.assertEqual(conf[FLG_TX], "0x00000001")
        self.assertEqual(conf[FLG_VAL], "0x00000001", "flag value flips 0 -> 1")

    def test_rng_inspect_reseed_then_seed_changed(self):
        seed_in = self._cp("rng-inspected")[RNG_SEED]
        self.assertEqual(self._cp("rng-reseed-confirmed")[RNG_TX], "0x00000001")
        seed_after = self._cp("rng-reinspected-seed-changed")[RNG_SEED]
        self.assertNotEqual(seed_after, seed_in, "reseed must change the sampled seed")

    def test_save_inspect_is_read_only(self):
        insp = self._cp("save-inspected")
        self.assertEqual(insp[SV_COUNT], "0x00000001")
        back = self._cp("save-back-readonly-unchanged")
        self.assertEqual(back[SV_COUNT], "0x00000001", "read-only: Back must not mutate")
        self.assertEqual(back[HUB_OPEN], "0x00000009")

    def test_map_interactive_after_hub_closes(self):
        c = self._cp("hub-closed-map-interactive")
        self.assertEqual(c[S_HUB], "0x00", "hub fully closed")
        self.assertEqual(c[CURSOR_X], "0x07", "player cursor responds to input (0x06 -> 0x07)")

    def test_no_probe_asserts_a_relocated_pointer_value(self):
        for c in self.scenario.checkpoints:
            for p in c.probes:
                if p.expected is None or p.size < 4:
                    continue
                value = int(p.expected, 16)
                self.assertFalse(
                    any(lo <= value <= hi for lo, hi in _POINTER_RANGES),
                    f"{c.name} probe 0x{p.address:08x} asserts pointer-range value {p.expected}",
                )

    def test_committed_fingerprint_matches(self):
        fp = gba_playtest.validate_fingerprint(
            json.loads(DEBUG_FINGERPRINT.read_text(encoding="utf-8")), str(DEBUG_FINGERPRINT)
        )
        self.assertEqual(fp["scenario"], DEBUG_NAME)
        self.assertEqual(len(fp["checkpoints"]), 14)


class ToolsReleaseNegativeFilesTests(unittest.TestCase):
    def test_release_sibling_asserts_all_zero(self):
        scenario = gba_playtest.load_scenario(RELEASE_SCENARIO)
        self.assertEqual(scenario.name, RELEASE_NAME)
        any_probe = False
        for c in scenario.checkpoints:
            self.assertFalse(c.framebuffer)
            for p in c.probes:
                any_probe = True
                self.assertEqual(
                    p.expected, "0x00000000",
                    f"release {c.name} probe 0x{p.address:08x} must be zero (tools compiled out)",
                )
        self.assertTrue(any_probe, "release sibling must carry all-zero probes")


class ToolsRuntimeTests(unittest.TestCase):
    def _run(self, rom, scenario_path, fingerprint_path, name):
        if not rom.exists():
            raise unittest.SkipTest(f"modern ROM not built: {rom}")
        scenario = gba_playtest.load_scenario(scenario_path)
        expected = gba_playtest.validate_fingerprint(
            json.loads(fingerprint_path.read_text(encoding="utf-8")), str(fingerprint_path)
        )
        try:
            actual = gba_playtest.capture(rom, scenario)  # blank SRAM
        except gba_playtest.PlaytestError as exc:
            if any(m in str(exc) for m in _UNAVAILABLE_MARKERS):
                raise unittest.SkipTest(f"libmGBA integration skipped: {exc}") from exc
            raise
        differences = gba_playtest.compare_fingerprints(expected, actual, policy="behavior")
        self.assertEqual(differences, [], f"{name}: {differences}")

    def test_debug_rom_matches_committed_fingerprint(self):
        self._run(DEBUG_ROM, DEBUG_SCENARIO, DEBUG_FINGERPRINT, DEBUG_NAME)

    def test_release_rom_stays_all_zero(self):
        self._run(RELEASE_ROM, RELEASE_SCENARIO, RELEASE_FINGERPRINT, RELEASE_NAME)


if __name__ == "__main__":
    unittest.main()
