#include "global.h"

#if FE8_CO_POWERS

#include "proc.h"
#include "hardware.h"
#include "fontgrp.h"
#include "bmunit.h"
#include "bm.h"
#include "bmio.h"
#include "bmlib.h"
#include "bmdifficulty.h"
#include "sysutil.h"
#include "savemenu.h"
#include "soundwrapper.h"
#include "uiutils.h"
#include "uimenu.h"
#include "face.h"
#include "constants/characters.h"
#include "constants/classes.h"
#include "constants/songs.h"
#include "power.h"
#include "mapanim.h"

#include "ctc.h"
#include "ap.h"
#include "eventinfo.h"
#include "efxbattle.h"
#include "constants/items.h"
#include "constants/video-global.h"

#define CO_POWERS_UNIT_DISPLAY_FRAMES 5

// moves the camera onto each blue unit 
struct CoPowersProc
{
    PROC_HEADER;

    u8 unitIndex; // current unit 
};

static void CoPowers_Init(struct CoPowersProc* proc);
static void CoPowers_Step(struct CoPowersProc* proc);
static void CoPowers_Anim(struct CoPowersProc* proc);
static void CoPowers_ReturnCamera(struct CoPowersProc* proc);
struct ProcCmd CONST_DATA ProcScr_MapAnimBarrierfx2[];

CONST_DATA struct ProcCmd gProcScr_CoPowers[] = {
    PROC_NAME("COPOWERS"),
    PROC_CALL(LockGame),
    PROC_CALL(CoPowers_Init),

PROC_LABEL(0),
    PROC_CALL(CoPowers_Step),
    PROC_WHILE_EXISTS(ProcScr_CamMove),
    PROC_CALL(CoPowers_Anim),
    PROC_WHILE_EXISTS(ProcScr_MapAnimBarrierfx2),
    // PROC_SLEEP(CO_POWERS_UNIT_DISPLAY_FRAMES),
    PROC_GOTO(0),
PROC_LABEL(99),
    PROC_CALL(CoPowers_ReturnCamera),
    PROC_WHILE_EXISTS(ProcScr_CamMove),
    PROC_CALL(UnlockGame),
    PROC_END,
};

static void CoPowers_Init(struct CoPowersProc* proc)
{
    proc->unitIndex = 0;
}
static void CoPowers_ReturnCamera(struct CoPowersProc* proc)
{
    EnsureCameraOntoPosition(proc, gBmSt.playerCursor.x, gBmSt.playerCursor.y);
}
static void CoPowers_Step(struct CoPowersProc* proc)
{
    int i;
    struct Unit* unit = NULL;

    for (i = proc->unitIndex + 1; i < FACTION_BLUE + 0x40; ++i) {
        struct Unit* candidate = GetUnit(i);

        if (UNIT_IS_VALID(candidate) && !(candidate->state & (US_DEAD | US_HIDDEN | US_NOT_DEPLOYED))) {
            unit = candidate;
            break;
        }
    }

    if (!unit) {
        Proc_Goto(proc, 99);
        return;
    }

    proc->unitIndex = i;

    EnsureCameraOntoPosition(proc, unit->xPos, unit->yPos);
    // SetCursorMapPosition(unit->xPos, unit->yPos);
}

// display a glowy animation on each unit 
void MapAnimBarrierfx_Loop2(struct MAEffectProc * proc)
{
    static u8 const unk_param_list[] =
    {
        0, 0, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1,
        // 1, 1, 1, 1, 1, 1, 1, 1,
        // 1, 1, 1, 1, 1, 1, 1, 1,
        // 1, 1, 1, 1, 1, 1, 1, 1,
        // 1, 1, 1, 1, 0, 0,
        
        UINT8_MAX, // end
    };

    PutTmAnimFrameFromTsa(
        gBG2TilemapBuffer,
        proc->xDisplay / 8 - 2, proc->yDisplay / 8 - 8,
        TILEREF(BGCHR_MANIM_160, BGPAL_MANIM_4),
        4, 10, Tsa_Mapnightmare,
        unk_param_list[proc->unk48++]);

    BG_EnableSyncByMask(BG2_SYNC_BIT);

    if (unk_param_list[proc->unk48] == UINT8_MAX)
        Proc_Break(proc);
}
struct ProcCmd CONST_DATA ProcScr_MapAnimBarrierfx2[] = {
    PROC_SLEEP(1),
    PROC_CALL(MapAnimBarrierfx_Init),
    PROC_REPEAT(MapAnimBarrierfx_Loop2),
    PROC_CALL(MapSpellAnim_CommonEnd),
    PROC_END,
};
void MapAnimCallSpellAssocBarrierfx2(struct Unit * unit)
{
    struct MAEffectProc * proc;

    proc = Proc_Start(ProcScr_MapAnimBarrierfx2, PROC_TREE_3);

    proc->xDisplay = (SCREEN_TILE_X(unit->xPos) * 2 + 1) * 8;
    proc->yDisplay = (SCREEN_TILE_Y(unit->yPos) * 2 + 1) * 8;
}
static void CoPowers_Anim(struct CoPowersProc* proc)
{
    struct Unit* unit = GetUnit(proc->unitIndex); 
    if (!UNIT_IS_VALID(unit)) 
    { 
        return; 
    } 

    MapAnimCallSpellAssocBarrierfx2(unit);

} 

