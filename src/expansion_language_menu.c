#include "global.h"

#include <string.h>

#include "expansion_language_menu.h"

/*
 * First-start blocking language selector + later settings submenu
 * (issue #18 sprint 3).
 *
 * Like src/expansion_locale.c/src/expansion_save_prefs.c, this file is
 * compiled by both the legacy (agbcc) and modern (GCC) source globs but
 * only linked into the modern ROM -- so every construct at file scope
 * must stay strict C89-compilable even where it can never actually be
 * exercised by the legacy/archival build (see include/expansion_locale.h's
 * own file comment for the precedent this follows).
 *
 * ExpansionLanguageMenu_DecideStartupAction below is the one exception:
 * it is pure scalar-only logic with no locale/prefs-catalog dependency
 * beyond the types already declared in include/expansion_language_menu.h,
 * so it needs no generated-header access and is safe to host-test
 * directly, unguarded, exactly like include/expansion_save_prefs.h's own
 * pure Build/ValidateRaw/Normalize functions (src/bmsave-lib.c).
 *
 * Everything below that -- the GBA runtime glue (screen bring-up, Proc
 * script, MenuDef/MenuItemDef construction, catalog resolution) -- needs
 * the generated build/expansion-localization/generated/expansion_msg_ids.h
 * EXP_MSG_* macros, which are only ever generated/added to the include
 * path for the modern build (see modern.mk's "Localization catalog"
 * section); it is therefore guarded by `#ifdef MODERN`, exactly like
 * every call site that actually invokes it (src/gamecontrol.c/
 * src/uiconfig.c).
 */

/* --- Pure, dual-linked (legacy/modern/host) startup decision logic ------- */

enum ExpansionLanguageMenuStartupAction ExpansionLanguageMenu_DecideStartupAction(
    enum ExpansionUserPrefsState prefsState,
    bool8 requiresPrompt,
    u8 enabledLocaleCount,
    enum ExpansionLanguageMenuPromptReason *outPromptReason)
{
    enum ExpansionLanguageMenuPromptReason reason;
    enum ExpansionLanguageMenuStartupAction action;

    reason = EXPANSION_LANGUAGE_PROMPT_NONE;

    if (!requiresPrompt)
    {
        action = EXPANSION_LANGUAGE_STARTUP_APPLY_ONLY;
    }
    else
    {
        switch (prefsState)
        {
        case EXPANSION_USER_PREFS_UNSET:
            reason = EXPANSION_LANGUAGE_PROMPT_UNSET;
            break;

        case EXPANSION_USER_PREFS_CORRUPT:
            reason = EXPANSION_LANGUAGE_PROMPT_CORRUPT;
            break;

        case EXPANSION_USER_PREFS_UNKNOWN_LOCALE:
            reason = EXPANSION_LANGUAGE_PROMPT_UNKNOWN_LOCALE;
            break;

        case EXPANSION_USER_PREFS_DISABLED_LOCALE:
            reason = EXPANSION_LANGUAGE_PROMPT_DISABLED_LOCALE;
            break;

        default:
            /* Defensive only: EXPANSION_USER_PREFS_VALID/_MIGRATED never
             * set requiresPrompt (see ExpansionUserPrefs_Normalize's own
             * contract), so this branch cannot be reached through any
             * real caller -- treated the same as UNSET rather than
             * silently leaving `reason` unset. */
            reason = EXPANSION_LANGUAGE_PROMPT_UNSET;
            break;
        }

        /* enabledLocaleCount == 0 is treated exactly like 1 (auto-select
         * the caller's resolved default) -- a defensive fallback that
         * can only arise from a self-contradictory build configuration,
         * since FE8_EXPANSION_DEFAULT_LOCALE_ID is always one of the
         * enabled mask bits (include/expansion_config.h). */
        if (enabledLocaleCount <= 1)
            action = EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT;
        else
            action = EXPANSION_LANGUAGE_STARTUP_SHOW_MENU;
    }

    if (outPromptReason != NULL)
        *outPromptReason = reason;

    return action;
}

/* --- Bounded diagnostic probe (issue #13) -------------------------------- */

