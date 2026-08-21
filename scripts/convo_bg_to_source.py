#!/usr/bin/env python3
"""Convert a multipalette conversation-background PNG into the raw 8bpp +
palette pair the build compiles from (see include/types.h's struct gfx_set
and src/eventscr2.c's LoadMultipaletteConvoBg).

Ported from the FE8U_256ColBG patch's Sommie.py (SRR_FEGBA/gfx/BGs), which
this reproduces exactly: for a 224- or 192-colour image, any pixel using
palette index >= 32 is shifted up by (256 - colCount) so a gap opens right
after index 31 -- 32 colours (2 banks) for 224, 64 colours (4 banks) for
192 -- leaving that gap in the palette for text/chatbubble/portrait UI to
use without touching the background's own colours. A 256-colour image is
passed through unshifted (no gap; the whole palette belongs to the image).

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
BGR555 palette holding only the image's own colCount colours (224*2=448 or
192*2=384 bytes for the reduced modes, matching Sommie.py's own truncation)
-- not a full 256-entry table. The runtime loader (LoadMultipaletteConvoBg,
src/eventscr2.c) applies bytes [0:64) to banks 0-1 and the rest to banks
4-15, skipping banks 2-3 (224) or 2-5 (192) entirely so whatever else has
those banks loaded (text/chatbubble/portrait UI) is left alone.
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
                    if col > 31:
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
    # LoadMultipaletteConvoBg splits this back into two ApplyPalettes calls
    # at load time: entries [0:32) to banks 0-1, entries [32:colCount) to
    # the banks starting right after the reserved gap. Index 0's own entry
    # is written but never referenced by any pixel once the merge above ran.
    pal = pal[: col_count * 3]
    entries = bytearray()
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
