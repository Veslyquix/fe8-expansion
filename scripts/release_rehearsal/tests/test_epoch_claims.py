"""Tests for scripts/release_rehearsal/epoch_claims.py (issue #9 verifier
remediation: stale save-compatibility-epoch claim regression guard)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import epoch_claims as ep  # noqa: E402


class CurrentEpochTests(unittest.TestCase):
    def test_real_repo_current_epoch_is_an_int(self):
        self.assertIsInstance(ep.current_epoch(ROOT), int)

    def test_real_repo_current_epoch_matches_config_mk(self):
        # config.mk's own EXPANSION_SAVE_COMPAT_EPOCH ?= value, read the
        # exact same way scripts/modernize/expansion_config.py's own
        # callers (modern.mk, manifest.py) do.
        import expansion_config as ec  # noqa: E402 (already on sys.path via epoch_claims)
        cfg = ec.parse_config_mk(ROOT / "config.mk")
        expected = ec.validate_save_compat_epoch(cfg["EXPANSION_SAVE_COMPAT_EPOCH"])
        self.assertEqual(ep.current_epoch(ROOT), expected)


class RealRepoIsCleanTests(unittest.TestCase):
    def test_real_repo_has_no_stale_epoch_claims(self):
        findings = ep.find_stale_epoch_claims(ROOT)
        self.assertEqual(findings, [], findings)

    def test_check_reports_ok_on_real_repo(self):
        report = ep.check(ROOT)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["errors"], [])

    def test_starter_content_header_no_longer_claims_epoch_stays_1(self):
        """Regression test for the exact known falsehood this module was
        built to catch: include/expansion_starter_content.h previously
        asserted "(EXPANSION_SAVE_COMPAT_EPOCH stays 1)" after issue #18
        sprint 2 bumped the live epoch to 2."""
        text = (ROOT / "include" / "expansion_starter_content.h").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"EPOCH\s+stays\s+1\b")


class StaleClaimDetectionTests(unittest.TestCase):
    """Synthetic fixtures -- proves the detector actually fires on the
    known falsehood shape, and stays silent on legitimate historical
    migration statements, independent of this repository's own live
    epoch value drifting in the future."""

    def _scan(self, text, epoch=2):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "fake_header.h"
            target.write_text(text, encoding="utf-8")
            return ep.find_stale_epoch_claims(tmp_path, ("fake_header.h",), epoch=epoch)

    def test_stays_n_falsehood_is_caught(self):
        findings = self._scan(" * (EXPANSION_SAVE_COMPAT_EPOCH stays 1).\n", epoch=2)
        self.assertEqual(len(findings), 1)
        self.assertIn("fake_header.h:1", findings[0])
        self.assertIn("claims", findings[0])

    def test_remains_n_falsehood_is_caught(self):
        findings = self._scan(" * save compat epoch remains 1 today.\n", epoch=2)
        self.assertEqual(len(findings), 1)

    def test_matching_current_value_is_never_flagged(self):
        findings = self._scan(" * (EXPANSION_SAVE_COMPAT_EPOCH stays 2).\n", epoch=2)
        self.assertEqual(findings, [])

    def test_historical_arrow_transition_statement_is_never_flagged(self):
        findings = self._scan(
            " * Bump EXPANSION_SAVE_COMPAT_EPOCH 1 -> 2 for issue #18 sprint 2.\n", epoch=2,
        )
        self.assertEqual(findings, [])

    def test_historical_from_to_transition_statement_is_never_flagged(self):
        findings = self._scan(
            " * Bump EXPANSION_SAVE_COMPAT_EPOCH and SAVE_FORMAT_VERSION_CURRENT from 1 to 2.\n",
            epoch=2,
        )
        self.assertEqual(findings, [])

    def test_no_epoch_bump_prose_without_a_literal_stale_number_is_never_flagged(self):
        findings = self._scan(
            " * Save format: untouched. No new save field, no epoch bump.\n", epoch=2,
        )
        self.assertEqual(findings, [])

    def test_unrelated_prose_mentioning_epoch_keyword_without_a_claim_verb_is_never_flagged(self):
        findings = self._scan(
            " * See docs/save_format.md for EXPANSION_SAVE_COMPAT_EPOCH details.\n", epoch=2,
        )
        self.assertEqual(findings, [])

    def test_missing_target_file_is_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            findings = ep.find_stale_epoch_claims(Path(tmp), ("does/not/exist.h",), epoch=2)
        self.assertEqual(findings, [])


class CanonicalTableDefaultTests(unittest.TestCase):
    """Fresh-review remediation: docs/config_identity.md's own
    "Settings reference" table documents EXPANSION_SAVE_COMPAT_EPOCH's
    *Default* column as a plain, present-tense table cell -- no
    "stays"/"remains" claim verb at all -- so it needs its own, narrow
    structural cross-check (never a broadened regex that would risk
    flagging legitimate historical migration prose elsewhere)."""

    def _scan_canonical_table(self, default_cell: str, epoch: int):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "config_identity.md"
            target.write_text(
                "# Framework configuration and ROM identity (issue #8)\n\n"
                "| Setting | Constraint | Default | Affects |\n"
                "| --- | --- | --- | --- |\n"
                f"| `EXPANSION_SAVE_COMPAT_EPOCH` | integer, `[0, 65535]` | {default_cell} "
                "| save-format compatibility gate |\n",
                encoding="utf-8",
            )
            return ep.find_stale_epoch_claims(tmp_path, ("config_identity.md",), epoch=epoch)

    def test_stale_canonical_table_default_1_is_caught_when_live_epoch_is_2(self):
        """The exact fresh-review finding: the canonical table's Default
        column says `1` while the live epoch is `2`."""
        findings = self._scan_canonical_table("`1`", epoch=2)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("config_identity.md:5", findings[0])
        self.assertIn("canonical settings-reference table", findings[0])
        self.assertIn("currently 1", findings[0])
        self.assertIn("live config.mk value is 2", findings[0])

    def test_current_canonical_table_default_2_passes(self):
        findings = self._scan_canonical_table("`2`", epoch=2)
        self.assertEqual(findings, [])

    def test_real_repo_canonical_table_default_matches_live_epoch(self):
        """The real docs/config_identity.md itself, scanned exactly the
        way DEFAULT_TARGETS does it -- proves the actual fix (not merely
        a synthetic fixture)."""
        findings = ep.find_stale_epoch_claims(ROOT, ("docs/config_identity.md",))
        self.assertEqual(findings, [], findings)

    def test_real_repo_config_identity_is_in_default_targets(self):
        self.assertIn("docs/config_identity.md", ep.DEFAULT_TARGETS)

    def test_historical_1_to_2_prose_elsewhere_in_the_same_doc_still_passes(self):
        """A historical migration sentence living in the very same file
        (as docs/config_identity.md's own prose does, just below its own
        table) must never be flagged -- only the canonical table row's
        own Default column is semantically checked."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "config_identity.md"
            target.write_text(
                "| Setting | Constraint | Default | Affects |\n"
                "| --- | --- | --- | --- |\n"
                "| `EXPANSION_SAVE_COMPAT_EPOCH` | integer, `[0, 65535]` | `2` "
                "| save-format compatibility gate |\n\n"
                "`EXPANSION_SAVE_COMPAT_EPOCH` has been bumped once, from `1` to `2`, "
                "for issue #18 sprint 2.\n",
                encoding="utf-8",
            )
            findings = ep.find_stale_epoch_claims(tmp_path, ("config_identity.md",), epoch=2)
        self.assertEqual(findings, [])

    def test_canonical_table_check_never_applies_to_a_differently_named_file(self):
        """The structural table check is scoped by exact filename -- a
        different file with an identically-shaped stale table row is
        untouched by it (broad, file-name-independent table scanning is
        deliberately out of scope here)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "unrelated_table.md"
            target.write_text(
                "| Setting | Constraint | Default | Affects |\n"
                "| --- | --- | --- | --- |\n"
                "| `EXPANSION_SAVE_COMPAT_EPOCH` | integer, `[0, 65535]` | `1` "
                "| save-format compatibility gate |\n",
                encoding="utf-8",
            )
            findings = ep.find_stale_epoch_claims(tmp_path, ("unrelated_table.md",), epoch=2)
        self.assertEqual(findings, [])

    def test_table_row_with_no_parseable_default_is_never_flagged(self):
        findings = self._scan_canonical_table("`n/a`", epoch=2)
        self.assertEqual(findings, [])

    def test_check_reports_the_stale_canonical_table_default_too(self):
        """The `check()` manifest-shaped entry point (used by
        manifest.py's check_epoch_claims) must surface this finding as
        well -- not merely the lower-level find_stale_epoch_claims().
        Uses the real repo's own config.mk (copied verbatim, live epoch
        2) so `check()`'s own `current_epoch()` resolution is exercised
        for real, not stubbed."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "config.mk").write_text(
                (ROOT / "config.mk").read_text(encoding="utf-8"), encoding="utf-8",
            )
            (tmp_path / "config_identity.md").write_text(
                "| Setting | Constraint | Default | Affects |\n"
                "| --- | --- | --- | --- |\n"
                "| `EXPANSION_SAVE_COMPAT_EPOCH` | integer, `[0, 65535]` | `1` "
                "| save-format compatibility gate |\n",
                encoding="utf-8",
            )
            report = ep.check(tmp_path, ("config_identity.md",))
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["errors"]), 1)


class CliTests(unittest.TestCase):
    def test_main_exit_zero_on_real_repo(self):
        self.assertEqual(ep.main(["--repo-root", str(ROOT)]), 0)

    def test_main_exit_one_on_synthetic_stale_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "config.mk").write_text(
                (ROOT / "config.mk").read_text(encoding="utf-8"), encoding="utf-8",
            )
            stale = tmp_path / "stale.h"
            stale.write_text(" * (EXPANSION_SAVE_COMPAT_EPOCH stays 1).\n", encoding="utf-8")
            self.assertEqual(
                ep.main(["--repo-root", str(tmp_path), "stale.h"]), 1,
            )


if __name__ == "__main__":
    unittest.main()
