#include "global.h"

#include "constants/songs.h"
#include "constants/msg.h"

#include "proc.h"
#include "uimenu.h"
#include "helpbox.h"
#include "statscreen.h"
#include "fontgrp.h"
#include "hardware.h"
#include "uiutils.h"
#include "bm.h"
#include "bmsave.h"
#include "savemenu.h"
#include "sysutil.h"
#include "soundwrapper.h"
#include "gamecontrol.h"

#include "save_format.h"
#include "save_compat_menu.h"

#ifdef MODERN
/* Issue #18 sprint 3: these two labels are expansion-authored
 * (registry keys framework.back/save_compat.menu_erase_all), so they
 * are resolved through the catalog/current-locale resolver instead of
 * the vanilla MSG_SAVE_COMPAT_BACK/MSG_SAVE_COMPAT_ERASE_ALL lookup --
 * every other string in this file (diagnostic HelpBox messages, the
 * erase-confirmation Yes/No labels) is untouched vanilla dialogue. */
#include "expansion_locale.h"
#include "expansion_msg_ids.h"
#endif

/*
 * Global save-compatibility gate UI (issue #2 slice 2). See
 * include/save_compat_menu.h and docs/save_format.md for the full design
 * rationale. This proc is reached only from StartSaveMenu() (savemenu.c)
 * when ClassifySramSaveCompat() != SAVE_COMPAT_CURRENT, and it never calls
 * IsSaveValid, ReadSaveBlockInfo, ReadGameSave, or any slot/current-struct
 * accessor -- only the global classifier and InitGlobalSaveInfodata() (the
 * format-independent whole-chip wipe/current initializer) on confirmed
 * erase.
 */

/*
 * NOTE: `ewram_data` is a NOLOAD linker section (see ldscript.txt) -- it is
 * never copied from ROM at boot, on real hardware or under emulation, so a
 * non-zero compile-time initializer here would never actually be applied
 * (this matches every other EWRAM_DATA global in this codebase, which are
 * all declared with a `0`/FALSE initializer for the same reason). Both
 * globals below are therefore deliberately zero-initialized; the only
 * trustworthy read of gSaveCompatMenuLastState is one taken after
 * gSaveCompatMenuActive has been observed TRUE at least once (i.e. after
 * the gate has actually run and written a real classification), never as
 * a "no dialog ever shown" default.
 */
EWRAM_DATA u8 gSaveCompatMenuActive = FALSE;
EWRAM_DATA u8 gSaveCompatMenuLastState = 0;

struct SaveCompatMenuProc
{
    PROC_HEADER;

    enum SaveCompatState compatState;
    u8 choice;
};

enum
{
    SAVE_COMPAT_CHOICE_NONE = 0,
    SAVE_COMPAT_CHOICE_BACK,
    SAVE_COMPAT_CHOICE_ERASE_REQUESTED,
    SAVE_COMPAT_CHOICE_ERASE_CONFIRMED,
};

enum
{
    PL_SAVECOMPAT_MAIN = 1,
    PL_SAVECOMPAT_ERASE = 2,
    PL_SAVECOMPAT_DO_ERASE = 3,
    PL_SAVECOMPAT_END = 4,
};

static int SaveCompatMenu_GetDiagnosticMsgId(enum SaveCompatState compat)
{
    switch (compat)
    {
    case SAVE_COMPAT_VALID_LEGACY_OR_VANILLA:
        return MSG_SAVE_COMPAT_LEGACY;

    case SAVE_COMPAT_HEADER_CORRUPT:
        return MSG_SAVE_COMPAT_HEADER_CORRUPT;

    case SAVE_COMPAT_METADATA_CORRUPT:
        return MSG_SAVE_COMPAT_METADATA_CORRUPT;

    case SAVE_COMPAT_MIGRATABLE_OLDER:
        return MSG_SAVE_COMPAT_OLDER;

    case SAVE_COMPAT_NEWER_UNSUPPORTED:
        return MSG_SAVE_COMPAT_NEWER;

    case SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE:
        return MSG_SAVE_COMPAT_CONFIG_INCOMPATIBLE;

    case SAVE_COMPAT_EMPTY:
    case SAVE_COMPAT_CURRENT:
    default:
        /* SAVE_COMPAT_EMPTY should already have been auto-converted to
         * SAVE_COMPAT_CURRENT by EraseSramDataIfInvalid() before the save
         * menu is ever reachable, and SAVE_COMPAT_CURRENT never reaches
         * this proc at all (see StartSaveMenu()). Both are handled here
         * only as a defensive fallback so an unexpected value can never
         * format a garbage message id. */
        return MSG_SAVE_COMPAT_UNKNOWN;
    }
}

