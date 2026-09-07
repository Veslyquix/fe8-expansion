#include "global.h"

#if FE8_MODE_SELECT

#include "proc.h"
#include "hardware.h"
#include "bm.h"
#include "m4a.h"
#include "soundwrapper.h"
#include "fontgrp.h"
#include "face.h"
#include "uiutils.h"
#include "ctc.h"
#include "savemenu.h"
#include "ekrbattle.h"
#include "efxbattle.h"
#include "bmlib.h"
#include "mu.h"
#include "bmsave.h"
#include "sysutil.h"
#include "modeselect.h"

#include "constants/faces.h"
#include "constants/songs.h"

/* Ported from the classic FE7 "Mode Select" hack (two source drops: the
 * FE8-address-adapted "FE8ModeSelect", trusted as the source of truth, and
 * a fork by Jester that fixes two bugs -- a misaligned/glitched inner-frame
 * tilemap (see Tsa_084150E0_Full below) and a black-background/redraw bug
 * on returning to the save screen (see ModeSelect_End). The tilemap fix is
 * applied verbatim. The redraw fix is adapted, not copied verbatim: this
 * repo's own src/savemenu.c already runs SaveMenu_ReloadScreenFormDifficulty
 * (a full BG0-3/font/palette rebuild) immediately after this proc ends, for
 * both the plain-difficulty-select and Mode Select paths -- so only
 * Jester's PROC_MARK_SAVEDRAW/PROC_MARK_D unblock (undoing ModeSelect_Init's
 * own block) is needed here; her SaveMenu_Init/InitScreen/
 * LoadExtraMenuGraphics re-invocation would be redundant in this repo's
 * proc flow. Also: this repo's actual decompiled
 * SaveMenu_ResetLcdFormDifficulty (src/savemenu.c) never had the
 * SetupBackgrounds(gBgConfig_SaveMenu) call her fix removes, so that half
 * of the fix needs no corresponding change here at all. Everything else
 * follows FE8ModeSelect.
 *
 * Wired in from src/savemenu.c's PL_SAVEMENU_DIFFICULTY_SEL step, in place
 * of vanilla's NewNewGameDifficultySelect.
 *
 * RAM: the spinning carousel needs 3 concurrent "EkrUnitMainMini" mini-
 * animation slots (struct AnimBuffer, include/ekrbattle.h). Rather than
 * allocate new large scratch buffers, this reuses the same battle-
 * animation RAM every other mini-carousel screen in this repo already
 * reuses (src/classchg-sel.c, src/purchase_generics.c): the actor/target
 * battle-animation image-sheet/OAM/palette/frame-data buffers for slots 0
 * and 1, and opinfo.c's own class-display carousel buffers for slot 2 --
 * none of these are ever live at the same time as the save-menu's New Game
 * flow, so sharing them is safe. See sModeSelectImgSheetBufs and its
 * siblings below.
 *
 * This file's own small proc-state (carousel slot state, text, blend
 * counters) is EWRAM_OVERLAY(gameending) rather than plain EWRAM_DATA --
 * NOT the "gamestart" tag opinfo.c's own buffers use, since that overlay's
 * free (non-fixed-address) region is already almost entirely consumed by
 * gOpInfoData/gOpInfoImgSheetBuf themselves (linker/expansion.ld pins
 * several vanilla globals at fixed offsets starting at 0x2038 into that
 * overlay, leaving barely any headroom). ending_details.c's end-of-game
 * details screen (EWRAM_OVERLAY(gameending)) has no such fixed-address
 * constraints and is just as provably non-concurrent with the save-menu's
 * New Game flow -- you can't be viewing the ending and starting a new game
 * at the same time -- so it's a safe, unconstrained home for this data.
 */

#define ModeSelectBg0Tm gBG0TilemapBuffer
#define ModeSelectClawTm gBG1TilemapBuffer
#define ModeSelectBg3Tm gBG3TilemapBuffer

struct ModeSelectTextState
{
    struct Font font;
    struct Text text[7];
};

EWRAM_OVERLAY(gameending) static struct ModeSelectTextState sModeSelectText = {0};

/* gUnk_0201E8D4 / gUnk_0201E97C in the FE7 source: fixed-address globals
 * sized for 3 concurrent carousel slots. No FE8 equivalent exists (this
 * mini-carousel machinery is otherwise only ever used one slot at a time
 * in this repo -- see opinfo.h's single gOpInfoData/gUnk_4), so these are
 * this file's own small proc-state arrays (not "graphics buffers" in the
 * RAM-reuse sense above -- each entry is under 0x30 bytes). */
EWRAM_OVERLAY(gameending) static struct AnimBuffer sModeSelectAnimBuf[3] = {0};
EWRAM_OVERLAY(gameending) static struct AnimMagicFxBuffer sModeSelectMagicFx[3] = {0};

/* gUnk_0201E9F4 in the FE7 source: per-slot cache of each carousel
 * character's un-dimmed palette (15 colours, skipping the transparent
 * index 0), used by ModeSelectPalette_ApplyBlend to re-derive a dimmed
 * copy every frame without repeatedly re-reading VRAM. */
EWRAM_OVERLAY(gameending) static u16 sModeSelectPaletteCache[3 * 15] = {0};

// gUnk_ModeSelect_02000000 / _02000001 in the FE7 source.
EWRAM_OVERLAY(gameending) static u8 sModeSelectBlendThreshold = 0;
EWRAM_OVERLAY(gameending) static u8 sModeSelectBlendAmount = 0;

extern u8 gOpInfoImgSheetBuf[0x2000];
extern u8 gUnk_0[];
extern u8 gUnk_1[];
extern u8 gUnk_2[];

/* Slot 0/1 reuse the real battle-animation actor/target scratch (only safe
 * because Mode Select never runs during a battle); slot 2 reuses the
 * class-display carousel's own single-slot scratch (only safe because
 * Mode Select never runs during that screen either). */
