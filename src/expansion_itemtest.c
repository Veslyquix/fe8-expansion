#include "global.h"

#include "expansion_itemtest.h"

#if FE8_EXPANSION_ITEMTEST_ENABLED

#include <string.h>

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
#include "bmbattle.h"
#include "expansion_mechanics.h"
#include "expansion_starter_content.h"
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

/* Scratch team buffer for the MultiArena/link roundtrip (stage 4) and
 * scratch combatants for the issue #6 content-mechanic stage (stage 7,
 * the very last stage this proc script runs -- see the PROC_CALL list
 * at the bottom of this file) share one EWRAM allocation below: the
 * proc script is a strictly sequential state machine (never concurrent,
 * never re-entrant), stage 4 fully drains sArenaTeamOut/sArenaTeamIn
 * into gItemExpansionProbe fields before it returns, and no stage
 * between 4 and 7 ever touches this buffer again, so stage 7's
 * combatants can safely reuse the same bytes once stage 4 is done with
 * them. EWRAM (not stack): struct Unit is far too large for
 * MULTIARENA_UNITS_PER_TEAM copies, and struct BattleUnit embeds a
 * whole struct Unit, on a proc's stack. This is scratch reuse only --
 * sContentBearer and sContentControl still get their own, separate
 * members (never merged with each other): the content stage keeps both
 * combatants concurrently live across a single
 * ExpansionMechanicsApplyBattleStats() call each way. */
EWRAM_DATA static union
{
    struct
    {
        struct Unit out[MULTIARENA_UNITS_PER_TEAM];
        struct Unit in[MULTIARENA_UNITS_PER_TEAM];
    } arena;
    struct
    {
        struct BattleUnit bearer;
        struct BattleUnit control;
    } content;
} sArenaContentScratch;
#define sArenaTeamOut   (sArenaContentScratch.arena.out)
#define sArenaTeamIn    (sArenaContentScratch.arena.in)
#define sContentBearer  (sArenaContentScratch.content.bearer)
#define sContentControl (sArenaContentScratch.content.control)

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

/* The negative control for the issue #6 content stage: a second unit that is
 * deployed on the same map from turn 1 and never receives the content item,
 * so one run records the content mechanic firing for the bearer and NOT
 * firing for a unit that does not carry it. */
#define ITEMTEST_CONTROL_PID CHARACTER_SETH

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

/* Registry index of a mechanic key, using only the public introspection
 * API (ExpansionMechanicsCount/KeyAt). Returns ITEMTEST_INDEX_NONE when the
 * key is not registered. */
static u32 ItemExpansionTest_FindMechanicIndex(const char * key)
{
    const char * entry;
    int count;
    int i;

    count = ExpansionMechanicsCount();

    for (i = 0; i < count; i++)
    {
        entry = ExpansionMechanicsKeyAt(i);

        if (entry != NULL && strcmp(entry, key) == 0)
            return (u32)i;
    }

    return ITEMTEST_INDEX_NONE;
}

static u32 ItemExpansionTest_SlotValue(int slot)
{
    if (slot < 0)
        return ITEMTEST_INDEX_NONE;

    return (u32)slot;
}

/* FNV-1a 32, over the NUL-terminated string the production name path
 * returned. A hash plus the length is a scalar, order-sensitive witness of
 * the exact bytes drawn, so the probe never has to publish a pointer (or a
 * framebuffer) to prove the text. Offset basis/prime are the published
 * FNV-1a 32 constants. */
#define ITEMTEST_FNV1A_OFFSET 2166136261u
#define ITEMTEST_FNV1A_PRIME 16777619u

static u32 ItemExpansionTest_StringHash(const char * text)
{
    u32 hash = ITEMTEST_FNV1A_OFFSET;
    const u8 * cursor = (const u8 *)text;

    if (text == NULL)
        return 0;

    while (*cursor != 0)
    {
        hash ^= (u32)*cursor++;
        hash *= ITEMTEST_FNV1A_PRIME;
    }

    return hash;
}

