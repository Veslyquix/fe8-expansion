#!/usr/bin/env python3
"""Generate the NIMAP2 voicegroup sources from the upstream EA-patch data.

NIMAP2 ("native instrument map, revision 2") is a community FE-hacking patch
that replaces FE8's voicegroup000 -- of whose 128 slots vanilla fills only 23,
the rest being dummy square waves -- with a General-MIDI-shaped instrument
map, so an arbitrary MIDI arranged against GM instrument numbers plays with
roughly the intended timbres. The companion "drumfix" fills the gaps in FE8's
own percussion voicegroups (079/080/081/083/084) at the GM percussion note
positions those maps leave empty; every entry it writes lands on a slot that
held a dummy square wave, so vanilla percussion is untouched.

Note that the voicegroup000 replacement is *not* vanilla-neutral: song001
(the title theme) plays out of voicegroup000 and its voices do change. See
config.mk's NIMAP2 block for the specifics.

Upstream ships both as Event Assembler patches that write raw bytes to
hardcoded vanilla ROM offsets, referencing sample data by absolute vanilla
address. That representation cannot survive into this repository: the modern
build relays out the whole ROM, so `0x08512AB8` is not a sample here. This
script re-expresses the same data as ordinary decomp voicegroup assembly, with
every sample pointer resolved back to its `DirectSoundData_*` symbol via
`reference/fe8u_symbols.txt`, so the linker places them wherever it likes.

Run from the repository root:

    python3 scripts/sound/gen_nimap2.py --upstream <path-to-upstream-bgm-dir>

The generated files are committed; this script exists to document exactly how
they were derived and to allow regeneration if the upstream data changes. It
is deliberately NOT wired into the build -- the build consumes the committed
.s files only, so neither a build nor a checkout depends on the upstream tree.
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SYMBOL_FILE = REPO_ROOT / "reference" / "fe8u_symbols.txt"
VOICEGROUP_DIR = REPO_ROOT / "sound" / "voicegroups"

# Voice entries are a flat 12-byte array; a voicegroup is just N of them.
VOICE_ENTRY_SIZE = 12

# Vanilla base addresses of the voicegroups the drumfix patches into, taken
# from reference/fe8u_symbols.txt. Used only to translate the upstream
# patch's absolute ORG offsets into (voicegroup, entry index) pairs.
DRUM_VOICEGROUP_BASES = {
    "voicegroup079": 0x082226B0,
    "voicegroup080": 0x082228F0,
    "voicegroup081": 0x08222B30,
    "voicegroup082": 0x08222D70,
    "voicegroup083": 0x08222FB0,
    "voicegroup084": 0x082231F0,
}

GENERATED_HEADER = """\
\t@ GENERATED FILE -- do not edit by hand.
\t@ Regenerate with: python3 scripts/sound/gen_nimap2.py --upstream <dir>
\t@
{description}

\t.include "asm/macros/music_voice.inc"

\t.section .rodata

\t.align 2
\t@********************** Voicegroup **********************@

