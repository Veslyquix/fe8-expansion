#!/usr/bin/env python3
"""Localization-specific runtime memory-budget rollup (issue #18 sprint 4).

Combines four independently-real data sources into one report -- never
fabricating or hardcoding a byte count:

  1. The generic linker map/ELF budget (scripts/linker_report/budget.py),
     which parses the *actual* GNU ld .map for this build and reports each
     GBA memory region's real `free_bytes` (capacity minus every mapped
     section, including the floating `.data`/`.bss` tail up to
     `__floating_end` and any pinned symbol after it) -- this is the real,
     non-hardcoded "headroom to the next pinned region" the issue #18
     sprint 4 WHAT #5 asks for. No threshold in this file is ever a fixed
     magic number.
  2. The localization source-catalog budget (scripts/localization/generate
     .build_budget / `localization-budget` Make target), which reports the
     *source* catalog string/index bytes, decoded-scratch budget, and used
     glyph/codepoint counts -- entirely derived from the registry and all
     generated locale catalogs, independent of any particular linked ROM.
  3. Real `nm -S` symbol sizes read directly from the build's own linked
     ELF for the concrete localization runtime module symbols (the
     EWRAM selector/settings UI state probe, the locale resolver's EWRAM
     state/cache, every generated locale pointer array, and the shared
     catalog descriptor/populated-count metadata) -- there is no separate
     synthetic struct here, only whatever `nm` reports for this exact build.
  4. The optional linker-defined `.locale_data` upper-ROM bank. When a
     current map contains its section and/or `__locale_bank_start` /
     `__locale_bank_end` symbols, the report derives real occupancy and
     headroom bounded by the actual mapped ROM region end (and never beyond
     the architectural 0x0A000000 limit). Thus an empty 16 MiB build reports
     zero upper-bank capacity/headroom, while a 32 MiB build reports the real
     upper-bank capacity. Older maps without that linker foundation simply
     omit the field.

This script never invents numbers: every field is either copied verbatim
from (1)/(2), or is a real `nm`-derived integer for (3). Optional symbols
(e.g. a debug-only probe compiled out of a release build) are omitted rather
than zero-filled. Required generated catalog symbols are reported as missing,
and `--check` fails instead of producing a success-shaped partial rollup.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget as generic_budget  # noqa: E402

NM = os.environ.get("NM", "arm-none-eabi-nm")

# Concrete, real symbol names emitted by src/expansion_locale.c,
# src/expansion_language_menu.c, and the generated catalog C. Fixed runtime
# metadata uses explicit names; locale arrays use the source budget's
# generated-locale list as a strict allowlist.
EWRAM_UI_STATE_SYMBOLS = (
    "gExpansionLanguageMenuProbe",
)
EWRAM_RESOLVER_STATE_SYMBOLS = (
    "sCurrentLocale",
    "sCurrentLocaleValid",
    "sCacheLocale",
    "sCacheMsgId",
    "sCacheValid",
    "sScratch",
)
ROM_CATALOG_INDEX_SYMBOLS = (
    "gExpansionLocaleMsgIds",
    "gExpansionLocaleMsgCount",
    "gExpansionLocaleTombstoneCount",
)
ROM_CATALOG_DESCRIPTOR_SYMBOLS = (
    "gExpansionLocaleCatalogs",
    "gExpansionLocalePopulatedCount",
)
ROM_CATALOG_STRING_PREFIX = "gExpansionCatalog_"
ROM_CATALOG_STRING_RE = re.compile(
    rf"^{re.escape(ROM_CATALOG_STRING_PREFIX)}[A-Za-z][A-Za-z0-9_]*$"
)
LOCALE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")
LOCALE_BANK_SECTION = ".locale_data"
LOCALE_BANK_START_SYMBOL = "__locale_bank_start"
LOCALE_BANK_END_SYMBOL = "__locale_bank_end"
LOCALE_BANK_LIMIT = 0x0A000000


def _nm_sizes(elf: str) -> dict[str, int]:
    """Real `nm -S --size-sort` symbol -> size (bytes) map for `elf`.

    Symbols with no recorded size (e.g. undefined/external) are omitted.
    """
    result = subprocess.run(
        [NM, "-S", elf], capture_output=True, text=True, check=True,
    )
    sizes: dict[str, int] = {}
    pattern = re.compile(
        r"^([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+\S\s+(\S+)$"
    )
    for line in result.stdout.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        _address, size_hex, name = match.groups()
        sizes[name] = int(size_hex, 16)
    return sizes


def _symbol_rollup(sizes: dict[str, int], names: tuple[str, ...]) -> dict[str, Any]:
    present = {name: sizes[name] for name in names if name in sizes}
    missing = [name for name in names if name not in sizes]
    return {
        "symbols": present,
        "total_bytes": sum(present.values()),
        "missing": missing,
    }


def _catalog_string_symbol_names(
    sizes: dict[str, int],
    localization_budget: dict[str, Any] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the strict catalog-array allowlist and unexpected prefix matches."""
    prefixed = sorted(
        name for name in sizes if name.startswith(ROM_CATALOG_STRING_PREFIX)
    )
    valid_prefixed = tuple(
        name for name in prefixed if ROM_CATALOG_STRING_RE.fullmatch(name)
    )
    invalid_prefixed = tuple(
        name for name in prefixed if not ROM_CATALOG_STRING_RE.fullmatch(name)
    )

    if localization_budget is None:
        return valid_prefixed, invalid_prefixed

    locales = localization_budget.get("locales_generated")
    if not isinstance(locales, list):
        raise ValueError(
            "localization budget must contain a locales_generated list"
        )

    expected: list[str] = []
    seen = set()
    for locale in locales:
        if not isinstance(locale, str) or not LOCALE_ID_RE.fullmatch(locale):
            raise ValueError(
                f"invalid locale id in localization budget: {locale!r}"
            )
        symbol = ROM_CATALOG_STRING_PREFIX + locale.replace("-", "_")
        if symbol not in seen:
            expected.append(symbol)
            seen.add(symbol)

    unexpected = tuple(
        sorted(set(valid_prefixed).difference(expected))
    ) + invalid_prefixed
    return tuple(expected), unexpected


