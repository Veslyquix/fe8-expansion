#include "global.h"

#if FE8_CO_POWERS

#include "proc.h"
#include "hardware.h"
#include "fontgrp.h"
#include "bmunit.h"
#include "bm.h"
#include "bmio.h"
#include "bmlib.h"
#include "bmudisp.h"
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
#include "statscreen.h"
#include "ctc.h"
#include "ap.h"
#include "eventinfo.h"
#include "efxbattle.h"
#include "constants/items.h"
#include "constants/video-global.h"
#include "icon.h"

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
    // PROC_CALL(LockGame),
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
    // PROC_CALL(UnlockGame),
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

#define CO_AFFINITY_ROW_MAX 8 // max class-affinity rows this screen draws (DrawStatWithBar's `num` must stay small and unique)

enum {
    CO_SCREEN_PAGE_INFO,
    CO_SCREEN_PAGE_POWER,
    CO_SCREEN_PAGE_SUPER,
    CO_SCREEN_PAGE_AFFINITY,
    CO_SCREEN_PAGE_COUNT,
};

struct CoClassAffinity {
    const char* className; // unused for display now (SMS icon + bar replace name+hearts); kept for reference/tooling
    u8 classId;
    u8 rating; // 1-5; not wired up to the bar yet, see CoScreen_DrawPageAffinity
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
    CO_ONEILL,
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

/* O'Neill leans hard into offense, like Flak; weak with anything magical. */
static const struct CoClassAffinity sOneillAffinities[] = {
    { "Soldier",    CLASS_SOLDIER,       3 },
    { "Knight",     CLASS_ARMOR_KNIGHT,  2 },
    { "Mage",       CLASS_MAGE,          1 },
    { "Archer",     CLASS_ARCHER,        3 },
    { "Fighter",    CLASS_FIGHTER,       5 },
    { "Mercenary",  CLASS_MERCENARY,     4 },
    { "Cavalier",   CLASS_CAVALIER,      4 },
};

/* Temporary placeholder text/portraits -- faceId reuses existing vanilla
 * character portraits as stand-ins pending real CO art.
 *
 * Francis: Power/Super Power descriptions are adapted from Advance Wars
 * 1's Andy (Hyper Repair / Hyper Upgrade) as placeholder copy.
 *
 * O'Neill: Power/Super Power descriptions are adapted from Advance Wars
 * 1's Flak (Barrage / Brutal Barrage) as placeholder copy. */
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
    [CO_ONEILL] = {
        .name = "O'Neill",
        .faceId = CHARACTER_EIRIKA,
        .title = "The Reckless Brawler",
        .infoLine1 = "A brash commander who trusts raw",
        .infoLine2 = "firepower over careful planning.",
        .powerName = "Barrage",
        .powerDesc1 = "All of O'Neill's units gain +10%",
        .powerDesc2 = "firepower for the turn.",
        .superPowerName = "Brutal Barrage",
        .superPowerDesc1 = "All of O'Neill's units gain +20%",
        .superPowerDesc2 = "firepower and +10% defense for the turn.",
        .affinities = sOneillAffinities,
        .affinityCount = ARRAY_COUNT(sOneillAffinities),
    },
};

struct CoScreenSt {
    u8 coId;
};

/* Group 0 -- shared/aliased with gStatScreen, gUiTmScratchA/B/C
 * (src/statscreen.c) and other group-0 EWRAM_OVERLAY users. Safe: the CO
 * screen and the unit stat screen can never be open at the same time. */
EWRAM_OVERLAY(0) struct CoScreenSt gCoScreen = {};

/* True only during CoCommanderFade_* (Up/Down brightness fade), never
 * during a page slide -- lets CoScreen_DrawAffinitySprites tell the two
 * transitions apart (see its comment). */
static bool8 sCoCommanderFading = FALSE;

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

/* gStatScreen.text[] slots this screen borrows (see the EWRAM_OVERLAY(0)
 * comment on gCoScreen above -- safe since this screen and the unit stat
 * screen never run at the same time). Each slot needs its own struct Text
 * handle, InitText'd to the string's actual width, before PutDrawText can
 * draw into it -- passing NULL/an uninitialized handle is what left the
 * screen black. */
