"""Tests for scripts/release_rehearsal/cli.py (issue #9) -- the top-level
`make release-check` / `make release-rehearse` entry points."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "scripts.release_rehearsal.cli", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class CheckSubcommandTests(unittest.TestCase):
    def test_exit_zero_for_well_formed_blocked_report(self):
        result = run_cli("check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"status": "blocked"', result.stdout)
        self.assertNotIn('"status": "mechanically eligible"', result.stdout)

    def test_stderr_explicitly_states_blocked(self):
        result = run_cli("check")
        self.assertIn("BLOCKED", result.stderr)

    def test_report_is_valid_json(self):
        result = run_cli("check")
        data = json.loads(result.stdout)
        self.assertIn("status", data)
        self.assertIn("reasons", data)

    def test_invalid_target_sha_is_actionable_exit_2(self):
        result = run_cli("check", "--target-sha", "not-a-sha")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)


class RehearseSubcommandTests(unittest.TestCase):
    def test_exit_zero_and_archives_match(self):
        result = run_cli("rehearse")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["archive"]["match"])
        self.assertEqual(data["status"], "blocked")

    def test_stderr_mentions_deterministic_and_blocked(self):
        result = run_cli("rehearse")
        self.assertIn("deterministic", result.stderr)
        self.assertIn("BLOCKED", result.stderr)

    def test_rebuild_blocker_present(self):
        result = run_cli("rehearse")
        data = json.loads(result.stdout)
        self.assertEqual(data["rebuild"]["status"], "blocked")
        self.assertIn("mgfembp", str(data["rebuild"]["reasons"]))


if __name__ == "__main__":
    unittest.main()
