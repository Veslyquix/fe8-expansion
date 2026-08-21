#include "global.h"
#include "bm.h"
#include "bmlib.h"
#include "bmitem.h"
#include "bmbattle.h"
#include "ctc.h"
#include "draw_mapanim.h"
#include "eventinfo.h"
#include "hardware.h"
#include "mapanim.h"
#include "soundwrapper.h"
#include "constants/items.h"

#if FE8_DRAW_MAP_ANIMS

#define DRAW_MAP_ANIM_OBJCHR 0x198
#define DRAW_MAP_ANIM_OBJCHR_NUMBERS 0x1C0
#define DRAW_MAP_ANIM_OBJPAL 26
#define DRAW_MAP_ANIM_OBJPAL_NUMBERS 27
#define DRAW_MAP_ANIM_VRAM_SIZE 0x800
#define DRAW_MAP_ANIM_MIN_FRAMES 28
#define DRAW_MAP_ANIM_NUMBERS_FLAG 0xEE

struct DrawMapAnimProc
{
    PROC_HEADER;

    /* 2C */ const struct DrawMapAnimFrame * frames;
    /* 30 */ u32 startClock;
    /* 34 */ u16 totalDuration;
    /* 36 */ u8 targetActorId;
    /* 37 */ u8 animId;
    /* 38 */ u8 loadedFrame;
    /* 39 */ u8 _pad39[0x3C - 0x39];
};

static int DrawMapAnim_GetTargetActorId(void)
{
    if (gManimSt.hitAttributes & BATTLE_HIT_ATTR_DEVIL)
        return gManimSt.subjectActorId;

    return gManimSt.targetActorId;
}

static int DrawMapAnim_GetAnimationId(void)
{
    u16 item = gManimSt.actor[gManimSt.subjectActorId].bu->weaponBefore;
    int itemIndex = GetItemIndex(item);

    if (itemIndex == ITEM_SWORD_SILVER)
        return DRAW_MAP_ANIM_SHARDS1;

    switch (GetItemType(item))
    {
        case ITYPE_SWORD:
            return DRAW_MAP_ANIM_MAP_SWORD;

        case ITYPE_LANCE:
            return DRAW_MAP_ANIM_MAP_LANCE;

        case ITYPE_AXE:
            return DRAW_MAP_ANIM_MAP_AXE;

        case ITYPE_BOW:
            return DRAW_MAP_ANIM_MAP_BOW;

        case ITYPE_ANIMA:
            return DRAW_MAP_ANIM_MAP_MAGIC;

        case ITYPE_LIGHT:
            return DRAW_MAP_ANIM_MAP_LIGHT;

        case ITYPE_DARK:
            return DRAW_MAP_ANIM_MAP_DARK;

        case ITYPE_MONSTER:
        case ITYPE_DRAGN:
            return DRAW_MAP_ANIM_MAP_MONSTER;
    }

    return DRAW_MAP_ANIM_NONE;
}

static u16 DrawMapAnim_GetTotalDuration(const struct DrawMapAnimFrame * frames)
{
    u16 duration = 0;

    if (!frames)
        return 0;

    while (frames->duration != 0)
    {
        duration += frames->duration;
        frames++;
    }

    return duration;
}

static const struct DrawMapAnimFrame * DrawMapAnim_GetFrameForTime(
    const struct DrawMapAnimFrame * frames,
    int elapsed)
{
    int duration = 0;

    if (!frames)
        return NULL;

    while (frames->duration != 0)
    {
        duration += frames->duration;

        if (elapsed <= duration)
            return frames;

        frames++;
    }

    return NULL;
}

static void DrawMapAnim_LoadNumbers(void)
{
    RegisterDataMove(
        gDrawMapAnimNumbersImg,
        OBJ_CHR_ADDR(DRAW_MAP_ANIM_OBJCHR_NUMBERS),
        6 * 2 * CHR_SIZE);

    CopyToPaletteBuffer(
        gDrawMapAnimNumbersPal,
        DRAW_MAP_ANIM_OBJPAL_NUMBERS * 0x20,
        0x20);
}

static void DrawMapAnim_PutDigit(int x, int y, int digit)
{
    int chr = DRAW_MAP_ANIM_OBJCHR_NUMBERS;

    if (digit > 5)
    {
        chr += 0x20;
        digit -= 6;
    }

    CallARM_PushToSecondaryOAM(
        OAM1_X(x),
        OAM0_Y(y),
        gObject_8x8,
        OAM2_CHR(chr + digit) + OAM2_PAL(DRAW_MAP_ANIM_OBJPAL_NUMBERS) + OAM2_LAYER(2));
}

static int DrawMapAnim_GetDisplayDamage(void)
{
    int damage;

    if (gManimSt.hitAttributes & BATTLE_HIT_ATTR_MISS)
        return 0;

    damage = gManimSt.hitDamage;

    if (damage <= 0)
        return 0;

    if (damage > 99)
        return 99;

    return damage;
}

static void DrawMapAnim_PutDamageNumber(struct DrawMapAnimProc * proc)
{
    struct Unit * unit;
    int elapsed;
    int height;
    int xWiggle;
    int x;
    int y;
    int damage;

    if (CheckFlag(DRAW_MAP_ANIM_NUMBERS_FLAG))
        return;

    damage = DrawMapAnim_GetDisplayDamage();
    if (damage == 0)
        return;

    unit = gManimSt.actor[proc->targetActorId].unit;
    elapsed = GetGameClock() - proc->startClock;

    height = elapsed >> 1;
    if (height > 12)
        height = 12;

    xWiggle = (height >> 1) + 4;
    while (xWiggle > 4)
        xWiggle -= 4;

    x = unit->xPos * 16 - gBmSt.camera.x + 4 - xWiggle;
    y = unit->yPos * 16 - gBmSt.camera.y - height;

    if (damage >= 10)
        DrawMapAnim_PutDigit(x, y, damage / 10);

    DrawMapAnim_PutDigit(x + 8, y, damage % 10);
}

