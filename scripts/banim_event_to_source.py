"""Compile this repo's checked-in battle-animation sources (banim/src/) into
banim asset sources (FE8_NEW_ANIMS), using the local AAA.py compiler
(tools/aaa/AAA.py) -- entirely within this repo, no Windows/AA.exe/external
directory dependency.

banim/src/<pack>_<weapon>/ holds the real, git-tracked source for one
animation: the FE-Repo pack's frame-command script (<Weapon>.txt) and its
numbered frame PNGs (<Weapon>_NNN.png). This script runs AAA.py against a
scratch copy of that source (so banim/src/ stays free of build byproducts),
then converts AAA.py's compiled Event-Assembler installer into this repo's
banim/graphics-banim assets.

Why AAA.py and not AA.exe: AA.exe is a Windows-only proprietary binary this
repo cannot build from; its output was also never git-tracked here, so a
`make clean_fast` (whose sweep doesn't know about these battery-animation
files -- see CREDITS.md) once made an entire class's animation unrecoverable
except by re-running AA.exe on the original machine. AAA.py is a pure-Python
reimplementation (see tools/aaa/AAA.py's own header) that runs anywhere this
repo's own Python does, and its checked-in banim/src/ inputs are small text
+ PNGs a normal `git status` would flag if ever deleted.

Key correctness notes learned the hard way:

* AAA.py's `framedata` section is a MIX of literal BYTE runs and POIN2
  pointer references to its own sheet labels (Anim_<Weapon>_Sheet_N, 0-based
  -- unlike AA.exe's 1-based Sheet_N seen in earlier work). The pointers must
  be resolved to real assembler symbols at link time, so this section is
  compiled as an actual object (`_script.o`) with genuine `.word <label>`
  relocations, NOT emitted as a pre-compressed blob.

* The repo's compressing linker (scripts/arm_compressing_linker.py) can only
  take a `.o` input via the `>lz` compression path -- `process_input_object()`
  does nothing at all for a `.o` with no comptype. So the section handed to
  it must be UNCOMPRESSED, exactly like vanilla's assembled `.data.script`
  (see scripts/merge_banim_s.sh + banim_code.inc). AAA.py's own framedata
  bytes are literal/uncompressed already (no LZ77 header) -- unlike AA.exe's,
  which were pre-compressed and had to be decompressed here first.

* AAA.py computes a REAL, distinct OAM table per facing (Anim_<Weapon>_rtl
  and _ltr are genuinely different byte streams -- verified). We deliberately
  DON'T store both: banim/data_banim.o is pinned to a fixed, hard address
  range in linker/expansion.ld (0xC02000-0xEE0000, ~2.86MB -- the next pinned
  region starts right after it), and storing a genuine second OAM table for
  every animation overflowed that budget by ~125KB on the very first attempt.
  Instead we only extract `rtl` and point BOTH struct fields at it, exactly
  like the AA.exe-sourced entries did, relying on the existing "AutoGenLeftOAM"
  runtime mirror (src/banim_autogen_left_oam.c) to derive the left-facing OAM
  at runtime -- already verified in-game for the earlier AA.exe pipeline, so
  this doesn't depend on trusting AAA.py's own `ltr` computation at all.

* `_modes.bin`: every vanilla banim/*_modes.bin is 96B (12 mode offsets + 12
  reserved zero words, per merge_banim_s.sh). AAA.py's sectiondata is the
  same 12-offset table (48B); padded to match.

* `.index` in struct BattleAnimDef is ONE-BASED: GetBattleAnimationId
  (src/banim-ekrcmd.c) returns `idx - 1`. banim_data[] slot == .index - 1.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = REPO / "banim" / "src"
AAA_DIR = REPO / "tools" / "aaa"

PACK_CREDIT = {
    "soldier":  '[Soldier-Custom] FE10-Style [M] by Flasuban',
    "brigand":  '[Brigand-Reskin] Fully-Clothed [M] by Flasuban',
    "fighter":  '[Fighter-Variant] FE9 Repal [M] by Glenwing',
    "knight":   '[Knight-Variant] Generic [M] by SALVAGED',
    "merc":     '[Mercenary-Reskin] Armored SALVAGED Style [M]',
    "archer":   '[Archer-Reskin] FE5-Style [M] by Pushwall',
    "cavalier": '[Cavalier-Variant] [M] Generic by SALVAGED v2',
    "pegasus":  '[Peg T1 Base] [F] Repal v2 + Weapons by Flasuban',
}

# Order here fixes banim_data[] slot assignment; soldier occupies 0xC9..0xCB.
PACK_WEAPONS = [
    ("soldier",  ["Sword", "Lance", "Unarmed"]),
    ("brigand",  ["Axe", "Handaxe", "Unarmed"]),
    ("fighter",  ["Axe", "Handaxe", "Unarmed"]),
    ("knight",   ["Sword", "Lance", "Axe", "Handaxe", "Bow", "Unarmed"]),
    ("merc",     ["Sword", "Unarmed"]),
    ("archer",   ["Bow", "Unarmed"]),
    ("cavalier", ["Sword", "Lance", "Axe", "Handaxe", "Bow", "Unarmed"]),
    ("pegasus",  ["Sword", "Lance", "Axe", "Handaxe", "Magic", "Unarmed"]),
]

FIRST_SLOT = 0xC9  # first free banim_data[] slot after the 201 vanilla entries

# struct BattleAnim::abbr is char[12] -> <= 11 chars.
CLASS_TAG  = {"soldier": "sld", "brigand": "brg", "fighter": "fig", "knight": "knt",
              "merc": "mrc", "archer": "arc", "cavalier": "cav", "pegasus": "peg"}
WEAPON_TAG = {"Sword": "sw", "Lance": "ln", "Axe": "ax", "Handaxe": "hx",
              "Bow": "bw", "Magic": "mg", "Unarmed": "un"}

def compile_with_aaa(pack, weapon, work_dir):
    """Copy the checked-in source + AAA.py into a scratch dir and compile it
    there, so banim/src/ never accumulates build byproducts. Returns
    (installer_text, work_dir) -- the raw framedata sidecar files
    tools/aaa/AAA.py also writes live alongside the source in work_dir."""
    src_dir = SRC_DIR / f"{pack}_{weapon.lower()}"
    if not src_dir.is_dir():
        raise FileNotFoundError(f"no checked-in source at {src_dir}")

    shutil.copytree(src_dir, work_dir)
    shutil.copy(AAA_DIR / "AAA.py", work_dir / "AAA.py")
    shutil.copy(AAA_DIR / "lzss.py", work_dir / "lzss.py")

    result = subprocess.run(
        [sys.executable, "AAA.py", f"{weapon}.txt"],
        cwd=work_dir, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"AAA.py failed for {pack}/{weapon}:\n{result.stdout}\n{result.stderr}")

    installer = work_dir / f"{weapon}Installer.event"
    if not installer.is_file():
        raise RuntimeError(f"AAA.py did not produce {installer.name}")
    return installer.read_text(errors="ignore")


def read_framedata_raw(work_dir, weapon):
    """The raw sidecar tools/aaa/AAA.py writes: frameData bytes exactly as
    computed in memory, and a parallel (byte_offset, sheet_index) list for
    every sheet-pointer word -- see the patch there for why this replaces
    reverse-parsing the .event text's framedata section."""
    raw = (work_dir / f"{weapon}_framedata.raw.bin").read_bytes()
    pointers = {}
    for line in (work_dir / f"{weapon}_framedata.pointers.txt").read_text().splitlines():
        off, sheet = line.split()
        pointers[int(off)] = int(sheet)  # already 0-based
    return raw, pointers


