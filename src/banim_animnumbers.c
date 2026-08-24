#include "global.h"
#include "anime.h"
#include "banim_animnumbers.h"
#include "bmbattle.h"
#include "ekrbattle.h"
#include "eventinfo.h"
#include "hardware.h"
#include "proc.h"

#if FE8_BATTLE_ANIMATION_NUMBERS

#define ANIM_NUMBERS_DIGIT_TILE_BASE 0x102
#define ANIM_NUMBERS_SIGN_TILE_BASE 0x120
#define ANIM_NUMBERS_SIDE_TILE_STRIDE 0x10
#define ANIM_NUMBERS_DIGIT_TILE_SIZE 0x40
#define ANIM_NUMBERS_DIGIT_ROW_STRIDE 0x400
#define ANIM_NUMBERS_MAX_DIGITS 5

struct ProcAnimNumbersDelayDigits
{
    PROC_HEADER;

    /* 29 */ u8 digitCount;
    /* 2A */ s16 value;
    /* 2C */ u8 animPosition;
};

extern AnimScr * CONST_DATA gAnimNumbersDigitsAnimScrs[];

void AnimNumbers_LoadDigits(struct ProcAnimNumbersDelayDigits * proc);
void AnimNumbers_LoadMissNoDamageGfx(ProcPtr proc);

static const u32 sAnimNumbersZeroTop[] = {
    0x00000000, 0x00000000, 0x00000000, 0x88800000,
    0xAAD88000, 0x8DD1D800, 0x08111800, 0x08111D80,
    0x00000000, 0x00000000, 0x00000000, 0x00000888,
    0x00088DAA, 0x008D1DD8, 0x00811180, 0x08D11180,
};

static const u32 sAnimNumbersZeroBottom[] = {
    0x08BBBB80, 0x08BBBB80, 0x08AAAD80, 0x08AAA800,
    0x8DAAD800, 0x11D88000, 0x88800000, 0x00000000,
    0x08BBBB80, 0x08BBBB80, 0x08DAAA80, 0x008AAA80,
    0x008DAAD8, 0x00088D11, 0x00000888, 0x00000000,
};

static const u16 sAnimNumbersPalettes[] = {
    0x001F, 0x7BDE, 0x0000, 0x57D3, 0x0000, 0x0000, 0x0000, 0x0000,
    0x14A5, 0x0000, 0x57D3, 0x6BD8, 0x0000, 0x27CB, 0x0000, 0x0000,
    0x03E0, 0x7BDE, 0x0000, 0x567E, 0x0000, 0x0000, 0x0000, 0x0000,
    0x14A5, 0x0000, 0x567E, 0x6B1E, 0x0000, 0x257E, 0x0000, 0x0000,
};

CONST_DATA struct ProcCmd ProcScr_AnimNumbersDelayDigits[] = {
    PROC_SLEEP(1),
    PROC_CALL(AnimNumbers_LoadDigits),
    PROC_END,
};

CONST_DATA struct ProcCmd ProcScr_AnimNumbersDelayMissNoDamageGfx[] = {
    PROC_SLEEP(1),
    PROC_CALL(AnimNumbers_LoadMissNoDamageGfx),
    PROC_END,
};

static int AnimNumbers_Abs(int value)
{
    if (value < 0)
        return -value;

    return value;
}

static int AnimNumbers_GetDigitCount(int value)
{
    int count = 1;

    value = AnimNumbers_Abs(value);

    while (value >= 10 && count < ANIM_NUMBERS_MAX_DIGITS)
    {
        value /= 10;
        count++;
    }

    return count;
}

static int AnimNumbers_GetRoundIndex(struct Anim * anim)
{
    int round = anim->nextRoundId;
    struct Anim * other = GetAnimAnotherSide(anim);

    if (other->nextRoundId > round)
        round = other->nextRoundId;

    if (round <= 0)
        return 0;

    return round - 1;
}

static int AnimNumbers_GetAttackerPosition(const struct BattleHit * hit)
{
    bool isEnemy = (hit->info & BATTLE_HIT_INFO_RETALIATION) != 0;

    if (gBanimPositionIsEnemy[EKR_POS_L] == isEnemy)
        return EKR_POS_L;

    return EKR_POS_R;
}

static int AnimNumbers_GetLutValue(int round, int position)
{
    int value = GetEfxHp(round * 2 + position);

    if (value == 0xFFFF)
        return -1;

    return value;
}

static int AnimNumbers_GetHpChangeFromLut(int round, int position)
{
    int before = AnimNumbers_GetLutValue(round, position);
    int after = AnimNumbers_GetLutValue(round + 1, position);

    if (before < 0 || after < 0)
        return 0;

    return after - before;
}

