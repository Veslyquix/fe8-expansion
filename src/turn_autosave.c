#include "global.h"
#include "turn_autosave.h"

#if FE8_TURN_AUTOSAVE

#include "bmsave.h"
#include "bmunit.h"
#include "variables.h"

/* How many further Player Phase starts to wait, after the alive/deployed
 * headcount drops, before accepting the new (lower) count as the baseline
 * and resuming writes. */
#define TURN_AUTOSAVE_DEBOUNCE_TURNS 2

/* Player army unit-index span (see GetUnit/gUnitLookup, src/bmunit.c) --
 * generous on purpose so a future roster expansion can't silently
 * undercount without anyone noticing. */
#define TURN_AUTOSAVE_UNIT_SLOT_MAX 0x3F

/* No real deployment gets anywhere near this; caps the scan below rather
 * than let it run needlessly long. */
#define TURN_AUTOSAVE_COUNT_CAP 50

static EWRAM_DATA u8 sTurnAutosaveLastAliveCount = 0;
static EWRAM_DATA u8 sTurnAutosaveTurnsSinceMismatch = 0;

static int TurnAutosave_CountAliveDeployedUnits(void) {
    int count = 0;
    int i;

    for (i = 1; i <= TURN_AUTOSAVE_UNIT_SLOT_MAX; i++) {
        struct Unit* unit = GetUnit(i);

        if (!unit || !unit->pCharacterData)
            continue;

        /* Dead, never deployed, or the unmapped high bit vanilla also
         * excludes here -- see US_UNAVAILABLE, include/bmunit.h. */
        if (unit->state & (US_UNAVAILABLE | US_BIT26))
            continue;

        count++;
        if (count >= TURN_AUTOSAVE_COUNT_CAP)
            break;
    }

    return count;
}

void TurnAutosave_TryWriteSuspend(void) {
    int aliveCount;

    /* gPlaySt.faction == FACTION_BLUE only while transitioning into
     * Player Phase -- every other phase change is left alone. */
    if (gPlaySt.faction != FACTION_BLUE)
        return;

    aliveCount = TurnAutosave_CountAliveDeployedUnits();

    if (aliveCount == sTurnAutosaveLastAliveCount) {
        sTurnAutosaveLastAliveCount = (u8)aliveCount;
        sTurnAutosaveTurnsSinceMismatch = 0;
    } else if (sTurnAutosaveTurnsSinceMismatch >= TURN_AUTOSAVE_DEBOUNCE_TURNS) {
        sTurnAutosaveLastAliveCount = (u8)aliveCount;
        sTurnAutosaveTurnsSinceMismatch = 0;
    } else {
        sTurnAutosaveTurnsSinceMismatch++;
        return;
    }

    gActionData.suspendPointType = SUSPEND_POINT_PHASECHANGE;
    WriteSuspendSave(SAVE_ID_SUSPEND);
}

#endif /* FE8_TURN_AUTOSAVE */