enum {
    CO_TEXT_HEADER,
    CO_TEXT_LABEL,
    CO_TEXT_SUBTITLE,
    CO_TEXT_LINE0,
    CO_TEXT_LINE1,
    CO_TEXT_COUNT,
};

/* Class-affinity row layout (page 4): local tile y of the first row and
 * the spacing between rows, in the gUiTmScratchA/C page-region coordinate
 * space CoScreen_DrawPageAffinity uses for the stat bars. The class SMS
 * icons are OBJ sprites instead (see CoScreen_DrawAffinitySprites), drawn
 * in real screen pixel coordinates every frame -- sprites aren't part of
 * the BG tile scratch buffers, same as how the page-number arrows/mu
 * platform are also plain OBJ sprites unaffected by the page slide. */
#define CO_AFFINITY_ROW_Y0 2
#define CO_AFFINITY_ROW_STEP 2
#define CO_AFFINITY_ICON_TILE_X (CO_PAGE_X + 1)
#define CO_AFFINITY_BAR_TILE_X 6

/* Page-content area, same footprint statscreen.c's own page region uses
 * (see gUiTmScratchA/C, sized exactly for an 18x18 area) -- screen tile
 * (CO_PAGE_X, CO_PAGE_Y) is scratch-buffer-local (0, 0). Sits on the LEFT
 * side of the screen; the portrait sits on the right (see CO_PORTRAIT_X
 * below), outside this rect entirely, which is why the header survives
 * page/commander slides untouched, exactly like statscreen.c's own left
 * panel survives its (mirror-image, portrait-on-the-left) page slides. */
#define CO_PAGE_X 1
#define CO_PAGE_Y 2
#define CO_PAGE_W 18
#define CO_PAGE_H 18

/* Portrait + name, right of the page-content area (see CO_PAGE_X/_W). */
#define CO_PORTRAIT_X (CO_PAGE_X + CO_PAGE_W)

static void CoScreen_PutText(int slot, u16* tm, int color, const char* str)
{
    struct Text* text = &gStatScreen.text[slot];

    InitText(text, (GetStringTextLen(str) + 8) / 8);
    PutDrawText(text, tm, color, 0, 0, str);
}

static void CoScreen_DrawHeader(void)
{
    const struct CoDefinition* co = GetCoDefinition(gCoScreen.coId);
    int fid = co->faceId;

    PutFace80x72(NULL, gBG2TilemapBuffer + TILEMAP_INDEX(CO_PORTRAIT_X, 1), fid, 0x4E0, 11);
    DrawUiFrame(
        BG_GetMapBuffer(3),            // back BG
        0x13, 0, 11, 11, TILEREF(0, 0), 2); // style 

    if (GetPortraitData(fid)->img)
        ApplyPalette(Pal_FaceDisplayPortrait, 2);
    else
        ApplyPalette(Pal_FaceDisplayGenericCard, 2);

    EnablePaletteSync();
    CoScreen_PutText(CO_TEXT_HEADER, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PORTRAIT_X+1, 10), TEXT_COLOR_SYSTEM_WHITE, co->name);
}

/* Everything below draws into the gUiTmScratchA/C page-region scratch
 * buffers (statscreen.c) at coordinates local to that 18x18 region, not
 * the real screen -- CoScreen_DrawPage/CoPageSlide_OnLoop below copy the
 * finished scratch content onto the real BG0/BG2 at (CO_PAGE_X, CO_PAGE_Y),
 * same two-buffer approach DisplayPage0/1/2 + PageSlide_OnLoop use. */

static void CoScreen_DrawPageInfo(const struct CoDefinition* co)
{
    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(0, 0), TEXT_COLOR_SYSTEM_GOLD, "Info");
    CoScreen_PutText(CO_TEXT_SUBTITLE, gUiTmScratchA + TILEMAP_INDEX(0, 2), TEXT_COLOR_SYSTEM_BLUE, co->title);
    CoScreen_PutText(CO_TEXT_LINE0, gUiTmScratchA + TILEMAP_INDEX(0, 4), TEXT_COLOR_SYSTEM_WHITE, co->infoLine1);
    CoScreen_PutText(CO_TEXT_LINE1, gUiTmScratchA + TILEMAP_INDEX(0, 6), TEXT_COLOR_SYSTEM_WHITE, co->infoLine2);
}

