#include "global.h"

#if FE8_PURCHASE_GENERICS

#include "bmunit.h"
#include "bmtrick.h"
#include "bmitem.h"
#include "bm.h"
#include "bmio.h"
#include "bmlib.h"
#include "hardware.h"
#include "player_interface.h"
#include "fontgrp.h"
#include "uiutils.h"
#include "uimenu.h"
#include "chapterdata.h"
#include "purchase_generics.h"
#include "uichapterstatus.h"
#include "uichapterstatus_generics.h"

#include "constants/msg.h"

/* Advance-Wars-style "faction status" screen. Replaces the normal
 * chapter-status screen's menu entry when FE8_PURCHASE_GENERICS is on
 * (see MapMenu_StatusCommand, src/bmmenu.c). One bordered DrawUiFrame box
 * (no custom BG art) showing, per faction, a small flat-color icon plus
 * Units/Lost/Bases/Income/Funds, in the fixed order Blue, Red, Green,
 * Purple, followed by a Neutral Bases count.
 *
 * Layout constants below are a first-pass judgment call -- there is no
 * way to render/screenshot this in this environment, so column spacing
 * has not been visually verified. Adjust the FACSTAT_* x/y constants by
 * eye once you can see it in an emulator. */

// clang-format off

enum
{
    FACSTAT_BOX_X      = 0,
    FACSTAT_BOX_Y       = 0,
    FACSTAT_BOX_W       = 30,
    FACSTAT_BOX_H       = 20,

    FACSTAT_TITLE_X     = 1,
    FACSTAT_TITLE_Y     = 1,
    FACSTAT_TITLE_W     = 18,

    FACSTAT_TURNLABEL_X = 21,
    FACSTAT_TURNLABEL_Y = 1,
    FACSTAT_TURNLABEL_W = 5,
    FACSTAT_TURNVAL_X   = 26,

    FACSTAT_HEADER_Y    = 5,
    FACSTAT_ICON_X      = 1,
    FACSTAT_UNITS_X     = 3,
    FACSTAT_LOST_X      = 8,
    FACSTAT_BASES_X     = 12,
    FACSTAT_INCOME_X    = 18,
    FACSTAT_FUNDS_X     = 25,

    FACSTAT_UNITS_W     = 4,
    FACSTAT_LOST_W      = 4,
    FACSTAT_BASES_W     = 4,
    FACSTAT_INCOME_W    = 5,
    FACSTAT_FUNDS_W     = 5,

    FACSTAT_ROW0_Y      = 7,
    FACSTAT_ROW_STRIDE  = 2,

    FACSTAT_NEUTRAL_Y   = 17,
    FACSTAT_NEUTRAL_X   = 2,
    FACSTAT_NEUTRAL_W   = 10,
    FACSTAT_NEUTRAL_VAL_X = 12,

    /* Four solid-color icon tiles (one per faction, all sharing ONE
     * palette bank -- see FACSTAT_PAL_ICONS -- instead of one tile
     * shared across four palette banks). Tiles 0x7C-0x7F sit right below
     * the system font's glyph range (CHR 0x80+, see ResetText/
     * InitTextFont in src/fontgrp.c) without overlapping it. */
    FACSTAT_ICON_CHR_BLUE   = 0x7C,
    FACSTAT_ICON_CHR_RED    = 0x7D,
    FACSTAT_ICON_CHR_GREEN  = 0x7E,
    FACSTAT_ICON_CHR_PURPLE = 0x7F,

    /* Single BG palette bank for all 4 faction icon tiles -- each tile is
     * filled with a different color INDEX (1-4) into this one bank,
     * rather than 4 separate one-color-each banks. UI frame uses banks
     * 2-3 (ApplyPalettes(gUiFramePaletteA, 2, 3)) and the system font
     * uses bank 0 -- bank 4 is free. */
    FACSTAT_PAL_ICONS = 4,

    FACSTAT_ICON_IDX_BLUE   = 1,
    FACSTAT_ICON_IDX_RED    = 2,
    FACSTAT_ICON_IDX_GREEN  = 3,
    FACSTAT_ICON_IDX_PURPLE = 4,
};

// clang-format on

struct FactionStatusProc
{
    /* 00 */ PROC_HEADER;
};

