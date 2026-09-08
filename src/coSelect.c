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
#include "class_preview.h"
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
 * scrolling re-loads one slot in place; see CoSelect_SyncSlots.
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
/* Concurrent battle animations. Only two are ever visible at once (one is
 * always rotating off-screen), so two slots is all this needs -- and dropping
 * the third frees its OBJ VRAM block (0x06016000 onwards) for the chapter
 * title below, as well as ~32KB of the overlay. More COs than slots are
 * handled by sliding the window, not by adding slots. */
#define CO_SELECT_SLOTS 2

/* Carousel positions, which is a separate thing from the buffer count above.
 * The positions are spaced 0x100 / CO_SELECT_POSITIONS apart, so this alone
 * decides the shape of the ring: three keeps the original layout (the selected
 * CO at the front, a second one visible up beside "Change", and a third slot
 * off the left of the screen). Only two positions are ever on screen at once,
 * which is what lets two buffers cover three positions -- see
 * CoSelect_HandOffBuffer. */
#define CO_SELECT_POSITIONS 3

/* Chapter title graphics, in the OBJ VRAM freed by the third animation slot.
 * PutChapterTitleGfx takes a tile index and writes 0x800 bytes (32x2 tiles) to
 * VRAM + chr * 0x20, so 0xBC0 lands at 0x06017800 and runs to 0x06018000, the
 * top of OBJ VRAM. It also stores chr & 0x3FF as gChapterTitleFxSt.chr_str,
 * which is 0x3C0 here -- the OBJ tile number the sprite table below uses. */
#define COSELECT_CHAPTER_TITLE_CHR 0xBC0
#define COSELECT_CHAPTER_TITLE_OBJ_CHR 0x3C0

/* Where the title is drawn. The banner sits at BG1 tilemap (12, 1), and BG1 is
 * scrolled by (8, -8) (see BG_SetPosition in CoSelect_Init), so that tile shows
 * at screen (12*8 - 8, 1*8 + 8).
 *
 * Note the title block is 192px wide with the text centred inside it (see
 * CHAPTER_TITLE_TEXT_WIDTH, src/chapter_title.c), so starting it at x=88 runs
 * past the right edge of a 240px screen; x=24 is what bonusclaim.c uses to
 * centre the same block. Adjust to taste -- this is the only place to change. */
#define COSELECT_CHAPTER_TITLE_X 64
#define COSELECT_CHAPTER_TITLE_Y 25

/* OBJ palette for the chapter title. 0xF is free only because this screen now
 * runs two animations rather than three -- they take 0xD onwards
 * (animBuf->oam2Pal = buffer + 0xD). Not 9: LoadUiSpinningArrowGfx claims that
 * one for the arrows (ApplyPalette(..., palId + 0x10), src/spinning_arrow.c)
 * and runs after this in CoSelect_Init, so a title there would have had its
 * palette overwritten. The rest are spoken for: 0xA/0xB frame art, 0xC faces. */
#define COSELECT_CHAPTER_TITLE_PAL 0xF

/* A second copy of the system icon sheet, in the OBJ VRAM freed by the third
 * animation buffer.
 *
 * LoadObjUIGfx (src/bm.c) normally puts this sheet at 0x06010000, where nearly
 * everything expects to find it -- but CoSelect_Init decompresses its own frame
 * sheet over that address immediately afterwards, so by the time anything
 * draws, the icons are gone. Loading it again here keeps them available without
 * disturbing the frame.
 *
 * Copy2dChr lays the sheet into the 32-tile-wide OBJ grid four rows deep, so
 * this occupies 0x06016000-0x06017000, clear of the chapter title above it.
 * 0x06016000 is OBJ tile 0x300, and R: Info is tile 0x0B into the sheet.
 * Palettes are LoadObjUIGfx's own gPal_MiscUiGraphics, at OBJ 0/1. */
#define COSELECT_SYS_ICON_ADDR ((void*)0x06016000)
#define COSELECT_SYS_ICON_CHR 0x300
/* "R: Info" is two sprites side by side, a 32x16 followed by an 8x16 -- 40px
 * wide in total. In the 32-tile-wide 2D OBJ grid the 32x16 takes tiles
 * +0x00..+0x03 of its row (and +0x20..+0x23 of the next), so the 8x16 that
 * follows it starts four tiles further along. */
#define COSELECT_SYS_ICON_RINFO_CHR (COSELECT_SYS_ICON_CHR + 0x0B)
#define COSELECT_SYS_ICON_RINFO_CHR2 (COSELECT_SYS_ICON_RINFO_CHR + 0x04)
#define COSELECT_SYS_ICON_PAL 0
#define COSELECT_SYS_ICON_X 184
#define COSELECT_SYS_ICON_Y 57

