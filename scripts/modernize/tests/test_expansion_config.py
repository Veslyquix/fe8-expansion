"""Tests for scripts/modernize/expansion_config.py (issue #8).

Covers: field validators (valid + malformed title/game code/maker code/
revision/ROM size/semantic version/build-id/preset/ABI/text shift),
config.mk parsing, the override-parameter precedence in load_identity()
(an explicit override always wins over config.mk's parsed value -- this is
the fix for the "two sources of truth" bug), build-commit resolution
precedence (explicit override > git rev-parse HEAD > "unknown" sentinel),
fingerprint determinism, generate_metadata_files()'s write-if-changed
behavior, and the validate/resolve/generate CLI subcommands (including
early, actionable rejection of invalid inputs and incompatible
combinations before any file is written).
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "modernize"))

import expansion_config as ec  # noqa: E402


def write_config_mk(
    directory: Path,
    version_major="0",
    version_minor="1",
    version_patch="0",
    rom_title="FIREEMBLEM2E",
    rom_game_code="BE8E",
    rom_maker_code="01",
    rom_revision="0",
    build_id="",
    save_compat_epoch="1",
    enabled_locales="en",
    default_locale="en",
    pseudo_locale="0",
    mechanics_hooks=None,
    mechanics_sample=None,
    danger_overlay_menu=None,
) -> Path:
    path = directory / "config.mk"
    # The issue #6 starter-feature flags are optional config.mk keys: a
    # fixture omits them (they default to 0, exercising the absent path)
    # unless a test passes an explicit value.
    feature_lines = []
    if mechanics_hooks is not None:
        feature_lines.append(f"EXPANSION_MECHANICS_HOOKS := {mechanics_hooks}")
    if mechanics_sample is not None:
        feature_lines.append(f"EXPANSION_MECHANICS_SAMPLE := {mechanics_sample}")
    if danger_overlay_menu is not None:
        feature_lines.append(
            f"EXPANSION_DANGER_OVERLAY_MENU := {danger_overlay_menu}"
        )
    path.write_text(
        "\n".join(
            [
                f"EXPANSION_VERSION_MAJOR := {version_major}",
                f"EXPANSION_VERSION_MINOR := {version_minor}",
                f"EXPANSION_VERSION_PATCH := {version_patch}",
                f"EXPANSION_ROM_TITLE := {rom_title}",
                f"EXPANSION_ROM_GAME_CODE := {rom_game_code}",
                f"EXPANSION_ROM_MAKER_CODE := {rom_maker_code}",
                f"EXPANSION_ROM_REVISION := {rom_revision}",
                f"EXPANSION_BUILD_ID := {build_id}",
                f"EXPANSION_SAVE_COMPAT_EPOCH := {save_compat_epoch}",
                f"EXPANSION_ENABLED_LOCALES := {enabled_locales}",
                f"EXPANSION_DEFAULT_LOCALE := {default_locale}",
                f"EXPANSION_PSEUDO_LOCALE := {pseudo_locale}",
                *feature_lines,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


class ValidateTitleTests(unittest.TestCase):
    def test_valid_title_passes_through(self):
        self.assertEqual(ec.validate_title("FIREEMBLEM2E"), "FIREEMBLEM2E")

    def test_exactly_12_bytes_is_ok(self):
        self.assertEqual(ec.validate_title("ABCDEFGHIJKL"), "ABCDEFGHIJKL")

    def test_empty_title_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_title("")

    def test_too_long_title_rejected(self):
        with self.assertRaises(ec.ConfigError) as ctx:
            ec.validate_title("THISISTOOLONG")
        self.assertIn("EXPANSION_ROM_TITLE", str(ctx.exception))

    def test_non_ascii_title_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_title("FE8\u00e9")


class ValidateGameCodeTests(unittest.TestCase):
    def test_valid_game_code_passes_through(self):
        self.assertEqual(ec.validate_game_code("BE8E"), "BE8E")

    def test_wrong_length_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_game_code("ABC")
        with self.assertRaises(ec.ConfigError):
            ec.validate_game_code("ABCDE")

    def test_non_ascii_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_game_code("B\u00e98E")


class ValidateMakerCodeTests(unittest.TestCase):
    def test_valid_maker_code_passes_through(self):
        self.assertEqual(ec.validate_maker_code("01"), "01")

    def test_wrong_length_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_maker_code("0")
        with self.assertRaises(ec.ConfigError):
            ec.validate_maker_code("012")


class ValidateRevisionTests(unittest.TestCase):
    def test_boundary_values_ok(self):
        self.assertEqual(ec.validate_revision(0), 0)
        self.assertEqual(ec.validate_revision(255), 255)
        self.assertEqual(ec.validate_revision("42"), 42)

    def test_out_of_range_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_revision(256)
        with self.assertRaises(ec.ConfigError):
            ec.validate_revision(-1)

    def test_non_integer_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_revision("not-a-number")


class ValidateRomSizeTests(unittest.TestCase):
    def test_named_sizes_case_insensitive(self):
        self.assertEqual(ec.validate_rom_size("16M"), 16 * 1024 * 1024)
        self.assertEqual(ec.validate_rom_size("16m"), 16 * 1024 * 1024)
        self.assertEqual(ec.validate_rom_size("32M"), 32 * 1024 * 1024)

    def test_exact_byte_counts_accepted(self):
        self.assertEqual(ec.validate_rom_size(str(32 * 1024 * 1024)), 32 * 1024 * 1024)

    def test_unsupported_size_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_rom_size("8M")
        with self.assertRaises(ec.ConfigError):
            ec.validate_rom_size("12345")

    def test_garbage_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_rom_size("banana")


class ValidateVersionTests(unittest.TestCase):
    def test_valid_version_components(self):
        self.assertEqual(ec.validate_version(1, 2, 3), (1, 2, 3))
        self.assertEqual(ec.validate_version("0", "1", "0"), (0, 1, 0))

    def test_boundary_values_ok(self):
        self.assertEqual(ec.validate_version(0, 0, 0), (0, 0, 0))
        self.assertEqual(ec.validate_version(255, 255, 255), (255, 255, 255))

    def test_out_of_range_component_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_version(256, 0, 0)
        with self.assertRaises(ec.ConfigError):
            ec.validate_version(0, -1, 0)

    def test_non_integer_component_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_version("x", 0, 0)


class ValidatePresetAbiTests(unittest.TestCase):
    def test_supported_presets_ok(self):
        self.assertEqual(ec.validate_preset("debug"), "debug")
        self.assertEqual(ec.validate_preset("release"), "release")

    def test_unsupported_preset_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_preset("profiling")

    def test_supported_abis_ok(self):
        self.assertEqual(ec.validate_abi("aapcs"), "aapcs")
        self.assertEqual(ec.validate_abi("apcs-gnu"), "apcs-gnu")

    def test_unsupported_abi_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_abi("eabi")


class ValidateTextShiftTests(unittest.TestCase):
    def test_aligned_value_ok(self):
        self.assertEqual(ec.validate_text_shift("0"), 0)
        self.assertEqual(ec.validate_text_shift("1024"), 1024)

    def test_unaligned_value_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_text_shift("3")

    def test_non_numeric_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_text_shift("nope")


class ValidateBuildIdOverrideTests(unittest.TestCase):
    def test_none_and_empty_are_ok_and_mean_unset(self):
        self.assertIsNone(ec.validate_build_id_override(None))
        self.assertIsNone(ec.validate_build_id_override(""))

    def test_valid_hex_sha_is_lowercased(self):
        self.assertEqual(ec.validate_build_id_override("ABCDEF12"), "abcdef12")

    def test_short_prefix_ok(self):
        self.assertEqual(ec.validate_build_id_override("abcd"), "abcd")

    def test_timestamp_like_value_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_build_id_override("2024-01-01T00:00:00Z")

    def test_branch_name_like_value_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_build_id_override("feature/my-branch")

    def test_too_short_or_too_long_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_build_id_override("abc")
        with self.assertRaises(ec.ConfigError):
            ec.validate_build_id_override("a" * 41)


class ParseConfigMkTests(unittest.TestCase):
    def test_parses_all_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_config_mk(Path(tmp))
            values = ec.parse_config_mk(path)
        for key in ec.CONFIG_MK_KEYS:
            self.assertIn(key, values)
        self.assertEqual(values["EXPANSION_ROM_TITLE"], "FIREEMBLEM2E")

    def test_ignores_comments_and_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.mk"
            path.write_text(
                "\n".join(
                    [
                        "# a leading comment",
                        "",
                        "EXPANSION_VERSION_MAJOR := 0  # inline comment",
                        "EXPANSION_VERSION_MINOR := 1",
                        "EXPANSION_VERSION_PATCH := 0",
                        "EXPANSION_ROM_TITLE := FIREEMBLEM2E",
                        "EXPANSION_ROM_GAME_CODE := BE8E",
                        "EXPANSION_ROM_MAKER_CODE := 01",
                        "EXPANSION_ROM_REVISION := 0",
                        "EXPANSION_BUILD_ID :=",
                        "EXPANSION_SAVE_COMPAT_EPOCH := 1",
                        "EXPANSION_ENABLED_LOCALES := en",
                        "EXPANSION_DEFAULT_LOCALE := en",
                        "EXPANSION_PSEUDO_LOCALE := 0",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            values = ec.parse_config_mk(path)
        self.assertEqual(values["EXPANSION_VERSION_MAJOR"], "0")

    def test_missing_file_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.parse_config_mk(Path("/nonexistent/config.mk"))

    def test_missing_required_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.mk"
            path.write_text("EXPANSION_VERSION_MAJOR := 0\n", encoding="utf-8")
            with self.assertRaises(ec.ConfigError) as ctx:
                ec.parse_config_mk(path)
        self.assertIn("EXPANSION_ROM_TITLE", str(ctx.exception))


class ResolveBuildCommitTests(unittest.TestCase):
    def test_explicit_override_wins(self):
        commit = ec.resolve_build_commit("abcd1234", Path("."))
        self.assertEqual(commit, "abcd1234")

    def test_falls_back_to_git_rev_parse_head(self):
        # This repository itself is a git checkout, so HEAD must resolve to
        # a real 40-hex-character commit SHA.
        commit = ec.resolve_build_commit(None, ROOT)
        self.assertRegex(commit, r"^[0-9a-f]{40}$")

    def test_falls_back_to_unknown_sentinel_outside_a_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            commit = ec.resolve_build_commit(None, Path(tmp))
        self.assertEqual(commit, "unknown")

    def test_nested_non_git_tree_never_adopts_outer_repo_head(self):
        """issue #9 remediation regression: a non-git candidate tree
        nested *inside* an unrelated outer Git repository (with its own,
        different HEAD) must resolve to the fixed "unknown" sentinel --
        never git's own upward-directory-discovery-found outer HEAD."""
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp) / "outer"
            outer.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=str(outer), check=True)
            subprocess.run(
                ["git", "config", "user.email", "outer@example.invalid"], cwd=str(outer), check=True
            )
            subprocess.run(["git", "config", "user.name", "outer"], cwd=str(outer), check=True)
            (outer / "outer-file.txt").write_text("unrelated outer repository content\n")
            subprocess.run(["git", "add", "outer-file.txt"], cwd=str(outer), check=True)
            subprocess.run(["git", "commit", "-q", "-m", "outer commit"], cwd=str(outer), check=True)
            outer_head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=str(outer), capture_output=True, text=True, check=True,
            ).stdout.strip()

            candidate = outer / "nested" / "candidate"
            candidate.mkdir(parents=True)
            self.assertFalse((candidate / ".git").exists())

            commit = ec.resolve_build_commit(None, candidate)
            self.assertEqual(commit, "unknown")
            self.assertNotEqual(commit, outer_head)

    def test_nested_non_git_tree_makes_no_git_subprocess_call_at_all(self):
        """The fix must never even *invoke* git for a candidate root with
        no `.git` of its own -- not merely "invoke it, but discard/ignore
        an unwanted result". A patched `subprocess.run` that raises on
        any call proves this empirically."""
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp) / "outer"
            outer.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=str(outer), check=True)
            candidate = outer / "nested" / "candidate"
            candidate.mkdir(parents=True)

            def _forbidden_run(*args, **kwargs):
                raise AssertionError(f"unexpected subprocess.run call: {args!r} {kwargs!r}")

            with mock.patch.object(ec.subprocess, "run", _forbidden_run):
                commit = ec.resolve_build_commit(None, candidate)
            self.assertEqual(commit, "unknown")