u8 CoPowers_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    Proc_Start(gProcScr_CoPowers, PROC_TREE_3);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

/* ---------------------------------------------------------------------- *
 * CO profile screen ("CO" map-menu entry): a full-screen, 4-page
 * commander bio, laid out with the same portrait+name header on every
 * page (like the unit stat screen's left panel, src/statscreen.c). 
 * ---------------------------------------------------------------------- */

#define CO_AFFINITY_BAR_MAX 5 // hearts drawn for a "great" matchup

enum {
    CO_SCREEN_PAGE_INFO,
    CO_SCREEN_PAGE_POWER,
    CO_SCREEN_PAGE_SUPER,
    CO_SCREEN_PAGE_AFFINITY,
    CO_SCREEN_PAGE_COUNT,
};

struct CoClassAffinity {
    const char* className;
    u8 classId;
    u8 rating; // 1-5, CO_AFFINITY_BAR_MAX hearts drawn; 3 = neutral
};

struct CoDefinition {
    const char* name;
    int faceId;
    const char* title; // shown on the info page (e.g. their epithet)
    const char* infoLine1;
    const char* infoLine2;
    const char* powerName;
    const char* powerDesc1;
    const char* powerDesc2;
    const char* superPowerName;
    const char* superPowerDesc1;
    const char* superPowerDesc2;
    const struct CoClassAffinity* affinities;
    u8 affinityCount;
};

enum {
    CO_FRANCIS,
    CO_COUNT,
};

/* Mirrors the classes actually sellable in sPurchaseGenericDefinitions
 * (src/purchase_generics.c) -- keep the class list in sync if that table
 * changes. Ratings are placeholder flavor, not balance-tuned. */
static const struct CoClassAffinity sFrancisAffinities[] = {
    { "Soldier",    CLASS_SOLDIER,       4 },
    { "Knight",     CLASS_ARMOR_KNIGHT,  5 },
    { "Mage",       CLASS_MAGE,          2 },
    { "Archer",     CLASS_ARCHER,        3 },
    { "Fighter",    CLASS_FIGHTER,       4 },
    { "Mercenary",  CLASS_MERCENARY,     3 },
    { "Cavalier",   CLASS_CAVALIER,      5 },
};

/* Temporary placeholder text -- Francis is the only CO defined so far.
 * faceId reuses CHARACTER_SETH's portrait as a stand-in pending real CO
 * art. Power/Super Power descriptions are adapted from Advance Wars 1's
 * Andy (Hyper Repair / Hyper Upgrade) as placeholder copy, to be replaced
 * with original text later. */
static const struct CoDefinition sCoDefinitions[CO_COUNT] = {
    [CO_FRANCIS] = {
        .name = "Francis",
        .faceId = CHARACTER_SETH,
        .title = "The Steadfast Commander",
        .infoLine1 = "A stalwart tactician who leads from",
        .infoLine2 = "the front and never leaves a unit behind.",
        .powerName = "Barrage",
        .powerDesc1 = "All of Francis's units are healed.",
        .powerDesc2 = " ",
        .superPowerName = "War Council",
        .superPowerDesc1 = "All of Francis's units are fully repaired,",
        .superPowerDesc2 = "rearmed, and gain a firepower boost.",
        .affinities = sFrancisAffinities,
        .affinityCount = ARRAY_COUNT(sFrancisAffinities),
    },
};

struct CoScreenSt {
    u8 coId;
    u8 page;
};

/* Group 0 -- shared/aliased with gStatScreen, gUiTmScratchA/B/C
 * (src/statscreen.c) and other group-0 EWRAM_OVERLAY users. Safe: the CO
 * screen and the unit stat screen can never be open at the same time. */
EWRAM_OVERLAY(0) struct CoScreenSt gCoScreen = {};

static const struct CoDefinition* GetCoDefinition(int coId)
{
    if (coId < 0 || coId >= CO_COUNT)
        coId = CO_FRANCIS;

    return &sCoDefinitions[coId];
}

int CoScreen_GetCoCount(void)
{
    return CO_COUNT;
}

