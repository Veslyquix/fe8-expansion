"""Runtime + static coverage for issue #2's final slice: a deterministic
ordinary-UI Suspend -> soft-reset -> Resume proof, built on top of #11
Slice 1's debug-only "Fast Boot: Chapter 2" launcher
(tools/gba-playtest/scenarios/debugtools-hub-modern-debug.json).

Scenario: tools/gba-playtest/scenarios/savesuspend-resume-modern-debug.json
Fingerprint: tools/gba-playtest/fingerprints/savesuspend-resume-modern-debug.json

Unlike every other savecompat-* scenario (which only proves the
compatibility *gate*'s classification/dialog behavior), this scenario
drives the actual gameplay Suspend command through the ordinary Map Menu
(cursor navigation + A presses only -- no test hook), triggers the real
soft-reset key combo (A+B+SELECT+START), and navigates the ordinary
title/save-menu Resume path, then proves the restored live game state
(gPlaySt.chapterIndex/faction/xCursor/yCursor and a unit item probe)
matches exactly what was captured by the manual Suspend -- not the
earlier automatic Player-Phase-start auto-suspend that fires before any
user action (vanilla FE7/FE8 behavior; both share the same
WriteSuspendSave()/alternating-slot mechanism, so the scenario's
"suspend-confirmed" checkpoint proves the manual write landed in the
*other* SaveBlockInfo slot with a distinct cursor position, not merely
that *a* valid suspend save exists).

This is debug-only: the Chapter 2 launcher does not exist in release
builds (see docs/debugtools.md), so this scenario is only wired into
tools/gba-playtest/run_save_compat_checks.py for MODERN_CONFIG=debug and
is not part of the release fingerprint set.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAYTEST_DIR = REPO_ROOT / "tools" / "gba-playtest"
SCENARIOS_DIR = PLAYTEST_DIR / "scenarios"
FINGERPRINTS_DIR = PLAYTEST_DIR / "fingerprints"
SCENARIO_PATH = SCENARIOS_DIR / "savesuspend-resume-modern-debug.json"
FINGERPRINT_PATH = FINGERPRINTS_DIR / "savesuspend-resume-modern-debug.json"

sys.path.insert(0, str(PLAYTEST_DIR))
sys.path.insert(0, str(PLAYTEST_DIR / "tests"))

import gba_playtest  # noqa: E402
import host_mode  # noqa: E402
import sram_fixture as sf  # noqa: E402
import sram_hash_mirror  # noqa: E402

MODERN_DEBUG_ROM = host_mode.modern_rom("debug")


def _capture_or_skip(rom: Path, scenario, sram_image: Path):
    """Live capture against a repository ROM. Host-only mode
    (GBA_PLAYTEST_HOST_ONLY=1) skips before the ROM is touched; normal mode
    keeps the previous explicit backend-unavailable skip."""
    return host_mode.capture_live_or_skip(
        rom, scenario, sram_image, label="savesuspend-resume runtime coverage"
    )


class SavesuspendResumeScenarioFilesTests(unittest.TestCase):
    """Schema/committed-artifact checks that need no ROM build at all."""

    def setUp(self):
        self.assertTrue(SCENARIO_PATH.exists(), f"missing scenario: {SCENARIO_PATH}")
        self.data = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
        self.scenario = gba_playtest.load_scenario(SCENARIO_PATH)

    def test_scenario_parses_under_the_real_schema(self):
        # gba_playtest.load_scenario() already raises PlaytestError on any
        # schema violation (overlapping/unordered frames, bad probe hex
        # width, duplicate checkpoint names/frames, ...); reaching here
        # proves the committed scenario is schema-valid.
        self.assertEqual(self.scenario.name, "savesuspend-resume")

    def test_checkpoint_names_and_order_match_the_documented_flow(self):
        names = [checkpoint.name for checkpoint in self.scenario.checkpoints]
        self.assertEqual(
            names,
            ["suspend-confirmed", "post-soft-reset-boot", "resumed-chapter2"],
        )
        frames = [checkpoint.frame for checkpoint in self.scenario.checkpoints]
        self.assertEqual(frames, sorted(frames), "checkpoints must be in frame order")

    def test_input_reuses_the_existing_hub_launcher_frames_verbatim(self):
        """The scenario must replay tools/gba-playtest/scenarios/
        debugtools-hub-modern-debug.json's own frames byte-for-byte (same
        Fast Boot: Chapter 2 hotkey -> hub -> launcher route) before any
        of this scenario's own additional input, per the task's
        "reuse existing input/probe/checkpoint/schema" requirement --
        never re-deriving or duplicating that launcher input sequence."""
        hub_path = SCENARIOS_DIR / "debugtools-hub-modern-debug.json"
        hub_data = json.loads(hub_path.read_text(encoding="utf-8"))
        hub_frames = hub_data["frames"]
        self.assertEqual(
            self.data["frames"][: len(hub_frames)], hub_frames,
            "savesuspend-resume-modern-debug.json must replay the hub "
            "scenario's frames verbatim as its prefix",
        )

    def test_input_includes_ordinary_map_menu_suspend_navigation(self):
        """Cursor-only navigation (A/DOWN taps), never a raw memory-poke
        directive -- this schema has no such directive to begin with, but
        this test also pins the down-then-select shape so a future edit
        can't silently replace it with a degenerate all-A sequence."""
        frames = self.data["frames"]
        down_taps = [f for f in frames if f["keys"] == ["DOWN"]]
        self.assertGreaterEqual(
            len(down_taps), 4,
            "expected at least 4 DOWN taps to walk the Map Menu cursor "
            "from 'Unit' down to 'Suspend'",
        )
        a_taps = [f for f in frames if f["keys"] == ["A"]]
        self.assertGreaterEqual(len(a_taps), 3, "expected multiple A taps "
                                 "(open menu, select Suspend, confirm Yes)")

    def test_input_includes_the_ordinary_soft_reset_combo(self):
        """A+B+SELECT+START held together for a sustained window -- the
        real SoftResetIfKeyComboPressed() combo, never a scripted
        core-reset call."""
        frames = self.data["frames"]
        combo = {"A", "B", "SELECT", "START"}
        combo_frames = [f for f in frames if set(f["keys"]) == combo]
        self.assertEqual(
            len(combo_frames), 1,
            "expected exactly one held A+B+SELECT+START window",
        )
        held_length = combo_frames[0]["end"] - combo_frames[0]["start"]
        self.assertGreaterEqual(
            held_length, 30,
            "soft-reset combo must be held long enough for "
            "SoftResetIfKeyComboPressed() to observe it every frame",
        )

    def test_suspend_confirmed_checkpoint_proves_distinct_manual_write(self):
        """The checkpoint immediately after the manual Suspend confirm
        must probe both alternating SaveBlockInfo slots (SAVE_ID_SUSPEND
        and SAVE_ID_SUSPEND_ALT) plus both slots' own stored cursor
        position, and those two stored cursor values must differ -- the
        static proof that this checkpoint distinguishes the manual write
        from the earlier automatic Player-Phase-start auto-suspend."""
        checkpoint = next(
            c for c in self.data["checkpoints"] if c["name"] == "suspend-confirmed"
        )
        probes_by_addr = {p["address"]: p["expected"] for p in checkpoint["probes"]}
        # Primary slot (SAVE_ID_SUSPEND) magic/kind + its stored cursor.
        self.assertEqual(probes_by_addr["0x0e000094"], "0x24")
        self.assertEqual(probes_by_addr["0x0e00009a"], "0x01")
        self.assertIn("0x0e0000e6", probes_by_addr)
        # Alt slot (SAVE_ID_SUSPEND_ALT) magic/kind + its stored cursor.
        self.assertEqual(probes_by_addr["0x0e0000a4"], "0x24")
        self.assertEqual(probes_by_addr["0x0e0000aa"], "0x01")
        self.assertIn("0x0e00205e", probes_by_addr)
        # The two slots' own stored xCursor bytes must differ: one is the
        # automatic auto-save's cursor, the other is this manual command's.
        self.assertNotEqual(
            probes_by_addr["0x0e0000e6"], probes_by_addr["0x0e00205e"],
            "primary and alt slots' stored cursor must differ -- proves "
            "the manual Suspend wrote a distinct slot from the automatic "
            "auto-suspend, not a no-op repeat of it",
        )
        # Debug-only suppression probe must read back exactly 0.
        self.assertEqual(probes_by_addr["0x020315b0"], "0x00000000")
        self.assertTrue(checkpoint["sram_hash"])

    def test_resumed_checkpoint_proves_intended_restored_state(self):
        checkpoint = next(
            c for c in self.data["checkpoints"] if c["name"] == "resumed-chapter2"
        )
        probes_by_addr = {p["address"]: p["expected"] for p in checkpoint["probes"]}
        self.assertEqual(probes_by_addr["0x020210b2"], "0x02")  # chapterIndex
        self.assertEqual(probes_by_addr["0x020210b3"], "0x00")  # faction
        self.assertEqual(probes_by_addr["0x020210b6"], "0x09")  # xCursor
        self.assertEqual(probes_by_addr["0x020210b7"], "0x04")  # yCursor
        self.assertEqual(probes_by_addr["0x0202fa0a"], "0x2809")  # Rapier item

    def test_committed_fingerprint_exists_and_matches_scenario(self):
        self.assertTrue(FINGERPRINT_PATH.exists(), f"missing fingerprint: {FINGERPRINT_PATH}")
        fingerprint = json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8"))
        gba_playtest.validate_fingerprint(fingerprint, str(FINGERPRINT_PATH))
        self.assertEqual(fingerprint["scenario"], "savesuspend-resume")
        names = [c["name"] for c in fingerprint["checkpoints"]]
        self.assertEqual(
            names, ["suspend-confirmed", "post-soft-reset-boot", "resumed-chapter2"]
        )