static void* const sModeSelectImgSheetBufs[3] = {
    gBanimLeftImgSheetBuf, gBanimRightImgSheetBuf, gOpInfoImgSheetBuf,
};
static void* const sModeSelectPaletteBufs[3] = {
    gBanimPaletteLeft, gBanimPaletteRight, gUnk_1,
};
static void* const sModeSelectOamBufs[3] = {
    gBanimOaml, gBanimOamr2, gUnk_0,
};
static void* const sModeSelectFrameDataBufs[3] = {
    gBanimScrLeft, gBanimScrRight, gUnk_2,
};

struct ModeSelectProc
{
    /* 00 */ PROC_HEADER;
    /* 2C */ s32 unk_2c;
    /* 30 */ u16 unk_30;
    /* 32 */ u16 unk_32;
    /* 34 */ s32 unk_34;
    /* 38 */ void* unk_38; // ProcPtr; ProcScr_ModeSelectSpriteDraw instance
    /* 3C */ struct FaceProc* unk_3c;
    /* 40 */ u8 unk_40; // bitmask of unlocked difficulties (see fe7u_func_0809E9FC below)
    /* 41 */ u8 unk_41; // currently-highlighted carousel slot (0-2)
    /* 42 */ u8 unk_42; // bit0: started via the save-menu hook (always set -- see StartModeSelect)
    /* 43 */ u8 unk_43[3]; // per-slot chosen difficulty (0 normal, 1 hard)
    /* 46 */ STRUCT_PAD(0x46, 0x49);
    /* 49 */ u8 unk_49[3]; // per-slot lord index (0 Eirika, 1 Ephraim, 2 Lyon)
    /* 4C */ u8 unk_4c; // number of selectable slots (2 or 3)
    /* 50 */ s32 unk_50;
};

struct ModeSelectSpriteDrawProc
{
    /* 00 */ PROC_HEADER;
    /* 2C */ s32 unk_2c;
    /* 30 */ s32 unk_30;
    /* 34 */ s32 unk_34;

    /* 38 */ s32 unk_38;
    /* 3C */ u8 unk_3c;
    /* 3E */ u16 unk_3e;
    /* 40 */ s32 unk_40;
    /* 44 */ s32 unk_44;
    /* 48 */ s32 unk_48;
    /* 4C */ u8 unk_4c;
    /* 4D */ u8 unk_4d;
    /* 4E */ u8 unk_4e;
};

/* fe7u_func_0809E9FC in the FE7 source: real behavior (unlock hard modes
 * once enough saves are completed, via LoadMetaSave/
 * MetaSave_CountCompletedPlaythroughs) is FE7-specific meta-save plumbing
 * this repo has no equivalent of, and is already entirely commented out in
 * the trusted FE8ModeSelect.c source, hardcoded to unlock everything.
 * Keeping that exactly as committed there, not as a regression. */
// src/code_80AC6AC.c -- not yet declared in any header (see its own file's
// still-address-named filename), so forward-declared here like this repo's
// own convention for other not-yet-header-exposed functions.
int InterpolateCubicSpline(int a, int b, int c, int d, int e);

static int ModeSelect_GetUnlockedDifficultyMask(void)
{
    return 0x1f;
}

// clang-format off

static const int sModeSelectLordText[3][3] = {
    { 0x212, 0x78B, 0x4FE }, // Eirika / "The Valiant" / "Str"
    { 0x220, 0x78B, 0x4FE }, // Ephraim / "The Valiant" / "Str"
    { 0x234, 0x78B, 0x4FF }, // Lyon / "The Valiant" / "Mag"
};

// clang-format on

static void ModeSelectAnim_Pause(struct AnimBuffer* pAnimBuf)
{
    pAnimBuf->anim1->state3 |= 8;
    pAnimBuf->anim2->state3 |= 8;
}

static const int sModeSelectBanimIds[] = {
    2, 0, 0x9c,
};

// FE7U: 0x080A7480
static void InitModeSelectAnims(int count, u8* lordIndices)
{
    int i;

    for (i = 0; i < count; i++)
    {
        sModeSelectAnimBuf[i].xPos = 320;
        sModeSelectAnimBuf[i].yPos = 88;
        sModeSelectAnimBuf[i].animId = sModeSelectBanimIds[lordIndices[i]];
        sModeSelectAnimBuf[i].roundType = 6;
        sModeSelectAnimBuf[i].genericPalId = 0;
        sModeSelectAnimBuf[i].state2 = 1;
        sModeSelectAnimBuf[i].oam2Tile = (i * 0x2000 + 0x2000) >> 5;
        sModeSelectAnimBuf[i].oam2Pal = i + 0xd;

        sModeSelectAnimBuf[i].pImgSheetBuf = sModeSelectImgSheetBufs[i];
        sModeSelectAnimBuf[i].unk_24 = sModeSelectOamBufs[i];
        sModeSelectAnimBuf[i].unk_20 = sModeSelectPaletteBufs[i];
        sModeSelectAnimBuf[i].unk_28 = sModeSelectFrameDataBufs[i];

        sModeSelectAnimBuf[i].charPalId = 0xffff;

        sModeSelectAnimBuf[i].unk_30 = &sModeSelectMagicFx[i];

        sModeSelectMagicFx[i].magicFuncIdx = 0;
        sModeSelectMagicFx[i].xOffsetBg = 0;
        sModeSelectMagicFx[i].yOffsetBg = 0;
        sModeSelectMagicFx[i].xOffsetObj = 0;
        sModeSelectMagicFx[i].yOffsetObj = 0;
        sModeSelectMagicFx[i].objChr = 0;
        sModeSelectMagicFx[i].objPalId = 0;
        sModeSelectMagicFx[i].bgChr = 0;
        sModeSelectMagicFx[i].bgPalId = 0;
        sModeSelectMagicFx[i].bg = 0;

        sModeSelectMagicFx[i].bgTmBuf = NULL;
        sModeSelectMagicFx[i].bgImgBuf = NULL;
        sModeSelectMagicFx[i].bgTsaBuf = NULL;
        sModeSelectMagicFx[i].objImgBuf = NULL;
        sModeSelectMagicFx[i].resetCallback = NULL;

        NewEkrUnitMainMini(&sModeSelectAnimBuf[i]);
    }
}