\t.global {symbol}
{symbol}:
"""


def load_sample_symbols():
    """address -> symbol, for every DirectSoundData_* in the vanilla symbol map."""
    if not SYMBOL_FILE.exists():
        sys.exit(f"missing {SYMBOL_FILE} (needed to resolve sample pointers)")

    symbols = {}
    for line in SYMBOL_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 2 or not parts[0].lower().startswith("0x"):
            continue
        name = parts[1]
        if not name.startswith("DirectSoundData_"):
            continue
        symbols.setdefault(int(parts[0], 16), name)
    return symbols


def resolve_sample(address, symbols):
    name = symbols.get(address)
    if name is None:
        sys.exit(
            f"sample pointer 0x{address:08X} has no DirectSoundData_* symbol in "
            f"{SYMBOL_FILE.name}; cannot express it relocatably"
        )
    return name


def format_voice(entry, symbols):
    """One 12-byte voice entry -> one music_voice.inc macro invocation.

    Mirrors the macro definitions in asm/macros/music_voice.inc exactly; any
    entry type those macros do not cover is a hard error rather than a silent
    byte blob, so a surprise in the upstream data surfaces here.
    """
    voice_type = entry[0]

    if voice_type in (0x00, 0x08, 0x10):
        macro = {
            0x00: "voice_directsound",
            0x08: "voice_directsound_no_resample",
            0x10: "voice_directsound_alt",
        }[voice_type]
        base_key = entry[1]
        pan_byte = entry[3]
        pointer = int.from_bytes(entry[4:8], "little")
        attack, decay, sustain, release = entry[8:12]
        sample = resolve_sample(pointer, symbols)

        # _voice_directsound re-derives the pan byte as `pan ? (0x80 | pan) : 0`,
        # which cannot represent every raw value -- notably 0x80 itself
        # ("forced pan, value 0"), which upstream does use. Emit the macro only
        # when it reproduces the original byte exactly, and fall back to
        # explicit bytes otherwise rather than silently altering the panning.
        pan = pan_byte & 0x7F
        if (0x80 | pan if pan else 0x00) == pan_byte:
            return (
                f"\t{macro} {base_key}, {pan}, {sample}, "
                f"{attack}, {decay}, {sustain}, {release}"
            )

        return (
            f"\t@ pan byte 0x{pan_byte:02X} has no music_voice.inc macro form\n"
            f"\t.byte {voice_type}, {base_key}, 0, 0x{pan_byte:02X}\n"
            f"\t.4byte {sample}\n"
            f"\t.byte {attack}, {decay}, {sustain}, {release}"
        )

    if voice_type in (0x01, 0x09):
        macro = "voice_square_1" if voice_type == 0x01 else "voice_square_1_alt"
        sweep = entry[3]
        duty = entry[4] & 0x3
        attack = entry[8] & 0x7
        decay = entry[9] & 0x7
        sustain = entry[10] & 0xF
        release = entry[11] & 0x7
        return f"\t{macro} {sweep}, {duty}, {attack}, {decay}, {sustain}, {release}"

    if voice_type in (0x02, 0x0A):
        macro = "voice_square_2" if voice_type == 0x02 else "voice_square_2_alt"
        duty = entry[4] & 0x3
        attack = entry[8] & 0x7
        decay = entry[9] & 0x7
        sustain = entry[10] & 0xF
        release = entry[11] & 0x7
        return f"\t{macro} {duty}, {attack}, {decay}, {sustain}, {release}"

    if voice_type in (0x40, 0x80):
        pointer = int.from_bytes(entry[4:8], "little")
        group = next(
            (n for n, base in DRUM_VOICEGROUP_BASES.items() if base == pointer), None
        )
        if group is None:
            sys.exit(f"keysplit target 0x{pointer:08X} is not a known voicegroup")
        if voice_type == 0x80:
            return f"\tvoice_keysplit_all {group}"
        split = int.from_bytes(entry[8:12], "little")
        sys.exit(
            f"voice_keysplit (0x40) with table 0x{split:08X} needs a keysplit "
            "symbol mapping; upstream NIMAP2 was not expected to use one"
        )

    sys.exit(f"unhandled voice entry type 0x{voice_type:02X}")


VOICE_DIRECT_RE = re.compile(
    r"VoiceDirect\(\s*" + r"\s*,\s*".join([r"(0x[0-9A-Fa-f]+)"] * 8) + r"\s*\)"
)


def parse_nimap_event(path):
    """Upstream fe8nimap2.event -> list of raw 12-byte voice entries.

    The upstream macro is:
        VoiceDirect(Type, BaseNote, Pan, Address, EnvAtk, EnvDec, EnvSus, EnvRel)
        -> BYTE Type BaseNote $00 Pan; WORD Address; BYTE Atk Dec Sus Rel
    """
    entries = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = VOICE_DIRECT_RE.search(line)
        if not match:
            continue
        voice_type, base_note, pan, address, atk, dec, sus, rel = (
            int(value, 16) for value in match.groups()
        )
        entries.append(
            bytes([voice_type, base_note, 0x00, pan])
            + address.to_bytes(4, "little")
            + bytes([atk, dec, sus, rel])
        )
    return entries


ORG_INCBIN_RE = re.compile(
    r'ORG\s+(0x[0-9A-Fa-f]+)\s*;\s*#incbin\s+"([^"]+)"', re.IGNORECASE
)


def parse_drumfix(installer_path):
    """Upstream drumfix installer -> {voicegroup: {entry index: raw entry}}.

    Each `ORG <vanilla offset>; #incbin "<file>"` writes one or more whole
    12-byte voice entries over an existing percussion voicegroup. The offsets
    are ROM-relative (no 0x08000000 base), so they are rebased here before
    being resolved against DRUM_VOICEGROUP_BASES.
    """
    patches = {}
    for line in installer_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = ORG_INCBIN_RE.search(line)
        if not match:
            continue

        address = int(match.group(1), 16) | 0x08000000
        blob = (installer_path.parent / match.group(2)).read_bytes()

        if len(blob) % VOICE_ENTRY_SIZE:
            sys.exit(f"{match.group(2)}: {len(blob)} bytes is not a whole voice count")

        group = None
        for name, base in sorted(
            DRUM_VOICEGROUP_BASES.items(), key=lambda item: item[1], reverse=True
        ):
            if address >= base:
                group, base_address = name, base
                break
        if group is None:
            sys.exit(f"patch address 0x{address:08X} precedes every known voicegroup")

        offset = address - base_address
        if offset % VOICE_ENTRY_SIZE:
            sys.exit(f"patch address 0x{address:08X} is not voice-entry aligned")

        index = offset // VOICE_ENTRY_SIZE
        for i in range(len(blob) // VOICE_ENTRY_SIZE):
            entry = blob[i * VOICE_ENTRY_SIZE : (i + 1) * VOICE_ENTRY_SIZE]
            patches.setdefault(group, {})[index + i] = entry

    return patches


def count_vanilla_voices(name):
    """How many voice entries the committed vanilla voicegroup source has."""
    source = (VOICEGROUP_DIR / f"{name}.s").read_text(encoding="utf-8")
    return sum(
        1
        for line in source.splitlines()
        if line.strip().startswith(("voice_", "cry"))
    )


def write_voicegroup(symbol, lines, description):
    """Emit sound/voicegroups/<symbol>_nimap2.s defining `symbol` itself.

    The NIMAP2 file *replaces* its vanilla counterpart in the link rather than
    sitting alongside it (see NIMAP2_VOICEGROUPS in the Makefile), so it has to
    define the very same symbol every existing song already references --
    only the filename carries the _nimap2 suffix.
    """
    path = VOICEGROUP_DIR / f"{symbol}_nimap2.s"
    body = GENERATED_HEADER.format(symbol=symbol, description=description)
    path.write_text(body + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)} ({len(lines)} voices)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upstream",
        required=True,
        type=Path,
        help="upstream bgm directory containing nimap/ (the EA patch source)",
    )
    args = parser.parse_args()

    nimap_dir = args.upstream / "nimap"
    nimap_event = nimap_dir / "fe8nimap2.event"
    drumfix_installer = nimap_dir / "FE8_Drumfix" / "Installer.event"

    for required in (nimap_event, drumfix_installer):
        if not required.exists():
            sys.exit(f"missing upstream file: {required}")

    symbols = load_sample_symbols()

    # --- voicegroup000: the instrument map itself ---------------------------
    entries = parse_nimap_event(nimap_event)
    if len(entries) != 128:
        sys.exit(f"expected 128 NIMAP2 voices, parsed {len(entries)}")

    lines = [
        f"{format_voice(entry, symbols)}\t@ {index}"
        for index, entry in enumerate(entries)
    ]
    write_voicegroup(
        "voicegroup000",
        lines,
        "\t@ NIMAP2 instrument map: replaces vanilla voicegroup000's 128\n"
        "\t@ placeholder square waves with a General-MIDI-shaped map, so custom\n"
        "\t@ songs arranged against GM instrument numbers sound as intended.\n"
        "\t@ Trailing comment on each line is the GM program number.",
    )

    # --- drumfix: percussion voicegroup patches -----------------------------
    patches = parse_drumfix(drumfix_installer)

    for group in sorted(patches):
        vanilla_lines = (VOICEGROUP_DIR / f"{group}.s").read_text(
            encoding="utf-8"
        ).splitlines()
        voice_lines = [
            line for line in vanilla_lines if line.strip().startswith(("voice_", "cry"))
        ]

        patched = list(voice_lines)
        for index, entry in sorted(patches[group].items()):
            if index >= len(patched):
                sys.exit(
                    f"{group}: drumfix patches entry {index} but the vanilla "
                    f"group only has {len(patched)}"
                )
            # Strip the vanilla trailing address comment; it no longer applies.
            patched[index] = f"{format_voice(entry, symbols)}\t@ drumfix"

        write_voicegroup(
            group,
            patched,
            f"\t@ NIMAP2 drumfix: {group} with {len(patches[group])} percussion\n"
            "\t@ entries replaced so GM drum-track note numbers land on real\n"
            "\t@ percussion samples instead of vanilla's gaps/placeholders.",
        )


if __name__ == "__main__":
    main()
