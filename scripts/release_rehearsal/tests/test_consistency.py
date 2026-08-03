"""Tests for scripts/release_rehearsal/consistency.py (issue #9)."""

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

from scripts.release_rehearsal import consistency as cc
from scripts.release_rehearsal import git_source as gs
from scripts.modernize.migrations.registry import MigrationStep, MECHANICAL


def _git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _init_repo(root: Path) -> None:
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "Tester", cwd=root)


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
        """issue #9 residual-hardening: a genuinely valid full topology
        now also requires both the previous *and* the next supported
        version to have their own real, status-compatible 'supported'
        entry -- not merely satisfy the ordering (</>) comparisons."""
        ledger = _valid_ledger(
            previous_supported_version="0.0.9", current_version="0.1.0", next_supported_version="0.2.0",
            supported=[
                {"version": "0.0.9", "status": "eol", "eol": "2024-01-01"},
                {"version": "0.1.0", "status": "current", "eol": None},
                {"version": "0.2.0", "status": "supported", "eol": None},
            ],
        )
        self.assertEqual(cc.check_version_ledger(ledger, "0.1.0"), [])

    def test_valid_full_topology_with_previous_still_supported(self):
        """The previous version does not have to already be 'eol' --
        an overlapping/extended-support previous version is equally
        valid, so long as it is not (re-)marked 'current'."""
        ledger = _valid_ledger(
            previous_supported_version="0.0.9", current_version="0.1.0", next_supported_version=None,
            supported=[
                {"version": "0.0.9", "status": "supported", "eol": None},
                {"version": "0.1.0", "status": "current", "eol": None},
            ],
        )
        self.assertEqual(cc.check_version_ledger(ledger, "0.1.0"), [])

    # --- issue #9 residual-hardening: fresh-verifier-reproduced gaps ----
    # A fresh, independent verifier reproduced two concrete acceptance
    # gaps against `check_version_ledger` (and, unwired before this
    # change, the live `scripts/release_rehearsal/manifest.py` path that
    # calls it -- see test_manifest.py's `VersionLedgerManifestWiringTests`
    # for the corresponding through-the-manifest reproduction): (1) a
    # `status:"current"` entry that also carries a non-null EOL date, and
    # (2) `previous_supported_version` absent from `supported[]` entirely.
    # `next_supported_version` is hardened symmetrically even though the
    # verifier did not name it explicitly, per issue #9's own instruction
    # to validate it "if the schema exposes it" (it does).

    def test_current_status_entry_with_non_null_eol_rejected(self):
        ledger = _valid_ledger(supported=[{"version": "0.1.0", "status": "current", "eol": "2025-06-01"}])
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(
            any("status:'current'" in error and "eol" in error.lower() for error in errors), errors
        )

    def test_current_status_entry_with_null_eol_is_accepted(self):
        ledger = _valid_ledger(supported=[{"version": "0.1.0", "status": "current", "eol": None}])
        self.assertEqual(cc.check_version_ledger(ledger, "0.1.0"), [])

    def test_previous_supported_version_absent_from_supported_rejected(self):
        """`previous_supported_version` names a real MAJOR.MINOR.PATCH
        version, correctly ordered below `current_version`, but with no
        corresponding entry anywhere in 'supported' at all -- the exact
        gap the fresh verifier reproduced."""
        ledger = _valid_ledger(previous_supported_version="0.0.9")
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(
            any("previous_supported_version" in error and "0.0.9" in error and "does not appear" in error
                for error in errors),
            errors,
        )

    def test_next_supported_version_absent_from_supported_rejected(self):
        ledger = _valid_ledger(next_supported_version="0.2.0")
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(
            any("next_supported_version" in error and "0.2.0" in error and "does not appear" in error
                for error in errors),
            errors,
        )

    def test_previous_supported_version_status_current_rejected(self):
        """A version referenced by `previous_supported_version` must not
        itself carry status:'current' -- that status is exclusively
        `current_version`'s."""
        ledger = _valid_ledger(
            previous_supported_version="0.0.9",
            supported=[
                {"version": "0.0.9", "status": "current", "eol": None},
                {"version": "0.1.0", "status": "current", "eol": None},
            ],
        )
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(
            any("previous_supported_version" in error and "0.0.9" in error and "not a compatible status" in error
                for error in errors),
            errors,
        )

    def test_previous_supported_version_status_supported_is_compatible(self):
        ledger = _valid_ledger(
            previous_supported_version="0.0.9",
            supported=[
                {"version": "0.0.9", "status": "supported", "eol": None},
                {"version": "0.1.0", "status": "current", "eol": None},
            ],
        )
        self.assertEqual(cc.check_version_ledger(ledger, "0.1.0"), [])

    def test_previous_supported_version_duplicate_entry_rejected(self):
        ledger = _valid_ledger(
            previous_supported_version="0.0.9",
            supported=[
                {"version": "0.0.9", "status": "eol", "eol": "2020-01-01"},
                {"version": "0.0.9", "status": "eol", "eol": "2020-01-01"},
                {"version": "0.1.0", "status": "current", "eol": None},
            ],
        )
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(
            any("previous_supported_version" in error and "matches 2" in error for error in errors), errors
        )

    def test_next_supported_version_status_eol_rejected(self):
        """A version referenced by `next_supported_version` cannot
        already be 'eol' -- it has not even become current yet."""
        ledger = _valid_ledger(
            next_supported_version="0.2.0",
            supported=[
                {"version": "0.1.0", "status": "current", "eol": None},
                {"version": "0.2.0", "status": "eol", "eol": "2024-01-01"},
            ],
        )
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(
            any("next_supported_version" in error and "0.2.0" in error and "not a compatible status" in error
                for error in errors),
            errors,
        )

    def test_next_supported_version_status_current_rejected(self):
        ledger = _valid_ledger(
            next_supported_version="0.2.0",
            supported=[
                {"version": "0.1.0", "status": "current", "eol": None},
                {"version": "0.2.0", "status": "current", "eol": None},
            ],
        )
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(
            any("next_supported_version" in error and "0.2.0" in error and "not a compatible status" in error
                for error in errors),
            errors,
        )

    def test_next_supported_version_status_supported_is_compatible(self):
        ledger = _valid_ledger(
            next_supported_version="0.2.0",
            supported=[
                {"version": "0.1.0", "status": "current", "eol": None},
                {"version": "0.2.0", "status": "supported", "eol": None},
            ],
        )
        self.assertEqual(cc.check_version_ledger(ledger, "0.1.0"), [])

    def test_real_ledger_is_consistent_with_config_mk(self):
        import json
        ledger = json.loads((ROOT / "docs" / "release_data" / "version_ledger.json").read_text())
        config_values = ec.parse_config_mk(ROOT / "config.mk")
        candidate_version = f"{config_values['EXPANSION_VERSION_MAJOR']}.{config_values['EXPANSION_VERSION_MINOR']}.{config_values['EXPANSION_VERSION_PATCH']}"
        self.assertEqual(cc.check_version_ledger(ledger, candidate_version), [])

    # --- issue #9 residual-hardening: SemVer adjacency ------------------
    # A fresh, independent verifier reproduced a ledger whose
    # previous_supported_version names a real, correctly-ordered, valid
    # "supported" entry that is nonetheless *not* the adjacent
    # predecessor of current_version -- another recorded version sits
    # strictly between them. Selecting that more-distant predecessor as
    # the changelog SemVer-delta baseline can make an actually-small bump
    # (versus the true last release) look artificially large, inflating
    # the apparent evidence for a bigger declared `semver_impact`.

    def test_non_adjacent_previous_supported_version_rejected(self):
        """Concrete reproducer: 0.0.9 (selected, older predecessor) <
        0.0.9 < 0.1.0 (intervening, true adjacent predecessor) < 0.2.0
        (current_version). Selecting 0.0.9 instead of 0.1.0 as the
        baseline would make the apparent bump 0.0.9 -> 0.2.0 (minor) look
        the same as -- or, with different numbers, larger than -- the
        true 0.1.0 -> 0.2.0 delta. This must fail closed."""
        ledger = _valid_ledger(
            previous_supported_version="0.0.9",
            current_version="0.2.0",
            next_supported_version=None,
            supported=[
                {"version": "0.0.9", "status": "eol", "eol": "2020-01-01"},
                {"version": "0.1.0", "status": "eol", "eol": "2021-01-01"},
                {"version": "0.2.0", "status": "current", "eol": None},
            ],
        )
        errors = cc.check_version_ledger(ledger, "0.2.0")
        self.assertTrue(
            any(
                "previous_supported_version" in error and "0.0.9" in error
                and "not the adjacent predecessor" in error and "0.1.0" in error
                for error in errors
            ),
            errors,
        )

    def test_non_adjacent_previous_supported_version_with_larger_inflated_bump(self):
        """Sharper reproducer where the inflation is unambiguous:
        classify_bump() only looks at *which* MAJOR/MINOR/PATCH segment
        first differs, not by how much -- so the true adjacent
        predecessor (0.1.0) is only a 'patch' bump away from current
        (0.1.1), but the selected, older, non-adjacent predecessor
        (0.0.9) makes classify_bump() report 'minor' instead (the MINOR
        segment differs from 0.0.9), a strictly larger declared-impact
        floor via required_minimum_bump_rank() -- exactly the inflation
        this adjacency check exists to reject."""
        true_adjacent_bump = cc.classify_bump("0.1.0", "0.1.1")
        inflated_bump = cc.classify_bump("0.0.9", "0.1.1")
        self.assertEqual(true_adjacent_bump, "patch")
        self.assertEqual(inflated_bump, "minor")
        self.assertNotEqual(
            true_adjacent_bump, inflated_bump,
            "reproducer numbers must actually demonstrate inflation, not merely non-adjacency",
        )

        ledger = _valid_ledger(
            previous_supported_version="0.0.9",
            current_version="0.1.1",
            next_supported_version=None,
            supported=[
                {"version": "0.0.9", "status": "eol", "eol": "2020-01-01"},
                {"version": "0.1.0", "status": "eol", "eol": "2021-01-01"},
                {"version": "0.1.1", "status": "current", "eol": None},
            ],
        )
        errors = cc.check_version_ledger(ledger, "0.1.1")
        self.assertTrue(
            any(
                "previous_supported_version" in error and "0.0.9" in error
                and "not the adjacent predecessor" in error and "0.1.0" in error
                for error in errors
            ),
            errors,
        )
        # And the ledger/consistency check must fail closed overall --
        # not merely emit a warning-shaped, still-empty result.
        self.assertNotEqual(errors, [])

    def test_adjacent_previous_supported_version_with_intervening_eol_gap_is_still_accepted(self):
        """Sanity check: when previous_supported_version genuinely *is*
        the closest recorded version below current_version, adjacency
        must not be rejected merely because other, older, non-
        intervening 'eol' history also exists in 'supported'."""
        ledger = _valid_ledger(
            previous_supported_version="0.1.0",
            current_version="0.1.1",
            next_supported_version=None,
            supported=[
                {"version": "0.0.9", "status": "eol", "eol": "2020-01-01"},
                {"version": "0.1.0", "status": "eol", "eol": "2021-01-01"},
                {"version": "0.1.1", "status": "current", "eol": None},
            ],
        )
        self.assertEqual(cc.check_version_ledger(ledger, "0.1.1"), [])

    def test_non_adjacent_next_supported_version_rejected(self):
        """Symmetric successor-adjacency reproducer: 0.3.0 is selected as
        next_supported_version, but 0.2.0 (recorded, 'supported') is the
        true adjacent successor of current_version 0.1.0."""
        ledger = _valid_ledger(
            current_version="0.1.0",
            next_supported_version="0.3.0",
            supported=[
                {"version": "0.1.0", "status": "current", "eol": None},
                {"version": "0.2.0", "status": "supported", "eol": None},
                {"version": "0.3.0", "status": "supported", "eol": None},
            ],
        )
        errors = cc.check_version_ledger(ledger, "0.1.0")
        self.assertTrue(
            any(
                "next_supported_version" in error and "0.3.0" in error
                and "not the adjacent successor" in error and "0.2.0" in error
                for error in errors
            ),
            errors,
        )

    def test_adjacent_next_supported_version_is_accepted(self):
        ledger = _valid_ledger(
            current_version="0.1.0",
            next_supported_version="0.2.0",
            supported=[
                {"version": "0.1.0", "status": "current", "eol": None},
                {"version": "0.2.0", "status": "supported", "eol": None},
                {"version": "0.3.0", "status": "supported", "eol": None},
            ],
        )
        self.assertEqual(cc.check_version_ledger(ledger, "0.1.0"), [])


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


