/*
 * Issue #11 closure -- host-test-only stub implementations for the small
 * set of GBA-hardware/menu-engine/unit/convoy/event-flag/RNG/save-format
 * symbols that src/debugtools_tools.c (and src/debugtools_registry.c,
 * linked alongside it) reference but this host test never needs the real
 * engine subsystem for (real unit/convoy/flag/RNG/save-format state is
 * owned by src/bmunit.c, src/bmcontainer.c, src/eventinfo.c, src/rng.c,
 * src/bmsave-lib.c -- each with their own deep proc/hardware/SRAM
 * dependency graphs well outside what a debug-tool-behavior host test
 * needs). Each fake below is small, test-controllable (via the
 * DebugToolsHostStub_Set* setters), and -- where the real semantics are
 * simple/pure -- mirrors the real implementation's own logic exactly
 * (SetUnitHp/SetUnitStatus's clamping, see src/bmunit.c) so the host test
 * still proves real behavioral semantics, not just call-count wiring.
 *
 * This file is never compiled into the actual GBA ROM (not referenced by
 * modern.mk/Makefile) and is not itself part of the debug-tools feature.
 */
#include <string.h>

#include "global.h"
#include "hardware.h"
#include "fontgrp.h"
#include "uimenu.h"
#include "proc.h"
#include "bmunit.h"
#include "bmcontainer.h"
#include "eventinfo.h"
#include "rng.h"
#include "bmsave.h"
#include "save_format.h"
#include "expansion_debugtools.h"

/* --- Hardware/menu stand-ins (mirrors debugtools_actions_host_stubs.c) - */

struct KeyStatusBuffer gDebugToolsToolsTestKeyStatus = {0};
struct KeyStatusBuffer * CONST_DATA gKeyStatusPtr = &gDebugToolsToolsTestKeyStatus;

struct LCDControlBuffer gLCDControlBuffer = {0};

static u16 sToolsStubBgMap[32 * 32];

u16* BG_GetMapBuffer(int bg)
{
    (void)bg;
    return sToolsStubBgMap;
}

void SetupDebugFontForBG(int bg, int tileDataOffset)
{
    (void)bg;
    (void)tileDataOffset;
}

void PrintDebugStringToBG(u16* bg, const char* asciiStr)
{
    (void)bg;
    (void)asciiStr;
}

u8 MenuAlwaysEnabled(const struct MenuItemDef* def, int number)
{
    (void)def;
    (void)number;
    return 1;
}

u8 MenuCancelSelect(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;
    return 0;
}

int gDebugToolsToolsHostStub_StartOrphanMenuCallCount = 0;
const struct MenuDef* gDebugToolsToolsHostStub_LastMenuDef = NULL;

struct MenuProc* StartOrphanMenu(const struct MenuDef* def)
{
    gDebugToolsToolsHostStub_StartOrphanMenuCallCount++;
    gDebugToolsToolsHostStub_LastMenuDef = def;
    return NULL;
}

/* This driver links the real src/debugtools_registry.c alongside
 * src/debugtools_tools.c so DebugTools_OpenHub() (called from each tool
 * submenu's real onEnd) is the real implementation -- but neither the
 * real launcher (src/debugtools_launcher.c) nor the real Weather/Fog
 * adapter (src/debugtools_actions.c) is linked here (out of scope for
 * this tools-focused driver), so their lazy-registration call sites still
 * need a stand-in. */
void DebugTools_RegisterBuiltinActions(void)
{
}

void DebugTools_RegisterChapter4PrepAction(void)
{
    /* Issue #11 closure: the real implementation (src/debugtools_launcher.c)
     * has its own dedicated host tests and is deliberately not linked
     * here; src/debugtools_registry.c's DebugTools_OpenHub calls this
     * function unconditionally, so a stand-in is needed here too. */
}

void DebugTools_RegisterWeatherFogActions(void)
{
}

/* --- gPlaySt: DebugTools_PrepHotkeyCheck (src/debugtools_registry.c) and
 * this driver's own Flag-tool inspect assertions read
 * gPlaySt.chapterStateBits/chapterIndex. --------------------------------- */
struct PlaySt gPlaySt = {0};

/* --- Unit inspector fakes -----------------------------------------------
 * GetUnitMaxHp/GetUnitCurrentHp/SetUnitHp/SetUnitStatus mirror
 * src/bmunit.c's own real clamping logic exactly (simple, pure struct
 * field access -- see that file's inline definitions) so this host test
 * proves real HP-clamp/status-clear semantics, not just call wiring.
 * GetUnitFromCharId is the one genuinely fake lookup: test-controllable
 * via DebugToolsHostStub_SetFakeUnit, so both the "target found" and
 * "target not found" paths are directly, deterministically testable. */

static struct Unit sDebugToolsToolsFakeUnit;
static int sDebugToolsToolsFakeUnitPresent = 0;

void DebugToolsHostStub_SetFakeUnit(int present, int curHp, int maxHp)
{
    sDebugToolsToolsFakeUnitPresent = present;

    if (present)
    {
        memset(&sDebugToolsToolsFakeUnit, 0, sizeof(sDebugToolsToolsFakeUnit));
        /* Any non-NULL pointer satisfies UNIT_IS_VALID's pCharacterData
         * check; this driver never dereferences it. */
        sDebugToolsToolsFakeUnit.pCharacterData = (const struct CharacterData*)&sDebugToolsToolsFakeUnit;
        sDebugToolsToolsFakeUnit.curHP = (s8)curHp;
        sDebugToolsToolsFakeUnit.maxHP = (s8)maxHp;
    }
}

