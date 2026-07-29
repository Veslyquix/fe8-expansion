"""Byte-exact, host-only Python mirror of tools/gba-playtest/backend.c's
hash_region()/read_pixel(): the same FNV-1a 64-bit construction
restricted to a rectangular sub-region of a 240x160 RGB24 framebuffer,
and the same 24-bit canonical R,G,B single-pixel extraction, that
gba_playtest.py's scenario schema exposes as `regions`/`pixel_probes`
(issue #18 sprint 5 WHAT #5 visible-pseudo-locale-marker proof).

This mirror exists purely so host-side stdlib `unittest` coverage can
prove properties of the region-hash/pixel-read algorithms themselves (see
test_region_pixel_schema.py) without requiring libmGBA or a built ROM. It
is never imported by gba_playtest.py's own capture/verify pipeline or any
check that asserts against a real ROM -- the single source of truth for
what a check actually asserts against a ROM remains the compiled
backend.c.
"""

from __future__ import annotations

from typing import Sequence

GBA_SCREEN_WIDTH = 240
GBA_SCREEN_HEIGHT = 160

# Standard FNV-1a 64-bit offset basis / prime, matching backend.c's
# hash_framebuffer()/hash_region() literals exactly
# (UINT64_C(14695981039346656037) / UINT64_C(1099511628211)).
_FNV_OFFSET_BASIS = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3
_MASK64 = 0xFFFFFFFFFFFFFFFF


def _validate_framebuffer(framebuffer: Sequence[int]) -> None:
    if len(framebuffer) != GBA_SCREEN_WIDTH * GBA_SCREEN_HEIGHT:
        raise ValueError(
            f"framebuffer must contain exactly {GBA_SCREEN_WIDTH * GBA_SCREEN_HEIGHT} "
            f"32-bit pixels, got {len(framebuffer)}"
        )


def compute_region_hash(
    framebuffer: Sequence[int], x: int, y: int, width: int, height: int
) -> str:
    """Returns the same 'fnv1a64-region:...' text gba_playtest.py's
    capture pipeline would report for the [x, x+width) x [y, y+height)
    sub-rectangle of `framebuffer` (row-major list/tuple of
    GBA_SCREEN_WIDTH*GBA_SCREEN_HEIGHT 32-bit host color_t values, byte0=R
    byte1=G byte2=B byte3=ignored padding/alpha), exactly mirroring
    backend.c's hash_region()."""
    _validate_framebuffer(framebuffer)
    if width < 1 or height < 1 or x < 0 or y < 0:
        raise ValueError("region x/y/width/height must be positive")
    if x + width > GBA_SCREEN_WIDTH or y + height > GBA_SCREEN_HEIGHT:
        raise ValueError("region exceeds framebuffer bounds")
    hash_value = _FNV_OFFSET_BASIS
    for row in range(height):
        line_offset = (y + row) * GBA_SCREEN_WIDTH + x
        for col in range(width):
            pixel = framebuffer[line_offset + col]
            for shift in (0, 8, 16):
                hash_value ^= (pixel >> shift) & 0xFF
                hash_value = (hash_value * _FNV_PRIME) & _MASK64
    return f"fnv1a64-region:{hash_value:016x}"


def read_pixel_rgb(framebuffer: Sequence[int], x: int, y: int) -> str:
    """Returns the same '0xrrggbb' text gba_playtest.py's capture pipeline
    would report for pixel (x, y) of `framebuffer`, exactly mirroring
    backend.c's read_pixel(): the source color_t's R/G/B bytes (bit
    positions 0/8/16, host endianness/alpha/padding-independent, same
    extraction as hash_region()) re-packed into a conventional 0xRRGGBB
    integer so the printed hex reads left-to-right as R, then G, then B."""
    _validate_framebuffer(framebuffer)
    if not (0 <= x < GBA_SCREEN_WIDTH) or not (0 <= y < GBA_SCREEN_HEIGHT):
        raise ValueError("pixel coordinate out of framebuffer bounds")
    pixel = framebuffer[y * GBA_SCREEN_WIDTH + x]
    r = pixel & 0xFF
    g = (pixel >> 8) & 0xFF
    b = (pixel >> 16) & 0xFF
    return f"0x{(r << 16) | (g << 8) | b:06x}"


def compute_whole_frame_hash(framebuffer: Sequence[int]) -> str:
    """Returns the same 'fnv1a64-rgb24:...' text gba_playtest.py's
    capture pipeline would report for the whole framebuffer, exactly
    mirroring backend.c's hash_framebuffer() -- provided here purely so
    tests can cross-check that a region hash is NOT simply a re-encoding
    of the whole-frame hash (a distinct, independently meaningful
    quantity)."""
    return compute_region_hash(framebuffer, 0, 0, GBA_SCREEN_WIDTH, GBA_SCREEN_HEIGHT).replace(
        "fnv1a64-region:", "fnv1a64-rgb24:"
    )
