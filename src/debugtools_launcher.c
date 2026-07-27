#include "global.h"

#include "proc.h"
#include "uimenu.h"
#include "bmunit.h"
#include "playerphase.h"
#include "expansion_debugtools.h"

/*
 * Lifecycle-safe deterministic Chapter 2 launcher.
 *
 * The earlier "Fast Boot" action tore down and restarted the whole
 * GameCtrlProc tree from inside its own (orphan MenuProc) onSelected
 * callback -- proc-tree lifecycle corruption that hung later
 * prologue/Chapter 1/Chapter 2 experiments at unrelated event/fade stages.
 * This file now owns only the one built-in hub action ("Fast Boot: Chapter
 * 2") plus the pending-request/bootstrap-suppression state it arms: the
 * action itself never touches gProcScr_GameControl, gProc_BMapMain, units,
 * or events. See include/expansion_debugtools.h and docs/debugtools.md for
 * the full handoff (Title_IDLE detects the pending request after the hub
 * closes; GameControl_PostIntro, in src/gamecontrol.c, is the only place
 * that consumes it and performs the actual deterministic boot).
 */

#if FE8_EXPANSION_DEBUGTOOLS_ENABLED

EWRAM_DATA static u8 sChapter2LaunchPending = 0;
EWRAM_DATA static u8 sBootstrapSuppressionActive = 0;
EWRAM_DATA static u16 sBootstrapObserverTimer = 0;

/* Bounded fail-safe for the observer below: comfortably above the
 * ~13050-frame arm-to-interactive window the debug playtest scenario
 * actually exercises (frame 950 arm -> frame 14000 interactive, see
 * docs/debugtools.md) -- only a genuinely stuck/abandoned deterministic
 * boot can ever reach this, never a normal Chapter 2 run. */
#define DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES 21600

