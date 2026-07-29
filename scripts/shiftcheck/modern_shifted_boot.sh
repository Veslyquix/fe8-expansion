#!/bin/sh
# Shifted-boot verification for the modern expansion linker.
#
# Builds a shifted ROM by passing --defsym=__text_shift=<SHIFT> (the P9-A
# interface MODERN_TEXT_SHIFT) and verifies it produces the same deterministic
# boot fingerprints as the normal ROM using gba_playtest behavior policy.
#
# Exit: 0=PASS, 1=FAIL (diverged), 2=setup/build error.
#
# Usage:
#   scripts/shiftcheck/modern_shifted_boot.sh [shift_amount]
#   SHIFTCHECK_SHIFT=0x80000 scripts/shiftcheck/modern_shifted_boot.sh
set -eu

die() { printf 'error: %s\n' "$*" >&2; exit 2; }

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
. "$SCRIPT_DIR/modern_toolchain.sh"
cd "$ROOT_DIR"

# --- Configuration (all overridable via env) ---
SHIFT="${1:-${SHIFTCHECK_SHIFT:-0x40000}}"
OUTDIR="${SHIFTCHECK_OUTDIR:-build/shiftcheck}"
OBJECTS_LST="${SHIFTCHECK_OBJECTS_LST:-build/expansion-modern/debug/aapcs/link/objects.lst}"
BANIM_SYM="${SHIFTCHECK_BANIM_SYM:-banim/data_banim.o.sym.o}"
LDSCRIPT="${SHIFTCHECK_LDSCRIPT:-linker/expansion.ld}"
BASE_ELF="${SHIFTCHECK_BASE_ELF:-build/expansion-modern/debug/aapcs/fireemblem8.elf}"
ROM_SIZE="${SHIFTCHECK_ROM_SIZE_BYTES:-0x01000000}"
ROM_SIZE_NAME="${SHIFTCHECK_ROM_SIZE:-16M}"
PAD_TO="${SHIFTCHECK_PAD_TO:-0x9000000}"
PREFIX="${PREFIX:-arm-none-eabi-}"

# --- Tool resolution ---
CC=$(shiftcheck_resolve_tool \
    "${MODERN_CC:-${CC:-${PREFIX}gcc}}" "$ROOT_DIR" "${PREFIX}gcc") ||
    die "cannot find ${PREFIX}gcc; set MODERN_CC or PATH"
LD=$(shiftcheck_resolve_tool \
    "${MODERN_LD:-${LD:-${PREFIX}ld}}" "$ROOT_DIR" "${PREFIX}ld") ||
    die "cannot find ${PREFIX}ld; set MODERN_LD or PATH"
OBJCOPY=$(shiftcheck_resolve_tool \
    "${MODERN_OBJCOPY:-${OBJCOPY:-${PREFIX}objcopy}}" \
    "$ROOT_DIR" "${PREFIX}objcopy") ||
    die "cannot find ${PREFIX}objcopy; set MODERN_OBJCOPY or PATH"
NM=$(shiftcheck_resolve_tool \
    "${MODERN_NM:-${NM:-${PREFIX}nm}}" "$ROOT_DIR" "${PREFIX}nm") ||
    die "cannot find ${PREFIX}nm; set MODERN_NM or PATH"

# --- Prerequisite check ---
[ -f "$LDSCRIPT" ]    || die "missing ldscript: $LDSCRIPT"
[ -f "$OBJECTS_LST" ] || die "missing objects list: $OBJECTS_LST (build expansion-modern-elf first)"
[ -f "$BANIM_SYM" ]   || die "missing banim sidecar: $BANIM_SYM"
[ -f "$BASE_ELF" ]     || die "missing base ELF: $BASE_ELF"

# --- Library discovery ---
libgcc_dir=$(shiftcheck_libgcc_dir "$CC") ||
    die "cannot discover libgcc via $CC"
libc_dir=$(shiftcheck_newlib_dir "$CC" "${MODERN_NEWLIB_LIB:-}") ||
    die "cannot discover libc via $CC; set MODERN_NEWLIB_LIB"

