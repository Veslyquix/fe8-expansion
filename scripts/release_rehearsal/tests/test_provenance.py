"""Tests for scripts/release_rehearsal/provenance.py (issue #9; exact-provenance remediation)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import provenance as prov


def _base_entry(**overrides):
    entry = {
        "path": "src/main.c",
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


def _git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


class LoadManifestTests(unittest.TestCase):
    def test_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_manifest(Path(tmp), "code.json", [_base_entry()])
            entries = prov.load_manifest(path)
            self.assertEqual(len(entries), 1)

    def test_missing_key_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = {"path": "src/main.c", "category": "code"}
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
    """issue #9 exact-provenance remediation: coverage is pure exact-path
    set membership -- an entry's `path` covers *only* that exact path,
    never a descendant."""

    def test_reports_missing_paths(self):
        entries = [_base_entry(path="src/main.c")]
        gaps = prov.coverage_gaps(entries, ["src/main.c", "docs/readme.md", "graphics/x.png"])
        self.assertEqual(gaps, ["docs/readme.md", "graphics/x.png"])

    def test_no_gaps_when_fully_covered(self):
        entries = [_base_entry(path="src/main.c"), _base_entry(path="docs/readme.md")]
        gaps = prov.coverage_gaps(entries, ["src/main.c", "docs/readme.md"])
        self.assertEqual(gaps, [])

    def test_category_root_no_longer_covers_nested_exact_files(self):
        """The pre-remediation defect: a single category-level entry
        (e.g. "src") used to cover every exact per-file allowlist path
        nested under it by directory-prefix. That is exactly what issue
        #9's exact-provenance-binding requirement forbids now -- a
        directory-shaped entry covers *only* that literal path (which is
        never itself a real tracked file), never any descendant."""
        entries = [_base_entry(path="src")]
        gaps = prov.coverage_gaps(entries, ["src/main.c", "src/lib/helper.c"])
        self.assertEqual(gaps, ["src/lib/helper.c", "src/main.c"])

    def test_new_allowlisted_file_without_exact_provenance_fails(self):
        """A new tracked file, once added to the allowlist, must still
        fail provenance coverage until an exact same-path provenance
        record is explicitly present -- even though a directory-level
        entry for its parent already exists."""
        entries = [_base_entry(path="src/main.c")]
        gaps = prov.coverage_gaps(entries, ["src/main.c", "src/new_file.c"])
        self.assertEqual(gaps, ["src/new_file.c"])

    def test_sibling_prefix_does_not_falsely_cover(self):
        """"src" must not cover "scripts/x.py" merely because both start
        with the same few letters -- coverage was always a real path-
        segment prefix relationship at most, and is now not even that:
        pure exact-path equality only."""
        entries = [_base_entry(path="src")]
        gaps = prov.coverage_gaps(entries, ["scripts/x.py"])
        self.assertEqual(gaps, ["scripts/x.py"])


class FindGhostEntriesTests(unittest.TestCase):
    def test_entry_covering_nothing_is_a_ghost(self):
        entries = [_base_entry(path="src/main.c"), _base_entry(path="long-deleted-file.c")]
        ghosts = prov.find_ghost_entries(entries, ["src/main.c"])
        self.assertEqual(ghosts, ["long-deleted-file.c"])

    def test_entry_covering_something_is_not_a_ghost(self):
        entries = [_base_entry(path="src/main.c")]
        self.assertEqual(prov.find_ghost_entries(entries, ["src/main.c"]), [])

    def test_prefix_only_directory_style_entry_is_a_ghost(self):
        """issue #9 exact-provenance remediation: a bare category/
        directory-style entry (e.g. "src") is never itself an exact
        tracked file -- it is reported as a ghost (covers nothing in the
        exact allowlist), never treated as "covering" its descendants."""
        entries = [_base_entry(path="src")]
        ghosts = prov.find_ghost_entries(entries, ["src/main.c", "src/lib/helper.c"])
        self.assertEqual(ghosts, ["src"])


class FindDuplicateEntryPathsTests(unittest.TestCase):
    def test_exact_duplicate_path_detected(self):
        entries = [_base_entry(path="src/main.c"), _base_entry(path="src/main.c")]
        self.assertEqual(prov.find_duplicate_entry_paths(entries), ["src/main.c"])

    def test_unique_paths_have_no_duplicates(self):
        entries = [_base_entry(path="src/main.c"), _base_entry(path="docs/readme.md")]
        self.assertEqual(prov.find_duplicate_entry_paths(entries), [])


class FindAmbiguousEntriesTests(unittest.TestCase):
    """`find_ambiguous_entries` is now a defense-in-depth hygiene guard: it
    can never legitimately fire against a genuine exact per-tracked-file
    data set (no real Git blob path can be a directory-prefix ancestor of
    another), so its only job is catching a leftover category/prefix-
    style entry left mixed in with exact entries."""

    def test_ancestor_descendant_pair_is_ambiguous(self):
        entries = [_base_entry(path="src"), _base_entry(path="src/lib")]
        ambiguous = prov.find_ambiguous_entries(entries)
        self.assertEqual(ambiguous, ["src", "src/lib"])

    def test_disjoint_siblings_are_not_ambiguous(self):
        entries = [_base_entry(path="src/main.c"), _base_entry(path="docs/readme.md")]
        self.assertEqual(prov.find_ambiguous_entries(entries), [])

    def test_single_entry_is_never_ambiguous(self):
        entries = [_base_entry(path="src/main.c")]
        self.assertEqual(prov.find_ambiguous_entries(entries), [])

    def test_deep_ancestor_of_a_nested_exact_path_is_ambiguous(self):
        """A stray "src" entry alongside a properly exact "src/lib/x.c"
        entry must still be caught even though they are not adjacent
        path-segments apart."""
        entries = [_base_entry(path="src"), _base_entry(path="src/lib/x.c")]
        ambiguous = prov.find_ambiguous_entries(entries)
        self.assertEqual(ambiguous, ["src", "src/lib/x.c"])

    def test_many_exact_sibling_files_are_never_falsely_ambiguous(self):
        """A large, flat set of genuinely exact, unrelated per-file paths
        (the normal, real shape of this data) must never be flagged."""
        entries = [_base_entry(path=f"src/file_{i}.c") for i in range(200)]
        self.assertEqual(prov.find_ambiguous_entries(entries), [])


class EvaluateCoverageTests(unittest.TestCase):
    def test_clean_bijection_has_no_reasons(self):
        entries = [_base_entry(path="src/main.c"), _base_entry(path="docs/readme.md")]
        reasons = prov.evaluate_coverage(entries, ["src/main.c", "docs/readme.md"])
        self.assertEqual(reasons, [])

    def test_gap_reported(self):
        entries = [_base_entry(path="src/main.c")]
        reasons = prov.evaluate_coverage(entries, ["src/main.c", "docs/readme.md"])
        self.assertTrue(any("missing provenance entry for docs/readme.md" in r for r in reasons))

    def test_ghost_reported(self):
        entries = [_base_entry(path="src/main.c"), _base_entry(path="nonexistent")]
        reasons = prov.evaluate_coverage(entries, ["src/main.c"])
        self.assertTrue(any("ghost provenance entry" in r and "nonexistent" in r for r in reasons))

    def test_prefix_only_entry_fails_coverage(self):
        """issue #9 exact-provenance remediation: a category/directory-
        style entry ("src") that used to legitimately cover
        "src/main.c" by directory-prefix must now fail -- both as a
        ghost (its own path is not exactly allowlisted) and leaving
        "src/main.c" itself as a missing gap."""
        entries = [_base_entry(path="src")]
        reasons = prov.evaluate_coverage(entries, ["src/main.c"])
        self.assertTrue(any("ghost provenance entry" in r and "src" in r for r in reasons))
        self.assertTrue(any("missing provenance entry for src/main.c" in r for r in reasons))

    def test_duplicate_reported(self):
        entries = [_base_entry(path="src/main.c"), _base_entry(path="src/main.c")]
        reasons = prov.evaluate_coverage(entries, ["src/main.c"])
        self.assertTrue(any("duplicate provenance entry path" in r for r in reasons))

    def test_ambiguous_reported(self):
        entries = [_base_entry(path="src"), _base_entry(path="src/lib")]
        reasons = prov.evaluate_coverage(entries, ["src/lib"])
        self.assertTrue(any("ambiguous/leftover category-style provenance entry" in r for r in reasons))

    def test_one_exact_record_per_member_passes_structurally_but_blocked_for_facts(self):
        """A perfectly exact, one-record-per-member bijection (no gap, no
        ghost, no duplicate, no ambiguity) must report zero *coverage*
        reasons -- but the overall provenance status is still "blocked"
        while any entry's own facts (author/license/redistribution/
        reviewer) remain unresolved. Structural exactness is necessary,
        never sufficient, for eligibility."""
        entries = [_base_entry(path="src/main.c"), _base_entry(path="docs/readme.md")]
        coverage_reasons = prov.evaluate_coverage(entries, ["src/main.c", "docs/readme.md"])
        self.assertEqual(coverage_reasons, [])
        status, reasons = prov.evaluate(entries)
        self.assertEqual(status, "blocked")
        self.assertTrue(reasons)


class CheckGitlinkPinsTests(unittest.TestCase):
    """issue #9 exact-provenance remediation: a "submodule"-category
    entry's declared `pinned_commit` must match the actual gitlink
    object id Git's own tree records, not merely whatever the JSON
    itself claims."""

    def _init_repo_with_gitlink(self, root: Path, gitlink_sha: str) -> None:
        _git("init", "-q", cwd=root)
        _git("config", "user.email", "t@example.com", cwd=root)
        _git("config", "user.name", "Tester", cwd=root)
        (root / "regular.txt").write_text("hello\n")
        _git("add", "regular.txt", cwd=root)
        # Fabricate a gitlink (mode 160000) tree entry directly via
        # `git update-index --add --cacheinfo` -- no real submodule
        # needs to be configured/initialized for this.
        _git(
            "update-index", "--add", "--cacheinfo", f"160000,{gitlink_sha},mgfembp",
            cwd=root,
        )
        _git("commit", "-q", "-m", "initial", cwd=root)

    def test_matching_pin_has_no_reasons(self):
        sha = "c87e74dcd6c8878b809e013cd8ff0c52baa75332"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo_with_gitlink(root, sha)
            entries = [_base_entry(path="mgfembp", category="submodule", pinned_commit=sha)]
            self.assertEqual(prov.check_gitlink_pins(entries, root), [])

    def test_mismatched_pin_fails(self):
        real_sha = "c87e74dcd6c8878b809e013cd8ff0c52baa75332"
        wrong_sha = "0" * 40
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo_with_gitlink(root, real_sha)
            entries = [_base_entry(path="mgfembp", category="submodule", pinned_commit=wrong_sha)]
            reasons = prov.check_gitlink_pins(entries, root)
            self.assertTrue(reasons)
            self.assertTrue(any("does not match" in r and "mgfembp" in r for r in reasons))

    def test_no_submodule_entries_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git("init", "-q", cwd=root)
            entries = [_base_entry(path="src/main.c", category="code")]
            self.assertEqual(prov.check_gitlink_pins(entries, root), [])

    def test_non_git_root_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = [_base_entry(path="mgfembp", category="submodule", pinned_commit="c87e74dcd6c8878b809e013cd8ff0c52baa75332")]
            self.assertEqual(prov.check_gitlink_pins(entries, root), [])

    def test_missing_gitlink_path_fails(self):
        sha = "c87e74dcd6c8878b809e013cd8ff0c52baa75332"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo_with_gitlink(root, sha)
            entries = [_base_entry(path="does-not-exist", category="submodule", pinned_commit=sha)]
            reasons = prov.check_gitlink_pins(entries, root)
            self.assertTrue(any("no gitlink is recorded" in r for r in reasons))

    def test_real_repo_gitlink_pin_matches(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        self.assertEqual(prov.check_gitlink_pins(entries, ROOT), [])


class GenerateExactEntriesTests(unittest.TestCase):
    """Tests for the deterministic generator (`generate_exact_entries`)
    that fans `PROVENANCE_ROOT_SEED`'s small, human-curated per-root
    values out to one exact per-file record."""

    SEED = (
        prov.RootSeed("src", "code", "code note", None),
        prov.RootSeed("docs", "code", "docs note", None),
        prov.RootSeed("mgfembp", "submodule", "submodule note", "c87e74dcd6c8878b809e013cd8ff0c52baa75332"),
    )

    def test_fans_out_one_exact_entry_per_path(self):
        entries = prov.generate_exact_entries(
            ["src/main.c", "src/lib/helper.c", "docs/readme.md", "mgfembp"], seed=self.SEED,
        )
        by_path = {entry["path"]: entry for entry in entries}
        self.assertEqual(sorted(by_path), ["docs/readme.md", "mgfembp", "src/lib/helper.c", "src/main.c"])
        self.assertEqual(by_path["src/main.c"]["category"], "code")
        self.assertEqual(by_path["src/main.c"]["notes"], "code note")
        self.assertEqual(by_path["mgfembp"]["pinned_commit"], "c87e74dcd6c8878b809e013cd8ff0c52baa75332")

    def test_generated_entries_never_invent_resolved_facts(self):
        entries = prov.generate_exact_entries(["src/main.c"], seed=self.SEED)
        entry = entries[0]
        self.assertEqual(entry["author"], "NOASSERTION")
        self.assertEqual(entry["rightsholder"], "NOASSERTION")
        self.assertEqual(entry["license"], "NOASSERTION")
        self.assertFalse(entry["redistribution_approved"])
        self.assertIsNone(entry["reviewer"])

    def test_unassigned_path_is_actionable(self):
        with self.assertRaises(prov.ProvenanceError) as ctx:
            prov.generate_exact_entries(["totally/unrooted/path.c"], seed=self.SEED)
        self.assertIn("matches no seed root", str(ctx.exception))

    def test_ambiguous_seed_roots_are_actionable(self):
        overlapping_seed = self.SEED + (prov.RootSeed("src/lib", "code", "nested root", None),)
        with self.assertRaises(prov.ProvenanceError) as ctx:
            prov.generate_exact_entries(["src/lib/helper.c"], seed=overlapping_seed)
        self.assertIn("matches more than one seed root", str(ctx.exception))

    def test_root_itself_is_a_valid_exact_path(self):
        """A root path that is *itself* one of the exact allowlisted
        paths (e.g. a root that is a real tracked file, not just a
        directory) gets its own exact entry too."""
        entries = prov.generate_exact_entries(["docs"], seed=self.SEED)
        self.assertEqual(entries[0]["path"], "docs")

    def test_real_seed_covers_the_real_exact_allowlist_with_no_errors(self):
        """`PROVENANCE_ROOT_SEED` (the real, checked-in 46-root seed) must
        assign every single real, checked-in exact allowlist path to
        exactly one root -- this is exactly the invariant that let this
        repository regenerate its provenance data deterministically
        instead of requiring ~9,000 hand-authored records."""
        allowlist = json.loads(
            (ROOT / "docs" / "release_data" / "source_allowlist.json").read_text(encoding="utf-8")
        )["paths"]
        entries = prov.generate_exact_entries(allowlist)
        self.assertEqual(sorted(entry["path"] for entry in entries), sorted(allowlist))

    def test_write_generated_provenance_splits_by_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            provenance_dir = Path(tmp)
            entries = prov.generate_exact_entries(
                ["src/main.c", "docs/readme.md", "mgfembp"], seed=self.SEED,
            )
            counts = prov.write_generated_provenance(provenance_dir, entries)
            self.assertEqual(counts, {"code.json": 2, "assets.json": 0, "submodules.json": 1})
            written = json.loads((provenance_dir / "code.json").read_text(encoding="utf-8"))
            self.assertEqual([e["path"] for e in written], ["docs/readme.md", "src/main.c"])


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

    def test_real_repo_provenance_is_a_clean_bijection_over_the_exact_allowlist(self):
        """The real, checked-in provenance manifests must fully, cleanly,
        unambiguously cover the real, checked-in exact allowlist -- no
        gap, no ghost, no duplicate/ambiguous entry, and (issue #9
        exact-provenance remediation) the exact *set* of provenance paths
        must equal the exact *set* of allowlist paths one-for-one -- not
        merely 46 category roots "covering" thousands of files by
        prefix."""
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        allowlist = json.loads(
            (ROOT / "docs" / "release_data" / "source_allowlist.json").read_text(encoding="utf-8")
        )["paths"]
        self.assertEqual(prov.evaluate_coverage(entries, allowlist), [])
        entry_paths = [entry["path"] for entry in entries]
        self.assertEqual(len(entry_paths), len(set(entry_paths)), "no duplicate provenance paths")
        self.assertEqual(sorted(entry_paths), sorted(allowlist), "exact one-record-per-member bijection")

    def test_real_provenance_has_one_record_per_allowlist_member_not_one_per_category(self):
        """issue #9 exact-provenance remediation's headline fact: there
        are as many provenance records as there are exact allowlisted
        members (thousands), never merely a handful of category roots."""
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        allowlist = json.loads(
            (ROOT / "docs" / "release_data" / "source_allowlist.json").read_text(encoding="utf-8")
        )["paths"]
        self.assertEqual(len(entries), len(allowlist))
        self.assertGreater(len(entries), 9000)

    def test_real_gitlink_pin_matches_the_actual_tree(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        self.assertEqual(prov.check_gitlink_pins(entries, ROOT), [])


if __name__ == "__main__":
    unittest.main()