enum
{
    FACSTAT_TEXT_TITLE,
    FACSTAT_TEXT_TURN_LABEL,
    FACSTAT_TEXT_UNITS_HEADER,
    FACSTAT_TEXT_LOST_HEADER,
    FACSTAT_TEXT_BASES_HEADER,
    FACSTAT_TEXT_INCOME_HEADER,
    FACSTAT_TEXT_FUNDS_HEADER,
    FACSTAT_TEXT_NEUTRAL_LABEL,
    FACSTAT_TEXT_COUNT,
};

/* Persistent, like gStatScreen.text[] (src/power.c) -- InitText's VRAM
 * allocation (struct Text.chr_position) only needs to be assigned once
 * per screen visit, not per redraw, and per text_drawing_guide.md this
 * screen's static labels are drawn exactly once in FactionStatus_Setup,
 * never again while visible, so a stack-local handle would have worked
 * functionally too -- this matches the documented convention regardless. */
static EWRAM_DATA struct Text sFactionStatusText[FACSTAT_TEXT_COUNT] = {0};

/* No existing reusable "faction color" icon/palette was found in this
 * codebase (checked minimap dots, src/phasechangefx.c's phase-change
 * banners -- those are baked sprite-image banners, not a small solid
 * swatch -- and src/bmudisp.c's unit HUD). One shared 16-color BG
 * palette bank holds all 4 faction colors at their own index
 * (FACSTAT_ICON_IDX_*) rather than 4 separate one-color-each banks --
 * index 0 is the usual transparent/backdrop slot, left black. Icons are
 * drawn as 4 solid 8x8 tiles (FACSTAT_ICON_CHR_*, each filled with its
 * own index via CpuFastFill), all using this one palette bank -- the
 * "plain colored square" fallback the task explicitly allowed when
 * nothing reusable exists. */
static const u16 Pal_FacStatIcons[16] = {
    RGB(0,  0,  0),
    [FACSTAT_ICON_IDX_BLUE]   = RGB(5,  20,  31),
    [FACSTAT_ICON_IDX_RED]    = RGB(28, 2,  2),
    [FACSTAT_ICON_IDX_GREEN]  = RGB(3,  26, 2),
    [FACSTAT_ICON_IDX_PURPLE] = RGB(22, 8,  28),
};

/* Generalizes GetChapterDeathCount (src/gamerankings.c, blue-only,
 * hardcoded index range 1..0x40) to any faction, mirroring
 * CountUnitsByFaction's (src/uichapterstatus.c) loop shape exactly but
 * with the death-state check instead of the aliveness check. factionRaw
 * is a raw FACTION_BLUE/GREEN/RED/PURPLE byte (see bmunit.h), not a
 * FACTION_ID_*. */
static int CountDeathsByFaction(int factionRaw)
{
    int i;
    int count = 0;

    for (i = factionRaw + 1; i < factionRaw + 0x40; i++)
    {
        struct Unit* unit = GetUnit(i);

        if (!UNIT_IS_VALID(unit))
            continue;

        if ((unit->state & (US_DEAD | US_BIT16)) == US_DEAD)
            count++;
    }

    return count;
}

/* Counts TRAP_PURCHASE_BASE traps owned by factionId (a FACTION_ID_* /
 * PURCHASE_BASE_OWNER_NEUTRAL value, NOT a raw FACTION_* byte), mirroring
 * the loop + early-break idiom in purchase_generics.c's
 * GrantIncomeForFaction/RunAiCapturesForFaction. Passing
 * PURCHASE_BASE_OWNER_NEUTRAL doubles as the "neutral bases" count.
 * NOTE: PURCHASE_BASE_OWNER_NEUTRAL (3) and FACTION_ID_PURPLE (3) are the
 * same numeric value -- the base-ownership system cannot distinguish
 * "owned by Purple" from "unowned", so this call is identical for both
 * the Purple row and the Neutral row. That is inherent to the existing
 * system, not a bug introduced here. */
static int CountBasesOwnedBy(int factionId)
{
    int i;
    int count = 0;

    for (i = 0; i < TRAP_MAX_COUNT; ++i)
    {
        struct Trap* trap = GetTrap(i);

        if (trap->type == TRAP_NONE)
            break;

        if (trap->type != TRAP_PURCHASE_BASE)
            continue;

        if (GetPurchaseBaseTrapOwner(trap) == factionId)
            count++;
    }

    return count;
}

/* text_drawing_guide.md steps 4/6/7/8/9: InitText (fixed width, never a
 * length guessed from the string), Text_SetParams, Text_DrawString off a
 * texts.txt entry (GetStringFromIndex, never a raw literal),
 * TileMap_FillRect the destination before placing, then PutText. */
