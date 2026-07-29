"""Tests for scripts/release_rehearsal/consistency.py (issue #9)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "modernize"))

import expansion_config as ec  # noqa: E402

from scripts.release_rehearsal import consistency as cc
from scripts.modernize.migrations.registry import MigrationStep, MECHANICAL


def _valid_ledger(**overrides):
    ledger = {
        "current_version": "0.1.0",
        "previous_supported_version": None,
        "next_supported_version": None,
        "supported": [{"version": "0.1.0", "status": "current", "eol": None}],
    }
    ledger.update(overrides)
    return ledger


class VersionLedgerTests(unittest.TestCase):
    def test_valid_ledger_has_no_errors(self):
        self.assertEqual(cc.check_version_ledger(_valid_ledger(), "0.1.0"), [])

    def test_missing_keys_reported(self):
        errors = cc.check_version_ledger({}, "0.1.0")
        self.assertEqual(len(errors), 1)
        self.assertIn("missing required key", errors[0])

    def test_invalid_current_version_format(self):
        errors = cc.check_version_ledger(_valid_ledger(current_version="v1"), "0.1.0")
        self.assertTrue(any("not a valid" in error for error in errors))

    def test_candidate_version_mismatch_with_ledger(self):
        errors = cc.check_version_ledger(_valid_ledger(), "0.2.0")
        self.assertTrue(any("does not match" in error and "0.2.0" in error for error in errors))

    def test_duplicate_supported_versions_rejected(self):
        ledger = _valid_ledger(supported=[
            {"version": "0.1.0", "status": "current", "eol": None},
            {"version": "0.1.0", "status": "eol", "eol": "2020-01-01"},
        ])
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(any("duplicate" in error for error in errors))

    def test_no_current_status_entry_rejected(self):
        ledger = _valid_ledger(supported=[{"version": "0.1.0", "status": "supported", "eol": None}])
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(any("exactly one status:'current'" in error for error in errors))

    def test_two_current_status_entries_rejected(self):
        ledger = _valid_ledger(supported=[
            {"version": "0.1.0", "status": "current", "eol": None},
            {"version": "0.2.0", "status": "current", "eol": None},
        ])
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(any("exactly one status:'current'" in error for error in errors))

    def test_invalid_status_value_rejected(self):
        ledger = _valid_ledger(supported=[{"version": "0.1.0", "status": "bogus", "eol": None}])
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(any("not in" in error for error in errors))

    def test_invalid_eol_date_rejected(self):
        ledger = _valid_ledger(supported=[{"version": "0.1.0", "status": "current", "eol": "not-a-date"}])
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(any("eol" in error for error in errors))

    def test_previous_not_less_than_current_rejected(self):
        ledger = _valid_ledger(previous_supported_version="0.2.0", current_version="0.1.0",
                                supported=[{"version": "0.1.0", "status": "current", "eol": None}])
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(any("previous_supported_version must be less than" in error for error in errors))

    def test_next_not_greater_than_current_rejected(self):
        ledger = _valid_ledger(next_supported_version="0.0.5")
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(any("next_supported_version must be greater than" in error for error in errors))

    def test_previous_equals_current_rejected(self):
        ledger = _valid_ledger(previous_supported_version="0.1.0")
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(any("must not equal current_version" in error for error in errors))

    def test_previous_equals_next_rejected(self):
        ledger = _valid_ledger(previous_supported_version="0.0.9", next_supported_version="0.0.9",
                                current_version="0.1.0",
                                supported=[
                                    {"version": "0.0.9", "status": "eol", "eol": "2020-01-01"},
                                    {"version": "0.1.0", "status": "current", "eol": None},
                                ])
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(any("must not be equal" in error for error in errors))

    def test_valid_full_topology(self):
        ledger = _valid_ledger(
            previous_supported_version="0.0.9", current_version="0.1.0", next_supported_version="0.2.0",
            supported=[
                {"version": "0.0.9", "status": "eol", "eol": "2024-01-01"},
                {"version": "0.1.0", "status": "current", "eol": None},
            ],
        )
        self.assertEqual(cc.check_version_ledger(ledger, "0.1.0"), [])

    def test_real_ledger_is_consistent_with_config_mk(self):
        import json
        ledger = json.loads((ROOT / "docs" / "release_data" / "version_ledger.json").read_text())
        config_values = ec.parse_config_mk(ROOT / "config.mk")
        candidate_version = f"{config_values['EXPANSION_VERSION_MAJOR']}.{config_values['EXPANSION_VERSION_MINOR']}.{config_values['EXPANSION_VERSION_PATCH']}"
        self.assertEqual(cc.check_version_ledger(ledger, candidate_version), [])


class ClassifyBumpTests(unittest.TestCase):
    def test_initial_when_no_previous(self):
        self.assertEqual(cc.classify_bump(None, "0.1.0"), "initial")

    def test_none_when_equal(self):
        self.assertEqual(cc.classify_bump("0.1.0", "0.1.0"), "none")

    def test_patch_bump(self):
        self.assertEqual(cc.classify_bump("0.1.0", "0.1.1"), "patch")

    def test_minor_bump(self):
        self.assertEqual(cc.classify_bump("0.1.0", "0.2.0"), "minor")

    def test_major_bump(self):
        self.assertEqual(cc.classify_bump("0.9.0", "1.0.0"), "major")

    def test_regression_raises(self):
        with self.assertRaises(cc.ConsistencyError):
            cc.classify_bump("0.2.0", "0.1.0")


class RequiredMinimumBumpRankTests(unittest.TestCase):
    def test_pre_1_0_major_collapses_to_minor(self):
        self.assertEqual(
            cc.required_minimum_bump_rank("major", pre_1_0=True), cc.BUMP_RANK["minor"]
        )

    def test_post_1_0_major_requires_major(self):
        self.assertEqual(
            cc.required_minimum_bump_rank("major", pre_1_0=False), cc.BUMP_RANK["major"]
        )

    def test_minor_requires_minor_regardless_of_era(self):
        self.assertEqual(cc.required_minimum_bump_rank("minor", pre_1_0=True), cc.BUMP_RANK["minor"])
        self.assertEqual(cc.required_minimum_bump_rank("minor", pre_1_0=False), cc.BUMP_RANK["minor"])

    def test_none_requires_nothing(self):
        self.assertEqual(cc.required_minimum_bump_rank("none", pre_1_0=True), 0)


class ChangelogSemverDeltaTests(unittest.TestCase):
    def test_initial_version_has_no_errors_regardless_of_impact(self):
        self.assertEqual(cc.check_changelog_semver_delta(None, "0.1.0", "major", 0), [])

    def test_pre_1_0_major_impact_satisfied_by_minor_bump(self):
        self.assertEqual(cc.check_changelog_semver_delta("0.1.0", "0.2.0", "major", 0), [])

    def test_pre_1_0_major_impact_violated_by_patch_bump(self):
        errors = cc.check_changelog_semver_delta("0.1.0", "0.1.1", "major", 0)
        self.assertTrue(errors)
        self.assertIn("minor", errors[0])

    def test_pre_1_0_minor_impact_violated_by_no_bump(self):
        errors = cc.check_changelog_semver_delta("0.1.0", "0.1.0", "minor", 0)
        self.assertTrue(errors)

    def test_pre_1_0_patch_impact_satisfied_by_patch_bump(self):
        self.assertEqual(cc.check_changelog_semver_delta("0.1.0", "0.1.1", "patch", 0), [])

    def test_pre_1_0_none_impact_never_errors(self):
        self.assertEqual(cc.check_changelog_semver_delta("0.1.0", "0.1.0", "none", 0), [])
        self.assertEqual(cc.check_changelog_semver_delta("0.1.0", "0.5.0", "none", 0), [])

    def test_post_1_0_major_impact_violated_by_minor_bump(self):
        errors = cc.check_changelog_semver_delta("1.0.0", "1.1.0", "major", 1)
        self.assertTrue(errors)

    def test_post_1_0_major_impact_satisfied_by_major_bump(self):
        self.assertEqual(cc.check_changelog_semver_delta("1.0.0", "2.0.0", "major", 1), [])

    def test_bumping_more_than_required_is_fine(self):
        self.assertEqual(cc.check_changelog_semver_delta("0.1.0", "0.2.0", "patch", 0), [])

    def test_version_regression_reported(self):
        errors = cc.check_changelog_semver_delta("0.2.0", "0.1.0", "none", 0)
        self.assertTrue(errors)
        self.assertIn("greater than", errors[0])


class CFallbackMetadataTests(unittest.TestCase):
    HEADER_TEMPLATE = '''#ifndef GUARD_EXPANSION_CONFIG_H
#define GUARD_EXPANSION_CONFIG_H
#ifndef FE8_EXPANSION_VERSION_MAJOR
#define FE8_EXPANSION_VERSION_MAJOR {major}
#endif
#ifndef FE8_EXPANSION_VERSION_MINOR
#define FE8_EXPANSION_VERSION_MINOR {minor}
#endif
#ifndef FE8_EXPANSION_VERSION_PATCH
#define FE8_EXPANSION_VERSION_PATCH {patch}
#endif
#ifndef FE8_EXPANSION_VERSION_STRING
#define FE8_EXPANSION_VERSION_STRING "{version_string}"
#endif
#ifndef FE8_EXPANSION_ROM_TITLE
#define FE8_EXPANSION_ROM_TITLE "{rom_title}"
#endif
#ifndef FE8_EXPANSION_ROM_GAME_CODE
#define FE8_EXPANSION_ROM_GAME_CODE "{rom_game_code}"
#endif
#ifndef FE8_EXPANSION_ROM_MAKER_CODE
#define FE8_EXPANSION_ROM_MAKER_CODE "{rom_maker_code}"
#endif
#ifndef FE8_EXPANSION_ROM_REVISION
#define FE8_EXPANSION_ROM_REVISION {rom_revision}
#endif
#ifndef FE8_EXPANSION_SAVE_COMPAT_EPOCH
#define FE8_EXPANSION_SAVE_COMPAT_EPOCH {epoch}
#endif
#ifndef FE8_EXPANSION_CONFIG_FINGERPRINT
#define FE8_EXPANSION_CONFIG_FINGERPRINT "{fingerprint}"
#endif
#endif
'''

    CONFIG_VALUES = {
        "EXPANSION_VERSION_MAJOR": "0",
        "EXPANSION_VERSION_MINOR": "1",
        "EXPANSION_VERSION_PATCH": "0",
        "EXPANSION_ROM_TITLE": "FIREEMBLEM2E",
        "EXPANSION_ROM_GAME_CODE": "BE8E",
        "EXPANSION_ROM_MAKER_CODE": "01",
        "EXPANSION_ROM_REVISION": "0",
        "EXPANSION_SAVE_COMPAT_EPOCH": "1",
    }

    def _write_header(self, tmp_path, **overrides):
        fields = {
            "major": "0", "minor": "1", "patch": "0", "version_string": "0.1.0",
            "rom_title": "FIREEMBLEM2E", "rom_game_code": "BE8E", "rom_maker_code": "01",
            "rom_revision": "0", "epoch": "1", "fingerprint": "0" * 16,
        }
        fields.update(overrides)
        include_dir = tmp_path / "include"
        include_dir.mkdir(parents=True, exist_ok=True)
        (include_dir / "expansion_config.h").write_text(self.HEADER_TEMPLATE.format(**fields), encoding="utf-8")

    def test_consistent_header_has_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._write_header(tmp_path)
            self.assertEqual(cc.check_c_fallback_metadata(tmp_path, self.CONFIG_VALUES), [])

    def test_version_major_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._write_header(tmp_path, major="9")
            errors = cc.check_c_fallback_metadata(tmp_path, self.CONFIG_VALUES)
            self.assertTrue(any("FE8_EXPANSION_VERSION_MAJOR" in error for error in errors))

    def test_version_string_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._write_header(tmp_path, version_string="9.9.9")
            errors = cc.check_c_fallback_metadata(tmp_path, self.CONFIG_VALUES)
            self.assertTrue(any("FE8_EXPANSION_VERSION_STRING" in error for error in errors))

    def test_rom_title_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._write_header(tmp_path, rom_title="WRONGTITLE")
            errors = cc.check_c_fallback_metadata(tmp_path, self.CONFIG_VALUES)
            self.assertTrue(any("FE8_EXPANSION_ROM_TITLE" in error for error in errors))

    def test_save_compat_epoch_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._write_header(tmp_path, epoch="99")
            errors = cc.check_c_fallback_metadata(tmp_path, self.CONFIG_VALUES)
            self.assertTrue(any("FE8_EXPANSION_SAVE_COMPAT_EPOCH" in error for error in errors))

    def test_malformed_fingerprint_shape_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._write_header(tmp_path, fingerprint="NOTHEX!!")
            errors = cc.check_c_fallback_metadata(tmp_path, self.CONFIG_VALUES)
            self.assertTrue(any("FE8_EXPANSION_CONFIG_FINGERPRINT" in error for error in errors))

    def test_missing_header_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            errors = cc.check_c_fallback_metadata(Path(tmp), self.CONFIG_VALUES)
            self.assertTrue(errors)
            self.assertIn("not found", errors[0])

    def test_real_repo_header_is_consistent_with_config_mk(self):
        config_values = ec.parse_config_mk(ROOT / "config.mk")
        errors = cc.check_c_fallback_metadata(ROOT, config_values)
        self.assertEqual(errors, [])


class MigrationEpochReachabilityTests(unittest.TestCase):
    def test_epoch_1_reachable_via_none_to_1(self):
        registry = (MigrationStep(epoch_from=None, epoch_to=1, kind=MECHANICAL, description="x"),)
        self.assertEqual(cc.check_migration_epoch_reachability(1, registry), [])

    def test_unreachable_epoch_reported(self):
        registry = (MigrationStep(epoch_from=None, epoch_to=1, kind=MECHANICAL, description="x"),)
        errors = cc.check_migration_epoch_reachability(2, registry)
        self.assertTrue(errors)
        self.assertIn("no migration path", errors[0])

    def test_multi_hop_chain_reachable(self):
        registry = (
            MigrationStep(epoch_from=None, epoch_to=1, kind=MECHANICAL, description="x"),
            MigrationStep(epoch_from=1, epoch_to=2, kind=MECHANICAL, description="y"),
            MigrationStep(epoch_from=2, epoch_to=3, kind=MECHANICAL, description="z"),
        )
        self.assertEqual(cc.check_migration_epoch_reachability(3, registry), [])

    def test_broken_link_in_chain_detected(self):
        """epoch 3 declared reachable from 2, but nothing reaches 2 -- a
        genuine registry gap."""
        registry = (
            MigrationStep(epoch_from=None, epoch_to=1, kind=MECHANICAL, description="x"),
            MigrationStep(epoch_from=2, epoch_to=3, kind=MECHANICAL, description="z"),
        )
        errors = cc.check_migration_epoch_reachability(3, registry)
        self.assertTrue(errors)

    def test_real_registry_reaches_current_config_mk_epoch(self):
        from scripts.modernize.migrations import registry as real_registry
        config_values = ec.parse_config_mk(ROOT / "config.mk")
        epoch = int(config_values["EXPANSION_SAVE_COMPAT_EPOCH"])
        self.assertEqual(cc.check_migration_epoch_reachability(epoch, real_registry.registry()), [])


if __name__ == "__main__":
    unittest.main()
