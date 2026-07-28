#ifndef GUARD_EXPANSION_SAVE_PREFS_H
#define GUARD_EXPANSION_SAVE_PREFS_H

/*
 * Versioned/checksummed expansion user save preferences (issue #18
 * sprint 2): the persisted, per-save record of the player's own locale
 * selection, distinct from -- and never derived from -- the build-time
 * locale configuration (FE8_EXPANSION_DEFAULT_LOCALE_ID/
 * FE8_EXPANSION_ENABLED_LOCALE_MASK, include/expansion_config.h) or the
 * runtime resolver's in-memory current locale (src/expansion_locale.c).
 *
 * struct ExpansionUserPrefs lives at a fixed byte offset
 * (EXPANSION_USER_PREFS_META_OFFSET) inside struct ExpansionSaveMeta's
 * previously-fully-unused `reserved` tail (include/save_format.h) --
 * i.e. its absolute SRAM offset is
 * SRAM_OFFSET_EXPANSION_SAVE_META + 0x30 + EXPANSION_USER_PREFS_META_OFFSET.
 * This does NOT move SRAM_OFFSET_EXPANSION_SAVE_META, struct
 * ExpansionSaveMeta's own size (0x5C) or its 0x00-0x2F named-field
 * layout/checksum domain, or any neighboring struct SaveBlocks field
 * (in particular `xmap`) -- see docs/save_format.md and
 * scripts/modernize/tests/test_save_format_layout.py.
 *
 * struct ExpansionSaveMeta's own checksum only covers bytes [0x00, 0x2E)
 * (EXPANSION_SAVE_META_SIZE_FOR_CHECKSUM) and therefore never covers this
 * record -- it carries its own independent magic/version/checksum so it
 * can be validated (and migrated) on its own, exactly like
 * ExpansionSaveMeta itself is validated independently of the vanilla
 * struct GlobalSaveInfo header. See EXPANSION_USER_PREFS_SIZE_FOR_CHECKSUM
 * below.
 *
 * No-wipe contract: every function below that classifies or reads an
 * on-disk record NEVER calls WipeSram() (src/bmsave-lib.c) or otherwise
 * touches any byte outside this record's own fixed
 * EXPANSION_USER_PREFS_META_OFFSET..+sizeof(struct ExpansionUserPrefs)
 * window. An unset (all-zero -- every pre-sprint-2 "current" save's
 * reserved tail was always deterministically zeroed by
 * BuildCurrentExpansionSaveMeta(), never left as uninitialized garbage --
 * see src/bmsave-lib.c) or all-0xFF (the documented blank-SRAM fill
 * pattern) record classifies as EXPANSION_USER_PREFS_UNSET, never
 * CORRUPT; an unknown/disabled locale id or a checksum mismatch never
 * triggers any SRAM mutation, only a runtime fallback + "requires
 * prompt" signal (see ExpansionUserPrefs_Normalize below).
 *
 * All Build/Checksum/ValidateRaw/Load/Normalize functions here are pure
 * struct-and-macro logic (no expansion_locale.c symbol references), so
 * this header/its bmsave-lib.c implementation compiles AND links under
 * both the legacy agbcc build and every modern build cell, exactly like
 * include/save_format.h. Only ExpansionUserPrefs_Store (which must call
 * ExpansionLocale_SetCurrent()/ExpansionLocale_InvalidateCache() to keep
 * the runtime resolver's cache coherent with what was just persisted) is
 * implemented in src/expansion_save_prefs.c, which -- like
 * src/expansion_locale.c -- is compiled by both builds (agbcc must be
 * able to typecheck it) but only linked into the modern ROM (see
 * ldscript.txt's explicit legacy object list, which names neither file,
 * and modern.mk's `wildcard src/*.c`).
 */

#include "global.h"
#include "expansion_locale.h"
#include "save_format.h"

/* Distinct from both a never-written-since-sprint-2 zeroed reserved tail
 * (0x00) and the documented blank-SRAM fill pattern (0xFF), so either
 * legacy state is unambiguously "no preference recorded yet" rather than
 * "corrupt". */
#define EXPANSION_USER_PREFS_MAGIC 0xA5u

/* Current on-media version of struct ExpansionUserPrefs itself. Bump
 * together with a layout/semantic change to this struct specifically
 * (independent of SAVE_FORMAT_VERSION_CURRENT/FE8_EXPANSION_SAVE_COMPAT_EPOCH,
 * which gate the outer ExpansionSaveMeta record) -- see
 * ExpansionUserPrefs_ValidateRaw's version handling below. */
#define EXPANSION_USER_PREFS_VERSION_CURRENT 1u

/* flags bit 0: the player explicitly chose this locale (via a future
 * settings UI); unset means this record was auto-populated with the
 * build's configured default (e.g. by a brand-new save or a migrated
 * older save) and no explicit choice has been made yet. Bits 1-7 are
 * reserved and must always be written as 0. */
#define EXPANSION_USER_PREFS_FLAG_LOCALE_EXPLICIT 0x01u

