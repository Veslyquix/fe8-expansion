#include "global.h"

#if FE8_WAR_ROOM

#include "hardware.h"
#include "proc.h"
#include "fontgrp.h"
#include "uimenu.h"
#include "uiutils.h"
#include "bm.h"
#include "bmio.h"
#include "bmmap.h"
#include "bmunit.h"
#include "bmlib.h"
#include "chapterdata.h"
#include "minimap.h"
#include "eventinfo.h"
#include "worldmap.h"
#include "soundroom.h"
#include "soundwrapper.h"
#include "gamecontrol.h"
#include "warroom.h"

#include "constants/chapters.h"
#include "constants/songs.h"
#include "constants/msg.h"

/* --- Game-mode select (top-level) screen --------------------------------- */

enum WarRoomMainMenuChoice
{
    WARROOM_MAINMENU_NONE = 0,
    WARROOM_MAINMENU_CAMPAIGN,
    WARROOM_MAINMENU_WAR_ROOM,
    WARROOM_MAINMENU_SOUND_ROOM,
    WARROOM_MAINMENU_LINK_ARENA,
};

enum
{
    LBL_WARROOM_MAINMENU_LOOP = 0,
    LBL_WARROOM_MAINMENU_DONE = 1,
};

struct WarRoomMainMenuProc
{
    PROC_HEADER;
};

EWRAM_DATA static u8 sWarRoomMainMenuChoice = WARROOM_MAINMENU_NONE;

static int WarRoomMainMenu_RowDraw(struct MenuProc *menu, struct MenuItemProc *item)
{
    if (item->availability == MENU_DISABLED)
        Text_SetColor(&item->text, TEXT_COLOR_SYSTEM_GRAY);
    else
        Text_SetColor(&item->text, TEXT_COLOR_SYSTEM_WHITE);

    Text_DrawString(&item->text, GetStringFromIndex(item->def->nameMsgId));

    PutText(
        &item->text,
        TILEMAP_LOCATED(BG_GetMapBuffer(menu->frontBg), item->xTile, item->yTile));

    return 0;
}

static u8 WarRoomMainMenu_RowSelected(struct MenuProc *menu, struct MenuItemProc *item)
{
    (void)menu;

    sWarRoomMainMenuChoice = (u8)item->def->helpMsgId;

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_CLEAR | MENU_ACT_SND6A;
}

/* Rows in on-screen order. Only Campaign/War Room/Sound Room/Link Arena are
 * enabled today -- the rest are planned features, shown greyed out with no
 * onSelected effect (MENU_DISABLED rows are never selectable, so pressing A
 * on them is already a no-op via the menu engine itself). */
static CONST_DATA struct MenuItemDef sWarRoomMainMenuItems[] =
{
    { "", MSG_MAINMENU_CAMPAIGN,     WARROOM_MAINMENU_CAMPAIGN,   0, 0, MenuAlwaysEnabled,  WarRoomMainMenu_RowDraw, WarRoomMainMenu_RowSelected, 0, 0, 0 },
    { "", MSG_MAINMENU_WAR_ROOM,     WARROOM_MAINMENU_WAR_ROOM,   0, 0, MenuAlwaysEnabled,  WarRoomMainMenu_RowDraw, WarRoomMainMenu_RowSelected, 0, 0, 0 },
    { "", MSG_MAINMENU_BATTLE_TOWER, WARROOM_MAINMENU_NONE,       0, 0, MenuAlwaysDisabled, WarRoomMainMenu_RowDraw, WarRoomMainMenu_RowSelected, 0, 0, 0 },
    { "", MSG_MAINMENU_DESIGN_ROOM,  WARROOM_MAINMENU_NONE,       0, 0, MenuAlwaysDisabled, WarRoomMainMenu_RowDraw, WarRoomMainMenu_RowSelected, 0, 0, 0 },
    { "", MSG_MAINMENU_VS,           WARROOM_MAINMENU_NONE,       0, 0, MenuAlwaysDisabled, WarRoomMainMenu_RowDraw, WarRoomMainMenu_RowSelected, 0, 0, 0 },
    { "", MSG_MAINMENU_RECORDS,      WARROOM_MAINMENU_NONE,       0, 0, MenuAlwaysDisabled, WarRoomMainMenu_RowDraw, WarRoomMainMenu_RowSelected, 0, 0, 0 },
    { "", MSG_MAINMENU_SHOP,         WARROOM_MAINMENU_NONE,       0, 0, MenuAlwaysDisabled, WarRoomMainMenu_RowDraw, WarRoomMainMenu_RowSelected, 0, 0, 0 },
    { "", MSG_MAINMENU_SOUND_ROOM,   WARROOM_MAINMENU_SOUND_ROOM, 0, 0, MenuAlwaysEnabled,  WarRoomMainMenu_RowDraw, WarRoomMainMenu_RowSelected, 0, 0, 0 },
    { "", MSG_MAINMENU_LINK_ARENA,   WARROOM_MAINMENU_LINK_ARENA, 0, 0, MenuAlwaysEnabled,  WarRoomMainMenu_RowDraw, WarRoomMainMenu_RowSelected, 0, 0, 0 },
    MenuItemsEnd,
};

