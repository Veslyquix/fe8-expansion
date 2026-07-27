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
        self.assertEqual(ec.validate_feature_flags("1", "1", "0"), (1, 1, 0))

    def test_all_off_is_ok(self):
        self.assertEqual(ec.validate_feature_flags("0", "0", "0"), (0, 0, 0))

    def test_hooks_without_sample_is_ok(self):
        self.assertEqual(ec.validate_feature_flags("1", "0", "1"), (1, 0, 1))


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


if __name__ == "__main__":
    unittest.main()
