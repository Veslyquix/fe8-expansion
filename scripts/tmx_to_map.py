#!/bin/python3
"""Convert a Tiled (mapeditor.org) .tmx map into this repo's map .bin
format -- the same format scripts/mar_to_map.py produces from FEBuilder's
own .mar map-editor format, so a chapter's map layout can be authored/
edited directly in this repo (in Tiled) instead of round-tripping through
FEBuilder to export a .mar.

Usage: tmx_to_map.py map.tmx map.bin

Requirements on the .tmx (Tiled's defaults already satisfy these; only
matters if you hand-edit the XML or change Map Properties):
  - orientation="orthogonal", infinite="0" (a single fixed-size grid).
  - Exactly one <tileset>, OR several with correctly ascending firstgid
    (standard Tiled multi-tileset gid resolution) -- FE8 maps only ever
    address one physical tileset image, but this doesn't assume that.
  - Exactly one <layer>, whose <data> is either the plain per-tile XML
    form (<tile gid="N"/> children, Tiled's "Tile Layer Format: XML") or
    encoding="csv" (Tiled's default for new maps) -- NOT base64/gzip/zlib
    (switch Map Properties > Tile Layer Format to CSV or XML if needed).

Tile value transform (confirmed byte-for-byte against a known-good .mar/
.tmx pair of the same map, graphics/map/layout/NewPrologueMap): a raw
FE8 map tile value is exactly `(gid - tileset_firstgid) * 4` -- Tiled
indexes this tileset's 16x16 tiles directly, but FE8's own map format
addresses a 4x finer-grained tile space (each 16x16 Tiled tile is 4
consecutive raw values apart). gid 0 (Tiled's "empty tile") maps to raw
value 0. This mirrors mar_to_map.py's own `raw_mar_value >> 3` (which
divides out a different fixed factor from FEBuilder's own on-disk .mar
encoding) -- both land on the same final per-cell value the game itself
reads from the compiled map .bin.
"""
import sys
import xml.etree.ElementTree as ET

FLIP_FLAGS_MASK = 0xF0000000  # Tiled's horizontal/vertical/diagonal/rotated flip bits


def parse_tilesets(root):
    """[(firstgid, name)], sorted descending by firstgid -- standard Tiled
    multi-tileset gid resolution: the owning tileset for a gid is the
    first one (highest firstgid) whose firstgid is <= that gid."""
    tilesets = []
    for ts in root.findall("tileset"):
        firstgid = ts.get("firstgid")
        if firstgid is None:
            sys.exit(f"error: <tileset> missing firstgid (external .tsx tilesets "
                      f"aren't supported -- embed the tileset in the .tmx)")
        tilesets.append((int(firstgid), ts.get("name", "?")))
    if not tilesets:
        sys.exit("error: .tmx has no <tileset>")
    tilesets.sort(key=lambda t: t[0], reverse=True)
    return tilesets


def resolve_local_index(gid, tilesets, path):
    gid &= ~FLIP_FLAGS_MASK
    if gid == 0:
        return 0
    for firstgid, name in tilesets:
        if gid >= firstgid:
            return gid - firstgid
    sys.exit(f"error: {path}: tile gid={gid} is below every tileset's firstgid")


def parse_layer_gids(root, path):
    layers = root.findall("layer")
    if not layers:
        sys.exit(f"error: {path}: no <layer> found")
    if len(layers) > 1:
        print(f"warning: {path}: {len(layers)} <layer> elements found, "
              f"using only the first (\"{layers[0].get('name', '?')}\") -- "
              f"FE8 maps are a single flat tile grid", file=sys.stderr)
    layer = layers[0]
    data = layer.find("data")
    if data is None:
        sys.exit(f"error: {path}: <layer> has no <data>")

    encoding = data.get("encoding")
    if encoding is None:
        tiles = data.findall("tile")
        if not tiles:
            sys.exit(f"error: {path}: <data> has no <tile> children and no "
                      f"encoding attribute -- unsupported layer data format")
        return [int(t.get("gid", "0")) for t in tiles]
    elif encoding == "csv":
        text = (data.text or "").strip()
        if not text:
            sys.exit(f"error: {path}: <data encoding=\"csv\"> is empty")
        return [int(v) for v in text.replace("\n", "").split(",") if v.strip()]
    else:
        sys.exit(f"error: {path}: <data encoding=\"{encoding}\"> is not supported "
                  f"(base64/gzip/zlib) -- in Tiled, Map > Map Properties > "
                  f"Tile Layer Format, switch to \"CSV\" or \"XML\", then re-save")


def convert(path):
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "map":
        sys.exit(f"error: {path}: root element is <{root.tag}>, not <map>")

    orientation = root.get("orientation")
    if orientation != "orthogonal":
        sys.exit(f"error: {path}: orientation=\"{orientation}\", must be \"orthogonal\"")
    if root.get("infinite") not in (None, "0"):
        sys.exit(f"error: {path}: infinite maps aren't supported -- in Tiled, "
                  f"uncheck Map > Map Properties > Infinite, then re-save")

    width = int(root.get("width"))
    height = int(root.get("height"))
    if not (1 <= width <= 255 and 1 <= height <= 255):
        sys.exit(f"error: {path}: {width}x{height} out of range (1-255 each)")

    tilesets = parse_tilesets(root)
    gids = parse_layer_gids(root, path)

    if len(gids) != width * height:
        sys.exit(f"error: {path}: layer has {len(gids)} tiles, expected "
                  f"{width}*{height}={width * height}")

    flipped = sum(1 for g in gids if g & FLIP_FLAGS_MASK)
    if flipped:
        print(f"warning: {path}: {flipped} tile(s) have a Tiled flip/rotate flag set -- "
              f"FE8 map tiles have no per-cell flip, the flag is silently ignored",
              file=sys.stderr)

    out = bytearray()
    out.append(width)
    out.append(height)
    for gid in gids:
        value = resolve_local_index(gid, tilesets, path) * 4
        if value > 0xFFFF:
            sys.exit(f"error: {path}: tile value {value} overflows 16 bits "
                      f"(gid {gid} too far past its tileset's firstgid)")
        out.append(value & 0xFF)
        out.append((value >> 8) & 0xFF)

    return bytes(out)


def main(args):
    try:
        path = args[1]
        out_path = args[2]
    except IndexError:
        sys.exit(f"Usage: {args[0]} map.tmx map.bin")

    data = convert(path)
    with open(out_path, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main(sys.argv)