static u32 ItemExpansionTest_StringLength(const char * text)
{
    u32 length = 0;

    if (text == NULL)
        return 0;

    while (text[length] != 0)
        length++;

    return length;
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

    /* Issue #6 content example, boot half: the compile-time config flag, the
     * bundled item's typed ID, and the state of the PUBLIC mechanics registry
     * after the framework's single built-in install point has run. None of
     * this needs a map, so a modern release ROM records it too. */
    ExpansionMechanicsInstallBuiltins();

    gItemExpansionProbe.contentEnabled = (u32)ExpansionStarterContentIsEnabled();
    gItemExpansionProbe.contentItemId = (u32)ExpansionStarterContentItemId();
    gItemExpansionProbe.contentMechanicsCount = (u32)ExpansionMechanicsCount();
    gItemExpansionProbe.contentMechanicIndex =
        ItemExpansionTest_FindMechanicIndex(EXPANSION_STARTER_CONTENT_KEY);
    gItemExpansionProbe.contentSampleIndex =
        ItemExpansionTest_FindMechanicIndex(EXPANSION_MECHANICS_SAMPLE_KEY);
    gItemExpansionProbe.contentRegisterOk = gExpansionMechanicsProbe.registerOkCount;
    gItemExpansionProbe.contentRegisterErr = gExpansionMechanicsProbe.registerErrCount;
    gItemExpansionProbe.contentLastResult = gExpansionMechanicsProbe.lastResult;

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
    const char * name;
    int item;

    (void)proc;

    unit = ItemExpansionTest_GetTargetUnit();
    item = (int)gItemExpansionProbe.eventItem;

    if (item == 0)
        item = MakeNewItem(ITEM_EXPANSION_CE);

    name = GetItemName(item);

    gItemExpansionProbe.uiNamePtr = (u32)name;
    gItemExpansionProbe.uiNameLen = ItemExpansionTest_StringLength(name);
    gItemExpansionProbe.uiNameHash = ItemExpansionTest_StringHash(name);
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

/* Stage 7 (issue #6): the bundled content example end to end on a live map.
 *
 * Both combatants are built by the production InitBattleUnit() from real,
 * deployed units, and the bonus is applied through the PUBLIC registry seam
 * ExpansionMechanicsApplyBattleStats() -- the very entry point
 * ComputeBattleUnitStats() itself calls. Nothing here re-implements the
 * mechanic, and nothing special-cases a stat.
 *
 * The bearer received the content item from the production event decoder in
 * stage 2; the control unit never did. One apply each therefore records the
 * content mechanic's bounded avoid bonus for the bearer only, next to the
 * content-free sample's bounded defence bonus for both -- a positive and its
 * negative control in the same deterministic run. */
static void ItemExpansionTest_StageContent(struct ItemExpansionTestProc * proc)
{
    struct Unit * bearer;
    struct Unit * control;
    ItemId item;
    u32 appliesBefore;
    u32 triggersBefore;
    short avoidBefore;
    short defenseBefore;

    (void)proc;

    /* Content flag off: record the explicit "no bearer / no control" sentinels
     * and complete the stage, so a probe build WITHOUT the content example
     * still reaches ITEMTEST_STAGE_ALL and its negative control is an
     * explicit recorded value rather than an untouched zero. */
    if (!ExpansionStarterContentIsEnabled())
    {
        gItemExpansionProbe.contentBearerItemSlot = ITEMTEST_INDEX_NONE;
        gItemExpansionProbe.contentControlItemSlot = ITEMTEST_INDEX_NONE;
        gItemExpansionProbe.stagesCompleted |= ITEMTEST_STAGE_CONTENT;
        return;
    }

    bearer = ItemExpansionTest_GetTargetUnit();
    control = GetUnitFromCharId(ITEMTEST_CONTROL_PID);

    if (bearer == NULL || control == NULL)
        return;

    item = ExpansionStarterContentItemId();

    gItemExpansionProbe.contentBearerPid = UNIT_CHAR_ID(bearer);
    gItemExpansionProbe.contentControlPid = UNIT_CHAR_ID(control);
    gItemExpansionProbe.contentBearerItemSlot =
        ItemExpansionTest_SlotValue(GetUnitItemSlot(bearer, (int)item));
    gItemExpansionProbe.contentControlItemSlot =
        ItemExpansionTest_SlotValue(GetUnitItemSlot(control, (int)item));

    appliesBefore = gExpansionMechanicsProbe.applyCount;
    triggersBefore = gExpansionMechanicsProbe.sampleTriggerCount;

    /* sContentBearer/sContentControl alias the already-drained arena
     * scratch above (see the union comment by their declaration):
     * InitBattleUnit() only ever sets a named subset of struct
     * BattleUnit's fields (src/bmbattle.c), the same way it does for a
     * genuinely fresh, zero-BSS EWRAM global, so this scratch must be
     * explicitly rezeroed before every use here -- exactly the same
     * convention this file already applies to sUnpackedUnit above,
     * which is reused across stages 5 and 6 for the same reason. */
    CpuFill16(0, &sContentBearer, sizeof(sContentBearer));
    CpuFill16(0, &sContentControl, sizeof(sContentControl));

    InitBattleUnit(&sContentBearer, bearer);
    InitBattleUnit(&sContentControl, control);

    avoidBefore = sContentBearer.battleAvoidRate;
    defenseBefore = sContentBearer.battleDefense;
    ExpansionMechanicsApplyBattleStats(&sContentBearer, &sContentControl, 0);
    gItemExpansionProbe.contentBearerAvoidDelta =
        (u32)((int)sContentBearer.battleAvoidRate - (int)avoidBefore);
    gItemExpansionProbe.contentBearerDefenseDelta =
        (u32)((int)sContentBearer.battleDefense - (int)defenseBefore);

    avoidBefore = sContentControl.battleAvoidRate;
    defenseBefore = sContentControl.battleDefense;
    ExpansionMechanicsApplyBattleStats(&sContentControl, &sContentBearer, 0);
    gItemExpansionProbe.contentControlAvoidDelta =
        (u32)((int)sContentControl.battleAvoidRate - (int)avoidBefore);
    gItemExpansionProbe.contentControlDefenseDelta =
        (u32)((int)sContentControl.battleDefense - (int)defenseBefore);

    gItemExpansionProbe.contentApplyCount =
        gExpansionMechanicsProbe.applyCount - appliesBefore;
    gItemExpansionProbe.contentSampleTriggerCount =
        gExpansionMechanicsProbe.sampleTriggerCount - triggersBefore;

    gItemExpansionProbe.stagesCompleted |= ITEMTEST_STAGE_CONTENT;
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
    PROC_CALL(ItemExpansionTest_StageContent),
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
