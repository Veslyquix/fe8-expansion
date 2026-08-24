#ifndef GUARD_DEBUFFS_H
#define GUARD_DEBUFFS_H

#include "global.h"

#ifdef DEBUFFS_EXIST

#include "bmunit.h"

struct BattleUnit;

#define UNIT_DEBUFF_MIN (-31)
#define UNIT_DEBUFF_MAX 31
#define UNIT_DEBUFF_DEFAULT_RESTORE_PER_TURN 2
#define UNIT_BUFF_DEFAULT_DEPLETE_PER_TURN 1

#define UNIT_DEBUFF_STAT_BIT(stat) (1 << (stat))
#define UNIT_DEBUFF_COMBAT_STAT_MASK \
    (UNIT_DEBUFF_STAT_BIT(UNIT_DEBUFF_STAT_POW) | UNIT_DEBUFF_STAT_BIT(UNIT_DEBUFF_STAT_SKL) | \
     UNIT_DEBUFF_STAT_BIT(UNIT_DEBUFF_STAT_SPD) | UNIT_DEBUFF_STAT_BIT(UNIT_DEBUFF_STAT_DEF) | \
     UNIT_DEBUFF_STAT_BIT(UNIT_DEBUFF_STAT_RES) | UNIT_DEBUFF_STAT_BIT(UNIT_DEBUFF_STAT_LCK))

void UnitClearDebuffs(struct Unit *unit);
void UnitClearStatModifiers(struct Unit *unit);
bool UnitHasDebuff(struct Unit *unit);
int UnitGetDebuff(struct Unit *unit, int stat);
int UnitApplyDebuffToStat(struct Unit *unit, int stat, int value);
void UnitSetDebuff(struct Unit *unit, int stat, int amount);
void UnitAddDebuff(struct Unit *unit, int stat, int amount);
void UnitAddPercentDebuff(struct Unit *unit, int stat, int percent);
void UnitRestoreDebuffsTowardsNeutral(struct Unit *unit, int amount);
void BattleApplyWeaponDebuff(struct BattleUnit *attacker, struct BattleUnit *defender);
void BattleApplyUnitDebuffs(struct Unit *unit, struct BattleUnit *bu);

#endif /* DEBUFFS_EXIST */

#endif /* GUARD_DEBUFFS_H */