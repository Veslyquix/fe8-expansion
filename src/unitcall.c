#include "global.h"

#if FE8_SKILLSYSTEM

#include "unitcall.h"

#include "bmunit.h"
#include "bmmap.h"
#include "bmidoten.h"
#include "bmudisp.h"
#include "bmmind.h"
#include "bmbattle.h"
#include "bmitem.h"
#include "player_interface.h"
#include "mu.h"
#include "proc.h"
#include "cp_common.h"

#include "constants/characters.h"
#include "constants/classes.h"
#include "constants/items.h"

// One tiny walker proc per unit currently walking toward the caller (see
// struct UnitCallWalkerProc below) -- mirrors Make6CKOIDO_common's pattern
// (src/koido.c) of keeping a unit's own move-command buffer inside its own
// proc struct and handing it to SetMuMoveScript, rather than a shared
// scratch table sized for every possible target. Ticked up whenever a
// walker proc actually starts an MU, ticked down in its own end callback,
// so the conductor never needs to enumerate/dereference specific procs to
// know how many are in flight.
static u8 sUnitCallActiveWalkers;

struct UnitCallWalkerProc {
    PROC_HEADER;

    u8 unitId;
    u8 destX;
    u8 destY;
    u8 script[UNIT_CALL_SCRIPT_LEN];
};

void UnitCallWalker_Update(struct UnitCallWalkerProc* proc);
void UnitCallWalker_OnEnd(struct UnitCallWalkerProc* proc);

struct ProcCmd CONST_DATA gProcScr_UnitCallWalker[] = {
    PROC_NAME("CALLWALK"),
    PROC_SET_END_CB(UnitCallWalker_OnEnd),
    PROC_REPEAT(UnitCallWalker_Update),
    PROC_END,
};

// The conductor: just the queue of who's still waiting to be sent walking
// plus the bookkeeping to stagger the initial few. Sized to fit comfortably
// inside a single Proc slot (see src/proc.c, sizeof(struct Proc)).
struct UnitCallProc {
    PROC_HEADER;

    u8 callerId;
    u8 pendingIds[UNIT_CALL_MAX_TARGETS]; // 0 == already consumed
    u8 pendingCount;
    u8 totalStarted;
    u8 rampUnitId; // unit whose progress currently gates the next stagger start; 0 once the initial ramp-up is done
};

void UnitCall_Update(struct UnitCallProc* proc);

struct ProcCmd CONST_DATA gProcScr_UnitCall[] = {
    PROC_NAME("UNITCALL"),
    // ApplyUnitAction (which starts this proc via ActionCall) and
    // PlayerPhase_FinishAction's EndAllMus() call both run as PROC_CALL
    // steps in the same player-phase script, so they execute in the same
    // frame with no yield in between. Starting a walker's MU immediately
    // would have it killed by that EndAllMus() before ever animating --
    // sleep one frame so the first UnitCall_Update tick (and everything it
    // starts) lands strictly after the turn-completion flow has finished.
    PROC_SLEEP(1),
    PROC_REPEAT(UnitCall_Update),
    PROC_END,
};

bool CanUnitCall(struct Unit* unit)
{
    if (unit->state & US_HAS_MOVED)
        return FALSE;

    if (unit->pCharacterData->number != UNIT_CALL_CHARACTER)
        return FALSE;

    return TRUE;
}

static bool IsCallableClass(int classId)
{
    switch (classId) {
        case CLASS_SOLDIER:
        case CLASS_ARMOR_KNIGHT:
        case CLASS_ARMOR_KNIGHT_F:
        case CLASS_FIGHTER:
        case CLASS_MAGE:
        case CLASS_MAGE_F:
            return TRUE;

        default:
            return FALSE;
    }
}

bool IsUnitCallable(struct Unit* candidate, struct Unit* caller)
{
    int dist;

    if (candidate->pCharacterData == NULL)
        return FALSE;

    if (candidate == caller)
        return FALSE;

    if (UNIT_FACTION(candidate) != UNIT_FACTION(caller))
        return FALSE;

    if (candidate->state & (US_HAS_MOVED | US_HIDDEN))
        return FALSE;

    if (!IsCallableClass(candidate->pClassData->number))
        return FALSE;

    dist = ABS(candidate->xPos - caller->xPos) + ABS(candidate->yPos - caller->yPos);

    if (dist == 0 || dist > UNIT_CALL_RANGE)
        return FALSE;

    return TRUE;
}