class FingerprintDeterminismTests(unittest.TestCase):
    def test_same_inputs_produce_same_fingerprint(self):
        fields = {"version": [0, 1, 0], "abi": "aapcs"}
        self.assertEqual(ec.compute_fingerprint(fields), ec.compute_fingerprint(dict(fields)))

    def test_key_order_does_not_affect_fingerprint(self):
        a = {"abi": "aapcs", "version": [0, 1, 0]}
        b = {"version": [0, 1, 0], "abi": "aapcs"}
        self.assertEqual(ec.compute_fingerprint(a), ec.compute_fingerprint(b))

    def test_different_inputs_produce_different_fingerprints(self):
        a = {"abi": "aapcs"}
        b = {"abi": "apcs-gnu"}
        self.assertNotEqual(ec.compute_fingerprint(a), ec.compute_fingerprint(b))

    def test_debug_and_release_presets_produce_different_fingerprints(self):
        base = {
            "version": [0, 1, 0], "abi": "aapcs", "rom_size_bytes": 16 * 1024 * 1024,
            "text_shift": 0, "rom_title": "FIREEMBLEM2E", "rom_game_code": "BE8E",
            "rom_maker_code": "01", "rom_revision": 0,
        }
        debug = ec.compute_fingerprint(dict(base, config_preset="debug"))
        release = ec.compute_fingerprint(dict(base, config_preset="release"))
        self.assertNotEqual(debug, release)


