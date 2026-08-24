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
#include "constants/msg.h"
#include "bg.h"
#include "scene.h"
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


/* 
PutDrawText generally causes graphical glitches when text before does not have a fixed width in vram. 
Using `GetStringTextLen(str) + 8) / 8` to get the width of text is problematic, because 
the text in vram will shift around when being redrawn. This doesn't matter if the screen is faded to black. 

When adding text, follow this schema: 
1. In root\texts\texts.txt, add a new text entry at the end and write the text with a definition. 

2. Refer to this text only through `char *GetStringFromIndex(int index);`, never raw strings. 
    GetStringFromIndexInBuffer can be used to join multiple strings together when necessary (e.g. with Text_DrawNumber).

3. Init 
    void InitSystemTextFont(void); (for everything that isn't a dialogue event) 
    void ResetText(void); // resets to the default font and initializes text vram location
        void ResetTextFont(void); // resets text vram location for the active font. Use this if you
    // aren't using gDefaultFont but need to update all text. (E.g. after InitTextFont)
    // Skip this step 3 if text is being drawn after menu text was just drawn. 

4. Width
    void InitText(struct Text *a, int tileWidth); // Set the width for all text handles that will be used. Also does TextClear
    // void InitTextDb(struct Text * text, int tileWidth);  /  void InitTextInitInfo(const struct TextInitInfo* a);
    // flips it between the two halves of that reserved space so the new string renders into the other VRAM half while the previously-drawn one is still on screen. 
    // That avoids the flicker/tearing you'd get from redrawing glyphs into the same tiles currently being scanned out
    Use InitTextDb instead of InitText when this text redraws every frame (live counters). 
    tileWidth should default to 10 for things that are 1-3 words, or 20 for lines of text. 

5. Clear vram 
    void ClearText(struct Text *text); 
    // If you are redrawing text and skipping steps 3-4, start here. This is unnecessary if steps 1-2 were done. 
            
6. Optional parameters 
    void Text_SetParams(struct Text* th, int x, int colorId); // offset the x position and/or set a colour. 
    // default to 0x and TEXT_COLOR_SYSTEM_WHITE, except for titles as TEXT_COLOR_SYSTEM_GOLD or TEXT_COLOR_SYSTEM_BLUE

7. Draw into vram 
    void Text_DrawString(struct Text * text, const char* str);
    Draw the text to vram. 
    Only use Text_DrawNumber if a variable number is needed in the middle of a text str. 

8. Erase the gBG dest buffer space where the text will be placed. 
    void TileMap_FillRect(u16 *dest, int width, int height, int fillValue);
    Each line of text is always height 2. fillValue is generally 0, except for sprite text with 
    the box, which is 0x4444 (using SpriteText_DrawBackground). 
    
9. Place it on the screen 
    void PutText(struct Text* th, u16* dest);
    
*/

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

#define CO_AFFINITY_ROW_MAX 7

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
    u16 nameMsg;
    int faceId;
    u16 titleMsg; // shown on the info page (e.g. their epithet)
    u16 infoMsg; // single texts.txt entry, [LF]-separated (see PrintStringToTexts, src/scene.c)
    u16 powerNameMsg;
    u16 powerDescMsg; // single texts.txt entry, [LF]-separated
    u16 superPowerNameMsg;
    u16 superPowerDescMsg; // single texts.txt entry, [LF]-separated
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
 * changes. */
static const struct CoClassAffinity sFrancisAffinities[] = {
    { "Soldier",    CLASS_SOLDIER,       64 },
    { "Knight",     CLASS_ARMOR_KNIGHT,  60 },
    { "Brigand",    CLASS_BRIGAND,       56 },
    { "Archer",     CLASS_ARCHER,        52 },
    { "Fighter",    CLASS_FIGHTER,       48 },
    { "Mercenary",  CLASS_MERCENARY,     44 },
    { "Cavalier",   CLASS_CAVALIER,      40 },
    { "Monk",       CLASS_MONK,          36 },
    { "Mage",       CLASS_MAGE,          32 },
    { "Cleric",     CLASS_CLERIC,        28 },
    { "Shaman",     CLASS_SHAMAN,        24 },
    // { "Dancer",     CLASS_DANCER,        8 },
    { "Thief",      CLASS_THIEF,         20 },
    { "Pegasus Kn.",   CLASS_PEGASUS_KNIGHT,      0 },
    { "Wyvern Rider",  CLASS_WYVERN_RIDER,      4 },
};

