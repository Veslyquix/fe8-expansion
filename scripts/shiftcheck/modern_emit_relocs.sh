#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
. "$script_dir/modern_toolchain.sh"

default_out="$repo_root/build/shiftcheck/modern_relocs.elf"
if [ "$#" -gt 0 ] && [ "${1#-}" = "$1" ]; then
    out="$1"
    shift
else
    out="$default_out"
fi

case "$out" in
    *.elf) map_out="${out%.elf}.map" ;;
    *) map_out="$out.map" ;;
esac

PREFIX=${PREFIX:-arm-none-eabi-}
CC=$(shiftcheck_resolve_tool \
    "${MODERN_CC:-${CC:-${PREFIX}gcc}}" "$repo_root" "${PREFIX}gcc") ||
    {
        printf 'error: cannot resolve modern compiler\n' >&2
        exit 1
    }
LD=$(shiftcheck_resolve_tool \
    "${MODERN_LD:-${LD:-${PREFIX}ld}}" "$repo_root" "${PREFIX}ld") ||
    {
        printf 'error: cannot resolve modern linker\n' >&2
        exit 1
    }
OBJECTS_LST=${OBJECTS_LST:-$repo_root/build/expansion-modern/debug/aapcs/link/objects.lst}
BANIM_SYM=${BANIM_SYM:-$repo_root/banim/data_banim.modern.o.sym.o}
LDSCRIPT=${LDSCRIPT:-$repo_root/linker/expansion.ld}
ROM_SIZE_BYTES=${ROM_SIZE_BYTES:-0x01000000}
TEXT_SHIFT=${TEXT_SHIFT:-0}
# Must match modern.mk's MODERN_BANIM_DATA_BASE, which banim/data_banim.modern.o
# (see BANIM_SYM above) is pre-linked against -- see linker/expansion.ld's
# __banim_data_base_abs placement for why this can't just be any value.
BANIM_DATA_BASE=${BANIM_DATA_BASE:-0x08ca0000}

for path in "$OBJECTS_LST" "$BANIM_SYM" "$LDSCRIPT"; do
    if [ ! -f "$path" ]; then
        printf 'error: required input missing: %s\n' "$path" >&2
        exit 1
    fi
done

libgcc_dir=$(shiftcheck_libgcc_dir "$CC") || {
    printf 'error: cannot discover libgcc via %s\n' "$CC" >&2
    exit 1
}

libc_dir=$(shiftcheck_newlib_dir "$CC" "${MODERN_NEWLIB_LIB:-}") || {
    printf 'error: cannot discover libc.a via %s\n' "$CC" >&2
    printf 'Set MODERN_NEWLIB_LIB to the directory containing libc.a.\n' >&2
    exit 1
}

mkdir -p "$(dirname -- "$out")"

exec "$LD" \
    --orphan-handling=error \
    --defsym=__rom_size="$ROM_SIZE_BYTES" \
    --defsym=__text_shift="$TEXT_SHIFT" \
    --defsym=__banim_data_base_abs="$BANIM_DATA_BASE" \
    -T "$LDSCRIPT" \
    -Map "$map_out" \
    @"$OBJECTS_LST" \
    -R "$BANIM_SYM" \
    -L "$libgcc_dir" \
    -L "$libc_dir" \
    -q \
    -o "$out" \
    -lc -lnosys -lgcc \
    "$@"
