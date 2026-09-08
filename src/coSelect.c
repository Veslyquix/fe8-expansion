#include "global.h"

#if FE8_CO_POWERS

#include "proc.h"
#include "hardware.h"
#include "bm.h"
#include "m4a.h"
#include "soundwrapper.h"
#include "fontgrp.h"
#include "face.h"
#include "uiutils.h"
#include "ctc.h"
#include "ekrbattle.h"
#include "efxbattle.h"
#include "bmlib.h"
#include "mu.h"
#include "sysutil.h"
#include "statscreen.h"
#include "bmunit.h"
#include "bmmap.h"
#include "bmudisp.h"
#include "event.h"
#include "power.h"
#include "coSelect.h"
#include "bmio.h" 

#include "constants/characters.h"
#include "constants/faces.h"
#include "constants/songs.h"

/* CO select: pick a faction's commander from a spinning carousel, using the
 * same screen the Mode Select port (src/modeselect.c) builds -- same
 * backgrounds, claw frame, rotoscaled BG2 spell circle, portrait and text
 * layout -- with the three lords replaced by the COs from sCoDefinitions
 * (src/power.c) and the difficulty rows dropped.
 *
 * Entry point is StartCoSelect, called as an ASMC from an event script, so it
 * runs on the live battle map rather than from a menu. It reads two event
 * slots: EVT_SLOT_1 is a bitfield of enabled CO ids (0 = all), EVT_SLOT_3 is
 * the faction whose commander is being set. Pressing A/START commits the
 * highlighted CO via SetFactionCo.
 *
 * Each CO animates as their real unit's current class if that unit is on the
 * map, else the character's defaultClass -- see Co_GetDisplayClassId
 * (src/power.c) and CoSelect_GetBanimId below.
 *
 * Only CO_SELECT_SLOTS battle animations are ever loaded at once. With more
 * enabled COs than that, the slots are a sliding window over the CO list and
 * scrolling re-loads one slot in place; see CoSelect_SlideWindow.
 *
 * RAM: like Mode Select, all three slots' animation scratch plus this file's
 * own state live in one dedicated EWRAM overlay. That is not optional --
 * every ewram_overlay_* section starts at __ewram_start, so overlay tags alias
 * each other and buffers borrowed from two different tags would overlap. The
 * flip side is that this overlay necessarily sits on top of every other one,
 * so anything in another overlay that must survive this screen has to be
 * re-created on the way out. Unit and map state is plain EWRAM_DATA (see
 * src/bmunit.c, src/bmmap.c) and so is unaffected, but transient overlay-0 map
 * state is not: CoSelect_End rebuilds the map display for that reason. Known
 * remaining risk is anything else parked in overlay 0 during an event -- e.g.
 * sWeatherEffect (src/bmio.c) -- which may need re-applying if it turns out to
 * matter in practice.
 */

#define CoSelectBg0Tm gBG0TilemapBuffer
#define CoSelectClawTm gBG1TilemapBuffer
#define CoSelectBg3Tm gBG3TilemapBuffer

struct CoSelectTextState
{
    struct Font font;
    // text[3] in the FE7 source is allocated (InitText) but never drawn to
    // (no PutDrawText call anywhere references it, in either source) -- a
    // genuinely dead slot there, so it's dropped here. Indices above it
    // are renumbered down by one accordingly (old 4/5/6 -> 3/4/5).
    struct Text text[6];
};

/* Per-slot battle-animation scratch buffer sizes. These come from the FE7
 * source's own hardcoded per-slot address strides (0x020000F4/0x020060F4/
 * 0x020168F4/0x02016AD4 and friends), and they match this repo's own banim
 * buffers exactly -- with one caveat on the image sheet: the decomp declares
 * gBanimLeftImgSheetBuf as [0x1000], but RegisterAISSheetGraphics
 * (src/banim-ekrmain.c) decompresses and DMAs a full 0x2000 into it. Vanilla
 * gets away with that because gEkrKakudaiSomeBufLeft[0x1000] sits immediately
 * after it; the sheet is really one 0x2000 buffer split across two names.
 * Size the real thing correctly here rather than inheriting that overflow. */
/* Concurrent battle animations. Three fits the carousel's look (one always
 * off-screen) and costs about 97KB of the shared overlay window; more COs than
 * this are handled by sliding the window, not by adding slots. */
#define CO_SELECT_SLOTS 3

#define COSELECT_IMGSHEET_SIZE 0x2000
#define COSELECT_OAM_SIZE      0x5800
#define COSELECT_PALETTE_SIZE  0x00A0
#define COSELECT_FRAMEDATA_SIZE 0x2A00