/* O'Neill leans hard into offense, like Flak; weak with anything magical. */
static const struct CoClassAffinity sOneillAffinities[] = {
    { "Soldier",    CLASS_SOLDIER,       16 },
    { "Knight",     CLASS_ARMOR_KNIGHT,  8 },
    { "Brigand",    CLASS_BRIGAND,       8 },
    { "Archer",     CLASS_ARCHER,        8 },
    { "Fighter",    CLASS_FIGHTER,       8 },
    { "Mercenary",  CLASS_MERCENARY,     8 },
    { "Cavalier",   CLASS_CAVALIER,      8 },
    { "Monk",       CLASS_MONK,          8 },
    { "Mage",       CLASS_MAGE,          8 },
    { "Cleric",     CLASS_CLERIC,        8 },
    { "Shaman",     CLASS_SHAMAN,        8 },
    // { "Dancer",     CLASS_DANCER,        8 },
    { "Thief",      CLASS_THIEF,         8 },
    { "Pegasus Kn.",   CLASS_PEGASUS_KNIGHT,      8 },
    { "Wyvern Rider",  CLASS_WYVERN_RIDER,      8 },
};


static const struct CoDefinition sCoDefinitions[CO_COUNT] = {
    [CO_FRANCIS] = {
        .nameMsg = MSG_CO_FRANCIS_NAME,
        .faceId = 4,
        .titleMsg = MSG_CO_FRANCIS_TITLE,
        .infoMsg = MSG_CO_FRANCIS_INFO,
        .powerNameMsg = MSG_CO_FRANCIS_POWER_NAME,
        .powerDescMsg = MSG_CO_FRANCIS_POWER_DESC,
        .superPowerNameMsg = MSG_CO_FRANCIS_SUPER_NAME,
        .superPowerDescMsg = MSG_CO_FRANCIS_SUPER_DESC,
        .affinities = sFrancisAffinities,
        .affinityCount = ARRAY_COUNT(sFrancisAffinities),
    },
    [CO_ONEILL] = {
        .nameMsg = MSG_CO_ONEILL_NAME,
        .faceId = 0x30,
        .titleMsg = MSG_CO_ONEILL_TITLE,
        .infoMsg = MSG_CO_ONEILL_INFO,
        .powerNameMsg = MSG_CO_ONEILL_POWER_NAME,
        .powerDescMsg = MSG_CO_ONEILL_POWER_DESC,
        .superPowerNameMsg = MSG_CO_ONEILL_SUPER_NAME,
        .superPowerDescMsg = MSG_CO_ONEILL_SUPER_DESC,
        .affinities = sOneillAffinities,
        .affinityCount = ARRAY_COUNT(sOneillAffinities),
    },
};

struct CoScreenSt {
    u8 coId;
    u16 bgScrollTimer; // BG3 frlgUiFrame diagonal scroll, see CoScreen_UpdateBgScroll
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
    return GetStringFromIndex(GetCoDefinition(coId)->nameMsg);
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
 * screen never run at the same time). Every simultaneously-visible string
 * needs its OWN slot/handle: LINE0-3 used to share one CO_TEXT_LINE1
 * handle across up to 3 lines at once, which meant they all pointed at the
 * same VRAM glyph range -- whichever line drew last would visually bleed
 * into the others. See memory: feedback_text_add_workflow. */
enum {
    CO_TEXT_HEADER,
    CO_TEXT_LABEL,
    CO_TEXT_SUBTITLE,
    CO_TEXT_LINE0,
    CO_TEXT_LINE1,
    CO_TEXT_LINE2,
    CO_TEXT_LINE3,
    CO_TEXT_COUNT,
};

/* Fixed tileWidth per the text-adding schema (memory:
 * feedback_text_add_workflow): short labels/names get 10 tiles, full
 * description lines get 20. Never size a Text handle from
 * GetStringTextLen(str) -- that recomputes a *different* width every
 * redraw depending on what string happens to be current, which shifts
 * where neighboring handles' VRAM ranges start and corrupts them. */
