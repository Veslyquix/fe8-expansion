#include "global.h"

#include <string.h>
#include <stdio.h>

#include "proc.h"
#include "uimenu.h"
#include "fontgrp.h"
#include "hardware.h"
#include "bmunit.h"
#include "bmcontainer.h"
#include "eventinfo.h"
#include "rng.h"
#include "bmsave.h"
#include "save_format.h"
#include "expansion_debugtools.h"

#include "constants/characters.h"
#include "constants/items.h"

/*
 * Issue #11 closure -- the five bounded, validated debug tools:
 *   5. Unit inspection/edit
 *   6. Convoy inspection/edit
 *   7. Flag/chapter/event state action
 *   8. RNG inspection/control
 *   9. Save compatibility/state inspection
 *
 * Each is a single registry action, following the exact same
 * StartOrphanMenu submenu idiom src/debugtools_actions.c's Weather/Fog
 * actions already use. Every mutating tool (5-8) opens a bounded
 * two-item "Confirm <action>" / "Back" submenu -- a mutation only ever
 * happens after that explicit, separate confirmation input, never on the
 * initial hub selection alone. Tool 9 is read-only (no Confirm item at
 * all: nothing to confirm). See include/expansion_debugtools.h's "Five
 * bounded validated tools" block comment, docs/debugtools.md, and
 * reports/debugtools_issue11_closure.md.
 *
 * No tool ever performs a raw/arbitrary address write, nor accepts an
 * unvalidated numeric index from outside this file: every target is
 * either a fixed in-range constant (DEBUGTOOLS_UNIT_TARGET_CHARACTER,
 * DEBUGTOOLS_CONVOY_TEST_ITEM, DEBUGTOOLS_DEBUG_EVENT_FLAG_ID,
 * DEBUGTOOLS_TOOLS_RNG_SEED below) or produced by an existing engine
 * lookup helper (GetUnitFromCharId) that itself returns NULL on failure
 * -- callers below always re-check via UNIT_IS_VALID/DEBUGTOOLS_ASSERT
 * immediately before any mutation. This file never edits
 * src/bmdebug.c, src/menu_def.c, or src/uidebug.c, and never touches
 * SRAM/any save-block struct directly.
 */

#if FE8_EXPANSION_DEBUGTOOLS_ENABLED

enum
{
    /* Distinct from Weather (0xE0) and Fog (0xE1), src/debugtools_actions.c,
     * and from every static src/menu_def.c overrideId -- see that file's
     * own comment on DEBUGTOOLS_WEATHER_OVERRIDE_ID for why this must
     * never collide. */
    DEBUGTOOLS_UNIT_OVERRIDE_ID = 0xE2,
    DEBUGTOOLS_CONVOY_OVERRIDE_ID = 0xE3,
    DEBUGTOOLS_FLAG_OVERRIDE_ID = 0xE4,
    DEBUGTOOLS_RNG_OVERRIDE_ID = 0xE5
};

/* Fixed, documented, always-in-range targets -- never a contributor- or
 * player-supplied numeric index. */
#define DEBUGTOOLS_UNIT_TARGET_CHARACTER CHARACTER_EIRIKA
#define DEBUGTOOLS_CONVOY_TEST_ITEM ITEM_VULNERARY

/* Highest valid chapter-scoped event-flag bit: GetChapterFlagBitsSize()
 * (src/eventinfo.c) is 5 bytes == 40 bits (indices 0-39), and
 * include/constants/event-flags.h documents indices 7-40 as free/scratch
 * (0-6 are real, meaningful gameplay flags). 39 is deliberately the
 * highest in-range bit, re-validated at every mutation site via
 * DEBUGTOOLS_ASSERT rather than trusted as a compile-time-only fact. */
#define DEBUGTOOLS_DEBUG_EVENT_FLAG_ID 39

/* Arbitrary fixed debug reseed value, distinct from
 * DEBUGTOOLS_FASTBOOT_RNG_SEED (src/gamecontrol.c) so the two are never
 * confused in logs/tests. */
#define DEBUGTOOLS_TOOLS_RNG_SEED 0x1EE7C0DEu

static void DebugToolsTools_ShowStatusLine(const char* text)
{
    SetupDebugFontForBG(2, 0);
    PrintDebugStringToBG(BG_GetMapBuffer(2) + TILEMAP_INDEX(1, 1), text);
    gLCDControlBuffer.dispcnt.bg2_on = 1;
}

/* --- 5. Unit inspection/edit -------------------------------------------- */

EWRAM_DATA static struct MenuItemDef sUnitMenuItemDefs[3] = {{0}}; /* confirm + back + terminator */