@host_mode.live_artifact_testcase("savesuspend-resume runtime coverage")
class SavesuspendResumeRuntimeTests(unittest.TestCase):
    """Executes the scenario end-to-end against the built modern debug
    ROM and compares against the committed fingerprint.

    Category B (tests/host_mode.py): in host-only mode this class is skipped
    before the ROM is touched. In normal mode it is skipped (never a false
    pass) if that ROM has not been built yet or the libmGBA backend is
    unavailable in this environment."""

    @classmethod
    def setUpClass(cls):
        host_mode.require_built_rom(MODERN_DEBUG_ROM, "modern debug ROM")

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="gba-playtest-savesuspend-resume-")
        self.addCleanup(self._tmpdir.cleanup)
        self.fixture_dir = Path(self._tmpdir.name)

    def test_suspend_reset_resume_matches_committed_fingerprint(self):
        fixture_path = self.fixture_dir / "current.sav"
        sf.write_fixture(fixture_path, sf.STATE_CURRENT)
        scenario = gba_playtest.load_scenario(SCENARIO_PATH)
        actual = _capture_or_skip(MODERN_DEBUG_ROM, scenario, fixture_path)
        expected = json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8"))
        differences = gba_playtest.compare_fingerprints(expected, actual, policy="behavior")
        self.assertEqual(differences, [], f"savesuspend-resume: {differences}")

    def test_sram_hash_changes_from_the_initial_fixture(self):
        """Requirement 5: SRAM must have changed from the initial
        synthetic CURRENT fixture after the manual Suspend write. Uses
        the existing byte-exact Python mirror of backend.c's hash_sram()
        (tests/sram_hash_mirror.py) applied to the same
        sram_hash_exclude_ranges the checkpoint itself declares, so this
        is the same normalized hash the backend reports -- not merely a
        differently-computed value that happens to differ for unrelated
        reasons."""
        fixture_path = self.fixture_dir / "current.sav"
        sf.write_fixture(fixture_path, sf.STATE_CURRENT)
        checkpoint_data = next(
            c for c in json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))["checkpoints"]
            if c["name"] == "suspend-confirmed"
        )
        exclude_ranges = [
            (r["offset"], r["length"])
            for r in checkpoint_data.get("sram_hash_exclude_ranges", [])
        ]
        initial_hash = sram_hash_mirror.compute_sram_hash(
            fixture_path.read_bytes(), exclude_ranges
        )
        scenario = gba_playtest.load_scenario(SCENARIO_PATH)
        actual = _capture_or_skip(MODERN_DEBUG_ROM, scenario, fixture_path)
        checkpoints = {c["name"]: c for c in actual["checkpoints"]}
        confirmed_hash = checkpoints["suspend-confirmed"]["sram_hash"]
        self.assertNotEqual(
            initial_hash, confirmed_hash,
            "SRAM must have changed from the initial fixture after the "
            "manual Suspend write",
        )