static int AnimNumbers_GetCappedDisplayValue(int position)
{
    return AnimNumbers_GetHpChangeFromLut(gEfxHpLutOff[position], position);
}

static int AnimNumbers_GetUncappedDisplayValue(const struct BattleHit * hit, int position)
{
    int attacker;
    int target;
    int value = hit->hpChange;

    if (value == 0)
        return 0;

    attacker = AnimNumbers_GetAttackerPosition(hit);

    if (hit->attributes & BATTLE_HIT_ATTR_DEVIL)
        target = attacker;
    else
        target = attacker ^ 1;

    if (hit->attributes & BATTLE_HIT_ATTR_HPSTEAL)
    {
        if (position == attacker)
            return value;

        if (position == target)
            return -value;

        return 0;
    }

    if (position != target)
        return 0;

    return -value;
}

static int AnimNumbers_GetDisplayValue(struct Anim * anim, bool useCappedValue)
{
    int position = GetAnimPosition(anim);
    int round = AnimNumbers_GetRoundIndex(anim);
    const struct BattleHit * hit = gBattleHitArray + round;
    int value;

    if (hit->info & BATTLE_HIT_INFO_END)
        return 0;

    if (hit->attributes & BATTLE_HIT_ATTR_MISS)
        return 0;

    value = AnimNumbers_GetUncappedDisplayValue(hit, position);
    if (value == 0)
        return 0;

    if (useCappedValue)
        return AnimNumbers_GetCappedDisplayValue(position);

    return value;
}

static int AnimNumbers_GetYOffset(struct Anim * anim, int digitCount, int previousX, int previousDigitCount)
{
    int x0;
    int x1;
    int d0;
    int d1;
    int rightEdge;
    int leftEdge;

    if (previousDigitCount == 0)
        return 0x28;

    x0 = anim->xPosition;
    x1 = previousX;
    d0 = digitCount;
    d1 = previousDigitCount;

    if (x1 < x0)
    {
        int tmp;

        tmp = x0;
        x0 = x1;
        x1 = tmp;

        tmp = d0;
        d0 = d1;
        d1 = tmp;
    }

    rightEdge = x0 + d0 * 8 + 4;
    leftEdge = x1 - (d1 * 8 + 4);

    if (AnimNumbers_Abs(leftEdge - rightEdge) <= 8)
        return 0x38;

    return 0x28;
}

static void AnimNumbers_CopyDigit(int digit, u8 * dst)
{
    u8 * img = (u8 *)Img_EkrLvupNumBig;
    int index = digit - 1;

    if (digit == 0)
    {
        CpuFastCopy(sAnimNumbersZeroTop, dst, ANIM_NUMBERS_DIGIT_TILE_SIZE);
        CpuFastCopy(sAnimNumbersZeroBottom, dst + ANIM_NUMBERS_DIGIT_ROW_STRIDE, ANIM_NUMBERS_DIGIT_TILE_SIZE);
        return;
    }

    CpuFastCopy(img + index * ANIM_NUMBERS_DIGIT_TILE_SIZE, dst, ANIM_NUMBERS_DIGIT_TILE_SIZE);
    CpuFastCopy(
        img + index * ANIM_NUMBERS_DIGIT_TILE_SIZE + ANIM_NUMBERS_DIGIT_ROW_STRIDE,
        dst + ANIM_NUMBERS_DIGIT_ROW_STRIDE,
        ANIM_NUMBERS_DIGIT_TILE_SIZE);
}

void AnimNumbers_LoadDigits(struct ProcAnimNumbersDelayDigits * proc)
{
    int value = proc->value;
    int absValue = AnimNumbers_Abs(value);
    int denom;
    int i;
    u8 * img = (u8 *)Img_EkrLvupNumBig;
    u8 * digitDst = OBJ_VRAM0 + (ANIM_NUMBERS_DIGIT_TILE_BASE + proc->animPosition * ANIM_NUMBERS_SIDE_TILE_STRIDE) * CHR_SIZE;
    u8 * signDst = OBJ_VRAM0 + (ANIM_NUMBERS_SIGN_TILE_BASE + proc->animPosition * ANIM_NUMBERS_SIDE_TILE_STRIDE) * CHR_SIZE;

    if (value > 0)
    {
        CopyToPaletteBuffer(sAnimNumbersPalettes, 0x2A0 + (1 - proc->animPosition) * 0x20, 0x20);
        CpuFastCopy(img + 0x1C * ANIM_NUMBERS_DIGIT_TILE_SIZE, signDst, CHR_SIZE);
    }
    else
    {
        CopyToPaletteBuffer(sAnimNumbersPalettes + 0x10, 0x2A0 + (1 - proc->animPosition) * 0x20, 0x20);
        CpuFastCopy(img + 0x1D * ANIM_NUMBERS_DIGIT_TILE_SIZE, signDst, CHR_SIZE);
    }

    EnablePaletteSync();

    denom = 1;
    for (i = 1; i < proc->digitCount; i++)
        denom *= 10;

    for (i = 0; i < proc->digitCount; i++)
    {
        int digit = absValue / denom;

        absValue -= digit * denom;
        AnimNumbers_CopyDigit(digit, digitDst + i * 2 * CHR_SIZE);

        denom /= 10;
    }

}

