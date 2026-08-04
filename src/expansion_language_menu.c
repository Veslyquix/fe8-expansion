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

enum ExpansionLanguageSettingsAction ExpansionLanguageMenu_DecideSettingsAction(
    u32 enabledLocaleMask,
    ExpansionLocaleId currentLocale,
    int direction,
    ExpansionLocaleId *outLocale)
{
    ExpansionLocaleId locales[EXPANSION_LOCALE_COUNT];
    ExpansionLocaleId locale;
    int currentIndex;
    int count;

    count = 0;
    currentIndex = -1;

    for (locale = 0; locale < EXPANSION_LOCALE_COUNT; ++locale)
    {
        if (!(enabledLocaleMask & (1u << locale)))
            continue;

        locales[count] = locale;

        if (locale == currentLocale)
            currentIndex = count;

        count++;
    }

    if (outLocale != NULL)
        *outLocale = currentLocale;

    if (direction == 0 || count <= 1)
        return EXPANSION_LANGUAGE_SETTINGS_NONE;

    if (currentIndex < 0)
    {
        if (direction > 0)
        {
            if (outLocale != NULL)
                *outLocale = locales[0];

            return EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE;
        }

        return EXPANSION_LANGUAGE_SETTINGS_NONE;
    }

    if (count <= EXPANSION_LANGUAGE_INLINE_MAX)
    {
        if (direction < 0 && currentIndex > 0)
        {
            if (outLocale != NULL)
                *outLocale = locales[currentIndex - 1];

            return EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE;
        }

        if (direction > 0 && currentIndex + 1 < count)
        {
            if (outLocale != NULL)
                *outLocale = locales[currentIndex + 1];

            return EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE;
        }

        return EXPANSION_LANGUAGE_SETTINGS_NONE;
    }

    if (currentIndex == 0)
    {
        if (direction > 0)
        {
            if (outLocale != NULL)
                *outLocale = locales[1];

            return EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE;
        }

        return EXPANSION_LANGUAGE_SETTINGS_NONE;
    }

    if (currentIndex == 1 || currentIndex >= 2)
    {
        if (direction < 0)
        {
            if (outLocale != NULL)
                *outLocale = (currentIndex == 1) ? locales[0] : locales[1];

            return EXPANSION_LANGUAGE_SETTINGS_SELECT_LOCALE;
        }

        if (direction > 0)
        {
            if (outLocale != NULL)
                *outLocale = EXPANSION_LOCALE_INVALID;

            return EXPANSION_LANGUAGE_SETTINGS_OPEN_MENU;
        }
    }

    return EXPANSION_LANGUAGE_SETTINGS_NONE;
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
#include "uiconfig.h"

/* One row per BUILD-ENABLED locale slot, plus one reserved Back row
 * (settings submenu only) -- mirrors DEBUGTOOLS_HUB_MENU_SLOTS' own
 * sizing contract (src/debugtools_registry.c), but bounded by the
 * compile-time FE8_EXPANSION_ENABLED_LOCALE_MASK popcount rather than
 * the full EXPANSION_LOCALE_COUNT identifier-space size: which locales
 * ExpansionLocale_IsEnabled() ever reports enabled is itself fixed
 * entirely by that same build-time mask (src/expansion_locale.c), never
 * by SRAM/runtime state, so BuildLocaleRows below can never write more
 * than popcount(mask) locale rows + one Back row regardless of
 * EXPANSION_LOCALE_COUNT's own (much larger, future-reserved) size.
 * Sizing against the mask instead of the full identifier space matters:
 * EWRAM is at a premium once issue #6's starter runtime coexists with
 * issue #18's locale runtime (see expansion-modern-itemexpansion-check's
 * FE8_ITEM_ID_CAP=0xCE debug probe build), and every build today ships
 * exactly one enabled locale, so the full 8-slot reservation this used
 * to carry was ten times more than any real build ever needed. No extra
 * cushion row is added beyond the exact popcount(mask)+1 (locale rows +
 * one Back row) plus the zeroed MenuItemDef sentinel StartMenu requires
 * after the last visible row. Growing to a multi-locale build simply grows
 * this same expression -- it is not a fixed constant to maintain by hand.
 * Issue #18 sprint 6: this popcount
 * is no longer computed locally -- it is the exact same
 * FE8_EXPANSION_ENABLED_LOCALE_COUNT single source of truth
 * (include/expansion_config.h) src/bmsave-lib.c's
 * BuildCurrentExpansionSaveMeta() now reads too, so the two call sites
 * can never quietly drift apart on "how many locales does this build
 * enable". */
#define EXPANSION_LANGUAGE_MENU_MAX_ROWS \
    (FE8_EXPANSION_ENABLED_LOCALE_COUNT + 2)

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

static const ExpansionMsgId sLocaleShortNameMsgIds[EXPANSION_LOCALE_COUNT] =
{
    EXP_MSG_FRAMEWORK_LOCALE_SHORT_NAME_EN,       /* EXPANSION_LOCALE_EN */
    EXPANSION_MSG_ID_INVALID,                     /* EXPANSION_LOCALE_JA (reserved) */
    EXPANSION_MSG_ID_INVALID,                     /* EXPANSION_LOCALE_ZH_HANS (reserved) */
    EXPANSION_MSG_ID_INVALID,                     /* EXPANSION_LOCALE_FR (reserved) */
    EXPANSION_MSG_ID_INVALID,                     /* EXPANSION_LOCALE_DE (reserved) */
    EXPANSION_MSG_ID_INVALID,                     /* EXPANSION_LOCALE_ES (reserved) */
    EXPANSION_MSG_ID_INVALID,                     /* EXPANSION_LOCALE_IT (reserved) */
    EXP_MSG_FRAMEWORK_LOCALE_SHORT_NAME_QPS_PLOC, /* EXPANSION_LOCALE_QPS_PLOC */
};

/* RAM-resident MenuItemDef adapter, rebuilt every time either MenuDef
 * below is (re)shown -- same "contributor/runtime code never edits an
 * engine-owned const MenuItemDef table" idiom as
 * src/debugtools_registry.c's sHubMenuItemDefs. A SINGLE array shared by
 * both the first-start selector and the later settings submenu: the two
 * are never simultaneously live (the selector is a blocking child of
 * early boot -- src/gamecontrol.c -- that always finishes before the
 * title/gameplay this settings submenu is only ever reachable from --
 * src/uiconfig.c -- can begin), and each menu's own
 * ExpansionLanguageMenu_BuildLocaleRows call fully rewrites every row
 * (memset then repopulate) immediately before its StartMenu, so neither
 * ever depends on whatever the other last left behind. */
EWRAM_DATA static struct MenuItemDef sLanguageMenuItemDefs[EXPANSION_LANGUAGE_MENU_MAX_ROWS] = {0};

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
 * the settings submenu: commits the choice when it actually differs from
 * the current locale (no redundant SRAM write/cache-generation bump for
 * reselecting the already-current locale there), via
 * ExpansionUserPrefs_Store (which itself calls ExpansionLocale_SetCurrent/
 * InvalidateCache on a verified-successful write).
 *
 * Issue #18 sprint 6 (runtime blocker fix): the first-start selector
 * ALSO commits when `locale == previous` if
 * gExpansionLanguageMenuProbe.needsPreferenceRepair is still set --
 * i.e. the on-disk record ExpansionUserPrefs_Load() read this boot was
 * UNSET/CORRUPT/UNKNOWN_LOCALE/DISABLED_LOCALE. Without this, choosing
 * the row that happens to match ExpansionLocale_GetCurrent()'s own
 * fallback-default value (extremely likely: `previous` is that same
 * build-configured default whenever no valid record has ever been
 * adopted this boot) looked exactly like a redundant no-op reselection
 * and skipped the write entirely, leaving the corrupt/unset/unknown/
 * disabled record on disk unrepaired forever -- re-prompting on every
 * future boot even after the player had already "chosen" a locale.
 * Gated on `active` (true only while the first-start selector's own
 * MenuProc is alive, never during the later settings submenu) so the
 * settings submenu's own unconditional "same locale = no-op" contract
 * is never affected by this repair path. */
static bool8 ExpansionLanguageMenu_StoreSelection(
    ExpansionLocaleId locale,
    bool8 mustRepair,
    bool8 settingsSelection)
{
    ExpansionLocaleId previous = ExpansionLocale_GetCurrent();

    gExpansionLanguageMenuProbe.selectedLocale = locale;

    if (locale != previous || mustRepair)
    {
        if (ExpansionUserPrefs_Store(locale, TRUE))
        {
            gExpansionLanguageMenuProbe.cacheGeneration++;
            gExpansionLanguageMenuProbe.needsPreferenceRepair = FALSE;

            if (settingsSelection)
                gExpansionLanguageMenuProbe.settingsChangeCount++;

            gExpansionLanguageMenuProbe.currentLocale = ExpansionLocale_GetCurrent();
            return TRUE;
        }
    }

    gExpansionLanguageMenuProbe.currentLocale = ExpansionLocale_GetCurrent();

    return FALSE;
}

static u8 ExpansionLanguageMenu_RowSelected(struct MenuProc *menu, struct MenuItemProc *item)
{
    ExpansionLocaleId locale = (ExpansionLocaleId)item->def->helpMsgId;
    bool8 mustRepair;

    (void)menu;

    mustRepair = (bool8)(gExpansionLanguageMenuProbe.active
                       && gExpansionLanguageMenuProbe.needsPreferenceRepair);

    ExpansionLanguageMenu_StoreSelection(
        locale,
        mustRepair,
        gExpansionLanguageMenuProbe.settingsActive);

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

        /* Cannot overflow: EXPANSION_LANGUAGE_MENU_MAX_ROWS reserves all
         * enabled locale rows, the optional Back row, and one sentinel. */
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
    sLanguageMenuItemDefs,
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

static CONST_DATA struct ProcCmd gProcScr_RedrawConfigAfterLanguageMenu[] =
{
    PROC_SLEEP(1),
    PROC_CALL(Config_RedrawAfterLanguageMenu),
    PROC_END,
};

static void ExpansionLanguageMenu_SettingsOnEnd(struct MenuProc *proc)
{
    gExpansionLanguageMenuProbe.settingsActive = FALSE;
    Proc_Start(gProcScr_RedrawConfigAfterLanguageMenu, proc->proc_parent);
}

CONST_DATA struct MenuDef gExpansionLanguageSettingsMenuDef =
{
    {6, 6, 18, 0},
    0,
    sLanguageMenuItemDefs,
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

    /* Issue #18 sprint 6 (runtime blocker fix): explicit repair
     * obligation, set directly from ExpansionUserPrefs_Normalize()'s own
     * requiresPrompt output -- TRUE for every non-VALID/MIGRATED state,
     * regardless of what effectiveLocale/enabledCount happen to resolve
     * to. Only cleared below by a verified-successful
     * ExpansionUserPrefs_Store() (AUTO_SELECT here, or the first-start
     * selector's own repair write in ExpansionLanguageMenu_RowSelected).
     * APPLY_ONLY never needs to clear it -- requiresPrompt is already
     * FALSE for the VALID/MIGRATED states that reach that action. */
    gExpansionLanguageMenuProbe.needsPreferenceRepair = requiresPrompt;

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
            {
                gExpansionLanguageMenuProbe.cacheGeneration++;
                gExpansionLanguageMenuProbe.needsPreferenceRepair = FALSE;
            }

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
    ExpansionLanguageMenu_BuildLocaleRows(sLanguageMenuItemDefs, FALSE);

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
    struct MenuProc *menu;
    ExpansionLocaleId current;
    ExpansionLocaleId locale;
    u8 itemIndex;

    ExpansionLanguageMenu_BuildLocaleRows(sLanguageMenuItemDefs, TRUE);

    gExpansionLanguageMenuProbe.settingsActive = TRUE;
    gExpansionLanguageMenuProbe.settingsOpenCount++;

    BG_Fill(gBG0TilemapBuffer, 0);
    BG_Fill(gBG1TilemapBuffer, 0);
    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT);

    ResetTextFont();
    menu = StartMenu(&gExpansionLanguageSettingsMenuDef, parent);

    current = ExpansionLocale_GetCurrent();
    itemIndex = 0;

    for (locale = 0; locale < EXPANSION_LOCALE_COUNT; ++locale)
    {
        if (!ExpansionLocale_IsEnabled(locale))
            continue;

        if (locale == current)
        {
            menu->itemCurrent = itemIndex;
            break;
        }

        itemIndex++;
    }
}

const char *ExpansionLanguageMenu_ResolveLocaleName(ExpansionLocaleId locale, bool8 compact)
{
    ExpansionMsgId msgId;

    if (!ExpansionLocale_IsSupported(locale))
        locale = ExpansionLocale_GetDefault();

    msgId = compact ? sLocaleShortNameMsgIds[locale] : sLocaleNameMsgIds[locale];

    if (msgId == EXPANSION_MSG_ID_INVALID)
        msgId = sLocaleNameMsgIds[locale];

    return ExpansionLocale_Resolve(EXPANSION_LOCALE_EN, msgId);
}

bool8 ExpansionLanguageMenu_SelectSettingsLocale(ExpansionLocaleId locale)
{
    return ExpansionLanguageMenu_StoreSelection(locale, FALSE, TRUE);
}

#endif /* MODERN */
