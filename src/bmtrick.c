#include "global.h"

#include "constants/terrains.h"
#include "constants/event-flags.h"

#include "bmunit.h"
#include "bmmap.h"
#include "chapterdata.h"
#include "eventinfo.h"
#include "proc.h"
#include "event.h"
#include "uiselecttarget.h"
#include "bmtarget.h"
#include "bmudisp.h"
#include "bmusailment.h"
#include "bmtrick.h"

struct ProcCmd CONST_DATA gProcScr_UpdateTraps[] =
{
    PROC_CALL(CountDownTraps),
    PROC_CALL(RefreshEntityBmMapsAsRed),

    PROC_CALL(GenerateTrapDamageTargets),
    PROC_CALL(RecordTrapDamageDefeats),

    PROC_CALL(GenerateDisplayedTrapDamageTargets),
    PROC_START_CHILD_BLOCKING(gProcScr_TrapDamageDisplay),

    PROC_CALL(ResetCountedDownTraps),
    PROC_CALL(RefreshEntityBmMaps),

    PROC_CALL(PostTrapExecFlag),

    PROC_END,
};

static void GenerateFireTileTrapTargets(int x, int y, int damage);
static void GenerateArrowTrapTargets(int x, int y, int damage);
static void GenerateGasTrapTargets(int x, int y, int damage, int facing);
static s8 ShouldSkipGasTrapDisplay(int x, int y, int facing);

EWRAM_DATA static struct Trap sTrapPool[TRAP_MAX_COUNT] = {};
EWRAM_DATA static struct Trap sTrapLast = {};

inline struct Trap* GetTrap(int id)
{
    return sTrapPool + id;
}

void ClearTraps(void)
{
    int i;

    for (i = 0; i < TRAP_MAX_COUNT; ++i)
        sTrapPool[i].type = TRAP_NONE;

    sTrapLast.type = TRAP_NONE;
}

struct Trap* GetTrapAt(int x, int y)
{
    struct Trap* it;

lop:
    for (it = GetTrap(0); it->type != TRAP_NONE; ++it)
    {
        // Check trap position
        if ((x == it->xPos) && (y == it->yPos))
            return it;

        // Check if we on a wall, and there is a wall above
        // In which case the trap would be on the topmost wall tile
        if (gBmMapTerrain[y][x] == TERRAIN_WALL_DAMAGED)
        {
            if ((y > 0) && gBmMapTerrain[y-1][x] == TERRAIN_WALL_DAMAGED)
            {
                y = y-1;
                goto lop;
            }
        }
    }

    return NULL;
}

struct Trap* GetTypedTrapAt(int x, int y, int trapType)
{
    struct Trap* it;

    for (it = GetTrap(0); it->type != TRAP_NONE; ++it)
    {
        // Check trap position
        if ((it->xPos == x) && (it->yPos == y) && (it->type == trapType))
            return it;

        // Check if we want a wall
        if (trapType == TERRAIN_WALL_DAMAGED)
        {
            // Check if we on a wall, and there is a wall above
            // In which case the trap would be on the topmost wall tile
            if (gBmMapTerrain[y][x] == TERRAIN_WALL_DAMAGED)
            {
                if ((y > 0) && gBmMapTerrain[y-1][x] == TERRAIN_WALL_DAMAGED)
                {
                    return GetTrapAt(x, y-1);
                }
            }
        }
    }

    return NULL;
}

struct Trap* AddTrap(int x, int y, int trapType, int meta)
{
    struct Trap* trap;

    // Find first free trap
    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap) {}

    trap->xPos = x;
    trap->yPos = y;
    trap->type = trapType;
    trap->extra = meta;

    return trap;
}

struct Trap* AddDamagingTrap(int x, int y, int trapType, int meta, int turnCountdown, int turnInterval, int damage)
{
    struct Trap* trap = AddTrap(x, y, trapType, meta);

