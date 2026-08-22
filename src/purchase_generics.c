#include "global.h"

#if FE8_PURCHASE_GENERICS

#include "constants/characters.h"
#include "constants/classes.h"
#include "constants/items.h"
#include "constants/songs.h"
#include "constants/terrains.h"

#include "bm.h"
#include "banim_data.h"
#include "bmidoten.h"
#include "bmlib.h"
#include "hardware.h"
#include "bmio.h"
#include "bmitem.h"
#include "bmmap.h"
#include "bmmind.h"
#include "uimenu.h"
#include "bmmenu.h"
#include "bmunit.h"
#include "bmudisp.h"
#include "bmtrick.h"
#include "classchg.h"
#include "ctc.h"
#include "efxbattle.h"
#include "ekrbattle.h"
#include "face.h"
#include "fontgrp.h"
#include "icon.h"
#include "m4a.h"
#include "menu_def.h"
#include "purchase_generics.h"
#include "rng.h"
#include "soundwrapper.h"
#include "uiutils.h"
#include "opinfo.h"
#include "helpbox.h"
#include "statscreen.h"

#define PURCHASE_GENERIC_PAGE_SIZE 7
// #define PURCHASE_GENERIC_PAGE_SLOT 5
#define PURCHASE_GENERIC_FACE_SLOT 0
#define PURCHASE_GENERIC_PLATFORM_TERRAIN 0x3F
#define PURCHASE_GENERIC_PLATFORM_X 212
#define PURCHASE_GENERIC_PLATFORM_Y 132
#define PURCHASE_GENERIC_PLATFORM_BG_X 130
#define PURCHASE_GENERIC_PLATFORM_BG_Y 138
#define PURCHASE_GENERIC_REEL_ENTRY_COUNT 65

// Palette bg IDs 0xB (class card) and 0xF (battle animation spells) won't work with fog
// so a BG must be set when working with fog maps, I guess

struct PurchaseGenericDefinition
{
    const char* name;
    u8 classId;
    u32 cost;
    u8 items[UNIT_DEFINITION_ITEM_COUNT];
};

static int sPurchaseGenericPage = 0;
static int sPurchaseGenericBaseX = 0;
static int sPurchaseGenericBaseY = 0;
static int sPurchaseGenericFactionId = FACTION_ID_BLUE;
static bool sPurchaseGenericFaceActive = false;
static bool sPurchaseGenericPlatformActive = false;
static bool sPurchaseGenericMenuOpen = false;
static bool sPurchaseGenericPreviewStartedMiniAnim = false;
static u8 sPurchaseGenericSavedBg0Priority = 0;

struct PurchaseGenericMenuLockProc
{
    PROC_HEADER;
};

static void DrawPurchaseGenericDetails(const struct PurchaseGenericDefinition* def);
static void StartPurchaseGenericMenuLockProc(void);
static void EndPurchaseGenericMenuLockProc(void);
static void PurchaseGenericPlatformPreview_ResetScript(struct OpInfoClassDisplayProc* proc);

static const struct ProcCmd sProc_PurchaseGenericPlatformPreview[];

extern u8 Tsa_PurchaseGenericPortraitBox[];
extern u8 Tsa_PurchaseGenericCostBox[];
extern u8 Tsa_PurchaseGenericItemBox[];
extern u8 Tsa_PurchaseGenericBottomStats[];
extern u8 Tsa_PurchaseGenericTopStats[];

void EndBanimTerrain(struct BanimUnkStructComm* buf);
void InitBanimTerrain(struct BanimUnkStructComm* buf);
void SetBanimTerrainPos(struct BanimUnkStructComm* buf, s16 x1, s16 y1, s16 x2, s16 y2);

