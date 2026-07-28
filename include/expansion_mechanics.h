#ifndef GUARD_EXPANSION_MECHANICS_H
#define GUARD_EXPANSION_MECHANICS_H

/*
 * Public battle-stat mechanics hook registry (issue #6).
 *
 * A small, fixed-capacity registry that lets a contributor extend the
 * vanilla battle-stat computation through one narrow, typed seam instead of
 * hand-editing src/bmbattle.c. ComputeBattleUnitStats() (src/bmbattle.c)
 * calls ExpansionMechanicsApplyBattleStats() exactly once per subject, after
 * every vanilla base stat is computed and before the effective-stat pass, so
 * a registered mechanic sees a fully-computed subject and may nudge its
 * already-computed battle stats.
 *
 * This is deliberately NOT the debug-tools registry (include/
 * expansion_debugtools.h): that one routes menu actions for a debug hub;
 * this one routes typed battle-stat callbacks and shares no storage, no
 * global router, and no menu wiring with it.
 *
 * Compile-time gating (see include/expansion_config.h / config.mk):
 *   FE8_EXPANSION_MECHANICS_HOOKS  -- 0 compiles the whole registry body out
 *                                     to disabled stubs and the seam call
 *                                     vanishes entirely (byte-identical
 *                                     vanilla battle math); 1 links it.
 *   FE8_EXPANSION_MECHANICS_SAMPLE -- 1 (requires HOOKS=1) registers the
 *                                     bundled sample mechanic through the
 *                                     public ExpansionMechanicsRegister()
 *                                     API, never by special-casing a stat.
 *
 * This header is C89/agbcc-safe and, like the rest of the expansion
 * headers, expects global.h (its u8/u16/u32/s32 typedefs) to have been
 * included first.
 */

#include "expansion_config.h"

struct BattleUnit;

/* Fixed capacity and copy-in string bounds (each *_SIZE counts the NUL). */
#define EXPANSION_MECHANICS_MAX 8
#define EXPANSION_MECHANICS_KEY_SIZE 24
#define EXPANSION_MECHANICS_LABEL_SIZE 32

/* Distinct, explicit result codes -- ExpansionMechanicsRegister() always
 * returns exactly one of these and, on any non-OK code, leaves the registry
 * unchanged. */
enum ExpansionMechanicsResult
{
    EXPANSION_MECHANICS_OK = 0,
    EXPANSION_MECHANICS_ERR_DISABLED,     /* feature compiled out (HOOKS=0) */
    EXPANSION_MECHANICS_ERR_NULL_ARG,     /* NULL key, label, or callback */
    EXPANSION_MECHANICS_ERR_KEY_LENGTH,   /* key empty or too long for its buffer */
    EXPANSION_MECHANICS_ERR_LABEL_LENGTH, /* label empty or too long for its buffer */
    EXPANSION_MECHANICS_ERR_DUPLICATE,    /* key already registered */
    EXPANSION_MECHANICS_ERR_CAPACITY,     /* registry already holds _MAX entries */
    EXPANSION_MECHANICS_ERR_REENTRANT     /* register attempted during an apply */
};

/* Read-only context handed to every mechanic on each apply. Carries only
 * typed handles/flags -- never a void* and never a raw item/character ID.
 *
 * IMPORTANT -- `opponent` is NOT guaranteed to have finalized battle stats.
 * See "Apply order" on the callback typedef below before reading anything
 * from it beyond its underlying `unit` fields. */
struct ExpansionMechanicsContext
{
    const struct BattleUnit* opponent; /* read-only opposing combatant; may be NULL */
    u16 battleConfig;                  /* BATTLE_CONFIG_* flags for this computation */
};

/*
 * Typed battle-stat mechanic callback. It may adjust the mutable subject's
 * already-computed battle stats and must treat the context (and the opponent
 * inside it) as read-only.
 *
 * Apply order (src/bmbattle.c). The seam runs at the END of
 * ComputeBattleUnitStats(), once per subject, after every vanilla base stat
 * for THAT SUBJECT is computed and before ComputeBattleUnitEffectiveStats().
 * BattleGenerate() computes the two combatants in sequence:
 *
 *     ComputeBattleUnitStats(&gBattleActor,  &gBattleTarget);  // apply #1
 *     ComputeBattleUnitStats(&gBattleTarget, &gBattleActor);   // apply #2
 *     ComputeBattleUnitEffectiveStats(...);                    // both, after
 *
 * So on apply #1 the subject is the ATTACKER and `context->opponent` (the
 * defender) has NOT had its battle stats computed yet: its battleAttack,
 * battleDefense, battleHitRate, battleAvoidRate, battleCritRate,
 * battleDodgeRate and friends still hold values from a previous computation
 * or from initialization -- reading them is a real bug, not a rounding
 * detail. Only on apply #2 is the opponent (the attacker) fully computed.
 * Within either apply, effective-stat adjustments (weapon triangle, effective
 * damage) have not run for EITHER combatant.
 *
 * Therefore a mechanic must be written so it is correct under both orders.
 * Safe inputs: the subject's own already-computed battle stats, and the
 * opponent's stable underlying `opponent->unit` data (class, level, status,
 * position, current/max HP). Unsafe input: any `opponent->battle*` field.
 * If a mechanic genuinely needs both combatants' finalized battle stats, it
 * belongs at a later seam than this one; do not work around the ordering by
 * caching state between applies -- registration and apply order are
 * deterministic, but the pairing is not re-entrant and
 * ExpansionMechanicsRegister() during an apply is rejected outright
 * (EXPANSION_MECHANICS_ERR_REENTRANT).
 *
 * The bundled sample mechanic deliberately reads only the subject's own HP,
 * so it is immune to this ordering.
 */