class LoadIdentityTests(unittest.TestCase):
    def test_defaults_come_from_config_mk(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            identity = ec.load_identity(
                config_mk_path=config_mk,
                config_preset="debug",
                abi="aapcs",
                rom_size="16M",
                repo_root=Path(tmp),
            )
        self.assertEqual(identity.rom_title, "FIREEMBLEM2E")
        self.assertEqual(identity.rom_game_code, "BE8E")
        self.assertEqual(identity.version_string, "0.1.0")
        self.assertEqual(identity.build_commit, "unknown")

    def test_override_wins_over_config_mk_value(self):
        """The fix for the two-sources-of-truth bug: an explicit override
        parameter must take precedence over config.mk's parsed value."""
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            identity = ec.load_identity(
                config_mk_path=config_mk,
                config_preset="debug",
                abi="aapcs",
                rom_size="16M",
                repo_root=Path(tmp),
                rom_title="FE8CUSTOMTST",
                rom_game_code="ZZZZ",
                rom_maker_code="9X",
                rom_revision=7,
                version_major=2,
            )
        self.assertEqual(identity.rom_title, "FE8CUSTOMTST")
        self.assertEqual(identity.rom_game_code, "ZZZZ")
        self.assertEqual(identity.rom_maker_code, "9X")
        self.assertEqual(identity.rom_revision, 7)
        self.assertEqual(identity.version_major, 2)

    def test_empty_string_override_falls_back_to_config_mk(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            identity = ec.load_identity(
                config_mk_path=config_mk,
                config_preset="debug",
                abi="aapcs",
                rom_size="16M",
                repo_root=Path(tmp),
                rom_title="",
            )
        self.assertEqual(identity.rom_title, "FIREEMBLEM2E")

    def test_invalid_override_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            with self.assertRaises(ec.ConfigError):
                ec.load_identity(
                    config_mk_path=config_mk,
                    config_preset="debug",
                    abi="aapcs",
                    rom_size="16M",
                    repo_root=Path(tmp),
                    rom_game_code="ABC",
                )

    def test_fingerprint_is_populated_and_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            first = ec.load_identity(
                config_mk_path=config_mk, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp),
            )
            second = ec.load_identity(
                config_mk_path=config_mk, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp),
            )
        self.assertEqual(first.config_fingerprint, second.config_fingerprint)
        self.assertTrue(first.config_fingerprint)

    def test_debug_vs_release_fingerprints_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            debug = ec.load_identity(
                config_mk_path=config_mk, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp),
            )
            release = ec.load_identity(
                config_mk_path=config_mk, config_preset="release", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp),
            )
        self.assertNotEqual(debug.config_fingerprint, release.config_fingerprint)

    def test_build_id_override_from_config_mk_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp), build_id="deadbeef")
            identity = ec.load_identity(
                config_mk_path=config_mk, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp),
            )
        self.assertEqual(identity.build_commit, "deadbeef")

    def test_explicit_build_id_override_wins_over_config_mk(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp), build_id="deadbeef")
            identity = ec.load_identity(
                config_mk_path=config_mk, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp), build_id_override="cafef00d",
            )
        self.assertEqual(identity.build_commit, "cafef00d")


class ValidateEnabledLocalesTests(unittest.TestCase):
    def test_single_en_ok(self):
        self.assertEqual(ec.validate_enabled_locales("en"), ("en",))

    def test_en_and_qps_ok_and_normalized_to_stable_order(self):
        # Input order is reversed from the stable id order; the validator
        # must normalize to the fixed stable-id order regardless.
        self.assertEqual(
            ec.validate_enabled_locales("qps-ploc,en"), ("en", "qps-ploc")
        )

    def test_list_input_accepted(self):
        self.assertEqual(ec.validate_enabled_locales(["en", "qps-ploc"]), ("en", "qps-ploc"))

    def test_real_cjk_locales_are_configurable_and_stably_ordered(self):
        expected = {
            "en,ja": ("en", "ja"),
            "en,zh-Hans": ("en", "zh-Hans"),
            "zh-Hans,en,ja": ("en", "ja", "zh-Hans"),
        }
        for configured, normalized in expected.items():
            with self.subTest(configured=configured):
                self.assertEqual(
                    ec.validate_enabled_locales(configured),
                    normalized,
                )

    def test_empty_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_enabled_locales("")

    def test_missing_en_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_enabled_locales("qps-ploc")

    def test_unknown_locale_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_enabled_locales("en,klingon")

    def test_duplicate_locale_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_enabled_locales("en,en")

    def test_reserved_but_unconfigurable_locale_rejected(self):
        for locale in ("fr", "de", "es", "it"):
            with self.assertRaises(ec.ConfigError):
                ec.validate_enabled_locales(f"en,{locale}")


class ValidateDefaultLocaleTests(unittest.TestCase):
    def test_default_within_enabled_set_ok(self):
        self.assertEqual(ec.validate_default_locale("en", ("en", "qps-ploc")), "en")

    def test_default_not_in_enabled_set_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_default_locale("qps-ploc", ("en",))

    def test_unknown_default_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_default_locale("klingon", ("en",))


