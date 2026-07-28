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
 * module). Does not touch
 * struct GameOption's `selectors[4]` array or resize that struct, and
 * does not touch Title_IDLE or any issue #11 debug hotkey.
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

    /* Incremented only by this module, only when a locale change is
     * actually committed (startup auto-select, or a settings-submenu
     * selection that differs from the previously-current locale) --
     * never on a redundant re-selection of the already-current locale.
     * Distinct from (and not a substitute for) ExpansionLocale_
     * InvalidateCache()'s own internal bookkeeping (src/expansion_locale.c,
     * not part of this sprint's file domain). */
    u16 cacheGeneration;

    /* Number of times the startup Proc script has run this session
     * (always exactly 1 per boot in practice -- exposed for host/
     * playtest assertions, not expected to ever exceed 1). */
    u16 startupRunCount;

    /* Number of times the settings submenu has been opened. */
    u16 settingsOpenCount;

    /* Number of times a settings-submenu selection actually changed the
     * current locale (i.e. how many times cacheGeneration was bumped
     * from within the settings submenu specifically, as opposed to from
     * the startup path). */
    u16 settingsChangeCount;
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
 * Opens the independent settings submenu as a blocking child of `parent`
 * (typically the Config screen's own ConfigProc) -- never touches
 * struct GameOption/its selectors[4] array. Selecting a locale here
 * calls ExpansionUserPrefs_Store() (persisting + invalidating the
 * runtime resolver cache) only when it actually differs from the
 * current locale; Back leaves prefs/current locale untouched.
 */
void ExpansionLanguageMenu_OpenSettings(ProcPtr parent);

/*
 * Resolves the *current* ExpansionLocale_GetCurrent()'s own
 * self-referential display name (e.g. "English"/"Pseudo (Test)"),
 * always against EXPANSION_LOCALE_EN (a proper noun, never
 * translated) -- used by src/uiconfig.c's guarded
 * GAME_OPTION_LANGUAGE value-column special case so the Config
 * screen shows which locale is active without duplicating this
 * module's private locale-name table. Never GetStringFromIndex/
 * vanilla MSG_*.
 */
const char *ExpansionLanguageMenu_ResolveCurrentLocaleName(void);

#endif /* GUARD_EXPANSION_LANGUAGE_MENU_H */