static void WarRoomMainMenu_PrepareScreen(void)
{
    SetupBackgrounds(NULL);
    SetPrimaryHBlankHandler(NULL);

    ResetText();
    ApplySystemObjectsPalettes();
    LoadUiFrameGraphics();
    LoadObjUIGfx();

    SetDispEnable(1, 1, 1, 1, 1);

    /* The title screen leaves windows/blending configured for its own
     * effects (e.g. a vignette or fade blended against the backdrop) --
     * without resetting them here, BG content still renders into the BG
     * layers (visible in a tile/BG viewer) but the compositor blends/masks
     * it down to nothing on the actual screen. Mirrors
     * SaveMenu_ResetLcdFormDifficulty's own win0_on/win1_on/objWin_on reset
     * (src/savemenu.c), generalized via the SetWinEnable macro. */
    SetWinEnable(0, 0, 0);
    SetBlendConfig(0, 0, 0, 0);

    BG_SetPosition(BG_0, 0, 0);
    BG_SetPosition(BG_1, 0, 0);
    BG_SetPosition(BG_2, 0, 0);
    BG_SetPosition(BG_3, 0, 0);
}

static CONST_DATA struct MenuDef gWarRoomMainMenuDef =
{
    {6, 0, 18, 0},
    0,
    sWarRoomMainMenuItems,
    0,
    0,
    0,
    0, /* onBPress: intentionally NULL -- there is nowhere to go back to
        * from the first screen after the title. */
    0,
    0,
};

static void WarRoomMainMenu_PrepareAndOpen(struct WarRoomMainMenuProc *proc)
{
    WarRoomMainMenu_PrepareScreen();

    sWarRoomMainMenuChoice = WARROOM_MAINMENU_NONE;

    StartMenu(&gWarRoomMainMenuDef, proc);
}

static u8 WarRoomMainMenu_ChildBlocked(struct WarRoomMainMenuProc *proc)
{
    return proc->proc_lockCnt > 0;
}

/* --- Chapter select ("War Room" proper) ----------------------------------- */

static CONST_DATA u8 sWarRoomChapterIds[] =
{
    CHAPTER_L_PROLOGUE,
    CHAPTER_L_1,
    CHAPTER_L_2,
    CHAPTER_L_4,
    CHAPTER_L_5X,
    CHAPTER_L_6,
    CHAPTER_L_8,
};

#define WARROOM_CHAPTER_COUNT ((int)(sizeof(sWarRoomChapterIds) / sizeof(sWarRoomChapterIds[0])))
#define WARROOM_VISIBLE_ROWS 5

/* Minimap preview panel: top-left corner it's drawn at, in the mode
 * select's BG0 tilemap, and how many minimap tiles (each covering a 2x2
 * block of map tiles -- see DrawMinimapInternal, src/minimap.c) it shows
 * before clipping. Chapters larger than this only show their own top-left
 * corner -- a deliberate simplification, not a bug: a scrollable/full-size
 * preview would need its own camera, which this screen doesn't have. */
#define WARROOM_MINIMAP_TILE_X 20
#define WARROOM_MINIMAP_TILE_Y 4
#define WARROOM_MINIMAP_TILES_W 10
#define WARROOM_MINIMAP_TILES_H 10

struct WarRoomChapterSelectProc
{
    PROC_HEADER;

    u8 cursor;
    u8 topIndex;
    bool8 committed;

    struct Text titleText;
    struct Text rowText[WARROOM_VISIBLE_ROWS];
};

