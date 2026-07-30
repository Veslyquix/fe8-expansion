#include "global.h"

#include "expansion_itemtest.h"

#if FE8_EXPANSION_ITEMTEST_ENABLED

#include "proc.h"
#include "hardware.h"
#include "fontgrp.h"
#include "bmitem.h"
#include "bmunit.h"
#include "bmsave.h"
#include "bmmap.h"
#include "bmlib.h"
#include "playerphase.h"
#include "bm.h"
#include "rng.h"
#include "event.h"
#include "eventscript.h"
#include "EAstdlib.h"
#include "worldmap.h"
#include "gamecontrol.h"
#include "constants/items.h"
#include "constants/items_expansion.h"
#include "constants/characters.h"
#include "constants/chapters.h"
#include "constants/worldmap.h"

/*
 * Runtime harness for the opt-in expanded item ID space (issue #10).
 * See include/expansion_itemtest.h for the contract and the
 * "orchestrate only, never re-implement" rule this file obeys.
 */

extern struct ProcCmd CONST_DATA ProcScr_WorldMapWrapper[];
extern struct ProcCmd CONST_DATA gProcScr_TitleScreen[];
extern struct ProcCmd CONST_DATA gProcScr_GameControl[];

EWRAM_DATA struct ItemExpansionProbe gItemExpansionProbe = {0};

EWRAM_DATA static u8 sTitleStartRequested = 0;
EWRAM_DATA static u8 sChapterBootRequested = 0;
EWRAM_DATA static u8 sBootSuppressionActive = 0;
EWRAM_DATA static u16 sTitleIdleFrames = 0;

/* Scratch team buffer for the MultiArena/link roundtrip below. EWRAM (not
 * stack): struct Unit is far too large for MULTIARENA_UNITS_PER_TEAM
 * copies on a proc's stack. */
EWRAM_DATA static struct Unit sArenaTeamOut[MULTIARENA_UNITS_PER_TEAM];
EWRAM_DATA static struct Unit sArenaTeamIn[MULTIARENA_UNITS_PER_TEAM];

/* Scratch packed-record buffers for the game-save/suspend pack+unpack
 * roundtrips below, and the unit the production unpackers restore into. */
EWRAM_DATA static struct GameSavePackedUnit sPackedUnit;
EWRAM_DATA static struct SuspendSavePackedUnit sSuspendUnit;
EWRAM_DATA static struct Unit sUnpackedUnit;

/* Team name for the MultiArena/link roundtrip below (original, ASCII). */
CONST_DATA static char sArenaTeamName[MULTIARENA_TEAMNAME_SIZE + 1] = "ITEMTEST";

/* Bounded fail-safe for the "wait for a stable Player Phase" poll below,
 * mirroring the debug launcher's own bootstrap observer timeout. Only a
 * genuinely stuck boot can ever reach it; the probe then simply never
 * stamps its magic and the host runner reports the exact stage reached. */
#define ITEMTEST_BOOT_TIMEOUT_FRAMES 21600

/* Frames to let the freshly interactive map settle (all scripted opening
 * dialogue advanced, no scenario input left in flight) before the probe
 * touches anything. */
#define ITEMTEST_SETTLE_FRAMES 600

/* Title-screen idle frames to wait before the probe build starts the game
 * by itself (see ItemExpansionTest_RequestsTitleStart). */
#define ITEMTEST_TITLE_IDLE_FRAMES 120

/* The unit the production event targets and every later production save
 * path carries. Eirika is deployed from the first turn of Chapter 2. */
#define ITEMTEST_TARGET_PID CHARACTER_EIRIKA

/* Fixed RN seed for the scripted boot (see ItemExpansionTest_PrepareChapterBoot). */
#define ITEMTEST_RNG_SEED 0x42D690E9

/* Free BG0 tilemap row used as the UI draw destination: row 19 is below
 * the map view's own drawn area, so the production draw calls have a real,
 * writable tilemap target without fighting the live map UI for tiles. */
#define ITEMTEST_UI_TILE_X 2
#define ITEMTEST_UI_TILE_Y 19

struct ItemExpansionTestProc
{
    PROC_HEADER;

    u16 timer;
};

/* A real event script in the production grammar (include/EAstdlib.h),
 * decoded and executed by the unmodified event engine: SVAL loads the item
 * into event slot 3, GIVEITEMTO runs EV_CMD_GIVEITEM's own production
 * handler (Event37_GiveItem -> NewPopup_ItemGot -> the ordinary
 * "got item" popup that adds it to the unit). The legacy 0xCD item is
 * given first through the exact same command, so one run proves both the
 * old and the expanded value take the identical production path. */
