#ifndef GUARD_MAPGEN_SAVE_SEED_H
#define GUARD_MAPGEN_SAVE_SEED_H

/*
 * Persisted FE8_MAPGEN generation seed: the per-save record of the u32 seed
 * MapGen_SessionSeed() (src/mapgen.c) rolls from boot-elapsed frames + live
 * controller state the first time a save needs one. Sibling record to
 * struct ExpansionUserPrefs (include/expansion_save_prefs.h, issue #18
 * sprint 2) -- same reserved-tail placement strategy, same
 * magic/version/reserved/checksum shape, same no-wipe contract -- placed
 * immediately after it rather than duplicating its own space.
 *
 * struct MapGenSaveSeed lives at a fixed byte offset
 * (MAPGEN_SAVE_SEED_META_OFFSET) inside struct ExpansionSaveMeta's
 * `reserved` tail (include/save_format.h) -- i.e. its absolute SRAM offset
 * is SRAM_OFFSET_EXPANSION_SAVE_META + 0x30 + MAPGEN_SAVE_SEED_META_OFFSET.
 * This does NOT move SRAM_OFFSET_EXPANSION_SAVE_META, struct
 * ExpansionSaveMeta's own size/checksum domain, struct ExpansionUserPrefs'
 * own offset/size, or any neighboring struct SaveBlocks field -- see
 * scripts/modernize/tests/test_save_format_layout.py, which probes this
 * record the same way it already probes ExpansionUserPrefs.
 *
 * Deliberately NOT gated behind #if FE8_MAPGEN: like ExpansionUserPrefs, the
 * on-disk layout has to stay identical and testable across every build
 * configuration regardless of which FE8_* features happen to be enabled
 * (compare include/save_format.h's own file comment) -- only the runtime
 * code that actually calls MapGenSaveSeed_Load/Store (src/mapgen.c) is
 * feature-gated. Implementation lives in src/bmsave-lib.c, already linked by
 * both the legacy and modern builds, so this header needs no new
 * ldscript.txt/modern.mk object wiring.
 *
 * There is no analogue to ExpansionUserPrefs' "unknown/disabled locale"
 * states here -- a seed has no enable/disable dimension -- so
 * MapGenSaveSeedState only distinguishes UNSET / CORRUPT / VALID.
 *
 * No-wipe contract: every function here never calls WipeSram() or otherwise
 * touches any byte outside this record's own fixed
 * MAPGEN_SAVE_SEED_META_OFFSET..+sizeof(struct MapGenSaveSeed) window. An
 * unset (all-zero -- BuildCurrentExpansionSaveMeta()'s memset() already
 * zeroes this record on every brand-new save, the same way it leaves every
 * other not-yet-assigned byte of `reserved` zeroed) or all-0xFF (the
 * documented blank-SRAM fill pattern) record classifies as
 * MAPGEN_SAVE_SEED_UNSET, never CORRUPT.
 */

#include "global.h"
#include "expansion_save_prefs.h"
#include "save_format.h"

/* Distinct from EXPANSION_USER_PREFS_MAGIC (0xA5) and both legacy "unset"
 * fill patterns (0x00 and 0xFF), so neither is ever misread as CORRUPT. */
#define MAPGEN_SAVE_SEED_MAGIC 0x5Du

#define MAPGEN_SAVE_SEED_VERSION_CURRENT 1u

/*
 * Fixed-width, explicit-endianness, zero implicit padding among the named
 * fields. ALIGN(4) for the same cross-compiler size-agreement reason as
 * struct ExpansionUserPrefs (see that struct's own comment): the unpadded
 * size here (8 named-field bytes + 2-byte checksum = 0x0A) is not a
 * multiple of 4.
 */