#define CO_TEXT_WIDTH_SHORT 10
#define CO_TEXT_WIDTH_LINE 20

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



/* Text-adding schema (memory: feedback_text_add_workflow), steps 4-9 per
 * string: (4) InitText with a fixed tileWidth (also clears the handle);
 * (6) Text_SetParams for x-offset/color; (7) Text_DrawString the string,
 * fetched only via GetStringFromIndex, never a raw literal; (8)
 * TileMap_FillRect to erase the destination tiles the string will land
 * on; (9) PutText to place it. Steps 1-2 (texts.txt entry +
 * GetStringFromIndex) are satisfied by every caller passing a MSG_ id.
 * Step 3 (InitSystemTextFont/ResetText) happens once in CoScreen_Setup,
 * not per string. */
static void CoScreen_PutText(int slot, u16* tm, int tileWidth, int color, int msgId)
{
    struct Text* text = &gStatScreen.text[slot];

    InitText(text, tileWidth);
    Text_SetParams(text, 0, color);
    Text_DrawString(text, GetStringFromIndex(msgId));
    TileMap_FillRect(tm, tileWidth, 2, 0);
    PutText(text, tm);
}

/* Vanilla's own answer to "how do you draw a multi-line string": ONE
 * texts.txt entry holds the whole block with [LF] separating lines (not
 * one entry per line) -- Text_DrawString/Text_DrawStringASCII
 * (src/fontgrp.c) stop at the first [LF] they hit, and PutText only ever
 * places a single row, so a multi-line source string still needs one
 * struct Text handle per line. PrintStringToTexts (src/scene.c, used by
 * the dialogue box) is the vanilla helper that reconciles the two: it
 * walks the single source string, and on each [LF] PutTexts whatever
 * accumulated in the current line's handle before moving to the next
 * handle in the array. tm here is line 0's destination; PrintStringToTexts
 * advances by a tilemap row pair (0x40) per line internally. */
static void CoScreen_PutMultilineText(u16* tm, int color, int msgId)
{
    struct Text* texts[4];
    int i;

    for (i = 0; i < 4; ++i) {
        struct Text* text = &gStatScreen.text[CO_TEXT_LINE0 + i];

        InitText(text, CO_TEXT_WIDTH_LINE);
        Text_SetParams(text, 0, color);
        texts[i] = text;
    }

    TileMap_FillRect(tm, CO_TEXT_WIDTH_LINE, 4 * 2, 0);

    PrintStringToTexts(texts, GetStringFromIndex(msgId), tm, 4);
}

static void CoScreen_DrawHeader(void)
{
    const struct CoDefinition* co = GetCoDefinition(gCoScreen.coId);
    int fid = co->faceId;

    PutFace80x72(NULL, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PORTRAIT_X+1, 1), fid, 0x280, 11);
    DrawUiFrame(
        BG_GetMapBuffer(2),            // back BG
        0x13, 0, 12, 11, TILEREF(0, 0), 2); // style

    if (GetPortraitData(fid)->img)
        ApplyPalette(Pal_FaceDisplayPortrait, 2);
    else
        ApplyPalette(Pal_FaceDisplayGenericCard, 2);

    EnablePaletteSync();
    CoScreen_PutText(CO_TEXT_HEADER, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PORTRAIT_X + 1, 10),
        CO_TEXT_WIDTH_SHORT, TEXT_COLOR_SYSTEM_WHITE, co->nameMsg); // CoScreen_GetCoName
}

/* Everything below draws into the gUiTmScratchA/C page-region scratch
 * buffers (statscreen.c) at coordinates local to that 18x18 region, not
 * the real screen -- CoScreen_DrawPage/CoPageSlide_OnLoop below copy the
 * finished scratch content onto the real BG0/BG2 at (CO_PAGE_X, CO_PAGE_Y),
 * same two-buffer approach DisplayPage0/1/2 + PageSlide_OnLoop use. */