def _catalog_string_rollup(
    sizes: dict[str, int],
    localization_budget: dict[str, Any] | None,
) -> dict[str, Any]:
    names, unexpected = _catalog_string_symbol_names(sizes, localization_budget)
    rollup = _symbol_rollup(sizes, names)
    rollup["unexpected"] = list(unexpected)
    return rollup


def _catalog_symbol_errors(report: dict[str, Any]) -> list[str]:
    errors = []
    for group_name in (
        "rom_catalog_index",
        "rom_catalog_descriptors",
        "rom_catalog_strings",
    ):
        group = report[group_name]
        if group["missing"]:
            errors.append(
                f"{group_name} missing required symbols: "
                + ", ".join(group["missing"])
            )
        if group.get("unexpected"):
            errors.append(
                f"{group_name} contains symbols outside the generated-locale "
                f"allowlist: {', '.join(group['unexpected'])}"
            )
    return errors


def _locale_bank_rollup(map_report: dict[str, Any]) -> dict[str, Any] | None:
    assignments = {
        entry["name"]: entry["address"]
        for entry in map_report.get("pinned_assignments", ())
        if entry.get("name") in (LOCALE_BANK_START_SYMBOL, LOCALE_BANK_END_SYMBOL)
    }
    section = next(
        (
            entry
            for entry in map_report.get("sections", ())
            if entry.get("name") == LOCALE_BANK_SECTION
        ),
        None,
    )

    start = assignments.get(LOCALE_BANK_START_SYMBOL)
    end = assignments.get(LOCALE_BANK_END_SYMBOL)
    if section is not None:
        start = start if start is not None else section["address"]
        end = end if end is not None else section["address"] + section["size_bytes"]
    if start is None or end is None:
        return None

    rom_region = next(
        (
            entry
            for entry in map_report.get("regions", ())
            if entry.get("name") == "rom"
        ),
        None,
    )
    if (
        rom_region is None
        or "origin" not in rom_region
        or "capacity_bytes" not in rom_region
    ):
        return None

    rom_region_end = rom_region["origin"] + rom_region["capacity_bytes"]
    limit = min(LOCALE_BANK_LIMIT, rom_region_end)
    occupied = max(0, end - start)
    capacity = max(0, limit - start)
    return {
        "start_address": start,
        "end_address": end,
        "limit_address": limit,
        "capacity_bytes": capacity,
        "occupied_bytes": occupied,
        "headroom_bytes": max(0, capacity - occupied),
        "overflow": end > limit or end < start,
        "section_present": section is not None,
    }