class ValidatePseudoLocaleTests(unittest.TestCase):
    def test_zero_without_qps_ok(self):
        self.assertEqual(ec.validate_pseudo_locale("0", ("en",)), 0)

    def test_one_with_qps_ok(self):
        self.assertEqual(ec.validate_pseudo_locale("1", ("en", "qps-ploc")), 1)

    def test_one_without_qps_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_pseudo_locale("1", ("en",))

    def test_zero_with_qps_rejected(self):
        with self.assertRaises(ec.ConfigError):
            ec.validate_pseudo_locale("0", ("en", "qps-ploc"))

    def test_non_zero_one_value_rejected(self):
        for bogus in ("2", "true", "yes", "-1", ""):
            with self.assertRaises(ec.ConfigError):
                ec.validate_pseudo_locale(bogus, ("en",))


class ValidateLocaleRomSizeTests(unittest.TestCase):
    def test_english_and_pseudo_profiles_allow_16m(self):
        ec.validate_locale_rom_size(("en",), 16 * 1024 * 1024)
        ec.validate_locale_rom_size(("en", "qps-ploc"), 16 * 1024 * 1024)

    def test_real_cjk_profiles_require_32m(self):
        for locales in (
            ("en", "ja"),
            ("en", "zh-Hans"),
            ("en", "ja", "zh-Hans"),
        ):
            with self.subTest(locales=locales):
                with self.assertRaises(ec.ConfigError) as ctx:
                    ec.validate_locale_rom_size(locales, 16 * 1024 * 1024)
                self.assertIn("MODERN_ROM_SIZE=32M", str(ctx.exception))

    def test_real_cjk_profiles_allow_32m(self):
        for locales in (
            ("en", "ja"),
            ("en", "zh-Hans"),
            ("en", "ja", "zh-Hans"),
        ):
            with self.subTest(locales=locales):
                ec.validate_locale_rom_size(locales, 32 * 1024 * 1024)


class ComputeLocaleMaskTests(unittest.TestCase):
    def test_en_only_mask_is_bit_zero(self):
        self.assertEqual(ec.compute_locale_mask(("en",)), 0x1)

    def test_en_and_qps_mask_matches_bit_positions(self):
        # en=0, qps-ploc=7 -- see scripts/localization/schema.py LOCALE_IDS.
        self.assertEqual(ec.compute_locale_mask(("en", "qps-ploc")), 0x81)

    def test_en_ja_zh_mask_matches_stable_bit_positions(self):
        self.assertEqual(ec.compute_locale_mask(("en", "ja", "zh-Hans")), 0x7)


class LoadIdentityLocaleTests(unittest.TestCase):
    """load_identity() end-to-end locale config resolution -- defaults,
    overrides, invalid combinations, and the fingerprint/save-epoch
    independence guarantee (issue #18 sprint 1 WHAT item 5)."""

    def test_defaults_are_en_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            identity = ec.load_identity(
                config_mk_path=config_mk, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp),
            )
        self.assertEqual(identity.enabled_locales, ("en",))
        self.assertEqual(identity.default_locale, "en")
        self.assertEqual(identity.pseudo_locale_enabled, 0)
        self.assertEqual(identity.enabled_locale_mask, 0x1)
        self.assertEqual(identity.default_locale_id, 0)

    def test_config_mk_qps_enabled_is_honored(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(
                Path(tmp), enabled_locales="en,qps-ploc", pseudo_locale="1"
            )
            identity = ec.load_identity(
                config_mk_path=config_mk, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp),
            )
        self.assertEqual(identity.enabled_locales, ("en", "qps-ploc"))
        self.assertEqual(identity.pseudo_locale_enabled, 1)
        self.assertEqual(identity.enabled_locale_mask, 0x81)

    def test_override_wins_over_config_mk(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            identity = ec.load_identity(
                config_mk_path=config_mk, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp),
                enabled_locales="en,qps-ploc", default_locale="qps-ploc", pseudo_locale="1",
            )
        self.assertEqual(identity.enabled_locales, ("en", "qps-ploc"))
        self.assertEqual(identity.default_locale, "qps-ploc")
        self.assertEqual(identity.pseudo_locale_enabled, 1)

    def test_invalid_locale_combination_from_config_mk_fails_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp), pseudo_locale="1")  # qps not enabled
            with self.assertRaises(ec.ConfigError):
                ec.load_identity(
                    config_mk_path=config_mk, config_preset="debug", abi="aapcs",
                    rom_size="16M", repo_root=Path(tmp),
                )

    def test_cjk_profiles_reject_16m_and_resolve_at_32m(self):
        for configured in ("en,ja", "en,zh-Hans", "zh-Hans,en,ja"):
            with self.subTest(configured=configured):
                with tempfile.TemporaryDirectory() as tmp:
                    config_mk = write_config_mk(
                        Path(tmp), enabled_locales=configured
                    )
                    with self.assertRaises(ec.ConfigError) as ctx:
                        ec.load_identity(
                            config_mk_path=config_mk,
                            config_preset="debug",
                            abi="aapcs",
                            rom_size="16M",
                            repo_root=Path(tmp),
                        )
                    identity = ec.load_identity(
                        config_mk_path=config_mk,
                        config_preset="debug",
                        abi="aapcs",
                        rom_size="32M",
                        repo_root=Path(tmp),
                    )
                self.assertIn("MODERN_ROM_SIZE=32M", str(ctx.exception))
                expected = tuple(
                    locale
                    for locale in ("en", "ja", "zh-Hans")
                    if locale in configured.split(",")
                )
                self.assertEqual(identity.enabled_locales, expected)

    def test_cjk_default_locale_ja_and_zh_hans_resolve(self):
        for default_locale, expected_id in (("ja", 1), ("zh-Hans", 2)):
            with self.subTest(default_locale=default_locale):
                with tempfile.TemporaryDirectory() as tmp:
                    config_mk = write_config_mk(
                        Path(tmp),
                        enabled_locales="en,ja,zh-Hans",
                        default_locale=default_locale,
                    )
                    identity = ec.load_identity(
                        config_mk_path=config_mk,
                        config_preset="release",
                        abi="aapcs",
                        rom_size="32M",
                        repo_root=Path(tmp),
                    )
                self.assertEqual(identity.default_locale, default_locale)
                self.assertEqual(identity.default_locale_id, expected_id)
                self.assertEqual(identity.enabled_locale_mask, 0x7)

    def test_locale_config_changes_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            config_a = write_config_mk(Path(tmp_a))
            config_b = write_config_mk(
                Path(tmp_b), enabled_locales="en,qps-ploc", pseudo_locale="1"
            )
            identity_a = ec.load_identity(
                config_mk_path=config_a, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp_a),
            )
            identity_b = ec.load_identity(
                config_mk_path=config_b, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp_b),
            )
        self.assertNotEqual(identity_a.config_fingerprint, identity_b.config_fingerprint)

    def test_locale_config_change_does_not_move_save_compat_epoch(self):
        """The exact property WHAT item 5 requires: changing the locale
        config changes the fingerprint but never the save-compat epoch."""
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            config_a = write_config_mk(Path(tmp_a), save_compat_epoch="42")
            config_b = write_config_mk(
                Path(tmp_b), save_compat_epoch="42",
                enabled_locales="en,qps-ploc", pseudo_locale="1",
            )
            identity_a = ec.load_identity(
                config_mk_path=config_a, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp_a),
            )
            identity_b = ec.load_identity(
                config_mk_path=config_b, config_preset="debug", abi="aapcs",
                rom_size="16M", repo_root=Path(tmp_b),
            )
        self.assertNotEqual(identity_a.config_fingerprint, identity_b.config_fingerprint)
        self.assertEqual(identity_a.save_compat_epoch, identity_b.save_compat_epoch)
        self.assertEqual(identity_a.save_compat_epoch, 42)


