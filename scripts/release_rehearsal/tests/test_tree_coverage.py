"""Tests for scripts/release_rehearsal/tree_coverage.py (issue #9
mandatory correction #2: exact immutable HEAD tree coverage with
explicit export exclusions)."""

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
from scripts.release_rehearsal import tree_coverage as tc

GITLINK_SHA = "c87e74dcd6c8878b809e013cd8ff0c52baa75332"
OTHER_SHA = "0" * 40


def _git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _init_repo_with_gitlink(root: Path, gitlink_sha: str = GITLINK_SHA, gitlink_path: str = "mgfembp") -> str:
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "Tester", cwd=root)
    (root / "src").mkdir()
    (root / "src" / "main.c").write_text("int x;")
    (root / "docs").mkdir()
    (root / "docs" / "readme.md").write_text("hi")
    _git("add", "-A", cwd=root)
    _git("update-index", "--add", "--cacheinfo", f"160000,{gitlink_sha},{gitlink_path}", cwd=root)
    _git("commit", "-q", "-m", "init", cwd=root)
    return gs.resolve_sha(root, "HEAD")


def _exclusion(path=GITLINK_SHA and "mgfembp", kind="gitlink", mode="160000", oid=GITLINK_SHA, reason="because"):
    return tc.ExclusionEntry(path=path, kind=kind, mode=mode, oid=oid, reason=reason)


def _write_exclusions(dir_path: Path, entries) -> Path:
    path = dir_path / "export_exclusions.json"
    path.write_text(json.dumps({"exclusions": [
        {"path": e.path, "kind": e.kind, "mode": e.mode, "oid": e.oid, "reason": e.reason} for e in entries
    ]}), encoding="utf-8")
    return path


class LoadExclusionsTests(unittest.TestCase):
    def test_valid_document_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion()])
            entries = tc.load_exclusions(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].path, "mgfembp")

    def test_missing_key_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export_exclusions.json"
            path.write_text(json.dumps({"exclusions": [{"path": "mgfembp", "kind": "gitlink"}]}), encoding="utf-8")
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_invalid_kind_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion(kind="directory")])
            with self.assertRaises(tc.TreeCoverageError) as ctx:
                tc.load_exclusions(path)
            self.assertIn("kind", str(ctx.exception))

    def test_gitlink_kind_requires_gitlink_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion(mode="100644")])
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_malformed_oid_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion(oid="abc")])
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_uppercase_oid_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion(oid="A" * 40)])
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_duplicate_path_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion(), _exclusion()])
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_empty_exclusions_array_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export_exclusions.json"
            path.write_text(json.dumps({"exclusions": []}), encoding="utf-8")
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_non_json_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export_exclusions.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)


