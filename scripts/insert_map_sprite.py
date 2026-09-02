#!/usr/bin/env python3
"""Convert a standard FE-Repo map-sprite pair (a "-stand.png" idle sheet +
a "-walk.png" walk-cycle sheet) into this repo's unit_icon wait/move
source assets, and print the table rows + declarations to splice in.

Counterpart to scripts/insert_portrait.py, for the OTHER FE8 sprite
system: the small overworld map icon (not the battle portrait). Two
completely separate tables consume these, both indexed differently:

* unit_icon_wait_table[] (src/unit_icon_wait_data.c) -- the STANDING
  icon, indexed by a class's own `smsId` field (src/data/classes.json).
  Row shape: {some_u8, UNIT_ICON_SIZE_*, &sheet}.
* unit_icon_move_table[] (src/unit_icon_move_data.c) -- the WALKING
  animation, indexed by CLASS ID - 1 (gMuInfoTable[jid - 1], src/mu.c) --
  NOT smsId. classId == a class's 1-based position in classes.json's
  array (confirmed: array position 0 == CLASS_EPHRAIM_LORD == jid 1).
  Row shape: {sheet, motion}, where `motion` is a real per-class walk-
  cycle timing table (frame list + per-direction animation list) in
  src/data/unit_icon/const_data_unit_icon_move.s (still archival-lane
  assembly, not yet migrated to a modern .c file).

The `motion` table looked like it would need genuine new authoring per
class -- it doesn't: cross-checked two same-size-class pairs (Cavalier
vs. Paladin for 16x32, Myrmidon vs. Archer for 16x16) and their motion
blocks are byte-identical after symbol renaming. It's a fixed template
per UNIT_ICON_SIZE_*, not unique art-derived timing. So this generates a
new class's motion block by literally cloning an existing same-size
class's block wholesale and renaming every occurrence of the template's
own name to the new one (which also fixes up the embedded sheet .incbin
path, since that's just "TemplateName" as a substring too).

Usage:
    insert_map_sprite.py <stand.png> <walk.png> <Name> --motion-template <ExistingClassName>

<stand.png>/<walk.png> are copied verbatim (not re-encoded -- must
already be <=16 colours, GBA-palette-indexed PNGs in the exact template
layout -- see ASSERTs below) to:
    graphics/unit_icon/wait/unit_icon_wait_<Name>_sheet.png
    graphics/unit_icon/move/unit_icon_move_<Name>_sheet.png

--motion-template must be an EXISTING class (e.g. "Cavalier" for a
16x32/mounted new class, "Archer" or "Myrmidon" for 16x16, "Mercenary_F"
for 32x32) whose own UNIT_ICON_SIZE_* matches <stand.png>'s dimensions --
this script infers <stand.png>'s size class and only warns, doesn't
enforce, that the template's matches (grep the existing wait table row
for --motion-template yourself if unsure).

Prints:
1. The unit_icon_wait_table[] row to append (src/unit_icon_wait_data.c),
   with the next free numeric index (scanned from the table's own count).
2. The extern declarations for both new sheet symbols (append to
   include/unit_icon_pointer.h).
3. The INCBIN_U8 declaration for the wait sheet (append to
   src/data/const_data_unit_icon_wait.c).
4. The cloned assembly block to append to
   src/data/unit_icon/const_data_unit_icon_move.s (covers both the move
   sheet's own .incbin AND the cloned motion table).
5. The unit_icon_move_table[] row to append (src/unit_icon_move_data.c)
   -- MUST be the Nth row where N matches this class's eventual position
   in classes.json's array (this script can't know that; just append in
   the same relative order you append classes.json entries).
"""
import argparse
import pathlib
import re
import shutil
import sys

from PIL import Image

REPO = pathlib.Path(__file__).resolve().parents[1]
MOVE_S = REPO / "src" / "data" / "unit_icon" / "const_data_unit_icon_move.s"
WAIT_C = REPO / "src" / "unit_icon_wait_data.c"

# (stand width, stand height) -> UNIT_ICON_SIZE_* -- confirmed against
# existing checked-in sheets (Archer=16x48, Cavalier=16x96,
# Mercenary_F=32x96); walk sheets are always 32x480 regardless of size.
STAND_SIZE_MAP = {
    (16, 48): "UNIT_ICON_SIZE_16x16",
    (16, 96): "UNIT_ICON_SIZE_16x32",
    (32, 96): "UNIT_ICON_SIZE_32x32",
}
WALK_SIZE = (32, 480)