/* Frame of the 30-frame rotation at which the buffer hand-off happens -- far
 * enough in that the outgoing animation has left the screen, early enough that
 * the incoming one is ready before it rotates into view.
 *
 * Separate per direction because the two are not symmetric: rotating left, the
 * buffer being reused is the one that was at the front and is travelling to the
 * back, so the swap has to wait until it is gone. Rotating right, it is the one
 * coming from the back to the front, so it wants loading as early as the
 * outgoing position allows. Tune independently. */
#define COSELECT_SLOT_RELOAD_FRAME_LEFT 15
#define COSELECT_SLOT_RELOAD_FRAME_RIGHT 6

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

    /* Which animation buffer each carousel position is currently using, or -1
     * for the position that has none (the one off-screen). Lives here rather
     * than on the proc so the sprite-draw proc can read it while drawing. */
    s8 posBuf[CO_SELECT_POSITIONS];

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
    /* 2C */ s32 rotTimer; // frames into the current rotation (see CoSelect_Loop_Rotate)
    /* 30 */ u16 angle; // carousel angle now
    /* 32 */ u16 angleTarget; // carousel angle the current rotation is heading for
    /* 34 */ s32 rotDir; // +1 rotating left, -1 rotating right
    /* 38 */ void* spriteProc; // ProcPtr; ProcScr_CoSelectSpriteDraw instance
    /* 3C */ struct FaceProc* faceProc;
    /* 40 */ u8 faction; // faction whose CO is being set (gEventSlots[EVT_SLOT_3])
    /* 41 */ u8 curSlot; // carousel position at the front, holding the selected CO
    /* 42 */ u8 flags; // bit0: entry flag, always set (see StartCoSelect)
    /* 43 */ u8 coCount; // number of enabled COs in coList
    /* 44 */ u8 coList[CO_COUNT]; // enabled CO ids, in ascending id order
    /* 49 */ u8 bufCo[CO_SELECT_SLOTS]; // CO id currently loaded in each anim buffer
    /* 4C */ u8 posCount; // live carousel positions, min(coCount, CO_SELECT_POSITIONS)
    /* 4D */ u8 coIndex; // coList index of the selected CO
    /* 4E */ u8 rebuilding; // set while re-entering from the CO info page
    /* 4F */ u8 syncPending; // hand a buffer over once the rotation has hidden it
    /* 50 */ s32 idleTimer; // frames since the last input, drives the idle anim replay
};

struct CoSelectSpriteDrawProc
{
    /* 00 */ PROC_HEADER;
    /* 2C */ s32 blinkTimer; // counts up once confirmed; blinks the "Press Start" sprite
    /* 30 */ s32 palTimer; // drives the OBJ pal 0xB colour cycle
    /* 34 */ s32 centerX; // carousel centre
    /* 38 */ s32 centerY;
    /* 3C */ u8 glowing; // whether to position/glow the slot animations at all
    /* 3E */ u16 angle; // carousel rotation
    /* 40 */ s32 slotCount;
    /* 44 */ s32 angleStep; // angle between adjacent slots (0x100 / slotCount)
    /* 48 */ s32 blendPhase; // ramps up and down, feeding the spell-circle blend
    /* 4C */ u8 blendDir; // 0 ramping up, 1 ramping down
    /* 4D */ u8 handRow; // hand cursor row
    /* 4E */ u8 handFlags; // bit1: freeze the hand cursor
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
 * default). */
 
static int CoSelect_GetBanimId(int coId)
{
    int classId = Co_GetDisplayClassId(coId);

    /* Pass a representative weapon rather than nothing: a class's
     * SPECIAL_BANIM_WTYPE ("unarmed") entry is usually its dodge-only
     * animation, not the combat animation you want to show off in a picker.
     * See include/class_preview.h. */
    return GetClassPreviewBanimId(classId, GetClassPreviewWeapon(classId));
}

/* Load one carousel slot with one CO's battle animation. Split out of the
 * original's init-everything loop because the slots are a sliding window: with
 * more enabled COs than slots, scrolling re-loads a single slot in place
 * rather than rebuilding the whole carousel (see CoSelect_SyncSlots). */
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

/* Give the two on-screen positions a buffer each, load them, and mark the
 * remaining position (the off-screen one) as having none. */
static void InitCoSelectAnims(struct CoSelectProc* proc)
{
    int pos;
    int buf = 0;

    for (pos = 0; pos < CO_SELECT_POSITIONS; pos++)
        sCoSelectScratch.posBuf[pos] = -1;

    for (pos = 0; pos < proc->posCount && buf < CO_SELECT_SLOTS; pos++)
    {
        int coId = proc->coList[(proc->coIndex + pos) % proc->coCount];
        int slot = (proc->curSlot + pos) % proc->posCount;

        sCoSelectScratch.posBuf[slot] = buf;
        proc->bufCo[buf] = coId;
        InitCoSelectAnimSlot(buf, coId);
        buf++;
    }
}

// FE7U: 0x080A75CC
static void EndCoSelectAnims(s32 count)
{
    int i;

    for (i = 0; i < count; i++)
        EndEkrUnitMainMini(CoSelectGetAnimBuf(i));
}

