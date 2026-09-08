#ifndef GUARD_COSELECT_H
#define GUARD_COSELECT_H

#include "proc.h"

#if FE8_CO_POWERS

/* CO select screen -- a copy of the Mode Select carousel (src/modeselect.c)
 * that picks a faction's commander instead of a lord/difficulty. Called as an
 * ASMC from an event script, so it runs on the live battle map:
 *
 *     SVAL(EVT_SLOT_1, <bitfield of enabled CO ids, 0 = all>)
 *     SVAL(EVT_SLOT_3, <faction>)
 *     ASMC(StartCoSelect)
 *
 * Blocks the event proc until the player confirms with A/START, which commits
 * the highlighted CO through SetFactionCo (src/power.c). See src/coSelect.c.
 */
void StartCoSelect(ProcPtr parent);

#endif // FE8_CO_POWERS

#endif // GUARD_COSELECT_H
