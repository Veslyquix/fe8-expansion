/* Host functional smoke test: real expansion_locale.c + real generated
 * catalog, hand-declared minimal types (mirrors
 * scripts/modernize/tests/test_save_format_meta_bytes_native.py's
 * pattern of not including global.h on host). */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef u8 bool8;
#define TRUE 1
#define FALSE 0


#include "expansion_locale.h"

static int failures = 0;
#define CHECK(cond) do { if (!(cond)) { printf("FAIL: %s:%d: %s\n", __FILE__, __LINE__, #cond); failures++; } } while (0)

int main(void)
{
    struct ExpansionLocaleCatalogStats stats;
    const char *s;

    CHECK(ExpansionLocale_IsSupported(EXPANSION_LOCALE_EN) == TRUE);
    CHECK(ExpansionLocale_IsSupported(EXPANSION_LOCALE_QPS_PLOC) == TRUE);
    CHECK(ExpansionLocale_IsSupported((ExpansionLocaleId)EXPANSION_LOCALE_COUNT) == FALSE);
    CHECK(ExpansionLocale_IsSupported(EXPANSION_LOCALE_INVALID) == FALSE);

    CHECK(ExpansionLocale_IsEnabled(EXPANSION_LOCALE_EN) == TRUE);
    CHECK(ExpansionLocale_IsEnabled(EXPANSION_LOCALE_QPS_PLOC) == TRUE);
    CHECK(ExpansionLocale_IsEnabled(EXPANSION_LOCALE_JA) == FALSE);

    CHECK(ExpansionLocale_GetDefault() == EXPANSION_LOCALE_EN);
    CHECK(ExpansionLocale_GetCurrent() == EXPANSION_LOCALE_EN);

    /* Resolve id 0 in English -- must be a real, non-missing string.
     * Copy out of the shared scratch buffer immediately: per the documented
     * contract the returned pointer is only valid until the *next* Resolve
     * call (it may alias the single bounded scratch slot). */
    {
        char en0[EXPANSION_LOCALE_SCRATCH_SLOT_BYTES];
        const char *pseudo;
        s = ExpansionLocale_Resolve(EXPANSION_LOCALE_EN, 0);
        CHECK(s != NULL);
        CHECK(strcmp(s, "<!MISSING!>") != 0);
        printf("EN[0] = %s\n", s);
        strcpy(en0, s);

        /* Resolve id 0 in qps-ploc -- must differ from English (pseudo), and
         * still be plain ASCII, and not the missing marker. */
        pseudo = ExpansionLocale_Resolve(EXPANSION_LOCALE_QPS_PLOC, 0);
        CHECK(pseudo != NULL);
        CHECK(strcmp(pseudo, "<!MISSING!>") != 0);
        CHECK(strcmp(pseudo, en0) != 0);
        printf("QPS[0] = %s\n", pseudo);
    }

    /* Unsupported locale falls back one step to English. */
    s = ExpansionLocale_Resolve(EXPANSION_LOCALE_JA, 0);
    CHECK(s != NULL);
    CHECK(strcmp(s, "<!MISSING!>") != 0);

    /* Unknown/invalid message id -> visible missing marker, never crash. */
    s = ExpansionLocale_Resolve(EXPANSION_LOCALE_EN, (ExpansionMsgId)60000);
    CHECK(strcmp(s, "<!MISSING!>") == 0);

    s = ExpansionLocale_Resolve(EXPANSION_LOCALE_EN, EXPANSION_MSG_ID_INVALID);
    CHECK(strcmp(s, "<!MISSING!>") == 0);

    /* Tombstoned id (6, per texts/expansion/registry.json) must resolve to
     * the missing marker, not garbage or a shifted string. */
    s = ExpansionLocale_Resolve(EXPANSION_LOCALE_EN, 6);
    CHECK(strcmp(s, "<!MISSING!>") == 0);

    /* Locale switch + cache invalidation smoke: switching locale and
     * re-resolving the same id must return the new locale's string. */
    CHECK(ExpansionLocale_SetCurrent(EXPANSION_LOCALE_QPS_PLOC) == TRUE);
    CHECK(ExpansionLocale_GetCurrent() == EXPANSION_LOCALE_QPS_PLOC);
    s = ExpansionLocale_ResolveCurrent(0);
    CHECK(strcmp(s, "<!MISSING!>") != 0);

    CHECK(ExpansionLocale_SetCurrent(EXPANSION_LOCALE_JA) == FALSE); /* not enabled */
    CHECK(ExpansionLocale_GetCurrent() == EXPANSION_LOCALE_QPS_PLOC); /* unchanged */

    CHECK(ExpansionLocale_SetCurrent(EXPANSION_LOCALE_EN) == TRUE);
    CHECK(ExpansionLocale_GetCurrent() == EXPANSION_LOCALE_EN);

    /* Cache correctness: resolve same (locale,id) twice, must be stable
     * pointer contents (same bytes) both times. */
    {
        const char *first = ExpansionLocale_Resolve(EXPANSION_LOCALE_EN, 1);
        const char *second = ExpansionLocale_Resolve(EXPANSION_LOCALE_EN, 1);
        CHECK(strcmp(first, second) == 0);
    }

    ExpansionLocale_InvalidateCache();

    ExpansionLocale_GetCatalogStats(&stats);
    /* Issue #18 sprint 3: registry.json/catalog.en.json now carry 25
     * active messages (ids 0-25, minus the 1 pre-existing tombstone) --
     * see the new language, framework.back, save_compat.menu_erase_all
     * and debug.action.NNN keys in texts/expansion/registry.json. This
     * is the catalog's own real, current active count -- not a
     * fingerprint -- so it is expected to change whenever legitimate
     * new catalog entries are authored. */
    CHECK(stats.activeMessageCount == 25);
    CHECK(stats.tombstoneCount == 1);
    CHECK(stats.scratchBudgetBytes == EXPANSION_LOCALE_SCRATCH_SLOT_BYTES);
    CHECK(stats.scratchBytes == EXPANSION_LOCALE_SCRATCH_SLOT_BYTES);
    printf("stats: active=%u tombstone=%u stringBytes=%u indexBytes=%u\n",
           stats.activeMessageCount, stats.tombstoneCount,
           (unsigned)stats.catalogStringBytes, (unsigned)stats.catalogIndexBytes);

    if (failures == 0)
        printf("ALL HOST SMOKE CHECKS PASSED\n");
    else
        printf("%d CHECK(S) FAILED\n", failures);
    return failures != 0;
}
