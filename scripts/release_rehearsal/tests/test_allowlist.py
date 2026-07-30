"""Tests for scripts/release_rehearsal/allowlist.py (issue #9)."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import allowlist as al
from scripts.release_rehearsal import git_source as gs


def _git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _init_repo(root: Path) -> None:
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "Tester", cwd=root)


class GenerateEntriesTests(unittest.TestCase):
    def test_generates_every_tracked_file_and_gitlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int x;")
            (root / "docs").mkdir()
            (root / "docs" / "readme.md").write_text("hi")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = al.generate_entries(root, sha)
            self.assertEqual(entries, ["docs/readme.md", "src/main.c"])

    def test_generated_document_has_required_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "f.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            document = al.generate_allowlist_document(root, sha)
            self.assertEqual(document["schema_version"], al.SCHEMA_VERSION)
            self.assertEqual(document["generated_from_sha"], sha)
            self.assertEqual(document["paths"], ["f.txt"])


class CheckAllowlistCompletenessTests(unittest.TestCase):
    def test_missing_and_stale_entries_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "a.txt").write_text("a")
            (root / "b.txt").write_text("b")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")

            # allowlist has "a.txt" (still tracked, fine), "c.txt" (stale --
            # no longer/never tracked), and is missing "b.txt" (a real gap).
            missing, stale = al.check_allowlist_completeness(root, ["a.txt", "c.txt"], sha)
            self.assertEqual(missing, ["b.txt"])
            self.assertEqual(stale, ["c.txt"])

    def test_exact_match_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            missing, stale = al.check_allowlist_completeness(root, ["a.txt"], sha)
            self.assertEqual(missing, [])
            self.assertEqual(stale, [])

    def test_new_unlisted_tracked_file_is_reported_missing(self):
        """The literal issue #9 requirement: a new tracked file with no
        allowlist entry must fail (be reported), never be silently
        invisible."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")

            (root / "new_unreviewed.txt").write_text("new")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "add new file", cwd=root)
            new_sha = gs.resolve_sha(root, "HEAD")

            missing, stale = al.check_allowlist_completeness(root, ["a.txt"], new_sha)
            self.assertEqual(missing, ["new_unreviewed.txt"])


class CheckFunctionTests(unittest.TestCase):
    def test_check_reports_human_readable_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "a.txt").write_text("a")
            (root / "b.txt").write_text("b")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)

            allowlist_path = root / "allow.json"
            allowlist_path.write_text(json.dumps({"paths": ["a.txt"]}), encoding="utf-8")
            errors = al.check(root, allowlist_path, "HEAD")
            self.assertEqual(len(errors), 1)
            self.assertIn("b.txt", errors[0])

    def test_check_clean_allowlist_has_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)

            allowlist_path = root / "allow.json"
            allowlist_path.write_text(json.dumps({"paths": ["a.txt"]}), encoding="utf-8")
            self.assertEqual(al.check(root, allowlist_path, "HEAD"), [])

    def test_malformed_allowlist_json_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)

            allowlist_path = root / "allow.json"
            allowlist_path.write_text("{not json", encoding="utf-8")
            errors = al.check(root, allowlist_path, "HEAD")
            self.assertEqual(len(errors), 1)

    def test_duplicate_allowlist_entries_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.json"
            path.write_text(json.dumps({"paths": ["a.txt", "a.txt"]}), encoding="utf-8")
            with self.assertRaises(al.AllowlistError):
                al.load_allowlist_paths(path)


class CheckAllowlistCompletenessNonGitTests(unittest.TestCase):
    """issue #9 verifier remediation: the non-git analogue of
    `check_allowlist_completeness`, used only when `repo_root` has no
    `.git` at all (a genuine extracted archive/non-git candidate tree).
    Regression coverage for the fresh-verifier-reproduced defect: this
    must never invoke git plumbing, and must correctly report both a
    present-but-unlisted file ("missing") and an allowlisted member with
    no on-disk representation at all ("unrepresented"), including a
    gitlink-style directory-only entry like "mgfembp"."""

    def test_exact_match_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["a.txt"])
            self.assertEqual(missing, [])
            self.assertEqual(unrepresented, [])

    def test_present_unlisted_file_is_reported_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            (root / "b.txt").write_text("b")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["a.txt"])
            self.assertEqual(missing, ["b.txt"])
            self.assertEqual(unrepresented, [])

    def test_absent_allowlisted_file_is_reported_unrepresented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["a.txt", "gone.txt"])
            self.assertEqual(missing, [])
            self.assertEqual(unrepresented, ["gone.txt"])

    def test_gitlink_style_directory_entry_is_represented_not_unrepresented(self):
        """A real extracted GitHub source archive materializes a
        submodule mountpoint (e.g. "mgfembp") as an empty directory, not
        as a missing path -- this must count as represented, exactly
        like a real git tree's gitlink entry never requires blob
        content."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mgfembp").mkdir()
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["mgfembp"])
            self.assertEqual(unrepresented, [])

    def test_truly_absent_gitlink_directory_is_unrepresented(self):
        """The precise "missing/unrepresented gitlink/mgfembp" blocker
        issue #9 requires: if the extraction omits even the empty
        directory mountpoint, that must be reported, not silently
        ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["a.txt", "mgfembp"])
            self.assertEqual(unrepresented, ["mgfembp"])

    def test_symlink_at_allowlisted_path_never_counts_as_represented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.txt").write_text("real")
            (root / "linked.txt").symlink_to("real.txt")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["linked.txt"])
            self.assertEqual(unrepresented, ["linked.txt"])

    def test_never_invokes_git_even_when_nested_inside_a_real_repo(self):
        """issue #9 verifier remediation: a non-git candidate tree's
        completeness check must never invoke git plumbing against it --
        not even accidentally via git's own upward-directory-discovery
        finding an unrelated *enclosing* git repository. Proven by
        nesting the synthetic fixture directly inside this real,
        git-tracked worktree (ROOT): if any git command leaked through
        with this directory as its cwd, it would silently report ROOT's
        own real tracked-file set (thousands of paths) instead of the
        tiny fixture's, and these assertions would fail."""
        nested = ROOT / "scripts" / "release_rehearsal" / "tests" / ".issue9-non-git-fixture-tmp"
        self.addCleanup(shutil.rmtree, nested, True)
        nested.mkdir(exist_ok=True)
        (nested / "only.txt").write_text("x")
        missing, unrepresented = al.check_allowlist_completeness_non_git(nested, ["only.txt"])
        self.assertEqual(missing, [])
        self.assertEqual(unrepresented, [])


