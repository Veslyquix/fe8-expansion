/*
 * Fast Boot: Chapter 2 lifecycle host tests -- host-test-only stub
 * implementations for the small set of Proc-engine/game-state symbols
 * that src/debugtools_launcher.c references but this host test never
 * actually needs to execute end to end (real proc scheduling, real
 * world-map/battle-map state). These stubs exist ONLY so the real,
 * unmodified src/debugtools_launcher.c can be compiled and linked with a
 * native host compiler (see
 * tools/gba-playtest/tests/test_debugtools_registry.py) to exercise its
 * pending-request/bootstrap-suppression logic with real executed code
 * instead of source-text pattern matching alone.
 *
 * Proc_Start/Proc_Find/Proc_Break are instrumented (call counts + last
 * script pointer recorded) rather than merely stubbed inert, so tests can
 * assert exactly which proc APIs the launcher action does and does not
 * call -- in particular, that DebugToolsLauncher_FastBootChapter2 (the hub
 * action) never calls Proc_Start/Proc_Break/Proc_Find at all (it only
 * arms a flag), while DebugTools_ArmBootstrapSuppression (called only from
 * src/gamecontrol.c, never from the launcher action) is the sole caller
 * that starts the bootstrap observer proc.
 *
 * This file is never compiled into the actual GBA ROM (not referenced by
 * modern.mk/Makefile) and is not itself part of the debug-tools feature.
 */
#include "global.h"
#include "proc.h"
#include "playerphase.h"
#include "bmunit.h"
#include "hardware.h"
#include "fontgrp.h"
#include "uimenu.h"

struct PlaySt gPlaySt;

/* src/debugtools_registry.c (the real, unmodified hub/registry owner of
 * gDebugToolsProbe and DebugTools_RegisterAction) is linked alongside
 * src/debugtools_launcher.c for this driver, so only its own small set of
 * hardware/menu-engine stand-ins (menu construction/rendering, hardware
 * key polling) are needed here -- mirrors debugtools_host_stubs.c, minus
 * that file's DebugTools_RegisterBuiltinActions override (this driver
 * links the real one from src/debugtools_launcher.c instead). */
struct KeyStatusBuffer gDebugToolsLauncherTestKeyStatus = {0};
struct KeyStatusBuffer * CONST_DATA gKeyStatusPtr = &gDebugToolsLauncherTestKeyStatus;

struct LCDControlBuffer gLCDControlBuffer = {0};

static u16 sDebugToolsLauncherStubBgMap[32 * 32];

u16* BG_GetMapBuffer(int bg)
{
    (void)bg;
    return sDebugToolsLauncherStubBgMap;
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

struct MenuProc* StartOrphanMenu(const struct MenuDef* def)
{
    (void)def;
    return NULL;
}

int gDebugToolsHostStub_ProcStartCallCount = 0;
int gDebugToolsHostStub_ProcBreakCallCount = 0;
int gDebugToolsHostStub_ProcFindCallCount = 0;
int gDebugToolsHostStub_ProcEndCallCount = 0;
const struct ProcCmd* gDebugToolsHostStub_LastStartedScript = NULL;

/* A single static "handle" is returned for any script Proc_Start is asked
 * to start. Proc_Find reports it as present for exactly two
 * independently-toggleable identities, matched by script pointer (never
 * by a single undifferentiated flag -- this driver needs to prove
 * DebugToolsObserver_WaitForStablePlayerPhase reacts to
 * gProcScr_PlayerPhase specifically, and separately prove the bootstrap
 * observer's own script is a real singleton). The title-return/
 * abandoned-run condition is no longer a Proc_Find-based poll (see
 * src/debugtools_launcher.c's DebugTools_NotifyTitleScreenStarting doc
 * comment for why: FreeProcess, src/proc.c, never clears a freed proc's
 * proc_script field, so scanning for a live gProcScr_TitleScreen instance
 * cannot reliably distinguish it from a stale freed slot) -- it is now an
 * explicit, event-driven call this driver exercises directly:
 *
 *   1. gProcScr_PlayerPhase, once DebugToolsHostStub_SetPlayerPhaseRunning(1)
 *      has been called (success condition);
 *   2. whichever script Proc_Start most recently started (the bootstrap
 *      observer itself, captured via gDebugToolsHostStub_LastStartedScript),
 *      for as long as sObserverAlive is set -- Proc_Start sets it, Proc_End
 *      clears it, so DebugTools_CleanupBootstrapObserver's own
 *      Proc_Find(...)-then-Proc_End(...) sequence can be driven and
 *      observed with real executed code instead of being assumed. */
static int sPlayerPhaseRunning = 0;
static int sObserverAlive = 0;
static int sFakeProcHandle;

void DebugToolsHostStub_SetPlayerPhaseRunning(int running)
{
    sPlayerPhaseRunning = running;
}

int DebugToolsHostStub_IsObserverAlive(void)
{
    return sObserverAlive;
}

ProcPtr Proc_Start(const struct ProcCmd* script, ProcPtr parent)
{
    (void)parent;
    gDebugToolsHostStub_ProcStartCallCount++;
    gDebugToolsHostStub_LastStartedScript = script;
    sObserverAlive = 1;
    return &sFakeProcHandle;
}

void Proc_Break(ProcPtr proc)
{
    (void)proc;
    gDebugToolsHostStub_ProcBreakCallCount++;
}

void Proc_End(ProcPtr proc)
{
    (void)proc;
    gDebugToolsHostStub_ProcEndCallCount++;
    sObserverAlive = 0;
}

ProcPtr Proc_Find(const struct ProcCmd* script)
{
    gDebugToolsHostStub_ProcFindCallCount++;

    if (script == gProcScr_PlayerPhase && sPlayerPhaseRunning)
        return &sFakeProcHandle;

    if (script == gDebugToolsHostStub_LastStartedScript && sObserverAlive)
        return &sFakeProcHandle;

    return NULL;
}

void DebugTools_RegisterWeatherFogActions(void)
{
    /* The real implementation (src/debugtools_actions.c, slice 2) has its
     * own dedicated host tests (debugtools_actions_driver.c). This driver
     * links the whole of src/debugtools_registry.c (whose DebugTools_OpenHub
     * calls this function unconditionally), so a stub must exist here even
     * though this launcher-lifecycle driver never itself calls OpenHub. */
}

void DebugTools_RegisterExtendedToolActions(void)
{
    /* Issue #11 closure: the real implementation (src/debugtools_tools.c)
     * has its own dedicated host tests. Same rationale as
     * DebugTools_RegisterWeatherFogActions above -- src/debugtools_registry.c's
     * DebugTools_OpenHub calls this function unconditionally, so a stub
     * must exist here even though this launcher-lifecycle driver never
     * itself calls OpenHub. */
}

/* DebugToolsObserver_WaitForStablePlayerPhase is a PROC_REPEAT callback:
 * this host test drives it directly (see debugtools_launcher_driver.c),
 * so gProcScr_PlayerPhase only needs to exist as a distinguishable
 * pointer value, never actually run. */
struct ProcCmd gProcScr_PlayerPhase[] = { { 0, NULL } };