static void CoScreen_DrawPageInfo(const struct CoDefinition* co)
{
    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(0, 0), CO_TEXT_WIDTH_SHORT, TEXT_COLOR_SYSTEM_GOLD, MSG_CO_LABEL_INFO);
    CoScreen_PutText(CO_TEXT_SUBTITLE, gUiTmScratchA + TILEMAP_INDEX(0, 2), CO_TEXT_WIDTH_LINE, TEXT_COLOR_SYSTEM_BLUE, co->titleMsg);
    CoScreen_PutMultilineText(gUiTmScratchA + TILEMAP_INDEX(0, 4), TEXT_COLOR_SYSTEM_WHITE, co->infoMsg);
}

static void CoScreen_DrawPagePower(const struct CoDefinition* co)
{
    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(0, 0), CO_TEXT_WIDTH_SHORT, TEXT_COLOR_SYSTEM_GOLD, MSG_CO_LABEL_POWER);
    CoScreen_PutText(CO_TEXT_SUBTITLE, gUiTmScratchA + TILEMAP_INDEX(0, 2), CO_TEXT_WIDTH_LINE, TEXT_COLOR_SYSTEM_BLUE, co->powerNameMsg);
    CoScreen_PutMultilineText(gUiTmScratchA + TILEMAP_INDEX(0, 4), TEXT_COLOR_SYSTEM_WHITE, co->powerDescMsg);
}

static void CoScreen_DrawPageSuper(const struct CoDefinition* co)
{
    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(0, 0), CO_TEXT_WIDTH_SHORT, TEXT_COLOR_SYSTEM_GOLD, MSG_CO_LABEL_SUPER);
    CoScreen_PutText(CO_TEXT_SUBTITLE, gUiTmScratchA + TILEMAP_INDEX(0, 2), CO_TEXT_WIDTH_LINE, TEXT_COLOR_SYSTEM_BLUE, co->superPowerNameMsg);
    CoScreen_PutMultilineText(gUiTmScratchA + TILEMAP_INDEX(0, 4), TEXT_COLOR_SYSTEM_WHITE, co->superPowerDescMsg);
}
#define BAR_VRAM_WIDTH 5
void DrawCoInfoBar(int num, int x, int y, int base, int total, int max)
{
    // PutNumberOrBlank(gUiTmScratchA + TILEMAP_INDEX(x, y),
        // (base == max) ? TEXT_COLOR_SYSTEM_GREEN : TEXT_COLOR_SYSTEM_BLUE, base);

    // PutNumberBonus(total - base, gUiTmScratchA + TILEMAP_INDEX(x + 1, y));

    // if (total > 30)
        // total = 30;

    /* The whole bar is filled yellow, then DrawStatBarGfxCo (src/statbar.c)
     * overlays green from the left (total above base) or red from the
     * right (total below base) to show how far off base total is. */
    DrawStatBarGfxCo(0x1C0 + num*BAR_VRAM_WIDTH, BAR_VRAM_WIDTH,
        gUiTmScratchB + TILEMAP_INDEX(x - 2, y + 1),
        TILEREF(0, STATSCREEN_BGPAL_6), max, total, base);
        // TILEREF(0, STATSCREEN_BGPAL_6), max * 41 / 30, total * 41 / 30, base * 41 / 30);
}
static void CoScreen_DrawPageAffinity(const struct CoDefinition* co)
{
    int i;
    int y = CO_AFFINITY_ROW_Y0;

    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(0, 0), CO_TEXT_WIDTH_SHORT, TEXT_COLOR_SYSTEM_GOLD, MSG_CO_LABEL_AFFINITY);
     
    // pixels long. base in yellow. if total is higher, those pixels in green. if max, all green. 
    for (i = 0; i < co->affinityCount && i < CO_AFFINITY_ROW_MAX; ++i) {
        DrawCoInfoBar(i, CO_AFFINITY_BAR_TILE_X, y, 32, co->affinities[i].rating, 32);
        y += CO_AFFINITY_ROW_STEP;
    }
    int offset = i; 
    y = CO_AFFINITY_ROW_Y0; 
    for (i = 0; i < co->affinityCount && i < CO_AFFINITY_ROW_MAX; ++i) {
        DrawCoInfoBar(i+offset, CO_AFFINITY_BAR_TILE_X+9, y, 32, co->affinities[i+offset].rating, 32);
        y += CO_AFFINITY_ROW_STEP;
    }
    
}

