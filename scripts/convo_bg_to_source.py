#!/usr/bin/env python3
"""Convert a multipalette conversation-background PNG into the raw 8bpp +
palette pair the build compiles from (see include/types.h's struct gfx_set
and src/eventscr2.c's LoadMultipaletteConvoBg).

Ported from the FE8U_256ColBG patch's Sommie.py (SRR_FEGBA/gfx/BGs), with
one deviation from Sommie.py for the 192-colour mode (see below). A
256-colour image is passed through unshifted (no gap; the whole palette
belongs to the image).

For a 224-colour image, any pixel using palette index >= 32 is shifted up
by 32 so a gap opens right after index 31 -- the image keeps banks 0-1 for
its own low colours, and banks 2-3 (32 colours) are left untouched for
text/chatbubble/portrait UI.

For a 192-colour image (a newer, different scheme from Sommie.py's
original): banks 0-3 (64 colours) are left untouched *entirely* -- for
got item / gold popup UI -- and every pixel maps into banks 4-15 instead,
i.e. every pixel index is shifted up by 64 unconditionally (no low-index
exception the way 224 keeps one). See LoadMultipaletteConvoBg
(src/eventscr2.c) for the matching runtime side of this.

Palette index 0 is additionally reserved everywhere (Sommie.py does not do
this): GBA 8bpp BG tiles always treat colour index 0 as transparent, in
every mode, not just the ones with a text/chatbubble gap -- a real image
pixel landing on index 0 shows the backdrop through it instead of its
intended colour. If the source PNG's own index 0 is actually used by any
pixel, this merges those pixels into whichever other palette entry is
closest in RGB space (typically imperceptible) and frees index 0, rather
than reserving a whole extra colour slot for it.

Usage:
    python3 scripts/convo_bg_to_source.py <colCount> <input.png> \\
        <output.8bpp> <output.gbapal>

<colCount> is 256, 224, or 192. <input.png> must be indexed-colour
("P" mode), exactly 256x160 (the full 32x20-tile BG map -- the visible
screen only shows the left 240 of those 256 pixels), and must not use any
palette index >= colCount (checked below).

Output <output.8bpp> is raw, gbagfx-compatible tile-order 8bpp data (still
needs `tools/gbagfx/gbagfx <output.8bpp> <output.8bpp>.lz` to compress for
INCBIN -- this script does not compress). <output.gbapal> is a packed
BGR555 palette:
  - 256 mode: colCount (256) entries, no padding -- the whole table.
  - 224 mode: colCount (224) entries, no padding -- entries [0:32) are
    real colours for banks 0-1, entries [32:224) are real colours for
    banks 4-15 (LoadMultipaletteConvoBg applies set->pal to banks 0-1 and
    set->pal+32 to banks 4-15).
  - 192 mode: 224 entries -- a 32-entry *dummy* padding block (never
    applied to any bank -- LoadMultipaletteConvoBg only ever reads this
    file starting at set->pal+32) followed by the 192 real colours, which
    land entirely in banks 4-15.
"""
import argparse
import struct
import sys
from pathlib import Path

from PIL import Image


def convert(col_count: int, src: Path, out_gfx: Path, out_pal: Path) -> None:
    if col_count not in (256, 224, 192):
        raise SystemExit(f"colCount must be 256, 224, or 192, got {col_count}")

    im = Image.open(src)
    if im.mode != "P":
        raise SystemExit(f"{src}: not an indexed-colour (P mode) PNG")
    if im.size != (256, 160):
        raise SystemExit(f"{src}: must be exactly 256x160, got {im.size}")

    gap = 256 - col_count  # 0, 32, or 64
    width, height = im.size

    pal = im.getpalette() or []
    pal += [0] * (col_count * 3 - len(pal))

    data = bytearray(im.getdata())
    if 0 in data:
        r0, g0, b0 = pal[0], pal[1], pal[2]
        best_idx, best_dist = None, None
        for idx in range(1, col_count):
            r, g, b = pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2]
            dist = (r - r0) ** 2 + (g - g0) ** 2 + (b - b0) ** 2
            if best_dist is None or dist < best_dist:
                best_dist, best_idx = dist, idx
        if best_idx is None:
            raise SystemExit(
                f"{src}: pixels use palette index 0 (transparent on real "
                f"hardware) and there is no other colour to merge them "
                f"into -- reduce the image to fewer than {col_count} colours"
            )
        for i, v in enumerate(data):
            if v == 0:
                data[i] = best_idx
        im = im.copy()
        im.putdata(data)

    pixels = im.load()

    out = bytearray(width * height)
    i = 0
    for ytile in range(height // 8):
        v = ytile * 8
        for xtile in range(width // 8):
            h = xtile * 8
            for y in range(8):
                for x in range(8):
                    col = pixels[h + x, v + y]
                    # 192 mode reserves banks 0-3 entirely and maps every
                    # pixel into banks 4-15 -- unlike 224, there is no
                    # low-index exception (224 keeps indices <=31 in
                    # banks 0-1; 192 has nothing in banks 0-3 at all).
                    if col_count == 192 or col > 31:
                        col += gap
                        if col > 255:
                            raise SystemExit(
                                f"{src}: uses a palette index >= {col_count} "
                                f"(pixel maps to {col}); reduce the image to "
                                f"{col_count} colours or lower"
                            )
                    out[i] = col
                    i += 1

    out_gfx.write_bytes(bytes(out))

    # Packed, truncated to the image's own colCount colours -- no gap
    # inserted here (that only exists in the pixel indices written above).
    # Index 0's own entry is written but never referenced by any pixel once
    # the merge above ran.
    #
    # 224 mode: LoadMultipaletteConvoBg applies entries [0:32) to banks 0-1
    # and entries [32:224) to banks 4-15, so this table needs no padding --
    # both halves are real colours.
    #
    # 192 mode: LoadMultipaletteConvoBg only ever reads this file starting
    # at set->pal+32 (there is no separate banks-0-1 call the way 224 has),
    # so a 32-entry dummy block goes first -- it is never applied to any
    # bank -- followed by the 192 real colours, which land entirely in
    # banks 4-15.
    pal = pal[: col_count * 3]
    entries = bytearray()
    if col_count == 192:
        entries += b"\x00\x00" * 32
    for idx in range(col_count):
        r, g, b = pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2]
        entries += struct.pack("<H", (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))

    out_pal.write_bytes(bytes(entries))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("colCount", type=int)
    parser.add_argument("input", type=Path)
    parser.add_argument("output_gfx", type=Path)
    parser.add_argument("output_pal", type=Path)
    args = parser.parse_args(argv)

    convert(args.colCount, args.input, args.output_gfx, args.output_pal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