/* Always linked, in every build -- see include/expansion_language_menu.h.
 * Zero-initialized EWRAM is guaranteed on every boot (src/main.c's
 * unconditional CpuFastFill of all of EWRAM before any gameplay code
 * runs), so this struct reliably starts all-zero, exactly like
 * gDebugToolsProbe (src/debugtools_registry.c). */
EWRAM_DATA struct ExpansionLanguageMenuProbe gExpansionLanguageMenuProbe = {0};

#ifdef MODERN

#include "expansion_msg_ids.h"
#include "proc.h"
#include "uimenu.h"
#include "fontgrp.h"
#include "hardware.h"
#include "uiutils.h"
#include "bm.h"

/* One row per stable locale slot, plus one reserved Back row (settings
 * submenu only), plus one implicit all-zero MenuItemsEnd terminator --
 * mirrors DEBUGTOOLS_HUB_MENU_SLOTS' own sizing contract
 * (src/debugtools_registry.c). 8 (EXPANSION_LOCALE_COUNT) + 2 = 10,
 * comfortably under MENU_ITEM_MAX (11, include/uimenu.h). */
#define EXPANSION_LANGUAGE_MENU_MAX_ROWS (EXPANSION_LOCALE_COUNT + 2)

/* Sentinel stashed in a locale-row MenuItemDef's otherwise-unused
 * helpMsgId field (u16) to mark the settings submenu's own reserved Back
 * row -- never a real ExpansionLocaleId (those are always <
 * EXPANSION_LOCALE_COUNT, i.e. < 8). */
#define EXPANSION_LANGUAGE_MENU_ROW_BACK EXPANSION_LOCALE_INVALID

/* Parallel-indexed to ExpansionLocaleId (include/expansion_locale.h):
 * which catalog message (if any) names that locale, always resolved
 * against EXPANSION_LOCALE_EN specifically -- these are self-referential
 * proper nouns ("English", "Pseudo (Test)"), never translated content.
 * Every reserved (not-yet-populated) locale slot maps to
 * EXPANSION_MSG_ID_INVALID; sprint 1 only ships real catalog content
 * for EN/QPS_PLOC (see include/expansion_locale.h), matching what
 * FE8_EXPANSION_ENABLED_LOCALE_MASK can ever actually enable today. */
static const ExpansionMsgId sLocaleNameMsgIds[EXPANSION_LOCALE_COUNT] =
{
    EXP_MSG_FRAMEWORK_LOCALE_NAME_EN,       /* EXPANSION_LOCALE_EN */
    EXPANSION_MSG_ID_INVALID,               /* EXPANSION_LOCALE_JA (reserved) */
    EXPANSION_MSG_ID_INVALID,               /* EXPANSION_LOCALE_ZH_HANS (reserved) */
    EXPANSION_MSG_ID_INVALID,               /* EXPANSION_LOCALE_FR (reserved) */
    EXPANSION_MSG_ID_INVALID,               /* EXPANSION_LOCALE_DE (reserved) */
    EXPANSION_MSG_ID_INVALID,               /* EXPANSION_LOCALE_ES (reserved) */
    EXPANSION_MSG_ID_INVALID,               /* EXPANSION_LOCALE_IT (reserved) */
    EXP_MSG_FRAMEWORK_LOCALE_NAME_QPS_PLOC, /* EXPANSION_LOCALE_QPS_PLOC */
};

/* RAM-resident MenuItemDef adapters, rebuilt every time the corresponding
 * MenuDef is (re)shown -- same "contributor/runtime code never edits an
 * engine-owned const MenuItemDef table" idiom as
 * src/debugtools_registry.c's sHubMenuItemDefs. */
EWRAM_DATA static struct MenuItemDef sSelectorMenuItemDefs[EXPANSION_LANGUAGE_MENU_MAX_ROWS] = {0};
EWRAM_DATA static struct MenuItemDef sSettingsMenuItemDefs[EXPANSION_LANGUAGE_MENU_MAX_ROWS] = {0};

struct ExpansionLanguageSelectorProc
{
    PROC_HEADER;
};

enum
{
    LBL_EXPANSION_LANGUAGE_SELECTOR_DONE = 1,
};

