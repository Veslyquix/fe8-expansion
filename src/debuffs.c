#include "global.h"

#ifdef DEBUFFS_EXIST

#include "constants/items.h"

#include "bmbattle.h"
#include "bmitem.h"
#include "bmunit.h"
#include "debuffs.h"

#define UNIT_DEBUFF_PACKED_BYTE_COUNT 6

static int ClampDebuff(int value)
{
    if (value > UNIT_DEBUFF_MAX)
        return UNIT_DEBUFF_MAX;

    if (value < UNIT_DEBUFF_MIN)
        return UNIT_DEBUFF_MIN;

    return value;
}

static int AbsInt(int value)
{
    return value < 0 ? -value : value;
}

static u8 UnitGetDebuffPackedByte(struct Unit *unit, int byte)
{
    if (byte < 4)
        return unit->debuffs[byte];

    return byte == 4 ? unit->_u3B : unit->_u47;
}

static void UnitSetDebuffPackedByte(struct Unit *unit, int byte, u8 value)
{
    if (byte < 4)
        unit->debuffs[byte] = value;
    else
        *(byte == 4 ? &unit->_u3B : &unit->_u47) = value;
}

static int GetRawStatForDebuff(struct Unit *unit, int stat)
{
    switch (stat) {
    case UNIT_DEBUFF_STAT_POW:
        return unit->pow;

    case UNIT_DEBUFF_STAT_SKL:
        return unit->skl;

    case UNIT_DEBUFF_STAT_SPD:
        return unit->spd;

    case UNIT_DEBUFF_STAT_DEF:
        return unit->def;

    case UNIT_DEBUFF_STAT_RES:
        return unit->res;

    case UNIT_DEBUFF_STAT_LCK:
        return unit->lck;

    case UNIT_DEBUFF_STAT_MOV:
        return UNIT_MOV_BASE(unit) + unit->movBonus;
    }

    return 0;
}

int UnitGetDebuff(struct Unit *unit, int stat)
{
    int bit;
    int byte;
    int shift;
    int raw;

    if (!unit || stat < 0 || stat >= UNIT_DEBUFF_STAT_COUNT)
        return 0;

    bit = stat * 6;
    byte = bit / 8;
    shift = bit & 7;

    raw = UnitGetDebuffPackedByte(unit, byte);
    if (byte + 1 < UNIT_DEBUFF_PACKED_BYTE_COUNT)
        raw |= UnitGetDebuffPackedByte(unit, byte + 1) << 8;

    raw = (raw >> shift) & 0x3F;

    if (raw & 0x20)
        raw -= 0x40;

    return raw;
}

void UnitSetDebuff(struct Unit *unit, int stat, int amount)
{
    int bit;
    int byte;
    int shift;
    int raw;

    if (!unit || stat < 0 || stat >= UNIT_DEBUFF_STAT_COUNT)
        return;

    amount = ClampDebuff(amount) & 0x3F;
    bit = stat * 6;
    byte = bit / 8;
    shift = bit & 7;

    raw = UnitGetDebuffPackedByte(unit, byte);
    if (byte + 1 < UNIT_DEBUFF_PACKED_BYTE_COUNT)
        raw |= UnitGetDebuffPackedByte(unit, byte + 1) << 8;

    raw &= ~(0x3F << shift);
    raw |= amount << shift;

    UnitSetDebuffPackedByte(unit, byte, raw & 0xFF);
    if (byte + 1 < UNIT_DEBUFF_PACKED_BYTE_COUNT)
        UnitSetDebuffPackedByte(unit, byte + 1, (raw >> 8) & 0xFF);
}

void UnitClearDebuffs(struct Unit *unit)
{
    int i;

    if (!unit)
        return;

    for (i = 0; i < UNIT_DEBUFF_STAT_COUNT; ++i) {
        if (UnitGetDebuff(unit, i) < 0)
            UnitSetDebuff(unit, i, 0);
    }
}

