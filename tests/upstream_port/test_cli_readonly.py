import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.upstream_port import cli, constants
from tests.upstream_port import helpers as h


def _run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def _git_status(cwd):
    return subprocess.run(
        ["git", "status", "--short"], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


class CliReadOnlyDefaultsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)
        self.state_path = os.path.join(self._tmp.name, "state.json")
        code, _, _ = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path, "init-state", "--ref", "decomp/master"]
        )
        self.assertEqual(code, 0)

    def test_scan_does_not_mutate_state_file_or_worktree(self):
        h.commit(self.fixture.upstream_dir, {"src/x.c": "int x;\n"}, "code: x", seconds_offset=10)
        h.refetch(self.fixture)

        with open(self.state_path) as fh:
            before_state = fh.read()
        before_status = _git_status(self.fixture.fork_dir)
        before_decomp_master = h.rev_parse(self.fixture.fork_dir, "decomp/master")

        code, out, _ = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path, "scan", "--ref", "decomp/master", "--format", "json"]
        )
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["unreviewed_count"], 1)

        with open(self.state_path) as fh:
            self.assertEqual(fh.read(), before_state)
        self.assertEqual(_git_status(self.fixture.fork_dir), before_status)
        self.assertEqual(h.rev_parse(self.fixture.fork_dir, "decomp/master"), before_decomp_master)

    def test_drift_is_read_only_and_exit_code_reflects_drift(self):
        code, _, _ = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path, "drift", "--ref", "decomp/master"]
        )
        self.assertEqual(code, 0)  # clean, nothing new yet

        h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        code, _, _ = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path, "drift", "--ref", "decomp/master"]
        )
        self.assertEqual(code, 2)  # drift detected, but still just a read

    def test_report_rejects_sha_outside_allowed_range(self):
        h.create_branch(self.fixture.upstream_dir, "side", self.fixture.base_sha)
        h.checkout(self.fixture.upstream_dir, "side")
        side_sha = h.commit(self.fixture.upstream_dir, {"side.txt": "1"}, "side", seconds_offset=5)
        h.checkout(self.fixture.upstream_dir, "master")

        code, _, err = _run_cli(
            [
                "--repo", self.fixture.fork_dir, "--state", self.state_path,
                "report", "--ref", "decomp/master", "--sha", side_sha,
                "--out-dir", os.path.join(self.fixture.fork_dir, "build", "upstream-port", "x"),
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("rejected", err)

    def test_fetch_rejects_mismatched_remote_url(self):
        code, out, err = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path, "fetch", "--remote", self.fixture.remote_name]
        )
        # Fixture's remote points at a local tmp path, never the pinned
        # canonical URL, so this must be rejected before any network-ish
        # operation is attempted.
        self.assertEqual(code, 1)
        self.assertIn("refusing to fetch", err)

    def test_fetch_succeeds_when_url_matches_pinned_canonical(self):
        with mock.patch.object(constants, "CANONICAL_UPSTREAM_URL", self.fixture.upstream_dir):
            with mock.patch.object(cli.constants, "CANONICAL_UPSTREAM_URL", self.fixture.upstream_dir):
                code, out, _ = _run_cli(
                    ["--repo", self.fixture.fork_dir, "fetch", "--remote", self.fixture.remote_name]
                )
        self.assertEqual(code, 0)
        self.assertIn("fetched", out)


class CliUpdateStateFlowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)
        self.state_path = os.path.join(self._tmp.name, "state.json")
        _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path, "init-state", "--ref", "decomp/master"]
        )

    def test_mark_then_advance_ported_end_to_end(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)

        code, _, err = _run_cli(
            [
                "--repo", self.fixture.fork_dir, "--state", self.state_path,
                "update-state", "mark", "--sha", sha1, "--status", "ported",
                "--rationale", "trivial", "--evidence", "diffed by hand", "--now", "2024-01-01T00:00:00Z",
            ]
        )
        self.assertEqual(code, 0, err)

        code, _, err = _run_cli(
            [
                "--repo", self.fixture.fork_dir, "--state", self.state_path,
                "update-state", "advance-ported", "--ref", "decomp/master",
            ]
        )
        self.assertEqual(code, 0, err)

        with open(self.state_path) as fh:
            state = json.load(fh)
        self.assertEqual(state["last_ported"]["sha"], sha1)
        self.assertEqual(state["commits"][sha1]["status"], "ported")

    def test_advance_ported_blocked_without_marking(self):
        h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        code, _, err = _run_cli(
            [
                "--repo", self.fixture.fork_dir, "--state", self.state_path,
                "update-state", "advance-ported", "--ref", "decomp/master",
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("not yet ported", err)


if __name__ == "__main__":
    unittest.main()