CONST_DATA static EventListScr EventScr_ItemExpansionProbe[] = {
    SVAL(EVT_SLOT_3, ITEM_UNK_CD)
    GIVEITEMTO(ITEMTEST_TARGET_PID)

    SVAL(EVT_SLOT_3, ITEM_EXPANSION_CE)
    GIVEITEMTO(ITEMTEST_TARGET_PID)

    ENDA
};

static struct Unit * ItemExpansionTest_GetTargetUnit(void)
{
    return GetUnitFromCharId(ITEMTEST_TARGET_PID);
}

/* Reports the raw items[] halfword holding the given item id, or 0 when
 * the unit does not carry it. Pure observation of a production-owned
 * inventory: the search uses the engine's own ITEM_INDEX accessor. */
static u32 ItemExpansionTest_FindRawItem(struct Unit * unit, int itemIndex)
{
    int i;

    if (unit == NULL)
        return 0;

    for (i = 0; i < UNIT_ITEM_COUNT; i++)
    {
        if (ITEM_INDEX(unit->items[i]) == itemIndex)
            return unit->items[i];
    }

    return 0;
}

static int ItemExpansionTest_FindItemSlot(struct Unit * unit, int itemIndex)
{
    int i;

    if (unit == NULL)
        return -1;

    for (i = 0; i < UNIT_ITEM_COUNT; i++)
    {
        if (ITEM_INDEX(unit->items[i]) == itemIndex)
            return i;
    }

    return -1;
}

int ItemExpansionTest_RequestsTitleStart(void)
{
    if (sTitleStartRequested)
        return 0;

    /* Let the title screen finish coming up and idle for a moment first,
     * so the boot commits from a settled title -- the same place the debug
     * hub's own launch commits from -- rather than on the very first idle
     * frame. Title_IDLE runs once per frame, so this counts title idle
     * frames directly. */
    if (++sTitleIdleFrames < ITEMTEST_TITLE_IDLE_FRAMES)
        return 0;

    sTitleStartRequested = 1;
    sChapterBootRequested = 1;

    return 1;
}

int ItemExpansionTest_IsBootSuppressionActive(void)
{
    return sBootSuppressionActive;
}

int ItemExpansionTest_ConsumeChapterBootRequest(void)
{
    if (!sChapterBootRequested)
        return 0;

    sChapterBootRequested = 0;

    return 1;
}

static void ItemExpansionTest_WaitForPlayerPhase(struct ItemExpansionTestProc * proc)
{
    u32 live = 0;

    gItemExpansionProbe.lastChapterIndex = gPlaySt.chapterIndex;
    gItemExpansionProbe.lastFaction = gPlaySt.faction;
    gItemExpansionProbe.wmLocation = gGMData.units[0].location;
    gItemExpansionProbe.wmCurrentNode = gGMData.current_node;

    if (Proc_Find(gProc_BMapMain) != NULL)
        gItemExpansionProbe.mapMainSeen = 1;

    if (Proc_Find(gProcScr_PlayerPhase) != NULL)
        gItemExpansionProbe.playerPhaseSeen = 1;

    if (Proc_Find(ProcScr_WorldMapWrapper) != NULL)
        live |= 1 << 0;

    if (Proc_Find(gProcScr_TitleScreen) != NULL)
        live |= 1 << 1;

    if (Proc_Find(gProcScr_GameControl) != NULL)
        live |= 1 << 2;

    if (EventEngineExists())
        live |= 1 << 3;

    if (Proc_Find(gProc_BMapMain) != NULL)
        live |= 1 << 4;

    gItemExpansionProbe.procStateBits |= live;
    gItemExpansionProbe.procStateNow = live;

    if (gPlaySt.faction == FACTION_BLUE && Proc_Find(gProcScr_PlayerPhase) != NULL)
    {
        gItemExpansionProbe.phaseWaitFrames = proc->timer;
        proc->timer = 0;
        Proc_Break(proc);
        return;
    }

    if (++proc->timer >= ITEMTEST_BOOT_TIMEOUT_FRAMES)
    {
        gItemExpansionProbe.phaseWaitFrames = proc->timer;
        gItemExpansionProbe.phaseTimedOut = 1;
        proc->timer = 0;
        Proc_Break(proc);
    }
}

static void ItemExpansionTest_Settle(struct ItemExpansionTestProc * proc)
{
    if (++proc->timer >= ITEMTEST_SETTLE_FRAMES)
    {
        /* Boot window over: the ordinary automatic suspend write resumes
         * from here on, exactly as in any other build. */
        sBootSuppressionActive = 0;

        proc->timer = 0;
        Proc_Break(proc);
    }
}

