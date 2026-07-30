"""Tests for scripts/release_rehearsal/cli.py (issue #9) -- the top-level
`make release-check` / `make release-rehearse` entry points, and the
machine-distinct status/exit contract (issue #9 verifier remediation)."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import cli as rc  # noqa: E402

NONEXISTENT_SHA = "0123456789abcdef0123456789abcdef01234567"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "scripts.release_rehearsal.cli", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def _real_head_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True,
    ).stdout.strip()


def _extract_head_archive(head_sha: str) -> Path:
    """A real `git archive` extraction of this repository's own actual
    HEAD into a fresh temp directory with **no** `.git` at all -- a
    genuine non-git candidate tree exactly like a downloaded, extracted
    GitHub source archive (never a hand-authored fake; "mgfembp"
    naturally lands as a real empty directory here, exactly as GitHub's
    own auto-generated archive produces it). Caller owns cleanup."""
    tmp = Path(tempfile.mkdtemp(prefix="fe8-issue9-cli-extracted-"))
    archive = subprocess.run(["git", "archive", head_sha], cwd=str(ROOT), capture_output=True)
    assert archive.returncode == 0, archive.stderr
    extract = subprocess.run(["tar", "-x"], input=archive.stdout, cwd=str(tmp))
    assert extract.returncode == 0
    assert not (tmp / ".git").exists(), "fixture must be a genuine non-git tree"
    return tmp


# Module-level cache: at most one real `git archive HEAD | tar -x` for
# this entire test module (several test classes below each need their
# own genuine non-git extracted tree of the same, current HEAD; re-
# running the extraction once per class/test would be correct but
# needlessly slow for a ~9000-tracked-file repository). Read-only
# consumers use `_shared_head_tree()` directly; anything that mutates
# its own copy calls `_copy_of_shared_head_tree()` instead (a local
# filesystem copy, no repeated git/tar subprocess spawn).
_shared_head_sha = None
_shared_head_tree_path = None


def _shared_head_sha_and_tree():
    global _shared_head_sha, _shared_head_tree_path
    if _shared_head_tree_path is None:
        _shared_head_sha = _real_head_sha()
        _shared_head_tree_path = _extract_head_archive(_shared_head_sha)
    return _shared_head_sha, _shared_head_tree_path


def _copy_of_shared_head_tree() -> Path:
    _, template = _shared_head_sha_and_tree()
    dest = Path(tempfile.mkdtemp(prefix="fe8-issue9-cli-extracted-copy-"))
    shutil.rmtree(dest)  # copytree requires the destination not to exist yet
    shutil.copytree(template, dest)
    return dest


def tearDownModule():
    global _shared_head_tree_path
    if _shared_head_tree_path is not None:
        shutil.rmtree(_shared_head_tree_path, ignore_errors=True)
        _shared_head_tree_path = None


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

    def test_long_reasons_list_is_capped_for_readability_but_not_silently_dropped(self):
        """A real "blocked" report can carry 200+ individual reasons (one
        per honestly-unresolved provenance fact); the *rendered Markdown*
        caps how many are printed for readability, but must say exactly
        how many more exist rather than silently truncating with no
        indication."""
        many_reasons = [f"synthetic-reason-{i}" for i in range(50)]
        text = rc.render_markdown_summary({"status": "blocked", "reasons": many_reasons})
        for reason in many_reasons[: rc._MAX_RENDERED_REASONS]:
            self.assertIn(reason, text)
        self.assertIn(f"and {50 - rc._MAX_RENDERED_REASONS} more reason(s)", text)
        self.assertNotIn("synthetic-reason-49", text)

    def test_short_reasons_list_is_never_truncated(self):
        text = rc.render_markdown_summary({"status": "blocked", "reasons": ["only-one-reason"]})
        self.assertIn("only-one-reason", text)
        self.assertNotIn("more reason(s)", text)

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


class NonexistentTargetShaExitContractTests(unittest.TestCase):
    """issue #9 fresh-verifier reproduction (defect class 1): a
    well-formed (40-lowercase-hex) but nonexistent --target-sha in this
    *actual* git repository must never traceback -- it is an actionable
    tooling error (exit 2), never confusable with EXIT_NOT_ELIGIBLE (1,
    which is coincidentally also Python's own unhandled-exception exit
    code -- exactly the collision this remediation closes)."""

    def _assert_no_traceback(self, result):
        self.assertNotIn("Traceback (most recent call last)", result.stderr)
        self.assertNotIn("Traceback (most recent call last)", result.stdout)

    def test_check_nonexistent_sha_exits_2_not_traceback(self):
        result = run_cli("check", "--target-sha", NONEXISTENT_SHA)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)

    def test_summary_nonexistent_sha_exits_2_not_traceback(self):
        result = run_cli("summary", "--target-sha", NONEXISTENT_SHA)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)

    def test_rehearse_nonexistent_sha_exits_2_not_traceback(self):
        result = run_cli("rehearse", "--target-sha", NONEXISTENT_SHA)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)

    def test_nonexistent_sha_with_require_eligible_is_still_exit_2_not_1(self):
        """The tooling error must take precedence over --require-
        eligible's own exit 1 -- a crash is never allowed to masquerade
        as (or be conflated with) "not eligible"."""
        result = run_cli("check", "--target-sha", NONEXISTENT_SHA, "--require-eligible")
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)


class ExtractedNonGitTreeEndToEndTests(unittest.TestCase):
    """issue #9 fresh-verifier reproduction (defect class 2): the
    documented non-git/extracted candidate path, with a required exact
    40-lowercase-hex --target-sha override, must genuinely work
    end-to-end -- canonical JSON, a truthful BLOCKED status (this
    extraction is real, current, and license/provenance-unresolved,
    exactly like the live repository -- never a fabricated eligible
    result), and the exact same machine-distinct exit contract as a
    real git worktree. The fixture is a real `git archive` extraction of
    this repository's own actual HEAD (see `_extract_head_archive`)."""

    @classmethod
    def setUpClass(cls):
        # Read-only for every test in this class -- safe to share the
        # single module-level extraction directly (see
        # `_shared_head_sha_and_tree`); `tearDownModule` owns its cleanup.
        cls.head_sha, cls.tree = _shared_head_sha_and_tree()

    def _assert_no_traceback(self, result):
        self.assertNotIn("Traceback (most recent call last)", result.stderr)
        self.assertNotIn("Traceback (most recent call last)", result.stdout)

    def test_check_with_exact_sha_is_canonical_blocked_json_no_traceback(self):
        result = run_cli("check", "--repo-root", str(self.tree), "--target-sha", self.head_sha)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "blocked")
        self.assertEqual(data["target_sha"], self.head_sha)
        self.assertTrue(data["allowlist"]["ok"], data["allowlist"]["errors"])
        self.assertEqual(data["source_guard"]["status"], "pass")

    def test_check_expect_status_blocked_exits_zero(self):
        result = run_cli(
            "check", "--repo-root", str(self.tree), "--target-sha", self.head_sha,
            "--expect-status", "blocked",
        )
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_require_eligible_exits_exactly_1(self):
        result = run_cli(
            "check", "--repo-root", str(self.tree), "--target-sha", self.head_sha,
            "--require-eligible",
        )
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 1)

    def test_check_missing_target_sha_is_actionable_exit_2(self):
        result = run_cli("check", "--repo-root", str(self.tree))
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--target-sha", result.stderr)

    def test_rehearse_with_exact_sha_is_canonical_blocked_json_no_traceback(self):
        result = run_cli("rehearse", "--repo-root", str(self.tree), "--target-sha", self.head_sha)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "blocked")
        self.assertTrue(data["archive"]["match"])
        self.assertEqual(data["archive"]["target_sha"], self.head_sha)
        self.assertEqual(data["rebuild"]["status"], "blocked")
        self.assertTrue(any(".git" in reason for reason in data["rebuild"]["reasons"]))

    def test_rehearse_expect_status_blocked_exits_zero(self):
        result = run_cli(
            "rehearse", "--repo-root", str(self.tree), "--target-sha", self.head_sha,
            "--expect-status", "blocked",
        )
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rehearse_require_eligible_exits_exactly_1(self):
        result = run_cli(
            "rehearse", "--repo-root", str(self.tree), "--target-sha", self.head_sha,
            "--require-eligible",
        )
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 1)

    def test_rehearse_missing_target_sha_is_actionable_exit_2_not_traceback(self):
        """The literal reproduced defect: previously tracebacked (exit
        1) via rebuild_rehearsal_blocker's unconditional 'git submodule
        status' call; now fails fast and actionably before any git
        invocation is attempted at all."""
        result = run_cli("rehearse", "--repo-root", str(self.tree))
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--target-sha", result.stderr)

    def test_summary_with_exact_sha_no_traceback(self):
        result = run_cli("summary", "--repo-root", str(self.tree), "--target-sha", self.head_sha)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("`blocked`", result.stdout)

    def test_summary_missing_target_sha_is_actionable_exit_2(self):
        result = run_cli("summary", "--repo-root", str(self.tree))
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)