void UnitClearStatModifiers(struct Unit *unit)
{
    int i;

    if (!unit)
        return;

    for (i = 0; i < 4; ++i)
        unit->debuffs[i] = 0;

    unit->_u3B = 0;
    unit->_u47 = 0;
}

bool UnitHasDebuff(struct Unit *unit)
{
    int i;

    if (!unit)
        return false;

    for (i = 0; i < UNIT_DEBUFF_STAT_COUNT; ++i) {
        if (UnitGetDebuff(unit, i) < 0)
            return true;
    }

    return false;
}

int UnitApplyDebuffToStat(struct Unit *unit, int stat, int value)
{
    value += UnitGetDebuff(unit, stat);

    if (value < 0)
        return 0;

    return value;
}

void UnitAddDebuff(struct Unit *unit, int stat, int amount)
{
    int current;

    if (!unit || stat < 0 || stat >= UNIT_DEBUFF_STAT_COUNT || amount == 0)
        return;

    current = UnitGetDebuff(unit, stat);

#ifdef DEBUFFS_STACK
    current += amount;
#else
    if (amount < 0) {
        if (current > 0)
            current += amount;
        else if (current > amount)
            current = amount;
    } else {
        if (current < 0)
            current += amount;
        else if (current < amount)
            current = amount;
    }
#endif

    UnitSetDebuff(unit, stat, current);
    // brk; 
    // UnitSetDebuff(unit, stat, -1);
    // brk; 
}

void UnitAddPercentDebuff(struct Unit *unit, int stat, int percent)
{
    int raw;
    int amount;

    if (!unit || percent == 0)
        return;

    raw = GetRawStatForDebuff(unit, stat);
    amount = (raw * AbsInt(percent)) / 100;

    if (raw > 0 && amount == 0)
        amount = 1;

    if (percent < 0)
        amount = -amount;

    UnitAddDebuff(unit, stat, amount);
}

void UnitRestoreDebuffsTowardsNeutral(struct Unit *unit, int amount)
{
    int i;
    int value;

    if (!unit || amount <= 0)
        return;

    for (i = 0; i < UNIT_DEBUFF_STAT_COUNT; ++i) {
        value = UnitGetDebuff(unit, i);

        if (value < 0) {
            value += amount;

            if (value > 0)
                value = 0;
        } else if (value > 0) {
            value -= UNIT_BUFF_DEFAULT_DEPLETE_PER_TURN;

            if (value < 0)
                value = 0;
        }

        UnitSetDebuff(unit, i, value);
    }
}

void BattleApplyWeaponDebuff(struct BattleUnit *attacker, struct BattleUnit *defender)
{
    if (!(gBattleStats.config & BATTLE_CONFIG_REAL))
        return;

    if (!attacker || !defender)
        return;

    if (GetItemIndex(attacker->weaponBefore) != ITEM_LANCE_IRON)
        return;

    if (!UNIT_IS_VALID(&defender->unit))
        return;

    defender->pendingDebuffHits++;
}

void BattleApplyUnitDebuffs(struct Unit *unit, struct BattleUnit *bu)
{
    int i;

    if (!unit || !bu || !UNIT_IS_VALID(unit) || unit->curHP == 0)
        return;

    for (i = 0; i < bu->pendingDebuffHits; ++i) {
        UnitAddPercentDebuff(unit, UNIT_DEBUFF_STAT_POW, -20);
        UnitAddPercentDebuff(unit, UNIT_DEBUFF_STAT_SKL, -20);
        UnitAddPercentDebuff(unit, UNIT_DEBUFF_STAT_SPD, -20);
        UnitAddPercentDebuff(unit, UNIT_DEBUFF_STAT_DEF, -20);
        UnitAddPercentDebuff(unit, UNIT_DEBUFF_STAT_RES, -20);
        UnitAddPercentDebuff(unit, UNIT_DEBUFF_STAT_LCK, -20);
    }
}

#endif /* DEBUFFS_EXIST */
