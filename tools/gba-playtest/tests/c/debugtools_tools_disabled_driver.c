/*
 * Issue #11 closure -- disabled-path host test driver for
 * src/debugtools_tools.c. Compiled and linked against the real
 * translation unit with FE8_EXPANSION_DEBUGTOOLS_ENABLED=0 (the same gate
 * a supported modern release build uses): the whole extended-tools
 * module must physically collapse to the one harmless no-op public entry
 * point, with no menu/hardware/unit/convoy/flag/RNG/save-format stub of
 * any kind required to link successfully.
 *
 * Prints "DEBUGTOOLS_TOOLS_DISABLED_HOST_TEST: PASS" and exits 0 on
 * success.
 */
#include <stdio.h>

#include "global.h"
#include "expansion_debugtools.h"

int main(void)
{
    /* No menu/hardware/unit/convoy/flag/RNG/save-format stub of any kind
     * is linked alongside this driver and src/debugtools_tools.c
     * (disabled) -- if the disabled body ever grew a real dependency on
     * any of those, this driver would fail to *link*, not just fail an
     * assertion. */
    DebugTools_RegisterExtendedToolActions();

    printf("DEBUGTOOLS_TOOLS_DISABLED_HOST_TEST: PASS\n");
    return 0;
}