const char StrCoSelect_Commander[] = "Commander:";
const char StrCoSelect_Affinity[] = "Affinity:";

// FE7U: 0x080A75F0
static void PutCoSelectLabelText(void)
{
    ClearText(&sCoSelectScratch.text.text[4]);
    ClearText(&sCoSelectScratch.text.text[5]);

    PutDrawText(&sCoSelectScratch.text.text[4], CoSelectClawTm + TILEMAP_INDEX(14, 6), TEXT_COLOR_SYSTEM_WHITE, 0, 0, StrCoSelect_Commander);
    PutDrawText(&sCoSelectScratch.text.text[5], CoSelectClawTm + TILEMAP_INDEX(14, 10), TEXT_COLOR_SYSTEM_WHITE, 0, 0, StrCoSelect_Affinity);

    BG_EnableSyncByMask(BG1_SYNC_BIT);
}

/* The CO's name and the class being animated for them. Both come from the
 * CO's character rather than from struct CoDefinition -- see its charId. */
static void PutCoSelectCharacterText(s32 coId)
{
    const struct CharacterData* character = GetCharacterData(Co_GetCharId(coId));
    
    int briefMsg = Co_GetBriefMsg(coId);

    ClearText(&sCoSelectScratch.text.text[2]);
    ClearText(&sCoSelectScratch.text.text[3]);

    PutDrawText(&sCoSelectScratch.text.text[2], CoSelectClawTm + TILEMAP_INDEX(14, 8),
        TEXT_COLOR_SYSTEM_BLUE, 0, 0, GetStringFromIndex(character->nameTextId));

    if (briefMsg)
        PutDrawText(&sCoSelectScratch.text.text[3], CoSelectClawTm + TILEMAP_INDEX(14, 12),
            TEXT_COLOR_SYSTEM_BLUE, 0, 0, GetStringFromIndex(briefMsg));

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
    proc->palTimer = 0;
    proc->angle = 0;
    proc->glowing = 0;
    proc->centerX = DISPLAY_WIDTH / 2;
    proc->centerY = DISPLAY_HEIGHT;
    proc->slotCount = 0;
    proc->angleStep = 0;
    proc->blendPhase = 0;
    proc->blendDir = 0;
    proc->blinkTimer = 0;
    proc->handFlags = 0;
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

/* The chapter title, as six 32x16 sprites stepping four tiles at a time --
 * the same shape as the save menu's own title sprite (gSprite_SavemenuData_20,
 * src/savemenu_data.c). The 4-tile step relies on OBJ VRAM being in 2D mapping
 * mode, which is this engine's default (obj1dMap stays 0; see src/aw2_gfx.c's
 * note): a 32x16 sprite then takes four tiles from one row and four from the
 * next row of the 32-tile-wide OBJ grid, which is exactly how
 * PutChapterTitleGfx lays the 32x2 block out.
 *
 * Layer 0, not 2: BG1 (the claw frame this sits inside) is priority 0 on this
 * screen, and an OBJ only draws in front of a BG of equal priority -- at
 * layer 2 the title was hidden behind the frame. */
static const u16 Sprite_CoSelect_ChapterTitle[] = {
    6,
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16,                OAM2_CHR(COSELECT_CHAPTER_TITLE_OBJ_CHR + 0x00) + OAM2_LAYER(0),
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16 + OAM1_X(32),   OAM2_CHR(COSELECT_CHAPTER_TITLE_OBJ_CHR + 0x04) + OAM2_LAYER(0),
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16 + OAM1_X(64),   OAM2_CHR(COSELECT_CHAPTER_TITLE_OBJ_CHR + 0x08) + OAM2_LAYER(0),
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16 + OAM1_X(96),   OAM2_CHR(COSELECT_CHAPTER_TITLE_OBJ_CHR + 0x0C) + OAM2_LAYER(0),
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16 + OAM1_X(128),  OAM2_CHR(COSELECT_CHAPTER_TITLE_OBJ_CHR + 0x10) + OAM2_LAYER(0),
    OAM0_SHAPE_32x16, OAM1_SIZE_32x16 + OAM1_X(160),  OAM2_CHR(COSELECT_CHAPTER_TITLE_OBJ_CHR + 0x14) + OAM2_LAYER(0),
};

/* Load the current chapter's title into the OBJ VRAM freed by the third
 * animation slot, and put its palette in OBJ palettes 8/9 (both free on this
 * screen: the animations take 0xD-0xF, the face 0xC, and the frame art 0xA/0xB).
 *
 * This works whether or not TEXT_CHAPTER_NAMES is on -- PutChapterTitleGfx
 * renders the name as text when it is and decompresses the pre-drawn banner
 * graphic when it isn't, so no gating is needed here. Modelled on
 * BonusClaim's use of the same three calls (src/bonusclaim.c). */
static void CoSelect_LoadChapterTitle(void)
{
    ApplyChapterTitlePal(0, 0x10 + COSELECT_CHAPTER_TITLE_PAL);
    EnablePaletteSync();

    PutChapterTitleGfx(COSELECT_CHAPTER_TITLE_CHR, GetChapterTitleExtra(&gPlaySt));
}

/* Reload the system icon sheet somewhere this screen won't overwrite it --
 * same source and layout as LoadObjUIGfx (src/bm.c), just a different
 * destination. The palettes are the ones LoadObjUIGfx already applied. */
static void CoSelect_LoadSystemIcons(void)
{
#if FE8_DISPLAY_OBTAINABLE_ITEM
    /* Declared locally, as src/bm.c's LoadObjUIGfx does -- it has no header. */
    extern u8 gGfx_ObtainableItemIcons[];
#endif

#if FE8_DISPLAY_OBTAINABLE_ITEM
    /* The obtainable-item sheet is 24 tiles wide, not the vanilla 18 -- keep
     * Copy2dChr's row width matching the source, as LoadObjUIGfx does. */
    Decompress(gGfx_ObtainableItemIcons, gGenericBuffer);
    Copy2dChr(gGenericBuffer, COSELECT_SYS_ICON_ADDR, 0x18, 4);
#else
    Decompress(gGfx_MiscUiGraphics, gGenericBuffer);
    Copy2dChr(gGenericBuffer, COSELECT_SYS_ICON_ADDR, 0x12, 4);
#endif

    ApplyPalettes(gPal_MiscUiGraphics, 0x10, 2);
    EnablePaletteSync();
}

// FE7U: 0x080A79A4
static void CoSelectSpriteDraw_Loop(struct CoSelectSpriteDrawProc* proc)
{
    s32 i;

    if (proc->glowing != 0)
    {
        /* i is a carousel position, not a buffer: the position with no buffer
         * (the one off-screen) simply isn't drawn. Palettes are per-buffer, so
         * the glow is applied by buffer index while the placement uses the
         * position's own angle. */
        for (i = 0; i < proc->slotCount; i++)
        {
            s32 angle = (proc->angle >> 4) + i * proc->angleStep + 40;
            s32 x = (proc->centerX << 12) + SIN(angle) * 70;
            s32 y = (((proc->centerY << 12) + COS(angle) * 28) >> 12) - 16;
            int buf = sCoSelectScratch.posBuf[i];

            if (buf < 0)
                continue;

            SetMainMiniAnimPos(CoSelectGetAnimBuf(buf), x >> 12, y);
            CoSelectPalette_ApplyGlow(buf, (proc->angle >> 4) + i * proc->angleStep);
        }
    }

    BgAffinRotScaling(BG_2, proc->angle, 0, 0, 0x160, 0x160);
    BgAffinScaling(BG_2, 0x280, 0x100);
    BgAffinAnchoring(BG_2, proc->centerX, proc->centerY, 76, 76);

    sCoSelectScratch.blendAmount = InterpolateCubicSpline(8, 8, 16, 16, proc->blendPhase);

    if (proc->blendDir == 0)
    {
        proc->blendPhase += 8;
        if (proc->blendPhase >= 0x400)
            proc->blendDir = 1;
    }
    else
    {
        proc->blendPhase -= 8;
        if (proc->blendPhase <= 0)
            proc->blendDir = 0;
    }

    // handRow only picks which row the hand cursor sits on -- it is not a
    // spin speed.
    // if (proc->handFlags & 2)
        // DisplayFrozenUiHandExt(108, (proc->handRow & 1) * 16 + 104, OAM2_CHR(0x3C0) + OAM2_LAYER(2));
    // else
        // DisplayUiHandExt(108, proc->handRow * 16 + 104, OAM2_CHR(0x3C0) + OAM2_LAYER(2));

    PutSpriteExt(0xd, 0, 8, Sprite_CoSelect_Mode, OAM2_PAL(11));
    PutSpriteExt(0xd, 20, 28, Sprite_CoSelect_Select, OAM2_PAL(11));
    PutSpriteExt(0xd, 40, 64, Sprite_CoSelect_Change, OAM2_PAL(11));

    PutSpriteExt(0xd, COSELECT_CHAPTER_TITLE_X, COSELECT_CHAPTER_TITLE_Y,
        Sprite_CoSelect_ChapterTitle, OAM2_PAL(COSELECT_CHAPTER_TITLE_PAL));

    /* "R: Info" -- R opens the highlighted CO's info page. */
    PutSprite(0xd, COSELECT_SYS_ICON_X, COSELECT_SYS_ICON_Y, gObject_32x16,
        OAM2_CHR(COSELECT_SYS_ICON_RINFO_CHR) + OAM2_PAL(COSELECT_SYS_ICON_PAL) + OAM2_LAYER(0));
    PutSprite(0xd, COSELECT_SYS_ICON_X + 32, COSELECT_SYS_ICON_Y, gObject_8x16,
        OAM2_CHR(COSELECT_SYS_ICON_RINFO_CHR2) + OAM2_PAL(COSELECT_SYS_ICON_PAL) + OAM2_LAYER(0));

    if ((proc->blinkTimer >> 2 & 1) == 0)
        PutSpriteExt(0xd, 8, 130, Sprite_CoSelect_PressStart, OAM2_PAL(11));

    if (proc->blinkTimer != 0)
        proc->blinkTimer++;

    CoSelectPalette_CyclePressStart(proc->palTimer);
    proc->palTimer++;
}

static const struct ProcCmd sProc_CoSelectSpriteDraw[] = {
    PROC_NAME("CoSelectSpriteDraw"),
    PROC_CALL(CoSelectSpriteDraw_Init),
    PROC_YIELD,
    PROC_REPEAT(CoSelectSpriteDraw_Loop),
    PROC_END,
};
const struct ProcCmd* const ProcScr_CoSelectSpriteDraw = sProc_CoSelectSpriteDraw;

// Starts the "Press Start" blink timer (blinkTimer counts up from 1; bit 2 of
// it gates whether the sprite is drawn each frame).
static void CoSelectSpriteDraw_SetActive(bool active)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
        proc->blinkTimer = 1;
}

