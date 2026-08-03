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


class ObjectKindTests(unittest.TestCase):
    def test_commit_object_reports_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            self.assertEqual(gs.object_kind(root, sha), "commit")

    def test_tree_object_reports_tree_not_commit(self):
        """The exact final-review-found defect this whole check family
        exists to catch: `git write-tree`'s own output SHA names a real
        object, but that object's kind is 'tree', never 'commit'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            tree_sha = gs.write_index_tree(root)
            self.assertEqual(gs.object_kind(root, tree_sha), "tree")

    def test_nonexistent_object_reports_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            self.assertIsNone(gs.object_kind(root, "a" * 40))


class IsAncestorCommitTests(unittest.TestCase):
    def test_head_is_its_own_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            self.assertTrue(gs.is_ancestor_commit(root, sha, "HEAD"))

    def test_earlier_commit_is_ancestor_of_later_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "first", cwd=root)
            first_sha = gs.resolve_sha(root, "HEAD")
            (root / "f.txt").write_text("y")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "second", cwd=root)
            self.assertTrue(gs.is_ancestor_commit(root, first_sha, "HEAD"))

    def test_unrelated_commit_is_not_ancestor(self):
        """A commit that genuinely exists but sits on a history this
        branch's own HEAD never descends from (an orphan branch here)
        must never be reported as an ancestor."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "main-first", cwd=root)
            _git("checkout", "-q", "--orphan", "other", cwd=root)
            (root / "g.txt").write_text("y")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "orphan-first", cwd=root)
            orphan_sha = gs.resolve_sha(root, "HEAD")
            _git("checkout", "-q", "master", cwd=root)
            self.assertFalse(gs.is_ancestor_commit(root, orphan_sha, "HEAD"))


class CheckGenerationBasisIsCommitTests(unittest.TestCase):
    """Final-review-found critical finding #2: `source_allowlist.json`
    claimed 'generation_basis_sha' is a commit, but the checked-in value
    was actually an unreachable/dangling tree object produced by index
    materialization -- a false, ephemeral documentary claim. This is the
    single, shared, mechanical truthfulness check for that field, used
    by both `allowlist.py` and `tree_coverage.py`."""

    def _write_doc(self, path: Path, basis) -> None:
        import json

        doc = {"generation_basis_sha": basis} if basis is not None else {}
        path.write_text(json.dumps(doc), encoding="utf-8")

    def test_reproduces_the_dangling_tree_false_commit_case(self):
        """The exact reported defect, reproduced end to end: generate an
        'index'-derived tree SHA (a real object, but never reachable
        from any ref, exactly like the checked-in bug this fix closes),
        write it into a document's 'generation_basis_sha' field, and
        confirm the shared check rejects it -- both for being the wrong
        object kind, and for being unreachable."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            (root / "g.txt").write_text("y")
            _git("add", "g.txt", cwd=root)
            tree_sha = gs.write_index_tree(root)
            # never actually committed -- 'tree_sha' stays a genuinely
            # dangling, unreachable-from-any-ref object, exactly like
            # the real bug this closes.
            doc_path = root / "allow.json"
            self._write_doc(doc_path, tree_sha)
            errors = gs.check_generation_basis_is_commit(root, doc_path)
            self.assertEqual(len(errors), 1)
            self.assertIn(tree_sha, errors[0])
            self.assertIn("not a commit", errors[0])

    def test_real_reachable_commit_basis_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            doc_path = root / "allow.json"
            self._write_doc(doc_path, sha)
            self.assertEqual(gs.check_generation_basis_is_commit(root, doc_path), [])

    def test_unreachable_but_real_commit_basis_rejected(self):
        """A basis SHA that names a genuine *commit* object (not a
        tree) is still rejected if that commit is not reachable from
        HEAD at all -- e.g. it sits on an orphan branch/history this
        branch's own HEAD never descends from -- an equally ephemeral/
        unverifiable claim, just with the "wrong kind of object" defect
        replaced by an "unreachable" one."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "main-first", cwd=root)
            _git("checkout", "-q", "--orphan", "other", cwd=root)
            (root / "g.txt").write_text("y")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "orphan-first", cwd=root)
            orphan_sha = gs.resolve_sha(root, "HEAD")
            _git("checkout", "-q", "master", cwd=root)
            doc_path = root / "allow.json"
            self._write_doc(doc_path, orphan_sha)
            errors = gs.check_generation_basis_is_commit(root, doc_path)
            self.assertEqual(len(errors), 1)
            self.assertIn("not HEAD nor any ancestor", errors[0])

    def test_missing_object_entirely_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            doc_path = root / "allow.json"
            self._write_doc(doc_path, "a" * 40)
            errors = gs.check_generation_basis_is_commit(root, doc_path)
            self.assertEqual(len(errors), 1)
            self.assertIn("does not name any object", errors[0])

    def test_malformed_basis_value_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            doc_path = root / "allow.json"
            self._write_doc(doc_path, "not-a-sha")
            errors = gs.check_generation_basis_is_commit(root, doc_path)
            self.assertEqual(len(errors), 1)
            self.assertIn("must be a 40-lowercase-hex object id", errors[0])

    def test_absent_field_is_not_a_defect(self):
        """A document that makes no 'generation_basis_sha' claim at all
        has nothing this check can validate or contradict."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            doc_path = root / "allow.json"
            self._write_doc(doc_path, None)
            self.assertEqual(gs.check_generation_basis_is_commit(root, doc_path), [])

    def test_non_git_repo_root_returns_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc_path = root / "allow.json"
            self._write_doc(doc_path, "9c4f7d7bf54ad783690701d6ef78e1479875e1c6")
            self.assertEqual(gs.check_generation_basis_is_commit(root, doc_path), [])


if __name__ == "__main__":
    unittest.main()