/*
 * Fixed-width, explicit-endianness (native GBA little-endian), zero
 * implicit padding among the named fields. ALIGN(4) is required for
 * cross-compiler layout agreement (same class of divergence documented
 * at struct BonusClaimSaveData, include/bmsave.h): this struct's
 * unpadded size (8 named-field bytes + 2-byte checksum = 0x0A) is not a
 * multiple of 4, so legacy agbcc's always-round-to-4 struct-size
 * convention would otherwise disagree with AAPCS-conformant modern GCC's
 * round-to-own-natural-alignment (2, from checksum) convention --
 * ALIGN(4) forces both compilers to agree on sizeof == 0x0C. This
 * matters here even though the struct is only ever accessed via an
 * explicit byte offset/memcpy into struct ExpansionSaveMeta's `reserved`
 * array (never as a named field of that struct), because the exact same
 * struct type/size is used to size the ReadSramFast()/
 * WriteAndVerifySramFast() calls in both the legacy and modern builds --
 * see scripts/modernize/tests/test_save_format_layout.py.
 */
struct ExpansionUserPrefs {
    /* 0x00 */ u8 magic;
    /* 0x01 */ u8 version;
    /* 0x02 */ u8 localeId;    /* ExpansionLocaleId (include/expansion_locale.h) */
    /* 0x03 */ u8 flags;       /* EXPANSION_USER_PREFS_FLAG_* bits */
    /* 0x04 */ u8 reserved[4]; /* reserved for near-future fields; always 0 */
    /* 0x08 */ u16 checksum;   /* Checksum16() over bytes [0x00, 0x08) */
} ALIGN(4); /* size = 0x0C (agbcc rounds the unpadded 0x0A up to a 4-byte multiple) */

/* Number of leading bytes of struct ExpansionUserPrefs covered by its own
 * checksum field (everything strictly before the checksum itself) --
 * mirrors EXPANSION_SAVE_META_SIZE_FOR_CHECKSUM's naming/role. */
#define EXPANSION_USER_PREFS_SIZE_FOR_CHECKSUM 0x08

/* Fixed byte offset of struct ExpansionUserPrefs within struct
 * ExpansionSaveMeta's `reserved` tail (include/save_format.h). Currently
 * 0 -- prefs occupies the very first bytes of that tail. */
#define EXPANSION_USER_PREFS_META_OFFSET 0

/* Size, in bytes, of struct ExpansionSaveMeta's `reserved` tail itself
 * (0x5C - 0x30); duplicated here as a literal (rather than
 * sizeof(((struct ExpansionSaveMeta *)0)->reserved), which is not a
 * valid constant-expression operand for a preprocessor-evaluated macro)
 * so EXPANSION_SAVE_META_RESERVED_HEADROOM_BYTES below can be computed
 * at compile time; scripts/modernize/tests/test_save_format_layout.py
 * cross-checks this literal against the real struct's sizeof/offsetof. */
#define EXPANSION_SAVE_META_RESERVED_SIZE 0x2C

/* Compile-time headroom left in ExpansionSaveMeta's reserved tail after
 * ExpansionUserPrefs -- reported so a future field added to `reserved`
 * knows its budget without recomputing this by hand. Must never go
 * negative; proven by test_save_format_layout.py's probe. */
#define EXPANSION_SAVE_META_RESERVED_HEADROOM_BYTES \
    (EXPANSION_SAVE_META_RESERVED_SIZE - EXPANSION_USER_PREFS_META_OFFSET - 0x0C)

/*
 * Classification of an on-disk (or synthetic, for tests) struct
 * ExpansionUserPrefs record. Never gates SRAM mutation on its own --
 * only ExpansionUserPrefs_Store (src/expansion_save_prefs.c) ever writes
 * this record, and only after validating the locale it is about to
 * persist is itself supported+enabled.
 */
enum ExpansionUserPrefsState {
    /* Every byte of the record is 0x00 (this build's/every pre-sprint-2
     * build's deterministic "never written" pattern -- see
     * BuildCurrentExpansionSaveMeta(), src/bmsave-lib.c) or every byte is
     * 0xFF (the documented blank-SRAM fill pattern, WipeSram()). Either
     * way: no preference has ever been recorded. */
    EXPANSION_USER_PREFS_UNSET,

    /* magic mismatch (and not the UNSET blank pattern above), or magic
     * matches but the record's own checksum does not, or a formatVersion
     * newer than EXPANSION_USER_PREFS_VERSION_CURRENT (this build cannot
     * safely interpret a future version's semantics). */
    EXPANSION_USER_PREFS_CORRUPT,

    /* magic/checksum/version all valid, but localeId is not one of the
     * EXPANSION_LOCALE_COUNT stable slots (include/expansion_locale.h) --
     * e.g. a save carried forward from a build with more locale slots
     * than this one knows about. */
    EXPANSION_USER_PREFS_UNKNOWN_LOCALE,

    /* magic/checksum/version all valid and localeId is a supported slot,
     * but this build's FE8_EXPANSION_ENABLED_LOCALE_MASK does not enable
     * it (e.g. a locale was disabled after the player selected it). */
    EXPANSION_USER_PREFS_DISABLED_LOCALE,

