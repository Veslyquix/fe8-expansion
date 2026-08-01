"""Tests for scripts/release_rehearsal/allowlist.py (issue #9)."""

import json
import shutil
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
    def test_generates_every_tracked_file(self):
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

    def test_gitlink_excluded_from_generated_entries(self):
        """schema_version 3 / issue #9 mandatory correction #2: a
        gitlink (submodule mountpoint) is never included in the
        generated allowlist -- it is a separate, explicit export
        exclusion (see scripts/release_rehearsal/tree_coverage.py)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "regular.txt").write_text("hello\n")
            _git("add", "regular.txt", cwd=root)
            _git(
                "update-index", "--add", "--cacheinfo",
                "160000,c87e74dcd6c8878b809e013cd8ff0c52baa75332,a-submodule",
                cwd=root,
            )
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = al.generate_entries(root, sha)
            self.assertEqual(entries, ["regular.txt"])
            self.assertNotIn("a-submodule", entries)

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
            self.assertEqual(document["modes"], {"f.txt": "100644"})

    def test_excluded_blob_paths_removed_from_generated_entries_and_modes(self):
        """issue #9 guardian-correction remediation (D2): an ordinary
        tracked blob explicitly declared its own non-gitlink export
        exclusion (e.g. the self-referential-evidence provenance
        manifest) is removed from the generated allowlist exactly like a
        gitlink already is."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "included.txt").write_text("x")
            (root / "excluded.txt").write_text("y")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            entries = al.generate_entries(root, sha, excluded_blob_paths=["excluded.txt"])
            self.assertEqual(entries, ["included.txt"])
            modes = al.generate_modes(root, sha, excluded_blob_paths=["excluded.txt"])
            self.assertEqual(modes, {"included.txt": "100644"})


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


class CheckAllowlistCompletenessGitlinkExclusionTests(unittest.TestCase):
    """schema_version 3 / issue #9 mandatory correction #2: a tracked
    gitlink is never expected to have its own allowlist entry -- it must
    never be reported as "missing" here, and its presence in the
    allowlist would itself be a "stale" (unexpected) entry."""

    def test_gitlink_is_never_reported_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "regular.txt").write_text("hello\n")
            _git("add", "regular.txt", cwd=root)
            _git(
                "update-index", "--add", "--cacheinfo",
                "160000,c87e74dcd6c8878b809e013cd8ff0c52baa75332,a-submodule",
                cwd=root,
            )
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            missing, stale = al.check_allowlist_completeness(root, ["regular.txt"], sha)
            self.assertEqual(missing, [])
            self.assertEqual(stale, [])

    def test_gitlink_erroneously_allowlisted_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "regular.txt").write_text("hello\n")
            _git("add", "regular.txt", cwd=root)
            _git(
                "update-index", "--add", "--cacheinfo",
                "160000,c87e74dcd6c8878b809e013cd8ff0c52baa75332,a-submodule",
                cwd=root,
            )
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            missing, stale = al.check_allowlist_completeness(root, ["regular.txt", "a-submodule"], sha)
            self.assertEqual(missing, [])
            self.assertEqual(stale, ["a-submodule"])


