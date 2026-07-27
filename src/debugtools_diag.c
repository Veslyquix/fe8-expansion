#include "global.h"

#include "expansion_debugtools.h"

/*
 * Issue #11 closure -- diagnostics foundation: a bounded structured
 * probe/log ring plus a non-fatal assert record. See the "Diagnostics"
 * block comment in include/expansion_debugtools.h for the full contract
 * and explicit non-goals (no mgba_printf, no interactive debugger, no
 * arbitrary memory editor).
 *
 * Every entry point below compiles to a trivial disabled stub when
 * FE8_EXPANSION_DEBUGTOOLS_ENABLED is 0, same convention as every other
 * file in this subsystem.
 */

#if FE8_EXPANSION_DEBUGTOOLS_ENABLED

EWRAM_DATA static struct DebugToolsLogEntry sLogRing[DEBUGTOOLS_LOG_RING_SIZE] = {{0}};
EWRAM_DATA static u32 sLogRingTotalWrites = 0;

void DebugTools_LogEvent(u32 code, u32 a, u32 b)
{
    int slot = (int)(sLogRingTotalWrites % DEBUGTOOLS_LOG_RING_SIZE);

    sLogRing[slot].code = code;
    sLogRing[slot].a = a;
    sLogRing[slot].b = b;

    sLogRingTotalWrites++;

    gDebugToolsProbe.logEventCount = sLogRingTotalWrites;
    gDebugToolsProbe.lastLogCode = code;
}

int DebugTools_GetLogCount(void)
{
    if (sLogRingTotalWrites >= DEBUGTOOLS_LOG_RING_SIZE)
        return DEBUGTOOLS_LOG_RING_SIZE;

    return (int)sLogRingTotalWrites;
}

const struct DebugToolsLogEntry* DebugTools_GetLogEntry(int index)
{
    int count = DebugTools_GetLogCount();
    int slot;

    if (index < 0 || index >= count)
        return NULL;

    /* index 0 == most recently written entry: walk backward from the
     * next-write slot. */
    slot = (int)((sLogRingTotalWrites - 1 - (u32)index) % DEBUGTOOLS_LOG_RING_SIZE);

    return &sLogRing[slot];
}

void DebugTools_RecordAssertFailure(u32 code)
{
    gDebugToolsProbe.assertFailureCount++;
    gDebugToolsProbe.lastAssertCode = code;

    DebugTools_LogEvent(DEBUGTOOLS_LOG_ASSERT_FAILURE, code, 0);
}

u32 DebugTools_GetAssertFailureCount(void)
{
    return gDebugToolsProbe.assertFailureCount;
}

u32 DebugTools_GetLastAssertCode(void)
{
    return gDebugToolsProbe.lastAssertCode;
}

#else /* !FE8_EXPANSION_DEBUGTOOLS_ENABLED */

void DebugTools_LogEvent(u32 code, u32 a, u32 b)
{
    /* No-op: nothing to log in a release build. */
    (void)code;
    (void)a;
    (void)b;
}

int DebugTools_GetLogCount(void)
{
    return 0;
}

const struct DebugToolsLogEntry* DebugTools_GetLogEntry(int index)
{
    (void)index;

    return NULL;
}

void DebugTools_RecordAssertFailure(u32 code)
{
    /* No-op: nothing to record in a release build. */
    (void)code;
}

u32 DebugTools_GetAssertFailureCount(void)
{
    return 0;
}

u32 DebugTools_GetLastAssertCode(void)
{
    return DEBUGTOOLS_ASSERT_NONE;
}

#endif /* FE8_EXPANSION_DEBUGTOOLS_ENABLED */
