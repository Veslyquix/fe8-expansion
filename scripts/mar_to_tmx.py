#!/bin/python3
"""Convert an existing .mar map (FEBuilder's own map-editor format) into a
Tiled (mapeditor.org) .tmx, the inverse of scripts/tmx_to_map.py -- for
turning a vanilla (or any existing) map into the format this repo's custom
maps use, so it can be edited directly in Tiled afterward.

Usage: mar_to_tmx.py map.mar map.tmx [--tileset-image PATH] [--tileset-name NAME]
                                      [--tile-size N] [--columns N]

Round-trip fidelity: the tile DATA this writes is exact -- feeding the
output back through tmx_to_map.py reproduces the original map's compiled
.bin byte-for-byte (this is checked by
scripts/maptools_tests/test_map_conversion.py, which round-trips every
committed .mar/.tmx pair). This is the inverse of tmx_to_map.py's own
transform: FE8's raw per-cell value is `(gid - firstgid) * 4`, so this
writes `gid = value // 4 + firstgid` (a value not evenly divisible by 4
is not a real FE8 tile id and is rejected rather than silently truncated).

Visual editing caveat: the <tileset><image> this writes is a REFERENCE
ONLY (Tiled needs *a* path to open the file; nothing in this repo's build
reads it) -- unlike tmx_to_map.py, which ignores image data entirely, so
it plays no part in what the compiled .bin ends up containing. To actually
SEE tiles while editing in Tiled, pass --tileset-image pointing at a real
flat spritesheet PNG for this map's tileset (FEBuilder's own map editor
can export one, or point at wherever you already have it -- e.g. the
FieldsPale.png used for the Fields tileset). Without it, Tiled will show
a "file not found" placeholder for the tileset, but the DATA remains
correct and fully round-trippable regardless -- you can still assign
tiles by gid number, or fix the <image> path later.
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom


def load_mar(mar_path):
    json_path = mar_path[:-4] + ".json" if mar_path.endswith(".mar") else mar_path + ".json"
    if not os.path.exists(json_path):
        sys.exit(f"error: map layout info not found: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    with open(mar_path, "rb") as f:
        mar = f.read()

    values = []
    for i in range(0, len(mar), 2):
        raw = mar[i] | (mar[i + 1] << 8)
        values.append(raw >> 3)

    width, height = meta["width"], meta["height"]
    if len(values) != width * height:
        sys.exit(f"error: {mar_path} has {len(values)} tiles, but "
                 f"{json_path} says {width}x{height}={width * height}")

    return width, height, values


def build_tmx(width, height, values, tileset_name, tileset_image,
              tile_size, columns, firstgid=1):
    tilecount = None
    if tileset_image and os.path.exists(tileset_image):
        try:
            from PIL import Image
            with Image.open(tileset_image) as im:
                img_w, img_h = im.size
        except Exception:
            img_w = img_h = None
    else:
        img_w = img_h = None

    if img_w and columns is None:
        columns = img_w // tile_size
    if columns is None:
        columns = 32  # matches this repo's other 512px-wide tileset sheets
    if img_w and img_h:
        tilecount = columns * (img_h // tile_size)

    root = ET.Element("map", {
        "version": "1.9",
        "tiledversion": "1.9.2",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "width": str(width),
        "height": str(height),
        "tilewidth": str(tile_size),
        "tileheight": str(tile_size),
        "infinite": "0",
        "nextlayerid": "2",
        "nextobjectid": "1",
    })

    ts_attrs = {
        "firstgid": str(firstgid),
        "name": tileset_name,
        "tilewidth": str(tile_size),
        "tileheight": str(tile_size),
        "columns": str(columns),
    }
    if tilecount is not None:
        ts_attrs["tilecount"] = str(tilecount)
    tileset = ET.SubElement(root, "tileset", ts_attrs)
    image_attrs = {"source": tileset_image or f"{tileset_name}.png"}
    if img_w and img_h:
        image_attrs["width"] = str(img_w)
        image_attrs["height"] = str(img_h)
    ET.SubElement(tileset, "image", image_attrs)

    layer = ET.SubElement(root, "layer", {
        "id": "1", "name": "Tile Layer 1", "width": str(width), "height": str(height),
    })
    data = ET.SubElement(layer, "data")
    for value in values:
        if value % 4 != 0:
            sys.exit(f"error: raw tile value {value} is not divisible by 4 -- "
                     f"not a value tmx_to_map.py's transform can represent exactly")
        gid = value // 4 + firstgid
        ET.SubElement(data, "tile", {"gid": str(gid)})

    return root


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mar", help="input .mar (with a matching .json sidecar)")
    ap.add_argument("tmx", help="output .tmx")
    ap.add_argument("--tileset-name", default=None,
                    help="tileset name in the .tmx (default: derived from the map name)")
    ap.add_argument("--tileset-image", default=None,
                    help="path to a real tileset spritesheet PNG, for visual editing in "
                         "Tiled (optional -- the tile DATA is correct either way)")
    ap.add_argument("--tile-size", type=int, default=16, help="tile size in pixels (default 16)")
    ap.add_argument("--columns", type=int, default=None,
                    help="tileset columns (default: inferred from --tileset-image, else 32)")
    args = ap.parse_args()

    width, height, values = load_mar(args.mar)
    tileset_name = args.tileset_name or os.path.splitext(os.path.basename(args.mar))[0]

    root = build_tmx(width, height, values, tileset_name, args.tileset_image,
                      args.tile_size, args.columns)

    rough = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(rough).toprettyxml(indent=" ")
    # minidom adds its own XML declaration line; drop it, we write our own below
    pretty = "\n".join(pretty.split("\n")[1:])

    with open(args.tmx, "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(pretty.strip() + "\n")

    if not args.tileset_image:
        print(f"note: no --tileset-image given -- {args.tmx}'s tileset image "
              f"reference is a placeholder; the tile data is correct and "
              f"round-trippable regardless, but Tiled won't be able to show "
              f"tile art until you point it at a real spritesheet (Tileset "
              f"panel > right-click > Tileset Properties in Tiled, or re-run "
              f"with --tileset-image).", file=sys.stderr)


if __name__ == "__main__":
    main()