// Fills outIds (capacity UNIT_CALL_MAX_TARGETS) with every unit currently
// callable by caller and returns how many were found (capped at
// UNIT_CALL_MAX_TARGETS).
static int BuildCallTargetList(struct Unit* caller, u8* outIds)
{
    int id;
    int count = 0;

    for (id = 1; id < 0xC0; id++) {
        struct Unit* candidate = GetUnit(id);

        if (!IsUnitCallable(candidate, caller))
            continue;

        if (count < UNIT_CALL_MAX_TARGETS)
            outIds[count] = id;

        count++;
    }

    return count;
}

// Finds the reachable tile (honoring candidate's own movement type/stat)
// closest to caller, using its full movement to close as much distance as
// possible -- mirrors the scan AiTryMoveTowards uses (src/cp_utility.c).
static bool FindCallDestination(struct Unit* candidate, struct Unit* caller, struct Vec2* out)
{
    int ix, iy;
    int bestRange = -1;

    GenerateUnitMovementMap(candidate);
    GenerateExtendedMovementMapOnRange(caller->xPos, caller->yPos, GetUnitMovementCost(candidate));

    for (iy = 0; iy < gBmMapSize.y; iy++) {
        for (ix = 0; ix < gBmMapSize.x; ix++) {
            if (gBmMapMovement[iy][ix] > MAP_MOVEMENT_MAX)
                continue;

            if (gBmMapUnit[iy][ix] != 0 && gBmMapUnit[iy][ix] != candidate->index)
                continue;

            if (ix == caller->xPos && iy == caller->yPos)
                continue;

            if (bestRange < 0 || gBmMapRange[iy][ix] < bestRange) {
                bestRange = gBmMapRange[iy][ix];
                out->x = ix;
                out->y = iy;
            }
        }
    }

    return (bestRange >= 0);
}

static int CountMoveSteps(const u8* script)
{
    int i;

    for (i = 0; i < UNIT_CALL_SCRIPT_LEN && script[i] != MOVE_CMD_HALT; i++)
        ;

    return i;
}

// Removes and returns the next not-yet-consumed id from proc->pendingIds
// (0 if none left).
static u8 PopNextPendingId(struct UnitCallProc* proc)
{
    int i;

    for (i = 0; i < proc->pendingCount; i++) {
        if (proc->pendingIds[i] != 0) {
            u8 id = proc->pendingIds[i];
            proc->pendingIds[i] = 0;
            return id;
        }
    }

    return 0;
}

static bool HasNoMorePending(struct UnitCallProc* proc)
{
    int i;

    for (i = 0; i < proc->pendingCount; i++) {
        if (proc->pendingIds[i] != 0)
            return FALSE;
    }

    return TRUE;
}

// Starts a walker (and its MU) for the next reachable pending candidate, if
// any and if the MU pool has room. Skips (drops) any candidate that turns
// out to be fully boxed in.
static void TrySpawnNextWalker(struct UnitCallProc* proc)
{
    struct Unit* caller;
    u8 candidateId;
    struct Unit* candidate;
    struct Vec2 dest;
    struct UnitCallWalkerProc* walker;
    struct MuProc* mu;

    if (!CanStartMu())
        return;

    caller = GetUnit(proc->callerId);

    for (;;) {
        candidateId = PopNextPendingId(proc);

        if (candidateId == 0)
            return;

        candidate = GetUnit(candidateId);

        if (FindCallDestination(candidate, caller, &dest))
            break;

        // Boxed in -- drop it and try the next pending candidate.
    }

    // FindCallDestination's GenerateExtendedMovementMapOnRange call above
    // repoints gWorkingBmMap at gBmMapRange -- point it back at the
    // movement-cost map GenerateBestMovementScript needs to backtrack.
    SetWorkingBmMap(gBmMapMovement);

    walker = Proc_Start(gProcScr_UnitCallWalker, PROC_TREE_3);

    if (!walker)
        return; // proc pool exhausted; candidate is lost this call (rare)

    walker->unitId = candidateId;
    walker->destX = dest.x;
    walker->destY = dest.y;

    GenerateBestMovementScript(dest.x, dest.y, walker->script);

    // Claim the destination so later candidates don't also path onto it.
    gBmMapUnit[dest.y][dest.x] = candidate->index;

    HideUnitSprite(candidate);
    candidate->state |= US_HIDDEN; 
    mu = StartMu(candidate);

    if (mu) {
        SetMuDefaultFacing(mu);
        SetMuMoveScript(mu, walker->script);
    }

    sUnitCallActiveWalkers++;
    proc->totalStarted++;
    proc->rampUnitId = candidateId;
}

static bool IsUnitAtLeastThirdDone(u8 unitId)
{
    struct Unit* unit;
    struct MuProc* mu;
    int total;

    if (unitId == 0)
        return TRUE;

    unit = GetUnit(unitId);
    mu = GetUnitMu(unit);

    if (!mu || !IsMuActive(mu))
        return TRUE; // already finished (or never started)

    total = CountMoveSteps((u8*)mu->config->movescr);

    if (total == 0)
        return TRUE;

    return (mu->config->pc * 3 >= total);
}

