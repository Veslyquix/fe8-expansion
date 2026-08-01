/*
 * Issue #6 host test driver -- public mechanics hook registry (enabled path).
 *
 * Links against the real, unmodified src/expansion_mechanics.c compiled for
 * the host (see tools/gba-playtest/tests/test_expansion_mechanics.py) and
 * drives ExpansionMechanicsRegister/Count/KeyAt/LabelAt/LastResult/Apply
 * through the exact public API (include/expansion_mechanics.h) contributor
 * code uses -- not a reimplementation. Proves capacity, deterministic append
 * order, duplicate/null/length rejection, capacity-full rejection, the
 * reentrancy guard, and a real battle-stat apply moving a real field.
 *
 * Prints "MECHANICS_HOST_TEST: PASS" and exits 0 on success; on any failure
 * prints the specific failing assertion to stderr and exits 1 (fail fast).
 */
#include <stdio.h>
#include <string.h>

#include "global.h"
#include "bmbattle.h"
#include "expansion_mechanics.h"

#define CHECK(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "MECHANICS_HOST_TEST: FAIL: %s\n", msg); \
            return 1; \
        } \
    } while (0)

static int sNoopCalls;
static void NoopMechanic(struct BattleUnit* subject, const struct ExpansionMechanicsContext* ctx)
{
    (void)subject;
    (void)ctx;
    sNoopCalls++;
}

static void PlusTwoDefenseMechanic(struct BattleUnit* subject, const struct ExpansionMechanicsContext* ctx)
{
    (void)ctx;
    subject->battleDefense += 2;
}

/* A mechanic that tries to register *during* apply -- must be rejected. */
static enum ExpansionMechanicsResult sReentrantResult;
static int sReentrantSeen;
static void ReentrantMechanic(struct BattleUnit* subject, const struct ExpansionMechanicsContext* ctx)
{
    (void)subject;
    (void)ctx;
    sReentrantSeen = ExpansionMechanicsIsApplying(); /* must be 1 while applying */
    sReentrantResult = ExpansionMechanicsRegister("reentrant.key", "reentrant", NoopMechanic);
}

