# Linker Reports

Deterministic memory-budget report from a GNU ld `.map` file.

## Usage

```bash
# Map-only (no ELF cross-validation):
python3 scripts/linker_report/budget.py \
    --map fireemblem8.map \
    --output reports/linker-budget.json

# With ELF cross-validation (graceful degradation if readelf unavailable):
python3 scripts/linker_report/budget.py \
    --map fireemblem8.map \
    --elf fireemblem8.elf \
    --output reports/linker-budget.json

# Product gate: require real ELF/map identity and safe RAM headroom:
python3 scripts/linker_report/budget.py \
    --map fireemblem8.map \
    --elf fireemblem8.elf \
    --output build/linker-budget.json \
    --validate-elf \
    --require-positive-headroom ewram

# Check mode (exits 1 on map-derived memory-budget drift):
python3 scripts/linker_report/budget.py \
    --map fireemblem8.map \
    --output reports/linker-budget.json \
    --check
```

## Output

A JSON report with:

- **regions** — per-region physical capacity, occupied bytes, usable free
  bytes, and utilization. IWRAM additionally reports physical free bytes,
  bytes reserved above `__sp_usr`, statically usable capacity, usable static
  headroom below `__sp_usr`, the minimum user-stack margin, and remaining
  static-growth headroom beyond that margin.
- **sections** — every output section with address, size, overlay flag, region.
- **overlays** — EWRAM overlays grouped by base address with per-group peak.
- **pinned_assignments** — linker symbol assignments at GBA memory addresses.
- **elf** — optional ELF section cross-validation (when `--elf` is supplied).

The report is deterministic: no timestamps, no absolute host paths, stable
ordering (by address then name).

Check mode compares the map-derived regions, mapped sections, overlays, pinned
assignments, and overflow state. Derived shift/end markers such as
`__floating_end` are reported but not baselined because linker veneer insertion
may move them without changing any memory boundary. Optional ELF diagnostics
also remain inspectable without becoming host-sensitive baseline fields.
ELF comparison matches every non-empty mapped output section to an allocatable
ELF section by output-section name, VMA, and size. Indented map-only input
subsections such as `.locale_data.font.*` are not treated as ELF output
sections. This models GNU ld's zero-sized, non-allocatable output placeholders
(for example an empty 16 MiB `.locale_data`) without exempting a populated
locale bank: a missing section or a same-name address/size mismatch fails
actionably. Unlike diagnostic-only `--elf`, `--validate-elf` also fails closed
when readelf is unavailable.

For IWRAM, `capacity_bytes` remains the physical 32 KiB region size while
`free_bytes` is the statically usable headroom ending at `__sp_usr`;
`physical_free_bytes` retains the hardware-region view. The linker exports
`__iwram_static_end`, `__iwram_static_limit`, and `__sp_usr`. `crt0` initializes
the downward-growing system/user stack at `__sp_usr`; the historical fixed
layout left `0x1658` bytes below it and the current CJK scratch leaves `0x1158`.
The linker therefore preserves a `0x1000` minimum user-stack margin, leaving
`0x158` bytes of current static-growth headroom. Both the linker assertion and
`--require-positive-headroom iwram` enforce that floor.

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | Success, no region overflow |
| 1    | Overflow, validation/headroom failure, or `--check` drift |
| 2    | Malformed input or missing file |

## Tests

```bash
python3 -m unittest discover -s scripts/linker_report/tests -v
```

## Overlay audit

`overlay_audit.py` checks every overlay against EWRAM capacity and maps retained
`.relROM` relocations back to their owning object. If an object that owns data
in one overlay references a symbol owned by another overlay, the audit fails
with both object and symbol names.

```bash
python3 scripts/linker_report/overlay_audit.py \
    --map build/expansion-modern/debug/aapcs/fireemblem8.map \
    --elf build/expansion-modern/debug/aapcs/shiftcheck/fireemblem8.relocs.elf \
    --output build/expansion-modern/debug/aapcs/shiftcheck/overlay-audit.json \
    --require-relocations
```

`--require-relocations` is the CI mode: missing tools, a missing retained-reloc
ELF, timeout, or an ELF without relocations is an error rather than a skip.
