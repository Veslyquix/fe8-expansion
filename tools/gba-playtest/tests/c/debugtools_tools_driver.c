/*
 * Issue #11 closure -- host-executed behavior test driver for the five
 * bounded validated tools (src/debugtools_tools.c): unit inspect/heal,
 * convoy inspect/add, flag/chapter inspect/toggle, RNG inspect/reseed,
 * and save-state inspect (read-only).
 *
 * Links directly against the real, unmodified src/debugtools_tools.c and
 * src/debugtools_registry.c (compiled for the host, see
 * test_debugtools_registry.py) plus debugtools_tools_host_stubs.c's small
 * set of engine/hardware/menu stand-ins, and drives
 * DebugTools_RegisterExtendedToolActions/DebugTools_GetRegisteredAction/
 * each action's own onSelected and confirm-submenu MenuItemDef::onSelected
 * through the exact same MenuProc/MenuItemProc callback shape the real
 * menu engine uses -- not a reimplementation of any tool's logic.
 *
 * Prints "DEBUGTOOLS_TOOLS_HOST_TEST: PASS" and exits 0 on success; on
 * any failure it prints the specific failing assertion to stderr and
 * exits 1 without running further checks (fail fast, actionable
 * diagnostic).
 */
#include <stdio.h>
#include <string.h>

#include "global.h"
#include "uimenu.h"
#include "expansion_debugtools.h"
#include "save_format.h"

#define CHECK(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "DEBUGTOOLS_TOOLS_HOST_TEST: FAIL: %s\n", msg); \
            return 1; \
        } \
    } while (0)

#define CLOSE_HUB_FLAGS (MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR)

extern int gDebugToolsToolsHostStub_StartOrphanMenuCallCount;
extern const struct MenuDef* gDebugToolsToolsHostStub_LastMenuDef;
extern void DebugToolsHostStub_SetFakeUnit(int present, int curHp, int maxHp);
extern void DebugToolsHostStub_SetFakeConvoy(int count, int full);
extern void DebugToolsHostStub_ClearFakeFlags(void);
extern void DebugToolsHostStub_SetFakeSaveCompatState(enum SaveCompatState state);

extern struct MenuDef CONST_DATA gDebugToolsUnitMenuDef;
extern struct MenuDef CONST_DATA gDebugToolsConvoyMenuDef;
extern struct MenuDef CONST_DATA gDebugToolsFlagMenuDef;
extern struct MenuDef CONST_DATA gDebugToolsRngMenuDef;
extern struct MenuDef CONST_DATA gDebugToolsSaveStateMenuDef;

