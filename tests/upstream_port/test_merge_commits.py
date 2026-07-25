"""Coverage for the merge-commit determinism audit finding.

Plain `git diff-tree`/`git format-patch` have sharp, silent edges on merge
commits (2+ parents): by default `diff-tree` returns an empty path list for
a merge, and `format-patch -1 --stdout <merge-sha>` silently walks past the
merge and formats a *different*, non-merge ancestor commit instead. Both are
exactly the kind of "quietly wrong" behavior this fix closes:

  - `git_utils.changed_paths()` must return the deterministic, sorted UNION
    of the diff against every parent for a merge commit (never silently
    empty), while still behaving correctly for ordinary and root commits.
  - `git_utils.format_patch_text()` / `report.generate()` must refuse a
    merge commit outright, before any output directory is created or any
    file is written -- never emit an empty or misleading patch.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from scripts.upstream_port import git_utils, report as report_mod
from tests.upstream_port import helpers as h


class ChangedPathsRootAndOrdinaryCommitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo_dir = os.path.join(self._tmp.name, "repo")
        h.init_repo(self.repo_dir)

    def test_root_commit_changed_paths_is_not_silently_empty(self):
        # Plain `git diff-tree --name-only` (no --root) silently returns
        # nothing for a root commit -- this is the regression this test
        # guards against.
        root_sha = h.commit(self.repo_dir, {"a.txt": "1\n", "sub/b.txt": "2\n"}, "root commit")
        paths = git_utils.changed_paths(root_sha, self.repo_dir)
        self.assertEqual(paths, ["a.txt", "sub/b.txt"])

    def test_ordinary_single_parent_commit_changed_paths(self):
        h.commit(self.repo_dir, {"a.txt": "1\n"}, "root", seconds_offset=0)
        sha2 = h.commit(self.repo_dir, {"b.txt": "2\n"}, "second", seconds_offset=10)
        paths = git_utils.changed_paths(sha2, self.repo_dir)
        self.assertEqual(paths, ["b.txt"])


class MergeCommitChangedPathsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo_dir = os.path.join(self._tmp.name, "repo")
        h.init_repo(self.repo_dir)
        self.base_sha = h.commit(self.repo_dir, {"base.txt": "0\n"}, "base", seconds_offset=0)
        h.create_branch(self.repo_dir, "topic-a", self.base_sha)
        h.create_branch(self.repo_dir, "topic-b", self.base_sha)

        h.checkout(self.repo_dir, "topic-a")
        self.sha_a = h.commit(
            self.repo_dir, {"a-only.txt": "a\n"}, "topic-a: add a-only.txt", seconds_offset=10
        )

        h.checkout(self.repo_dir, "topic-b")
        self.sha_b = h.commit(
            self.repo_dir, {"b-only.txt": "b\n"}, "topic-b: add b-only.txt", seconds_offset=20
        )

        h.checkout(self.repo_dir, "master")
        h.run_git(["merge", "-q", "topic-a"], self.repo_dir)  # fast-forward master to topic-a
        self.merge_sha = h.merge_no_ff(
            self.repo_dir, "topic-b", "merge topic-b into master", seconds_offset=30
        )

    def test_is_merge_commit_detects_two_parents(self):
        self.assertTrue(git_utils.is_merge_commit(self.merge_sha, self.repo_dir))
        self.assertFalse(git_utils.is_merge_commit(self.sha_a, self.repo_dir))
        parents = git_utils.commit_parents(self.merge_sha, self.repo_dir)
        self.assertEqual(len(parents), 2)
        self.assertIn(self.sha_a, parents)
        self.assertIn(self.sha_b, parents)

    def test_changed_paths_is_deterministic_sorted_union_not_empty(self):
        # This is the exact regression: plain `git diff-tree --name-only`
        # with no flags returns [] for a merge commit by default.
        paths = git_utils.changed_paths(self.merge_sha, self.repo_dir)
        self.assertEqual(paths, ["a-only.txt", "b-only.txt"])
        # Deterministic irrespective of parent traversal order: recomputing
        # must give byte-identical output.
        self.assertEqual(paths, git_utils.changed_paths(self.merge_sha, self.repo_dir))

    def test_format_patch_text_refuses_merge_commit(self):
        with self.assertRaises(git_utils.GitError) as ctx:
            git_utils.format_patch_text(self.merge_sha, self.repo_dir)
        self.assertIn(self.merge_sha, str(ctx.exception))
        self.assertIn("merge commit", str(ctx.exception))


class MergeCommitScanAndReportIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)

        h.create_branch(self.fixture.upstream_dir, "topic-a", self.fixture.base_sha)
        h.create_branch(self.fixture.upstream_dir, "topic-b", self.fixture.base_sha)

        h.checkout(self.fixture.upstream_dir, "topic-a")
        self.sha_a = h.commit(
            self.fixture.upstream_dir, {"a-only.txt": "a\n"}, "topic-a: add a-only.txt",
            seconds_offset=10,
        )

        h.checkout(self.fixture.upstream_dir, "topic-b")
        self.sha_b = h.commit(
            self.fixture.upstream_dir, {"b-only.txt": "b\n"}, "topic-b: add b-only.txt",
            seconds_offset=20,
        )

        h.checkout(self.fixture.upstream_dir, "master")
        h.run_git(["merge", "-q", "topic-a"], self.fixture.upstream_dir)
        self.merge_sha = h.merge_no_ff(
            self.fixture.upstream_dir, "topic-b", "merge topic-b into master",
            seconds_offset=30,
        )
        h.refetch(self.fixture)

        from scripts.upstream_port import constants, state as state_mod

        self.state = state_mod.default_state(
            constants.CANONICAL_UPSTREAM_URL,
            self.fixture.remote_name,
            "decomp/master",
            self.fixture.base_sha,
        )
        self.out_dir = os.path.join(self.fixture.fork_dir, "build", "upstream-port", "batch")

    def test_scan_classifies_merge_commit_with_union_paths_in_order(self):
        from scripts.upstream_port import scan as scan_mod

        result = scan_mod.scan(self.fixture.fork_dir, "decomp/master", self.state)
        shas = [c.sha for c in result.commits]
        self.assertIn(self.merge_sha, shas)
        merge_report = next(c for c in result.commits if c.sha == self.merge_sha)
        self.assertEqual(merge_report.changed_paths, ["a-only.txt", "b-only.txt"])
        self.assertEqual(sorted(merge_report.categories.keys()), ["a-only.txt", "b-only.txt"])

    def test_report_rejects_merge_commit_selection_before_any_write(self):
        self.assertFalse(os.path.exists(self.out_dir))
        with self.assertRaises(report_mod.SelectionError) as ctx:
            report_mod.generate(
                self.fixture.fork_dir, self.fixture.remote_name, "decomp/master",
                [self.merge_sha], self.out_dir,
            )
        message = str(ctx.exception)
        self.assertIn(self.merge_sha, message)
        self.assertIn("merge commit", message)
        # Fail-closed: no output directory, no partial report/patch files.
        self.assertFalse(os.path.exists(self.out_dir))

    def test_report_rejects_merge_commit_even_when_mixed_with_valid_sha(self):
        # A mixed selection (one valid non-merge SHA + the merge SHA) must
        # still be rejected wholesale, with no partial output written for
        # the valid SHA either.
        with self.assertRaises(report_mod.SelectionError):
            report_mod.generate(
                self.fixture.fork_dir, self.fixture.remote_name, "decomp/master",
                [self.sha_a, self.merge_sha], self.out_dir,
            )
        self.assertFalse(os.path.exists(self.out_dir))


if __name__ == "__main__":
    unittest.main()