/* Stage 1: the runtime item record itself, read exactly the way every
 * gameplay caller reads it. */
static void ItemExpansionTest_StageItemData(struct ItemExpansionTestProc * proc)
{
    const struct ItemData * data;
    int made;

    (void)proc;

    data = GetItemData(ITEM_EXPANSION_CE);

    gItemExpansionProbe.configuredCap = ITEM_ID_CONFIGURED_CAP;
    gItemExpansionProbe.dataNumber = data->number;
    gItemExpansionProbe.dataNameTextId = data->nameTextId;
    gItemExpansionProbe.dataDescTextId = data->descTextId;
    gItemExpansionProbe.dataIconId = data->iconId;
    gItemExpansionProbe.dataWeaponType = data->weaponType;
    gItemExpansionProbe.dataMaxUses = data->maxUses;
    gItemExpansionProbe.dataAttributes = data->attributes;

    made = MakeNewItem(ITEM_EXPANSION_CE);

    gItemExpansionProbe.madeItem = made;
    gItemExpansionProbe.lookupIndex = GetItemIndex(made);
    gItemExpansionProbe.lookupUses = GetItemUses(made);
    gItemExpansionProbe.legacyDataNumber = GetItemData(ITEM_UNK_CD)->number;

    gItemExpansionProbe.stagesCompleted |= ITEMTEST_STAGE_ITEMDATA;
}

/* Stage 2a: hand the script to the production event engine. */
static void ItemExpansionTest_StageEventStart(struct ItemExpansionTestProc * proc)
{
    (void)proc;

    CallEvent((const u16 *)EventScr_ItemExpansionProbe, EV_EXEC_GAMEPLAY);
}

static void ItemExpansionTest_WaitForEvent(struct ItemExpansionTestProc * proc)
{
    gItemExpansionProbe.eventWaitFrames++;

    if (EventEngineExists())
    {
        proc->timer = 0;

        /* Fail-safe: never poll forever if the engine somehow stalls. */
        if (gItemExpansionProbe.eventWaitFrames >= ITEMTEST_BOOT_TIMEOUT_FRAMES)
            Proc_Break(proc);

        return;
    }

    /* The "got item" popup ends a few frames after the engine itself; let
     * it settle so the inventory read below sees the committed result. */
    if (++proc->timer >= 60)
        Proc_Break(proc);
}

/* Stage 2b: observe what the production decoder actually did to a real
 * unit's real inventory. */
static void ItemExpansionTest_StageEventVerify(struct ItemExpansionTestProc * proc)
{
    struct Unit * unit;

    (void)proc;

    unit = ItemExpansionTest_GetTargetUnit();

    if (unit != NULL)
        gItemExpansionProbe.eventUnitPid = UNIT_CHAR_ID(unit);

    gItemExpansionProbe.eventItemSlot = ItemExpansionTest_FindItemSlot(unit, ITEM_EXPANSION_CE);
    gItemExpansionProbe.eventItem = ItemExpansionTest_FindRawItem(unit, ITEM_EXPANSION_CE);
    gItemExpansionProbe.eventLegacyItem = ItemExpansionTest_FindRawItem(unit, ITEM_UNK_CD);

    gItemExpansionProbe.stagesCompleted |= ITEMTEST_STAGE_EVENT;
}

/* Stage 3: the production item UI. DrawItemMenuLine is the exact call the
 * item menu, trade screen and shop use; DrawItemStatScreenLine is the
 * stat-screen ("detail") line. Both are given a real struct Text and a
 * real BG0 tilemap destination, and what they wrote is read straight back
 * out of the tilemap buffer. */