def build_report(
    map_report: dict[str, Any],
    elf: str,
    localization_budget: dict[str, Any] | None,
) -> dict[str, Any]:
    sizes = _nm_sizes(elf)
    region_by_name = {r["name"]: r for r in map_report["regions"]}

    report: dict[str, Any] = {
        "schema_version": 1,
        "regions_headroom": {
            name: {
                "free_bytes": region_by_name[name]["free_bytes"],
                "capacity_bytes": region_by_name[name]["capacity_bytes"],
                "occupied_bytes": region_by_name[name]["occupied_bytes"],
                "overflow": region_by_name[name]["overflow"],
            }
            for name in ("ewram", "iwram", "rom")
            if name in region_by_name
        },
        "ewram_ui_state": _symbol_rollup(sizes, EWRAM_UI_STATE_SYMBOLS),
        "ewram_resolver_state": _symbol_rollup(sizes, EWRAM_RESOLVER_STATE_SYMBOLS),
        "rom_catalog_index": _symbol_rollup(sizes, ROM_CATALOG_INDEX_SYMBOLS),
        "rom_catalog_descriptors": _symbol_rollup(
            sizes, ROM_CATALOG_DESCRIPTOR_SYMBOLS
        ),
        "rom_catalog_strings": _catalog_string_rollup(
            sizes, localization_budget
        ),
        "map_overflow": map_report["overflow"],
    }
    if localization_budget is not None:
        report["source_catalog_budget"] = {
            "active_message_count": localization_budget["active_message_count"],
            "tombstone_count": localization_budget["tombstone_count"],
            "locales_generated": localization_budget["locales_generated"],
            "catalog_string_bytes": localization_budget["catalog_string_bytes"],
            "catalog_index_bytes": localization_budget["catalog_index_bytes"],
            "scratch_budget_bytes": localization_budget["scratch_budget_bytes"],
            "scratch_slot_bytes_used_max": localization_budget["scratch_slot_bytes_used_max"],
            "scratch_headroom_bytes": localization_budget["scratch_headroom_bytes"],
            "glyphs_used_count": localization_budget["codepoints"]["glyphs_used_count"],
        }
    locale_bank = _locale_bank_rollup(map_report)
    if locale_bank is not None:
        report["locale_bank"] = locale_bank
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, help="Path to the modern .map file")
    parser.add_argument("--elf", required=True, help="Path to the modern .elf file")
    parser.add_argument(
        "--localization-budget", default=None,
        help="Optional path to a generated localization budget.json "
             "(e.g. build/expansion-modern/expansion-localization/generated/budget.json)",
    )
    parser.add_argument("--output", required=True, help="Path to write JSON report")
    parser.add_argument(
        "--check", action="store_true",
        help="Fail (exit 1) if the real linker map reports an overflow or "
             "required generated catalog symbols are missing/unexpected. "
             "Never a hardcoded byte threshold.",
    )
    args = parser.parse_args(argv)

    localization_budget = None
    if args.localization_budget:
        localization_budget_path = Path(args.localization_budget)
        if not localization_budget_path.is_file():
            parser.error(
                "--localization-budget does not exist: "
                f"{localization_budget_path}"
            )
        localization_budget = json.loads(
            localization_budget_path.read_text(encoding="utf-8")
        )

    with open(args.map, "r", encoding="utf-8", errors="replace") as handle:
        map_text = handle.read()
    regions, sections, assignments = generic_budget.parse_map(map_text)
    elf_sections = generic_budget.parse_elf_sections(args.elf)
    map_report = generic_budget.generate_report(regions, sections, assignments, elf_sections)

    report = build_report(map_report, args.elf, localization_budget)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.check:
        errors = _catalog_symbol_errors(report)
        if report["map_overflow"]:
            errors.insert(
                0,
                "the real linker map reports a region overflow "
                f"(see {args.output}: regions_headroom)",
            )
        if errors:
            print("error: localization budget check failed:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1

    print(f"localization budget report written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