class MalformedExtractedTreeTests(unittest.TestCase):
    """issue #9 verifier remediation (DONE criterion): missing/extra/
    unsafe member fixtures against a real extracted candidate tree.
    Never fabricates an eligible legal fact -- every fixture here is
    still, honestly, license/provenance-BLOCKED; the only question
    tested is the *mechanical* exit-code/traceback contract."""

    @classmethod
    def setUpClass(cls):
        cls.head_sha, _ = _shared_head_sha_and_tree()

    def _extract(self) -> Path:
        """Each test here needs its *own* independently-mutable tree
        (one deletes a file, one overwrites one, one adds one) -- copied
        locally from the shared read-only template rather than re-
        running `git archive` again for every single fixture."""
        tree = _copy_of_shared_head_tree()
        self.addCleanup(shutil.rmtree, tree, True)
        return tree

    def _assert_no_traceback(self, result):
        self.assertNotIn("Traceback (most recent call last)", result.stderr)
        self.assertNotIn("Traceback (most recent call last)", result.stdout)

    def test_unsafe_member_content_is_controlled_exit_2_via_rehearse(self):
        """An allowlisted, otherwise-harmless text file overwritten with
        content that fails the hard-deny magic-byte check (ELF magic),
        independent of its unchanged, harmless ".md" extension -- a
        structurally malformed candidate `rehearse` must refuse to
        archive, not traceback and not silently accept."""
        tree = self._extract()
        (tree / "README.md").write_bytes(b"\x7fELF" + b"\x00" * 32)
        result = run_cli("rehearse", "--repo-root", str(tree), "--target-sha", self.head_sha)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)

    def test_missing_allowlisted_member_is_controlled_exit_2_via_rehearse(self):
        """A declared allowlist member entirely absent from the
        extraction (not merely untracked -- genuinely never extracted)
        must refuse to archive with a controlled, actionable exit 2."""
        tree = self._extract()
        (tree / "README.md").unlink()
        result = run_cli("rehearse", "--repo-root", str(tree), "--target-sha", self.head_sha)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)
        self.assertIn("README.md", result.stderr)

    def test_missing_allowlisted_member_is_reported_blocked_via_check(self):
        """`check` (report-only; never attempts to build archive bytes)
        instead reports this as an honestly-blocked business fact --
        never a crash, and consistent with `rehearse`'s exit 2 above:
        both mechanically detect and report the exact same underlying
        gap, at their respective layers."""
        tree = self._extract()
        (tree / "README.md").unlink()
        result = run_cli("check", "--repo-root", str(tree), "--target-sha", self.head_sha)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "blocked")
        self.assertFalse(data["allowlist"]["ok"])
        self.assertTrue(any("README.md" in e for e in data["allowlist"]["errors"]))

    def test_extra_unlisted_member_is_reported_blocked_not_exit_2(self):
        """An extra, never-allowlisted file present in an extracted tree
        is excluded from the archive and flagged as a `not-allowlisted`
        source_guard violation -- a normal, well-formed BLOCKED business
        result (see docs/release_process.md), never a tooling crash;
        this is pre-existing, intentional behavior (mirrors how a live
        git worktree's untracked byproducts are handled), regression-
        guarded here at the CLI layer for a genuine extracted tree."""
        tree = self._extract()
        (tree / "unreviewed_extra_file.c").write_text("int extra;\n")
        result = run_cli("check", "--repo-root", str(tree), "--target-sha", self.head_sha)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "blocked")
        self.assertTrue(
            any("unreviewed_extra_file.c" in v and "not-allowlisted" in v
                for v in data["source_guard"]["violations"])
        )
        # And `rehearse` still succeeds (the extra file is silently
        # excluded from the archive bytes, never causing a refusal).
        rehearse_result = run_cli("rehearse", "--repo-root", str(tree), "--target-sha", self.head_sha)
        self._assert_no_traceback(rehearse_result)
        self.assertEqual(rehearse_result.returncode, 0, rehearse_result.stderr)


