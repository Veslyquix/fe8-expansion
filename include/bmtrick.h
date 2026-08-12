#ifndef GUARD_BMTRICK_H
#define GUARD_BMTRICK_H

enum
{
    TRAP_MAX_COUNT = 64,
};

enum
{
    TRAP_NONE       = 0,
    TRAP_BALLISTA   = 1,
    TRAP_OBSTACLE   = 2, // walls & snags
    TRAP_MAPCHANGE  = 3,
    TRAP_FIRETILE   = 4,
    TRAP_GAS        = 5,
    TRAP_MAPCHANGE2 = 6, // TODO: figure out
    TRAP_LIGHTARROW = 7,
    TRAP_8          = 8,
    TRAP_9          = 9,
    TRAP_TORCHLIGHT = 10,
    TRAP_MINE       = 11,
    TRAP_GORGON_EGG = 12, // TODO: figure out
    TRAP_LIGHT_RUNE = 13,
    TRAP_14         = 14,
    TRAP_FIRE_THIEF = 15,
    TRAP_MINE_ASSASSIN = 16,
#if FE8_PURCHASE_GENERICS
    TRAP_PURCHASE_BASE = 17,
#endif
};

enum
{
    // Ballista extdata definitions
    TRAP_EXTDATA_BLST_RIDDEN   = 1, // "is ridden" boolean
    TRAP_EXTDATA_BLST_ITEMUSES = 2, // ballista item uses

    // Trap (Fire/Gas/Arrow) extdata definitions
    TRAP_EXTDATA_TRAP_TURNFIRST = 0, // start turn countdown
    TRAP_EXTDATA_TRAP_TURNNEXT  = 1, // repeat turn countdown
    TRAP_EXTDATA_TRAP_COUNTER   = 2, // turn counter
    TRAP_EXTDATA_TRAP_DAMAGE    = 3, // trap damage (needs confirmation)

    // Light Rune extdata definitions
    TRAP_EXTDATA_RUNE_TURNSLEFT        = 2, // turns left beofre wearing out

    // Purchase base extdata definitions
#if FE8_PURCHASE_GENERICS
    TRAP_EXTDATA_PURCHASE_BASE_OWNER   = 0,
    TRAP_EXTDATA_PURCHASE_BASE_KIND    = 1,
    TRAP_EXTDATA_PURCHASE_BASE_CAPTURER = 2,
    TRAP_EXTDATA_PURCHASE_BASE_GOLD_PER_TURN = 3,
#endif
};

#if FE8_PURCHASE_GENERICS
enum
{
    PURCHASE_BASE_KIND_VILLAGE = 1,
    PURCHASE_BASE_KIND_FORT = 2,
    PURCHASE_BASE_KIND_HOUSE = 3,
    PURCHASE_BASE_KIND_GATE = 4,
    PURCHASE_BASE_KIND_THRONE = 5,
    PURCHASE_BASE_OWNER_NEUTRAL = 3,
    PURCHASE_BASE_CAPTURE_NONE = -1,
    PURCHASE_BASE_CAPTURE_REQUIRED = 200,
    PURCHASE_BASE_GOLD_UNIT = 500,
    PURCHASE_BASE_DEFAULT_GOLD_PER_TURN = 2,
};
#endif

struct Trap
{
    /* 00 */ u8 xPos;
    /* 01 */ u8 yPos;

    /* 02 */ u8 type;

    /* 03 */ u8 extra; // extra data (meaning varies based on trap type)
    /* 04 */ s8 data[4]; // more extra data (see above enum for per trap type entry allocations)
};

#define TRAP_INDEX(aTrap) ((aTrap) - GetTrap(0))

void ClearTraps(void);
struct Trap* GetTrapAt(int x, int y);
struct Trap* GetTypedTrapAt(int x, int y, int trapType);
struct Trap* AddTrap(int x, int y, int trapType, int meta);
struct Trap* AddDamagingTrap(int x, int y, int trapType, int meta, int turnCountdown, int turnInterval, int damage);
struct Trap* RemoveTrap(struct Trap* trap);
void AddFireTile(int x, int y, int turnCountdown, int turnInterval);
void AddGasTrap(int x, int y, int facing, int turnCountdown, int turnInterval);
void AddArrowTrap(int x, int turnCountdown, int turnInterval);
void AddMapChangeTrap(int x, int y, int turnCountdown, int turnInterval);
void AddTrap8(int x, int y);
void AddTrap9(int x, int y, int meta);
#if FE8_PURCHASE_GENERICS
struct Trap* AddPurchaseBaseTrap(int x, int y, int owner, int kind);
struct Trap* GetPurchaseBaseTrapAt(int x, int y);
void SetPurchaseBaseTrapOwner(struct Trap* trap, int owner);
int GetPurchaseBaseTrapOwner(struct Trap* trap);
void SetPurchaseBaseTrapCapturer(struct Trap* trap, int capturer);
int GetPurchaseBaseTrapCapturer(struct Trap* trap);
void SetPurchaseBaseTrapCaptureProgress(struct Trap* trap, int progress);
int GetPurchaseBaseTrapCaptureProgress(struct Trap* trap);
void SetPurchaseBaseTrapGoldPerTurn(struct Trap* trap, int amount);
int GetPurchaseBaseTrapGoldPerTurn(struct Trap* trap);
bool IsPurchaseBaseTerrain(int terrain);
void InitPurchaseBaseTrapsFromTerrain(void);
#endif
void InitMapObstacles(void);
void ApplyEnabledMapChanges(void);
void RefreshAllLightRunes(void);
int GetObstacleHpAt(int x, int y);
const struct MapChange* GetMapChange(int id);
int GetMapChangeIdAt(int x, int y);
void ApplyMapChangesById(int mapChangeId);
void EnableMapChange(int mapChangeId);
void DisableMapChange(int id);
s8 IsMapChangeEnabled(int id);
void UnitHideIfUnderRoof(struct Unit* unit);
void UpdateRoofedUnits(void);
void GenerateTrapDamageTargets(void);
void GenerateDisplayedTrapDamageTargets(void);
void CountDownTraps(void);
void ResetCountedDownTraps(void);
void RefreshEntityBmMapsAsRed(void);
void RecordTrapDamageDefeats(void);
void PostTrapExecFlag(void);
struct Trap* AddLightRune(int x, int y);
struct Trap* RemoveLightRune(struct Trap* trap);
void DecayTraps(void);
void DisableAllLightRunes(void);
void EnableAllLightRunes(void);
struct Trap* GetTrap(int id);

#endif // GUARD_BMTRICK_H
