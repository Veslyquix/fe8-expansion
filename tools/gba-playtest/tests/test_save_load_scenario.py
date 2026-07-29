"""Issue #13 closure: deterministic clean-boot normal SAVE/LOAD round trip.

Scenario:    tools/gba-playtest/scenarios/save-load.json
Fingerprint: tools/gba-playtest/fingerprints/save-load-modern-debug.json

Reuses new-game.json's clean-boot SaveMenu New Game -> slot 0 write, then a
real A+B+SELECT+START soft reset (RAM reinitialized), then the top-level
SaveMenu RESTART item -> PostSaveMenuHandler -> ReadGameSave slot 0 (src/
savemenu.c) -- a genuine NORMAL game-save LOAD, distinct from Suspend/
ReadSuspendSave. Proven by the playthroughIdentifier (0x020210bc) and
chapterModeIndex (0x020210bf) discriminants going 1 (created) -> 0 (soft-reset
cleared) -> 1 (loaded) plus before/after whole-SRAM hashes. Debug-only: its
soft-reset input timing is debug-calibrated exactly as
savesuspend-resume-modern-debug.json is (see modern.mk's
expansion-modern-saveload-check). Uses the same deterministic pre-seeded
CURRENT-format SRAM fixture as new-game.json.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAYTEST_DIR = REPO_ROOT / "tools" / "gba-playtest"
SCENARIOS_DIR = PLAYTEST_DIR / "scenarios"
FINGERPRINTS_DIR = PLAYTEST_DIR / "fingerprints"
SCENARIO_PATH = SCENARIOS_DIR / "save-load.json"
FINGERPRINT_PATH = FINGERPRINTS_DIR / "save-load-modern-debug.json"

SLOT = 0x020210B0        # gPlaySt.gameSaveSlot
PLAYTHROUGH = 0x020210BC  # gPlaySt.playthroughIdentifier
MODE = 0x020210BF        # gPlaySt.chapterModeIndex

sys.path.insert(0, str(PLAYTEST_DIR))
sys.path.insert(0, str(PLAYTEST_DIR / "tests"))
import gba_playtest  # noqa: E402
import host_mode  # noqa: E402
import sram_fixture as sf  # noqa: E402

DEBUG_ROM = host_mode.modern_rom("debug")


class SaveLoadScenarioFilesTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCENARIO_PATH.exists(), f"missing scenario: {SCENARIO_PATH}")
        self.scenario = gba_playtest.load_scenario(SCENARIO_PATH)

    def test_scenario_parses_enabled(self):
        self.assertEqual(self.scenario.name, "save-load")
        self.assertFalse(self.scenario.disabled)
        self.assertIsNone(self.scenario.blocker)

    def test_checkpoint_names_and_order(self):
        names = [c.name for c in self.scenario.checkpoints]
        self.assertEqual(
            names,
            [
                "pre-write-empty-slots",
                "new-game-created",
                "post-soft-reset-reinit",
                "restart-load-complete",
            ],
        )

    def test_input_includes_the_soft_reset_combo(self):
        combo = (
            gba_playtest.KEY_BITS["A"]
            | gba_playtest.KEY_BITS["B"]
            | gba_playtest.KEY_BITS["SELECT"]
            | gba_playtest.KEY_BITS["START"]
        )
        masks = {frame.key_mask for frame in self.scenario.inputs}
        self.assertIn(combo, masks, "must include the A+B+SELECT+START soft reset")

    def test_load_is_proven_by_discriminant_transition(self):
        by_name = {c.name: c for c in self.scenario.checkpoints}
        created = {p.address: p.expected for p in by_name["new-game-created"].probes}
        reset = {p.address: p.expected for p in by_name["post-soft-reset-reinit"].probes}
        loaded = {p.address: p.expected for p in by_name["restart-load-complete"].probes}
        # 1 (created) -> 0 (soft-reset cleared) -> 1 (ReadGameSave restored)
        self.assertEqual(created[PLAYTHROUGH], "0x01")
        self.assertEqual(reset[PLAYTHROUGH], "0x00")
        self.assertEqual(loaded[PLAYTHROUGH], "0x01")
        self.assertEqual(created[MODE], "0x01")
        self.assertEqual(reset[MODE], "0x00")
        self.assertEqual(loaded[MODE], "0x01")
        self.assertEqual(loaded[SLOT], "0x00")

    def test_write_is_proven_by_sram_hash_change(self):
        by_name = {c.name: c for c in self.scenario.checkpoints}
        self.assertTrue(by_name["pre-write-empty-slots"].sram_hash)
        self.assertTrue(by_name["new-game-created"].sram_hash)

    def test_committed_fingerprint_matches(self):
        self.assertTrue(FINGERPRINT_PATH.exists(), f"missing: {FINGERPRINT_PATH}")
        fp = gba_playtest.validate_fingerprint(
            json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8")), str(FINGERPRINT_PATH)
        )
        self.assertEqual(fp["scenario"], "save-load")
        self.assertEqual(len(fp["checkpoints"]), 4)


@host_mode.live_artifact_testcase("save-load runtime coverage")
class SaveLoadRuntimeTests(unittest.TestCase):
    """Category B (tests/host_mode.py): host-only mode skips this class
    before the ROM is touched; normal mode is unchanged."""

    def test_debug_rom_matches_committed_fingerprint(self):
        host_mode.require_built_rom(DEBUG_ROM, "modern debug ROM")
        scenario = gba_playtest.load_scenario(SCENARIO_PATH)
        expected = gba_playtest.validate_fingerprint(
            json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8")), str(FINGERPRINT_PATH)
        )
        with tempfile.TemporaryDirectory(prefix="gba-playtest-save-load-test-") as tmp:
            fixture = sf.write_deterministic_current_fixture(Path(tmp) / "current.sav")
            actual = host_mode.capture_live_or_skip(
                DEBUG_ROM, scenario, fixture, label="save-load runtime coverage"
            )
        differences = gba_playtest.compare_fingerprints(expected, actual, policy="behavior")
        self.assertEqual(differences, [], f"save-load: {differences}")


if __name__ == "__main__":
    unittest.main()