static u8 DebugToolsLauncher_FastBootChapter2(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;

    /* Only arms the pending request and closes the hub -- no
     * Proc_EndEach/Proc_Start of gProcScr_GameControl, no Proc_Goto of
     * gProc_BMapMain, no unit/event manipulation. */
    DebugTools_RequestChapter2Launch();

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

CONST_DATA static struct DebugToolsAction sFastBootChapter2Action = {
    1, "Fast Boot: Chapter 2", DebugToolsLauncher_FastBootChapter2
};

static u8 DebugToolsLauncher_FastBootChapter4Prep(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;

    /* Only arms the pending request and closes the hub -- exactly the
     * same narrow contract as DebugToolsLauncher_FastBootChapter2 above:
     * no Proc_EndEach/Proc_Start of gProcScr_GameControl, no Proc_Goto of
     * gProc_BMapMain, no unit/event manipulation. */
    DebugTools_RequestChapter4PrepLaunch();

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

CONST_DATA static struct DebugToolsAction sFastBootChapter4PrepAction = {
    4, "Fast Boot: Ch4 Prep", DebugToolsLauncher_FastBootChapter4Prep
};

void DebugTools_RegisterBuiltinActions(void)
{
    /* Idempotent: a repeat call reports DEBUGTOOLS_ERR_DUPLICATE (same
     * id/label) -- an expected, non-silent result that this one-shot
     * lazy-init call site deliberately ignores. Registers *only* the
     * Chapter 2 launcher -- unchanged from before issue #11 closure, so
     * Weather/Fog's own hub-menu row indices (registered right after
     * this call, from DebugTools_RegisterWeatherFogActions) stay exactly
     * where every pre-existing scenario's own input script already
     * expects them. */
    DebugTools_RegisterAction(&sFastBootChapter2Action);
}

/* Issue #11 closure: registered from its own call, deliberately *after*
 * DebugTools_RegisterWeatherFogActions() in DebugTools_OpenHub()
 * (src/debugtools_registry.c) -- not bundled into
 * DebugTools_RegisterBuiltinActions() above -- specifically so this new
 * action never shifts Weather/Fog's own pre-existing hub-menu row
 * indices (1, 2), which every debugtools-map-hub-modern-*.json scenario's
 * own cursor-navigation input script already depends on. */
void DebugTools_RegisterChapter4PrepAction(void)
{
    DebugTools_RegisterAction(&sFastBootChapter4PrepAction);
}

void DebugTools_RequestChapter2Launch(void)
{
    /* Idempotent: a second arm while one is already pending changes
     * nothing observable -- exactly one request is ever queued. */
    sChapter2LaunchPending = 1;
    gDebugToolsProbe.pendingLaunchRequest = DEBUGTOOLS_LAUNCH_REQUEST_MAGIC;
}

int DebugTools_IsChapter2LaunchPending(void)
{
    return sChapter2LaunchPending;
}

int DebugTools_ConsumePendingChapter2Launch(void)
{
    if (!sChapter2LaunchPending)
        return 0;

    sChapter2LaunchPending = 0;
    gDebugToolsProbe.pendingLaunchRequest = 0;
    gDebugToolsProbe.launchRequestConsumedCount++;

    return 1;
}

/* --- Fast Boot: Chapter 4 (Prep) --------------------------------------
 * Issue #11 closure: a second, independent hub action + pending-request
 * pair, reaching Chapter 4 instead of Chapter 2. Chapter 4's own
 * beginning event script (EventScr_Ch4_BeginningScene,
 * src/events/ch4-eventscript.h) calls CALL(EventScr_CommonPrep) partway
 * through -- unlike Chapter 2's, which never does -- so this is the
 * deterministic path to a genuine, live PrepScreenProc
 * (gProcScr_SALLYCURSOR) that exercises the debug-tools prep hotkey
 * entry point against real engine behavior. Entirely independent state from the
 * Chapter 2 request above: arming one never affects the other, and
 * GameControl_PostIntro (src/gamecontrol.c) consumes each at its own
 * call site. Both share the same DebugTools_ArmBootstrapSuppression()/
 * DebugToolsObserver_WaitForStablePlayerPhase machinery below -- that
 * machinery is already chapter-agnostic (it only ever polls
 * gPlaySt.faction/gProcScr_PlayerPhase, never a specific chapter index),
 * so no changes were needed there for a second launch target. */

EWRAM_DATA static u8 sChapter4PrepLaunchPending = 0;

void DebugTools_RequestChapter4PrepLaunch(void)
{
    /* Idempotent, same contract as DebugTools_RequestChapter2Launch. */
    sChapter4PrepLaunchPending = 1;
    gDebugToolsProbe.pendingCh4PrepLaunchRequest = DEBUGTOOLS_LAUNCH_REQUEST_MAGIC;
}

int DebugTools_IsChapter4PrepLaunchPending(void)
{
    return sChapter4PrepLaunchPending;
}

int DebugTools_ConsumePendingChapter4PrepLaunch(void)
{
    if (!sChapter4PrepLaunchPending)
        return 0;

    sChapter4PrepLaunchPending = 0;
    gDebugToolsProbe.pendingCh4PrepLaunchRequest = 0;
    gDebugToolsProbe.ch4PrepLaunchRequestConsumedCount++;

    return 1;
}

/* Bootstrap observer end callback (PROC_SET_END_CB below): runs exactly
 * once, synchronously, on EVERY termination path of the observer proc --
 * its own Proc_Break-to-PROC_END fallthrough (success/title-return/
 * timeout, all below), this module's own explicit
 * DebugTools_CleanupBootstrapObserver() (via Proc_End), or any other
 * future teardown of PROC_TREE_3 -- so the one-shot suppression can never
 * outlive this proc, regardless of *why* or *how* it ends. This is the
 * single source of truth for clearing suppression; nothing else in this
 * file clears it directly.
 *
 * Deliberately not `static`: not part of the public API (not declared in
 * include/expansion_debugtools.h), but host tests
 * (tools/gba-playtest/tests/c/debugtools_launcher_driver.c) link directly
 * against the real, unmodified src/debugtools_launcher.c and call this
 * (and DebugToolsObserver_WaitForStablePlayerPhase below) directly to
 * prove each termination path's own effect with real executed code,
 * rather than only through the public arm/cleanup entry points. */
void DebugToolsObserver_OnEnd(ProcPtr proc)
{
    (void)proc;

    sBootstrapSuppressionActive = 0;
    gDebugToolsProbe.bootstrapSuppressionActive = 0;
}

/* Bootstrap observer: polls, once per frame, for either of two mutually
 * exclusive success/fail-safe end conditions, and does nothing at all (no
 * state change, no proc redirect) until one is met:
 *
 *   1. Success -- blue faction's own gProcScr_PlayerPhase actually
 *      running: the first stable Player Phase of the deterministic boot.
 *   2. Timeout -- DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES elapsed
 *      without success: a bounded fail-safe for any stuck/abandoned
 *      path the explicit success check above never catches.
 *
 * The third fail-safe end condition -- the run being abandoned/returned
 * to title before a stable Player Phase was ever reached -- is handled
 * separately, by DebugTools_NotifyTitleScreenStarting below, called
 * directly from src/titlescreen.c's StartTitleScreen_* functions the
 * moment gProcScr_TitleScreen is actually (re)started, rather than by
 * this poll scanning the proc tree for it: Proc_Find(gProcScr_TitleScreen)
 * cannot reliably distinguish "the title screen is actually running
 * again" from "a just-freed proc slot's stale proc_script field still
 * happens to equal that pointer" (FreeProcess, src/proc.c, never clears
 * proc_script on free) -- which, in practice, false-positived on this
 * poll's very first tick every single time (the just-ended real title
 * screen proc's own freed slot), clearing suppression almost immediately
 * and letting BmMain_SuspendBeforePhase's WriteSuspendSave fire for real
 * in the middle of the deterministic boot, corrupting/stalling the rest
 * of Chapter 2's progression. Both paths funnel through the same
 * DebugTools_CleanupBootstrapObserver(), so DebugToolsObserver_OnEnd
 * still remains the one and only place suppression actually clears
 * either way.
 *
 * Every path below ends identically -- Proc_Break(proc), falling through
 * to this script's own PROC_END -- so DebugToolsObserver_OnEnd is always
 * the one and only place suppression actually clears. It never redirects
 * gProcScr_PlayerPhase, gProcScr_TitleScreen, gProc_BMapMain, or any
 * other proc.
 *
 * Deliberately not `static` -- see DebugToolsObserver_OnEnd above: host
 * tests call this directly with a driver-owned ProcPtr to prove each of
 * the two branches independently (which counter increments, that
 * Proc_Break fires exactly once per detected condition and not
 * otherwise), without needing the real GBA Proc script dispatcher. */
void DebugToolsObserver_WaitForStablePlayerPhase(ProcPtr proc)
{
    if (gPlaySt.faction == FACTION_BLUE && Proc_Find(gProcScr_PlayerPhase) != NULL)
    {
        gDebugToolsProbe.playerPhaseObservedCount++;
        Proc_Break(proc);
        return;
    }

    if (++sBootstrapObserverTimer >= DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES)
    {
        gDebugToolsProbe.observerTimeoutCount++;
        Proc_Break(proc);
        return;
    }
}

static struct ProcCmd CONST_DATA sDebugToolsBootstrapObserverScript[] = {
    PROC_SET_END_CB(DebugToolsObserver_OnEnd),
    PROC_REPEAT(DebugToolsObserver_WaitForStablePlayerPhase),
    PROC_END,
};

void DebugTools_CleanupBootstrapObserver(void)
{
    /* Explicit, idempotent, synchronous cleanup -- safe to call at any
     * time, including when no observer is currently alive (a plain
     * no-op then, no double-decrement/-clear of anything). Proc_Find is
     * the authoritative singleton check: it can only ever report at most
     * one live proc for this script, because every arm below always
     * routes through here first, and every observer termination path
     * (success/title-return/timeout/this function) always ends the
     * previous one before another is ever started. Proc_End is
     * synchronous (unlike Proc_Break, which only takes effect on that
     * proc's own next scheduled tick), so this is the one call site
     * allowed to end the observer directly from OUTSIDE its own tick;
     * DebugToolsObserver_OnEnd (the script's PROC_SET_END_CB) still fires
     * synchronously from inside Proc_End itself, so suppression clears
     * exactly as it would for any other termination path. */
    ProcPtr observer = Proc_Find(sDebugToolsBootstrapObserverScript);

    if (observer != NULL)
        Proc_End(observer);

    /* Fail-safe even on the (should-never-happen) chance Proc_Find ever
     * failed to locate a live observer this module itself started --
     * suppression is cleared here too, matching what the end callback
     * would otherwise do. */
    sBootstrapSuppressionActive = 0;
    gDebugToolsProbe.bootstrapSuppressionActive = 0;
}

void DebugTools_ArmBootstrapSuppression(void)
{
    /* Fail-safe singleton (see DebugTools_CleanupBootstrapObserver): a
     * repeated arm -- whether from a genuinely new launch or a stale
     * observer left over from a prior aborted/incomplete boot -- always
     * cleans up any existing observer/flag first, then starts exactly
     * one fresh observer. Two observers can therefore never be alive at
     * once, and suppression can never be left stuck on by a duplicate
     * arm. */
    DebugTools_CleanupBootstrapObserver();

    sBootstrapSuppressionActive = 1;
    gDebugToolsProbe.bootstrapSuppressionActive = 1;
    gDebugToolsProbe.bootstrapObserverArmCount++;
    sBootstrapObserverTimer = 0;

    Proc_Start(sDebugToolsBootstrapObserverScript, PROC_TREE_3);
}

int DebugTools_IsBootstrapSuppressionActive(void)
{
    return sBootstrapSuppressionActive;
}

void DebugTools_NotifyTitleScreenStarting(void)
{
    /* No-op whenever suppression is not currently active -- an ordinary
     * title screen (re)start (first boot, a real user quitting back to
     * title, etc.) is not "abandoning a pending deterministic boot".
     * gDebugToolsProbe.observerTitleReturnCount and the cleanup call
     * below only ever fire while a bootstrap observer genuinely still
     * has suppression armed. */
    if (!sBootstrapSuppressionActive)
        return;

    gDebugToolsProbe.observerTitleReturnCount++;
    DebugTools_CleanupBootstrapObserver();
}

#else /* !FE8_EXPANSION_DEBUGTOOLS_ENABLED */

void DebugTools_RegisterBuiltinActions(void)
{
    /* No-op: nothing to register in a release build. */
}

void DebugTools_RegisterChapter4PrepAction(void)
{
    /* No-op: nothing to register in a release build. */
}

void DebugTools_RequestChapter2Launch(void)
{
    /* No-op: the hub/action are unreachable in a release build. */
}

int DebugTools_IsChapter2LaunchPending(void)
{
    return 0;
}

int DebugTools_ConsumePendingChapter2Launch(void)
{
    return 0;
}

void DebugTools_RequestChapter4PrepLaunch(void)
{
    /* No-op: the hub/action are unreachable in a release build. */
}

int DebugTools_IsChapter4PrepLaunchPending(void)
{
    return 0;
}

int DebugTools_ConsumePendingChapter4PrepLaunch(void)
{
    return 0;
}

void DebugTools_ArmBootstrapSuppression(void)
{
    /* No-op: nothing to suppress, no observer to start. */
}

void DebugTools_CleanupBootstrapObserver(void)
{
    /* No-op: no observer/flag can exist in a release build. */
}

int DebugTools_IsBootstrapSuppressionActive(void)
{
    return 0;
}

void DebugTools_NotifyTitleScreenStarting(void)
{
    /* No-op: no observer/flag can exist in a release build. */
}

#endif /* FE8_EXPANSION_DEBUGTOOLS_ENABLED */