// FE7U: 0x080A75CC
static void EndModeSelectAnims(s32 count)
{
    int i;

    for (i = 0; i < count; i++)
        EndEkrUnitMainMini(&sModeSelectAnimBuf[i]);
}

const char StrModeSelect_MainCharacter[] = "Main character:";
const char StrModeSelect_Weapon[] = "Weapon:";

// FE7U: 0x080A75F0
static void PutModeSelectLabelText(void)
{
    ClearText(&sModeSelectText.text[5]);
    ClearText(&sModeSelectText.text[6]);

    PutDrawText(&sModeSelectText.text[5], ModeSelectClawTm + TILEMAP_INDEX(14, 6), TEXT_COLOR_SYSTEM_WHITE, 0, 0, StrModeSelect_MainCharacter);
    PutDrawText(&sModeSelectText.text[6], ModeSelectClawTm + TILEMAP_INDEX(14, 10), TEXT_COLOR_SYSTEM_WHITE, 0, 0, StrModeSelect_Weapon);

    BG_EnableSyncByMask(BG1_SYNC_BIT);
}

const char StrModeSelect_Swd[] = "Swd";
const char StrModeSelect_Lnc[] = "Lnc";
const char StrModeSelect_Mag[] = "Mag";

static const char* const sModeSelectWeaponText[] = {
    StrModeSelect_Swd,
    StrModeSelect_Lnc,
    StrModeSelect_Mag,
};

// FE7U: 0x080A7668
static void PutModeSelectCharacterText(s32 index)
{
    ClearText(&sModeSelectText.text[2]);
    ClearText(&sModeSelectText.text[3]);
    ClearText(&sModeSelectText.text[4]);

    PutDrawText(&sModeSelectText.text[2], ModeSelectClawTm + TILEMAP_INDEX(14, 8), TEXT_COLOR_SYSTEM_BLUE, 0, 0, GetStringFromIndex(sModeSelectLordText[index][0]));
    PutDrawText(&sModeSelectText.text[4], ModeSelectClawTm + TILEMAP_INDEX(19, 10), TEXT_COLOR_SYSTEM_BLUE, 0, 0, sModeSelectWeaponText[index]);

    BG_EnableSyncByMask(BG1_SYNC_BIT);
}

// FE7U: 0x080A76F8
static void PutModeSelectDifficultyText(struct ModeSelectProc* proc)
{
    int chosen = proc->unk_43[proc->unk_41];

    ClearText(&sModeSelectText.text[0]);
    ClearText(&sModeSelectText.text[1]);

    PutDrawText(&sModeSelectText.text[0], ModeSelectClawTm + TILEMAP_INDEX(15, 12), chosen == 0 ? TEXT_COLOR_SYSTEM_GOLD : TEXT_COLOR_SYSTEM_GRAY, 0, 0, GetStringFromIndex(0x053E));

    BG_EnableSyncByMask(BG1_SYNC_BIT);

    switch (proc->unk_49[proc->unk_41])
    {
        case 0:
            if (!(proc->unk_40 & 1))
                return;
            break;

        case 1:
            if (!(proc->unk_40 & 4))
                return;
            break;

        case 2:
            if (!(proc->unk_40 & 0x10))
                return;
            break;
    }

    PutDrawText(&sModeSelectText.text[1], ModeSelectClawTm + TILEMAP_INDEX(15, 14), chosen == 1 ? TEXT_COLOR_SYSTEM_GOLD : TEXT_COLOR_SYSTEM_GRAY, 0, 0, GetStringFromIndex(0x053F));
}

static const int sModeSelectFaceIds[3] = {
    FID_EIRIKA,
    FID_EPHRAIM,
    0x46, // FID_LYON
};

// FE7U: 0x080A77C0
static struct FaceProc* StartModeSelectFace(int index)
{
    struct FaceProc* pFaceProc = StartFace2(0, sModeSelectFaceIds[index], 204, 72, (FACE_DISP_KIND(FACE_96x80) | FACE_DISP_HLAYER(FACE_HLAYER_0)));
    StartFaceFadeIn(pFaceProc);
    return pFaceProc;
}

extern u8 Img_08415BE8[]; // lord0 chapter-range icon, top-left
extern u8 Img_08415CB0[]; // lord0 chapter-range icon, bottom-left
extern u8 Img_08415DC4[]; // lord0 chapter-range icon, top-right
extern u8 Img_08415E04[]; // lord0 chapter-range icon, bottom-right

extern u8 Img_08415E54[]; // lord1 chapter-range icon, top-left
extern u8 Img_08415F14[]; // lord1 chapter-range icon, bottom-left
extern u8 Img_08415FF0[]; // lord1 chapter-range icon, top-right
extern u8 Img_0841601C[]; // lord1 chapter-range icon, bottom-right

extern u8 Img_08416058[]; // lord2 chapter-range icon, top-left
extern u8 Img_08416118[]; // lord2 chapter-range icon, bottom-left
extern u8 Img_084161F4[]; // lord2 chapter-range icon, top-right
extern u8 Img_08416220[]; // lord2 chapter-range icon, bottom-right

// FE7U: 0x080A77F8
static void LoadModeSelectChapterGfx(s32 lordIndex)
{
    static void* const sChapterGfx[3][4] = {
        { Img_08415BE8, Img_08415CB0, Img_08415DC4, Img_08415E04 },
        { Img_08415E54, Img_08415F14, Img_08415FF0, Img_0841601C },
        { Img_08416058, Img_08416118, Img_084161F4, Img_08416220 },
    };

    Decompress(sChapterGfx[lordIndex][0], (void*)0x60102C0);
    Decompress(sChapterGfx[lordIndex][1], (void*)0x60106C0);
    Decompress(sChapterGfx[lordIndex][2], (void*)0x6010AC0);
    Decompress(sChapterGfx[lordIndex][3], (void*)0x6010EC0);
}