struct Unit* GetUnitFromCharId(int charId)
{
    (void)charId;

    if (!sDebugToolsToolsFakeUnitPresent)
        return NULL;

    return &sDebugToolsToolsFakeUnit;
}

int GetUnitMaxHp(struct Unit* unit)
{
    return unit->maxHP;
}

int GetUnitCurrentHp(struct Unit* unit)
{
    return unit->curHP;
}

void SetUnitHp(struct Unit* unit, int value)
{
    unit->curHP = (s8)value;

    if (unit->curHP > GetUnitMaxHp(unit))
        unit->curHP = (s8)GetUnitMaxHp(unit);
}

void SetUnitStatus(struct Unit* unit, int status)
{
    if (status == 0)
    {
        unit->statusIndex = 0;
        unit->statusDuration = 0;
    }
    else
    {
        unit->statusIndex = (u8)status;
        unit->statusDuration = 5;
    }
}

/* --- Convoy inspector fakes ---------------------------------------------
 * A small test-controllable item count/capacity, mirroring
 * src/bmcontainer.c's own AddItemToConvoy contract (returns -1 without
 * mutating anything when full). */

static int sDebugToolsToolsFakeConvoyCount = 0;
static int sDebugToolsToolsFakeConvoyFull = 0;

void DebugToolsHostStub_SetFakeConvoy(int count, int full)
{
    sDebugToolsToolsFakeConvoyCount = count;
    sDebugToolsToolsFakeConvoyFull = full;
}

int GetConvoyItemCount(void)
{
    return sDebugToolsToolsFakeConvoyCount;
}

int AddItemToConvoy(int item)
{
    (void)item;

    if (sDebugToolsToolsFakeConvoyFull)
        return -1;

    sDebugToolsToolsFakeConvoyCount++;
    return sDebugToolsToolsFakeConvoyCount - 1;
}

/* --- Flag/chapter/event state fakes --------------------------------------
 * A small fixed-size chapter-scoped flag bit array, matching the real
 * GetChapterFlagBitsSize() == 5 (40 bits) exactly. */

static u8 sDebugToolsToolsFakeChapterFlagBits[5];

void DebugToolsHostStub_ClearFakeFlags(void)
{
    memset(sDebugToolsToolsFakeChapterFlagBits, 0, sizeof(sDebugToolsToolsFakeChapterFlagBits));
}

void SetFlag(int flag)
{
    sDebugToolsToolsFakeChapterFlagBits[flag / 8] |= (u8)(1 << (flag % 8));
}

void ClearFlag(int flag)
{
    sDebugToolsToolsFakeChapterFlagBits[flag / 8] &= (u8)~(1 << (flag % 8));
}

bool CheckFlag(int flag)
{
    return (sDebugToolsToolsFakeChapterFlagBits[flag / 8] >> (flag % 8)) & 1;
}

int GetChapterFlagBitsSize(void)
{
    return 5;
}

/* --- RNG inspect/control fakes -------------------------------------------
 * Test-controllable seed state; InitRN/SetLCGRNValue/AdvanceGetLCGRNValue
 * are wired so a reseed is directly observable (the new seed value is
 * mirrored into seeds[0]), without reimplementing the real LCG/Fibonacci
 * generator math src/rng.c owns. */

static u16 sDebugToolsToolsFakeRngSeeds[3] = {0x1111, 0x2222, 0x3333};
static s32 sDebugToolsToolsFakeLcgValue = 0;

void StoreRNState(u16* seeds)
{
    seeds[0] = sDebugToolsToolsFakeRngSeeds[0];
    seeds[1] = sDebugToolsToolsFakeRngSeeds[1];
    seeds[2] = sDebugToolsToolsFakeRngSeeds[2];
}

void LoadRNState(const u16* seeds)
{
    sDebugToolsToolsFakeRngSeeds[0] = seeds[0];
    sDebugToolsToolsFakeRngSeeds[1] = seeds[1];
    sDebugToolsToolsFakeRngSeeds[2] = seeds[2];
}

void SetLCGRNValue(s32 seed)
{
    sDebugToolsToolsFakeLcgValue = seed;
}

unsigned AdvanceGetLCGRNValue(void)
{
    return (unsigned)sDebugToolsToolsFakeLcgValue;
}

void InitRN(s32 seed)
{
    sDebugToolsToolsFakeRngSeeds[0] = (u16)seed;
    sDebugToolsToolsFakeRngSeeds[1] = (u16)(seed + 1);
    sDebugToolsToolsFakeRngSeeds[2] = (u16)(seed + 2);
}

int NextRN(void) { return 0; }
void InitRN_Unused(void) {}
int NextRN_100(void) { return 0; }
int NextRN_N(int max) { (void)max; return 0; }
s8 Roll1RN(int threshold) { (void)threshold; return 0; }
s8 Roll2RN(int threshold) { (void)threshold; return 0; }

/* --- Save compatibility/state inspection fakes --------------------------- */

static enum SaveCompatState sDebugToolsToolsFakeSaveCompatState = SAVE_COMPAT_CURRENT;

void DebugToolsHostStub_SetFakeSaveCompatState(enum SaveCompatState state)
{
    sDebugToolsToolsFakeSaveCompatState = state;
}

enum SaveCompatState ClassifySramSaveCompat(void)
{
    return sDebugToolsToolsFakeSaveCompatState;
}