static void CoSelectSpriteDraw_SetGlowing(bool glowing)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
        proc->glowing = glowing;
}

static void CoSelectSpriteDraw_SetSlotCount(s32 count)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
    {
        proc->slotCount = count;
        proc->angleStep = 0x100 / count;
    }
}

static void CoSelectSpriteDraw_SetCenter(s32 x, s32 y)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
    {
        proc->centerX = x;
        proc->centerY = y;
    }
    sCoSelectScratch.blendThreshold = y - 60;
}

static void CoSelectSpriteDraw_SetAngle(u16 angle)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
        proc->angle = angle;
}

static void CoSelectSpriteDraw_SetSpin(u8 direction, u8 speed)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    if (proc != NULL)
    {
        proc->handRow = direction;
        proc->handFlags = speed;
    }
}

static s32 CoSelectSpriteDraw_GetSlotAngleStep(void)
{
    struct CoSelectSpriteDrawProc* proc = Proc_Find(ProcScr_CoSelectSpriteDraw);
    return proc->angleStep;
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
// always run when entering via StartCoSelect (flags & 1 is always set).
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
    if (proc->flags & 1)
        CoSelect_InitBgs();
}

static const struct FaceVramEntry sCoSelectFaceConfig[] = {
    { .tileOffset = 0x1000, .paletteId = 0xC },
    { .tileOffset = 0x1000, .paletteId = 0xC },
    { .tileOffset = 0x1000, .paletteId = 0xC },
    { .tileOffset = 0x1000, .paletteId = 0xC },
};

