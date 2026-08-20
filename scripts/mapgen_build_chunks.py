#!/usr/bin/env python3
"""Generates src/mapgen_chunks_data.c for FE8_MAPGEN.

Run at build time (see the rule in modern.mk); output is not committed, same
as src/msg_data.c. Reads every .tmx under scripts/map_gen/chunks/*/tmx/ and
emits the flat tables include/mapgen_chunks_data.h declares: one entry per
chunk (raw, uncropped dimensions + the edge(s) its filename says it was cut
against) plus one shared array of its non-background tiles. Cropping to
MAX_X/MAX_Y/MAX_TILES happens at placement time in src/mapgen.c, not here --
those stay runtime-editable without rerunning this script.

Usage:
    python3 scripts/mapgen_build_chunks.py [output.c]
"""

import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS_GLOB = os.path.join(REPO, "scripts", "map_gen", "chunks", "*", "tmx", "*.tmx")
DEFAULT_OUT = os.path.join(REPO, "src", "mapgen_chunks_data.c")

EDGE_RE = re.compile(r"_edge([A-Za-z]*)$")
EDGE_BITS = {"T": 1, "B": 2, "L": 4, "R": 8}   # must match include/mapgen_chunks_data.h

# u8 fields in struct MapGenChunk / MapGenChunkTile.
MAX_DIM = 255
MAX_TILES_PER_CHUNK = 255


def parse_edge_mask(stem):
    m = EDGE_RE.search(stem)
    if not m or not m.group(1) or m.group(1).lower() == "none":
        return 0
    mask = 0
    for ch in m.group(1).upper():
        mask |= EDGE_BITS.get(ch, 0)
    return mask


def decode_layer(data_el, width, height):
    """[gid, ...] row-major, 0 for background. Handles both the per-cell
    <tile gid="N"/> form these chunks use and a bare CSV body, in case a chunk
    is ever re-exported in the other encoding."""
    if data_el.get("encoding") == "csv" or (data_el.text and data_el.text.strip()
                                            and not list(data_el)):
        text = "".join(data_el.itertext())
        gids = [int(v) for v in re.findall(r"-?\d+", text)]
    else:
        gids = []
        for tile in data_el.findall("tile"):
            gid = tile.get("gid")
            gids.append(int(gid) if gid else 0)

    expected = width * height
    if len(gids) < expected:
        gids.extend([0] * (expected - len(gids)))
    return gids[:expected]


def load_chunk(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        print(f"warning: skipping {path}: {exc}", file=sys.stderr)
        return None

    width = int(root.get("width", "0"))
    height = int(root.get("height", "0"))
    if width <= 0 or height <= 0 or width > MAX_DIM or height > MAX_DIM:
        return None

    layer = root.find("layer")
    data_el = layer.find("data") if layer is not None else None
    if data_el is None:
        return None

    gids = decode_layer(data_el, width, height)

    tiles = []
    for i, gid in enumerate(gids):
        # gid<=1 is background OR raw tile index 0 (the tileset's reserved
        # "undefined" placeholder, see mapgen_chunks_data.h) -- neither is
        # real content, both are dropped the same way.
        if gid <= 1:
            continue
        y, x = divmod(i, width)
        tiles.append((x, y, gid - 1))

    if not tiles or len(tiles) > MAX_TILES_PER_CHUNK:
        return None

    stem = os.path.splitext(os.path.basename(path))[0]
    return dict(width=width, height=height, edges=parse_edge_mask(stem), tiles=tiles)


def generate(out_path):
    paths = sorted(glob.glob(CHUNKS_GLOB))
    chunks = []
    for p in paths:
        c = load_chunk(p)
        if c:
            chunks.append(c)

    lines = [
        '#include "global.h"',
        '',
        '#include "mapgen_chunks_data.h"',
        '',
        '#if FE8_MAPGEN',
        '',
    ]

    all_tiles = []
    chunk_rows = []
    for c in chunks:
        offset = len(all_tiles)
        all_tiles.extend(c["tiles"])
        chunk_rows.append(
            f'    {{{c["width"]}, {c["height"]}, {c["edges"]}, {len(c["tiles"])}, {offset}}},'
        )

    tile_count = max(len(all_tiles), 1)
    lines.append(f'const struct MapGenChunkTile gMapGenChunkTiles[{tile_count}] = {{')
    for i in range(0, len(all_tiles), 8):
        row = all_tiles[i:i + 8]
        lines.append('    ' + ' '.join(f'{{{x}, {y}, {t}}},' for x, y, t in row))
    if not all_tiles:
        lines.append('    {0, 0, 0},')
    lines.append('};')
    lines.append('')

    chunk_count = max(len(chunks), 1)
    lines.append(f'const struct MapGenChunk gMapGenChunks[{chunk_count}] = {{')
    lines.extend(chunk_rows)
    if not chunks:
        lines.append('    {0, 0, 0, 0, 0},')
    lines.append('};')
    lines.append('')
    lines.append(f'const u16 gMapGenChunkCount = {len(chunks)};')
    lines.append('')
    lines.append('#endif // FE8_MAPGEN')
    lines.append('')

    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", newline="\n") as f:
        f.write("\n".join(lines))
    os.replace(tmp_path, out_path)

    total_tiles = len(all_tiles)
    print(f"wrote {out_path}: {len(chunks)} chunks ({total_tiles} tiles) "
          f"from {len(paths)} .tmx files")


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    generate(out_path)


if __name__ == "__main__":
    main()
