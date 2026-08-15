"""Convert AA.exe-produced .event battle-animation installers into this repo's
banim asset sources (FE8_NEW_ANIMS).

Key correctness notes learned the hard way:

* AA.exe's `framedata` section is ALREADY LZ77-compressed (0x10 header). The
  repo's compressing linker (scripts/arm_compressing_linker.py) can only take
  a `.o` input via the `>lz` compression path -- `process_input_object()` does
  nothing at all for a `.o` with no comptype -- and a `.o` is mandatory here
  because the frame stream embeds sheet POINTERS that must be resolved at link
  time. So the section we hand it must be UNCOMPRESSED, exactly like vanilla's
  assembled `.data.script` (see scripts/merge_banim_s.sh + banim_code.inc).
  Feeding it AA.exe's already-compressed bytes double-compresses them: the
  engine LZ77-decompresses once (src/banim-ekrmain.c) and then executes still-
  compressed garbage -> crash. Hence: decompress here, emit plain `.word`s.

* The sheet pointers live inside that compressed stream as literal bytes (AA.exe
  deliberately keeps them literal so Event Assembler can patch them). To find
  them post-decompression we substitute a unique sentinel per POIN2, decompress,
  then locate each sentinel. A back-reference may legitimately duplicate one, so
  every occurrence is rewritten.

* `_modes.bin`: AA.exe emits only the 12 real mode offsets (48B); every vanilla
  banim/*_modes.bin is 96B (12 offsets + 12 reserved zero words, per
  merge_banim_s.sh). Verified: no vanilla file has a nonzero byte past offset 48.
  Left short, a high mode index reads into the neighbouring asset.

* `.index` in struct BattleAnimDef is ONE-BASED: GetBattleAnimationId
  (src/banim-ekrcmd.c) returns `idx - 1`. banim_data[] slot == .index - 1.
"""
import re, os, pathlib

# Repo root is derived from this file's location; the AA.exe .event output
# directory is machine-specific, so it can be overridden with $BANIM_EVENT_DIR.
REPO = str(pathlib.Path(__file__).resolve().parents[1])
EVENT_DIR = os.environ.get(
    "BANIM_EVENT_DIR",
    "/mnt/c/Users/David/Desktop/SRR_FEGBA/gfx/Anims/event")

WEAPONS = {
    "sword": ("[SoldierCustom]_FE10Style_[M]_by_Flasuban_Sword Installer.event", "Sword"),
    "lance": ("[SoldierCustom]_FE10Style_[M]_by_Flasuban_Lance Installer.event", "Lance"),
    "unarmed": ("[SoldierCustom]_FE10Style_[M]_by_Flasuban_Unarmed Installer.event", "Unarmed"),
}
ABBR = {"sword": "newsldsw1", "lance": "newsldln1", "unarmed": "newsldun1"}

SENTINEL_BASE = 0xE5000000  # far outside valid cmd (0x80/0x85/0x86) & ptr (0x08xx) space


def read_event(fname):
    return open(os.path.join(EVENT_DIR, fname), errors="ignore").read()


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
    n = 0
    while f"Anim_{animname}_Sheet_{n+1}:" in text:
        n += 1
    return n


def lz77_decompress(data):
    assert data[0] == 0x10, f"not an LZ77 stream (first byte {data[0]:#04x})"
    size = data[1] | (data[2] << 8) | (data[3] << 16)
    out = bytearray()
    pos = 4
    while len(out) < size:
        flags = data[pos]; pos += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                b0, b1 = data[pos], data[pos + 1]; pos += 2
                length = (b0 >> 4) + 3
                disp = ((b0 & 0xF) << 8 | b1) + 1
                for _ in range(length):
                    out.append(out[-disp])
            else:
                out.append(data[pos]); pos += 1
    assert len(out) == size, f"decompressed {len(out)} != header size {size}"
    return bytes(out)


def build_compressed_with_sentinels(text, animname):
    """Rebuild AA.exe's compressed framedata stream, substituting a unique
    4-byte sentinel for each POIN2 sheet reference. Returns (stream, refs)
    where refs[i] = sheet number (1-based, as written in the .event)."""
    section = extract_section_text(text, f"Anim_{animname}_framedata:")
    stream = bytearray()
    refs = []
    for part in (p.strip() for p in section.split(';')):
        if not part:
            continue
        if part.startswith("POIN2"):
            m = re.match(r'POIN2\s+Anim_' + re.escape(animname) + r'_Sheet_(\d+)', part)
            if not m:
                raise ValueError(f"unrecognized POIN2: {part!r}")
            stream += (SENTINEL_BASE | len(refs)).to_bytes(4, 'little')
            refs.append(int(m.group(1)))
        elif part.startswith("BYTE"):
            for tok in re.findall(r'0x[0-9a-fA-F]{1,2}|\b\d+\b', part[4:]):
                stream.append(int(tok, 16) if tok.startswith('0x') else int(tok))
        elif part.startswith("ALIGN"):
            continue
        else:
            raise ValueError(f"unrecognized framedata token: {part!r}")
    return bytes(stream), refs


