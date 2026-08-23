#include "global.h"

#ifdef DEBUFFS_EXIST

#include "constants/items.h"
#include "id_space.h"

#include "bmbattle.h"
#include "bmitem.h"
#include "bmunit.h"
#include "debuffs.h"

#define UNIT_DEBUFF_PACKED_BYTE_COUNT 6

/* Per-stat debuff for one weapon: `percent` is applied to the unit's raw
 * (undebuffed) stat first (e.g. -20 = reduce by 20% of that stat, rounded
 * down but never to a no-op if the stat is positive -- matches
 * UnitAddPercentDebuff's existing "round up to at least 1" rule), then
 * `flat` is subtracted from that result (e.g. -5 = 5 more off). Both are
 * plain signed deltas, same sign convention as UnitAddDebuff/UnitSetDebuff
 * (negative = debuff). A stat left at {0, 0} isn't touched at all.
 *
 * Example: 10 Str, percent=-20, flat=-5 -> 10 - (10*20/100) - 5 = 3. */
struct WeaponDebuffStat {
    s8 percent;
    s8 flat;
};

/* One entry per debuffable stat (see enum udef_debuff_stat, bmunit.h). */
struct WeaponDebuffEntry {
    struct WeaponDebuffStat pow;
    struct WeaponDebuffStat skl;
    struct WeaponDebuffStat spd;
    struct WeaponDebuffStat def;
    struct WeaponDebuffStat res;
    struct WeaponDebuffStat lck;
    struct WeaponDebuffStat mov;
};

/* Indexed directly by item id (not scanned) -- gWeaponDebuffTable[item] is
 * the weapon's debuff entry, or an all-zero (no-op) entry for any item that
 * doesn't debuff on hit. Sized to the build's configured item id cap
 * (id_space.h) so every valid item id is always a safe, in-bounds index. */
CONST_DATA struct WeaponDebuffEntry gWeaponDebuffTable[ITEM_ID_CONFIGURED_CAP] = {
    [ITEM_LANCE_SLIM] = {
        .pow = { .percent = -20 },
        .skl = { .percent = -20 },
        .spd = { .percent = -20 },
        .def = { .percent = -20 },
        .res = { .percent = -20 },
        .lck = { .percent = -20 },
        .mov = { .percent = -20 },
    },
};

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

static const struct WeaponDebuffEntry * GetWeaponDebuffEntry(int item)
{
    int itemIndex = GetItemIndex(item);

    if (itemIndex <= 0 || itemIndex >= (int)ARRAY_COUNT(gWeaponDebuffTable))
        return NULL;

    return &gWeaponDebuffTable[itemIndex];
}

static const struct WeaponDebuffStat * GetWeaponDebuffStatEntry(const struct WeaponDebuffEntry *entry, int stat)
{
    switch (stat) {
    case UNIT_DEBUFF_STAT_POW: return &entry->pow;
    case UNIT_DEBUFF_STAT_SKL: return &entry->skl;
    case UNIT_DEBUFF_STAT_SPD: return &entry->spd;
    case UNIT_DEBUFF_STAT_DEF: return &entry->def;
    case UNIT_DEBUFF_STAT_RES: return &entry->res;
    case UNIT_DEBUFF_STAT_LCK: return &entry->lck;
    case UNIT_DEBUFF_STAT_MOV: return &entry->mov;
    }

    return NULL;
}

/* Percent first, then flat -- see struct WeaponDebuffStat's comment. */
static void ApplyWeaponDebuffStat(struct Unit *unit, int stat, const struct WeaponDebuffStat *statEntry)
{
    int raw;
    int percentAmount;

    if (!statEntry || (statEntry->percent == 0 && statEntry->flat == 0))
        return;

    percentAmount = 0;

    if (statEntry->percent != 0) {
        raw = GetRawStatForDebuff(unit, stat);
        percentAmount = (raw * AbsInt(statEntry->percent)) / 100;

        if (raw > 0 && percentAmount == 0)
            percentAmount = 1;

        if (statEntry->percent < 0)
            percentAmount = -percentAmount;
    }

    UnitAddDebuff(unit, stat, percentAmount + statEntry->flat);
}

void BattleApplyWeaponDebuff(struct BattleUnit *attacker, struct BattleUnit *defender)
{
    int item;

    if (!(gBattleStats.config & BATTLE_CONFIG_REAL))
        return;

    if (!attacker || !defender)
        return;

    item = GetItemIndex(attacker->weaponBefore);

    if (!GetWeaponDebuffEntry(item))
        return;

    if (!UNIT_IS_VALID(&defender->unit))
        return;

    defender->pendingDebuffItem = item;
    defender->pendingDebuffHits++;
}

void BattleApplyUnitDebuffs(struct Unit *unit, struct BattleUnit *bu)
{
    int i;
    const struct WeaponDebuffEntry *entry;

    if (!unit || !bu || !UNIT_IS_VALID(unit) || unit->curHP == 0)
        return;

    if (bu->pendingDebuffHits <= 0)
        return;

    entry = GetWeaponDebuffEntry(bu->pendingDebuffItem);

    if (!entry)
        return;

    for (i = 0; i < bu->pendingDebuffHits; ++i) {
        ApplyWeaponDebuffStat(unit, UNIT_DEBUFF_STAT_POW, GetWeaponDebuffStatEntry(entry, UNIT_DEBUFF_STAT_POW));
        ApplyWeaponDebuffStat(unit, UNIT_DEBUFF_STAT_SKL, GetWeaponDebuffStatEntry(entry, UNIT_DEBUFF_STAT_SKL));
        ApplyWeaponDebuffStat(unit, UNIT_DEBUFF_STAT_SPD, GetWeaponDebuffStatEntry(entry, UNIT_DEBUFF_STAT_SPD));
        ApplyWeaponDebuffStat(unit, UNIT_DEBUFF_STAT_DEF, GetWeaponDebuffStatEntry(entry, UNIT_DEBUFF_STAT_DEF));
        ApplyWeaponDebuffStat(unit, UNIT_DEBUFF_STAT_RES, GetWeaponDebuffStatEntry(entry, UNIT_DEBUFF_STAT_RES));
        ApplyWeaponDebuffStat(unit, UNIT_DEBUFF_STAT_LCK, GetWeaponDebuffStatEntry(entry, UNIT_DEBUFF_STAT_LCK));
        ApplyWeaponDebuffStat(unit, UNIT_DEBUFF_STAT_MOV, GetWeaponDebuffStatEntry(entry, UNIT_DEBUFF_STAT_MOV));
    }
}

#endif /* DEBUFFS_EXIST */
