/*
 * Issue #11 closure -- host-executed diagnostics foundation behavior test
 * driver.
 *
 * Links directly against the real, unmodified src/debugtools_diag.c
 * (compiled for the host, see test_debugtools_registry.py) plus its own
 * definition of gDebugToolsProbe (src/debugtools_diag.c only ever
 * *references* that struct through include/expansion_debugtools.h's
 * extern declaration -- it never defines it, so this driver must, rather
 * than pulling in the whole registry module for a diagnostics-only test).
 * Drives DebugTools_LogEvent/DebugTools_GetLogCount/DebugTools_GetLogEntry/
 * DebugTools_RecordAssertFailure/DebugTools_GetAssertFailureCount/
 * DebugTools_GetLastAssertCode/DEBUGTOOLS_ASSERT through the exact public
 * API any tool uses (include/expansion_debugtools.h) -- not a
 * reimplementation of the ring/assert logic.
 *
 * Prints "DEBUGTOOLS_DIAG_HOST_TEST: PASS" and exits 0 on success; on any
 * failure it prints the specific failing assertion to stderr and exits 1
 * without running further checks (fail fast, actionable diagnostic).
 */
#include <stdio.h>

#include "global.h"
#include "expansion_debugtools.h"

#define CHECK(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "DEBUGTOOLS_DIAG_HOST_TEST: FAIL: %s\n", msg); \
            return 1; \
        } \
    } while (0)

struct DebugToolsProbe gDebugToolsProbe = {0};