extern u16 Pal_084150C0[];
/* CO select's own OBJ sheet (src/data/const_data_coselect.c), replacing Mode
 * Select's Img_08414940 -- same 128-tile layout and same OBJ palette 0xB, just
 * "CO" wording on the label sprites. */
extern u8 Img_CoSelectObjFrame[];
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

    Decompress(Img_CoSelectObjFrame, (void*)0x6010000);
    ApplyPalette(Pal_0841625C, 0x1A);

    CoSelect_LoadChapterTitle();
    CoSelect_LoadSystemIcons();

    ResetClassReelSpell();
    NewEfxAnimeDrvProc();

    proc->spriteProc = Proc_Start(sProc_CoSelectSpriteDraw, proc);
    CoSelectSpriteDraw_SetCenter(0, 0x70);

    /* On a rebuild (returning from the CO info page) the CO list and the
     * selection are already set up and must be preserved -- only the
     * graphics below need recreating. */
    if (!proc->rebuilding)
    {
        proc->curSlot = 0;
        proc->posCount = 0;
        proc->coCount = 0;

        /* Enabled COs come from gEventSlot[1] as a bitfield (bit N = CO id N), with
         * 0 meaning "all of them" so a script can just omit the SVAL. Anything the
         * mask selects beyond CO_COUNT is ignored, and CO_NONE is skipped
         * outright -- it is the "faction has no commander" marker, not a CO, and
         * its sCoDefinitions entry is blank (no character, no animation). */
        {
            u32 mask = gEventSlots[EVT_SLOT_1];

            if (mask == 0)
                mask = ~0u;

            for (i = CO_NONE + 1; i < CO_COUNT; i++)
            {
                if (mask & (1u << i))
                {
                    proc->coList[proc->coCount] = i;
                    proc->coCount++;
                }
            }
        }

        /* An empty mask would leave the carousel with nothing to draw and no valid
         * selection, so fall back to the first real CO rather than running empty. */
        if (proc->coCount == 0)
        {
            proc->coList[0] = CO_NONE + 1;
            proc->coCount = 1;
        }

        proc->faction = gEventSlots[EVT_SLOT_3];

        /* Carousel positions, capped at CO_SELECT_POSITIONS -- this is what sets
         * the ring's spacing. The animation buffers are a separate, smaller
         * budget handed around between positions (see CoSelect_HandOffBuffer). */
        proc->posCount = proc->coCount < CO_SELECT_POSITIONS
            ? proc->coCount
            : CO_SELECT_POSITIONS;
        proc->coIndex = 0;
    }

    CoSelectSpriteDraw_SetSlotCount(proc->posCount);
    InitCoSelectAnims(proc);

    for (i = 0; i < CO_SELECT_SLOTS; i++)
        CoSelectPalette_CacheUndimmed(i);

    CoSelectSpriteDraw_SetGlowing(true);
    StartUiSpinningArrows(proc);
    LoadUiSpinningArrowGfx(0, 0xd20, 9);
    LoadUiSpinningArrowGfx(0, 0xd20, 9);
    SetUiSpinningArrowPositions(30, 61, 68, 61);
    SetUiSpinningArrowConfig(3);
    

    InitTextFont(&sCoSelectScratch.text.font, (void*)0x600E000, 0x100, 0xe);

    InitText(&sCoSelectScratch.text.text[0], 8);
    InitText(&sCoSelectScratch.text.text[1], 9);
    InitText(&sCoSelectScratch.text.text[2], 8);
    InitText(&sCoSelectScratch.text.text[3], 8);
    InitText(&sCoSelectScratch.text.text[4], 10);
    InitText(&sCoSelectScratch.text.text[5], 8);

    /* Resting angle for whichever slot is at the front. This has to use the
     * same formula CoSelect_RotateLeft/Right target and CoSelect_Loop_Rotate
     * settles on, or the carousel ends up parked between slots.
     *
     * The FE7 original wrote `curSlot * angleStep * 0x10` here, which happens
     * to agree only when curSlot is 0 -- always true there, because Init only
     * ever ran on a fresh screen. It is not true on the rebuild coming back
     * from the CO info page, which restores a non-zero curSlot: that left the
     * wrong CO facing front (so the class animation belonged to a different
     * CO) and made the next rotation compute a huge delta and spin wildly. */
    proc->angle = ((0x100 - CoSelectSpriteDraw_GetSlotAngleStep() * proc->curSlot) << 4) & 0xfff;

    proc->faceProc = StartCoSelectFace(proc->coList[proc->coIndex]);
    PutCoSelectLabelText();
    PutCoSelectCharacterText(proc->coList[proc->coIndex]);
    CoSelectSpriteDraw_SetSpin(0, proc->flags);
    CoSelectSpriteDraw_SetAngle(proc->angle);
    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT);

    proc->rotTimer = 0;
    proc->idleTimer = 0;
    proc->syncPending = FALSE;

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
    s32 step = ++proc->rotTimer;

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
    s32 step = ++proc->rotTimer;

    tmp = 0x48 - (((0x10 - step) * 0x48) * (0x10 - step) / 256);

    SetWin0Box(0, tmp + 8, 0xf0, -0x68 - tmp);

    if (step == 0x10)
        Proc_Break(proc);
}

