#ifndef GUARD_SAVE_FORMAT_H
#define GUARD_SAVE_FORMAT_H

/*
 * Expansion save-format foundation (issue #2 slice 1).
 *
 * This header declares the on-media ExpansionSaveMeta record that lives in
 * the previously-unused 0x5C-byte pad at SRAM offset 0x73A4 (struct
 * SaveBlocks, include/bmsave.h) plus the raw-byte compatibility classifier
 * that inspects only the global save header and this metadata record --
 * never any current save-block struct -- before deciding whether SRAM
 * contents may be safely auto-initialized.
 *
 * All actual function bodies live in src/bmsave-lib.c (already linked by
 * both the legacy and modern builds) so that adding this header never
 * requires new ldscript.txt/modern.mk object wiring. This header itself
 * only declares fixed-width types, so it is safe to include from any
 * translation unit that already includes bmsave.h.
 *
 * See docs/save_format.md for the full on-media format, the
 * compatibility-vs-diagnostic field split rationale, and the destructive
 * wipe policy.
 */

#include "global.h"

struct GlobalSaveInfo;

/* Not NUL-terminated; compared byte-for-byte. */
#define EXPANSION_SAVE_META_MAGIC "FSAV"
#define EXPANSION_SAVE_META_MAGIC_SIZE 4

/* Current on-media save-format version. Bump together with
 * FE8_EXPANSION_SAVE_COMPAT_EPOCH (include/expansion_config.h) whenever a
 * save-layout/serialization change is made -- see docs/save_format.md.
 *
 * Bumped 1 -> 2 for issue #18 sprint 2: struct ExpansionUserPrefs
 * (include/expansion_save_prefs.h) now occupies a fixed sub-region of
 * this struct's `reserved` tail below. This is a conservative bump, not
 * a strictly-required one -- the sub-record carries its own independent
 * magic/version/checksum and treats a zeroed reserved tail (every
 * pre-sprint-2 build's deterministic output) as EXPANSION_USER_PREFS_UNSET
 * rather than corrupt, so a pre-sprint-2 build's saves already parse
 * safely under the new logic and a post-sprint-2 build's saves are
 * simply ignored (never misread) by a pre-sprint-2 build. The version
 * is still bumped per this project's stated policy of bumping on any
 * save-layout/serialization change to this struct, however additive. */
#define SAVE_FORMAT_VERSION_CURRENT 2

/* Diagnostic-only: which ABI produced this save. Never gates
 * compatibility -- see docs/save_format.md. */
enum SaveAbiId {
    SAVE_ABI_ID_APCS_GNU = 0,
    SAVE_ABI_ID_AAPCS = 1
};

/*
 * Fixed-width, explicit-endianness (native GBA little-endian), zero
 * implicit padding. Every byte of the 0x5C-byte pad is accounted for by a
 * named field, so sizeof(struct ExpansionSaveMeta) == 0x5C exactly and it
 * can directly replace the old `_pad_` field in struct SaveBlocks without
 * shifting include/bmsave.h's `xmap` field, or any other existing offset.
 *
 * Compatibility gates: magic, formatVersion, compatEpoch.
 * Diagnostics only (never gate compatibility): abiId, frameworkVersionPacked,
 * configFingerprint, buildCommitShort. See docs/save_format.md.
 */
struct ExpansionSaveMeta {
    /* 0x00 */ u8 magic[EXPANSION_SAVE_META_MAGIC_SIZE];
    /* 0x04 */ u8 formatVersion;
    /* 0x05 */ STRUCT_PAD(0x05, 0x06);
    /* 0x06 */ u16 compatEpoch;
    /* 0x08 */ u8 abiId;
    /* 0x09 */ STRUCT_PAD(0x09, 0x0C);
    /* 0x0C */ u32 frameworkVersionPacked;
    /* 0x10 */ char configFingerprint[17]; /* 16 hex chars + NUL */
    /* 0x21 */ STRUCT_PAD(0x21, 0x24);
    /* 0x24 */ char buildCommitShort[9]; /* 8 hex chars + NUL */
    /* 0x2D */ STRUCT_PAD(0x2D, 0x2E);
    /* 0x2E */ u16 checksum; /* Checksum16() over bytes [0x00, 0x2E) */
    /* 0x30 */ u8 reserved[0x5C - 0x30]; /* reserved for future fields --
                                             * bytes [0x30, 0x30 +
                                             * EXPANSION_USER_PREFS_SIZE)
                                             * are struct ExpansionUserPrefs
                                             * (include/expansion_save_prefs.h,
                                             * issue #18 sprint 2); the
                                             * remainder stays reserved. */
}; /* size = 0x5C */

