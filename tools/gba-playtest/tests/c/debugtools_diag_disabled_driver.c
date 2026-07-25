/*
 * Issue #11 closure -- disabled-path host test driver for
 * src/debugtools_diag.c. Compiled and linked against the real translation
 * unit with FE8_EXPANSION_DEBUGTOOLS_ENABLED=0 (the same gate a supported
 * modern release build uses): every entry point must physically collapse
 * to a trivial no-op/zero-returning stub, with no ring/assert-record
 * storage of any kind required to link successfully.
 *
 * Prints "DEBUGTOOLS_DIAG_DISABLED_HOST_TEST: PASS" and exits 0 on
 * success.
 */
#include <stdio.h>

#include "global.h"
#include "expansion_debugtools.h"

#define CHECK(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "DEBUGTOOLS_DIAG_DISABLED_HOST_TEST: FAIL: %s\n", msg); \
            return 1; \
        } \
    } while (0)

struct DebugToolsProbe gDebugToolsProbe = {0};

int main(void)
{
    DebugTools_LogEvent(DEBUGTOOLS_LOG_UNIT_INSPECT, 1, 2);
    CHECK(DebugTools_GetLogCount() == 0, "disabled build must never record any log entry");
    CHECK(DebugTools_GetLogEntry(0) == NULL, "disabled build must always return NULL for any log entry index");
    CHECK(gDebugToolsProbe.logEventCount == 0, "disabled build must leave gDebugToolsProbe.logEventCount at 0");

    DEBUGTOOLS_ASSERT(0, DEBUGTOOLS_ASSERT_UNIT_TARGET_INVALID);
    CHECK(DebugTools_GetAssertFailureCount() == 0, "disabled build must never record an assert failure");
    CHECK(DebugTools_GetLastAssertCode() == DEBUGTOOLS_ASSERT_NONE, "disabled build's last assert code must stay DEBUGTOOLS_ASSERT_NONE");
    CHECK(gDebugToolsProbe.assertFailureCount == 0, "disabled build must leave gDebugToolsProbe.assertFailureCount at 0");

    printf("DEBUGTOOLS_DIAG_DISABLED_HOST_TEST: PASS\n");
    return 0;
}
