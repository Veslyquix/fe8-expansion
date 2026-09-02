
#include "global.h"

#include "proc.h"
#include "cp_data.h"
#include "cp_utility.h"

#include "cp_common.h"

#if FE8_CO_POWERS
#include "power.h"
#endif
#if FE8_AW2_ASSETS
#include "player_interface.h"
#include "uichapterstatus.h" // CountUnitsByFaction
#endif

#if FE8_VESLY_DEBUGGER
int ShouldAIControlRemainingUnits(void);
#endif

static void AiPhaseInit(struct Proc* proc);
static void AiPhaseBerserkInit(struct Proc* proc);
static void AiPhaseCleanup(struct Proc* proc);
#if FE8_CO_POWERS
static int AiPhaseCoPowersHook(struct Proc* proc);
#endif
static void AiOrderStart(struct Proc* proc);
#if FE8_AW2_ASSETS
static void AiPhaseGoalDisplayCleanup(struct Proc* proc);
#endif

EWRAM_DATA struct AiState gAiState = {0};

CONST_DATA
struct ProcCmd gProcScr_CpPhase[] =
{
    PROC_NAME("E_CPPHASE"),

    PROC_CALL(AiPhaseInit),
#if FE8_CO_POWERS
    /* Its own script step (not folded into AiPhaseInit above) so that if
     * CoPowers_OnAiPhaseStart decides to use a power, the roll-call/effect
     * proc it starts (gProcScr_CoPowers, see src/power.c) fully finishes --
     * camera pans, barrier animations, camera return -- before AiOrderStart
     * below spins up the faction's actual turn logic. A blocking child
     * only holds up ITS OWN parent's advancement past the step that
     * started it; two blocking children started from the very same step
     * would run concurrently as siblings instead of one after the other,
     * which is why this needs its own step rather than sharing
     * AiPhaseInit's. */
    PROC_CALL_2(AiPhaseCoPowersHook),
#endif
    PROC_CALL(AiOrderStart),
    PROC_YIELD,

#if FE8_AW2_ASSETS
    /* Not folded into AiPhaseCleanup below -- that function is shared with
     * gProcScr_BerserkCpPhase, which can interrupt an ongoing PLAYER phase
     * (a unit going berserk mid-turn) and must not tear down whatever side
     * windows the player already had up. */
    PROC_CALL(AiPhaseGoalDisplayCleanup),
#endif
    PROC_CALL(AiPhaseCleanup),

    PROC_END,
};

CONST_DATA
struct ProcCmd gProcScr_BerserkCpPhase[] =
{
    PROC_NAME("E_BSKPHASE"),

    PROC_CALL(AiPhaseBerserkInit),
    PROC_YIELD,

    PROC_CALL(AiPhaseCleanup),

    PROC_END,
};

static void AiPhaseInit(struct Proc* proc)
{
    int i;

    gAiState.flags = AI_FLAG_0;
    gAiState.unk7E = -1;

    gAiState.orderState = 0;

    for (i = 0; i < 8; ++i)
        gAiState.cmd_result[i] = 0;

    gAiState.specialItemFlags = gAiItemConfigTable[gPlaySt.chapterIndex];
    gAiState.unk84 = 0;

    UpdateAllPhaseHealingAIStatus();
    SetupUnitInventoryAIFlags();

#if FE8_AW2_ASSETS
    /* Skip the window entirely for a phase with no units to act -- e.g. an
     * NPC phase with no NPCs on the map, which AiOrderStart below finishes
     * in essentially 0 frames, just long enough for the window's own
     * appear (and, moments later, AiPhaseGoalDisplayCleanup's disappear)
     * to be visibly seen flashing by. */
    if (CountUnitsByFaction(gPlaySt.faction) != 0)
        StartAiPhaseGoalDisplay();
#endif
}

#if FE8_CO_POWERS
static int AiPhaseCoPowersHook(struct Proc* proc)
{
    return CoPowers_OnAiPhaseStart(proc);
}
#endif

static void AiOrderStart(struct Proc* proc)
{
    Proc_StartBlocking(gProcScr_CpOrder, proc);
}

#if FE8_AW2_ASSETS
static void AiPhaseGoalDisplayCleanup(struct Proc* proc)
{
    EndAiPhaseGoalDisplay();
}
#endif

static void AiPhaseBerserkInit(struct Proc* proc)
{
    int i;

    gAiState.flags = AI_FLAG_BERSERKED;
#if FE8_VESLY_DEBUGGER
    if (ShouldAIControlRemainingUnits())
        gAiState.flags = AI_FLAG_0;
#endif
    gAiState.unk7E = -1;

    for (i = 0; i < 8; ++i)
        gAiState.cmd_result[i] = 0;

    gAiState.specialItemFlags = gAiItemConfigTable[gPlaySt.chapterIndex];

    UpdateAllPhaseHealingAIStatus();
    SetupUnitInventoryAIFlags();

    Proc_StartBlocking(gProcScr_BerserkCpOrder, proc);
}

static void AiPhaseCleanup(struct Proc* proc)
{
    gAiState.flags = AI_FLAGS_NONE;
}
