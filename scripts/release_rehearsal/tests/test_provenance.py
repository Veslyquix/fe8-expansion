"""Tests for scripts/release_rehearsal/provenance.py (issue #9)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import provenance as prov


def _base_entry(**overrides):
    entry = {
        "path": "src",
        "category": "code",
        "author": "NOASSERTION",
        "rightsholder": "NOASSERTION",
        "license": "NOASSERTION",
        "redistribution_approved": False,
        "reviewer": None,
        "notes": "seed",
    }
    entry.update(overrides)
    return entry


def _write_manifest(dir_path: Path, name: str, entries) -> Path:
    path = dir_path / name
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


class LoadManifestTests(unittest.TestCase):
    def test_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_manifest(Path(tmp), "code.json", [_base_entry()])
            entries = prov.load_manifest(path)
            self.assertEqual(len(entries), 1)

    def test_missing_key_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = {"path": "src", "category": "code"}
            path = _write_manifest(Path(tmp), "code.json", [bad])
            with self.assertRaises(prov.ProvenanceError) as ctx:
                prov.load_manifest(path)
            self.assertIn("missing required key", str(ctx.exception))

    def test_bad_category_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_manifest(Path(tmp), "code.json", [_base_entry(category="nonsense")])
            with self.assertRaises(prov.ProvenanceError):
                prov.load_manifest(path)

    def test_redistribution_approved_must_be_real_bool(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_manifest(Path(tmp), "code.json", [_base_entry(redistribution_approved="true")])
            with self.assertRaises(prov.ProvenanceError):
                prov.load_manifest(path)

    def test_submodule_requires_pinned_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_manifest(Path(tmp), "submodules.json", [_base_entry(
                path="mgfembp", category="submodule", pinned_commit=None,
            )])
            with self.assertRaises(prov.ProvenanceError) as ctx:
                prov.load_manifest(path)
            self.assertIn("pinned_commit", str(ctx.exception))

    def test_submodule_with_pinned_commit_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_manifest(Path(tmp), "submodules.json", [_base_entry(
                path="mgfembp", category="submodule",
                pinned_commit="c87e74dcd6c8878b809e013cd8ff0c52baa75332",
            )])
            entries = prov.load_manifest(path)
            self.assertEqual(entries[0]["pinned_commit"], "c87e74dcd6c8878b809e013cd8ff0c52baa75332")

    def test_not_a_list_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "code.json"
            path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
            with self.assertRaises(prov.ProvenanceError):
                prov.load_manifest(path)

    def test_non_json_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "code.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(prov.ProvenanceError):
                prov.load_manifest(path)


class EvaluateTests(unittest.TestCase):
    def test_noassertion_blocks(self):
        status, reasons = prov.evaluate([_base_entry(license="NOASSERTION")])
        self.assertEqual(status, "blocked")
        self.assertTrue(any("license" in reason for reason in reasons))

    def test_unapproved_redistribution_blocks(self):
        status, reasons = prov.evaluate([_base_entry(
            author="Jane Doe", rightsholder="Jane Doe", license="MIT",
            redistribution_approved=False, reviewer="Jane Reviewer",
        )])
        self.assertEqual(status, "blocked")
        self.assertTrue(any("redistribution_approved is false" in reason for reason in reasons))

    def test_missing_reviewer_blocks(self):
        status, reasons = prov.evaluate([_base_entry(
            author="Jane Doe", rightsholder="Jane Doe", license="MIT",
            redistribution_approved=True, reviewer=None,
        )])
        self.assertEqual(status, "blocked")
        self.assertTrue(any("no named reviewer" in reason for reason in reasons))

    def test_fully_resolved_entry_is_approved(self):
        status, reasons = prov.evaluate([_base_entry(
            author="Jane Doe", rightsholder="Jane Doe", license="MIT",
            redistribution_approved=True, reviewer="Jane Reviewer",
        )])
        self.assertEqual(status, "approved")
        self.assertEqual(reasons, [])

    def test_empty_entries_blocks(self):
        status, reasons = prov.evaluate([])
        self.assertEqual(status, "blocked")
        self.assertTrue(reasons)

    def test_reasons_are_sorted_deterministic(self):
        entries = [_base_entry(path="b"), _base_entry(path="a")]
        _, reasons1 = prov.evaluate(entries)
        _, reasons2 = prov.evaluate(list(reversed(entries)))
        self.assertEqual(reasons1, reasons2)


class CoverageGapsTests(unittest.TestCase):
    def test_reports_missing_paths(self):
        entries = [_base_entry(path="src")]
        gaps = prov.coverage_gaps(entries, ["src", "docs", "graphics"])
        self.assertEqual(gaps, ["docs", "graphics"])

    def test_no_gaps_when_fully_covered(self):
        entries = [_base_entry(path="src"), _base_entry(path="docs")]
        gaps = prov.coverage_gaps(entries, ["src", "docs"])
        self.assertEqual(gaps, [])


class RepositoryStateTests(unittest.TestCase):
    """The current, real, committed provenance manifests must evaluate to
    an honest, exact BLOCKED status -- never a false 'approved'."""

    def test_real_manifests_are_blocked(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        status, reasons = prov.evaluate(entries)
        self.assertEqual(status, "blocked")
        self.assertTrue(reasons)

    def test_mgfembp_pinned_and_unapproved(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        mgfembp = [entry for entry in entries if entry["path"] == "mgfembp"]
        self.assertEqual(len(mgfembp), 1)
        self.assertEqual(mgfembp[0]["pinned_commit"], "c87e74dcd6c8878b809e013cd8ff0c52baa75332")
        self.assertFalse(mgfembp[0]["redistribution_approved"])

    def test_full_allowlist_coverage(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        allowlist = json.loads(
            (ROOT / "docs" / "release_data" / "source_allowlist.json").read_text(encoding="utf-8")
        )["paths"]
        gaps = prov.coverage_gaps(entries, allowlist)
        self.assertEqual(gaps, [])

    def test_no_entry_invents_a_license_or_approval(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        for entry in entries:
            if entry["path"] == "mgfembp":
                continue
            self.assertEqual(entry["license"], "NOASSERTION")
            self.assertEqual(entry["author"], "NOASSERTION")
            self.assertFalse(entry["redistribution_approved"])
            self.assertIsNone(entry["reviewer"])


if __name__ == "__main__":
    unittest.main()