class ReleaseTagAuthorityGitTests(unittest.TestCase):
    """issue #9 SemVer trust-boundary fix (B): `check_release_tag_authority`
    cross-checks a ledger's descriptive `previous_supported_version`
    claim against this repository's real, immutable, annotated
    `expansion/MAJOR.MINOR.PATCH` release-tag history -- covering every
    adversarial case named in the task contract."""

    def _commit(self, root: Path, name: str = "f.txt") -> str:
        (root / name).write_text(name)
        _git("add", "-A", cwd=root)
        _git("commit", "-q", "-m", name, cwd=root)
        return gs.resolve_sha(root, "HEAD")

    def test_no_tag_first_release_declares_no_predecessor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            sha = self._commit(root)
            errors = cc.check_release_tag_authority(root, sha, "1.0.0", None)
            self.assertEqual(errors, [])

    def test_fabricated_predecessor_with_no_tags_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            sha = self._commit(root)
            errors = cc.check_release_tag_authority(root, sha, "1.0.0", "0.9.0")
            self.assertTrue(errors)
            self.assertTrue(any("does not match the true immediate predecessor" in e for e in errors))
            self.assertTrue(any("None" in e for e in errors))

    def test_annotated_predecessor_matches_declared_ledger_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            self._commit(root, "a.txt")
            _git("tag", "-a", "-m", "r1", "expansion/1.0.0", cwd=root)
            sha = self._commit(root, "b.txt")
            errors = cc.check_release_tag_authority(root, sha, "2.0.0", "1.0.0")
            self.assertEqual(errors, [])

    def test_omitted_predecessor_when_real_tag_exists_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            self._commit(root, "a.txt")
            _git("tag", "-a", "-m", "r1", "expansion/1.0.0", cwd=root)
            sha = self._commit(root, "b.txt")
            errors = cc.check_release_tag_authority(root, sha, "2.0.0", None)
            self.assertTrue(errors)
            self.assertTrue(any("1.0.0" in e for e in errors))

    def test_older_selected_predecessor_with_newer_reachable_tag_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            self._commit(root, "a.txt")
            _git("tag", "-a", "-m", "r1", "expansion/1.0.0", cwd=root)
            self._commit(root, "b.txt")
            _git("tag", "-a", "-m", "r2", "expansion/1.5.0", cwd=root)
            sha = self._commit(root, "c.txt")
            errors = cc.check_release_tag_authority(root, sha, "2.0.0", "1.0.0")
            self.assertTrue(errors)
            self.assertTrue(any("1.5.0" in e for e in errors))

    def test_lightweight_tag_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            sha = self._commit(root)
            _git("tag", "expansion/1.0.0", cwd=root)
            errors = cc.check_release_tag_authority(root, sha, "2.0.0", "1.0.0")
            self.assertTrue(errors)
            self.assertTrue(any("lightweight" in e for e in errors))

    def test_malformed_tag_name_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            sha = self._commit(root)
            _git("tag", "-a", "-m", "bad", "expansion/not-a-version", cwd=root)
            errors = cc.check_release_tag_authority(root, sha, "2.0.0", "1.0.0")
            self.assertTrue(errors)
            self.assertTrue(any("malformed" in e for e in errors))

    def test_tag_not_reachable_from_target_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            self._commit(root, "a.txt")
            _git("tag", "-a", "-m", "r1", "expansion/1.0.0", cwd=root)
            _git("checkout", "-q", "--orphan", "other", cwd=root)
            target_sha = self._commit(root, "b.txt")
            errors = cc.check_release_tag_authority(root, target_sha, "2.0.0", "1.0.0")
            self.assertTrue(errors)
            self.assertTrue(any("None" in e for e in errors))

    def test_tag_pointing_at_current_version_fails(self):
        """A release tag already exists for the exact candidate version
        being built -- a candidate must never reuse an already-tagged
        version, regardless of what commit that tag happens to point
        at."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            sha = self._commit(root, "a.txt")
            _git("tag", "-a", "-m", "already released", "expansion/2.0.0", cwd=root)
            errors = cc.check_release_tag_authority(root, sha, "2.0.0", None)
            self.assertTrue(errors)
            self.assertTrue(any("already exists for the current candidate version" in e for e in errors))


class ReleaseTagAuthorityNonGitTests(unittest.TestCase):
    """issue #9 SemVer trust-boundary fix (B3): the non-git/archive
    equivalent -- an explicit, external, protected release-history
    attestation is required, bound exactly to `target_sha` and
    `current_version`; a missing/malformed/mismatched attestation must
    fail closed, never fabricate an empty release history."""

    TARGET_SHA = "c" * 40

    def _write_attestation(self, path: Path, **overrides):
        doc = {
            "schema_version": cc.RELEASE_HISTORY_ATTESTATION_SCHEMA_VERSION,
            "target_sha": self.TARGET_SHA,
            "current_version": "2.0.0",
            "previous_supported_version": "1.0.0",
        }
        doc.update(overrides)
        path.write_text(json.dumps(doc), encoding="utf-8")

    def test_missing_attestation_fails_closed(self):
        errors = cc.check_release_tag_authority_non_git(None, self.TARGET_SHA, "2.0.0", "1.0.0")
        self.assertTrue(errors)
        self.assertTrue(any("no explicit, external, protected release-history attestation" in e for e in errors))

    def test_matching_attestation_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attestation.json"
            self._write_attestation(path)
            errors = cc.check_release_tag_authority_non_git(path, self.TARGET_SHA, "2.0.0", "1.0.0")
            self.assertEqual(errors, [])

    def test_mismatched_target_sha_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attestation.json"
            self._write_attestation(path, target_sha="d" * 40)
            errors = cc.check_release_tag_authority_non_git(path, self.TARGET_SHA, "2.0.0", "1.0.0")
            self.assertTrue(errors)
            self.assertTrue(any("does not match this candidate's own exact target SHA" in e for e in errors))

    def test_mismatched_current_version_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attestation.json"
            self._write_attestation(path, current_version="3.0.0")
            errors = cc.check_release_tag_authority_non_git(path, self.TARGET_SHA, "2.0.0", "1.0.0")
            self.assertTrue(errors)
            self.assertTrue(any("does not match this candidate's own current version" in e for e in errors))

    def test_tampered_previous_supported_version_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attestation.json"
            self._write_attestation(path, previous_supported_version="0.5.0")
            errors = cc.check_release_tag_authority_non_git(path, self.TARGET_SHA, "2.0.0", "1.0.0")
            self.assertTrue(errors)
            self.assertTrue(any("does not match the version ledger's own declared" in e for e in errors))

    def test_truncated_json_attestation_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attestation.json"
            path.write_text("{not json", encoding="utf-8")
            errors = cc.check_release_tag_authority_non_git(path, self.TARGET_SHA, "2.0.0", "1.0.0")
            self.assertTrue(errors)
            self.assertTrue(any("not valid JSON" in e for e in errors))

    def test_wrong_top_level_type_attestation_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attestation.json"
            path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            errors = cc.check_release_tag_authority_non_git(path, self.TARGET_SHA, "2.0.0", "1.0.0")
            self.assertTrue(errors)

    def test_load_release_history_attestation_missing_key_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attestation.json"
            path.write_text(json.dumps({"schema_version": 1, "target_sha": self.TARGET_SHA}), encoding="utf-8")
            with self.assertRaises(cc.ReleaseHistoryAttestationError):
                cc.load_release_history_attestation(path)

    def test_never_fabricates_empty_history_when_ledger_declares_none(self):
        """Even when the ledger honestly declares no predecessor at all,
        a non-git candidate must still supply a real, bound attestation
        -- absence of one is never silently treated as an implicit,
        free "first release" pass for a non-git materialization."""
        errors = cc.check_release_tag_authority_non_git(None, self.TARGET_SHA, "1.0.0", None)
        self.assertTrue(errors)



if __name__ == "__main__":
    unittest.main()
