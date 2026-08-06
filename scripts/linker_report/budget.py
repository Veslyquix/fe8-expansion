#!/usr/bin/env python3
"""Deterministic memory-budget report from a GNU ld map file.

Parses the Memory Configuration and Linker script and memory map sections of a
GNU ld .map file to produce a stable JSON report of per-region usage, overlay
dimensions, pinned symbol assignments, and optional ELF cross-validation.

Output is deterministic: no timestamps, no absolute host paths, stable ordering.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
READELF = os.environ.get("READELF", "arm-none-eabi-readelf")

# GBA memory regions by address prefix.
REGION_RANGES = {
    "rom": (0x08000000, 0x0A000000),
    "iwram": (0x03000000, 0x03008000),
    "ewram": (0x02000000, 0x02040000),
}

CHECK_KEYS = (
    "schema_version",
    "regions",
    "sections",
    "overlays",
    "pinned_assignments",
    "overflow",
)

DYNAMIC_ASSIGNMENT_NAMES = {
    "__ewram_persistent_start",
    "__ewram_used_end",
    "__floating_end",
    "__shift_end",
    "__shift_start",
    "_banim_pal_end",
    "_banim_pal_size",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MemoryRegion:
    name: str
    origin: int
    length: int


@dataclass
class OutputSection:
    name: str
    address: int
    size: int


@dataclass
class SymbolAssignment:
    name: str
    address: int
    expression: str


@dataclass
class ElfSection:
    name: str
    type_name: str
    address: int
    size: int
    flags: str


# ---------------------------------------------------------------------------
# Map parser
# ---------------------------------------------------------------------------

_MEMORY_ROW_RE = re.compile(
    r"^(\S+)\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)"
)

# Output section on ONE line: "NAME  0xADDR  0xSIZE"
_SECTION_ONELINE_RE = re.compile(
    r"^([A-Za-z_.][A-Za-z0-9_.]*)\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)(?:\s|$)"
)

# Output section on TWO lines: name alone, then indented "0xADDR  0xSIZE"
_SECTION_NAME_RE = re.compile(
    r"^([A-Za-z_.][A-Za-z0-9_.]*)\s*$"
)
_SECTION_ADDR_SIZE_RE = re.compile(
    r"^\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)(?:\s|$)"
)

# Symbol assignment: "  0xADDR  name = expression"
_ASSIGN_RE = re.compile(
    r"^\s+(0x[0-9a-fA-F]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$"
)


def _classify_region(address: int) -> str | None:
    """Map an address to its GBA memory region name."""
    for name, (lo, hi) in REGION_RANGES.items():
        if lo <= address < hi or address == hi:
            return name
    return None


def _classify_region_with_boundary(address: int) -> tuple[str | None, bool]:
    """Map an address to its GBA memory region name and boundary status."""
    for name, (lo, hi) in REGION_RANGES.items():
        if lo <= address < hi:
            return name, False
        if address == hi:
            return name, True
    return None, False


def _default_empty_section_address(name: str, regions: list[MemoryRegion]) -> int | None:
    """Infer an address for empty sections when the map omits addr/size."""
    if "overlay" not in name:
        return None

    for region in regions:
        if region.name == "ewram":
            return region.origin

    return REGION_RANGES["ewram"][0]


def parse_map(text: str) -> tuple[
    list[MemoryRegion], list[OutputSection], list[SymbolAssignment]
]:
    """Parse a GNU ld map file text into structured data."""
    regions: list[MemoryRegion] = []
    sections: list[OutputSection] = []
    assignments: list[SymbolAssignment] = []

    lines = text.splitlines()
    n = len(lines)
    i = 0

    # Phase 1: Find and parse Memory Configuration
    while i < n:
        if lines[i].strip() == "Memory Configuration":
            i += 1
            break
        i += 1
    else:
        raise ValueError("Map file missing 'Memory Configuration' block")

    # Skip the header row ("Name  Origin  Length  Attributes")
    while i < n and not _MEMORY_ROW_RE.match(lines[i]):
        i += 1

    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            break
        m = _MEMORY_ROW_RE.match(line)
        if m:
            name = m.group(1)
            if name != "*default*":
                regions.append(MemoryRegion(
                    name=name,
                    origin=int(m.group(2), 16),
                    length=int(m.group(3), 16),
                ))
        i += 1

    # Phase 2: Find "Linker script and memory map"
    while i < n:
        if "Linker script and memory map" in lines[i]:
            i += 1
            break
        i += 1

    # Phase 3: Parse output sections and assignments
    while i < n:
        line = lines[i]

        # Check for symbol assignment
        am = _ASSIGN_RE.match(line)
        if am:
            addr = int(am.group(1), 16)
            # Only record GBA-relevant assignments (not small linker constants)
            if _classify_region(addr) is not None:
                assignments.append(SymbolAssignment(
                    name=am.group(2),
                    address=addr,
                    expression=am.group(3),
                ))
            i += 1
            continue

        # Check for one-line output section
        sm = _SECTION_ONELINE_RE.match(line)
        if sm:
            sections.append(OutputSection(
                name=sm.group(1),
                address=int(sm.group(2), 16),
                size=int(sm.group(3), 16),
            ))
            i += 1
            continue

        # Check for two-line output section (name, then addr+size on next)
        nm = _SECTION_NAME_RE.match(line)
        if nm and i + 1 < n:
            next_line = lines[i + 1]
            next_m = _SECTION_ADDR_SIZE_RE.match(next_line)
            if next_m:
                sections.append(OutputSection(
                    name=nm.group(1),
                    address=int(next_m.group(1), 16),
                    size=int(next_m.group(2), 16),
                ))
                i += 2
                continue

            name = nm.group(1)
            if not next_line.strip() or next_line.lstrip().startswith("*("):
                address = _default_empty_section_address(name, regions)
                if address is not None:
                    sections.append(OutputSection(name=name, address=address, size=0))
                    i += 1
                    continue

        i += 1

    return regions, sections, assignments


# ---------------------------------------------------------------------------
# ELF cross-validation (optional, graceful degradation)
# ---------------------------------------------------------------------------

_READELF_SECTION_RE = re.compile(
    r"^\s*\[\s*\d+\]\s+"
    r"(\S+)\s+"           # name
    r"(\S+)\s+"           # type
    r"([0-9a-fA-F]+)\s+"  # address
    r"[0-9a-fA-F]+\s+"    # offset
    r"([0-9a-fA-F]+)\s+"  # size
    r"[0-9a-fA-F]+\s+"    # entsize
    r"(\S*)\s+"           # flags
)


def parse_elf_sections(elf_path: str) -> list[ElfSection] | None:
    """Try to get allocatable ELF sections via readelf. Returns None on failure."""
    try:
        result = subprocess.run(
            [READELF, "-W", "-S", elf_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        return None

    sections: list[ElfSection] = []
    for line in result.stdout.splitlines():
        m = _READELF_SECTION_RE.match(line)
        if m:
            flags = m.group(5)
            # Only allocatable sections
            if "A" in flags:
                sections.append(ElfSection(
                    name=m.group(1),
                    type_name=m.group(2),
                    address=int(m.group(3), 16),
                    size=int(m.group(4), 16),
                    flags=flags,
                ))
    return sections if sections else None


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _region_for_section(section: OutputSection, regions: list[MemoryRegion]) -> str | None:
    """Find which declared memory region contains this section's address."""
    for r in regions:
        if r.origin <= section.address < r.origin + r.length:
            return r.name
    return _classify_region(section.address)


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge half-open intervals."""
    merged: list[tuple[int, int]] = []

    for start, end in sorted(interval for interval in intervals if interval[1] > interval[0]):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue

        merged[-1] = (merged[-1][0], max(merged[-1][1], end))

    return merged


def generate_report(
    regions: list[MemoryRegion],
    sections: list[OutputSection],
    assignments: list[SymbolAssignment],
    elf_sections: list[ElfSection] | None,
) -> dict[str, Any]:
    """Build the deterministic JSON-serializable report."""

    overlay_names: set[str] = set()
    for s in sections:
        if "overlay" in s.name:
            overlay_names.add(s.name)

    overlays_by_base: dict[int, list[OutputSection]] = {}
    for s in sections:
        if s.name in overlay_names:
            overlays_by_base.setdefault(s.address, []).append(s)

    region_intervals: dict[str, list[tuple[int, int]]] = {}
    for s in sections:
        if s.name in overlay_names:
            continue

        rname = _region_for_section(s, regions)
        if rname:
            region_intervals.setdefault(rname, []).append((s.address, s.address + s.size))

    for base_addr, group in overlays_by_base.items():
        region_name = _classify_region(base_addr)
        if region_name is None or not group:
            continue

        peak = max(section.size for section in group)
        region_intervals.setdefault(region_name, []).append((base_addr, base_addr + peak))

    # Build region report
    region_report = []
    overflow = False
    for r in sorted(regions, key=lambda x: x.origin):
        merged = _merge_intervals(region_intervals.get(r.name, []))
        occupied = sum(end - start for start, end in merged)
        util = round(occupied * 100.0 / r.length, 2) if r.length > 0 else 0.0
        region_limit = r.origin + r.length
        region_overflow = any(start < r.origin or end > region_limit for start, end in merged)
        if region_overflow:
            overflow = True
        region_report.append({
            "name": r.name,
            "origin": r.origin,
            "capacity_bytes": r.length,
            "occupied_bytes": occupied,
            "free_bytes": max(0, r.length - occupied),
            "utilization_percent": util,
            "overflow": region_overflow,
        })

    # Overlays: group by base address
    overlay_report = []
    for base_addr in sorted(overlays_by_base.keys()):
        group = sorted(overlays_by_base[base_addr], key=lambda x: x.name)
        peak = max(s.size for s in group) if group else 0
        region_name = _classify_region(base_addr)
        for s in group:
            overlay_report.append({
                "name": s.name,
                "address": s.address,
                "size_bytes": s.size,
                "peak_bytes": peak,
                "region": region_name,
            })

    # Only mapped memory sections belong in a memory-budget baseline.
    # Debug/comment/attribute sections sit at address zero and their sizes can
    # vary with absolute checkout/toolchain paths without changing the ROM.
    budget_sections = [
        section
        for section in sections
        if section.name in overlay_names
        or _region_for_section(section, regions) is not None
    ]

    # Sections list (sorted by address, then name for stability)
    section_report = []
    for s in sorted(budget_sections, key=lambda x: (x.address, x.name)):
        section_report.append({
            "name": s.name,
            "address": s.address,
            "size_bytes": s.size,
            "is_overlay": s.name in overlay_names,
            "region": _region_for_section(s, regions),
        })

    # Pinned assignments (sorted by address, then name)
    pinned_report = []
    for a in sorted(assignments, key=lambda x: (x.address, x.name)):
        region_name, is_boundary = _classify_region_with_boundary(a.address)
        entry = {
            "name": a.name,
            "address": a.address,
            "expression": a.expression,
            "region": region_name,
        }
        if is_boundary:
            entry["boundary"] = True
        pinned_report.append(entry)

    # ELF cross-validation
    elf_report: dict[str, Any]
    if elf_sections is not None:
        elf_names = {es.name for es in elf_sections if es.size > 0}
        # readelf's allocatable-section view deliberately omits zero-sized
        # output placeholders such as an empty 16 MiB .locale_data bank.
        # Compare only map sections that occupy bytes; a populated locale
        # bank remains non-zero/allocatable and is still cross-validated.
        map_names = {s.name for s in budget_sections if s.size > 0}
        elf_report = {
            "available": True,
            "section_count": len(elf_sections),
            "sections": [
                {
                    "name": es.name,
                    "type": es.type_name,
                    "address": es.address,
                    "size_bytes": es.size,
                    "flags": es.flags,
                }
                for es in sorted(elf_sections, key=lambda x: (x.address, x.name))
            ],
            "cross_validation": {
                "in_elf_not_map": sorted(elf_names - map_names),
                "in_map_not_elf": sorted(map_names - elf_names),
            },
        }
    else:
        elf_report = {"available": False}

    return {
        "schema_version": SCHEMA_VERSION,
        "regions": region_report,
        "sections": section_report,
        "overlays": overlay_report,
        "pinned_assignments": pinned_report,
        "elf": elf_report,
        "overflow": overflow,
    }


def check_projection(report: dict[str, Any]) -> dict[str, Any]:
    """Return the deterministic, map-derived fields used for drift checks."""
    projection = {key: report[key] for key in CHECK_KEYS}
    projection["pinned_assignments"] = [
        assignment
        for assignment in report["pinned_assignments"]
        if assignment["name"] not in DYNAMIC_ASSIGNMENT_NAMES
        and not (
            assignment["name"].startswith("__ewram_overlay_")
            and assignment["name"].endswith("_end")
        )
    ]
    return projection


def render_check_diff(
    expected: dict[str, Any], actual: dict[str, Any]
) -> str:
    """Render an actionable diff for deterministic budget fields."""
    expected_lines = json.dumps(
        check_projection(expected), indent=2, sort_keys=True
    ).splitlines()
    actual_lines = json.dumps(
        check_projection(actual), indent=2, sort_keys=True
    ).splitlines()
    return "\n".join(difflib.unified_diff(
        expected_lines,
        actual_lines,
        fromfile="committed",
        tofile="generated",
        lineterm="",
    ))


def elf_cross_validation_errors(
    report: dict[str, Any], require_available: bool = False,
) -> list[str]:
    """Return section-name mismatches from the current ELF diagnostics."""
    elf_report = report.get("elf", {})
    if not elf_report.get("available"):
        return ["ELF cross-validation unavailable"] if require_available else []

    cross_validation = elf_report.get("cross_validation", {})
    errors = []
    for key in ("in_elf_not_map", "in_map_not_elf"):
        values = cross_validation.get(key, [])
        if values:
            errors.append(f"{key}: {', '.join(values)}")
    return errors


def positive_headroom_errors(
    report: dict[str, Any], region_names: list[str],
) -> list[str]:
    """Return errors for requested regions without at least one free byte."""
    regions = {region["name"]: region for region in report.get("regions", ())}
    errors = []
    for name in dict.fromkeys(region_names):
        region = regions.get(name)
        if region is None:
            errors.append(f"required region is missing: {name}")
            continue
        if region.get("overflow") or region.get("free_bytes", 0) <= 0:
            errors.append(
                f"{name} requires positive headroom: "
                f"free_bytes={region.get('free_bytes', 0)} "
                f"overflow={region.get('overflow')}"
            )
    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic memory-budget report from a GNU ld map file."
    )
    parser.add_argument("--map", required=True, help="Path to the .map file")
    parser.add_argument("--elf", default=None, help="Path to the ELF for cross-validation")
    parser.add_argument("--output", required=True, help="Path to write JSON report")
    parser.add_argument(
        "--check", action="store_true",
        help="Compare generated report against existing --output; exit 1 on drift"
    )
    parser.add_argument(
        "--validate-elf", action="store_true",
        help="Fail if non-empty mapped output sections and allocatable ELF "
             "sections diverge. Requires --elf.",
    )
    parser.add_argument(
        "--require-positive-headroom",
        action="append",
        default=[],
        choices=tuple(REGION_RANGES),
        metavar="REGION",
        help="Fail unless REGION has at least one free byte. Repeatable.",
    )
    args = parser.parse_args(argv)

    if args.validate_elf and not args.elf:
        parser.error("--validate-elf requires --elf")

    map_path = Path(args.map)
    if not map_path.is_file():
        print(f"error: map file not found: {args.map}", file=sys.stderr)
        return 2

    try:
        map_text = map_path.read_text(errors="replace")
    except OSError as e:
        print(f"error: cannot read map file: {e}", file=sys.stderr)
        return 2

    try:
        regions, sections, assignments = parse_map(map_text)
    except ValueError as e:
        print(f"error: malformed map file: {e}", file=sys.stderr)
        return 2

    if not regions:
        print("error: no memory regions found in map file", file=sys.stderr)
        return 2

    elf_sections = None
    if args.elf:
        elf_sections = parse_elf_sections(args.elf)
        if elf_sections is None:
            print("warning: ELF cross-validation unavailable", file=sys.stderr)

    report = generate_report(regions, sections, assignments, elf_sections)
    report_json = json.dumps(report, indent=2) + "\n"

    output_path = Path(args.output)
    elf_errors = (
        elf_cross_validation_errors(
            report, require_available=args.validate_elf,
        )
        if args.check or args.validate_elf
        else []
    )
    headroom_errors = positive_headroom_errors(
        report, args.require_positive_headroom,
    )

    if args.check:
        if not output_path.is_file():
            print(f"error: expected report not found: {args.output}", file=sys.stderr)
            return 1
        try:
            existing_report = json.loads(output_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read expected report: {exc}", file=sys.stderr)
            return 2

        if elf_errors:
            print("check failed: ELF/map section mismatch", file=sys.stderr)
            for error in elf_errors:
                print(f"  - {error}", file=sys.stderr)
            return 1

        if headroom_errors:
            print("check failed: memory headroom requirement", file=sys.stderr)
            for error in headroom_errors:
                print(f"  - {error}", file=sys.stderr)
            return 1

        if check_projection(existing_report) == check_projection(report):
            print(f"check passed: {args.output}", file=sys.stderr)
            return 0

        print(f"check failed: report drift detected in {args.output}", file=sys.stderr)
        print(render_check_diff(existing_report, report), file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_json)
    n_sections = len(report["sections"])
    n_overlays = len(report["overlays"])
    print(
        f"wrote {n_sections} sections, {n_overlays} overlays to {args.output}",
        file=sys.stderr,
    )

    if elf_errors:
        print("validation failed: ELF/map section mismatch", file=sys.stderr)
        for error in elf_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if headroom_errors:
        print("validation failed: memory headroom requirement", file=sys.stderr)
        for error in headroom_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    return 1 if report["overflow"] else 0


if __name__ == "__main__":
    sys.exit(main())