static void SaveCompatMenu_Init(struct SaveCompatMenuProc* proc)
{
    SaveMenu_Init();

    ResetTextFont();
    LoadUiFrameGraphics();
    LoadObjUIGfx();

    LoadHelpBoxGfx(OBJ_VRAM0 + OBJCHR_SAVEMENU_SLOTSEL_HELPBOX * TILE_SIZE_4BPP, OBJPAL_SAVEMENU_SLOTSEL_HELPBOX);
    StartHelpBoxExt_Unk(0x30, 0x30, SaveCompatMenu_GetDiagnosticMsgId(proc->compatState));
    PlaySoundEffect(SONG_70);

    gSaveCompatMenuActive = TRUE;
    gSaveCompatMenuLastState = proc->compatState;
}

static void SaveCompatMenu_WaitDiagnosticDismiss(struct SaveCompatMenuProc* proc)
{
    if (gKeyStatusPtr->newKeys & (A_BUTTON | B_BUTTON | R_BUTTON))
    {
        PlaySoundEffect(SONG_71);
        CloseHelpBox();
        Proc_Break(proc);
    }
}

static u8 SaveCompatMenu_SelectBack(struct MenuProc* menu, struct MenuItemProc* item)
{
    struct SaveCompatMenuProc* proc = (struct SaveCompatMenuProc*) menu->proc_parent;
    proc->choice = SAVE_COMPAT_CHOICE_BACK;
    return MENU_ACT_SKIPCURSOR | MENU_ACT_CLEAR | MENU_ACT_END | MENU_ACT_SND6B;
}

static u8 SaveCompatMenu_SelectErase(struct MenuProc* menu, struct MenuItemProc* item)
{
    struct SaveCompatMenuProc* proc = (struct SaveCompatMenuProc*) menu->proc_parent;
    proc->choice = SAVE_COMPAT_CHOICE_ERASE_REQUESTED;
    return MENU_ACT_SKIPCURSOR | MENU_ACT_CLEAR | MENU_ACT_END | MENU_ACT_SND6A;
}

#ifdef MODERN
static int SaveCompatMenu_DrawBackLabel(struct MenuProc *proc, struct MenuItemProc *item)
{
    if (item->def->color)
        Text_SetColor(&item->text, item->def->color);

    if (item->availability == MENU_DISABLED)
        Text_SetColor(&item->text, TEXT_COLOR_SYSTEM_GRAY);

    Text_DrawString(&item->text, ExpansionLocale_ResolveCurrent(EXP_MSG_FRAMEWORK_BACK));

    PutText(&item->text, TILEMAP_LOCATED(BG_GetMapBuffer(proc->frontBg), item->xTile, item->yTile));

    return 0;
}

static int SaveCompatMenu_DrawEraseAllLabel(struct MenuProc *proc, struct MenuItemProc *item)
{
    if (item->def->color)
        Text_SetColor(&item->text, item->def->color);

    if (item->availability == MENU_DISABLED)
        Text_SetColor(&item->text, TEXT_COLOR_SYSTEM_GRAY);

    Text_DrawString(
        &item->text,
        ExpansionLocale_ResolveCurrent(EXP_MSG_SAVE_COMPAT_MENU_ERASE_ALL));

    PutText(&item->text, TILEMAP_LOCATED(BG_GetMapBuffer(proc->frontBg), item->xTile, item->yTile));

    return 0;
}
#endif

CONST_DATA struct MenuItemDef gSaveCompatMenuItems[] = {
#ifdef MODERN
    {"", 0, 0, 0, 121, MenuAlwaysEnabled, SaveCompatMenu_DrawBackLabel, SaveCompatMenu_SelectBack, 0, 0, 0},
    {"", 0, 0, 0, 122, MenuAlwaysEnabled, SaveCompatMenu_DrawEraseAllLabel, SaveCompatMenu_SelectErase, 0, 0, 0},
#else
    {"", MSG_SAVE_COMPAT_BACK, 0, 0, 121, MenuAlwaysEnabled, 0, SaveCompatMenu_SelectBack, 0, 0, 0},
    {"", MSG_SAVE_COMPAT_ERASE_ALL, 0, 0, 122, MenuAlwaysEnabled, 0, SaveCompatMenu_SelectErase, 0, 0, 0},
#endif
    MenuItemsEnd
};

/* Back is always item 0 / the default cursor position -- StartMenuCore()
 * initializes itemCurrent to 0, so Back is selected by default without any
 * extra setup here. */
CONST_DATA struct MenuDef gSaveCompatMenuDef = {
    {1, 1, 20, 0},
    0,
    gSaveCompatMenuItems,
    0,
    0,
    0,
    SaveCompatMenu_SelectBack, /* B press == choosing Back */
    0,
    0
};

