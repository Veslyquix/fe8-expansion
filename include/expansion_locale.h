#ifndef GUARD_EXPANSION_LOCALE_H
#define GUARD_EXPANSION_LOCALE_H

/*
 * Stable expansion framework locale/message identifiers and runtime
 * resolver API (issue #18 sprint 1).
 *
 * ExpansionLocaleId/ExpansionMsgId are brand-new, independently numbered
 * identifier spaces -- never alias or reuse GetLang()/SetLang()/
 * gLanguageMode (vanilla language runtime), any vanilla MSG_* id
 * (include/constants/msg.h), or any XMAP magic/identifier. Nothing here
 * reads, decodes, or depends on the vanilla texts/texts.txt ->
 * src/msg_data.c pipeline, its Huffman decode cache, or gMsgTable.
 *
 * Every message/locale string this framework ships is new, original
 * expansion-framework English (plus a deterministic ASCII pseudo-locale
 * transform of that same English -- see scripts/localization/pseudo.py);
 * this file and src/expansion_locale.c never contain vanilla dialogue or
 * any FE8J/EU/CN original-game text.
 *
 * The canonical message registry/catalog source lives under
 * texts/expansion/ (registry.json + catalog.en.json); the generated,
 * per-build C catalog (never committed -- see scripts/localization/
 * generate.py and modern.mk's "Localization catalog" section) is written
 * under build/expansion-localization/generated/ and defines the `extern`
 * data declared below. This header intentionally declares no save/UI
 * API yet -- that is later sprint work; the functions below are the only
 * supported entry point into the expansion catalog in sprint 1.
 *
 * This file is compiled by both the legacy (agbcc) and modern (GCC)
 * source globs -- like include/expansion_metadata.h/src/expansion_metadata.c
 * (issue #8) -- but src/expansion_locale.c is only linked into the modern
 * ROM (see linker/expansion.ld's generic .rodata/.text wildcard vs.
 * ldscript.txt's explicit legacy object list, which never names it).
 * Consequently every symbol declared `extern` here must stay compilable
 * (not necessarily linkable) under strict C89/agbcc.
 */

/* --- Stable locale identifiers ------------------------------------------- */

/*
 * Stable, append-only, test-locked locale ordering -- mirrors
 * scripts/localization/schema.py's LOCALE_IDS tuple exactly (index for
 * index); do not renumber an existing entry, and a retired locale's slot
 * must never be reused. Sprint 1 ships real catalog content only for
 * EXPANSION_LOCALE_EN and EXPANSION_LOCALE_QPS_PLOC -- every other id
 * below is a reserved slot for a future sprint.
 */
typedef u8 ExpansionLocaleId;

#define EXPANSION_LOCALE_EN       0
#define EXPANSION_LOCALE_JA       1
#define EXPANSION_LOCALE_ZH_HANS  2
#define EXPANSION_LOCALE_FR       3
#define EXPANSION_LOCALE_DE       4
#define EXPANSION_LOCALE_ES       5
#define EXPANSION_LOCALE_IT       6
/* ASCII pseudo-locale test harness ("Pseudo (Test)"); deterministically
 * derived from the English catalog at generate time. This is a QA/test
 * tool, never a real translation of any language. */
#define EXPANSION_LOCALE_QPS_PLOC 7

#define EXPANSION_LOCALE_COUNT    8
#define EXPANSION_LOCALE_INVALID  0xFFu

/* --- Stable message identifiers ------------------------------------------ */

/*
 * Independently and separately numbered from ExpansionLocaleId above and
 * from every vanilla MSG_* constant (include/constants/msg.h) -- never
 * alias or reuse either. Concrete per-message numeric values (EXP_MSG_*)
 * are generated from texts/expansion/registry.json into
 * build/expansion-localization/generated/expansion_msg_ids.h (see
 * scripts/localization/generate.py); this header only fixes the type and
 * sentinel every caller needs regardless of the current registry
 * contents.
 */
typedef u16 ExpansionMsgId;
#define EXPANSION_MSG_ID_INVALID 0xFFFFu