struct MapGenSaveSeed {
    /* 0x00 */ u8 magic;
    /* 0x01 */ u8 version;
    /* 0x02 */ u8 reserved[2]; /* reserved for near-future fields; always 0 */
    /* 0x04 */ u32 seed;
    /* 0x08 */ u16 checksum;   /* Checksum16() over bytes [0x00, 0x08) */
} ALIGN(4); /* size = 0x0C */

/* Number of leading bytes of struct MapGenSaveSeed covered by its own
 * checksum field. */
#define MAPGEN_SAVE_SEED_SIZE_FOR_CHECKSUM 0x08

/* Fixed byte offset of struct MapGenSaveSeed within struct
 * ExpansionSaveMeta's `reserved` tail -- right after struct
 * ExpansionUserPrefs, not at a separately-chosen offset, so the two records
 * can never be made to overlap by an independent edit to either one. */
#define MAPGEN_SAVE_SEED_META_OFFSET (EXPANSION_USER_PREFS_META_OFFSET + 0x0C)

/* Compile-time headroom left in the reserved tail after both records.
 * Mirrors EXPANSION_SAVE_META_RESERVED_HEADROOM_BYTES; must never go
 * negative, proven by test_save_format_layout.py's probe. */
#define MAPGEN_SAVE_SEED_RESERVED_HEADROOM_BYTES \
    (EXPANSION_SAVE_META_RESERVED_SIZE - MAPGEN_SAVE_SEED_META_OFFSET - 0x0C)

enum MapGenSaveSeedState {
    /* Every byte of the record is 0x00 (BuildCurrentExpansionSaveMeta()'s
     * deterministic "never written" pattern) or every byte is 0xFF (the
     * documented blank-SRAM fill pattern). Either way: no seed has ever
     * been rolled for this save. */
    MAPGEN_SAVE_SEED_UNSET,

    /* magic mismatch (and not the UNSET blank pattern above), the record's
     * own checksum does not match, or a version newer than
     * MAPGEN_SAVE_SEED_VERSION_CURRENT. */
    MAPGEN_SAVE_SEED_CORRUPT,

    /* magic/checksum/version all valid: the seed field is trustworthy. */
    MAPGEN_SAVE_SEED_VALID
};

/* Builds a fully-populated, current, checksummed MapGenSaveSeed record
 * in-memory. Never touches SRAM. */
void MapGenSaveSeed_Build(struct MapGenSaveSeed *rec, u32 seed);

/* Recomputes and returns the checksum for the given record (mirrors
 * Checksum16(rec, MAPGEN_SAVE_SEED_SIZE_FOR_CHECKSUM)). */
u16 MapGenSaveSeedChecksum(struct MapGenSaveSeed const *rec);

/* Pure classifier: decides state from an already-read record plus whether
 * its raw byte region is either documented "unset" pattern. Does not touch
 * SRAM. */
enum MapGenSaveSeedState MapGenSaveSeed_ValidateRaw(struct MapGenSaveSeed const *rec, bool8 regionUnset);

/* Reads the live SRAM record (from within gSram->expansionSaveMeta.reserved)
 * and classifies it. If SRAM is not confirmed working (IsSramWorking() ==
 * false) this conservatively returns MAPGEN_SAVE_SEED_CORRUPT rather than
 * UNSET. `out` (if non-NULL) always receives the raw record read,
 * regardless of state. */
enum MapGenSaveSeedState MapGenSaveSeed_Load(struct MapGenSaveSeed *out);

/* Builds a fresh record for `seed` and performs exactly one bounded
 * WriteAndVerifySramFast() call covering only this record's own
 * MAPGEN_SAVE_SEED_META_OFFSET..+sizeof(...) window inside
 * gSram->expansionSaveMeta.reserved -- never WipeSram(), never any other
 * SRAM byte. Returns FALSE (writing nothing) if SRAM is not confirmed
 * working; otherwise returns whether the write verified successfully. */
bool8 MapGenSaveSeed_Store(u32 seed);

#endif /* GUARD_MAPGEN_SAVE_SEED_H */