void UnitCall_Update(struct UnitCallProc* proc)
{
    if (sUnitCallActiveWalkers < UNIT_CALL_MAX_CONCURRENT) {
        bool canSpawn = TRUE;

        // During the initial ramp (first UNIT_CALL_MAX_CONCURRENT starts),
        // gate on the 1/3-progress rule so units peel off staggered instead
        // of all at once. Once that many have been started, later
        // backfills (a slot freed by a finished walker) are immediate.
        if (proc->totalStarted < UNIT_CALL_MAX_CONCURRENT && proc->rampUnitId != 0)
            canSpawn = IsUnitAtLeastThirdDone(proc->rampUnitId);

        if (canSpawn)
            TrySpawnNextWalker(proc);
    }

    if (sUnitCallActiveWalkers == 0 && HasNoMorePending(proc)) { 
        Proc_End(proc);
        RefreshEntityBmMaps();
    }
        
}

void StartUnitCallConvergence(struct Unit* caller)
{
    struct UnitCallProc* proc = Proc_Start(gProcScr_UnitCall, PROC_TREE_3);

    if (!proc)
        return;

    sUnitCallActiveWalkers = 0;

    proc->callerId = caller->index;
    proc->pendingCount = BuildCallTargetList(caller, proc->pendingIds);

    if (proc->pendingCount > UNIT_CALL_MAX_TARGETS)
        proc->pendingCount = UNIT_CALL_MAX_TARGETS;

    // Every pending unit is about to walk away from its current tile, so
    // clear all of them from the occupancy map up front, before anyone's
    // destination is decided -- otherwise an earlier-decided unit's
    // still-occupied origin would wrongly block a later unit from passing
    // through or landing on it. TrySpawnNextWalker re-claims each unit's
    // chosen destination as soon as it's decided, so two pending units can
    // still never be routed onto the same tile.
    {
        int i;

        for (i = 0; i < proc->pendingCount; i++) {
            struct Unit* pending = GetUnit(proc->pendingIds[i]);
            gBmMapUnit[pending->yPos][pending->xPos] = 0;
        }
    }

    proc->totalStarted = 0;
    proc->rampUnitId = 0;

    // Deliberately not starting the first walker here -- see the PROC_SLEEP
    // note on gProcScr_UnitCall above. UnitCall_Update's first tick (after
    // that sleep) starts it instead.
}

void UnitCallWalker_Update(struct UnitCallWalkerProc* proc)
{
    struct Unit* unit = GetUnit(proc->unitId);
    struct MuProc* mu = GetUnitMu(unit);

    if (mu && IsMuActive(mu))
        return;

    // MOVE_CMD_HALT (what a normal completed walk ends on) only parks the
    // MU proc in MU_STATE_INACTIVE -- it doesn't free its pool slot the way
    // MOVE_CMD_END/EndMu do. Free it explicitly or it leaks a MU_MAX_COUNT
    // slot for the rest of the session.
    if (mu)
        EndMu(mu);

    gBmMapUnit[unit->yPos][unit->xPos] = 0;

    unit->xPos = proc->destX;
    unit->yPos = proc->destY;

    gBmMapUnit[unit->yPos][unit->xPos] = unit->index;

    ShowUnitSprite(unit);
    unit->state &= ~(US_HIDDEN); 

    // The unit's persistent map sprite handle caches its last-known screen
    // position; ShowUnitSprite alone just clears the hide bit, so without
    // this it reappears back at its origin tile instead of its destination.
    
    RefreshUnitSprites();

    Proc_End(proc);
}

void UnitCallWalker_OnEnd(struct UnitCallWalkerProc* proc)
{
    if (sUnitCallActiveWalkers > 0)
        sUnitCallActiveWalkers--;
}

// ITEM_UNK_C3/BD/BE are otherwise-unused vanilla dummy weapon slots
// (src/data_items.c) repurposed to drive this: each carries a
// SPELL_ASSOC_DATA count=1 entry (src/spellassoc-data.c), which is what
// routes the Ekr battle intro to a solo/single-unit-centered scene instead
// of a normal two-sided one (the same mechanism ITEM_STAFF_LATONA uses).
// Real callable-weapon items don't have such an entry -- adding one to a
// real weapon would also force every ordinary battle using it (any unit,
// any time) into the same solo layout, so a dedicated per-category
// placeholder is used instead of the caller's real equipped weapon.
static u16 GetCallAnimWeapon(struct Unit* unit)
{
    switch (unit->pClassData->number) {
        case CLASS_FIGHTER:
            return ITEM_UNK_BD; // Axe

        case CLASS_MAGE:
        case CLASS_MAGE_F:
            return ITEM_UNK_BE; // Anima

        case CLASS_SOLDIER:
        case CLASS_ARMOR_KNIGHT:
        case CLASS_ARMOR_KNIGHT_F:
        default:
            return ITEM_UNK_C3; // Lance
    }
}