class GenerateMetadataFilesTests(unittest.TestCase):
    def _identity(self, tmp):
        config_mk = write_config_mk(Path(tmp))
        return ec.load_identity(
            config_mk_path=config_mk, config_preset="debug", abi="aapcs",
            rom_size="16M", repo_root=Path(tmp),
        )

    def test_writes_json_and_mk_with_expected_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity = self._identity(tmp)
            out_dir = Path(tmp) / "generated"
            paths = ec.generate_metadata_files(out_dir, identity)
            data = json.loads(paths["json"].read_text(encoding="utf-8"))
            mk_text = paths["mk"].read_text(encoding="utf-8")
        self.assertEqual(data["rom_title"], "FIREEMBLEM2E")
        self.assertEqual(data["config_fingerprint"], identity.config_fingerprint)
        self.assertIn(f"MODERN_BUILD_COMMIT := {identity.build_commit}", mk_text)
        self.assertIn(f"MODERN_CONFIG_FINGERPRINT := {identity.config_fingerprint}", mk_text)

    def test_does_not_rewrite_file_when_content_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity = self._identity(tmp)
            out_dir = Path(tmp) / "generated"
            paths = ec.generate_metadata_files(out_dir, identity)
            first_mtime = paths["json"].stat().st_mtime_ns
            # Regenerate with the exact same identity -- content is
            # byte-identical, so the file must not be rewritten.
            ec.generate_metadata_files(out_dir, identity)
            second_mtime = paths["json"].stat().st_mtime_ns
        self.assertEqual(first_mtime, second_mtime)

    def test_rewrites_file_when_content_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity = self._identity(tmp)
            out_dir = Path(tmp) / "generated"
            paths = ec.generate_metadata_files(out_dir, identity)
            original = paths["json"].read_text(encoding="utf-8")

            identity.rom_revision = 9
            ec.generate_metadata_files(out_dir, identity)
            updated = paths["json"].read_text(encoding="utf-8")
        self.assertNotEqual(original, updated)


