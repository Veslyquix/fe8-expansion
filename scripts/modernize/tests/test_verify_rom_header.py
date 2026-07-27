"""Tests for scripts/modernize/verify_rom_header.py.

Covers valid-header round-tripping and each individually detected mismatch:
wrong size, title, game code, maker code, fixed byte, and checksum. Also
covers the CLI entry point's exit codes and stderr messaging, plus the
--size option (named '16M'/'32M' sizes, exact byte counts, and invalid
values) that lets callers -- e.g. modern.mk's expansion-modern-rom recipe --
verify ROMs configured for a size other than the 16 MiB default. Also
covers the embedded ExpansionMetadata record (issue #8): locating, parsing,
and verifying it via find_expansion_metadata/parse_expansion_metadata/
verify_expansion_metadata and the expected_revision/expected_metadata
verify_rom_header kwargs, plus the --title/--game-code/--maker-code/
--revision/--metadata-json CLI flags. All tests build a synthetic, minimal
GBA header in memory; none depend on a real ROM build or the modern
toolchain.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "modernize"))

import verify_rom_header as vrh  # noqa: E402


def make_valid_header(size: int = vrh.EXPECTED_SIZE) -> bytearray:
    """Build a minimal, checksum-correct 16 MiB ROM image in memory."""
    data = bytearray(b"\xff" * size)
    data[vrh.HEADER_TITLE_OFFSET : vrh.HEADER_TITLE_OFFSET + vrh.HEADER_TITLE_SIZE] = (
        vrh.EXPECTED_TITLE.encode("ascii").ljust(vrh.HEADER_TITLE_SIZE, b"\x00")
    )
    data[
        vrh.HEADER_GAME_CODE_OFFSET : vrh.HEADER_GAME_CODE_OFFSET
        + vrh.HEADER_GAME_CODE_SIZE
    ] = vrh.EXPECTED_GAME_CODE.encode("ascii")
    data[
        vrh.HEADER_MAKER_CODE_OFFSET : vrh.HEADER_MAKER_CODE_OFFSET
        + vrh.HEADER_MAKER_CODE_SIZE
    ] = vrh.EXPECTED_MAKER_CODE.encode("ascii")
    data[vrh.HEADER_FIXED_BYTE_OFFSET] = vrh.EXPECTED_FIXED_BYTE
    data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
    return data


def make_metadata_dict(**overrides) -> dict:
    """A complete, valid expansion_build_metadata.json-shaped dict (see
    scripts/modernize/expansion_config.py's ExpansionIdentity.to_dict()),
    with any field overridable for mismatch tests."""
    base = {
        "version_major": 0,
        "version_minor": 1,
        "version_patch": 0,
        "version_packed": 256,
        "version_string": "0.1.0",
        "build_commit": "a" * 40,
        "config_fingerprint": "0123456789abcdef",
        "config_preset": "debug",
        "abi": "aapcs",
        "rom_title": "FIREEMBLEM2E",
        "rom_game_code": "BE8E",
        "rom_maker_code": "01",
        "rom_revision": 0,
        "rom_size_bytes": 16 * 1024 * 1024,
        "enabled_locale_mask": 1,
        "default_locale_id": 0,
        "pseudo_locale_enabled": 0,
    }
    base.update(overrides)
    return base


def pack_metadata(metadata: dict) -> bytes:
    """Pack a make_metadata_dict()-shaped dict into the exact on-ROM byte
    layout of struct ExpansionMetadata (include/expansion_metadata.h),
    mirroring src/expansion_metadata.c's field order exactly."""
    return vrh.EXPANSION_METADATA_STRUCT.pack(
        vrh.EXPANSION_METADATA_MAGIC,
        metadata["version_major"],
        metadata["version_minor"],
        metadata["version_patch"],
        0,  # reserved0
        metadata["version_packed"],
        metadata["version_string"].encode("ascii"),
        metadata["build_commit"].encode("ascii"),
        metadata["config_fingerprint"].encode("ascii"),
        metadata["config_preset"].encode("ascii"),
        metadata["abi"].encode("ascii"),
        metadata["rom_title"].encode("ascii"),
        metadata["rom_game_code"].encode("ascii"),
        metadata["rom_maker_code"].encode("ascii"),
        metadata["rom_revision"],
        metadata["rom_size_bytes"],
        metadata["enabled_locale_mask"],
        metadata["default_locale_id"],
        metadata["pseudo_locale_enabled"],
        b"\x00\x00",  # reserved1
    )


def embed_metadata(data: bytearray, metadata: dict, offset: int = 0x1000) -> bytearray:
    """Embed a packed ExpansionMetadata record into a synthetic ROM image at
    a 4-byte-aligned offset (mirroring where the linker places .rodata)."""
    assert offset % 4 == 0
    packed = pack_metadata(metadata)
    data[offset : offset + len(packed)] = packed
    return data


class VerifyRomHeaderTests(unittest.TestCase):
    def write_rom(self, directory: Path, data: bytes) -> Path:
        path = directory / "fixture.gba"
        path.write_bytes(data)
        return path

    def test_valid_header_reports_all_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = self.write_rom(Path(tmp), make_valid_header())
            facts = vrh.verify_rom_header(rom)
        self.assertEqual(facts["size"], vrh.EXPECTED_SIZE)
        self.assertEqual(facts["title"], vrh.EXPECTED_TITLE)
        self.assertEqual(facts["game_code"], vrh.EXPECTED_GAME_CODE)
        self.assertEqual(facts["maker_code"], vrh.EXPECTED_MAKER_CODE)
        self.assertEqual(facts["fixed_byte"], vrh.EXPECTED_FIXED_BYTE)
        self.assertEqual(
            facts["checksum"], vrh.compute_checksum(bytes(make_valid_header()))
        )

    def test_wrong_size_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = self.write_rom(Path(tmp), make_valid_header()[:-1])
            with self.assertRaises(vrh.RomHeaderError) as ctx:
                vrh.verify_rom_header(rom)
        self.assertIn("size", str(ctx.exception))
        self.assertIn(str(vrh.EXPECTED_SIZE), str(ctx.exception))

    def test_wrong_title_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_TITLE_OFFSET : vrh.HEADER_TITLE_OFFSET + 4] = b"XXXX"
            # Recompute checksum so only the title is wrong, isolating the check.
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            rom = self.write_rom(Path(tmp), data)
            with self.assertRaises(vrh.RomHeaderError) as ctx:
                vrh.verify_rom_header(rom)
        self.assertIn("title", str(ctx.exception))

    def test_wrong_game_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_GAME_CODE_OFFSET : vrh.HEADER_GAME_CODE_OFFSET + 4] = (
                b"ZZZZ"
            )
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            rom = self.write_rom(Path(tmp), data)
            with self.assertRaises(vrh.RomHeaderError) as ctx:
                vrh.verify_rom_header(rom)
        self.assertIn("game code", str(ctx.exception))

    def test_wrong_maker_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_MAKER_CODE_OFFSET : vrh.HEADER_MAKER_CODE_OFFSET + 2] = (
                b"99"
            )
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            rom = self.write_rom(Path(tmp), data)
            with self.assertRaises(vrh.RomHeaderError) as ctx:
                vrh.verify_rom_header(rom)
        self.assertIn("maker code", str(ctx.exception))

    def test_wrong_fixed_byte_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_FIXED_BYTE_OFFSET] = 0x00
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            rom = self.write_rom(Path(tmp), data)
            with self.assertRaises(vrh.RomHeaderError) as ctx:
                vrh.verify_rom_header(rom)
        self.assertIn("fixed header byte", str(ctx.exception))

    def test_wrong_checksum_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_CHECKSUM_OFFSET] ^= 0xFF
            rom = self.write_rom(Path(tmp), data)
            with self.assertRaises(vrh.RomHeaderError) as ctx:
                vrh.verify_rom_header(rom)
        self.assertIn("checksum", str(ctx.exception))

    def test_non_ascii_title_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_TITLE_OFFSET] = 0x01
            rom = self.write_rom(Path(tmp), data)
            with self.assertRaises(vrh.RomHeaderError) as ctx:
                vrh.verify_rom_header(rom)
        self.assertIn("printable ASCII", str(ctx.exception))

    def test_cli_exit_codes_and_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_rom = self.write_rom(root, make_valid_header())
            good = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                 str(valid_rom)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertIn("ROM header valid", good.stdout)

            bad_data = make_valid_header()
            bad_data[vrh.HEADER_CHECKSUM_OFFSET] ^= 0xFF
            bad_rom = self.write_rom(root, bad_data)
            bad = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                 str(bad_rom)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("checksum", bad.stderr)

    # -- --size CLI option / parse_size ---------------------------------------

    def test_parse_size_named_16m_is_case_insensitive(self):
        for text in ("16M", "16m"):
            self.assertEqual(vrh.parse_size(text), 16 * 1024 * 1024)

    def test_parse_size_named_32m_is_case_insensitive(self):
        for text in ("32M", "32m"):
            self.assertEqual(vrh.parse_size(text), 32 * 1024 * 1024)

    def test_parse_size_accepts_exact_byte_counts(self):
        self.assertEqual(vrh.parse_size("1024"), 1024)
        self.assertEqual(vrh.parse_size("0x1000000"), 0x1000000)

    def test_parse_size_rejects_non_numeric_garbage(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            vrh.parse_size("64M")  # not one of the named sizes, not numeric

    def test_parse_size_rejects_zero_and_negative(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            vrh.parse_size("0")
        with self.assertRaises(argparse.ArgumentTypeError):
            vrh.parse_size("-1")

    def test_verify_rom_header_accepts_explicit_expected_size(self):
        thirty_two_mib = 32 * 1024 * 1024
        with tempfile.TemporaryDirectory() as tmp:
            rom = self.write_rom(Path(tmp), make_valid_header(thirty_two_mib))
            facts = vrh.verify_rom_header(rom, expected_size=thirty_two_mib)
        self.assertEqual(facts["size"], thirty_two_mib)

    def test_verify_rom_header_rejects_16m_rom_when_32m_expected(self):
        thirty_two_mib = 32 * 1024 * 1024
        with tempfile.TemporaryDirectory() as tmp:
            rom = self.write_rom(Path(tmp), make_valid_header())  # 16 MiB
            with self.assertRaises(vrh.RomHeaderError) as ctx:
                vrh.verify_rom_header(rom, expected_size=thirty_two_mib)
        self.assertIn(str(thirty_two_mib), str(ctx.exception))

    def test_cli_size_flag_accepts_valid_32m_rom(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = self.write_rom(Path(tmp), make_valid_header(32 * 1024 * 1024))
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                 "--size", "32M", str(rom)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ROM header valid", result.stdout)

    def test_cli_size_flag_rejects_16m_rom_requested_as_32m(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = self.write_rom(Path(tmp), make_valid_header())  # 16 MiB
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                 "--size", "32M", str(rom)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("size", result.stderr)
        self.assertIn(str(32 * 1024 * 1024), result.stderr)

    def test_cli_size_flag_defaults_to_16m(self):
        """Omitting --size entirely must preserve the pre-32M-support
        default behavior of requiring exactly 16 MiB."""
        with tempfile.TemporaryDirectory() as tmp:
            rom = self.write_rom(Path(tmp), make_valid_header())  # 16 MiB
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                 str(rom)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_size_flag_rejects_invalid_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = self.write_rom(Path(tmp), make_valid_header())
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                 "--size", "not-a-size", str(rom)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid ROM size", result.stderr)

    def test_missing_rom_reports_error_not_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist.gba"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                 str(missing)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


    # -- expected_revision (issue #8) ------------------------------------------

    def test_expected_revision_none_skips_check(self):
        """Preserve prior behavior: no expected_revision means the revision
        byte is never inspected, no matter its value."""
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_SOFTWARE_VERSION_OFFSET] = 200
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            rom = self.write_rom(Path(tmp), data)
            facts = vrh.verify_rom_header(rom)
        self.assertEqual(facts["revision"], 200)

    def test_expected_revision_matching_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_SOFTWARE_VERSION_OFFSET] = 7
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            rom = self.write_rom(Path(tmp), data)
            facts = vrh.verify_rom_header(rom, expected_revision=7)
        self.assertEqual(facts["revision"], 7)

    def test_expected_revision_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_SOFTWARE_VERSION_OFFSET] = 3
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            rom = self.write_rom(Path(tmp), data)
            with self.assertRaises(vrh.RomHeaderError) as ctx:
                vrh.verify_rom_header(rom, expected_revision=9)
        self.assertIn("revision", str(ctx.exception))


class ExpansionMetadataTests(unittest.TestCase):
    """Tests for the embedded ExpansionMetadata record (issue #8): locating
    it via find_expansion_metadata, parsing via parse_expansion_metadata,
    and verifying it against a generated expansion_build_metadata.json-
    shaped dict via verify_expansion_metadata / verify_rom_header's
    expected_metadata kwarg."""

    def write_rom(self, directory: Path, data: bytes) -> Path:
        path = directory / "fixture.gba"
        path.write_bytes(data)
        return path

    def test_find_expansion_metadata_locates_record(self):
        data = make_valid_header()
        metadata = make_metadata_dict()
        embed_metadata(data, metadata, offset=0x2000)
        offset = vrh.find_expansion_metadata(bytes(data))
        self.assertEqual(offset, 0x2000)

    def test_find_expansion_metadata_missing_is_rejected(self):
        data = make_valid_header()
        with self.assertRaises(vrh.ExpansionMetadataError) as ctx:
            vrh.find_expansion_metadata(bytes(data))
        self.assertIn("no embedded ExpansionMetadata record found", str(ctx.exception))

    def test_find_expansion_metadata_ambiguous_differing_records_rejected(self):
        data = make_valid_header()
        embed_metadata(data, make_metadata_dict(rom_revision=1), offset=0x2000)
        embed_metadata(data, make_metadata_dict(rom_revision=2), offset=0x3000)
        with self.assertRaises(vrh.ExpansionMetadataError) as ctx:
            vrh.find_expansion_metadata(bytes(data))
        self.assertIn("differing contents", str(ctx.exception))

    def test_find_expansion_metadata_duplicate_identical_records_ok(self):
        """Two byte-identical copies (e.g. an accidental duplicate section)
        are not ambiguous -- they agree, so the first offset is used."""
        data = make_valid_header()
        metadata = make_metadata_dict()
        embed_metadata(data, metadata, offset=0x2000)
        embed_metadata(data, metadata, offset=0x3000)
        offset = vrh.find_expansion_metadata(bytes(data))
        self.assertEqual(offset, 0x2000)

    def test_parse_expansion_metadata_round_trips_all_fields(self):
        data = make_valid_header()
        metadata = make_metadata_dict(
            version_major=1, version_minor=2, version_patch=3, rom_revision=42
        )
        embed_metadata(data, metadata, offset=0x2000)
        record = vrh.parse_expansion_metadata(bytes(data))
        for key, value in metadata.items():
            self.assertEqual(record[key], value, key)

    def test_parse_expansion_metadata_truncated_record_rejected(self):
        data = make_valid_header()
        metadata = make_metadata_dict()
        embed_metadata(data, metadata, offset=len(data) - 8)
        # Only 8 bytes remain after the magic -- far short of a full record.
        with self.assertRaises(vrh.ExpansionMetadataError) as ctx:
            vrh.parse_expansion_metadata(bytes(data), offset=len(data) - 8)
        self.assertIn("truncated", str(ctx.exception))

    def test_verify_expansion_metadata_all_fields_match(self):
        data = make_valid_header()
        metadata = make_metadata_dict()
        embed_metadata(data, metadata, offset=0x2000)
        record = vrh.verify_expansion_metadata(bytes(data), metadata)
        self.assertEqual(record["build_commit"], metadata["build_commit"])

    def test_verify_expansion_metadata_detects_each_mismatched_field(self):
        mismatches = {
            "version_major": 9,
            "build_commit": "b" * 40,
            "config_fingerprint": "fedcba9876543210",
            "config_preset": "release",
            "abi": "apcs-gnu",
            "rom_title": "OTHERTITLE",
            "rom_game_code": "ZZZZ",
            "rom_maker_code": "9X",
            "rom_revision": 5,
            "rom_size_bytes": 32 * 1024 * 1024,
            "enabled_locale_mask": 0x81,
            "default_locale_id": 7,
            "pseudo_locale_enabled": 1,
        }
        for field, bad_value in mismatches.items():
            with self.subTest(field=field):
                data = make_valid_header()
                embedded = make_metadata_dict()
                embed_metadata(data, embedded, offset=0x2000)
                expected = make_metadata_dict()
                expected[field] = bad_value
                with self.assertRaises(vrh.ExpansionMetadataError) as ctx:
                    vrh.verify_expansion_metadata(bytes(data), expected)
                self.assertIn(field, str(ctx.exception))

    def test_verify_expansion_metadata_ignores_keys_not_in_expected(self):
        """expected may be a partial dict; only keys present are checked."""
        data = make_valid_header()
        embed_metadata(data, make_metadata_dict(rom_revision=77), offset=0x2000)
        record = vrh.verify_expansion_metadata(bytes(data), {"rom_revision": 77})
        self.assertEqual(record["rom_revision"], 77)

    def test_verify_rom_header_with_expected_metadata_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            metadata = make_metadata_dict()
            embed_metadata(data, metadata, offset=0x2000)
            rom = self.write_rom(Path(tmp), data)
            facts = vrh.verify_rom_header(rom, expected_metadata=metadata)
        self.assertIn("metadata", facts)
        self.assertEqual(facts["metadata"]["config_preset"], "debug")

    def test_verify_rom_header_with_expected_metadata_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            embed_metadata(data, make_metadata_dict(rom_revision=1), offset=0x2000)
            rom = self.write_rom(Path(tmp), data)
            with self.assertRaises(vrh.ExpansionMetadataError):
                vrh.verify_rom_header(
                    rom, expected_metadata=make_metadata_dict(rom_revision=2)
                )

    def test_verify_rom_header_missing_metadata_record_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = self.write_rom(Path(tmp), make_valid_header())
            with self.assertRaises(vrh.ExpansionMetadataError):
                vrh.verify_rom_header(rom, expected_metadata=make_metadata_dict())

    # -- CLI: --title/--game-code/--maker-code/--revision/--metadata-json ----

    def test_cli_title_game_code_maker_code_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_TITLE_OFFSET : vrh.HEADER_TITLE_OFFSET + vrh.HEADER_TITLE_SIZE] = (
                b"CUSTOMROM".ljust(vrh.HEADER_TITLE_SIZE, b"\x00")
            )
            data[
                vrh.HEADER_GAME_CODE_OFFSET : vrh.HEADER_GAME_CODE_OFFSET
                + vrh.HEADER_GAME_CODE_SIZE
            ] = b"ZZZZ"
            data[
                vrh.HEADER_MAKER_CODE_OFFSET : vrh.HEADER_MAKER_CODE_OFFSET
                + vrh.HEADER_MAKER_CODE_SIZE
            ] = b"9X"
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            rom = self.write_rom(Path(tmp), data)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                    "--title", "CUSTOMROM",
                    "--game-code", "ZZZZ",
                    "--maker-code", "9X",
                    str(rom),
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ROM header valid", result.stdout)

    def test_cli_revision_flag_matching_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_SOFTWARE_VERSION_OFFSET] = 5
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            rom = self.write_rom(Path(tmp), data)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                    "--revision", "5",
                    str(rom),
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_revision_flag_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_valid_header()
            data[vrh.HEADER_SOFTWARE_VERSION_OFFSET] = 5
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            rom = self.write_rom(Path(tmp), data)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                    "--revision", "6",
                    str(rom),
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("revision", result.stderr)

    def test_cli_metadata_json_supplies_defaults_and_verifies_embedded_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = make_metadata_dict(
                rom_title="CUSTOMROM", rom_game_code="ZZZZ", rom_maker_code="9X", rom_revision=5
            )
            data = make_valid_header()
            data[vrh.HEADER_TITLE_OFFSET : vrh.HEADER_TITLE_OFFSET + vrh.HEADER_TITLE_SIZE] = (
                b"CUSTOMROM".ljust(vrh.HEADER_TITLE_SIZE, b"\x00")
            )
            data[
                vrh.HEADER_GAME_CODE_OFFSET : vrh.HEADER_GAME_CODE_OFFSET
                + vrh.HEADER_GAME_CODE_SIZE
            ] = b"ZZZZ"
            data[
                vrh.HEADER_MAKER_CODE_OFFSET : vrh.HEADER_MAKER_CODE_OFFSET
                + vrh.HEADER_MAKER_CODE_SIZE
            ] = b"9X"
            data[vrh.HEADER_SOFTWARE_VERSION_OFFSET] = 5
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            embed_metadata(data, metadata, offset=0x2000)
            rom = self.write_rom(root, data)

            metadata_json = root / "expansion_build_metadata.json"
            metadata_json.write_text(json.dumps(metadata), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                    "--metadata-json", str(metadata_json),
                    str(rom),
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("embedded metadata valid", result.stdout)

    def test_cli_metadata_json_mismatch_fails_actionably(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = make_valid_header()
            data[vrh.HEADER_SOFTWARE_VERSION_OFFSET] = 0
            data[vrh.HEADER_CHECKSUM_OFFSET] = vrh.compute_checksum(bytes(data))
            embed_metadata(data, make_metadata_dict(config_fingerprint="1111111111111111"), offset=0x2000)
            rom = self.write_rom(root, data)

            metadata_json = root / "expansion_build_metadata.json"
            metadata_json.write_text(
                json.dumps(make_metadata_dict(config_fingerprint="2222222222222222")),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                    "--metadata-json", str(metadata_json),
                    str(rom),
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("config_fingerprint", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_metadata_json_missing_file_fails_actionably(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rom = self.write_rom(root, make_valid_header())
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "modernize" / "verify_rom_header.py"),
                    "--metadata-json", str(root / "does-not-exist.json"),
                    str(rom),
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
