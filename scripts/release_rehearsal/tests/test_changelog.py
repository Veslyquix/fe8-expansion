"""Tests for scripts/release_rehearsal/changelog.py (issue #9)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import changelog as cl


def _write(dir_path: Path, name: str, data: dict) -> Path:
    path = dir_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class LoadFragmentTests(unittest.TestCase):
    def test_valid_fragment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "a.json", {
                "issue": 9, "category": "added", "summary": "thing", "semver_impact": "minor",
            })
            fragment = cl.load_fragment(path)
            self.assertEqual(fragment["category"], "added")
            self.assertEqual(fragment["issue"], 9)

    def test_missing_field_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "a.json", {"category": "added", "summary": "x"})
            with self.assertRaises(cl.ChangelogError) as ctx:
                cl.load_fragment(path)
            self.assertIn("semver_impact", str(ctx.exception))

    def test_bad_category_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "a.json", {
                "category": "nonsense", "summary": "x", "semver_impact": "none",
            })
            with self.assertRaises(cl.ChangelogError):
                cl.load_fragment(path)

    def test_bad_impact_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "a.json", {
                "category": "added", "summary": "x", "semver_impact": "epic",
            })
            with self.assertRaises(cl.ChangelogError):
                cl.load_fragment(path)

    def test_empty_summary_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "a.json", {
                "category": "added", "summary": "   ", "semver_impact": "none",
            })
            with self.assertRaises(cl.ChangelogError):
                cl.load_fragment(path)

    def test_non_json_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            path.write_text("not json{{{", encoding="utf-8")
            with self.assertRaises(cl.ChangelogError):
                cl.load_fragment(path)

    def test_issue_must_be_int_or_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "a.json", {
                "issue": "nine", "category": "added", "summary": "x", "semver_impact": "none",
            })
            with self.assertRaises(cl.ChangelogError):
                cl.load_fragment(path)


class AggregateAndRenderTests(unittest.TestCase):
    def test_aggregate_impact_picks_highest(self):
        fragments = [
            {"category": "fixed", "summary": "a", "semver_impact": "patch", "issue": 1},
            {"category": "added", "summary": "b", "semver_impact": "major", "issue": 2},
            {"category": "changed", "summary": "c", "semver_impact": "minor", "issue": 3},
        ]
        self.assertEqual(cl.aggregate_impact(fragments), "major")

    def test_aggregate_impact_empty_is_none(self):
        self.assertEqual(cl.aggregate_impact([]), "none")

    def test_render_is_deterministic_across_calls(self):
        fragments = [
            {"category": "fixed", "summary": "z fix", "semver_impact": "patch", "issue": 5},
            {"category": "fixed", "summary": "a fix", "semver_impact": "patch", "issue": 1},
            {"category": "added", "summary": "a feature", "semver_impact": "minor", "issue": None},
        ]
        first = cl.render_unreleased(fragments)
        second = cl.render_unreleased(list(reversed(fragments)))
        self.assertEqual(first, second)

    def test_render_empty_fragments(self):
        rendered = cl.render_unreleased([])
        self.assertIn("No unreleased changes.", rendered)

    def test_render_category_ordering(self):
        fragments = [
            {"category": "fixed", "summary": "a fix", "semver_impact": "patch", "issue": 1},
            {"category": "added", "summary": "a feature", "semver_impact": "minor", "issue": 2},
        ]
        rendered = cl.render_unreleased(fragments)
        self.assertLess(rendered.index("### Added"), rendered.index("### Fixed"))


class LoadFragmentsTests(unittest.TestCase):
    def test_sorted_by_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write(tmp_path, "b.json", {"category": "added", "summary": "b", "semver_impact": "none"})
            _write(tmp_path, "a.json", {"category": "added", "summary": "a", "semver_impact": "none"})
            fragments = cl.load_fragments(tmp_path)
            self.assertEqual([f["summary"] for f in fragments], ["a", "b"])

    def test_missing_dir_is_actionable(self):
        with self.assertRaises(cl.ChangelogError):
            cl.load_fragments(Path("/nonexistent/changelog_fragments"))

    def test_non_json_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "README.md").write_text("not a fragment", encoding="utf-8")
            _write(tmp_path, "a.json", {"category": "added", "summary": "a", "semver_impact": "none"})
            fragments = cl.load_fragments(tmp_path)
            self.assertEqual(len(fragments), 1)


class CheckTests(unittest.TestCase):
    def _setup(self, tmp_path: Path, fragments):
        fragment_dir = tmp_path / "changelog_fragments"
        fragment_dir.mkdir()
        for index, fragment in enumerate(fragments):
            _write(fragment_dir, f"{index}.json", fragment)
        return fragment_dir

    def test_fresh_changelog_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragments = [{"category": "added", "summary": "thing", "semver_impact": "none", "issue": 1}]
            fragment_dir = self._setup(tmp_path, fragments)
            rendered = cl.render_unreleased(cl.load_fragments(fragment_dir))
            changelog_path = tmp_path / "CHANGELOG.md"
            changelog_path.write_text(
                f"# Changelog\n\n## [Unreleased]\n\n{cl.UNRELEASED_BEGIN}\n{rendered}{cl.UNRELEASED_END}\n",
                encoding="utf-8",
            )
            ok, errors, _, impact = cl.check(fragment_dir, changelog_path)
            self.assertTrue(ok, errors)
            self.assertEqual(impact, "none")

    def test_stale_changelog_fails_actionably(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragments = [{"category": "added", "summary": "thing", "semver_impact": "none", "issue": 1}]
            fragment_dir = self._setup(tmp_path, fragments)
            changelog_path = tmp_path / "CHANGELOG.md"
            changelog_path.write_text(
                f"# Changelog\n\n{cl.UNRELEASED_BEGIN}\nstale text\n{cl.UNRELEASED_END}\n",
                encoding="utf-8",
            )
            ok, errors, _, _ = cl.check(fragment_dir, changelog_path)
            self.assertFalse(ok)
            self.assertTrue(any("stale" in error for error in errors))

    def test_missing_markers_fails_actionably(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragment_dir = self._setup(tmp_path, [])
            changelog_path = tmp_path / "CHANGELOG.md"
            changelog_path.write_text("# Changelog\n\nno markers here\n", encoding="utf-8")
            ok, errors, _, _ = cl.check(fragment_dir, changelog_path)
            self.assertFalse(ok)
            self.assertTrue(any("marker" in error for error in errors))

    def test_missing_changelog_file_fails_actionably(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragment_dir = self._setup(tmp_path, [])
            ok, errors, _, _ = cl.check(fragment_dir, tmp_path / "NOPE.md")
            self.assertFalse(ok)
            self.assertTrue(any("not found" in error for error in errors))

    def test_invalid_fragment_schema_fails_actionably(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragment_dir = tmp_path / "changelog_fragments"
            fragment_dir.mkdir()
            _write(fragment_dir, "bad.json", {"category": "not-a-category", "summary": "x", "semver_impact": "none"})
            ok, errors, _, _ = cl.check(fragment_dir, tmp_path / "CHANGELOG.md")
            self.assertFalse(ok)
            self.assertTrue(any("category" in error for error in errors))


class RepositoryStateTests(unittest.TestCase):
    """Sanity check against the real, committed changelog_fragments/ + CHANGELOG.md."""

    def test_real_changelog_is_fresh(self):
        ok, errors, _, _ = cl.check(ROOT / "changelog_fragments", ROOT / "CHANGELOG.md")
        self.assertTrue(ok, errors)


if __name__ == "__main__":
    unittest.main()
