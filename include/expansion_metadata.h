#ifndef GUARD_EXPANSION_METADATA_H
#define GUARD_EXPANSION_METADATA_H

/*
 * Embedded expansion framework metadata record (issue #8).
 *
 * A `const struct ExpansionMetadata` instance (see
 * src/expansion_metadata.c) is compiled into every modern ROM's .rodata,
 * so the ROM itself unambiguously exposes its framework magic, semantic
 * version, build commit, config fingerprint/preset/ABI, and configured
 * ROM identity -- independent of any build log or generated file that
 * never makes it into the ROM. scripts/modernize/verify_rom_header.py
 * locates this record by scanning for MAGIC and verifies its fields
 * against the same generated expansion_build_metadata.json used to build
 * the ROM (see scripts/modernize/expansion_config.py).
 *
 * Field sizes are chosen so the struct has zero implicit compiler padding
 * (every multi-byte field falls on its natural alignment boundary); this
 * exact layout is mirrored by verify_rom_header.py's
 * EXPANSION_METADATA_STRUCT format string -- keep the two in sync.
 */

#define EXPANSION_METADATA_MAGIC "FE8M"
#define EXPANSION_METADATA_MAGIC_SIZE 4

#define EXPANSION_METADATA_VERSION_STRING_SIZE 16
#define EXPANSION_METADATA_BUILD_COMMIT_SIZE 41
#define EXPANSION_METADATA_CONFIG_FINGERPRINT_SIZE 17
#define EXPANSION_METADATA_CONFIG_PRESET_SIZE 8
#define EXPANSION_METADATA_ABI_SIZE 12
#define EXPANSION_METADATA_ROM_TITLE_SIZE 13
#define EXPANSION_METADATA_ROM_GAME_CODE_SIZE 5
#define EXPANSION_METADATA_ROM_MAKER_CODE_SIZE 3

struct ExpansionMetadata
{
    /* 00 */ u8 magic[EXPANSION_METADATA_MAGIC_SIZE]; /* "FE8M", not NUL-terminated */
    /* 04 */ u8 versionMajor;
    /* 05 */ u8 versionMinor;
    /* 06 */ u8 versionPatch;
    /* 07 */ u8 reserved0;
    /* 08 */ u32 versionPacked;
    /* 0C */ char versionString[EXPANSION_METADATA_VERSION_STRING_SIZE];
    /* 1C */ char buildCommit[EXPANSION_METADATA_BUILD_COMMIT_SIZE];
    /* 45 */ char configFingerprint[EXPANSION_METADATA_CONFIG_FINGERPRINT_SIZE];
    /* 56 */ char configPreset[EXPANSION_METADATA_CONFIG_PRESET_SIZE];
    /* 5E */ char abi[EXPANSION_METADATA_ABI_SIZE];
    /* 6A */ char romTitle[EXPANSION_METADATA_ROM_TITLE_SIZE];
    /* 77 */ char romGameCode[EXPANSION_METADATA_ROM_GAME_CODE_SIZE];
    /* 7C */ char romMakerCode[EXPANSION_METADATA_ROM_MAKER_CODE_SIZE];
    /* 7F */ u8 romRevision;
    /* 80 */ u32 romSizeBytes;
    /* Locale identity (issue #18 sprint 1) -- see
     * include/expansion_config.h's FE8_EXPANSION_ENABLED_LOCALE_MASK/
     * FE8_EXPANSION_DEFAULT_LOCALE_ID/FE8_EXPANSION_PSEUDO_LOCALE_ENABLED
     * and include/expansion_locale.h's ExpansionLocaleId. Appended after
     * every issue #8 field (append-only, version-safe: this addition
     * neither moves nor resizes any existing field, so it cannot break
     * scripts/modernize/verify_rom_header.py's MAGIC-based scanner or any
     * already-built ROM's existing metadata layout expectations). */
    /* 84 */ u32 enabledLocaleMask;
    /* 88 */ u8 defaultLocale;
    /* 89 */ u8 pseudoLocaleEnabled;
    /* 8A */ u8 reserved1[2];
}; /* size: 0x8C */

extern const struct ExpansionMetadata gExpansionMetadata;

#endif /* GUARD_EXPANSION_METADATA_H */
