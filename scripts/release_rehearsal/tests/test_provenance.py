"""Tests for scripts/release_rehearsal/provenance.py (issue #9; exact-provenance remediation)."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import git_source as gs
from scripts.release_rehearsal import provenance as prov
from scripts.release_rehearsal import tree_coverage as tc


def _base_entry(**overrides):
    """issue #9 mandatory correction #3: every "code"/"asset" entry now
    also needs a well-formed (schema-valid, not necessarily *live*-
    cross-checked -- that is `CheckBlobIdentityTests`' job below) 'oid'/
    'sha256'; a "submodule" entry must never carry a non-null 'sha256' at
    all (a gitlink has no blob content). This helper supplies harmless
    placeholder defaults for the common "code"/"asset" case, and drops
    them back out automatically for a "submodule"-category override so
    every existing call site that only cares about the other fields
    keeps working unchanged."""
    entry = {
        "path": "src/main.c",
        "category": "code",
        "author": "NOASSERTION",
        "rightsholder": "NOASSERTION",
        "license": "NOASSERTION",
        "redistribution_approved": False,
        "reviewer": None,
        "notes": "seed",
        "oid": "a" * 40,
        "sha256": "b" * 64,
    }
    entry.update(overrides)
    if entry["category"] == "submodule":
        if "sha256" not in overrides:
            entry["sha256"] = None
        if "oid" not in overrides:
            entry.pop("oid", None)
        if "url" not in overrides:
            entry["url"] = "https://example.invalid/mgfembp.git"
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

    def test_stray_self_entry_for_excluded_code_json_is_a_ghost(self):
        """issue #9 guardian-correction remediation (D2), the "excluded
        self-referential evidence path" tamper probe: docs/release_data/
        provenance/code.json is now an explicit export exclusion (see
        tree_coverage.py) and is never a required-coverage path -- a
        stray, leftover self-record for it (e.g. left behind by a
        generator that was not updated, or hand-added back in) is
        reported as a ghost, never silently accepted as legitimate
        coverage just because its path happens to name a real provenance
        manifest file."""
        required_paths = ["src/main.c", "mgfembp"]  # deliberately excludes code.json's own path
        entries = [
            _base_entry(path="src/main.c"),
            _base_entry(path="mgfembp", category="submodule", pinned_commit="c" * 40),
            _base_entry(path="docs/release_data/provenance/code.json"),
        ]
        ghosts = prov.find_ghost_entries(entries, required_paths)
        self.assertIn("docs/release_data/provenance/code.json", ghosts)


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


class AssignRootTests(unittest.TestCase):
    """Pure (no git access) fan-out/ambiguity logic, split out of
    `generate_exact_entries` specifically so it stays unit-testable
    without a real git repository (`_assign_root`)."""

    SEED = (
        prov.RootSeed("src", "code", "code note"),
        prov.RootSeed("docs", "code", "docs note"),
        prov.RootSeed("mgfembp", "submodule", "submodule note"),
    )

    def test_exact_root_path_assigned(self):
        self.assertEqual(prov._assign_root("docs", self.SEED).root, "docs")

    def test_nested_path_assigned_to_covering_root(self):
        self.assertEqual(prov._assign_root("src/lib/helper.c", self.SEED).root, "src")

    def test_unassigned_path_is_actionable(self):
        with self.assertRaises(prov.ProvenanceError) as ctx:
            prov._assign_root("totally/unrooted/path.c", self.SEED)
        self.assertIn("matches no seed root", str(ctx.exception))

    def test_ambiguous_seed_roots_are_actionable(self):
        overlapping_seed = self.SEED + (prov.RootSeed("src/lib", "code", "nested root"),)
        with self.assertRaises(prov.ProvenanceError) as ctx:
            prov._assign_root("src/lib/helper.c", overlapping_seed)
        self.assertIn("matches more than one seed root", str(ctx.exception))

    def test_real_cjk_font_path_uses_narrow_cjk_seed(self):
        assigned = prov._assign_root(
            "fonts/cjk/upstream/NotoSansJP-Regular.otf",
            prov.PROVENANCE_ROOT_SEED,
        )
        self.assertEqual(assigned.root, "fonts/cjk")
        self.assertEqual(assigned.notes, prov._NOTE_CJK_FONT_ASSETS)

    def test_unrelated_font_path_requires_separate_review(self):
        with self.assertRaises(prov.ProvenanceError) as ctx:
            prov._assign_root(
                "fonts/unrelated/FutureFont-Regular.otf",
                prov.PROVENANCE_ROOT_SEED,
            )
        self.assertIn("matches no seed root", str(ctx.exception))

    def test_real_seed_covers_the_real_exact_allowlist_and_exclusions_with_no_errors(self):
        """`PROVENANCE_ROOT_SEED` (the real, checked-in 46-root seed) must
        assign every single real, checked-in exact allowlist/exclusion
        path to exactly one root -- this is exactly the invariant that
        lets this repository regenerate its provenance data
        deterministically instead of requiring ~9,000 hand-authored
        records."""
        allowlist = json.loads(
            (ROOT / "docs" / "release_data" / "source_allowlist.json").read_text(encoding="utf-8")
        )["paths"]
        exclusions = json.loads(
            (ROOT / "docs" / "release_data" / "export_exclusions.json").read_text(encoding="utf-8")
        )["exclusions"]
        all_paths = list(allowlist) + [entry["path"] for entry in exclusions]
        for path in all_paths:
            prov._assign_root(path, prov.PROVENANCE_ROOT_SEED)  # raises on any real defect


class GenerateExactEntriesTests(unittest.TestCase):
    """Tests for the deterministic generator (`generate_exact_entries`)
    that fans `PROVENANCE_ROOT_SEED`'s small, human-curated per-root
    values out to one exact per-file record -- issue #9 mandatory
    correction #3: every generated "code"/"asset" entry is now bound to
    its exact, live Git blob identity (`oid`/`sha256`), and every
    generated "submodule" entry's `pinned_commit` is read fresh from the
    live gitlink -- never carried over/hand-supplied."""

    SEED = (
        prov.RootSeed("src", "code", "code note"),
        prov.RootSeed("docs", "code", "docs note"),
        prov.RootSeed("mgfembp", "submodule", "submodule note"),
    )
    GITLINK_SHA = "c87e74dcd6c8878b809e013cd8ff0c52baa75332"

    def _make_repo(self, root: Path) -> str:
        _git("init", "-q", cwd=root)
        _git("config", "user.email", "t@example.com", cwd=root)
        _git("config", "user.name", "Tester", cwd=root)
        (root / "src").mkdir()
        (root / "src" / "main.c").write_text("int main(void){return 0;}")
        (root / "src" / "lib").mkdir()
        (root / "src" / "lib" / "helper.c").write_text("int helper(void){return 1;}")
        (root / "docs").mkdir()
        (root / "docs" / "readme.md").write_text("hi\n")
        (root / ".gitmodules").write_text(
            '[submodule "mgfembp"]\n\tpath = mgfembp\n\turl = https://example.invalid/mgfembp.git\n'
        )
        _git("add", "-A", cwd=root)
        _git("update-index", "--add", "--cacheinfo", f"160000,{self.GITLINK_SHA},mgfembp", cwd=root)
        _git("commit", "-q", "-m", "init", cwd=root)
        return gs.resolve_sha(root, "HEAD")

    def test_fans_out_one_exact_entry_per_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._make_repo(root)
            entries = prov.generate_exact_entries(
                root, sha,
                ["src/main.c", "src/lib/helper.c", "docs/readme.md"], ["mgfembp"],
                seed=self.SEED,
            )
            by_path = {entry["path"]: entry for entry in entries}
            self.assertEqual(sorted(by_path), ["docs/readme.md", "mgfembp", "src/lib/helper.c", "src/main.c"])
            self.assertEqual(by_path["src/main.c"]["category"], "code")
            self.assertEqual(by_path["src/main.c"]["notes"], "code note")
            self.assertEqual(by_path["mgfembp"]["pinned_commit"], self.GITLINK_SHA)
            self.assertEqual(by_path["mgfembp"]["category"], "submodule")
            self.assertIsNone(by_path["mgfembp"].get("sha256"))

    def test_generated_blob_entries_have_real_oid_and_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._make_repo(root)
            entries = prov.generate_exact_entries(root, sha, ["src/main.c"], [], seed=self.SEED)
            entry = entries[0]
            tree_entry = {e.path: e for e in gs.list_tree(root, sha)}["src/main.c"]
            self.assertEqual(entry["oid"], tree_entry.object_id)
            expected_sha256 = hashlib.sha256(b"int main(void){return 0;}").hexdigest()
            self.assertEqual(entry["sha256"], expected_sha256)

    def test_generated_entries_never_invent_resolved_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._make_repo(root)
            entries = prov.generate_exact_entries(root, sha, ["src/main.c"], [], seed=self.SEED)
            entry = entries[0]
            self.assertEqual(entry["author"], "NOASSERTION")
            self.assertEqual(entry["rightsholder"], "NOASSERTION")
            self.assertEqual(entry["license"], "NOASSERTION")
            self.assertFalse(entry["redistribution_approved"])
            self.assertIsNone(entry["reviewer"])

    def test_changed_blob_gets_a_fresh_oid_and_sha256_not_the_old_one(self):
        """The literal issue #9 requirement: regenerating after a blob's
        content changes must produce the *new* identity, never
        preserve/re-emit the old one."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha1 = self._make_repo(root)
            entries1 = prov.generate_exact_entries(root, sha1, ["src/main.c"], [], seed=self.SEED)

            (root / "src" / "main.c").write_text("int main(void){return 42;}")
            _git("commit", "-q", "-am", "change main.c", cwd=root)
            sha2 = gs.resolve_sha(root, "HEAD")
            entries2 = prov.generate_exact_entries(root, sha2, ["src/main.c"], [], seed=self.SEED)

            self.assertNotEqual(entries1[0]["oid"], entries2[0]["oid"])
            self.assertNotEqual(entries1[0]["sha256"], entries2[0]["sha256"])

    def test_docs_path_declared_as_an_exclusion_is_actionable(self):
        """A path whose seed root assigns it a non-"submodule" category
        (here: "docs" -> "code") must be declared in `allowlist_paths`,
        never smuggled in via `exclusion_paths` alone."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._make_repo(root)
            with self.assertRaises(prov.ProvenanceError) as ctx:
                prov.generate_exact_entries(root, sha, ["src/main.c"], ["docs/readme.md"], seed=self.SEED)
            self.assertIn("was not declared in allowlist_paths", str(ctx.exception))

    def test_mgfembp_declared_as_allowlisted_is_actionable(self):
        """The mirror-image: a "submodule"-category path (mgfembp) must
        be declared in `exclusion_paths`, never smuggled in via
        `allowlist_paths` alone."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._make_repo(root)
            with self.assertRaises(prov.ProvenanceError) as ctx:
                prov.generate_exact_entries(root, sha, ["mgfembp"], [], seed=self.SEED)
            self.assertIn("was not declared in exclusion_paths", str(ctx.exception))

    def test_submodule_path_not_a_live_gitlink_is_actionable(self):
        """Even when correctly declared via `exclusion_paths`, a path
        that is not *actually* a live gitlink in the tree is still
        rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._make_repo(root)
            with self.assertRaises(prov.ProvenanceError) as ctx:
                prov.generate_exact_entries(root, sha, ["src/main.c"], ["mgfembp-does-not-exist"], seed=(
                    self.SEED + (prov.RootSeed("mgfembp-does-not-exist", "submodule", "note"),)
                ))
            self.assertIn("not a live gitlink", str(ctx.exception))

    def test_code_path_not_a_live_safe_blob_is_actionable(self):
        """Even when correctly declared via `allowlist_paths`, a path
        that is not *actually* a live safe blob in the tree is still
        rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._make_repo(root)
            with self.assertRaises(prov.ProvenanceError) as ctx:
                prov.generate_exact_entries(root, sha, ["docs/does-not-exist.md"], [], seed=self.SEED)
            self.assertIn("not a live safe blob", str(ctx.exception))

    def test_unassigned_path_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._make_repo(root)
            with self.assertRaises(prov.ProvenanceError) as ctx:
                prov.generate_exact_entries(root, sha, ["totally/unrooted/path.c"], [], seed=self.SEED)
            self.assertIn("matches no seed root", str(ctx.exception))

    def test_root_itself_is_a_valid_exact_path(self):
        """A root path that is *itself* one of the exact allowlisted
        paths (e.g. a root that is a real tracked file, not just a
        directory) gets its own exact entry too."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._make_repo(root)
            entries = prov.generate_exact_entries(root, sha, ["docs/readme.md"], [], seed=self.SEED)
            self.assertEqual(entries[0]["path"], "docs/readme.md")

    def test_real_repo_generation_matches_the_real_allowlist_and_exclusions(self):
        """End-to-end against this actual repository's own real HEAD:
        `PROVENANCE_ROOT_SEED` must assign every real allowlist/exclusion
        path with no error, and every generated entry's identity must
        equal what `git ls-tree`/blob content actually says."""
        allowlist = json.loads(
            (ROOT / "docs" / "release_data" / "source_allowlist.json").read_text(encoding="utf-8")
        )["paths"]
        exclusions = json.loads(
            (ROOT / "docs" / "release_data" / "export_exclusions.json").read_text(encoding="utf-8")
        )["exclusions"]
        # issue #9 guardian-correction remediation (D2): only a
        # *gitlink*-kind exclusion (mgfembp) is ever fanned into
        # generation/required-coverage -- a `self_referential_evidence`-
        # kind exclusion (docs/release_data/provenance/code.json) is
        # deliberately never assigned any provenance category at all
        # (see PROVENANCE_ROOT_SEED/`_assign_root`'s own category-vs-
        # declared-set cross-check), exactly mirroring the real
        # `provenance.py generate`/`check` CLI's own `_load_exclusion_
        # paths` filtering.
        exclusion_paths = [entry["path"] for entry in exclusions if entry["kind"] == "gitlink"]
        sha = gs.resolve_sha(ROOT, "HEAD")
        # A small, fast subset (the full ~9000-path generation is exercised
        # by RepositoryStateTests against the actual committed data below;
        # regenerating it here too would just needlessly re-hash ~70MB of
        # blobs for a second time in the same test run).
        sample = sorted(allowlist)[:25] + exclusion_paths
        entries = prov.generate_exact_entries(ROOT, sha, sample, exclusion_paths, seed=prov.PROVENANCE_ROOT_SEED)
        self.assertEqual(sorted(e["path"] for e in entries), sorted(sample))
        mgfembp = next(e for e in entries if e["path"] == "mgfembp")
        self.assertEqual(mgfembp["pinned_commit"], self.GITLINK_SHA)

    def test_write_generated_provenance_splits_by_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._make_repo(root)
            entries = prov.generate_exact_entries(
                root, sha, ["src/main.c", "docs/readme.md"], ["mgfembp"], seed=self.SEED,
            )
            provenance_dir = Path(tempfile.mkdtemp())
            counts = prov.write_generated_provenance(provenance_dir, entries)
            self.assertEqual(counts, {"code.json": 2, "assets.json": 0, "submodules.json": 1})
            written = json.loads((provenance_dir / "code.json").read_text(encoding="utf-8"))
            self.assertEqual([e["path"] for e in written], ["docs/readme.md", "src/main.c"])


class LoadExclusionPathsDelegatesToTreeCoverageTests(unittest.TestCase):
    """issue #9 (final-review follow-up): `provenance._load_exclusion_
    paths` used to be its own second, independent, permissive parser of
    `docs/release_data/export_exclusions.json` -- it accepted any entry
    with a string `path` and a bare `kind == "gitlink"` string
    comparison, with no curated-path check, no `oid` shape/well-
    formedness check, no mode check, and no duplicate-path check at all.
    That was backstopped (never exploitable) only because
    `tree_coverage.check_partition()`/`manifest.py`'s composite report
    separately, correctly rejected the same malformed/fabricated row --
    an independent review flagged this as a live defense-in-depth gap:
    the same trust file should have exactly one strict validator, not
    two parsers that can silently drift apart. This class proves the
    provenance reader itself -- not only a composite backstop -- now
    fails closed, because it delegates entirely to
    `tree_coverage.load_exclusion_paths(..., kinds=tree_coverage.
    PROVENANCE_REQUIRED_EXCLUSION_KINDS)` instead of re-implementing a
    second, more permissive reader."""

    @staticmethod
    def _write_exclusions(dir_path, entries):
        exclusions_path = dir_path / "export_exclusions.json"
        exclusions_path.write_text(json.dumps({"exclusions": entries}), encoding="utf-8")
        return exclusions_path

    def test_missing_exclusions_file_still_returns_empty_unchanged(self):
        """Behavior unchanged by this fix: a genuinely absent exclusions
        file still returns an empty list, never an error (this mirrors
        every existing `check`/`generate` call site's own
        `args.exclusions.is_file()` guard)."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(prov._load_exclusion_paths(Path(tmp) / "does-not-exist.json"), [])

    def test_only_gitlink_kind_paths_are_returned(self):
        """The real, curated self-referential-evidence exclusion
        (`docs/release_data/provenance/code.json`) must never be fanned
        into the provenance-required set -- only `PROVENANCE_REQUIRED_
        EXCLUSION_KINDS` (today just `KIND_GITLINK`) paths come back,
        exactly as before this fix."""
        with tempfile.TemporaryDirectory() as tmp:
            curated_path = sorted(tc.SELF_REFERENTIAL_EVIDENCE_PATHS)[0]
            exclusions_path = self._write_exclusions(Path(tmp), [
                {"path": "mgfembp", "kind": "gitlink", "mode": gs.MODE_GITLINK, "oid": "a" * 40, "reason": "r"},
                {"path": curated_path, "kind": "self_referential_evidence", "mode": "100644", "oid": None, "reason": "r"},
            ])
            self.assertEqual(prov._load_exclusion_paths(exclusions_path), ["mgfembp"])

    def test_arbitrary_gitlink_path_with_fabricated_oid_fails_the_reader_directly(self):
        """An arbitrary/uncurated gitlink path (tree_coverage places no
        curation requirement on a gitlink *path* itself, unlike self-
        referential-evidence) carrying a fabricated, not-well-formed
        `oid` (here: too short, never a real 40-lowercase-hex commit)
        must be rejected by the reader itself -- the old permissive
        reader accepted any string `path` unconditionally."""
        with tempfile.TemporaryDirectory() as tmp:
            exclusions_path = self._write_exclusions(Path(tmp), [
                {"path": "some/arbitrary/gitlink", "kind": "gitlink", "mode": gs.MODE_GITLINK,
                 "oid": "not-a-real-oid", "reason": "bogus"},
            ])
            with self.assertRaises(prov.ProvenanceError) as ctx:
                prov._load_exclusion_paths(exclusions_path)
            self.assertIn("some/arbitrary/gitlink", str(ctx.exception))

    def test_null_oid_on_a_gitlink_entry_fails_the_reader(self):
        """A gitlink-kind entry's `oid` is mandatory (unlike self-
        referential-evidence's, which must be null); a null/missing
        `oid` must be rejected here, not silently treated as an
        excluded/unpinned gitlink."""
        with tempfile.TemporaryDirectory() as tmp:
            exclusions_path = self._write_exclusions(Path(tmp), [
                {"path": "mgfembp", "kind": "gitlink", "mode": gs.MODE_GITLINK, "oid": None, "reason": "r"},
            ])
            with self.assertRaises(prov.ProvenanceError):
                prov._load_exclusion_paths(exclusions_path)

    def test_mismatched_case_oid_fails_the_reader(self):
        """A well-formed-length but not-lowercase (i.e. never a real Git
        OID as Git itself would ever print it) `oid` must be rejected --
        the old reader never inspected `oid` at all for any kind."""
        with tempfile.TemporaryDirectory() as tmp:
            exclusions_path = self._write_exclusions(Path(tmp), [
                {"path": "mgfembp", "kind": "gitlink", "mode": gs.MODE_GITLINK, "oid": "A" * 40, "reason": "r"},
            ])
            with self.assertRaises(prov.ProvenanceError):
                prov._load_exclusion_paths(exclusions_path)

    def test_wrong_mode_on_a_gitlink_entry_fails_the_reader(self):
        """A gitlink-kind entry must record Git's real gitlink mode
        (`160000`); any other mode (e.g. an ordinary blob mode) is
        rejected here -- the old reader never inspected `mode` at all."""
        with tempfile.TemporaryDirectory() as tmp:
            exclusions_path = self._write_exclusions(Path(tmp), [
                {"path": "mgfembp", "kind": "gitlink", "mode": "100644", "oid": "a" * 40, "reason": "r"},
            ])
            with self.assertRaises(prov.ProvenanceError):
                prov._load_exclusion_paths(exclusions_path)

    def test_unrecognized_kind_fails_the_reader(self):
        """A `kind` outside `tree_coverage.VALID_EXCLUSION_KINDS`
        entirely (never merely "not the literal string 'gitlink'", the
        old reader's only check) must be rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            exclusions_path = self._write_exclusions(Path(tmp), [
                {"path": "mgfembp", "kind": "bogus-kind", "mode": gs.MODE_GITLINK, "oid": "a" * 40, "reason": "r"},
            ])
            with self.assertRaises(prov.ProvenanceError):
                prov._load_exclusion_paths(exclusions_path)

    def test_duplicate_exclusion_entry_fails_the_reader(self):
        """Two exclusion rows for the exact same path (even if each is
        individually well-formed) must be rejected -- the old reader had
        no duplicate-path check at all and would have silently
        deduplicated it away via its bare list-append."""
        with tempfile.TemporaryDirectory() as tmp:
            exclusions_path = self._write_exclusions(Path(tmp), [
                {"path": "mgfembp", "kind": "gitlink", "mode": gs.MODE_GITLINK, "oid": "a" * 40, "reason": "r"},
                {"path": "mgfembp", "kind": "gitlink", "mode": gs.MODE_GITLINK, "oid": "b" * 40, "reason": "r2"},
            ])
            with self.assertRaises(prov.ProvenanceError) as ctx:
                prov._load_exclusion_paths(exclusions_path)
            self.assertIn("duplicate", str(ctx.exception).lower())

    def test_self_evidence_misuse_on_an_arbitrary_path_fails_the_reader(self):
        """An arbitrary/uncurated tracked path masquerading as
        `kind == "self_referential_evidence"` (never a member of
        `tree_coverage.SELF_REFERENTIAL_EVIDENCE_PATHS`) must still be
        rejected here even though this reader only ever *returns*
        gitlink-kind paths -- the whole exclusions document is validated
        up front, so a bogus row of any kind poisons the file, exactly
        like `tree_coverage.load_exclusions()` itself, never silently
        ignored merely because it would be filtered out of the final
        result anyway."""
        with tempfile.TemporaryDirectory() as tmp:
            exclusions_path = self._write_exclusions(Path(tmp), [
                {"path": "mgfembp", "kind": "gitlink", "mode": gs.MODE_GITLINK, "oid": "a" * 40, "reason": "r"},
                {"path": "docs/some/arbitrary/file.md", "kind": "self_referential_evidence",
                 "mode": "100644", "oid": None, "reason": "bogus"},
            ])
            with self.assertRaises(prov.ProvenanceError) as ctx:
                prov._load_exclusion_paths(exclusions_path)
            self.assertIn("docs/some/arbitrary/file.md", str(ctx.exception))

    def test_arbitrary_gitlink_bogus_exclusion_fails_check_end_to_end(self):
        """The full reproducer, wired end-to-end through `prov.main`'s
        `check` subcommand (the actual CLI/`make release-check` entry
        point that computes `required_paths` via `_load_exclusion_
        paths`): a bogus exclusions file must make `check` fail loudly
        (non-zero exit), never silently succeed merely because
        `tree_coverage.check_partition()` would separately catch the
        same defect against the same file."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git("init", "-q", cwd=root)
            _git("config", "user.email", "t@example.com", cwd=root)
            _git("config", "user.name", "T", cwd=root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)

            allowlist_path = root / "allow.json"
            allowlist_path.write_text(json.dumps({"paths": ["a.txt"]}), encoding="utf-8")
            provenance_dir = root / "provenance"
            provenance_dir.mkdir()
            (provenance_dir / "code.json").write_text(json.dumps([
                _base_entry(path="a.txt"),
            ]), encoding="utf-8")
            exclusions_path = self._write_exclusions(root, [
                {"path": "some/arbitrary/gitlink", "kind": "gitlink", "mode": gs.MODE_GITLINK,
                 "oid": "not-a-real-oid", "reason": "bogus"},
            ])
            rc = prov.main([
                "check",
                "--repo-root", str(root),
                "--provenance-dir", str(provenance_dir),
                "--allowlist", str(allowlist_path),
                "--exclusions", str(exclusions_path),
            ])
            self.assertEqual(rc, 2, "a bogus exclusions file must make 'check' fail loudly, exit code 2")


class CheckBlobIdentityTests(unittest.TestCase):
    """issue #9 mandatory correction #3: a "code"/"asset"-category
    entry's declared `oid`/`sha256` must match the actual, live blob
    Git's own tree records, not merely whatever the JSON itself claims."""

    def _init_repo_with_file(self, root: Path, content: bytes = b"int x;") -> str:
        _git("init", "-q", cwd=root)
        _git("config", "user.email", "t@example.com", cwd=root)
        _git("config", "user.name", "Tester", cwd=root)
        (root / "main.c").write_bytes(content)
        _git("add", "main.c", cwd=root)
        _git("commit", "-q", "-m", "initial", cwd=root)
        return gs.resolve_sha(root, "HEAD")

    def _real_identity(self, root: Path, sha: str, path: str):
        tree_entry = {e.path: e for e in gs.list_tree(root, sha)}[path]
        data = gs.read_blobs(root, [tree_entry.object_id])[tree_entry.object_id]
        return tree_entry.object_id, hashlib.sha256(data).hexdigest()

    def test_matching_identity_has_no_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_repo_with_file(root)
            oid, sha256_value = self._real_identity(root, sha, "main.c")
            entries = [_base_entry(path="main.c", oid=oid, sha256=sha256_value)]
            self.assertEqual(prov.check_blob_identity(entries, root, sha), [])

    def test_stale_oid_after_content_change_fails(self):
        """The literal issue #9 requirement: a changed blob whose
        provenance record was not regenerated must invalidate (never
        silently pass) the old record."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha1 = self._init_repo_with_file(root, b"int x;")
            oid1, sha256_1 = self._real_identity(root, sha1, "main.c")

            (root / "main.c").write_bytes(b"int x; int y;")
            _git("commit", "-q", "-am", "change", cwd=root)
            sha2 = gs.resolve_sha(root, "HEAD")

            stale_entries = [_base_entry(path="main.c", oid=oid1, sha256=sha256_1)]
            reasons = prov.check_blob_identity(stale_entries, root, sha2)
            self.assertTrue(any("does not match" in r and "main.c" in r for r in reasons))

    def test_wrong_sha256_with_correct_oid_fails(self):
        """oid and sha256 are independently cross-checked -- a correct
        oid never excuses an incorrect sha256."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_repo_with_file(root)
            oid, _real_sha256 = self._real_identity(root, sha, "main.c")
            entries = [_base_entry(path="main.c", oid=oid, sha256="0" * 64)]
            reasons = prov.check_blob_identity(entries, root, sha)
            self.assertTrue(any("sha256" in r and "does not match" in r for r in reasons))

    def test_missing_path_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_repo_with_file(root)
            entries = [_base_entry(path="does-not-exist.c", oid="a" * 40, sha256="b" * 64)]
            reasons = prov.check_blob_identity(entries, root, sha)
            self.assertTrue(any("no safe blob is recorded" in r for r in reasons))

    def test_gitlink_path_declared_as_code_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_repo_with_file(root)
            _git("update-index", "--add", "--cacheinfo", "160000,c87e74dcd6c8878b809e013cd8ff0c52baa75332,link", cwd=root)
            _git("commit", "-q", "-m", "add gitlink", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = [_base_entry(path="link", oid="a" * 40, sha256="b" * 64)]
            reasons = prov.check_blob_identity(entries, root, sha)
            self.assertTrue(any("no safe blob is recorded" in r for r in reasons))

    def test_no_code_or_asset_entries_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._init_repo_with_file(root)
            entries = [_base_entry(path="mgfembp", category="submodule", pinned_commit="a" * 40)]
            self.assertEqual(prov.check_blob_identity(entries, root, sha), [])

    def test_non_git_root_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = [_base_entry(path="main.c", oid="a" * 40, sha256="b" * 64)]
            self.assertEqual(prov.check_blob_identity(entries, root, "HEAD"), [])

    def test_no_path_is_exempted_from_blob_identity_any_more(self):
        """issue #9 guardian-correction remediation (D2): a fresh,
        independent review found the previous version of this module
        exempted ALL THREE provenance-manifest files (code.json,
        assets.json, submodules.json) from `check_blob_identity`, even
        though only code.json's *own* self-record is genuinely
        structurally self-referential (a record about code.json's own
        content would have to live inside code.json itself). code.json
        is now an explicit export exclusion (see
        `tree_coverage.KIND_SELF_REFERENTIAL_EVIDENCE`) and is never
        generated with a self-record at all any more -- so there is
        nothing left to exempt here: an obviously wrong oid/sha256 for
        *any* path, including one claiming to describe
        docs/release_data/provenance/{code,assets,submodules}.json
        itself, is now flagged with no exception whatsoever."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_dir = root / "docs" / "release_data" / "provenance"
            root_dir.mkdir(parents=True)
            (root_dir / "code.json").write_text("[]\n")
            _git("init", "-q", cwd=root)
            _git("config", "user.email", "t@example.com", cwd=root)
            _git("config", "user.name", "Tester", cwd=root)
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = [_base_entry(
                path="docs/release_data/provenance/code.json", oid="0" * 40, sha256="0" * 64,
            )]
            reasons = prov.check_blob_identity(entries, root, sha)
            self.assertTrue(reasons)
            self.assertTrue(any("does not match" in r for r in reasons), reasons)

    def test_assets_and_submodules_manifest_tampering_is_detected(self):
        """The literal issue #9 D2 requirement: assets.json and
        submodules.json (unlike code.json -- see above) must be live-
        bound to their immutable HEAD oid/sha256 with no exemption at
        all; a committed change to either file's content must invalidate
        its own provenance record (which lives inside code.json, a
        *different* tracked file -- never itself) exactly like any other
        ordinary tracked blob, and a correct, freshly-derived record for
        either must still pass cleanly."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provenance_dir = root / "docs" / "release_data" / "provenance"
            provenance_dir.mkdir(parents=True)
            (provenance_dir / "assets.json").write_text("[]\n")
            (provenance_dir / "submodules.json").write_text("[]\n")
            _git("init", "-q", cwd=root)
            _git("config", "user.email", "t@example.com", cwd=root)
            _git("config", "user.name", "Tester", cwd=root)
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")

            for path in (
                "docs/release_data/provenance/assets.json",
                "docs/release_data/provenance/submodules.json",
            ):
                oid, sha256_value = self._real_identity(root, sha, path)
                good_entries = [_base_entry(path=path, oid=oid, sha256=sha256_value)]
                self.assertEqual(prov.check_blob_identity(good_entries, root, sha), [])

                tampered_entries = [_base_entry(path=path, oid="0" * 40, sha256="0" * 64)]
                reasons = prov.check_blob_identity(tampered_entries, root, sha)
                self.assertTrue(reasons, f"{path} tampering must be detected, never exempted")
                self.assertTrue(
                    any(path in r and "does not match" in r for r in reasons), reasons
                )

    def test_changed_same_path_blob_invalidates_its_own_record(self):
        """A committed content change at the exact same tracked path
        (never a rename/new path) must invalidate its old provenance
        record -- the direct, minimal reproduction of the literal issue
        #9 mandatory correction #3 requirement, kept here alongside the
        D2 assets/submodules/code-specific probes above for one
        complete, self-contained tamper-probe suite."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha1 = self._init_repo_with_file(root, b"original content")
            oid1, sha256_1 = self._real_identity(root, sha1, "main.c")
            stale_entries = [_base_entry(path="main.c", oid=oid1, sha256=sha256_1)]
            self.assertEqual(prov.check_blob_identity(stale_entries, root, sha1), [])

            (root / "main.c").write_bytes(b"tampered content, same path")
            _git("commit", "-q", "-am", "tamper", cwd=root)
            sha2 = gs.resolve_sha(root, "HEAD")

            reasons = prov.check_blob_identity(stale_entries, root, sha2)
            self.assertTrue(any("main.c" in r and "does not match" in r for r in reasons), reasons)

    def test_real_repo_blob_identity_matches(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        self.assertEqual(prov.check_blob_identity(entries, ROOT), [])


class RepositoryStateTests(unittest.TestCase):
    """The current, real, committed provenance manifests must evaluate to
    an honest, exact BLOCKED status -- never a false 'mechanically
    eligible' (and this module must never emit the bare status token
    "approved" at all -- see EvaluateTests.
    test_fully_resolved_entry_is_mechanically_eligible)."""

    @staticmethod
    def _combined_required_paths():
        """issue #9 guardian-correction remediation (D2): the real,
        production required-coverage set is the included allowlist plus
        only the *gitlink*-kind export exclusions (today, just mgfembp)
        -- never a `KIND_SELF_REFERENTIAL_EVIDENCE` exclusion (today,
        docs/release_data/provenance/code.json), which deliberately
        never receives its own provenance-manifest entry at all (see
        `scripts/release_rehearsal/manifest.py`'s `check_provenance`,
        which computes this exact same filtered set via
        `tc.load_exclusion_paths(..., kinds=tc.
        PROVENANCE_REQUIRED_EXCLUSION_KINDS)`)."""
        allowlist = json.loads(
            (ROOT / "docs" / "release_data" / "source_allowlist.json").read_text(encoding="utf-8")
        )["paths"]
        exclusions = json.loads(
            (ROOT / "docs" / "release_data" / "export_exclusions.json").read_text(encoding="utf-8")
        )["exclusions"]
        gitlink_exclusion_paths = {entry["path"] for entry in exclusions if entry["kind"] == "gitlink"}
        return sorted(set(allowlist) | gitlink_exclusion_paths)

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
        self.assertIsNone(mgfembp[0].get("sha256"))

    def test_full_allowlist_and_exclusions_coverage(self):
        """issue #9 mandatory correction #2/#3: coverage now spans the
        *combined* included allowlist + excluded export-exclusions path
        set -- mgfembp's own record must be neither a gap nor a ghost."""
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        gaps = prov.coverage_gaps(entries, self._combined_required_paths())
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

    def test_real_repo_provenance_is_a_clean_bijection_over_the_combined_set(self):
        """The real, checked-in provenance manifests must fully, cleanly,
        unambiguously cover the real, checked-in exact allowlist +
        export-exclusions set -- no gap, no ghost, no duplicate/ambiguous
        entry, and the exact *set* of provenance paths must equal that
        combined set one-for-one -- not merely 46 category roots
        "covering" thousands of files by prefix."""
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        required_paths = self._combined_required_paths()
        self.assertEqual(prov.evaluate_coverage(entries, required_paths), [])
        entry_paths = [entry["path"] for entry in entries]
        self.assertEqual(len(entry_paths), len(set(entry_paths)), "no duplicate provenance paths")
        self.assertEqual(sorted(entry_paths), required_paths, "exact one-record-per-member bijection")

    def test_real_provenance_has_one_record_per_member_not_one_per_category(self):
        """issue #9 exact-provenance remediation's headline fact: there
        are as many provenance records as there are exact allowlisted +
        excluded members (thousands), never merely a handful of category
        roots."""
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        self.assertEqual(len(entries), len(self._combined_required_paths()))
        self.assertGreater(len(entries), 9000)

    def test_every_code_and_asset_entry_has_well_formed_oid_and_sha256(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        for entry in entries:
            if entry["category"] == "submodule":
                self.assertIsNone(entry.get("sha256"))
                continue
            self.assertRegex(entry["oid"], r"^[0-9a-f]{40}$", entry["path"])
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$", entry["path"])

    def test_real_gitlink_pin_matches_the_actual_tree(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        self.assertEqual(prov.check_gitlink_pins(entries, ROOT), [])

    def test_code_json_itself_has_no_provenance_entry(self):
        """issue #9 guardian-correction remediation (D2): the real,
        committed docs/release_data/provenance/code.json must never
        contain its own self-record any more -- it is an explicit export
        exclusion (docs/release_data/export_exclusions.json), not an
        included allowlist member, and never requires (or receives) its
        own oid/sha256-bound provenance entry."""
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        self_paths = [
            entry["path"] for entry in entries
            if entry["path"] == "docs/release_data/provenance/code.json"
        ]
        self.assertEqual(self_paths, [])

    def test_assets_and_submodules_json_still_have_exact_provenance_entries(self):
        """The other half of the D2 fix: assets.json and submodules.json
        remain fully *included* allowlist members with their own real,
        live-bound oid/sha256 provenance entries (recorded inside
        code.json) -- only code.json itself was ever exempted/excluded."""
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        by_path = {entry["path"]: entry for entry in entries}
        for path in (
            "docs/release_data/provenance/assets.json",
            "docs/release_data/provenance/submodules.json",
        ):
            self.assertIn(path, by_path)
            self.assertEqual(by_path[path]["category"], "code")
            self.assertRegex(by_path[path]["oid"], r"^[0-9a-f]{40}$")
            self.assertRegex(by_path[path]["sha256"], r"^[0-9a-f]{64}$")

    def test_code_json_is_an_explicit_self_referential_evidence_exclusion(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        allowlist = json.loads(
            (ROOT / "docs" / "release_data" / "source_allowlist.json").read_text(encoding="utf-8")
        )["paths"]
        exclusions = json.loads(
            (ROOT / "docs" / "release_data" / "export_exclusions.json").read_text(encoding="utf-8")
        )["exclusions"]
        self.assertNotIn("docs/release_data/provenance/code.json", allowlist)
        matches = [e for e in exclusions if e["path"] == "docs/release_data/provenance/code.json"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["kind"], "self_referential_evidence")

    def test_real_blob_identity_matches_the_actual_tree(self):
        entries = prov.load_all(ROOT / "docs" / "release_data" / "provenance")
        self.assertEqual(prov.check_blob_identity(entries, ROOT), [])


if __name__ == "__main__":
    unittest.main()