class ModeBindingTests(unittest.TestCase):
    """issue #9 guardian-correction remediation (D4): an included path's
    exact Git mode is bound alongside its mere path string, and cross-
    checked against the live tree -- a committed executable-bit/mode
    change must make this canonical data stale/fail until regenerated."""

    def _commit(self, root: Path, mode_str: str) -> str:
        _init_repo(root)
        (root / "f.txt").write_text("x")
        _git("add", "-A", cwd=root)
        if mode_str == "100755":
            (root / "f.txt").chmod(0o755)
            _git("update-index", "--chmod=+x", "f.txt", cwd=root)
        _git("commit", "-q", "-m", "init", cwd=root)
        return gs.resolve_sha(root, "HEAD")

    def test_load_allowlist_modes_returns_none_when_key_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.json"
            path.write_text(json.dumps({"paths": ["a.txt"]}), encoding="utf-8")
            self.assertIsNone(al.load_allowlist_modes(path))

    def test_load_allowlist_modes_rejects_unsupported_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.json"
            path.write_text(
                json.dumps({"paths": ["a.txt"], "modes": {"a.txt": "040000"}}), encoding="utf-8"
            )
            with self.assertRaises(al.AllowlistError):
                al.load_allowlist_modes(path)

    def test_load_allowlist_modes_accepts_every_valid_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.json"
            path.write_text(json.dumps({
                "paths": ["a.txt", "b.sh", "c.lnk"],
                "modes": {"a.txt": "100644", "b.sh": "100755", "c.lnk": "120000"},
            }), encoding="utf-8")
            modes = al.load_allowlist_modes(path)
            self.assertEqual(modes, {"a.txt": "100644", "b.sh": "100755", "c.lnk": "120000"})

    def test_mode_bijection_detects_missing_and_extra(self):
        missing, extra = al.check_mode_bijection(["a.txt", "b.txt"], {"a.txt": "100644", "c.txt": "100644"})
        self.assertEqual(missing, ["b.txt"])
        self.assertEqual(extra, ["c.txt"])

    def test_mode_identity_matches_for_a_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._commit(root, "100644")
            reasons = al.check_mode_identity(root, {"f.txt": "100644"}, sha)
            self.assertEqual(reasons, [])

    def test_committed_executable_bit_change_makes_mode_data_stale(self):
        """The literal issue #9 D4 requirement: a committed chmod
        (100644 -> 100755, or vice versa) must be detected as stale mode
        data, not silently ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha1 = self._commit(root, "100644")
            declared_modes = {"f.txt": "100644"}
            self.assertEqual(al.check_mode_identity(root, declared_modes, sha1), [])

            (root / "f.txt").chmod(0o755)
            _git("update-index", "--chmod=+x", "f.txt", cwd=root)
            _git("commit", "-q", "-am", "chmod +x", cwd=root)
            sha2 = gs.resolve_sha(root, "HEAD")

            reasons = al.check_mode_identity(root, declared_modes, sha2)
            self.assertTrue(any("f.txt" in r and "100755" in r for r in reasons), reasons)

    def test_mode_identity_reports_missing_tracked_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = self._commit(root, "100644")
            reasons = al.check_mode_identity(root, {"does-not-exist.txt": "100644"}, sha)
            self.assertTrue(reasons)

    def test_check_end_to_end_detects_stale_mode(self):
        """Wired end-to-end through al.check(): a committed mode change
        must surface as an actionable finding, exactly like a content or
        path change already does."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha1 = self._commit(root, "100644")
            allowlist_path = root / "allow.json"
            allowlist_path.write_text(json.dumps({
                "paths": ["f.txt"], "modes": {"f.txt": "100644"},
            }), encoding="utf-8")
            self.assertEqual(al.check(root, allowlist_path, sha1), [])

            (root / "f.txt").chmod(0o755)
            _git("update-index", "--chmod=+x", "f.txt", cwd=root)
            _git("commit", "-q", "-am", "chmod +x", cwd=root)
            sha2 = gs.resolve_sha(root, "HEAD")

            errors = al.check(root, allowlist_path, sha2)
            self.assertTrue(any("f.txt" in e for e in errors), errors)


class ClosedWorldSymlinkNeverSkippedTests(unittest.TestCase):
    """issue #9 guardian-correction remediation (D5): `_present_paths`
    (formerly `_present_regular_files`, which `continue`d straight past
    any symlink) must never skip a filesystem entry by kind -- a stray,
    unlisted symlink at any path is now reported as "missing from
    allowlist", never silently invisible."""

    def test_stray_symlink_is_reported_missing_from_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            (root / "real.txt").write_text("real")
            (root / "stray-link.txt").symlink_to("real.txt")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["a.txt", "real.txt"])
            self.assertIn("stray-link.txt", missing)

    def test_present_paths_includes_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.txt").write_text("real")
            (root / "link.txt").symlink_to("real.txt")
            present = al._present_paths(root)
            self.assertIn("link.txt", present)
            self.assertIn("real.txt", present)


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


