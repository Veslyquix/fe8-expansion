#include "global.h"
#include <string.h>
#include "expansion_locale.h"

/*
 * Runtime message resolver (issue #18 sprint 1). Reads only the
 * generated, read-only ROM catalog tables declared in
 * include/expansion_locale.h (defined by the generated
 * expansion_locale_catalog.c -- see scripts/localization/generate.py) and
 * a single bounded, owned scratch cache slot below. Never touches
 * vanilla gMsgTable, the vanilla Huffman decode cache, or gGenericBuffer.
 *
 * This file is compiled (but never linked -- see this header's own file
 * comment) by the legacy agbcc build too, so every construct here must
 * stay strict C89: declarations only at the top of a block, no `//`
 * comments, no mixed declarations/statements.
 */

struct ExpansionLocaleCatalogView
{
    const ExpansionMsgId *ids;
    const char *const *strings;
    u16 count;
};

/*
 * EWRAM_DATA (not a bare `static`): this project's modern linker
 * script (linker/expansion.ld) places any *non-zero*-initialized
 * file-scope static that lacks an explicit section attribute into
 * the pinned ROM output section as ordinary initialized `.data`
 * (there is no generic per-object EWRAM `.data` copy-on-boot step --
 * only files with an explicit `ewram_data`-tagged symbol, i.e. the
 * EWRAM_DATA attribute, land in the writable `ewram_data` EWRAM
 * region; see every other EWRAM_DATA static elsewhere in this
 * codebase, e.g. src/hardware.c/src/uiselecttarget.c). Without this
 * attribute, every write through ExpansionLocale_SetCurrent() would
 * silently target read-only cartridge ROM and have no effect,
 * leaving ExpansionLocale_GetCurrent() stuck reading back whatever
 * byte the ROM image happens to hold at that address forever --
 * i.e. locale selection would never actually take effect. `ewram_data`
 * is a NOLOAD output section (like `.bss`), so it only guarantees a
 * zero initial value, never the compiled non-zero initializer below
 * -- hence the separate sCurrentLocaleValid flag (naturally
 * zero/FALSE at boot) rather than relying on an EXPANSION_LOCALE_INVALID
 * sentinel surviving as this variable's true first-boot value.
 */
static EWRAM_DATA ExpansionLocaleId sCurrentLocale;
static EWRAM_DATA bool8 sCurrentLocaleValid = FALSE;

/* Single bounded, owned scratch cache slot. Deliberately not shared with
 * (and never aliased to) gGenericBuffer -- see this header's file
 * comment -- to avoid any concurrent-use hazard with unrelated systems
 * that already use that buffer. */
static char sScratch[EXPANSION_LOCALE_SCRATCH_SLOT_BYTES];
/*
 * Also EWRAM_DATA for the same reason as sCurrentLocale above.
 * These two are read only when sCacheValid is TRUE (see
 * ExpansionLocale_Resolve() below), so -- unlike sCurrentLocale --
 * their exact value before the very first cache population is
 * never observed; they are given the EXPANSION_LOCALE_INVALID/
 * EXPANSION_MSG_ID_INVALID sentinels here purely for defensive
 * clarity when inspected (e.g. by a debugger or playtest probe),
 * not because any control-flow branch depends on that exact
 * first-boot bit pattern the way ExpansionLocale_GetCurrent()
 * depends on sCurrentLocaleValid.
 */
static EWRAM_DATA ExpansionLocaleId sCacheLocale = EXPANSION_LOCALE_INVALID;
static EWRAM_DATA ExpansionMsgId sCacheMsgId = EXPANSION_MSG_ID_INVALID;
static bool8 sCacheValid = FALSE;

/* Visible, always-safe (no catalog lookup, no locale, never fails its own
 * size bound) ASCII fallback marker -- a code constant, not catalog
 * content, so it is available even if the generated catalog is somehow
 * absent/corrupt. */
static const char sMissingMarker[] = "<!MISSING!>";

static const struct ExpansionLocaleCatalogView *GetCatalogView(ExpansionLocaleId locale)
{
    static struct ExpansionLocaleCatalogView sEnView;
    static struct ExpansionLocaleCatalogView sQpsView;

    if (locale == EXPANSION_LOCALE_EN)
    {
        sEnView.ids = gExpansionLocaleMsgIds;
        sEnView.strings = gExpansionCatalog_en;
        sEnView.count = gExpansionLocaleMsgCount;
        return &sEnView;
    }
    if (locale == EXPANSION_LOCALE_QPS_PLOC)
    {
        sQpsView.ids = gExpansionLocaleMsgIds;
        sQpsView.strings = gExpansionCatalog_qps_ploc;
        sQpsView.count = gExpansionLocaleMsgCount;
        return &sQpsView;
    }
    return NULL;
}

/* Binary search over view->ids[] (generated ascending-sorted by
 * scripts/localization/generate.py). Returns NULL if msgId is not
 * present in this view -- never partial/garbage data. */
