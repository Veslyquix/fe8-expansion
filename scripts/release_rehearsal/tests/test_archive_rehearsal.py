"""Tests for scripts/release_rehearsal/archive_rehearsal.py (issue #9)."""

import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import archive_rehearsal as ar
from scripts.release_rehearsal import git_source as gs
from scripts.release_rehearsal import source_guard as sg


def _git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _init_repo(root: Path) -> None:
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "Tester", cwd=root)


def _make_source_tree(root: Path):
    (root / "src").mkdir()
    (root / "src" / "main.c").write_text("int main(void) { return 0; }\n")
    (root / "docs").mkdir()
    (root / "docs" / "readme.md").write_text("hello\n")


def _make_git_source_tree_committed(root: Path, allowlist=("src/main.c", "docs/readme.md")):
    """A minimal committed git repo with the same layout as
    `_make_source_tree`, plus an exact-file allowlist matching it."""
    _init_repo(root)
    _make_source_tree(root)
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "initial", cwd=root)
    return set(allowlist)


class BuildDeterministicArchiveTests(unittest.TestCase):
    """Non-git trees (a genuine extracted archive/non-git candidate)
    still use the raw-filesystem fallback path -- these tests are
    unaffected by the issue #9 git-blob immutability rework. issue #9
    verifier remediation: every allowlist below is now the exact
    per-file shape (a bare directory name like "src" no longer expands
    to "every file underneath it" -- see `_filesystem_allowlisted_files`
    and `ExactFilesystemAllowlistTests` below)."""

    def test_two_builds_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _make_source_tree(root)
            allowlist = {"src/main.c", "docs/readme.md"}
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
            ar.build_deterministic_archive(root, {"src/main.c", "docs/readme.md"}, dest)
            with tarfile.open(dest, "r") as tar:
                for member in tar.getmembers():
                    self.assertEqual(member.mtime, 0)
                    self.assertEqual(member.uid, 0)
                    self.assertEqual(member.gid, 0)
                    self.assertEqual(member.uname, "")
                    self.assertEqual(member.gname, "")
                    self.assertTrue(member.isreg())

    def test_archive_output_mode_is_canonicalized_regardless_of_source_mode(self):
        """issue #9 guardian-correction remediation (D4): the archive's
        *written* tar mode is always the fixed `CANONICAL_FILE_MODE`
        (`0o644`), regardless of whether the source path's own live
        filesystem/Git mode is an ordinary `100644` file or an executable
        `100755` one -- a deliberate, documented determinism policy (see
        docs/release_process.md's "Archive member mode policy"), not an
        accidental preservation. Mode-binding (`source_allowlist.json`'s
        `"modes"` map, `check_mode_identity`) is a drift-detection/
        provenance-identity concern only; it never changes what the
        archive itself actually writes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "ordinary.txt").write_text("ordinary\n")
            (root / "ordinary.txt").chmod(0o644)
            (root / "executable.sh").write_text("#!/bin/sh\necho hi\n")
            (root / "executable.sh").chmod(0o755)
            dest = Path(tmp) / "out.tar"
            ar.build_deterministic_archive(root, {"ordinary.txt", "executable.sh"}, dest)
            with tarfile.open(dest, "r") as tar:
                members = {m.name: m for m in tar.getmembers()}
            self.assertEqual(members["ordinary.txt"].mode, ar.CANONICAL_FILE_MODE)
            self.assertEqual(members["executable.sh"].mode, ar.CANONICAL_FILE_MODE)
            self.assertEqual(members["ordinary.txt"].mode, members["executable.sh"].mode)

    def test_git_backed_archive_output_mode_is_canonicalized_for_a_committed_executable(self):
        """The git-blob-bound half of the same D4 requirement: a
        committed `100755` (executable) blob still archives with the
        fixed `CANONICAL_FILE_MODE`, never its live Git mode."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _init_repo(root)
            (root / "run.sh").write_text("#!/bin/sh\necho hi\n")
            (root / "run.sh").chmod(0o755)
            _git("add", "-A", cwd=root)
            _git("update-index", "--chmod=+x", "run.sh", cwd=root)
            _git("commit", "-q", "-m", "add executable", cwd=root)
            dest = Path(tmp) / "out.tar"
            ar.build_deterministic_archive(root, {"run.sh"}, dest)
            with tarfile.open(dest, "r") as tar:
                member = tar.getmembers()[0]
            self.assertEqual(member.mode, ar.CANONICAL_FILE_MODE)

    def test_member_order_is_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "z").mkdir()
            (root / "z" / "z.c").write_text("int z;")
            (root / "a").mkdir()
            (root / "a" / "a.c").write_text("int a;")
            dest = Path(tmp) / "out.tar"
            ar.build_deterministic_archive(root, {"z/z.c", "a/a.c"}, dest)
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
                ar.build_deterministic_archive(root, {"src/bad.gba"}, dest)

    def test_wired_membership_exact_check_refuses_on_extra_members(self):
        """issue #9 guardian-correction remediation (D5): the actual,
        wired `build_deterministic_archive` -- not merely
        `tree_coverage.check_archive_membership_exact` tested in
        isolation -- refuses to write anything at all when the
        membership-exact check it calls internally reports a problem.
        `missing_members`/`extra_members` can never actually disagree
        with the declared allowlist through *normal* input today (the
        git-tree entries are always pre-filtered to the allowlist set),
        so the "extra members" branch is exercised here by patching the
        real check function this module actually calls (defense-in-depth
        for a *future* filtering bug) -- proving the wiring itself, not
        re-implementing tree_coverage's own already-tested logic."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            allowlist = _make_git_source_tree_committed(root)
            dest = Path(tmp) / "out.tar"
            with mock.patch.object(
                ar.tc, "check_archive_membership_exact",
                return_value=(["forced-missing.c"], ["forced-extra.c"]),
            ):
                with self.assertRaises(ar.ArchiveRehearsalError) as ctx:
                    ar.build_deterministic_archive(root, allowlist, dest)
            self.assertIn("forced-missing.c", str(ctx.exception))
            self.assertIn("forced-extra.c", str(ctx.exception))
            self.assertFalse(dest.exists())


class ExactFilesystemAllowlistTests(unittest.TestCase):
    """issue #9 verifier remediation: `_filesystem_allowlisted_files` (the
    non-git archive-content fallback) now matches the allowlist exactly
    -- a bare directory-shaped entry no longer expands to every file
    nested underneath it."""

    def test_bare_directory_entry_no_longer_expands_to_its_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            files = ar._filesystem_allowlisted_files(root, {"src"})
            self.assertEqual(files, [])

    def test_known_file_included_unlisted_sibling_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "known.c").write_text("int known;")
            (root / "src" / "unlisted.c").write_text("int unlisted;")
            files = ar._filesystem_allowlisted_files(root, {"src/known.c"})
            relpaths = sorted(p.relative_to(root).as_posix() for p in files)
            self.assertEqual(relpaths, ["src/known.c"])

    def test_a_directory_that_shares_an_allowlisted_gitlink_style_name_contributes_nothing(self):
        """A directory on disk that happens to share its name with an
        allowlist entry (e.g. an uninitialized/initialized `mgfembp`
        submodule mountpoint) is a structural parent only -- it never
        implicitly authorizes whatever files might be sitting inside it,
        matching the git-backed path's own "gitlink contents are never
        enumerated" invariant (see `GitBackedArchiveTests.
        test_gitlink_member_never_archived_even_if_allowlisted`)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mgfembp").mkdir()
            (root / "mgfembp" / "some_submodule_file.py").write_text("x = 1\n")
            files = ar._filesystem_allowlisted_files(root, {"mgfembp"})
            self.assertEqual(files, [])

    def test_nested_unlisted_file_never_silently_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "known.c").write_text("int known;")
            (root / "src" / "known.c").chmod(0o644)
            (root / "src" / "deep").mkdir()
            (root / "src" / "deep" / "unlisted.c").write_text("int unlisted;")
            dest = Path(tmp) / "out.tar"
            ar.build_deterministic_archive(root, {"src/known.c"}, dest)
            with tarfile.open(dest, "r") as tar:
                names = sorted(m.name for m in tar.getmembers())
            self.assertEqual(names, ["src/known.c"])


class NonGitMissingMemberRefusalTests(unittest.TestCase):
    """issue #9 verifier remediation: a non-git candidate tree (a
    genuine extracted archive) must refuse to build an archive at all
    -- a controlled `ArchiveRehearsalError`, never a silent partial
    archive -- when a declared allowlist member has *no* on-disk
    representation whatsoever (neither a file nor a directory). This is
    distinct from, and does not change, the pre-existing "extra
    unlisted file is silently excluded" behavior proven by
    `ExactFilesystemAllowlistTests` above."""

    def test_missing_allowlisted_member_refused_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "present.c").write_text("int x;")
            dest = Path(tmp) / "out.tar"
            with self.assertRaises(ar.ArchiveRehearsalError) as ctx:
                ar.build_deterministic_archive(root, {"present.c", "missing.c"}, dest)
            self.assertIn("missing.c", str(ctx.exception))

    def test_missing_gitlink_style_directory_member_refused(self):
        """A gitlink-style entry (e.g. "mgfembp") absent even as an
        empty directory -- not merely lacking blob content, which is
        normal -- is exactly the "missing/unrepresented gitlink"
        blocker this module must report."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "present.c").write_text("int x;")
            dest = Path(tmp) / "out.tar"
            with self.assertRaises(ar.ArchiveRehearsalError) as ctx:
                ar.build_deterministic_archive(root, {"present.c", "mgfembp"}, dest)
            self.assertIn("mgfembp", str(ctx.exception))

    def test_present_gitlink_style_directory_member_is_not_refused(self):
        """The mirror-image positive control: a genuinely-present
        (even if empty) gitlink-style directory must never be refused
        -- only a *missing* one is a blocker."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (root / "present.c").write_text("int x;")
            (root / "mgfembp").mkdir()
            dest = Path(tmp) / "out.tar"
            ar.build_deterministic_archive(root, {"present.c", "mgfembp"}, dest)
            with tarfile.open(dest, "r") as tar:
                names = [m.name for m in tar.getmembers()]
            self.assertEqual(names, ["present.c"])


class GitBackedArchiveTests(unittest.TestCase):
    """issue #9 verifier remediation: when `root` IS a real git working
    tree, archive content must come exclusively from immutable git blobs
    bound to an exact commit SHA, never the mutable worktree/index."""

    def test_git_backed_archive_matches_filesystem_fallback_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            allowlist = _make_git_source_tree_committed(root)
            dest = Path(tmp) / "out.tar"
            ar.build_deterministic_archive(root, allowlist, dest)
            with tarfile.open(dest, "r") as tar:
                names = sorted(m.name for m in tar.getmembers())
            self.assertEqual(names, sorted(allowlist))

    def test_result_bound_to_exact_resolved_target_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            allowlist = _make_git_source_tree_committed(root)
            report = ar.rehearse_archive_twice(root, allowlist)
            self.assertEqual(report["target_sha"], gs.resolve_sha(root, "HEAD"))
            self.assertTrue(report["match"])

    def test_unstaged_worktree_mutation_does_not_change_archive_hash(self):
        """Core issue #9 requirement: mutate a *tracked* file directly on
        disk, without staging or committing, and prove the archive
        content/hash is unaffected -- it is bound to HEAD, not the
        worktree."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            allowlist = _make_git_source_tree_committed(root)
            before = ar.rehearse_archive_twice(root, allowlist)

            (root / "src" / "main.c").write_text("int main(void) { return 0xDEADBEEF; } // mutated\n")

            after = ar.rehearse_archive_twice(root, allowlist)
            self.assertEqual(after["hash1"], before["hash1"])
            self.assertEqual(after["target_sha"], before["target_sha"])

    def test_staged_but_uncommitted_mutation_does_not_change_archive_hash(self):
        """A *staged* (``git add``ed) change to a tracked file -- still
        not committed -- must also leave the archive unaffected: the
        archive is bound to HEAD, never the index."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            allowlist = _make_git_source_tree_committed(root)
            before = ar.rehearse_archive_twice(root, allowlist)

            (root / "src" / "main.c").write_text("int main(void) { return 42; } // staged mutation\n")
            _git("add", "src/main.c", cwd=root)
            self.assertFalse(gs.is_worktree_clean(root))

            after = ar.rehearse_archive_twice(root, allowlist)
            self.assertEqual(after["hash1"], before["hash1"])

    def test_an_actual_commit_does_change_the_archive_hash(self):
        """The mirror-image positive control: once a change is actually
        committed (a new HEAD), the archive DOES change -- proving the
        hash comparison above is a meaningful, non-trivial assertion
        rather than e.g. a always-empty/degenerate archive."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            allowlist = _make_git_source_tree_committed(root)
            before = ar.rehearse_archive_twice(root, allowlist)

            (root / "src" / "main.c").write_text("int main(void) { return 7; }\n")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "real change", cwd=root)

            after = ar.rehearse_archive_twice(root, allowlist)
            self.assertNotEqual(after["hash1"], before["hash1"])
            self.assertNotEqual(after["target_sha"], before["target_sha"])

    def test_explicit_target_sha_override_reads_that_historical_commit(self):
        """Passing an explicit --target-sha binds the archive to that
        exact historical commit, ignoring whatever HEAD/the worktree look
        like now."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            allowlist = _make_git_source_tree_committed(root)
            first_sha = gs.resolve_sha(root, "HEAD")
            first_report = ar.rehearse_archive_twice(root, allowlist, target_sha=first_sha)

            (root / "src" / "main.c").write_text("int main(void) { return 1; }\n")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "second commit", cwd=root)

            pinned_report = ar.rehearse_archive_twice(root, allowlist, target_sha=first_sha)
            self.assertEqual(pinned_report["hash1"], first_report["hash1"])
            self.assertEqual(pinned_report["target_sha"], first_sha)

    def test_tracked_symlink_rejected_even_though_committed(self):
        """An unsafe git mode (120000 symlink), even fully committed, must
        still be rejected -- immutability binds *which bytes*, never
        excuses *what kind* of content those bytes represent."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _init_repo(root)
            (root / "src").mkdir()
            (root / "src" / "real.c").write_text("int x;\n")
            (root / "src" / "link.c").symlink_to("real.c")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "with symlink", cwd=root)

            with self.assertRaises(ar.ArchiveRehearsalError) as ctx:
                ar.rehearse_archive_twice(root, {"src/real.c", "src/link.c"})
            self.assertIn("prohibited-symlink", str(ctx.exception))

    def test_gitlink_member_never_silently_archived_even_if_allowlisted(self):
        """issue #9 mandatory correction #2: a gitlink is never supposed
        to be an "included" allowlist entry any more at all (it belongs
        to the separate, explicit export-exclusions set instead -- see
        scripts/release_rehearsal/tree_coverage.py). If one somehow ends
        up allowlisted anyway (a hand-edited/corrupt allowlist), this
        must now be a hard, fail-closed refusal (`ArchiveRehearsalError`,
        via the archive-membership-exact check) -- never a silently
        built partial archive that quietly drops it without saying so."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _init_repo(root)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}\n")
            _git("add", "-A", cwd=root)

            nested = Path(tmp) / "nested"
            nested.mkdir()
            _init_repo(nested)
            (nested / "f.txt").write_text("x")
            _git("add", "-A", cwd=nested)
            _git("commit", "-q", "-m", "nested", cwd=nested)
            nested_sha = _git("rev-parse", "HEAD", cwd=nested).strip()
            _git("update-index", "--add", "--cacheinfo", f"160000,{nested_sha},vendor", cwd=root)
            _git("commit", "-q", "-m", "with gitlink", cwd=root)

            dest = Path(tmp) / "out.tar"
            with self.assertRaises(ar.ArchiveRehearsalError) as ctx:
                ar.build_deterministic_archive(root, {"src/main.c", "vendor"}, dest)
            self.assertIn("vendor", str(ctx.exception))
            self.assertFalse(dest.exists())

    def test_gitlink_correctly_omitted_from_allowlist_archives_cleanly(self):
        """The correct, supported shape: a gitlink is never passed as an
        allowlist member at all -- only the real, included blob is."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _init_repo(root)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}\n")
            _git("add", "-A", cwd=root)

            nested = Path(tmp) / "nested"
            nested.mkdir()
            _init_repo(nested)
            (nested / "f.txt").write_text("x")
            _git("add", "-A", cwd=nested)
            _git("commit", "-q", "-m", "nested", cwd=nested)
            nested_sha = _git("rev-parse", "HEAD", cwd=nested).strip()
            _git("update-index", "--add", "--cacheinfo", f"160000,{nested_sha},vendor", cwd=root)
            _git("commit", "-q", "-m", "with gitlink", cwd=root)

            dest = Path(tmp) / "out.tar"
            ar.build_deterministic_archive(root, {"src/main.c"}, dest)
            with tarfile.open(dest, "r") as tar:
                names = [m.name for m in tar.getmembers()]
            self.assertEqual(names, ["src/main.c"])


class RehearseArchiveTwiceTests(unittest.TestCase):
    """issue #9 verifier remediation: every allowlist below is the exact
    per-file shape -- see `ExactFilesystemAllowlistTests` above."""

    def test_match_true_for_clean_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _make_source_tree(root)
            report = ar.rehearse_archive_twice(root, {"src/main.c", "docs/readme.md"})
            self.assertTrue(report["match"])
            self.assertEqual(report["hash1"], report["hash2"])

    def test_no_temporary_files_retained_after_rehearsal(self):
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "fe8-release-rehearsal-*")))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _make_source_tree(root)
            ar.rehearse_archive_twice(root, {"src/main.c", "docs/readme.md"})
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
                ar.rehearse_archive_twice(root, {"src/bad.gba"})
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
            report_a = ar.rehearse_archive_twice(root_a, {"src/main.c", "docs/readme.md"})
            report_b = ar.rehearse_archive_twice(
                root_b, {"src/main.c", "docs/readme.md", "src/extra.c"}
            )
            self.assertNotEqual(report_a["hash1"], report_b["hash1"])


class NonGitTargetShaBindingTests(unittest.TestCase):
    """issue #9 verifier remediation: the documented non-git/extracted
    candidate path's exact --target-sha override must be bound into the
    archive report as an external identity *assertion* -- never
    silently discarded to None, and never verified against git (there
    is no git metadata to verify it against in a non-git tree)."""

    def test_asserted_target_sha_is_bound_into_the_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _make_source_tree(root)
            asserted_sha = "a" * 40
            report = ar.rehearse_archive_twice(
                root, {"src/main.c", "docs/readme.md"}, target_sha=asserted_sha,
            )
            self.assertEqual(report["target_sha"], asserted_sha)
            self.assertTrue(report["match"])

    def test_omitted_target_sha_is_still_none_not_fabricated(self):
        """The flip side: never *invent* an identity either -- omitting
        --target-sha for a non-git tree still reports `target_sha: None`
        here (the CLI layer is what makes it a mandatory, actionable
        error before ever reaching this point -- see
        scripts/release_rehearsal/cli.py's cmd_rehearse)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _make_source_tree(root)
            report = ar.rehearse_archive_twice(root, {"src/main.c", "docs/readme.md"})
            self.assertIsNone(report["target_sha"])


class RebuildEligibilityTests(unittest.TestCase):
    """`evaluate_rebuild_eligibility` in isolation, against synthetic
    fixtures -- never touching the real repository's mgfembp state."""

    def _make_repo_with_submodule(self, tmp, initialized, approved, identity_matches=True):
        root = Path(tmp) / "root"
        root.mkdir()
        _init_repo(root)
        (root / "src").mkdir()
        (root / "src" / "main.c").write_text("int x;\n")
        # A real ".gitmodules" mapping is required for "git submodule
        # status" (which evaluate_rebuild_eligibility() shells out to) to
        # recognize "vendor" as a submodule path at all -- the URL is
        # never actually fetched from in this test (or anywhere in this
        # module), it only needs to exist syntactically.
        (root / ".gitmodules").write_text(
            '[submodule "vendor"]\n\tpath = vendor\n\turl = https://example.invalid/vendor.git\n'
        )
        _git("add", "-A", cwd=root)

        nested = Path(tmp) / "nested"
        nested.mkdir()
        _init_repo(nested)
        (nested / "f.txt").write_text("x")
        _git("add", "-A", cwd=nested)
        _git("commit", "-q", "-m", "nested", cwd=nested)
        # issue #9 guardian-correction remediation (D3): a real submodule
        # checkout normally has its own configured 'origin' remote
        # (populated by "git submodule update --init"/"git clone
        # --recurse-submodules"); evaluate_rebuild_eligibility() now
        # cross-checks this against .gitmodules's declared URL, so this
        # synthetic fixture must configure a matching one for the
        # "eligible" scenarios below to remain eligible.
        _git("remote", "add", "origin", "https://example.invalid/vendor.git", cwd=nested)
        nested_sha = _git("rev-parse", "HEAD", cwd=nested).strip()
        _git("update-index", "--add", "--cacheinfo", f"160000,{nested_sha},vendor", cwd=root)
        _git("commit", "-q", "-m", "with gitlink", cwd=root)

        if initialized:
            # A real "initialized" state means the submodule directory
            # exists on disk as a valid, self-contained git checkout
            # (including its own real .git directory, not merely a
            # gitdir-pointer file) with matching content checked out --
            # exactly what "git submodule status" itself inspects.
            import shutil
            shutil.rmtree(root / "vendor", ignore_errors=True)
            shutil.copytree(nested, root / "vendor", ignore_dangling_symlinks=True)
            # "git submodule status" additionally requires the submodule
            # to be registered in local config (normally done by "git
            # submodule init", a purely local/offline bookkeeping step
            # that only copies the URL out of .gitmodules -- never a
            # network fetch) before it will report it as initialized/
            # in-sync rather than "-" (not initialized), even though the
            # checkout above is already fully present on disk.
            _git("submodule", "init", "--", "vendor", cwd=root)

        pinned_commit = nested_sha if identity_matches else "0" * 40
        provenance_dir = Path(tmp) / "provenance"
        provenance_dir.mkdir()
        (provenance_dir / "submodules.json").write_text(json.dumps([
            {
                "path": "vendor", "category": "submodule", "author": "NOASSERTION",
                "rightsholder": "NOASSERTION", "license": "NOASSERTION",
                "redistribution_approved": approved, "reviewer": ("Jane" if approved else None),
                "notes": "synthetic fixture", "pinned_commit": pinned_commit,
                # issue #9 mandatory correction #4: every "submodule"-category
                # provenance entry now also requires a non-empty 'url'.
                "url": "https://example.invalid/vendor.git",
            }
        ]), encoding="utf-8")
        return root, provenance_dir

    def test_uninitialized_submodule_is_ineligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_repo_with_submodule(tmp, initialized=False, approved=True)
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertFalse(report["submodule_initialized"])
            self.assertTrue(any("not initialized" in reason for reason in report["reasons"]))

    def test_unapproved_provenance_is_ineligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_repo_with_submodule(tmp, initialized=True, approved=False)
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertFalse(report["provenance_redistribution_approved"])

    def test_identity_mismatch_is_ineligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_repo_with_submodule(
                tmp, initialized=True, approved=True, identity_matches=False
            )
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertFalse(report["identity_matches_pinned"])
            self.assertTrue(any("does not match" in reason for reason in report["reasons"]))

    def test_initialized_approved_matching_identity_is_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_repo_with_submodule(tmp, initialized=True, approved=True)
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertTrue(eligible, report["reasons"])
            self.assertEqual(report["reasons"], [])

    def test_missing_provenance_entry_is_ineligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_repo_with_submodule(tmp, initialized=True, approved=True)
            (provenance_dir / "submodules.json").write_text("[]", encoding="utf-8")
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertTrue(any("no provenance entry" in reason for reason in report["reasons"]))


# issue #9 guardian-correction remediation (D1): the legacy, copy-of-a-
# mutable-directory `run_build_twice()` helper (and its dedicated test
# class that used to live here) was deleted outright from
# archive_rehearsal.py -- it was never wired into `rebuild_rehearsal_
# blocker()`'s status computation, but its mere presence let release-
# evidence docs and a test's own docstring misattribute it as if it
# proved the real, wired `verified_success` path (an independent review
# reproduced this as defect D1). `RunBuildTwiceFromImmutableSourceTests`
# below is the real replacement -- it exercises the actual function
# `rebuild_rehearsal_blocker()` uses, including the "failing build" and
# "missing declared output" cases the deleted class used to cover.