static void DrawMapAnim_LoadFrameGfx(const struct DrawMapAnimFrame * frame)
{
    CopyToPaletteBuffer(frame->pal, DRAW_MAP_ANIM_OBJPAL * 0x20, 0x20);
    EnablePaletteSync();

    Decompress(frame->img, gGenericBuffer);
    RegisterDataMove(gGenericBuffer, OBJ_CHR_ADDR(DRAW_MAP_ANIM_OBJCHR), DRAW_MAP_ANIM_VRAM_SIZE);
}

static void DrawMapAnim_PutFrameSprite(struct DrawMapAnimProc * proc)
{
    struct Unit * unit = gManimSt.actor[proc->targetActorId].unit;
    int x = unit->xPos * 16 - gBmSt.camera.x - 24;
    int y = unit->yPos * 16 - gBmSt.camera.y - 24;

    CallARM_PushToSecondaryOAM(
        OAM1_X(x),
        OAM0_Y(y),
        gObject_64x64,
        OAM2_CHR(DRAW_MAP_ANIM_OBJCHR) + OAM2_PAL(DRAW_MAP_ANIM_OBJPAL) + OAM2_LAYER(2));
}

static void DrawMapAnim_Init(struct DrawMapAnimProc * proc)
{
    int animId = DrawMapAnim_GetAnimationId();

    proc->animId = animId;
    proc->frames = gDrawMapAnimTable[animId];
    proc->startClock = GetGameClock();
    proc->totalDuration = DrawMapAnim_GetTotalDuration(proc->frames);
    proc->targetActorId = DrawMapAnim_GetTargetActorId();
    proc->loadedFrame = 0xFF;

    DrawMapAnim_LoadNumbers();
}

static void DrawMapAnim_Loop(struct DrawMapAnimProc * proc)
{
    int elapsed = GetGameClock() - proc->startClock;
    const struct DrawMapAnimFrame * frame;
    int frameIndex;
    int stopFrame = proc->totalDuration;

    if (stopFrame < DRAW_MAP_ANIM_MIN_FRAMES)
        stopFrame = DRAW_MAP_ANIM_MIN_FRAMES;

    if (!(gManimSt.hitAttributes & BATTLE_HIT_ATTR_MISS))
        DrawMapAnim_PutDamageNumber(proc);

    frame = DrawMapAnim_GetFrameForTime(proc->frames, elapsed);

    if (frame)
    {
        frameIndex = frame - proc->frames;

        if (proc->loadedFrame != frameIndex)
        {
            proc->loadedFrame = frameIndex;

            if (frame->sfx != 0)
                PlaySoundEffect(frame->sfx);

            DrawMapAnim_LoadFrameGfx(frame);
        }

        DrawMapAnim_PutFrameSprite(proc);
    }

    if (elapsed >= stopFrame && gManimSt.hp_changing == false)
        Proc_Break(proc);
}

static void DrawMapAnim_Cleanup(struct DrawMapAnimProc * proc)
{
    RegisterFillTile(0, OBJ_CHR_ADDR(DRAW_MAP_ANIM_OBJCHR), DRAW_MAP_ANIM_VRAM_SIZE);
    ClearTileRigistry();
}

CONST_DATA struct ProcCmd ProcScr_DrawMapAnimSprite[] = {
    PROC_CALL(DrawMapAnim_Init),
    PROC_REPEAT(DrawMapAnim_Loop),
    PROC_CALL(DrawMapAnim_Cleanup),
    PROC_END
};

void DrawMapAnim_RoundCleanup(ProcPtr proc)
{
    EnablePaletteSync();
}

CONST_DATA struct ProcCmd ProcScr_DrawMapAnimDefaultItemEffect[] = {
    PROC_CALL(MapAnim_BeginSubjectFastAnim),
    PROC_CALL(MapAnim_MoveSubjectsTowardsTarget),
    PROC_SLEEP(0x1),
    PROC_CALL(MapAnim_MoveSubjectsTowardsTarget),
    PROC_SLEEP(0x1),
    PROC_CALL(MapAnim_MoveSubjectsTowardsTarget),
    PROC_SLEEP(0x1),
    PROC_CALL(MapAnim_MoveSubjectsTowardsTarget),
    PROC_SLEEP(0x1),
    PROC_CALL(MapAnim_MoveCameraOnTarget),
    PROC_SLEEP(0x2),
    PROC_CALL(MapAnim_BeginRoundSpecificAnims),
    PROC_START_CHILD(ProcScr_DrawMapAnimSprite),
    PROC_YIELD,
    PROC_CALL(MapAnim_MoveSubjectsAwayFromTarget),
    PROC_SLEEP(0x1),
    PROC_CALL(MapAnim_MoveSubjectsAwayFromTarget),
    PROC_SLEEP(0x1),
    PROC_CALL(MapAnim_MoveSubjectsAwayFromTarget),
    PROC_SLEEP(0x1),
    PROC_CALL(MapAnim_MoveSubjectsAwayFromTarget),
    PROC_WHILE_EXISTS(ProcScr_DrawMapAnimSprite),
    PROC_CALL(DrawMapAnim_RoundCleanup),
    PROC_END
};

#endif /* FE8_DRAW_MAP_ANIMS */


