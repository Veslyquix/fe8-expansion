#!/usr/bin/env python3
"""Generate transitional modern-link artifacts from legacy linker inputs.

Transforms the per-object legacy ldscript, sym_iwram, and
linker_script_sound into modern-compatible variants by:

1. Substituting object paths listed in a replacement manifest.
2. Redirecting INCLUDE statements to generated include files.
3. Mapping agbcc libc/libgcc archive member names to modern newlib
   equivalents and widening section selectors.
4. Removing proven-obsolete library entries (dp-bit, fp-bit, syscalls,
   libcfunc).
5. Adding transitional catchalls for sections modern GCC emits but the
   per-object legacy layout does not place.
6. Relaxing only the ``gLoadUnitBuffer``/``end`` EWRAM pins that
   overflow by a few bytes under modern object sizes (issue-#4 debt).

All outputs are deterministic and contain no timestamps or absolute host
paths beyond those in the inputs.  Tracked linker inputs are never
modified.

**FE6 SIO note**: ``fe6sio_payload.bin.lz`` is an untracked generated
blob.  A clean regeneration still invokes the mgfembp submodule's own
agbcc variant.  This tool does not solve or conceal that dependency.

Usage::

    python3 scripts/modernize/prepare_modern_link.py \\
        --root .  --modern-root build/expansion-modern/debug/aapcs \\
        --manifest build/expansion-modern/debug/aapcs/manifest.txt \\
        --output-dir build/expansion-modern/debug/aapcs/link
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path, PurePosixPath

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OBJ_RE = re.compile(r"((?:src|asm)/[\w/.+-]+\.o)(?=[\s(;:]|\Z)")

_LIBC_MEMBER_RE = re.compile(
    r"\*libc\.a:([\w.+-]+\.o)(\([^)]*\))"
)

_LIBGCC_DPFP_RE = re.compile(
    r"\s*\*libgcc\.a:(?:dp-bit|fp-bit)\.o\([^)]*\)\s*;"
)

_LIB_SECTION_RE = re.compile(
    r"(\*lib\w+\.a:[\w.+-]+\.o)\((\.\w+)\)"
)

_EWRAM_LOADUNIT_RE = re.compile(
    r"\. = 0x3EFB8;\s*(gLoadUnitBuffer)\s*=\s*\.;"
)

_EWRAM_END_RE = re.compile(
    r"\. = 0x3EFB8;\s*(end)\s*=\s*\.;"
)

_REMOVED_LIBC = frozenset({"syscalls.o", "libcfunc.o"})
_LIBM_MEMBERS = frozenset({"s_isinf.o", "s_isnan.o"})

_MODERN_IWRAM_PLACEMENTS = {
    "gText_GoldBox": (0x1DA0, "src/bmshop.o", ".bss.gText_GoldBox"),
    "SoundMainRAM_Buffer": (0x2C60, "src/m4a.o", ".bss.code"),
    "gSoundInfo": (0x5410, "src/m4a.o", ".bss.gSoundInfo"),
    "gMPlayJumpTable": (0x6480, "src/m4a.o", ".bss.gMPlayJumpTable"),
    "gCgbChans": (0x6510, "src/m4a.o", ".bss.gCgbChans"),
    "gMPlayMemAccArea": (0x6710, "src/m4a.o", ".bss.gMPlayMemAccArea"),
    "ReadSramFast": (0x67A0, "src/agb_sram.o", ".bss.ReadSramFast"),
    "VerifySramFast": (0x67A4, "src/agb_sram.o", ".bss.VerifySramFast"),
}

_MODERN_IWRAM_ALIASES = {
    "gUnk_62": 0x2C61,
    "gUnk_84": 0x6484,
    "gUnk_85": 0x6508,
    "gUnk_86": 0x650C,
}

_AGBSRAM_BSS_ANCHOR = ". = ALIGN(4); src/agb_sram.o(.bss);"
_AGBSRAM_BSS_REPLACEMENT = (
    ". = ALIGN(4); {obj}(.bss.readSramFast_Work);\n"
    "        . = ALIGN(4); {obj}(.bss.verifySramFast_Work);\n"
    "        . = ALIGN(4); {obj}(.bss.verifySramValueFast_Work);"
)

_WIDEN_SECTIONS = {
    ".text": ".text .text.*",
    ".rodata": ".rodata .rodata.*",
    ".data": ".data .data.*",
    ".bss": ".bss .bss.*",
}

# Anchors — the generator fails if these are not found exactly once.
_ANCHOR_ARM_CALL_TEXT_RE = re.compile(
    r'("?[^"\n]*asm/arm_call\.o"?)\(\.text\);'
)
_ANCHOR_RODATA_COMMENT = "/* .rodata */"
_ANCHOR_DATA_COMMENT = "/* .data */"
_ANCHOR_ROM_CLOSE = "} = 0"
_ANCHOR_ROM_START = "ROM __text_start :"
_ANCHOR_EWRAM_END_MARKER = "end = .;"
_ANCHOR_INCLUDE_IWRAM = 'INCLUDE "sym_iwram.txt"'
_ANCHOR_INCLUDE_SOUND = 'INCLUDE "linker_script_sound.txt"'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_manifest(path: str) -> set[str]:
    """Load a newline-delimited manifest of source-relative .o paths."""
    entries = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                entries.add(stripped)
    return entries


def _quote_ld_path(path: str) -> str:
    """Quote a linker-script path if it contains spaces."""
    if '"' in path or "\n" in path:
        raise ValueError(f"path contains unsupported characters: {path!r}")
    if " " in path:
        return f'"{path}"'
    return path


def _substitute_objects(text: str, manifest: set[str], modern_root: str) -> str:
    """Replace every manifest object reference with its modern-root path."""
    def _repl(m: re.Match[str]) -> str:
        rel = m.group(1)
        if rel in manifest:
            return _quote_ld_path(str(PurePosixPath(modern_root) / rel))
        return rel
    return _OBJ_RE.sub(_repl, text)


def _map_libc_member(text: str) -> str:
    """Rename legacy libc member references to modern newlib names."""
    def _repl(m: re.Match[str]) -> str:
        member = m.group(1)
        sections = m.group(2)
        if member in _REMOVED_LIBC:
            return f"/* removed: libc {member} */"
        if member in _LIBM_MEMBERS:
            return f"*libm.a:libm_a-{member}{sections}"
        return f"*libc.a:libc_a-{member}{sections}"
    return _LIBC_MEMBER_RE.sub(_repl, text)


def _remove_obsolete_libgcc(text: str) -> str:
    """Remove dp-bit.o and fp-bit.o entries (no modern equivalent)."""
    return _LIBGCC_DPFP_RE.sub("", text)


def _widen_lib_sections(text: str) -> str:
    """Add .text.* / .rodata.* wildcards to explicit library section specs."""
    def _repl(m: re.Match[str]) -> str:
        prefix = m.group(1)
        section = m.group(2)
        wider = _WIDEN_SECTIONS.get(section)
        if wider:
            return f"{prefix}({wider})"
        return m.group(0)
    return _LIB_SECTION_RE.sub(_repl, text)


def _relax_ewram_pins(text: str) -> str:
    """Float the gLoadUnitBuffer and end EWRAM pins (transitional #4 debt)."""
    text = _EWRAM_LOADUNIT_RE.sub(
        r"/* transitional: pin relaxed for modern object sizes (issue #4) */\n"
        r"        \1 = .;",
        text,
    )
    text = _EWRAM_END_RE.sub(
        r"/* transitional: pin relaxed for modern object sizes (issue #4) */\n"
        r"        \1 = .;",
        text,
    )
    return text


def _restore_iwram_placements(text: str, manifest: set[str], modern_root: str) -> str:
    """Replace stale IWRAM pin assignments with explicit modern section placements.

    Requires all IWRAM owner objects be in the manifest (compiled with
    ``-fdata-sections``).  Raises ``ValueError`` if any are missing.
    """
    required_owners = sorted({
        src_obj for _, src_obj, _ in _MODERN_IWRAM_PLACEMENTS.values()
    })
    missing = [o for o in required_owners if o not in manifest]
    if missing:
        raise ValueError(
            f"IWRAM placement requires modern -fdata-sections objects"
            f" in manifest; missing: {missing}"
        )

    anchor = _AGBSRAM_BSS_ANCHOR
    for candidate in [anchor, _substitute_objects(anchor, manifest, modern_root)]:
        if candidate in text:
            obj_path = _quote_ld_path(
                str(PurePosixPath(modern_root) / "src/agb_sram.o")
            )
            replacement = _AGBSRAM_BSS_REPLACEMENT.format(obj=obj_path)
            text = text.replace(candidate, replacement, 1)
            break
    else:
        raise ValueError("agb_sram.o(.bss) anchor not found")

    for sym, (offset, src_obj, section) in sorted(_MODERN_IWRAM_PLACEMENTS.items()):
        pin_pattern = re.compile(
            rf"^\. = 0x{offset:06X};\s*{re.escape(sym)}\s*=\s*\.;",
            re.MULTILINE | re.IGNORECASE,
        )
        matches = pin_pattern.findall(text)
        if len(matches) != 1:
            raise ValueError(
                f"IWRAM pin {sym!r} at 0x{offset:06X} found"
                f" {len(matches)} times (expected 1)"
            )

        obj_path = _quote_ld_path(
            str(PurePosixPath(modern_root) / src_obj)
        )
        replacement = (
            f". = 0x{offset:06X};"
            f" /* transitional: modern object placement (issue #4) */\n"
            f"        . = ALIGN(4); {obj_path}({section});"
        )
        text = pin_pattern.sub(replacement, text, count=1)

    for alias, addr in sorted(_MODERN_IWRAM_ALIASES.items()):
        pin_pattern = re.compile(
            rf"^\. = 0x{addr:06X};\s*{re.escape(alias)}\s*=\s*\.;",
            re.MULTILINE | re.IGNORECASE,
        )
        matches = pin_pattern.findall(text)
        if len(matches) != 1:
            raise ValueError(
                f"IWRAM alias {alias!r} at 0x{addr:06X} found"
                f" {len(matches)} times (expected 1)"
            )
        replacement = f"PROVIDE({alias} = __iwram_start + 0x{addr:06X});"
        text = pin_pattern.sub(replacement, text, count=1)

    return text


def _check_anchor(text: str, anchor: str, name: str) -> None:
    """Fail if the anchor is not found exactly once."""
    count = text.count(anchor)
    if count != 1:
        raise ValueError(
            f"anchor {name!r} found {count} times (expected 1): {anchor!r}"
        )


def _add_catchalls(text: str) -> str:
    """Insert transitional section catchalls at proven anchors."""
    # After arm_call.o(.text): catch remaining .text
    matches = list(_ANCHOR_ARM_CALL_TEXT_RE.finditer(text))
    if len(matches) != 1:
        raise ValueError(
            f"anchor 'arm_call .text' found {len(matches)} times (expected 1)"
        )
    m = matches[0]
    text = text[:m.end()] + (
        "\n        /* transitional: catch remaining .text */\n"
        "        *(.text .text.* .glue_7 .glue_7t)"
    ) + text[m.end():]

    # Before /* .data */: catch remaining .rodata
    _check_anchor(text, _ANCHOR_DATA_COMMENT, ".data comment")
    text = text.replace(
        _ANCHOR_DATA_COMMENT,
        "/* transitional: catch remaining .rodata */\n"
        "        *(.rodata .rodata.* .rodata.str1.* .rodata.cst*)\n\n"
        "        " + _ANCHOR_DATA_COMMENT,
    )

    # After last pinned data before } = 0: catch remaining .data/.text/.rodata
    _check_anchor(text, _ANCHOR_ROM_CLOSE, "ROM close")
    text = text.replace(
        _ANCHOR_ROM_CLOSE,
        "        /* transitional: catch remaining library sections */\n"
        "        *(.data .data.* .text .text.* .rodata .rodata.*)\n"
        + _ANCHOR_ROM_CLOSE,
    )

    # Before ROM section: catch remaining .bss
    _check_anchor(text, _ANCHOR_ROM_START, "ROM start")
    text = text.replace(
        _ANCHOR_ROM_START,
        "    /* transitional: catch remaining .bss */\n"
        "    .bss.catchall (NOLOAD) : { *(.bss .bss.* COMMON) } > ewram\n\n"
        + _ANCHOR_ROM_START,
    )

    return text


def _add_ewram_catchall(text: str) -> str:
    """Add ewram_data catchall before end marker in ewram_data section."""
    # The end marker after pin relaxation is just "end = .;"
    # preceded by "gLoadUnitBuffer = .;"
    marker = "        gLoadUnitBuffer = .;\n"
    _check_anchor(text, marker, "gLoadUnitBuffer line")
    text = text.replace(
        marker,
        "        /* transitional: catch remaining ewram_data */\n"
        "        *(ewram_data)\n" + marker,
    )
    return text


def _redirect_includes(text: str, output_dir: str) -> str:
    """Redirect INCLUDE directives to generated files in output_dir."""
    if '"' in output_dir or "\n" in output_dir:
        raise ValueError(
            f"output directory contains unsupported characters: {output_dir!r}"
        )
    iwram_out = str(PurePosixPath(output_dir) / "sym_iwram.ld")
    sound_out = str(PurePosixPath(output_dir) / "linker_script_sound.ld")
    _check_anchor(text, _ANCHOR_INCLUDE_IWRAM, "INCLUDE sym_iwram")
    _check_anchor(text, _ANCHOR_INCLUDE_SOUND, "INCLUDE linker_script_sound")
    text = text.replace(
        _ANCHOR_INCLUDE_IWRAM,
        f'INCLUDE "{iwram_out}"',
    )
    text = text.replace(
        _ANCHOR_INCLUDE_SOUND,
        f'INCLUDE "{sound_out}"',
    )
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transform_ldscript(
    text: str,
    manifest: set[str],
    modern_root: str,
    output_dir: str,
) -> str:
    """Apply all transformations to the main ldscript."""
    text = _substitute_objects(text, manifest, modern_root)
    text = _map_libc_member(text)
    text = _remove_obsolete_libgcc(text)
    text = _widen_lib_sections(text)
    text = _relax_ewram_pins(text)
    text = _add_ewram_catchall(text)
    text = _add_catchalls(text)
    text = _redirect_includes(text, output_dir)
    return text


def transform_include(
    text: str,
    manifest: set[str],
    modern_root: str,
) -> str:
    """Apply object/library transformations to an included linker fragment."""
    text = _substitute_objects(text, manifest, modern_root)
    text = _map_libc_member(text)
    text = _remove_obsolete_libgcc(text)
    text = _widen_lib_sections(text)
    return text


def transform_iwram_include(
    text: str,
    manifest: set[str],
    modern_root: str,
) -> str:
    """Apply all transforms to the sym_iwram include, including IWRAM placement."""
    text = transform_include(text, manifest, modern_root)
    text = _restore_iwram_placements(text, manifest, modern_root)
    return text


def _quote_response_path(path: str) -> str:
    """Quote a response-file object path if it contains spaces."""
    if '"' in path or "\n" in path:
        raise ValueError(f"object path contains unsupported characters: {path!r}")
    if " " in path:
        return f'"{path}"'
    return path


def build_object_list(
    manifest: set[str],
    modern_root: str,
    legacy_objects: list[str],
) -> list[str]:
    """Build a deduplicated object list: modern for manifest, legacy for rest.

    Returns a sorted, deterministic list of object paths.  Paths with
    spaces are quoted for GNU ld response-file compatibility.
    """
    seen_bases: dict[str, str] = {}
    result: list[str] = []

    for rel in sorted(manifest):
        modern_path = str(PurePosixPath(modern_root) / rel)
        seen_bases[rel] = modern_path
        result.append(_quote_response_path(modern_path))

    for legacy in legacy_objects:
        if legacy not in seen_bases:
            seen_bases[legacy] = legacy
            result.append(_quote_response_path(legacy))

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate transitional modern-link artifacts.",
        epilog=(
            "NOTE: fe6sio_payload.bin.lz is an untracked generated blob. "
            "A clean regeneration still invokes the mgfembp submodule's "
            "own agbcc variant. This tool does not solve or conceal that "
            "dependency."
        ),
    )
    parser.add_argument("--root", required=True, help="Repository root")
    parser.add_argument("--modern-root", required=True,
                        help="Modern object output directory")
    parser.add_argument("--manifest", required=True,
                        help="Newline-delimited list of source-relative .o paths")
    parser.add_argument("--output-dir", required=True,
                        help="Output directory for generated link artifacts")
    parser.add_argument("--legacy-objects", nargs="*", default=[],
                        help="Additional legacy .o paths not in manifest")

    args = parser.parse_args(argv)
    root = Path(args.root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest(args.manifest)

    # Read legacy inputs
    ldscript = (root / "ldscript.txt").read_text(encoding="utf-8")
    sym_iwram = (root / "sym_iwram.txt").read_text(encoding="utf-8")
    sound_script = (root / "linker_script_sound.txt").read_text(encoding="utf-8")

    # Transform
    out_dir_str = str(output_dir)
    ldscript_out = transform_ldscript(ldscript, manifest, args.modern_root, out_dir_str)
    iwram_out = transform_iwram_include(sym_iwram, manifest, args.modern_root)
    sound_out = transform_include(sound_script, manifest, args.modern_root)

    # Build object list
    obj_list = build_object_list(manifest, args.modern_root, args.legacy_objects)

    # Write outputs
    (output_dir / "ldscript.ld").write_text(ldscript_out, encoding="utf-8")
    (output_dir / "sym_iwram.ld").write_text(iwram_out, encoding="utf-8")
    (output_dir / "linker_script_sound.ld").write_text(sound_out, encoding="utf-8")
    (output_dir / "objects.lst").write_text(
        "\n".join(obj_list) + "\n", encoding="utf-8"
    )

    print(f"Generated {len(obj_list)} object entries in {output_dir}")
    print(f"  manifest objects: {len(manifest)}")
    print(f"  legacy objects: {len(obj_list) - len(manifest)}")


if __name__ == "__main__":
    main()
