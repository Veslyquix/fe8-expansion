#ifndef GUARD_TURN_AUTOSAVE_H
#define GUARD_TURN_AUTOSAVE_H

#include "expansion_config.h"

#if FE8_TURN_AUTOSAVE
/* Called from BmMain_SuspendBeforePhase (src/bm.c) in place of vanilla's
 * unconditional per-phase-change suspend write. Only writes while
 * transitioning into Player Phase. The first Player Phase of each chapter
 * establishes an alive-unit baseline and saves; later Player Phases save
 * unless a player unit that was alive at the previous Player Phase start
 * has died or become unavailable since then. */
void TurnAutosave_TryWriteSuspend(void);
void TurnAutosave_OnBlueUnitKilled(void);
#endif

#endif /* GUARD_TURN_AUTOSAVE_H */