    trap->data[TRAP_EXTDATA_TRAP_TURNFIRST] = turnCountdown;
    trap->data[TRAP_EXTDATA_TRAP_TURNNEXT]  = turnInterval;
    trap->data[TRAP_EXTDATA_TRAP_COUNTER]   = turnCountdown;
    trap->data[TRAP_EXTDATA_TRAP_DAMAGE]    = damage;

    return trap;
}

struct Trap* RemoveTrap(struct Trap* trap)
{
    while (trap->type != TRAP_NONE)
    {
        *trap++ = *(trap + 1);
    }

    // return trap; // BUG
}

void AddFireTile(int x, int y, int turnCountdown, int turnInterval)
{
    AddDamagingTrap(x, y, TRAP_FIRETILE, 0, turnCountdown, turnInterval, 10);
}

void AddGasTrap(int x, int y, int facing, int turnCountdown, int turnInterval)
{
    AddDamagingTrap(x, y, TRAP_GAS, facing, turnCountdown, turnInterval, 3);
}

void AddArrowTrap(int x, int turnCountdown, int turnInterval)
{
    AddDamagingTrap(x, 0, TRAP_LIGHTARROW, 0, turnCountdown, turnInterval, 10);
}

void AddMapChangeTrap(int x, int y, int turnCountdown, int turnInterval)
{
    AddDamagingTrap(x, y, TRAP_MAPCHANGE2, 0, turnCountdown, turnInterval, 0);
}

void AddTrap8(int x, int y)
{
    AddTrap(x, y, TRAP_8, 0);
}

void AddTrap9(int x, int y, int meta)
{
    AddTrap(x, y, TRAP_9, meta);
}

#if FE8_PURCHASE_GENERICS
struct Trap* AddPurchaseBaseTrap(int x, int y, int owner, int kind)
{
    struct Trap* trap = AddTrap(x, y, TRAP_PURCHASE_BASE, 0);

    trap->extra = 0;
    trap->data[TRAP_EXTDATA_PURCHASE_BASE_OWNER] = owner;
    trap->data[TRAP_EXTDATA_PURCHASE_BASE_KIND] = kind;
    trap->data[TRAP_EXTDATA_PURCHASE_BASE_CAPTURER] = PURCHASE_BASE_CAPTURE_NONE;
    trap->data[TRAP_EXTDATA_PURCHASE_BASE_GOLD_PER_TURN] = PURCHASE_BASE_DEFAULT_GOLD_PER_TURN;

    return trap;
}

struct Trap* GetPurchaseBaseTrapAt(int x, int y)
{
    return GetTypedTrapAt(x, y, TRAP_PURCHASE_BASE);
}

// Camp/Tent are runtime TRAP_PURCHASE_BASE traps with kind CAMP/TENT (see
// PURCHASE_BASE_KIND_CAMP/_TENT); chapter authoring uses the TRAP_CAMP/
// TRAP_TENT TrapData.type tags (LoadTrapData, src/bmtrap.c), which call
// these constructors directly instead of going through the terrain-scan
// InitPurchaseBaseTrapsFromTerrain path villages/forts/houses use.
struct Trap* AddCampTrap(int x, int y, int owner)
{
    struct Trap* trap = AddPurchaseBaseTrap(x, y, owner, PURCHASE_BASE_KIND_CAMP);

    // data[TRAP_EXTDATA_PURCHASE_BASE_GOLD_PER_TURN] is repurposed to store
    // Camp's current battle HP -- Camp/Tent always grant a flat
    // CAMP_TENT_GOLD_PER_TURN (see GrantIncomeForFaction), so the
    // gold-per-turn slot is otherwise unused for this kind, and no other
    // call site reads it for a CAMP-kind trap.
    SetCampTrapHp(trap, CAMP_STARTING_HP);

    return trap;
}

struct Trap* AddTentTrap(int x, int y, int owner)
{
    return AddPurchaseBaseTrap(x, y, owner, PURCHASE_BASE_KIND_TENT);
}