/* Confirmed-erase submenu. Deliberately does NOT reuse
 * gYesNoSelectionMenuDef/gYesNoSelectionMenuItems (src/menu_def.c): its
 * "Yes" callback (MenuCommand_SelectYes) is hardcoded to
 * UnitRemoveItem(gActiveUnit, ...) for the item-discard flow and must never
 * run in a title-screen/save-compatibility context. MSG_843/MSG_844 (the
 * existing localized "Yes"/"No" strings) are reused for the labels only. */
static u8 SaveCompatMenu_ConfirmEraseYes(struct MenuProc* menu, struct MenuItemProc* item)
{
    struct SaveCompatMenuProc* proc = (struct SaveCompatMenuProc*) menu->proc_parent;
    proc->choice = SAVE_COMPAT_CHOICE_ERASE_CONFIRMED;
    return MENU_ACT_SKIPCURSOR | MENU_ACT_CLEAR | MENU_ACT_END | MENU_ACT_SND6A;
}

CONST_DATA struct MenuItemDef gSaveCompatEraseConfirmItems[] = {
    {"", MSG_843, 0, 0, 123, MenuAlwaysEnabled, 0, SaveCompatMenu_ConfirmEraseYes, 0, 0, 0}, /* Yes */
    {"", MSG_844, 0, 0, 124, MenuAlwaysEnabled, 0, MenuCancelSelect, 0, 0, 0}, /* No */
    MenuItemsEnd
};

CONST_DATA struct MenuDef gSaveCompatEraseConfirmMenuDef = {
    {0, 0, 7, 0},
    1,
    gSaveCompatEraseConfirmItems,
    0,
    0,
    0,
    MenuCancelSelect, /* B press == No */
    0,
    0
};

/*
 * PROC_CALL always advances to the next script step within the same
 * frame (ProcCmd_CALL_ROUTINE unconditionally returns TRUE -- see
 * src/proc.c), regardless of proc_lockCnt. StartMenuAt() only *starts* a
 * blocking child menu proc (Proc_StartBlocking() increments this proc's
 * lockCnt); it does not itself wait for a selection. So every
 * PROC_CALL(...ShowXMenu) must be followed by PROC_WHILE on this routine
 * to actually block script progression until the child menu proc ends
 * and writes proc->choice, or the "choice" read below would always see
 * SAVE_COMPAT_CHOICE_NONE and silently fall through as if Back had been
 * pressed -- making Erase All unreachable.
 */
static u8 SaveCompatMenu_ChildMenuBlocked(struct SaveCompatMenuProc* proc)
{
    return proc->proc_lockCnt > 0;
}

static void SaveCompatMenu_ShowMainMenu(struct SaveCompatMenuProc* proc)
{
    struct MenuRect rect;
    rect.x = 4;
    rect.y = 10;
    rect.w = 20;
    rect.h = 0;

    proc->choice = SAVE_COMPAT_CHOICE_NONE;
    StartMenuAt(&gSaveCompatMenuDef, rect, (ProcPtr) proc);
}

static void SaveCompatMenu_RouteMainChoice(struct SaveCompatMenuProc* proc)
{
    if (proc->choice == SAVE_COMPAT_CHOICE_ERASE_REQUESTED)
        Proc_Goto(proc, PL_SAVECOMPAT_ERASE);

    /* Any other outcome (Back explicitly chosen, or B-pressed cancel,
     * which SaveCompatMenu_SelectBack also handles) falls through to the
     * next script step, SaveCompatMenu_DoBack -- the safe default. */
}

static void SaveCompatMenu_DoBack(struct SaveCompatMenuProc* proc)
{
    /*
     * Exactly the existing "no save data selected" signal
     * (GameControl_SwitchPostSaveMenu(), src/gamecontrol.c): returns to
     * the title screen through the unmodified existing path, with no SRAM
     * writes performed anywhere on this branch.
     */
    SetNextGameActionId(GAME_ACTION_5);
    gSaveCompatMenuActive = FALSE;
}

static void SaveCompatMenu_ShowEraseConfirm(struct SaveCompatMenuProc* proc)
{
    struct MenuRect rect;
    rect.x = 8;
    rect.y = 10;
    rect.w = 8;
    rect.h = 0;

    /*
     * HIGH-severity fix: render the authored irreversible-erase warning
     * (MSG_SAVE_COMPAT_ERASE_CONFIRM, "Erase all save data? This cannot
     * be undone.") alongside the bare Yes/No submenu, using the same
     * StartHelpBoxExt_Unk/LoadHelpBoxGfx pattern already used for the
     * state-specific diagnostic in SaveCompatMenu_Init -- so a player can
     * never reach a destructive Yes/No confirmation with no contextual
     * warning displayed. Positioned above the submenu's own rect
     * (x=8,y=10 tiles == pixels 64,80) so the two windows never overlap.
     * Closed unconditionally in SaveCompatMenu_RouteEraseChoice, whether
     * the player confirms (Yes) or cancels (No/B) -- the warning is only
     * ever relevant while this submenu itself is on screen.
     */
    LoadHelpBoxGfx(OBJ_VRAM0 + OBJCHR_SAVEMENU_SLOTSEL_HELPBOX * TILE_SIZE_4BPP, OBJPAL_SAVEMENU_SLOTSEL_HELPBOX);
    StartHelpBoxExt_Unk(0x20, 0x08, MSG_SAVE_COMPAT_ERASE_CONFIRM);

    proc->choice = SAVE_COMPAT_CHOICE_NONE;
    StartMenuAt(&gSaveCompatEraseConfirmMenuDef, rect, (ProcPtr) proc);
}

