import subprocess
import tempfile
import unittest

from scripts.upstream_port import constants, drift as drift_mod, state as state_mod
from tests.upstream_port import helpers as h


class DriftTests(unittest.TestCase):
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

    def test_clean_state_no_drift(self):
        report = drift_mod.compute_drift(self.fixture.fork_dir, "decomp/master", self.state)
        self.assertFalse(report.has_drift)
        self.assertFalse(report.integrity_problem)
        self.assertEqual(report.exit_code(), 0)
        self.assertEqual(report.unreviewed_count, 0)

    def test_ref_moved_since_scan_detected(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        report = drift_mod.compute_drift(self.fixture.fork_dir, "decomp/master", self.state)
        self.assertTrue(report.ref_moved_since_scan)
        self.assertTrue(report.has_drift)
        self.assertEqual(report.unreviewed_count, 1)
        self.assertEqual(report.exit_code(), 2)

    def test_unreachable_state_sha_is_integrity_problem(self):
        self.state["last_scanned"]["sha"] = "f" * 40  # never-existing object
        report = drift_mod.compute_drift(self.fixture.fork_dir, "decomp/master", self.state)
        self.assertFalse(report.last_scanned_reachable)
        self.assertTrue(report.integrity_problem)
        self.assertEqual(report.exit_code(), 3)

    def test_diverged_histories_is_integrity_problem(self):
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

        self.state["last_ported"] = {"ref": "decomp/side", "sha": side_sha}
        self.state["last_scanned"] = {"ref": "decomp/side", "sha": side_sha}
        report = drift_mod.compute_drift(self.fixture.fork_dir, "decomp/master", self.state)
        self.assertTrue(report.histories_diverged)
        self.assertTrue(report.integrity_problem)
        self.assertEqual(report.exit_code(), 3)
        self.assertTrue(any("diverged" in issue for issue in report.issues))

    def test_unresolvable_ref_is_integrity_problem(self):
        report = drift_mod.compute_drift(self.fixture.fork_dir, "decomp/does-not-exist", self.state)
        self.assertIsNone(report.ref_sha)
        self.assertTrue(report.integrity_problem)
        self.assertEqual(report.exit_code(), 3)


if __name__ == "__main__":
    unittest.main()