static void CoScreen_DrawPagePower(const struct CoDefinition* co)
{
    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(0, 0), TEXT_COLOR_SYSTEM_GOLD, "CO Power");
    CoScreen_PutText(CO_TEXT_SUBTITLE, gUiTmScratchA + TILEMAP_INDEX(0, 2), TEXT_COLOR_SYSTEM_BLUE, co->powerName);
    CoScreen_PutText(CO_TEXT_LINE0, gUiTmScratchA + TILEMAP_INDEX(0, 4), TEXT_COLOR_SYSTEM_WHITE, co->powerDesc1);
    CoScreen_PutText(CO_TEXT_LINE1, gUiTmScratchA + TILEMAP_INDEX(0, 6), TEXT_COLOR_SYSTEM_WHITE, co->powerDesc2);
}

static void CoScreen_DrawPageSuper(const struct CoDefinition* co)
{
    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(0, 0), TEXT_COLOR_SYSTEM_GOLD, "Super CO Power");
    CoScreen_PutText(CO_TEXT_SUBTITLE, gUiTmScratchA + TILEMAP_INDEX(0, 2), TEXT_COLOR_SYSTEM_BLUE, co->superPowerName);
    CoScreen_PutText(CO_TEXT_LINE0, gUiTmScratchA + TILEMAP_INDEX(0, 4), TEXT_COLOR_SYSTEM_WHITE, co->superPowerDesc1);
    CoScreen_PutText(CO_TEXT_LINE1, gUiTmScratchA + TILEMAP_INDEX(0, 6), TEXT_COLOR_SYSTEM_WHITE, co->superPowerDesc2);
}
void DrawCoInfoBar(int num, int x, int y, int base, int total, int max)
{
    int diff = total - base;

    // PutNumberOrBlank(gUiTmScratchA + TILEMAP_INDEX(x, y),
        // (base == max) ? TEXT_COLOR_SYSTEM_GREEN : TEXT_COLOR_SYSTEM_BLUE, base);

    // PutNumberBonus(diff, gUiTmScratchA + TILEMAP_INDEX(x + 1, y));

    if (total > 30)
    {
        total = 30;
        diff = total - base;
    }

    DrawStatBarGfx(0x480 + num*6, 6,
        gUiTmScratchC + TILEMAP_INDEX(x - 2, y + 1),
        TILEREF(0, STATSCREEN_BGPAL_6), max * 41 / 30, base * 41 / 30, diff * 41 / 30);
}
static void CoScreen_DrawPageAffinity(const struct CoDefinition* co)
{
    int i;
    int y = CO_AFFINITY_ROW_Y0;

    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(0, 0), TEXT_COLOR_SYSTEM_GOLD, "Class Affinity");

    /* Bars are all half-filled for now (base == total, half of max) --
     * real per-class affinity values aren't wired up yet. DrawStatWithBar
     * (src/statscreen.c) needs a small unique `num` per simultaneously
     * visible bar (it owns num*6 VRAM tiles for its bar graphic), which
     * the row index i provides. */
     
    // pixels long. base in yellow. if total is higher, those pixels in green. if max, all green. 
    u8 val[CO_AFFINITY_ROW_MAX] = { 12, 8, 14, 6, 16, 4, 22, 0 } ;
    // u8 val1[CO_AFFINITY_ROW_MAX] = { 12, 8, 14, 6, 16, 4, 22, 0 } ;
    for (i = 0; i < co->affinityCount && i < CO_AFFINITY_ROW_MAX; ++i) {
        DrawCoInfoBar(i, CO_AFFINITY_BAR_TILE_X, y, 5, val[i], 20);

        y += CO_AFFINITY_ROW_STEP;
    }
}