static ExpansionLocaleId ExpansionLanguageMenu_FindSoleEnabledLocale(void)
{
    ExpansionLocaleId i;

    for (i = 0; i < EXPANSION_LOCALE_COUNT; ++i)
    {
        if (ExpansionLocale_IsEnabled(i))
            return i;
    }

    /* Defensive only -- see ExpansionLanguageMenu_DecideStartupAction's
     * own comment on enabledLocaleCount == 0: cannot happen through any
     * valid build configuration. */
    return ExpansionLocale_GetDefault();
}

/* Shared onDraw for every locale-name/Back row in both the first-start
 * selector and the settings submenu: resolves the row's own label via
 * ExpansionLocale_Resolve/ExpansionLocale_ResolveCurrent and draws it
 * with Text_DrawStringASCII -- never GetStringFromIndex/vanilla MSG_*,
 * and never Text_DrawString (which only ever decodes via the vanilla
 * Huffman/GetStringFromIndex pipeline for a non-zero nameMsgId, or
 * item->def->name otherwise -- neither of which is what this row's
 * helpMsgId-keyed catalog lookup needs). */
static int ExpansionLanguageMenu_RowDraw(struct MenuProc *menu, struct MenuItemProc *item)
{
    u16 rowKey = item->def->helpMsgId;
    const char *label;

    if (item->def->color)
        Text_SetColor(&item->text, item->def->color);

    if (item->availability == MENU_DISABLED)
        Text_SetColor(&item->text, TEXT_COLOR_SYSTEM_GRAY);

    if (rowKey == EXPANSION_LANGUAGE_MENU_ROW_BACK)
        label = ExpansionLocale_ResolveCurrent(EXP_MSG_FRAMEWORK_BACK);
    else
        label = ExpansionLocale_Resolve(EXPANSION_LOCALE_EN, sLocaleNameMsgIds[(ExpansionLocaleId)rowKey]);

    Text_DrawStringASCII(&item->text, label);

    PutText(
        &item->text,
        TILEMAP_LOCATED(BG_GetMapBuffer(menu->frontBg), item->xTile, item->yTile));

    return 0;
}

/* Shared onSelected for every locale row (never the Back row -- that one
 * uses MenuCancelSelect directly) in both the first-start selector and
 * the settings submenu: commits the choice only when it actually differs
 * from the current locale (no redundant SRAM write/cache-generation bump
 * for reselecting the already-current locale), via
 * ExpansionUserPrefs_Store (which itself calls ExpansionLocale_SetCurrent/
 * InvalidateCache on a verified-successful write). */
static u8 ExpansionLanguageMenu_RowSelected(struct MenuProc *menu, struct MenuItemProc *item)
{
    ExpansionLocaleId locale = (ExpansionLocaleId)item->def->helpMsgId;
    ExpansionLocaleId previous = ExpansionLocale_GetCurrent();

    (void)menu;

    gExpansionLanguageMenuProbe.selectedLocale = locale;

    if (locale != previous)
    {
        if (ExpansionUserPrefs_Store(locale, TRUE))
        {
            gExpansionLanguageMenuProbe.cacheGeneration++;

            if (gExpansionLanguageMenuProbe.settingsActive)
                gExpansionLanguageMenuProbe.settingsChangeCount++;
        }
    }

    gExpansionLanguageMenuProbe.currentLocale = ExpansionLocale_GetCurrent();

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_CLEAR | MENU_ACT_SND6A;
}

/* Populates `defs` (an EXPANSION_LANGUAGE_MENU_MAX_ROWS-sized array) with
 * one row per build-enabled ExpansionLocaleId (in ascending id order --
 * never the currently-selected/enabled-order-dependent order, so a
 * host/playtest scenario's cursor navigation is deterministic across
 * runs), optionally followed by one reserved Back row. Returns the total
 * row count actually written. */
