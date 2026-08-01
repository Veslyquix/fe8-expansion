#!/usr/bin/env python3
"""Verify a GBA ROM's header fields, size, and checksum.

Checks the fixed-format GBA cartridge header this project ships in
``src/rom_header.s``: exact ROM size, title, game code, maker code, the
fixed magic byte, and the checksum byte at offset 0xBD recomputed from the
header bytes at 0xA0..0xBC. This does not compare ROM contents byte-for-byte
against any other build; it only proves the produced ROM is a well-formed,
internally consistent GBA image with this project's expected identity
fields.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Optional

# Offsets are absolute file offsets, matching the GBA cartridge header layout
# starting at 0x00 (entry point) through 0xBF (end of the fixed header).
HEADER_TITLE_OFFSET = 0xA0
HEADER_TITLE_SIZE = 12
HEADER_GAME_CODE_OFFSET = 0xAC
HEADER_GAME_CODE_SIZE = 4
HEADER_MAKER_CODE_OFFSET = 0xB0
HEADER_MAKER_CODE_SIZE = 2
HEADER_FIXED_BYTE_OFFSET = 0xB2
# The GBA header's "software version" byte; this project uses it as the
# expansion framework's ROM revision (see config.mk EXPANSION_ROM_REVISION).
# expected_revision is optional (default None == "don't check") so every
# pre-existing caller that never mentioned revision keeps its old behavior.
HEADER_SOFTWARE_VERSION_OFFSET = 0xBC
HEADER_CHECKSUM_RANGE = (0xA0, 0xBC)  # inclusive start, inclusive end
HEADER_CHECKSUM_OFFSET = 0xBD
HEADER_CHECKSUM_MAGIC = 0x19
HEADER_END = 0xC0

# Expected identity fields, matching src/rom_header.s exactly.
EXPECTED_TITLE = "FIREEMBLEM2E"
EXPECTED_GAME_CODE = "BE8E"
EXPECTED_MAKER_CODE = "01"
EXPECTED_FIXED_BYTE = 0x96
EXPECTED_SIZE = 16 * 1024 * 1024  # 16 MiB, matching --pad-to 0x9000000

# Named ROM sizes accepted by --size, matching modern.mk's MODERN_ROM_SIZE
# values (16M -> --pad-to 0x9000000, 32M -> --pad-to 0xA000000).
NAMED_ROM_SIZES = {
    "16M": 16 * 1024 * 1024,
    "32M": 32 * 1024 * 1024,
}

# --- Embedded ExpansionMetadata record (see include/expansion_metadata.h,
# src/expansion_metadata.c). This mirrors that C struct's layout exactly --
# keep both in sync when changing either.
EXPANSION_METADATA_MAGIC = b"FE8M"
# Issue #18 sprint 1 appends the locale identity fields after
# rom_size_bytes (u32 enabledLocaleMask, u8 defaultLocale, u8
# pseudoLocaleEnabled, 2 reserved bytes) -- append-only, so every
# pre-existing offset above is unchanged; see include/expansion_metadata.h.
EXPANSION_METADATA_STRUCT = struct.Struct("<4sBBBBI16s41s17s8s12s13s5s3sBIIBB2s")
EXPANSION_METADATA_FIELDS = (
    "magic",
    "version_major",
    "version_minor",
    "version_patch",
    "reserved0",
    "version_packed",
    "version_string",
    "build_commit",
    "config_fingerprint",
    "config_preset",
    "abi",
    "rom_title",
    "rom_game_code",
    "rom_maker_code",
    "rom_revision",
    "rom_size_bytes",
    "enabled_locale_mask",
    "default_locale_id",
    "pseudo_locale_enabled",
    "reserved1",
)
# Fields holding fixed-size, NUL-terminated ASCII text that should be
# decoded to str (all struct fields except magic and the plain integers).
_EXPANSION_METADATA_TEXT_FIELDS = (
    "version_string",
    "build_commit",
    "config_fingerprint",
    "config_preset",
    "abi",
    "rom_title",
    "rom_game_code",
    "rom_maker_code",
)


class ExpansionMetadataError(Exception):
    """The embedded ExpansionMetadata record is missing or does not match
    the expected build metadata (expansion_build_metadata.json)."""


def find_expansion_metadata(data: bytes) -> int:
    """Locate the single embedded ExpansionMetadata record's file offset.

    Scans 4-byte-aligned offsets for EXPANSION_METADATA_MAGIC, matching how
    the record is placed in .rodata by src/expansion_metadata.c. Raises
    ExpansionMetadataError if the magic is absent, or if it is found more
    than once with differing contents (an ambiguous/inconsistent ROM).
    """
    found: list[int] = []
    start = 0
    while True:
        offset = data.find(EXPANSION_METADATA_MAGIC, start)
        if offset == -1:
            break
        if offset % 4 == 0 and offset + EXPANSION_METADATA_STRUCT.size <= len(data):
            found.append(offset)
        start = offset + 4
    if not found:
        raise ExpansionMetadataError(
            f"no embedded ExpansionMetadata record found (magic "
            f"{EXPANSION_METADATA_MAGIC!r} not present at a 4-byte-aligned offset)"
        )
    if len(found) > 1:
        blobs = {data[o : o + EXPANSION_METADATA_STRUCT.size] for o in found}
        if len(blobs) > 1:
            raise ExpansionMetadataError(
                f"found {len(found)} embedded ExpansionMetadata records at "
                f"offsets {found} with differing contents; expected exactly one"
            )
    return found[0]


def parse_expansion_metadata(data: bytes, offset: Optional[int] = None) -> dict:
    """Parse the embedded ExpansionMetadata record into a plain dict.

    If offset is None, it is located via find_expansion_metadata() first.
    """
    if offset is None:
        offset = find_expansion_metadata(data)
    raw = data[offset : offset + EXPANSION_METADATA_STRUCT.size]
    if len(raw) != EXPANSION_METADATA_STRUCT.size:
        raise ExpansionMetadataError(
            f"embedded ExpansionMetadata record at offset 0x{offset:X} is "
            f"truncated: got {len(raw)} bytes, expected "
            f"{EXPANSION_METADATA_STRUCT.size}"
        )
    values = EXPANSION_METADATA_STRUCT.unpack(raw)
    record = dict(zip(EXPANSION_METADATA_FIELDS, values))
    if record["magic"] != EXPANSION_METADATA_MAGIC:
        raise ExpansionMetadataError(
            f"embedded record magic {record['magic']!r} != expected "
            f"{EXPANSION_METADATA_MAGIC!r}"
        )
    for name in _EXPANSION_METADATA_TEXT_FIELDS:
        record[name] = record[name].split(b"\x00", 1)[0].decode("ascii")
    return record


def verify_expansion_metadata(data: bytes, expected: dict) -> dict:
    """Verify the embedded ExpansionMetadata record against `expected`
    (typically loaded from a generated expansion_build_metadata.json --
    see scripts/modernize/expansion_config.py). Raises
    ExpansionMetadataError naming the first mismatched field.
    """
    record = parse_expansion_metadata(data)

    checks = (
        ("version_major", "version_major"),
        ("version_minor", "version_minor"),
        ("version_patch", "version_patch"),
        ("version_packed", "version_packed"),
        ("version_string", "version_string"),
        ("build_commit", "build_commit"),
        ("config_fingerprint", "config_fingerprint"),
        ("config_preset", "config_preset"),
        ("abi", "abi"),
        ("rom_title", "rom_title"),
        ("rom_game_code", "rom_game_code"),
        ("rom_maker_code", "rom_maker_code"),
        ("rom_revision", "rom_revision"),
        ("rom_size_bytes", "rom_size_bytes"),
        ("enabled_locale_mask", "enabled_locale_mask"),
        ("default_locale_id", "default_locale_id"),
        ("pseudo_locale_enabled", "pseudo_locale_enabled"),
    )
    for record_key, expected_key in checks:
        if expected_key not in expected:
            continue
        actual_value = record[record_key]
        expected_value = expected[expected_key]
        if actual_value != expected_value:
            raise ExpansionMetadataError(
                f"embedded ExpansionMetadata field {record_key!r} is "
                f"{actual_value!r}; expected {expected_value!r}"
            )
    return record


class RomHeaderError(Exception):
    """The ROM's size, header fields, or checksum do not match expectations."""


