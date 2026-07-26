import os
import subprocess
import tempfile
import unittest

from scripts.upstream_port import report as report_mod
from tests.upstream_port import helpers as h


class ReportPatchTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)
        # Make the output directory gitignored in the fork repo, mirroring
        # the real repo's dedicated ignore rule for upstream-port output.
        h.write_files(self.fixture.fork_dir, {".gitignore": "/out/\n"})
        subprocess.run(["git", "add", "-A"], cwd=self.fixture.fork_dir, check=True)
        subprocess.run(
            ["git", "-c", "user.name=x", "-c", "user.email=x@x.invalid", "commit", "-q", "-m", "add gitignore"],
            cwd=self.fixture.fork_dir, check=True,
        )
        self.out_dir = os.path.join(self.fixture.fork_dir, "out", "batch")

    def test_generate_writes_patch_and_report_for_selected_sha(self):
        sha1 = h.commit(
            self.fixture.upstream_dir, {"src/battle.c": "int x;\n"}, "code: add battle", seconds_offset=10
        )
        h.refetch(self.fixture)

        report = report_mod.generate(
            self.fixture.fork_dir, self.fixture.remote_name, "decomp/master", [sha1], self.out_dir
        )
        self.assertEqual(report["selected_count"], 1)
        patch_path = os.path.join(self.out_dir, report["entries"][0]["patch_filename"])
        self.assertTrue(os.path.exists(patch_path))
        with open(patch_path) as fh:
            patch_text = fh.read()
        self.assertIn(sha1, patch_text)
        self.assertIn(h.FIXED_AUTHOR_EMAIL, patch_text)
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, "report.json")))
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, "report.md")))

    def test_unselected_sha_gets_no_patch(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        sha2 = h.commit(self.fixture.upstream_dir, {"b.txt": "2"}, "c2", seconds_offset=20)
        h.refetch(self.fixture)

        report = report_mod.generate(
            self.fixture.fork_dir, self.fixture.remote_name, "decomp/master", [sha1], self.out_dir
        )
        self.assertEqual(report["selected_count"], 1)
        filenames = os.listdir(self.out_dir)
        self.assertTrue(any(sha1[:12] in f for f in filenames))
        self.assertFalse(any(sha2[:12] in f for f in filenames))

    def test_rejects_sha_not_reachable_from_allowed_refs(self):
        h.create_branch(self.fixture.upstream_dir, "side", self.fixture.base_sha)
        h.checkout(self.fixture.upstream_dir, "side")
        side_sha = h.commit(self.fixture.upstream_dir, {"side.txt": "1"}, "side commit", seconds_offset=5)
        h.checkout(self.fixture.upstream_dir, "master")
        # Note: side branch is never fetched into the fork's decomp remote,
        # and never reachable from decomp/master -- must be rejected.
        with self.assertRaises(report_mod.SelectionError):
            report_mod.generate(
                self.fixture.fork_dir, self.fixture.remote_name, "decomp/master", [side_sha], self.out_dir
            )

    def test_rejects_malformed_sha(self):
        with self.assertRaises(report_mod.SelectionError):
            report_mod.generate(
                self.fixture.fork_dir, self.fixture.remote_name, "decomp/master", ["not-a-sha"], self.out_dir
            )

    def test_rejects_empty_selection(self):
        with self.assertRaises(report_mod.SelectionError):
            report_mod.generate(
                self.fixture.fork_dir, self.fixture.remote_name, "decomp/master", [], self.out_dir
            )

    def test_refuses_non_ignored_output_dir(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        not_ignored = os.path.join(self.fixture.fork_dir, "tracked-output-dir")
        with self.assertRaises(report_mod.OutputSafetyError):
            report_mod.generate(
                self.fixture.fork_dir, self.fixture.remote_name, "decomp/master", [sha1], not_ignored
            )

    def test_git_status_clean_after_generate(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        report_mod.generate(
            self.fixture.fork_dir, self.fixture.remote_name, "decomp/master", [sha1], self.out_dir
        )
        status = subprocess.run(
            ["git", "status", "--short"], cwd=self.fixture.fork_dir,
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertEqual(status.strip(), "")


if __name__ == "__main__":
    unittest.main()
