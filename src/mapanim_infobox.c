#include "global.h"
#include "functions.h"
#include "variables.h"
#include "hardware.h"
#include "uiutils.h"
#include "bmio.h"
#include "soundwrapper.h"
#include "bmunit.h"
#include "bmitem.h"
#include "icon.h"
#include "prepscreen.h"
#include "mapanim.h"
#include "bmlib.h"
#include "bmmind.h"
#include "constants/songs.h"

void UncompMapBattleBoxNumGfx(int tileNum)
{
#if FE8_BATTLE_STATS_NO_ANIMS
    /* "-" instead of "?" for a blank/undisplayable digit. */
    extern u16 Img_BattleStatsNoAnimsNum[];
    Decompress(
        Img_BattleStatsNoAnimsNum,
        (u8*)(VRAM) + GetBackgroundTileDataOffset(0) + 0x20*(tileNum & 0x3FF));
#else
    Decompress(
        Img_MapBattleInfoNum,
        (u8*)(VRAM) + GetBackgroundTileDataOffset(0) + 0x20*(tileNum & 0x3FF));
#endif
}

void MapAnim_DrawNumber(u16* tilemap, int num, int tileref, int len, u16 blankref, int arg5)
{
    char buf[8];
    int i, j;

    for (i = sizeof(buf)-1; i >= 0; --i) {
        buf[i] = '0' + num % 10;
        num = num / 10;

        if (num == 0) {
            for (j = i - 1; j >= 0; --j)
                buf[j] = ' ';

            break;
        }
    }

    PutNumberTilesRightAligned(tilemap, buf + sizeof(buf)-1, tileref, len, arg5);

    for (i = len - 1; i > 0 && buf[7 - i] == ' '; --i)
        tilemap[-i] = blankref;
}

void PrepareMapBattleBoxNumGfx(const u8* src)
{
    UncompMapBattleBoxNumGfx(0x20);
    Decompress(src, (u8*)(VRAM + 0x20 * 43)); // TODO: named constants
    ApplyPalette(Pal_MapBattleInfoNum, 5);
}

void MapAnim_DrawBarSegment(u16* buf1, int* buf2, int arg2, int arg3, int arg4)
{
    int r1;
    if (*buf2 > arg3)
        r1 = arg3;
    else
        r1 = *buf2;

    *buf1 = TILEREF(arg4 + r1, arg2);
    *buf2 += 1 - arg3;

    if (*buf2 < 0)
        *buf2 = 0;
}

void MapAnim_DrawBar(u16* tilemap, int arg1, int arg2, int arg3, u16* buf)
{
    int unk4, count = 0;
    u16* it;

    for (it = buf; it[0]; it += 2)
        count -= 1 - it[0];

    count += 1;

    if (arg1 == arg2)
        unk4 = count;
    else
        unk4 = ((count<<8) / arg1 * arg2) >> 8;

    if (unk4 == 0 && arg2 > 0)
        unk4 = 1;

    for (it = buf; it[0]; ++tilemap, it += 2)
        MapAnim_DrawBarSegment(tilemap, &unk4, gMapanimInfobox_1[arg3], it[0], it[1]);
}

void EndMapAnimInfoWindow(void)
{
    Proc_EndEach(ProcScr_MapBattleInfoBox);
}

void StartMapAnimInfoWindow(int x, int y, struct Proc* parent)
{
    struct MAInfoFrameProc* proc = Proc_Start(ProcScr_MapBattleInfoBox, PROC_TREE_3);

    proc->x = x;
    proc->y = y;

    proc->maMain = parent;
}

void ProcMapInfoBox_OnEnd(void)
{
    SetPrimaryHBlankHandler(NULL);
    ClearBg0Bg1();
}

void ProcMapInfoBox_OnDraw(struct MAInfoFrameProc* proc)
{
    BG_SetPosition(0, 0, 0);
    BG_SetPosition(1, 0, 0);

#if FE8_BATTLE_STATS_NO_ANIMS
    {
        extern u8 Img_BattleStatsNoAnimsInfoBox[];
        Decompress(
            Img_BattleStatsNoAnimsInfoBox,
            (void*)(VRAM) + GetBackgroundTileDataOffset(1) + BM_BGCHR_BANIM_IFBACK * 0x20);
    }
#else
    Decompress(
        Img_MapBattleInfoBox,
        (void*)(VRAM) + GetBackgroundTileDataOffset(1) + BM_BGCHR_BANIM_IFBACK * 0x20); //< TODO: put in macro?
#endif

    PrepareMapBattleBoxNumGfx(Img_MapBattleInfoHpBar);

    switch (gManimSt.actorCount) {
    case 1:
        DisplayBattleInfoBox(proc, 0, -5);
        break;

    case 2:
        DisplayBattleInfoBox(proc, 0, -1);
        DisplayBattleInfoBox(proc, 1, -11);
        break;
    } // switch (gManimSt.actorCount_maybe)

    InitScanline();

    StartManimFrameGradientScanlineEffect(
        gManimSt.actor[0].hp_info_y*8,
        gManimSt.actor[0].hp_info_y*8 + 0x20,
        gPaletteBuffer[BGPAL_OFFSET(1) + 1],
        gPaletteBuffer[BGPAL_OFFSET(2) + 1]);
}