/* Class SMS icons for the affinity page -- OBJ sprites, so they need
 * redrawing every frame (see gProcScr_CoPageNumCtrl below), not just once
 * like the tile-based bars above. */
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
    int offset = i; 
    y = CO_AFFINITY_ROW_Y0;

    for (i = 0; i < co->affinityCount && i < CO_AFFINITY_ROW_MAX; ++i) {
        PutUnitSpriteForClassId(0,
            (CO_AFFINITY_ICON_TILE_X+10) * 8,
            (CO_PAGE_Y + y) * 8,
            0xC800,
            co->affinities[i+offset].classId);

        y += CO_AFFINITY_ROW_STEP;
    }
    
    
    ForceSyncUnitSpriteSheet();
}

static void CoScreen_DrawPage(void)
{
    const struct CoDefinition* co = GetCoDefinition(gCoScreen.coId);

    ResetText();
    CoScreen_DrawHeader();

    CpuFastFill(0, gUiTmScratchA, sizeof(u16) * 0x280);
    CpuFastFill(0, gUiTmScratchB, sizeof(u16) * 0x240);
    CpuFastFill(0, gUiTmScratchC, sizeof(u16) * 0x240);

    /* Page-content border. Drawn into gUiTmScratchC (scratch-local coords,
     * i.e. offset by -CO_PAGE_X/-CO_PAGE_Y from the on-screen position) so
     * it survives the page-slide's fill+copy cycle and CoScreen_DrawPage's
     * own scratch clear above -- drawing straight into gBG2TilemapBuffer
     * here would get wiped out the next time either of those run. */
    DrawUiFrame(
        gUiTmScratchC,                  // back BG
        0, 1, 19, 17, TILEREF(0, 0), 0); // style

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
        gUiTmScratchB + srcOff,
        gBG1TilemapBuffer + dstOff + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y),
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
    CoScreen_DrawPage();

    TileMap_CopyRect(gUiTmScratchA, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);
    TileMap_CopyRect(gUiTmScratchB, gBG1TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);
    TileMap_CopyRect(gUiTmScratchC, gBG2TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);

    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT | BG2_SYNC_BIT);
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

static void CoScreen_UpdateBgScroll(ProcPtr proc);

CONST_DATA struct ProcCmd gProcScr_CoPageNumCtrl[] = {
    PROC_CALL(CoInfoCtrl_OnInit),

PROC_LABEL(0),
    PROC_SLEEP(0),

    PROC_CALL(CoInfoCtrl_CheckSlide),
    PROC_CALL(CoInfoCtrl_UpdateArrows),
    PROC_CALL(CoInfoCtrl_UpdatePageNum),
    // PROC_CALL(PageNumCtrl_DisplayMuPlatform),
    PROC_CALL(CoScreen_DrawAffinitySprites),
    PROC_CALL(CoScreen_UpdateBgScroll),

    PROC_GOTO(0),

    PROC_END,
};

/* Full 16-color bank for the CO stat bars (src/statbar.c's
 * DrawStatBarCo/DrawStatBarGfxCo). Was a single unreadable, comma-less
 * (and therefore non-compiling) line of raw bytes -- rewritten as one
 * RGB(r, g, b) entry per color (see include/gba/defines.h), decoded
 * little-endian pair by pair from the original bytes, with the original
 * raw u16 value kept as a comment for cross-reference. This bank's index
 * values are the raw 4bpp pixel values src/statbar.c's DrawStatBar*Col
 * helpers write into the bar bitmap: 3/4/14 border/shadow/unfilled
 * (DrawStatBarUnfilledCol/LeftBorder/RightBorder/Shadow), 1/5 yellow fill
 * (DrawStatBarFilledCol), 12/13 green "capped" fill (DrawStatBarCappedCol),
 * 10/11 red "minus" fill (DrawStatBarMinusCol). */
