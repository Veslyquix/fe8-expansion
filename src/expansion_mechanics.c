#include "global.h"

#include <string.h>

#include "bmbattle.h"
#include "expansion_mechanics.h"
#include "expansion_starter_content.h"

/*
 * Public battle-stat mechanics hook registry (issue #6). See
 * include/expansion_mechanics.h for the API contract.
 *
 * Layout mirrors src/debugtools_registry.c's proven shape but shares no code
 * with it: the whole enabled body is compiled out to trivial disabled stubs
 * when FE8_EXPANSION_MECHANICS_HOOKS is 0, while gExpansionMechanicsProbe is
 * linked into every build (always zero-initialized EWRAM -- see src/main.c's
 * unconditional EWRAM clear before any gameplay code) so a disabled/default
 * build's negative-control scenarios can assert it stays all-zero.
 *
 * Compiled by both the legacy and modern C source globs; only linked into the
 * modern ROM (linker/expansion.ld pulls every object's sections; ldscript.txt
 * lists legacy objects explicitly and does not list this one). Uses only
 * C89/agbcc-safe constructs and positional initialization.
 */

EWRAM_DATA struct ExpansionMechanicsProbe gExpansionMechanicsProbe = {0};

#if FE8_EXPANSION_MECHANICS_HOOKS

struct ExpansionMechanicsEntry
{
    char key[EXPANSION_MECHANICS_KEY_SIZE];
    char label[EXPANSION_MECHANICS_LABEL_SIZE];
    ExpansionMechanicsBattleStatFunc callback;
};

EWRAM_DATA static struct ExpansionMechanicsEntry sEntries[EXPANSION_MECHANICS_MAX] = {0};
EWRAM_DATA static int sCount = 0;
EWRAM_DATA static enum ExpansionMechanicsResult sLastResult = EXPANSION_MECHANICS_OK;
EWRAM_DATA static u8 sInApply = 0;
EWRAM_DATA static u8 sBuiltinsInstalled = 0;

/* Length of s up to (but not counting) its NUL, capped at cap. A return of
 * cap therefore means "no NUL within the first cap bytes" -- i.e. too long to
 * store NUL-terminated in a cap-byte buffer. */
static int ExpansionMechanicsBoundedLen(const char* s, int cap)
{
    int n = 0;

    while (n < cap && s[n] != '\0')
        n++;

    return n;
}

static enum ExpansionMechanicsResult ExpansionMechanicsFail(enum ExpansionMechanicsResult result)
{
    sLastResult = result;
    gExpansionMechanicsProbe.registerErrCount++;
    gExpansionMechanicsProbe.lastResult = (u32)result;
    return result;
}

enum ExpansionMechanicsResult ExpansionMechanicsRegister(
    const char* key,
    const char* label,
    ExpansionMechanicsBattleStatFunc callback)
{
    int keyLen;
    int labelLen;
    int i;

    /* Registration is forbidden while a battle-stat apply is iterating the
     * table: a mechanic must not grow the table it is being walked from. */
    if (sInApply)
        return ExpansionMechanicsFail(EXPANSION_MECHANICS_ERR_REENTRANT);

    if (key == NULL || label == NULL || callback == NULL)
        return ExpansionMechanicsFail(EXPANSION_MECHANICS_ERR_NULL_ARG);

    keyLen = ExpansionMechanicsBoundedLen(key, EXPANSION_MECHANICS_KEY_SIZE);
    if (keyLen == 0 || keyLen >= EXPANSION_MECHANICS_KEY_SIZE)
        return ExpansionMechanicsFail(EXPANSION_MECHANICS_ERR_KEY_LENGTH);

    labelLen = ExpansionMechanicsBoundedLen(label, EXPANSION_MECHANICS_LABEL_SIZE);
    if (labelLen == 0 || labelLen >= EXPANSION_MECHANICS_LABEL_SIZE)
        return ExpansionMechanicsFail(EXPANSION_MECHANICS_ERR_LABEL_LENGTH);

    for (i = 0; i < sCount; i++)
    {
        if (strcmp(sEntries[i].key, key) == 0)
            return ExpansionMechanicsFail(EXPANSION_MECHANICS_ERR_DUPLICATE);
    }

    if (sCount >= EXPANSION_MECHANICS_MAX)
        return ExpansionMechanicsFail(EXPANSION_MECHANICS_ERR_CAPACITY);

    /* Copy-in (lengths already bounded above), NUL-terminating explicitly. */
    memcpy(sEntries[sCount].key, key, (unsigned int)keyLen);
    sEntries[sCount].key[keyLen] = '\0';
    memcpy(sEntries[sCount].label, label, (unsigned int)labelLen);
    sEntries[sCount].label[labelLen] = '\0';
    sEntries[sCount].callback = callback;
    sCount++;

    sLastResult = EXPANSION_MECHANICS_OK;
    gExpansionMechanicsProbe.registerOkCount++;
    gExpansionMechanicsProbe.lastResult = (u32)EXPANSION_MECHANICS_OK;
    return EXPANSION_MECHANICS_OK;
}