static void ItemExpansionTest_StageUi(struct ItemExpansionTestProc * proc)
{
    struct Text text;
    u16 * mapOut;
    struct Unit * unit;
    int item;

    (void)proc;

    unit = ItemExpansionTest_GetTargetUnit();
    item = (int)gItemExpansionProbe.eventItem;

    if (item == 0)
        item = MakeNewItem(ITEM_EXPANSION_CE);

    gItemExpansionProbe.uiNamePtr = (u32)GetItemName(item);
    gItemExpansionProbe.uiIconId = GetItemIconId(item);
    gItemExpansionProbe.uiDescId = GetItemDescId(item);

    mapOut = gBG0TilemapBuffer + TILEMAP_INDEX(ITEMTEST_UI_TILE_X, ITEMTEST_UI_TILE_Y);

    InitText(&text, 12);
    DrawItemMenuLine(&text, item, unit != NULL ? IsItemDisplayUsable(unit, item) : 1, mapOut);

    gItemExpansionProbe.uiMenuIconTile = mapOut[0];
    gItemExpansionProbe.uiMenuNameTile = mapOut[2];
    gItemExpansionProbe.uiMenuUsesTile = mapOut[11];

    mapOut = gBG0TilemapBuffer + TILEMAP_INDEX(ITEMTEST_UI_TILE_X, ITEMTEST_UI_TILE_Y + 1);

    InitText(&text, 12);
    DrawItemStatScreenLine(&text, item, TEXT_COLOR_SYSTEM_WHITE, mapOut);

    gItemExpansionProbe.uiStatIconTile = mapOut[0];
    gItemExpansionProbe.uiStatSlashTile = mapOut[12];

    gItemExpansionProbe.stagesCompleted |= ITEMTEST_STAGE_UI;
}

/* Stage 4: the MultiArena/link team representation -- the same packed
 * 14-bit item fields the link cable ships -- written to and read back from
 * SRAM by the production arena save code. */
static void ItemExpansionTest_StageMultiArena(struct ItemExpansionTestProc * proc)
{
    char nameBack[MULTIARENA_TEAMNAME_SIZE + 1];
    struct Unit * unit;
    int i;

    (void)proc;

    unit = ItemExpansionTest_GetTargetUnit();

    if (unit == NULL)
        return;

    /* Every slot must be a fully formed unit: WriteGameSavePackedUnit
     * dereferences pClassData before it ever checks pCharacterData. */
    for (i = 0; i < MULTIARENA_UNITS_PER_TEAM; i++)
        sArenaTeamOut[i] = *unit;

    CpuFill16(0, sArenaTeamIn, sizeof(sArenaTeamIn));
    CpuFill16(0, nameBack, sizeof(nameBack));

    WriteMultiArenaSaveTeam(0, sArenaTeamOut, sArenaTeamName);
    ReadMultiArenaSaveTeam(0, sArenaTeamIn, nameBack);

    gItemExpansionProbe.arenaItem =
        ItemExpansionTest_FindRawItem(&sArenaTeamIn[0], ITEM_EXPANSION_CE);
    gItemExpansionProbe.arenaLegacyItem =
        ItemExpansionTest_FindRawItem(&sArenaTeamIn[0], ITEM_UNK_CD);
    gItemExpansionProbe.arenaEmptySlot = sArenaTeamIn[0].items[UNIT_ITEM_COUNT - 1];

    gItemExpansionProbe.stagesCompleted |= ITEMTEST_STAGE_MULTIARENA;
}

/* Stage 5: the production game-save unit pack/unpack primitives -- the
 * exact pair the whole-block game-save writer/reader themselves use
 * per unit, and
 * the pair that squeezes each item into the on-media 14-bit item field.
 * The packed buffer is this file's own scratch, never a live save slot:
 * the harness must not overwrite the player's save blocks, and the
 * repository's own save-hook guard (tools/gba-playtest/tests/
 * test_savesuspend_resume_scenario.py NoNewSaveInternalHookTests) records
 * that no new whole-block save-writer call site may appear in src/. The
 * whole-block save/suspend cycle itself is covered on this very ROM by
 * expansion-modern-savefmt-check's ordinary-UI scenarios. */
static void ItemExpansionTest_StageGameSave(struct ItemExpansionTestProc * proc)
{
    struct Unit * unit;

    (void)proc;

    unit = ItemExpansionTest_GetTargetUnit();

    if (unit == NULL)
        return;

    CpuFill16(0, &sPackedUnit, sizeof(sPackedUnit));
    CpuFill16(0, &sUnpackedUnit, sizeof(sUnpackedUnit));

    WriteGameSavePackedUnit(unit, &sPackedUnit);
    LoadSavedUnit(&sPackedUnit, &sUnpackedUnit);

    gItemExpansionProbe.gameSaveItem =
        ItemExpansionTest_FindRawItem(&sUnpackedUnit, ITEM_EXPANSION_CE);
    gItemExpansionProbe.gameSaveLegacyItem =
        ItemExpansionTest_FindRawItem(&sUnpackedUnit, ITEM_UNK_CD);
    gItemExpansionProbe.gameSaveEmptySlot = sUnpackedUnit.items[UNIT_ITEM_COUNT - 1];

    /* The packed record's own 14-bit item field, straight out of the
     * on-media bitfield the production packer wrote. */
    gItemExpansionProbe.gameSavePackedField = sPackedUnit.item4;

    gItemExpansionProbe.stagesCompleted |= ITEMTEST_STAGE_GAMESAVE;
}

