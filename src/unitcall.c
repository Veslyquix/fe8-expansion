#include "global.h"

#if FE8_SKILLSYSTEM

#include "unitcall.h"

#include "bmunit.h"
#include "bmmap.h"
#include "bmidoten.h"
#include "bmudisp.h"
#include "bmmind.h"
#include "mu.h"
#include "proc.h"
#include "cp_common.h"

#include "constants/characters.h"
#include "constants/classes.h"

// Precomputed per-candidate movement scripts/destinations, built once (all
// candidates at once) when a Call is issued. Kept out of struct UnitCallProc
// because the Proc pool hands out fixed sizeof(struct Proc) slots (see
// src/proc.c) with no room for a ~1KB table.
static u8 sUnitCallScripts[UNIT_CALL_MAX_TARGETS][MOVE_CMD_MAX_COUNT];
static u8 sUnitCallDestX[UNIT_CALL_MAX_TARGETS];
static u8 sUnitCallDestY[UNIT_CALL_MAX_TARGETS];

struct UnitCallSlot {
    u8 unitId; // 0 == this MU slot is idle
    u8 originX;
    u8 originY;
    u8 destX;
    u8 destY;
    u8 scriptIndex; // index into sUnitCallScripts/sUnitCallDest{X,Y}
};

struct UnitCallProc {
    PROC_HEADER;

    u8 callerId;
    u8 pendingIds[UNIT_CALL_MAX_TARGETS];
    u8 pendingCount;
    u8 nextPendingIndex;
    u8 rampState; // index of the highest slot started so far by the stagger
    struct UnitCallSlot slots[UNIT_CALL_MAX_CONCURRENT];
};

void UnitCall_Update(struct UnitCallProc* proc);

struct ProcCmd CONST_DATA gProcScr_UnitCall[] = {
    PROC_NAME("UNITCALL"),
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

    for (i = 0; i < MOVE_CMD_MAX_COUNT && script[i] != MOVE_CMD_HALT; i++)
        ;

    return i;
}

// Starts the next not-yet-started pending unit (if any) walking into
// proc's slotIndex; leaves the slot idle if nothing is left pending or no
// MU proc is currently free.
static void AdvancePendingIntoSlot(struct UnitCallProc* proc, int slotIndex)
{
    int pendIdx;
    u8 unitId;
    struct Unit* unit;
    struct UnitCallSlot* slot;
    struct MuProc* mu;

    while (proc->nextPendingIndex < proc->pendingCount
           && proc->pendingIds[proc->nextPendingIndex] == 0)
        proc->nextPendingIndex++;

    if (proc->nextPendingIndex >= proc->pendingCount) {
        proc->slots[slotIndex].unitId = 0;
        return;
    }

    if (!CanStartMu()) {
        // No free MU slot right now -- leave idle and retry next tick.
        proc->slots[slotIndex].unitId = 0;
        return;
    }

    pendIdx = proc->nextPendingIndex;
    unitId = proc->pendingIds[pendIdx];
    unit = GetUnit(unitId);

    HideUnitSprite(unit);
    mu = StartMu(unit);

    if (!mu) {
        ShowUnitSprite(unit);
        proc->slots[slotIndex].unitId = 0;
        return;
    }

    proc->nextPendingIndex++;

    slot = &proc->slots[slotIndex];
    slot->unitId = unitId;
    slot->originX = unit->xPos;
    slot->originY = unit->yPos;
    slot->destX = sUnitCallDestX[pendIdx];
    slot->destY = sUnitCallDestY[pendIdx];
    slot->scriptIndex = pendIdx;

    SetMuDefaultFacing(mu);
    SetMuMoveScript(mu, sUnitCallScripts[pendIdx]);
}

// Commits the real position update for a unit whose MU has finished
// walking (the actual struct Unit position/occupancy is deliberately left
// untouched until the visual walk completes -- see StartUnitCallConvergence).
static void FinishCallSlot(struct UnitCallProc* proc, int slotIndex)
{
    struct UnitCallSlot* slot = &proc->slots[slotIndex];
    struct Unit* unit = GetUnit(slot->unitId);

    gBmMapUnit[slot->originY][slot->originX] = 0;

    unit->xPos = slot->destX;
    unit->yPos = slot->destY;

    gBmMapUnit[unit->yPos][unit->xPos] = unit->index;

    ShowUnitSprite(unit);

    slot->unitId = 0;
}

