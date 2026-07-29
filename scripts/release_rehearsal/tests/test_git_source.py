"""Tests for scripts/release_rehearsal/git_source.py (issue #9)."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import git_source as gs


def _git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _init_repo(root: Path) -> None:
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "Tester", cwd=root)


class IsGitRepoTests(unittest.TestCase):
    def test_non_git_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(gs.is_git_repo(Path(tmp)))

    def test_real_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            self.assertTrue(gs.is_git_repo(root))

    def test_real_repository_state(self):
        self.assertTrue(gs.is_git_repo(ROOT))


class ResolveShaTests(unittest.TestCase):
    def test_resolves_head_to_exact_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            self.assertRegex(sha, r"^[0-9a-f]{40}$")
            self.assertEqual(sha, _git("rev-parse", "HEAD", cwd=root).strip())

    def test_unresolvable_revision_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            with self.assertRaises(gs.GitSourceError):
                gs.resolve_sha(root, "not-a-real-ref")

    def test_real_repo_head(self):
        sha = gs.resolve_sha(ROOT, "HEAD")
        self.assertRegex(sha, r"^[0-9a-f]{40}$")


class IsWorktreeCleanTests(unittest.TestCase):
    def test_clean_after_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            self.assertTrue(gs.is_worktree_clean(root))

    def test_dirty_after_unstaged_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            (root / "f.txt").write_text("mutated")
            self.assertFalse(gs.is_worktree_clean(root))

    def test_dirty_after_staged_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            (root / "f.txt").write_text("mutated")
            _git("add", "-A", cwd=root)
            self.assertFalse(gs.is_worktree_clean(root))


class ListTreeTests(unittest.TestCase):
    def test_lists_regular_files_with_correct_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int x;")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = gs.list_tree(root, sha)
            paths = {entry.path: entry for entry in entries}
            self.assertIn("src/main.c", paths)
            self.assertEqual(paths["src/main.c"].mode, gs.MODE_REGULAR)
            self.assertTrue(paths["src/main.c"].is_safe_blob)
            self.assertFalse(paths["src/main.c"].is_gitlink)
            self.assertFalse(paths["src/main.c"].is_symlink)

    def test_lists_executable_bit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            script = root / "run.sh"
            script.write_text("#!/bin/sh\necho hi\n")
            script.chmod(0o755)
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = {entry.path: entry for entry in gs.list_tree(root, sha)}
            self.assertEqual(entries["run.sh"].mode, gs.MODE_EXECUTABLE)
            self.assertTrue(entries["run.sh"].is_safe_blob)

    def test_lists_symlink_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "real.txt").write_text("x")
            (root / "link.txt").symlink_to("real.txt")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = {entry.path: entry for entry in gs.list_tree(root, sha)}
            self.assertEqual(entries["link.txt"].mode, gs.MODE_SYMLINK)
            self.assertTrue(entries["link.txt"].is_symlink)
            self.assertFalse(entries["link.txt"].is_safe_blob)

    def test_gitlink_mode_and_object_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)

            nested = Path(tmp) / "nested"
            nested.mkdir()
            _init_repo(nested)
            (nested / "n.txt").write_text("y")
            _git("add", "-A", cwd=nested)
            _git("commit", "-q", "-m", "nested", cwd=nested)
            nested_sha = _git("rev-parse", "HEAD", cwd=nested).strip()

            _git("update-index", "--add", "--cacheinfo", f"160000,{nested_sha},vendor", cwd=root)
            _git("commit", "-q", "-m", "add gitlink", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = {entry.path: entry for entry in gs.list_tree(root, sha)}
            self.assertEqual(entries["vendor"].mode, gs.MODE_GITLINK)
            self.assertEqual(entries["vendor"].obj_type, "commit")
            self.assertEqual(entries["vendor"].object_id, nested_sha)
            self.assertTrue(entries["vendor"].is_gitlink)

    def test_real_repo_mgfembp_is_gitlink(self):
        sha = gs.resolve_sha(ROOT, "HEAD")
        entries = {entry.path: entry for entry in gs.list_tree(ROOT, sha)}
        self.assertIn("mgfembp", entries)
        self.assertTrue(entries["mgfembp"].is_gitlink)
        self.assertEqual(entries["mgfembp"].object_id, "c87e74dcd6c8878b809e013cd8ff0c52baa75332")


class GitBatchBlobReaderTests(unittest.TestCase):
    def test_reads_exact_blob_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("exact content\n")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = {entry.path: entry for entry in gs.list_tree(root, sha)}
            with gs.GitBatchBlobReader(root) as reader:
                data = reader.read(entries["f.txt"].object_id)
            self.assertEqual(data, b"exact content\n")

    def test_multiple_reads_on_one_persistent_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "a.txt").write_text("aaa")
            (root / "b.txt").write_text("bbb")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = {entry.path: entry for entry in gs.list_tree(root, sha)}
            with gs.GitBatchBlobReader(root) as reader:
                self.assertEqual(reader.read(entries["a.txt"].object_id), b"aaa")
                self.assertEqual(reader.read(entries["b.txt"].object_id), b"bbb")
                self.assertEqual(reader.read(entries["a.txt"].object_id), b"aaa")

    def test_used_outside_context_manager_is_actionable(self):
        reader = gs.GitBatchBlobReader(ROOT)
        with self.assertRaises(gs.GitSourceError):
            reader.read("deadbeef")

    def test_read_blobs_convenience_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("hello\n")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = {entry.path: entry for entry in gs.list_tree(root, sha)}
            result = gs.read_blobs(root, [entries["f.txt"].object_id])
            self.assertEqual(result[entries["f.txt"].object_id], b"hello\n")

    def test_matches_committed_blob_content(self):
        sha = gs.resolve_sha(ROOT, "HEAD")
        entries = {entry.path: entry for entry in gs.list_tree(ROOT, sha)}
        target = "scripts/release_rehearsal/manifest.py"
        with gs.GitBatchBlobReader(ROOT) as reader:
            data = reader.read(entries[target].object_id)
        # NOTE: this is a *content* sanity check against a known-committed
        # blob, not a claim that this module reads the worktree -- it
        # reads the immutable blob keyed by object id; see
        # test_archive_rehearsal.py's mutation tests for the property
        # that actually matters (worktree edits cannot change this).
        self.assertIn(b"ManifestError", data)


class WriteIndexTreeTests(unittest.TestCase):
    def test_write_index_tree_reflects_staged_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("committed\n")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)

            (root / "g.txt").write_text("staged-not-committed\n")
            _git("add", "g.txt", cwd=root)
            index_sha = gs.write_index_tree(root)
            entries = {entry.path for entry in gs.list_tree(root, index_sha)}
            self.assertIn("g.txt", entries)
            # HEAD itself must NOT include the staged-but-uncommitted file.
            head_entries = {entry.path for entry in gs.list_tree(root, gs.resolve_sha(root, "HEAD"))}
            self.assertNotIn("g.txt", head_entries)


if __name__ == "__main__":
    unittest.main()
