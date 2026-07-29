"""Tests for scripts/release_rehearsal/manifest.py (issue #9)."""

import json
import subprocess
import sys
import tempfile
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
            self._write_allowlist(root, ["src", "docs"])
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
            self._write_allowlist(root, ["src", "docs"])
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "src" / "bad.gba").write_bytes(b"\x00" * 16)
            self._git("add", "src", "docs", cwd=root)

            report = rm.check_source_guard(root)
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(any("bad.gba" in v for v in report["violations"]))

    def test_non_git_tree_closed_world_still_rejects_extra_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_allowlist(root, ["src"])
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("int main(void){return 0;}")
            (root / "evil").mkdir()

            report = rm.check_source_guard(root)
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(
                any("evil" in v and "not-allowlisted" in v for v in report["violations"])
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


if __name__ == "__main__":
    unittest.main()
