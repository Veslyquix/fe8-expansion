#!/usr/bin/env python3
"""Localization-specific runtime memory-budget rollup (issue #18 sprint 4).

Combines three independently-real data sources into one report -- never
fabricating or hardcoding a byte count:

  1. The generic linker map/ELF budget (scripts/linker_report/budget.py),
     which parses the *actual* GNU ld .map for this build and reports each
     GBA memory region's real `free_bytes` (capacity minus every mapped
     section, including the floating `.data`/`.bss` tail up to
     `__floating_end` and any pinned symbol after it) -- this is the real,
     non-hardcoded "headroom to the next pinned region" the issue #18
     sprint 4 WHAT #5 asks for. No threshold in this file is ever a fixed
     magic number: `--check` only fails when the map itself reports
     `overflow: true` for a region (i.e. real linker-verified overrun).
  2. The localization source-catalog budget (scripts/localization/generate
     .build_budget / `localization-budget` Make target), which reports the
     *source* catalog string/index bytes, decoded-scratch budget, and used
     glyph/codepoint counts -- entirely derived from
     texts/expansion/registry.json + catalog.en.json, independent of any
     particular linked ROM.
  3. Real `nm -S` symbol sizes read directly from the build's own linked
     ELF for the concrete localization runtime module symbols (the
     EWRAM selector/settings UI state probe, and the locale resolver's
     EWRAM state/cache) -- this is what WHAT #5 calls "EWRAM scratch+UI
     state"; there is no separate synthetic struct here, only whatever
     `nm` reports for this exact build.

This script never invents numbers: every field is either copied verbatim
from (1)/(2), or is a real `nm`-derived integer for (3). If a named symbol
does not exist in this build (e.g. a debug-only probe compiled out of a
release build), its entry is simply omitted -- never zero-filled or
guessed.
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

# Concrete, real symbol names emitted by src/expansion_locale.c and
# src/expansion_language_menu.c -- see those files for the authoritative
# definitions. Kept as an explicit allowlist (rather than a wildcard scan)
# so a report always names exactly what it measured.
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
ROM_CATALOG_STRING_SYMBOLS = (
    "gExpansionCatalog_en",
    "gExpansionCatalog_qps_ploc",
)


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
        "rom_catalog_strings": _symbol_rollup(sizes, ROM_CATALOG_STRING_SYMBOLS),
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
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, help="Path to the modern .map file")
    parser.add_argument("--elf", required=True, help="Path to the modern .elf file")
    parser.add_argument(
        "--localization-budget", default=None,
        help="Optional path to a generated localization budget.json "
             "(build/expansion-localization/generated/budget.json)",
    )
    parser.add_argument("--output", required=True, help="Path to write JSON report")
    parser.add_argument(
        "--check", action="store_true",
        help="Fail (exit 1) if the underlying real linker map reports an "
             "overflow for any region. Never a hardcoded byte threshold.",
    )
    args = parser.parse_args(argv)

    with open(args.map, "r", encoding="utf-8", errors="replace") as handle:
        map_text = handle.read()
    regions, sections, assignments = generic_budget.parse_map(map_text)
    elf_sections = generic_budget.parse_elf_sections(args.elf)
    map_report = generic_budget.generate_report(regions, sections, assignments, elf_sections)

    localization_budget = None
    if args.localization_budget and Path(args.localization_budget).is_file():
        localization_budget = json.loads(Path(args.localization_budget).read_text(encoding="utf-8"))

    report = build_report(map_report, args.elf, localization_budget)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.check and report["map_overflow"]:
        print(
            "error: localization budget check failed -- the real linker map "
            f"reports a region overflow (see {args.output}: regions_headroom)",
            file=sys.stderr,
        )
        return 1

    print(f"localization budget report written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