# ---------------------------------------------------------------------
# Static proof (no ROM/execution required): this task adds no new direct
# C call site into the save-internal write/read functions -- the manual
# Suspend in the scenario above goes exclusively through the ordinary Map
# Menu UI's existing call site, never a new test-only hook.
# ---------------------------------------------------------------------

SRC_DIR = REPO_ROOT / "src"
_SAVE_INTERNAL_CALL_RE = re.compile(
    r"\b(WriteSuspendSave|ReadSuspendSave|WriteGameSave|ReadGameSave)\s*\("
)

# The exact, pre-existing call sites as of this task (src/bmsave.c itself,
# which defines these functions, is excluded). Recorded once here so any
# future diff that adds a *new* call site anywhere in src/ fails loudly --
# proving this task did not add one, and guarding against a silent one
# being added later without deliberate review of this list.
_EXPECTED_CALL_SITE_COUNTS = {
    "src/bm.c": 1,
    "src/bmarena.c": 1,
    "src/bmbattle.c": 1,
    "src/bmdebug.c": 6,
    "src/bmtrap.c": 1,
    "src/bonusclaim.c": 1,
    "src/cp_decide.c": 1,
    "src/playerphase.c": 2,
    "src/savemenu.c": 7,
    "src/sio_term.c": 1,
    "src/uiarena.c": 1,
}


