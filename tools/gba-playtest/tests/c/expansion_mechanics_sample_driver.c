/*
 * Issue #6 host test driver -- bundled sample mechanic (Full-HP Guard).
 *
 * Links against the real src/expansion_mechanics.c compiled with both
 * FE8_EXPANSION_MECHANICS_HOOKS=1 and FE8_EXPANSION_MECHANICS_SAMPLE=1 (see
 * test_expansion_mechanics.py). Proves the sample is installed through the
 * public registration API (never special-cased), that its effect is exactly
 * +1 battleDefense at full HP, that it does nothing below full HP, and that
 * it is clamped at the cap. Prints "MECHANICS_SAMPLE_HOST_TEST: PASS".
 */
#include <stdio.h>
#include <string.h>

#include "global.h"
#include "bmbattle.h"
#include "expansion_mechanics.h"

#define CHECK(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "MECHANICS_SAMPLE_HOST_TEST: FAIL: %s\n", msg); \
            return 1; \
        } \
    } while (0)

static void ApplyWith(struct BattleUnit* subject, int maxHp, int curHp, int def)
{
    memset(subject, 0, sizeof(*subject));
    subject->unit.maxHP = (s8)maxHp;
    subject->unit.curHP = (s8)curHp;
    subject->battleDefense = (short)def;
    ExpansionMechanicsApplyBattleStats(subject, NULL, 0);
}

int main(void)
{
    struct BattleUnit subject;

    /* --- InstallBuiltins registers exactly the sample, via the public API. --- */
    ExpansionMechanicsReset();
    ExpansionMechanicsInstallBuiltins();
    CHECK(ExpansionMechanicsCount() == 1, "exactly one built-in must be installed");
    CHECK(strcmp(ExpansionMechanicsKeyAt(0), EXPANSION_MECHANICS_SAMPLE_KEY) == 0,
          "the built-in must be the sample, registered by key");

    /* Idempotent: installing again must not duplicate it. */
    ExpansionMechanicsInstallBuiltins();
    CHECK(ExpansionMechanicsCount() == 1, "InstallBuiltins must be idempotent");

    /* --- Full HP: exactly +1 battleDefense, probe trigger counted. --- */
    ExpansionMechanicsReset();
    memset(&gExpansionMechanicsProbe, 0, sizeof(gExpansionMechanicsProbe));
    ApplyWith(&subject, 20, 20, 5);
    CHECK(subject.battleDefense == 6, "full-HP guard must add exactly 1 to battleDefense");
    CHECK(gExpansionMechanicsProbe.sampleTriggerCount == 1, "sample trigger must be counted once");
    CHECK(gExpansionMechanicsProbe.lastDefenseDelta == 1, "net defense delta must be 1");

    /* --- Below full HP: no effect. --- */
    ExpansionMechanicsReset();
    memset(&gExpansionMechanicsProbe, 0, sizeof(gExpansionMechanicsProbe));
    ApplyWith(&subject, 20, 19, 5);
    CHECK(subject.battleDefense == 5, "below full HP the guard must not fire");
    CHECK(gExpansionMechanicsProbe.sampleTriggerCount == 0, "no trigger below full HP");
    CHECK(gExpansionMechanicsProbe.lastDefenseDelta == 0, "no delta below full HP");

    /* --- Clamp at the cap: full HP but already at cap yields no bonus. --- */
    ExpansionMechanicsReset();
    memset(&gExpansionMechanicsProbe, 0, sizeof(gExpansionMechanicsProbe));
    ApplyWith(&subject, 20, 20, EXPANSION_MECHANICS_SAMPLE_GUARD_CAP);
    CHECK(subject.battleDefense == EXPANSION_MECHANICS_SAMPLE_GUARD_CAP,
          "guard must be clamped at the cap");
    CHECK(gExpansionMechanicsProbe.sampleTriggerCount == 0, "no trigger when clamped");

    /* --- Zero maxHP guard: never divides-by-zero / never fires. --- */
    ExpansionMechanicsReset();
    ApplyWith(&subject, 0, 0, 5);
    CHECK(subject.battleDefense == 5, "a unit with zero maxHP must not trigger the guard");

    printf("MECHANICS_SAMPLE_HOST_TEST: PASS\n");
    return 0;
}