static void WarRoomChapterSelect_DrawMinimap(struct WarRoomChapterSelectProc *proc)
{
    u8 chapterId = sWarRoomChapterIds[proc->cursor];
    u16 *vram = (u16 *)BG_CHR_ADDR(2);
    int chr = ((u32)vram << 15) >> 20;
    int width, height;
    int x, y;

    DrawMinimap(chapterId, vram, -1);

    width = gBmMapSize.x / 2;
    height = gBmMapSize.y / 2;

    if (width > WARROOM_MINIMAP_TILES_W)
        width = WARROOM_MINIMAP_TILES_W;
    if (height > WARROOM_MINIMAP_TILES_H)
        height = WARROOM_MINIMAP_TILES_H;

    for (y = 0; y < WARROOM_MINIMAP_TILES_H; y++)
    {
        for (x = 0; x < WARROOM_MINIMAP_TILES_W; x++)
        {
            u16 *dest = gBG0TilemapBuffer + TILEMAP_INDEX(WARROOM_MINIMAP_TILE_X + x, WARROOM_MINIMAP_TILE_Y + y);

            if (x < width && y < height)
                *dest = chr + y * (gBmMapSize.x / 2) + x;
            else
                *dest = 0;
        }
    }

    BG_EnableSyncByMask(BG0_SYNC_BIT);
}

static void WarRoomChapterSelect_Redraw(struct WarRoomChapterSelectProc *proc)
{
    int i;

    TileMap_FillRect(TILEMAP_LOCATED(gBG0TilemapBuffer, 1, 2), 18, 2, 0);
    Text_DrawString(&proc->titleText, GetStringFromIndex(MSG_WARROOM_TITLE));
    PutText(&proc->titleText, TILEMAP_LOCATED(gBG0TilemapBuffer, 1, 2));

    TileMap_FillRect(TILEMAP_LOCATED(gBG0TilemapBuffer, 1, 4), 18, WARROOM_VISIBLE_ROWS * 2, 0);

    for (i = 0; i < WARROOM_VISIBLE_ROWS; i++)
    {
        int chapterSlot = proc->topIndex + i;
        int y = 4 + i * 2;

        if (chapterSlot >= WARROOM_CHAPTER_COUNT)
            continue;

        Text_SetColor(&proc->rowText[i],
            (chapterSlot == proc->cursor) ? TEXT_COLOR_SYSTEM_GOLD : TEXT_COLOR_SYSTEM_WHITE);

        Text_DrawString(&proc->rowText[i], GetChapterTitleName(sWarRoomChapterIds[chapterSlot]));
        PutText(&proc->rowText[i], TILEMAP_LOCATED(gBG0TilemapBuffer, 1, y));
    }

    WarRoomChapterSelect_DrawMinimap(proc);
}

static void WarRoomChapterSelect_Init(struct WarRoomChapterSelectProc *proc)
{
    int i;

    proc->cursor = 0;
    proc->topIndex = 0;
    proc->committed = FALSE;

    WarRoomMainMenu_PrepareScreen();

    InitText(&proc->titleText, 20);
    Text_SetParams(&proc->titleText, 0, TEXT_COLOR_SYSTEM_GOLD);

    for (i = 0; i < WARROOM_VISIBLE_ROWS; i++)
    {
        InitText(&proc->rowText[i], 20);
        Text_SetParams(&proc->rowText[i], 0, TEXT_COLOR_SYSTEM_WHITE);
    }

    WarRoomChapterSelect_Redraw(proc);
}

static void WarRoomChapterSelect_Loop(struct WarRoomChapterSelectProc *proc)
{
    u16 newKeys = gKeyStatusPtr->newKeys;

    if (newKeys & DPAD_DOWN)
    {
        if (proc->cursor + 1 < WARROOM_CHAPTER_COUNT)
        {
            proc->cursor++;
            if (proc->cursor >= proc->topIndex + WARROOM_VISIBLE_ROWS)
                proc->topIndex++;

            PlaySoundEffect(SONG_SE_SYS_CURSOR_UD1);
            WarRoomChapterSelect_Redraw(proc);
        }
    }
    else if (newKeys & DPAD_UP)
    {
        if (proc->cursor > 0)
        {
            proc->cursor--;
            if (proc->cursor < proc->topIndex)
                proc->topIndex--;

            PlaySoundEffect(SONG_SE_SYS_CURSOR_UD1);
            WarRoomChapterSelect_Redraw(proc);
        }
    }
    else if (newKeys & A_BUTTON)
    {
        proc->committed = TRUE;
        PlaySoundEffect(SONG_SE_SYS_WINDOW_SELECT1);
        Proc_Break(proc);
    }
    else if (newKeys & B_BUTTON)
    {
        proc->committed = FALSE;
        PlaySoundEffect(SONG_SE_SYS_WINDOW_CANSEL1);
        Proc_Break(proc);
    }
}