static const struct PurchaseGenericDefinition sPurchaseGenericDefinitions[] =
{
    { "Soldier", CLASS_SOLDIER, 1000, { ITEM_LANCE_IRON, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Knight", CLASS_ARMOR_KNIGHT, 1800, { ITEM_LANCE_IRON, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Pegasus", CLASS_PEGASUS_KNIGHT, 2500, { ITEM_LANCE_IRON, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Cavalier", CLASS_CAVALIER, 2200, { ITEM_SWORD_IRON, ITEM_LANCE_IRON, ITEM_NONE, ITEM_NONE } },
    { "Fighter", CLASS_FIGHTER, 1400, { ITEM_AXE_IRON, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Mercenary", CLASS_MERCENARY, 1800, { ITEM_SWORD_IRON, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Archer", CLASS_ARCHER, 1400, { ITEM_BOW_IRON, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Mage", CLASS_MAGE, 1800, { ITEM_ANIMA_FIRE, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Dancer", CLASS_DANCER, 4000, { ITEM_NONE, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Cleric", CLASS_CLERIC, 1600, { ITEM_STAFF_HEAL, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Brigand", CLASS_BRIGAND, 1400, { ITEM_AXE_IRON, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Paladin", CLASS_PALADIN, 9000, { ITEM_SWORD_IRON, ITEM_LANCE_IRON, ITEM_NONE, ITEM_NONE } },
    { "Hero", CLASS_HERO, 8500, { ITEM_SWORD_IRON, ITEM_AXE_IRON, ITEM_NONE, ITEM_NONE } },
    { "Warrior", CLASS_WARRIOR, 8000, { ITEM_AXE_IRON, ITEM_BOW_IRON, ITEM_NONE, ITEM_NONE } },
    { "Sniper", CLASS_SNIPER, 8000, { ITEM_BOW_IRON, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "General", CLASS_GENERAL, 8500, { ITEM_LANCE_IRON, ITEM_NONE, ITEM_NONE, ITEM_NONE } },
    { "Sage", CLASS_SAGE, 9000, { ITEM_ANIMA_FIRE, ITEM_STAFF_HEAL, ITEM_NONE, ITEM_NONE } },
    { "Bishop", CLASS_BISHOP, 9000, { ITEM_LIGHT_LIGHTNING, ITEM_STAFF_HEAL, ITEM_NONE, ITEM_NONE } },
};

static struct ClassReelAnimScr CONST_DATA sPurchaseGenericPlatformScript[] =
{
    { CLASS_REEL_OP_5, 0x28 },
    { CLASS_REEL_OP_1, 0 },
    { CLASS_REEL_OP_8, 0 },
    { CLASS_REEL_OP_5, 0x28 },
    { CLASS_REEL_OP_3, 0 },
    { CLASS_REEL_OP_0, 0 },
};

static struct ClassReelEnt sPurchaseGenericFallbackReelEntry;

static int GetPurchaseGenericCount(void)
{
    return sizeof(sPurchaseGenericDefinitions) / sizeof(sPurchaseGenericDefinitions[0]);
}

static int GetPurchaseGenericPageCount(void)
{
    return (GetPurchaseGenericCount() + PURCHASE_GENERIC_PAGE_SIZE - 1) / PURCHASE_GENERIC_PAGE_SIZE;
}

static const struct PurchaseGenericDefinition* GetPurchaseGenericForSlot(int slot)
{
    int index = sPurchaseGenericPage * PURCHASE_GENERIC_PAGE_SIZE + slot;

    if (index < 0 || index >= GetPurchaseGenericCount())
        return NULL;

    return sPurchaseGenericDefinitions + index;
}

static const struct PurchaseGenericDefinition* GetPurchaseGenericByClass(int classId)
{
    int i;

    for (i = 0; i < GetPurchaseGenericCount(); ++i)
    {
        if (sPurchaseGenericDefinitions[i].classId == classId)
            return sPurchaseGenericDefinitions + i;
    }

    return NULL;
}

static void SetPurchaseGenericMenuPage(struct MenuProc* menu, int page)
{
    int pageCount = GetPurchaseGenericPageCount();

    if (page < 0)
        page = pageCount - 1;

    if (page >= pageCount)
        page = 0;

    sPurchaseGenericPage = page;

    if (GetPurchaseGenericForSlot(menu->itemCurrent) == NULL)
        menu->itemCurrent = 0;

    RedrawMenu(menu);
    DrawPurchaseGenericDetails(GetPurchaseGenericForSlot(menu->itemCurrent));
}

static int GetFactionIdForUnit(struct Unit* unit)
{
    return UNIT_FACTION(unit) >> 6;
}

static int GetCurrentFactionId(void)
{
    return gPlaySt.faction >> 6;
}

static bool CanUnitCapturePurchaseBase(struct Unit* unit)
{
    switch (unit->pClassData->number)
    {
    case CLASS_SOLDIER:
    case CLASS_ARMOR_KNIGHT:
    case CLASS_GENERAL:
        return true;

    default:
        return false;
    }
}

static bool IsPurchaseGenericBaseTile(int x, int y)
{
    if (x < 0 || y < 0 || x >= gBmMapSize.x || y >= gBmMapSize.y)
        return false;

    return IsPurchaseBaseTerrain(gBmMapTerrain[y][x]);
}

static int GetPurchaseBaseKindAt(int x, int y)
{
    switch (gBmMapTerrain[y][x])
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

static struct Trap* GetOrCreatePurchaseBaseTrapAt(int x, int y)
{
    struct Trap* trap = GetPurchaseBaseTrapAt(x, y);

    if (trap != NULL)
        return trap;

    if (!IsPurchaseGenericBaseTile(x, y))
        return NULL;

    return AddPurchaseBaseTrap(x, y, PURCHASE_BASE_OWNER_NEUTRAL, GetPurchaseBaseKindAt(x, y));
}

static bool CanUsePurchaseBaseNow(struct Unit* unit)
{
    struct Trap* trap;
    int owner;

    if (unit == NULL)
        return false;

    if (unit->pClassData->number == CLASS_PHANTOM)
        return false;

    if (unit->state & US_HAS_MOVED)
        return false;

    trap = GetOrCreatePurchaseBaseTrapAt(unit->xPos, unit->yPos);

    if (trap == NULL)
        return false;

    owner = GetPurchaseBaseTrapOwner(trap);

    if (owner == GetFactionIdForUnit(unit))
        return false;

    return CanUnitCapturePurchaseBase(unit);
}

static int GetCaptureAmountForUnit(struct Unit* unit)
{
    int maxHp = GetUnitMaxHp(unit);
    int curHp = GetUnitCurrentHp(unit);

    if (maxHp <= 0 || curHp <= 0)
        return 1;

    return (curHp * 10) / maxHp;
}

static bool TryCapturePurchaseBase(struct Trap* trap, struct Unit* unit)
{
    int factionId = GetFactionIdForUnit(unit);
    int progress;

    if (GetPurchaseBaseTrapOwner(trap) == factionId)
        return true;

    if (GetPurchaseBaseTrapCapturer(trap) == PURCHASE_BASE_CAPTURE_NONE ||
        (u8)GetPurchaseBaseTrapCapturer(trap) != (u8)unit->index)
    {
        SetPurchaseBaseTrapCapturer(trap, unit->index);
        SetPurchaseBaseTrapCaptureProgress(trap, 0);
    }

    progress = GetPurchaseBaseTrapCaptureProgress(trap) + GetCaptureAmountForUnit(unit);

    if (progress >= PURCHASE_BASE_CAPTURE_REQUIRED)
    {
        SetPurchaseBaseTrapOwner(trap, factionId);
        SetPurchaseBaseTrapCapturer(trap, PURCHASE_BASE_CAPTURE_NONE);
        SetPurchaseBaseTrapCaptureProgress(trap, 0);

        // House/Fort are drawn in the new owner's faction palette
        // (RefreshUnitSprites) -- redraw immediately so the recolor is
        // visible the moment capture completes, not just on the next
        // unrelated map refresh.
        RefreshUnitSprites();
        ForceSyncUnitSpriteSheet();

        return true;
    }

    SetPurchaseBaseTrapCaptureProgress(trap, progress);
    return false;
}

static int FindSpawnPositionFrom(int baseX, int baseY, int classId, int* xOut, int* yOut)
{
    static const s8 offsets[][2] =
    {
        { 0, -1 },
        { 1, 0 },
        { 0, 1 },
        { -1, 0 },
        { 1, -1 },
        { 1, 1 },
        { -1, 1 },
        { -1, -1 },
    };

    const struct ClassData* class = GetClassData(classId);
    const s8* movCost = class->pMovCostTable[0];
    int i;

    for (i = 0; i < (int)(sizeof(offsets) / sizeof(offsets[0])); ++i)
    {
        int x = baseX + offsets[i][0];
        int y = baseY + offsets[i][1];
        int terrain;

        if (x < 0 || y < 0 || x >= gBmMapSize.x || y >= gBmMapSize.y)
            continue;

        if (gBmMapUnit[y][x] != 0)
            continue;

        if (gBmMapHidden[y][x] & HIDDEN_BIT_UNIT)
            continue;

        terrain = gBmMapTerrain[y][x];

        if (movCost[terrain] < 0)
            continue;

        *xOut = x;
        *yOut = y;
        return true;
    }

    return false;
}

static void BuildGenericUnitDefinition(
    const struct PurchaseGenericDefinition* def,
    int factionId,
    int x,
    int y,
    struct UnitDefinition* out)
{
    int i;

    CpuFill16(0, out, sizeof(*out));

    out->charIndex = CHARACTER_CITIZEN;
    out->classIndex = def->classId;
    out->leaderCharIndex = CHARACTER_NONE;
    out->autolevel = false;
    out->allegiance = factionId;
    out->level = 1;
    out->xPosition = x;
    out->yPosition = y;

    for (i = 0; i < UNIT_DEFINITION_ITEM_COUNT; ++i)
        out->items[i] = def->items[i];
}

#if FE8_FORT_UNITS_START_GREYED_OUT
static bool TryFortSpawnPosition(int baseX, int baseY, int* xOut, int* yOut)
{
    if (GetPurchaseBaseKindAt(baseX, baseY) != PURCHASE_BASE_KIND_FORT)
        return false;

    if (gBmMapUnit[baseY][baseX] != 0)
        return false;

    if (gBmMapHidden[baseY][baseX] & HIDDEN_BIT_UNIT)
        return false;

    *xOut = baseX;
    *yOut = baseY;
    return true;
}
#endif

static bool PurchaseGenericUnitForFaction(const struct PurchaseGenericDefinition* def, int factionId, int baseX, int baseY)
{
    struct UnitDefinition uDef;
    struct Unit* unit;
    int x, y;
    bool spawnedOnFort = false;

    if (GetFactionChapterGoldAmount(factionId) < def->cost)
        return false;

#if FE8_FORT_UNITS_START_GREYED_OUT
    spawnedOnFort = TryFortSpawnPosition(baseX, baseY, &x, &y);
#endif

    if (!spawnedOnFort && !FindSpawnPositionFrom(baseX, baseY, def->classId, &x, &y))
        return false;

    BuildGenericUnitDefinition(def, factionId, x, y, &uDef);

    unit = LoadUnit(&uDef);

    if (unit == NULL)
        return false;

#if FE8_FORT_UNITS_START_GREYED_OUT
    if (spawnedOnFort)
        unit->state |= US_HAS_MOVED;
#endif

    SubFactionChapterGoldAmount(factionId, def->cost);

    RefreshEntityBmMaps();
    RenderBmMap();
    RefreshUnitSprites();
    ForceSyncUnitSpriteSheet();

    return true;
}

static const char* GetPurchaseGenericClassName(const struct PurchaseGenericDefinition* def)
{
    const struct ClassData* class;
    const char* name;

    if (def == NULL)
        return "";

    class = GetClassData(def->classId);

    if (class != NULL && class->nameTextId != 0)
    {
        name = GetStringFromIndex(class->nameTextId);

        if (name != NULL && name[0] != '\0')
            return name;
    }

    return def->name;
}

static u8 GetPurchaseGenericOptionAvailability(const struct PurchaseGenericDefinition* def)
{
    int x, y;

    if (def == NULL)
        return MENU_NOTSHOWN;

    if (GetFactionChapterGoldAmount(sPurchaseGenericFactionId) < def->cost)
        return MENU_DISABLED;

    if (!FindSpawnPositionFrom(sPurchaseGenericBaseX, sPurchaseGenericBaseY, def->classId, &x, &y))
        return MENU_DISABLED;

    return MENU_ENABLED;
}

static void PutPurchaseGenericText(int x, int y, int color, int width, const char* str)
{
    struct Text text;

    InitText(&text, width);
    PutDrawText(&text, TILEMAP_LOCATED(gBG0TilemapBuffer, x, y), color, 0, width, str);
}

static void PutPurchaseGenericTextIndent(int x, int y, int color, int width, const char* str)
{
    struct Text text;

    InitText(&text, width);
    Text_SetCursor(&text, 2);
    PutDrawText(&text, TILEMAP_LOCATED(gBG0TilemapBuffer, x, y), color, 0, width, str);
}


static void PutPurchaseGenericBaseStat(int y, const char* label, int base)
{
    PutPurchaseGenericText(2, y, TEXT_COLOR_SYSTEM_GOLD, 3, label);
    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, 6, y), TEXT_COLOR_SYSTEM_BLUE, base);
}

static void PutPurchaseGenericGoldAmount(int x, int y, int amount)
{
    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, x, y), TEXT_COLOR_SYSTEM_BLUE, amount);
    PutSpecialChar(TILEMAP_LOCATED(gBG0TilemapBuffer, x + 1, y), TEXT_COLOR_SYSTEM_GOLD, TEXT_SPECIAL_G);
}

static void EndPurchaseGenericClassCard(void)
{
    if (sPurchaseGenericFaceActive && gFaces[PURCHASE_GENERIC_FACE_SLOT] != NULL)
        EndFaceById(PURCHASE_GENERIC_FACE_SLOT);

    sPurchaseGenericFaceActive = false;
}

static void StartPurchaseGenericClassCard(const struct PurchaseGenericDefinition* def)
{
    const struct ClassData* class;
    int portraitId;

    EndPurchaseGenericClassCard();

    if (def == NULL)
        return;

    class = GetClassData(def->classId);

    if (class == NULL)
        return;

    portraitId = class->defaultPortraitId;

    if (portraitId == 0 || gFaces[PURCHASE_GENERIC_FACE_SLOT] != NULL)
        return;

    PutFace80x72_Core(gBG0TilemapBuffer + TILEMAP_INDEX(20, 1), portraitId, 0x180, 0xB);
    BG_EnableSyncByMask(BG0_SYNC_BIT | BG2_SYNC_BIT);
    // if (StartFace(
        // PURCHASE_GENERIC_FACE_SLOT,
        // portraitId,
        // 160,
        // 0,
        // FACE_DISP_KIND(FACE_96x80) | FACE_DISP_HLAYER(FACE_HLAYER_1)) != NULL)
        // sPurchaseGenericFaceActive = true;
}

// Picks a plausible tome/staff for classes previewed without a matching real
// weapon defined for the generic, matching vanilla's own per-class defaults:
// anima->Fire (Elfire once promoted), light->Lightning (Shine), dark->Flux
// (Luna), staff->Heal (Mend). Whichever the class's actual rank array grants
// first.
static int GetPurchaseGenericDefaultSpellItem(const struct ClassData* class)
{
    bool promoted = (class->attributes & CA_PROMOTED) != 0;

    if (class->baseRanks[ITYPE_ANIMA])
        return promoted ? ITEM_ANIMA_ELFIRE : ITEM_ANIMA_FIRE;
    if (class->baseRanks[ITYPE_LIGHT])
        return promoted ? ITEM_LIGHT_SHINE : ITEM_LIGHT_LIGHTNING;
    if (class->baseRanks[ITYPE_DARK])
        return promoted ? ITEM_DARK_LUNA : ITEM_DARK_FLUX;
    if (class->baseRanks[ITYPE_STAFF])
        return promoted ? ITEM_STAFF_MEND : ITEM_STAFF_HEAL;

    return ITEM_NONE;
}

// gClassReelSpellAnimFuncLut indices (banim-efxop.c): 0 none, 1 fire,
// 2 thunder, 3 heal, 4 light, 5 flux. Promotion doesn't change which of
// these plays (Fire and Elfire share the same cast effect), only which item
// GetPurchaseGenericDefaultSpellItem would hand out.
static int GetPurchaseGenericDefaultMagicFx(const struct ClassData* class)
{
    if (class->baseRanks[ITYPE_ANIMA])
        return 1;
    if (class->baseRanks[ITYPE_LIGHT])
        return 4;
    if (class->baseRanks[ITYPE_DARK])
        return 5;
    if (class->baseRanks[ITYPE_STAFF])
        return 3;

    return 0;
}

static int GetPurchaseGenericPlatformAnimId(const struct PurchaseGenericDefinition* def)
{
    const struct ClassData* class;
    const struct BattleAnimDef* animDef;
    int i;
    int item = 0;
    int expectedType;

    if (def == NULL)
        return 0;

    class = GetClassData(def->classId);

    if (class == NULL || class->pBattleAnimDef == NULL)
        return 0;

    animDef = class->pBattleAnimDef;

    if (def->items[0] != ITEM_NONE)
        item = MakeNewItem(def->items[0]);

    expectedType = item != 0 ? (GetItemType(item) + 0x100) : SPECIAL_BANIM_WTYPE;

    for (i = 0; animDef[i].index != 0; ++i)
    {
        if (animDef[i].wtype == expectedType)
            return animDef[i].index - 1;
    }

    // the generic's defined item (if any) doesn't match anything this
    // class's animDef has - if the class can actually cast, try its default
    // spell before giving up to the unarmed/special case below
    item = GetPurchaseGenericDefaultSpellItem(class);
    if (item != ITEM_NONE)
    {
        expectedType = GetItemType(item) + 0x100;

        for (i = 0; animDef[i].index != 0; ++i)
        {
            if (animDef[i].wtype == expectedType)
                return animDef[i].index - 1;
        }
    }

    for (i = 0; animDef[i].index != 0; ++i)
    {
        if (animDef[i].wtype == SPECIAL_BANIM_WTYPE)
            return animDef[i].index - 1;
    }

    return 0;
}

static struct ClassReelEnt* GetPurchaseGenericPlatformReelEntry(const struct PurchaseGenericDefinition* def)
{
    int i;
    const struct ClassData* class;

    if (def == NULL)
        return NULL;

    for (i = 0; i < PURCHASE_GENERIC_REEL_ENTRY_COUNT; i++)
    {
        if (gClassReelData[i].classId == def->classId)
            return &gClassReelData[i];
    }

    class = GetClassData(def->classId);

    sPurchaseGenericFallbackReelEntry.descTextId = 0;
    sPurchaseGenericFallbackReelEntry.paletteId = -1;
    sPurchaseGenericFallbackReelEntry.classId = def->classId;
    sPurchaseGenericFallbackReelEntry.unk_06 = 0;
    sPurchaseGenericFallbackReelEntry.banimId = GetPurchaseGenericPlatformAnimId(def);
    sPurchaseGenericFallbackReelEntry.magicFx = class != NULL ? GetPurchaseGenericDefaultMagicFx(class) : 0;
    sPurchaseGenericFallbackReelEntry.unk_09 = 0;
    sPurchaseGenericFallbackReelEntry.unk_0A = 0;
    sPurchaseGenericFallbackReelEntry.unk_0B = 0;
    sPurchaseGenericFallbackReelEntry.unk_0C = 0;
    sPurchaseGenericFallbackReelEntry.unk_0D = PURCHASE_GENERIC_PLATFORM_TERRAIN;
    sPurchaseGenericFallbackReelEntry.unk_0E = PURCHASE_GENERIC_PLATFORM_TERRAIN;
    sPurchaseGenericFallbackReelEntry.unk_0F = 0;
    sPurchaseGenericFallbackReelEntry.script = sPurchaseGenericPlatformScript;

    return &sPurchaseGenericFallbackReelEntry;
}

static void EndPurchaseGenericPlatformPreview(void)
{
    if (!sPurchaseGenericPlatformActive)
        return;

    Proc_EndEach(sProc_PurchaseGenericPlatformPreview);
}

static bool IsPurchaseGenericPlatformBanimSafe(struct ClassReelEnt* entry)
{
    struct BattleAnim* anim;
    int paletteId;

    if (entry == NULL || entry->banimId >= banim_number)
        return false;

    anim = &banim_data[entry->banimId];

    if (!IsValidLz77DecompressionData(anim->script) ||
        !IsValidLz77DecompressionData(anim->oam_r) ||
        !IsValidLz77DecompressionData(anim->oam_l) ||
        !IsValidLz77DecompressionData(anim->pal))
        return false;

    paletteId = entry->paletteId;

    if (paletteId != -1)
    {
        if (paletteId < 0 || (u32)paletteId >= banim_pal_head.number)
            return false;

        if (!IsValidLz77DecompressionData(character_battle_animation_palette_table[paletteId].pal))
            return false;
    }

    return true;
}

static void SetPurchaseGenericPlatformAnimLayer(u16 layer)
{
    if (gOpInfoData.anim1 != NULL)
    {
        gOpInfoData.anim1->oam2Base &= ~OAM2_LAYER(3);
        gOpInfoData.anim1->oam2Base |= OAM2_LAYER(layer);
    }

    if (gOpInfoData.anim2 != NULL)
    {
        gOpInfoData.anim2->oam2Base &= ~OAM2_LAYER(3);
        gOpInfoData.anim2->oam2Base |= OAM2_LAYER(layer);
    }
}

static void SetupPurchaseGenericPlatformAnim(struct OpInfoClassDisplayProc* proc, struct ClassReelEnt* entry)
{
    NewEfxAnimeDrvProc();

    gOpInfoData.charPalId = entry->paletteId;
    gOpInfoData.xPos = PURCHASE_GENERIC_PLATFORM_X;
    gOpInfoData.yPos = PURCHASE_GENERIC_PLATFORM_Y;
    gOpInfoData.animId = entry->banimId;
    gOpInfoData.roundType = ANIM_ROUND_TAKING_HIT_CLOSE;
    gOpInfoData.genericPalId = entry->unk_06;
    gOpInfoData.state2 = 1;
    gOpInfoData.oam2Tile = 0x200;
    gOpInfoData.oam2Pal = 0xA;
    gOpInfoData.pImgSheetBuf = gBanimLeftImgSheetBuf;
    gOpInfoData.unk_24 = gBanimOaml;
    gOpInfoData.unk_20 = gBanimPaletteLeft;
    gOpInfoData.unk_28 = gBanimScrLeft;
    gOpInfoData.unk_30 = &gUnk_4;

    gUnk_4.magicFuncIdx = entry->magicFx;
    gUnk_4.xOffsetBg = entry->unk_09;
    gUnk_4.yOffsetBg = entry->unk_0A;
    gUnk_4.xOffsetObj = entry->unk_0B;
    gUnk_4.yOffsetObj = entry->unk_0C;
    gUnk_4.objChr = 0x300;
    gUnk_4.objPalId = 0xD;
    gUnk_4.bgChr = 0x1E0; 
    gUnk_4.bgPalId = 0xD;
    gUnk_4.bg = 1;
    gUnk_4.bgTmBuf = gBG1TilemapBuffer;
    gUnk_4.bgImgBuf = gSpellAnimBgfx;
    gUnk_4.bgTsaBuf = gEkrTsaBuffer;
    gUnk_4.objImgBuf = gBuf_Banim;
    gUnk_4.resetCallback = ClassChgSel_SetBlendWindowConfig;

    ResetClassReelSpell();
    NewEkrUnitMainMini(&gOpInfoData);
    sPurchaseGenericPreviewStartedMiniAnim = true;
    SetPurchaseGenericPlatformAnimLayer(0);

    gUnk_Opinfo_0.terrain_l = PURCHASE_GENERIC_PLATFORM_TERRAIN;
    gUnk_Opinfo_0.pal_l = 0xE;
    gUnk_Opinfo_0.chr_l = 0x380; // unused here 
    gUnk_Opinfo_0.terrain_r = PURCHASE_GENERIC_PLATFORM_TERRAIN;
    gUnk_Opinfo_0.pal_r = 0xF;
    gUnk_Opinfo_0.chr_r = 0x3C0; 
    gUnk_Opinfo_0.distance = 0;
    gUnk_Opinfo_0.unk0E = -1;
    gUnk_Opinfo_0.unk1C = (void*)0x06010000;
    gUnk_Opinfo_0.unk20 = gUnk_Banim_Ekrbattle_0;

    InitBanimTerrain(&gUnk_Opinfo_0);
    SetBanimTerrainPos(
        &gUnk_Opinfo_0,
        PURCHASE_GENERIC_PLATFORM_BG_X,
        PURCHASE_GENERIC_PLATFORM_BG_Y,
        PURCHASE_GENERIC_PLATFORM_BG_X + 0x60,
        PURCHASE_GENERIC_PLATFORM_BG_Y);

    proc->classReelEnt = entry;
    PurchaseGenericPlatformPreview_ResetScript(proc);
}

static void StartPurchaseGenericPlatformPreview(const struct PurchaseGenericDefinition* def)
{
    struct OpInfoClassDisplayProc* proc;
    struct ClassReelEnt* entry;

    EndPurchaseGenericPlatformPreview();

    if (def == NULL)
        return;

    entry = GetPurchaseGenericPlatformReelEntry(def);

    if (!IsPurchaseGenericPlatformBanimSafe(entry))
        return;

    proc = Proc_Start(sProc_PurchaseGenericPlatformPreview, PROC_TREE_3);
    SetupPurchaseGenericPlatformAnim(proc, entry);

    sPurchaseGenericPlatformActive = true;
}
#define FUNDS_Y 0
static void DrawPurchaseGenericUiBoxes(const struct PurchaseGenericDefinition* def)
{
    int i;

    CallARM_FillTileRect(TILEMAP_LOCATED(gBG2TilemapBuffer, 0, 0), Tsa_PurchaseGenericTopStats, 0);
    CallARM_FillTileRect(TILEMAP_LOCATED(gBG2TilemapBuffer, 0, 5), Tsa_PurchaseGenericBottomStats, 0);
    CallARM_FillTileRect(TILEMAP_LOCATED(gBG2TilemapBuffer, 19, 0), Tsa_PurchaseGenericPortraitBox, 0);

    if (def == NULL)
        return;

    CallARM_FillTileRect(TILEMAP_LOCATED(gBG2TilemapBuffer, 9, FUNDS_Y), Tsa_PurchaseGenericCostBox, 0);

    // for (i = 0; i < UNIT_DEFINITION_ITEM_COUNT && def->items[i] != ITEM_NONE; ++i)
    // {
        // static const u8 itemBoxX[] = { 28, 26, 28, 26 };
        // static const u8 itemBoxY[] = { 11, 11, 13, 13 };

        // CallARM_FillTileRect(
            // TILEMAP_LOCATED(gBG2TilemapBuffer, itemBoxX[i], itemBoxY[i]),
            // Tsa_PurchaseGenericItemBox,
            // 0);
    // }
}
#define GENERICS_MENU_X 9
#define GENERICS_MENU_Y 4
static void DrawPurchaseGenericList(void)
{
    int i;

    for (i = 0; i < PURCHASE_GENERIC_PAGE_SIZE; ++i)
    {
        const struct PurchaseGenericDefinition* def = GetPurchaseGenericForSlot(i);
        int color;

        if (def == NULL)
            continue;

        color = GetPurchaseGenericOptionAvailability(def) == MENU_ENABLED
            ? TEXT_COLOR_SYSTEM_GOLD
            : TEXT_COLOR_SYSTEM_GRAY;

        PutPurchaseGenericText(GENERICS_MENU_X+1, GENERICS_MENU_Y + 1 + i * 2, color, 7, GetPurchaseGenericClassName(def));
    }

    PutPurchaseGenericText(22, 18, TEXT_COLOR_SYSTEM_GREEN, 4, "Page");
    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, 26, 18), TEXT_COLOR_SYSTEM_BLUE, sPurchaseGenericPage + 1);
    PutSpecialChar(TILEMAP_LOCATED(gBG0TilemapBuffer, 27, 18), TEXT_COLOR_SYSTEM_WHITE, TEXT_SPECIAL_SLASH);
    PutNumber(TILEMAP_LOCATED(gBG0TilemapBuffer, 28, 18), TEXT_COLOR_SYSTEM_BLUE, GetPurchaseGenericPageCount());
}
/*
static void DrawPurchaseGenericStartingItems(const struct PurchaseGenericDefinition* def)
{
    int i;

    if (def == NULL)
        return;

    TileMap_FillRect(gBG0TilemapBuffer + TILEMAP_INDEX(26, 11), 4, 4, 0);
    TileMap_FillRect(gBG2TilemapBuffer + TILEMAP_INDEX(26, 11), 4, 4, 0);
    BG_EnableSyncByMask(BG0_SYNC_BIT|BG2_SYNC_BIT);
    for (i = 0; i < UNIT_DEFINITION_ITEM_COUNT && def->items[i] != ITEM_NONE; ++i)
    {
        static const u8 itemIconX[] = { 28, 26, 28, 26 };
        static const u8 itemIconY[] = { 11, 11, 13, 13 };
        int item = MakeNewItem(def->items[i]);

        DrawIcon(
            TILEMAP_LOCATED(gBG0TilemapBuffer, itemIconX[i], itemIconY[i]),
            GetItemIconId(item),
            TILEREF(0, 0xC));
    }

    // if (def->items[0] == ITEM_NONE)
        // PutPurchaseGenericText(22, 14, TEXT_COLOR_SYSTEM_GRAY, 4, "None");

    LoadIconPalettes(0xC);
}
*/
static void DrawPurchaseGenericGoldPanel(const struct PurchaseGenericDefinition* def)
{
    if (def == NULL)
        return;

    PutPurchaseGenericText(9, FUNDS_Y, TEXT_COLOR_SYSTEM_GOLD, 4, " Funds:");
    PutPurchaseGenericGoldAmount(17, FUNDS_Y, GetFactionChapterGoldAmount(sPurchaseGenericFactionId));

    PutPurchaseGenericText(9, FUNDS_Y+2, TEXT_COLOR_SYSTEM_GOLD, 4, " Cost:");
    PutPurchaseGenericGoldAmount(17, FUNDS_Y+2, def->cost);
}

static void DrawPurchaseGenericDetails(const struct PurchaseGenericDefinition* def)
{
    const struct ClassData* class = NULL;

    // TileMap_FillRect(gBG2TilemapBuffer, 30, 20, 0);
    TileMap_FillRect(gBG0TilemapBuffer, 30, 20, 0);
    TileMap_FillRect(gBG1TilemapBuffer, 30, 20, 0);
    EndPurchaseGenericPlatformPreview();
    ResetIconGraphics();
    ResetTextFont();

    DrawPurchaseGenericUiBoxes(def);
    DrawPurchaseGenericList();

    if (def == NULL)
    {
        EndPurchaseGenericClassCard();
        BG_EnableSyncByMask(BG0_SYNC_BIT | BG2_SYNC_BIT);
        return;
    }

    class = GetClassData(def->classId);

    PutPurchaseGenericTextIndent(1, 1, TEXT_COLOR_SYSTEM_GOLD, 7, GetPurchaseGenericClassName(def));
    PutPurchaseGenericText(4, 3, TEXT_COLOR_SYSTEM_GOLD, 4, "Base");

    if (class != NULL)
    {
        PutPurchaseGenericBaseStat(5, "HP", class->baseHP);
        PutPurchaseGenericBaseStat(7, "Pow", class->basePow);
        PutPurchaseGenericBaseStat(9, "Skl", class->baseSkl);
        PutPurchaseGenericBaseStat(11, "Spd", class->baseSpd);
        PutPurchaseGenericBaseStat(13, "Def", class->baseDef);
        PutPurchaseGenericBaseStat(15, "Res", class->baseRes);
        PutPurchaseGenericBaseStat(17, "Mov", class->baseMov);
    }

    DrawPurchaseGenericGoldPanel(def);
    // DrawPurchaseGenericStartingItems(def);
    StartPurchaseGenericClassCard(def);
    StartPurchaseGenericPlatformPreview(def);

    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT | BG2_SYNC_BIT);
}

static void ClearPurchaseGenericDetails(void)
{
    EndPurchaseGenericPlatformPreview();
    EndPurchaseGenericClassCard();
    ResetIconGraphics();
    ApplyUnitSpritePalettes();
    TileMap_FillRect(gBG2TilemapBuffer, 30, 20, 0);
    TileMap_FillRect(gBG1TilemapBuffer, 30, 20, 0);
    TileMap_FillRect(gBG0TilemapBuffer, 30, 20, 0);
    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT | BG2_SYNC_BIT);
}

static u8 PurchaseGenericMenuItemUsability(const struct MenuItemDef* def, int number)
{
    const struct PurchaseGenericDefinition* purchaseDef = GetPurchaseGenericForSlot(number);

    (void)def;

    return GetPurchaseGenericOptionAvailability(purchaseDef);
}

static int PurchaseGenericMenuItemDraw(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    (void)menu;
    ClearText(&menuItem->text);

    return 0;
}

static u8 PurchaseGenericMenuItemSelect(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    const struct PurchaseGenericDefinition* def = GetPurchaseGenericForSlot(menuItem->itemNumber);

    if (def == NULL || menuItem->availability == MENU_DISABLED)
    {
        (void)menu;
        return MENU_ACT_SND6B;
    }

    if (!PurchaseGenericUnitForFaction(def, sPurchaseGenericFactionId, sPurchaseGenericBaseX, sPurchaseGenericBaseY))
        return MENU_ACT_SND6B;

    ClearPurchaseGenericDetails();

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

static int PurchaseGenericMenuItemSwitchIn(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    (void)menu;

    DrawPurchaseGenericDetails(GetPurchaseGenericForSlot(menuItem->itemNumber));

    return 0;
}

static u8 PurchaseGenericMenuItemIdle(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    (void)menuItem;

    if (gKeyStatusPtr->newKeys & DPAD_LEFT)
    {
        SetPurchaseGenericMenuPage(menu, sPurchaseGenericPage - 1);

        return MENU_ACT_SKIPCURSOR | MENU_ACT_SND6A;
    }

    if (gKeyStatusPtr->newKeys & DPAD_RIGHT)
    {
        SetPurchaseGenericMenuPage(menu, sPurchaseGenericPage + 1);

        return MENU_ACT_SKIPCURSOR | MENU_ACT_SND6A;
    }

    return 0;
}

static u8 PurchaseGenericPageIdle(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    (void)menuItem;

    if (gKeyStatusPtr->newKeys & DPAD_LEFT)
    {
        SetPurchaseGenericMenuPage(menu, sPurchaseGenericPage - 1);

        return MENU_ACT_SKIPCURSOR | MENU_ACT_SND6A;
    }

    if (gKeyStatusPtr->newKeys & DPAD_RIGHT)
    {
        SetPurchaseGenericMenuPage(menu, sPurchaseGenericPage + 1);

        return MENU_ACT_SKIPCURSOR | MENU_ACT_SND6A;
    }

    return 0;
}

static int PurchaseGenericPageSwitchIn(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    (void)menu;
    (void)menuItem;

    DrawPurchaseGenericDetails(NULL);

    return 0;
}

static int PurchaseGenericPageDraw(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    (void)menu;
    ClearText(&menuItem->text);

    return 0;
}

static u8 PurchaseGenericPageSelect(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    (void)menuItem;

    SetPurchaseGenericMenuPage(menu, sPurchaseGenericPage + 1);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_SND6A;
}

static u8 PurchaseGenericBack(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    (void)menu;
    (void)menuItem;

    ClearPurchaseGenericDetails();

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6B | MENU_ACT_CLEAR;
}

static void PurchaseGenericMenuInit(struct MenuProc* menu)
{
    (void)menu;

    StartPurchaseGenericMenuLockProc();
    DrawPurchaseGenericDetails(GetPurchaseGenericForSlot(0));
}

static void PurchaseGenericMenuEnd(struct MenuProc* menu)
{
    (void)menu;

    sPurchaseGenericMenuOpen = false;
    ClearPurchaseGenericDetails();
    gLCDControlBuffer.bg0cnt.priority = sPurchaseGenericSavedBg0Priority;
    EndPurchaseGenericMenuLockProc();
}

u8 PurchaseGenericsCommandUsability(const struct MenuItemDef* def, int number)
{
    (void)def;
    (void)number;

    return CanUsePurchaseBaseNow(gActiveUnit) ? MENU_ENABLED : MENU_NOTSHOWN;
}

int PurchaseGenericsCommandDraw(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    const char* text = "Capture";

    PutDrawText(
        &menuItem->text,
        TILEMAP_LOCATED(BG_GetMapBuffer(menu->frontBg), menuItem->xTile, menuItem->yTile),
        menuItem->availability == MENU_DISABLED ? TEXT_COLOR_SYSTEM_GRAY : TEXT_COLOR_SYSTEM_WHITE,
        0, menu->rect.w - 1, text);

    return 0;
}

u8 PurchaseGenericsCommandEffect(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    struct Trap* trap;
    int factionId;

    (void)menu;
    (void)menuItem;

    trap = GetOrCreatePurchaseBaseTrapAt(gActiveUnit->xPos, gActiveUnit->yPos);

    if (trap == NULL)
        return MENU_ACT_SND6B;

    factionId = GetFactionIdForUnit(gActiveUnit);

    if (GetPurchaseBaseTrapOwner(trap) == factionId)
        return MENU_ACT_SND6B;

    if (!CanUnitCapturePurchaseBase(gActiveUnit))
        return MENU_ACT_SND6B;

    TryCapturePurchaseBase(trap, gActiveUnit);
    gActionData.unitActionType = UNIT_ACTION_PURCHASE_GENERIC;
    gActiveUnit->state |= US_HAS_MOVED;

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}




static void PurchaseGenericMenuLock_OnInit(struct PurchaseGenericMenuLockProc* proc)
{
    BMapDispSuspend();
    LockGame();
}

static void PurchaseGenericMenuLock_OnLoop(struct PurchaseGenericMenuLockProc* proc)
{
    if (!sPurchaseGenericMenuOpen)
    {
        Proc_Break(proc);
        return;
    }

}

static void PurchaseGenericMenuLock_OnEnd(struct PurchaseGenericMenuLockProc* proc)
{

    BMapDispResume();
    UnlockGame();
    RefreshUnitSprites();
    RefreshEntityBmMaps();
    RenderBmMap();
}

const struct ProcCmd PurchaseGenericsProcCmd[] =
{
    PROC_NAME("PurchaseGenericsMenuLock"),
    PROC_END_DUPLICATES,
    PROC_SET_END_CB(PurchaseGenericMenuLock_OnEnd),
    PROC_CALL(PurchaseGenericMenuLock_OnInit),
    PROC_REPEAT(PurchaseGenericMenuLock_OnLoop),
    PROC_END,
};

static void PurchaseGenericPlatformPreview_ResetScript(struct OpInfoClassDisplayProc* proc)
{
    proc->script = proc->classReelEnt->script;

    if (proc->script == NULL)
        proc->script = sPurchaseGenericPlatformScript;
}

static void PurchaseGenericPlatformPreview_CheckMenuOpen(struct OpInfoClassDisplayProc* proc)
{
    if (!sPurchaseGenericMenuOpen)
        Proc_Goto(proc, 1);
}

static void PurchaseGenericPlatformPreview_ExecScript(struct OpInfoClassDisplayProc* proc)
{
    ClassInfoDisplay_ExecScript(proc);
    SetPurchaseGenericPlatformAnimLayer(0);
}

static void PurchaseGenericPlatformPreview_LoopScript(struct OpInfoClassDisplayProc* proc)
{
    ClassInfoDisplay_LoopScript(proc);
    SetPurchaseGenericPlatformAnimLayer(0);
}

static void PurchaseGenericPlatformPreview_OnEnd(struct OpInfoClassDisplayProc* proc)
{
    (void)proc;

    EndActiveClassReelSpell();
    EndActiveClassReelBgColorProc();

    if (sPurchaseGenericPreviewStartedMiniAnim)
        EndEkrUnitMainMini(&gOpInfoData);

    EndBanimTerrain(&gUnk_Opinfo_0);
    EndEfxAnimeDrvProc();
    ApplyUnitSpritePalettes();

    sPurchaseGenericPreviewStartedMiniAnim = false;
    sPurchaseGenericPlatformActive = false;
}

static const struct ProcCmd sProc_PurchaseGenericPlatformPreview[] =
{
    PROC_NAME("PurchaseGenericPlatformPreview"),
    PROC_SET_END_CB(PurchaseGenericPlatformPreview_OnEnd),

PROC_LABEL(0),
    PROC_CALL(PurchaseGenericPlatformPreview_CheckMenuOpen),
    PROC_CALL(PurchaseGenericPlatformPreview_ExecScript),
    PROC_REPEAT(PurchaseGenericPlatformPreview_LoopScript),
    PROC_GOTO(0),

PROC_LABEL(10),
    PROC_CALL(PurchaseGenericPlatformPreview_ResetScript),

    PROC_GOTO(0),

PROC_LABEL(1),
    PROC_END,
};

static void StartPurchaseGenericMenuLockProc(void)
{
    sPurchaseGenericMenuOpen = true;
    Proc_Start(PurchaseGenericsProcCmd, PROC_TREE_3);
}

static void EndPurchaseGenericMenuLockProc(void)
{
    Proc_EndEach(PurchaseGenericsProcCmd);
}

bool PurchaseGenerics_TryStartTileMenu(int x, int y)
{
    struct Trap* trap;

    if (x < 0 || y < 0 || x >= gBmMapSize.x || y >= gBmMapSize.y)
        return false;

    if (gBmMapUnit[y][x] != 0)
        return false;

    if (gBmMapHidden[y][x] & HIDDEN_BIT_UNIT)
        return false;

    trap = GetPurchaseBaseTrapAt(x, y);

    if (trap == NULL)
        return false;

    if (GetPurchaseBaseTrapOwner(trap) != FACTION_ID_BLUE)
        return false;

    sPurchaseGenericPage = 0;
    sPurchaseGenericBaseX = x;
    sPurchaseGenericBaseY = y;
    sPurchaseGenericFactionId = FACTION_ID_BLUE;
    TileMap_FillRect(gBG2TilemapBuffer, 30, 20, 0);
    BG_EnableSyncByMask(BG2_SYNC_BIT);
    sPurchaseGenericSavedBg0Priority = gLCDControlBuffer.bg0cnt.priority;
    gLCDControlBuffer.bg0cnt.priority = 1;
    
    // struct MenuProc* menu = StartOrphanMenu(&gPurchaseGenericsMenuDef);
    struct MenuProc* menu = StartOrphanMenuExt(&gPurchaseGenericsMenuDef, 2, TILEREF(0, 0), 0, 0); // backBg as 2, frontBg (text) as 0

    return true;
}

static int CountFactionUnitsByClass(int factionId, int classId)
{
    int i;
    int count = 0;
    int faction = factionId << 6;

    for (i = faction + 1; i < faction + 0x40; ++i)
    {
        struct Unit* unit = GetUnit(i);

        if (!UNIT_IS_VALID(unit))
            continue;

        if (unit->state & (US_DEAD | US_UNAVAILABLE))
            continue;

        if (unit->pClassData->number == classId)
            ++count;
    }

    return count;
}

static void GrantIncomeForFaction(int factionId)
{
    int i;

    for (i = 0; i < TRAP_MAX_COUNT; ++i)
    {
        struct Trap* trap = GetTrap(i);
        int kind;

        if (trap->type == TRAP_NONE)
            break;

        if (trap->type != TRAP_PURCHASE_BASE)
            continue;

        if (GetPurchaseBaseTrapOwner(trap) != factionId)
            continue;

        kind = trap->data[TRAP_EXTDATA_PURCHASE_BASE_KIND];

        if (kind == PURCHASE_BASE_KIND_CAMP || kind == PURCHASE_BASE_KIND_TENT)
        {
            // Camp/Tent grant a flat amount per turn rather than the
            // PURCHASE_BASE_GOLD_UNIT * goldPerTurn formula -- that
            // gold-per-turn slot is repurposed to store Camp's battle HP
            // (see AddCampTrap), so it must never be read here.
            AddFactionChapterGoldAmount(factionId, CAMP_TENT_GOLD_PER_TURN);
            continue;
        }

        AddFactionChapterGoldAmount(
            factionId,
            PURCHASE_BASE_GOLD_UNIT * GetPurchaseBaseTrapGoldPerTurn(trap));
    }
}

static const struct PurchaseGenericDefinition* GetAiPriorityPurchase(int factionId)
{
    if (CountFactionUnitsByClass(factionId, CLASS_SOLDIER) < 3)
        return GetPurchaseGenericByClass(CLASS_SOLDIER);

    if (CountFactionUnitsByClass(factionId, CLASS_ARMOR_KNIGHT) < 2)
        return GetPurchaseGenericByClass(CLASS_ARMOR_KNIGHT);

    return sPurchaseGenericDefinitions + NextRN_N(GetPurchaseGenericCount());
}

static void RunAiPurchasesForFaction(int factionId)
{
    int i;

    for (i = 0; i < TRAP_MAX_COUNT; ++i)
    {
        struct Trap* trap = GetTrap(i);
        const struct PurchaseGenericDefinition* def;

        if (trap->type == TRAP_NONE)
            break;

        if (trap->type != TRAP_PURCHASE_BASE)
            continue;

        if (GetPurchaseBaseTrapOwner(trap) != factionId)
            continue;

        def = GetAiPriorityPurchase(factionId);

        if (def != NULL)
            PurchaseGenericUnitForFaction(def, factionId, trap->xPos, trap->yPos);
    }
}

static void RunAiCapturesForFaction(int factionId)
{
    int i;
    int faction = factionId << 6;

    for (i = faction + 1; i < faction + 0x40; ++i)
    {
        struct Unit* unit = GetUnit(i);
        struct Trap* trap;

        if (!UNIT_IS_VALID(unit))
            continue;

        if (unit->state & (US_DEAD | US_UNAVAILABLE))
            continue;

        if (!CanUnitCapturePurchaseBase(unit))
            continue;

        trap = GetOrCreatePurchaseBaseTrapAt(unit->xPos, unit->yPos);

        if (trap == NULL)
            continue;

        if (GetPurchaseBaseTrapOwner(trap) == factionId)
            continue;

        TryCapturePurchaseBase(trap, unit);
    }
}

// Used by AiAttemptOffensiveAction (src/cp_battle.c) to prefer holding a
// base the active unit is already standing on over going to fight -- the
// actual capture progress is applied automatically at the start of this
// unit's next phase by RunAiCapturesForFaction above, so all the AI needs
// to do here is not wander off the trap tile to attack instead.
bool AiShouldCaptureBaseInsteadOfAttacking(void)
{
    struct Trap* trap;

    if (!CanUnitCapturePurchaseBase(gActiveUnit))
        return false;

    trap = GetPurchaseBaseTrapAt(gActiveUnit->xPos, gActiveUnit->yPos);

    if (trap == NULL)
        return false;

    return GetPurchaseBaseTrapOwner(trap) != GetFactionIdForUnit(gActiveUnit);
}

// Used by AiScriptCmd_12_MoveTowardsEnemy (src/cp_script.c) to path towards
// an unowned base instead of an enemy when the base is closer. Mirrors
// AiFindTargetInReachByFunc's own extended-movement-range distance search
// (src/cp_utility.c), but over purchase-base traps instead of units --
// InitPurchaseBaseTrapsFromTerrain (src/bmtrick.c) guarantees every
// real-terrain base already has a Trap by the time any chapter's AI runs,
// so a plain trap-table scan sees every candidate, not just ones a unit has
// already visited.
bool AiFindClosestCapturableBase(struct Vec2* out, u8* distanceOut)
{
    int i;
    int ownFaction;
    u8 bestDistance = 0xFF;
    s16 xOut = -1;
    s16 yOut = 0;

    if (!CanUnitCapturePurchaseBase(gActiveUnit))
        return false;

    ownFaction = GetFactionIdForUnit(gActiveUnit);

    GenerateExtendedMovementMapOnRange(gActiveUnit->xPos, gActiveUnit->yPos, GetUnitMovementCost(gActiveUnit));

    for (i = 0; i < TRAP_MAX_COUNT; ++i)
    {
        struct Trap* trap = GetTrap(i);

        if (trap->type == TRAP_NONE)
            break;

        if (trap->type != TRAP_PURCHASE_BASE)
            continue;

        if (GetPurchaseBaseTrapOwner(trap) == ownFaction)
            continue;

        if (gBmMapRange[trap->yPos][trap->xPos] > MAP_MOVEMENT_MAX)
            continue;

        if (gBmMapRange[trap->yPos][trap->xPos] > bestDistance)
            continue;

        bestDistance = gBmMapRange[trap->yPos][trap->xPos];
        xOut = trap->xPos;
        yOut = trap->yPos;
    }

    if (xOut < 0)
        return false;

    out->x = xOut;
    out->y = yOut;
    *distanceOut = bestDistance;

    return true;
}

void PurchaseGenerics_OnNewPhase(void)
{
    int factionId = GetCurrentFactionId();

    if (gPlaySt.faction != FACTION_BLUE)
        RunAiCapturesForFaction(factionId);

    GrantIncomeForFaction(factionId);

    if (gPlaySt.faction != FACTION_BLUE)
        RunAiPurchasesForFaction(factionId);
}

static CONST_DATA struct MenuItemDef sPurchaseGenericsMenuItems[] =
{
    { "", 0, 0, 0, 0, PurchaseGenericMenuItemUsability, PurchaseGenericMenuItemDraw, PurchaseGenericMenuItemSelect, PurchaseGenericMenuItemIdle, PurchaseGenericMenuItemSwitchIn, 0 },
    { "", 0, 0, 0, 0, PurchaseGenericMenuItemUsability, PurchaseGenericMenuItemDraw, PurchaseGenericMenuItemSelect, PurchaseGenericMenuItemIdle, PurchaseGenericMenuItemSwitchIn, 0 },
    { "", 0, 0, 0, 0, PurchaseGenericMenuItemUsability, PurchaseGenericMenuItemDraw, PurchaseGenericMenuItemSelect, PurchaseGenericMenuItemIdle, PurchaseGenericMenuItemSwitchIn, 0 },
    { "", 0, 0, 0, 0, PurchaseGenericMenuItemUsability, PurchaseGenericMenuItemDraw, PurchaseGenericMenuItemSelect, PurchaseGenericMenuItemIdle, PurchaseGenericMenuItemSwitchIn, 0 },
    { "", 0, 0, 0, 0, PurchaseGenericMenuItemUsability, PurchaseGenericMenuItemDraw, PurchaseGenericMenuItemSelect, PurchaseGenericMenuItemIdle, PurchaseGenericMenuItemSwitchIn, 0 },
    { "", 0, 0, 0, 0, PurchaseGenericMenuItemUsability, PurchaseGenericMenuItemDraw, PurchaseGenericMenuItemSelect, PurchaseGenericMenuItemIdle, PurchaseGenericMenuItemSwitchIn, 0 },
    { "", 0, 0, 0, 0, PurchaseGenericMenuItemUsability, PurchaseGenericMenuItemDraw, PurchaseGenericMenuItemSelect, PurchaseGenericMenuItemIdle, PurchaseGenericMenuItemSwitchIn, 0 },
    // { "", 0, 0, 0, 0, MenuAlwaysEnabled, PurchaseGenericPageDraw, PurchaseGenericPageSelect, PurchaseGenericPageIdle, PurchaseGenericPageSwitchIn, 0 },
    MenuItemsEnd
};

u8 PurchaseMenu_HelpBox(struct MenuProc* menu, struct MenuItemProc* menuItem) {
    LoadHelpBoxGfx((void*)0x06011000, -1);
    int classId = GetPurchaseGenericForSlot(menu->itemCurrent)->classId;
    if (classId) {
    StartHelpBox(menuItem->xTile * 8, menuItem->yTile << 3,
    GetClassData(classId)->descTextId);
    }

    return 0;
}



CONST_DATA struct MenuDef gPurchaseGenericsMenuDef =
{
    { GENERICS_MENU_X, GENERICS_MENU_Y, 9, 0 },
    0,
    sPurchaseGenericsMenuItems,
    PurchaseGenericMenuInit,
    PurchaseGenericMenuEnd,
    0,
    PurchaseGenericBack,
    MenuAutoHelpBoxSelect,
    PurchaseMenu_HelpBox
};

#endif