class GenerateExclusionsDocumentTests(unittest.TestCase):
    def test_generates_one_entry_per_gitlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            document = tc.generate_exclusions_document(root, sha)
            self.assertEqual(len(document["exclusions"]), 1)
            self.assertEqual(document["exclusions"][0]["path"], "mgfembp")
            self.assertEqual(document["exclusions"][0]["oid"], GITLINK_SHA)
            self.assertEqual(document["exclusions"][0]["mode"], "160000")

    def test_unknown_gitlink_path_has_no_seed_reason_and_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root, gitlink_path="some-new-submodule")
            with self.assertRaises(tc.TreeCoverageError) as ctx:
                tc.generate_exclusions_document(root, sha)
            self.assertIn("no curated reason", str(ctx.exception))

    def test_no_gitlinks_at_all_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git("init", "-q", cwd=root)
            _git("config", "user.email", "t@example.com", cwd=root)
            _git("config", "user.name", "Tester", cwd=root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            with self.assertRaises(tc.TreeCoverageError):
                tc.generate_exclusions_document(root, sha)


class CheckPartitionTests(unittest.TestCase):
    """Core coverage: included allowlist (+) excluded gitlinks == the
    complete tree, disjointly."""

    def test_clean_partition_has_no_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [_exclusion()], sha)
            self.assertTrue(result.is_clean())
            self.assertEqual(result.reasons(), [])

    def test_new_tracked_file_absent_from_both_sets_fails(self):
        """The literal issue #9 requirement: a new tracked path in
        neither set must fail coverage, never silently vanish."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(root, ["src/main.c"], [_exclusion()], sha)
            self.assertIn("docs/readme.md", result.missing_included)
            self.assertFalse(result.is_clean())

    def test_new_gitlink_absent_from_exclusions_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [], sha)
            self.assertIn("mgfembp", result.missing_excluded)
            self.assertFalse(result.is_clean())

    def test_stale_included_entry_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(
                root, ["src/main.c", "docs/readme.md", "long-gone.txt"], [_exclusion()], sha,
            )
            self.assertEqual(result.stale_included, ["long-gone.txt"])

    def test_stale_excluded_entry_detected(self):
        """An export-exclusion entry whose path is no longer a tracked
        gitlink at all (removed, or never real) is reported stale --
        while the real gitlink, still separately and correctly covered
        by its own entry, is not itself affected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            ghost = tc.ExclusionEntry(path="nonexistent-submodule", kind="gitlink", mode="160000", oid=OTHER_SHA, reason="x")
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [_exclusion(), ghost], sha)
            self.assertIn("nonexistent-submodule", result.stale_excluded)
            self.assertEqual(result.missing_excluded, [])  # mgfembp is still correctly covered by _exclusion()
            self.assertFalse(result.is_clean())

    def test_stale_oid_on_excluded_entry_detected(self):
        """A gitlink whose pin changed (superproject bumped the
        submodule commit) but whose export-exclusion record was not
        regenerated must fail as a stale mode/OID -- never silently
        "still excluded, so still fine"."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            stale = _exclusion(oid=OTHER_SHA)
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [stale], sha)
            self.assertEqual(result.mismatched_excluded, ["mgfembp"])

    def test_overlap_between_included_and_excluded_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(
                root, ["src/main.c", "docs/readme.md", "mgfembp"], [_exclusion()], sha,
            )
            self.assertIn("mgfembp", result.overlap)

    def test_silent_extension_filtering_never_hides_a_new_tracked_file(self):
        """A new tracked file must fail coverage regardless of its
        extension/name -- there is no filename/extension-based silent
        skip anywhere in this partition check (unlike, say, a naive
        checker that only looks at '*.c'/'*.md' files)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            (root / "new.unexpected.ext12345").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "add odd file", cwd=root)
            new_sha = gs.resolve_sha(root, "HEAD")
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [_exclusion()], new_sha)
            self.assertIn("new.unexpected.ext12345", result.missing_included)

    def test_prefix_exclusion_of_a_real_directory_is_rejected(self):
        """Do not broad-prefix exclude directories: an export-exclusion
        entry may never be a directory-prefix ancestor of another
        tracked path."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            broad = tc.ExclusionEntry(path="src", kind="gitlink", mode="160000", oid=OTHER_SHA, reason="x")
            result = tc.check_partition(root, ["docs/readme.md"], [_exclusion(), broad], sha)
            self.assertIn("src", result.prefix_exclusions)

    def test_reasons_are_sorted_and_human_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(root, ["src/main.c"], [], sha)
            reasons = result.reasons()
            self.assertEqual(reasons, sorted(reasons))
            self.assertTrue(any("docs/readme.md" in r for r in reasons))
            self.assertTrue(any("mgfembp" in r for r in reasons))


class CheckEndToEndTests(unittest.TestCase):
    def test_check_reads_files_and_reports_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            allowlist_path = root / "allow.json"
            allowlist_path.write_text(json.dumps({"paths": ["src/main.c", "docs/readme.md"]}), encoding="utf-8")
            exclusions_path = _write_exclusions(root, [_exclusion()])
            self.assertEqual(tc.check(root, allowlist_path, exclusions_path, sha), [])

    def test_check_reports_malformed_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowlist_path = root / "allow.json"
            allowlist_path.write_text("{not json", encoding="utf-8")
            exclusions_path = _write_exclusions(root, [_exclusion()])
            reasons = tc.check(root, allowlist_path, exclusions_path, "HEAD")
            self.assertTrue(reasons)

    def test_check_reports_malformed_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowlist_path = root / "allow.json"
            allowlist_path.write_text(json.dumps({"paths": ["a.txt"]}), encoding="utf-8")
            exclusions_path = root / "export_exclusions.json"
            exclusions_path.write_text("{not json", encoding="utf-8")
            reasons = tc.check(root, allowlist_path, exclusions_path, "HEAD")
            self.assertTrue(reasons)


class ArchiveMembershipExactTests(unittest.TestCase):
    def test_exact_match_has_no_findings(self):
        missing, extra = tc.check_archive_membership_exact(["a.txt", "b.txt"], ["a.txt", "b.txt"])
        self.assertEqual(missing, [])
        self.assertEqual(extra, [])

    def test_missing_member_detected(self):
        missing, extra = tc.check_archive_membership_exact(["a.txt"], ["a.txt", "b.txt"])
        self.assertEqual(missing, ["b.txt"])
        self.assertEqual(extra, [])

    def test_extra_member_detected(self):
        """An archive containing something beyond the included set (e.g.
        a gitlink that slipped through) must be reported, never silently
        accepted as "a superset is fine"."""
        missing, extra = tc.check_archive_membership_exact(["a.txt", "mgfembp"], ["a.txt"])
        self.assertEqual(missing, [])
        self.assertEqual(extra, ["mgfembp"])


class CheckNonGitTreeTests(unittest.TestCase):
    """The closed-world, no-.git-at-all analogue -- a genuine extracted
    candidate tree (e.g. a real 'git archive HEAD | tar -x' extraction)."""

    def test_clean_extraction_has_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").mkdir()  # git archive materializes a gitlink as an empty dir
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertTrue(result.is_clean())

    def test_missing_included_file_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mgfembp").mkdir()
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("src/main.c", result.missing)

    def test_missing_excluded_directory_detected(self):
        """The precise 'missing/unrepresented gitlink' blocker: if even
        the empty directory mountpoint is absent, that is reported."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("mgfembp", result.missing)

    def test_extra_unlisted_file_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").mkdir()
            (root / "new_unreviewed.txt").write_text("new")
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("new_unreviewed.txt", result.extra)

    def test_excluded_path_materialized_as_a_file_is_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").write_text("not a directory!")
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("mgfembp", result.unsafe)

    def test_included_path_materialized_as_a_symlink_is_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.txt").write_text("real")
            (root / "src.c").symlink_to("real.txt")
            (root / "mgfembp").mkdir()
            result = tc.check_non_git_tree(root, ["src.c"], [_exclusion()])
            self.assertIn("src.c", result.unsafe)

    def test_excluded_path_materialized_as_a_symlink_is_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "real_dir").mkdir()
            (root / "mgfembp").symlink_to("real_dir")
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("mgfembp", result.unsafe)

    def test_never_invokes_git(self):
        """Mirrors allowlist.py's own non-git regression: nesting the
        fixture inside this real repository must never leak an outer
        git invocation (there simply is none in this function at all)."""
        import shutil
        nested = ROOT / "scripts" / "release_rehearsal" / "tests" / ".issue9-tree-coverage-fixture-tmp"
        self.addCleanup(shutil.rmtree, nested, True)
        nested.mkdir(exist_ok=True)
        (nested / "only.txt").write_text("x")
        (nested / "mgfembp").mkdir()
        result = tc.check_non_git_tree(nested, ["only.txt"], [_exclusion()])
        self.assertTrue(result.is_clean())