/*
 * Per-slot byte budget for the runtime resolver's single bounded scratch
 * cache slot below -- every active registry message's max_decoded_bytes
 * (texts/expansion/registry.json) must be <= this value in both English
 * and the derived pseudo-locale form; scripts/localization/schema.py's
 * MAX_DECODED_BYTES_MAX mirrors this constant and is cross-checked by
 * scripts/localization/tests/test_generate.py.
 */
#define EXPANSION_LOCALE_SCRATCH_SLOT_BYTES 96

/* --- Generated catalog data (defined by the generated
 * expansion_locale_catalog.c -- see scripts/localization/generate.py) --- */

/*
 * Ascending-sorted array of every active ExpansionMsgId, shared by every
 * populated locale table below (a message either exists, at the same
 * array index, in every populated locale, or it does not exist at all --
 * sprint 1 has no locale with partial coverage). gExpansionLocaleMsgCount
 * is this array's element count.
 */
extern const ExpansionMsgId gExpansionLocaleMsgIds[];
extern const u16 gExpansionLocaleMsgCount;

/* Parallel-indexed (to gExpansionLocaleMsgIds) plain-ASCII C string
 * tables for the two locales sprint 1 actually populates. */
extern const char *const gExpansionCatalog_en[];
extern const char *const gExpansionCatalog_qps_ploc[];

/* Build-time tombstone count (texts/expansion/registry.json entries with
 * status "tombstone") -- exposed at runtime purely as budget/diagnostic
 * data; tombstoned ids are otherwise invisible to the resolver. */
extern const u16 gExpansionLocaleTombstoneCount;

/* --- Runtime resolver API ------------------------------------------------- */

struct ExpansionLocaleCatalogStats
{
    u16 activeMessageCount;
    u16 tombstoneCount;
    u32 catalogStringBytes;
    u32 catalogIndexBytes;
    u32 scratchBytes;
    u32 scratchBudgetBytes;
};

/* A locale id is "supported" if it is one of the EXPANSION_LOCALE_COUNT
 * stable slots above -- independent of whether it is currently enabled by
 * build configuration (see ExpansionLocale_IsEnabled below) or whether any
 * catalog content has been generated for it yet. */
bool8 ExpansionLocale_IsSupported(ExpansionLocaleId locale);

/* A locale id is "enabled" if the configured EXPANSION_ENABLED_LOCALES
 * build setting (config.mk / scripts/modernize/expansion_config.py) marks
 * it enabled for this build. Sprint 1 only ever allows EN and/or
 * EXPANSION_LOCALE_QPS_PLOC to be enabled. */
bool8 ExpansionLocale_IsEnabled(ExpansionLocaleId locale);

ExpansionLocaleId ExpansionLocale_GetDefault(void);
ExpansionLocaleId ExpansionLocale_GetCurrent(void);

/* Returns FALSE (and leaves the current locale unchanged) if `locale` is
 * not supported or not enabled; otherwise switches the current locale and
 * invalidates the resolver's cache (see ExpansionLocale_InvalidateCache),
 * then returns TRUE. */
bool8 ExpansionLocale_SetCurrent(ExpansionLocaleId locale);

/*
 * Resolves one message for one explicit locale: exact message in that
 * locale, else a single-step fallback to the English catalog, else a
 * visible ASCII "missing" marker -- never a second fallback hop, never a
 * crash, and never unbounded recursion. The returned pointer is valid
 * until the next call to ExpansionLocale_Resolve/ExpansionLocale_
 * ResolveCurrent/ExpansionLocale_InvalidateCache/ExpansionLocale_SetCurrent
 * (it may alias the bounded internal scratch cache).
 */
const char *ExpansionLocale_Resolve(ExpansionLocaleId locale, ExpansionMsgId msgId);

/* Convenience wrapper: ExpansionLocale_Resolve(ExpansionLocale_GetCurrent(), msgId). */
const char *ExpansionLocale_ResolveCurrent(ExpansionMsgId msgId);

/* Invalidates the resolver's single bounded scratch cache slot. Called
 * automatically by ExpansionLocale_SetCurrent on an actual locale change;
 * exposed directly for host tests and for any future caller that mutates
 * catalog state out from under a live cache entry. */
void ExpansionLocale_InvalidateCache(void);

void ExpansionLocale_GetCatalogStats(struct ExpansionLocaleCatalogStats *out);

#endif /* GUARD_EXPANSION_LOCALE_H */
