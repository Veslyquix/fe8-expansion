#!/bin/python3
"""Create an IPS patch (source -> target).

IPS addresses are 3 bytes (max offset 0xFFFFFF), so both the source and the
target must be at most 16MB -- this is the classic IPS ceiling, unlike UPS
(scripts/gen_ups.py) which has no such limit.

Usage: gen_ips.py <source.gba> <target.gba> <out.ips>
"""
import sys

import numpy as np

MAX_OFFSET = 0xFFFFFF  # 3-byte address field
MAX_CHUNK = 0xFFFF      # 2-byte size field (0x0000 is reserved for RLE records)


def write_offset(n: int) -> bytes:
    return n.to_bytes(3, byteorder="big")


def create_patch(src: bytes, dst: bytes) -> bytes:
    if len(dst) > MAX_OFFSET + 1:
        sys.exit(f"error: target is {len(dst)} bytes, exceeds IPS's 16MB (0x1000000) limit")
    if len(src) > MAX_OFFSET + 1:
        sys.exit(f"error: source is {len(src)} bytes, exceeds IPS's 16MB (0x1000000) limit")

    src_len, dst_len = len(src), len(dst)
    max_len = max(src_len, dst_len)

    src_arr = np.frombuffer(src, dtype=np.uint8)
    dst_arr = np.frombuffer(dst, dtype=np.uint8)

    if src_len < max_len:
        src_arr = np.pad(src_arr, (0, max_len - src_len))
    if dst_len < max_len:
        dst_arr = np.pad(dst_arr, (0, max_len - dst_len))

    diff_positions = np.flatnonzero(src_arr != dst_arr)

    patch = bytearray(b"PATCH")

    i = 0
    n = len(diff_positions)
    while i < n:
        start = int(diff_positions[i])
        j = i
        while j + 1 < n and diff_positions[j + 1] == diff_positions[j] + 1:
            j += 1
        end = int(diff_positions[j]) + 1  # exclusive

        pos = start
        while pos < end:
            chunk = dst_arr[pos : min(pos + MAX_CHUNK, end)]
            patch += write_offset(pos)
            patch += len(chunk).to_bytes(2, byteorder="big")
            patch += chunk.tobytes()
            pos += len(chunk)

        i = j + 1

    patch += b"EOF"

    return bytes(patch)


def main():
    if len(sys.argv) != 4:
        sys.exit(f"usage: {sys.argv[0]} <source.gba> <target.gba> <out.ips>")

    src_path, dst_path, out_path = sys.argv[1:4]

    with open(src_path, "rb") as f:
        src = f.read()
    with open(dst_path, "rb") as f:
        dst = f.read()

    patch = create_patch(src, dst)

    with open(out_path, "wb") as f:
        f.write(patch)

    print(f"Wrote {out_path} ({len(patch)} bytes)")


if __name__ == "__main__":
    main()