/* Stage 6: the production suspend-save unit encode/decode primitives, the
 * pair the whole-block suspend writer/reader themselves use per unit (same
 * scratch-buffer reasoning as stage 5). */
static void ItemExpansionTest_StageSuspend(struct ItemExpansionTestProc * proc)
{
    struct Unit * unit;

    (void)proc;

    unit = ItemExpansionTest_GetTargetUnit();

    if (unit == NULL)
        return;

    CpuFill16(0, &sSuspendUnit, sizeof(sSuspendUnit));
    CpuFill16(0, &sUnpackedUnit, sizeof(sUnpackedUnit));

    EncodeSuspendSavePackedUnit(unit, &sSuspendUnit);
    ReadSuspendSavePackedUnit(&sSuspendUnit, &sUnpackedUnit);

    gItemExpansionProbe.suspendItem =
        ItemExpansionTest_FindRawItem(&sUnpackedUnit, ITEM_EXPANSION_CE);
    gItemExpansionProbe.suspendLegacyItem =
        ItemExpansionTest_FindRawItem(&sUnpackedUnit, ITEM_UNK_CD);
    gItemExpansionProbe.suspendEmptySlot = sUnpackedUnit.items[UNIT_ITEM_COUNT - 1];
    gItemExpansionProbe.suspendPackedField = sSuspendUnit.item4;

    gItemExpansionProbe.stagesCompleted |= ITEMTEST_STAGE_SUSPEND;
}

static void ItemExpansionTest_Finish(struct ItemExpansionTestProc * proc)
{
    (void)proc;

    if (gItemExpansionProbe.stagesCompleted == ITEMTEST_STAGE_ALL)
        gItemExpansionProbe.magic = ITEM_EXPANSION_PROBE_MAGIC;
}

CONST_DATA static struct ProcCmd sItemExpansionTestScript[] = {
    PROC_NAME("ITEMTEST"),

    /* Stage 1 runs immediately, before anything is waited on: the runtime
     * item-record lookup needs no map, so every build that boots at all --
     * debug or release -- records it. */
    PROC_CALL(ItemExpansionTest_StageItemData),

    PROC_REPEAT(ItemExpansionTest_WaitForPlayerPhase),
    PROC_REPEAT(ItemExpansionTest_Settle),

    PROC_CALL(ItemExpansionTest_StageEventStart),
    PROC_REPEAT(ItemExpansionTest_WaitForEvent),
    PROC_CALL(ItemExpansionTest_StageEventVerify),
    PROC_CALL(ItemExpansionTest_StageUi),
    PROC_CALL(ItemExpansionTest_StageMultiArena),
    PROC_CALL(ItemExpansionTest_StageGameSave),
    PROC_CALL(ItemExpansionTest_StageSuspend),
    PROC_CALL(ItemExpansionTest_Finish),

    PROC_END,
};

void ItemExpansionTest_PrepareChapterBoot(void)
{
    /* Deterministic RNG seed, exactly like the debug hub's own launcher
     * (src/gamecontrol.c): a scripted boot skips the save/difficulty menus
     * that normally seed the RN state, so seed it here to make the run
     * independent of how many frames/RNG draws happened before. */
    SetLCGRNValue(ITEMTEST_RNG_SEED);
    InitRN(AdvanceGetLCGRNValue());

    /* The same new-game bootstrap production sequence
     * GameControl_InitTutorialGame and the debug hub's Chapter 2 launcher
     * already use (see src/gamecontrol.c). EWRAM only; no SRAM write. */
    InitPlayConfig(0, 0);
    gPlaySt.chapterModeIndex = CHAPTER_MODE_COMMON;
    ResetPermanentFlags();
    ResetChapterFlags();
    InitUnits();
    gPlaySt.chapterIndex = CHAPTER_L_2;

    GmDataInit();

    /* Same rest-stop placement the debug hub's Chapter 2 launcher uses: the
     * ordinary world-map traversal then resolves Chapter 2 on its own, with
     * no chapter-specific event or battle logic bypassed. */
    gGMData.units[0].location = NODE_CASTLE_FRELIA;

    gItemExpansionProbe.bootPrepared = 1;
    sBootSuppressionActive = 1;

    Proc_Start(sItemExpansionTestScript, PROC_TREE_3);
}

#endif /* FE8_EXPANSION_ITEMTEST_ENABLED */