int ExpansionMechanicsCount(void)
{
    return sCount;
}

const char* ExpansionMechanicsKeyAt(int index)
{
    if (index < 0 || index >= sCount)
        return NULL;

    return sEntries[index].key;
}

const char* ExpansionMechanicsLabelAt(int index)
{
    if (index < 0 || index >= sCount)
        return NULL;

    return sEntries[index].label;
}

enum ExpansionMechanicsResult ExpansionMechanicsLastResult(void)
{
    return sLastResult;
}

int ExpansionMechanicsIsApplying(void)
{
    return sInApply ? 1 : 0;
}

void ExpansionMechanicsReset(void)
{
    sCount = 0;
    sInApply = 0;
    sBuiltinsInstalled = 0;
    sLastResult = EXPANSION_MECHANICS_OK;
}

#if FE8_EXPANSION_MECHANICS_SAMPLE
/*
 * Sample mechanic: "Full-HP Guard". Generic and content-free -- it reads only
 * the subject's own HP (never an item or character numeric ID). When the
 * subject is at full HP it grants exactly one point of already-computed
 * battleDefense, clamped at _GUARD_CAP so the bonus is strictly bounded. It
 * applies in every context ComputeBattleUnitStats() runs in (the context's
 * battleConfig is available but intentionally not branched on), so a UI
 * forecast matches the real bout.
 */
static void ExpansionMechanicsSampleFullHpGuard(
    struct BattleUnit* subject,
    const struct ExpansionMechanicsContext* context)
{
    int maxHp;
    int curHp;

    (void)context;

    maxHp = subject->unit.maxHP;
    curHp = subject->unit.curHP;

    if (maxHp > 0 && curHp >= maxHp)
    {
        if (subject->battleDefense < EXPANSION_MECHANICS_SAMPLE_GUARD_CAP)
        {
            subject->battleDefense += EXPANSION_MECHANICS_SAMPLE_GUARD_BONUS;
            gExpansionMechanicsProbe.sampleTriggerCount++;
        }
    }
}
#endif /* FE8_EXPANSION_MECHANICS_SAMPLE */

void ExpansionMechanicsInstallBuiltins(void)
{
    if (sBuiltinsInstalled)
        return;

    sBuiltinsInstalled = 1;

#if FE8_EXPANSION_MECHANICS_SAMPLE
    ExpansionMechanicsRegister(
        EXPANSION_MECHANICS_SAMPLE_KEY,
        EXPANSION_MECHANICS_SAMPLE_LABEL,
        ExpansionMechanicsSampleFullHpGuard);
#endif

    /* The bundled issue #6 content example registers itself here, through
     * the same public ExpansionMechanicsRegister() API, so the framework has
     * exactly ONE built-in install point and no second router. A no-op when
     * FE8_EXPANSION_STARTER_CONTENT is 0. */
    ExpansionStarterContentInstallMechanics();
}

void ExpansionMechanicsApplyBattleStats(
    struct BattleUnit* subject,
    const struct BattleUnit* opponent,
    u16 battleConfig)
{
    int i;
    short before;
    struct ExpansionMechanicsContext context;

    if (subject == NULL)
        return;

    ExpansionMechanicsInstallBuiltins();

    context.opponent = opponent;
    context.battleConfig = battleConfig;

    before = subject->battleDefense;

    sInApply = 1;
    for (i = 0; i < sCount; i++)
        sEntries[i].callback(subject, &context);
    sInApply = 0;

    gExpansionMechanicsProbe.applyCount++;
    gExpansionMechanicsProbe.lastAppliedCount = (u32)sCount;
    gExpansionMechanicsProbe.lastDefenseDelta =
        (s32)((int)subject->battleDefense - (int)before);
}

#else /* !FE8_EXPANSION_MECHANICS_HOOKS -- disabled stubs, every symbol present */

enum ExpansionMechanicsResult ExpansionMechanicsRegister(
    const char* key,
    const char* label,
    ExpansionMechanicsBattleStatFunc callback)
{
    (void)key;
    (void)label;
    (void)callback;
    return EXPANSION_MECHANICS_ERR_DISABLED;
}

int ExpansionMechanicsCount(void)
{
    return 0;
}

const char* ExpansionMechanicsKeyAt(int index)
{
    (void)index;
    return NULL;
}

const char* ExpansionMechanicsLabelAt(int index)
{
    (void)index;
    return NULL;
}

enum ExpansionMechanicsResult ExpansionMechanicsLastResult(void)
{
    return EXPANSION_MECHANICS_ERR_DISABLED;
}

int ExpansionMechanicsIsApplying(void)
{
    return 0;
}

void ExpansionMechanicsReset(void)
{
}

void ExpansionMechanicsInstallBuiltins(void)
{
}

void ExpansionMechanicsApplyBattleStats(
    struct BattleUnit* subject,
    const struct BattleUnit* opponent,
    u16 battleConfig)
{
    (void)subject;
    (void)opponent;
    (void)battleConfig;
}

#endif /* FE8_EXPANSION_MECHANICS_HOOKS */
