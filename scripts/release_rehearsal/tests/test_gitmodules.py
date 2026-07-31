"""Tests for scripts/release_rehearsal/gitmodules.py (issue #9 mandatory
correction #4)."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import gitmodules as gm


def _git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


class ParseGitmodulesTests(unittest.TestCase):
    def test_single_section_parsed(self):
        content = '[submodule "mgfembp"]\n\tpath = mgfembp\n\turl = https://example.invalid/x.git\n'
        sections = gm.parse_gitmodules(content)
        self.assertEqual(sections, {"mgfembp": {"path": "mgfembp", "url": "https://example.invalid/x.git"}})

    def test_multiple_sections_parsed(self):
        content = (
            '[submodule "a"]\n\tpath = a\n\turl = https://example.invalid/a.git\n'
            '[submodule "b"]\n\tpath = b\n\turl = https://example.invalid/b.git\n'
        )
        sections = gm.parse_gitmodules(content)
        self.assertEqual(sorted(sections), ["a", "b"])

    def test_blank_lines_and_comments_ignored(self):
        content = (
            '# a comment\n\n[submodule "x"]\n\t; another comment\n\tpath = x\n\n\turl = https://example.invalid/x.git\n'
        )
        sections = gm.parse_gitmodules(content)
        self.assertEqual(sections["x"]["path"], "x")

    def test_empty_content_has_no_sections(self):
        self.assertEqual(gm.parse_gitmodules(""), {})

    def test_duplicate_section_is_actionable(self):
        content = '[submodule "x"]\n\tpath = x\n[submodule "x"]\n\tpath = x\n'
        with self.assertRaises(gm.GitmodulesError) as ctx:
            gm.parse_gitmodules(content)
        self.assertIn("duplicate section", str(ctx.exception))

    def test_duplicate_key_in_section_is_actionable(self):
        content = '[submodule "x"]\n\tpath = x\n\tpath = y\n'
        with self.assertRaises(gm.GitmodulesError) as ctx:
            gm.parse_gitmodules(content)
        self.assertIn("duplicate key", str(ctx.exception))

    def test_content_before_any_section_is_actionable(self):
        content = '\tpath = x\n[submodule "x"]\n\tpath = x\n'
        with self.assertRaises(gm.GitmodulesError) as ctx:
            gm.parse_gitmodules(content)
        self.assertIn("before any", str(ctx.exception))

    def test_unparseable_line_in_section_is_actionable(self):
        content = '[submodule "x"]\n\tthis is not a key value line\n'
        with self.assertRaises(gm.GitmodulesError) as ctx:
            gm.parse_gitmodules(content)
        self.assertIn("unparseable line", str(ctx.exception))

    def test_malformed_section_header_treated_as_content_line(self):
        """A line that merely resembles (but does not exactly match) a
        section header, appearing before any real section, is still
        actionably rejected -- never silently ignored."""
        content = '[submodule mgfembp]\n\tpath = mgfembp\n'
        with self.assertRaises(gm.GitmodulesError):
            gm.parse_gitmodules(content)


class LoadGitmodulesSectionsTests(unittest.TestCase):
    def _init_repo(self, root: Path) -> None:
        _git("init", "-q", cwd=root)
        _git("config", "user.email", "t@example.com", cwd=root)
        _git("config", "user.name", "Tester", cwd=root)

    def test_loads_from_a_real_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            (root / ".gitmodules").write_text(
                '[submodule "vendor"]\n\tpath = vendor\n\turl = https://example.invalid/vendor.git\n'
            )
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sections = gm.load_gitmodules_sections(root, "HEAD")
            self.assertEqual(sections["vendor"]["url"], "https://example.invalid/vendor.git")

    def test_missing_gitmodules_file_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            with self.assertRaises(gm.GitmodulesError) as ctx:
                gm.load_gitmodules_sections(root, "HEAD")
            self.assertIn("not a tracked regular file", str(ctx.exception))

    def test_malformed_gitmodules_content_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo(root)
            (root / ".gitmodules").write_text("not valid at all\n")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            with self.assertRaises(gm.GitmodulesError):
                gm.load_gitmodules_sections(root, "HEAD")

    def test_real_repo_gitmodules_parses_cleanly(self):
        sections = gm.load_gitmodules_sections(ROOT, "HEAD")
        self.assertEqual(sections["mgfembp"]["path"], "mgfembp")
        self.assertEqual(sections["mgfembp"]["url"], "https://github.com/StanHash/mgfembp.git")


if __name__ == "__main__":
    unittest.main()