class CheckAllowlistCompletenessNonGitTests(unittest.TestCase):
    """issue #9 verifier remediation: the non-git analogue of
    `check_allowlist_completeness`, used only when `repo_root` has no
    `.git` at all (a genuine extracted archive/non-git candidate tree).
    Regression coverage for the fresh-verifier-reproduced defect: this
    must never invoke git plumbing, and must correctly report both a
    present-but-unlisted file ("missing") and an allowlisted member with
    no on-disk representation at all ("unrepresented"), including a
    gitlink-style directory-only entry like "mgfembp"."""

    def test_exact_match_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["a.txt"])
            self.assertEqual(missing, [])
            self.assertEqual(unrepresented, [])

    def test_present_unlisted_file_is_reported_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            (root / "b.txt").write_text("b")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["a.txt"])
            self.assertEqual(missing, ["b.txt"])
            self.assertEqual(unrepresented, [])

    def test_absent_allowlisted_file_is_reported_unrepresented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["a.txt", "gone.txt"])
            self.assertEqual(missing, [])
            self.assertEqual(unrepresented, ["gone.txt"])

    def test_gitlink_style_directory_entry_is_represented_not_unrepresented(self):
        """A real extracted GitHub source archive materializes a
        submodule mountpoint (e.g. "mgfembp") as an empty directory, not
        as a missing path -- this must count as represented, exactly
        like a real git tree's gitlink entry never requires blob
        content."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mgfembp").mkdir()
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["mgfembp"])
            self.assertEqual(unrepresented, [])

    def test_truly_absent_gitlink_directory_is_unrepresented(self):
        """The precise "missing/unrepresented gitlink/mgfembp" blocker
        issue #9 requires: if the extraction omits even the empty
        directory mountpoint, that must be reported, not silently
        ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["a.txt", "mgfembp"])
            self.assertEqual(unrepresented, ["mgfembp"])

    def test_symlink_at_allowlisted_path_never_counts_as_represented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.txt").write_text("real")
            (root / "linked.txt").symlink_to("real.txt")
            missing, unrepresented = al.check_allowlist_completeness_non_git(root, ["linked.txt"])
            self.assertEqual(unrepresented, ["linked.txt"])

    def test_never_invokes_git_even_when_nested_inside_a_real_repo(self):
        """issue #9 verifier remediation: a non-git candidate tree's
        completeness check must never invoke git plumbing against it --
        not even accidentally via git's own upward-directory-discovery
        finding an unrelated *enclosing* git repository. Proven by
        nesting the synthetic fixture directly inside this real,
        git-tracked worktree (ROOT): if any git command leaked through
        with this directory as its cwd, it would silently report ROOT's
        own real tracked-file set (thousands of paths) instead of the
        tiny fixture's, and these assertions would fail."""
        nested = ROOT / "scripts" / "release_rehearsal" / "tests" / ".issue9-non-git-fixture-tmp"
        self.addCleanup(shutil.rmtree, nested, True)
        nested.mkdir(exist_ok=True)
        (nested / "only.txt").write_text("x")
        missing, unrepresented = al.check_allowlist_completeness_non_git(nested, ["only.txt"])
        self.assertEqual(missing, [])
        self.assertEqual(unrepresented, [])


