/*
 * Issue #11 slice 2 -- host-test-only stub implementations for the small
 * set of GBA-hardware/menu-engine/proc/dormant-bmdebug symbols that
 * src/debugtools_actions.c references but this host test never actually
 * needs to execute for real (menu construction/rendering, hardware key
 * polling, the real ProcScr_DebugMonitor script, and the real dormant
 * DebugMenu_Weather.../DebugMenu_Fog... bodies in src/bmdebug.c). These stubs
 * exist ONLY so the real, unmodified src/debugtools_actions.c (and the
 * real, unmodified src/debugtools_registry.c linked alongside it) can be
 * compiled and linked with a native host compiler (see
 * tools/gba-playtest/tests/test_debugtools_registry.py) to exercise the
 * Weather/Fog adapter's registration/wiring/lifecycle logic with real
 * executed code instead of source-text pattern matching alone.
 *
 * Proc_Find/Proc_Start/Proc_EndEach and StartOrphanMenu are instrumented
 * (call counts + last-argument capture) rather than merely stubbed inert,
 * so the driver can assert exactly which proc/menu APIs the adapter calls
 * and with which arguments -- in particular, that the Weather action only
 * starts ProcScr_DebugMonitor when none is already alive, that its onEnd
 * only ever ends an instance it itself started, and that the Fog action
 * never touches ProcScr_DebugMonitor/Proc_EndEach at all.
 *
 * This file is never compiled into the actual GBA ROM (not referenced by
 * modern.mk/Makefile) and is not itself part of the debug-tools feature.
 */
#include "global.h"

#include "hardware.h"
#include "fontgrp.h"
#include "uimenu.h"
#include "proc.h"
#include "bmdebug.h"
#include "expansion_debugtools.h"

struct KeyStatusBuffer gDebugToolsActionsTestKeyStatus = {0};
struct KeyStatusBuffer * CONST_DATA gKeyStatusPtr = &gDebugToolsActionsTestKeyStatus;

struct LCDControlBuffer gLCDControlBuffer = {0};

/* Issue #11 closure: DebugTools_PrepHotkeyCheck (src/debugtools_registry.c)
 * now reads gPlaySt.chapterStateBits to observe a live prep screen --
 * a plain zero-initialized instance is enough for this Weather/Fog-
 * focused driver (PLAY_FLAG_PREPSCREEN simply reads as unset). */
struct PlaySt gPlaySt = {0};

static u16 sActionsStubBgMap[32 * 32];

