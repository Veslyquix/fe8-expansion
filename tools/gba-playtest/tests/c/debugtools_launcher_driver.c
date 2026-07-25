/*
 * Fast Boot: Chapter 2 -- host-executed pending-request/bootstrap-
 * suppression lifecycle test driver.
 *
 * Links directly against the real, unmodified src/debugtools_launcher.c
 * (compiled for the host, see test_debugtools_registry.py) plus
 * debugtools_launcher_host_stubs.c's Proc_Start/Proc_Find/Proc_Break/
 * Proc_End instrumentation, and drives both the public pending-request/
 * bootstrap-suppression API (include/expansion_debugtools.h) and the two
 * internal-but-externally-linked observer helpers
 * (DebugToolsObserver_WaitForStablePlayerPhase, DebugToolsObserver_OnEnd
 * -- deliberately not `static`, and not declared in the public header;
 * see their doc comments in src/debugtools_launcher.c) directly: no Proc/
 * game-engine reimplementation, no source-text pattern matching for this
 * part of the proof.
 *
 * The observer's own poll body (DebugToolsObserver_WaitForStablePlayerPhase)
 * now only implements two of the three end conditions directly (success,
 * timeout); the third (abandoned/returned-to-title) is implemented as the
 * separate, event-driven DebugTools_NotifyTitleScreenStarting -- called
 * from src/titlescreen.c's StartTitleScreen_* functions, not polled via
 * Proc_Find(gProcScr_TitleScreen) -- because FreeProcess (src/proc.c)
 * never clears a freed proc's own proc_script field, so scanning the proc
 * tree for a live gProcScr_TitleScreen instance could not reliably
 * distinguish "the title screen is actually running again" from "a
 * just-freed proc slot's stale proc_script field still happens to equal
 * that pointer" -- exactly the false positive that, in the real ROM,
 * cleared suppression on the observer's very first tick and let
 * BmMain_SuspendBeforePhase's WriteSuspendSave fire mid-boot.
 *
 * Deliberately does NOT stub Proc_EndEach, gProcScr_GameControl,
 * gProc_BMapMain, InitUnits, or GmDataInit -- if src/debugtools_launcher.c
 * ever referenced any of those symbols, this driver would fail to *link*
 * (undefined reference), which is itself part of the proof that the hub
 * action never touches GameCtrlProc lifecycle, BMapMain, or unit/game-data
 * loading directly.
 *
 * Prints "DEBUGTOOLS_LAUNCHER_HOST_TEST: PASS" and exits 0 on success; on
 * any failure it prints the specific failing assertion to stderr and
 * exits 1 without running further checks (fail fast, actionable
 * diagnostic).
 */
#include <stdio.h>

#include "global.h"
#include "proc.h"
#include "expansion_debugtools.h"

extern int gDebugToolsHostStub_ProcStartCallCount;
extern int gDebugToolsHostStub_ProcBreakCallCount;
extern int gDebugToolsHostStub_ProcFindCallCount;
extern int gDebugToolsHostStub_ProcEndCallCount;

extern void DebugToolsHostStub_SetPlayerPhaseRunning(int running);
extern int DebugToolsHostStub_IsObserverAlive(void);

/* Deliberately not declared in include/expansion_debugtools.h -- see the
 * doc comments on both in src/debugtools_launcher.c for why they are
 * left with external linkage anyway. */
extern void DebugToolsObserver_WaitForStablePlayerPhase(ProcPtr proc);
extern void DebugToolsObserver_OnEnd(ProcPtr proc);

/* Mirrors the internal (not header-exposed) constant of the same name in
 * src/debugtools_launcher.c. test_debugtools_registry.py's structural
 * checks independently regex-extract that file's own definition and
 * assert it equals this literal, so this driver can never silently drift
 * out of sync with the real bound if it is ever tuned. */
#define DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES 21600

#define CHECK(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "DEBUGTOOLS_LAUNCHER_HOST_TEST: FAIL: %s\n", msg); \
            return 1; \
        } \
    } while (0)

static int sFakeObserverProc;