int main(void)
{
    const struct DebugToolsAction* action;
    u8 rc;

    /* --- Registration: five actions, ids 5-9, deterministic order. ---- */
    DebugTools_RegisterExtendedToolActions();
    CHECK(DebugTools_GetRegisteredCount() == 5, "expected exactly 5 extended tool actions registered");

    action = DebugTools_GetRegisteredAction(0);
    CHECK(action != NULL && action->id == 5 && strcmp(action->label, "Unit Inspect") == 0, "action 0 must be Unit Inspect (id 5)");
    action = DebugTools_GetRegisteredAction(1);
    CHECK(action != NULL && action->id == 6 && strcmp(action->label, "Convoy Inspect") == 0, "action 1 must be Convoy Inspect (id 6)");
    action = DebugTools_GetRegisteredAction(2);
    CHECK(action != NULL && action->id == 7 && strcmp(action->label, "Flag/Chapter") == 0, "action 2 must be Flag/Chapter (id 7)");
    action = DebugTools_GetRegisteredAction(3);
    CHECK(action != NULL && action->id == 8 && strcmp(action->label, "RNG Inspect") == 0, "action 3 must be RNG Inspect (id 8)");
    action = DebugTools_GetRegisteredAction(4);
    CHECK(action != NULL && action->id == 9 && strcmp(action->label, "Save State") == 0, "action 4 must be Save State (id 9)");

    /* Idempotent: a repeat call must not grow the registry. */
    DebugTools_RegisterExtendedToolActions();
    CHECK(DebugTools_GetRegisteredCount() == 5, "a repeat DebugTools_RegisterExtendedToolActions call must not grow the registry");

    /* ================= 1. Unit inspect/heal ========================= */

    /* --- Valid target: inspect samples HP, confirm heals + clears status. */
    DebugToolsHostStub_SetFakeUnit(1, 5, 20);
    action = DebugTools_GetRegisteredAction(0);
    rc = action->onSelected(NULL, NULL);
    CHECK(rc == CLOSE_HUB_FLAGS, "Unit Inspect onSelected must close the hub");
    CHECK(gDebugToolsToolsHostStub_LastMenuDef == &gDebugToolsUnitMenuDef, "Unit Inspect must open gDebugToolsUnitMenuDef");
    CHECK(gDebugToolsProbe.unitInspectTargetFound == 1, "valid target must set unitInspectTargetFound");
    CHECK(gDebugToolsProbe.unitInspectLastCurHp == 5, "inspect must sample curHP");
    CHECK(gDebugToolsProbe.unitInspectLastMaxHp == 20, "inspect must sample maxHP");
    CHECK(gDebugToolsProbe.unitHealTransactionCount == 0, "inspect alone must never apply a heal transaction");

    CHECK(strcmp(gDebugToolsUnitMenuDef.menuItems[0].name, "Confirm Heal to Full") == 0, "unit submenu item 0 must be the Confirm item");
    CHECK(strcmp(gDebugToolsUnitMenuDef.menuItems[1].name, "Back") == 0, "unit submenu item 1 must be Back");
    CHECK(gDebugToolsUnitMenuDef.menuItems[1].onSelected == MenuCancelSelect, "unit submenu Back must use MenuCancelSelect");

    rc = gDebugToolsUnitMenuDef.menuItems[0].onSelected(NULL, NULL);
    CHECK(rc == CLOSE_HUB_FLAGS, "Unit confirm must close its submenu");
    CHECK(gDebugToolsProbe.unitHealTransactionCount == 1, "confirming heal on a valid target must apply exactly one transaction");
    CHECK(DebugTools_GetAssertFailureCount() == 0, "healing a valid target must never record an assert failure");

    /* --- Invalid target: inspect reports not-found, confirm is a safe,
     * logged, assert-recorded no-op -- never a crash, never a silent
     * mutation of an invalid pointer. */
    DebugToolsHostStub_SetFakeUnit(0, 0, 0);
    rc = DebugTools_GetRegisteredAction(0)->onSelected(NULL, NULL);
    (void)rc;
    CHECK(gDebugToolsProbe.unitInspectTargetFound == 0, "missing target must clear unitInspectTargetFound");
    CHECK(gDebugToolsProbe.unitInspectLastCurHp == 0, "missing target must sample curHP as 0");

    {
        u32 healCountBefore = gDebugToolsProbe.unitHealTransactionCount;
        u32 assertCountBefore = DebugTools_GetAssertFailureCount();

        rc = gDebugToolsUnitMenuDef.menuItems[0].onSelected(NULL, NULL);
        CHECK(rc == CLOSE_HUB_FLAGS, "Unit confirm must still close its submenu even for an invalid target");
        CHECK(gDebugToolsProbe.unitHealTransactionCount == healCountBefore, "confirming heal on an invalid target must never apply a transaction");
        CHECK(DebugTools_GetAssertFailureCount() == assertCountBefore + 1, "confirming heal on an invalid target must record exactly one assert failure");
        CHECK(DebugTools_GetLastAssertCode() == DEBUGTOOLS_ASSERT_UNIT_TARGET_INVALID, "the recorded assert code must be DEBUGTOOLS_ASSERT_UNIT_TARGET_INVALID");
    }

    /* ================= 2. Convoy inspect/add ========================= */

    DebugToolsHostStub_SetFakeConvoy(3, 0);
    rc = DebugTools_GetRegisteredAction(1)->onSelected(NULL, NULL);
    CHECK(rc == CLOSE_HUB_FLAGS, "Convoy Inspect onSelected must close the hub");
    CHECK(gDebugToolsToolsHostStub_LastMenuDef == &gDebugToolsConvoyMenuDef, "Convoy Inspect must open gDebugToolsConvoyMenuDef");
    CHECK(gDebugToolsProbe.convoyLastItemCount == 3, "inspect must sample the convoy item count");
    CHECK(gDebugToolsProbe.convoyAddTransactionCount == 0, "inspect alone must never apply an add transaction");

    rc = gDebugToolsConvoyMenuDef.menuItems[0].onSelected(NULL, NULL);
    CHECK(rc == CLOSE_HUB_FLAGS, "Convoy confirm must close its submenu");
    CHECK(gDebugToolsProbe.convoyAddTransactionCount == 1, "confirming add with room available must apply exactly one transaction");

    /* --- Full convoy: confirm must be a safe, logged no-op. ----------- */
    DebugToolsHostStub_SetFakeConvoy(100, 1);
    DebugTools_GetRegisteredAction(1)->onSelected(NULL, NULL);
    {
        u32 addCountBefore = gDebugToolsProbe.convoyAddTransactionCount;

        rc = gDebugToolsConvoyMenuDef.menuItems[0].onSelected(NULL, NULL);
        CHECK(rc == CLOSE_HUB_FLAGS, "Convoy confirm must still close its submenu when full");
        CHECK(gDebugToolsProbe.convoyAddTransactionCount == addCountBefore, "confirming add on a full convoy must never apply a transaction");
    }

    /* ================= 3. Flag/chapter/event state =================== */

    DebugToolsHostStub_ClearFakeFlags();
    gPlaySt.chapterIndex = 2;

    rc = DebugTools_GetRegisteredAction(2)->onSelected(NULL, NULL);
    CHECK(rc == CLOSE_HUB_FLAGS, "Flag/Chapter Inspect onSelected must close the hub");
    CHECK(gDebugToolsToolsHostStub_LastMenuDef == &gDebugToolsFlagMenuDef, "Flag/Chapter Inspect must open gDebugToolsFlagMenuDef");
    CHECK(gDebugToolsProbe.chapterIndexSample == 2, "inspect must sample gPlaySt.chapterIndex");
    CHECK(gDebugToolsProbe.debugFlagLastValue == 0, "a freshly cleared debug flag must sample as 0");
    CHECK(gDebugToolsProbe.debugFlagToggleCount == 0, "inspect alone must never apply a toggle transaction");

    {
        u32 assertCountBeforeToggle = DebugTools_GetAssertFailureCount();

        rc = gDebugToolsFlagMenuDef.menuItems[0].onSelected(NULL, NULL);
        CHECK(rc == CLOSE_HUB_FLAGS, "Flag confirm must close its submenu");
        CHECK(gDebugToolsProbe.debugFlagToggleCount == 1, "confirming toggle must apply exactly one transaction");
        CHECK(gDebugToolsProbe.debugFlagLastValue == 1, "toggling a cleared flag must set it");
        CHECK(DebugTools_GetAssertFailureCount() == assertCountBeforeToggle,
              "toggling the fixed in-range debug flag must never record a new assert failure");
    }

    rc = gDebugToolsFlagMenuDef.menuItems[0].onSelected(NULL, NULL);
    CHECK(gDebugToolsProbe.debugFlagToggleCount == 2, "a second confirm must apply a second transaction");
    CHECK(gDebugToolsProbe.debugFlagLastValue == 0, "toggling a set flag must clear it back");

    /* ================= 4. RNG inspect/control ========================= */

    rc = DebugTools_GetRegisteredAction(3)->onSelected(NULL, NULL);
    CHECK(rc == CLOSE_HUB_FLAGS, "RNG Inspect onSelected must close the hub");
    CHECK(gDebugToolsToolsHostStub_LastMenuDef == &gDebugToolsRngMenuDef, "RNG Inspect must open gDebugToolsRngMenuDef");
    CHECK(gDebugToolsProbe.rngInspectSeedSample0 == 0x1111, "inspect must sample the current seed state (fake initial seed)");
    CHECK(gDebugToolsProbe.rngReseedTransactionCount == 0, "inspect alone must never apply a reseed transaction");

    rc = gDebugToolsRngMenuDef.menuItems[0].onSelected(NULL, NULL);
    CHECK(rc == CLOSE_HUB_FLAGS, "RNG confirm must close its submenu");
    CHECK(gDebugToolsProbe.rngReseedTransactionCount == 1, "confirming reseed must apply exactly one transaction");

    DebugTools_GetRegisteredAction(3)->onSelected(NULL, NULL);
    CHECK(gDebugToolsProbe.rngInspectSeedSample0 != 0x1111, "a re-inspect after reseeding must observe a changed seed state");

    /* ================= 5. Save compatibility/state (read-only) ======== */

    DebugToolsHostStub_SetFakeSaveCompatState(SAVE_COMPAT_CURRENT);
    rc = DebugTools_GetRegisteredAction(4)->onSelected(NULL, NULL);
    CHECK(rc == CLOSE_HUB_FLAGS, "Save State Inspect onSelected must close the hub");
    CHECK(gDebugToolsToolsHostStub_LastMenuDef == &gDebugToolsSaveStateMenuDef, "Save State Inspect must open gDebugToolsSaveStateMenuDef");
    CHECK(gDebugToolsProbe.saveCompatLastState == (u32)SAVE_COMPAT_CURRENT, "inspect must sample the current save-compat state");
    CHECK(gDebugToolsProbe.saveCompatInspectCount == 1, "inspect must increment the inspect counter exactly once");

    /* Read-only: no Confirm item at all -- the submenu's only live item
     * must be Back, using the same MenuCancelSelect idiom as every other
     * tool's Back entry. */
    CHECK(strcmp(gDebugToolsSaveStateMenuDef.menuItems[0].name, "Back") == 0, "save-state submenu's only item must be Back");
    CHECK(gDebugToolsSaveStateMenuDef.menuItems[0].onSelected == MenuCancelSelect, "save-state submenu Back must use MenuCancelSelect");

    DebugToolsHostStub_SetFakeSaveCompatState(SAVE_COMPAT_MIGRATABLE_OLDER);
    DebugTools_GetRegisteredAction(4)->onSelected(NULL, NULL);
    CHECK(gDebugToolsProbe.saveCompatLastState == (u32)SAVE_COMPAT_MIGRATABLE_OLDER, "a re-inspect must resample a changed save-compat state");
    CHECK(gDebugToolsProbe.saveCompatInspectCount == 2, "a second inspect must increment the counter again");

    printf("DEBUGTOOLS_TOOLS_HOST_TEST: PASS\n");
    return 0;
}
