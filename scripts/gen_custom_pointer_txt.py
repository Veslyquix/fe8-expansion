#!/bin/python3
"""Generate fireemblem8.custom_pointer.txt (FEBuilderGBA's per-ROM pointer
override file) from this build's gFebuilderPointers[] array
(src/febuilder_pointers.c, #if FE8_FEBUILDER_POINTERS).

FEBuilderGBA's ROMFE8U.cs hardcodes, for most fields, the vanilla ROM address
of a POINTER CELL -- an inline literal-pool word inside some function, holding
the real table address -- which FEBuilder dereferences to reach the table. A
recompiled ROM has no equivalent literal pool at any stable address, so
src/febuilder_pointers.c supplies purpose-built pointer cells instead, and this
script reports each cell's own ROM offset.

Each field's kind comes from tools/febuilder_pointers/field_order.txt:

  slot    FEBuilder wants a pointer cell -> emit the ROM offset of this array
          entry itself, so FEBuilder's dereference lands on the real table.
  direct  FEBuilder wants the data address itself (no indirection in vanilla
          either) -> emit the stored address, converted to a ROM file offset.
  scalar  a size/count/id constant -> emit the stored value verbatim.

Usage: gen_custom_pointer_txt.py <elf> <gba> <field_order.txt> <out.txt>
"""
import struct
import subprocess
import sys

ROM_BASE = 0x08000000
ROM_END = 0x0A000000


def find_symbol_address(nm_path, elf_path, symbol):
    result = subprocess.run(
        [nm_path, elf_path], capture_output=True, text=True, check=True
    )
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == symbol:
            return int(parts[0], 16)
    sys.exit(f"error: symbol '{symbol}' not found in {elf_path}")


def main():
    if len(sys.argv) != 5:
        sys.exit(f"usage: {sys.argv[0]} <elf> <gba> <field_order.txt> <out.txt>")

    elf_path, gba_path, field_order_path, out_path = sys.argv[1:5]
    nm_path = "arm-none-eabi-nm"

    fields = []
    with open(field_order_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, kind = line.partition("\t")
            fields.append((name.strip(), kind.strip()))

    array_addr = find_symbol_address(nm_path, elf_path, "gFebuilderPointers")
    if not ROM_BASE <= array_addr < ROM_END:
        sys.exit(f"error: gFebuilderPointers address {array_addr:#x} is not in ROM space")
    array_offset = array_addr - ROM_BASE

    with open(gba_path, "rb") as f:
        f.seek(array_offset)
        raw = f.read(4 * len(fields))

    if len(raw) != 4 * len(fields):
        sys.exit(
            f"error: read {len(raw)} bytes for {len(fields)} entries, "
            f"expected {4 * len(fields)} -- field_order.txt and the C array "
            f"are out of sync"
        )

    values = struct.unpack(f"<{len(fields)}I", raw)

    lines = []
    for i, ((name, kind), value) in enumerate(zip(fields, values)):
        if kind == "slot":
            # The pointer cell's own ROM offset; FEBuilder dereferences it.
            emitted = array_offset + i * 4
        elif kind == "direct":
            # Taking a Thumb function's address sets bit 0; FEBuilder wants the
            # plain address (vanilla's own values for these fields are even).
            # Every data table here is at least 2-byte aligned, so clearing
            # bit 0 is a no-op for them. Scalars are deliberately excluded --
            # their odd values (item ids, struct offsets) are meaningful.
            value &= ~1
            if ROM_BASE <= value < ROM_END:
                emitted = value - ROM_BASE
            else:
                # EWRAM/IWRAM address -- reported absolute, as vanilla does.
                emitted = value
        elif kind == "scalar":
            emitted = value
        else:
            sys.exit(f"error: unknown kind {kind!r} for field {name!r}")

        lines.append(f"{name}\t{emitted:#x}")

    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {out_path} ({len(fields)} entries)")


if __name__ == "__main__":
    main()