static void CoSelect_StopSpinAndResetTimer(struct CoSelectProc* proc)
{
    s32 i;

    for (i = 0; i < CO_SELECT_SLOTS; i++)
        CoSelectAnim_Pause(CoSelectGetAnimBuf(i));

    proc->idleTimer = 0;
}

/* The animation buffer showing the selected CO, i.e. the one at the front
 * position. curSlot is a carousel position, not a buffer index, so it has to
 * go through the position->buffer map. Never NULL in practice: the front
 * position always has a buffer. */
static struct AnimBuffer* CoSelectGetFrontAnimBuf(struct CoSelectProc* proc)
{
    int buf = sCoSelectScratch.posBuf[proc->curSlot];

    return CoSelectGetAnimBuf(buf < 0 ? 0 : buf);
}

/* The CO that belongs at carousel position p: the front position shows the
 * selected CO, and each position further round the ring shows the next CO in
 * the list. */
static int CoSelect_CoForPosition(struct CoSelectProc* proc, int pos)
{
    int offset = (pos - proc->curSlot + proc->posCount) % proc->posCount;

    return proc->coList[(proc->coIndex + offset) % proc->coCount];
}

/* Load an animation buffer with a CO, replacing whatever it held. */
static void CoSelect_LoadBuffer(struct CoSelectProc* proc, int buf, int coId)
{
    if (proc->bufCo[buf] == coId)
        return;

    EndEkrUnitMainMini(CoSelectGetAnimBuf(buf));
    proc->bufCo[buf] = coId;
    InitCoSelectAnimSlot(buf, coId);
    CoSelectPalette_CacheUndimmed(buf);
}

