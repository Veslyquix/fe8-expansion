"""Tests for scripts/release_rehearsal/stale_count_claims.py (issue #9
verifier remediation: stale aggregate test-count claim regression
guard)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import stale_count_claims as sc  # noqa: E402


class RealRepoIsCleanTests(unittest.TestCase):
    def test_real_repo_has_no_stale_count_claims(self):
        findings = sc.find_stale_count_claims(ROOT)
        self.assertEqual(findings, [], findings)

    def test_check_reports_ok_on_real_repo(self):
        report = sc.check(ROOT)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["errors"], [])

    def test_release_closure_candidate_no_longer_hardcodes_860(self):
        """Regression test for the exact known defect: docs/release_
        closure_candidate.md previously hardcoded '860 tests' multiple
        times (a frozen aggregate count that drifts the moment a test
        is added/renamed)."""
        text = (ROOT / "docs" / "release_closure_candidate.md").read_text(encoding="utf-8")
        self.assertNotIn("860 tests", text)
        self.assertNotRegex(text, r"\d+\s+tests?\s+pass\b")


class StaleCountDetectionTests(unittest.TestCase):
    """Synthetic fixtures -- proves the detector fires on the known
    falsehood shapes and stays silent on legitimate small semantic
    constants/deltas, independent of this repository's own live test
    count drifting in the future."""

    def _scan(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "fake_doc.md"
            target.write_text(text, encoding="utf-8")
            return sc.find_stale_count_claims(tmp_path, ("fake_doc.md",))

    def test_parenthetical_test_count_is_caught(self):
        findings = self._scan("the full test suite (860 tests) passes cleanly\n")
        self.assertEqual(len(findings), 1)
        self.assertIn("fake_doc.md:1", findings[0])

    def test_ran_n_tests_shape_is_caught(self):
        findings = self._scan("`Ran 860 tests ... FAILED (failures=7)`\n")
        self.assertEqual(len(findings), 1)

    def test_all_n_passing_shape_is_caught(self):
        findings = self._scan("a clean, all-860-passing suite run\n")
        self.assertEqual(len(findings), 1)

    def test_n_tests_pass_shape_is_caught(self):
        findings = self._scan("860 tests pass, including 7 new regression tests\n")
        self.assertEqual(len(findings), 1)

    def test_small_semantic_delta_is_never_flagged(self):
        findings = self._scan("860 tests pass, including 2 new regression tests\n")
        # Only the aggregate "860 tests pass" clause is flagged, never
        # the "2 new regression tests" delta on the same line.
        self.assertEqual(len(findings), 1)
        self.assertIn("860 tests pass", findings[0])
        self.assertNotIn("2 new regression tests", findings[0].split("context:")[0])

    def test_migration_number_prose_is_never_flagged(self):
        findings = self._scan("Bump EXPANSION_SAVE_COMPAT_EPOCH from 1 to 2 for issue #18.\n")
        self.assertEqual(findings, [])

    def test_structural_finding_count_prose_is_never_flagged(self):
        findings = self._scan("seven live structural findings were disclosed.\n")
        self.assertEqual(findings, [])

    def test_unrelated_numeric_prose_is_never_flagged(self):
        findings = self._scan("the configured item ID cap is raised to 0xCE.\n")
        self.assertEqual(findings, [])

    def test_missing_target_file_is_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            findings = sc.find_stale_count_claims(Path(tmp), ("does/not/exist.md",))
        self.assertEqual(findings, [])


class CliTests(unittest.TestCase):
    def test_main_exit_zero_on_real_repo(self):
        self.assertEqual(sc.main(["--repo-root", str(ROOT)]), 0)

    def test_main_exit_one_on_synthetic_stale_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stale = tmp_path / "stale.md"
            stale.write_text("the suite (860 tests) passes\n", encoding="utf-8")
            self.assertEqual(sc.main(["--repo-root", str(tmp_path), "stale.md"]), 1)


if __name__ == "__main__":
    unittest.main()
