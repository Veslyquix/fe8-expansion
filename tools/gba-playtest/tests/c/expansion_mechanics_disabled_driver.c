/*
 * Issue #6 host test driver -- disabled path (FE8_EXPANSION_MECHANICS_HOOKS=0).
 *
 * Links against the real src/expansion_mechanics.c compiled with the feature
 * OFF. Proves every public entry point returns the disabled result / a no-op,
 * that apply changes nothing, and that the always-linked probe stays all-zero
 * (the negative-control invariant scenarios rely on). Prints
 * "MECHANICS_DISABLED_HOST_TEST: PASS".
 */
#include <stdio.h>
#include <string.h>

#include "global.h"
#include "bmbattle.h"
#include "expansion_mechanics.h"

#define CHECK(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "MECHANICS_DISABLED_HOST_TEST: FAIL: %s\n", msg); \
            return 1; \
        } \
    } while (0)

static void NoopMechanic(struct BattleUnit* subject, const struct ExpansionMechanicsContext* ctx)
{
    (void)subject;
    (void)ctx;
}

static int ProbeIsAllZero(void)
{
    const unsigned char* p = (const unsigned char*)&gExpansionMechanicsProbe;
    unsigned int i;
    for (i = 0; i < sizeof(gExpansionMechanicsProbe); i++)
    {
        if (p[i] != 0)
            return 0;
    }
    return 1;
}

int main(void)
{
    struct BattleUnit subject;

    memset(&gExpansionMechanicsProbe, 0, sizeof(gExpansionMechanicsProbe));

    CHECK(ExpansionMechanicsRegister("k", "l", NoopMechanic) == EXPANSION_MECHANICS_ERR_DISABLED,
          "register must report DISABLED when the feature is off");
    CHECK(ExpansionMechanicsCount() == 0, "disabled registry must always report 0");
    CHECK(ExpansionMechanicsKeyAt(0) == NULL, "disabled KeyAt must be NULL");
    CHECK(ExpansionMechanicsLabelAt(0) == NULL, "disabled LabelAt must be NULL");
    CHECK(ExpansionMechanicsLastResult() == EXPANSION_MECHANICS_ERR_DISABLED,
          "disabled LastResult must be DISABLED");
    CHECK(ExpansionMechanicsIsApplying() == 0, "disabled IsApplying must be 0");

    ExpansionMechanicsInstallBuiltins();
    CHECK(ExpansionMechanicsCount() == 0, "disabled InstallBuiltins must register nothing");

    memset(&subject, 0, sizeof(subject));
    subject.unit.maxHP = 20;
    subject.unit.curHP = 20;
    subject.battleDefense = 5;
    ExpansionMechanicsApplyBattleStats(&subject, NULL, 0);
    CHECK(subject.battleDefense == 5, "disabled apply must not change any battle stat");

    CHECK(ProbeIsAllZero(), "disabled build must leave the probe all-zero");

    printf("MECHANICS_DISABLED_HOST_TEST: PASS\n");
    return 0;
}