class CliTests(unittest.TestCase):
    SCRIPT = ROOT / "scripts" / "modernize" / "expansion_config.py"

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(self.SCRIPT), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_validate_succeeds_silently_for_valid_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            result = self.run_cli(
                "validate",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_resolve_prints_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            result = self.run_cli(
                "resolve",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MODERN_BUILD_COMMIT=", result.stdout)
        self.assertIn("MODERN_CONFIG_FINGERPRINT=", result.stdout)
        self.assertIn("MODERN_VERSION_STRING=0.1.0", result.stdout)
        self.assertIn("MODERN_SAVE_COMPAT_EPOCH=1", result.stdout)

    def test_resolve_save_compat_epoch_override_changes_token_not_fingerprint(
        self,
    ):
        """Regression test for issue #2 slice 1 review finding #4 (HIGH):
        modern.mk threads --save-compat-epoch through this CLI's resolve
        command to get the MODERN_SAVE_COMPAT_EPOCH token it embeds in
        MODERN_CFLAGS's -D define and in the compile-settings stamp. This
        proves the override changes that token while leaving
        MODERN_CONFIG_FINGERPRINT untouched -- the save-compat epoch must
        remain a distinct compatibility gate, never folded into the #8
        config fingerprint (see ExpansionIdentity.fingerprint_fields)."""
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            baseline = self.run_cli(
                "resolve",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
            )
            overridden = self.run_cli(
                "resolve",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
                "--save-compat-epoch", "2",
            )
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        self.assertEqual(overridden.returncode, 0, overridden.stderr)
        self.assertIn("MODERN_SAVE_COMPAT_EPOCH=1", baseline.stdout)
        self.assertIn("MODERN_SAVE_COMPAT_EPOCH=2", overridden.stdout)

        def fingerprint_of(stdout: str) -> str:
            for token in stdout.split():
                if token.startswith("MODERN_CONFIG_FINGERPRINT="):
                    return token
            raise AssertionError(f"no fingerprint token in: {stdout}")

        self.assertEqual(
            fingerprint_of(baseline.stdout), fingerprint_of(overridden.stdout)
        )

    def test_resolve_prints_locale_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            result = self.run_cli(
                "resolve",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MODERN_EXPANSION_ENABLED_LOCALE_MASK=1", result.stdout)
        self.assertIn("MODERN_EXPANSION_DEFAULT_LOCALE_ID=0", result.stdout)
        self.assertIn("MODERN_EXPANSION_PSEUDO_LOCALE_ENABLED=0", result.stdout)

    def test_resolve_locale_overrides_change_tokens_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            baseline = self.run_cli(
                "resolve",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
            )
            overridden = self.run_cli(
                "resolve",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
                "--enabled-locales", "en,qps-ploc",
                "--pseudo-locale", "1",
            )
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        self.assertEqual(overridden.returncode, 0, overridden.stderr)
        self.assertIn("MODERN_EXPANSION_ENABLED_LOCALE_MASK=1 ", baseline.stdout)
        self.assertIn("MODERN_EXPANSION_ENABLED_LOCALE_MASK=129", overridden.stdout)

        def fingerprint_of(stdout: str) -> str:
            for token in stdout.split():
                if token.startswith("MODERN_CONFIG_FINGERPRINT="):
                    return token
            raise AssertionError(f"no fingerprint token in: {stdout}")

        self.assertNotEqual(fingerprint_of(baseline.stdout), fingerprint_of(overridden.stdout))

    def test_resolve_fails_early_on_inconsistent_locale_combination(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            result = self.run_cli(
                "resolve",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
                "--pseudo-locale", "1",  # qps-ploc not enabled -- must fail
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("error:", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_resolve_cjk_profiles_require_32m_and_emit_real_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            rejected = self.run_cli(
                "resolve",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
                "--enabled-locales", "en,ja",
            )
            accepted = self.run_cli(
                "resolve",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "32M",
                "--repo-root", tmp,
                "--enabled-locales", "zh-Hans,en,ja",
                "--default-locale", "zh-Hans",
            )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("MODERN_ROM_SIZE=32M", rejected.stderr)
        self.assertEqual(rejected.stdout, "")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertIn("MODERN_EXPANSION_ENABLED_LOCALE_MASK=7", accepted.stdout)
        self.assertIn("MODERN_EXPANSION_DEFAULT_LOCALE_ID=2", accepted.stdout)

    def test_generate_writes_metadata_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            out_dir = Path(tmp) / "generated"
            result = self.run_cli(
                "generate",
                "--config-mk", str(config_mk),
                "--config", "release",
                "--abi", "apcs-gnu",
                "--rom-size", "32M",
                "--repo-root", tmp,
                "--output-dir", str(out_dir),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((out_dir / "expansion_build_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(data["config_preset"], "release")
            self.assertEqual(data["abi"], "apcs-gnu")
            self.assertEqual(data["rom_size_bytes"], 32 * 1024 * 1024)

    def test_resolve_honors_identity_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            result = self.run_cli(
                "resolve",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
                "--title", "FE8CUSTOMTST",
                "--game-code", "ZZZZ",
                "--maker-code", "9X",
                "--revision", "7",
            )
            out_dir = Path(tmp) / "generated"
            self.run_cli(
                "generate",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
                "--output-dir", str(out_dir),
                "--title", "FE8CUSTOMTST",
                "--game-code", "ZZZZ",
                "--maker-code", "9X",
                "--revision", "7",
            )
            data = json.loads(
                (out_dir / "expansion_build_metadata.json").read_text(encoding="utf-8")
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["rom_title"], "FE8CUSTOMTST")
        self.assertEqual(data["rom_game_code"], "ZZZZ")
        self.assertEqual(data["rom_maker_code"], "9X")
        self.assertEqual(data["rom_revision"], 7)

    # -- invalid inputs / incompatible combinations fail before any write ---

    def test_invalid_title_fails_before_writing_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp), rom_title="TOOLONGTITLE!!")
            out_dir = Path(tmp) / "generated"
            result = self.run_cli(
                "generate",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
                "--output-dir", str(out_dir),
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EXPANSION_ROM_TITLE", result.stderr)
        self.assertFalse(out_dir.exists())

    def test_invalid_game_code_fails_before_writing_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp), rom_game_code="ABC")
            out_dir = Path(tmp) / "generated"
            result = self.run_cli(
                "generate",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
                "--output-dir", str(out_dir),
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EXPANSION_ROM_GAME_CODE", result.stderr)
        self.assertFalse(out_dir.exists())

    def test_unsupported_preset_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            result = self.run_cli(
                "validate",
                "--config-mk", str(config_mk),
                "--config", "profiling",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error", result.stderr)

    def test_unsupported_abi_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            result = self.run_cli(
                "validate",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "eabi",
                "--rom-size", "16M",
                "--repo-root", tmp,
            )
        self.assertNotEqual(result.returncode, 0)
        # argparse enforces the choices= constraint itself (SUPPORTED_ABIS),
        # so an unsupported --abi is rejected before validate_abi() even
        # runs -- still an actionable, pre-compilation diagnostic.
        self.assertIn("--abi", result.stderr)
        self.assertIn("invalid choice", result.stderr)

    def test_unsupported_rom_size_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            result = self.run_cli(
                "validate",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "8M",
                "--repo-root", tmp,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MODERN_ROM_SIZE", result.stderr)

    def test_invalid_build_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            result = self.run_cli(
                "validate",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
                "--build-id", "not-a-sha-branch-name",
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EXPANSION_BUILD_ID", result.stderr)

    def test_missing_config_mk_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(
                "validate",
                "--config-mk", str(Path(tmp) / "does-not-exist.mk"),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("config.mk", result.stderr)


class ValidateFeatureFlagTests(unittest.TestCase):
    """Issue #6: each starter-feature flag is a strict 0/1 build switch."""

    def test_zero_and_one_pass_through(self):
        self.assertEqual(ec.validate_feature_flag("EXPANSION_MECHANICS_HOOKS", "0"), 0)
        self.assertEqual(ec.validate_feature_flag("EXPANSION_MECHANICS_HOOKS", "1"), 1)
        self.assertEqual(ec.validate_feature_flag("EXPANSION_MECHANICS_HOOKS", 1), 1)

    def test_negative_one_rejected(self):
        with self.assertRaises(ec.ConfigError) as ctx:
            ec.validate_feature_flag("EXPANSION_MECHANICS_HOOKS", "-1")
        self.assertIn("EXPANSION_MECHANICS_HOOKS", str(ctx.exception))

    def test_two_rejected(self):
        with self.assertRaises(ec.ConfigError) as ctx:
            ec.validate_feature_flag("EXPANSION_DANGER_OVERLAY_MENU", "2")
        self.assertIn("out of range", str(ctx.exception))

    def test_text_rejected(self):
        with self.assertRaises(ec.ConfigError) as ctx:
            ec.validate_feature_flag("EXPANSION_MECHANICS_SAMPLE", "yes")
        self.assertIn("not an integer", str(ctx.exception))


class ValidateFeatureFlagRelationshipTests(unittest.TestCase):
    """Issue #6: the sample mechanic can only exist with the hook registry."""

    def test_sample_requires_hooks(self):
        with self.assertRaises(ec.ConfigError) as ctx:
            ec.validate_feature_flags("0", "1", "0")
        message = str(ctx.exception)
        self.assertIn("EXPANSION_MECHANICS_SAMPLE=1", message)
        self.assertIn("EXPANSION_MECHANICS_HOOKS=1", message)

    def test_sample_with_hooks_is_ok(self):
        self.assertEqual(ec.validate_feature_flags("1", "1", "0"), (1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0))

    def test_all_off_is_ok(self):
        self.assertEqual(ec.validate_feature_flags("0", "0", "0"), (0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0))

    def test_hooks_without_sample_is_ok(self):
        self.assertEqual(ec.validate_feature_flags("1", "0", "1"), (1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0))

    def test_content_defaults_off_for_legacy_three_argument_callers(self):
        """The issue #6 Sprint 2 content flag is an OPTIONAL fourth switch:
        an existing three-argument call keeps its exact previous meaning and
        simply resolves the content flag to 0."""
        self.assertEqual(ec.validate_feature_flags("1", "1", "1"), (1, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0))


class LoadIdentityFeatureFlagTests(unittest.TestCase):
    """Issue #6: flags flow into the identity/JSON and the fingerprint, but
    never into the independent save-compatibility epoch/key."""

    def _identity(self, tmp, **kwargs):
        config_mk = write_config_mk(Path(tmp))
        return ec.load_identity(
            config_mk_path=config_mk,
            config_preset="debug",
            abi="aapcs",
            rom_size="16M",
            repo_root=Path(tmp),
            **kwargs,
        )

    def test_absent_flags_default_to_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity = self._identity(tmp)
        self.assertEqual(identity.mechanics_hooks, 0)
        self.assertEqual(identity.mechanics_sample, 0)
        self.assertEqual(identity.danger_overlay_menu, 0)

    def test_flags_appear_in_json_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity = self._identity(tmp, mechanics_hooks="1", danger_overlay_menu="1")
        data = identity.to_dict()
        self.assertEqual(data["mechanics_hooks"], 1)
        self.assertEqual(data["mechanics_sample"], 0)
        self.assertEqual(data["danger_overlay_menu"], 1)

    def test_flag_change_changes_fingerprint_but_not_epoch_or_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._identity(tmp)
            hooks = self._identity(tmp, mechanics_hooks="1")
            sample = self._identity(tmp, mechanics_hooks="1", mechanics_sample="1")
            danger = self._identity(tmp, danger_overlay_menu="1")
        # Every flag toggle changes the config fingerprint...
        self.assertNotEqual(base.config_fingerprint, hooks.config_fingerprint)
        self.assertNotEqual(hooks.config_fingerprint, sample.config_fingerprint)
        self.assertNotEqual(base.config_fingerprint, danger.config_fingerprint)
        # ...while the save-compatibility epoch/key is untouched by all of them.
        for identity in (base, hooks, sample, danger):
            self.assertEqual(identity.save_compat_epoch, 1)

    def test_feature_flags_are_not_in_save_compat_key(self):
        """The save-compatibility gate is the epoch alone; flags live only in
        the diagnostic fingerprint, so they can never make an existing save
        look incompatible."""
        with tempfile.TemporaryDirectory() as tmp:
            base = self._identity(tmp)
            hooks = self._identity(tmp, mechanics_hooks="1")
        self.assertEqual(base.save_compat_epoch, hooks.save_compat_epoch)
        self.assertIn("features", base.fingerprint_fields())
        self.assertNotIn("save_compat_epoch", base.fingerprint_fields())

    def test_sample_without_hooks_rejected_in_load_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ec.ConfigError):
                self._identity(tmp, mechanics_sample="1")


class FeatureFlagCliTests(unittest.TestCase):
    SCRIPT = ROOT / "scripts" / "modernize" / "expansion_config.py"

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(self.SCRIPT), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def _resolve(self, tmp, *extra):
        config_mk = write_config_mk(Path(tmp))
        return self.run_cli(
            "resolve",
            "--config-mk", str(config_mk),
            "--config", "debug",
            "--abi", "aapcs",
            "--rom-size", "16M",
            "--repo-root", tmp,
            *extra,
        )

    @staticmethod
    def _fingerprint_of(stdout):
        for token in stdout.split():
            if token.startswith("MODERN_CONFIG_FINGERPRINT="):
                return token
        raise AssertionError(f"no fingerprint token in: {stdout}")

    def test_hooks_flag_changes_fingerprint_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = self._resolve(tmp)
            hooks = self._resolve(tmp, "--mechanics-hooks", "1")
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        self.assertEqual(hooks.returncode, 0, hooks.stderr)
        self.assertNotEqual(
            self._fingerprint_of(baseline.stdout), self._fingerprint_of(hooks.stdout)
        )
        # The epoch token is unchanged by a feature-flag toggle.
        self.assertIn("MODERN_SAVE_COMPAT_EPOCH=1", baseline.stdout)
        self.assertIn("MODERN_SAVE_COMPAT_EPOCH=1", hooks.stdout)

    def test_sample_without_hooks_fails_at_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._resolve(tmp, "--mechanics-sample", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EXPANSION_MECHANICS_SAMPLE=1", result.stderr)

    def test_invalid_flag_value_fails_at_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._resolve(tmp, "--danger-overlay-menu", "2")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("out of range", result.stderr)

    def test_generate_json_contains_feature_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_mk = write_config_mk(Path(tmp))
            out_dir = Path(tmp) / "generated"
            result = self.run_cli(
                "generate",
                "--config-mk", str(config_mk),
                "--config", "debug",
                "--abi", "aapcs",
                "--rom-size", "16M",
                "--repo-root", tmp,
                "--mechanics-hooks", "1",
                "--danger-overlay-menu", "1",
                "--output-dir", str(out_dir),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(
                (out_dir / "expansion_build_metadata.json").read_text(encoding="utf-8")
            )
        self.assertEqual(data["mechanics_hooks"], 1)
        self.assertEqual(data["mechanics_sample"], 0)
        self.assertEqual(data["danger_overlay_menu"], 1)


class StarterContentFlagTests(unittest.TestCase):
    """Issue #6 Sprint 2: the EXPANSION_STARTER_CONTENT opt-in flag.

    An independent 0/1 identity flag with two hard dependencies -- the
    mechanics hook registry, and an item ID cap that actually reaches
    ITEM_EXPANSION_CE -- folded into the config fingerprint and the
    generated metadata, and deliberately NOT part of the save format.
    """

    def _identity(self, **kwargs):
        params = dict(
            config_mk_path=ROOT / "config.mk",
            config_preset="release",
            abi="aapcs",
            rom_size="16M",
            build_id_override="abcdef12",
        )
        params.update(kwargs)
        return ec.load_identity(**params)

    def test_default_is_off(self):
        identity = self._identity()
        self.assertEqual(identity.starter_content, 0)
        self.assertEqual(
            identity.fingerprint_fields()["features"]["starter_content"], 0)

    def test_config_mk_default_is_zero(self):
        cfg = ec.parse_config_mk(ROOT / "config.mk")
        self.assertEqual(cfg["EXPANSION_STARTER_CONTENT"], "0")

    def test_enabled_requires_mechanics_hooks(self):
        with self.assertRaises(ec.ConfigError) as ctx:
            self._identity(starter_content=1, mechanics_hooks=0,
                           item_id_cap="0xCE")
        message = str(ctx.exception)
        self.assertIn("EXPANSION_STARTER_CONTENT=1", message)
        self.assertIn("EXPANSION_MECHANICS_HOOKS=1", message)

    def test_enabled_requires_expanded_item_cap(self):
        with self.assertRaises(ec.ConfigError) as ctx:
            self._identity(starter_content=1, mechanics_hooks=1)
        message = str(ctx.exception)
        self.assertIn("EXPANSION_STARTER_CONTENT=1", message)
        self.assertIn("FE8_ITEM_ID_CAP", message)
        self.assertIn("ITEM_EXPANSION_CE", message)

    def test_enabled_with_both_dependencies_resolves(self):
        identity = self._identity(starter_content=1, mechanics_hooks=1,
                                  item_id_cap="0xCE")
        self.assertEqual(identity.starter_content, 1)

    def test_invalid_values_rejected_actionably(self):
        for bad in ("2", "-1", "yes", ""):
            if bad == "":
                continue
            with self.assertRaises(ec.ConfigError) as ctx:
                self._identity(starter_content=bad, mechanics_hooks=1,
                               item_id_cap="0xCE")
            self.assertIn("EXPANSION_STARTER_CONTENT", str(ctx.exception))

    def test_platform_stays_testable_at_any_cap_with_content_off(self):
        """The dependency is one-way: raising the cap alone must never
        require the content flag, so the issue #10 ID-space platform stays
        independently testable."""
        for cap in (None, "0xCD", "0xCE", "0xFF"):
            identity = self._identity(starter_content=0, item_id_cap=cap)
            self.assertEqual(identity.starter_content, 0)

    def test_flag_changes_the_config_fingerprint(self):
        off = self._identity(starter_content=0, mechanics_hooks=1,
                             item_id_cap="0xCE")
        on = self._identity(starter_content=1, mechanics_hooks=1,
                            item_id_cap="0xCE")
        self.assertNotEqual(off.config_fingerprint, on.config_fingerprint)

    def test_flag_never_changes_the_save_compat_epoch(self):
        off = self._identity(starter_content=0, mechanics_hooks=1,
                             item_id_cap="0xCE")
        on = self._identity(starter_content=1, mechanics_hooks=1,
                            item_id_cap="0xCE")
        self.assertEqual(off.save_compat_epoch, on.save_compat_epoch)
        # Compared against the real, committed config.mk's current epoch
        # (issue #18 sprint 2 bumped it 1 -> 2) rather than a hardcoded
        # literal, so this test never silently drifts from that file again.
        cfg = ec.parse_config_mk(ROOT / "config.mk")
        self.assertEqual(
            on.save_compat_epoch, int(cfg["EXPANSION_SAVE_COMPAT_EPOCH"])
        )

    def test_flag_appears_in_generated_metadata_json(self):
        identity = self._identity(starter_content=1, mechanics_hooks=1,
                                  item_id_cap="0xCE")
        with tempfile.TemporaryDirectory() as tmp:
            paths = ec.generate_metadata_files(Path(tmp), identity)
            data = json.loads(paths["json"].read_text(encoding="utf-8"))
        self.assertEqual(data["starter_content"], 1)

    def test_item_cap_constants_match_the_idspace_source_of_truth(self):
        """expansion_config.py restates the item cap boundary because it runs
        as a bare script; it must never drift from idspace.py, which owns it."""
        sys.path.insert(0, str(ROOT))
        from scripts.generated_data import idspace

        self.assertEqual(ec.ITEM_ID_EXPANSION_FIRST, idspace.ITEM_EXPANSION_FIRST)
        self.assertEqual(ec.ITEM_ID_DEFAULT_CAP, idspace.ITEM_DEFAULT_CAP)
        self.assertEqual(ec.ITEM_ID_DEFAULT_CAP,
                         idspace.domain_by_key("item").configured_cap)

    def test_invalid_item_cap_rejected(self):
        with self.assertRaises(ec.ConfigError):
            self._identity(item_id_cap="not-a-number")
        with self.assertRaises(ec.ConfigError):
            self._identity(item_id_cap="0x100")


class StarterContentCompileTimeContractTests(unittest.TestCase):
    """The same two dependencies must also be hard C compile errors."""

    def test_config_header_defaults_the_flag_off(self):
        text = (ROOT / "include" / "expansion_config.h").read_text(encoding="utf-8")
        self.assertIn("#ifndef FE8_EXPANSION_STARTER_CONTENT", text)
        self.assertIn("#define FE8_EXPANSION_STARTER_CONTENT 0", text)

    def test_config_header_errors_without_hooks(self):
        text = (ROOT / "include" / "expansion_config.h").read_text(encoding="utf-8")
        self.assertIn(
            "#if FE8_EXPANSION_STARTER_CONTENT && !FE8_EXPANSION_MECHANICS_HOOKS", text)

    def test_content_header_errors_below_the_expansion_cap(self):
        text = (ROOT / "include" / "expansion_starter_content.h").read_text(
            encoding="utf-8")
        self.assertIn("#if ITEM_ID_CONFIGURED_CAP < ITEM_ID_EXPANSION_FIRST", text)

    def test_modern_mk_flows_the_flag_and_cap(self):
        text = (ROOT / "modern.mk").read_text(encoding="utf-8")
        self.assertIn("-DFE8_EXPANSION_STARTER_CONTENT=$(EXPANSION_STARTER_CONTENT)", text)
        self.assertIn('--starter-content "$(EXPANSION_STARTER_CONTENT)"', text)
        self.assertIn('--item-id-cap "$(FE8_ITEM_ID_CAP)"', text)
        self.assertIn("starter_content=$(EXPANSION_STARTER_CONTENT)", text)


if __name__ == "__main__":
    unittest.main()
