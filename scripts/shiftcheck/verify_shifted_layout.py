#!/usr/bin/env python3
"""Verify that a modern shifted link moves only the floating ROM region."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


NM_LINE_RE = re.compile(r"^([0-9A-Fa-f]+)\s+\S\s+(\S+)$")
PINNED_SYMBOL_ADDRESSES = {
    "banim_number": 0x08C00000,
    "banim_data": 0x08C00008,
    "banim_terrain_head": 0x08EE0000,
    "battle_terrain_table": 0x08EE0008,
    "_banim_pal_start": 0x08EF8000,
    "banim_pal_head": 0x08EF8000,
    "character_battle_animation_palette_table": 0x08EF8008,
}
BANIM_OVERLAY_SPANS = (
    ("gBanimLeftImgSheetBuf", "gEkrKakudaiSomeBufLeft", 0x1000),
    ("gEkrKakudaiSomeBufLeft", "gBanimRightImgSheetBuf", 0x1000),
    ("gBanimRightImgSheetBuf", "gEkrKakudaiSomeBufRight", 0x1000),
    ("gBanimOaml", "gBanimOamr2", 0x5800),
    ("gBanimOamr2", "gBanimScrLeft", 0x5800),
    ("gBanimScrLeft", "gBanimScrRight", 0x2A00),
)
SAVE_PALETTE_SPANS = (
    ("Pal_ChapterTitleAlt", "gPal_SaveSlotHardSelectedBlendA", 0x12),
    (
        "gPal_SaveSlotHardSelectedBlendA",
        "gPal_SaveSlotHardUnselectedBlendA",
        0x20,
    ),
    (
        "gPal_SaveSlotHardUnselectedBlendA",
        "gPal_SaveSlotHardSelectedBlendB",
        0xE0,
    ),
    (
        "gPal_SaveSlotHardSelectedBlendB",
        "gPal_SaveSlotHardUnselectedBlendB",
        0x20,
    ),
    ("gPal_SaveSlotHardUnselectedBlendB", "Pal_ChapterTitleMain", 0x4E),
)
UNITLIST_OVERLAY_SPANS = (
    ("gSortedUnitsBuf", "gSortedUnits", 0x300),
    ("gSortedUnits", "gUnitlistscreen_0", 0x100),
    ("gUnitlistscreen_0", "gUnitlistscreen_1", 0x800),
    ("gUnitlistscreen_1", "gUnitlistscreen_2", 0x80),
    ("gUnitlistscreen_2", "gUnitlistscreen_3", 0x38),
    ("gUnitlistscreen_3", "gUnitlistscreen_4", 0xA8),
    ("gUnitlistscreen_4", "gUnitlistscreen_5", 0x08),
    ("gUnitlistscreen_5", "gUnitlistscreen_6", 0x08),
    ("gUnitlistscreen_6", "gUnitlistscreen_7", 0x08),
    ("gUnitlistscreen_7", "gUnitlistscreen_8", 0x1000),
    ("gUnitlistscreen_8", "gUnitlistscreen_9", 0x04),
)
RELATIVE_SPANS = (
    BANIM_OVERLAY_SPANS
    + SAVE_PALETTE_SPANS
    + UNITLIST_OVERLAY_SPANS
)
REQUIRED_SYMBOLS = (
    "Init",
    "__shift_start",
    "__shift_end",
    "ReadSramFast_Core",
    "__floating_end",
    *PINNED_SYMBOL_ADDRESSES,
    *(symbol for span in RELATIVE_SPANS for symbol in span[:2]),
)


def parse_symbols(nm: str, elf: Path) -> dict[str, int]:
    try:
        result = subprocess.run(
            [nm, "-n", "--defined-only", str(elf)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"cannot run nm for {elf}: {exc}") from exc

    if result.returncode != 0:
        raise ValueError(f"nm failed for {elf}: {result.stderr.strip()}")

    symbols: dict[str, int] = {}
    for line in result.stdout.splitlines():
        match = NM_LINE_RE.match(line.strip())
        if match:
            symbols[match.group(2)] = int(match.group(1), 16)

    missing = [name for name in REQUIRED_SYMBOLS if name not in symbols]
    if missing:
        raise ValueError(f"{elf} is missing symbols: {', '.join(missing)}")

    return symbols


def verify_layout(base: dict[str, int], shifted: dict[str, int], shift: int) -> list[str]:
    errors = []

    if base["__shift_start"] != base["__shift_end"]:
        errors.append(
            "base ELF is already shifted: "
            f"__shift_start={base['__shift_start']:#010x}, "
            f"__shift_end={base['__shift_end']:#010x}"
        )

    for symbol in ("Init", "__shift_start", *PINNED_SYMBOL_ADDRESSES):
        if shifted[symbol] != base[symbol]:
            errors.append(
                f"pinned symbol {symbol} moved: "
                f"{base[symbol]:#010x} -> {shifted[symbol]:#010x}"
            )

    for label, symbols in (("base", base), ("shifted", shifted)):
        for symbol, expected in PINNED_SYMBOL_ADDRESSES.items():
            if symbols[symbol] != expected:
                errors.append(
                    f"{label} pinned symbol {symbol} is "
                    f"{symbols[symbol]:#010x}, expected {expected:#010x}"
                )

        for start, end, size in RELATIVE_SPANS:
            actual = symbols[end] - symbols[start]
            if actual != size:
                errors.append(
                    f"{label} relative span {start}->{end} is "
                    f"{actual:#x}, expected {size:#x}"
                )

    for symbol in ("__shift_end", "ReadSramFast_Core"):
        expected = base[symbol] + shift
        if shifted[symbol] != expected:
            errors.append(
                f"floating symbol {symbol} moved by "
                f"{shifted[symbol] - base[symbol]:#x}, expected {shift:#x}"
            )

    actual_padding = shifted["__shift_end"] - shifted["__shift_start"]
    if actual_padding != shift:
        errors.append(
            f"shift padding is {actual_padding:#x}, expected {shift:#x}"
        )

    if shifted["__floating_end"] < base["__floating_end"] + shift:
        errors.append(
            "__floating_end did not move beyond the requested shift; "
            "the floating region may overlap its base layout"
        )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-elf", required=True, type=Path)
    parser.add_argument("--shifted-elf", required=True, type=Path)
    parser.add_argument("--shift", required=True)
    parser.add_argument("--nm", default="arm-none-eabi-nm")
    args = parser.parse_args(argv)

    try:
        shift = int(args.shift, 0)
    except ValueError:
        print(f"error: invalid shift amount: {args.shift}", file=sys.stderr)
        return 2

    if shift <= 0 or shift % 4:
        print("error: shift must be a positive, 4-byte-aligned value", file=sys.stderr)
        return 2

    for path in (args.base_elf, args.shifted_elf):
        if not path.is_file():
            print(f"error: ELF not found: {path}", file=sys.stderr)
            return 2

    try:
        base = parse_symbols(args.nm, args.base_elf)
        shifted = parse_symbols(args.nm, args.shifted_elf)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors = verify_layout(base, shifted, shift)
    if errors:
        print("shifted layout verification failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        f"shifted layout verified: floating={shift:#x}, pinned symbols unchanged"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