    /* magic/checksum valid, version is older than
     * EXPANSION_USER_PREFS_VERSION_CURRENT, and localeId is supported+
     * enabled: a well-formed older-version record this build accepts
     * and treats as forward-compatible (this struct's field layout has
     * not changed since version 1, so no in-place field transform is
     * needed yet; the version check exists so a future incompatible
     * layout change has somewhere safe to branch from). */
    EXPANSION_USER_PREFS_MIGRATED,

    /* magic/checksum/version all valid, current version, localeId
     * supported and enabled: fully trustworthy, no fallback needed. */
    EXPANSION_USER_PREFS_VALID
};

/* Builds a fully-populated, current, checksummed ExpansionUserPrefs
 * record in-memory. Never touches SRAM. `explicitSelection` should be
 * FALSE for an auto-populated default (new save / migrated older save)
 * and TRUE only when the player actually chose `localeId` themselves. */
void ExpansionUserPrefs_Build(struct ExpansionUserPrefs *prefs, ExpansionLocaleId localeId, bool8 explicitSelection);

/* Recomputes and returns the checksum for the given record (mirrors
 * Checksum16(prefs, EXPANSION_USER_PREFS_SIZE_FOR_CHECKSUM)). */
u16 ExpansionUserPrefsChecksum(struct ExpansionUserPrefs const *prefs);

/* Pure classifier: decides state from an already-read record plus
 * whether its raw byte region is either documented "unset" pattern
 * (all-0x00 or all-0xFF). Does not touch SRAM -- safe to unit test in
 * isolation, exactly like ClassifySaveCompatRaw (include/save_format.h). */
enum ExpansionUserPrefsState ExpansionUserPrefs_ValidateRaw(struct ExpansionUserPrefs const *prefs, bool8 regionUnset);

/* Reads the live SRAM prefs record (from within
 * gSram->expansionSaveMeta.reserved) and classifies it. If SRAM is not
 * confirmed working (IsSramWorking() == false) this conservatively
 * returns EXPANSION_USER_PREFS_CORRUPT rather than UNSET, mirroring
 * ClassifySramSaveCompat()'s same hardware-fault guard. `out` (if
 * non-NULL) always receives the raw record read, regardless of state. */
enum ExpansionUserPrefsState ExpansionUserPrefs_Load(struct ExpansionUserPrefs *out);

/* Resolves a classified record down to the single (effective locale id,
 * requires-prompt) pair every runtime caller actually needs: for
 * EXPANSION_USER_PREFS_VALID/EXPANSION_USER_PREFS_MIGRATED, the stored
 * localeId with requiresPrompt=FALSE; for every other state, this
 * build's configured default locale (FE8_EXPANSION_DEFAULT_LOCALE_ID)
 * with requiresPrompt=TRUE, signaling that a UI should re-prompt the
 * player rather than silently trust an unusable record. Pure -- never
 * touches SRAM. Either output pointer may be NULL. Returns `state`
 * unchanged, for convenient chaining. */
enum ExpansionUserPrefsState ExpansionUserPrefs_Normalize(
    struct ExpansionUserPrefs const *prefs,
    enum ExpansionUserPrefsState state,
    ExpansionLocaleId *outLocaleId,
    bool8 *outRequiresPrompt);

/* Pure, dual-linked (bmsave-lib.c) building block for
 * ExpansionUserPrefs_Store (src/expansion_save_prefs.c): validates that
 * `localeId` is supported+enabled (by macro only -- never calls
 * ExpansionLocale_IsSupported/IsEnabled, so this stays legacy-linkable),
 * checks IsSramWorking(), builds a fully-checksummed current record, and
 * performs exactly one bounded WriteAndVerifySramFast() call covering
 * only this record's own EXPANSION_USER_PREFS_META_OFFSET..+sizeof(...)
 * window inside gSram->expansionSaveMeta.reserved -- never WipeSram(),
 * never any other SRAM byte. Returns FALSE (writing nothing) if
 * `localeId` is not supported+enabled or SRAM is not confirmed working;
 * otherwise returns whether the write verified successfully. */
bool8 ExpansionUserPrefs_StoreRaw(ExpansionLocaleId localeId, bool8 explicitSelection);

/* Full store entry point (src/expansion_save_prefs.c, modern-ROM-linked
 * only -- see this header's file comment): rejects an unsupported/
 * disabled `localeId` outright (no SRAM write, matching
 * ExpansionUserPrefs_StoreRaw's own guard), otherwise calls
 * ExpansionUserPrefs_StoreRaw() and, only on a verified-successful write,
 * calls ExpansionLocale_SetCurrent(localeId) (include/expansion_locale.h)
 * to invalidate the runtime resolver's cache and adopt the newly-stored
 * locale immediately -- the "cache invalidation signal" contract. Returns
 * FALSE (with nothing written) if `localeId` is unsupported/disabled, or
 * if the SRAM write itself failed verification. */
bool8 ExpansionUserPrefs_Store(ExpansionLocaleId localeId, bool8 explicitSelection);

#endif /* GUARD_EXPANSION_SAVE_PREFS_H */
