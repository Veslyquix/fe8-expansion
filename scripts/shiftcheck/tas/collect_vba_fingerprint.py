#!/usr/bin/env python3
"""Collect VBA-rr GD checkpoints into deterministic JSON."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys


def checkpoint_frames(expected_frames, checkpoint_count):
    if expected_frames <= 0:
        raise ValueError("expected frame count must be positive")
    if checkpoint_count <= 0:
        raise ValueError("checkpoint count must be positive")
    frames = {
        max(1, min(expected_frames, (index * expected_frames) // checkpoint_count))
        for index in range(1, checkpoint_count + 1)
    }
    frames.add(expected_frames)
    return sorted(frames)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rom_identity(path):
    data = path.read_bytes()
    if len(data) < 0xB0:
        raise ValueError(f"{path}: ROM is too small")
    return {
        "path": str(path),
        "sha1": hashlib.sha1(data).hexdigest(),
        "size": len(data),
        "title": data[0xA0:0xAC].rstrip(b"\0").decode("ascii", "replace"),
        "game_code": data[0xAC:0xB0].decode("ascii", "replace"),
    }


def collect(out_dir, tag, expected_frames, checkpoint_count, rom):
    expected = checkpoint_frames(expected_frames, checkpoint_count)
    manifest_path = out_dir / f"{tag}_manifest.txt"
    done_path = out_dir / f"{tag}_done.txt"

    try:
        manifest = [int(line) for line in manifest_path.read_text().split()]
        done_text = done_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ValueError(str(error)) from error

    match = re.fullmatch(r"reached=(\d+) expected=(\d+)", done_text)
    if match is None:
        raise ValueError(f"{done_path}: malformed done marker {done_text!r}")
    reached, reported_expected = (int(value) for value in match.groups())
    if reported_expected != expected_frames:
        raise ValueError(
            f"{done_path}: expected {reported_expected}, requested {expected_frames}"
        )

    checkpoints = []
    for frame in manifest:
        path = out_dir / f"{tag}_{frame:07d}.gd"
        if not path.is_file():
            raise ValueError(f"missing checkpoint: {path}")
        checkpoints.append(
            {
                "frame": frame,
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
                "path": str(path),
            }
        )

    return {
        "schema_version": 1,
        "tag": tag,
        "fingerprint_format": "vba-gd-v1",
        "rom": _rom_identity(rom),
        "expected_frames": expected_frames,
        "emulation_frames": reached,
        "checkpoint_frames": expected,
        "checkpoints": checkpoints,
        "complete": reached == expected_frames and manifest == expected,
    }


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--expected-frames", required=True, type=int)
    parser.add_argument("--checkpoint-count", required=True, type=int)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        result = collect(
            args.out_dir,
            args.tag,
            args.expected_frames,
            args.checkpoint_count,
            args.rom,
        )
        _write_json(args.output, result)
    except (OSError, ValueError) as error:
        print(f"collect_vba_fingerprint: error: {error}", file=sys.stderr)
        return 2

    print(
        "collect_vba_fingerprint: "
        f"captured={result['emulation_frames']} "
        f"expected={result['expected_frames']} "
        f"complete={result['complete']} -> {args.output}"
    )
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
