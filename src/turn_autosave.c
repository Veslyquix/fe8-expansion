#include "global.h"
#include "turn_autosave.h"

#if FE8_TURN_AUTOSAVE

#include "bmsave.h"
#include "bmunit.h"
#include "variables.h"

/* Player army unit-index span (see GetUnit/gUnitLookup, src/bmunit.c). */
#define TURN_AUTOSAVE_UNIT_SLOT_MAX 0x3F

static EWRAM_DATA u32 sTurnAutosaveAliveMaskLo = 0;
static EWRAM_DATA u32 sTurnAutosaveAliveMaskHi = 0;
static EWRAM_DATA bool8 sTurnAutosaveHasBaseline = false;
static EWRAM_DATA u8 sTurnAutosaveBaselineChapter = 0;
static EWRAM_DATA bool8 sTurnAutosaveBlueDeathSincePlayerPhase = false;

static bool8 TurnAutosave_IsAliveDeployedBlueUnit(struct Unit* unit)
{
    if (!unit || !unit->pCharacterData)
        return false;

    /* Dead, never deployed, or the unmapped high bit vanilla also excludes
     * here -- see US_UNAVAILABLE, include/bmunit.h. */
    if (unit->state & (US_UNAVAILABLE | US_BIT26))
        return false;

    return true;
}

static void TurnAutosave_BuildAliveMask(u32* loOut, u32* hiOut)
{
    int i;
    u32 lo = 0;
    u32 hi = 0;

    for (i = 1; i <= TURN_AUTOSAVE_UNIT_SLOT_MAX; i++)
    {
        int bit = i - 1;

        if (!TurnAutosave_IsAliveDeployedBlueUnit(GetUnit(i)))
            continue;

        if (bit < 32)
            lo |= 1u << bit;
        else
            hi |= 1u << (bit - 32);
    }

    *loOut = lo;
    *hiOut = hi;
}

static bool8 TurnAutosave_BaselineLostUnit(u32 currentLo, u32 currentHi)
{
    if ((sTurnAutosaveAliveMaskLo & ~currentLo) != 0)
        return true;

    if ((sTurnAutosaveAliveMaskHi & ~currentHi) != 0)
        return true;

    return false;
}

void TurnAutosave_OnBlueUnitKilled(void)
{
    sTurnAutosaveBlueDeathSincePlayerPhase = true;
}

static void TurnAutosave_SetBaseline(u32 currentLo, u32 currentHi)
{
    sTurnAutosaveAliveMaskLo = currentLo;
    sTurnAutosaveAliveMaskHi = currentHi;
    sTurnAutosaveHasBaseline = true;
    sTurnAutosaveBaselineChapter = gPlaySt.chapterIndex;
}

void TurnAutosave_TryWriteSuspend(void)
{
    u32 currentLo;
    u32 currentHi;

    /* gPlaySt.faction == FACTION_BLUE only while transitioning into
     * Player Phase -- every other phase change is left alone. */
    if (gPlaySt.faction != FACTION_BLUE)
        return;

    TurnAutosave_BuildAliveMask(&currentLo, &currentHi);

    if (sTurnAutosaveBlueDeathSincePlayerPhase
        || (sTurnAutosaveHasBaseline && sTurnAutosaveBaselineChapter == gPlaySt.chapterIndex
            && TurnAutosave_BaselineLostUnit(currentLo, currentHi)))
    {
        TurnAutosave_SetBaseline(currentLo, currentHi);
        sTurnAutosaveBlueDeathSincePlayerPhase = false;
        return;
    }

    TurnAutosave_SetBaseline(currentLo, currentHi);
    sTurnAutosaveBlueDeathSincePlayerPhase = false;

    gActionData.suspendPointType = SUSPEND_POINT_PHASECHANGE;
    WriteSuspendSave(SAVE_ID_SUSPEND);
}

#endif /* FE8_TURN_AUTOSAVE */
