"""Issue #11 closure: live prep-screen SELECT+B debug-hotkey positive proof.

Scenario:    tools/gba-playtest/scenarios/debugtools-ch4-prep-positive-modern-debug.json
Fingerprint: tools/gba-playtest/fingerprints/debugtools-ch4-prep-positive-modern-debug.json

Boots the debug-only "Fast Boot: Ch4 Prep" launcher, traverses the Chapter 4
world map (L cursor-jump + A node-confirm), skips the beginning event/scripted
battle to the real CALL(EventScr_CommonPrep) PREP opcode, navigates the prep
at-menu to rest gProcScr_SALLYCURSOR in PrepScreenProc_MapIdle (proc_idleCb
== 0x080905d1), and fires the SELECT+B prep hotkey. Proves
gDebugToolsProbe.prepScreenObservedCount (0x02031854) goes 0 -> 1, the hub
opens (hubOpenCount 0x02031818 1 -> 2, sHubActive 0x02031614 0 -> 1), the hub
reentrancy is idempotent (a 2nd SELECT+B leaves hubOpenCount at 2), and prep
stays live (gPlaySt.chapterStateBits 0x020210b8 == 0x10) after the hub closes.
This is the live prep-screen arrival that was an explicit issue #11 residual;
it now runs as the debug branch of expansion-modern-debugtools-prep-check.
Debug-only: the launcher and hotkey are compiled out of a release build.
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
NAME = "debugtools-ch4-prep-positive-modern-debug"
SCENARIO_PATH = SCENARIOS_DIR / f"{NAME}.json"
FINGERPRINT_PATH = FINGERPRINTS_DIR / f"{NAME}.json"
DEBUG_ROM = REPO_ROOT / "build" / "expansion-modern" / "debug" / "aapcs" / "fireemblem8.gba"

PREP_FLAG = 0x020210B8        # gPlaySt.chapterStateBits (PLAY_FLAG_PREPSCREEN=0x10)
PREP_OBS = 0x02031854        # gDebugToolsProbe.prepScreenObservedCount
HUB_OPEN = 0x02031818        # gDebugToolsProbe.hubOpenCount
MAPIDLE_IDLECB = 0x080905D1  # PrepScreenProc_MapIdle | Thumb bit

sys.path.insert(0, str(PLAYTEST_DIR))
import gba_playtest  # noqa: E402

_UNAVAILABLE_MARKERS = (
    "C compiler ",
    "mgba/core/core.h: No such file",
    "'mgba/core/core.h' file not found",
    "cannot find -lmgba",
    "library not found for -lmgba",
)


class PrepPositiveScenarioFilesTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCENARIO_PATH.exists(), f"missing scenario: {SCENARIO_PATH}")
        self.scenario = gba_playtest.load_scenario(SCENARIO_PATH)

    def test_scenario_parses_enabled(self):
        self.assertEqual(self.scenario.name, NAME)
        self.assertFalse(self.scenario.disabled)

    def test_checkpoint_names_and_order(self):
        names = [c.name for c in self.scenario.checkpoints]
        self.assertEqual(
            names,
            [
                "prep-mapidle-live-before-hotkey",
                "select-b-opens-hub-in-live-prep",
                "second-select-b-idempotent-and-return-to-prep",
                "prep-still-live-and-stable-longrun",
            ],
        )

    def test_input_includes_select_b_prep_hotkey(self):
        combo = gba_playtest.KEY_BITS["SELECT"] | gba_playtest.KEY_BITS["B"]
        masks = {frame.key_mask for frame in self.scenario.inputs}
        self.assertIn(combo, masks, "must include the SELECT+B prep hotkey")

    def test_hotkey_observation_and_reentrancy_are_semantic(self):
        by_name = {c.name: c for c in self.scenario.checkpoints}
        for c in self.scenario.checkpoints:
            self.assertFalse(c.framebuffer, f"{c.name} must not be framebuffer-based")
        before = {p.address: p.expected for p in by_name["prep-mapidle-live-before-hotkey"].probes}
        opened = {p.address: p.expected for p in by_name["select-b-opens-hub-in-live-prep"].probes}
        reentry = {
            p.address: p.expected
            for p in by_name["second-select-b-idempotent-and-return-to-prep"].probes
        }
        # In live prep MapIdle, hotkey not yet pressed.
        self.assertEqual(before[PREP_FLAG], "0x10")
        self.assertEqual(before[PREP_OBS], "0x00000000")
        # A proc probe reads gProcScr_SALLYCURSOR's proc_idleCb; its value
        # being PrepScreenProc_MapIdle|Thumb (0x080905d1) is what proves the
        # SELECT+B is consumed in the real MapIdle handler, not elsewhere.
        self.assertIn("0x080905d1", before.values())
        # SELECT+B increments prepScreenObservedCount 0 -> 1 and opens the hub.
        self.assertEqual(opened[PREP_OBS], "0x00000001")
        self.assertEqual(opened[HUB_OPEN], "0x00000002")
        self.assertEqual(opened[PREP_FLAG], "0x10")
        # Reentrancy: hubOpenCount stays 2 (idempotent), prep still live.
        self.assertEqual(reentry[HUB_OPEN], "0x00000002")
        self.assertEqual(reentry[PREP_FLAG], "0x10")

    def test_committed_fingerprint_matches(self):
        self.assertTrue(FINGERPRINT_PATH.exists(), f"missing: {FINGERPRINT_PATH}")
        fp = gba_playtest.validate_fingerprint(
            json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8")), str(FINGERPRINT_PATH)
        )
        self.assertEqual(fp["scenario"], NAME)
        self.assertEqual(len(fp["checkpoints"]), 4)


class PrepPositiveRuntimeTests(unittest.TestCase):
    def test_debug_rom_matches_committed_fingerprint(self):
        if not DEBUG_ROM.exists():
            raise unittest.SkipTest(f"modern debug ROM not built: {DEBUG_ROM}")
        scenario = gba_playtest.load_scenario(SCENARIO_PATH)
        expected = gba_playtest.validate_fingerprint(
            json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8")), str(FINGERPRINT_PATH)
        )
        try:
            actual = gba_playtest.capture(DEBUG_ROM, scenario)  # blank SRAM
        except gba_playtest.PlaytestError as exc:
            if any(m in str(exc) for m in _UNAVAILABLE_MARKERS):
                raise unittest.SkipTest(f"libmGBA integration skipped: {exc}") from exc
            raise
        differences = gba_playtest.compare_fingerprints(expected, actual, policy="behavior")
        self.assertEqual(differences, [], f"prep-positive: {differences}")


if __name__ == "__main__":
    unittest.main()