bool IsCampOrTentTrap(struct Trap* trap, int kind)
{
    if (trap == NULL || trap->type != TRAP_PURCHASE_BASE)
        return FALSE;

    return trap->data[TRAP_EXTDATA_PURCHASE_BASE_KIND] == kind;
}

void SetCampTrapHp(struct Trap* trap, int hp)
{
    if (trap == NULL)
        return;

    if (hp < 0)
        hp = 0;

    if (hp > CAMP_MAX_HP)
        hp = CAMP_MAX_HP;

    trap->data[TRAP_EXTDATA_PURCHASE_BASE_GOLD_PER_TURN] = hp;
}

int GetCampTrapHp(struct Trap* trap)
{
    if (trap == NULL)
        return 0;

    return trap->data[TRAP_EXTDATA_PURCHASE_BASE_GOLD_PER_TURN];
}

void SetPurchaseBaseTrapOwner(struct Trap* trap, int owner)
{
    if (trap != NULL)
        trap->data[TRAP_EXTDATA_PURCHASE_BASE_OWNER] = owner;
}

int GetPurchaseBaseTrapOwner(struct Trap* trap)
{
    if (trap == NULL)
        return PURCHASE_BASE_OWNER_NEUTRAL;

    return trap->data[TRAP_EXTDATA_PURCHASE_BASE_OWNER];
}

void SetPurchaseBaseTrapCapturer(struct Trap* trap, int capturer)
{
    if (trap != NULL)
        trap->data[TRAP_EXTDATA_PURCHASE_BASE_CAPTURER] = capturer;
}

int GetPurchaseBaseTrapCapturer(struct Trap* trap)
{
    if (trap == NULL)
        return PURCHASE_BASE_CAPTURE_NONE;

    return trap->data[TRAP_EXTDATA_PURCHASE_BASE_CAPTURER];
}

void ResetPurchaseBaseTrapCapture(struct Trap* trap)
{
    if (trap == NULL)
        return;

    trap->data[TRAP_EXTDATA_PURCHASE_BASE_CAPTURER] = PURCHASE_BASE_CAPTURE_NONE;
    trap->extra = 0;
}

void ResetPurchaseBaseTrapCaptureByUnit(int unitIndex)
{
    struct Trap* trap;

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        if (trap->type != TRAP_PURCHASE_BASE)
            continue;

        if (GetPurchaseBaseTrapCaptureProgress(trap) <= 0)
            continue;

        if ((u8)trap->data[TRAP_EXTDATA_PURCHASE_BASE_CAPTURER] == (u8)unitIndex)
            ResetPurchaseBaseTrapCapture(trap);
    }
}

void SetPurchaseBaseTrapCaptureProgress(struct Trap* trap, int progress)
{
    if (trap == NULL)
        return;

    if (progress < 0)
        progress = 0;

    if (progress > PURCHASE_BASE_CAPTURE_REQUIRED)
        progress = PURCHASE_BASE_CAPTURE_REQUIRED;

    trap->extra = progress;
}

int GetPurchaseBaseTrapCaptureProgress(struct Trap* trap)
{
    if (trap == NULL)
        return 0;

    return trap->extra;
}

void SetPurchaseBaseTrapGoldPerTurn(struct Trap* trap, int amount)
{
    if (trap == NULL)
        return;

    if (amount <= 0)
        amount = PURCHASE_BASE_DEFAULT_GOLD_PER_TURN;

    trap->data[TRAP_EXTDATA_PURCHASE_BASE_GOLD_PER_TURN] = amount;
}

int GetPurchaseBaseTrapGoldPerTurn(struct Trap* trap)
{
    int amount;

    if (trap == NULL)
        return PURCHASE_BASE_DEFAULT_GOLD_PER_TURN;

    amount = trap->data[TRAP_EXTDATA_PURCHASE_BASE_GOLD_PER_TURN];

    return amount <= 0 ? PURCHASE_BASE_DEFAULT_GOLD_PER_TURN : amount;
}