// FE7U: 0x080A7860 -- caches this slot's undimmed palette for
// ModeSelectPalette_ApplyBlend to fade from every frame.
static void ModeSelectPalette_CacheUndimmed(s32 palId)
{
    int i;
    u16* src = gPaletteBuffer + (palId + 0xd) * 0x10 + 0x101;

    for (i = 0; i < 0xf; i++)
        sModeSelectPaletteCache[i + palId * 0xf] = *src++;
}

// FE7U: 0x080A7890
static void ModeSelectPalette_ApplyBlend(s32 palId, s32 amount)
{
    s32 i;
    u16* dst = gPaletteBuffer + (palId + 0xd) * 0x10 + 0x101;

    if (amount > 0x40)
        amount = 0x40;

    amount = amount + (sModeSelectBlendAmount - 10) * 2;

    for (i = 0; i < 0xf; i++)
    {
        s32 accum = 0;
        s32 r, g, b;
        u16 base = sModeSelectPaletteCache[i + palId * 0xf];

        r = (amount * (base & RED_MASK)) >> 6;
        accum += (r < 0) ? 0 : (r <= RED_MASK ? (r & RED_MASK) : RED_MASK);

        g = (amount * (base & GREEN_MASK)) >> 6;
        accum += (g < 0) ? 0 : (g <= GREEN_MASK ? (g & GREEN_MASK) : GREEN_MASK);

        b = (amount * (base & BLUE_MASK)) >> 6;
        *dst = accum + ((b < 0) ? 0 : (b <= BLUE_MASK ? (b & BLUE_MASK) : BLUE_MASK));

        dst++;
    }

    EnablePaletteSync();
}

// FE7U: 0x080A793C
static void ModeSelectPalette_ApplyGlow(s32 palId, s32 signedByte)
{
    s32 b = signedByte & 0xff;
    s32 amount = (((b >= 0x81) ? b - 0x80 : 0x80 - b) * 0x30 >> 7);
    ModeSelectPalette_ApplyBlend(palId, amount + 0x10);
}

// FE7U: 0x080A796C
static void ModeSelectSpriteDraw_Init(struct ModeSelectSpriteDrawProc* proc)
{
    proc->unk_30 = 0;
    proc->unk_3e = 0;
    proc->unk_3c = 0;
    proc->unk_34 = DISPLAY_WIDTH / 2;
    proc->unk_38 = DISPLAY_HEIGHT;
    proc->unk_40 = 0;
    proc->unk_44 = 0;
    proc->unk_48 = 0;
    proc->unk_4c = 0;
    proc->unk_2c = 0;
    proc->unk_4e = 0;
}

// clang-format off

// FE7U: 0x08CE483C
static const u16 Sprite_ModeSelect_Mode[] = {
    4,
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16, 0,
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16 + OAM1_X(32), OAM2_CHR(0x4),
    OAM0_SHAPE_32x8 + OAM0_Y(16), OAM1_SIZE_32x8, OAM2_CHR(0x40),
    OAM0_SHAPE_32x8 + OAM0_Y(16), OAM1_SIZE_32x8 + OAM1_X(32), OAM2_CHR(0x44),
};

// FE7U: 0x08CE4856
static const u16 Sprite_ModeSelect_Select[] = {
    6,
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16, OAM2_CHR(0x8),
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16 + OAM1_X(32), OAM2_CHR(0xC),
    OAM0_SHAPE_8x16, OAM1_SIZE_8x16 + OAM1_X(64), OAM2_CHR(0x10),
    OAM0_SHAPE_32x8 + OAM0_Y(16), OAM1_SIZE_32x8, OAM2_CHR(0x60),
    OAM0_SHAPE_32x8 + OAM0_Y(16), OAM1_SIZE_32x8 + OAM1_X(32), OAM2_CHR(0x64),
    OAM0_SHAPE_8x8 + OAM0_Y(16), OAM1_SIZE_8x8 + OAM1_X(64), OAM2_CHR(0x68),
};

// FE7U: 0x08CE487C
static const u16 Sprite_ModeSelect_PressStart[] = {
    5,
    OAM0_SHAPE_32x8, OAM1_SIZE_32x8, OAM2_CHR(0x11),
    OAM0_SHAPE_32x8 + OAM0_Y(8), OAM1_SIZE_32x8, OAM2_CHR(0x49),
    OAM0_SHAPE_32x8, OAM1_SIZE_32x8 + OAM1_X(32), OAM2_CHR(0x31),
    OAM0_SHAPE_32x8 + OAM0_Y(8), OAM1_SIZE_32x8 + OAM1_X(32), OAM2_CHR(0x4D),
    OAM0_SHAPE_8x16, OAM1_SIZE_8x16 + OAM1_X(64), OAM2_CHR(0x55),
};

// FE7U: 0x08CE489C
static const u16 Sprite_ModeSelect_Change[] = {
    1,
    OAM0_SHAPE_32x8, OAM1_SIZE_32x8, OAM2_CHR(0x51),
};

// FE7U: 0x08CE48A4
static const u16 Sprite_ModeSelect_ChapterRange[] = {
    4,
    OAM0_SHAPE_32x16 + OAM0_AFFINE_ENABLE, OAM1_SIZE_32x16, OAM2_CHR(0x16),
    OAM0_SHAPE_32x16 + OAM0_AFFINE_ENABLE, OAM1_SIZE_32x16 + OAM1_X(32), OAM2_CHR(0x1A),
    OAM0_SHAPE_16x16 + OAM0_AFFINE_ENABLE, OAM1_SIZE_16x16 + OAM1_X(64), OAM2_CHR(0x1E),
    OAM0_SHAPE_32x16 + OAM0_AFFINE_ENABLE, OAM1_SIZE_32x16 + OAM1_X(80), OAM2_CHR(0x56),
};

// clang-format on