/* Move the buffer from the position that has just rotated off-screen onto the
 * position rotating on, and load the CO that position needs.
 *
 * There are three carousel positions but only two animation buffers, which
 * works because only two positions are ever on screen at once. Whichever
 * direction the ring turns, exactly one position leaves the screen and one
 * arrives, so the leaving position's buffer is handed straight to the arriving
 * one. Relative to the already-updated curSlot the leaving position is always
 * the one behind the front; the arriving one is the new front when rotating
 * right, or the far side of the ring when rotating left.
 *
 * Only needed when there are more positions than buffers -- with two or fewer
 * COs every position keeps its own buffer permanently. */
static void CoSelect_HandOffBuffer(struct CoSelectProc* proc, int dir)
{
    int leaving;
    int arriving;
    int buf;

    if (proc->posCount <= CO_SELECT_SLOTS)
        return;

    leaving  = (proc->curSlot + proc->posCount - 1) % proc->posCount;
    arriving = dir > 0 ? (proc->curSlot + 1) % proc->posCount : proc->curSlot;

    buf = sCoSelectScratch.posBuf[leaving];

    if (buf < 0)
        return;

    sCoSelectScratch.posBuf[leaving] = -1;
    sCoSelectScratch.posBuf[arriving] = buf;

    CoSelect_LoadBuffer(proc, buf, CoSelect_CoForPosition(proc, arriving));
}

/* Advance the selection by one CO and rotate the carousel one position.
 * dir is +1 for "left" (the next CO in the list) and -1 for "right".
 *
 * The buffer hand-off is deliberately not done here: at this instant both
 * visible positions are still on screen, so swapping either one's animation
 * now would change a CO in place in front of the player. It waits until
 * COSELECT_SLOT_RELOAD_FRAME_LEFT/_RIGHT, by which point the leaving position
 * has gone. */
static void CoSelect_Step(struct CoSelectProc* proc, int dir)
{
    proc->coIndex = (proc->coIndex + dir + proc->coCount) % proc->coCount;
    proc->curSlot = (proc->curSlot + dir + proc->posCount) % proc->posCount;

    proc->syncPending = TRUE;
}

// FE7U: 0x080A817C
static void CoSelect_Loop_KeyHandler(struct CoSelectProc* proc)
{
    /* L is deliberately not a rotate any more: R opens the CO info page, so
     * leaving L on rotation would make the two shoulder buttons do unrelated
     * things. Rotation is the d-pad. */
    if (gKeyStatusPtr->heldKeys & DPAD_LEFT)
    {
        Proc_Goto(proc, 1);
        SetUiSpinningArrowFastMaybe(0);
        PlaySoundEffect(0x67);
        CoSelect_StopSpinAndResetTimer(proc);
        return;
    }

    if (gKeyStatusPtr->newKeys & R_BUTTON)
    {
        PlaySoundEffect(0x6a);
        Proc_Goto(proc, 5);
        return;
    }

    if (gKeyStatusPtr->heldKeys & DPAD_RIGHT)
    {
        Proc_Goto(proc, 2);
        SetUiSpinningArrowFastMaybe(1);
        PlaySoundEffect(0x67);
        CoSelect_StopSpinAndResetTimer(proc);
        return;
    }

    if (gKeyStatusPtr->newKeys & (START_BUTTON | A_BUTTON))
    {
        proc->rotTimer = 0;

        PlaySoundEffect(0x6a);
        Proc_Goto(proc, 3);

        CoSelectGetFrontAnimBuf(proc)->roundType = 0;
        RestartMainMiniAnim(CoSelectGetFrontAnimBuf(proc));

        /* Commit the highlighted CO to the faction the caller asked for. */
        SetFactionCo(proc->faction, proc->coList[proc->coIndex]);

        CoSelectSpriteDraw_SetActive(1);
        return;
    }

    proc->idleTimer++;

    if ((proc->idleTimer & 0x1ff) == 0x20)
    {
        CoSelectGetFrontAnimBuf(proc)->roundType = 2;
        RestartMainMiniAnim(CoSelectGetFrontAnimBuf(proc));
    }

    if ((proc->idleTimer & 0x1ff) != 0x80)
        return;

    CoSelectAnim_Pause(CoSelectGetFrontAnimBuf(proc));
}

// FE7U: 0x080A8424
static void CoSelect_RotateRight(struct CoSelectProc* proc)
{
    proc->rotDir = -1;
    proc->rotTimer = 0;

    StartFaceFadeOut(proc->faceProc);

    CoSelect_Step(proc, -1);

    proc->angleTarget = (0x100 - CoSelectSpriteDraw_GetSlotAngleStep() * proc->curSlot) << 4;

    if (proc->angleTarget < proc->angle)
        proc->angleTarget += 0x1000;
}

// FE7U: 0x080A848C
static void CoSelect_RotateLeft(struct CoSelectProc* proc)
{
    proc->rotDir = 1;
    proc->rotTimer = 0;

    StartFaceFadeOut(proc->faceProc);

    CoSelect_Step(proc, +1);

    proc->angleTarget = (0x100 - CoSelectSpriteDraw_GetSlotAngleStep() * proc->curSlot) << 4;

    if (proc->angleTarget > proc->angle)
        proc->angle += 0x1000;
}

