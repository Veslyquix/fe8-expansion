/*
 * Issue #18 sprint 4 host driver -- prints the real, compiler-computed
 * offsetof()/sizeof() layout of struct ExpansionLanguageMenuProbe
 * (include/expansion_language_menu.h) as plain "field=decimal" lines.
 *
 * This never links src/expansion_language_menu.c (offsetof/sizeof are
 * compile-time only, no symbols needed) -- it only proves the *header's*
 * own field order/packing, which is exactly what a real GBA `nm`/objdump
 * symbol-address readout would also reflect for gExpansionLanguageMenuProbe
 * (a plain EWRAM struct, no vtable/dynamic layout). Used by
 * test_locale_probe_schema.py to prove every hardcoded probe address in
 * tools/gba-playtest/scenarios/locale-*.json is `base + offsetof(field)`,
 * not an independently (and possibly incorrectly) guessed literal, so a
 * future header edit that reorders/resizes a field is caught here instead
 * of silently producing a wrong-field pinned fingerprint.
 */
#include <stddef.h>
#include <stdio.h>
#include "expansion_language_menu.h"

int main(void)
{
    printf("active=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, active));
    printf("settingsActive=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, settingsActive));
    printf("promptShown=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, promptShown));
    printf("autoSelected=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, autoSelected));
    printf("promptReason=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, promptReason));
    printf("prefsState=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, prefsState));
    printf("selectedLocale=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, selectedLocale));
    printf("currentLocale=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, currentLocale));
    printf("enabledLocaleCount=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, enabledLocaleCount));
    printf("cacheGeneration=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, cacheGeneration));
    printf("startupRunCount=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, startupRunCount));
    printf("settingsOpenCount=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, settingsOpenCount));
    printf("settingsChangeCount=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, settingsChangeCount));
    printf("needsPreferenceRepair=%zu\n", offsetof(struct ExpansionLanguageMenuProbe, needsPreferenceRepair));
    printf("sizeof=%zu\n", sizeof(struct ExpansionLanguageMenuProbe));
    return 0;
}