mkdir -p "$OUTDIR"

# --- Link with shift ---
printf 'Linking shifted ELF (__text_shift=%s)...\n' "$SHIFT"
"$LD" \
    --orphan-handling=error \
    --defsym=__rom_size="$ROM_SIZE" \
    --defsym=__text_shift="$SHIFT" \
    -T "$LDSCRIPT" \
    -Map "$OUTDIR/shifted.map" \
    @"$OBJECTS_LST" \
    -R "$BANIM_SYM" \
    -L "$libgcc_dir" \
    -L "$libc_dir" \
    -o "$OUTDIR/shifted.elf" \
    -lc -lnosys -lgcc \
    || die "shifted link failed"

# --- Convert to ROM ---
printf 'Converting to ROM...\n'
"$OBJCOPY" --strip-debug -O binary --pad-to "$PAD_TO" --gap-fill=0xff \
    "$OUTDIR/shifted.elf" "$OUTDIR/shifted.gba" \
    || die "objcopy failed"

# --- Verify layout and ROM identity ---
python3 scripts/shiftcheck/verify_shifted_layout.py \
    --base-elf "$BASE_ELF" \
    --shifted-elf "$OUTDIR/shifted.elf" \
    --shift "$SHIFT" \
    --nm "$NM" ||
    die "shifted layout verification failed"

python3 scripts/modernize/verify_rom_header.py \
    --size "$ROM_SIZE_NAME" "$OUTDIR/shifted.gba" ||
    die "shifted ROM header verification failed"

# --- Verify boot and title behavior ---
# SHIFTCHECK_SRAM_IMAGE (issue #18 sprint 4): optional path to an exact
# 0x8000-byte raw SRAM image loaded before frame 0, for scenarios that
# require a specific starting save state (e.g. a synthetic
# ExpansionUserPrefs fixture) rather than this backend's own default/blank
# SRAM. Unset by default -- every pre-existing caller (BOOT/TITLE, and any
# SHIFTCHECK_SCENARIO override that does not set it) is completely
# unaffected and keeps booting from the backend's default SRAM exactly as
# before.
verify_scenario()
{
    label=$1
    scenario=$2
    expected=$3
    sram_image=${4:-}

    [ -f "$scenario" ] || die "missing scenario: $scenario"
    [ -f "$expected" ] || die "missing fingerprint: $expected"

    printf 'Verifying shifted %s behavior (shift=%s)...\n' "$label" "$SHIFT"
    if ! python3 tools/gba-playtest/gba_playtest.py verify \
        --rom "$OUTDIR/shifted.gba" \
        --scenario "$scenario" \
        --expected "$expected" \
        ${sram_image:+--sram-image "$sram_image"} \
        --policy behavior
    then
        printf 'SHIFTED %s: FAIL (shift=%s)\n' "$label" "$SHIFT" >&2
        return 1
    fi

    printf 'SHIFTED %s: PASS (shift=%s)\n' "$label" "$SHIFT"
}

if [ -n "${SHIFTCHECK_SCENARIO:-}" ] || [ -n "${SHIFTCHECK_EXPECTED:-}" ]; then
    [ -n "${SHIFTCHECK_SCENARIO:-}" ] &&
        [ -n "${SHIFTCHECK_EXPECTED:-}" ] ||
        die "SHIFTCHECK_SCENARIO and SHIFTCHECK_EXPECTED must be set together"
    verify_scenario "SCENARIO" "$SHIFTCHECK_SCENARIO" "$SHIFTCHECK_EXPECTED" \
        "${SHIFTCHECK_SRAM_IMAGE:-}" ||
        exit 1
else
    verify_scenario \
        "BOOT" \
        "tools/gba-playtest/scenarios/boot.json" \
        "tools/gba-playtest/fingerprints/boot.json" ||
        exit 1
    verify_scenario \
        "TITLE" \
        "tools/gba-playtest/scenarios/title-progression.json" \
        "${SHIFTCHECK_TITLE_EXPECTED:-tools/gba-playtest/fingerprints/title-progression-modern-debug.json}" ||
        exit 1
fi

exit 0