/* Number of leading bytes of struct ExpansionSaveMeta covered by its own
 * checksum field (everything strictly before the checksum itself). */
#define EXPANSION_SAVE_META_SIZE_FOR_CHECKSUM 0x2E

/*
 * Raw-byte save compatibility classification. All non-EMPTY states are
 * decided from only the global save header (struct GlobalSaveInfo) and this
 * metadata record -- never by interpreting any current save-block struct.
 * Live EMPTY detection additionally verifies the remaining SRAM as opaque
 * bytes before any block is touched. See docs/save_format.md.
 */
enum SaveCompatState {
    /* Live SRAM has one uniform erased fill (hardware-style 0xFF or
     * deterministic emulator/movie-style 0x00), excluding only SramInit's
     * four-byte hardware probe. This is the ONLY state that may trigger an
     * automatic full-SRAM wipe/initialize. */
    SAVE_COMPAT_EMPTY,

    /* Global header is valid (name/magic32/magic16/checksum all check out)
     * but the metadata record's magic is absent. Covers both true vanilla
     * FE8 saves and legacy expansion saves written before this slice. */
    SAVE_COMPAT_VALID_LEGACY_OR_VANILLA,

    /* Global header itself fails validation (bad name/magic/checksum) and
     * is not the documented blank pattern either. */
    SAVE_COMPAT_HEADER_CORRUPT,

    /* Global header is valid but the metadata record's own checksum does
     * not match its contents. */
    SAVE_COMPAT_METADATA_CORRUPT,

    /* Global header and metadata are both valid, and formatVersion/
     * compatEpoch exactly match the current build. */
    SAVE_COMPAT_CURRENT,

    /* Valid metadata whose formatVersion is older than current -- may be
     * migratable by the host-side tool (scripts/modernize/save_format_tool.py). */
    SAVE_COMPAT_MIGRATABLE_OLDER,

    /* Valid metadata whose formatVersion is newer than this build knows
     * how to interpret. */
    SAVE_COMPAT_NEWER_UNSUPPORTED,

    /* Valid metadata at the current formatVersion, but compatEpoch does not
     * match FE8_EXPANSION_SAVE_COMPAT_EPOCH. */
    SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE
};

/* Builds a fully-populated, current, checksummed ExpansionSaveMeta record
 * from this build's FE8_EXPANSION_* configuration. Never touches SRAM. */
void BuildCurrentExpansionSaveMeta(struct ExpansionSaveMeta *meta);

/* Recomputes and returns the checksum for the given metadata record
 * (mirrors Checksum16(meta, EXPANSION_SAVE_META_SIZE_FOR_CHECKSUM)). */
u16 ExpansionSaveMetaChecksum(struct ExpansionSaveMeta const *meta);

/* Pure classifier: decides compatibility from an already-read header and
 * metadata pair plus whether each raw region is uniformly erased (hardware
 * 0xFF or deterministic emulator/movie 0x00). Does not touch SRAM. Its
 * blank flags are trusted inputs; destructive live callers must use
 * ClassifySramSaveCompat(), which verifies the complete chip first. */
enum SaveCompatState ClassifySaveCompatRaw(
    struct GlobalSaveInfo const *header,
    bool headerRegionBlank,
    struct ExpansionSaveMeta const *meta,
    bool metaRegionBlank);

/* Reads live SRAM and classifies it. EMPTY requires one uniform fill across
 * the complete chip except SramInit's four-byte probe. If SRAM is not
 * confirmed working (IsSramWorking() == false), conservatively returns
 * SAVE_COMPAT_HEADER_CORRUPT rather than risking an automatic wipe. */
enum SaveCompatState ClassifySramSaveCompat(void);

#endif /* GUARD_SAVE_FORMAT_H */