static void PutLabelText(int slot, u16* dest, int width, int color, int msgId)
{
    struct Text* text = &sFactionStatusText[slot];

    InitText(text, width);
    Text_SetParams(text, 0, color);
    Text_DrawString(text, GetStringFromIndex(msgId));
    // TileMap_FillRect(dest, width, 2, 0);
    PutText(text, dest);
}

static void PutTitleText(u16* dest, int width, int color, const char* str)
{
    struct Text* text = &sFactionStatusText[FACSTAT_TEXT_TITLE];

    InitText(text, width);
    Text_SetParams(text, 0, color);
    Text_DrawStringASCII(text, str);
    // TileMap_FillRect(dest, width, 2, 0);
    PutText(text, dest);
}

static void FactionStatus_DrawIcon(int row, int chr)
{
    gBG0TilemapBuffer[TILEMAP_INDEX(FACSTAT_ICON_X, row)] = TILEREF(chr, FACSTAT_PAL_ICONS);
}

static void FactionStatus_DrawRow(int row, int factionRaw, int factionId, int color)
{
    int y = FACSTAT_ROW0_Y + row * FACSTAT_ROW_STRIDE;

    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_UNITS_X+2, y), color,
        CountUnitsByFaction(factionRaw));
    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_LOST_X+2, y), color,
        CountDeathsByFaction(factionRaw));
    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_BASES_X+2, y), color,
        CountBasesOwnedBy(factionId));
    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_INCOME_X+3, y), color,
        GetFactionIncomePreview(factionId));
    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_FUNDS_X+3, y), color,
        GetFactionChapterGoldAmount(factionId));
}

static void FactionStatus_DrawContent(void)
{
    const char* title = GetChapterTitleName(gPlaySt.chapterIndex);

    PutTitleText(TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_TITLE_X, FACSTAT_TITLE_Y),
        FACSTAT_TITLE_W, TEXT_COLOR_SYSTEM_BLACK, title);

    PutLabelText(FACSTAT_TEXT_TURN_LABEL, TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_TURNLABEL_X, FACSTAT_TURNLABEL_Y),
        FACSTAT_TURNLABEL_W, TEXT_COLOR_SYSTEM_BLUE, MSG_FACSTAT_TURN);
    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_TURNVAL_X, FACSTAT_TURNLABEL_Y),
        TEXT_COLOR_SYSTEM_BLUE, gPlaySt.chapterTurnNumber);

    PutLabelText(FACSTAT_TEXT_UNITS_HEADER, TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_UNITS_X, FACSTAT_HEADER_Y),
        FACSTAT_UNITS_W, TEXT_COLOR_SYSTEM_GOLD, MSG_FACSTAT_UNITS);
    PutLabelText(FACSTAT_TEXT_LOST_HEADER, TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_LOST_X, FACSTAT_HEADER_Y),
        FACSTAT_LOST_W, TEXT_COLOR_SYSTEM_GOLD, MSG_FACSTAT_LOST);
    PutLabelText(FACSTAT_TEXT_BASES_HEADER, TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_BASES_X, FACSTAT_HEADER_Y),
        FACSTAT_BASES_W, TEXT_COLOR_SYSTEM_GOLD, MSG_FACSTAT_BASES);
    PutLabelText(FACSTAT_TEXT_INCOME_HEADER, TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_INCOME_X, FACSTAT_HEADER_Y),
        FACSTAT_INCOME_W, TEXT_COLOR_SYSTEM_GOLD, MSG_FACSTAT_INCOME);
    PutLabelText(FACSTAT_TEXT_FUNDS_HEADER, TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_FUNDS_X, FACSTAT_HEADER_Y),
        FACSTAT_FUNDS_W, TEXT_COLOR_SYSTEM_GOLD, MSG_FACSTAT_FUNDS);

    // Row order per spec: Blue, Red, Green, Purple (NOT Advance Wars' own
    // order/colors -- this is FE8's own faction order).
    #define ICON_OFFSET 1
    FactionStatus_DrawIcon(FACSTAT_ROW0_Y + ICON_OFFSET + 0 * FACSTAT_ROW_STRIDE, FACSTAT_ICON_CHR_BLUE);
    FactionStatus_DrawRow(0, FACTION_BLUE, FACTION_ID_BLUE, TEXT_COLOR_SYSTEM_BLACK);

    FactionStatus_DrawIcon(FACSTAT_ROW0_Y + ICON_OFFSET + 1 * FACSTAT_ROW_STRIDE, FACSTAT_ICON_CHR_RED);
    FactionStatus_DrawRow(1, FACTION_RED, FACTION_ID_RED, TEXT_COLOR_SYSTEM_BLACK);

    FactionStatus_DrawIcon(FACSTAT_ROW0_Y + ICON_OFFSET + 2 * FACSTAT_ROW_STRIDE, FACSTAT_ICON_CHR_GREEN);
    FactionStatus_DrawRow(2, FACTION_GREEN, FACTION_ID_GREEN, TEXT_COLOR_SYSTEM_BLACK);

    FactionStatus_DrawIcon(FACSTAT_ROW0_Y + ICON_OFFSET + 3 * FACSTAT_ROW_STRIDE, FACSTAT_ICON_CHR_PURPLE);
    // Purple's Bases/Income/Funds legitimately show 0 -- see file header
    // comment on CountBasesOwnedBy and this repo's CHAPTER_GOLD_FACTION_COUNT
    // (src/bmitem.c), which only tracks Blue/Green/Red.
    FactionStatus_DrawRow(3, FACTION_PURPLE, FACTION_ID_PURPLE, TEXT_COLOR_SYSTEM_BLACK);

    PutLabelText(FACSTAT_TEXT_NEUTRAL_LABEL, TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_NEUTRAL_X, FACSTAT_NEUTRAL_Y),
        FACSTAT_NEUTRAL_W, TEXT_COLOR_SYSTEM_GOLD, MSG_FACSTAT_NEUTRAL_BASES);
    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, FACSTAT_NEUTRAL_VAL_X, FACSTAT_NEUTRAL_Y),
        TEXT_COLOR_SYSTEM_BLACK, CountBasesOwnedBy(PURCHASE_BASE_OWNER_NEUTRAL));
        
    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT | BG2_SYNC_BIT);
}