/* All of this screen's state -- the three carousel slots' animation scratch
 * plus this file's own small per-slot/UI state -- lives in one dedicated
 * EWRAM overlay (linker/expansion.ld's ewram_overlay_coselect).
 *
 * The earlier attempt here borrowed individual buffers from the banim and
 * gamestart overlays (gBanimLeftImgSheetBuf/gBanimOaml/gBanimScrLeft for
 * slots 0-1, gUnk_0/gUnk_1/gUnk_2 for slot 2) and put this struct in
 * gUiTmScratchA/C. That cannot work: every ewram_overlay_* tag starts at
 * __ewram_start, so the banim and gamestart buffers are *the same physical
 * memory* as each other, and gUiTmScratch{A,B,C} land inside gBanimScr*.
 * Slot 2's OAM buffer overlapped slot 1's image sheet and both palettes,
 * and slot 0's frame data overlapped this very struct -- which is what
 * produced the corrupted/upside-down third lord, the bad OAM ("oops obj
 * xsiz"), and the earlier AnimBuffer pointer corruption.
 *
 * A dedicated tag is disjoint by construction and still costs no new EWRAM:
 * overlays alias each other by design, and this one is smaller than the
 * gamestart overlay it shares an address range with. Nothing here is live
 * outside this screen -- no battle animation and no opening cinematic runs
 * while the save menu's New Game flow is open.
 *
 * A dedicated tag only guarantees the three slots don't collide with *each
 * other*. It guarantees nothing about other tags: since every tag starts at
 * __ewram_start, this struct necessarily sits on top of overlay 0, banim,
 * gamestart and the rest. Anything in another overlay that must survive this
 * screen has to be re-created on the way out -- see CoSelect_End, which
 * reloads the save-slot metadata (EWRAM_OVERLAY(0)) this struct overwrites. */
struct CoSelectScratch
{
    u8 imgSheet[CO_SELECT_SLOTS][COSELECT_IMGSHEET_SIZE];
    u8 oam[CO_SELECT_SLOTS][COSELECT_OAM_SIZE];
    u8 frameData[CO_SELECT_SLOTS][COSELECT_FRAMEDATA_SIZE];
    u8 palette[CO_SELECT_SLOTS][COSELECT_PALETTE_SIZE];

    struct AnimBuffer animBuf[CO_SELECT_SLOTS];
    struct AnimMagicFxBuffer magicFx[CO_SELECT_SLOTS];
    u16 paletteCache[CO_SELECT_SLOTS * 15]; // gUnk_0201E9F4 in the FE7 source
    struct CoSelectTextState text;
    u8 blendThreshold; // gUnk_CoSelect_02000000 in the FE7 source
    u8 blendAmount;    // gUnk_CoSelect_02000001 in the FE7 source
};

EWRAM_OVERLAY(coselect) struct CoSelectScratch sCoSelectScratch = {0};

static struct AnimBuffer* CoSelectGetAnimBuf(int slot)
{
    return &sCoSelectScratch.animBuf[slot];
}

static struct AnimMagicFxBuffer* CoSelectGetMagicFx(int slot)
{
    return &sCoSelectScratch.magicFx[slot];
}

struct CoSelectProc
{
    /* 00 */ PROC_HEADER;
    /* 2C */ s32 unk_2c;
    /* 30 */ u16 unk_30;
    /* 32 */ u16 unk_32;
    /* 34 */ s32 unk_34;
    /* 38 */ void* unk_38; // ProcPtr; ProcScr_CoSelectSpriteDraw instance
    /* 3C */ struct FaceProc* unk_3c;
    /* 40 */ u8 faction; // faction whose CO is being set (gEventSlot[3])
    /* 41 */ u8 unk_41; // currently-highlighted carousel slot (0..slotCount-1)
    /* 42 */ u8 unk_42; // bit0: entry flag, always set (see StartCoSelect)
    /* 43 */ u8 coCount; // number of enabled COs in coList
    /* 44 */ u8 coList[CO_COUNT]; // enabled CO ids, in ascending id order
    /* 49 */ u8 slotCo[CO_SELECT_SLOTS]; // CO id currently loaded in each anim slot
    /* 4C */ u8 unk_4c; // number of live anim slots (min(coCount, CO_SELECT_SLOTS))
    /* 4D */ u8 windowBase; // coList index shown by slot 0 (see CoSelect_SlideWindow)
    /* 50 */ s32 unk_50;
};

struct CoSelectSpriteDrawProc
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
 * the trusted FE8CoSelect.c source, hardcoded to unlock everything.
 * Keeping that exactly as committed there, not as a regression. */
// src/code_80AC6AC.c -- not yet declared in any header (see its own file's
// still-address-named filename), so forward-declared here like this repo's
// own convention for other not-yet-header-exposed functions.
int InterpolateCubicSpline(int a, int b, int c, int d, int e);

static void CoSelectAnim_Pause(struct AnimBuffer* pAnimBuf)
{
    pAnimBuf->anim1->state3 |= 8;
    pAnimBuf->anim2->state3 |= 8;
}

/* Battle animation for a CO, from the class Co_GetDisplayClassId picks (their
 * real unit's current class if that unit is on the map, else the character's
 * default). Mirrors the engine's own lookup: walk the class's BattleAnimDef
 * list for its SPECIAL_BANIM_WTYPE ("no weapon") entry, falling back to the
 * first entry, and note the stored index is 1-based. */
 
// int GetDebuggerDefaultPreviewWeapon(int classId); 
static int CoSelect_GetBanimId(int coId)
{
    const struct ClassData* class = GetClassData(Co_GetDisplayClassId(coId));
    const struct BattleAnimDef* animDef;
    int i;

    if (class == NULL || class->pBattleAnimDef == NULL)
        return 0;

    animDef = class->pBattleAnimDef;
    
    return animDef[0].index - 1; 

    // for (i = 0; animDef[i].index != 0; i++)
        // if (animDef[i].wtype == SPECIAL_BANIM_WTYPE)
            // return animDef[i].index - 1;

    // return animDef[0].index != 0 ? animDef[0].index - 1 : 0;
}