static const char *FindInView(const struct ExpansionLocaleCatalogView *view, ExpansionMsgId msgId)
{
    u16 low;
    u16 high;

    if (view == NULL || view->count == 0)
        return NULL;

    low = 0;
    high = view->count;
    while (low < high)
    {
        u16 mid = (u16)(low + (high - low) / 2);
        ExpansionMsgId candidate = view->ids[mid];
        if (candidate == msgId)
            return view->strings[mid];
        if (candidate < msgId)
            low = (u16)(mid + 1);
        else
            high = mid;
    }
    return NULL;
}

bool8 ExpansionLocale_IsSupported(ExpansionLocaleId locale)
{
    return (bool8)(locale < EXPANSION_LOCALE_COUNT);
}

bool8 ExpansionLocale_IsEnabled(ExpansionLocaleId locale)
{
    if (!ExpansionLocale_IsSupported(locale))
        return FALSE;
    return (bool8)((FE8_EXPANSION_ENABLED_LOCALE_MASK & ((u32)1 << locale)) != 0);
}

ExpansionLocaleId ExpansionLocale_GetDefault(void)
{
    return (ExpansionLocaleId)FE8_EXPANSION_DEFAULT_LOCALE_ID;
}

ExpansionLocaleId ExpansionLocale_GetCurrent(void)
{
    if (!sCurrentLocaleValid)
        return ExpansionLocale_GetDefault();
    return sCurrentLocale;
}

bool8 ExpansionLocale_SetCurrent(ExpansionLocaleId locale)
{
    if (!ExpansionLocale_IsSupported(locale) || !ExpansionLocale_IsEnabled(locale))
        return FALSE;
    if (!sCurrentLocaleValid || sCurrentLocale != locale)
    {
        sCurrentLocale = locale;
        sCurrentLocaleValid = TRUE;
        ExpansionLocale_InvalidateCache();
    }
    return TRUE;
}

void ExpansionLocale_InvalidateCache(void)
{
    sCacheValid = FALSE;
    sCacheLocale = EXPANSION_LOCALE_INVALID;
    sCacheMsgId = EXPANSION_MSG_ID_INVALID;
}

const char *ExpansionLocale_Resolve(ExpansionLocaleId locale, ExpansionMsgId msgId)
{
    const char *found;
    size_t length;

    if (msgId == EXPANSION_MSG_ID_INVALID)
        return sMissingMarker;

    if (sCacheValid && sCacheLocale == locale && sCacheMsgId == msgId)
        return sScratch;

    found = FindInView(GetCatalogView(locale), msgId);
    if (found == NULL && locale != EXPANSION_LOCALE_EN)
    {
        /* One-step English fallback only -- never a second hop. */
        found = FindInView(GetCatalogView(EXPANSION_LOCALE_EN), msgId);
    }
    if (found == NULL)
        return sMissingMarker;

    length = strlen(found);
    if (length + 1 > (size_t)EXPANSION_LOCALE_SCRATCH_SLOT_BYTES)
    {
        /* Size bound violated: fail visible, never crash, never recurse.
         * Build-time validation (scripts/localization/catalog.py) is
         * expected to reject any message that could ever reach here. */
        return sMissingMarker;
    }
    memcpy(sScratch, found, length + 1);
    sCacheValid = TRUE;
    sCacheLocale = locale;
    sCacheMsgId = msgId;
    return sScratch;
}

const char *ExpansionLocale_ResolveCurrent(ExpansionMsgId msgId)
{
    return ExpansionLocale_Resolve(ExpansionLocale_GetCurrent(), msgId);
}

void ExpansionLocale_GetCatalogStats(struct ExpansionLocaleCatalogStats *out)
{
    u16 populatedLocales;
    u32 stringBytes;
    u16 i;

    if (out == NULL)
        return;

    populatedLocales = 2; /* en, qps-ploc -- see GetCatalogView */
    stringBytes = 0;
    for (i = 0; i < gExpansionLocaleMsgCount; i++)
    {
        stringBytes += (u32)(strlen(gExpansionCatalog_en[i]) + 1);
        stringBytes += (u32)(strlen(gExpansionCatalog_qps_ploc[i]) + 1);
    }

    out->activeMessageCount = gExpansionLocaleMsgCount;
    out->tombstoneCount = gExpansionLocaleTombstoneCount;
    out->catalogStringBytes = stringBytes;
    out->catalogIndexBytes = (u32)(gExpansionLocaleMsgCount * sizeof(ExpansionMsgId))
        + (u32)(gExpansionLocaleMsgCount * sizeof(char *) * populatedLocales);
    out->scratchBytes = (u32)sizeof(sScratch);
    out->scratchBudgetBytes = (u32)EXPANSION_LOCALE_SCRATCH_SLOT_BYTES;
}