u16* BG_GetMapBuffer(int bg)
{
    (void)bg;
    return sActionsStubBgMap;
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

/* --- StartOrphanMenu: captures the def pointer instead of discarding it,
 * so the driver can prove Weather/Fog's onSelected wired up exactly the
 * gDebugToolsWeatherMenuDef/gDebugToolsFogMenuDef sentinel -- never a
 * hand-rolled copy. --------------------------------------------------- */
int gDebugToolsActionsHostStub_StartOrphanMenuCallCount = 0;
const struct MenuDef* gDebugToolsActionsHostStub_LastMenuDef = NULL;

struct MenuProc* StartOrphanMenu(const struct MenuDef* def)
{
    gDebugToolsActionsHostStub_StartOrphanMenuCallCount++;
    gDebugToolsActionsHostStub_LastMenuDef = def;
    return NULL;
}

/* --- Proc engine: ProcScr_DebugMonitor only needs to exist as a
 * distinguishable pointer value for Proc_Find/Proc_Start/Proc_EndEach to
 * compare against below -- it is never actually scheduled/ticked here. */
struct ProcCmd CONST_DATA ProcScr_DebugMonitor[] = { { 0, NULL } };

int gDebugToolsActionsHostStub_ProcFindCallCount = 0;
int gDebugToolsActionsHostStub_ProcStartCallCount = 0;
int gDebugToolsActionsHostStub_ProcEndEachCallCount = 0;
const struct ProcCmd* gDebugToolsActionsHostStub_LastStartedScript = NULL;
const struct ProcCmd* gDebugToolsActionsHostStub_LastEndEachScript = NULL;

static int sMonitorAlive = 0;

void DebugToolsHostStub_SetMonitorAlive(int alive)
{
    sMonitorAlive = alive;
}

int DebugToolsHostStub_IsMonitorAlive(void)
{
    return sMonitorAlive;
}

ProcPtr Proc_Find(const struct ProcCmd* script)
{
    gDebugToolsActionsHostStub_ProcFindCallCount++;

    if (script == ProcScr_DebugMonitor && sMonitorAlive)
        return (ProcPtr)1; /* any non-NULL "handle" */

    return NULL;
}

ProcPtr Proc_Start(const struct ProcCmd* script, ProcPtr parent)
{
    (void)parent;
    gDebugToolsActionsHostStub_ProcStartCallCount++;
    gDebugToolsActionsHostStub_LastStartedScript = script;
    sMonitorAlive = 1;
    return (ProcPtr)1;
}

void Proc_EndEach(const struct ProcCmd* script)
{
    gDebugToolsActionsHostStub_ProcEndEachCallCount++;
    gDebugToolsActionsHostStub_LastEndEachScript = script;
    sMonitorAlive = 0;
}

/* --- Dormant src/bmdebug.c bodies: this driver only proves the adapter
 * wires these exact function pointers into its one live MenuItemDef, so
 * it never needs to link the real bmdebug.c (a huge, engine-dependent
 * file) -- distinct trivial stub bodies are enough for pointer-identity
 * comparisons in the driver. */
int gDebugToolsActionsHostStub_WeatherDrawCallCount = 0;
u8 gDebugToolsActionsHostStub_WeatherEffectCallCount = 0;
u8 gDebugToolsActionsHostStub_WeatherIdleCallCount = 0;
int gDebugToolsActionsHostStub_FogDrawCallCount = 0;
u8 gDebugToolsActionsHostStub_FogEffectCallCount = 0;
u8 gDebugToolsActionsHostStub_FogIdleCallCount = 0;

int DebugMenu_WeatherDraw(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;
    gDebugToolsActionsHostStub_WeatherDrawCallCount++;
    return 0;
}

u8 DebugMenu_WeatherEffect(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;
    gDebugToolsActionsHostStub_WeatherEffectCallCount++;
    return 0;
}

u8 DebugMenu_WeatherIdle(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;
    gDebugToolsActionsHostStub_WeatherIdleCallCount++;
    return 0;
}

int DebugMenu_FogDraw(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;
    gDebugToolsActionsHostStub_FogDrawCallCount++;
    return 0;
}

u8 DebugMenu_FogEffect(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;
    gDebugToolsActionsHostStub_FogEffectCallCount++;
    return 0;
}

u8 DebugMenu_FogIdle(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;
    gDebugToolsActionsHostStub_FogIdleCallCount++;
    return 0;
}

/* This driver links the real src/debugtools_registry.c alongside
 * src/debugtools_actions.c so DebugTools_OpenHub() (called from each
 * submenu's real onEnd) is the real implementation, not a stub -- but the
 * real launcher (src/debugtools_launcher.c) is deliberately not linked
 * here (out of scope for this driver), so its lazy-registration call site
 * still needs a stand-in. */
void DebugTools_RegisterBuiltinActions(void)
{
    /* Intentionally empty: this driver registers its own filler actions
     * directly (via DebugTools_RegisterAction) when it needs to prove the
     * "capacity remains <=9 including Chapter 2 launcher" boundary,
     * rather than depending on the real launcher module. */
}

void DebugTools_RegisterChapter4PrepAction(void)
{
    /* Issue #11 closure: the real implementation (src/debugtools_launcher.c)
     * has its own dedicated host tests and is deliberately not linked
     * here; src/debugtools_registry.c's DebugTools_OpenHub calls this
     * function unconditionally, so a stand-in is needed here too. */
}

void DebugTools_RegisterExtendedToolActions(void)
{
    /* Issue #11 closure: the real implementation (src/debugtools_tools.c)
     * has its own dedicated host tests and is deliberately not linked
     * here (out of scope for this Weather/Fog-focused driver), so its
     * lazy-registration call site (from DebugTools_OpenHub) still needs a
     * stand-in. */
}