/* Load one carousel slot with one CO's battle animation. Split out of the
 * original's init-everything loop because the slots are a sliding window: with
 * more enabled COs than slots, scrolling re-loads a single slot in place
 * rather than rebuilding the whole carousel (see CoSelect_SlideWindow). */
static void InitCoSelectAnimSlot(int i, int coId)
{
    {
        struct AnimBuffer* animBuf = CoSelectGetAnimBuf(i);
        struct AnimMagicFxBuffer* magicFx = CoSelectGetMagicFx(i);

        animBuf->xPos = 320;
        animBuf->yPos = 88;
        animBuf->animId = CoSelect_GetBanimId(coId);
        animBuf->roundType = 6;
        animBuf->genericPalId = 0;
        animBuf->state2 = 1;
        animBuf->oam2Tile = (i * 0x2000 + 0x2000) >> 5;
        animBuf->oam2Pal = i + 0xd;

        animBuf->pImgSheetBuf = sCoSelectScratch.imgSheet[i];
        animBuf->unk_24 = sCoSelectScratch.oam[i];
        animBuf->unk_20 = sCoSelectScratch.palette[i];
        animBuf->unk_28 = sCoSelectScratch.frameData[i];

        animBuf->charPalId = 0xffff;

        animBuf->unk_30 = magicFx;

        magicFx->magicFuncIdx = 0;
        magicFx->xOffsetBg = 0;
        magicFx->yOffsetBg = 0;
        magicFx->xOffsetObj = 0;
        magicFx->yOffsetObj = 0;
        magicFx->objChr = 0;
        magicFx->objPalId = 0;
        magicFx->bgChr = 0;
        magicFx->bgPalId = 0;
        magicFx->bg = 0;

        magicFx->bgTmBuf = NULL;
        magicFx->bgImgBuf = NULL;
        magicFx->bgTsaBuf = NULL;
        magicFx->objImgBuf = NULL;
        magicFx->resetCallback = NULL;

        NewEkrUnitMainMini(animBuf);
    }
}

static void InitCoSelectAnims(struct CoSelectProc* proc)
{
    int i;

    for (i = 0; i < proc->unk_4c; i++)
        InitCoSelectAnimSlot(i, proc->slotCo[i]);
}

// FE7U: 0x080A75CC
static void EndCoSelectAnims(s32 count)
{
    int i;

    for (i = 0; i < count; i++)
        EndEkrUnitMainMini(CoSelectGetAnimBuf(i));
}

const char StrCoSelect_Commander[] = "Commander:";
const char StrCoSelect_Class[] = "Class:";

// FE7U: 0x080A75F0
static void PutCoSelectLabelText(void)
{
    ClearText(&sCoSelectScratch.text.text[4]);
    ClearText(&sCoSelectScratch.text.text[5]);

    PutDrawText(&sCoSelectScratch.text.text[4], CoSelectClawTm + TILEMAP_INDEX(14, 6), TEXT_COLOR_SYSTEM_WHITE, 0, 0, StrCoSelect_Commander);
    PutDrawText(&sCoSelectScratch.text.text[5], CoSelectClawTm + TILEMAP_INDEX(14, 10), TEXT_COLOR_SYSTEM_WHITE, 0, 0, StrCoSelect_Class);

    BG_EnableSyncByMask(BG1_SYNC_BIT);
}

/* The CO's name and the class being animated for them. Both come from the
 * CO's character rather than from struct CoDefinition -- see its charId. */
static void PutCoSelectCharacterText(s32 coId)
{
    const struct CharacterData* character = GetCharacterData(Co_GetCharId(coId));
    const struct ClassData* class = GetClassData(Co_GetDisplayClassId(coId));

    ClearText(&sCoSelectScratch.text.text[2]);
    ClearText(&sCoSelectScratch.text.text[3]);

    PutDrawText(&sCoSelectScratch.text.text[2], CoSelectClawTm + TILEMAP_INDEX(14, 8),
        TEXT_COLOR_SYSTEM_BLUE, 0, 0, GetStringFromIndex(character->nameTextId));

    if (class != NULL)
        PutDrawText(&sCoSelectScratch.text.text[3], CoSelectClawTm + TILEMAP_INDEX(19, 10),
            TEXT_COLOR_SYSTEM_BLUE, 0, 0, GetStringFromIndex(class->nameTextId));

    BG_EnableSyncByMask(BG1_SYNC_BIT);
}

// FE7U: 0x080A77C0
static struct FaceProc* StartCoSelectFace(int coId)
{
    int faceId = GetCharacterData(Co_GetCharId(coId))->portraitId;
    struct FaceProc* pFaceProc = StartFace2(0, faceId, 204, 72, (FACE_DISP_KIND(FACE_96x80) | FACE_DISP_HLAYER(FACE_HLAYER_0)));
    StartFaceFadeIn(pFaceProc);
    return pFaceProc;
}

// FE7U: 0x080A7860 -- caches this slot's undimmed palette for
// CoSelectPalette_ApplyBlend to fade from every frame.
static void CoSelectPalette_CacheUndimmed(s32 palId)
{
    int i;
    u16* src = gPaletteBuffer + (palId + 0xd) * 0x10 + 0x101;

    for (i = 0; i < 0xf; i++)
        sCoSelectScratch.paletteCache[i + palId * 0xf] = *src++;
}