void AnimNumbers_LoadMissNoDamageGfx(ProcPtr proc)
{
    LZ77UnCompVram(Img_NODAMGEMIS, OBJ_VRAM0 + 0x2000);
}

void AnimNumbers_StartDelayedMissNoDamageGfx(void)
{
    Proc_Start(ProcScr_AnimNumbersDelayMissNoDamageGfx, PROC_TREE_3);
}

void AnimNumbers_ReloadMissNoDamagePalette(struct Anim * anim)
{
    int position = GetAnimPosition(anim);

    CpuFastCopy(gBanimmisc_8 + position * 0x10, PAL_OBJ(5 + (1 - position)), 0x20);
    EnablePaletteSync();
}

int AnimNumbers_DisplayDamage(struct Anim * anim, bool useCappedValue, int previousX, int previousDigitCount)
{
    int value;
    int digitCount;
    int position;
    int pal;
    int oam2;
    int yOffset;
    struct ProcAnimNumbersDelayDigits * proc;
    struct ProcEkrSubAnimeEmulator * subProc;
    struct ProcEfxDamageMojiEffectOBJ * objProc;

    if (CheckFlag(BATTLE_ANIMATION_NUMBERS_FLAG))
        return 0;

    value = AnimNumbers_GetDisplayValue(anim, useCappedValue);
    if (value == 0)
        return 0;

    digitCount = AnimNumbers_GetDigitCount(value);
    position = GetAnimPosition(anim);
    pal = 5 + (1 - position);
    oam2 = (pal << 12) | 0x100 | (position << 4);
    yOffset = AnimNumbers_GetYOffset(anim, digitCount, previousX, previousDigitCount);

    proc = Proc_Start(ProcScr_AnimNumbersDelayDigits, PROC_TREE_3);
    proc->digitCount = digitCount;
    proc->value = value;
    proc->animPosition = position;

    subProc = NewEkrsubAnimeEmulator(
        anim->xPosition,
        anim->yPosition - yOffset,
        gAnimNumbersDigitsAnimScrs[digitCount - 1],
        2,
        oam2,
        0,
        PROC_TREE_3);

    objProc = Proc_Start(ProcScr_efxDamageMojiEffectOBJ, PROC_TREE_3);
    objProc->anim = anim;
    objProc->timer = 0;
    objProc->terminator = 0x32;
    objProc->sub_proc = subProc;

    return digitCount;
}

void AnimNumbers_DisplayAttack(struct Anim * anim)
{
    int digitCount = AnimNumbers_DisplayDamage(anim, false, 0, 0);

    AnimNumbers_DisplayDamage(GetAnimAnotherSide(anim), true, anim->xPosition, digitCount);
}

void AnimNumbers_DisplayHeal(struct Anim * anim)
{
    int digitCount = AnimNumbers_DisplayDamage(anim, false, 0, 0);

    AnimNumbers_DisplayDamage(GetAnimAnotherSide(anim), true, anim->xPosition, digitCount);
}

void AnimNumbers_DisplayNosferatuHeal(struct Anim * anim)
{
    AnimNumbers_DisplayDamage(anim, true, 0, 0);
}

void AnimNumbers_EndDamageMojiSubProc(struct ProcEfxDamageMojiEffectOBJ * proc)
{
    if (proc->sub_proc != NULL)
    {
        Proc_End(proc->sub_proc);
        proc->sub_proc = NULL;
    }
}

void AnimNumbers_KillDigits(void)
{
    struct ProcEfxDamageMojiEffectOBJ * proc;

    while ((proc = Proc_Find(ProcScr_efxDamageMojiEffectOBJ)) != NULL)
    {
        AnimNumbers_EndDamageMojiSubProc(proc);
        Proc_End(proc);
    }
}

#endif /* FE8_BATTLE_ANIMATION_NUMBERS */