/* Class SMS icons for the affinity page -- OBJ sprites, so they need
 * redrawing every frame (see gProcScr_CoPageNumCtrl below), not just once
 * like the tile-based bars above. PutUnitSpriteForClassId (src/bmudisp.c)
 * is used instead of PutUiUnitSprite because there's no real struct Unit
 * for a purchasable class definition -- PutUnitSpriteForClassId is the
 * same SMS icon draw, just keyed by class id directly (see its other
 * callers: src/uisupport.c, src/prep_itemscreen.c, src/bonusclaim.c). */
static void CoScreen_DrawAffinitySprites(ProcPtr proc)
{
    const struct CoDefinition* co;
    int i;
    int y;

    if (gStatScreen.page != CO_SCREEN_PAGE_AFFINITY)
        return;

    /* Suppressed during a page slide (content underneath is shifting
     * position, and these sprites don't slide with it -- see the comment
     * above), but NOT during a commander fade: that's a pure brightness
     * blend over everything already on screen (SetBlendTargetA includes
     * the OBJ layer), so keeping these sprites drawn each frame during it
     * is what makes them fade along with the portrait instead of just
     * vanishing. */
    if (gStatScreen.inTransition && !sCoCommanderFading)
        return;

    co = GetCoDefinition(gCoScreen.coId);
    y = CO_AFFINITY_ROW_Y0;

    for (i = 0; i < co->affinityCount && i < CO_AFFINITY_ROW_MAX; ++i) {
        PutUnitSpriteForClassId(0,
            CO_AFFINITY_ICON_TILE_X * 8,
            (CO_PAGE_Y + y) * 8,
            0xC800,
            co->affinities[i].classId);

        y += CO_AFFINITY_ROW_STEP;
    }
    ForceSyncUnitSpriteSheet();
}

static void CoScreen_DrawPage(void)
{
    const struct CoDefinition* co = GetCoDefinition(gCoScreen.coId);

    ResetText();

    CpuFastFill(0, gUiTmScratchA, sizeof(u16) * 0x280);
    CpuFastFill(0, gUiTmScratchC, sizeof(u16) * 0x240);

    switch (gStatScreen.page) {
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
}

/* Page/commander transition slide -- a port of statscreen.c's
 * PageSlide_OnLoop/StartPageSlide (sPageSlideOffsetLut, gProcScr_SSPageSlide),
 * reusing the same gUiTmScratchA/C double-buffer approach and struct
 * StatScreenEffectProc, but redrawing via CoScreen_DrawHeader/DrawPage
 * instead of the unit-stat-screen-specific DisplayLeftPanel/DisplayPage
 * (those are hardwired to gStatScreen.unit, so can't be reused directly).
 * DPAD_LEFT/RIGHT move to the next page; DPAD_UP/DOWN move to the next
 * commander -- both drive this same slide, just updating gStatScreen.page
 * or gCoScreen.coId beforehand (see CoScreen_KeyListener). The header
 * (portrait+name) is cheap to redraw unconditionally on every slide, so
 * there's no need to special-case "page only" vs. "commander changed". */
static s8 CONST_DATA sCoPageSlideOffsetLut[] = {
    // transition page out
    -4, -7, -10, -12, -14,

    INT8_MAX, // draw new page

    // transition page in
    13, 9, 7, 5, 3, 2, 1, 0,

    INT8_MIN, // end
};

static void CoPageSlide_OnLoop(struct StatScreenEffectProc* proc)
{
    int off;
    int len, dstOff, srcOff;

    TileMap_FillRect(gBG0TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H, 0);
    TileMap_FillRect(gBG2TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H, 0);

    off = sCoPageSlideOffsetLut[proc->timer];

    if (off == INT8_MAX) {
        CoScreen_DrawHeader();
        CoScreen_DrawPage();

        proc->timer++;
        off = sCoPageSlideOffsetLut[proc->timer];
    }

    if (proc->key & (DPAD_LEFT | DPAD_UP))
        off = -off;

    len = CO_PAGE_W - (off < 0 ? -off : off);

    if (off < 0) {
        dstOff = 0;
        srcOff = -off;
    } else {
        dstOff = off;
        srcOff = 0;
    }

    TileMap_CopyRect(
        gUiTmScratchA + srcOff,
        gBG0TilemapBuffer + dstOff + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y),
        len, CO_PAGE_H);

    TileMap_CopyRect(
        gUiTmScratchC + srcOff,
        gBG2TilemapBuffer + dstOff + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y),
        len, CO_PAGE_H);

    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT | BG2_SYNC_BIT);

    proc->timer++;
    off = sCoPageSlideOffsetLut[proc->timer];

    if (off == INT8_MIN)
        Proc_Break(proc);
}