// FE7U: 0x080A79A4
static void ModeSelectSpriteDraw_Loop(struct ModeSelectSpriteDrawProc* proc)
{
    s32 i;

    if (proc->unk_3c != 0)
    {
        for (i = 0; i < proc->unk_40; i++)
        {
            s32 angle = (proc->unk_3e >> 4) + i * proc->unk_44 + 40;
            s32 x = (proc->unk_34 << 12) + SIN(angle) * 70;
            s32 y = (((proc->unk_38 << 12) + COS(angle) * 28) >> 12) - 16;

            SetMainMiniAnimPos(&sModeSelectAnimBuf[i], x >> 12, y);
            ModeSelectPalette_ApplyGlow(i, (proc->unk_3e >> 4) + i * proc->unk_44);
        }
    }

    BgAffinRotScaling(BG_2, proc->unk_3e, 0, 0, 0x160, 0x160);
    BgAffinScaling(BG_2, 0x280, 0x100);
    BgAffinAnchoring(BG_2, proc->unk_34, proc->unk_38, 76, 76);

    sModeSelectBlendAmount = InterpolateCubicSpline(8, 8, 16, 16, proc->unk_48);

    if (proc->unk_4c == 0)
    {
        proc->unk_48 += 8;
        if (proc->unk_48 >= 0x400)
            proc->unk_4c = 1;
    }
    else
    {
        proc->unk_48 -= 8;
        if (proc->unk_48 <= 0)
            proc->unk_4c = 0;
    }

    proc->unk_3e += proc->unk_4d;

    if (proc->unk_2c != 0)
        proc->unk_2c--;
}

static const struct ProcCmd sProc_ModeSelectSpriteDraw[] = {
    PROC_NAME("ModeSelectSpriteDraw"),
    PROC_CALL(ModeSelectSpriteDraw_Init),
    PROC_REPEAT(ModeSelectSpriteDraw_Loop),
    PROC_END,
};
const struct ProcCmd* const ProcScr_ModeSelectSpriteDraw = sProc_ModeSelectSpriteDraw;

static void ModeSelectSpriteDraw_SetActive(bool active)
{
    struct ModeSelectSpriteDrawProc* proc = Proc_Find(ProcScr_ModeSelectSpriteDraw);
    if (proc != NULL)
        proc->unk_2c = active;
}

static void ModeSelectSpriteDraw_SetGlowing(bool glowing)
{
    struct ModeSelectSpriteDrawProc* proc = Proc_Find(ProcScr_ModeSelectSpriteDraw);
    if (proc != NULL)
        proc->unk_3c = glowing;
}

static void ModeSelectSpriteDraw_SetSlotCount(s32 count)
{
    struct ModeSelectSpriteDrawProc* proc = Proc_Find(ProcScr_ModeSelectSpriteDraw);
    if (proc != NULL)
    {
        proc->unk_40 = count;
        proc->unk_44 = 0x100 / count;
    }
}

static void ModeSelectSpriteDraw_SetCenter(s32 x, s32 y)
{
    struct ModeSelectSpriteDrawProc* proc = Proc_Find(ProcScr_ModeSelectSpriteDraw);
    if (proc != NULL)
    {
        proc->unk_34 = x;
        proc->unk_38 = y;
    }
    sModeSelectBlendThreshold = y - 60;
}

static void ModeSelectSpriteDraw_SetAngle(u16 angle)
{
    struct ModeSelectSpriteDrawProc* proc = Proc_Find(ProcScr_ModeSelectSpriteDraw);
    if (proc != NULL)
        proc->unk_3e = angle;
}

static void ModeSelectSpriteDraw_SetSpin(u8 direction, u8 speed)
{
    struct ModeSelectSpriteDrawProc* proc = Proc_Find(ProcScr_ModeSelectSpriteDraw);
    if (proc != NULL)
    {
        proc->unk_4d = direction;
        proc->unk_4e = speed;
    }
}

static s32 ModeSelectSpriteDraw_GetSlotAngleStep(void)
{
    struct ModeSelectSpriteDrawProc* proc = Proc_Find(ProcScr_ModeSelectSpriteDraw);
    return proc->unk_44;
}

// Blend effect on the outer spell-circle background (HBlank handler).
static void ModeSelectBg_UpdateSpellCircleBlend(void)
{
    u16 vcount = REG_VCOUNT + 1;

    if (vcount > DISPLAY_HEIGHT)
        vcount = 0;

    if (vcount & 1)
        return;

    if (vcount < sModeSelectBlendThreshold)
    {
        REG_BLDCNT = 0xc1;
        REG_BLDY = (sModeSelectBlendThreshold != 0)
            ? (sModeSelectBlendThreshold - vcount) * 0x10 / sModeSelectBlendThreshold
            : 0;
    }
    else
    {
        REG_BLDCNT = 0x144;
        REG_BLDALPHA = sModeSelectBlendAmount | 0x1000;
    }
}

static const u16 sModeSelectBgConfig[] = {
    0x0000, 0x6000, 0x0000,
    0xC000, 0x6800, 0x0000,
    0x8000, 0x7800, 0x0000,
    0x8000, 0x7800, 0x0000,
};

extern u16 Pal_084138F0[];
extern u16 Pal_0840F9A0[];
extern u8 Img_08418E44[];
extern u8 Img_0840FEB4[];
extern u8 Tsa_0840FA00[];
extern u8 Tsa_08411F34[];