// FE7U: 0x080A7890
static void CoSelectPalette_ApplyBlend(s32 palId, s32 amount)
{
    s32 i;
    u16* dst = gPaletteBuffer + (palId + 0xd) * 0x10 + 0x101;

    if (amount > 0x40)
        amount = 0x40;

    amount = amount + (sCoSelectScratch.blendAmount - 10) * 2;

    for (i = 0; i < 0xf; i++)
    {
        s32 accum = 0;
        s32 r, g, b;
        u16 base = sCoSelectScratch.paletteCache[i + palId * 0xf];

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
static void CoSelectPalette_ApplyGlow(s32 palId, s32 signedByte)
{
    s32 b = signedByte & 0xff;
    s32 amount = (((b >= 0x81) ? b - 0x80 : 0x80 - b) * 0x30 >> 7);
    CoSelectPalette_ApplyBlend(palId, amount + 0x10);
}

// FE7U: 0x080A796C
static void CoSelectSpriteDraw_Init(struct CoSelectSpriteDrawProc* proc)
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
static const u16 Sprite_CoSelect_Mode[] = {
    4,
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16, 0,
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16 + OAM1_X(32), OAM2_CHR(0x4),
    OAM0_SHAPE_32x8 + OAM0_Y(16), OAM1_SIZE_32x8, OAM2_CHR(0x40),
    OAM0_SHAPE_32x8 + OAM0_Y(16), OAM1_SIZE_32x8 + OAM1_X(32), OAM2_CHR(0x44),
};

// FE7U: 0x08CE4856
static const u16 Sprite_CoSelect_Select[] = {
    6,
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16, OAM2_CHR(0x8),
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16 + OAM1_X(32), OAM2_CHR(0xC),
    OAM0_SHAPE_8x16, OAM1_SIZE_8x16 + OAM1_X(64), OAM2_CHR(0x10),
    OAM0_SHAPE_32x8 + OAM0_Y(16), OAM1_SIZE_32x8, OAM2_CHR(0x60),
    OAM0_SHAPE_32x8 + OAM0_Y(16), OAM1_SIZE_32x8 + OAM1_X(32), OAM2_CHR(0x64),
    OAM0_SHAPE_8x8 + OAM0_Y(16), OAM1_SIZE_8x8 + OAM1_X(64), OAM2_CHR(0x68),
};

// FE7U: 0x08CE487C
static const u16 Sprite_CoSelect_PressStart[] = {
    5,
    OAM0_SHAPE_32x8, OAM1_SIZE_32x8, OAM2_CHR(0x11),
    OAM0_SHAPE_32x8 + OAM0_Y(8), OAM1_SIZE_32x8, OAM2_CHR(0x49),
    OAM0_SHAPE_32x8, OAM1_SIZE_32x8 + OAM1_X(32), OAM2_CHR(0x31),
    OAM0_SHAPE_32x8 + OAM0_Y(8), OAM1_SIZE_32x8 + OAM1_X(32), OAM2_CHR(0x4D),
    OAM0_SHAPE_8x16, OAM1_SIZE_8x16 + OAM1_X(64), OAM2_CHR(0x55),
};

// FE7U: 0x08CE489C
static const u16 Sprite_CoSelect_Change[] = {
    1,
    OAM0_SHAPE_32x8, OAM1_SIZE_32x8, OAM2_CHR(0x51),
};

// clang-format on

extern u16 Pal_084150C0[];

/* Palette cycling for the "Press Start" sprite (OBJ palette 0xB, colour 13).
 *
 * FE7U: 0x080A73F8. Both FE8CoSelect.c and Jester's fork leave this as an
 * empty stub, so it was ported here from the FE7 ROM's own Thumb code rather
 * than from either C source. It crossfades between colours 12 and 13 of
 * Pal_084150C0 (the same palette ApplyPalette loads into slot 0x1B) on a
 * 64-step triangle wave: rising over 0-31, falling over 32-63. Both halves
 * use weights summing to 32, hence the >> 5. */
static void CoSelectPalette_CyclePressStart(s32 timer)
{
    s32 t = timer & 0x3f;
    s32 wA, wB;
    u16 a = Pal_084150C0[12];
    u16 b = Pal_084150C0[13];
    s32 color;

    if (t <= 31)
    {
        wA = 32 - t;
        wB = t;
    }
    else
    {
        wA = t - 32;
        wB = 64 - t;
    }

    color = ((((a & RED_MASK) * wA + (b & RED_MASK) * wB) >> 5) & RED_MASK);
    color += ((((a & GREEN_MASK) * wA + (b & GREEN_MASK) * wB) >> 5) & GREEN_MASK);
    color += ((((a & BLUE_MASK) * wA + (b & BLUE_MASK) * wB) >> 5) & BLUE_MASK);

    gPaletteBuffer[0x100 + 0xb * 0x10 + 0xd] = color;

    EnablePaletteSync();
}

// FE7U: 0x080A79A4
static void CoSelectSpriteDraw_Loop(struct CoSelectSpriteDrawProc* proc)
{
    s32 i;

    if (proc->unk_3c != 0)
    {
        for (i = 0; i < proc->unk_40; i++)
        {
            s32 angle = (proc->unk_3e >> 4) + i * proc->unk_44 + 40;
            s32 x = (proc->unk_34 << 12) + SIN(angle) * 70;
            s32 y = (((proc->unk_38 << 12) + COS(angle) * 28) >> 12) - 16;

            SetMainMiniAnimPos(CoSelectGetAnimBuf(i), x >> 12, y);
            CoSelectPalette_ApplyGlow(i, (proc->unk_3e >> 4) + i * proc->unk_44);
        }
    }

    BgAffinRotScaling(BG_2, proc->unk_3e, 0, 0, 0x160, 0x160);
    BgAffinScaling(BG_2, 0x280, 0x100);
    BgAffinAnchoring(BG_2, proc->unk_34, proc->unk_38, 76, 76);

    sCoSelectScratch.blendAmount = InterpolateCubicSpline(8, 8, 16, 16, proc->unk_48);

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

    // unk_4d is the chosen difficulty (0 = Normal, 1 = Hard); it only picks
    // which row the hand cursor sits on. It is NOT a spin speed — feeding it
    // into unk_3e made the carousel rotate whenever Hard was selected.
    if (proc->unk_4e & 2)
        DisplayFrozenUiHandExt(108, (proc->unk_4d & 1) * 16 + 104, OAM2_CHR(0x3C0) + OAM2_LAYER(2));
    else
        DisplayUiHandExt(108, proc->unk_4d * 16 + 104, OAM2_CHR(0x3C0) + OAM2_LAYER(2));

    PutSpriteExt(0xd, 0, 8, Sprite_CoSelect_Mode, OAM2_PAL(11));
    PutSpriteExt(0xd, 20, 28, Sprite_CoSelect_Select, OAM2_PAL(11));
    PutSpriteExt(0xd, 40, 64, Sprite_CoSelect_Change, OAM2_PAL(11));

    if ((proc->unk_2c >> 2 & 1) == 0)
        PutSpriteExt(0xd, 8, 130, Sprite_CoSelect_PressStart, OAM2_PAL(11));

    if (proc->unk_2c != 0)
        proc->unk_2c++;

    CoSelectPalette_CyclePressStart(proc->unk_30);
    proc->unk_30++;
}

static const struct ProcCmd sProc_CoSelectSpriteDraw[] = {
    PROC_NAME("CoSelectSpriteDraw"),
    PROC_CALL(CoSelectSpriteDraw_Init),
    PROC_YIELD,
    PROC_REPEAT(CoSelectSpriteDraw_Loop),
    PROC_END,
};
const struct ProcCmd* const ProcScr_CoSelectSpriteDraw = sProc_CoSelectSpriteDraw;

// Starts the "Press Start" blink timer (unk_2c counts up from 1; bit 2 of it
// gates whether the sprite is drawn each frame).
static void CoSelectSpriteDraw_SetActive(bool active)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
        proc->unk_2c = 1;
}

static void CoSelectSpriteDraw_SetGlowing(bool glowing)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
        proc->unk_3c = glowing;
}