static void CoPageSlide_OnEnd(struct StatScreenEffectProc* proc)
{
    gStatScreen.inTransition = FALSE;
}

CONST_DATA struct ProcCmd gProcScr_CoPageSlide[] = {
    PROC_REPEAT(CoPageSlide_OnLoop),
    PROC_CALL(CoPageSlide_OnEnd),

    PROC_END,
};

static void CoStartSlide(u16 key, struct Proc* parent)
{
    struct StatScreenEffectProc* proc;

    if (Proc_Find(gProcScr_CoPageSlide))
        return;

    PlaySoundEffect(SONG_6F);
    ResetUnitSpriteHover();

    proc = (void*)Proc_StartBlocking(gProcScr_CoPageSlide, parent);

    proc->timer = 0;
    proc->key = key;

    gStatScreen.pageSlideKey = key;
    gStatScreen.inTransition = TRUE;
}

/* Commander (Up/Down) transition -- ported from statscreen.c's
 * "unit slide" (UnitSlide_InitFadeOut/FadeOutLoop/InitFadeIn/FadeInLoop,
 * StartUnitSlide/gProcScr_SSUnitSlide), which is a *different* mechanism
 * from the page slide above: on a unit change, vanilla doesn't shift
 * tiles -- it fades the whole panel to black via the GBA's brightness
 * blend effect (SetBlendConfig effect 3), redraws everything at the
 * midpoint (UnitSlide_SetNewUnit calls StatScreen_Display fresh, which
 * includes the portrait), then fades back in. That's what makes the
 * portrait "slide": vanilla's version also drifts gStatScreen.mu (the
 * little walking map-sprite icon) up/down during the fade via
 * SetMuScreenPosition, but the CO screen has no equivalent on-map sprite
 * to move, so only the brightness fade is ported here -- the portrait and
 * page both redraw together at the blackout point, same as vanilla. */
static void CoCommanderFade_InitOut(struct StatScreenEffectProc* proc)
{
    gStatScreen.inTransition = TRUE;
    sCoCommanderFading = TRUE;

    proc->timer = 0;

    SetBlendTargetA(1, 1, 1, 1, 1);
}

static void CoCommanderFade_OutLoop(struct StatScreenEffectProc* proc)
{
    SetBlendConfig(3, 0, 0, proc->timer);

    proc->timer += 2;

    if (proc->timer > 0x10) {
        proc->timer = 0x10;
        SetBlendConfig(3, 0, 0, proc->timer);
        Proc_Break(proc);
    }
}

static void CoCommanderFade_SetNewCo(struct StatScreenEffectProc* proc)
{
    CoScreen_DrawHeader();
    CoScreen_DrawPage();

    TileMap_CopyRect(gUiTmScratchA, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);
    TileMap_CopyRect(gUiTmScratchC, gBG2TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);

    BG_EnableSyncByMask(BG0_SYNC_BIT | BG2_SYNC_BIT);
}

static void CoCommanderFade_InitIn(struct StatScreenEffectProc* proc)
{
    proc->timer = 0x10;
}

static void CoCommanderFade_InLoop(struct StatScreenEffectProc* proc)
{
    proc->timer -= 2;

    if (proc->timer <= 0) {
        proc->timer = 0;
        SetBlendConfig(3, 0, 0, 0);
        SetDefaultColorEffects();
        gStatScreen.inTransition = FALSE;
        sCoCommanderFading = FALSE;
        Proc_Break(proc);
        return;
    }

    SetBlendConfig(3, 0, 0, proc->timer);
}