def compute_checksum(data: bytes) -> int:
    """Recompute the header checksum byte from bytes 0xA0..0xBC inclusive."""
    start, end = HEADER_CHECKSUM_RANGE
    region = data[start : end + 1]
    return (-(sum(region) + HEADER_CHECKSUM_MAGIC)) & 0xFF


def decode_ascii_field(raw: bytes, label: str) -> str:
    value = raw.rstrip(b"\x00")
    if any(byte < 0x20 or byte > 0x7E for byte in value):
        raise RomHeaderError(f"ROM {label} is not printable ASCII: {raw!r}")
    return value.decode("ascii")


def parse_size(value: str) -> int:
    """Parse a --size argument: a named size ('16M', '32M') or an exact byte count.

    Named sizes are matched case-insensitively against NAMED_ROM_SIZES. Any
    other value is parsed as an integer byte count (accepts decimal or
    0x-prefixed hex). Raises argparse.ArgumentTypeError on anything else,
    including zero or negative byte counts.
    """
    named = NAMED_ROM_SIZES.get(value.strip().upper())
    if named is not None:
        return named
    try:
        size = int(value.strip(), 0)
    except ValueError as error:
        allowed = ", ".join(sorted(NAMED_ROM_SIZES))
        raise argparse.ArgumentTypeError(
            f"invalid ROM size {value!r}; expected one of [{allowed}] or an "
            f"exact byte count"
        ) from error
    if size <= 0:
        raise argparse.ArgumentTypeError(f"ROM size must be positive, got {size}")
    return size