def extract_section_text(text, label):
    idx = text.find(label)
    if idx == -1:
        raise ValueError(f"label {label!r} not found")
    rest = text[idx + len(label):]
    m = re.search(r'\n[A-Za-z_][A-Za-z0-9_]*:', rest)
    return rest[:m.start()] if m else rest


def extract_raw_bytes(text, label):
    section = extract_section_text(text, label)
    return bytes(int(t, 16) for t in re.findall(r'0x[0-9a-fA-F]{1,2}', section))


def count_sheets(text, animname):
    # AAA.py's own sheets are 0-based (Anim_X_Sheet_0, _1, ...).
    n = 0
    while f"Anim_{animname}_Sheet_{n}:" in text:
        n += 1
    return n


def emit_script_asm(raw, pointer_positions, sheet_syms, sym):
    """raw is AAA.py's frameData buffer verbatim (see read_framedata_raw --
    no text round-trip, so no header/padding stripping needed here)."""
    assert len(raw) % 4 == 0, "script must be a whole number of words"
    lines, plain = [], []

    def flush():
        if plain:
            lines.append("\t.word " + ", ".join(plain))
            plain.clear()

    for off in range(0, len(raw), 4):
        if off in pointer_positions:
            flush()
            lines.append(f"\t.word {sheet_syms[pointer_positions[off]]}")
        else:
            plain.append(hex(int.from_bytes(raw[off:off + 4], 'little')))
            if len(plain) == 8:
                flush()
    flush()
    return "\n".join(lines)


def label(path):
    lbl = os.path.basename(path.split("|")[0].split(">")[0]).split(".")
    return lbl[0] if lbl[1] == "4bpp" else lbl[0] + "_" + lbl[1]