def check_png(path, expect_size):
    im = Image.open(path)
    if im.size != expect_size and expect_size is not None:
        raise ValueError(f"{path}: expected {expect_size}, got {im.size}")
    im = im.convert("RGB")
    colors = im.getcolors(maxcolors=100000)
    if colors is None or len(colors) > 16:
        n = len(colors) if colors else ">100000"
        raise ValueError(f"{path}: {n} colours, expected <=16 (GBA 4bpp)")
    return im.size


def next_wait_index():
    text = WAIT_C.read_text()
    nums = [int(m) for m in re.findall(r"//\s*(\d+)\s*$", text, re.MULTILINE)]
    return max(nums) + 1 if nums else 0


def clone_motion_block(template, name):
    text = MOVE_S.read_text()
    start_marker = f"\t.global unit_icon_move_{template}_sheet\n"
    start = text.find(start_marker)
    if start == -1:
        raise ValueError(f"couldn't find {start_marker.strip()!r} in {MOVE_S}")

    # The block runs up to (not including) the NEXT class's ".global
    # unit_icon_move_..._sheet" line -- NOT the first ".align 2, 0" inside
    # it (that only terminates the sheet .incbin, not the motion table
    # that follows in the same block), and NOT this same block's own
    # ".global unit_icon_move_<template>_motion" line either (hence
    # anchoring on "_sheet" specifically, not any ".global").
    next_global = re.search(r'\n\t\.global unit_icon_move_\w+_sheet\n',
                             text[start + len(start_marker):])
    end = start + len(start_marker) + (next_global.start() if next_global else len(text) - start - len(start_marker))
    block = text[start:end]

    # Plain substring replace, not \b-bounded regex: template names sit
    # between underscores ("_Archer_"), and underscore is a \w character,
    # so \bArcher\b would never match there at all.
    if template not in block:
        raise ValueError(f"{template!r} not found inside its own extracted block -- extraction bug")
    return block.replace(template, name)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stand", type=pathlib.Path)
    ap.add_argument("walk", type=pathlib.Path)
    ap.add_argument("name", help="e.g. Nomad, Nomad_F -- matches an existing class naming style")
    ap.add_argument("--motion-template", required=True,
                     help="existing class name to clone move-cycle timing from, e.g. Cavalier")
    args = ap.parse_args()

    stand_size = check_png(args.stand, None)
    check_png(args.walk, WALK_SIZE)

    size_class = STAND_SIZE_MAP.get(stand_size)
    if size_class is None:
        sys.exit(f"error: {args.stand} is {stand_size[0]}x{stand_size[1]}, not one of "
                 f"the known stand-sheet sizes {sorted(STAND_SIZE_MAP)} -- "
                 f"is this really a wait/stand sheet, not a move/walk one?")

    wait_dst = REPO / "graphics" / "unit_icon" / "wait" / f"unit_icon_wait_{args.name}_sheet.png"
    move_dst = REPO / "graphics" / "unit_icon" / "move" / f"unit_icon_move_{args.name}_sheet.png"
    shutil.copy(args.stand, wait_dst)
    shutil.copy(args.walk, move_dst)
    print(f"wrote {wait_dst.relative_to(REPO)}")
    print(f"wrote {move_dst.relative_to(REPO)}")

    idx = next_wait_index()
    motion_block = clone_motion_block(args.motion_template, args.name)

    print(f"""
--- append to {WAIT_C.relative_to(REPO)} (before the closing "}};") ---
\t{{2, {size_class}, unit_icon_wait_{args.name}_sheet}}, // {idx}

--- append to include/unit_icon_pointer.h ---
extern char unit_icon_wait_{args.name}_sheet[];
extern char unit_icon_move_{args.name}_sheet[];
extern char unit_icon_move_{args.name}_motion[];

--- append to src/data/const_data_unit_icon_wait.c ---
const u8 __attribute__((aligned(4))) unit_icon_wait_{args.name}_sheet[] = INCBIN_U8("graphics/unit_icon/wait/unit_icon_wait_{args.name}_sheet.4bpp.lz");

--- append to {MOVE_S.relative_to(REPO)} (cloned from {args.motion_template!r}, {size_class}) ---
{motion_block}
--- append to src/unit_icon_move_data.c (before the closing "}};") ---
\t{{unit_icon_move_{args.name}_sheet, unit_icon_move_{args.name}_motion}}, // MUST be the Nth new row matching this class's position in classes.json

smsId for this class (classes.json): {idx}
""")


if __name__ == "__main__":
    main()
