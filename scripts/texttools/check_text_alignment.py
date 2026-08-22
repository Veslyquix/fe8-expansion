#!/usr/bin/env python3
"""
Detect (and optionally fix) a Huffman-alignment bug in texts.txt-format
message files.

text_to_utf8_u16_array (textprocess.py) packs two raw bytes into each u16
symbol for any byte >= 0x20 (ordinary printable text), but consumes
control-code bytes one at a time, since every single-byte control code in
textdefs.txt (like [X] = 0, the string terminator, and [.] = 31) is below
0x20. If the text before a trailing [X] has an odd number of >=0x20 bytes,
[X]'s own zero byte gets swallowed as the *second half* of the last text
byte's pair instead of starting a pair of its own -- producing a nonzero,
garbage terminator symbol instead of a clean 0x0000. At runtime this means
the string has no real terminator and rendering/measurement code runs into
whatever data follows it.

The established fix (already used for several existing entries, e.g.
Frederick[.][X]/Fox[.][X]/Liz[.][X] in texts/texts.txt) is a single [.] pad
byte immediately before [X]: since [.] is itself always consumed as its
own standalone one-byte symbol, inserting it shifts [X]'s start position
by exactly one, flipping its parity so it lands alone.

This script re-uses textprocess.py's own encoder (no reimplemented
byte-packing logic to drift out of sync) to actually encode every message
in texts.txt, and simply checks whether messages ending in a literal "[X]"
produced a trailing 0x0000 symbol. It is deliberately state-agnostic: it
re-derives the correct answer from the current text every time, so it
equally catches a missing pad, a stale/unnecessary pad after a name edit,
or any other cause of the same misalignment -- not just the one pattern
that motivated it.

Usage:
    check_text_alignment.py [--fix] [--main texts/texts.txt]
                             [--defs texts/textdefs.txt]
                             [--encoding utf8|cp932]

Exit status is nonzero if any misaligned entries were found (and not
fixed), so this can be wired into a pre-build check or CI step.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textprocess as tp

TERMINATOR_TOKEN = "[X]"


class MsgBlock:
    def __init__(self, file_path, line_start, line_end, definiation, text):
        self.file_path = file_path
        self.line_start = line_start  # inclusive, 0-based
        self.line_end = line_end      # exclusive
        self.definiation = definiation
        self.text = text


def collect_message_blocks(file_path, blocks=None):
    """Mirrors textprocess.process_file's own parsing loop (same
    directives, same block boundaries), but keeps each block's exact
    source line range instead of only its encoded data, so a fix can be
    written back to the right place."""
    if blocks is None:
        blocks = []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        include_match = tp.RE_INCLUDE.match(stripped)
        if include_match:
            include_file = include_match.group(1)
            include_path = os.path.join(os.path.dirname(file_path), include_file)
            if os.path.isfile(include_path):
                collect_message_blocks(include_path, blocks)
            i += 1
            continue

        directive_match = tp.RE_MSGIDX.match(stripped)
        macro_match = tp.RE_MACRO.match(stripped) if stripped.startswith('##') else None

        if directive_match or macro_match:
            definiation = macro_match.group(1) if macro_match else stripped
            line_start = i
            i += 1
            text_lines = []
            while i < len(lines) and not lines[i].startswith("#"):
                text_lines.append(lines[i].rstrip('\n'))
                i += 1
            text = ''.join(text_lines)
            blocks.append(MsgBlock(file_path, line_start, i, definiation, text))
        else:
            i += 1

    return blocks


def is_misaligned(text, control_chars, encoding_method):
    """True if `text` ends in a literal "[X]" but encodes to a last u16
    symbol other than 0 -- i.e. the terminator got swallowed into the
    preceding byte pair instead of standing alone."""
    if not text.rstrip().endswith(TERMINATOR_TOKEN):
        return False

    data = tp.text_to_u16_array(text, control_chars, encoding_method)
    return not data or data[-1] != 0


def patch_block(lines, block):
    """Insert "[.]" immediately before the last "[X]" found within the
    block's own lines, searching from the last line backwards (the
    terminator is virtually always on the final content line, but this
    is robust to it not being)."""
    for line_no in range(block.line_end - 1, block.line_start, -1):
        idx = lines[line_no].rfind(TERMINATOR_TOKEN)
        if idx != -1:
            lines[line_no] = lines[line_no][:idx] + "[.]" + lines[line_no][idx:]
            return True
    return False


def fix_file(file_path, misaligned_blocks):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Patch bottom-to-top so earlier line numbers in the same file stay
    # valid as later blocks (which appear after, i.e. with higher line
    # numbers) are patched first.
    for block in sorted(misaligned_blocks, key=lambda b: b.line_start, reverse=True):
        if not patch_block(lines, block):
            print(f"warning: could not locate {TERMINATOR_TOKEN} to patch for "
                  f"{block.definiation} in {file_path}", file=sys.stderr)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--main", default=os.path.join("texts", "texts.txt"),
                         help="entry-point text file (default: texts/texts.txt)")
    parser.add_argument("--defs", default=os.path.join("texts", "textdefs.txt"),
                         help="control-code definitions file (default: texts/textdefs.txt)")
    parser.add_argument("--encoding", default="utf8", choices=["utf8", "cp932"],
                         help="encoding method to match the real build (default: utf8, "
                              "matching the Makefile's textprocess.py invocation)")
    parser.add_argument("--fix", action="store_true",
                         help="rewrite the offending line(s) in place instead of only reporting")
    args = parser.parse_args()

    control_chars = tp.load_control_chars(args.defs)
    blocks = collect_message_blocks(args.main)

    misaligned = [b for b in blocks if is_misaligned(b.text, control_chars, args.encoding)]

    if not misaligned:
        print(f"checked {len(blocks)} message(s), all aligned")
        return 0

    by_file = {}
    for b in misaligned:
        by_file.setdefault(b.file_path, []).append(b)

    for b in misaligned:
        print(f"{b.file_path}:{b.line_start + 1}: {b.definiation}: "
              f"terminator misaligned (missing/incorrect [.] pad)")

    if args.fix:
        for file_path, file_blocks in by_file.items():
            fix_file(file_path, file_blocks)
        print(f"fixed {len(misaligned)} entr{'y' if len(misaligned) == 1 else 'ies'}")
        return 0

    print(f"{len(misaligned)} misaligned entr{'y' if len(misaligned) == 1 else 'ies'} "
          f"found -- rerun with --fix to patch automatically")
    return 1


if __name__ == "__main__":
    sys.exit(main())