class MaterializeImmutableSourceTreeTests(unittest.TestCase):
    """issue #9 mandatory correction #7: `materialize_immutable_source_tree`
    must extract the exact *committed* tree at `target_sha` -- never the
    live, potentially-mutable worktree."""

    def test_extraction_matches_committed_content_not_worktree_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _init_repo(root)
            (root / "a.txt").write_text("committed\n")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = _git("rev-parse", "HEAD", cwd=root).strip()

            # Mutate the live worktree *after* resolving the target SHA --
            # the materialization must be completely unaffected by this.
            (root / "a.txt").write_text("mutated-after-sha-resolved\n")

            dest = Path(tmp) / "materialized"
            dest.mkdir()
            ar.materialize_immutable_source_tree(root, sha, dest)
            self.assertEqual((dest / "a.txt").read_text(), "committed\n")

    def test_nonexistent_sha_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            _init_repo(root)
            (root / "a.txt").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            dest = Path(tmp) / "materialized"
            dest.mkdir()
            with self.assertRaises(ar.ArchiveRehearsalError):
                ar.materialize_immutable_source_tree(root, "0" * 40, dest)


class RunBuildTwiceFromImmutableSourceTests(unittest.TestCase):
    """issue #9 mandatory correction #7: the independent-immutable-
    materialization double-build -- two separate source trees,
    materialized independently from the same immutable `target_sha`
    (never a copy of the live worktree), each in its own build/output
    directory, with each materialization's own input files verified
    unchanged after the build runs."""

    def _make_repo(self, tmp) -> tuple:
        root = Path(tmp) / "root"
        root.mkdir()
        _init_repo(root)
        (root / "input.txt").write_text("hello\n")
        _git("add", "-A", cwd=root)
        _git("commit", "-q", "-m", "init", cwd=root)
        sha = _git("rev-parse", "HEAD", cwd=root).strip()
        return root, sha

    def test_deterministic_build_reports_verified_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._make_repo(tmp)
            build_command = [
                sys.executable, "-c",
                "open('out.bin', 'wb').write(open('input.txt', 'rb').read())",
            ]
            result = ar.run_build_twice_from_immutable_source(root, sha, build_command, ["out.bin"])
            self.assertTrue(result["match"], result)
            self.assertEqual(result["input_tree_mutation_problems1"], [])
            self.assertEqual(result["input_tree_mutation_problems2"], [])

    def test_live_worktree_mutation_after_sha_resolution_never_affects_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._make_repo(tmp)
            (root / "input.txt").write_text("MUTATED-LIVE-WORKTREE-BYTES\n")
            build_command = [
                sys.executable, "-c",
                "open('out.bin', 'wb').write(open('input.txt', 'rb').read())",
            ]
            result = ar.run_build_twice_from_immutable_source(root, sha, build_command, ["out.bin"])
            self.assertTrue(result["match"], result)
            # both materializations reflect the *committed* "hello\n",
            # never the mutated live worktree bytes -- if they had leaked
            # through, the two hashes would still match each other (both
            # runs would see the same mutation), so this is checked via
            # the mutation-detector as an independent, additional proof:
            # the committed input.txt itself was never touched by the
            # build (it only ever wrote a *new* out.bin).
            self.assertEqual(result["input_tree_mutation_problems1"], [])

    def test_build_that_mutates_its_declared_input_is_reported_as_a_failure(self):
        """The literal issue #9 requirement: mutating one materialization
        must fail -- never silently "match": True."""
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._make_repo(tmp)
            build_command = [
                sys.executable, "-c",
                "open('input.txt', 'w').write('mutated-by-the-build-script'); "
                "open('out.bin', 'wb').write(b'output')",
            ]
            result = ar.run_build_twice_from_immutable_source(root, sha, build_command, ["out.bin"])
            self.assertFalse(result["match"])
            self.assertTrue(result["input_tree_mutation_problems1"])
            self.assertTrue(any("mutated" in p for p in result["input_tree_mutation_problems1"]))

    def test_build_that_deletes_its_declared_input_is_reported_as_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._make_repo(tmp)
            build_command = [
                sys.executable, "-c",
                "import os; os.remove('input.txt'); open('out.bin', 'wb').write(b'output')",
            ]
            result = ar.run_build_twice_from_immutable_source(root, sha, build_command, ["out.bin"])
            self.assertFalse(result["match"])
            self.assertTrue(any("disappeared" in p for p in result["input_tree_mutation_problems1"]))

    def test_nondeterministic_build_reports_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._make_repo(tmp)
            build_command = [
                sys.executable, "-c",
                "import os; open('out.bin', 'wb').write(os.urandom(32))",
            ]
            result = ar.run_build_twice_from_immutable_source(root, sha, build_command, ["out.bin"])
            self.assertFalse(result["match"])
            self.assertNotEqual(result["hashes1"], result["hashes2"])

    def test_failing_build_command_reports_no_match(self):
        """issue #9 guardian-correction remediation (D1): the same
        "a non-zero exit must never match" case the deleted legacy
        run_build_twice() used to cover, now proven against the actual,
        wired immutable-materialization function."""
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._make_repo(tmp)
            build_command = [sys.executable, "-c", "import sys; sys.exit(1)"]
            result = ar.run_build_twice_from_immutable_source(root, sha, build_command, ["out.bin"])
            self.assertEqual(result["returncode1"], 1)
            self.assertEqual(result["returncode2"], 1)
            self.assertFalse(result["match"])

    def test_missing_declared_output_reports_no_match(self):
        """issue #9 guardian-correction remediation (D1): the same
        "a build that never writes its declared output must never
        match" case the deleted legacy run_build_twice() used to cover,
        now proven against the actual, wired immutable-materialization
        function."""
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._make_repo(tmp)
            build_command = [sys.executable, "-c", "pass"]
            result = ar.run_build_twice_from_immutable_source(root, sha, build_command, ["never_written.bin"])
            self.assertFalse(result["outputs_present"])
            self.assertFalse(result["match"])

    def test_extra_materialize_callback_runs_independently_for_each_run(self):
        """`extra_materialize` is invoked once per independent
        materialization -- proven by having it write a marker file whose
        *content* the build command echoes into its declared output;
        both runs must independently reproduce the identical marker
        content (never share state)."""
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._make_repo(tmp)

            def _add_marker(run_root: Path) -> None:
                (run_root / "marker.txt").write_text("shared-marker-content\n")

            build_command = [
                sys.executable, "-c",
                "open('out.bin', 'wb').write(open('marker.txt', 'rb').read())",
            ]
            result = ar.run_build_twice_from_immutable_source(
                root, sha, build_command, ["out.bin"], extra_materialize=_add_marker,
            )
            self.assertTrue(result["match"], result)

    def test_sharing_a_materialization_directory_between_runs_is_rejected(self):
        """The literal issue #9 requirement: sharing a source/build dir
        between the two runs must fail -- simulated here by forcing
        `tempfile.mkdtemp` to return the *same* path both times (the only
        way this could ever happen, since real `mkdtemp()` calls are
        always unique) and confirming the explicit collision guard
        rejects it rather than silently reporting a result."""
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._make_repo(tmp)
            shared_dir = Path(tmp) / "forced-shared-run-dir"
            shared_dir.mkdir()
            build_command = [sys.executable, "-c", "open('out.bin', 'wb').write(b'x')"]
            with mock.patch("tempfile.mkdtemp", return_value=str(shared_dir)):
                with self.assertRaises(ar.ArchiveRehearsalError) as ctx:
                    ar.run_build_twice_from_immutable_source(root, sha, build_command, ["out.bin"])
            self.assertIn("same directory", str(ctx.exception))


