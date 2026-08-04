#ifndef GUARD_EXPANSION_LANGUAGE_MENU_H
#define GUARD_EXPANSION_LANGUAGE_MENU_H

/*
 * First-start blocking language selector + later settings submenu
 * runtime glue (issue #18 sprint 3).
 *
 * This header/its implementation (src/expansion_language_menu.c) is
 * compiled by both the legacy (agbcc) and modern (GCC) source globs --
 * like include/expansion_locale.h/src/expansion_locale.c -- but the
 * implementation is only *linked* into the modern ROM (see ldscript.txt's
 * explicit legacy object list, which never names it). Every symbol
 * declared here must therefore stay compilable (not necessarily
 * linkable) under strict C89/agbcc; every call site that actually
 * *invokes* one of these symbols from a dual-linked file (src/gamecontrol.c,
 * src/uiconfig.c) must itself be guarded by `#ifdef MODERN` so the legacy
 * link never needs these symbols to exist.
 *
 * Never reads/writes GetLang()/SetLang()/gLanguageMode, any vanilla MSG_*
 * id, or gMsgTable -- only include/expansion_locale.h's
 * ExpansionLocale_ family and include/expansion_save_prefs.h's
 * ExpansionUserPrefs_ family (both consumed, never modified, by this
 * module). Does not resize struct GameOption's fixed `selectors[4]`
 * array, and does not touch Title_IDLE or any issue #11 debug hotkey.
 */

#include "global.h"
#include "expansion_locale.h"
#include "expansion_save_prefs.h"
#include "proc.h"

/* --- Startup decision (pure, host-testable) ------------------------------ */

enum ExpansionLanguageMenuStartupAction
{
    /* prefs record is VALID/MIGRATED: apply the stored locale to the
     * runtime resolver (ExpansionLocale_SetCurrent) and show no UI. */
    EXPANSION_LANGUAGE_STARTUP_APPLY_ONLY = 0,

    /* prefs record requires a prompt, but only one locale is enabled by
     * this build: silently persist that single locale and show no UI. */
    EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT = 1,

    /* prefs record requires a prompt and more than one locale is
     * enabled: the blocking first-start selector must be shown. */
    EXPANSION_LANGUAGE_STARTUP_SHOW_MENU = 2,
};

enum ExpansionLanguageMenuPromptReason
{
    /* No prompt was (or would be) needed -- prefs were VALID/MIGRATED. */
    EXPANSION_LANGUAGE_PROMPT_NONE = 0,

    /* Mirrors EXPANSION_USER_PREFS_UNSET. */
    EXPANSION_LANGUAGE_PROMPT_UNSET = 1,

    /* Mirrors EXPANSION_USER_PREFS_CORRUPT. */
    EXPANSION_LANGUAGE_PROMPT_CORRUPT = 2,

    /* Mirrors EXPANSION_USER_PREFS_UNKNOWN_LOCALE. */
    EXPANSION_LANGUAGE_PROMPT_UNKNOWN_LOCALE = 3,

    /* Mirrors EXPANSION_USER_PREFS_DISABLED_LOCALE. */
    EXPANSION_LANGUAGE_PROMPT_DISABLED_LOCALE = 4,
};

enum ExpansionLanguageSettingsAction
{
    EXPANSION_LANGUAGE_SETTINGS_NONE = 0,
    EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE = 1,
    EXPANSION_LANGUAGE_SETTINGS_OPEN_MENU = 2,
};

#define EXPANSION_LANGUAGE_INLINE_MAX 3

/*
 * Pure scalar-only decision function -- no SRAM/Proc/GBA-hardware
 * dependency, fully unit-testable on host. `prefsState`/`requiresPrompt`
 * are exactly ExpansionUserPrefs_Normalize()'s own outputs;
 * `enabledLocaleCount` is the number of ExpansionLocaleId slots for
 * which ExpansionLocale_IsEnabled() is true (0 is treated exactly like 1
 * -- a defensive fallback that can only arise from a self-contradictory
 * build configuration, since FE8_EXPANSION_DEFAULT_LOCALE_ID is always
 * one of the enabled bits -- see include/expansion_config.h). Writes
 * *outPromptReason (if non-NULL) unconditionally.
 */
enum ExpansionLanguageMenuStartupAction ExpansionLanguageMenu_DecideStartupAction(
    enum ExpansionUserPrefsState prefsState,
    bool8 requiresPrompt,
    u8 enabledLocaleCount,
    enum ExpansionLanguageMenuPromptReason *outPromptReason);

/*
 * Pure settings-row decision logic. Builds with up to three enabled
 * locales select all languages inline. Builds with more than three show
 * the first two locales plus More: moving right from the second locale
 * (or from a current locale outside the first two) opens the full menu,
 * while moving left from an out-of-line locale selects the second inline
 * locale. `direction` is negative for Left and positive for Right.
 * `outLocale` receives the locale to select, or
 * EXPANSION_LOCALE_INVALID when the full menu should open.
 */
enum ExpansionLanguageSettingsAction ExpansionLanguageMenu_DecideSettingsAction(
    u32 enabledLocaleMask,
    ExpansionLocaleId currentLocale,
    int direction,
    ExpansionLocaleId *outLocale);

/* --- Bounded diagnostic probe (issue #13) -------------------------------- */

/*
 * Always exists (debug and release, exactly like struct DebugToolsProbe --
 * see include/expansion_debugtools.h), zero-initialized EWRAM, plain
 * scalar fields only -- never a raw pointer. Schema (field order/type) is
 * stable; new fields may only be appended.
 */
