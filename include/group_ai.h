#ifndef GUARD_GROUP_AI_H
#define GUARD_GROUP_AI_H

#include "expansion_config.h"

struct Unit;

#if FE8_GROUP_AI
/* Called once after a completed attack action (ActionCombat, src/bmmind.c).
 * If either combatant is group-tagged (see AI_UNIT_CONFIG_GROUPID_MASK,
 * include/cp_common.h) and neither is an NPC, every enemy unit sharing that
 * group id has its tag cleared, its AI2 forced to AI_B_00 (Charge), and is
 * queued to act again this enemy phase. See src/group_ai.c. */
void GroupAI_OnAttack(struct Unit* attacker, struct Unit* defender);
#endif

#endif /* GUARD_GROUP_AI_H */
