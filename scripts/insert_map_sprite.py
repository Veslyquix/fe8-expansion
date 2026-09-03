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

import numpy as np
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


# One .2byte-triple OAM entry ("Y, attr1, attr2") followed by its tile
# pointer, for a single frame_N -- matches the shape every frame in this
# repo's move-sheet motion blocks uses (regular, non-affine, one sprite
# per frame). attr1's low 9 bits are a signed on-screen X offset (see
# _signed9/_pack_x9 below); everything above bit8 (shape/size/flip) is
# preserved untouched by the correction pass.
_FRAME_RE = re.compile(
    r'(unit_icon_move_(\w+)_frame_(\d+): @[^\n]*\n'
    r'\t\.2byte 1 @ oam entries\n'
    r'\t\.2byte (0x[0-9A-Fa-f]+), (0x[0-9A-Fa-f]+), (0x[0-9A-Fa-f]+) @ OAM Data #0\n'
    r'\t\.2byte (0x[0-9A-Fa-f]+) @ Sheet Tile #0\n)'
)


def _signed9(raw):
    raw &= 0x1FF
    return raw - 512 if raw & 0x100 else raw


def _pack_x9(attr1, x):
    return (attr1 & ~0x1FF) | (x & 0x1FF)


def _block_content_x_range(img, tile_val, sheet_width_px=32, tile_px=8):
    """(min_x, max_x) of non-background pixels in the 32x32 block this
    frame's tile pointer selects, or None if the block is blank. tile_val
    is in TILE units (8x8 each); sheet is sheet_width_px wide, so every
    (sheet_width_px // tile_px) tiles is one 8px-tall strip -- a 32px-tall
    block is 4 such strips, i.e. tile_val steps of 0x10 between frames'
    own blocks (matches this repo's actual const_data_unit_icon_move.s
    tile pointers: 0x0, 0x10, 0x20, ...)."""
    tiles_per_row = sheet_width_px // tile_px
    y0 = (tile_val // tiles_per_row) * tile_px
    w, h = img.size
    if y0 >= h:
        return None
    arr = np.array(img)
    crop = arr[y0:min(y0 + 32, h), 0:min(sheet_width_px, w)]
    nz = np.argwhere(crop != 0)
    if len(nz) == 0:
        return None
    xs = nz[:, 1]
    return int(xs.min()), int(xs.max())


def align_motion_block_to_own_art(block, name, template_img_path, new_img_path):
    """Corrects each frame's OAM X offset so the NEW class's own art lands
    at the same on-screen position the TEMPLATE's art does for that frame,
    instead of leaving the template's cloned (donor-art-tuned) X offsets
    in place unchanged.

    Why this exists: the motion table's frame layout/timing IS a genuine
    fixed template shared across same-UNIT_ICON_SIZE classes, but a few
    individual frames (typically the trailing "settle" frames, seen for
    both Archer and Thief) carry a small hand-tuned per-class X nudge
    compensating for exactly where that donor's artist happened to draw
    the character within the frame's 32px-wide block. A new class's art
    only coincidentally shares a donor's placement in most frames (whole
    sprite sheets are often traced/adapted from one specific donor, e.g.
    LynLord's from Eirika_Lord) -- but not always in every single frame.
    Blindly cloning the donor's OAM bytes wholesale silently carries over
    THAT donor's nudges, which is wrong for any frame where the new art's
    own placement doesn't match the donor's. Confirmed via a real bug:
    LynLord's frames 0-15 pixel-matched Eirika_Lord's art exactly (fine to
    clone as-is), but frames 16-18 sat ~4px further right in LynLord's own
    sheet -- cloning Archer's (or even Eirika_Lord's) OAM X for those 3
    frames put LynLord's sprite visibly off during that animation.

    Returns (corrected_block, corrections) where corrections is a list of
    (frame_num, delta_px) for every frame this actually changed -- print
    these so a human can sanity-check the result once, rather than
    trusting silent pixel math forever.
    """
    template_img = Image.open(template_img_path)
    new_img = Image.open(new_img_path)

    corrections = []

    def _replace(m):
        whole, frame_name, frame_num, y, attr1_s, attr2, tile_s = m.groups()
        if frame_name != name:
            return whole
        tile_val = int(tile_s, 16)
        tmpl_range = _block_content_x_range(template_img, tile_val)
        new_range = _block_content_x_range(new_img, tile_val)
        if tmpl_range is None or new_range is None:
            return whole
        tmpl_center = (tmpl_range[0] + tmpl_range[1]) / 2
        new_center = (new_range[0] + new_range[1]) / 2
        delta = round(tmpl_center - new_center)
        if delta == 0:
            return whole
        attr1 = int(attr1_s, 16)
        x = _signed9(attr1)
        new_attr1 = _pack_x9(attr1, x + delta)
        corrections.append((int(frame_num), delta))
        return whole.replace(
            f"{attr1_s}, {attr2} @ OAM Data #0",
            f"0x{new_attr1:04X}, {attr2} @ OAM Data #0",
        )

    corrected = _FRAME_RE.sub(_replace, block)
    return corrected, corrections


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

    # Re-derive each frame's OAM X offset from where THIS class's own art
    # actually sits, instead of trusting the donor's cloned bytes verbatim
    # -- see align_motion_block_to_own_art's docstring for why (a real bug:
    # LynLord's frames 16-18 sat ~4px right of Eirika_Lord's, which her
    # cloned motion table didn't account for).
    template_move_png = REPO / "graphics" / "unit_icon" / "move" / f"unit_icon_move_{args.motion_template}_sheet.png"
    corrections = []
    if template_move_png.exists():
        motion_block, corrections = align_motion_block_to_own_art(
            motion_block, args.name, template_move_png, move_dst)
    else:
        print(f"warning: {template_move_png.relative_to(REPO)} not found on disk -- "
              f"skipping per-frame alignment correction, motion block is an "
              f"UNCHECKED clone of {args.motion_template!r}'s own OAM offsets",
              file=sys.stderr)

    if corrections:
        print(f"note: adjusted {len(corrections)} frame(s)' OAM X offset (bbox-center "
              f"alignment against {args.name}'s own art instead of "
              f"{args.motion_template!r}'s) -- (frame, delta_px): {corrections}. "
              f"This is a best-effort SUGGESTION, not a guaranteed-correct value --  "
              f"bbox-center comparison is thrown off when the new class's art is "
              f"legitimately a different width than the template's (different horse "
              f"breed, hair, cape, ...), producing a nonzero 'correction' for frames "
              f"that don't actually need one. Load both PNGs side by side and eyeball "
              f"the flagged frames before trusting this over the template's own value.",
              file=sys.stderr)

    print(f"""
--- append to {WAIT_C.relative_to(REPO)} (before the closing "}};") ---
\t{{2, {size_class}, unit_icon_wait_{args.name}_sheet}}, // {idx}

--- append to include/unit_icon_pointer.h ---
extern char unit_icon_wait_{args.name}_sheet[];
extern char unit_icon_move_{args.name}_sheet[];
extern char unit_icon_move_{args.name}_motion[];

--- append to src/data/const_data_unit_icon_wait.c ---
const u8 __attribute__((aligned(4))) unit_icon_wait_{args.name}_sheet[] = INCBIN_U8("graphics/unit_icon/wait/unit_icon_wait_{args.name}_sheet.4bpp.lz");

--- append to {MOVE_S.relative_to(REPO)} (cloned from {args.motion_template!r}, {size_class}, per-frame X-aligned to {args.name}'s own art) ---
{motion_block}
--- append to src/unit_icon_move_data.c (before the closing "}};") ---
\t{{unit_icon_move_{args.name}_sheet, unit_icon_move_{args.name}_motion}}, // MUST be the Nth new row matching this class's position in classes.json

smsId for this class (classes.json): {idx}
""")


if __name__ == "__main__":
    main()
