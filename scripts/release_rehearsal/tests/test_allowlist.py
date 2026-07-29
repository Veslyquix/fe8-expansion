"""Tests for scripts/release_rehearsal/allowlist.py (issue #9)."""

import json
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