static u8 ExpansionLanguageMenu_BuildLocaleRows(struct MenuItemDef *defs, bool8 includeBackRow)
{
    ExpansionLocaleId locale;
    u8 count = 0;

    memset(defs, 0, sizeof(struct MenuItemDef) * EXPANSION_LANGUAGE_MENU_MAX_ROWS);

    for (locale = 0; locale < EXPANSION_LOCALE_COUNT; ++locale)
    {
        if (!ExpansionLocale_IsEnabled(locale))
            continue;

        /* Cannot overflow: at most EXPANSION_LOCALE_COUNT locale rows,
         * and EXPANSION_LANGUAGE_MENU_MAX_ROWS reserves room for all of
         * them plus the Back row below. */
        defs[count].name = "";
        defs[count].nameMsgId = 0;
        defs[count].helpMsgId = locale;
        defs[count].isAvailable = MenuAlwaysEnabled;
        defs[count].onDraw = ExpansionLanguageMenu_RowDraw;
        defs[count].onSelected = ExpansionLanguageMenu_RowSelected;
        ++count;
    }

    if (includeBackRow)
    {
        defs[count].name = "";
        defs[count].helpMsgId = EXPANSION_LANGUAGE_MENU_ROW_BACK;
        defs[count].isAvailable = MenuAlwaysEnabled;
        defs[count].onDraw = ExpansionLanguageMenu_RowDraw;
        defs[count].onSelected = MenuCancelSelect;
        ++count;
    }

    return count;
}

/* Fresh, from-scratch screen bring-up -- deliberately does not try to
 * preserve/restore whatever ProcScr_GameEarlyStartUI (src/opanim-
 * healthsafetyscreen.c) left on screen: OpAnimInit (src/data/opanim.c),
 * which always runs immediately after this proc ends (whether or not it
 * actually showed anything), performs its own full SetupBackgrounds-based
 * bring-up regardless, exactly mirroring the equivalent, already-proven
 * from-scratch pattern src/uiconfig.c's Config_Init uses for its own
 * generic (non-map) UI screen. */
static void ExpansionLanguageMenu_PrepareScreen(void)
{
    SetupBackgrounds(NULL);
    SetPrimaryHBlankHandler(NULL);

    ResetText();
    ApplySystemObjectsPalettes();
    LoadUiFrameGraphics();

    SetDispEnable(1, 1, 1, 1, 1);

    BG_SetPosition(BG_0, 0, 0);
    BG_SetPosition(BG_1, 0, 0);
    BG_SetPosition(BG_2, 0, 0);
    BG_SetPosition(BG_3, 0, 0);
}

static void ExpansionLanguageMenu_SelectorOnEnd(struct MenuProc *proc)
{
    (void)proc;

    gExpansionLanguageMenuProbe.active = FALSE;
}

CONST_DATA struct MenuDef gExpansionLanguageSelectorMenuDef =
{
    {6, 6, 18, 0},
    0,
    sSelectorMenuItemDefs,
    0,
    ExpansionLanguageMenu_SelectorOnEnd,
    0,
    0, /* onBPress: intentionally NULL -- the mandatory first-start
        * selector can never be B-cancelled (see
        * ProcessMenuSelectInput's `if (proc->def->onBPress)` guard,
        * include/uimenu.h/src/uimenu.c). */
    0,
    0,
};

static void ExpansionLanguageMenu_SettingsOnEnd(struct MenuProc *proc)
{
    (void)proc;

    gExpansionLanguageMenuProbe.settingsActive = FALSE;
}

CONST_DATA struct MenuDef gExpansionLanguageSettingsMenuDef =
{
    {6, 6, 18, 0},
    0,
    sSettingsMenuItemDefs,
    0,
    ExpansionLanguageMenu_SettingsOnEnd,
    0,
    MenuCancelSelect, /* Back is always allowed here; never mutates prefs. */
    0,
    0,
};