static void DebugToolsUnit_OnEnd(struct MenuProc* menu)
{
    (void)menu;

    DebugTools_OpenHub();
}

CONST_DATA struct MenuDef gDebugToolsUnitMenuDef = {
    {1, 1, 15, 0},
    0,
    sUnitMenuItemDefs,
    0,
    DebugToolsUnit_OnEnd,
    0,
    MenuCancelSelect,
    0,
    0
};

static u8 DebugToolsUnit_ConfirmSelected(struct MenuProc* menu, struct MenuItemProc* item)
{
    struct Unit* unit;

    (void)menu;
    (void)item;

    unit = GetUnitFromCharId(DEBUGTOOLS_UNIT_TARGET_CHARACTER);

    DEBUGTOOLS_ASSERT(UNIT_IS_VALID(unit), DEBUGTOOLS_ASSERT_UNIT_TARGET_INVALID);

    if (UNIT_IS_VALID(unit))
    {
        SetUnitHp(unit, GetUnitMaxHp(unit));
        SetUnitStatus(unit, 0);

        gDebugToolsProbe.unitHealTransactionCount++;
        DebugTools_LogEvent(DEBUGTOOLS_LOG_UNIT_HEAL_APPLIED,
            (u32)GetUnitCurrentHp(unit), (u32)GetUnitMaxHp(unit));
    }
    else
    {
        DebugTools_LogEvent(DEBUGTOOLS_LOG_UNIT_HEAL_SKIPPED_INVALID, 0, 0);
    }

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

static void DebugToolsUnit_BuildMenuItems(void)
{
    memset(sUnitMenuItemDefs, 0, sizeof(sUnitMenuItemDefs));

    sUnitMenuItemDefs[0].name = "Confirm Heal to Full";
    sUnitMenuItemDefs[0].overrideId = DEBUGTOOLS_UNIT_OVERRIDE_ID;
    sUnitMenuItemDefs[0].isAvailable = MenuAlwaysEnabled;
    sUnitMenuItemDefs[0].onSelected = DebugToolsUnit_ConfirmSelected;

    sUnitMenuItemDefs[1].name = "Back";
    sUnitMenuItemDefs[1].isAvailable = MenuAlwaysEnabled;
    sUnitMenuItemDefs[1].onSelected = MenuCancelSelect;

    /* sUnitMenuItemDefs[2] stays all-zero: the terminator. */
}

static u8 DebugToolsActions_UnitInspectSelected(struct MenuProc* menu, struct MenuItemProc* item)
{
    struct Unit* unit;
    char buf[24];

    (void)menu;
    (void)item;

    unit = GetUnitFromCharId(DEBUGTOOLS_UNIT_TARGET_CHARACTER);

    if (UNIT_IS_VALID(unit))
    {
        gDebugToolsProbe.unitInspectTargetFound = 1;
        gDebugToolsProbe.unitInspectLastCurHp = (u32)GetUnitCurrentHp(unit);
        gDebugToolsProbe.unitInspectLastMaxHp = (u32)GetUnitMaxHp(unit);
        sprintf(buf, "UNIT HP %d/%d", GetUnitCurrentHp(unit), GetUnitMaxHp(unit));
    }
    else
    {
        gDebugToolsProbe.unitInspectTargetFound = 0;
        gDebugToolsProbe.unitInspectLastCurHp = 0;
        gDebugToolsProbe.unitInspectLastMaxHp = 0;
        sprintf(buf, "UNIT N/A");
    }

    DebugTools_LogEvent(DEBUGTOOLS_LOG_UNIT_INSPECT,
        gDebugToolsProbe.unitInspectLastCurHp, gDebugToolsProbe.unitInspectLastMaxHp);
    DebugToolsTools_ShowStatusLine(buf);

    DebugToolsUnit_BuildMenuItems();
    StartOrphanMenu(&gDebugToolsUnitMenuDef);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

CONST_DATA static struct DebugToolsAction sUnitInspectAction = {
    5, "Unit Inspect", DebugToolsActions_UnitInspectSelected
};

/* --- 6. Convoy inspection/edit ------------------------------------------ */

EWRAM_DATA static struct MenuItemDef sConvoyMenuItemDefs[3] = {{0}};

static void DebugToolsConvoy_OnEnd(struct MenuProc* menu)
{
    (void)menu;

    DebugTools_OpenHub();
}

CONST_DATA struct MenuDef gDebugToolsConvoyMenuDef = {
    {1, 1, 15, 0},
    0,
    sConvoyMenuItemDefs,
    0,
    DebugToolsConvoy_OnEnd,
    0,
    MenuCancelSelect,
    0,
    0
};

static u8 DebugToolsConvoy_ConfirmSelected(struct MenuProc* menu, struct MenuItemProc* item)
{
    int slot;

    (void)menu;
    (void)item;

    /* AddItemToConvoy (src/bmcontainer.c) already bounds-checks capacity
     * internally and returns -1 without mutating anything when full --
     * no separate DEBUGTOOLS_ASSERT is needed to keep this bounded, but
     * the result is still explicitly branched on so a full convoy is a
     * logged, visible no-op rather than a silently ignored request. */
    slot = AddItemToConvoy(DEBUGTOOLS_CONVOY_TEST_ITEM);

    if (slot != -1)
    {
        gDebugToolsProbe.convoyAddTransactionCount++;
        DebugTools_LogEvent(DEBUGTOOLS_LOG_CONVOY_ADD_APPLIED,
            (u32)DEBUGTOOLS_CONVOY_TEST_ITEM, (u32)slot);
    }
    else
    {
        DebugTools_LogEvent(DEBUGTOOLS_LOG_CONVOY_ADD_SKIPPED_FULL,
            (u32)DEBUGTOOLS_CONVOY_TEST_ITEM, 0);
    }

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

static void DebugToolsConvoy_BuildMenuItems(void)
{
    memset(sConvoyMenuItemDefs, 0, sizeof(sConvoyMenuItemDefs));

    sConvoyMenuItemDefs[0].name = "Confirm Add Item";
    sConvoyMenuItemDefs[0].overrideId = DEBUGTOOLS_CONVOY_OVERRIDE_ID;
    sConvoyMenuItemDefs[0].isAvailable = MenuAlwaysEnabled;
    sConvoyMenuItemDefs[0].onSelected = DebugToolsConvoy_ConfirmSelected;

    sConvoyMenuItemDefs[1].name = "Back";
    sConvoyMenuItemDefs[1].isAvailable = MenuAlwaysEnabled;
    sConvoyMenuItemDefs[1].onSelected = MenuCancelSelect;
}

static u8 DebugToolsActions_ConvoyInspectSelected(struct MenuProc* menu, struct MenuItemProc* item)
{
    int count;
    char buf[24];

    (void)menu;
    (void)item;

    count = GetConvoyItemCount();
    gDebugToolsProbe.convoyLastItemCount = (u32)count;
    sprintf(buf, "CONVOY %d/%d", count, (int)CONVOY_ITEM_COUNT);

    DebugTools_LogEvent(DEBUGTOOLS_LOG_CONVOY_INSPECT, (u32)count, 0);
    DebugToolsTools_ShowStatusLine(buf);

    DebugToolsConvoy_BuildMenuItems();
    StartOrphanMenu(&gDebugToolsConvoyMenuDef);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

CONST_DATA static struct DebugToolsAction sConvoyInspectAction = {
    6, "Convoy Inspect", DebugToolsActions_ConvoyInspectSelected
};

/* --- 7. Flag/chapter/event state action ---------------------------------- */

EWRAM_DATA static struct MenuItemDef sFlagMenuItemDefs[3] = {{0}};

static void DebugToolsFlag_OnEnd(struct MenuProc* menu)
{
    (void)menu;

    DebugTools_OpenHub();
}

CONST_DATA struct MenuDef gDebugToolsFlagMenuDef = {
    {1, 1, 15, 0},
    0,
    sFlagMenuItemDefs,
    0,
    DebugToolsFlag_OnEnd,
    0,
    MenuCancelSelect,
    0,
    0
};

static u8 DebugToolsFlag_ConfirmSelected(struct MenuProc* menu, struct MenuItemProc* item)
{
    int inRange;

    (void)menu;
    (void)item;

    /* Defense in depth: SetFlag/ClearFlag (src/eventinfo.c) do not
     * themselves bounds-check a chapter-scoped index against
     * GetChapterFlagBitsSize()*8 -- this re-validation is what makes the
     * fixed DEBUGTOOLS_DEBUG_EVENT_FLAG_ID constant an explicitly
     * range-validated target rather than a trusted-by-convention one. */
    inRange = (DEBUGTOOLS_DEBUG_EVENT_FLAG_ID >= 0)
        && (DEBUGTOOLS_DEBUG_EVENT_FLAG_ID < GetChapterFlagBitsSize() * 8);

    DEBUGTOOLS_ASSERT(inRange, DEBUGTOOLS_ASSERT_FLAG_ID_OUT_OF_RANGE);

    if (inRange)
    {
        if (CheckFlag(DEBUGTOOLS_DEBUG_EVENT_FLAG_ID))
            ClearFlag(DEBUGTOOLS_DEBUG_EVENT_FLAG_ID);
        else
            SetFlag(DEBUGTOOLS_DEBUG_EVENT_FLAG_ID);

        gDebugToolsProbe.debugFlagToggleCount++;
        gDebugToolsProbe.debugFlagLastValue = (u32)CheckFlag(DEBUGTOOLS_DEBUG_EVENT_FLAG_ID);

        DebugTools_LogEvent(DEBUGTOOLS_LOG_FLAG_TOGGLE_APPLIED,
            gDebugToolsProbe.debugFlagLastValue, 0);
    }

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

static void DebugToolsFlag_BuildMenuItems(void)
{
    memset(sFlagMenuItemDefs, 0, sizeof(sFlagMenuItemDefs));

    sFlagMenuItemDefs[0].name = "Confirm Toggle Flag";
    sFlagMenuItemDefs[0].overrideId = DEBUGTOOLS_FLAG_OVERRIDE_ID;
    sFlagMenuItemDefs[0].isAvailable = MenuAlwaysEnabled;
    sFlagMenuItemDefs[0].onSelected = DebugToolsFlag_ConfirmSelected;

    sFlagMenuItemDefs[1].name = "Back";
    sFlagMenuItemDefs[1].isAvailable = MenuAlwaysEnabled;
    sFlagMenuItemDefs[1].onSelected = MenuCancelSelect;
}

static u8 DebugToolsActions_FlagInspectSelected(struct MenuProc* menu, struct MenuItemProc* item)
{
    char buf[24];

    (void)menu;
    (void)item;

    gDebugToolsProbe.chapterIndexSample = (u32)(u8)gPlaySt.chapterIndex;
    gDebugToolsProbe.debugFlagLastValue = (u32)CheckFlag(DEBUGTOOLS_DEBUG_EVENT_FLAG_ID);
    sprintf(buf, "CH %d FLAG %d", (int)(u8)gPlaySt.chapterIndex,
        (int)gDebugToolsProbe.debugFlagLastValue);

    DebugTools_LogEvent(DEBUGTOOLS_LOG_FLAG_INSPECT,
        gDebugToolsProbe.chapterIndexSample, gDebugToolsProbe.debugFlagLastValue);
    DebugToolsTools_ShowStatusLine(buf);

    DebugToolsFlag_BuildMenuItems();
    StartOrphanMenu(&gDebugToolsFlagMenuDef);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

CONST_DATA static struct DebugToolsAction sFlagInspectAction = {
    7, "Flag/Chapter", DebugToolsActions_FlagInspectSelected
};

/* --- 8. RNG inspection/control ------------------------------------------ */

EWRAM_DATA static struct MenuItemDef sRngMenuItemDefs[3] = {{0}};

static void DebugToolsRng_OnEnd(struct MenuProc* menu)
{
    (void)menu;

    DebugTools_OpenHub();
}

CONST_DATA struct MenuDef gDebugToolsRngMenuDef = {
    {1, 1, 15, 0},
    0,
    sRngMenuItemDefs,
    0,
    DebugToolsRng_OnEnd,
    0,
    MenuCancelSelect,
    0,
    0
};

static u8 DebugToolsRng_ConfirmSelected(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;

    /* Same reseed idiom src/gamecontrol.c's Chapter 2/4 launchers already
     * use (SetLCGRNValue then InitRN(AdvanceGetLCGRNValue())) -- a
     * bounded, fully-deterministic RNG control action, never a raw seed
     * write outside of rng.c's own public API. */
    SetLCGRNValue((s32)DEBUGTOOLS_TOOLS_RNG_SEED);
    InitRN((s32)AdvanceGetLCGRNValue());

    gDebugToolsProbe.rngReseedTransactionCount++;
    DebugTools_LogEvent(DEBUGTOOLS_LOG_RNG_RESEED_APPLIED, DEBUGTOOLS_TOOLS_RNG_SEED, 0);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

static void DebugToolsRng_BuildMenuItems(void)
{
    memset(sRngMenuItemDefs, 0, sizeof(sRngMenuItemDefs));

    sRngMenuItemDefs[0].name = "Confirm Reseed";
    sRngMenuItemDefs[0].overrideId = DEBUGTOOLS_RNG_OVERRIDE_ID;
    sRngMenuItemDefs[0].isAvailable = MenuAlwaysEnabled;
    sRngMenuItemDefs[0].onSelected = DebugToolsRng_ConfirmSelected;

    sRngMenuItemDefs[1].name = "Back";
    sRngMenuItemDefs[1].isAvailable = MenuAlwaysEnabled;
    sRngMenuItemDefs[1].onSelected = MenuCancelSelect;
}

static u8 DebugToolsActions_RngInspectSelected(struct MenuProc* menu, struct MenuItemProc* item)
{
    u16 seeds[3];
    char buf[24];

    (void)menu;
    (void)item;

    StoreRNState(seeds);
    gDebugToolsProbe.rngInspectSeedSample0 = (u32)seeds[0];
    sprintf(buf, "RNG SEED %04X", (unsigned int)seeds[0]);

    DebugTools_LogEvent(DEBUGTOOLS_LOG_RNG_INSPECT, (u32)seeds[0], 0);
    DebugToolsTools_ShowStatusLine(buf);

    DebugToolsRng_BuildMenuItems();
    StartOrphanMenu(&gDebugToolsRngMenuDef);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

CONST_DATA static struct DebugToolsAction sRngInspectAction = {
    8, "RNG Inspect", DebugToolsActions_RngInspectSelected
};

/* --- 9. Save compatibility/state inspection (read-only) ------------------ */

EWRAM_DATA static struct MenuItemDef sSaveStateMenuItemDefs[2] = {{0}}; /* back + terminator: nothing to confirm */

static void DebugToolsSaveState_OnEnd(struct MenuProc* menu)
{
    (void)menu;

    DebugTools_OpenHub();
}

CONST_DATA struct MenuDef gDebugToolsSaveStateMenuDef = {
    {1, 1, 15, 0},
    0,
    sSaveStateMenuItemDefs,
    0,
    DebugToolsSaveState_OnEnd,
    0,
    MenuCancelSelect,
    0,
    0
};

static void DebugToolsSaveState_BuildMenuItems(void)
{
    memset(sSaveStateMenuItemDefs, 0, sizeof(sSaveStateMenuItemDefs));

    sSaveStateMenuItemDefs[0].name = "Back";
    sSaveStateMenuItemDefs[0].isAvailable = MenuAlwaysEnabled;
    sSaveStateMenuItemDefs[0].onSelected = MenuCancelSelect;
}

static u8 DebugToolsActions_SaveStateInspectSelected(struct MenuProc* menu, struct MenuItemProc* item)
{
    enum SaveCompatState state;
    char buf[24];

    (void)menu;
    (void)item;

    /* Read-only: ClassifySramSaveCompat (src/bmsave-lib.c) only inspects
     * the global save header/expansion metadata record and never mutates
     * SRAM or any save-block struct -- see include/save_format.h. This
     * tool never calls BuildCurrentExpansionSaveMeta with a live SRAM
     * target, InitGlobalSaveInfodata, or any writer. */
    state = ClassifySramSaveCompat();
    gDebugToolsProbe.saveCompatLastState = (u32)state;
    gDebugToolsProbe.saveCompatInspectCount++;
    sprintf(buf, "SAVE STATE %d", (int)state);

    DebugTools_LogEvent(DEBUGTOOLS_LOG_SAVESTATE_INSPECT, (u32)state, 0);
    DebugToolsTools_ShowStatusLine(buf);

    DebugToolsSaveState_BuildMenuItems();
    StartOrphanMenu(&gDebugToolsSaveStateMenuDef);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

CONST_DATA static struct DebugToolsAction sSaveStateInspectAction = {
    9, "Save State", DebugToolsActions_SaveStateInspectSelected
};

/* --- Registration -------------------------------------------------------- */

void DebugTools_RegisterExtendedToolActions(void)
{
    /* Idempotent: a repeat call reports DEBUGTOOLS_ERR_DUPLICATE (same
     * id/label) for each action -- an expected, non-silent result this
     * one-shot lazy-init call site (DebugTools_OpenHub,
     * src/debugtools_registry.c) deliberately ignores, same as
     * DebugTools_RegisterBuiltinActions/DebugTools_RegisterWeatherFogActions. */
    DebugTools_RegisterAction(&sUnitInspectAction);
    DebugTools_RegisterAction(&sConvoyInspectAction);
    DebugTools_RegisterAction(&sFlagInspectAction);
    DebugTools_RegisterAction(&sRngInspectAction);
    DebugTools_RegisterAction(&sSaveStateInspectAction);
}

#else /* !FE8_EXPANSION_DEBUGTOOLS_ENABLED */

void DebugTools_RegisterExtendedToolActions(void)
{
    /* No-op: nothing to register in a release build. */
}

#endif /* FE8_EXPANSION_DEBUGTOOLS_ENABLED */