// FE7U: 0x080A4E58 -- sets up the outer spinning spell-circle background,
// always run when entering via StartModeSelect (unk_42 & 1 is always set).
static void ModeSelect_InitBgs(void)
{
    SetupBackgrounds((u16*)sModeSelectBgConfig);

    gLCDControlBuffer.dispcnt.mode = 1;

    gLCDControlBuffer.bg2cnt.screenSize = 1;
    gLCDControlBuffer.bg2cnt.areaOverflowMode = 0;

    gLCDControlBuffer.bg0cnt.priority = 3;
    gLCDControlBuffer.bg1cnt.priority = 0;
    gLCDControlBuffer.bg2cnt.priority = 2;
    gLCDControlBuffer.bg3cnt.priority = 2;

    EndAllMus();

    SetDispEnable(0, 0, 0, 0, 0);

    sModeSelectBlendAmount = 10;
    sModeSelectBlendThreshold = 100;

    SetPrimaryHBlankHandler(ModeSelectBg_UpdateSpellCircleBlend);

    CopyToPaletteBuffer(Pal_084138F0, 0x220, 0x100);
    CopyToPaletteBuffer(Pal_0840F9A0, 0, 0x60);

    Decompress(Img_08418E44, (void*)(GetBackgroundTileDataOffset(BG_0) + 0x6000000));
    CallARM_FillTileRect(ModeSelectBg0Tm, Tsa_0840FA00, 0);

    Decompress(Img_0840FEB4, (void*)(GetBackgroundTileDataOffset(BG_3) + 0x6000000));
    // TODO(needs emulator/visual verification): the FE7 source calls this
    // BG3 tilemap through a lower-level 4-arg primitive
    // (dest, tsaData, base=0, linebits=5) than CallARM_FillTileRect's own
    // single packed 3rd argument; this repo's decomp doesn't have that
    // primitive under its own name, so the packed form here is a
    // best-effort mapping (base 0 contributes nothing, so linebits=5 is
    // passed through directly) rather than a confirmed-correct one.
    CallARM_FillTileRect(ModeSelectBg3Tm, Tsa_08411F34, 5);

    BG_EnableSyncByMask(BG3_SYNC_BIT);
}

// FE7U: 0x080A7C6C
static void ModeSelect_InitGfxMaybe(struct ModeSelectProc* proc)
{
    if (proc->unk_42 & 1)
        ModeSelect_InitBgs();
}

static const struct FaceVramEntry sModeSelectFaceConfig[] = {
    { .tileOffset = 0x1000, .paletteId = 0xC },
    { .tileOffset = 0x1000, .paletteId = 0xC },
    { .tileOffset = 0x1000, .paletteId = 0xC },
    { .tileOffset = 0x1000, .paletteId = 0xC },
};

extern u16 Pal_084150C0[];
extern u8 Img_08414940[];
extern u8 Tsa_084150E0_Full[];

extern u16 Pal_08415AA0[];
extern u8 Img_08415594[];
extern u8 Tsa_08415AC0[];

extern u16 Pal_0841625C[];

static void ModeSelectBg_ApplyCompressedTsa(u16* dest, u8* compressedTsa, u16 tileref)
{
    Decompress(compressedTsa, gGenericBuffer);
    CallARM_FillTileRect(dest, gGenericBuffer, tileref);
}

// FE7U: 0x080A7C84
static void ModeSelect_Init(struct ModeSelectProc* proc)
{
    int i;

    LoadObjUIGfx();

    BG_SetPosition(BG_1, 8, -8);

    Proc_BlockEachMarked(PROC_MARK_SAVEDRAW);
    Proc_BlockEachMarked(PROC_MARK_D);

    sModeSelectBlendThreshold = 100;

    SetupFaceGfxData((struct FaceVramEntry*)sModeSelectFaceConfig);

    ApplyPalette(Pal_08415AA0, 0xF);

    Decompress(Img_08415594, (void*)(0x6000000 + GetBackgroundTileDataOffset(1)));
    CallARM_FillTileRect(ModeSelectBg0Tm, Tsa_084150E0_Full, 0);
    ModeSelectBg_ApplyCompressedTsa(ModeSelectClawTm, Tsa_08415AC0, 0xf000);
    ApplyPalette(Pal_084150C0, 0x1B);

    Decompress(Img_08414940, (void*)0x6010000);
    ApplyPalette(Pal_0841625C, 0x1A);

    ResetClassReelSpell();
    NewEfxAnimeDrvProc();

    proc->unk_38 = Proc_Start(sProc_ModeSelectSpriteDraw, proc);
    ModeSelectSpriteDraw_SetCenter(0, 0x70);

    proc->unk_41 = 0;
    proc->unk_4c = 0;

    proc->unk_40 = ModeSelect_GetUnlockedDifficultyMask();

    if ((proc->unk_42 & 1) == 0)
    {
        static const int sHardModeMask[] = { 4, 0x10 };

        proc->unk_4c = 2;
        proc->unk_49[0] = 1;
        proc->unk_49[1] = 2;

        for (i = 0; i < proc->unk_4c; i++)
        {
            if ((gPlaySt.chapterStateBits & PLAY_FLAG_HARD) && (proc->unk_40 & sHardModeMask[i]))
                proc->unk_43[i] = 1;
            else
                proc->unk_43[i] = 0;
        }
    }
    else
    {
        proc->unk_49[0] = 0;
        proc->unk_4c++;

        if (proc->unk_40 & 2)
        {
            proc->unk_49[proc->unk_4c] = 1;
            proc->unk_4c++;
        }

        if (proc->unk_40 & 8)
        {
            proc->unk_49[proc->unk_4c] = 2;
            proc->unk_4c++;
        }

        for (i = 0; i < proc->unk_4c; i++)
            proc->unk_43[i] = 0;
    }

    ModeSelectSpriteDraw_SetSlotCount(proc->unk_4c);
    InitModeSelectAnims(proc->unk_4c, proc->unk_49);

    for (i = 0; i < proc->unk_4c; i++)
        ModeSelectPalette_CacheUndimmed(i);

    ModeSelectSpriteDraw_SetGlowing(true);
    StartUiSpinningArrows(proc);
    LoadUiSpinningArrowGfx(0, 0xd20, 9);
    LoadUiSpinningArrowGfx(0, 0xd20, 9);
    SetUiSpinningArrowPositions(30, 61, 68, 61);
    SetUiSpinningArrowConfig(3);

    InitTextFont(&sModeSelectText.font, (void*)0x600E000, 0x100, 0xe);

    InitText(&sModeSelectText.text[0], 5);
    InitText(&sModeSelectText.text[1], 9);
    InitText(&sModeSelectText.text[2], 5);
    InitText(&sModeSelectText.text[3], 8);
    InitText(&sModeSelectText.text[4], 4);
    InitText(&sModeSelectText.text[5], 10);
    InitText(&sModeSelectText.text[6], 5);

    proc->unk_30 = proc->unk_41 * ModeSelectSpriteDraw_GetSlotAngleStep() * 0x10;

    proc->unk_3c = StartModeSelectFace(proc->unk_49[proc->unk_41]);
    PutModeSelectLabelText();
    PutModeSelectCharacterText(proc->unk_49[proc->unk_41]);
    PutModeSelectDifficultyText(proc);
    ModeSelectSpriteDraw_SetSpin(proc->unk_43[proc->unk_41], proc->unk_42);
    ModeSelectSpriteDraw_SetAngle(proc->unk_30);

    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT);

    proc->unk_2c = 0;
    proc->unk_50 = 0;

    SetWinEnable(1, 0, 0);
    SetWin0Layers(1, 1, 1, 1, 1);
    SetWin0Box(0, 0x50, 0xf0, 0x50);
    SetWOutLayers(0, 0, 0, 0, 0);

    LoadModeSelectChapterGfx(proc->unk_49[proc->unk_41]);

    // clang-format off
    SetObjAffine(
        0,
        Div(+COS(0) * 16, 0x100),
        Div(-SIN(0) * 16, 0x100),
        Div(+SIN(0) * 16, 0x100),
        Div(+COS(0) * 16, 0x100)
    );
    // clang-format on
}

