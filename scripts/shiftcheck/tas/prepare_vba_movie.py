#!/usr/bin/env python3
"""Append one guard input frame to a VBM without changing replayed inputs.

VBA-rr svn421 can crash during teardown when Lua calls ``os.exit`` on the exact
movie-end frame. The TAS runner stops at the original frame count, so appending a
duplicate final input keeps the movie active during the clean scripted exit.
"""

import argparse
from pathlib import Path
import sys


def add_guard_frame(data):
    if len(data) < 0x100 or data[:4] != b"VBM\x1a":
        raise ValueError("not a VBM v1 movie")
    if int.from_bytes(data[4:8], "little") != 1:
        raise ValueError("unsupported VBM version")

    frame_count = int.from_bytes(data[12:16], "little")
    controller_flags = data[0x15] & 0x0F
    controller_count = controller_flags.bit_count()
    input_offset = int.from_bytes(data[0x3C:0x40], "little")
    if frame_count <= 0 or controller_count <= 0:
        raise ValueError("VBM has no input frames or controllers")

    bytes_per_frame = controller_count * 2
    input_end = input_offset + frame_count * bytes_per_frame
    if input_end > len(data):
        raise ValueError("VBM input stream is truncated")

    guarded = bytearray(data)
    guarded[12:16] = (frame_count + 1).to_bytes(4, "little")
    guarded[input_end:input_end] = data[input_end - bytes_per_frame : input_end]
    return bytes(guarded), frame_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    try:
        guarded, original_frames = add_guard_frame(args.input.read_bytes())
        args.output.write_bytes(guarded)
    except (OSError, ValueError) as error:
        print(f"prepare_vba_movie: error: {error}", file=sys.stderr)
        return 2

    print(
        f"prepare_vba_movie: {original_frames} -> {original_frames + 1} frames "
        f"(guarded copy: {args.output})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
