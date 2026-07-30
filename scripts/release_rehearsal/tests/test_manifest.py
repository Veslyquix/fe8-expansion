"""Tests for scripts/release_rehearsal/manifest.py (issue #9)."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "modernize"))

import expansion_config as ec  # noqa: E402

from scripts.release_rehearsal import manifest as rm


class ResolveTargetShaTests(unittest.TestCase):
    def test_explicit_override_must_be_exact_40_hex(self):
        with self.assertRaises(rm.ManifestError):
            rm.resolve_target_sha(ROOT, "deadbeef")

    def test_explicit_override_rejects_uppercase(self):
        with self.assertRaises(rm.ManifestError):
            rm.resolve_target_sha(ROOT, "A" * 40)

    def test_explicit_override_accepted(self):
        sha = "c717da36c51f94bc6051ec8954bed4ccec2b76fd"
        self.assertEqual(rm.resolve_target_sha(ROOT, sha), sha)

    def test_non_git_tree_without_override_is_actionable(self):
        with self.assertRaises(rm.ManifestError) as ctx:
            rm.resolve_target_sha(Path("/tmp"), None)
        self.assertIn("--target-sha", str(ctx.exception))

    def test_real_repo_resolves_from_git(self):
        sha = rm.resolve_target_sha(ROOT, None)
        self.assertRegex(sha, r"^[0-9a-f]{40}$")


class ShortShaTests(unittest.TestCase):
    def test_derive_short_sha(self):
        self.assertEqual(rm.derive_short_sha("c717da36c51f94bc6051ec8954bed4ccec2b76fd"), "c717da36")

    def test_verify_short_sha_ok(self):
        rm.verify_short_sha("c717da36c51f94bc6051ec8954bed4ccec2b76fd", "c717da36")

    def test_verify_short_sha_mismatch_is_actionable(self):
        with self.assertRaises(rm.ManifestError):
            rm.verify_short_sha("c717da36c51f94bc6051ec8954bed4ccec2b76fd", "deadbeef")

    def test_verify_short_sha_wrong_length_is_actionable(self):
        with self.assertRaises(rm.ManifestError):
            rm.verify_short_sha("c717da36c51f94bc6051ec8954bed4ccec2b76fd", "c717da3")

    def test_verify_short_sha_wrong_case_is_actionable(self):
        with self.assertRaises(rm.ManifestError):
            rm.verify_short_sha("c717da36c51f94bc6051ec8954bed4ccec2b76fd", "C717DA36")

    def test_verify_short_sha_unknown_sentinel_is_actionable(self):
        """scripts/modernize/expansion_config.py's own no-git-metadata
        fallback build_commit is the literal sentinel "unknown" -- an
        embedded short-sha of "unknown" must never be silently accepted
        as if it were a real, resolved build identity."""
        with self.assertRaises(rm.ManifestError):
            rm.verify_short_sha("c717da36c51f94bc6051ec8954bed4ccec2b76fd", "unknown")

    def test_verify_short_sha_missing_is_actionable(self):
        with self.assertRaises(rm.ManifestError):
            rm.verify_short_sha("c717da36c51f94bc6051ec8954bed4ccec2b76fd", "")


class CandidateTagTests(unittest.TestCase):
    def test_valid_tag(self):
        self.assertEqual(rm.build_candidate_tag("0.1.0"), "v0.1.0")

    def test_pre_1_0_valid(self):
        self.assertEqual(rm.build_candidate_tag("0.10.20"), "v0.10.20")

    def test_invalid_version_string_rejected(self):
        with self.assertRaises(rm.ManifestError):
            rm.build_candidate_tag("not-a-version")

    def test_leading_zero_rejected(self):
        with self.assertRaises(rm.ManifestError):
            rm.build_candidate_tag("0.01.0")


class CheckSourceGuardTests(unittest.TestCase):
    """Regression coverage for the reviewer-reproduced trust defect
    (post-815a5a8a): a git worktree manifest's source_guard result must be
    deterministic and host-state-independent -- gitignored/untracked build
    byproducts (.dep/ output, a built ELF/ROM, etc.) sitting in the live
    worktree must never change it, while tracked violations and a genuine
    non-git closed-world candidate must still be denied exactly as
    before."""

    @staticmethod
    def _git(*args, cwd):
        result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
        assert result.returncode == 0, f"git {args} failed: {result.stderr}"

    @staticmethod
    def _write_allowlist(root: Path, paths) -> None:
        allow_dir = root / "docs" / "release_data"
        allow_dir.mkdir(parents=True, exist_ok=True)
        (allow_dir / "source_allowlist.json").write_text(
            json.dumps({"paths": list(paths)}), encoding="utf-8"
        )

    def test_git_worktree_ignores_untracked_dot_dep_and_elf_byproducts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._git("init", "-q", cwd=root)
            self._write_allowlist(root, ["src/main.c"])
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            self._git("add", "src/main.c", "docs", cwd=root)

            report_before = rm.check_source_guard(root)
            self.assertEqual(report_before["status"], "pass")
            self.assertEqual(report_before["violations"], [])

            # Inject harmless untracked/gitignored build byproducts a live
            # development worktree routinely accumulates.
            (root / ".dep").mkdir()
            (root / ".dep" / "main.o.d").write_text("main.o: src/main.c\n")
            (root / "fireemblem8.elf").write_bytes(b"\x7fELF" + b"\x00" * 32)

            report_after = rm.check_source_guard(root)
            self.assertEqual(report_after, report_before)

    def test_git_worktree_still_detects_tracked_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._git("init", "-q", cwd=root)
            self._write_allowlist(root, ["src/main.c", "src/bad.gba", "docs"])
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "src" / "bad.gba").write_bytes(b"\x00" * 16)
            self._git("add", "src", "docs", cwd=root)

            report = rm.check_source_guard(root)
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(any("bad.gba" in v for v in report["violations"]))

    def test_non_git_tree_closed_world_still_rejects_extra_content(self):
        """issue #9 exact-provenance/source-guard remediation: the
        allowlist is exact per-file -- a bare directory-shaped entry
        ("src") no longer authorizes anything nested under it, and an
        entirely foreign file (not a bare, otherwise-harmless empty
        directory, which contributes nothing to any archive) must still
        fail closed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_allowlist(root, ["src/main.c"])
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "evil").mkdir()
            (root / "evil" / "payload.c").write_text("int payload;")

            report = rm.check_source_guard(root)
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(
                any("evil/payload.c" in v and "not-allowlisted" in v for v in report["violations"])
            )

    def test_non_git_tree_closed_world_still_rejects_unsafe_nested_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_allowlist(root, ["src"])
            (root / "src").mkdir()
            (root / "src" / "sneaky.gba").write_bytes(b"\x00" * 32)

            report = rm.check_source_guard(root)
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(any("sneaky.gba" in v for v in report["violations"]))

    def test_real_repo_source_guard_unaffected_by_untracked_byproducts(self):
        """The reviewer's exact reproduction: run against this real
        worktree and confirm injecting a harmless untracked/gitignored
        top-level byproduct never changes the report."""
        report_before = rm.check_source_guard(ROOT)
        marker = ROOT / ".pua-issue9-regression-marker-dir"
        self.assertFalse(marker.exists(), "test fixture collided with real worktree state")
        try:
            marker.mkdir()
            (marker / "fake.elf").write_bytes(b"\x7fELF" + b"\x00" * 32)
            report_after = rm.check_source_guard(ROOT)
            self.assertEqual(report_after, report_before)
        finally:
            (marker / "fake.elf").unlink()
            marker.rmdir()