void ProcMapInfoBox_AnimateHp(struct MAInfoFrameProc* proc)
{
    s8 updated = FALSE;
    int i;

    for (i = 0; i < gManimSt.actorCount; ++i) {
        u16 r4 = gManimSt.actor[i].hp_displayed_q4;

        if (r4 > gManimSt.actor[i].hp_cur*16)
            r4 = r4 - 16;

        if (r4 < gManimSt.actor[i].hp_cur*16) {
            r4 = r4 + 4;

            if (r4 % 16 == 0)
                PlaySoundEffect(SONG_75);
        }

        if (r4 != gManimSt.actor[i].hp_displayed_q4) {
            gManimSt.actor[i].hp_displayed_q4 = r4;
            MapInfoBox_DrawHp(proc, i);
            updated = TRUE;
        }
    }

    if (!updated && gManimSt.hp_changing)
        gManimSt.hp_changing = FALSE;
}

void MapInfoBox_DrawHp(struct MAInfoFrameProc* proc, int a)
{
    int dummy = gManimSt.actor[a].hp_displayed_q4/16;
    int r6 = (dummy >= 100);

    MapAnim_DrawNumber(
        gBG0TilemapBuffer + TILEMAP_INDEX(
            gManimSt.actor[a].hp_info_x + 3,
            gManimSt.actor[a].hp_info_y + 3),
        gManimSt.actor[a].hp_displayed_q4/16,
        TILEREF(32, BM_BGPAL_BANIM_UNK5), 3, 0, r6);

    MapAnim_DrawBar(
        gBG0TilemapBuffer + TILEMAP_INDEX(
            gManimSt.actor[a].hp_info_x + 4,
            gManimSt.actor[a].hp_info_y + 3),
        gManimSt.actor[a].hp_max,
        gManimSt.actor[a].hp_displayed_q4/16,
        0, gMapanimInfobox_0);

    BG_EnableSyncByMask(BG0_SYNC_BIT);
}

u16* GetBattleInfoPalByFaction(struct Unit* unit)
{
    switch (UNIT_FACTION(unit)) {
    case FACTION_BLUE:
        return Pal_MapBattleInfoBlue;

    case FACTION_RED:
        return Pal_MapBattleInfoRed;

    case FACTION_GREEN:
        return Pal_MapBattleInfoGreen;

    case FACTION_PURPLE:
        return Pal_MapBattleInfoPurple;
    } // switch (UNIT_FACTION(unit))

    return NULL;
}

#if FE8_BATTLE_STATS_NO_ANIMS
/* Modern-build port of a FEBuilder-style ROM patch (by Tequila) that shows
 * the attack forecast's Hit/Damage/Crit/AS numbers alongside the unit
 * name/HP boxes when battle animations are off, instead of that
 * information only being visible during the (skipped) battle animation
 * itself. Ported using this project's existing PutNumberTilesRightAligned-
 * based number-tile helper (MapAnim_DrawNumber) rather than the original
 * patch's own hand-rolled ASCII-to-tile routine, whose handling of the
 * 0xFF "not applicable" sentinel value looked unreliable on inspection
 * (branches to its tile-writing call without ever initializing the digit
 * buffer it reads from) -- this port leaves an N/A stat blank instead.
 *
 * Also ports the original patch's bottom weapon icon/name and weapon-
 * triangle arrow display using this project's local text/icon helpers. */

enum
{
    BSNA_TILE_HIT = 0x40,
    BSNA_TILE_DMG = 0x42,
    BSNA_TILE_CRIT = 0x45,
    BSNA_TILE_AS = 0x47,
    BSNA_TILE_ARROW = 0x4A,
    BSNA_PAL_ITEM_ICON = 4,
};

