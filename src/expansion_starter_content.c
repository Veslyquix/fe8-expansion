#include "global.h"

#include "expansion_starter_content.h"

/*
 * Bundled generated-data content example (issue #6, Sprint 2). See
 * include/expansion_starter_content.h for the contract.
 *
 * The whole enabled body compiles out to trivial disabled stubs when
 * FE8_EXPANSION_STARTER_CONTENT is 0, and this translation unit then holds no
 * data at all -- no EWRAM, no BSS, no rodata -- so a default build's memory
 * layout is untouched. Like src/expansion_mechanics.c it is compiled by both
 * the legacy and the modern C source globs but only linked into the modern
 * ROM (ldscript.txt lists legacy objects explicitly and does not list this
 * one). Uses only C89/agbcc-safe constructs.
 */

#if FE8_EXPANSION_STARTER_CONTENT

#include "bmitem.h"
#include "bmbattle.h"
#include "expansion_mechanics.h"
#include "constants/items_expansion.h"

/*
 * The mechanic itself. Reads only:
 *   * the subject's own inventory, through the production accessor
 *     GetUnitItemSlot(), and
 *   * the subject's own already-computed battleAvoidRate.
 * It never touches the context's opponent, so it is correct under both
 * apply orders documented on ExpansionMechanicsBattleStatFunc.
 */
static void ExpansionStarterContentCharmEvade(
    struct BattleUnit* subject,
    const struct ExpansionMechanicsContext* context)
{
    ItemId item;
    int bonused;

    (void)context;

    item = ExpansionStarterContentItemId();

    if (GetUnitItemSlot(&subject->unit, (int)item) < 0)
        return;

    bonused = (int)subject->battleAvoidRate + EXPANSION_STARTER_CONTENT_AVOID_BONUS;

    if (bonused > EXPANSION_STARTER_CONTENT_AVOID_CAP)
        bonused = EXPANSION_STARTER_CONTENT_AVOID_CAP;

    if (bonused > (int)subject->battleAvoidRate)
        subject->battleAvoidRate = (short)bonused;
}

void ExpansionStarterContentInstallMechanics(void)
{
    ExpansionMechanicsRegister(
        EXPANSION_STARTER_CONTENT_KEY,
        EXPANSION_STARTER_CONTENT_LABEL,
        ExpansionStarterContentCharmEvade);
}

ItemId ExpansionStarterContentItemId(void)
{
    return (ItemId)ITEM_EXPANSION_CE;
}

int ExpansionStarterContentIsEnabled(void)
{
    return 1;
}

#else /* !FE8_EXPANSION_STARTER_CONTENT -- disabled stubs, every symbol present */

void ExpansionStarterContentInstallMechanics(void)
{
}

ItemId ExpansionStarterContentItemId(void)
{
    return (ItemId)ITEM_ID_SENTINEL;
}

int ExpansionStarterContentIsEnabled(void)
{
    return 0;
}

#endif /* FE8_EXPANSION_STARTER_CONTENT */