// FE7U: 0x080A84F8
static void CoSelect_Loop_RotateCarousel(struct CoSelectProc* proc)
{
    s32 a, b, c;
    u16 angle;

    a = (proc->angleTarget - proc->angle) * proc->rotDir;
    proc->rotTimer++;

    b = a >> 2;
    c = b * (0x1e - proc->rotTimer) * (0x1e - proc->rotTimer) / 900;
    angle = proc->angle + proc->rotDir * 4 * (b - c);

    if (proc->rotTimer == 14)
        proc->faceProc = StartCoSelectFace(proc->coList[proc->coIndex]);

    if (proc->rotTimer == 20)
        PutCoSelectCharacterText(proc->coList[proc->coIndex]);

    /* Buffer hand-off -- see CoSelect_HandOffBuffer. By this point the leaving
     * position has rotated off-screen, and the arriving one still has the rest
     * of the rotation before it is visible. rotDir is +1 rotating left. */
    if (proc->syncPending &&
        proc->rotTimer == (proc->rotDir > 0
            ? COSELECT_SLOT_RELOAD_FRAME_LEFT
            : COSELECT_SLOT_RELOAD_FRAME_RIGHT))
    {
        proc->syncPending = FALSE;
        CoSelect_HandOffBuffer(proc, proc->rotDir);
    }

    if (proc->rotTimer == 30)
    {
        angle = proc->angleTarget & 0xfff;
        proc->angle = proc->angleTarget & 0xfff;

        /* Safety net: if the frame above was somehow missed, never leave the
         * carousel settled with a position holding the wrong CO. */
        if (proc->syncPending)
        {
            proc->syncPending = FALSE;
            CoSelect_HandOffBuffer(proc, proc->rotDir);
        }

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
    EndCoSelectAnims(CO_SELECT_SLOTS);
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
    
    
    // InitBmBgLayers();
    // UnpackChapterMapGraphics(gPlaySt.chapterIndex);
    
    RefreshBMapGraphics();
    
    
    RenderBmMap();
    RefreshUnitSprites();
    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT | BG2_SYNC_BIT | BG3_SYNC_BIT);
}

/* 
static void RefreshTrapsAndTerrain(void)
{
    ApplyEnabledMapChanges();
    RefreshTerrainBmMap();
    RefreshAllLightRunes();
    UpdateRoofedUnits();
    RefreshUnitSprites();
    RenderBmMap();
}
*/

/* Tear the carousel down so the CO info page can have the screen.
 *
 * This is not optional politeness: gCoScreen, gStatScreen and gUiTmScratchA/B/C
 * (src/power.c, src/statscreen.c) all live inside ewram_overlay_coselect --
 * every ewram_overlay_* section starts at __ewram_start, so the CO screen's
 * own state physically overlaps this screen's animation buffers. The
 * animations cannot survive it and are rebuilt from scratch on the way back
 * rather than restored. */
static void CoSelect_TeardownForCoInfo(struct CoSelectProc* proc)
{
    EndCoSelectAnims(CO_SELECT_SLOTS);
    EndEfxAnimeDrvProc();
    EndFaceById(0);
    EndUiSpinningArrows();

    if (proc->spriteProc != NULL)
    {
        Proc_End(proc->spriteProc);
        proc->spriteProc = NULL;
    }

    SetPrimaryHBlankHandler(NULL);
    SetWinEnable(0, 0, 0);
}

/* R: open the highlighted CO's info page, blocking until B closes it. */
static void CoSelect_StartCoInfo(struct CoSelectProc* proc)
{
    StartCoScreenForCo(proc, proc->coList[proc->coIndex]);
}

/* Mark the CoSelect_Init that follows as a rebuild, so it recreates the
 * graphics without rebuilding the CO list or resetting the selection. */
static void CoSelect_MarkRebuilding(struct CoSelectProc* proc)
{
    proc->rebuilding = TRUE;
}

static void CoSelect_ClearRebuilding(struct CoSelectProc* proc)
{
    proc->rebuilding = FALSE;
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

PROC_LABEL(5),
    /* R -> CO info page, B -> back here. The CO screen shares EWRAM with this
     * screen (see CoSelect_TeardownForCoInfo), so the carousel is torn down
     * and rebuilt around it rather than left standing underneath. */
    PROC_CALL(CoSelect_TeardownForCoInfo),
    PROC_CALL(CoSelect_StartCoInfo),
    PROC_YIELD,

    PROC_CALL(DisableAllGfx),
    PROC_YIELD,
    PROC_CALL(CoSelect_MarkRebuilding),
    PROC_CALL(CoSelect_InitGfxMaybe),
    PROC_YIELD,
    PROC_CALL(CoSelect_Init),
    PROC_CALL(CoSelect_ClearRebuilding),
    PROC_YIELD,
    PROC_REPEAT(CoSelect_TransitionSplitOpen),
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
    proc->flags = 1;
}

#endif // FE8_CO_POWERS