int main(void)
{
    const struct DebugToolsLogEntry* entry;
    int i;

    /* --- Empty ring: no entries yet. ---------------------------------- */
    CHECK(DebugTools_GetLogCount() == 0, "log ring must start empty");
    CHECK(DebugTools_GetLogEntry(0) == NULL, "index 0 of an empty ring must be NULL");
    CHECK(DebugTools_GetLogEntry(-1) == NULL, "a negative index must always be NULL");
    CHECK(gDebugToolsProbe.logEventCount == 0, "probe logEventCount must start at 0");
    CHECK(gDebugToolsProbe.lastLogCode == 0, "probe lastLogCode must start at 0");

    /* --- One entry: readable at index 0 (most recent). ---------------- */
    DebugTools_LogEvent(DEBUGTOOLS_LOG_UNIT_INSPECT, 7, 12);
    CHECK(DebugTools_GetLogCount() == 1, "log count must be 1 after one event");
    entry = DebugTools_GetLogEntry(0);
    CHECK(entry != NULL, "index 0 must be readable after one event");
    CHECK(entry->code == DEBUGTOOLS_LOG_UNIT_INSPECT, "entry code must round-trip");
    CHECK(entry->a == 7, "entry a must round-trip");
    CHECK(entry->b == 12, "entry b must round-trip");
    CHECK(DebugTools_GetLogEntry(1) == NULL, "index 1 must be NULL with only one entry logged");
    CHECK(gDebugToolsProbe.logEventCount == 1, "probe logEventCount must mirror total writes");
    CHECK(gDebugToolsProbe.lastLogCode == DEBUGTOOLS_LOG_UNIT_INSPECT, "probe lastLogCode must mirror the most recent code");

    /* --- Fill to exactly ring capacity: count caps at
     * DEBUGTOOLS_LOG_RING_SIZE, not the unbounded total. --------------- */
    for (i = 0; i < DEBUGTOOLS_LOG_RING_SIZE - 1; ++i)
        DebugTools_LogEvent(DEBUGTOOLS_LOG_CONVOY_INSPECT, (u32)i, 0);

    CHECK(DebugTools_GetLogCount() == DEBUGTOOLS_LOG_RING_SIZE, "log count must cap at DEBUGTOOLS_LOG_RING_SIZE once full");
    CHECK((int)gDebugToolsProbe.logEventCount == DEBUGTOOLS_LOG_RING_SIZE,
          "probe logEventCount must equal the unbounded total, which now equals ring size exactly");

    /* --- Overwrite past capacity: ring wraps (bounded by construction,
     * never grows), oldest entry is silently overwritten, count never
     * exceeds DEBUGTOOLS_LOG_RING_SIZE, and the unbounded probe total
     * keeps counting past it. ------------------------------------------ */
    DebugTools_LogEvent(DEBUGTOOLS_LOG_RNG_INSPECT, 0xAAAA, 0xBBBB);
    CHECK(DebugTools_GetLogCount() == DEBUGTOOLS_LOG_RING_SIZE, "log count must stay capped at DEBUGTOOLS_LOG_RING_SIZE after wraparound");
    CHECK(gDebugToolsProbe.logEventCount == (u32)(DEBUGTOOLS_LOG_RING_SIZE + 1),
          "probe logEventCount must keep counting past ring capacity (unbounded total)");

    entry = DebugTools_GetLogEntry(0);
    CHECK(entry != NULL, "index 0 must still be readable after wraparound");
    CHECK(entry->code == DEBUGTOOLS_LOG_RNG_INSPECT, "index 0 must be the just-written (most recent) entry after wraparound");
    CHECK(entry->a == 0xAAAA, "the wraparound entry's payload must round-trip");
    CHECK(entry->b == 0xBBBB, "the wraparound entry's payload must round-trip");

    /* Write sequence so far: #1 = UNIT_INSPECT(a=7) -> slot 0, #2..#8 =
     * CONVOY_INSPECT(a=0..6) -> slots 1..7 (ring now exactly full, no
     * eviction yet), #9 = RNG_INSPECT(a=0xAAAA) -> slot (9-1)%8 == 0,
     * overwriting write #1. The oldest *surviving* entry is therefore
     * write #2 (CONVOY_INSPECT, a=0), not write #1 -- eviction removes
     * exactly the single oldest entry, never more. */
    entry = DebugTools_GetLogEntry(DEBUGTOOLS_LOG_RING_SIZE - 1);
    CHECK(entry != NULL, "the oldest surviving entry must still be readable");
    CHECK(entry->code == DEBUGTOOLS_LOG_CONVOY_INSPECT && entry->a == 0,
          "the very first entry (UNIT_INSPECT) must have been evicted; CONVOY_INSPECT a=0 must now be the oldest surviving entry");

    CHECK(DebugTools_GetLogEntry(DEBUGTOOLS_LOG_RING_SIZE) == NULL, "an index == count must always be NULL (out of range)");

    /* --- Assert record: starts clean, records on failure, never on
     * success, and is itself a logged ring event. ----------------------- */
    CHECK(DebugTools_GetAssertFailureCount() == 0, "assert failure count must start at 0");
    CHECK(DebugTools_GetLastAssertCode() == DEBUGTOOLS_ASSERT_NONE, "last assert code must start at DEBUGTOOLS_ASSERT_NONE");

    DEBUGTOOLS_ASSERT(1 == 1, DEBUGTOOLS_ASSERT_FLAG_ID_OUT_OF_RANGE);
    CHECK(DebugTools_GetAssertFailureCount() == 0, "a true condition must never record an assert failure");

    DEBUGTOOLS_ASSERT(1 == 0, DEBUGTOOLS_ASSERT_UNIT_TARGET_INVALID);
    CHECK(DebugTools_GetAssertFailureCount() == 1, "a false condition must record exactly one assert failure");
    CHECK(DebugTools_GetLastAssertCode() == DEBUGTOOLS_ASSERT_UNIT_TARGET_INVALID, "the recorded code must match the failed assert's own code");
    CHECK(gDebugToolsProbe.assertFailureCount == 1, "probe assertFailureCount must mirror the running total");
    CHECK(gDebugToolsProbe.lastAssertCode == DEBUGTOOLS_ASSERT_UNIT_TARGET_INVALID, "probe lastAssertCode must mirror the most recent failure");

    entry = DebugTools_GetLogEntry(0);
    CHECK(entry != NULL && entry->code == DEBUGTOOLS_LOG_ASSERT_FAILURE,
          "an assert failure must itself append a DEBUGTOOLS_LOG_ASSERT_FAILURE ring entry");
    CHECK(entry->a == DEBUGTOOLS_ASSERT_UNIT_TARGET_INVALID, "the assert-failure log entry must carry the failing code as its payload");

    DEBUGTOOLS_ASSERT(0, DEBUGTOOLS_ASSERT_CONVOY_INDEX_OUT_OF_RANGE);
    CHECK(DebugTools_GetAssertFailureCount() == 2, "a second failure must increment the running total, never reset it");
    CHECK(DebugTools_GetLastAssertCode() == DEBUGTOOLS_ASSERT_CONVOY_INDEX_OUT_OF_RANGE, "the most recent failure's code must overwrite the previous one");

    printf("DEBUGTOOLS_DIAG_HOST_TEST: PASS\n");
    return 0;
}