static void CoSelectSpriteDraw_SetSlotCount(s32 count)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
    {
        proc->unk_40 = count;
        proc->unk_44 = 0x100 / count;
    }
}

static void CoSelectSpriteDraw_SetCenter(s32 x, s32 y)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
    {
        proc->unk_34 = x;
        proc->unk_38 = y;
    }
    sCoSelectScratch.blendThreshold = y - 60;
}

static void CoSelectSpriteDraw_SetAngle(u16 angle)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
        proc->unk_3e = angle;
}

static void CoSelectSpriteDraw_SetSpin(u8 direction, u8 speed)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
    {
        proc->unk_4d = direction;
        proc->unk_4e = speed;
    }
}

static s32 CoSelectSpriteDraw_GetSlotAngleStep(void)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    return proc->unk_44;
}

// Blend effect on the outer spell-circle background (HBlank handler).
static void CoSelectBg_UpdateSpellCircleBlend(void)
{
    u16 vcount = REG_VCOUNT + 1;

    if (vcount > DISPLAY_HEIGHT)
        vcount = 0;

    if (vcount & 1)
        return;

    if (vcount < sCoSelectScratch.blendThreshold)
    {
        REG_BLDCNT = 0xc1;
        REG_BLDY = (sCoSelectScratch.blendThreshold != 0)
            ? (sCoSelectScratch.blendThreshold - vcount) * 0x10 / sCoSelectScratch.blendThreshold
            : 0;
    }
    else
    {
        REG_BLDCNT = 0x144;
        REG_BLDALPHA = sCoSelectScratch.blendAmount | 0x1000;
    }
}