static void SaveCompatMenu_RouteEraseChoice(struct SaveCompatMenuProc* proc)
{
    /* Close the erase-confirm warning HelpBox unconditionally: it is only
     * relevant while the Yes/No submenu it accompanies is on screen,
     * regardless of which of the two outcomes below is taken. */
    CloseHelpBox();

    if (proc->choice == SAVE_COMPAT_CHOICE_ERASE_CONFIRMED)
        Proc_Goto(proc, PL_SAVECOMPAT_DO_ERASE);

    /* No / B-pressed cancel: fall through to PROC_GOTO(PL_SAVECOMPAT_MAIN)
     * below, returning to the Back/Erase list. No SRAM writes performed. */
}

static void SaveCompatMenu_DoErase(struct SaveCompatMenuProc* proc)
{
    /*
     * The only destructive action this proc may ever take, and only after
     * an explicit Yes/No confirmation. InitGlobalSaveInfodata() is the
     * existing format-independent whole-chip wipe/current initializer
     * (src/bmsave-lib.c) -- the same one EraseSramDataIfInvalid() already
     * uses for the SAVE_COMPAT_EMPTY case. It leaves SRAM in a state that
     * always reclassifies as SAVE_COMPAT_CURRENT.
     */
    InitGlobalSaveInfodata();

    gSaveCompatMenuActive = FALSE;
    gSaveCompatMenuLastState = ClassifySramSaveCompat();

    /* Re-enter the gate: guaranteed CURRENT now, so this recursive call
     * falls straight through to the normal save menu. proc_parent is the
     * same GameCtrlProc StartSaveMenu() itself was originally called
     * with -- Proc_StartBlocking() appends the new SaveMenuProc as an
     * additional sibling under it (proc_lockCnt is a counter, not a
     * single-child pointer -- see include/proc.h), so GameCtrlProc stays
     * correctly blocked until the real save menu ends, exactly as if this
     * compatibility proc had never existed. */
    StartSaveMenu(proc->proc_parent);
}

struct ProcCmd CONST_DATA gProcScr_SaveCompatMenu[] = {
    PROC_NAME("savecompatmenu"),
    PROC_YIELD,

    PROC_CALL(SaveCompatMenu_Init),
    PROC_CALL_ARG(NewFadeIn, 8),
    PROC_WHILE(FadeInExists),

    PROC_SLEEP(8),
    PROC_REPEAT(SaveCompatMenu_WaitDiagnosticDismiss),
    PROC_SLEEP(4),

PROC_LABEL(PL_SAVECOMPAT_MAIN),
    PROC_CALL(SaveCompatMenu_ShowMainMenu),
    PROC_WHILE(SaveCompatMenu_ChildMenuBlocked),
    PROC_CALL(SaveCompatMenu_RouteMainChoice),
    PROC_CALL(SaveCompatMenu_DoBack),
    PROC_GOTO(PL_SAVECOMPAT_END),

PROC_LABEL(PL_SAVECOMPAT_ERASE),
    PROC_CALL(SaveCompatMenu_ShowEraseConfirm),
    PROC_WHILE(SaveCompatMenu_ChildMenuBlocked),
    PROC_CALL(SaveCompatMenu_RouteEraseChoice),
    PROC_GOTO(PL_SAVECOMPAT_MAIN),

PROC_LABEL(PL_SAVECOMPAT_DO_ERASE),
    PROC_CALL(SaveCompatMenu_DoErase),

PROC_LABEL(PL_SAVECOMPAT_END),
    PROC_END,
};

void StartSaveCompatMenu(ProcPtr parent, enum SaveCompatState compat)
{
    struct SaveCompatMenuProc* proc = Proc_StartBlocking(gProcScr_SaveCompatMenu, parent);
    proc->compatState = compat;
    proc->choice = SAVE_COMPAT_CHOICE_NONE;

    gSaveCompatMenuActive = TRUE;
    gSaveCompatMenuLastState = compat;
}