class RebuildRehearsalBlockerTests(unittest.TestCase):
    def test_documents_github_autoarchive_contradiction(self):
        report = ar.rebuild_rehearsal_blocker(ROOT)
        self.assertIn("submodule", report["github_autoarchive_submodule_contradiction"])
        self.assertIn("mgfembp", report["github_autoarchive_submodule_contradiction"])

    def test_real_repo_reports_blocked_with_precise_reason(self):
        report = ar.rebuild_rehearsal_blocker(ROOT)
        self.assertEqual(report["status"], ar.REBUILD_STATUS_BLOCKED)
        self.assertTrue(any("mgfembp" in reason for reason in report["reasons"]))
        self.assertIn("mgfembp", report["submodule_status_output"])

    def test_status_is_one_of_the_four_distinct_machine_states(self):
        report = ar.rebuild_rehearsal_blocker(ROOT)
        self.assertIn(report["status"], ar.ALL_REBUILD_STATUSES)

    def test_eligible_but_no_build_command_reports_not_run_not_success(self):
        """A rebuild must never be described as verified/proved when it
        was not actually executed -- even when eligible (with a
        submodule_path/provenance_dir that actually *match* the
        synthetic fixture -- guardian-correction remediation: the
        previous version of this test called `rebuild_rehearsal_blocker`
        with neither, so it always fell back to the real repository's
        own unrelated "mgfembp"/`docs/release_data/provenance`
        defaults -- trivially blocked for the wrong reason, never
        actually exercising this eligible fixture through the wrapper at
        all), omitting an explicit build_command/output_relpaths must
        report exactly "not_run", never "verified_success" and never
        silently pass."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = RebuildEligibilityTests()._make_repo_with_submodule(
                tmp, initialized=True, approved=True
            )
            eligible, _ = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertTrue(eligible)
            report = ar.rebuild_rehearsal_blocker(
                root, attempt_build=True, submodule_path="vendor", provenance_dir=provenance_dir,
            )
            self.assertEqual(report["status"], ar.REBUILD_STATUS_NOT_RUN)
            self.assertNotEqual(report["status"], ar.REBUILD_STATUS_VERIFIED_SUCCESS)

    def test_attempt_build_false_is_not_run_when_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = RebuildEligibilityTests()._make_repo_with_submodule(
                tmp, initialized=True, approved=True
            )
            eligible, _ = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertTrue(eligible)
            # guardian-correction remediation: the previous version of
            # this test asserted nothing at all about
            # rebuild_rehearsal_blocker()'s actual status despite its own
            # name promising "is_not_run" -- now it actually calls it,
            # with matching submodule_path/provenance_dir, and checks.
            report = ar.rebuild_rehearsal_blocker(
                root, attempt_build=False, submodule_path="vendor", provenance_dir=provenance_dir,
            )
            self.assertEqual(report["status"], ar.REBUILD_STATUS_NOT_RUN)

    def test_current_live_repo_never_fetches_or_initializes_mgfembp(self):
        """Calling the real rehearsal against this actual repository must
        never mutate its submodule state (no fetch/init/approve)."""
        before = _git("submodule", "status", cwd=ROOT)
        ar.rebuild_rehearsal_blocker(ROOT)
        after = _git("submodule", "status", cwd=ROOT)
        self.assertEqual(before, after)


class RebuildRehearsalBlockerEndToEndBuildTests(unittest.TestCase):
    """issue #9 guardian-correction remediation (D1): drives the actual,
    wired `rebuild_rehearsal_blocker()` -- never a lower-level function
    in isolation, and never the deleted legacy `run_build_twice()` --
    through a synthetic, fully-eligible (initialized/approved/identity-
    matched/clean-worktree/URL-matched/pinned-object-accessible)
    submodule fixture, for every one of the machine-distinct rebuild
    outcomes a real double-build can produce: verified_success, a
    mismatch, a build failure, a missing declared output, a shared-
    directory refusal, and a source (input-tree) mutation."""

    def _make_eligible_repo(self, tmp):
        root, provenance_dir = RebuildEligibilityTests()._make_repo_with_submodule(
            tmp, initialized=True, approved=True,
        )
        eligible, eligibility_report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
        assert eligible, eligibility_report  # fixture sanity check, not this test's own assertion
        return root, provenance_dir

    def _blocker(self, root, provenance_dir, build_command, output_relpaths=("rom.bin",)):
        return ar.rebuild_rehearsal_blocker(
            root, attempt_build=True, build_command=build_command,
            output_relpaths=list(output_relpaths), submodule_path="vendor", provenance_dir=provenance_dir,
        )

    def test_verified_success_end_to_end(self):
        """The literal issue #9 D1 requirement: `rebuild_rehearsal_
        blocker()` itself, through a synthetic approved+pinned+
        initialized submodule fixture, executes a real hermetic build
        command twice from two independently materialized immutable
        inputs (the superproject's own tracked src/main.c *and* the
        pinned-commit-bound vendor/f.txt submodule content) and reports
        verified_success -- with distinct materialization roots,
        unchanged inputs, and matching declared outputs all directly
        observable in the report."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            build_command = [
                sys.executable, "-c",
                "import pathlib; "
                "a = pathlib.Path('src/main.c').read_bytes(); "
                "b = pathlib.Path('vendor/f.txt').read_bytes(); "
                "pathlib.Path('rom.bin').write_bytes(a + b)",
            ]
            report = self._blocker(root, provenance_dir, build_command)
            self.assertEqual(report["status"], ar.REBUILD_STATUS_VERIFIED_SUCCESS, report)
            result = report["build_result"]
            self.assertEqual(result["returncode1"], 0)
            self.assertEqual(result["returncode2"], 0)
            self.assertTrue(result["outputs_present"])
            self.assertEqual(result["hashes1"], result["hashes2"])
            self.assertEqual(result["input_tree_mutation_problems1"], [])
            self.assertEqual(result["input_tree_mutation_problems2"], [])
            self.assertNotEqual(result["materialization_root1"], result["materialization_root2"])
            expected_hash = hashlib.sha256(
                (root / "src" / "main.c").read_bytes() + (root / "vendor" / "f.txt").read_bytes()
            ).hexdigest()
            self.assertEqual(result["hashes1"]["rom.bin"], expected_hash)

    def test_mismatch_end_to_end_reports_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            build_command = [
                sys.executable, "-c",
                "import os; open('rom.bin', 'wb').write(os.urandom(32))",
            ]
            report = self._blocker(root, provenance_dir, build_command)
            self.assertEqual(report["status"], ar.REBUILD_STATUS_FAILED)
            self.assertNotEqual(
                report["build_result"]["hashes1"], report["build_result"]["hashes2"]
            )
            self.assertTrue(report["reasons"])

    def test_build_failure_end_to_end_reports_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            build_command = [sys.executable, "-c", "import sys; sys.exit(3)"]
            report = self._blocker(root, provenance_dir, build_command)
            self.assertEqual(report["status"], ar.REBUILD_STATUS_FAILED)
            self.assertEqual(report["build_result"]["returncode1"], 3)
            self.assertEqual(report["build_result"]["returncode2"], 3)

    def test_missing_output_end_to_end_reports_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            build_command = [sys.executable, "-c", "pass"]
            report = self._blocker(root, provenance_dir, build_command)
            self.assertEqual(report["status"], ar.REBUILD_STATUS_FAILED)
            self.assertFalse(report["build_result"]["outputs_present"])

    def test_source_mutation_end_to_end_reports_failed(self):
        """The literal D1 "source mutation" case: a build that mutates
        its own declared input (the superproject's own tracked
        src/main.c) must be reported failed, end-to-end, through
        `rebuild_rehearsal_blocker()` itself -- never silently
        "matched"."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            build_command = [
                sys.executable, "-c",
                "open('src/main.c', 'w').write('int x; // mutated-by-build'); "
                "open('rom.bin', 'wb').write(b'x')",
            ]
            report = self._blocker(root, provenance_dir, build_command)
            self.assertEqual(report["status"], ar.REBUILD_STATUS_FAILED)
            self.assertTrue(report["build_result"]["input_tree_mutation_problems1"])

    def test_shared_dir_refusal_end_to_end_raises(self):
        """The literal D1 "shared-dir refusal" case, proven through the
        actual wired `rebuild_rehearsal_blocker()` call -- not merely
        `run_build_twice_from_immutable_source()` in isolation."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            shared_dir = Path(tmp) / "forced-shared-run-dir"
            shared_dir.mkdir()
            build_command = [sys.executable, "-c", "open('rom.bin', 'wb').write(b'x')"]
            with mock.patch("tempfile.mkdtemp", return_value=str(shared_dir)):
                with self.assertRaises(ar.ArchiveRehearsalError) as ctx:
                    self._blocker(root, provenance_dir, build_command)
            self.assertIn("same directory", str(ctx.exception))


class SubmoduleDirtyWorktreeReproducerTests(unittest.TestCase):
    """issue #9 guardian-correction remediation (D3): the literal,
    reviewer-reproduced defect -- a submodule worktree whose HEAD commit
    still matches the pinned gitlink SHA, but whose *worktree bytes*
    have been locally modified/staged/added without a new commit, must
    never be treated as eligible, and (independently, in case
    eligibility were ever wrongly bypassed by a future bug) must never
    have its dirty bytes flow into a rebuild via the materializer
    either."""

    def _make_eligible_repo(self, tmp):
        return RebuildEligibilityTests()._make_repo_with_submodule(tmp, initialized=True, approved=True)

    def test_dirty_modified_tracked_file_is_ineligible(self):
        """The literal reviewer reproducer: modify a tracked file inside
        the submodule worktree, without staging or committing."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            (root / "vendor" / "f.txt").write_text("TAMPERED-UNCOMMITTED-BYTES")
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertFalse(report["submodule_worktree_clean"])
            self.assertTrue(any("not clean" in reason for reason in report["reasons"]))

    def test_staged_uncommitted_change_is_ineligible(self):
        """The staged variant: `git add`ed inside the submodule, but
        still not committed -- HEAD still matches the pin exactly."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            (root / "vendor" / "f.txt").write_text("STAGED-TAMPERED-BYTES")
            _git("add", "f.txt", cwd=root / "vendor")
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertFalse(report["submodule_worktree_clean"])

    def test_untracked_file_is_ineligible(self):
        """The untracked variant: an extra, never-added file smuggled
        into the submodule worktree."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            (root / "vendor" / "untracked-extra.txt").write_text("smuggled content")
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertFalse(report["submodule_worktree_clean"])

    def test_dirty_submodule_never_reaches_verified_success_through_the_blocker(self):
        """End-to-end reproducer: even a real, actually-attempted rebuild
        against a dirty-but-commit-matching submodule is reported
        blocked (ineligible), never verified_success, through
        `rebuild_rehearsal_blocker()` itself."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            (root / "vendor" / "f.txt").write_text("TAMPERED-UNCOMMITTED-BYTES")
            build_command = [
                sys.executable, "-c",
                "import pathlib; "
                "pathlib.Path('rom.bin').write_bytes(pathlib.Path('vendor/f.txt').read_bytes())",
            ]
            report = ar.rebuild_rehearsal_blocker(
                root, attempt_build=True, build_command=build_command,
                output_relpaths=["rom.bin"], submodule_path="vendor", provenance_dir=provenance_dir,
            )
            self.assertEqual(report["status"], ar.REBUILD_STATUS_BLOCKED)
            self.assertNotEqual(report["status"], ar.REBUILD_STATUS_VERIFIED_SUCCESS)

    def test_materializer_never_reflects_dirty_worktree_bytes_even_if_called_directly(self):
        """Defense-in-depth positive proof (the strongest form of the D3
        fix): even calling the new immutable-git-archive-based
        materializer directly -- bypassing eligibility entirely, as if
        some future bug granted eligibility anyway -- against a dirty
        submodule worktree produces the *pinned commit's* own immutable
        content, never the dirty worktree bytes. The fix does not merely
        rely on the eligibility gate catching every case."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            pinned_commit = json.loads(
                (provenance_dir / "submodules.json").read_text(encoding="utf-8")
            )[0]["pinned_commit"]
            (root / "vendor" / "f.txt").write_text("TAMPERED-UNCOMMITTED-BYTES")
            materialize = ar._materialize_verified_submodule_content(root, "vendor", pinned_commit)
            with tempfile.TemporaryDirectory() as run_dir:
                run_root = Path(run_dir) / "run"
                run_root.mkdir()
                materialize(run_root)
                self.assertEqual((run_root / "vendor" / "f.txt").read_text(), "x")


class SubmoduleUrlAndPinnedObjectFailClosedTests(unittest.TestCase):
    """issue #9 R3: the reviewer-reproduced remaining fail-open gaps in
    `evaluate_rebuild_eligibility` -- a missing/mismatched submodule
    origin URL (against *either* independent immutable declared source:
    .gitmodules or the provenance record), an inaccessible or wrong-type
    pinned commit object, and a genuine 'git status'/'git config'
    command failure (as opposed to their own ordinary not-clean/unset
    outcomes) -- must all make a rebuild non-eligible, each with its own
    actionable reason, never a silent pass. Every test here starts from
    the exact same fully-matching, genuinely eligible baseline fixture
    as `RebuildEligibilityTests`/`SubmoduleDirtyWorktreeReproducerTests`
    (`_make_repo_with_submodule(..., initialized=True, approved=True)`),
    mutating exactly one fact away from it."""

    def _make_eligible_repo(self, tmp):
        return RebuildEligibilityTests()._make_repo_with_submodule(tmp, initialized=True, approved=True)

    def test_clean_matching_baseline_is_eligible(self):
        """Positive control: the shared baseline fixture itself is
        genuinely, fully eligible -- with all three URL sources actually
        agreeing -- before any test below mutates exactly one fact away
        from it. If this ever fails, every other test in this class is
        meaningless."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertTrue(eligible, report["reasons"])
            self.assertEqual(report["reasons"], [])
            self.assertTrue(report["submodule_configured_url"])
            self.assertEqual(report["submodule_configured_url"], report["submodule_declared_url"])
            self.assertEqual(report["submodule_configured_url"], report["submodule_provenance_url"])

    def test_missing_origin_remote_is_ineligible(self):
        """issue #9 R3 literal reproducer: a submodule checkout with no
        configured 'origin' remote at all previously left the URL check
        vacuously passing (never actually evaluated at all, since the
        old condition required both sides to be known first); it must
        now be non-eligible with an actionable reason."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            _git("remote", "remove", "origin", cwd=root / "vendor")
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertIsNone(report["submodule_configured_url"])
            self.assertTrue(
                any("no configured 'remote.origin.url'" in reason for reason in report["reasons"]),
                report["reasons"],
            )

    def test_configured_url_mismatch_against_gitmodules_is_ineligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            _git("remote", "set-url", "origin", "https://example.invalid/TAMPERED.git", cwd=root / "vendor")
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertTrue(
                any("does not match .gitmodules's declared URL" in reason for reason in report["reasons"]),
                report["reasons"],
            )

    def test_configured_url_mismatch_against_provenance_is_ineligible(self):
        """The mirror-image: .gitmodules still agrees with the live
        configured origin, but the *separate*, independent provenance
        record's own 'url' has drifted -- also non-eligible. Proves the
        three-way check is not merely a two-way .gitmodules check with
        provenance along for the ride."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            submodules_json = provenance_dir / "submodules.json"
            entries = json.loads(submodules_json.read_text(encoding="utf-8"))
            entries[0]["url"] = "https://example.invalid/DRIFTED-PROVENANCE.git"
            submodules_json.write_text(json.dumps(entries), encoding="utf-8")
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertTrue(
                any("does not match the provenance-recorded URL" in reason for reason in report["reasons"]),
                report["reasons"],
            )

    def test_missing_provenance_url_is_ineligible(self):
        """`provenance.py`'s own file-loading schema already hard-fails
        an on-disk 'submodule'-category entry with no non-empty 'url'
        (issue #9 mandatory correction #4) -- this defensive branch in
        `evaluate_rebuild_eligibility` itself (never assuming that
        upstream schema enforcement is the only thing standing between
        a missing url and a false pass) is proven directly via a mocked
        `prov.load_all`, exactly like `_submodule_declared_url`'s own
        'no url' case is a plain, honestly-reported fact rather than an
        assumed impossibility."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            fake_entries = [{
                "path": "vendor", "pinned_commit": _git("rev-parse", "HEAD", cwd=root / "vendor").strip(),
                "redistribution_approved": True,
            }]
            with mock.patch(
                "scripts.release_rehearsal.archive_rehearsal.prov.load_all", return_value=fake_entries,
            ):
                eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertIsNone(report["submodule_provenance_url"])
            self.assertTrue(
                any("has no 'url' recorded" in reason for reason in report["reasons"]),
                report["reasons"],
            )

    def test_missing_gitmodules_declared_url_is_ineligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            (root / ".gitmodules").write_text('[submodule "vendor"]\n\tpath = vendor\n')
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "drop gitmodules url", cwd=root)
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertIsNone(report["submodule_declared_url"])
            self.assertTrue(
                any("declares no readable 'url'" in reason for reason in report["reasons"]),
                report["reasons"],
            )

    def test_pinned_object_wrong_type_blob_is_ineligible(self):
        """issue #9 R3: a `pinned_commit` that resolves to a real object
        of the *wrong type* (e.g. a blob, from a transcription mistake)
        must never be treated as an accessible commit -- `git cat-file
        -e <sha>^{commit}` itself already rejects this by object type,
        this proves `evaluate_rebuild_eligibility` actually surfaces
        that as a non-eligible finding."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            blob_sha = _git("hash-object", "f.txt", cwd=root / "vendor").strip()
            submodules_json = provenance_dir / "submodules.json"
            entries = json.loads(submodules_json.read_text(encoding="utf-8"))
            entries[0]["pinned_commit"] = blob_sha
            submodules_json.write_text(json.dumps(entries), encoding="utf-8")
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertFalse(report["submodule_pinned_object_accessible"])
            self.assertTrue(
                any(
                    "not accessible as a real, locally-present commit object" in reason
                    for reason in report["reasons"]
                ),
                report["reasons"],
            )

    def test_pinned_object_nonexistent_sha_is_ineligible(self):
        """A syntactically-plausible but entirely nonexistent commit SHA
        (never fetched/present in the submodule's own object database --
        e.g. a shallow clone) must also be reported not-accessible,
        never merely 'unverified'."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            submodules_json = provenance_dir / "submodules.json"
            entries = json.loads(submodules_json.read_text(encoding="utf-8"))
            entries[0]["pinned_commit"] = "f" * 40
            submodules_json.write_text(json.dumps(entries), encoding="utf-8")
            eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertFalse(report["submodule_pinned_object_accessible"])

    def test_git_status_command_failure_inside_submodule_is_ineligible(self):
        """issue #9 R3: a genuine 'git status' *command* failure inside
        the submodule worktree (as opposed to an ordinary dirty/clean
        result) must be caught and reported as its own actionable,
        non-eligible finding -- never silently swallowed into either a
        false 'clean' or an unrelated traceback."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            real_run = subprocess.run

            def _fake_run(cmd, *args, **kwargs):
                if cmd[:2] == ["git", "status"]:
                    return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="fatal: injected status failure")
                return real_run(cmd, *args, **kwargs)

            with mock.patch("scripts.release_rehearsal.archive_rehearsal.subprocess.run", side_effect=_fake_run):
                eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertFalse(report["submodule_worktree_clean"])
            self.assertTrue(
                any("git status failed inside" in reason for reason in report["reasons"]),
                report["reasons"],
            )

    def test_git_config_command_failure_is_ineligible(self):
        """The 'remote' side of the same guard: a genuine 'git config'
        command failure (as opposed to the entirely ordinary 'no origin
        set' exit code 1) must also be its own actionable, non-eligible
        finding, never folded into the same 'just unset' None."""
        with tempfile.TemporaryDirectory() as tmp:
            root, provenance_dir = self._make_eligible_repo(tmp)
            real_run = subprocess.run

            def _fake_run(cmd, *args, **kwargs):
                if cmd[:2] == ["git", "config"]:
                    return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="fatal: injected config failure")
                return real_run(cmd, *args, **kwargs)

            with mock.patch("scripts.release_rehearsal.archive_rehearsal.subprocess.run", side_effect=_fake_run):
                eligible, report = ar.evaluate_rebuild_eligibility(root, "vendor", provenance_dir)
            self.assertFalse(eligible)
            self.assertIsNone(report["submodule_configured_url"])
            self.assertTrue(
                any("git config --get remote.origin.url failed" in reason for reason in report["reasons"]),
                report["reasons"],
            )


class NonGitRebuildEligibilityTests(unittest.TestCase):
    """issue #9 verifier remediation: the literal reproduced defect --
    `rebuild_rehearsal_blocker()`/`evaluate_rebuild_eligibility()` must
    never invoke `git submodule status` (or any other git command)
    against a non-git `repo_root` (a genuine extracted archive/non-git
    candidate tree). Proven by nesting the fixture directly inside this
    real, git-tracked worktree (ROOT): if any git command leaked through
    with the fixture as its cwd, git's own upward directory discovery
    would find ROOT's real `.git` and silently report ROOT's own actual
    submodule state (which does mention "mgfembp") instead of failing
    closed for the extracted tree -- these assertions would then fail."""

    def _make_nested_non_git_fixture(self, name: str) -> Path:
        nested = ROOT / "scripts" / "release_rehearsal" / "tests" / name
        self.addCleanup(shutil.rmtree, nested, True)
        nested.mkdir(exist_ok=True)
        return nested

    def test_evaluate_rebuild_eligibility_is_ineligible_without_invoking_git(self):
        nested = self._make_nested_non_git_fixture(".issue9-rebuild-fixture-tmp-1")
        eligible, report = ar.evaluate_rebuild_eligibility(nested)
        self.assertFalse(eligible)
        self.assertEqual(report["submodule_status_output"], "")
        self.assertIsNone(report["submodule_checked_out_sha"])
        self.assertIsNone(report["provenance_pinned_commit"])
        self.assertFalse(report["provenance_redistribution_approved"])
        self.assertFalse(report["identity_matches_pinned"])
        self.assertTrue(any(".git" in reason for reason in report["reasons"]))
        # The real repository's own "mgfembp" submodule-status line must
        # never leak into a non-git candidate's report.
        self.assertNotIn("mgfembp", report["submodule_status_output"])

    def test_rebuild_rehearsal_blocker_non_git_repo_root_is_blocked_not_traceback(self):
        nested = self._make_nested_non_git_fixture(".issue9-rebuild-fixture-tmp-2")
        report = ar.rebuild_rehearsal_blocker(nested)
        self.assertEqual(report["status"], ar.REBUILD_STATUS_BLOCKED)
        self.assertIn("github_autoarchive_submodule_contradiction", report)
        self.assertTrue(any(".git" in reason for reason in report["reasons"]))

    def test_non_git_repo_root_never_mutates_or_queries_the_enclosing_repos_submodule_state(self):
        """A stronger positive control than the reason text alone: the
        real, enclosing repository's actual `git submodule status`
        output is completely unaffected by (and never consulted by)
        evaluating a nested non-git fixture."""
        before = _git("submodule", "status", cwd=ROOT)
        nested = self._make_nested_non_git_fixture(".issue9-rebuild-fixture-tmp-3")
        ar.rebuild_rehearsal_blocker(nested)
        after = _git("submodule", "status", cwd=ROOT)
        self.assertEqual(before, after)


class RepositoryStateTests(unittest.TestCase):
    """The real repository's own source tree must rehearse deterministically."""

    def test_real_tree_rehearses_deterministically(self):
        allowlist = sg.load_allowlist(ROOT / "docs" / "release_data" / "source_allowlist.json")
        report = ar.rehearse_archive_twice(ROOT, allowlist)
        self.assertTrue(report["match"])

    def test_real_tree_archive_is_git_blob_bound_not_worktree(self):
        allowlist = sg.load_allowlist(ROOT / "docs" / "release_data" / "source_allowlist.json")
        report = ar.rehearse_archive_twice(ROOT, allowlist)
        self.assertEqual(report["target_sha"], gs.resolve_sha(ROOT, "HEAD"))


class SourceCommentTestClassReferenceTests(unittest.TestCase):
    """issue #9 R4: a cheap, mechanical guard against the literal
    reproduced defect -- a source comment naming a nonexistent test
    class (this repository's own former `archive_rehearsal.py` comment
    pointing at a `RebuildRehearsalBlockerEndToEndVerifiedSuccessTests`
    that had never actually existed anywhere in this test suite). Every
    backtick-quoted `SomeIdentifierTests`-shaped reference appearing
    anywhere in `scripts/release_rehearsal/*.py`'s own source text
    (docstrings/comments) must name a real class actually defined
    somewhere under `scripts/release_rehearsal/tests/`. This is a plain
    static-text scan (no import/execution of the referencing module
    beyond what importing it for its own tests already does) -- it
    cannot by itself prove a reference describes the right *behavior*,
    only that the name is not simply stale/typo'd/deleted-out-from-under
    the comment."""

    _REFERENCE_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*Tests)`")
    _CLASS_DEF_RE = re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)

    def test_every_backtick_quoted_tests_class_reference_actually_exists(self):
        rehearsal_dir = Path(ar.__file__).resolve().parent
        tests_dir = rehearsal_dir / "tests"

        defined_classes = set()
        for test_file in sorted(tests_dir.glob("test_*.py")):
            defined_classes.update(self._CLASS_DEF_RE.findall(test_file.read_text(encoding="utf-8")))
        self.assertTrue(defined_classes, f"found no test classes at all under {tests_dir}")

        dangling = []
        for source_file in sorted(rehearsal_dir.glob("*.py")):
            referenced = sorted(set(self._REFERENCE_RE.findall(source_file.read_text(encoding="utf-8"))))
            for name in referenced:
                if name not in defined_classes:
                    dangling.append(f"{source_file.name}: `{name}`")

        self.assertEqual(
            dangling, [],
            "the following source comment(s) reference a `...Tests`-shaped class name that does "
            f"not actually exist as a real 'class NAME(...):' definition anywhere under {tests_dir} "
            f"-- fix the stale comment or the renamed/deleted test class: {dangling}",
        )


if __name__ == "__main__":
    unittest.main()
