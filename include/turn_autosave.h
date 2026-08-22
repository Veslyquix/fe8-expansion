#ifndef GUARD_TURN_AUTOSAVE_H
#define GUARD_TURN_AUTOSAVE_H

#include "expansion_config.h"

#if FE8_TURN_AUTOSAVE
/* Called from BmMain_SuspendBeforePhase (src/bm.c) in place of vanilla's
 * unconditional per-phase-change suspend write. Only ever writes while
 * transitioning into Player Phase, and only when the number of alive,
 * deployed player units hasn't dropped since the last successful write.
 * If it has (someone died), the write is withheld for
 * TURN_AUTOSAVE_DEBOUNCE_TURNS further Player Phase starts before the new
 * (lower) headcount is accepted as the new baseline and writing resumes --
 * so a death doesn't get silently autosaved over before the player has a
 * chance to notice and reload if they want to. */
void TurnAutosave_TryWriteSuspend(void);
#endif

#endif /* GUARD_TURN_AUTOSAVE_H */
