#include "global.h"
#include "expansion_metadata.h"

/*
 * The embedded expansion framework metadata record (see
 * include/expansion_metadata.h). Populated entirely from the
 * FE8_EXPANSION_* macros (include/expansion_config.h), which the modern
 * build supplies via `-D` command-line defines derived from config.mk and
 * MODERN_CONFIG/MODERN_ABI/MODERN_ROM_SIZE (see modern.mk). Uses
 * positional (not designated) initialization for C89/agbcc compatibility.
 *
 * This file is picked up (compiled) by both the legacy and modern C
 * source globs, but is only linked into the modern ROM: linker/expansion.ld
 * pulls in every object's .rodata via a generic wildcard rule, while
 * ldscript.txt (legacy) only links objects it lists explicitly, and does
 * not list this one.
 */
const struct ExpansionMetadata gExpansionMetadata =
{
    /* magic: individual chars, not the EXPANSION_METADATA_MAGIC string
     * literal, so the trailing NUL of the literal is never truncated
     * into (or missing from) this non-NUL-terminated 4-byte field. */
    { 'F', 'E', '8', 'M' },
    FE8_EXPANSION_VERSION_MAJOR,
    FE8_EXPANSION_VERSION_MINOR,
    FE8_EXPANSION_VERSION_PATCH,
    0,
    FE8_EXPANSION_VERSION_PACKED,
    FE8_EXPANSION_VERSION_STRING,
    FE8_EXPANSION_BUILD_COMMIT,
    FE8_EXPANSION_CONFIG_FINGERPRINT,
    FE8_EXPANSION_CONFIG_PRESET,
    FE8_EXPANSION_ABI,
    FE8_EXPANSION_ROM_TITLE,
    FE8_EXPANSION_ROM_GAME_CODE,
    FE8_EXPANSION_ROM_MAKER_CODE,
    FE8_EXPANSION_ROM_REVISION,
    FE8_EXPANSION_ROM_SIZE_BYTES,
    FE8_EXPANSION_ENABLED_LOCALE_MASK,
    FE8_EXPANSION_DEFAULT_LOCALE_ID,
    FE8_EXPANSION_PSEUDO_LOCALE_ENABLED,
    { 0, 0 }
};