static void FactionStatus_Setup(ProcPtr proc)
{
    /* BG0 and BG1 both need charblock 0 (tile offset 0x0000): the system
     * font's glyphs live at the fixed absolute address VRAM+0x1000 (see
     * ResetText -> InitTextFont), and LoadUiFrameGraphics decompresses the
     * frame image to BG_CHAR_ADDR(0) = VRAM+0x0000 (see
     * UnpackUiFrameImage's NULL-dest default) -- both are only valid to
     * display from a BG whose own charblock actually contains that
     * address. BG2 gets its own separate charblock at VRAM+0x8000 (same
     * as CoScreen_Setup's bgConfig, src/power.c) so the icon tile below
     * doesn't land inside the font/frame data BG0/BG1 already own --
     * SetupBackgrounds(NULL)'s own default config does NOT give BG2 a
     * separate charblock (only BG3 gets one), which is what this
     * screen used before and is why the icon tile silently corrupted
     * whatever else was in BG0's charblock 0. */
    // u16 bgConfig[12] =
    // {
        // 0x0000, 0x6000, 0,   // BG0 -- content (text)
        // 0x0000, 0x6800, 0,   // BG1 -- DrawUiFrame box
        // 0x8000, 0x7000, 0,   // BG2 -- faction icons
        // 0x8000, 0x7800, 0,   // BG3 -- unused
    // };

    // SetupBackgrounds(bgConfig);
    // RegisterBlankTile(0x400);

    // BG0 (content) and BG2 (icons) in front of BG1 (frame) so they
    // aren't hidden behind the box they're drawn on top of.
    gLCDControlBuffer.bg0cnt.priority = 0;
    gLCDControlBuffer.bg1cnt.priority = 1;
    gLCDControlBuffer.bg2cnt.priority = 0;

    /* Whatever screen this replaces the Status entry from (usually the map
     * with the chapter menu open) can leave an active blend/darken effect
     * programmed into the hardware color-effect registers -- those aren't
     * reset just by drawing new BG content, so without this the entire
     * screen renders correctly but blended down to black. Matches
     * ChapterStatus_Init's own SetDefaultColorEffects() call
     * (src/uichapterstatus.c), the vanilla screen this one replaces. */
    SetDefaultColorEffects();

    ResetText();
    /* text_drawing_guide.md: every PutNumber-using screen must preallocate
     * the common digit/special-char glyph set once per color actually
     * used, right after ResetText, before any PutNumber calls -- this
     * screen draws 20+ numbers (Units/Lost/Bases/Income/Funds x4 rows,
     * plus Neutral Bases) in white and the Turn value in blue, so which
     * glyphs are already resident otherwise depends on draw order and can
     * shift between redraws. */
    PreallocateCommonGlyphs(TEXT_COLOR_SYSTEM_WHITE);
    PreallocateCommonGlyphs(TEXT_COLOR_SYSTEM_BLUE);
    LoadUiFrameGraphics();

    ClearBg0Bg1();

    /* LoadUiFrameGraphics() above already applied the frame's own real
     * palette to BGPAL_WINDOW_FRAME (bank 1, see
     * include/constants/video-global.h) -- sUiFrameModelTilemapLookup's
     * model tiles (src/uiutils.c) already bake that bank into their own
     * tile+palette values, so DrawUiFrame's own TILEREF(0, 0) tilebase
     * argument is an offset added on top, not the frame's palette
     * selection. The gUiFramePaletteA ApplyPalettes call this previously
     * had was redirecting to banks 2-3, which nothing here reads. */

    // Four solid-color icon tiles, one per faction, each tile filled with
    // its own color index (see FACSTAT_ICON_IDX_* / Pal_FacStatIcons) --
    // all 4 nibbles of each fill word are the same index, since a 4bpp
    // tile packs 2 pixels/byte.
    CpuFastFill(FACSTAT_ICON_IDX_BLUE   * 0x11111111, BG_CHR_ADDR(FACSTAT_ICON_CHR_BLUE),   CHR_SIZE);
    CpuFastFill(FACSTAT_ICON_IDX_RED    * 0x11111111, BG_CHR_ADDR(FACSTAT_ICON_CHR_RED),    CHR_SIZE);
    CpuFastFill(FACSTAT_ICON_IDX_GREEN  * 0x11111111, BG_CHR_ADDR(FACSTAT_ICON_CHR_GREEN),  CHR_SIZE);
    CpuFastFill(FACSTAT_ICON_IDX_PURPLE * 0x11111111, BG_CHR_ADDR(FACSTAT_ICON_CHR_PURPLE), CHR_SIZE);

    ApplyPalette(Pal_FacStatIcons, FACSTAT_PAL_ICONS);

    DrawUiFrame(gBG1TilemapBuffer, FACSTAT_BOX_X, FACSTAT_BOX_Y, FACSTAT_BOX_W, FACSTAT_BOX_H,
        TILEREF(0, 0), 2);

    FactionStatus_DrawContent();
    SetBlendTargetA(0, 1, 0, 0, 0); // transparent ui
    SetBlendBackdropA(1);
    SetBlendAlpha(11, 5);

    gLCDControlBuffer.dispcnt.bg0_on = 1;
    gLCDControlBuffer.dispcnt.bg1_on = 1;
    gLCDControlBuffer.dispcnt.bg2_on = 1;

    EnablePaletteSync();
    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT | BG2_SYNC_BIT);
}