static void PutBattleStatsLabel(struct MapAnimActorState* actor, int gx, int gy, int tile, int width)
{
    u16* dst = gBG0TilemapBuffer + TILEMAP_INDEX(actor->hp_info_x + gx, actor->hp_info_y + gy);
    int i;

    for (i = 0; i < width; i++)
        dst[i] = TILEREF(tile + i, 3);
}

static void PutBattleStatsNumber(struct MapAnimActorState* actor, int gx, int gy, int value)
{
    u16* dst;

    if (value == 0xFF) /* not applicable */
        return;

    dst = gBG0TilemapBuffer + TILEMAP_INDEX(actor->hp_info_x + gx, actor->hp_info_y + gy);
    MapAnim_DrawNumber(dst, value, TILEREF(32, BM_BGPAL_BANIM_UNK5), 3, 0, 0);
}

static void PutBattleStatsWeapon(struct MapAnimActorState* actor, struct BattleUnit* bu)
{
    struct Text text;
    char* name;
    int width;
    u16* tm;

    if (bu->weaponBefore == 0)
        return;

    tm = gBG0TilemapBuffer + TILEMAP_INDEX(actor->hp_info_x + 1, actor->hp_info_y + 6);
    DrawIcon(tm, GetItemIconId(bu->weaponBefore), TILEREF(0, BSNA_PAL_ITEM_ICON));
    LoadIconPalette(0, BSNA_PAL_ITEM_ICON);

    name = GetItemName(bu->weaponBefore);
    width = (GetStringTextLen(name) + 7) / 8;
    if (width > 7)
        width = 7;

    InitText(&text, width);
    Text_SetColor(&text, TEXT_COLOR_SYSTEM_WHITE);
    Text_DrawString(&text, name);
    PutText(&text, tm + 3);
}

static void PutBattleStatsTriangleArrow(
    struct MapAnimActorState* actor, struct BattleUnit* bu, struct BattleUnit* otherBu)
{
    extern u8 Img_BattleStatsNoAnimsArrowIcons[];

    u16* tm;
    int tile;

    if (bu->wTriangleDmgBonus == 0)
        return;

    CpuFastCopy(
        Img_BattleStatsNoAnimsArrowIcons,
        (u8*)(VRAM) + GetBackgroundTileDataOffset(0) + BSNA_TILE_ARROW * CHR_SIZE,
        0x100);

    tile = (bu->wTriangleDmgBonus > otherBu->wTriangleDmgBonus)
        ? BSNA_TILE_ARROW + 1
        : BSNA_TILE_ARROW + 3;

    tm = gBG0TilemapBuffer + TILEMAP_INDEX(actor->hp_info_x + 10, actor->hp_info_y + 6);
    tm[0] = tile;
    tm[0x20] = tile + 4;
}

static void ShowBattleStatsNoAnims(int index)
{
    extern u8 Img_BattleStatsNoAnimsLabels[];
    extern u16 Pal_BattleStatsNoAnimsLabels[];

    struct MapAnimActorState* actor;
    struct BattleUnit* bu;
    struct BattleUnit* otherBu;
    int damage;

    if (gManimSt.actorCount != 2)
        return;

    Decompress(Img_BattleStatsNoAnimsLabels, (void*)0x06000800);
    ApplyPalettes(Pal_BattleStatsNoAnimsLabels, 3, 1);

    actor = &gManimSt.actor[index];
    bu = actor->bu;
    otherBu = gManimSt.actor[1 - index].bu;

    PutBattleStatsNumber(actor, 5, 4, bu->battleEffectiveHitRate);
    PutBattleStatsLabel(actor, 1, 4, BSNA_TILE_HIT, 2);

    damage = bu->battleAttack - otherBu->battleDefense;
    if (damage < 0)
        damage = 0;
    PutBattleStatsNumber(actor, 10, 4, damage);
    PutBattleStatsLabel(actor, 6, 4, BSNA_TILE_DMG, 3);

    PutBattleStatsNumber(actor, 5, 5, bu->battleEffectiveCritRate);
    PutBattleStatsLabel(actor, 1, 5, BSNA_TILE_CRIT, 2);

    if (gActionData.unitActionType != UNIT_ACTION_STAFF) /* no AS while using a staff */
        PutBattleStatsNumber(actor, 10, 5, bu->battleSpeed);
    PutBattleStatsLabel(actor, 6, 5, BSNA_TILE_AS, 3);

    PutBattleStatsWeapon(actor, bu);
    PutBattleStatsTriangleArrow(actor, bu, otherBu);

    BG_EnableSyncByMask(BG0_SYNC_BIT);
}
#endif

