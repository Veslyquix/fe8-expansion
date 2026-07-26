"""Issue #13 closure: deterministic Chapter 4 scripted-combat capture.

Scenario:    tools/gba-playtest/scenarios/combat.json
Fingerprint: tools/gba-playtest/fingerprints/combat-modern-debug.json

Boots the debug-only "Fast Boot: Ch4 Prep" launcher from a clean (blank-SRAM)
boot, traverses the Chapter 4 world map, and reaches EventScr_Ch4_Beginning-
Scene's own FIGHT(CHARACTER_ARTUR, ...) tutorial battle. The target enemy
gUnitArrayRed[0]'s curHP (0x0202eba7) transitions 15 -> 0 at the SCRIPT_BATTLE
opcode (Event3F_ScriptBattle, the real battle engine -- proven by the P8 to
occur one opcode before the following KILL), then the unit's pCharacterData
(0x0202eb94) is cleared as it is removed. Exact pre/post HP plus death, all
via fixed EWRAM unit probes -- never framebuffer/timing. Debug-only: the
launcher is compiled out of a release build (see modern.mk's
expansion-modern-combat-check).
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
SCENARIO_PATH = SCENARIOS_DIR / "combat.json"
FINGERPRINT_PATH = FINGERPRINTS_DIR / "combat-modern-debug.json"
DEBUG_ROM = REPO_ROOT / "build" / "expansion-modern" / "debug" / "aapcs" / "fireemblem8.gba"

RED0_CHAR = 0x0202EB94  # gUnitArrayRed[0].pCharacterData
RED0_CURHP = 0x0202EBA7  # gUnitArrayRed[0].curHP

sys.path.insert(0, str(PLAYTEST_DIR))
import gba_playtest  # noqa: E402

_UNAVAILABLE_MARKERS = (
    "C compiler ",
    "mgba/core/core.h: No such file",
    "'mgba/core/core.h' file not found",
    "cannot find -lmgba",
    "library not found for -lmgba",
)


class CombatScenarioFilesTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCENARIO_PATH.exists(), f"missing scenario: {SCENARIO_PATH}")
        self.scenario = gba_playtest.load_scenario(SCENARIO_PATH)

    def test_scenario_parses_enabled(self):
        self.assertEqual(self.scenario.name, "combat")
        self.assertFalse(self.scenario.disabled)
        self.assertIsNone(self.scenario.blocker)

    def test_checkpoint_names_and_order(self):
        names = [c.name for c in self.scenario.checkpoints]
        self.assertEqual(
            names,
            [
                "enemy-alive-before-fight",
                "artur-scripted-fight-lethal-hit",
                "enemy-dead-removed-by-kill",
            ],
        )

    def test_proof_is_semantic_unit_hp_not_framebuffer(self):
        for c in self.scenario.checkpoints:
            self.assertFalse(c.framebuffer, f"{c.name} must not be framebuffer-based")
            self.assertTrue(c.probes, f"{c.name} must carry unit probes")
        by_name = {c.name: c for c in self.scenario.checkpoints}
        # curHP falls 15 -> 0 across the battle; then the unit is removed.
        before = {p.address: p.expected for p in by_name["enemy-alive-before-fight"].probes}
        hit = {p.address: p.expected for p in by_name["artur-scripted-fight-lethal-hit"].probes}
        dead = {p.address: p.expected for p in by_name["enemy-dead-removed-by-kill"].probes}
        self.assertEqual(before[RED0_CURHP], "0x0f")
        self.assertEqual(hit[RED0_CURHP], "0x00")
        self.assertEqual(dead[RED0_CHAR], "0x00000000")

    def test_committed_fingerprint_matches(self):
        self.assertTrue(FINGERPRINT_PATH.exists(), f"missing: {FINGERPRINT_PATH}")
        fp = gba_playtest.validate_fingerprint(
            json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8")), str(FINGERPRINT_PATH)
        )
        self.assertEqual(fp["scenario"], "combat")
        self.assertEqual(len(fp["checkpoints"]), 3)


class CombatRuntimeTests(unittest.TestCase):
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
        self.assertEqual(differences, [], f"combat: {differences}")


if __name__ == "__main__":
    unittest.main()