int main(void)
{
    int i;

    /* Fresh state: nothing pending, no suppression, no proc calls yet. */
    CHECK(!DebugTools_IsChapter2LaunchPending(), "expected no pending request at start");
    CHECK(!DebugTools_IsBootstrapSuppressionActive(), "expected no suppression at start");
    CHECK(gDebugToolsHostStub_ProcStartCallCount == 0, "expected zero Proc_Start calls before any arm");
    CHECK(gDebugToolsHostStub_ProcBreakCallCount == 0, "expected zero Proc_Break calls before any arm");

    /* Arming a request only sets the pending flag and probe magic --
     * never touches any proc API (Proc_Start/Proc_Break call counts must
     * both stay exactly 0 through this call). */
    DebugTools_RequestChapter2Launch();
    CHECK(DebugTools_IsChapter2LaunchPending(), "request must be pending after arming");
    CHECK(gDebugToolsProbe.pendingLaunchRequest == DEBUGTOOLS_LAUNCH_REQUEST_MAGIC,
          "probe.pendingLaunchRequest must carry the DBL2 magic once armed");
    CHECK(gDebugToolsHostStub_ProcStartCallCount == 0, "arming a request must never call Proc_Start");
    CHECK(gDebugToolsHostStub_ProcBreakCallCount == 0, "arming a request must never call Proc_Break");

    /* Explicit duplicate-request proof: arming again while already
     * pending changes nothing observable -- exactly one request is ever
     * queued, and it is still consumed exactly once below. */
    DebugTools_RequestChapter2Launch();
    CHECK(DebugTools_IsChapter2LaunchPending(), "request must still be pending after a duplicate arm");
    CHECK(gDebugToolsProbe.pendingLaunchRequest == DEBUGTOOLS_LAUNCH_REQUEST_MAGIC,
          "probe.pendingLaunchRequest must be unaffected by a duplicate arm");

    /* Consuming clears the pending flag, clears the probe magic, and
     * increments the consumed counter exactly once. */
    CHECK(DebugTools_ConsumePendingChapter2Launch() != 0,
          "consuming a pending request must report success (nonzero)");
    CHECK(!DebugTools_IsChapter2LaunchPending(), "request must no longer be pending after consuming");
    CHECK(gDebugToolsProbe.pendingLaunchRequest == 0,
          "probe.pendingLaunchRequest must clear back to 0 once consumed");
    CHECK(gDebugToolsProbe.launchRequestConsumedCount == 1,
          "launchRequestConsumedCount must read exactly 1 after the first consume");

    /* Consuming again with nothing pending (the duplicate arm above only
     * ever produced one queued request) must be an explicit no-op: report
     * failure (0) and must not increment the consumed counter again. */
    CHECK(DebugTools_ConsumePendingChapter2Launch() == 0,
          "consuming with nothing pending must report failure (0)");
    CHECK(gDebugToolsProbe.launchRequestConsumedCount == 1,
          "launchRequestConsumedCount must stay 1 -- a duplicate consume must never double-count");

    /*
     * ---- Bootstrap suppression / observer lifecycle -------------------
     */

    /* Arming the bootstrap suppression starts exactly one proc (the
     * bootstrap observer) via Proc_Start, and never calls Proc_EndEach
     * (not stubbed/linked at all -- see file header) or Proc_Break. */
    DebugTools_ArmBootstrapSuppression();
    CHECK(DebugTools_IsBootstrapSuppressionActive(), "suppression must be active immediately after arming");
    CHECK(gDebugToolsProbe.bootstrapSuppressionActive != 0,
          "probe.bootstrapSuppressionActive must be nonzero once armed");
    CHECK(gDebugToolsHostStub_ProcStartCallCount == 1,
          "arming bootstrap suppression must start exactly one proc (the observer)");
    CHECK(gDebugToolsHostStub_ProcBreakCallCount == 0,
          "arming bootstrap suppression must never call Proc_Break itself");
    CHECK(gDebugToolsProbe.bootstrapObserverArmCount == 1,
          "bootstrapObserverArmCount must read exactly 1 after the first arm");
    CHECK(DebugToolsHostStub_IsObserverAlive(), "the observer must be alive immediately after arming");

    /* MEDIUM fix, idempotent-arm proof: arming a second time while the
     * first observer is still alive must clean it up (exactly one
     * Proc_End call) before starting exactly one fresh one -- never two
     * concurrent observers, and suppression must remain active
     * throughout (a repeat arm is not a gap in coverage). */
    {
        int startsBefore = gDebugToolsHostStub_ProcStartCallCount;
        int endsBefore = gDebugToolsHostStub_ProcEndCallCount;

        DebugTools_ArmBootstrapSuppression();
        CHECK(gDebugToolsHostStub_ProcEndCallCount == endsBefore + 1,
              "a repeat arm must end exactly one prior observer (Proc_End called once)");
        CHECK(gDebugToolsHostStub_ProcStartCallCount == startsBefore + 1,
              "a repeat arm must start exactly one fresh observer (Proc_Start called once more)");
        CHECK(DebugToolsHostStub_IsObserverAlive(),
              "exactly one observer must be alive after a repeat arm -- never zero, never two");
        CHECK(DebugTools_IsBootstrapSuppressionActive(),
              "suppression must still read active across a repeat arm");
        CHECK(gDebugToolsProbe.bootstrapObserverArmCount == 2,
              "bootstrapObserverArmCount must read exactly 2 after the second arm -- explicit, "
              "observable evidence that the repeat was handled, not silently ignored or duplicated");
    }

    /* CRITICAL fix, explicit cancel/end proof: calling
     * DebugTools_CleanupBootstrapObserver() directly -- with no Player
     * Phase ever reached -- must end the live observer and clear
     * suppression immediately. */
    DebugTools_CleanupBootstrapObserver();
    CHECK(!DebugTools_IsBootstrapSuppressionActive(),
          "explicit cleanup must clear suppression even though no Player Phase was ever reached");
    CHECK(gDebugToolsProbe.bootstrapSuppressionActive == 0,
          "probe.bootstrapSuppressionActive must clear to 0 after explicit cleanup");
    CHECK(!DebugToolsHostStub_IsObserverAlive(), "explicit cleanup must end the live observer");
    CHECK(gDebugToolsProbe.playerPhaseObservedCount == 0,
          "playerPhaseObservedCount must stay 0 -- this was the explicit-cleanup path, not success");

    /* Cleanup must also be a safe, idempotent no-op with nothing alive
     * (no double-decrement, no crash, no change to any counter). */
    {
        int endsBefore = gDebugToolsHostStub_ProcEndCallCount;

        DebugTools_CleanupBootstrapObserver();
        CHECK(gDebugToolsHostStub_ProcEndCallCount == endsBefore,
              "cleanup with nothing alive must not call Proc_End again");
        CHECK(!DebugTools_IsBootstrapSuppressionActive(), "suppression must still read inactive");
    }

    /* Re-arm after cleanup: a fresh observer starts correctly, with its
     * own fresh timer (proven by the timeout sub-test below reaching
     * exactly DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES calls, not
     * fewer, i.e. the timer was not left over from the arms above). */
    DebugTools_ArmBootstrapSuppression();
    CHECK(DebugTools_IsBootstrapSuppressionActive(), "re-arm after cleanup must activate suppression again");
    CHECK(DebugToolsHostStub_IsObserverAlive(), "re-arm after cleanup must start a fresh observer");
    CHECK(gDebugToolsProbe.bootstrapObserverArmCount == 3,
          "bootstrapObserverArmCount must read exactly 3 after the third (re-)arm");

    /*
     * ---- Direct observer-branch proof (real executed code, no full
     * Proc script dispatcher needed) --------------------------------
     */

    /* Neither condition met, timer not yet at the bound: must not touch
     * Proc_Break or any of the three termination counters. */
    DebugToolsHostStub_SetPlayerPhaseRunning(0);
    {
        int breaksBefore = gDebugToolsHostStub_ProcBreakCallCount;

        DebugToolsObserver_WaitForStablePlayerPhase(&sFakeObserverProc);
        CHECK(gDebugToolsHostStub_ProcBreakCallCount == breaksBefore,
              "the observer must not call Proc_Break while neither condition is met and the timer "
              "has not reached its bound");
    }

    /* Success path: gProcScr_PlayerPhase reported running -> exactly one
     * Proc_Break, playerPhaseObservedCount increments once, the other two
     * counters stay at 0. */
    DebugToolsHostStub_SetPlayerPhaseRunning(1);
    {
        int breaksBefore = gDebugToolsHostStub_ProcBreakCallCount;
        u32 observedBefore = gDebugToolsProbe.playerPhaseObservedCount;

        DebugToolsObserver_WaitForStablePlayerPhase(&sFakeObserverProc);
        CHECK(gDebugToolsHostStub_ProcBreakCallCount == breaksBefore + 1,
              "the success branch must call Proc_Break exactly once");
        CHECK(gDebugToolsProbe.playerPhaseObservedCount == observedBefore + 1,
              "playerPhaseObservedCount must increment exactly once on the success branch");
    }
    CHECK(gDebugToolsProbe.observerTitleReturnCount == 0,
          "observerTitleReturnCount must stay 0 -- the success branch, not the title-return branch, fired");
    CHECK(gDebugToolsProbe.observerTimeoutCount == 0,
          "observerTimeoutCount must stay 0 -- the success branch, not the timeout branch, fired");
    DebugToolsHostStub_SetPlayerPhaseRunning(0);

    /* DebugToolsObserver_OnEnd, called directly, unconditionally clears
     * suppression -- proven here with suppression currently still active
     * (re-armed above) despite the direct WaitForStablePlayerPhase calls
     * above never having gone through the real Proc dispatcher (which
     * would otherwise be what invokes it after a Proc_Break). */
    CHECK(DebugTools_IsBootstrapSuppressionActive(),
          "suppression must still read active going into the direct OnEnd proof (calling "
          "WaitForStablePlayerPhase directly does not itself run the real dispatcher/PROC_SET_END_CB)");
    DebugToolsObserver_OnEnd(&sFakeObserverProc);
    CHECK(!DebugTools_IsBootstrapSuppressionActive(),
          "DebugToolsObserver_OnEnd must unconditionally clear suppression when called directly");

    /* And calling it again, with suppression already clear, is a safe
     * no-op (idempotent, matching every other termination path). */
    DebugToolsObserver_OnEnd(&sFakeObserverProc);
    CHECK(!DebugTools_IsBootstrapSuppressionActive(), "a repeat OnEnd call must stay a no-op");

    /* Title-return path: re-arm fresh, then call
     * DebugTools_NotifyTitleScreenStarting() directly (as
     * src/titlescreen.c's StartTitleScreen_* functions do the moment
     * gProcScr_TitleScreen is actually (re)started) -> exactly one
     * Proc_End (not Proc_Break -- this is the synchronous
     * DebugTools_CleanupBootstrapObserver() path, not the observer's own
     * PROC_REPEAT poll body), observerTitleReturnCount increments once,
     * the other two counters do not move, and suppression clears
     * immediately (unlike the poll-based branches above, this path does
     * not need the real dispatcher to run PROC_SET_END_CB afterward --
     * DebugTools_CleanupBootstrapObserver's Proc_End call triggers
     * DebugToolsObserver_OnEnd synchronously). */
    DebugTools_ArmBootstrapSuppression();
    CHECK(gDebugToolsProbe.bootstrapObserverArmCount == 4,
          "bootstrapObserverArmCount must read exactly 4 after the fourth (re-)arm");

    /* A title screen starting while suppression is NOT active (the
     * ordinary case -- first boot, a real user quitting back to title
     * after suppression already cleared, etc.) must be a complete no-op:
     * no Proc_End, no counter movement. Proven first, before the
     * suppression-active case below, so the two cases are never
     * conflated. */
    DebugTools_CleanupBootstrapObserver();
    {
        int endsBefore = gDebugToolsHostStub_ProcEndCallCount;
        u32 titleReturnsBefore = gDebugToolsProbe.observerTitleReturnCount;

        DebugTools_NotifyTitleScreenStarting();
        CHECK(gDebugToolsHostStub_ProcEndCallCount == endsBefore,
              "notifying title-screen-starting with no suppression active must not call Proc_End");
        CHECK(gDebugToolsProbe.observerTitleReturnCount == titleReturnsBefore,
              "observerTitleReturnCount must not move when suppression was not active");
    }

    DebugTools_ArmBootstrapSuppression();
    CHECK(gDebugToolsProbe.bootstrapObserverArmCount == 5,
          "bootstrapObserverArmCount must read exactly 5 after the fifth (re-)arm");
    {
        int endsBefore = gDebugToolsHostStub_ProcEndCallCount;
        u32 titleReturnsBefore = gDebugToolsProbe.observerTitleReturnCount;
        u32 observedBefore = gDebugToolsProbe.playerPhaseObservedCount;
        u32 timeoutsBefore = gDebugToolsProbe.observerTimeoutCount;

        DebugTools_NotifyTitleScreenStarting();
        CHECK(gDebugToolsHostStub_ProcEndCallCount == endsBefore + 1,
              "the title-return path must end the live observer via Proc_End exactly once");
        CHECK(gDebugToolsProbe.observerTitleReturnCount == titleReturnsBefore + 1,
              "observerTitleReturnCount must increment exactly once on the title-return path");
        CHECK(gDebugToolsProbe.playerPhaseObservedCount == observedBefore,
              "playerPhaseObservedCount must not move on the title-return path");
        CHECK(gDebugToolsProbe.observerTimeoutCount == timeoutsBefore,
              "observerTimeoutCount must not move on the title-return path");
        CHECK(!DebugTools_IsBootstrapSuppressionActive(),
              "the title-return path must clear suppression immediately (synchronous Proc_End, "
              "unlike the poll-based branches, which only take effect via the real dispatcher)");
        CHECK(!DebugToolsHostStub_IsObserverAlive(),
              "the title-return path must leave no observer alive");
    }

    /* Calling it again with suppression already clear is a safe no-op
     * (idempotent, matching every other termination path): no further
     * Proc_End, no further counter movement. */
    {
        int endsBefore = gDebugToolsHostStub_ProcEndCallCount;
        u32 titleReturnsBefore = gDebugToolsProbe.observerTitleReturnCount;

        DebugTools_NotifyTitleScreenStarting();
        CHECK(gDebugToolsHostStub_ProcEndCallCount == endsBefore,
              "a repeat notify with suppression already clear must not call Proc_End again");
        CHECK(gDebugToolsProbe.observerTitleReturnCount == titleReturnsBefore,
              "a repeat notify with suppression already clear must not increment the counter again");
    }

    /* Timeout path: re-arm fresh (resets the internal frame timer to 0),
     * then call the observer branch DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES
     * times with neither other condition met -- Proc_Break must fire on
     * (and only on) the final call, and observerTimeoutCount must
     * increment exactly once. This is the same bounded fail-safe the real
     * ROM relies on to never leave suppression stuck on indefinitely. */
    DebugTools_ArmBootstrapSuppression();
    CHECK(gDebugToolsProbe.bootstrapObserverArmCount == 6,
          "bootstrapObserverArmCount must read exactly 6 after the sixth (re-)arm");
    {
        u32 timeoutsBefore = gDebugToolsProbe.observerTimeoutCount;
        int breaksBefore = gDebugToolsHostStub_ProcBreakCallCount;

        for (i = 0; i < DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES - 1; i++)
        {
            DebugToolsObserver_WaitForStablePlayerPhase(&sFakeObserverProc);
            CHECK(gDebugToolsHostStub_ProcBreakCallCount == breaksBefore,
                  "the timeout branch must not fire before the bound is reached");
        }

        DebugToolsObserver_WaitForStablePlayerPhase(&sFakeObserverProc);
        CHECK(gDebugToolsHostStub_ProcBreakCallCount == breaksBefore + 1,
              "the timeout branch must call Proc_Break exactly once, on the frame the bound is reached");
        CHECK(gDebugToolsProbe.observerTimeoutCount == timeoutsBefore + 1,
              "observerTimeoutCount must increment exactly once when the bound is reached");
    }
    DebugTools_CleanupBootstrapObserver();
    CHECK(!DebugTools_IsBootstrapSuppressionActive(), "cleanup after the timeout probe must clear suppression");

    /*
     * ---- Ordinary post-clear behavior is not suppressed ---------------
     *
     * Host-code proof (not merely runtime-scenario-implied) that once the
     * observer has cleared suppression through any path above,
     * DebugTools_IsBootstrapSuppressionActive() reads 0 -- the exact
     * condition BmMain_SuspendBeforePhase (src/bm.c), PlayerPhase_Suspend
     * (src/playerphase.c), and UnlockSoundRoomSong (src/soundwrapper.c)
     * check before skipping their normal write. Each of those guards is
     * `if (DebugTools_IsBootstrapSuppressionActive()) return;` immediately
     * followed by its own ordinary write -- with this reading 0, none of
     * them takes the early return, so each falls through to its normal,
     * unsuppressed behavior. (Their own WriteSuspendSave/SRAM-write call
     * sites are not linked into this lightweight host driver -- see the
     * structural source checks in test_debugtools_registry.py for the
     * accompanying proof that this guard shape is actually what every one
     * of those three call sites contains.) */
    CHECK(!DebugTools_IsBootstrapSuppressionActive(),
          "ordinary post-clear state must read inactive -- BmMain_SuspendBeforePhase/PlayerPhase_Suspend/"
          "UnlockSoundRoomSong's shared guard must fall through to their normal write, not skip it");

    /* A fresh request can still be armed and consumed again on a later
     * boot cycle -- the pending-request one-shot behavior is per-request,
     * not a permanent latch, and is entirely independent of the
     * suppression/observer lifecycle exercised above. */
    DebugTools_RequestChapter2Launch();
    CHECK(DebugTools_IsChapter2LaunchPending(), "a new request after a prior consume must be pending again");
    CHECK(DebugTools_ConsumePendingChapter2Launch() != 0, "the new request must be consumable");
    CHECK(gDebugToolsProbe.launchRequestConsumedCount == 2,
          "launchRequestConsumedCount must read exactly 2 after the second consume");

    /*
     * ---- Issue #11 closure: the second, independent Chapter 4 Prep
     * pending-request pair -------------------------------------------
     *
     * Mirrors the Chapter 2 request's own one-shot arm/pending/consume
     * contract exactly (DebugTools_RequestChapter4PrepLaunch/
     * IsChapter4PrepLaunchPending/ConsumePendingChapter4PrepLaunch), and
     * additionally proves the two requests are entirely independent
     * state: arming/consuming one never observably affects the other.
     */
    CHECK(!DebugTools_IsChapter4PrepLaunchPending(), "Chapter 4 Prep request must start not pending");
    CHECK(gDebugToolsProbe.pendingCh4PrepLaunchRequest == 0, "probe pendingCh4PrepLaunchRequest must start at 0");

    DebugTools_RequestChapter4PrepLaunch();
    CHECK(DebugTools_IsChapter4PrepLaunchPending(), "arming the Chapter 4 Prep request must make it pending");
    CHECK(gDebugToolsProbe.pendingCh4PrepLaunchRequest == (u32)DEBUGTOOLS_LAUNCH_REQUEST_MAGIC,
          "probe pendingCh4PrepLaunchRequest must mirror the armed magic value");
    CHECK(!DebugTools_IsChapter2LaunchPending(), "arming the Chapter 4 Prep request must never affect the Chapter 2 request's own pending state");

    /* Idempotent: a duplicate arm changes nothing observable. */
    DebugTools_RequestChapter4PrepLaunch();
    CHECK(DebugTools_IsChapter4PrepLaunchPending(), "a duplicate arm must leave the request pending (no queued second launch)");

    CHECK(gDebugToolsProbe.ch4PrepLaunchRequestConsumedCount == 0, "probe ch4PrepLaunchRequestConsumedCount must start at 0");
    CHECK(DebugTools_ConsumePendingChapter4PrepLaunch() != 0, "a pending Chapter 4 Prep request must be consumable exactly once");
    CHECK(!DebugTools_IsChapter4PrepLaunchPending(), "consuming the Chapter 4 Prep request must clear its pending state");
    CHECK(gDebugToolsProbe.pendingCh4PrepLaunchRequest == 0, "probe pendingCh4PrepLaunchRequest must clear to 0 once consumed");
    CHECK(gDebugToolsProbe.ch4PrepLaunchRequestConsumedCount == 1, "ch4PrepLaunchRequestConsumedCount must increment exactly once per consume");

    /* One-shot: consuming an already-empty request is a no-op, and must
     * never affect the Chapter 2 request's own (already-consumed-twice)
     * counters. */
    CHECK(DebugTools_ConsumePendingChapter4PrepLaunch() == 0, "consuming an empty Chapter 4 Prep request must be a no-op");
    CHECK(gDebugToolsProbe.ch4PrepLaunchRequestConsumedCount == 1, "a no-op consume must never increment ch4PrepLaunchRequestConsumedCount");
    CHECK(gDebugToolsProbe.launchRequestConsumedCount == 2, "Chapter 4 Prep consume activity must never affect the Chapter 2 request's own counters");

    printf("DEBUGTOOLS_LAUNCHER_HOST_TEST: PASS\n");
    return 0;
}