// FE7U: 0x080A8054
static void ModeSelect_TransitionSplitOpen(struct ModeSelectProc* proc)
{
    s32 tmp;
    s32 step = ++proc->unk_2c;

    SetDispEnable(1, 1, 1, 1, 1);

    tmp = 0x48 - (((0x10 - step) * 0x48) * (0x10 - step) / 256);

    SetWin0Box(0, 0x50 - tmp, 0xf0, tmp + 0x50);

    if (step == 0x10)
        Proc_Break(proc);
}

// FE7U: 0x080A80C4
static void ModeSelect_TransitionSplitClose(struct ModeSelectProc* proc)
{
    s32 tmp;
    s32 step = ++proc->unk_2c;

    tmp = 0x48 - (((0x10 - step) * 0x48) * (0x10 - step) / 256);

    SetWin0Box(0, tmp + 8, 0xf0, -0x68 - tmp);

    if (step == 0x10)
        Proc_Break(proc);
}

static void ModeSelect_StopSpinAndResetTimer(struct ModeSelectProc* proc)
{
    s32 i;

    for (i = 0; i < proc->unk_4c; i++)
        ModeSelectAnim_Pause(&sModeSelectAnimBuf[i]);

    proc->unk_50 = 0;
}

static void ModeSelect_SetDifficulty(struct ModeSelectProc* proc, s32 hard)
{
    proc->unk_43[proc->unk_41] = hard;

    PutModeSelectDifficultyText(proc);
    ModeSelectSpriteDraw_SetSpin(hard, proc->unk_42);
}

// FE7U: 0x080A817C
static void ModeSelect_Loop_KeyHandler(struct ModeSelectProc* proc)
{
    if ((gKeyStatusPtr->repeatedKeys & DPAD_UP) && proc->unk_43[proc->unk_41] == 1)
    {
        PlaySoundEffect(0x66);
        ModeSelect_SetDifficulty(proc, 0);
        return;
    }

    if (gKeyStatusPtr->repeatedKeys & DPAD_DOWN)
    {
        if (proc->unk_43[proc->unk_41] == 0)
        {
            if (proc->unk_49[proc->unk_41] == 0 && !(proc->unk_40 & 1))
            {
                PlaySoundEffect(0x6c);
                return;
            }

            if (proc->unk_49[proc->unk_41] == 1 && !(proc->unk_40 & 4))
            {
                PlaySoundEffect(0x6c);
                return;
            }

            if (proc->unk_49[proc->unk_41] == 2 && !(proc->unk_40 & 0x10))
            {
                PlaySoundEffect(0x6c);
                return;
            }

            PlaySoundEffect(0x66);
            ModeSelect_SetDifficulty(proc, 1);
            return;
        }
    }

    if (gKeyStatusPtr->heldKeys & (DPAD_LEFT | L_BUTTON))
    {
        Proc_Goto(proc, 1);
        SetUiSpinningArrowFastMaybe(0);
        PlaySoundEffect(0x67);
        ModeSelect_StopSpinAndResetTimer(proc);
        return;
    }

    if (gKeyStatusPtr->heldKeys & (DPAD_RIGHT | R_BUTTON))
    {
        Proc_Goto(proc, 2);
        SetUiSpinningArrowFastMaybe(1);
        PlaySoundEffect(0x67);
        ModeSelect_StopSpinAndResetTimer(proc);
        return;
    }

    if (gKeyStatusPtr->newKeys & (START_BUTTON | A_BUTTON))
    {
        proc->unk_2c = 0;

        PlaySoundEffect(0x6a);
        Proc_Goto(proc, 3);

        sModeSelectAnimBuf[proc->unk_41].roundType = 0;
        RestartMainMiniAnim(&sModeSelectAnimBuf[proc->unk_41]);

        if (proc->unk_42 & 1)
        {
            if (proc->unk_41 == 0)
                gPlaySt.chapterModeIndex = 2;

            if (proc->unk_41 == 1)
                gPlaySt.chapterModeIndex = 3;

            if (proc->unk_43[proc->unk_41] != 0)
                gPlaySt.chapterStateBits |= PLAY_FLAG_HARD;
            else
                gPlaySt.chapterStateBits &= ~PLAY_FLAG_HARD;
        }
        else
        {
            SaveMenu_SetDifficultyChoice(proc->unk_49[proc->unk_41], proc->unk_43[proc->unk_41]);
            ModeSelectSpriteDraw_SetSpin(proc->unk_43[proc->unk_41], proc->unk_42 | 2);
        }

        ModeSelectSpriteDraw_SetActive(1);
        return;
    }

    if ((gKeyStatusPtr->newKeys & B_BUTTON) && !(proc->unk_42 & 1))
    {
        proc->unk_2c = 0;

        PlaySoundEffect(0x6b);
        Proc_Goto(proc, 4);
        SaveMenu_SetDifficultyChoice(3, 0);
    }

    proc->unk_50++;

    if ((proc->unk_50 & 0x1ff) == 0x20)
    {
        sModeSelectAnimBuf[proc->unk_41].roundType = 2;
        RestartMainMiniAnim(&sModeSelectAnimBuf[proc->unk_41]);
    }

    if ((proc->unk_50 & 0x1ff) != 0x80)
        return;

    ModeSelectAnim_Pause(&sModeSelectAnimBuf[proc->unk_41]);
}

