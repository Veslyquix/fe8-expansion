"""Tests for scripts/release_rehearsal/manifest.py (issue #9)."""

import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