// Sets up a solo attack-swing animation (a class-appropriate placeholder
// weapon -- see GetCallAnimWeapon -- self-targeted) with a guaranteed miss
// so nothing actually takes damage. BattleInitItemEffect(unit, -1) leaves
// gBattleActor.weaponSlotIndex at -1 (no real inventory slot involved), so
// overwriting its weapon fields afterward never touches unit->items[].
// Unlike a real ActionCombat, there's no BattleApplyItemEffect (that would
// grant exp / consume weapon durability -- moot here anyway, since this
// isn't a real inventory item) and no BattleApplyGameStateUpdates afterward
// (no real target to update).
static void UnitCall_SetUpSoloAttackAnim(struct Unit* unit)
{
    u16 weapon = GetCallAnimWeapon(unit);

    BattleInitItemEffect(unit, -1);
    BattleInitItemEffectTarget(unit);

    gBattleActor.weapon = weapon;
    gBattleActor.weaponBefore = weapon;
    gBattleActor.weaponType = GetItemType(weapon);
    gBattleActor.weaponAttributes = GetItemAttributes(weapon);

    gBattleHitIterator->info |= BATTLE_HIT_INFO_BEGIN;
    gBattleHitIterator->attributes |= BATTLE_HIT_ATTR_MISS;
    (++gBattleHitIterator)->info |= BATTLE_HIT_INFO_END;
}

void UnitCall_BeginConvergence(ProcPtr proc)
{
    StartUnitCallConvergence(gActiveUnit);
}

// Mirrors sProcScr_CombatAction's shape (src/bmmind.c): BeginBattleAnimations
// runs as this blocked child's own first step, and normal proc ticking
// (including the parent player-phase proc this blocks) is suspended for the
// animation's whole real duration -- so the follow-up call genuinely only
// runs once the scene has finished, not just one frame later.
struct ProcCmd CONST_DATA gProcScr_CallAction[] = {
    PROC_NAME("CALLACTION"),
    PROC_CALL(BeginBattleAnimations),
    PROC_SLEEP(1),
    PROC_CALL(UnitCall_BeginConvergence),
    PROC_END,
};

s8 ActionCall(ProcPtr proc)
{
    // Real actions (Attack, Rescue, ...) never set US_HAS_MOVED themselves --
    // MoveActiveUnit (src/bmunit.c), called from PlayerPhase_FinishAction
    // only once ApplyUnitAction (and thus this whole blocking sequence) has
    // fully returned, is what actually grays the unit out via US_UNSELECTABLE.
    // Setting US_HAS_MOVED here both grayed the actor out before the
    // animation played and (since it aliases US_CANTOING) would wrongly deny
    // canto to canto-capable units using Call.

    if (GetBattleAnimPreconfType() != PLAY_ANIMCONF_OFF) {
        // Matches the vanilla ApplyUnitAction call sites for real actions:
        // the side windows must be torn down before a battle scene starts or
        // they reappear over it with corrupted graphics. PlayerPhase_FinishAction
        // restarts them once the player-phase script returns to idle.
        EndPlayerPhaseSideWindows();

        UnitCall_SetUpSoloAttackAnim(gActiveUnit);
        Proc_StartBlocking(gProcScr_CallAction, proc);
    } else {
        StartUnitCallConvergence(gActiveUnit);
    }

    return 1;
}

u8 CallCommandUsability(const struct MenuItemDef* def, int number)
{
    u8 ids[UNIT_CALL_MAX_TARGETS];

    if (!CanUnitCall(gActiveUnit))
        return MENU_NOTSHOWN;

    if (BuildCallTargetList(gActiveUnit, ids) == 0)
        return MENU_NOTSHOWN;

    return MENU_ENABLED;
}

u8 CallCommandEffect(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    gActionData.unitActionType = UNIT_ACTION_CALL;

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

bool AiTryDoCall(void)
{
    u8 ids[UNIT_CALL_MAX_TARGETS];

    if (!CanUnitCall(gActiveUnit))
        return FALSE;

    if (BuildCallTargetList(gActiveUnit, ids) == 0)
        return FALSE;

    AiSetDecision(gActiveUnit->xPos, gActiveUnit->yPos, AI_ACTION_CALL, 0, 0, 0, 0);

    return TRUE;
}

#endif // FE8_SKILLSYSTEM