// FE7U: 0x080A8424
static void ModeSelect_RotateRight(struct ModeSelectProc* proc)
{
    proc->unk_34 = -1;
    proc->unk_2c = 0;

    StartFaceFadeOut(proc->unk_3c);

    if (proc->unk_41 == 0)
        proc->unk_41 = proc->unk_4c - 1;
    else
        proc->unk_41--;

    proc->unk_32 = (0x100 - ModeSelectSpriteDraw_GetSlotAngleStep() * proc->unk_41) << 4;

    ModeSelect_SetDifficulty(proc, proc->unk_43[proc->unk_41]);

    if (proc->unk_32 < proc->unk_30)
        proc->unk_32 += 0x1000;
}

// FE7U: 0x080A848C
static void ModeSelect_RotateLeft(struct ModeSelectProc* proc)
{
    proc->unk_34 = 1;
    proc->unk_2c = 0;

    StartFaceFadeOut(proc->unk_3c);

    if (proc->unk_41 < proc->unk_4c - 1)
        proc->unk_41++;
    else
        proc->unk_41 = 0;

    proc->unk_32 = (0x100 - ModeSelectSpriteDraw_GetSlotAngleStep() * proc->unk_41) << 4;

    ModeSelect_SetDifficulty(proc, proc->unk_43[proc->unk_41]);

    if (proc->unk_32 > proc->unk_30)
        proc->unk_30 += 0x1000;
}

// FE7U: 0x080A84F8
static void ModeSelect_Loop_RotateCarousel(struct ModeSelectProc* proc)
{
    s32 a, b, c;
    u16 angle;

    a = (proc->unk_32 - proc->unk_30) * proc->unk_34;
    proc->unk_2c++;

    b = a >> 2;
    c = b * (0x1e - proc->unk_2c) * (0x1e - proc->unk_2c) / 900;
    angle = proc->unk_30 + proc->unk_34 * 4 * (b - c);

    if (proc->unk_2c == 13)
        LoadModeSelectChapterGfx(proc->unk_49[proc->unk_41]);

    if (proc->unk_2c == 14)
        proc->unk_3c = StartModeSelectFace(proc->unk_49[proc->unk_41]);

    if (proc->unk_2c == 20)
        PutModeSelectCharacterText(proc->unk_49[proc->unk_41]);

    if (proc->unk_2c == 30)
    {
        angle = proc->unk_32 & 0xfff;
        proc->unk_30 = proc->unk_32 & 0xfff;
        Proc_Break(proc);
    }

    // clang-format off
    SetObjAffine(
        0,
        Div(+COS(0) * 16, 0x100),
        Div(-SIN(0) * 16, 0x100),
        Div(+SIN(0) * 16, 0x100),
        Div(+COS(0) * 16, 0x100)
    );
    // clang-format on

    ModeSelectSpriteDraw_SetAngle(angle);
}

// FE7U: 0x080A8624
static void ModeSelect_End(struct ModeSelectProc* proc)
{
    EndModeSelectAnims(proc->unk_4c);
    EndEfxAnimeDrvProc();
    EndFaceById(0);

    /* Jester's fix (adapted): ModeSelect_Init blocks the save-menu's own
     * draw process (PROC_MARK_SAVEDRAW/PROC_MARK_D) so it doesn't render
     * underneath the carousel; it must be unblocked again here or the save
     * screen stays frozen/black after returning. Unlike the original FE7
     * hack, this repo's own PL_SAVEMENU_DIFFICULTY_SEL step already runs
     * SaveMenu_ReloadScreenFormDifficulty immediately after this proc ends
     * (src/savemenu.c) -- that call already fully rebuilds BG0-3, fonts,
     * and palettes from scratch for BOTH the plain-difficulty-select and
     * Mode Select paths, so re-running SaveMenu_Init/InitScreen/
     * LoadExtraMenuGraphics here (as the original fix does) would just be
     * redundant double-work, not a second bug fix. */
    Proc_UnblockEachMarked(PROC_MARK_SAVEDRAW);
    Proc_UnblockEachMarked(PROC_MARK_D);

    if (!(proc->unk_42 & 1))
        StartBgmVolumeChange(0x100, 0xc0, 0x10, 0);
    else
        SetPrimaryHBlankHandler(NULL);
}

// clang-format off

// FE7U: 0x08CE4930
static const struct ProcCmd sProc_ModeSelect[] =
{
    PROC_CALL(DisableAllGfx),
    PROC_YIELD,

    PROC_CALL(ModeSelect_InitGfxMaybe),
    PROC_YIELD,

    PROC_CALL(ModeSelect_Init),
    PROC_YIELD,

    PROC_REPEAT(ModeSelect_TransitionSplitOpen),

PROC_LABEL(0),
    PROC_REPEAT(ModeSelect_Loop_KeyHandler),

PROC_LABEL(1),
    PROC_CALL(ModeSelect_RotateLeft),
    PROC_REPEAT(ModeSelect_Loop_RotateCarousel),

    PROC_GOTO(0),

PROC_LABEL(2),
    PROC_CALL(ModeSelect_RotateRight),
    PROC_REPEAT(ModeSelect_Loop_RotateCarousel),

    PROC_GOTO(0),

PROC_LABEL(3),
    PROC_SLEEP(60),

PROC_LABEL(4),
    PROC_REPEAT(ModeSelect_TransitionSplitClose),
    PROC_CALL(ModeSelect_End),

    PROC_END,
};

// clang-format on

// FE7U: 0x080A8664
void StartModeSelect(ProcPtr parent)
{
    struct ModeSelectProc* proc = Proc_StartBlocking(sProc_ModeSelect, parent);
    proc->unk_42 = 1;
}

#endif // FE8_MODE_SELECT