class CombinedRequiredPathsTests(unittest.TestCase):
    def test_union_of_both_sets(self):
        combined = tc.combined_required_paths(["a.txt", "b.txt"], ["mgfembp"])
        self.assertEqual(combined, ["a.txt", "b.txt", "mgfembp"])

    def test_no_duplicates_on_pathological_overlap_input(self):
        combined = tc.combined_required_paths(["a.txt"], ["a.txt"])
        self.assertEqual(combined, ["a.txt"])


class RepositoryStateTests(unittest.TestCase):
    """The real, checked-in source_allowlist.json and export_exclusions.json
    must together be an exact, disjoint partition of this repository's own
    HEAD tree."""

    def test_real_repo_is_an_exact_disjoint_partition(self):
        allowlist_paths = al.load_allowlist_paths(ROOT / "docs" / "release_data" / "source_allowlist.json")
        exclusion_entries = tc.load_exclusions(ROOT / "docs" / "release_data" / "export_exclusions.json")
        result = tc.check_partition(ROOT, allowlist_paths, exclusion_entries, "HEAD")
        self.assertEqual(result.reasons(), [])
        self.assertTrue(result.is_clean())

    def test_real_repo_exclusions_contains_exactly_mgfembp(self):
        exclusion_entries = tc.load_exclusions(ROOT / "docs" / "release_data" / "export_exclusions.json")
        self.assertEqual([e.path for e in exclusion_entries], ["mgfembp"])
        self.assertEqual(exclusion_entries[0].oid, GITLINK_SHA)
        self.assertEqual(exclusion_entries[0].kind, "gitlink")

    def test_real_exclusions_check_via_cli_helper(self):
        reasons = tc.check(
            ROOT,
            ROOT / "docs" / "release_data" / "source_allowlist.json",
            ROOT / "docs" / "release_data" / "export_exclusions.json",
            "HEAD",
        )
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