class CheckFunctionNonGitTests(unittest.TestCase):
    """issue #9 verifier remediation: `check()` must dispatch to the
    non-git completeness check (never `git_source.list_tree`/any git
    invocation) when `repo_root` has no `.git` at all -- the literal,
    reproduced defect: `check()` previously called `gs.list_tree`
    unconditionally and tracebacked for both a non-git `repo_root` and a
    well-formed-but-nonexistent `target_sha` in a real git repo."""

    @staticmethod
    def _write_allowlist(path: Path, paths) -> None:
        path.write_text(json.dumps({"paths": list(paths)}), encoding="utf-8")

    def test_clean_non_git_tree_has_no_errors(self):
        """The allowlist document lives *outside* the scanned tree here
        (as e.g. a CI-fetched sidecar file would) purely to isolate this
        assertion from the self-referential-entry behavior covered by
        `test_allowlist_document_itself_inside_the_tree_must_self_list`
        below -- the real, checked-in
        docs/release_data/source_allowlist.json *is* inside the tree it
        describes, and lists its own path for exactly that reason."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "a.txt").write_text("a")
            allowlist_path = Path(tmp) / "allow.json"
            self._write_allowlist(allowlist_path, ["a.txt"])
            self.assertEqual(al.check(root, allowlist_path), [])

    def test_non_git_tree_reports_missing_and_unrepresented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "a.txt").write_text("a")
            (root / "extra.txt").write_text("extra")
            allowlist_path = Path(tmp) / "allow.json"
            self._write_allowlist(allowlist_path, ["a.txt", "gone.txt"])
            errors = al.check(root, allowlist_path)
            self.assertTrue(any("extra.txt" in e for e in errors))
            self.assertTrue(any("gone.txt" in e for e in errors))

    def test_allowlist_document_itself_inside_the_tree_must_self_list(self):
        """Mirrors this repository's own real
        docs/release_data/source_allowlist.json, which lives *inside*
        the tree it describes and lists its own path -- an allowlist
        document that forgets to self-list is exactly as much an
        actionable "missing from allowlist" finding as any other
        unlisted file, never a silently-tolerated special case."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a")
            allowlist_path = root / "allow.json"
            self._write_allowlist(allowlist_path, ["a.txt", "allow.json"])
            self.assertEqual(al.check(root, allowlist_path), [])

    def test_nonexistent_valid_form_sha_in_real_git_repo_raises_git_source_error(self):
        """issue #9 verifier remediation: a well-formed (40-lowercase-
        hex) but nonexistent target_sha in an *actual* git repository
        must raise `git_source.GitSourceError` (propagated, never
        swallowed) -- the CLI's single top-level exception boundary is
        what turns this into a controlled exit 2; `check()` itself must
        not paper over it as a soft business reason."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            allowlist_path = root / "allow.json"
            self._write_allowlist(allowlist_path, ["a.txt"])
            nonexistent_sha = "0123456789abcdef0123456789abcdef01234567"
            with self.assertRaises(gs.GitSourceError):
                al.check(root, allowlist_path, nonexistent_sha)


class RepositoryStateTests(unittest.TestCase):
    """The real, checked-in docs/release_data/source_allowlist.json must
    be exactly consistent with this repository's own tracked-file set."""

    @staticmethod
    def _real_excluded_blob_paths():
        exclusions_path = ROOT / "docs" / "release_data" / "export_exclusions.json"
        return al._load_non_gitlink_exclusion_paths(exclusions_path)

    def test_real_allowlist_is_exact_and_complete_at_head(self):
        allowlist_path = ROOT / "docs" / "release_data" / "source_allowlist.json"
        paths = al.load_allowlist_paths(allowlist_path)
        missing, stale = al.check_allowlist_completeness(
            ROOT, paths, "HEAD", self._real_excluded_blob_paths()
        )
        self.assertEqual(missing, [], "tracked file(s) missing an allowlist entry")
        self.assertEqual(stale, [], "stale allowlist entrie(s) for something no longer tracked")

    def test_real_allowlist_excludes_mgfembp_gitlink(self):
        """schema_version 3 / issue #9 mandatory correction #2: the
        `mgfembp` gitlink is never an allowlist ("included") entry any
        more -- it is instead its own explicit export-exclusion record
        in docs/release_data/export_exclusions.json. See
        scripts/release_rehearsal/tests/test_tree_coverage.py for the
        exact, disjoint-partition proof that ties both files together."""
        allowlist_path = ROOT / "docs" / "release_data" / "source_allowlist.json"
        paths = al.load_allowlist_paths(allowlist_path)
        self.assertNotIn("mgfembp", paths)

    def test_real_allowlist_excludes_self_referential_evidence_code_json(self):
        """issue #9 guardian-correction remediation (D2): the self-
        referential-evidence provenance manifest is likewise never an
        allowlist ("included") entry any more."""
        allowlist_path = ROOT / "docs" / "release_data" / "source_allowlist.json"
        paths = al.load_allowlist_paths(allowlist_path)
        self.assertNotIn("docs/release_data/provenance/code.json", paths)

    def test_real_allowlist_schema_version_is_4(self):
        import json
        allowlist_path = ROOT / "docs" / "release_data" / "source_allowlist.json"
        document = json.loads(allowlist_path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 4)

    def test_real_allowlist_modes_are_an_exact_bijection_and_match_head(self):
        """issue #9 guardian-correction remediation (D4): every real,
        committed allowlist path has its own recorded Git mode, bound
        exactly (no gap, no orphan), and cross-checked against the live
        tree."""
        allowlist_path = ROOT / "docs" / "release_data" / "source_allowlist.json"
        paths = al.load_allowlist_paths(allowlist_path)
        modes = al.load_allowlist_modes(allowlist_path)
        self.assertIsNotNone(modes)
        mode_missing, mode_extra = al.check_mode_bijection(paths, modes)
        self.assertEqual(mode_missing, [])
        self.assertEqual(mode_extra, [])
        self.assertEqual(al.check_mode_identity(ROOT, modes, "HEAD"), [])

    def test_real_check_end_to_end_is_clean(self):
        """The full, wired al.check() (allowlist bijection + exclusions +
        mode bijection/identity) against this repository's own real,
        committed data must report no findings at all."""
        allowlist_path = ROOT / "docs" / "release_data" / "source_allowlist.json"
        exclusions_path = ROOT / "docs" / "release_data" / "export_exclusions.json"
        self.assertEqual(al.check(ROOT, allowlist_path, "HEAD", exclusions_path), [])


if __name__ == "__main__":
    unittest.main()
