#!/usr/bin/env python3
"""Convert a standard 128x112 FEBuilder portrait sheet into this repo's
portrait_<Name>_{tileset,chibi,mouth}.png + _palette.agbpal source files,
and print the FaceData xMouth/yMouth/xEye/yEye tile-offset fields for
src/portrait_data.c.

Counterpart to dump_portrait.py (which goes ROM -> source assets); this
goes a standard portrait sheet -> source assets.

Tileset/chibi/mouth region mapping cross-validated two ways: against
SRR_FEGBA's portraits2dmp.py cut_image() coordinates, and independently
against this repo's own src/face.c (PutFace80x72_ExtraFrames' blink tile
offsets, FaceMouth_Loop's Register2dChrMove offsets) -- both agree
exactly.

xMouth/yMouth/xEye/yEye auto-detection ported from portraits2dmp.py's
cv_locate_eye_mouse_pos(): the source template's rows80-96,cols96-128
strip holds a small reference crop of the mouth's linework, and
rows48-64,cols96-128 holds one for the eyes (both also reused elsewhere
in the template as blink/mouth frame source material). Since a
portrait's eyes/mouth land at a different spot within the main face art
depending on the character, this searches an 8x8 grid of tile offsets
within the face region for the window that best matches each reference
crop -- the vanilla portraits' own xMouth/yMouth/xEye/yEye values were
plainly derived the same way (fixed template-relative offsets do not
work: different art, different mouth/eye position). Reusing another
character's calibrated offsets for new art is exactly the bug this
detection avoids.

Usage: insert_portrait.py <source.png> <Name>
Writes into graphics/portrait/ (relative to cwd, i.e. run from repo root).
"""
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

OUT_DIR = Path("graphics/portrait")
SEARCH_RANGE = range(0, 8)


def load_indexed(path):
    im = Image.open(path).convert("RGB")
    arr = np.array(im)  # (112, 128, 3)
    h, w, _ = arr.shape
    assert (h, w) == (112, 128), f"{path}: expected 128x112, got {w}x{h}"

    flat = arr.reshape(-1, 3)
    colors, inverse = np.unique(flat, axis=0, return_inverse=True)
    if len(colors) > 16:
        raise SystemExit(f"{path}: {len(colors)} unique colours, expected <=16")

    idx = inverse.reshape(h, w).astype(np.uint8)

    bg_color = tuple(arr[0, 0])
    bg_idx = next(i for i, c in enumerate(colors) if tuple(c) == bg_color)
    if bg_idx != 0:
        idx0_mask = idx == 0
        idxbg_mask = idx == bg_idx
        idx[idx0_mask] = bg_idx
        idx[idxbg_mask] = 0
        colors = colors.copy()
        colors[[0, bg_idx]] = colors[[bg_idx, 0]]

    pal = [tuple(int(v) for v in c) for c in colors]
    pal += [(0, 0, 0)] * (16 - len(pal))
    return idx, pal


def cut(idx):
    tileset = np.zeros((32, 256), dtype=np.uint8)
    tileset[0:32, 0:64] = idx[0:32, 16:80]      # hair
    tileset[0:32, 64:128] = idx[32:64, 16:80]   # face
    tileset[0:16, 128:160] = idx[64:80, 16:48]  # shoulders1
    tileset[16:32, 128:160] = idx[64:80, 48:80]  # shoulders2
    tileset[0:32, 160:176] = idx[48:80, 0:16]   # shoulders3
    tileset[0:32, 176:192] = idx[48:80, 80:96]  # shoulders4
    tileset[0:16, 192:224] = idx[48:64, 96:128]  # half-close blink
    tileset[16:32, 192:224] = idx[64:80, 96:128]  # full-close blink

    chibi = idx[16:48, 96:128].copy()

    mouth = np.zeros((96, 32), dtype=np.uint8)
    blocks = [
        (0, 80, 0), (32, 80, 16), (64, 80, 32),   # smile frames 1-3 (idle=3)
        (0, 96, 48), (32, 96, 64), (64, 96, 80),  # neutral frames 1-3 (idle=3)
    ]
    for src_x, src_y, dst_y in blocks:
        mouth[dst_y:dst_y + 8, 0:32] = idx[src_y:src_y + 8, src_x:src_x + 32]
        mouth[dst_y + 8:dst_y + 16, 0:32] = idx[src_y + 8:src_y + 16, src_x:src_x + 32]

    return tileset, chibi, mouth


def locate_eye_mouth(idx):
    idx16 = idx.astype(np.int16)
    eye_ref = idx16[48:64, 96:128]
    mouth_ref = idx16[80:96, 96:128]
    face = idx16[0:80, 0:96]

    best_eye, best_eye_diff = (0, 0), None
    best_mouth, best_mouth_diff = (0, 0), None
    for i in SEARCH_RANGE:
        for j in SEARCH_RANGE:
            window = face[8 * i:8 * i + 16, 8 * j:8 * j + 32]
            if window.shape != (16, 32):
                continue
            eye_diff = int(np.sum(np.sign(np.abs(window - eye_ref))))
            mouth_diff = int(np.sum(np.sign(np.abs(window - mouth_ref))))
            if best_eye_diff is None or eye_diff < best_eye_diff:
                best_eye, best_eye_diff = (j, i), eye_diff
            if best_mouth_diff is None or mouth_diff < best_mouth_diff:
                best_mouth, best_mouth_diff = (j, i), mouth_diff

    x_mouth, y_mouth = best_mouth
    x_eye, y_eye = best_eye
    return x_mouth, y_mouth, x_eye, y_eye


def save_indexed_png(arr, pal, path):
    im = Image.fromarray(arr, mode="P")
    flat_pal = []
    for r, g, b in pal:
        flat_pal += [r, g, b]
    im.putpalette(flat_pal)
    im.save(path)


def save_agbpal(pal, path):
    data = bytearray()
    for r, g, b in pal:
        v = (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
        data += struct.pack("<H", v)
    Path(path).write_bytes(bytes(data))


def main(argv):
    if len(argv) != 3:
        raise SystemExit(f"usage: {argv[0]} <source.png> <Name>")
    src, name = Path(argv[1]), argv[2]

    idx, pal = load_indexed(src)
    tileset, chibi, mouth = cut(idx)
    x_mouth, y_mouth, x_eye, y_eye = locate_eye_mouth(idx)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    save_indexed_png(tileset, pal, OUT_DIR / f"portrait_{name}_tileset.png")
    save_indexed_png(chibi, pal, OUT_DIR / f"portrait_{name}_chibi.png")
    save_indexed_png(mouth, pal, OUT_DIR / f"portrait_{name}_mouth.png")
    save_agbpal(pal, OUT_DIR / f"portrait_{name}_palette.agbpal")
    print(f"wrote portrait_{name}_{{tileset,chibi,mouth}}.png + _palette.agbpal")
    print(f"FaceData offsets: xMouth={x_mouth}, yMouth={y_mouth}, xEye={x_eye}, yEye={y_eye}")


if __name__ == "__main__":
    main(sys.argv)