static const u16 NewUiBarPal[] = {
    RGB(19, 26, 25), // 0x6753
    RGB(29, 30, 31), // 0x7FDD
    RGB(23, 25, 27), // 0x6F37
    RGB(16, 17, 19), // 0x4E30
    RGB(10,  9,  8), // 0x212A
    RGB(30, 29, 14), // 0x3BBE
    RGB(23, 19,  6), // 0x1A77
    RGB(17, 13,  6), // 0x19B1
    RGB(31, 15,  4), // 0x11FF
    RGB( 2, 15, 31), // 0x7DE2
    RGB(31, 0, 31), // 0x76F5
    RGB(31, 0, 0), // 0x6238
    RGB( 3, 23,  2), // 0x0AE3
    RGB(15, 31, 18), // 0x4BEF
    RGB(10, 10, 22), // 0x594A
    RGB( 0,  0,  0), // 0x0000
};

void UnpackNewUiBarPalette(int palId)
{
    if (palId < 0)
        palId = STATSCREEN_BGPAL_6;

    ApplyPalette(NewUiBarPal, palId);
}


/* BG3 diagonally-scrolling background (ported from Pokemblem's
 * ChallengeRunMenu frlgUiFrame, see graphics/bg/frlgUiFrame.png and its
 * Makefile rule). frlgUiFrame_map is a flat, uncompressed 32x32 array of
 * bare tile indices (0-7, no palette/flip bits) -- built by hand here
 * rather than via CallARM_FillTileRect, since that decodes the engine's
 * compressed native TSA format (see memory: feedback_bgfill_offset_overflow),
 * which this plain array isn't. Sits behind everything else on screen
 * (lowest BG priority) and always fills the full 32x32-tile screen, so
 * BG_SetPosition's hardware wraparound scrolls it seamlessly. */
#define CO_BG_FRAME_PAL_SLOT 3
#define CO_BG_FRAME_TILE_WIDTH 32
#define CO_BG_FRAME_TILE_HEIGHT 32
#define CO_BG_FRAME_TILE_BYTE_OFFSET 0x2000
#define CO_BG_FRAME_TILE_INDEX_OFFSET (CO_BG_FRAME_TILE_BYTE_OFFSET / 0x20)
static void CoScreen_LoadBgFrame(void)
{
    int x, y;

    gLCDControlBuffer.bg3cnt.priority = 3;
    BG_SetColorBpp(3, 4);

    Decompress(frlgUiFrame_tiles, (void*)(VRAM + GetBackgroundTileDataOffset(3) + 0x2000));
    ApplyPalette(frlgUiFrame_palette, CO_BG_FRAME_PAL_SLOT);

    for (y = 0; y < CO_BG_FRAME_TILE_HEIGHT; ++y) {
        for (x = 0; x < CO_BG_FRAME_TILE_WIDTH; ++x) {
            gBG3TilemapBuffer[TILEMAP_INDEX(x, y)] =
                (frlgUiFrame_map[y * CO_BG_FRAME_TILE_WIDTH + x] + CO_BG_FRAME_TILE_INDEX_OFFSET) | (CO_BG_FRAME_PAL_SLOT << 12);
        }
    }

    gCoScreen.bgScrollTimer = 0;
    BG_SetPosition(3, 0, 0);

    BG_EnableSyncByMask(BG3_SYNC_BIT);
}

/* Called every frame (see gProcScr_CoPageNumCtrl) -- advances the diagonal
 * scroll by half a pixel per frame on both axes (matching Pokemblem's own
 * `0 - (timer >> 1)`), wrapping seamlessly since the BG3 tilemap already
 * fills its full 32x32-tile (256x256px) screen. */
static void CoScreen_UpdateBgScroll(ProcPtr proc)
{
    gCoScreen.bgScrollTimer++;

    BG_SetPosition(3, -(gCoScreen.bgScrollTimer >> 1), -(gCoScreen.bgScrollTimer >> 1));
}

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
    UnpackNewUiBarPalette(STATSCREEN_BGPAL_6);
    // UnpackUiBarPalette(STATSCREEN_BGPAL_6);

    CoScreen_LoadBgFrame();

    CoScreen_DrawPage();
    EnablePaletteSync();

    TileMap_CopyRect(gUiTmScratchA, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);
    TileMap_CopyRect(gUiTmScratchB, gBG1TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);
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
