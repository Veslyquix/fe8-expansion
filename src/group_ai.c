#include "global.h"
#include "group_ai.h"

#if FE8_GROUP_AI

#include "bmunit.h"
#include "cp_common.h"

/* Ported from Pokemblem's GroupAI.asm (patches/GroupAI). The reference
 * patch's attacker-side gate mask is 0x5F (group-id bits 0-4 plus bit 6 of
 * "ai4"), while the defender-side gate and the per-candidate group-id
 * compare both use 0x1F (group-id bits only) -- kept byte-for-byte as
 * written rather than "cleaned up": bit 6's purpose isn't documented in the
 * source patch, and if it's ever set on a real group-tagged unit the
 * asymmetry means the attacker path simply never matches any candidate
 * (candidates are always masked to group-id bits only), same as the
 * original. Not ported: the reference's separate AggroGroupAI_IfInDanger
 * (a danger-map-driven decision of whether a zoning AI should even
 * approach) -- out of scope per the porting request.
 */
#define GROUP_AI_ATTACKER_GATE_MASK (AI_UNIT_CONFIG_GROUPID_MASK | (1 << 14))
#define GROUP_AI_DEFENDER_GATE_MASK AI_UNIT_CONFIG_GROUPID_MASK

/* Queue a unit to act again this enemy phase -- the same mechanism vanilla
 * already uses for e.g. reinforcements that should move immediately (see
 * BuildAiUnitList, src/cp_order.c). gAiState.units[] is a NUL-terminated
 * list of unit indices; append while keeping it terminated. */
static void GroupAI_QueueExtraTurn(u8 unitIndex) {
    int i = 0;

    while (i < (int)sizeof(gAiState.units) - 1 && gAiState.units[i] != 0)
        i++;

    if (i < (int)sizeof(gAiState.units) - 1) {
        gAiState.units[i] = unitIndex;
        gAiState.units[i + 1] = 0;
    }
}

void GroupAI_OnAttack(struct Unit* attacker, struct Unit* defender) {
    u16 groupGate;
    int i;

    if (!attacker || !defender)
        return;

    if (UNIT_FACTION(attacker) == FACTION_GREEN || UNIT_FACTION(defender) == FACTION_GREEN)
        return;

    groupGate = attacker->ai_config & GROUP_AI_ATTACKER_GATE_MASK;
    if (groupGate == 0)
        groupGate = defender->ai_config & GROUP_AI_DEFENDER_GATE_MASK;
    if (groupGate == 0)
        return;

    for (i = FACTION_RED; i < FACTION_PURPLE; i++) {
        struct Unit* candidate = GetUnit(i);

        if (!candidate || !candidate->pCharacterData)
            continue;

        if ((candidate->ai_config & AI_UNIT_CONFIG_GROUPID_MASK) != groupGate)
            continue;

        candidate->ai_config &= ~AI_UNIT_CONFIG_GROUPID_MASK;
        candidate->ai2 = AI_B_00; /* Charge (MoveToEnemy) */

        GroupAI_QueueExtraTurn(candidate->index);
    }
}

#endif /* FE8_GROUP_AI */
