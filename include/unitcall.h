#ifndef GUARD_UNITCALL_H
#define GUARD_UNITCALL_H

#include "uimenu.h"

#if FE8_SKILLSYSTEM

// Only this class can use the Call command.
#define UNIT_CALL_CLASS CLASS_HORN_BRIGAND

// Max distance tiles a unit can be called from.
#define UNIT_CALL_RANGE 6

// Move-unit procs the convergence proc drives itself. The calling unit's
// own MU proc is treated as a permanently reserved slot out of MU_MAX_COUNT
// (see include/mu.h), so only 3 are ever started here.
#define UNIT_CALL_MAX_CONCURRENT 3

// Largest number of allied units the convergence proc can track at once.
#define UNIT_CALL_MAX_TARGETS 16

// Per-walker movement script buffer size. UNIT_MOV_MAX(aUnit) is a hard 15
// tile-move cap (include/bmunit.h), so 15 move commands + 1 halt always
// fits -- far short of MOVE_CMD_MAX_COUNT (0x40), which sizes the general
// purpose (but unrelated) gWorkingMovementScript buffer.
#define UNIT_CALL_SCRIPT_LEN 16

// Whether unit is allowed to use the Call command at all (character check
// plus the usual "hasn't acted" gate).
bool CanUnitCall(struct Unit* unit);

// Whether candidate is a valid Call target for caller: same faction,
// hasn't acted, an allowed class, and within UNIT_CALL_RANGE tiles.
bool IsUnitCallable(struct Unit* candidate, struct Unit* caller);

u8 CallCommandUsability(const struct MenuItemDef* def, int number);
u8 CallCommandEffect(struct MenuProc* menu, struct MenuItemProc* menuItem);

// UNIT_ACTION_CALL handler, dispatched from ApplyUnitAction (src/bmmind.c).
s8 ActionCall(ProcPtr proc);

// Builds the eligible-target list for caller and kicks off the
// fire-and-forget convergence proc that walks them toward caller. Used both
// by ActionCall (player) and AiCallAction (src/cp_perform.c, AI).
void StartUnitCallConvergence(struct Unit* caller);

// Lets the AI decide to Call instead of attacking, called from the top of
// AiAttemptOffensiveAction (src/cp_battle.c). Returns true (and commits an
// AI_ACTION_CALL decision) iff gActiveUnit can Call and has at least one
// eligible ally in range.
bool AiTryDoCall(void);

#endif // FE8_SKILLSYSTEM

#endif // GUARD_UNITCALL_H
