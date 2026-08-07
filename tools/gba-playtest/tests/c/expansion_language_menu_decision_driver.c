/*
 * Issue #18 sprint 3 -- host-executed pure decision-logic test driver.
 *
 * Links directly against the real, unmodified
 * ExpansionLanguageMenu_DecideStartupAction (src/expansion_language_menu.c)
 * -- compiled for the host with no -DMODERN (this one function is
 * deliberately left unguarded/dual-linked, see that file's own header
 * comment) -- and exhaustively drives every
 * (prefsState, requiresPrompt, enabledLocaleCount) combination the real
 * ExpansionUserPrefs_Normalize()/ExpansionLocale_IsEnabled() callers can
 * ever actually produce, asserting both the returned
 * ExpansionLanguageMenuStartupAction and the written promptReason.
 *
 * Prints "EXPANSION_LANGUAGE_MENU_DECISION_HOST_TEST: PASS" and exits 0
 * on success; on any failure it prints the specific failing assertion to
 * stderr and exits 1 without running further checks.
 */
#include <stdio.h>

#include "global.h"
#include "expansion_language_menu.h"

#define CHECK(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "EXPANSION_LANGUAGE_MENU_DECISION_HOST_TEST: FAIL: %s\n", msg); \
            return 1; \
        } \
    } while (0)

static int CheckOne(
    enum ExpansionUserPrefsState prefsState,
    bool8 requiresPrompt,
    u8 enabledLocaleCount,
    enum ExpansionLanguageMenuStartupAction expectedAction,
    enum ExpansionLanguageMenuPromptReason expectedReason,
    const char *label)
{
    enum ExpansionLanguageMenuPromptReason reason = (enum ExpansionLanguageMenuPromptReason)0xFF;
    enum ExpansionLanguageMenuStartupAction action =
        ExpansionLanguageMenu_DecideStartupAction(prefsState, requiresPrompt, enabledLocaleCount, &reason);

    if (action != expectedAction)
    {
        fprintf(stderr,
            "EXPANSION_LANGUAGE_MENU_DECISION_HOST_TEST: FAIL: %s: action=%d expected=%d\n",
            label, (int)action, (int)expectedAction);
        return 0;
    }

    if (reason != expectedReason)
    {
        fprintf(stderr,
            "EXPANSION_LANGUAGE_MENU_DECISION_HOST_TEST: FAIL: %s: reason=%d expected=%d\n",
            label, (int)reason, (int)expectedReason);
        return 0;
    }

    return 1;
}

static int CheckSettings(
    u32 enabledMask,
    ExpansionLocaleId current,
    int direction,
    enum ExpansionLanguageSettingsAction expectedAction,
    ExpansionLocaleId expectedLocale,
    const char *label)
{
    ExpansionLocaleId locale = 0xEE;
    enum ExpansionLanguageSettingsAction action =
        ExpansionLanguageMenu_DecideSettingsAction(enabledMask, current, direction, &locale);

    if (action != expectedAction || locale != expectedLocale)
    {
        fprintf(stderr,
            "EXPANSION_LANGUAGE_MENU_DECISION_HOST_TEST: FAIL: %s: action=%d/%d locale=%u/%u\n",
            label, (int)action, (int)expectedAction, (unsigned)locale, (unsigned)expectedLocale);
        return 0;
    }

    return 1;
}