bool IsPurchaseBaseTerrain(int terrain)
{
    switch (terrain)
    {
    case TERRAIN_FORT:
    case TERRAIN_VILLAGE_REGULAR:
    case TERRAIN_VILLAGE_CLOSED:
    case TERRAIN_HOUSE:
    case TERRAIN_GATE_CASTLE:
    case TERRAIN_GATE_REGULAR:
    case TERRAIN_THRONE:
        return true;

    default:
        return false;
    }
}

static int GetPurchaseBaseKindFromTerrain(int terrain)
{
    switch (terrain)
    {
    case TERRAIN_FORT:
        return PURCHASE_BASE_KIND_FORT;

    case TERRAIN_HOUSE:
        return PURCHASE_BASE_KIND_HOUSE;

    case TERRAIN_GATE_CASTLE:
    case TERRAIN_GATE_REGULAR:
        return PURCHASE_BASE_KIND_GATE;

    case TERRAIN_THRONE:
        return PURCHASE_BASE_KIND_THRONE;

    default:
        return PURCHASE_BASE_KIND_VILLAGE;
    }
}

void InitPurchaseBaseTrapsFromTerrain(void)
{
    int ix, iy;

    for (iy = gBmMapSize.y - 1; iy >= 0; --iy)
    {
        for (ix = gBmMapSize.x - 1; ix >= 0; --ix)
        {
            int terrain = gBmMapTerrain[iy][ix];

            if (GetTrapAt(ix, iy) != NULL)
                continue;

            if (IsPurchaseBaseTerrain(terrain))
                AddPurchaseBaseTrap(ix, iy, PURCHASE_BASE_OWNER_NEUTRAL, GetPurchaseBaseKindFromTerrain(terrain));
        }
    }
}
#endif

void InitMapObstacles(void)
{
    int ix, iy;

    for (iy = gBmMapSize.y - 1; iy >= 0; --iy)
    {
        for (ix = gBmMapSize.x - 1; ix >= 0; --ix)
        {
            switch (gBmMapTerrain[iy][ix])
            {

            case TERRAIN_WALL_DAMAGED:
                if (gBmMapTerrain[iy-1][ix] == TERRAIN_WALL_DAMAGED)
                    continue; // walls are stacked, only the topmost tile gets a trap

                AddTrap(
                    ix, iy, TRAP_OBSTACLE,
                    GetROMChapterStruct(gPlaySt.chapterIndex)->mapCrackedWallHeath);

                break;

            case TERRAIN_SNAG:
                AddTrap(ix, iy, TRAP_OBSTACLE, 20);
                break;

            } // switch (gBmMapTerrain[iy][ix])
        }
    }
}

void ApplyEnabledMapChanges(void)
{
    struct Trap* trap;

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        switch (trap->type)
        {

        case TRAP_MAPCHANGE:
            ApplyMapChangesById(trap->extra);
            break;

        case TRAP_MAPCHANGE2:
            // this is a mystery
            ApplyMapChangesById(trap->extra ? trap->yPos : trap->xPos);
            break;

        } // switch (trap->type)
    }
}

void RefreshAllLightRunes(void)
{
    struct Trap* trap;

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        switch (trap->type)
        {

        case TRAP_LIGHT_RUNE:
            gBmMapTerrain[trap->yPos][trap->xPos] = TERRAIN_NONE;
            break;

        }
    }
}

int GetObstacleHpAt(int x, int y)
{
    struct Trap* trap;

    if ((trap = GetTrapAt(x, y)) != NULL)
    {
        return trap->extra;
    }

    if ((gBmMapTerrain[y][x] == TERRAIN_WALL_DAMAGED) && (gBmMapTerrain[y-1][x] == TERRAIN_WALL_DAMAGED))
    {
        if ((trap = GetTrapAt(x, y-1)) != NULL)
        {
            return trap->extra;
        }
    }

    return 0;
}