class Issue9LiteralReproductionCommandsTests(unittest.TestCase):
    """The four literal issue #9 reproduction commands (see the issue's
    own "Reproduce all verifier commands before changing" step), run
    verbatim -- asserted to never leak a Python traceback on stdout or
    stderr, regardless of the resulting exit code."""

    @classmethod
    def setUpClass(cls):
        # Also read-only -- reuses the same shared extraction as
        # `ExtractedNonGitTreeEndToEndTests` above (never a second
        # `git archive` invocation for this module).
        cls.head_sha, cls.tree = _shared_head_sha_and_tree()

    def _assert_no_traceback(self, result):
        self.assertNotIn("Traceback (most recent call last)", result.stderr)
        self.assertNotIn("Traceback (most recent call last)", result.stdout)

    def test_repro_1_check_nonexistent_target_sha(self):
        result = run_cli("check", "--target-sha", NONEXISTENT_SHA)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)

    def test_repro_2_summary_nonexistent_target_sha(self):
        result = run_cli("summary", "--target-sha", NONEXISTENT_SHA)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 2)

    def test_repro_3_check_extracted_tree_exact_target_sha(self):
        result = run_cli("check", "--repo-root", str(self.tree), "--target-sha", self.head_sha)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_repro_4_rehearse_extracted_tree_exact_target_sha(self):
        result = run_cli("rehearse", "--repo-root", str(self.tree), "--target-sha", self.head_sha)
        self._assert_no_traceback(result)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
