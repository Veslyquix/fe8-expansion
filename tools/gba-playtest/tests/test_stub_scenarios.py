"""Issue #13 closure: the combat and save schema-ready stubs are GONE.

Both `combat` and `save` are no longer disabled placeholders. They are now
real, enabled runtime scenarios:
  - tools/gba-playtest/scenarios/combat.json -- the Chapter 4 scripted
    FIGHT(CHARACTER_ARTUR, ...) resolved by the real battle engine
    (Event3F_ScriptBattle): the target enemy's curHP goes 15->0 at the
    SCRIPT_BATTLE opcode, then the unit is removed (death).
  - tools/gba-playtest/scenarios/save-load.json -- a genuine normal
    SaveMenu RESTART -> PostSaveMenuHandler -> ReadGameSave slot 0 load, proven
    by the playthroughIdentifier/chapterModeIndex discriminants going
    1 (created) -> 0 (soft-reset cleared) -> 1 (loaded).
See reports/gba_playtest_issue13_closure.md and modern.mk's
expansion-modern-combat-check / expansion-modern-saveload-check gates.

This test guards the closure: NO *.stub.json may remain, and nothing in the
harness may treat a disabled placeholder as a passing scenario.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAYTEST_DIR = REPO_ROOT / "tools" / "gba-playtest"
SCENARIOS_DIR = PLAYTEST_DIR / "scenarios"
STUBS_DIR = SCENARIOS_DIR / "stubs"

sys.path.insert(0, str(PLAYTEST_DIR))

import gba_playtest  # noqa: E402


class NoStubsRemainTests(unittest.TestCase):
    def test_no_stub_scenarios_exist_anywhere(self):
        remaining = sorted(p.name for p in SCENARIOS_DIR.rglob("*.stub.json"))
        self.assertEqual(
            remaining,
            [],
            "issue #13 closure removed every disabled stub; found: " f"{remaining}",
        )

    def test_the_former_combat_and_save_stubs_are_gone(self):
        self.assertFalse((STUBS_DIR / "combat.stub.json").exists())
        self.assertFalse((STUBS_DIR / "save.stub.json").exists())

    def test_no_committed_scenario_is_disabled(self):
        """Every committed scenario (excluding none) must be enabled -- a
        disabled scenario surviving here would be a stub by another name."""
        disabled = []
        for path in sorted(SCENARIOS_DIR.rglob("*.json")):
            scenario = gba_playtest.load_scenario(path)
            if scenario.disabled:
                disabled.append(path.name)
        self.assertEqual(
            disabled, [], f"unexpected disabled scenario(s): {disabled}"
        )


class FormerlyStubbedScenariosAreEnabledTests(unittest.TestCase):
    """The two scenarios that used to be stubs now parse as enabled, with
    real semantic (never framebuffer-only) checkpoints."""

    CASES = {
        "combat.json": {
            "name": "combat",
            # target enemy gUnitArrayRed[0].curHP (0x0202eba7) probed
            "must_probe": 0x0202EBA7,
        },
        "save-load.json": {
            "name": "save-load",
            # gPlaySt.chapterModeIndex (0x020210bf) discriminant probed
            "must_probe": 0x020210BF,
        },
    }

    def test_each_parses_enabled_with_checkpoints(self):
        for filename, spec in self.CASES.items():
            with self.subTest(filename=filename):
                path = SCENARIOS_DIR / filename
                self.assertTrue(path.exists(), f"missing scenario: {path}")
                scenario = gba_playtest.load_scenario(path)
                self.assertEqual(scenario.name, spec["name"])
                self.assertFalse(scenario.disabled)
                self.assertIsNone(scenario.blocker)
                self.assertGreater(len(scenario.checkpoints), 0)

    def test_each_proves_semantic_state_not_framebuffer_only(self):
        for filename, spec in self.CASES.items():
            with self.subTest(filename=filename):
                scenario = gba_playtest.load_scenario(SCENARIOS_DIR / filename)
                # No checkpoint relies on a framebuffer hash; every one
                # carries at least one RAM probe or an SRAM hash.
                for checkpoint in scenario.checkpoints:
                    self.assertFalse(
                        checkpoint.framebuffer,
                        f"{filename} checkpoint {checkpoint.name!r} must not be "
                        "framebuffer-based (semantic RAM/SRAM proof only)",
                    )
                    self.assertTrue(
                        checkpoint.probes or checkpoint.sram_hash,
                        f"{filename} checkpoint {checkpoint.name!r} must carry a "
                        "semantic probe or SRAM hash",
                    )
                probed = {
                    probe.address
                    for checkpoint in scenario.checkpoints
                    for probe in checkpoint.probes
                }
                self.assertIn(spec["must_probe"], probed)

    def test_each_has_a_committed_debug_fingerprint(self):
        fingerprints = {
            "combat.json": "combat-modern-debug.json",
            "save-load.json": "save-load-modern-debug.json",
        }
        for filename, fp_name in fingerprints.items():
            with self.subTest(filename=filename):
                fp_path = PLAYTEST_DIR / "fingerprints" / fp_name
                self.assertTrue(fp_path.exists(), f"missing fingerprint: {fp_path}")
                fingerprint = gba_playtest.validate_fingerprint(
                    json.loads(fp_path.read_text(encoding="utf-8")), str(fp_path)
                )
                self.assertEqual(
                    fingerprint["scenario"],
                    gba_playtest.load_scenario(SCENARIOS_DIR / filename).name,
                )


if __name__ == "__main__":
    unittest.main()
