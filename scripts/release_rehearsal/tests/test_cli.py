"""Tests for scripts/release_rehearsal/cli.py (issue #9) -- the top-level
`make release-check` / `make release-rehearse` entry points, and the
machine-distinct status/exit contract (issue #9 verifier remediation)."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import cli as rc  # noqa: E402


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

    def test_stdout_is_json_only_no_prose(self):
        """Canonical machine JSON goes to stdout; every human-readable
        diagnostic goes to stderr -- a consumer must never need to parse
        prose out of stdout."""
        result = run_cli("check")
        json.loads(result.stdout)  # must parse as a single JSON document

    def test_invalid_target_sha_is_actionable_exit_2(self):
        result = run_cli("check", "--target-sha", "not-a-sha")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)


class RequireEligibleGateTests(unittest.TestCase):
    """Publication-eligibility mode (issue #9 verifier remediation)."""

    def test_check_require_eligible_exits_nonzero_while_blocked(self):
        result = run_cli("check", "--require-eligible")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--require-eligible", result.stderr)

    def test_rehearse_require_eligible_exits_nonzero_while_blocked(self):
        result = run_cli("rehearse", "--require-eligible")
        self.assertEqual(result.returncode, 1)

    def test_tooling_error_takes_precedence_over_require_eligible(self):
        result = run_cli("check", "--target-sha", "not-a-sha", "--require-eligible")
        self.assertEqual(result.returncode, 2)


class ExpectStatusGateTests(unittest.TestCase):
    """Process-health/expected-status mode (issue #9 verifier
    remediation): only accepts BLOCKED when the caller explicitly asks
    for exactly that, and fails actionably on any mismatch."""

    def test_check_expect_status_blocked_matches_and_exits_zero(self):
        result = run_cli("check", "--expect-status", "blocked")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("matches expected", result.stderr)

    def test_check_expect_status_mechanically_eligible_mismatches(self):
        result = run_cli("check", "--expect-status", "mechanically-eligible")
        self.assertEqual(result.returncode, 3)
        self.assertIn("actual status is", result.stderr)

    def test_rehearse_expect_status_blocked_matches_and_exits_zero(self):
        result = run_cli("rehearse", "--expect-status", "blocked")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rehearse_expect_status_mechanically_eligible_mismatches(self):
        result = run_cli("rehearse", "--expect-status", "mechanically-eligible")
        self.assertEqual(result.returncode, 3)

    def test_invalid_expect_status_value_rejected_by_argparse(self):
        result = run_cli("check", "--expect-status", "not-a-real-status")
        self.assertNotEqual(result.returncode, 0)

    def test_require_eligible_and_expect_status_are_mutually_exclusive(self):
        result = run_cli("check", "--require-eligible", "--expect-status", "blocked")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not allowed with argument", result.stderr)


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

    def test_report_includes_allowlist_and_version_ledger(self):
        result = run_cli("rehearse")
        data = json.loads(result.stdout)
        self.assertIn("allowlist", data)
        self.assertIn("version_ledger", data)

    def test_target_sha_override_binds_the_archive_itself_not_just_the_manifest(self):
        """Regression test: --target-sha must bind the *archive's* content
        (archive.target_sha), not only the manifest's own target_sha
        field -- otherwise the two could silently refer to different
        commits."""
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True,
        ).stdout.strip()
        result = run_cli("rehearse", "--target-sha", head_sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["archive"]["target_sha"], head_sha)


class WorkflowGuardSubcommandTests(unittest.TestCase):
    """Dynamic, machine-JSON workflow guard invocation (issue #9 verifier
    remediation) -- used by the CI workflow itself instead of a bare
    script invocation whose only output is prose."""

    def test_real_workflow_is_clean_exit_zero(self):
        result = run_cli("workflow-guard", ".github/workflows/release-rehearsal.yml")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["violations"], [])

    def test_missing_file_is_actionable_exit_2(self):
        result = run_cli("workflow-guard", ".github/workflows/does-not-exist.yml")
        self.assertEqual(result.returncode, 2)


class RenderMarkdownSummaryTests(unittest.TestCase):
    """issue #9 verifier remediation: the $GITHUB_STEP_SUMMARY renderer
    must be entirely data-driven from whatever report dict it is given --
    proven here with synthetic "blocked" AND "mechanically eligible"
    dicts, never by only ever observing this real, currently-blocked
    repository (which could never by itself prove the eligible branch
    is not secretly hardcoded to print "BLOCKED")."""

    def test_blocked_synthetic_report_renders_blocked_and_its_reasons(self):
        report = {
            "status": "blocked",
            "reasons": ["synthetic-reason-one", "synthetic-reason-two"],
            "provenance": {"status": "blocked", "reasons": ["x"]},
            "source_guard": {"status": "pass", "violations": []},
        }
        text = rc.render_markdown_summary(report)
        self.assertIn("`blocked`", text)
        self.assertIn("synthetic-reason-one", text)
        self.assertIn("synthetic-reason-two", text)
        self.assertNotIn("mechanically eligible", text)

    def test_synthetic_mechanically_eligible_report_renders_that_truthfully(self):
        """The literal issue #9 requirement: if a report ever says
        "mechanically eligible", the rendered summary must say that --
        never a hardcoded "BLOCKED" regardless of the actual input."""
        report = {
            "status": "mechanically eligible",
            "reasons": [],
            "provenance": {"status": "mechanically eligible", "reasons": []},
            "source_guard": {"status": "pass", "violations": []},
            "allowlist": {"ok": True, "errors": []},
            "rebuild": {"status": "verified_success", "reasons": []},
        }
        text = rc.render_markdown_summary(report)
        self.assertIn("`mechanically eligible`", text)
        self.assertNotIn("`blocked`", text)
        self.assertIn("by itself a publication approval", text)

    def test_check_table_reflects_each_sub_report_status_dynamically(self):
        ok_report = {
            "status": "blocked", "reasons": ["r"],
            "allowlist": {"ok": True, "errors": []},
        }
        bad_report = {
            "status": "blocked", "reasons": ["r"],
            "allowlist": {"ok": False, "errors": ["gap"]},
        }
        ok_text = rc.render_markdown_summary(ok_report)
        bad_text = rc.render_markdown_summary(bad_report)
        self.assertIn("| `allowlist` | ✅ |", ok_text)
        self.assertIn("| `allowlist` | ❌ |", bad_text)

    def test_unknown_status_never_crashes_and_is_shown_verbatim(self):
        text = rc.render_markdown_summary({"status": "some-future-status", "reasons": []})
        self.assertIn("`some-future-status`", text)

    def test_real_repo_summary_command_matches_check_status(self):
        summary_result = run_cli("summary")
        check_result = run_cli("check")
        self.assertEqual(summary_result.returncode, 0, summary_result.stderr)
        check_data = json.loads(check_result.stdout)
        self.assertIn(f"`{check_data['status']}`", summary_result.stdout)

    def test_summary_workflow_file_uses_the_dynamic_cli_not_hardcoded_prose(self):
        """The actual committed workflow must invoke the dynamic renderer
        (`cli summary`), never a hand-written 'echo BLOCKED'-style step,
        so a status change is reflected without a workflow edit."""
        workflow_text = (ROOT / ".github" / "workflows" / "release-rehearsal.yml").read_text()
        self.assertIn("scripts.release_rehearsal.cli summary", workflow_text)
        self.assertIn("GITHUB_STEP_SUMMARY", workflow_text)


if __name__ == "__main__":
    unittest.main()
