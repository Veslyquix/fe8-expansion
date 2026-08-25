#!/bin/python3
"""Build a full-screen tilemap (TSA) by deduplicating a small periodic
source PNG's tiles and repeating that unit across a larger tile screen.

For backgrounds whose visual pattern is exactly periodic (e.g. a
diagonally-striped UI frame), the source PNG only needs to contain ONE
repeat unit -- this script dedupes that unit down to its unique 8x8 tiles
(feimg-style raw 4bpp bytes, in first-seen order, no flip matching) and
tiles its index pattern across a full screen-sized map (fetsa-style flat
u16 little-endian tile indices, no flip/palette bits set).

Used for graphics/bg/frlgUiFrame.png (src/power.c's CO screen BG3
scrolling background): a 32x32px (4x4 tile) unit, tiled 8x8 times to fill
a full 32x32-tile (256x256px) screen block.
"""

import argparse
import sys

from PIL import Image


def convert_tile_to_4bpp(pixels):
    result = bytearray()
    for i in range(0, len(pixels), 2):
        result.append((pixels[i] & 0xF) | ((pixels[i + 1] & 0xF) << 4))
    return bytes(result)


def extract_unit_tiles(image, unit_w, unit_h):
    """Returns (unique_tiles: list[bytes], unit_indices: list[list[int]])."""
    unique_tiles = []
    tile_to_index = {}
    unit_indices = [[0] * unit_w for _ in range(unit_h)]

    for ty in range(unit_h):
        for tx in range(unit_w):
            tile = image.crop((tx * 8, ty * 8, tx * 8 + 8, ty * 8 + 8))
            pixels = list(tile.getdata())
            tile_4bpp = convert_tile_to_4bpp(pixels)

            index = tile_to_index.get(tile_4bpp)
            if index is None:
                index = len(unique_tiles)
                tile_to_index[tile_4bpp] = index
                unique_tiles.append(tile_4bpp)

            unit_indices[ty][tx] = index

    return unique_tiles, unit_indices


def build_full_map(unit_indices, unit_w, unit_h, screen_w, screen_h):
    entries = []
    for y in range(screen_h):
        for x in range(screen_w):
            entries.append(unit_indices[y % unit_h][x % unit_w])
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("png_file", help="source PNG, exactly one repeat unit")
    parser.add_argument("out_tiles", help="output raw 4bpp tile data (.4bpp)")
    parser.add_argument("out_map", help="output flat u16 LE tilemap (.tsa.bin)")
    parser.add_argument("--screen-width", type=int, default=32, help="tilemap width in tiles (default 32)")
    parser.add_argument("--screen-height", type=int, default=32, help="tilemap height in tiles (default 32)")
    args = parser.parse_args()

    image = Image.open(args.png_file)
    if image.mode != "P":
        sys.exit("IMAGE ERROR: source PNG must be palette-indexed (P mode)")

    unit_w = image.width // 8
    unit_h = image.height // 8
    if unit_w == 0 or unit_h == 0:
        sys.exit("IMAGE ERROR: source PNG must be at least one 8x8 tile")

    unique_tiles, unit_indices = extract_unit_tiles(image, unit_w, unit_h)

    with open(args.out_tiles, "wb") as f:
        for tile in unique_tiles:
            f.write(tile)

    full_map = build_full_map(unit_indices, unit_w, unit_h, args.screen_width, args.screen_height)
    with open(args.out_map, "wb") as f:
        for entry in full_map:
            f.write(entry.to_bytes(2, byteorder="little"))


if __name__ == "__main__":
    main()
