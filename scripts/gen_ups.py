#!/bin/python3
"""Create a UPS patch (source -> target) using the standard UPS1 format.

Usage: gen_ups.py <source.gba> <target.gba> <out.ups>

Mismatch detection is vectorized with numpy (source vs. target are ~16-32MB,
byte-by-byte comparison in pure Python is too slow); the actual variable-length
record encoding still has to happen serially per the UPS spec, but only over
the (much smaller) set of differing runs rather than every byte.
"""
import struct
import sys
import zlib

import numpy as np


def write_number(n):
    """UPS's specific 7-bit VLV encoding (note the `n -= 1` after each
    non-final byte -- this is NOT plain LEB128)."""
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def create_patch(src: bytes, dst: bytes) -> bytes:
    src_len, dst_len = len(src), len(dst)
    max_len = max(src_len, dst_len)

    src_arr = np.frombuffer(src, dtype=np.uint8)
    dst_arr = np.frombuffer(dst, dtype=np.uint8)

    if src_len < max_len:
        src_arr = np.pad(src_arr, (0, max_len - src_len))
    if dst_len < max_len:
        dst_arr = np.pad(dst_arr, (0, max_len - dst_len))

    xor = src_arr ^ dst_arr
    diff_positions = np.flatnonzero(xor)

    patch = bytearray()
    patch += b"UPS1"
    patch += write_number(src_len)
    patch += write_number(dst_len)

    last_pos = 0
    i = 0
    n = len(diff_positions)
    while i < n:
        pos = int(diff_positions[i])
        patch += write_number(pos - last_pos)

        # Extend the run while positions are contiguous (a "run" ends at
        # the first matching byte, i.e. the first gap in diff_positions).
        j = i
        while j + 1 < n and diff_positions[j + 1] == diff_positions[j] + 1:
            j += 1

        run = xor[pos : int(diff_positions[j]) + 1]
        patch += run.tobytes()
        patch.append(0)  # terminator (a real matching byte follows)

        last_pos = int(diff_positions[j]) + 1
        i = j + 1

    patch += struct.pack("<I", zlib.crc32(src) & 0xFFFFFFFF)
    patch += struct.pack("<I", zlib.crc32(dst) & 0xFFFFFFFF)
    patch += struct.pack("<I", zlib.crc32(patch) & 0xFFFFFFFF)

    return bytes(patch)


def main():
    if len(sys.argv) != 4:
        sys.exit(f"usage: {sys.argv[0]} <source.gba> <target.gba> <out.ups>")

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
