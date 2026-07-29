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

    def test_fully_resolved_entry_is_mechanically_eligible(self):
        status, reasons = prov.evaluate([_base_entry(
            author="Jane Doe", rightsholder="Jane Doe", license="MIT",
            redistribution_approved=True, reviewer="Jane Reviewer",
        )])
        self.assertEqual(status, "mechanically eligible")
        self.assertNotEqual(status, "approved")
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

    def test_directory_prefix_covers_many_exact_files(self):
        """issue #9 verifier remediation: a single category-level entry
        (e.g. "src") must cover every exact per-file allowlist path
        nested under it -- the "equally strong" exact-or-directory-prefix
        binding this module implements instead of one near-duplicate
        record per file."""
        entries = [_base_entry(path="src")]
        gaps = prov.coverage_gaps(entries, ["src/main.c", "src/lib/helper.c", "src"])
        self.assertEqual(gaps, [])

    def test_sibling_prefix_does_not_falsely_cover(self):
        """"src" must not cover "scripts/x.py" merely because both start
        with the same few letters -- coverage is a real path-segment
        prefix (`src/`), never a bare string prefix."""
        entries = [_base_entry(path="src")]
        gaps = prov.coverage_gaps(entries, ["scripts/x.py"])
        self.assertEqual(gaps, ["scripts/x.py"])


class FindGhostEntriesTests(unittest.TestCase):
    def test_entry_covering_nothing_is_a_ghost(self):
        entries = [_base_entry(path="src"), _base_entry(path="long-deleted-dir")]
        ghosts = prov.find_ghost_entries(entries, ["src/main.c"])
        self.assertEqual(ghosts, ["long-deleted-dir"])

    def test_entry_covering_something_is_not_a_ghost(self):
        entries = [_base_entry(path="src")]
        self.assertEqual(prov.find_ghost_entries(entries, ["src/main.c"]), [])


class FindDuplicateEntryPathsTests(unittest.TestCase):
    def test_exact_duplicate_path_detected(self):
        entries = [_base_entry(path="src"), _base_entry(path="src")]
        self.assertEqual(prov.find_duplicate_entry_paths(entries), ["src"])

    def test_unique_paths_have_no_duplicates(self):
        entries = [_base_entry(path="src"), _base_entry(path="docs")]
        self.assertEqual(prov.find_duplicate_entry_paths(entries), [])


class FindAmbiguousEntriesTests(unittest.TestCase):
    def test_ancestor_descendant_pair_is_ambiguous(self):
        entries = [_base_entry(path="src"), _base_entry(path="src/lib")]
        ambiguous = prov.find_ambiguous_entries(entries)
        self.assertEqual(ambiguous, ["src", "src/lib"])

    def test_disjoint_siblings_are_not_ambiguous(self):
        entries = [_base_entry(path="src"), _base_entry(path="docs")]
        self.assertEqual(prov.find_ambiguous_entries(entries), [])

    def test_single_entry_is_never_ambiguous(self):
        entries = [_base_entry(path="src")]
        self.assertEqual(prov.find_ambiguous_entries(entries), [])


class EvaluateCoverageTests(unittest.TestCase):
    def test_clean_bijection_has_no_reasons(self):
        entries = [_base_entry(path="src"), _base_entry(path="docs")]
        reasons = prov.evaluate_coverage(entries, ["src/main.c", "docs/readme.md"])
        self.assertEqual(reasons, [])

    def test_gap_reported(self):
        entries = [_base_entry(path="src")]
        reasons = prov.evaluate_coverage(entries, ["src/main.c", "docs/readme.md"])
        self.assertTrue(any("missing provenance entry for docs/readme.md" in r for r in reasons))

    def test_ghost_reported(self):
        entries = [_base_entry(path="src"), _base_entry(path="nonexistent")]
        reasons = prov.evaluate_coverage(entries, ["src/main.c"])
        self.assertTrue(any("ghost provenance entry" in r and "nonexistent" in r for r in reasons))

    def test_duplicate_reported(self):
        entries = [_base_entry(path="src"), _base_entry(path="src")]
        reasons = prov.evaluate_coverage(entries, ["src/main.c"])
        self.assertTrue(any("duplicate provenance entry path" in r for r in reasons))

    def test_ambiguous_reported(self):
        entries = [_base_entry(path="src"), _base_entry(path="src/lib")]
        reasons = prov.evaluate_coverage(entries, ["src/main.c", "src/lib/x.c"])
        self.assertTrue(any("ambiguous/overlapping provenance coverage" in r for r in reasons))

    def test_real_repo_provenance_is_a_clean_bijection_over_the_exact_allowlist(self):
        """The real, checked-in provenance manifests must fully, cleanly,
        unambiguously cover the real, checked-in exact allowlist -- no
        gap, no ghost, no duplicate/ambiguous entry."""
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        allowlist = json.loads(
            (ROOT / "docs" / "release_data" / "source_allowlist.json").read_text(encoding="utf-8")
        )["paths"]
        self.assertEqual(prov.evaluate_coverage(entries, allowlist), [])


class RepositoryStateTests(unittest.TestCase):
    """The current, real, committed provenance manifests must evaluate to
    an honest, exact BLOCKED status -- never a false 'mechanically
    eligible' (and this module must never emit the bare status token
    "approved" at all -- see EvaluateTests.
    test_fully_resolved_entry_is_mechanically_eligible)."""

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