def main():
    import argparse
    import tempfile

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma-separated pack names to (re)compile, e.g. soldier,knight")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None

    banim_dir = REPO / "banim"
    gfx_dir = REPO / "graphics" / "banim"
    manifest, pointers, structs, report = [], [], [], []
    slot = FIRST_SLOT

    with tempfile.TemporaryDirectory(prefix="banim_aaa_") as tmp:
        tmp = pathlib.Path(tmp)
        for pack, weapons in PACK_WEAPONS:
            do_pack = only is None or pack in only
            manifest.append(f"# ---- {pack} (FE8_NEW_ANIMS) ----")
            for weapon in weapons:
                sym = f"banim_new{pack}_{weapon.lower()}"

                if do_pack:
                    work_dir = tmp / f"{pack}_{weapon.lower()}"
                    text = compile_with_aaa(pack, weapon, work_dir)
                    animname = weapon

                    modes = extract_raw_bytes(text, f"Anim_{animname}_sectiondata:")
                    assert len(modes) == 48, f"{sym}: expected 48B mode table, got {len(modes)}"
                    modes = modes + b"\x00" * 48  # -> vanilla 96B footprint

                    # Only rtl is stored -- see the module docstring's OAM note.
                    oam_r = extract_raw_bytes(text, f"Anim_{animname}_rtl:")
                    pal = extract_raw_bytes(text, f"Anim_{animname}_pal:")
                    sheets = [extract_raw_bytes(text, f"Anim_{animname}_Sheet_{i}:")
                              for i in range(count_sheets(text, animname))]

                    script, pointer_positions = read_framedata_raw(work_dir, weapon)
                    assert len(script) % 4 == 0, f"{sym}: framedata not word-aligned"

                    sheet_syms = []
                    for i, blob in enumerate(sheets):
                        sheet_syms.append(f"{sym}_sheet_{i}")
                        (gfx_dir / f"{sym}_sheet_{i}.4bpp.lz").write_bytes(blob)
                    for n in set(pointer_positions.values()):
                        assert 0 <= n < len(sheet_syms), f"{sym}: sheet index {n} out of range"

                    (banim_dir / f"{sym}_modes.bin").write_bytes(modes)
                    (banim_dir / f"{sym}_oam.bin.lz").write_bytes(oam_r)
                    (gfx_dir / f"{sym}.agbpal.lz").write_bytes(pal)

                    body = emit_script_asm(script, pointer_positions, sheet_syms, sym)
                    (banim_dir / f"{sym}_script.s").write_text(f"""@ vim:ft=armv4
@ Generated for FE8_NEW_ANIMS ({pack}, {weapon.lower()}) -- FE-Repo pack
@ "{PACK_CREDIT[pack]}" (see CREDITS.md). Compiled from the checked-in source
@ at banim/src/{pack}_{weapon.lower()}/ by tools/aaa/AAA.py and converted by
@ this script. Do not edit by hand; re-run `python3 scripts/banim_event_to_source.py`.
@
@ UNCOMPRESSED on purpose: linker_script_banim.txt applies ">lz" to this
@ section, and the engine LZ77-decompresses it exactly once at runtime.
\t.global {sym}_script
\t.section .data.script
{sym}_script:
{body}
""")
                    report.append((pack, weapon, slot, len(sheets), len(script)))
                else:
                    # Not recompiling this pack; report existing sheet count for the summary.
                    sheet_files = sorted(gfx_dir.glob(f"{sym}_sheet_*.4bpp.lz"))
                    report.append((pack, weapon, slot, len(sheet_files), -1))

                pal_l = f"graphics/banim/{sym}.agbpal.lz"
                oam_l = f"banim/{sym}_oam.bin.lz"
                scr_l = f"banim/{sym}_script.o|.data.script>lz"
                mod_l = f"banim/{sym}_modes.bin"
                n_sheets = report[-1][3]
                manifest += [f"graphics/banim/{sym}_sheet_{i}.4bpp.lz" for i in range(n_sheets)]
                manifest += [pal_l, oam_l, scr_l, mod_l]

                m_s, s_s = label(mod_l), f"{sym}_script_o"
                o_s, p_s = label(oam_l), label(pal_l)
                pointers += [f"extern int {m_s};", f"extern char {s_s};",
                             f"extern char {o_s};", f"extern char {p_s};"]
                abbr = f"new{CLASS_TAG[pack]}{WEAPON_TAG[weapon]}1"
                assert len(abbr) <= 11, abbr
                structs.append(
                    f'    {{"{abbr}", &{m_s}, &{s_s}, &{o_s}, &{o_s}, &{p_s}}}, '
                    f'// 0x{slot:02X} {pack} {weapon.lower()}')
                slot += 1

    (REPO / "_snip_manifest.txt").write_text("\n".join(manifest) + "\n")
    (REPO / "_snip_pointers.h").write_text("\n".join(pointers) + "\n")
    (REPO / "_snip_struct.c").write_text("\n".join(structs) + "\n")

    for pack, weapon, sl, ns, ls in report:
        size_note = f"{ls}B script" if ls >= 0 else "(unchanged)"
        print(f"  slot 0x{sl:02X} (.index 0x{sl+1:02X})  {pack:9} {weapon:8} "
              f"{ns} sheets, {size_note}")
    print(f"\n{len(report)} animations, slots 0x{FIRST_SLOT:02X}..0x{slot-1:02X}, "
          f"new banim_number = {slot}")


if __name__ == "__main__":
    main()