int main(void)
{
    struct BattleUnit subject;
    char key[EXPANSION_MECHANICS_KEY_SIZE + 4];
    char label[EXPANSION_MECHANICS_LABEL_SIZE + 4];
    int i;
    enum ExpansionMechanicsResult r;

    printf("EXPANSION_MECHANICS_MAX=%d\n", (int)EXPANSION_MECHANICS_MAX);
    CHECK(EXPANSION_MECHANICS_MAX == 8, "EXPANSION_MECHANICS_MAX must be 8");

    ExpansionMechanicsReset();
    CHECK(ExpansionMechanicsCount() == 0, "registry must start empty after reset");
    CHECK(ExpansionMechanicsKeyAt(0) == NULL, "KeyAt(0) must be NULL when empty");
    CHECK(ExpansionMechanicsLabelAt(0) == NULL, "LabelAt(0) must be NULL when empty");
    CHECK(ExpansionMechanicsIsApplying() == 0, "must not be applying at rest");

    /* --- Register one, verify OK + introspection + append order. --- */
    r = ExpansionMechanicsRegister("mech.alpha", "Alpha", NoopMechanic);
    CHECK(r == EXPANSION_MECHANICS_OK, "first register must be OK");
    CHECK(ExpansionMechanicsCount() == 1, "count must be 1 after first register");
    CHECK(strcmp(ExpansionMechanicsKeyAt(0), "mech.alpha") == 0, "KeyAt(0) mismatch");
    CHECK(strcmp(ExpansionMechanicsLabelAt(0), "Alpha") == 0, "LabelAt(0) mismatch");
    CHECK(ExpansionMechanicsLastResult() == EXPANSION_MECHANICS_OK, "LastResult must be OK");

    /* --- Duplicate key rejected, registry unchanged. --- */
    r = ExpansionMechanicsRegister("mech.alpha", "Alpha2", NoopMechanic);
    CHECK(r == EXPANSION_MECHANICS_ERR_DUPLICATE, "duplicate key must be rejected");
    CHECK(ExpansionMechanicsCount() == 1, "duplicate must not grow the registry");

    /* --- NULL argument rejected. --- */
    CHECK(ExpansionMechanicsRegister(NULL, "x", NoopMechanic) == EXPANSION_MECHANICS_ERR_NULL_ARG,
          "NULL key must be rejected");
    CHECK(ExpansionMechanicsRegister("k", NULL, NoopMechanic) == EXPANSION_MECHANICS_ERR_NULL_ARG,
          "NULL label must be rejected");
    CHECK(ExpansionMechanicsRegister("k", "l", NULL) == EXPANSION_MECHANICS_ERR_NULL_ARG,
          "NULL callback must be rejected");

    /* --- Empty and too-long key/label rejected. --- */
    CHECK(ExpansionMechanicsRegister("", "l", NoopMechanic) == EXPANSION_MECHANICS_ERR_KEY_LENGTH,
          "empty key must be rejected");
    for (i = 0; i < EXPANSION_MECHANICS_KEY_SIZE + 2; i++)
        key[i] = 'k';
    key[EXPANSION_MECHANICS_KEY_SIZE + 2] = '\0';
    CHECK(ExpansionMechanicsRegister(key, "l", NoopMechanic) == EXPANSION_MECHANICS_ERR_KEY_LENGTH,
          "over-long key must be rejected");
    CHECK(ExpansionMechanicsRegister("k2", "", NoopMechanic) == EXPANSION_MECHANICS_ERR_LABEL_LENGTH,
          "empty label must be rejected");
    for (i = 0; i < EXPANSION_MECHANICS_LABEL_SIZE + 2; i++)
        label[i] = 'l';
    label[EXPANSION_MECHANICS_LABEL_SIZE + 2] = '\0';
    CHECK(ExpansionMechanicsRegister("k3", label, NoopMechanic) == EXPANSION_MECHANICS_ERR_LABEL_LENGTH,
          "over-long label must be rejected");
    CHECK(ExpansionMechanicsCount() == 1, "rejected registrations must not grow the registry");

    /* --- Fill to capacity, then reject one more. --- */
    for (i = 1; i < EXPANSION_MECHANICS_MAX; i++)
    {
        char k[EXPANSION_MECHANICS_KEY_SIZE];
        k[0] = 'm'; k[1] = 'e'; k[2] = 'c'; k[3] = 'h';
        k[4] = '.'; k[5] = (char)('0' + i); k[6] = '\0';
        r = ExpansionMechanicsRegister(k, "cap", NoopMechanic);
        CHECK(r == EXPANSION_MECHANICS_OK, "registering up to capacity must be OK");
    }
    CHECK(ExpansionMechanicsCount() == EXPANSION_MECHANICS_MAX, "registry must be full");
    r = ExpansionMechanicsRegister("mech.over", "over", NoopMechanic);
    CHECK(r == EXPANSION_MECHANICS_ERR_CAPACITY, "registering past capacity must be rejected");
    CHECK(ExpansionMechanicsCount() == EXPANSION_MECHANICS_MAX, "capacity error must not grow the registry");

    /* --- Deterministic append order preserved: index 0 is still alpha. --- */
    CHECK(strcmp(ExpansionMechanicsKeyAt(0), "mech.alpha") == 0, "append order broken at 0");
    CHECK(ExpansionMechanicsKeyAt(EXPANSION_MECHANICS_MAX) == NULL, "KeyAt(MAX) must be NULL");

    /* --- Apply: a real mechanic moves a real battleDefense field; the probe
     * records semantic counters (never a pointer). --- */
    ExpansionMechanicsReset();
    memset(&gExpansionMechanicsProbe, 0, sizeof(gExpansionMechanicsProbe));
    sNoopCalls = 0;
    CHECK(ExpansionMechanicsRegister("def.plus2", "Def+2", PlusTwoDefenseMechanic) == EXPANSION_MECHANICS_OK,
          "register PlusTwoDefense");
    CHECK(ExpansionMechanicsRegister("noop", "Noop", NoopMechanic) == EXPANSION_MECHANICS_OK,
          "register Noop");
    memset(&subject, 0, sizeof(subject));
    subject.unit.maxHP = 20;
    subject.unit.curHP = 20;
    subject.battleDefense = 5;
    ExpansionMechanicsApplyBattleStats(&subject, NULL, 0);
    CHECK(subject.battleDefense == 7, "PlusTwoDefense must add exactly 2 to a real field");
    CHECK(sNoopCalls == 1, "every registered mechanic must run exactly once per apply");
    CHECK(gExpansionMechanicsProbe.applyCount == 1, "probe applyCount must be 1");
    CHECK(gExpansionMechanicsProbe.lastAppliedCount == 2, "probe lastAppliedCount must equal registered count");
    CHECK(gExpansionMechanicsProbe.lastDefenseDelta == 2, "probe lastDefenseDelta must be the real net change");

    /* --- Reentrancy: a mechanic that registers during apply is rejected and
     * the registry does not grow. --- */
    ExpansionMechanicsReset();
    sReentrantSeen = 0;
    sReentrantResult = EXPANSION_MECHANICS_OK;
    CHECK(ExpansionMechanicsRegister("reenter", "Reenter", ReentrantMechanic) == EXPANSION_MECHANICS_OK,
          "register ReentrantMechanic");
    ExpansionMechanicsApplyBattleStats(&subject, NULL, 0);
    CHECK(sReentrantSeen == 1, "reentrant mechanic must have run");
    CHECK(sReentrantResult == EXPANSION_MECHANICS_ERR_REENTRANT,
          "registering during apply must return ERR_REENTRANT");
    CHECK(ExpansionMechanicsCount() == 1, "reentrant register must not grow the registry");
    CHECK(ExpansionMechanicsIsApplying() == 0, "apply flag must be cleared after apply");

    printf("MECHANICS_HOST_TEST: PASS\n");
    return 0;
}
