import tempfile
import unittest

from scripts.upstream_port import constants, scan as scan_mod, state as state_mod
from tests.upstream_port import helpers as h


class ScanTests(unittest.TestCase):
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

    def test_scan_lists_unreviewed_commits_oldest_first(self):
        sha1 = h.commit(
            self.fixture.upstream_dir, {"Makefile": "all:\n\techo hi\n"}, "build: tweak", seconds_offset=10
        )
        sha2 = h.commit(
            self.fixture.upstream_dir, {"src/battle.c": "int x;\n"}, "code: add battle", seconds_offset=20
        )
        h.refetch(self.fixture)

        result = scan_mod.scan(self.fixture.fork_dir, "decomp/master", self.state)
        self.assertEqual(result.baseline_sha, self.fixture.base_sha)
        self.assertEqual([c.sha for c in result.commits], [sha1, sha2])
        self.assertEqual(result.commits[0].status, "pending")
        self.assertIn("modern-build-divergence-risk", result.commits[0].risk_flags)
        self.assertEqual(result.commits[1].categories["src/battle.c"], "code")
        self.assertEqual(result.commits[1].risk_flags, [])

    def test_scan_reflects_recorded_status(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        state_mod.upsert_commit_status(
            self.state, sha1, new_status="skipped", author_name="A", author_email="a@x.invalid",
            subject="c1", rationale="not needed", validation_evidence="reviewed", updated_at="2024-01-01T00:00:00Z",
        )
        result = scan_mod.scan(self.fixture.fork_dir, "decomp/master", self.state)
        self.assertEqual(result.commits[0].status, "skipped")

    def test_scan_empty_when_up_to_date(self):
        result = scan_mod.scan(self.fixture.fork_dir, "decomp/master", self.state)
        self.assertEqual(result.commits, [])
        self.assertEqual(result.unreviewed_count if hasattr(result, "unreviewed_count") else len(result.commits), 0)

    def test_scan_boundary_error_on_diverged_history(self):
        # Move last_ported to a SHA that only exists on a divergent branch.
        h.create_branch(self.fixture.upstream_dir, "side", self.fixture.base_sha)
        h.checkout(self.fixture.upstream_dir, "side")
        side_sha = h.commit(self.fixture.upstream_dir, {"side.txt": "1"}, "side commit", seconds_offset=5)
        h.checkout(self.fixture.upstream_dir, "master")
        h.commit(self.fixture.upstream_dir, {"master.txt": "1"}, "master commit", seconds_offset=10)
        import subprocess
        subprocess.run(
            ["git", "fetch", "-q", self.fixture.upstream_dir, "side:refs/remotes/decomp/side"],
            cwd=self.fixture.fork_dir, check=True,
        )
        h.refetch(self.fixture)

        self.state["last_ported"] = {"ref": "decomp/side", "sha": side_sha}
        with self.assertRaises(scan_mod.ScanBoundaryError):
            scan_mod.scan(self.fixture.fork_dir, "decomp/master", self.state)

    def test_render_text_contains_key_fields(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        result = scan_mod.scan(self.fixture.fork_dir, "decomp/master", self.state)
        text = scan_mod.render_text(result)
        self.assertIn(sha1, text)
        self.assertIn("unreviewed commits: 1", text)


if __name__ == "__main__":
    unittest.main()