const struct MapChange* GetMapChange(int id)
{
    const struct MapChange* mapChange = GetChapterMapChangesPointer(gPlaySt.chapterIndex);

    if (!mapChange)
        return NULL;

    while (mapChange->id >= 0)
    {
        if (id == mapChange->id)
            return mapChange;

        ++mapChange;
    }

    return NULL;
}

int GetMapChangeIdAt(int x, int y)
{
    int result = -1;

    const struct MapChange* mapChange = GetChapterMapChangesPointer(gPlaySt.chapterIndex);

    if (!mapChange)
        return result;

    while (mapChange->id >= 0)
    {
        if (x >= mapChange->xOrigin)
            if (y >= mapChange->yOrigin)
                if (mapChange->xOrigin + mapChange->xSize - 1 >= x)
                    if (mapChange->yOrigin + mapChange->ySize - 1 >= y)
                        result = mapChange->id;

        ++mapChange;
    }

    return result;
}

void ApplyMapChangesById(int id)
{
    int ix = 0, iy = 0;

    const struct MapChange* mapChange = GetMapChange(id);
    const u16* tileDataIt = mapChange->data;

    for (iy = 0; iy < mapChange->ySize; ++iy)
    {
        for (ix = 0; ix < mapChange->xSize; ++ix)
        {
            if (*tileDataIt != 0)
            {
                gBmMapBaseTiles[mapChange->yOrigin + iy][mapChange->xOrigin + ix] = *tileDataIt++;
            }
            else
            {
                ++tileDataIt;
            }
        }
    }
}

void EnableMapChange(int id)
{
    AddTrap(0, 0, TRAP_MAPCHANGE, id);
}

void DisableMapChange(int id)
{
    struct Trap* trap;

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        if (trap->type == TRAP_MAPCHANGE && trap->extra == id)
            RemoveTrap(trap);
    }
}

s8 IsMapChangeEnabled(int id)
{
    struct Trap* trap;

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        if (trap->type == TRAP_MAPCHANGE && trap->extra == id)
            return TRUE;
    }

    return FALSE;
}

void UnitHideIfUnderRoof(struct Unit* unit)
{
    if (gBmMapTerrain[unit->yPos][unit->xPos] == TERRAIN_ROOF)
    {
        unit->state |= (US_HIDDEN | US_UNDER_A_ROOF);
    }
}

void UpdateRoofedUnits(void)
{
    int i;

    for (i = 1; i < 0xC0; ++i)
    {
        struct Unit* unit = GetUnit(i);

        if (!UNIT_IS_VALID(unit))
            continue;

        if (!(unit->state & US_UNDER_A_ROOF))
            continue;

        if (gBmMapTerrain[unit->yPos][unit->xPos] != TERRAIN_ROOF)
        {
            unit->state = (unit->state &~ (US_UNDER_A_ROOF | US_HIDDEN)) | US_BIT8;
        }
    }

    RefreshEntityBmMaps();
    RefreshUnitSprites();
}

void GenerateFireTileTrapTargets(int x, int y, int damage)
{
    AddTarget(x, y, gBmMapUnit[y][x], damage);
}

void GenerateArrowTrapTargets(int x, int y, int damage)
{
    int iy;

    for (iy = 0; iy < gBmMapSize.y; ++iy)
    {
        if (gBmMapUnit[iy][x])
            AddTarget(x, iy, gBmMapUnit[iy][x], damage);
    }
}

