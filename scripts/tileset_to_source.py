#!/usr/bin/env python3
"""Convert an FEBuilder-style map tileset export into this repo's map assets.

A map tileset here is three checked-in sources under graphics/map/:

  <name>ObjectType.png        1024 8x8 tiles of 4bpp graphics, stored (like
                              the vanilla ObjectTypeN.png) as a 256x256
                              greyscale image whose 16 grey levels ARE the
                              4bpp indices. graphics_file_rules.mk turns it
                              into .4bpp, and Makefile's `%.lz` rule then
                              compresses it for incbin.
  <name>MapPalette.pal        JASC-PAL, 160 colours = the 10 map palette rows.
                              Makefile's `%.gbapal: %.pal` produces the binary.
  <name>TileConfiguration.S   1024 `metatile` entries (0x1000 u16 of TSA)
                              followed by the 0x200 u16 terrain lookup, per
                              graphics/map/tile_config.inc. Assembled to .bin
                              by Makefile, then compressed by `%.lz`.

The FEBuilder export supplies all three in two files:

  * the "Object Palette" PNG is 256x256 with pixel indices 0-15 (the tile
    graphics) AND a 160-colour palette (the 10 rows) -- so it feeds both the
    ObjectType image and the MapPalette.
  * the .mapchip_config is exactly 9216 bytes, the same layout the
    TileConfiguration binary decompresses to (8192 TSA + 1024 terrain).

Usage:
    python3 scripts/tileset_to_source.py --name SuperFields \\
        --palette-png "<...Object Palette (X).png>" \\
        --mapchip-config "<....mapchip_config>"
"""
import argparse
import os
import re
import pathlib

from PIL import Image

REPO = pathlib.Path(__file__).resolve().parents[1]
MAPDIR = REPO / "graphics" / "map"

TILES = 1024            # 8x8 tiles in an ObjectType sheet
PALETTE_COLOURS = 160   # 10 rows x 16
TSA_BYTES = 0x1000 * 2  # 0x1000 u16 of tile-graphics config
TERRAIN_BYTES = 0x200 * 2
CONFIG_BYTES = TSA_BYTES + TERRAIN_BYTES  # 9216


def load_terrain_names():
    """Reverse map value -> TERRAIN_* name from graphics/map/terrains.inc."""
    names = {}
    text = (MAPDIR / "terrains.inc").read_text()
    for name, value in re.findall(r'\.equ\s+(TERRAIN_\w+),\s*(0x[0-9A-Fa-f]+|\d+)', text):
        names.setdefault(int(value, 0), name)
    return names


def write_object_type(src: Image.Image, out_png: pathlib.Path):
    """4bpp indices -> 256x256 greyscale, matching the vanilla ObjectTypeN.png."""
    if src.mode != "P":
        raise SystemExit(f"expected an indexed (mode P) PNG, got mode {src.mode}")
    if src.size != (256, 256):
        raise SystemExit(f"expected a 256x256 tile sheet, got {src.size}")
    data = list(src.getdata())
    hi = max(data)
    if hi > 15:
        raise SystemExit(
            f"pixel index {hi} exceeds 4bpp; this export is not a plain tile sheet")
    grey = Image.new("L", src.size)
    # NOTE: the vanilla ObjectTypeN.png files store the 4bpp index INVERTED --
    # index 0 is white (255) and index 15 is black (0), i.e. grey = (15-i)*17.
    # gbagfx reproduces that inversion on the way back to .4bpp, so writing the
    # obvious i*17 yields a sheet whose every pixel is (15 - index): visually a
    # fine speckle across the whole map. Verified against vanilla
    # ObjectType1.png/.4bpp, and byte-for-byte against a reference ROM.
    grey.putdata([(15 - v) * 17 for v in data])
    grey.save(out_png)
    return len(set(data))


def write_palette(src: Image.Image, out_pal: pathlib.Path):
    """First 160 palette entries -> JASC-PAL, round-tripped through GBA 5-bit."""
    pal = src.getpalette()
    if pal is None or len(pal) < PALETTE_COLOURS * 3:
        raise SystemExit("source PNG has fewer than 160 palette entries")
    lines = ["JASC-PAL", "0100", str(PALETTE_COLOURS)]
    for i in range(PALETTE_COLOURS):
        r, g, b = pal[i * 3:i * 3 + 3]
        # Quantise to the GBA's 5 bits per channel, then re-expand, so the
        # committed .pal already reflects exactly what the hardware shows.
        lines.append(" ".join(str(round((v >> 3) * 255 / 31)) for v in (r, g, b)))
    # JASC-PAL is a CRLF format; tools/pal2gbapal rejects LF ("LF line
    # endings aren't supported"), and every committed graphics/map/*.pal is CRLF.
    out_pal.write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii"))


def write_tile_config(cfg: bytes, out_s: pathlib.Path, name: str):
    if len(cfg) != CONFIG_BYTES:
        raise SystemExit(
            f"mapchip_config is {len(cfg)} bytes, expected {CONFIG_BYTES} "
            f"({TSA_BYTES} TSA + {TERRAIN_BYTES} terrain)")
    terrain_names = load_terrain_names()
    out = [
        '\t.include "graphics/map/tile_config.inc"',
        "",
        "\t.section .rodata",
        "",
        f"@ {name}: converted from an FEBuilder .mapchip_config by",
        "@ scripts/tileset_to_source.py -- do not edit by hand.",
        "",
        "@ 1024 metatiles (tile-graphics configuration): TL, TR, BL, BR corner tiles",
    ]
    for i in range(0, TSA_BYTES, 8):
        tl, tr, bl, br = (int.from_bytes(cfg[i + n:i + n + 2], "little") for n in (0, 2, 4, 6))
        out.append(f"\tmetatile 0x{tl:04X}, 0x{tr:04X}, 0x{bl:04X}, 0x{br:04X}")
    out += ["", "@ Terrain-type lookup"]
    terrain = cfg[TSA_BYTES:]
    for i in range(0, len(terrain), 4):
        row = [terrain_names.get(b, f"0x{b:02X}") for b in terrain[i:i + 4]]
        out.append("\t.byte " + ", ".join(row))
    out_s.write_text("\n".join(out) + "\n")
    return sum(1 for b in terrain if b not in terrain_names)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help='asset prefix, e.g. "SuperFields"')
    ap.add_argument("--palette-png", required=True)
    ap.add_argument("--mapchip-config", required=True)
    args = ap.parse_args()

    src = Image.open(args.palette_png)
    cfg = pathlib.Path(args.mapchip_config).read_bytes()

    png = MAPDIR / f"{args.name}ObjectType.png"
    pal = MAPDIR / f"{args.name}MapPalette.pal"
    s = MAPDIR / f"{args.name}TileConfiguration.S"

    ncolours = write_object_type(src, png)
    write_palette(src, pal)
    unknown = write_tile_config(cfg, s, args.name)

    print(f"  {png.relative_to(REPO)}  ({TILES} tiles, {ncolours} indices used)")
    print(f"  {pal.relative_to(REPO)}  ({PALETTE_COLOURS} colours / 10 rows)")
    print(f"  {s.relative_to(REPO)}  (1024 metatiles + {TERRAIN_BYTES}B terrain"
          + (f", {unknown} raw terrain bytes with no TERRAIN_* name)" if unknown else ")"))


if __name__ == "__main__":
    main()