struct ExpansionLanguageMenuProbe
{
    /* 1 while the blocking first-start selector's own MenuProc is alive. */
    u8 active;

    /* 1 while the settings submenu's own MenuProc is alive. */
    u8 settingsActive;

    /* 1 if the blocking first-start selector was actually shown at least
     * once this boot (0 for an APPLY_ONLY/AUTO_SELECT boot). */
    u8 promptShown;

    /* 1 if EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT fired this boot. */
    u8 autoSelected;

    /* enum ExpansionLanguageMenuPromptReason from the most recent
     * startup decision. */
    u8 promptReason;

    /* enum ExpansionUserPrefsState from the most recent startup
     * ExpansionUserPrefs_Load()/Normalize() pair. */
    u8 prefsState;

    /* ExpansionLocaleId last selected/applied by this module (startup
     * apply/auto-select, or a settings-submenu selection). */
    u8 selectedLocale;

    /* ExpansionLocale_GetCurrent(), sampled after the most recent
     * startup or settings-submenu action. */
    u8 currentLocale;

    /* Number of ExpansionLocaleId slots enabled by this build, sampled
     * at the most recent startup decision. */
    u8 enabledLocaleCount;

    /* Incremented only by this module, only when
     * ExpansionUserPrefs_Store() actually verified-writes a record:
     * startup auto-select; a settings-submenu selection that differs
     * from the previously-current locale (never a redundant
     * re-selection of the already-current locale there -- the settings
     * submenu's own "same locale = no-op" contract is unconditional); or
     * -- issue #18 sprint 6 -- the first-start selector repairing a
     * corrupt/unset/unknown/disabled on-disk record even when the
     * chosen row happens to match the runtime resolver's current
     * fallback-default locale (see needsPreferenceRepair below). Distinct
     * from (and not a substitute for) ExpansionLocale_
     * InvalidateCache()'s own internal bookkeeping (src/expansion_locale.c,
     * not part of this sprint's file domain). */
    u16 cacheGeneration;

    /* Number of times the startup Proc script has run this session
     * (always exactly 1 per boot in practice -- exposed for host/
     * playtest assertions, not expected to ever exceed 1). */
    u16 startupRunCount;

    /* Number of times the settings submenu has been opened. */
    u16 settingsOpenCount;

    /* Number of times the Config language row or its More submenu
     * actually changed the current locale (as opposed to startup). */
    u16 settingsChangeCount;

    /*
     * Issue #18 sprint 6 (runtime blocker fix): explicit repair-state
     * flag, appended (never inserted -- see this struct's own "new
     * fields may only be appended" schema note) after every
     * pre-sprint-6 field so every existing scenario's hardcoded probe
     * address stays valid. Set from ExpansionUserPrefs_Normalize()'s own
     * `requiresPrompt` output at the start of every startup decision
     * (TRUE for UNSET/CORRUPT/UNKNOWN_LOCALE/DISABLED_LOCALE, FALSE for
     * VALID/MIGRATED) -- i.e. this is the same "does the on-disk record
     * need fixing" fact DecideStartupAction() itself branches on, not a
     * value re-derived later from comparing locale ids. Cleared only by
     * a verified-successful ExpansionUserPrefs_Store() (auto-select, or
     * the first-start selector's own repair write -- see
     * ExpansionLanguageMenu_RowSelected's own comment). Deliberately NOT
     * cleared by merely calling ExpansionLocale_SetCurrent() for
     * rendering/fallback purposes: adopting a fallback locale into the
     * runtime resolver so the selector has something to draw is not the
     * same as the player having actually confirmed+persisted a choice,
     * so this flag -- unlike comparing against
     * ExpansionLocale_GetCurrent() -- never confuses "what the runtime
     * is currently rendering" with "whether SRAM still needs repair". */
    u8 needsPreferenceRepair;
};

extern struct ExpansionLanguageMenuProbe gExpansionLanguageMenuProbe;

/* --- GBA runtime entry points --------------------------------------------- */

/*
 * Blocking first-start selector/apply proc -- see src/gamecontrol.c's
 * `#ifdef MODERN`-guarded PROC_START_CHILD_BLOCKING call site, inserted
 * immediately after ProcScr_GameEarlyStartUI and before ProcScr_OpAnim.
 * Never shown more than once per boot; ends immediately (no visible UI)
 * whenever the startup decision is APPLY_ONLY or AUTO_SELECT.
 */
extern struct ProcCmd CONST_DATA ProcScr_ExpansionLanguageSelector[];

/*
 * Opens the full settings submenu as a blocking child of `parent`
 * (typically the Config screen's own ConfigProc). The Config row calls
 * this only through More when more than three locales are enabled.
 * Selecting a locale here calls ExpansionUserPrefs_Store() (persisting
 * + invalidating the runtime resolver cache) only when it actually
 * differs from the current locale; Back leaves prefs/current locale
 * untouched.
 */
void ExpansionLanguageMenu_OpenSettings(ProcPtr parent);

/*
 * Resolves one locale's self-referential full or compact display name,
 * always against EXPANSION_LOCALE_EN (proper names/codes, never
 * translated). Compact names are used when multiple languages share the
 * Config value row. Never GetStringFromIndex/vanilla MSG_*.
 */
const char *ExpansionLanguageMenu_ResolveLocaleName(ExpansionLocaleId locale, bool8 compact);

/* Persists one inline settings-row selection and updates diagnostics. */
bool8 ExpansionLanguageMenu_SelectSettingsLocale(ExpansionLocaleId locale);

#endif /* GUARD_EXPANSION_LANGUAGE_MENU_H */
