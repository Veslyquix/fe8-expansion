#!/usr/bin/env python3
"""Generate a no$gba-format .sym symbol file from a built modern ELF.

no$gba's debugger auto-loads a `<romname>.sym` file placed next to the ROM
it's debugging, and uses it to show function/data names (instead of raw
addresses) in the disassembly view, call stack, and breakpoint list. The
format is one `AAAAAAAA name` pair per line (8-digit hex address, no `0x`
prefix, whitespace, symbol name); no$gba does its own sorting, so input
order doesn't matter.

Symbols come straight from arm-none-eabi-nm's own defined-symbol table, so
this only needs the toolchain's `nm` and the ELF -- no linker-script or
DWARF parsing of our own. Deliberately dependency-free (stdlib +
subprocess only), matching this repo's other scripts/modernize/*.py tools.

Only symbols with a real address are kept -- function/code (T/t), and
data/rodata/bss (D/d/R/r/B/b/W/w). Undefined (U/u) and absolute-value
(A/a) symbols are dropped: undefined ones have no address to show, and
absolute ones are overwhelmingly manifest constants pulled in from
assembly (register names, enum-like #defines) that happen to share nm's
output format but aren't things you'd ever want to see as a "function or
data" label while stepping through code in a debugger -- keeping them
would bury the real ~10k code/data symbols under ~270k constants clustered
at address 0.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

# nm single-letter symbol kinds worth keeping -- real code/data addresses.
# See `man nm`: uppercase = external/global, lowercase = local.
_ADDRESSABLE_KINDS = set("TtDdRrBbWw")


def generate(nm_path: str, elf_path: str) -> list[str]:
    result = subprocess.run(
        [nm_path, "-n", elf_path],
        capture_output=True, text=True, check=True,
    )

    lines = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) != 3:
            # Undefined symbols print as "         U name" (no address).
            continue

        addr, kind, name = parts

        if kind not in _ADDRESSABLE_KINDS:
            continue

        lines.append(f"{addr} {name}")

    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nm", default="nm", help="arm-none-eabi-nm binary to use")
    parser.add_argument("--elf", required=True, help="input ELF (with symbols, i.e. before --strip-debug)")
    parser.add_argument("--out", required=True, help="output .sym path")
    args = parser.parse_args(argv)

    lines = generate(args.nm, args.elf)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"wrote {len(lines)} symbols to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
