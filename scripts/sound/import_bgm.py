#!/usr/bin/env python3
"""Import upstream custom-BGM song sources into sound/songs/bgm/.

The community BGM packs distribute songs as Sappy-exported `.s` files. Those
are ordinary GBA m4a track data and assemble against this repo's
include/MPlayDef.s unchanged -- except that the exporter emits two constructs
GNU as rejects, both of which appear across a large fraction of the pack:

  1. Space-separated `.byte` operands (`.byte MODT 0`) instead of
     comma-separated ones. Upstream assembles these through Event Assembler,
     whose `BYTE a b` is space-separated, so the intended bytes are simply
     `a, b`; adding the comma reproduces them exactly.
  2. A `,byte` typo for `.byte`. The `.event` file s2ea generates from the
     same source shows the intended `BYTE` there, confirming it is a typo and
     not a deliberate directive.

Both rewrites are purely syntactic -- the emitted bytes are identical to what
upstream's Event Assembler path produces. verify_bgm.py checks exactly that,
by assembling the imported file and diffing it against bytes decoded
independently from upstream's own `.event` output.

Usage:

    python3 scripts/sound/import_bgm.py <upstream-song.s> [<upstream-song.s> ...]

Imported songs are committed; this script documents how they were derived and
makes adding more a one-liner. It is not part of the build.
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEST_DIR = REPO_ROOT / "sound" / "songs" / "bgm"

# `.byte`/`.word` operand lists, captured so the operand text can be normalized
# without disturbing indentation or trailing comments.
DIRECTIVE_RE = re.compile(r"^(\s*)([.,])(byte|word)(\s+)([^@]*?)(\s*)(@.*)?$", re.I)


def normalize_operands(operands):
    """`MODT 0` -> `MODT, 0`, leaving already-comma-separated text alone.

    Splits on commas first so existing separators are preserved verbatim, then
    comma-joins any run of whitespace-separated tokens inside a single field.
    Safe because no operand expression in these files contains whitespace (the
    exporter emits `132*Song_tbs/2`, `c_v-32` and friends unspaced) -- the
    importer asserts this below rather than assuming it.
    """
    fields = []
    for field in operands.split(","):
        tokens = field.split()
        if not tokens:
            continue
        fields.extend(tokens)
    return ", ".join(fields)


def convert(text, source_name):
    out, fixed_directive, fixed_commas = [], 0, 0

    for lineno, line in enumerate(text.splitlines(), 1):
        match = DIRECTIVE_RE.match(line)
        if not match:
            out.append(line)
            continue

        indent, sigil, directive, gap, operands, trail, comment = match.groups()

        if sigil == ",":
            fixed_directive += 1

        normalized = normalize_operands(operands)

        # The rewrite may only insert separators: the operand token sequence
        # itself must come out identical, or something was lost/reordered.
        before = [token for token in re.split(r"[,\s]+", operands) if token]
        after = [token for token in re.split(r"[,\s]+", normalized) if token]
        if before != after:
            sys.exit(
                f"{source_name}:{lineno}: operand rewrite changed content "
                f"({operands!r} -> {normalized!r}); refusing to guess"
            )
        if normalized != operands.strip():
            fixed_commas += 1

        rebuilt = f"{indent}.{directive}{gap}{normalized}"
        if comment:
            rebuilt += f"{trail}{comment}"
        out.append(rebuilt)

    return "\n".join(out) + "\n", fixed_directive, fixed_commas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path, help="upstream .s song files")
    args = parser.parse_args()

    DEST_DIR.mkdir(parents=True, exist_ok=True)

    for source in args.sources:
        if not source.exists():
            sys.exit(f"missing source: {source}")

        # Upstream ships CRLF; the repo is LF throughout.
        text = source.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        converted, fixed_directive, fixed_commas = convert(text, source.name)

        dest = DEST_DIR / source.name
        dest.write_text(converted, encoding="utf-8")
        dest.chmod(0o644)

        print(
            f"imported {dest.relative_to(REPO_ROOT)} "
            f"({fixed_commas} operand-comma fixes, {fixed_directive} ',byte' typos)"
        )


if __name__ == "__main__":
    main()