class RequiredDocsTests(unittest.TestCase):
    def test_all_present_on_real_repo(self):
        self.assertEqual(rm.check_required_docs(ROOT), [])

    def test_missing_doc_reported(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            missing = rm.check_required_docs(Path(tmp))
            self.assertTrue(missing)


class BuildManifestTests(unittest.TestCase):
    def test_real_repo_is_blocked_not_falsely_eligible(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertEqual(manifest["status"], "blocked")
        self.assertTrue(manifest["reasons"])
        self.assertNotEqual(manifest["status"], "mechanically eligible")

    def test_manifest_contains_full_and_short_sha(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertRegex(manifest["target_sha"], r"^[0-9a-f]{40}$")
        self.assertEqual(manifest["target_sha_short"], manifest["target_sha"][:8])

    def test_manifest_candidate_tag_matches_config_mk_version(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertEqual(manifest["candidate_tag"], f"v{manifest['version_string']}")

    def test_manifest_reports_provenance_and_source_guard_findings(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertEqual(manifest["provenance"]["status"], "blocked")
        self.assertTrue(manifest["provenance"]["reasons"])

    def test_manifest_migrations_ok_on_real_registry(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertTrue(manifest["migrations"]["ok"], manifest["migrations"]["errors"])

    def test_manifest_changelog_ok_on_real_changelog(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertTrue(manifest["changelog"]["ok"], manifest["changelog"]["errors"])

    def test_manifest_requires_exact_sha_for_archive_tree(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shutil.copy(ROOT / "config.mk", tmp_path / "config.mk")
            with self.assertRaises(rm.ManifestError) as ctx:
                rm.build_manifest(tmp_path, "release", "aapcs", "16M")
            self.assertIn("--target-sha", str(ctx.exception))

    def test_manifest_previous_next_supported_version_declared(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertIn("previous_supported_version", manifest)
        self.assertIn("next_supported_version", manifest)
        self.assertIsNone(manifest["previous_supported_version"])
        self.assertIsNone(manifest["next_supported_version"])

    def test_invalid_config_mk_is_actionable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "config.mk").write_text("EXPANSION_VERSION_MAJOR := 9999\n", encoding="utf-8")
            with self.assertRaises(ec.ConfigError):
                rm.build_manifest(
                    tmp_path, "release", "aapcs", "16M",
                    target_sha_override="c717da36c51f94bc6051ec8954bed4ccec2b76fd",
                )

    # --- issue #9 verifier remediation: new manifest sub-reports --------

    def test_manifest_includes_allowlist_report(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertIn("allowlist", manifest)
        self.assertIn("ok", manifest["allowlist"])

    def test_manifest_includes_version_ledger_report(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertIn("version_ledger", manifest)
        self.assertTrue(manifest["version_ledger"]["ok"], manifest["version_ledger"]["errors"])

    def test_manifest_includes_c_fallback_metadata_report(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertIn("c_fallback_metadata", manifest)
        self.assertTrue(manifest["c_fallback_metadata"]["ok"], manifest["c_fallback_metadata"]["errors"])

    def test_manifest_includes_migration_reachability_report(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertIn("migration_reachability", manifest)
        self.assertTrue(
            manifest["migration_reachability"]["ok"], manifest["migration_reachability"]["errors"]
        )

    def test_manifest_includes_rebuild_report_and_it_is_blocked_today(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertIn("rebuild", manifest)
        self.assertEqual(manifest["rebuild"]["status"], "blocked")

    def test_manifest_includes_doc_links_report_and_it_is_clean(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertIn("doc_links", manifest)
        self.assertTrue(manifest["doc_links"]["ok"], manifest["doc_links"]["errors"])


class RebuildStatusGatesEligibilityTests(unittest.TestCase):
    """issue #9 verifier remediation: the rebuild rehearsal's status must
    participate in the overall candidate status -- a rebuild that is not
    a verified success (blocked, not_run, or failed) must always force
    "blocked", even hypothetically if every *other* check were green.
    Exercised by mocking check_rebuild's dependency (archive_rehearsal's
    rebuild_rehearsal_blocker) directly, since forcing every other real
    check on this repository to pass would require actually resolving
    mgfembp's provenance -- exactly what must never happen here."""

    def _patched_manifest_reasons_for_rebuild_status(self, fake_rebuild_report):
        with mock.patch.object(rm.ar, "rebuild_rehearsal_blocker", return_value=fake_rebuild_report):
            return rm.build_manifest(ROOT, "release", "aapcs", "16M")

    def test_blocked_rebuild_contributes_reasons(self):
        manifest = self._patched_manifest_reasons_for_rebuild_status(
            {"status": "blocked", "reasons": ["synthetic-blocked-marker"]}
        )
        self.assertEqual(manifest["rebuild"]["status"], "blocked")
        self.assertIn("synthetic-blocked-marker", manifest["reasons"])
        self.assertEqual(manifest["status"], "blocked")

    def test_not_run_rebuild_contributes_reasons_and_blocks(self):
        manifest = self._patched_manifest_reasons_for_rebuild_status(
            {"status": "not_run", "reasons": ["synthetic-not-run-marker"]}
        )
        self.assertEqual(manifest["rebuild"]["status"], "not_run")
        self.assertIn("synthetic-not-run-marker", manifest["reasons"])
        self.assertEqual(manifest["status"], "blocked")

    def test_failed_rebuild_contributes_reasons_and_blocks(self):
        manifest = self._patched_manifest_reasons_for_rebuild_status(
            {"status": "failed", "reasons": ["synthetic-failed-marker"]}
        )
        self.assertEqual(manifest["rebuild"]["status"], "failed")
        self.assertIn("synthetic-failed-marker", manifest["reasons"])
        self.assertEqual(manifest["status"], "blocked")

    def test_verified_success_rebuild_adds_no_reasons_of_its_own(self):
        """A hypothetically-successful rebuild must not itself add any
        blocking reason -- the manifest may still be blocked overall for
        *other* (today, real) reasons, but never because of the rebuild."""
        manifest = self._patched_manifest_reasons_for_rebuild_status(
            {"status": "verified_success", "reasons": []}
        )
        self.assertEqual(manifest["rebuild"]["status"], "verified_success")
        self.assertNotIn("verified_success", " ".join(manifest["reasons"]))
        # Confirm no reason string originates from the rebuild dimension:
        for reason in manifest["reasons"]:
            self.assertNotIn("rebuild rehearsal status is", reason)


class NestedOuterRepositoryIdentityTests(unittest.TestCase):
    """issue #9 fresh-review remediation regression: build_manifest()'s
    own identity resolution (ec.load_identity -> resolve_build_commit)
    must never silently adopt an unrelated *outer* repository's HEAD as
    this candidate's build identity when repo_root is a non-git tree
    nested inside one -- the supplied exact --target-sha override must
    be the sole external build-identity source, threaded consistently
    into both `target_sha` and the (unpublished but internally-computed)
    embedded build-commit identity."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        outer = Path(cls.tmp.name) / "outer"
        outer.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(outer), check=True)
        subprocess.run(["git", "config", "user.email", "outer@example.invalid"], cwd=str(outer), check=True)
        subprocess.run(["git", "config", "user.name", "outer"], cwd=str(outer), check=True)
        (outer / "outer-file.txt").write_text("unrelated outer repository content\n")
        subprocess.run(["git", "add", "outer-file.txt"], cwd=str(outer), check=True)
        subprocess.run(["git", "commit", "-q", "-m", "outer commit"], cwd=str(outer), check=True)
        cls.outer_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(outer), capture_output=True, text=True, check=True,
        ).stdout.strip()

        cls.candidate = outer / "nested" / "candidate"
        cls.candidate.mkdir(parents=True)
        shutil.copy(ROOT / "config.mk", cls.candidate / "config.mk")
        cls.source_sha = "c717da36c51f94bc6051ec8954bed4ccec2b76fd"
        assert cls.outer_head != cls.source_sha

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_target_sha_is_the_supplied_override_never_the_outer_head(self):
        """resolve_target_sha() -- the single source of truth build_manifest()
        itself uses for `target_sha` -- must bind to the supplied exact
        override, never to `.git` upward-discovered from this non-git
        candidate's outer repository."""
        target_sha = rm.resolve_target_sha(self.candidate, self.source_sha)
        self.assertEqual(target_sha, self.source_sha)
        self.assertNotEqual(target_sha, self.outer_head)
        self.assertEqual(rm.derive_short_sha(target_sha), self.source_sha[:8])

    def test_target_sha_without_override_is_actionable_never_outer_head(self):
        """Without an override, this non-git nested candidate must raise
        the documented actionable --target-sha-required error -- never
        silently resolve (and adopt) the outer repository's HEAD."""
        with self.assertRaises(rm.ManifestError) as ctx:
            rm.resolve_target_sha(self.candidate, None)
        self.assertIn("--target-sha", str(ctx.exception))
        self.assertNotIn(self.outer_head, str(ctx.exception))

    def test_identity_build_commit_is_bound_to_the_supplied_override_not_outer_head(self):
        """The internally-resolved ExpansionIdentity used by
        build_manifest() must itself be bound to the exact supplied
        target SHA -- never independently re-derived via a second,
        unguarded `git rev-parse HEAD` call against `repo_root` (which,
        nested inside this outer repository, would otherwise adopt
        `outer_head` here)."""
        identity = ec.load_identity(
            config_mk_path=self.candidate / "config.mk",
            config_preset="release",
            abi="aapcs",
            rom_size="16M",
            repo_root=self.candidate,
            build_id_override=self.source_sha,
        )
        self.assertEqual(identity.build_commit, self.source_sha)
        self.assertNotEqual(identity.build_commit, self.outer_head)

    def test_no_git_call_leaks_outer_head_when_override_absent(self):
        """Defense-in-depth: even without any override threaded in,
        resolve_build_commit() itself must never adopt the outer
        repository's HEAD for this non-git candidate (see
        scripts/modernize/expansion_config.py's own guard)."""
        commit = ec.resolve_build_commit(None, self.candidate)
        self.assertEqual(commit, "unknown")
        self.assertNotEqual(commit, self.outer_head)


if __name__ == "__main__":
    unittest.main()
