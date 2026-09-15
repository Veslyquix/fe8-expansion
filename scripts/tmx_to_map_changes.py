#!/usr/bin/env python3
"""Extract FE8 map-change data from hidden Tiled layers.

Usage:
  tmx_to_map_changes.py map.tmx Ch2TileChanges --json-out src/data/map/change/Ch2TileChanges.json \
      --apply-data-map-change src/data/map/data_map_change.s

The expected Tiled convention matches common FE map-pack exports: the visible
layer is the base map, and each hidden layer is one tile change with integer
properties named ID, X, Y, Width, and Height. Layer data may be XML, CSV, or
base64 with optional zlib/gzip compression, matching scripts/tmx_to_map.py.
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tmx_to_map


def property_dict(layer):
    return {
        prop.get("name"): prop.get("value", "")
        for prop in layer.findall("./properties/property")
    }


def require_int(props, key, layer_name, path):
    if key not in props:
        sys.exit(f"error: {path}: layer \"{layer_name}\" is missing property {key}")
    try:
        return int(props[key], 0)
    except ValueError:
        sys.exit(f"error: {path}: layer \"{layer_name}\" property {key}={props[key]!r} is not an integer")


def map_values_from_gids(gids, tilesets, path):
    values = []
    for gid in gids:
        value = tmx_to_map.resolve_local_index(gid, tilesets, path) * 4
        if value > 0xFFFF:
            sys.exit(f"error: {path}: tile value {value} overflows 16 bits (gid {gid})")
        values.append(value)
    return values


def extract_changes(path, symbol):
    root = ET.parse(path).getroot()
    if root.tag != "map":
        sys.exit(f"error: {path}: root element is <{root.tag}>, not <map>")

    width = int(root.get("width"))
    height = int(root.get("height"))
    tilesets = tmx_to_map.parse_tilesets(root)
    changes = []
    arrays = []

    for layer in root.findall("layer"):
        if layer.get("visible") != "0":
            continue

        name = layer.get("name", "?")
        props = property_dict(layer)
        change_id = require_int(props, "ID", name, path)
        x = require_int(props, "X", name, path)
        y = require_int(props, "Y", name, path)
        w = require_int(props, "Width", name, path)
        h = require_int(props, "Height", name, path)

        if w <= 0 or h <= 0:
            sys.exit(f"error: {path}: layer \"{name}\" has non-positive size {w}x{h}")
        if x < 0 or y < 0 or x + w > width or y + h > height:
            sys.exit(f"error: {path}: layer \"{name}\" rectangle {x},{y},{w},{h} is outside {width}x{height}")

        gids = tmx_to_map.decode_layer_gids(layer, path)
        if len(gids) != width * height:
            sys.exit(f"error: {path}: layer \"{name}\" has {len(gids)} tiles, expected {width * height}")

        values = map_values_from_gids(gids, tilesets, path)
        cropped = []
        for row in range(h):
            start = (y + row) * width + x
            cropped.extend(values[start:start + w])

        label = f"{symbol}_change_{change_id}"
        changes.append({
            "id": change_id,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "tiles": label,
        })
        arrays.append((change_id, label, cropped, name))

    changes.sort(key=lambda change: change["id"])
    arrays.sort(key=lambda item: item[0])

    expected_ids = list(range(len(changes)))
    ids = [change["id"] for change in changes]
    if ids != expected_ids:
        sys.exit(f"error: {path}: hidden layer IDs are {ids}, expected contiguous IDs {expected_ids}")

    return {"name": symbol, "changes": changes}, arrays


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def format_short_lines(values):
    lines = []
    for i in range(0, len(values), 8):
        chunk = values[i:i + 8]
        lines.append("\t.short " + ", ".join(f"0x{value:04X}" for value in chunk))
    return lines


def format_arrays(arrays):
    out = []
    for _change_id, label, values, layer_name in arrays:
        out.append(f"\t.global {label}")
        out.append(f"{label}: @ {layer_name}")
        out.extend(format_short_lines(values))
        out.append("")
    return "\n".join(out).rstrip() + "\n\n"


def write_asm(path, arrays):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(format_arrays(arrays))


def apply_data_map_change(path, symbol, arrays):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    table_anchor = f"\t.align 2, 0\n\t.global {symbol}\n{symbol}:"
    table_pos = text.find(table_anchor)
    if table_pos < 0:
        sys.exit(f"error: {path}: could not find map-change table anchor for {symbol}")

    array_anchor = f"\t.global {symbol}_change_0\n"
    start = text.rfind(array_anchor, 0, table_pos)
    if start < 0:
        start = table_pos

    replacement = format_arrays(arrays)
    new_text = text[:start] + replacement + text[table_pos:]

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_text)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tmx")
    parser.add_argument("symbol")
    parser.add_argument("--json-out")
    parser.add_argument("--asm-out")
    parser.add_argument("--apply-data-map-change")
    args = parser.parse_args(argv[1:])

    data, arrays = extract_changes(args.tmx, args.symbol)

    if args.json_out:
        write_json(args.json_out, data)
    if args.asm_out:
        write_asm(args.asm_out, arrays)
    if args.apply_data_map_change:
        apply_data_map_change(args.apply_data_map_change, args.symbol, arrays)
    if not (args.json_out or args.asm_out or args.apply_data_map_change):
        json.dump(data, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv)
