"""Tests for scripts/release_rehearsal/manifest.py (issue #9)."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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


class CheckExternalAttestationTests(unittest.TestCase):
    """issue #9 mandatory correction #5: external/human attestation must
    remain outside candidate control. `check_external_attestation()`
    takes no arguments at all and always reports the same fixed
    "missing" substatus -- there is no in-repo mechanism (file, secret,
    flag, environment variable) that could ever change it."""

    def test_always_reports_missing(self):
        report = rm.check_external_attestation()
        self.assertEqual(report["status"], "missing")
        self.assertNotEqual(report["status"], "present")
        self.assertNotEqual(report["status"], "mechanically eligible")

    def test_always_reports_a_reason(self):
        report = rm.check_external_attestation()
        self.assertTrue(report["reasons"])
        self.assertTrue(any("external" in r and "attestation" in r for r in report["reasons"]))

    def test_takes_no_arguments(self):
        """There is no parameter at all this in-repo caller could ever
        supply to influence the result -- the function signature itself
        proves there is no candidate-controlled input path."""
        import inspect
        signature = inspect.signature(rm.check_external_attestation)
        self.assertEqual(len(signature.parameters), 0)

    def test_deterministic_across_repeated_calls(self):
        self.assertEqual(rm.check_external_attestation(), rm.check_external_attestation())


class ExternalAttestationCannotBeSatisfiedByInRepoDataTests(unittest.TestCase):
    """The strongest, most direct proof of issue #9 mandatory correction
    #5: even when *every other* sub-check is mocked to a fully-passing,
    synthetic "everything is fine" shape, the overall candidate status
    must still be exactly "blocked" -- solely because of the missing
    external attestation. No synthetic data, in-repo file, or candidate-
    controlled flag can ever flip this."""

    def _fully_passing_manifest(self, embedded_short_sha="__AUTO__"):
        """`embedded_short_sha` defaults to the one remaining fact this
        helper cannot mock away without defeating its own purpose: the
        real, live target SHA's own correct derived short form (issue #9
        verifier remediation added this as a second, equally
        never-mockable-away mandatory binding -- see
        `EmbeddedIdentityBindingMandatoryTests` below for the class that
        isolates *that* one instead). Pass `None` explicitly to instead
        prove the identity-binding reason alone surfaces here too."""
        target_sha = rm.resolve_target_sha(ROOT, None)
        if embedded_short_sha == "__AUTO__":
            embedded_short_sha = rm.derive_short_sha(target_sha)
        with mock.patch.object(rm, "check_required_docs", return_value=[]), \
             mock.patch.object(rm, "check_changelog", return_value={"ok": True, "errors": [], "aggregate_impact": "none"}), \
             mock.patch.object(rm, "check_provenance", return_value={"status": "mechanically eligible", "reasons": []}), \
             mock.patch.object(rm, "check_source_guard", return_value={"status": "pass", "violations": []}), \
             mock.patch.object(rm, "check_migrations", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_allowlist", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_tree_coverage", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_submodule_binding", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_version_ledger_and_semver", return_value={"ok": True, "errors": [], "ledger": {}}), \
             mock.patch.object(rm, "check_c_fallback", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_migration_reachability", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_doc_links", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_epoch_claims", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_rebuild", return_value={"status": rm.ar.REBUILD_STATUS_VERIFIED_SUCCESS, "reasons": []}):
            return rm.build_manifest(ROOT, "release", "aapcs", "16M", embedded_short_sha=embedded_short_sha)

    def test_overall_status_remains_blocked_even_with_everything_else_synthetically_passing(self):
        manifest = self._fully_passing_manifest()
        self.assertEqual(manifest["status"], "blocked")
        self.assertNotEqual(manifest["status"], "mechanically eligible")

    def test_the_only_remaining_reason_is_the_external_attestation_one(self):
        manifest = self._fully_passing_manifest()
        self.assertTrue(any("external" in r and "attestation" in r for r in manifest["reasons"]))
        # every OTHER dimension was mocked to a clean/passing shape, so no
        # other reason should have leaked through
        other_reasons = [r for r in manifest["reasons"] if "attestation" not in r]
        self.assertEqual(other_reasons, [])

    def test_external_attestation_substatus_is_missing_in_the_report(self):
        manifest = self._fully_passing_manifest()
        self.assertEqual(manifest["external_attestation"]["status"], "missing")

    def test_require_eligible_still_exits_non_eligible_even_when_everything_else_passes(self):
        """A pipeline demanding --require-eligible must still see this
        candidate as not eligible -- exactly like `cli.py`'s own
        `_apply_status_gates` reads `manifest["status"]` directly."""
        manifest = self._fully_passing_manifest()
        self.assertNotEqual(manifest["status"], "mechanically eligible")


class EmbeddedIdentityBindingMandatoryTests(unittest.TestCase):
    """issue #9 verifier remediation: symmetric to
    `ExternalAttestationCannotBeSatisfiedByInRepoDataTests` above --
    proves the *other* newly-mandatory, never-optional binding
    (embedded_short_sha) is equally un-mockable-away. Reuses the same
    fully-passing synthetic fixture (including a real, present external
    attestation this time -- mocked True here only to isolate this one
    dimension), so the only possible remaining reason is this module's
    own identity-binding one."""

    def _fully_passing_manifest_except_identity_binding(self):
        with mock.patch.object(rm, "check_required_docs", return_value=[]), \
             mock.patch.object(rm, "check_changelog", return_value={"ok": True, "errors": [], "aggregate_impact": "none"}), \
             mock.patch.object(rm, "check_provenance", return_value={"status": "mechanically eligible", "reasons": []}), \
             mock.patch.object(rm, "check_source_guard", return_value={"status": "pass", "violations": []}), \
             mock.patch.object(rm, "check_migrations", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_allowlist", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_tree_coverage", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_submodule_binding", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_external_attestation", return_value={"status": "present", "reasons": []}), \
             mock.patch.object(rm, "check_version_ledger_and_semver", return_value={"ok": True, "errors": [], "ledger": {}}), \
             mock.patch.object(rm, "check_c_fallback", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_migration_reachability", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_doc_links", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_epoch_claims", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_rebuild", return_value={"status": rm.ar.REBUILD_STATUS_VERIFIED_SUCCESS, "reasons": []}):
            # embedded_short_sha deliberately omitted (defaults to None) --
            # the one fact this test isolates as still-missing.
            return rm.build_manifest(ROOT, "release", "aapcs", "16M")

    def test_overall_status_remains_blocked_solely_from_missing_identity_binding(self):
        manifest = self._fully_passing_manifest_except_identity_binding()
        self.assertEqual(manifest["status"], "blocked")
        self.assertNotEqual(manifest["status"], "mechanically eligible")

    def test_the_only_remaining_reason_is_the_identity_binding_one(self):
        manifest = self._fully_passing_manifest_except_identity_binding()
        self.assertTrue(any("embedded short-form build commit" in r for r in manifest["reasons"]))
        other_reasons = [r for r in manifest["reasons"] if "embedded short-form build commit" not in r]
        self.assertEqual(other_reasons, [])

    def test_identity_binding_substatus_is_not_ok_in_the_report(self):
        manifest = self._fully_passing_manifest_except_identity_binding()
        self.assertFalse(manifest["identity_binding"]["ok"])
        self.assertIsNone(manifest["embedded_short_sha"])

    def test_supplying_a_correct_embedded_short_sha_clears_this_one_reason(self):
        """Positive control: supplying the exact correct short SHA (the
        first 8 hex chars of the real, live target SHA) makes this
        candidate's identity binding itself report ok -- proving the
        mandatory check is a real, satisfiable gate, never a permanent
        dead end."""
        target_sha = rm.resolve_target_sha(ROOT, None)
        correct_short = rm.derive_short_sha(target_sha)
        with mock.patch.object(rm, "check_required_docs", return_value=[]), \
             mock.patch.object(rm, "check_changelog", return_value={"ok": True, "errors": [], "aggregate_impact": "none"}), \
             mock.patch.object(rm, "check_provenance", return_value={"status": "mechanically eligible", "reasons": []}), \
             mock.patch.object(rm, "check_source_guard", return_value={"status": "pass", "violations": []}), \
             mock.patch.object(rm, "check_migrations", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_allowlist", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_tree_coverage", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_submodule_binding", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_external_attestation", return_value={"status": "present", "reasons": []}), \
             mock.patch.object(rm, "check_version_ledger_and_semver", return_value={"ok": True, "errors": [], "ledger": {}}), \
             mock.patch.object(rm, "check_c_fallback", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_migration_reachability", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_doc_links", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_epoch_claims", return_value={"ok": True, "errors": []}), \
             mock.patch.object(rm, "check_rebuild", return_value={"status": rm.ar.REBUILD_STATUS_VERIFIED_SUCCESS, "reasons": []}):
            manifest = rm.build_manifest(
                ROOT, "release", "aapcs", "16M", embedded_short_sha=correct_short,
            )
        self.assertEqual(manifest["status"], "mechanically eligible")
        self.assertTrue(manifest["identity_binding"]["ok"])
        self.assertEqual(manifest["embedded_short_sha"], correct_short)

    def test_mismatched_embedded_short_sha_is_an_actionable_tooling_error_not_a_soft_reason(self):
        """A *supplied-but-wrong* embedded_short_sha is a distinct,
        stronger failure mode than merely "missing" -- it must never be
        silently folded into "blocked" as if it were just another
        unresolved fact; verify_short_sha() raises before build_manifest
        gets anywhere near computing reasons/status at all."""
        with self.assertRaises(rm.ManifestError):
            rm.build_manifest(ROOT, "release", "aapcs", "16M", embedded_short_sha="deadbeef")



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

    def test_manifest_includes_epoch_claims_report_and_it_is_clean(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertIn("epoch_claims", manifest)
        self.assertTrue(manifest["epoch_claims"]["ok"], manifest["epoch_claims"]["errors"])

    def test_manifest_includes_identity_binding_report_missing_by_default(self):
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertIn("identity_binding", manifest)
        self.assertFalse(manifest["identity_binding"]["ok"])
        self.assertIsNone(manifest["embedded_short_sha"])


class VersionLedgerManifestWiringTests(unittest.TestCase):
    """issue #9 residual-hardening: a fresh, independent verifier
    reproduced the version-ledger topology gaps directly against the
    *live manifest path* (`scripts/release_rehearsal/manifest.py`'s own
    `check_version_ledger_and_semver`, exactly what `build_manifest` --
    and therefore `make release-check`/`make release-rehearse` -- calls),
    not merely `consistency.check_version_ledger()` in isolation (see
    scripts/release_rehearsal/tests/test_consistency.py's
    `VersionLedgerTests` for that isolated coverage). These tests call
    the actual manifest-layer function so a regression that only wires
    `consistency.py` back up to some *other*, unused helper would still
    be caught here."""

    @staticmethod
    def _identity(version_string="0.1.0"):
        major = int(version_string.split(".")[0])
        return SimpleNamespace(version_string=version_string, version_major=major)

    @staticmethod
    def _write_ledger(repo_root: Path, ledger: dict) -> None:
        release_data = repo_root / "docs" / "release_data"
        release_data.mkdir(parents=True, exist_ok=True)
        (release_data / "version_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")

    def test_live_manifest_path_rejects_current_entry_with_eol(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_ledger(root, {
                "current_version": "0.1.0",
                "previous_supported_version": None,
                "next_supported_version": None,
                "supported": [{"version": "0.1.0", "status": "current", "eol": "2024-01-01"}],
            })
            report = rm.check_version_ledger_and_semver(root, self._identity(), {"aggregate_impact": "none"})
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("status:'current'" in error and "eol" in error.lower() for error in report["errors"]),
                report["errors"],
            )

    def test_live_manifest_path_rejects_previous_supported_version_absent_from_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_ledger(root, {
                "current_version": "0.1.0",
                "previous_supported_version": "0.0.9",
                "next_supported_version": None,
                "supported": [{"version": "0.1.0", "status": "current", "eol": None}],
            })
            report = rm.check_version_ledger_and_semver(root, self._identity(), {"aggregate_impact": "none"})
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("previous_supported_version" in error and "0.0.9" in error and "does not appear" in error
                    for error in report["errors"]),
                report["errors"],
            )

    def test_live_manifest_path_rejects_next_supported_version_absent_from_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_ledger(root, {
                "current_version": "0.1.0",
                "previous_supported_version": None,
                "next_supported_version": "0.2.0",
                "supported": [{"version": "0.1.0", "status": "current", "eol": None}],
            })
            report = rm.check_version_ledger_and_semver(root, self._identity(), {"aggregate_impact": "none"})
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("next_supported_version" in error and "0.2.0" in error and "does not appear" in error
                    for error in report["errors"]),
                report["errors"],
            )

    def test_live_manifest_path_rejects_next_supported_version_status_eol(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_ledger(root, {
                "current_version": "0.1.0",
                "previous_supported_version": None,
                "next_supported_version": "0.2.0",
                "supported": [
                    {"version": "0.1.0", "status": "current", "eol": None},
                    {"version": "0.2.0", "status": "eol", "eol": "2024-01-01"},
                ],
            })
            report = rm.check_version_ledger_and_semver(root, self._identity(), {"aggregate_impact": "none"})
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("next_supported_version" in error and "not a compatible status" in error
                    for error in report["errors"]),
                report["errors"],
            )

    def test_live_manifest_path_accepts_valid_full_topology(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_ledger(root, {
                "current_version": "0.1.0",
                "previous_supported_version": "0.0.9",
                "next_supported_version": "0.2.0",
                "supported": [
                    {"version": "0.0.9", "status": "eol", "eol": "2024-01-01"},
                    {"version": "0.1.0", "status": "current", "eol": None},
                    {"version": "0.2.0", "status": "supported", "eol": None},
                ],
            })
            report = rm.check_version_ledger_and_semver(root, self._identity(), {"aggregate_impact": "none"})
            self.assertEqual(report["errors"], [])
            self.assertTrue(report["ok"])

    def test_real_repo_ledger_passes_through_the_live_manifest_path(self):
        """The real, live docs/release_data/version_ledger.json (today:
        previous/next both null) must still cleanly pass through this
        exact manifest-layer function -- hardening must never turn into
        a false positive against this repository's own honest ledger."""
        manifest = rm.build_manifest(ROOT, "release", "aapcs", "16M")
        self.assertEqual(manifest["version_ledger"]["errors"], [])
        self.assertTrue(manifest["version_ledger"]["ok"])


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