static bool SlotAtLeastThirdDone(struct UnitCallProc* proc, int slotIndex)
{
    struct UnitCallSlot* slot = &proc->slots[slotIndex];
    struct Unit* unit;
    struct MuProc* mu;
    int total;

    if (slot->unitId == 0)
        return TRUE; // nothing here to wait on -- don't block the ramp

    unit = GetUnit(slot->unitId);
    mu = GetUnitMu(unit);

    if (!mu || !IsMuActive(mu))
        return TRUE; // already finished

    total = CountMoveSteps((u8*)mu->config->movescr);

    if (total == 0)
        return TRUE;

    return (mu->config->pc * 3 >= total);
}

void UnitCall_Update(struct UnitCallProc* proc)
{
    int i;
    bool anyActive = FALSE;

    for (i = 0; i < UNIT_CALL_MAX_CONCURRENT; i++) {
        struct Unit* unit;
        struct MuProc* mu;

        if (proc->slots[i].unitId == 0)
            continue;

        unit = GetUnit(proc->slots[i].unitId);
        mu = GetUnitMu(unit);

        if (!mu || !IsMuActive(mu)) {
            FinishCallSlot(proc, i);
            AdvancePendingIntoSlot(proc, i);
        }
    }

    if (proc->rampState < UNIT_CALL_MAX_CONCURRENT - 1
        && SlotAtLeastThirdDone(proc, proc->rampState)) {
        proc->rampState++;
        AdvancePendingIntoSlot(proc, proc->rampState);
    }

    for (i = 0; i < UNIT_CALL_MAX_CONCURRENT; i++) {
        if (proc->slots[i].unitId != 0)
            anyActive = TRUE;
    }

    if (!anyActive && proc->nextPendingIndex >= proc->pendingCount)
        Proc_End(proc);
}

void StartUnitCallConvergence(struct Unit* caller)
{
    struct UnitCallProc* proc;
    int i;

    proc = Proc_Start(gProcScr_UnitCall, PROC_TREE_3);

    if (!proc)
        return;

    proc->callerId = caller->index;
    proc->pendingCount = BuildCallTargetList(caller, proc->pendingIds);

    if (proc->pendingCount > UNIT_CALL_MAX_TARGETS)
        proc->pendingCount = UNIT_CALL_MAX_TARGETS;

    proc->nextPendingIndex = 0;
    proc->rampState = 0;

    for (i = 0; i < UNIT_CALL_MAX_CONCURRENT; i++)
        proc->slots[i].unitId = 0;

    // Precompute every candidate's path synchronously and up front, same as
    // the AI does for a single unit (e.g. AiTryMoveTowards) -- the movement
    // scratch buffers are safe to reuse here since no range overlay is
    // currently on-screen (the unit menu that triggered this already
    // closed). Claim each destination in gBmMapUnit immediately so later
    // candidates in this same batch don't also path onto it.
    for (i = 0; i < proc->pendingCount; i++) {
        struct Unit* candidate = GetUnit(proc->pendingIds[i]);
        struct Vec2 dest;

        if (!FindCallDestination(candidate, caller, &dest)) {
            proc->pendingIds[i] = 0; // fully boxed in -- drop it
            continue;
        }

        SetWorkingBmMap(gBmMapMovement);
        GenerateBestMovementScript(dest.x, dest.y, sUnitCallScripts[i]);

        sUnitCallDestX[i] = dest.x;
        sUnitCallDestY[i] = dest.y;

        gBmMapUnit[dest.y][dest.x] = candidate->index;
    }

    AdvancePendingIntoSlot(proc, 0);
}

s8 ActionCall(ProcPtr proc)
{
    gActiveUnit->state |= US_HAS_MOVED;

    StartUnitCallConvergence(gActiveUnit);

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
