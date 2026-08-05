#!/usr/bin/env python3
"""Apply reproducible frame/input edits to a GBAHawk GBMV movie.

Patch operations are applied in order, and frame numbers refer to the movie
state produced by all preceding operations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path


KEYS = ("UP", "DOWN", "LEFT", "RIGHT", "START", "SELECT", "B", "A", "L", "R", "POWER")
KEY_INDEX = {key: index for index, key in enumerate(KEYS)}


class RetimeError(Exception):
    pass


def parse_keys(value: object, path: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RetimeError(f"{path} must be an array")
    keys: list[str] = []
    for index, key in enumerate(value):
        if not isinstance(key, str) or key not in KEY_INDEX:
            raise RetimeError(f"{path}[{index}] must be one of {', '.join(KEYS)}")
        if key in keys:
            raise RetimeError(f"{path} contains duplicate key {key!r}")
        keys.append(key)
    return tuple(keys)


def parse_positive_int(value: object, path: str, *, allow_zero: bool = True) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RetimeError(f"{path} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise RetimeError(f"{path} must be >= {minimum}")
    return value


def row_with_keys(keys: tuple[str, ...]) -> list[str]:
    row = ["."] * len(KEYS)
    for key in keys:
        row[KEY_INDEX[key]] = {
            "UP": "U",
            "DOWN": "D",
            "LEFT": "L",
            "RIGHT": "R",
            "START": "S",
            "SELECT": "s",
            "B": "B",
            "A": "A",
            "L": "l",
            "R": "r",
            "POWER": "P",
        }[key]
    return row


def require_frame(rows: list[list[str]], frame: int, path: str) -> None:
    if frame >= len(rows):
        raise RetimeError(f"{path} frame {frame} is outside movie length {len(rows)}")


def apply_patch(rows: list[list[str]], patch: dict[str, object]) -> None:
    if patch.get("schema_version") != 1:
        raise RetimeError("patch.schema_version must be 1")
    operations = patch.get("operations")
    if not isinstance(operations, list):
        raise RetimeError("patch.operations must be an array")

    for index, raw_operation in enumerate(operations):
        path = f"patch.operations[{index}]"
        if not isinstance(raw_operation, dict):
            raise RetimeError(f"{path} must be an object")
        operation = raw_operation.get("op")
        if operation not in {"set", "add", "remove", "insert", "delete", "move"}:
            raise RetimeError(f"{path}.op is unsupported: {operation!r}")

        if operation == "move":
            source = parse_positive_int(raw_operation.get("from"), f"{path}.from")
            target = parse_positive_int(raw_operation.get("to"), f"{path}.to")
            keys = parse_keys(raw_operation.get("keys"), f"{path}.keys")
            require_frame(rows, source, f"{path}.from")
            require_frame(rows, target, f"{path}.to")
            for key in keys:
                key_index = KEY_INDEX[key]
                rows[target][key_index] = rows[source][key_index]
                rows[source][key_index] = "."
            continue

        frame = parse_positive_int(raw_operation.get("frame"), f"{path}.frame")
        if operation == "insert":
            if frame > len(rows):
                raise RetimeError(f"{path}.frame {frame} is outside insertion range 0..{len(rows)}")
            count = parse_positive_int(raw_operation.get("count"), f"{path}.count", allow_zero=False)
            keys = parse_keys(raw_operation.get("keys", []), f"{path}.keys")
            rows[frame:frame] = [row_with_keys(keys) for _ in range(count)]
            continue
        if operation == "delete":
            require_frame(rows, frame, f"{path}.frame")
            count = parse_positive_int(raw_operation.get("count"), f"{path}.count", allow_zero=False)
            if frame + count > len(rows):
                raise RetimeError(f"{path} deletes past movie length {len(rows)}")
            del rows[frame:frame + count]
            continue

        require_frame(rows, frame, f"{path}.frame")
        keys = parse_keys(raw_operation.get("keys"), f"{path}.keys")
        if operation == "set":
            rows[frame] = row_with_keys(keys)
        else:
            for key in keys:
                key_index = KEY_INDEX[key]
                rows[frame][key_index] = row_with_keys((key,))[key_index] if operation == "add" else "."


def retime(movie: Path, rom: Path, patch_path: Path, output: Path) -> None:
    try:
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RetimeError(f"cannot read patch {patch_path}: {error}") from error
    if not isinstance(patch, dict):
        raise RetimeError("patch root must be an object")

    try:
        rom_sha1 = hashlib.sha1(rom.read_bytes()).hexdigest().upper()
    except OSError as error:
        raise RetimeError(f"cannot read ROM {rom}: {error}") from error

    with zipfile.ZipFile(movie) as source:
        infos = source.infolist()
        items = {info.filename: source.read(info.filename) for info in infos}

    input_name = next((name for name in items if name.lower() == "input log.txt"), None)
    header_name = next((name for name in items if name.lower() == "header.txt"), None)
    if input_name is None or header_name is None:
        raise RetimeError("movie must contain Header.txt and Input Log.txt")

    lines = items[input_name].decode("utf-8").splitlines()
    frame_indices = [
        index for index, line in enumerate(lines)
        if line.startswith("|") and line.endswith("|") and len(line[1:-1]) == len(KEYS)
    ]
    rows = [list(lines[index][1:-1]) for index in frame_indices]
    if not rows:
        raise RetimeError("Input Log.txt contains no frame rows")

    apply_patch(rows, patch)
    prefix = lines[:frame_indices[0]]
    suffix = lines[frame_indices[-1] + 1:]
    items[input_name] = (
        "\n".join(prefix + ["|" + "".join(row) + "|" for row in rows] + suffix) + "\n"
    ).encode("utf-8")

    header_lines = items[header_name].decode("utf-8").splitlines()
    items[header_name] = (
        "\n".join(
            "SHA1 " + rom_sha1 if line.startswith("SHA1 ") else line
            for line in header_lines
        ) + "\n"
    ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as destination:
        for info in infos:
            destination.writestr(info, items[info.filename])

    print(f"wrote {output}: frames={len(rows)} SHA1={rom_sha1}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("movie", type=Path)
    parser.add_argument("rom", type=Path)
    parser.add_argument("patch", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        retime(args.movie, args.rom, args.patch, args.output)
    except (RetimeError, OSError, zipfile.BadZipFile, UnicodeError) as error:
        print(f"retime_gbahawk_movie: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