def emit_script_asm(decompressed, sentinel_positions, sheet_syms, sym):
    assert len(decompressed) % 4 == 0, "script must be a whole number of words"
    lines, plain = [], []

    def flush():
        if plain:
            lines.append("\t.word " + ", ".join(plain))
            plain.clear()

    for off in range(0, len(decompressed), 4):
        if off in sentinel_positions:
            flush()
            lines.append(f"\t.word {sheet_syms[sentinel_positions[off]]}")
        else:
            plain.append(hex(int.from_bytes(decompressed[off:off + 4], 'little')))
            if len(plain) == 8:
                flush()
    flush()
    return "\n".join(lines)


def main():
    banim_dir, gfx_dir = os.path.join(REPO, "banim"), os.path.join(REPO, "graphics", "banim")
    manifest, pointers, structs = [], [], []

    for weapon, (fname, animname) in WEAPONS.items():
        text = read_event(fname)
        sym = f"banim_newsoldier_{weapon}"

        modes = extract_raw_bytes(text, f"Anim_{animname}_sectiondata:")
        assert len(modes) == 48, f"{weapon}: expected 48B mode table, got {len(modes)}"
        modes = modes + b'\x00' * 48                      # -> vanilla 96B footprint

        oam = extract_raw_bytes(text, f"Anim_{animname}_rtl:")        # already LZ77
        pal = extract_raw_bytes(text, f"Anim_{animname}_pal:")        # already LZ77
        sheets = [extract_raw_bytes(text, f"Anim_{animname}_Sheet_{i+1}:")
                  for i in range(count_sheets(text, animname))]       # already LZ77

        compressed, refs = build_compressed_with_sentinels(text, animname)
        script = lz77_decompress(compressed)

        # Locate every sentinel occurrence in the decompressed stream.
        sentinel_positions = {}
        for i, sheet_no in enumerate(refs):
            needle = (SENTINEL_BASE | i).to_bytes(4, 'little')
            start, found = 0, 0
            while True:
                at = script.find(needle, start)
                if at == -1:
                    break
                assert at % 4 == 0, f"{weapon}: sentinel {i} at unaligned offset {at}"
                sentinel_positions[at] = sheet_no - 1     # .event Sheet_N is 1-based
                found += 1
                start = at + 4
            assert found >= 1, f"{weapon}: sentinel {i} vanished during decompression"

        sheet_syms = []
        for i, blob in enumerate(sheets):
            sheet_syms.append(f"{sym}_sheet_{i}")
            open(os.path.join(gfx_dir, f"{sym}_sheet_{i}.4bpp.lz"), "wb").write(blob)
        for n in set(sentinel_positions.values()):
            assert 0 <= n < len(sheet_syms), f"{weapon}: sheet index {n} out of range"

        open(os.path.join(banim_dir, f"{sym}_modes.bin"), "wb").write(modes)
        open(os.path.join(banim_dir, f"{sym}_oam.bin.lz"), "wb").write(oam)
        open(os.path.join(gfx_dir, f"{sym}.agbpal.lz"), "wb").write(pal)

        body = emit_script_asm(script, sentinel_positions, sheet_syms, sym)
        with open(os.path.join(banim_dir, f"{sym}_script.s"), "w") as f:
            f.write(f"""@ vim:ft=armv4
@ Generated for FE8_NEW_ANIMS (CLASS_SOLDIER, {weapon}) -- source: FE-Repo
@ "[Soldier-Custom] FE10-Style [M] by Flasuban" (see CREDITS.md), compiled by
@ AA.exe and converted by scripts/banim_event_to_source.py.
@
@ UNCOMPRESSED on purpose: linker_script_banim.txt applies ">lz" to this
@ section, and the engine LZ77-decompresses it exactly once at runtime.
\t.global {sym}_script
\t.section .data.script
{sym}_script:
{body}
""")

        pal_l = f"graphics/banim/{sym}.agbpal.lz"
        oam_l = f"banim/{sym}_oam.bin.lz"
        scr_l = f"banim/{sym}_script.o|.data.script>lz"
        mod_l = f"banim/{sym}_modes.bin"

        manifest.append(f"# --- {sym} ({weapon}) ---")
        manifest += [f"graphics/banim/{s}.4bpp.lz" for s in sheet_syms]
        manifest += [pal_l, oam_l, scr_l, mod_l]

        def label(p):
            lbl = os.path.basename(p.split('|')[0].split('>')[0]).split('.')
            return lbl[0] if lbl[1] == '4bpp' else lbl[0] + '_' + lbl[1]

        m_s, s_s, o_s, p_s = label(mod_l), f"{sym}_script_o", label(oam_l), label(pal_l)
        pointers += [f"extern int {m_s};", f"extern char {s_s};",
                     f"extern char {o_s};", f"extern char {p_s};"]
        structs.append(f'    {{"{ABBR[weapon]}", &{m_s}, &{s_s}, &{o_s}, &{o_s}, &{p_s}}},')

        print(f"{weapon}: {len(sheets)} sheets, script {len(compressed)}B lz -> "
              f"{len(script)}B raw ({len(script)//4} words), "
              f"{len(refs)} sheet refs -> {len(sentinel_positions)} sites, modes {len(modes)}B")

    open(os.path.join(REPO, "_snip_manifest.txt"), "w").write("\n".join(manifest) + "\n")
    open(os.path.join(REPO, "_snip_pointers.h"), "w").write("\n".join(pointers) + "\n")
    open(os.path.join(REPO, "_snip_struct.c"), "w").write("\n".join(structs) + "\n")


if __name__ == "__main__":
    main()
