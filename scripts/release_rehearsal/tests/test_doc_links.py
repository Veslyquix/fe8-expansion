"""Tests for scripts/release_rehearsal/doc_links.py (issue #9)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import doc_links as dl


class FindBrokenLinksTests(unittest.TestCase):
    def test_broken_relative_link_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "a.md").write_text(
                "See [here](release/does_not_exist.json) for details.\n", encoding="utf-8"
            )
            broken = dl.find_broken_links(root, ["docs/a.md"])
            self.assertEqual(broken, [("docs/a.md", "release/does_not_exist.json")])

    def test_valid_relative_link_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs" / "release_data").mkdir(parents=True)
            (root / "docs" / "release_data" / "version_ledger.json").write_text("{}", encoding="utf-8")
            (root / "docs" / "a.md").write_text(
                "See [here](release_data/version_ledger.json) for details.\n", encoding="utf-8"
            )
            self.assertEqual(dl.find_broken_links(root, ["docs/a.md"]), [])

    def test_http_links_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "a.md").write_text(
                "See [here](https://example.invalid/does/not/exist) for details.\n", encoding="utf-8"
            )
            self.assertEqual(dl.find_broken_links(root, ["docs/a.md"]), [])

    def test_fragment_only_links_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "a.md").write_text("See [here](#some-heading) for details.\n", encoding="utf-8")
            self.assertEqual(dl.find_broken_links(root, ["docs/a.md"]), [])

    def test_link_with_trailing_fragment_resolved_against_path_part_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "b.md").write_text("x", encoding="utf-8")
            (root / "docs" / "a.md").write_text("See [here](b.md#section) for details.\n", encoding="utf-8")
            self.assertEqual(dl.find_broken_links(root, ["docs/a.md"]), [])

    def test_missing_doc_itself_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            broken = dl.find_broken_links(root, ["docs/does_not_exist.md"])
            self.assertEqual(broken, [("docs/does_not_exist.md", "<doc-missing>")])


class RepositoryStateTests(unittest.TestCase):
    """Regression guard for the three specific broken links the
    independent verifier found (docs/release_process.md,
    docs/public_api_policy.md, docs/migration_registry.md each linked a
    nonexistent "release/..." path instead of the real
    "release_data/..." path) -- these, and any future regression in the
    same doc set, must never reappear."""

    def test_no_broken_links_in_release_docs(self):
        broken = dl.find_broken_links(ROOT)
        self.assertEqual(broken, [], f"broken release-doc link(s): {broken}")

    def test_default_doc_set_all_exist(self):
        for relpath in dl.DEFAULT_DOCS:
            with self.subTest(doc=relpath):
                self.assertTrue((ROOT / relpath).is_file(), f"{relpath} missing")


if __name__ == "__main__":
    unittest.main()