void DisplayBattleInfoBox(struct MAInfoFrameProc* proc, int index, int arg2)
{
    gManimSt.actor[index].hp_info_x = proc->x + arg2;
    gManimSt.actor[index].hp_info_y = proc->y;

    ApplyPalette(
        GetBattleInfoPalByFaction(gManimSt.actor[index].unit),
        BM_BGPAL_BANIM_IFBACK + index);

    Decompress(
        TsaSet_MapBattleBoxGfx[gManimSt.actorCount][index], gGenericBuffer);

    CallARM_FillTileRect(
        TILEMAP_LOCATED(gBG1TilemapBuffer,
            gManimSt.actor[index].hp_info_x,
            gManimSt.actor[index].hp_info_y),
        (u16*) gGenericBuffer,
        (u16)(BM_BGCHR_BANIM_IFBACK | TILEREF(0, BM_BGPAL_BANIM_IFBACK + index)));

    BG_EnableSyncByMask(BG1_SYNC_BIT);

    PutStringCentered(
        TILEMAP_LOCATED(gBG0TilemapBuffer,
            gManimSt.actor[index].hp_info_x + 2,
            gManimSt.actor[index].hp_info_y + 1),
        0, 9,
        GetStringFromIndex(UNIT_NAME_ID(gManimSt.actor[index].unit)));

    BG_EnableSyncByMask(BG0_SYNC_BIT);

    gManimSt.actor[index].hp_displayed_q4 = gManimSt.actor[index].hp_cur*16;

    MapInfoBox_DrawHp(proc, index);

#if FE8_BATTLE_STATS_NO_ANIMS
    ShowBattleStatsNoAnims(index);
#endif
}

void MapInfoBox_PrepareForShake(struct MAInfoFrameProc* proc)
{
    proc->unk2A = 0;

    MapInfoBoxShake(proc);

    SetWinEnable(1, 0, 0);

    SetWin0Layers(1, 1, 1, 1, 1);
    SetWOutLayers(0, 0, 1, 1, 1);
}

void MapInfoBoxShake(struct MAInfoFrameProc* proc)
{
    // TODO: SetWin0PtA macro?
    gLCDControlBuffer.win0_left   = 0;
    gLCDControlBuffer.win0_top    = (proc->y+2)*8 - proc->unk2A;

    // TODO: SetWin0PtB macro?
    gLCDControlBuffer.win0_right  = 240; // TODO: SCREEN_WIDTH?
    gLCDControlBuffer.win0_bottom = (proc->y+2)*8 + proc->unk2A;

    proc->unk2A += 2;

    if (proc->unk2A > 0x10) {
        SetWinEnable(0, 0, 0);
        Proc_Break(proc);
    }
}

/** 
 * section.data
*/

CONST_DATA u16 gMapanimInfobox_0[] = {
    0x05, 0x2B, 0x08, 0x31,
    0x08, 0x31, 0x08, 0x31,
    0x08, 0x31, 0x08, 0x31,
    0x05, 0x3A, 0x00, 0x00
};

CONST_DATA int gMapanimInfobox_1[] = {
    0x05, 0x06
};

#if FE8_BATTLE_STATS_NO_ANIMS
extern u8 Tsa_BattleStatsNoAnimsBoxRight[];
extern u8 Tsa_BattleStatsNoAnimsBoxLeft[];
#endif

CONST_DATA u8* TsaSet_MapBattleBoxGfx[3][2] = {
    {Tsa_MapBattleBoxGfx1, Tsa_MapBattleBoxGfx1},
    {Tsa_MapBattleBoxGfx1, Tsa_MapBattleBoxGfx1},
#if FE8_BATTLE_STATS_NO_ANIMS
    {Tsa_BattleStatsNoAnimsBoxRight, Tsa_BattleStatsNoAnimsBoxLeft},
#else
    {Tsa_MapBattleBoxGfx3, Tsa_MapBattleBoxGfx2},
#endif
};

CONST_DATA struct ProcCmd ProcScr_MapBattleInfoBox[] = {
    PROC_SET_END_CB(ProcMapInfoBox_OnEnd),
    PROC_SLEEP(0x1),
    PROC_CALL(MapInfoBox_PrepareForShake),
    PROC_CALL(ProcMapInfoBox_OnDraw),
    PROC_REPEAT(MapInfoBoxShake),
    PROC_REPEAT(ProcMapInfoBox_AnimateHp),
    PROC_END
};
