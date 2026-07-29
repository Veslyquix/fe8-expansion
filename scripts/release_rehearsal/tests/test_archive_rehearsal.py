"""Tests for scripts/release_rehearsal/archive_rehearsal.py (issue #9)."""

import glob
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import archive_rehearsal as ar
from scripts.release_rehearsal import source_guard as sg


def _make_source_tree(root: Path):
    (root / "src").mkdir()
    (root / "src" / "main.c").write_text("int main(void) { return 0; }\n")
    (root / "docs").mkdir()
    (root / "docs" / "readme.md").write_text("hello\n")


class BuildDeterministicArchiveTests(unittest.TestCase):
    def test_two_builds_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _make_source_tree(root)
            allowlist = {"src", "docs"}
            dest1 = Path(tmp) / "one.tar"
            dest2 = Path(tmp) / "two.tar"
            ar.build_deterministic_archive(root, allowlist, dest1)
            ar.build_deterministic_archive(root, allowlist, dest2)
            self.assertEqual(ar.hash_file(dest1), ar.hash_file(dest2))

    def test_canonical_member_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _make_source_tree(root)
            dest = Path(tmp) / "out.tar"
            ar.build_deterministic_archive(root, {"src", "docs"}, dest)
            with tarfile.open(dest, "r") as tar:
                for member in tar.getmembers():
                    self.assertEqual(member.mtime, 0)
                    self.assertEqual(member.uid, 0)
                    self.assertEqual(member.gid, 0)
                    self.assertEqual(member.uname, "")
                    self.assertEqual(member.gname, "")
                    self.assertTrue(member.isreg())

    def test_member_order_is_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "z").mkdir()
            (root / "z" / "z.c").write_text("int z;")
            (root / "a").mkdir()
            (root / "a" / "a.c").write_text("int a;")
            dest = Path(tmp) / "out.tar"
            ar.build_deterministic_archive(root, {"z", "a"}, dest)
            with tarfile.open(dest, "r") as tar:
                names = [m.name for m in tar.getmembers()]
            self.assertEqual(names, sorted(names))

    def test_refuses_when_content_violates_source_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "src").mkdir()
            (root / "src" / "bad.gba").write_bytes(b"\x00" * 16)
            dest = Path(tmp) / "out.tar"
            with self.assertRaises(ar.ArchiveRehearsalError):
                ar.build_deterministic_archive(root, {"src"}, dest)


class RehearseArchiveTwiceTests(unittest.TestCase):
    def test_match_true_for_clean_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _make_source_tree(root)
            report = ar.rehearse_archive_twice(root, {"src", "docs"})
            self.assertTrue(report["match"])
            self.assertEqual(report["hash1"], report["hash2"])

    def test_no_temporary_files_retained_after_rehearsal(self):
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "fe8-release-rehearsal-*")))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _make_source_tree(root)
            ar.rehearse_archive_twice(root, {"src", "docs"})
        after = set(glob.glob(os.path.join(tempfile.gettempdir(), "fe8-release-rehearsal-*")))
        self.assertEqual(before, after)

    def test_cleanup_happens_even_on_failure(self):
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "fe8-release-rehearsal-*")))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "src").mkdir()
            (root / "src" / "bad.gba").write_bytes(b"\x00" * 16)
            with self.assertRaises(ar.ArchiveRehearsalError):
                ar.rehearse_archive_twice(root, {"src"})
        after = set(glob.glob(os.path.join(tempfile.gettempdir(), "fe8-release-rehearsal-*")))
        self.assertEqual(before, after)

    def test_different_content_produces_different_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root_a = Path(tmp) / "a"
            root_a.mkdir()
            _make_source_tree(root_a)
            root_b = Path(tmp) / "b"
            root_b.mkdir()
            _make_source_tree(root_b)
            (root_b / "src" / "extra.c").write_text("int extra;")
            report_a = ar.rehearse_archive_twice(root_a, {"src", "docs"})
            report_b = ar.rehearse_archive_twice(root_b, {"src", "docs"})
            self.assertNotEqual(report_a["hash1"], report_b["hash1"])


class RebuildRehearsalBlockerTests(unittest.TestCase):
    def test_documents_github_autoarchive_contradiction(self):
        report = ar.rebuild_rehearsal_blocker(ROOT)
        self.assertIn("submodule", report["github_autoarchive_submodule_contradiction"])
        self.assertIn("mgfembp", report["github_autoarchive_submodule_contradiction"])

    def test_real_repo_reports_blocked_with_precise_reason(self):
        report = ar.rebuild_rehearsal_blocker(ROOT)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any("mgfembp" in reason for reason in report["reasons"]))
        self.assertIn("mgfembp", report["submodule_status_output"])


class RepositoryStateTests(unittest.TestCase):
    """The real repository's own source tree must rehearse deterministically."""

    def test_real_tree_rehearses_deterministically(self):
        allowlist = sg.load_allowlist(ROOT / "docs" / "release_data" / "source_allowlist.json")
        report = ar.rehearse_archive_twice(ROOT, allowlist)
        self.assertTrue(report["match"])


if __name__ == "__main__":
    unittest.main()