/* Same bootstrap sequence the debug hub's "Fast Boot: Chapter N" launcher
 * uses (see GameControl_PostIntro, src/gamecontrol.c): a from-scratch new
 * game, dropped directly into the given chapter with no save data and no
 * world map. warRoomStateBits marks the run as War Room-originated; nothing
 * else in this build's own code reads it yet, but it's here for future
 * chapter/prep-screen code that needs to tell a War Room throwaway battle
 * apart from a real playthrough. */
static void WarRoom_BootstrapChapter(u8 chapterId)
{
    InitPlayConfig(0, 0);
    gPlaySt.chapterModeIndex = CHAPTER_MODE_COMMON;
    ResetPermanentFlags();
    ResetChapterFlags();
    InitUnits();
    gPlaySt.chapterIndex = chapterId;
    gPlaySt.warRoomStateBits |= WARROOM_FLAG_ACTIVE;

    GmDataInit();
}

static void WarRoomChapterSelect_Finish(struct WarRoomChapterSelectProc *proc)
{
    struct WarRoomMainMenuProc *mainMenuProc;
    struct GameCtrlProc *gameCtrl;

    if (!proc->committed)
        return;

    WarRoom_BootstrapChapter(sWarRoomChapterIds[proc->cursor]);

    /* proc_parent is the War Room main-menu screen (see
     * WarRoomMainMenu_Dispatch below, which starts this chapter-select
     * screen as a blocking child of itself); its own proc_parent is the
     * GameCtrlProc that started the whole mode-select flow
     * (LGAMECTRL_MODE_SELECT, src/gamecontrol.c). */
    mainMenuProc = (struct WarRoomMainMenuProc *)proc->proc_parent;
    gameCtrl = (struct GameCtrlProc *)mainMenuProc->proc_parent;

    Proc_Goto(gameCtrl, LGAMECTRL_WAR_ROOM_EXEC_BM);
    Proc_End(mainMenuProc);
}

static CONST_DATA struct ProcCmd gProcScr_WarRoomChapterSelect[] =
{
    PROC_CALL(WarRoomChapterSelect_Init),
    PROC_CALL(FadeInBlackSpeed20),
    PROC_YIELD,
    PROC_REPEAT(WarRoomChapterSelect_Loop),
    PROC_CALL(WarRoomChapterSelect_Finish),
    PROC_END,
};

/* --- Mode select dispatch/loop --------------------------------------------- */

static void WarRoomMainMenu_Dispatch(struct WarRoomMainMenuProc *proc)
{
    switch (sWarRoomMainMenuChoice)
    {
    case WARROOM_MAINMENU_CAMPAIGN:
        Proc_Goto((struct GameCtrlProc *)proc->proc_parent, LGAMECTRL_EXEC_SAVEMENU);
        Proc_Goto(proc, LBL_WARROOM_MAINMENU_DONE);
        return;

    case WARROOM_MAINMENU_LINK_ARENA:
        Proc_Goto((struct GameCtrlProc *)proc->proc_parent, 12);
        Proc_Goto(proc, LBL_WARROOM_MAINMENU_DONE);
        return;

    case WARROOM_MAINMENU_SOUND_ROOM:
        StartSoundRoomScreen(proc);
        return; /* falls back into the loop label -> mode select reshown */

    case WARROOM_MAINMENU_WAR_ROOM:
        /* Blocking: WarRoomChapterSelect_Finish above either ends this
         * whole screen itself (chapter chosen) or just returns (B
         * cancelled), in which case we fall back into the loop label and
         * reshow the mode select list below. */
        Proc_StartBlocking(gProcScr_WarRoomChapterSelect, proc);
        return;

    default:
        return;
    }
}

static CONST_DATA struct ProcCmd gProcScr_WarRoomMainMenu[] =
{
PROC_LABEL(LBL_WARROOM_MAINMENU_LOOP),
    PROC_CALL(WarRoomMainMenu_PrepareAndOpen),
    PROC_CALL(FadeInBlackSpeed20),
    PROC_YIELD,
    PROC_WHILE(WarRoomMainMenu_ChildBlocked),
    PROC_CALL(WarRoomMainMenu_Dispatch),
    PROC_YIELD,
    PROC_GOTO(LBL_WARROOM_MAINMENU_LOOP),

PROC_LABEL(LBL_WARROOM_MAINMENU_DONE),
    PROC_END,
};

void StartWarRoomMainMenu(ProcPtr parent)
{
    Proc_StartBlocking(gProcScr_WarRoomMainMenu, parent);
}

#endif // FE8_WAR_ROOM
