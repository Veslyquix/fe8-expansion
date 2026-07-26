"""Issue #13 closure: disabled schema-ready stub inventory and blocker
quality. `new-game` and `chapter` are no longer stubs (superseded by
tools/gba-playtest/scenarios/new-game.json and the reused, already-enabled
tools/gba-playtest/scenarios/debugtools-hub-modern-{debug,release}.json --
see reports/gba_playtest_issue13_closure.md). Only `combat` and `save`
remain disabled, each with a specific, evidenced blocker rather than a
generic "not attempted yet" placeholder, and `capture` must still reject
every one of them explicitly (never silently skip or half-run a disabled
scenario).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAYTEST_DIR = REPO_ROOT / "tools" / "gba-playtest"
STUBS_DIR = PLAYTEST_DIR / "scenarios" / "stubs"

sys.path.insert(0, str(PLAYTEST_DIR))

import gba_playtest  # noqa: E402


class StubInventoryTests(unittest.TestCase):
    def test_only_combat_and_save_stubs_remain(self):
        stub_files = sorted(p.name for p in STUBS_DIR.glob("*.stub.json"))
        self.assertEqual(stub_files, ["combat.stub.json", "save.stub.json"])

    def test_new_game_and_chapter_stubs_are_gone(self):
        self.assertFalse((STUBS_DIR / "new-game.stub.json").exists())
        self.assertFalse((STUBS_DIR / "chapter.stub.json").exists())


class RemainingStubQualityTests(unittest.TestCase):
    def _load(self, filename: str):
        path = STUBS_DIR / filename
        self.assertTrue(path.exists(), f"missing stub: {path}")
        scenario = gba_playtest.load_scenario(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return scenario, data

    def test_both_remaining_stubs_parse_disabled_with_no_checkpoints(self):
        for filename in ("combat.stub.json", "save.stub.json"):
            with self.subTest(filename=filename):
                scenario, _ = self._load(filename)
                self.assertTrue(scenario.disabled)
                self.assertEqual(scenario.checkpoints, ())
                self.assertTrue(scenario.blocker)

    def test_blockers_cite_the_closure_report_not_a_generic_placeholder(self):
        for filename in ("combat.stub.json", "save.stub.json"):
            with self.subTest(filename=filename):
                _, data = self._load(filename)
                blocker = data["blocker"]
                self.assertIn("reports/gba_playtest_issue13_closure.md", blocker)
                self.assertGreater(
                    len(blocker),
                    400,
                    "blocker should be a specific, evidenced account, not a "
                    "short generic placeholder",
                )

    def test_combat_blocker_documents_the_specific_geometry_and_stall_evidence(self):
        _, data = self._load("combat.stub.json")
        blocker = data["blocker"]
        for marker in (
            "gUnitArrayBlue",
            "FACTION_ENEMY",
            "single turn",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, blocker)

    def test_save_blocker_documents_what_is_already_covered_instead(self):
        _, data = self._load("save.stub.json")
        blocker = data["blocker"]
        for marker in (
            "savesuspend-resume-modern-debug.json",
            "new-game.json",
            "StartSaveMenuPostChapter",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, blocker)

    def test_capture_rejects_every_remaining_disabled_stub_explicitly(self):
        for filename in ("combat.stub.json", "save.stub.json"):
            with self.subTest(filename=filename):
                scenario, _ = self._load(filename)
                with self.assertRaisesRegex(gba_playtest.PlaytestError, "disabled"):
                    gba_playtest.capture(Path("unused.gba"), scenario)


if __name__ == "__main__":
    unittest.main()