static void ExpansionLanguageMenu_RuntimeInit(ProcPtr procPtr)
{
    struct ExpansionUserPrefs prefs;
    enum ExpansionUserPrefsState state;
    ExpansionLocaleId effectiveLocale;
    bool8 requiresPrompt;
    enum ExpansionLanguageMenuPromptReason reason;
    enum ExpansionLanguageMenuStartupAction action;
    u8 enabledCount;
    ExpansionLocaleId i;

    gExpansionLanguageMenuProbe.startupRunCount++;

    state = ExpansionUserPrefs_Load(&prefs);
    state = ExpansionUserPrefs_Normalize(&prefs, state, &effectiveLocale, &requiresPrompt);

    enabledCount = 0;
    for (i = 0; i < EXPANSION_LOCALE_COUNT; ++i)
    {
        if (ExpansionLocale_IsEnabled(i))
            enabledCount++;
    }

    action = ExpansionLanguageMenu_DecideStartupAction(state, requiresPrompt, enabledCount, &reason);

    gExpansionLanguageMenuProbe.prefsState = (u8)state;
    gExpansionLanguageMenuProbe.promptReason = (u8)reason;
    gExpansionLanguageMenuProbe.enabledLocaleCount = enabledCount;

    switch (action)
    {
    case EXPANSION_LANGUAGE_STARTUP_APPLY_ONLY:
        /* Already valid/migrated on disk -- adopt it in the runtime
         * resolver without rewriting SRAM. */
        ExpansionLocale_SetCurrent(effectiveLocale);

        gExpansionLanguageMenuProbe.autoSelected = FALSE;
        gExpansionLanguageMenuProbe.promptShown = FALSE;
        gExpansionLanguageMenuProbe.selectedLocale = effectiveLocale;
        gExpansionLanguageMenuProbe.currentLocale = ExpansionLocale_GetCurrent();

        Proc_Goto(procPtr, LBL_EXPANSION_LANGUAGE_SELECTOR_DONE);
        break;

    case EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT:
        {
            ExpansionLocaleId sole = ExpansionLanguageMenu_FindSoleEnabledLocale();

            if (ExpansionUserPrefs_Store(sole, FALSE))
                gExpansionLanguageMenuProbe.cacheGeneration++;

            gExpansionLanguageMenuProbe.autoSelected = TRUE;
            gExpansionLanguageMenuProbe.promptShown = FALSE;
            gExpansionLanguageMenuProbe.selectedLocale = sole;
            gExpansionLanguageMenuProbe.currentLocale = ExpansionLocale_GetCurrent();
        }

        Proc_Goto(procPtr, LBL_EXPANSION_LANGUAGE_SELECTOR_DONE);
        break;

    case EXPANSION_LANGUAGE_STARTUP_SHOW_MENU:
    default:
        gExpansionLanguageMenuProbe.autoSelected = FALSE;
        gExpansionLanguageMenuProbe.promptShown = TRUE;
        /* Falls through to the next script step (screen/menu bring-up)
         * -- no Proc_Goto here. */
        break;
    }
}

static void ExpansionLanguageMenu_ShowSelector(ProcPtr procPtr)
{
    ExpansionLanguageMenu_PrepareScreen();
    ExpansionLanguageMenu_BuildLocaleRows(sSelectorMenuItemDefs, FALSE);

    gExpansionLanguageMenuProbe.active = TRUE;

    StartMenu(&gExpansionLanguageSelectorMenuDef, procPtr);
}

static u8 ExpansionLanguageMenu_ChildMenuBlocked(ProcPtr procPtr)
{
    struct ExpansionLanguageSelectorProc *proc = (struct ExpansionLanguageSelectorProc *)procPtr;

    return proc->proc_lockCnt > 0;
}

struct ProcCmd CONST_DATA ProcScr_ExpansionLanguageSelector[] =
{
    PROC_CALL(ExpansionLanguageMenu_RuntimeInit),
    PROC_CALL(ExpansionLanguageMenu_ShowSelector),
    PROC_WHILE(ExpansionLanguageMenu_ChildMenuBlocked),

PROC_LABEL(LBL_EXPANSION_LANGUAGE_SELECTOR_DONE),
    PROC_END,
};

void ExpansionLanguageMenu_OpenSettings(ProcPtr parent)
{
    ExpansionLanguageMenu_BuildLocaleRows(sSettingsMenuItemDefs, TRUE);

    gExpansionLanguageMenuProbe.settingsActive = TRUE;
    gExpansionLanguageMenuProbe.settingsOpenCount++;

    StartMenu(&gExpansionLanguageSettingsMenuDef, parent);
}

const char *ExpansionLanguageMenu_ResolveCurrentLocaleName(void)
{
    ExpansionLocaleId current = ExpansionLocale_GetCurrent();

    return ExpansionLocale_Resolve(EXPANSION_LOCALE_EN, sLocaleNameMsgIds[current]);
}

#endif /* MODERN */