CONST_DATA struct ProcCmd gProcScr_CoCommanderFade[] = {
    PROC_CALL(CoCommanderFade_InitOut),
    PROC_REPEAT(CoCommanderFade_OutLoop),
    PROC_CALL(CoCommanderFade_SetNewCo),
    PROC_CALL(CoCommanderFade_InitIn),
    PROC_REPEAT(CoCommanderFade_InLoop),

    PROC_END,
};

static void CoStartCommanderFade(struct Proc* parent)
{
    if (Proc_Find(gProcScr_CoCommanderFade))
        return;

    PlaySoundEffect(SONG_C8);

    Proc_StartBlocking(gProcScr_CoCommanderFade, parent);
}

enum
{
    // Magical constants

    // Neutral left arrow position
    PAGENUM_LEFTARROW_X = 19,
    PAGENUM_LEFTARROW_Y = 143,

    // Neutral right arrow position
    PAGENUM_RIGHTARROW_X = 217,
    PAGENUM_RIGHTARROW_Y = 143,

    // initial arrow offset on select
    PAGENUM_SELECT_XOFF = 6,

    // arrow animation speeds
    PAGENUM_ANIMSPEED = 4,
    PAGENUM_SELECT_ANIMSPEED = 31,

    PAGENUM_DISPLAY_X = 180, // 215 
    PAGENUM_DISPLAY_Y = 148,

    // name animation scaling time
    PAGENAME_SCALE_TIME = 6,
};

void CoInfoCtrl_OnInit(struct StatScreenPageNameProc* proc)
{
    proc->xLeftCursor  = PAGENUM_LEFTARROW_X;
    proc->xRightCursor = PAGENUM_RIGHTARROW_X;

    proc->animTimerRight = 0;
    proc->animTimerLeft  = 0;

    proc->animSpeedRight = PAGENUM_ANIMSPEED;
    proc->animSpeedLeft = PAGENUM_ANIMSPEED;
}

void CoInfoCtrl_CheckSlide(struct StatScreenPageNameProc* proc)
{
    if (gStatScreen.pageSlideKey & DPAD_LEFT)
    {
        proc->animSpeedLeft = PAGENUM_SELECT_ANIMSPEED;
        proc->xLeftCursor = PAGENUM_LEFTARROW_X - PAGENUM_SELECT_XOFF;
    }

    if (gStatScreen.pageSlideKey & DPAD_RIGHT)
    {
        proc->animSpeedRight = PAGENUM_SELECT_ANIMSPEED;
        proc->xRightCursor = PAGENUM_RIGHTARROW_X + PAGENUM_SELECT_XOFF;
    }

    gStatScreen.pageSlideKey = 0;
}

void CoInfoCtrl_UpdateArrows(struct StatScreenPageNameProc* proc)
{
    int baseref = TILEREF(0x240, STATSCREEN_OBJPAL_4) + OAM2_LAYER(1);

    proc->animTimerLeft  += proc->animSpeedLeft;
    proc->animTimerRight += proc->animSpeedRight;

    if (proc->animSpeedLeft > PAGENUM_ANIMSPEED)
        proc->animSpeedLeft--;

    if (proc->animSpeedRight > PAGENUM_ANIMSPEED)
        proc->animSpeedRight--;

    if ((GetGameClock() % 4) == 0)
    {
        if (proc->xLeftCursor < PAGENUM_LEFTARROW_X)
            proc->xLeftCursor++;

        if (proc->xRightCursor > PAGENUM_RIGHTARROW_X)
            proc->xRightCursor--;
    }

    PutSprite(0,
        gStatScreen.xDispOff + proc->xLeftCursor,
        gStatScreen.yDispOff + PAGENUM_LEFTARROW_Y,
        gObject_8x16, baseref + 0x5A + (proc->animTimerLeft >> 5) % 6);

    PutSprite(0,
        gStatScreen.xDispOff + proc->xRightCursor,
        gStatScreen.yDispOff + PAGENUM_RIGHTARROW_Y,
        gObject_8x16_HFlipped, baseref + 0x5A + (proc->animTimerRight >> 5) % 6);
}

