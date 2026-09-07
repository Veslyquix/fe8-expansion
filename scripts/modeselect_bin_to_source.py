#!/usr/bin/env python3
"""One-off converter: FE7 Mode Select's dumped Img_*.bin/Pal_*.bin assets
(from the installer's `data/` folder) into editable indexed PNG sources
under graphics/modeselect/.

Every Img_*.bin is already GBA-LZ77-compressed 4bpp tile data (confirmed by
its 0x10 header byte) -- exactly this repo's own `.4bpp.lz` format. Every
Pal_*.bin is a raw BGR555 palette. This script:
  1. decompresses each Img_*.bin with gbagfx (-> raw .4bpp)
  2. combines it with its paired Pal_*.bin via gbagfx (-> indexed .png)
  3. round-trips the PNG back through gbagfx (.png -> .4bpp) and asserts the
     raw tile bytes match exactly, so the checked-in PNG is provably a
     faithful, losslessly-editable source for the original asset.

This is a one-shot migration tool (like insert_portrait.py/
insert_map_sprite.py), not a permanent build step: once the PNGs are
checked in, the existing generic `%.4bpp: %.png` / `%.gbapal: %.png` /
`%.lz: %` Makefile rules regenerate the compiled `.4bpp.lz`/`.gbapal` on
every build and `make clean_fast`, with no further Makefile changes.

Usage:
    python3 scripts/modeselect_bin_to_source.py <src_data_dir>
"""
import struct
import subprocess
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
GBAGFX = REPO / "tools" / "gbagfx" / "gbagfx"
OUT_DIR = REPO / "graphics" / "modeselect"

# (output name, Img_*.bin, Pal_*.bin)
PAIRS = [
    ("ModeSelectBg0", "Img_08418E44.bin", "Pal_0840F9A0.bin"),
    ("ModeSelectBg3", "Img_0840FEB4.bin", "Pal_084138F0.bin"),
    ("ModeSelectClawMenu", "Img_08415594.bin", "Pal_08415AA0.bin"),
    ("ModeSelectObjFrame", "Img_08414940.bin", "Pal_0841625C.bin"),
    # 12 chapter-range OBJ quadrant icons, 4 per lord, all sharing Pal_084150C0.
    ("ModeSelectChapter0TopLeft", "Img_08415BE8.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter0BottomLeft", "Img_08415CB0.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter0TopRight", "Img_08415DC4.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter0BottomRight", "Img_08415E04.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter1TopLeft", "Img_08415E54.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter1BottomLeft", "Img_08415F14.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter1TopRight", "Img_08415FF0.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter1BottomRight", "Img_0841601C.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter2TopLeft", "Img_08416058.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter2BottomLeft", "Img_08416118.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter2TopRight", "Img_084161F4.bin", "Pal_084150C0.bin"),
    ("ModeSelectChapter2BottomRight", "Img_08416220.bin", "Pal_084150C0.bin"),
]

# Pal_*.bin files with more than 16 colours (one row): the tile data only
# ever references indices 0-15 relative to whichever row is active at
# runtime, so the PNG's own embedded palette (first row only, see
# convert_one) can't carry the full bank. These get a full JASC-PAL sibling
# written alongside the PNG, and the compiled .gbapal used at runtime comes
# from THAT (via the existing `%.gbapal: %.pal` rule), not from the PNG --
# Makefile picks whichever source file (.pal or .png) is actually present
# for a given %.gbapal target name.
MULTIROW_PALETTES = {
    "ModeSelectBg0": "Pal_0840F9A0.bin",
    "ModeSelectBg3": "Pal_084138F0.bin",
}

# Pal_084150C0.bin (128 colours) is loaded once at runtime
# (ApplyPalette(Pal_084150C0, 0x1B)) and shared by all 12 chapter-range
# icon images -- it isn't "each icon's own palette", so it gets exactly
# one standalone .pal asset, not a per-icon one.
SHARED_PALETTES = {
    "ModeSelectChapterPal": "Pal_084150C0.bin",
}


def write_jasc_pal(raw_bgr555: bytes, out_pal: pathlib.Path):
    colours = len(raw_bgr555) // 2
    lines = ["JASC-PAL", "0100", str(colours)]
    for i in range(colours):
        (value,) = struct.unpack_from("<H", raw_bgr555, i * 2)
        r5, g5, b5 = value & 0x1F, (value >> 5) & 0x1F, (value >> 10) & 0x1F
        lines.append(" ".join(str(round(v * 255 / 31)) for v in (r5, g5, b5)))
    # tools/pal2gbapal requires CRLF, matching every committed graphics/*.pal.
    out_pal.write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii"))


def run(*args):
    subprocess.run([str(a) for a in args], check=True, capture_output=True)


def convert_one(src_dir: pathlib.Path, name: str, img_bin: str, pal_bin: str, tmp: pathlib.Path):
    img_lz = tmp / f"{name}.4bpp.lz"
    img_lz.write_bytes((src_dir / img_bin).read_bytes())

    # gbagfx's -palette wants exactly 16 colours (32 bytes) for a 4bpp
    # image; several source palettes are multi-row banks (the tile data's
    # own OAM/BG attribute selects which row applies at runtime), so use
    # just the first row for this PNG's own embedded preview palette --
    # this only affects how the checked-in PNG looks in an editor, not the
    # actual .4bpp tile bytes the ROM uses.
    pal_path = tmp / f"{name}.gbapal"
    pal_path.write_bytes((src_dir / pal_bin).read_bytes()[:32])

    raw_4bpp = tmp / f"{name}.4bpp"
    run(GBAGFX, img_lz, raw_4bpp)

    out_png = OUT_DIR / f"{name}.png"
    run(GBAGFX, raw_4bpp, out_png, "-palette", pal_path)

    # Round-trip verification: PNG -> .4bpp must reproduce the exact same
    # raw tile bytes we decompressed from the original .bin.
    check_4bpp = tmp / f"{name}.check.4bpp"
    run(GBAGFX, out_png, check_4bpp)
    original = raw_4bpp.read_bytes()
    roundtrip = check_4bpp.read_bytes()
    if original != roundtrip:
        raise SystemExit(f"{name}: PNG round-trip mismatch ({len(original)} vs {len(roundtrip)} bytes)")

    note = ""
    if name in MULTIROW_PALETTES:
        full_pal = (src_dir / MULTIROW_PALETTES[name]).read_bytes()
        write_jasc_pal(full_pal, OUT_DIR / f"{name}.pal")
        note = f" (+ {len(full_pal) // 2}-colour {name}.pal for the compiled .gbapal)"

    print(f"ok: {name}.png ({len(original)} bytes of 4bpp tile data, verified){note}")


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 1

    src_dir = pathlib.Path(argv[0])
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)
        for name, img_bin, pal_bin in PAIRS:
            convert_one(src_dir, name, img_bin, pal_bin, tmp)

    for name, pal_bin in SHARED_PALETTES.items():
        full_pal = (src_dir / pal_bin).read_bytes()
        write_jasc_pal(full_pal, OUT_DIR / f"{name}.pal")
        print(f"ok: {name}.pal ({len(full_pal) // 2}-colour shared palette)")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
