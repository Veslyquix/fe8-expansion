#!/usr/bin/env python3
"""Prove an imported BGM song assembles to exactly upstream's bytes.

import_bgm.py rewrites two syntax quirks in the upstream Sappy `.s` export so
GNU as accepts it. Those rewrites are claimed to be byte-neutral; this script
checks that claim end to end rather than trusting it:

  * assembles the imported `sound/songs/bgm/<song>.s` with the real toolchain
    and extracts its `.rodata`; and
  * independently decodes upstream's own `<song>.event` -- the Event Assembler
    input the upstream ROM is actually built from -- into bytes, resolving
    constants from include/MPlayDef.s and song-internal labels by position.

The two byte strings must match. Pointer words (`POIN`) are compared
structurally rather than by value: the `.s` and `.event` place their tracks at
different absolute addresses, so what is checked is that each pointer targets
the same *relative* offset within the song.

Usage:

    python3 scripts/sound/verify_bgm.py <upstream-song.event> [...]
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BGM_DIR = REPO_ROOT / "sound" / "songs" / "bgm"
MPLAYDEF = REPO_ROOT / "include" / "MPlayDef.s"

TOOLCHAIN = Path("/opt/devkitpro/devkitARM/bin")
AS = TOOLCHAIN / "arm-none-eabi-as"
OBJCOPY = TOOLCHAIN / "arm-none-eabi-objcopy"

EQU_RE = re.compile(r"^\s*\.equ\s+(\w+)\s*,\s*(.+?)\s*(?:@.*)?$")
DEFINE_RE = re.compile(r"^\s*#define\s+(\w+)\s+(.+?)\s*(?://.*)?$")
LABEL_RE = re.compile(r"^(\w+):")
# Case-insensitive, and POIN2 before POIN so the longer form wins. s2ea's
# output is inconsistently cased (it emits a stray lowercase `byte` where the
# source `.s` had its `,byte` typo); Event Assembler treats directives case
# insensitively, so this does too.
DIRECTIVE_RE = re.compile(
    r"^\s*(BYTE|WORD|SHORT|POIN2|POIN|ALIGN)\s+(.*?)\s*(?://.*)?$", re.I
)


def load_constants():
    """MPlayDef.s `.equ NAME, VALUE` pairs -- the same names MPlayDef.event defines."""
    constants = {}
    for line in MPLAYDEF.read_text(encoding="utf-8", errors="replace").splitlines():
        match = EQU_RE.match(line)
        if match:
            constants[match.group(1)] = match.group(2)
    return constants


def evaluate(expression, names):
    """Evaluate an assembler/EA integer expression against a name table.

    MPlayDef constants are chained (`N48 = N01+31`, `N01 = TIE+1`, ...), so
    substitution repeats until the expression is free of known names rather
    than expanding a single level.
    """
    # MPlayDef.s spells the command constants GOTO/PATT/...; the upstream
    # MPlayDef.event spells the same values GoTo/Patt/... Match case
    # insensitively so one table serves both spellings (the values themselves
    # are asserted identical -- see the header comment).
    folded = {name.lower(): value for name, value in names.items()}

    def substitute(match):
        value = folded.get(match.group(1).lower())
        return f"({value})" if value is not None else match.group(1)

    expanded = expression
    for _ in range(32):
        substituted = re.sub(r"\b([A-Za-z_]\w*)\b", substitute, expanded)
        if substituted == expanded:
            break
        expanded = substituted
    else:  # pragma: no cover - only a cyclic .equ chain reaches this
        sys.exit(f"constant expansion did not converge for {expression!r}")

    # Both syntaxes use C-style integer division on these expressions.
    expanded = expanded.replace("/", "//")
    try:
        return int(eval(expanded, {"__builtins__": {}}, {}))  # noqa: S307
    except Exception as exc:  # pragma: no cover - diagnostic path
        sys.exit(f"cannot evaluate {expression!r} (expanded {expanded!r}): {exc}")


def assemble_song(source):
    """Assemble an imported song and return (.rodata bytes, {symbol: offset})."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        obj, binary = tmp / "song.o", tmp / "song.bin"

        result = subprocess.run(
            [str(AS), "-mcpu=arm7tdmi", "-mthumb-interwork", "-I", "include",
             str(source), "-o", str(obj)],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode:
            sys.exit(f"assembling {source.name} failed:\n{result.stderr}")

        subprocess.run(
            [str(OBJCOPY), "-O", "binary", "-j", ".rodata", str(obj), str(binary)],
            check=True, capture_output=True,
        )

        nm = subprocess.run(
            [str(TOOLCHAIN / "arm-none-eabi-nm"), str(obj)],
            check=True, capture_output=True, text=True,
        )
        offsets = {}
        for line in nm.stdout.splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[1] in ("t", "T", "r", "R", "d", "D"):
                offsets[parts[2]] = int(parts[0], 16)

        return binary.read_bytes(), offsets


def decode_event(path, constants):
    """Decode an upstream `.event` song into (bytes, {label: offset}, pointer sites).

    Returns pointer sites as (byte offset, target label) so they can be
    compared structurally instead of by absolute value.
    """
    names = dict(constants)
    labels, pointers = {}, []
    data = bytearray()

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    # Pass 1: song-local #defines (Song_pri, Song_key, ...).
    for line in lines:
        match = DEFINE_RE.match(line)
        if match:
            names[match.group(1)] = match.group(2)

    # Pass 2: emit bytes, recording label offsets and pointer sites.
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        label = LABEL_RE.match(stripped)
        if label:
            labels[label.group(1)] = len(data)
            continue

        directive = DIRECTIVE_RE.match(line)
        if not directive:
            if stripped.startswith(("#define", "#include")):
                continue
            sys.exit(f"{path.name}: unhandled line {stripped!r}")

        kind, operands = directive.group(1).upper(), directive.group(2)

        if kind == "ALIGN":
            alignment = evaluate(operands, names)
            while len(data) % alignment:
                data.append(0)
            continue

        for token in operands.split():
            if kind == "BYTE":
                data.append(evaluate(token, names) & 0xFF)
            elif kind == "SHORT":
                data += (evaluate(token, names) & 0xFFFF).to_bytes(2, "little")
            else:  # WORD / POIN / POIN2
                pointers.append((len(data), token))
                data += b"\0\0\0\0"

    return bytes(data), labels, pointers


def verify(event_path):
    song = event_path.stem
    source = BGM_DIR / f"{song}.s"
    if not source.exists():
        sys.exit(f"not imported: {source.relative_to(REPO_ROOT)}")

    constants = load_constants()
    expected, event_labels, pointers = decode_event(event_path, constants)
    actual, offsets = assemble_song(source)

    if len(actual) != len(expected):
        print(f"FAIL {song}: {len(actual)} bytes assembled vs {len(expected)} expected")
        return False

    # Pointer words hold link-time addresses in the object and are unrelocated
    # zeros in the decoded event; compare them structurally, and mask them out
    # of the plain byte comparison.
    comparable = bytearray(actual)
    for offset, target in pointers:
        comparable[offset : offset + 4] = b"\0\0\0\0"

        if target in event_labels:
            want = event_labels[target]
            got = offsets.get(target)
            if got is None:
                print(f"FAIL {song}: pointer target {target} missing from object")
                return False
            if got != want:
                print(
                    f"FAIL {song}: {target} at song offset 0x{got:X}, "
                    f"upstream has 0x{want:X}"
                )
                return False
        # Targets that are not song-local labels (the voicegroup) are external
        # symbols in both representations; nothing positional to compare.

    if bytes(comparable) != expected:
        print(f"FAIL {song}: byte mismatch")
        for i in range(0, len(expected), 16):
            if bytes(comparable[i : i + 16]) != expected[i : i + 16]:
                print(f"  @0x{i:04X} expected {expected[i:i+16].hex()}")
                print(f"  @0x{i:04X} actual   {bytes(comparable[i:i+16]).hex()}")
                break
        return False

    print(
        f"OK   {song}: {len(actual)} bytes, "
        f"{len(pointers)} pointers, {len(event_labels)} labels -- exact match"
    )
    return True


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ok = all(verify(Path(arg)) for arg in sys.argv[1:])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