const char* CoScreen_GetCoName(int coId)
{
    return GetCoDefinition(coId)->name;
}

#define CO_GAUGE_MAX 9999

void CoGauge_OnDamage(int faction, int amount)
{
    int slot = faction >> 6;
    int value;

    if (slot < 0 || slot >= 4 || amount <= 0)
        return;

    value = gPlaySt.coGauge[slot] + amount;

    if (value > CO_GAUGE_MAX)
        value = CO_GAUGE_MAX;

    gPlaySt.coGauge[slot] = value;
}

s16 CoGauge_Get(int faction)
{
    int slot = faction >> 6;

    if (slot < 0 || slot >= 4)
        return 0;

    return gPlaySt.coGauge[slot];
}

void CoGauge_Set(int faction, s16 value)
{
    int slot = faction >> 6;

    if (slot < 0 || slot >= 4)
        return;

    if (value < 0)
        value = 0;
    else if (value > CO_GAUGE_MAX)
        value = CO_GAUGE_MAX;

    gPlaySt.coGauge[slot] = value;
}

void CoGauge_OnPowerUsed(int faction)
{
    CoGauge_Set(faction, 0);
}

static void CoScreen_DrawHeader(void)
{
    const struct CoDefinition* co = GetCoDefinition(gCoScreen.coId);
    int fid = co->faceId;

    PutFace80x72(NULL, gBG2TilemapBuffer + TILEMAP_INDEX(1, 1), fid, 0x200, 2);

    if (GetPortraitData(fid)->img)
        ApplyPalette(Pal_FaceDisplayPortrait, 2);
    else
        ApplyPalette(Pal_FaceDisplayGenericCard, 2);

    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 2), TEXT_COLOR_SYSTEM_WHITE, co->name);
}

static void CoScreen_DrawPageInfo(const struct CoDefinition* co)
{
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 5), TEXT_COLOR_SYSTEM_GOLD, "Info");
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 7), TEXT_COLOR_SYSTEM_BLUE, co->title);
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 9), TEXT_COLOR_SYSTEM_WHITE, co->infoLine1);
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 10), TEXT_COLOR_SYSTEM_WHITE, co->infoLine2);
}

static void CoScreen_DrawPagePower(const struct CoDefinition* co)
{
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 5), TEXT_COLOR_SYSTEM_GOLD, "CO Power");
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 7), TEXT_COLOR_SYSTEM_BLUE, co->powerName);
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 9), TEXT_COLOR_SYSTEM_WHITE, co->powerDesc1);
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 10), TEXT_COLOR_SYSTEM_WHITE, co->powerDesc2);
}

static void CoScreen_DrawPageSuper(const struct CoDefinition* co)
{
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 5), TEXT_COLOR_SYSTEM_GOLD, "Super CO Power");
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 7), TEXT_COLOR_SYSTEM_BLUE, co->superPowerName);
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 9), TEXT_COLOR_SYSTEM_WHITE, co->superPowerDesc1);
    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 10), TEXT_COLOR_SYSTEM_WHITE, co->superPowerDesc2);
}

static void CoScreen_DrawAffinityBar(int x, int y, int rating)
{
    int i;

    if (rating > CO_AFFINITY_BAR_MAX)
        rating = CO_AFFINITY_BAR_MAX;

    for (i = 0; i < CO_AFFINITY_BAR_MAX; ++i) {
        PutSpecialChar(gBG0TilemapBuffer + TILEMAP_INDEX(x + i, y), TEXT_COLOR_SYSTEM_WHITE, TEXT_SPECIAL_HEART);
    }
}

static void CoScreen_DrawPageAffinity(const struct CoDefinition* co)
{
    int i;
    int y = 6;

    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, 5), TEXT_COLOR_SYSTEM_GOLD, "Class Affinity");

    for (i = 0; i < co->affinityCount; ++i) {
        const struct CoClassAffinity* affinity = &co->affinities[i];

        PutString(gBG0TilemapBuffer + TILEMAP_INDEX(12, y), TEXT_COLOR_SYSTEM_WHITE, affinity->className);
        CoScreen_DrawAffinityBar(21, y, affinity->rating);

        y += 2;
    }
}

static void CoScreen_DrawPage(void)
{
    const struct CoDefinition* co = GetCoDefinition(gCoScreen.coId);

    BG_Fill(gBG0TilemapBuffer + TILEMAP_INDEX(12, 4), 0); // clear everything right of the portrait panel

    switch (gCoScreen.page) {
    case CO_SCREEN_PAGE_INFO:
        CoScreen_DrawPageInfo(co);
        break;

    case CO_SCREEN_PAGE_POWER:
        CoScreen_DrawPagePower(co);
        break;

    case CO_SCREEN_PAGE_SUPER:
        CoScreen_DrawPageSuper(co);
        break;

    case CO_SCREEN_PAGE_AFFINITY:
        CoScreen_DrawPageAffinity(co);
        break;
    }

    PutString(gBG0TilemapBuffer + TILEMAP_INDEX(24, 18), TEXT_COLOR_SYSTEM_WHITE, "L/R Page");

    BG_EnableSyncByMask(BG0_SYNC_BIT | BG2_SYNC_BIT);
}