class CheckFunctionNonGitTests(unittest.TestCase):
    """issue #9 verifier remediation: `check()` must dispatch to the
    non-git completeness check (never `git_source.list_tree`/any git
    invocation) when `repo_root` has no `.git` at all -- the literal,
    reproduced defect: `check()` previously called `gs.list_tree`
    unconditionally and tracebacked for both a non-git `repo_root` and a
    well-formed-but-nonexistent `target_sha` in a real git repo."""

    @staticmethod
    def _write_allowlist(path: Path, paths) -> None:
        path.write_text(json.dumps({"paths": list(paths)}), encoding="utf-8")

    def test_clean_non_git_tree_has_no_errors(self):
        """The allowlist document lives *outside* the scanned tree here
        (as e.g. a CI-fetched sidecar file would) purely to isolate this
        assertion from the self-referential-entry behavior covered by
        `test_allowlist_document_itself_inside_the_tree_must_self_list`
        below -- the real, checked-in
        docs/release_data/source_allowlist.json *is* inside the tree it
        describes, and lists its own path for exactly that reason."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "a.txt").write_text("a")
            allowlist_path = Path(tmp) / "allow.json"
            self._write_allowlist(allowlist_path, ["a.txt"])
            self.assertEqual(al.check(root, allowlist_path), [])

    def test_non_git_tree_reports_missing_and_unrepresented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "a.txt").write_text("a")
            (root / "extra.txt").write_text("extra")
            allowlist_path = Path(tmp) / "allow.json"
            self._write_allowlist(allowlist_path, ["a.txt", "gone.txt"])
            errors = al.check(root, allowlist_path)
            self.assertTrue(any("extra.txt" in e for e in errors))
            self.assertTrue(any("gone.txt" in e for e in errors))

    def test_allowlist_document_itself_inside_the_tree_must_self_list(self):
        """Mirrors this repository's own real
        docs/release_data/source_allowlist.json, which lives *inside*
        the tree it describes and lists its own path -- an allowlist
        document that forgets to self-list is exactly as much an
        actionable "missing from allowlist" finding as any other
        unlisted file, never a silently-tolerated special case."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            allowlist_path = root / "allow.json"
            self._write_allowlist(allowlist_path, ["a.txt", "allow.json"])
            self.assertEqual(al.check(root, allowlist_path), [])

    def test_nonexistent_valid_form_sha_in_real_git_repo_raises_git_source_error(self):
        """issue #9 verifier remediation: a well-formed (40-lowercase-
        hex) but nonexistent target_sha in an *actual* git repository
        must raise `git_source.GitSourceError` (propagated, never
        swallowed) -- the CLI's single top-level exception boundary is
        what turns this into a controlled exit 2; `check()` itself must
        not paper over it as a soft business reason."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            allowlist_path = root / "allow.json"
            self._write_allowlist(allowlist_path, ["a.txt"])
            nonexistent_sha = "0123456789abcdef0123456789abcdef01234567"
            with self.assertRaises(gs.GitSourceError):
                al.check(root, allowlist_path, nonexistent_sha)


class RepositoryStateTests(unittest.TestCase):
    """The real, checked-in docs/release_data/source_allowlist.json must
    be exactly consistent with this repository's own tracked-file set."""

    def test_real_allowlist_is_exact_and_complete_at_head(self):
        allowlist_path = ROOT / "docs" / "release_data" / "source_allowlist.json"
        paths = al.load_allowlist_paths(allowlist_path)
        missing, stale = al.check_allowlist_completeness(ROOT, paths, "HEAD")
        self.assertEqual(missing, [], "tracked file(s) missing an allowlist entry")
        self.assertEqual(stale, [], "stale allowlist entrie(s) for something no longer tracked")

    def test_real_allowlist_includes_mgfembp_gitlink(self):
        allowlist_path = ROOT / "docs" / "release_data" / "source_allowlist.json"
        paths = al.load_allowlist_paths(allowlist_path)
        self.assertIn("mgfembp", paths)


if __name__ == "__main__":
    unittest.main()