static const u16 sCoSelectBgConfig[] = {
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
// always run when entering via StartCoSelect (unk_42 & 1 is always set).
static void CoSelect_InitBgs(void)
{
    SetupBackgrounds((u16*)sCoSelectBgConfig);

    gLCDControlBuffer.dispcnt.mode = 1;

    gLCDControlBuffer.bg2cnt.screenSize = 1;
    gLCDControlBuffer.bg2cnt.areaOverflowMode = 0;

    gLCDControlBuffer.bg0cnt.priority = 3;
    gLCDControlBuffer.bg1cnt.priority = 0;
    gLCDControlBuffer.bg2cnt.priority = 2;
    gLCDControlBuffer.bg3cnt.priority = 2;

    EndAllMus();

    SetDispEnable(0, 0, 0, 0, 0);

    sCoSelectScratch.blendAmount = 10;
    sCoSelectScratch.blendThreshold = 100;

    SetPrimaryHBlankHandler(CoSelectBg_UpdateSpellCircleBlend);

    CopyToPaletteBuffer(Pal_084138F0, 0x220, 0x100);
    CopyToPaletteBuffer(Pal_0840F9A0, 0, 0x60);

    Decompress(Img_08418E44, (void*)(GetBackgroundTileDataOffset(BG_0) + 0x6000000));
    CallARM_FillTileRect(CoSelectBg0Tm, Tsa_0840FA00, 0);

    Decompress(Img_0840FEB4, (void*)(GetBackgroundTileDataOffset(BG_3) + 0x6000000));
    // The FE7 source's `sub_800154C(gBg3Tm, Tsa_08411F34, 0, 5)` is this
    // repo's BlitU8TileMapData (FE8U 0x0800154C) — the 8-bit affine-map
    // blit, NOT CallARM_FillTileRect. BG2/BG3 here are affine layers
    // (dispcnt.mode = 1), so their maps are one byte per tile; using the
    // 16-bit tilemap fill instead produces garbage on BG2.
    BlitU8TileMapData(CoSelectBg3Tm, Tsa_08411F34, 0, 5);

    BG_EnableSyncByMask(BG3_SYNC_BIT);
}

// FE7U: 0x080A7C6C
static void CoSelect_InitGfxMaybe(struct CoSelectProc* proc)
{
    if (proc->unk_42 & 1)
        CoSelect_InitBgs();
}

static const struct FaceVramEntry sCoSelectFaceConfig[] = {
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

static void CoSelectBg_ApplyCompressedTsa(u16* dest, u8* compressedTsa, u16 tileref)
{
    Decompress(compressedTsa, gGenericBuffer);
    CallARM_FillTileRect(dest, gGenericBuffer, tileref);
}

// FE7U: 0x080A7C84
static void CoSelect_Init(struct CoSelectProc* proc)
{
    int i;

    LoadObjUIGfx();

    BG_SetPosition(BG_1, 8, -8);

    Proc_BlockEachMarked(PROC_MARK_SAVEDRAW);
    Proc_BlockEachMarked(PROC_MARK_D);

    sCoSelectScratch.blendThreshold = 100;

    SetupFaceGfxData((struct FaceVramEntry*)sCoSelectFaceConfig);

    ApplyPalette(Pal_08415AA0, 0xF);

    Decompress(Img_08415594, (void*)(0x6000000 + GetBackgroundTileDataOffset(1)));
    CallARM_FillTileRect(CoSelectBg0Tm, Tsa_084150E0_Full, 0);
    CoSelectBg_ApplyCompressedTsa(CoSelectClawTm, Tsa_08415AC0, 0xf000);
    ApplyPalette(Pal_084150C0, 0x1B);

    Decompress(Img_08414940, (void*)0x6010000);
    ApplyPalette(Pal_0841625C, 0x1A);

    ResetClassReelSpell();
    NewEfxAnimeDrvProc();

    proc->unk_38 = Proc_Start(sProc_CoSelectSpriteDraw, proc);
    CoSelectSpriteDraw_SetCenter(0, 0x70);

    proc->unk_41 = 0;
    proc->unk_4c = 0;
    proc->coCount = 0;

    /* Enabled COs come from gEventSlot[1] as a bitfield (bit N = CO id N), with
     * 0 meaning "all of them" so a script can just omit the SVAL. Anything the
     * mask selects beyond CO_COUNT is ignored. */
    {
        u32 mask = gEventSlots[EVT_SLOT_1];

        if (mask == 0)
            mask = ~0u;

        for (i = 0; i < CO_COUNT; i++)
        {
            if (mask & (1u << i))
            {
                proc->coList[proc->coCount] = i;
                proc->coCount++;
            }
        }
    }

    /* An empty mask would leave the carousel with nothing to draw and no valid
     * selection, so fall back to the first CO rather than running empty. */
    if (proc->coCount == 0)
    {
        proc->coList[0] = 0;
        proc->coCount = 1;
    }

    proc->faction = gEventSlots[EVT_SLOT_3];

    /* The anim slots are a window over coList: as many as there are COs, capped
     * at CO_SELECT_SLOTS. With more COs than slots the window slides (see
     * CoSelect_SlideWindow) instead of the carousel growing. */
    proc->unk_4c = proc->coCount < CO_SELECT_SLOTS ? proc->coCount : CO_SELECT_SLOTS;

    for (i = 0; i < proc->unk_4c; i++)
        proc->slotCo[i] = proc->coList[i];

    CoSelectSpriteDraw_SetSlotCount(proc->unk_4c);
    InitCoSelectAnims(proc);

    for (i = 0; i < proc->unk_4c; i++)
        CoSelectPalette_CacheUndimmed(i);

    CoSelectSpriteDraw_SetGlowing(true);
    StartUiSpinningArrows(proc);
    LoadUiSpinningArrowGfx(0, 0xd20, 9);
    LoadUiSpinningArrowGfx(0, 0xd20, 9);
    SetUiSpinningArrowPositions(30, 61, 68, 61);
    SetUiSpinningArrowConfig(3);
    

    InitTextFont(&sCoSelectScratch.text.font, (void*)0x600E000, 0x100, 0xe);

    InitText(&sCoSelectScratch.text.text[0], 5);
    InitText(&sCoSelectScratch.text.text[1], 9);
    InitText(&sCoSelectScratch.text.text[2], 5);
    InitText(&sCoSelectScratch.text.text[3], 4);
    InitText(&sCoSelectScratch.text.text[4], 10);
    InitText(&sCoSelectScratch.text.text[5], 5);

    proc->unk_30 = proc->unk_41 * CoSelectSpriteDraw_GetSlotAngleStep() * 0x10;

    proc->unk_3c = StartCoSelectFace(proc->slotCo[proc->unk_41]);
    PutCoSelectLabelText();
    PutCoSelectCharacterText(proc->slotCo[proc->unk_41]);
    CoSelectSpriteDraw_SetSpin(0, proc->unk_42);
    CoSelectSpriteDraw_SetAngle(proc->unk_30);
    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT);

    proc->unk_2c = 0;
    proc->unk_50 = 0;

    SetWinEnable(1, 0, 0);
    SetWin0Layers(1, 1, 1, 1, 1);
    SetWin0Box(0, 0x50, 0xf0, 0x50);
    SetWOutLayers(0, 0, 0, 0, 0);

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
static void CoSelect_TransitionSplitOpen(struct CoSelectProc* proc)
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
static void CoSelect_TransitionSplitClose(struct CoSelectProc* proc)
{
    s32 tmp;
    s32 step = ++proc->unk_2c;

    tmp = 0x48 - (((0x10 - step) * 0x48) * (0x10 - step) / 256);

    SetWin0Box(0, tmp + 8, 0xf0, -0x68 - tmp);

    if (step == 0x10)
        Proc_Break(proc);
}

static void CoSelect_StopSpinAndResetTimer(struct CoSelectProc* proc)
{
    s32 i;

    for (i = 0; i < proc->unk_4c; i++)
        CoSelectAnim_Pause(CoSelectGetAnimBuf(i));

    proc->unk_50 = 0;
}

/* Which entry of coList a carousel slot is showing. The window's first slot
 * holds windowBase; slots run forward from there, wrapping around coList. */
static int CoSelect_SlotCoListIndex(struct CoSelectProc* proc, int slot)
{
    return (proc->windowBase + slot) % proc->coCount;
}

/* Slide the window one step so `slot` becomes the selection. Only meaningful
 * when there are more COs than slots: the slot rotating out of view is
 * re-loaded in place with the CO coming into view, which is one battle-anim
 * re-init per press rather than a full carousel rebuild. */
static void CoSelect_SlideWindow(struct CoSelectProc* proc, int dir)
{
    int slot;
    int coId;

    if (proc->coCount <= proc->unk_4c)
        return;

    proc->windowBase = (proc->windowBase + dir + proc->coCount) % proc->coCount;

    /* Moving forward, the slot that just left the back of the window is the one
     * now at its front, and vice versa. */
    slot = dir > 0 ? (proc->unk_4c - 1) : 0;
    coId = proc->coList[CoSelect_SlotCoListIndex(proc, slot)];

    if (proc->slotCo[slot] == coId)
        return;

    EndEkrUnitMainMini(CoSelectGetAnimBuf(slot));
    proc->slotCo[slot] = coId;
    InitCoSelectAnimSlot(slot, coId);
    CoSelectPalette_CacheUndimmed(slot);
}

// FE7U: 0x080A817C
static void CoSelect_Loop_KeyHandler(struct CoSelectProc* proc)
{
    if (gKeyStatusPtr->heldKeys & (DPAD_LEFT | L_BUTTON))
    {
        Proc_Goto(proc, 1);
        SetUiSpinningArrowFastMaybe(0);
        PlaySoundEffect(0x67);
        CoSelect_StopSpinAndResetTimer(proc);
        return;
    }

    if (gKeyStatusPtr->heldKeys & (DPAD_RIGHT | R_BUTTON))
    {
        Proc_Goto(proc, 2);
        SetUiSpinningArrowFastMaybe(1);
        PlaySoundEffect(0x67);
        CoSelect_StopSpinAndResetTimer(proc);
        return;
    }

    if (gKeyStatusPtr->newKeys & (START_BUTTON | A_BUTTON))
    {
        proc->unk_2c = 0;

        PlaySoundEffect(0x6a);
        Proc_Goto(proc, 3);

        CoSelectGetAnimBuf(proc->unk_41)->roundType = 0;
        RestartMainMiniAnim(CoSelectGetAnimBuf(proc->unk_41));

        /* Commit the highlighted CO to the faction the caller asked for. */
        SetFactionCo(proc->faction, proc->slotCo[proc->unk_41]);

        CoSelectSpriteDraw_SetActive(1);
        return;
    }

    proc->unk_50++;

    if ((proc->unk_50 & 0x1ff) == 0x20)
    {
        CoSelectGetAnimBuf(proc->unk_41)->roundType = 2;
        RestartMainMiniAnim(CoSelectGetAnimBuf(proc->unk_41));
    }

    if ((proc->unk_50 & 0x1ff) != 0x80)
        return;

    CoSelectAnim_Pause(CoSelectGetAnimBuf(proc->unk_41));
}

// FE7U: 0x080A8424
static void CoSelect_RotateRight(struct CoSelectProc* proc)
{
    proc->unk_34 = -1;
    proc->unk_2c = 0;

    StartFaceFadeOut(proc->unk_3c);

    if (proc->unk_41 == 0)
    {
        CoSelect_SlideWindow(proc, -1);
        proc->unk_41 = proc->unk_4c - 1;
    }
    else
    {
        proc->unk_41--;
    }

    proc->unk_32 = (0x100 - CoSelectSpriteDraw_GetSlotAngleStep() * proc->unk_41) << 4;

    if (proc->unk_32 < proc->unk_30)
        proc->unk_32 += 0x1000;
}

// FE7U: 0x080A848C
static void CoSelect_RotateLeft(struct CoSelectProc* proc)
{
    proc->unk_34 = 1;
    proc->unk_2c = 0;

    StartFaceFadeOut(proc->unk_3c);

    if (proc->unk_41 < proc->unk_4c - 1)
    {
        proc->unk_41++;
    }
    else
    {
        CoSelect_SlideWindow(proc, 1);
        proc->unk_41 = 0;
    }

    proc->unk_32 = (0x100 - CoSelectSpriteDraw_GetSlotAngleStep() * proc->unk_41) << 4;

    if (proc->unk_32 > proc->unk_30)
        proc->unk_30 += 0x1000;
}

// FE7U: 0x080A84F8
static void CoSelect_Loop_RotateCarousel(struct CoSelectProc* proc)
{
    s32 a, b, c;
    u16 angle;

    a = (proc->unk_32 - proc->unk_30) * proc->unk_34;
    proc->unk_2c++;

    b = a >> 2;
    c = b * (0x1e - proc->unk_2c) * (0x1e - proc->unk_2c) / 900;
    angle = proc->unk_30 + proc->unk_34 * 4 * (b - c);

    if (proc->unk_2c == 14)
        proc->unk_3c = StartCoSelectFace(proc->slotCo[proc->unk_41]);

    if (proc->unk_2c == 20)
        PutCoSelectCharacterText(proc->slotCo[proc->unk_41]);

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

    CoSelectSpriteDraw_SetAngle(angle);
}

// FE7U: 0x080A8624
static void CoSelect_End(struct CoSelectProc* proc)
{
    EndCoSelectAnims(proc->unk_4c);
    EndEfxAnimeDrvProc();
    EndFaceById(0);

    /* CoSelect_Init blocks the map's own draw processes so they don't render
     * underneath the carousel; unblock them or the map stays frozen. */
    Proc_UnblockEachMarked(PROC_MARK_SAVEDRAW);
    Proc_UnblockEachMarked(PROC_MARK_D);

    SetPrimaryHBlankHandler(NULL);

    /* Hand the screen back to the map. Unlike Mode Select -- which returns to
     * the save menu, whose own script redraws everything -- this runs from an
     * event on the live map, so nothing else is going to restore the display:
     * put the backgrounds, window and blend registers back the way the map
     * expects and let the event's own fade bring it back in. */
    SetupBackgrounds(NULL);
    gLCDControlBuffer.dispcnt.mode = 0;
    gLCDControlBuffer.bg2cnt.screenSize = 0;
    gLCDControlBuffer.bg2cnt.areaOverflowMode = 0;
    SetWinEnable(0, 0, 0);
    SetWOutLayers(1, 1, 1, 1, 1);
    SetBlendConfig(0, 0, 0, 0);
    BMapDispResume();
    UnlockGame();
    RefreshEntityBmMaps();
    RenderBmMap();
    RefreshUnitSprites();
    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT | BG2_SYNC_BIT | BG3_SYNC_BIT);
}

// clang-format off

// FE7U: 0x08CE4930
static const struct ProcCmd sProc_CoSelect[] =
{
    PROC_CALL(DisableAllGfx),
    PROC_YIELD,
    PROC_CALL(LockGame),
    PROC_CALL(BMapDispSuspend),

    PROC_CALL(CoSelect_InitGfxMaybe),
    PROC_YIELD,

    PROC_CALL(CoSelect_Init),
    PROC_YIELD,

    PROC_REPEAT(CoSelect_TransitionSplitOpen),

PROC_LABEL(0),
    PROC_REPEAT(CoSelect_Loop_KeyHandler),

PROC_LABEL(1),
    PROC_CALL(CoSelect_RotateLeft),
    PROC_REPEAT(CoSelect_Loop_RotateCarousel),

    PROC_GOTO(0),

PROC_LABEL(2),
    PROC_CALL(CoSelect_RotateRight),
    PROC_REPEAT(CoSelect_Loop_RotateCarousel),

    PROC_GOTO(0),

PROC_LABEL(3),
    PROC_SLEEP(60),

PROC_LABEL(4),
    PROC_REPEAT(CoSelect_TransitionSplitClose),
    PROC_CALL(CoSelect_End),

    PROC_END,
};

// clang-format on

/* ASMC entry point: ASMC(StartCoSelect) from an event script. Blocks the event
 * proc until the player picks a CO.
 *
 *   gEventSlots[EVT_SLOT_1] -- bitfield of enabled CO ids (bit N = CO id N),
 *                             0 meaning all of them
 *   gEventSlots[EVT_SLOT_3] -- faction whose commander is being set
 */
void StartCoSelect(ProcPtr parent)
{
    struct CoSelectProc* proc = Proc_StartBlocking(sProc_CoSelect, parent);
    proc->unk_42 = 1;
}

#endif // FE8_CO_POWERS