static void CoScreen_Setup(ProcPtr proc)
{
    gCoScreen.coId = gPlaySt.commanderId[FACTION_BLUE >> 6];
    gCoScreen.page = CO_SCREEN_PAGE_INFO;

    SetupBackgrounds(gBgConfig_SaveMenu);

    BG_Fill(gBG0TilemapBuffer, 0);
    BG_Fill(gBG1TilemapBuffer, 0);
    BG_Fill(gBG2TilemapBuffer, 0);
    BG_Fill(gBG3TilemapBuffer, 0);

    LoadUiFrameGraphics();

    gLCDControlBuffer.dispcnt.bg0_on = 1;
    gLCDControlBuffer.dispcnt.bg1_on = 1;
    gLCDControlBuffer.dispcnt.bg2_on = 1;
    gLCDControlBuffer.dispcnt.bg3_on = 1;
    gLCDControlBuffer.dispcnt.obj_on = 1;

    BG_SetPosition(0, 0, 0);
    BG_SetPosition(1, 0, 0);
    BG_SetPosition(2, 0, 0);
    BG_SetPosition(3, 0, 0);

    CoScreen_DrawHeader();
    CoScreen_DrawPage();
}

static void CoScreen_Teardown(ProcPtr proc)
{
    BG_Fill(gBG0TilemapBuffer, 0);
    BG_Fill(gBG1TilemapBuffer, 0);
    BG_Fill(gBG2TilemapBuffer, 0);
    BG_Fill(gBG3TilemapBuffer, 0);

    BG_EnableSyncByMask(0xF);

    // gLCDControlBuffer.dispcnt.bg0_on = 0;
    // gLCDControlBuffer.dispcnt.bg1_on = 0;
    // gLCDControlBuffer.dispcnt.bg2_on = 0;
    // gLCDControlBuffer.dispcnt.bg3_on = 0;
    // gLCDControlBuffer.dispcnt.obj_on = 0;

    ResetText();

    // CpuFastFill(0, gPaletteBuffer, 0x400);

    // EnablePaletteSync();
}

static void CoScreen_KeyListener(ProcPtr proc)
{
    if (gKeyStatusPtr->newKeys & B_BUTTON) {
        Proc_Break(proc);
        return;
    }

    if (gKeyStatusPtr->newKeys & (R_BUTTON | DPAD_RIGHT)) {
        gCoScreen.page = (gCoScreen.page + 1) % CO_SCREEN_PAGE_COUNT;
        CoScreen_DrawPage();
        PlaySoundEffect(SONG_SE_SYS_WINDOW_SELECT1);
    } else if (gKeyStatusPtr->newKeys & (L_BUTTON | DPAD_LEFT)) {
        gCoScreen.page = (gCoScreen.page + CO_SCREEN_PAGE_COUNT - 1) % CO_SCREEN_PAGE_COUNT;
        CoScreen_DrawPage();
        PlaySoundEffect(SONG_SE_SYS_WINDOW_SELECT1);
    }
}

CONST_DATA struct ProcCmd gProcScr_CoScreen[] = {
    PROC_NAME("COSCREEN"),
    PROC_CALL(LockGame),
    // PROC_CALL(StartFastFadeToBlack),
    // PROC_REPEAT(WaitForFade),
    PROC_CALL(BMapDispSuspend),
    PROC_SLEEP(0),
    PROC_CALL(CoScreen_Setup),

    // PROC_CALL_ARG(NewFadeIn, 16),
    // PROC_WHILE(FadeInExists),

    PROC_REPEAT(CoScreen_KeyListener),

    PROC_CALL_ARG(NewFadeOut, 16),
    PROC_WHILE(FadeOutExists),

    PROC_CALL(CoScreen_Teardown),
    PROC_SLEEP(0),
    PROC_CALL(BMapDispResume),
    PROC_CALL(RefreshBMapGraphics),
    PROC_CALL(StartFastFadeFromBlack),
    PROC_REPEAT(WaitForFade),
    PROC_CALL(UnlockGame),

    PROC_END,
};

u8 CoScreen_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    Proc_StartBlocking(gProcScr_CoScreen, PROC_TREE_3);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

#endif // FE8_CO_POWERS