int main(void)
{
    int ok = 1;

    /* --- requiresPrompt == FALSE: always APPLY_ONLY / PROMPT_NONE,
     * regardless of prefsState/enabledLocaleCount (VALID/MIGRATED never
     * set requiresPrompt -- see ExpansionUserPrefs_Normalize's own
     * contract). --- */
    ok &= CheckOne(EXPANSION_USER_PREFS_VALID, FALSE, 1,
        EXPANSION_LANGUAGE_STARTUP_APPLY_ONLY, EXPANSION_LANGUAGE_PROMPT_NONE,
        "valid/no-prompt/one-enabled");
    ok &= CheckOne(EXPANSION_USER_PREFS_VALID, FALSE, 8,
        EXPANSION_LANGUAGE_STARTUP_APPLY_ONLY, EXPANSION_LANGUAGE_PROMPT_NONE,
        "valid/no-prompt/all-enabled");
    ok &= CheckOne(EXPANSION_USER_PREFS_MIGRATED, FALSE, 2,
        EXPANSION_LANGUAGE_STARTUP_APPLY_ONLY, EXPANSION_LANGUAGE_PROMPT_NONE,
        "migrated/no-prompt/two-enabled");

    /* --- requiresPrompt == TRUE, enabledLocaleCount <= 1: always
     * AUTO_SELECT, with promptReason still reflecting the real prefsState
     * (so a probe/diagnostic can still tell *why* a prompt would have
     * been needed, even though none was shown). --- */
    ok &= CheckOne(EXPANSION_USER_PREFS_UNSET, TRUE, 1,
        EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT, EXPANSION_LANGUAGE_PROMPT_UNSET,
        "unset/prompt/one-enabled");
    ok &= CheckOne(EXPANSION_USER_PREFS_UNSET, TRUE, 0,
        EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT, EXPANSION_LANGUAGE_PROMPT_UNSET,
        "unset/prompt/zero-enabled-defensive");
    ok &= CheckOne(EXPANSION_USER_PREFS_CORRUPT, TRUE, 1,
        EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT, EXPANSION_LANGUAGE_PROMPT_CORRUPT,
        "corrupt/prompt/one-enabled");
    ok &= CheckOne(EXPANSION_USER_PREFS_UNKNOWN_LOCALE, TRUE, 1,
        EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT, EXPANSION_LANGUAGE_PROMPT_UNKNOWN_LOCALE,
        "unknown-locale/prompt/one-enabled");
    ok &= CheckOne(EXPANSION_USER_PREFS_DISABLED_LOCALE, TRUE, 1,
        EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT, EXPANSION_LANGUAGE_PROMPT_DISABLED_LOCALE,
        "disabled-locale/prompt/one-enabled");

    /* --- requiresPrompt == TRUE, enabledLocaleCount > 1: always
     * SHOW_MENU, with promptReason reflecting the real prefsState. --- */
    ok &= CheckOne(EXPANSION_USER_PREFS_UNSET, TRUE, 2,
        EXPANSION_LANGUAGE_STARTUP_SHOW_MENU, EXPANSION_LANGUAGE_PROMPT_UNSET,
        "unset/prompt/two-enabled");
    ok &= CheckOne(EXPANSION_USER_PREFS_CORRUPT, TRUE, 8,
        EXPANSION_LANGUAGE_STARTUP_SHOW_MENU, EXPANSION_LANGUAGE_PROMPT_CORRUPT,
        "corrupt/prompt/all-enabled");
    ok &= CheckOne(EXPANSION_USER_PREFS_UNKNOWN_LOCALE, TRUE, 3,
        EXPANSION_LANGUAGE_STARTUP_SHOW_MENU, EXPANSION_LANGUAGE_PROMPT_UNKNOWN_LOCALE,
        "unknown-locale/prompt/three-enabled");
    ok &= CheckOne(EXPANSION_USER_PREFS_DISABLED_LOCALE, TRUE, 8,
        EXPANSION_LANGUAGE_STARTUP_SHOW_MENU, EXPANSION_LANGUAGE_PROMPT_DISABLED_LOCALE,
        "disabled-locale/prompt/all-enabled");

    /* --- Defensive-only fallback: a self-contradictory prefsState value
     * that requiresPrompt claims needs a prompt for is still treated as
     * UNSET (never crashes/leaves reason uninitialized). --- */
    ok &= CheckOne(EXPANSION_USER_PREFS_VALID, TRUE, 2,
        EXPANSION_LANGUAGE_STARTUP_SHOW_MENU, EXPANSION_LANGUAGE_PROMPT_UNSET,
        "defensive-valid-but-requiresPrompt/two-enabled");

    /* outPromptReason == NULL must never crash. */
    {
        enum ExpansionLanguageMenuStartupAction action =
            ExpansionLanguageMenu_DecideStartupAction(EXPANSION_USER_PREFS_UNSET, TRUE, 1, NULL);
        CHECK(action == EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT, "NULL outPromptReason must still return a valid action");
    }

    /* One locale is display-only: Left/Right never opens a redundant menu. */
    ok &= CheckSettings(1u << EXPANSION_LOCALE_EN, EXPANSION_LOCALE_EN, +1,
        EXPANSION_LANGUAGE_SETTINGS_NONE, EXPANSION_LOCALE_EN,
        "settings/one/right-noop");

    /* Two and three locales are selected entirely inline. */
    ok &= CheckSettings(
        (1u << EXPANSION_LOCALE_EN) | (1u << EXPANSION_LOCALE_QPS_PLOC),
        EXPANSION_LOCALE_EN, +1,
        EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE, EXPANSION_LOCALE_QPS_PLOC,
        "settings/two/right");
    ok &= CheckSettings(
        (1u << EXPANSION_LOCALE_EN) | (1u << EXPANSION_LOCALE_QPS_PLOC),
        EXPANSION_LOCALE_QPS_PLOC, -1,
        EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE, EXPANSION_LOCALE_EN,
        "settings/two/left");
    ok &= CheckSettings(
        (1u << EXPANSION_LOCALE_EN) | (1u << EXPANSION_LOCALE_QPS_PLOC),
        EXPANSION_LOCALE_QPS_PLOC, +1,
        EXPANSION_LANGUAGE_SETTINGS_NONE, EXPANSION_LOCALE_QPS_PLOC,
        "settings/two/right-end");
    ok &= CheckSettings(0x07u, EXPANSION_LOCALE_JA, +1,
        EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE, EXPANSION_LOCALE_ZH_HANS,
        "settings/en-ja-zh/ja-right");
    ok &= CheckSettings(0x07u, EXPANSION_LOCALE_ZH_HANS, +1,
        EXPANSION_LANGUAGE_SETTINGS_NONE, EXPANSION_LOCALE_ZH_HANS,
        "settings/en-ja-zh/zh-right-end");

    /* The production four-locale profile (en, ja, zh-Hans, qps-ploc)
     * exposes English, Japanese, More. */
    ok &= CheckSettings(0x87u, EXPANSION_LOCALE_EN, +1,
        EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE, EXPANSION_LOCALE_JA,
        "settings/en-ja-zh-qps/first-right");
    ok &= CheckSettings(0x87u, EXPANSION_LOCALE_JA, +1,
        EXPANSION_LANGUAGE_SETTINGS_OPEN_MENU, EXPANSION_LOCALE_INVALID,
        "settings/en-ja-zh-qps/second-right-more");
    ok &= CheckSettings(0x87u, EXPANSION_LOCALE_ZH_HANS, +1,
        EXPANSION_LANGUAGE_SETTINGS_OPEN_MENU, EXPANSION_LOCALE_INVALID,
        "settings/en-ja-zh-qps/zh-right-more");
    ok &= CheckSettings(0x87u, EXPANSION_LOCALE_QPS_PLOC, -1,
        EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE, EXPANSION_LOCALE_JA,
        "settings/en-ja-zh-qps/qps-left");
    ok &= CheckSettings(0x87u, EXPANSION_LOCALE_JA, -1,
        EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE, EXPANSION_LOCALE_EN,
        "settings/en-ja-zh-qps/second-left");

    /* Defensive invalid current locale adopts the first enabled choice. */
    ok &= CheckSettings(
        (1u << EXPANSION_LOCALE_EN) | (1u << EXPANSION_LOCALE_QPS_PLOC),
        EXPANSION_LOCALE_INVALID, +1,
        EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE, EXPANSION_LOCALE_EN,
        "settings/invalid-current");

    CHECK(ok, "one or more decision-table cases failed (see FAIL lines above)");

    printf("EXPANSION_LANGUAGE_MENU_DECISION_HOST_TEST: PASS\n");
    return 0;
}