void CoInfoCtrl_UpdatePageNum(struct StatScreenPageNameProc* proc)
{
    int chr = 0x289;

    // page amt
    PutSprite(2,
        gStatScreen.xDispOff + PAGENUM_DISPLAY_X + 13,
        gStatScreen.yDispOff + PAGENUM_DISPLAY_Y,
        gObject_8x8, TILEREF(chr, STATSCREEN_OBJPAL_4) + OAM2_LAYER(3) + gStatScreen.pageAmt);

    // '/'
    PutSprite(2,
        gStatScreen.xDispOff + PAGENUM_DISPLAY_X + 7,
        gStatScreen.yDispOff + PAGENUM_DISPLAY_Y,
        gObject_8x8, TILEREF(chr, STATSCREEN_OBJPAL_4) + OAM2_LAYER(3));

    // page num
    PutSprite(2,
        gStatScreen.xDispOff + PAGENUM_DISPLAY_X,
        gStatScreen.yDispOff + PAGENUM_DISPLAY_Y,
        gObject_8x8, TILEREF(chr, STATSCREEN_OBJPAL_4) + OAM2_LAYER(3) + gStatScreen.page + 1);
}

CONST_DATA struct ProcCmd gProcScr_CoPageNumCtrl[] = {
    PROC_CALL(CoInfoCtrl_OnInit),

PROC_LABEL(0),
    PROC_SLEEP(0),

    PROC_CALL(CoInfoCtrl_CheckSlide),
    PROC_CALL(CoInfoCtrl_UpdateArrows),
    PROC_CALL(CoInfoCtrl_UpdatePageNum),
    // PROC_CALL(PageNumCtrl_DisplayMuPlatform),
    PROC_CALL(CoScreen_DrawAffinitySprites),

    PROC_GOTO(0),

    PROC_END,
};

static void CoScreen_Setup(ProcPtr proc)
{
    gCoScreen.coId = gPlaySt.commanderId[FACTION_BLUE >> 6];

    gStatScreen.page = CO_SCREEN_PAGE_INFO;
    gStatScreen.pageAmt = CO_SCREEN_PAGE_COUNT;
    gStatScreen.pageSlideKey = 0;
    gStatScreen.xDispOff = 0;
    gStatScreen.yDispOff = 0;
    gStatScreen.inTransition = FALSE;

    u16 bgConfig[12] =
    {
        0x0000, 0x6000, 0,
        0x0000, 0x6800, 0,
        0x8000, 0x7000, 0,
        0x8000, 0x7800, 0,
    };

    SetupBackgrounds(bgConfig);
    RegisterBlankTile(0x400);
    
    // LoadGameCoreGfxLegacyFrame();

    LoadUiFrameGraphics();
    ApplyUnitSpritePalettes();
    ApplySystemObjectsPalettes();
    ReadGameSaveCoreGfx();
    LoadUiFrameGraphicsTo(0x8000, -1);
    
    // LoadIconPalettes(4);
    LoadIconPalette(1, 0x13);
    LoadIconPalette(1, 0x14);

    /* Arrow/page-number OBJ graphics, same VRAM char offset
     * StatScreen_InitDisplay (src/statscreen.c) decompresses them to --
     * OBJPAL_4 itself is already populated by LoadGameCoreGfxLegacyFrame's
     * LoadObjUIGfx() (see CoScreen_Setup's earlier black-screen fix). */
    Decompress(Img_StatscreenObjs, (void*)(VRAM + 0x10000 + 0x240 * 0x20));

    /* Stat-bar graphics palette -- DrawStatWithBar/DrawStatBarGfx
     * (src/statscreen.c) draw into STATSCREEN_BGPAL_6, same as
     * StatScreen_InitDisplay's own UnpackUiBarPalette call. */
    UnpackUiBarPalette(STATSCREEN_BGPAL_6);

    

    CoScreen_DrawHeader();
    CoScreen_DrawPage();
    EnablePaletteSync();

    TileMap_CopyRect(gUiTmScratchA, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);
    TileMap_CopyRect(gUiTmScratchC, gBG2TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);

    BG_EnableSyncByMask(BG0_SYNC_BIT | BG2_SYNC_BIT);

    Proc_Start(gProcScr_CoPageNumCtrl, proc);
}