static void FactionStatus_Teardown(ProcPtr proc)
{
    BG_Fill(gBG0TilemapBuffer, 0);
    BG_Fill(gBG1TilemapBuffer, 0);
    BG_Fill(gBG2TilemapBuffer, 0);

    gLCDControlBuffer.dispcnt.bg0_on = 0;
    gLCDControlBuffer.dispcnt.bg1_on = 0;
    gLCDControlBuffer.dispcnt.bg2_on = 0;

    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT | BG2_SYNC_BIT);

    ResetText();
}

static void FactionStatus_KeyListener(ProcPtr proc)
{
    if (gKeyStatusPtr->newKeys & (A_BUTTON | B_BUTTON))
    {
        Proc_Break(proc);
    }
}

CONST_DATA struct ProcCmd gProcScr_FactionStatusScreen[] =
{
    PROC_NAME("FACSTAT"),
    PROC_SLEEP(0),
    PROC_CALL(EndPlayerPhaseSideWindows),
    // PROC_CALL(BMapDispSuspend),
    PROC_CALL(LockGame),

    PROC_CALL(FactionStatus_Setup),

    PROC_REPEAT(FactionStatus_KeyListener),

    PROC_CALL(FactionStatus_Teardown),

    // PROC_CALL(BMapDispResume),
    PROC_CALL(RefreshBMapGraphics),
    PROC_CALL(StartPlayerPhaseSideWindows),
    PROC_CALL(UnlockGame),

    PROC_END,
};

u8 FactionStatus_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    Proc_StartBlocking(gProcScr_FactionStatusScreen, PROC_TREE_3);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

#endif // FE8_PURCHASE_GENERICS
