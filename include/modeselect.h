#ifndef GUARD_MODESELECT_H
#define GUARD_MODESELECT_H

#include "proc.h"

#if FE8_MODE_SELECT
/* Starts the FE7-style "Mode Select" screen: a spinning Eirika/Ephraim/
 * Lyon carousel plus chapter-range and difficulty pickers. Wired in from
 * src/savemenu.c's PL_SAVEMENU_DIFFICULTY_SEL step in place of vanilla's
 * NewNewGameDifficultySelect. See src/modeselect.c. */
void StartModeSelect(ProcPtr parent);
#endif

#endif // GUARD_MODESELECT_H
