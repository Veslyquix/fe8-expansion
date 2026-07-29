"""Issue #13 closure: deterministic clean-boot "New Game" creation.

Scenario: tools/gba-playtest/scenarios/new-game.json
Fingerprints: tools/gba-playtest/fingerprints/new-game-modern-{debug,release}.json

Shares savecompat-current.json's own shared A/START title cadence (frames
0..900), which that scenario's own committed evidence already proves reaches
the ordinary top-level Save Menu with no dialog. This scenario additionally
replays three ordinary A confirmations -- New Game, Easy, first empty save
slot -- each on whatever item the real menu already defaults the cursor to,
never a scripted cursor move or a raw memory write. It proves both that the
Select Mode/empty-slot-list screens are reached (framebuffer) and that a real
SaveMenuWriteNewGame/WriteGameSave-class SRAM write happened (a before/
after whole-SRAM hash change) leaving `gPlaySt.chapterIndex`/`faction` at
CHAPTER_L_PROLOGUE/FACTION_BLUE -- semantic state, not merely a menu screen.

Unlike savecompat-current.json (which only proves the compatibility gate is
reached), this is the first scenario in this harness to prove a full "New
Game" creation round trip end-to-end.
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
SCENARIO_PATH = SCENARIOS_DIR / "new-game.json"
FINGERPRINT_PATHS = {
    "debug": FINGERPRINTS_DIR / "new-game-modern-debug.json",
    "release": FINGERPRINTS_DIR / "new-game-modern-release.json",
}
# The same deterministic CURRENT-format SRAM fixture issue #11 already uses
# for expansion-modern-debugtools-check (see modern.mk's
# MODERN_DEBUGTOOLS_SRAM_FIXTURE) -- reused here via the host-side generator
# directly rather than depending on a Make-produced build artifact, so this
# test can run standalone.

sys.path.insert(0, str(PLAYTEST_DIR))
sys.path.insert(0, str(PLAYTEST_DIR / "tests"))

import gba_playtest  # noqa: E402
import host_mode  # noqa: E402
import sram_fixture as sf  # noqa: E402

MODERN_ROMS = {config: host_mode.modern_rom(config) for config in ("debug", "release")}


class NewGameScenarioFilesTests(unittest.TestCase):
    """Schema/committed-artifact checks that need no ROM build at all."""

    def setUp(self):
        self.assertTrue(SCENARIO_PATH.exists(), f"missing scenario: {SCENARIO_PATH}")
        self.data = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
        self.scenario = gba_playtest.load_scenario(SCENARIO_PATH)

    def test_scenario_parses_under_the_real_schema(self):
        self.assertEqual(self.scenario.name, "new-game")
        self.assertFalse(self.scenario.disabled)

    def test_checkpoint_names_and_order_match_the_documented_flow(self):
        names = [checkpoint.name for checkpoint in self.scenario.checkpoints]
        self.assertEqual(
            names,
            ["new-game-menu-selected", "empty-slot-list-shown", "new-game-created"],
        )

    def test_input_reuses_savecompat_currents_shared_title_cadence_verbatim(self):
        savecompat_current = gba_playtest.load_scenario(
            SCENARIOS_DIR / "savecompat-current.json"
        )
        shared_prefix_length = len(savecompat_current.inputs)
        own_prefix = self.scenario.inputs[:shared_prefix_length]
        self.assertEqual(
            [(f.start, f.end, f.key_mask) for f in own_prefix],
            [(f.start, f.end, f.key_mask) for f in savecompat_current.inputs],
        )

    def test_only_ordinary_a_confirmations_follow_the_shared_prefix(self):
        savecompat_current = gba_playtest.load_scenario(
            SCENARIOS_DIR / "savecompat-current.json"
        )
        extra = self.scenario.inputs[len(savecompat_current.inputs):]
        self.assertEqual(len(extra), 3, "expected exactly 3 extra input windows")
        for frame_range in extra:
            self.assertEqual(
                frame_range.key_mask,
                gba_playtest.KEY_BITS["A"],
                "every extra input window must be a bare A press, never a "
                "scripted directional cursor move",
            )

    def test_new_game_created_checkpoint_proves_semantic_arrival(self):
        created = self.scenario.checkpoints[-1]
        self.assertEqual(created.name, "new-game-created")
        self.assertTrue(created.framebuffer)
        self.assertTrue(created.sram_hash)
        probed_addresses = {probe.address for probe in created.probes}
        # gPlaySt.chapterIndex (0x0e) and gPlaySt.faction (0x0f), at the
        # symbol addresses this closure derived from the modern ELF -- see
        # reports/gba_playtest_issue13_closure.md.
        self.assertIn(0x020210B2, probed_addresses)
        self.assertIn(0x020210B3, probed_addresses)

    def test_empty_slot_list_and_created_checkpoints_exclude_the_same_diagnostic_bytes(self):
        # Matches docs/save_format.md's "SRAM hash policy: exact vs.
        # normalized": both checkpoints must use the identical normalized
        # hash space (build-commit + its dependent checksum) so their
        # sram_hash values are directly, meaningfully comparable to prove a
        # real write happened -- not merely that the always-variable
        # buildCommitShort bytes changed.
        before, after = self.scenario.checkpoints[1], self.scenario.checkpoints[2]
        self.assertEqual(
            before.sram_hash_exclude_ranges, after.sram_hash_exclude_ranges
        )
        self.assertEqual(
            before.sram_hash_exclude_ranges,
            ((29640, 9), (29650, 2)),
        )

    def test_committed_fingerprints_exist_and_match_scenario_for_both_configs(self):
        for config, path in FINGERPRINT_PATHS.items():
            with self.subTest(config=config):
                self.assertTrue(path.exists(), f"missing fingerprint: {path}")
                fingerprint = gba_playtest.validate_fingerprint(
                    json.loads(path.read_text(encoding="utf-8")), str(path)
                )
                self.assertEqual(fingerprint["scenario"], "new-game")
                self.assertEqual(len(fingerprint["checkpoints"]), 3)

    def test_debug_and_release_fingerprints_report_distinct_rom_identities(self):
        debug_fp = json.loads(
            FINGERPRINT_PATHS["debug"].read_text(encoding="utf-8")
        )
        release_fp = json.loads(
            FINGERPRINT_PATHS["release"].read_text(encoding="utf-8")
        )
        self.assertNotEqual(debug_fp["rom"]["sha1"], release_fp["rom"]["sha1"])


@host_mode.live_artifact_testcase("new-game runtime coverage")
class NewGameRuntimeTests(unittest.TestCase):
    """Live libmGBA runs against the built modern ROMs, when available.

    Category B (see tests/host_mode.py): in host-only mode
    (GBA_PLAYTEST_HOST_ONLY=1) this whole class skips before any ROM is
    touched. In normal mode it behaves exactly as before -- skipping
    explicitly (never silently) when the modern ROM for a config has not been
    built locally, and running (and passing) anywhere the ROM exists,
    including the target-ROM CI gate that builds it just before running the
    runtime scenarios.
    """

    def _run(self, config: str):
        rom = MODERN_ROMS[config]
        host_mode.require_built_rom(rom, f"modern {config} ROM")
        scenario = gba_playtest.load_scenario(SCENARIO_PATH)
        expected = gba_playtest.validate_fingerprint(
            json.loads(FINGERPRINT_PATHS[config].read_text(encoding="utf-8")),
            str(FINGERPRINT_PATHS[config]),
        )
        with tempfile.TemporaryDirectory(prefix="gba-playtest-newgame-test-") as tmp:
            fixture_path = sf.write_deterministic_current_fixture(
                Path(tmp) / "current.sav"
            )
            actual = host_mode.capture_live_or_skip(
                rom,
                scenario,
                fixture_path,
                label=f"new-game runtime coverage ({config})",
            )
        differences = gba_playtest.compare_fingerprints(
            expected, actual, policy="behavior"
        )
        self.assertEqual(differences, [], f"config={config}: {differences}")

    def test_debug_rom_matches_committed_fingerprint(self):
        self._run("debug")

    def test_release_rom_matches_committed_fingerprint(self):
        self._run("release")


if __name__ == "__main__":
    unittest.main()
