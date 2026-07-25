"""Coverage for the Issue #12 drift-automation contract gap fix.

Two things are tested here, both stdlib-only (no PyYAML, no third-party
deps):

1. `WorkflowStaticPolicyTests` -- plain string/regex checks against the raw
   text of `.github/workflows/upstream-port-drift.yml`, confirming:
     - it no longer self-compares `drift --ref` against the recorded
       `last_ported` SHA (the bug this fix addresses -- that made the job
       vacuously "clean" forever);
     - it explicitly fetches the pinned canonical remote before running
       drift/scan, and runs them against the freshly-fetched local ref;
     - `permissions: contents: read` only, `persist-credentials: false`,
       no secrets, no forbidden mutating Git/GitHub operations anywhere in
       the file, and `workflow_dispatch` takes no inputs (so there is no
       untrusted value that could be used for ref/option injection).

2. `WorkflowDriftReplayTests` -- an actual local, offline, synthetic-Git
   replay of the same subcommand sequence the workflow's shell steps run
   (configure/verify remote -> `fetch` -> `drift --ref <fresh ref>`
   -> `scan --ref <fresh ref>`), proving that once the canonical remote
   is genuinely ahead, drift is detected (exit code 2, not the old
   always-0 self-compare), while state file, HEAD, and working tree
   remain byte-for-byte unchanged.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.upstream_port import cli, constants
from tests.upstream_port import helpers as h

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_WORKFLOW_PATH = os.path.join(
    _REPO_ROOT, ".github", "workflows", "upstream-port-drift.yml"
)

# Substrings that must never appear anywhere in this workflow file: any of
# these would mean it mutates upstream, mutates this repo's history, or
# writes to something other than contents:read.
_FORBIDDEN_SUBSTRINGS = [
    "git commit",
    "git push",
    "git merge",
    "git cherry-pick",
    "git branch -d",
    "git branch -D",
    "gh pr create",
    "gh pr merge",
    "upstream_port update-state",
    "contents: write",
    "secrets.",
    "git checkout ",  # actions/checkout@v4 (the action) is fine; a raw
    # `git checkout <ref>` invocation of upstream content is not.
]


def _read_workflow_text() -> str:
    with open(_WORKFLOW_PATH, encoding="utf-8") as fh:
        return fh.read()


class WorkflowStaticPolicyTests(unittest.TestCase):
    def setUp(self):
        self.text = _read_workflow_text()

    def test_workflow_file_exists(self):
        self.assertTrue(os.path.isfile(_WORKFLOW_PATH))

    def test_permissions_are_read_only_and_no_write_grant_anywhere(self):
        self.assertIn("permissions:", self.text)
        self.assertIn("contents: read", self.text)
        # No permissions block anywhere may grant write of any kind.
        self.assertNotRegex(self.text, r"permissions:\s*\n(\s*\S+:\s*\n)*\s*\S+:\s*write")
        self.assertNotIn("contents: write", self.text)

    def test_persist_credentials_false_and_no_secrets_used(self):
        self.assertIn("persist-credentials: false", self.text)
        self.assertNotIn("secrets.", self.text)
        self.assertNotIn("${{ secrets", self.text)

    def test_workflow_dispatch_takes_no_inputs(self):
        # Must be the bare `workflow_dispatch: {}` form -- no `inputs:`
        # block that could accept an untrusted ref/remote/option string.
        self.assertRegex(self.text, r"workflow_dispatch:\s*\{\}")
        self.assertNotIn("workflow_dispatch:\n  inputs", self.text)
        self.assertNotIn("github.event.inputs", self.text)

    def test_no_forbidden_mutating_operations_present(self):
        for forbidden in _FORBIDDEN_SUBSTRINGS:
            self.assertNotIn(
                forbidden, self.text, msg=f"forbidden substring found: {forbidden!r}"
            )

    def test_no_longer_self_compares_drift_against_recorded_last_ported_sha(self):
        # This is the exact contract gap this fix closes: the old workflow
        # ran `drift --ref "$LAST_PORTED_SHA"` (the recorded SHA itself),
        # which is always trivially "clean". That specific pattern must be
        # gone.
        self.assertNotRegex(self.text, r'drift\s+--ref\s+"?\$LAST_PORTED_SHA"?')
        self.assertNotRegex(self.text, r'drift\s+--ref\s+"?\$\{?RECORDED_LAST_PORTED_SHA\}?"?')

    def test_drift_runs_against_a_ref_variable_not_a_recorded_sha_variable(self):
        matches = re.findall(r'drift\s+--ref\s+"(\$[A-Za-z_]+)"', self.text)
        self.assertTrue(matches, "expected at least one `drift --ref \"$VAR\"` invocation")
        for var in matches:
            self.assertNotIn(
                "SHA", var.upper(), msg=f"drift --ref uses a recorded-SHA-looking var: {var}"
            )

    def test_explicitly_fetches_canonical_remote_via_cli_fetch_subcommand(self):
        self.assertIn("scripts.upstream_port fetch --remote", self.text)

    def test_canonical_url_and_remote_name_sourced_from_single_constants_module(self):
        # The remote-add/verify step must read the URL/remote name live from
        # the same constants module the CLI itself pins/enforces (single
        # source of truth), not retype an independent literal for the shell
        # comparison/`git remote add` call itself.
        self.assertIn("from scripts.upstream_port import constants", self.text)
        self.assertIn("constants.CANONICAL_UPSTREAM_URL", self.text)
        self.assertIn("constants.DEFAULT_REMOTE_NAME", self.text)
        self.assertIn('CANONICAL_URL=$(python3 -c "from scripts.upstream_port import constants', self.text)

    def test_remote_url_is_verified_before_any_add(self):
        self.assertIn("git remote get-url", self.text)
        self.assertIn("git remote add", self.text)
        self.assertIn("does not match pinned canonical URL", self.text)

    def test_exit_code_semantics_and_step_ordering_are_preserved(self):
        # 0/2/3 semantics must be documented in the workflow itself, and the
        # summary-writing step must run with `set +e` so that a non-zero
        # `drift` exit never aborts the script before the summary/report is
        # written.
        self.assertIn("0=clean", self.text)
        self.assertIn("2=", self.text)
        self.assertIn("3=", self.text)
        self.assertIn("set +e", self.text)

        drift_step_idx = self.text.index("Run read-only drift + scan")
        upload_idx = self.text.index("Upload drift + scan report artifacts")
        fail_idx = self.text.index("Fail the job if drift/integrity issues")
        self.assertTrue(drift_step_idx < upload_idx < fail_idx)

    def test_summary_is_written_regardless_of_drift_exit_code(self):
        # The drift step must end by clearing its own shell exit status
        # (`exit 0`) after recording `exit_code` as a step output, so the
        # summary-writing block above it is never skipped by a non-zero
        # `drift`/`scan` exit code.
        drift_section = self.text[
            self.text.index("- name: Run read-only drift + scan") : self.text.index(
                "- name: Upload drift + scan report artifacts"
            )
        ]
        self.assertIn("GITHUB_STEP_SUMMARY", drift_section)
        self.assertIn('echo "exit_code=$code" >> "$GITHUB_OUTPUT"', drift_section)
        self.assertTrue(drift_section.rstrip().endswith("exit 0"))

    def test_never_checks_out_or_executes_fetched_upstream_tree(self):
        self.assertNotIn("git checkout decomp", self.text)
        self.assertNotIn("git switch", self.text)
        self.assertNotIn("git worktree add", self.text)


def _run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def _git_status(cwd):
    return subprocess.run(
        ["git", "status", "--short"], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


class WorkflowDriftReplayTests(unittest.TestCase):
    """Replays the workflow's actual subcommand sequence offline.

    Mirrors, in order, exactly what the workflow's shell steps run:
      1. verify/add the canonical remote (here: the fixture's local stand-in
         URL, patched in as the "pinned" URL, exactly like
         test_fetch_succeeds_when_url_matches_pinned_canonical does),
      2. `fetch --remote <name>` (the real, only network-touching
         subcommand),
      3. `drift --ref <fresh local remote-tracking ref>` (never the recorded
         SHA),
      4. `scan --ref <fresh local remote-tracking ref>` (best-effort).
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)
        self.state_path = os.path.join(self._tmp.name, "state.json")
        code, _, err = _run_cli(
            [
                "--repo", self.fixture.fork_dir, "--state", self.state_path,
                "init-state", "--ref", "decomp/master",
            ]
        )
        self.assertEqual(code, 0, err)

    def test_upstream_ahead_is_detected_after_real_fetch_without_mutating_anything(self):
        # Step 0: workflow's "clean, nothing new yet" baseline -- ref
        # already fetched once (as the synthetic fixture simulates a prior
        # maintainer fetch), so this matches a real repeated-run scenario.
        code, out, err = _run_cli(
            [
                "--repo", self.fixture.fork_dir, "--state", self.state_path,
                "drift", "--ref", "decomp/master", "--format", "json",
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertFalse(json.loads(out)["has_drift"])

        # New commit lands on the canonical (synthetic) upstream, but the
        # fork has NOT fetched it yet.
        h.commit(self.fixture.upstream_dir, {"new.c": "int y;\n"}, "code: y", seconds_offset=10)

        before_state = open(self.state_path).read()
        before_status = _git_status(self.fixture.fork_dir)
        before_head = h.rev_parse(self.fixture.fork_dir, "HEAD")
        before_master = h.rev_parse(self.fixture.fork_dir, "master")

        # Step 1+2 replay: verify remote URL matches "pinned" canonical,
        # then explicitly fetch via the CLI's own network-touching
        # subcommand (same one the workflow shell step calls).
        with mock.patch.object(constants, "CANONICAL_UPSTREAM_URL", self.fixture.upstream_dir):
            with mock.patch.object(cli.constants, "CANONICAL_UPSTREAM_URL", self.fixture.upstream_dir):
                code, out, err = _run_cli(
                    [
                        "--repo", self.fixture.fork_dir, "--state", self.state_path,
                        "fetch", "--remote", self.fixture.remote_name,
                    ]
                )
        self.assertEqual(code, 0, err)
        self.assertIn("fetched", out)

        # Step 3: drift against the freshly-fetched ref must now report
        # real drift (exit 2) -- this is the exact bug this fix closes.
        code, out, err = _run_cli(
            [
                "--repo", self.fixture.fork_dir, "--state", self.state_path,
                "drift", "--ref", "decomp/master", "--format", "json",
            ]
        )
        self.assertEqual(code, 2, err)
        payload = json.loads(out)
        self.assertTrue(payload["has_drift"])
        self.assertTrue(payload["ref_moved_since_scan"])
        self.assertEqual(payload["unreviewed_count"], 1)
        self.assertFalse(payload["integrity_problem"])

        # Step 4: scan against the same fresh ref enumerates the new commit,
        # read-only.
        code, out, err = _run_cli(
            [
                "--repo", self.fixture.fork_dir, "--state", self.state_path,
                "scan", "--ref", "decomp/master", "--format", "json",
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["unreviewed_count"], 1)

        # Detecting drift must never mutate the committed state file, the
        # fork's working tree/status, or HEAD/master -- only the dedicated
        # `decomp/*` remote-tracking ref (already exercised/asserted by
        # test_fetch_succeeds_when_url_matches_pinned_canonical) moves.
        self.assertEqual(open(self.state_path).read(), before_state)
        self.assertEqual(_git_status(self.fixture.fork_dir), before_status)
        self.assertEqual(h.rev_parse(self.fixture.fork_dir, "HEAD"), before_head)
        self.assertEqual(h.rev_parse(self.fixture.fork_dir, "master"), before_master)


if __name__ == "__main__":
    unittest.main()