static void CoScreen_Teardown(ProcPtr proc)
{
    Proc_EndEach(gProcScr_CoPageNumCtrl);

    BG_Fill(gBG0TilemapBuffer, 0);
    BG_Fill(gBG1TilemapBuffer, 0);
    BG_Fill(gBG2TilemapBuffer, 0);
    BG_Fill(gBG3TilemapBuffer, 0);

    BG_EnableSyncByMask(0xF);

    gLCDControlBuffer.dispcnt.bg0_on = 0;
    gLCDControlBuffer.dispcnt.bg1_on = 0;
    gLCDControlBuffer.dispcnt.bg2_on = 0;
    gLCDControlBuffer.dispcnt.bg3_on = 0;
    gLCDControlBuffer.dispcnt.obj_on = 0;

    ResetText();

    CpuFastFill(0, gPaletteBuffer, 0x400);

    EnablePaletteSync();
}

static void CoScreen_KeyListener(ProcPtr proc)
{
    if (gKeyStatusPtr->newKeys & B_BUTTON) {
        Proc_Break(proc);
        return;
    }

    if (gStatScreen.inTransition)
        return;

    if (gKeyStatusPtr->repeatedKeys & DPAD_LEFT) {
        gStatScreen.page = (gStatScreen.page + CO_SCREEN_PAGE_COUNT - 1) % CO_SCREEN_PAGE_COUNT;
        CoStartSlide(DPAD_LEFT, proc);
    } else if (gKeyStatusPtr->repeatedKeys & DPAD_RIGHT) {
        gStatScreen.page = (gStatScreen.page + 1) % CO_SCREEN_PAGE_COUNT;
        CoStartSlide(DPAD_RIGHT, proc);
    } else if (gKeyStatusPtr->repeatedKeys & DPAD_UP) {
        gCoScreen.coId = (gCoScreen.coId + CoScreen_GetCoCount() - 1) % CoScreen_GetCoCount();
        CoStartCommanderFade(proc);
    } else if (gKeyStatusPtr->repeatedKeys & DPAD_DOWN) {
        gCoScreen.coId = (gCoScreen.coId + 1) % CoScreen_GetCoCount();
        CoStartCommanderFade(proc);
    }
}
void CoInfo_BlackenScreen(void)
{
    gLCDControlBuffer.dispcnt.bg0_on = FALSE;
    gLCDControlBuffer.dispcnt.bg1_on = FALSE;
    gLCDControlBuffer.dispcnt.bg2_on = FALSE;
    gLCDControlBuffer.dispcnt.bg3_on = FALSE;
    gLCDControlBuffer.dispcnt.obj_on = FALSE;

    SetBlendConfig(3, 0, 0, 0x10);

    SetBlendTargetA(0, 0, 0, 0, 0);
    SetBlendBackdropA(1);
    SetBlendBackdropB(0);

    // TODO: ResetBackdropColor macro?
    gPaletteBuffer[PAL_BACKDROP_OFFSET] = 0;
    EnablePaletteSync();
}


CONST_DATA struct ProcCmd gProcScr_CoScreen[] = {
    PROC_NAME("COSCREEN"),
    PROC_CALL(CoInfo_BlackenScreen),
    PROC_CALL(BMapDispSuspend),
    PROC_CALL(LockGame),

    PROC_SLEEP(2),
    PROC_CALL(CoScreen_Setup),
    
    // PROC_CALL(StartFastFadeToBlack),
    // PROC_REPEAT(WaitForFade),
    // PROC_CALL_ARG(NewFadeOut, 16),
    // PROC_WHILE(FadeOutExists),
    // PROC_CALL(BMapDispSuspend),
    PROC_SLEEP(0),
    
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
