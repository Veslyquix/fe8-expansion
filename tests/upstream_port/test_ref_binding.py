"""Adversarial coverage for the Issue #12 state-boundary integrity fix:
`update-state record-scan` and `update-state advance-ported` (and their
underlying `state.record_scan` / `state.advance_last_ported` functions) must
bind tightly to the selected upstream `--ref`'s own resolved local Git tip --
never accept an expansion-side, unrelated, diverged, past-the-tip, or
stale-but-related SHA -- and must never mutate state on rejection.

All fixtures are offline, synthetic, filesystem-only Git repos (see
tests/upstream_port/helpers.py) -- no network access, and upstream
"commits" are never executed, only read.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest

from scripts.upstream_port import cli, constants, git_utils, state as state_mod
from tests.upstream_port import helpers as h


def _run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class RecordScanRefBindingTests(unittest.TestCase):
    """Direct state.record_scan() coverage: explicit AND implicit paths."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)
        self.state = state_mod.default_state(
            constants.CANONICAL_UPSTREAM_URL,
            self.fixture.remote_name,
            "decomp/master",
            self.fixture.base_sha,
        )

    def test_implicit_record_scan_records_exact_resolved_tip(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        state_mod.record_scan(self.state, "decomp/master", None, self.fixture.fork_dir)
        self.assertEqual(self.state["last_scanned"]["sha"], sha1)
        self.assertEqual(
            self.state["last_scanned"]["sha"],
            git_utils.resolve_commit_sha("decomp/master", self.fixture.fork_dir),
        )

    def test_explicit_record_scan_matching_resolved_tip_ok(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        state_mod.record_scan(self.state, "decomp/master", sha1, self.fixture.fork_dir)
        self.assertEqual(self.state["last_scanned"]["sha"], sha1)

    def test_explicit_record_scan_old_but_related_sha_rejected(self):
        """A real, ancestor-reachable, but no-longer-the-tip SHA on the
        SAME branch must be rejected: record-scan binds to the ref's exact
        current tip, not merely "some ancestor of it"."""
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        sha2 = h.commit(self.fixture.upstream_dir, {"b.txt": "2"}, "c2", seconds_offset=20)
        h.refetch(self.fixture)
        before = json.dumps(self.state, sort_keys=True)
        with self.assertRaises(state_mod.StateError) as ctx:
            state_mod.record_scan(self.state, "decomp/master", sha1, self.fixture.fork_dir)
        self.assertIn(sha1, str(ctx.exception))
        self.assertIn(sha2, str(ctx.exception))
        self.assertEqual(json.dumps(self.state, sort_keys=True), before)

    def test_explicit_record_scan_expansion_only_sha_rejected(self):
        """A commit that only exists on the FORK's own local history
        (never fetched from/reachable via the canonical decomp remote) must
        be rejected outright, even though it's a real, locally-resolvable
        commit object."""
        expansion_sha = h.commit(
            self.fixture.fork_dir, {"expansion_only.txt": "local-only"},
            "expansion-side: not from upstream", seconds_offset=1,
            author_name=h.FIXED_FORK_AUTHOR_NAME, author_email=h.FIXED_FORK_AUTHOR_EMAIL,
        )
        before = json.dumps(self.state, sort_keys=True)
        with self.assertRaises(state_mod.StateError) as ctx:
            state_mod.record_scan(self.state, "decomp/master", expansion_sha, self.fixture.fork_dir)
        self.assertIn(expansion_sha, str(ctx.exception))
        self.assertEqual(json.dumps(self.state, sort_keys=True), before)

    def test_explicit_record_scan_non_full_sha_rejected(self):
        with self.assertRaises(state_mod.StateError):
            state_mod.record_scan(self.state, "decomp/master", "abc123", self.fixture.fork_dir)

    def test_explicit_record_scan_backward_still_rejected(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        state_mod.record_scan(self.state, "decomp/master", sha1, self.fixture.fork_dir)
        with self.assertRaises(state_mod.StateError):
            state_mod.record_scan(self.state, "decomp/master", self.fixture.base_sha, self.fixture.fork_dir)


class AdvancePortedRefBindingTests(unittest.TestCase):
    """Direct state.advance_last_ported() coverage: current-boundary ..
    ref-tip ancestry corridor, both explicit and implicit paths."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)
        self.state = state_mod.default_state(
            constants.CANONICAL_UPSTREAM_URL,
            self.fixture.remote_name,
            "decomp/master",
            self.fixture.base_sha,
        )

    def _mark_terminal(self, sha, status="ported"):
        state_mod.upsert_commit_status(
            self.state, sha, new_status=status, author_name="A", author_email="a@x.invalid",
            subject="s", rationale="r", validation_evidence="e", updated_at="2024-01-01T00:00:00Z",
        )

    def test_implicit_advance_records_exact_resolved_tip(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        self._mark_terminal(sha1)
        state_mod.advance_last_ported(self.state, "decomp/master", None, self.fixture.fork_dir)
        self.assertEqual(self.state["last_ported"]["sha"], sha1)

    def test_explicit_intermediate_candidate_within_corridor_accepted(self):
        """A candidate that is neither the OLD boundary nor ref's exact tip
        -- but IS a descendant of the old boundary AND an ancestor of the
        ref tip -- must be accepted once every commit up to it is
        accounted for (this is the legitimate "partial batch" workflow)."""
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        sha2 = h.commit(self.fixture.upstream_dir, {"b.txt": "2"}, "c2", seconds_offset=20)
        h.refetch(self.fixture)
        self._mark_terminal(sha1)
        state_mod.advance_last_ported(self.state, "decomp/master", sha1, self.fixture.fork_dir)
        self.assertEqual(self.state["last_ported"]["sha"], sha1)
        # Ref tip (sha2) has NOT been reached yet -- still an unaccounted,
        # legitimately-pending commit, not a corridor violation.
        self.assertNotIn(sha2, self.state["commits"])

    def test_explicit_expansion_only_candidate_rejected_even_if_descendant_of_old_boundary(self):
        """The exact vulnerability this fix closes: the OLD code only
        checked "is candidate a descendant of the current boundary", which
        an expansion-side (fork-local, never-upstream) commit can trivially
        satisfy since the fork's own history also descends from the same
        base commit. The NEW ref-tip-ancestor check must catch it."""
        expansion_sha = h.commit(
            self.fixture.fork_dir, {"expansion_only.txt": "local-only"},
            "expansion-side: not from upstream", seconds_offset=1,
            author_name=h.FIXED_FORK_AUTHOR_NAME, author_email=h.FIXED_FORK_AUTHOR_EMAIL,
        )
        # Sanity: this expansion commit IS a descendant of the current
        # last_ported boundary (the shared base) -- i.e. the OLD check
        # alone would have wrongly let this through.
        self.assertTrue(
            git_utils.is_ancestor(self.fixture.base_sha, expansion_sha, self.fixture.fork_dir)
        )
        before = json.dumps(self.state, sort_keys=True)
        with self.assertRaises(state_mod.StateError) as ctx:
            state_mod.advance_last_ported(
                self.state, "decomp/master", expansion_sha, self.fixture.fork_dir
            )
        self.assertIn(expansion_sha, str(ctx.exception))
        self.assertEqual(json.dumps(self.state, sort_keys=True), before)

    def test_explicit_diverged_side_branch_candidate_rejected(self):
        """A commit reachable only via a diverged/forked upstream branch
        (e.g. `decomp/side`), not via the selected `--ref` (`decomp/master`),
        must be rejected even though it's a genuine, locally-resolvable
        upstream-remote commit."""
        h.create_branch(self.fixture.upstream_dir, "side", self.fixture.base_sha)
        h.checkout(self.fixture.upstream_dir, "side")
        side_sha = h.commit(self.fixture.upstream_dir, {"side.txt": "1"}, "side commit", seconds_offset=5)
        h.checkout(self.fixture.upstream_dir, "master")
        h.commit(self.fixture.upstream_dir, {"master.txt": "1"}, "master commit", seconds_offset=10)
        subprocess.run(
            ["git", "fetch", "-q", self.fixture.upstream_dir, "side:refs/remotes/decomp/side"],
            cwd=self.fixture.fork_dir, check=True,
        )
        h.refetch(self.fixture)

        before = json.dumps(self.state, sort_keys=True)
        with self.assertRaises(state_mod.StateError) as ctx:
            state_mod.advance_last_ported(
                self.state, "decomp/master", side_sha, self.fixture.fork_dir
            )
        self.assertIn(side_sha, str(ctx.exception))
        self.assertEqual(json.dumps(self.state, sort_keys=True), before)

    def test_explicit_past_the_tip_candidate_rejected(self):
        """A candidate SHA that is a DESCENDANT of the selected ref's
        resolved tip (i.e. "after" it, not fetched/selected) must be
        rejected -- not just "not an ancestor of the old boundary"."""
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)  # decomp/master tip is now sha1
        sha2 = h.commit(self.fixture.upstream_dir, {"b.txt": "2"}, "c2", seconds_offset=20)
        # Deliberately do NOT refetch again -- decomp/master locally still
        # resolves to sha1, but sha2 is already locally resolvable because
        # both repos share the same object store via the local filesystem
        # remote (simulating a caller passing a SHA they saw upstream but
        # that the local ref hasn't caught up to yet).
        subprocess.run(
            ["git", "fetch", "-q", self.fixture.upstream_dir, "master"],
            cwd=self.fixture.fork_dir, check=True,
        )  # updates FETCH_HEAD/objects only, not decomp/master
        self.assertTrue(git_utils.object_exists(sha2, self.fixture.fork_dir))
        self.assertEqual(
            git_utils.resolve_commit_sha("decomp/master", self.fixture.fork_dir), sha1
        )
        before = json.dumps(self.state, sort_keys=True)
        with self.assertRaises(state_mod.StateError) as ctx:
            state_mod.advance_last_ported(
                self.state, "decomp/master", sha2, self.fixture.fork_dir
            )
        self.assertIn(sha2, str(ctx.exception))
        self.assertEqual(json.dumps(self.state, sort_keys=True), before)

    def test_explicit_unaccounted_intermediate_still_blocked(self):
        """Corridor membership alone is not sufficient -- the existing
        unaccounted-commits guard must still apply to a valid, in-corridor
        candidate."""
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        with self.assertRaises(state_mod.StateError) as ctx:
            state_mod.advance_last_ported(self.state, "decomp/master", sha1, self.fixture.fork_dir)
        self.assertIn(sha1, str(ctx.exception))
        self.assertIn("not yet ported/skipped/superseded", str(ctx.exception))


class CliRefBindingIntegrationTests(unittest.TestCase):
    """End-to-end CLI coverage: rejected calls never mutate the on-disk
    state file (byte-identical before/after), and the CLI error surfaces
    the same actionable message as the underlying state.py check."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)
        self.state_path = os.path.join(self._tmp.name, "state.json")
        code, _, err = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path, "init-state", "--ref", "decomp/master"]
        )
        self.assertEqual(code, 0, err)

    def test_cli_record_scan_rejects_expansion_sha_and_leaves_state_untouched(self):
        expansion_sha = h.commit(
            self.fixture.fork_dir, {"expansion_only.txt": "local-only"},
            "expansion-side: not from upstream", seconds_offset=1,
            author_name=h.FIXED_FORK_AUTHOR_NAME, author_email=h.FIXED_FORK_AUTHOR_EMAIL,
        )
        with open(self.state_path) as fh:
            before = fh.read()
        code, _, err = _run_cli(
            [
                "--repo", self.fixture.fork_dir, "--state", self.state_path,
                "update-state", "record-scan", "--ref", "decomp/master", "--sha", expansion_sha,
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("does not exactly match", err)
        with open(self.state_path) as fh:
            after = fh.read()
        self.assertEqual(before, after)

    def test_cli_advance_ported_rejects_diverged_candidate_and_leaves_state_untouched(self):
        h.create_branch(self.fixture.upstream_dir, "side", self.fixture.base_sha)
        h.checkout(self.fixture.upstream_dir, "side")
        side_sha = h.commit(self.fixture.upstream_dir, {"side.txt": "1"}, "side commit", seconds_offset=5)
        h.checkout(self.fixture.upstream_dir, "master")
        subprocess.run(
            ["git", "fetch", "-q", self.fixture.upstream_dir, "side:refs/remotes/decomp/side"],
            cwd=self.fixture.fork_dir, check=True,
        )
        h.refetch(self.fixture)

        with open(self.state_path) as fh:
            before = fh.read()
        code, _, err = _run_cli(
            [
                "--repo", self.fixture.fork_dir, "--state", self.state_path,
                "update-state", "advance-ported", "--ref", "decomp/master", "--sha", side_sha,
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("ancestry corridor", err)
        with open(self.state_path) as fh:
            after = fh.read()
        self.assertEqual(before, after)

    def test_cli_advance_ported_implicit_path_records_exact_tip(self):
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


if __name__ == "__main__":
    unittest.main()