void GenerateGasTrapTargets(int x, int y, int damage, int facing)
{
    int i;

    int xInc = 0;
    int yInc = 0;

    switch (facing)
    {

    case FACING_UP:
        xInc = 0;
        yInc = -1;

        break;

    case FACING_DOWN:
        xInc = 0;
        yInc = +1;

        break;

    case FACING_LEFT:
        xInc = -1;
        yInc = 0;

        break;

    case FACING_RIGHT:
        xInc = +1;
        yInc = 0;

        break;

    } // switch (facing)

    for (i = 2; i >= 0; --i)
    {
        x += xInc;
        y += yInc;

        if (gBmMapUnit[y][x])
            AddTarget(x, y, gBmMapUnit[y][x], damage);
    }
}

s8 ShouldSkipGasTrapDisplay(int x, int y, int facing)
{
    int i;

    int xInc = 0;
    int yInc = 0;

    s8 boolHasNoEffect = TRUE;

    switch (facing)
    {

    case FACING_UP:
        xInc = 0;
        yInc = -1;

        break;

    case FACING_DOWN:
        xInc = 0;
        yInc = +1;

        break;

    case FACING_LEFT:
        xInc = -1;
        yInc = 0;

        break;

    case FACING_RIGHT:
        xInc = +1;
        yInc = 0;

        break;

    } // switch (facing)

    for (i = 0; i < 3; ++i)
    {
        x += xInc;
        y += yInc;

        if (gBmMapUnit[y][x])
            boolHasNoEffect = FALSE;
    }

    return boolHasNoEffect;
}

void GenerateTrapDamageTargets(void)
{
    struct Trap* trap;

    InitTargets(0, 0);

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        if ((s8) trap->data[TRAP_EXTDATA_TRAP_COUNTER] == 0)
        {
            switch (trap->type)
            {

            case TRAP_FIRETILE:
                GenerateFireTileTrapTargets(trap->xPos, trap->yPos, (s8) trap->data[TRAP_EXTDATA_TRAP_DAMAGE]);
                break;

            case TRAP_LIGHTARROW:
                GenerateArrowTrapTargets(trap->xPos, trap->yPos, (s8) trap->data[TRAP_EXTDATA_TRAP_DAMAGE]);
                break;

            case TRAP_GAS:
                GenerateGasTrapTargets(trap->xPos, trap->yPos, (s8) trap->data[TRAP_EXTDATA_TRAP_DAMAGE], trap->extra);
                break;

            }
        }
    }
}

void GenerateDisplayedTrapDamageTargets(void)
{
    struct Trap* trap;

    int specialType = 0;

    InitTargets(0, 0);

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        if (trap->data[TRAP_EXTDATA_TRAP_COUNTER] == 0)
        {
            switch (trap->type)
            {

            case TRAP_FIRETILE:
                if (gBmMapUnit[trap->yPos][trap->xPos])
                {
                    AddTarget(trap->xPos, trap->yPos, 0, TRAP_FIRETILE);
                    GenerateFireTileTrapTargets(trap->xPos, trap->yPos, trap->data[TRAP_EXTDATA_TRAP_DAMAGE]);
                }

                break;

            case TRAP_GAS:
                switch (trap->extra)
                {

                    // TODO: figure out

                case FACING_UP:
                    specialType = 0x64;
                    break;

                case FACING_DOWN:
                    specialType = 0x65;
                    break;

                case FACING_LEFT:
                    specialType = 0x66;
                    break;

                case FACING_RIGHT:
                    specialType = 0x67;
                    break;

                } // switch (trap->data[TRAP_EXTDATA_GAS_FACING])

                if (!ShouldSkipGasTrapDisplay(trap->xPos, trap->yPos, trap->extra))
                {
                    AddTarget(trap->xPos, trap->yPos, 0, specialType);
                    GenerateGasTrapTargets(trap->xPos, trap->yPos, trap->data[TRAP_EXTDATA_TRAP_DAMAGE], trap->extra);
                }

                break;

            case TRAP_LIGHTARROW:
                AddTarget(trap->xPos, trap->yPos, 0, TRAP_LIGHTARROW);
                GenerateArrowTrapTargets(trap->xPos, trap->yPos, trap->data[TRAP_EXTDATA_TRAP_DAMAGE]);
                break;

            case TRAP_MAPCHANGE2:
                AddTarget(trap->extra ? trap->xPos : trap->yPos, TRAP_INDEX(trap), 0, trap->type);
                break;

            } // switch (trap->type)
        }
    }
}