typedef void (*ExpansionMechanicsBattleStatFunc)(
    struct BattleUnit* subject,
    const struct ExpansionMechanicsContext* context);

/*
 * Register a mechanic. key/label are copied into fixed internal buffers, so
 * the caller's strings need not outlive the call (lifetime-safe); both must
 * be non-empty and NUL-terminate within their *_SIZE bound. A NULL argument,
 * a duplicate key, a full registry, or a call made *during* an apply is each
 * rejected with its own result code and changes nothing. Returns the result
 * (also queryable via ExpansionMechanicsLastResult()).
 */
enum ExpansionMechanicsResult ExpansionMechanicsRegister(
    const char* key,
    const char* label,
    ExpansionMechanicsBattleStatFunc callback);

/* Introspection over the registry's deterministic registration order. */
int ExpansionMechanicsCount(void);
const char* ExpansionMechanicsKeyAt(int index);   /* NULL when out of range */
const char* ExpansionMechanicsLabelAt(int index); /* NULL when out of range */
enum ExpansionMechanicsResult ExpansionMechanicsLastResult(void);
int ExpansionMechanicsIsApplying(void); /* 1 while inside an apply, else 0 */

/* Clear every registration and re-arm built-in installation. Present in
 * every build (a no-op beyond bookkeeping when HOOKS=0). */
void ExpansionMechanicsReset(void);

/* Register the framework's built-in mechanics through the public
 * ExpansionMechanicsRegister() API. Only the sample, and only when
 * FE8_EXPANSION_MECHANICS_SAMPLE=1. Idempotent (safe to call repeatedly). */
void ExpansionMechanicsInstallBuiltins(void);

/*
 * The battle-stat seam. Called once per subject from ComputeBattleUnitStats()
 * (src/bmbattle.c) after vanilla base stats and before effective stats;
 * installs built-ins on first use, then applies every registered mechanic in
 * registration order. battleConfig is the live BATTLE_CONFIG_* bitmask so a
 * mechanic can distinguish real combat from a UI simulation or an arena bout.
 * Safe with a NULL subject. A no-op when HOOKS=0.
 */
void ExpansionMechanicsApplyBattleStats(
    struct BattleUnit* subject,
    const struct BattleUnit* opponent,
    u16 battleConfig);

/*
 * Bundled sample mechanic: "Full-HP Guard" (issue #6). When the subject is
 * at full HP it grants exactly one point of battleDefense, clamped so the
 * stat never exceeds _GUARD_CAP. It reads no item/character numeric IDs and
 * applies in every context ComputeBattleUnitStats() runs in (real combat,
 * UI-forecast simulation, and arena), so the forecast a player sees always
 * matches the real bout. It is registered only through the public API.
 */
#define EXPANSION_MECHANICS_SAMPLE_KEY "sample.fullhp_guard"
#define EXPANSION_MECHANICS_SAMPLE_LABEL "Full-HP Guard +1Def"
#define EXPANSION_MECHANICS_SAMPLE_GUARD_BONUS 1
#define EXPANSION_MECHANICS_SAMPLE_GUARD_CAP 99

/*
 * Always-linked semantic probe (issue #6 / #13 runtime harness). Zero-
 * initialized EWRAM in every build; only ever written on the enabled apply
 * path, so a default/disabled build leaves it all-zero for negative-control
 * scenarios. It records semantic counters only -- never a pointer value.
 */
struct ExpansionMechanicsProbe
{
    /* 00 */ u32 registerOkCount;    /* successful registrations */
    /* 04 */ u32 registerErrCount;   /* rejected registrations */
    /* 08 */ u32 applyCount;         /* ExpansionMechanicsApplyBattleStats calls */
    /* 0C */ u32 lastAppliedCount;   /* mechanics iterated on the most recent apply */
    /* 10 */ s32 lastDefenseDelta;   /* net battleDefense change on the most recent apply */
    /* 14 */ u32 sampleTriggerCount; /* times the sample actually granted its bonus */
    /* 18 */ u32 lastResult;         /* most recent enum ExpansionMechanicsResult */
};

extern struct ExpansionMechanicsProbe gExpansionMechanicsProbe;

#endif /* GUARD_EXPANSION_MECHANICS_H */
