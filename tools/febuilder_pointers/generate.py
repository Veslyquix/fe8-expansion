#!/bin/python3
"""Generate src/febuilder_pointers.c + tools/febuilder_pointers/field_order.txt
from the deref analysis, auto-resolving which symbols need a local extern."""
import os
import json
import re
import subprocess
import sys

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) or "."

entries = json.load(open(f"{HERE}/mapping.json"))

# Headers needed for the sizeof()/offsetof() scalar entries only.
SCALAR_HEADERS = [
    "bmunit.h", "bmitem.h", "face.h", "chapterdata.h", "soundroom.h",
    "proc.h", "bmsave.h", "constants/items.h", "constants/terrains.h",
]


def build_source(extra_externs):
    L = []
    L.append('#include "global.h"')
    L.append("")
    L.append("#if FE8_FEBUILDER_POINTERS")
    L.append("")
    L.append('#include "febuilder_pointers.h"')
    for h in SCALAR_HEADERS:
        L.append(f'#include "{h}"')
    L.append("")
    if extra_externs:
        L.append("/* Symbols with real external linkage that no header reachable from")
        L.append(" * global.h declares. Only their ADDRESS is taken below, so an opaque")
        L.append(" * byte-array type is sufficient and avoids duplicating (or conflicting")
        L.append(" * with) whatever richer type their defining translation unit uses. */")
        for s in sorted(extra_externs):
            L.append(f"extern const u8 {s}[];")
        L.append("")
    L.append("/* FEBuilderGBA's ROMFE8U.cs hardcodes, for each field, the vanilla ROM")
    L.append(" * address of a POINTER CELL -- an inline literal-pool word holding the")
    L.append(" * real table address -- which FEBuilder dereferences to find the table.")
    L.append(" * A recompiled ROM has no such literal pool at a stable address, so this")
    L.append(" * array supplies the equivalent: each 'slot' entry below IS a pointer")
    L.append(" * cell, and scripts/gen_custom_pointer_txt.py writes that cell's own ROM")
    L.append(" * offset into fireemblem8.custom_pointer.txt for FEBuilder to dereference.")
    L.append(" *")
    L.append(" * Entry kinds (see tools/febuilder_pointers/field_order.txt, which pairs")
    L.append(" * each field name with its kind, in this exact order):")
    L.append(" *   slot   -- FEBuilder wants a pointer cell; it gets this entry's address")
    L.append(" *   direct -- FEBuilder wants the data address itself; it gets this value")
    L.append(" *   scalar -- a size/count/id constant; it gets this value verbatim")
    L.append(" *")
    L.append(" * Mapping was derived by dereferencing each vanilla pointer cell in")
    L.append(" * baserom.gba, resolving the target through reference/fe8u_symbols.txt to")
    L.append(" * a vanilla symbol name, and confirming that same symbol exists here.")
    L.append(" * Scalars use sizeof()/offsetof()/real constants rather than copied")
    L.append(" * vanilla literals, so they track this repo's actual layout. */")
    L.append("CONST_DATA u32 gFebuilderPointers[] = {")
    for e in entries:
        if e.get("raw"):
            L.append(f'    {e["expr"]}, // {e["name"]} [{e["kind"]}]')
        elif e["kind"] == "scalar":
            L.append(f'    (u32)({e["expr"]}), // {e["name"]} [scalar]')
        else:
            L.append(f'    (u32)&({e["expr"]}), // {e["name"]} [{e["kind"]}]')
    L.append("};")
    L.append("")
    L.append("#endif")
    L.append("")
    return "\n".join(L)


CFLAGS = [
    "-isystem", "/usr/include/newlib", "-mcpu=arm7tdmi", "-mthumb",
    "-mthumb-interwork", "-std=gnu11", "-fgnu89-inline", "-ffreestanding",
    "-fno-builtin", "-fno-common", "-fno-pic", "-fno-pie",
    "-DMODERN=1", "-DFE8_FEBUILDER_POINTERS=1", "-DFE8_VESLY_DEBUGGER=1",
    "-DFE8_DANGER_BONES=1", "-DFE8_NEW_ANIMS=1", "-DFE8_NEW_TILESETS=1",
    "-DFE8_PURCHASE_GENERICS=1", "-DFE8_TITLE_256_COLORS=1",
    "-DFE8_MULTIPALETTE_BG=1", "-DFE8_MAPGEN=1", "-DFE8_MMB=1",
    "-DFE8_EXTEND_DESC_BOX=1", "-DFE8_DISPLAY_OBTAINABLE_ITEM=1",
    "-DFE8_CO_POWERS=1", "-DFE8_GAME_RANK=1", "-DFE8_CUSTOM_CAMPAIGN=1",
    "-DFE8_SKIP_OPENING=1", "-Iinclude", "-I.",
]

externs = set()
for attempt in range(12):
    src = build_source(externs)
    open(f"{REPO}/src/febuilder_pointers.c", "w").write(src)
    r = subprocess.run(
        ["arm-none-eabi-gcc"] + CFLAGS + ["-c", "src/febuilder_pointers.c",
                                          "-o", "/tmp/fp_probe.o"],
        cwd=REPO, capture_output=True, text=True)
    if r.returncode == 0:
        print(f"compiled clean after {attempt} extern round(s); {len(externs)} local externs")
        break
    new = set(re.findall(r"error: '([A-Za-z_][A-Za-z0-9_]*)' undeclared", r.stderr))
    new |= set(re.findall(r"error: '([A-Za-z_][A-Za-z0-9_]*)' was not declared", r.stderr))
    if not new - externs:
        print("STUCK. remaining errors:")
        print(r.stderr[:4000])
        sys.exit(1)
    externs |= new
else:
    print("too many rounds")
    sys.exit(1)

with open(f"{REPO}/tools/febuilder_pointers/field_order.txt", "w") as f:
    f.write("# <field name>\\t<kind>, one per gFebuilderPointers[] entry, same order.\n")
    f.write("# kind: slot=emit this entry's own ROM offset (FEBuilder derefs it),\n")
    f.write("#       direct=emit the stored address as a ROM offset,\n")
    f.write("#       scalar=emit the stored value verbatim.\n")
    for e in entries:
        f.write(f'{e["name"]}\t{e["kind"]}\n')

print("wrote", len(entries), "entries")