void CountDownTraps(void)
{
    struct Trap* trap;

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        switch (trap->type)
        {

        case TRAP_FIRETILE:
        case TRAP_GAS:
        case TRAP_LIGHTARROW:
        case TRAP_MAPCHANGE2:
            trap->data[TRAP_EXTDATA_TRAP_COUNTER]--;
            break;

        } // switch (trap->type)
    }
}

void ResetCountedDownTraps(void)
{
    struct Trap* trap;

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        switch (trap->type)
        {

        case TRAP_FIRETILE:
        case TRAP_GAS:
        case TRAP_LIGHTARROW:
        case TRAP_MAPCHANGE2:
            if (trap->data[TRAP_EXTDATA_TRAP_COUNTER] == 0)
                trap->data[TRAP_EXTDATA_TRAP_COUNTER] = trap->data[TRAP_EXTDATA_TRAP_TURNNEXT];

            break;

        } // switch (trap->type)
    }
}

void RefreshEntityBmMapsAsRed(void)
{
    int truePhase = gPlaySt.faction;
    gPlaySt.faction = FACTION_RED;

    RefreshEntityBmMaps();

    gPlaySt.faction = truePhase;
}

void RecordTrapDamageDefeats(void)
{
    PidStatsRecordTargetListDeaths(3);
}

void PostTrapExecFlag(void)
{
    // TODO: EID/FLAG DEFINITIONS

    if (CheckFlag(EVFLAG_GAMEOVER) || CountAvailableBlueUnits() == 0)
    {
        CallGameOverEvent();
    }

    if (!AreAnyEnemyUnitDead())
        SetFlag(EVFLAG_DEFEAT_ALL);
}

struct Trap* AddLightRune(int x, int y)
{
    struct Trap* trap = AddTrap(x, y, TRAP_LIGHT_RUNE, gBmMapTerrain[y][x]);

    trap->data[TRAP_EXTDATA_RUNE_TURNSLEFT] = 3;
    gBmMapTerrain[y][x] = TERRAIN_NONE;

    // return trap; // BUG
}

struct Trap* RemoveLightRune(struct Trap* trap)
{
    gBmMapTerrain[trap->yPos][trap->xPos] = GetTrueTerrainAt(trap->xPos, trap->yPos);
    return RemoveTrap(trap);
}

void DecayTraps(void)
{
    struct Trap* trap;

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        switch (trap->type)
        {

        case TRAP_TORCHLIGHT:
            trap->extra--;

            if (trap->extra == 0)
            {
                RemoveTrap(trap);
                trap--;
            }

            break;

        case TRAP_LIGHT_RUNE:
            trap->data[TRAP_EXTDATA_RUNE_TURNSLEFT]--;

            if (trap->data[TRAP_EXTDATA_RUNE_TURNSLEFT] == 0)
            {
                RemoveLightRune(trap);
                trap--;
            }

            break;

        } // switch (trap->type)
    }
}

void DisableAllLightRunes(void)
{
    struct Trap* trap;

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        switch (trap->type)
        {

        case TRAP_LIGHT_RUNE:
            gBmMapTerrain[trap->yPos][trap->xPos] = GetTrueTerrainAt(trap->xPos, trap->yPos);
            break;

        } // switch (trap->type)
    }
}

void EnableAllLightRunes(void)
{
    struct Trap* trap;

    for (trap = GetTrap(0); trap->type != TRAP_NONE; ++trap)
    {
        switch (trap->type)
        {

        case TRAP_LIGHT_RUNE:
            gBmMapTerrain[trap->yPos][trap->xPos] = TERRAIN_NONE;
            break;

        } // switch (trap->type)
    }
}