class NoNewSaveInternalHookTests(unittest.TestCase):
    """Proves this task's file domain (tools/gba-playtest only) added no
    new C call site into the save-internal write/read functions, and that
    src/'s existing call-site count is unchanged from the pre-recorded
    baseline above."""

    def test_no_new_direct_save_internal_call_site_in_src(self):
        actual_counts: dict[str, int] = {}
        for path in sorted(SRC_DIR.glob("*.c")):
            if path.name == "bmsave.c":
                continue  # defines the functions; not a "call site"
            text = path.read_text(encoding="utf-8", errors="replace")
            count = len(_SAVE_INTERNAL_CALL_RE.findall(text))
            if count:
                actual_counts[f"src/{path.name}"] = count
        self.assertEqual(
            actual_counts, _EXPECTED_CALL_SITE_COUNTS,
            "src/'s save-internal write/read call sites changed -- this "
            "task must not add a new one; if a legitimate engine change "
            "added one outside this task's scope, update the baseline "
            "deliberately",
        )

    def test_gba_playtest_tooling_itself_contains_no_save_internal_call(self):
        """The Python harness/scenario/fixture tooling must never invoke
        these C identifiers as a shortcut (they are C symbols with no
        Python binding here to begin with, but this pins the intent).
        This test file itself is excluded from the scan since its own
        docstrings/comments legitimately name these identifiers in prose
        to document what the scenario proves -- exactly the same
        comment-naming allowance test_save_compat_gate_safety.py's module
        docstring relies on for save_compat_menu.c."""
        self_path = Path(__file__).resolve()
        for path in sorted(PLAYTEST_DIR.rglob("*.py")):
            if path.resolve() == self_path:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertFalse(
                _SAVE_INTERNAL_CALL_RE.search(text),
                f"{path} unexpectedly references a save-internal call: "
                "the manual Suspend must be driven through the ordinary "
                "UI input only",
            )


if __name__ == "__main__":
    unittest.main()