def verify_rom_header(
    path: Path,
    expected_size: int = EXPECTED_SIZE,
    expected_title: str = EXPECTED_TITLE,
    expected_game_code: str = EXPECTED_GAME_CODE,
    expected_maker_code: str = EXPECTED_MAKER_CODE,
    expected_revision: Optional[int] = None,
    expected_metadata: Optional[dict] = None,
) -> dict[str, object]:
    """Verify size, identity fields, and checksum; return the parsed facts.

    ``expected_size``/``expected_title``/``expected_game_code``/
    ``expected_maker_code`` default to this module's EXPECTED_* constants,
    so every pre-existing caller that never mentions them keeps verifying
    today's exact hardcoded identity unchanged. ``expected_revision``
    defaults to None, meaning "don't check the revision byte at all" --
    also preserving prior behavior, since no earlier version of this
    function checked it. Passing an int enables that check.

    If ``expected_metadata`` (a dict, typically loaded from a generated
    expansion_build_metadata.json -- see
    scripts/modernize/expansion_config.py) is given, the embedded
    ExpansionMetadata record (see include/expansion_metadata.h) is also
    located and verified against it; the parsed record is included in the
    returned facts under "metadata". Raises RomHeaderError (header fields)
    or ExpansionMetadataError (embedded record) on any mismatch, naming
    the exact field and the expected vs. actual value.
    """
    size = path.stat().st_size
    if size != expected_size:
        raise RomHeaderError(
            f"ROM size {size} bytes does not match expected {expected_size} "
            f"bytes"
        )

    data = path.read_bytes()
    if len(data) < HEADER_END:
        raise RomHeaderError("ROM is too small to contain a GBA header")

    title = decode_ascii_field(
        data[HEADER_TITLE_OFFSET : HEADER_TITLE_OFFSET + HEADER_TITLE_SIZE],
        "title",
    )
    if title != expected_title:
        raise RomHeaderError(f"ROM title {title!r} != expected {expected_title!r}")

    game_code = decode_ascii_field(
        data[HEADER_GAME_CODE_OFFSET : HEADER_GAME_CODE_OFFSET + HEADER_GAME_CODE_SIZE],
        "game code",
    )
    if game_code != expected_game_code:
        raise RomHeaderError(
            f"ROM game code {game_code!r} != expected {expected_game_code!r}"
        )

    maker_code = decode_ascii_field(
        data[HEADER_MAKER_CODE_OFFSET : HEADER_MAKER_CODE_OFFSET + HEADER_MAKER_CODE_SIZE],
        "maker code",
    )
    if maker_code != expected_maker_code:
        raise RomHeaderError(
            f"ROM maker code {maker_code!r} != expected {expected_maker_code!r}"
        )

    fixed_byte = data[HEADER_FIXED_BYTE_OFFSET]
    if fixed_byte != EXPECTED_FIXED_BYTE:
        raise RomHeaderError(
            f"ROM fixed header byte 0x{fixed_byte:02X} != expected "
            f"0x{EXPECTED_FIXED_BYTE:02X}"
        )

    revision = data[HEADER_SOFTWARE_VERSION_OFFSET]
    if expected_revision is not None and revision != expected_revision:
        raise RomHeaderError(
            f"ROM revision {revision} != expected {expected_revision}"
        )

    expected_checksum = compute_checksum(data)
    actual_checksum = data[HEADER_CHECKSUM_OFFSET]
    if actual_checksum != expected_checksum:
        raise RomHeaderError(
            f"ROM checksum byte at 0x{HEADER_CHECKSUM_OFFSET:02X} is "
            f"0x{actual_checksum:02X}; recomputed from 0xA0..0xBC gives "
            f"0x{expected_checksum:02X}"
        )

    facts: dict[str, object] = {
        "size": size,
        "title": title,
        "game_code": game_code,
        "maker_code": maker_code,
        "fixed_byte": fixed_byte,
        "revision": revision,
        "checksum": actual_checksum,
    }

    if expected_metadata is not None:
        facts["metadata"] = verify_expansion_metadata(data, expected_metadata)

    return facts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="path to the GBA ROM to verify")
    parser.add_argument(
        "--size",
        type=parse_size,
        default=EXPECTED_SIZE,
        metavar="{16M,32M,BYTES}",
        help=(
            "expected ROM size: '16M' (default), '32M', or an exact byte "
            "count (decimal or 0x-prefixed hex)"
        ),
    )
    parser.add_argument(
        "--title", default=None, help=f"expected ROM title (default: {EXPECTED_TITLE!r})"
    )
    parser.add_argument(
        "--game-code",
        default=None,
        help=f"expected ROM game code (default: {EXPECTED_GAME_CODE!r})",
    )
    parser.add_argument(
        "--maker-code",
        default=None,
        help=f"expected ROM maker code (default: {EXPECTED_MAKER_CODE!r})",
    )
    parser.add_argument(
        "--revision",
        type=int,
        default=None,
        help="expected ROM revision byte (default: not checked)",
    )
    parser.add_argument(
        "--metadata-json",
        type=Path,
        default=None,
        help=(
            "path to a generated expansion_build_metadata.json (see "
            "scripts/modernize/expansion_config.py); when given, supplies "
            "defaults for --title/--game-code/--maker-code/--revision and "
            "additionally verifies the embedded ExpansionMetadata record"
        ),
    )
    args = parser.parse_args(argv)

    expected_metadata = None
    if args.metadata_json is not None:
        try:
            expected_metadata = json.loads(args.metadata_json.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"error: failed to read {args.metadata_json}: {error}", file=sys.stderr)
            return 1

    kwargs: dict[str, object] = {"expected_size": args.size}
    if args.title is not None:
        kwargs["expected_title"] = args.title
    elif expected_metadata is not None and "rom_title" in expected_metadata:
        kwargs["expected_title"] = expected_metadata["rom_title"]

    if args.game_code is not None:
        kwargs["expected_game_code"] = args.game_code
    elif expected_metadata is not None and "rom_game_code" in expected_metadata:
        kwargs["expected_game_code"] = expected_metadata["rom_game_code"]

    if args.maker_code is not None:
        kwargs["expected_maker_code"] = args.maker_code
    elif expected_metadata is not None and "rom_maker_code" in expected_metadata:
        kwargs["expected_maker_code"] = expected_metadata["rom_maker_code"]

    if args.revision is not None:
        kwargs["expected_revision"] = args.revision
    elif expected_metadata is not None and "rom_revision" in expected_metadata:
        kwargs["expected_revision"] = expected_metadata["rom_revision"]

    if expected_metadata is not None:
        kwargs["expected_metadata"] = expected_metadata

    try:
        facts = verify_rom_header(args.rom, **kwargs)
    except (RomHeaderError, ExpansionMetadataError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    summary = (
        f"ROM header valid: {args.rom} "
        f"(size={facts['size']} title={facts['title']!r} "
        f"game_code={facts['game_code']!r} maker_code={facts['maker_code']!r} "
        f"fixed_byte=0x{facts['fixed_byte']:02X} revision={facts['revision']} "
        f"checksum=0x{facts['checksum']:02X})"
    )
    if "metadata" in facts:
        metadata = facts["metadata"]
        summary += (
            f"; embedded metadata valid (version={metadata['version_string']!r} "
            f"build_commit={metadata['build_commit']!r} "
            f"config_fingerprint={metadata['config_fingerprint']!r} "
            f"config_preset={metadata['config_preset']!r} abi={metadata['abi']!r})"
        )
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
