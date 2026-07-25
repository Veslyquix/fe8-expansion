/*
 * Issue #11 closure -- host-executed id/label validation test driver.
 *
 * Links directly against the real, unmodified src/debugtools_registry.c
 * (compiled for the host, see test_debugtools_registry.py) plus
 * debugtools_host_stubs.c's small set of hardware/menu stand-ins, and
 * drives DebugTools_RegisterAction through the exact public API any
 * contributor action uses (include/expansion_debugtools.h), proving the
 * id==0 and empty/too-long label rejection paths this driver's sibling
 * (debugtools_registry_driver.c, capacity/order/duplicate-focused)
 * cannot exercise cleanly once its own registry is already at capacity.
 * A fresh, empty registry (a separate process per host test method) is
 * used here instead.
 *
 * Prints "DEBUGTOOLS_LABEL_VALIDATION_HOST_TEST: PASS" and exits 0 on
 * success; on any failure it prints the specific failing assertion to
 * stderr and exits 1 without running further checks (fail fast,
 * actionable diagnostic).
 */
#include <stdio.h>
#include <string.h>

#include "global.h"
#include "expansion_debugtools.h"

#define CHECK(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "DEBUGTOOLS_LABEL_VALIDATION_HOST_TEST: FAIL: %s\n", msg); \
            return 1; \
        } \
    } while (0)

static u8 DummyOnSelected(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;
    return 0;
}

int main(void)
{
    struct DebugToolsAction action;
    char longLabel[DEBUGTOOLS_LABEL_MAX_LENGTH + 2];
    char boundaryLabel[DEBUGTOOLS_LABEL_MAX_LENGTH + 1];
    int i;
    int rc;

    CHECK(DebugTools_GetRegisteredCount() == 0, "registry must start empty");

    /* --- id==0 is a reserved/uninitialized-looking sentinel, never a
     * legitimate contributor id. Must be rejected without changing the
     * registered count. --- */
    action.id = 0;
    action.label = "ZeroId";
    action.onSelected = DummyOnSelected;
    rc = DebugTools_RegisterAction(&action);
    CHECK(rc == DEBUGTOOLS_ERR_ID_INVALID, "id==0 must return DEBUGTOOLS_ERR_ID_INVALID");
    CHECK(DebugTools_GetLastRegistrationResult() == DEBUGTOOLS_ERR_ID_INVALID,
          "GetLastRegistrationResult must mirror DEBUGTOOLS_ERR_ID_INVALID");
    CHECK(DebugTools_GetRegisteredCount() == 0, "a rejected id==0 registration must not change the registered count");

    /* --- An empty label ("") must be rejected. --- */
    action.id = 1;
    action.label = "";
    action.onSelected = DummyOnSelected;
    rc = DebugTools_RegisterAction(&action);
    CHECK(rc == DEBUGTOOLS_ERR_LABEL_INVALID, "an empty label must return DEBUGTOOLS_ERR_LABEL_INVALID");
    CHECK(DebugTools_GetLastRegistrationResult() == DEBUGTOOLS_ERR_LABEL_INVALID,
          "GetLastRegistrationResult must mirror DEBUGTOOLS_ERR_LABEL_INVALID");
    CHECK(DebugTools_GetRegisteredCount() == 0, "a rejected empty-label registration must not change the registered count");

    /* --- A label one character over DEBUGTOOLS_LABEL_MAX_LENGTH must be
     * rejected. --- */
    for (i = 0; i < DEBUGTOOLS_LABEL_MAX_LENGTH + 1; ++i)
        longLabel[i] = 'A';
    longLabel[DEBUGTOOLS_LABEL_MAX_LENGTH + 1] = '\0';
    CHECK(strlen(longLabel) == (size_t)(DEBUGTOOLS_LABEL_MAX_LENGTH + 1),
          "test setup: longLabel must be exactly one character over the limit");

    action.id = 2;
    action.label = longLabel;
    action.onSelected = DummyOnSelected;
    rc = DebugTools_RegisterAction(&action);
    CHECK(rc == DEBUGTOOLS_ERR_LABEL_INVALID,
          "a label one character over DEBUGTOOLS_LABEL_MAX_LENGTH must return DEBUGTOOLS_ERR_LABEL_INVALID");
    CHECK(DebugTools_GetRegisteredCount() == 0, "a rejected too-long-label registration must not change the registered count");

    /* --- A label at exactly DEBUGTOOLS_LABEL_MAX_LENGTH must be
     * accepted (the bound is inclusive, matching the longest label
     * actually shipped in this file staying comfortably under it). --- */
    for (i = 0; i < DEBUGTOOLS_LABEL_MAX_LENGTH; ++i)
        boundaryLabel[i] = 'B';
    boundaryLabel[DEBUGTOOLS_LABEL_MAX_LENGTH] = '\0';
    CHECK(strlen(boundaryLabel) == (size_t)DEBUGTOOLS_LABEL_MAX_LENGTH,
          "test setup: boundaryLabel must be exactly at the limit");

    action.id = 3;
    action.label = boundaryLabel;
    action.onSelected = DummyOnSelected;
    rc = DebugTools_RegisterAction(&action);
    CHECK(rc == DEBUGTOOLS_OK, "a label at exactly DEBUGTOOLS_LABEL_MAX_LENGTH must be accepted");
    CHECK(DebugTools_GetRegisteredCount() == 1, "the accepted boundary-length registration must increment the registered count");

    /* --- Label pointer lifetime contract: this driver only ever
     * registers plain string-literal/static-storage labels, matching the
     * documented contributor contract (include/expansion_debugtools.h,
     * "Five bounded validated tools" / DebugTools_RegisterAction). The
     * registry stores the label pointer itself (never copies bytes), so
     * a still-valid pointer must still read back the exact same content
     * after other registration attempts have been rejected in between. */
    {
        const struct DebugToolsAction* got = DebugTools_GetRegisteredAction(0);
        CHECK(got != NULL && got->id == 3, "the boundary-length action must be readable back");
        CHECK(strcmp(got->label, boundaryLabel) == 0, "the boundary-length label must read back unchanged");
    }

    printf("DEBUGTOOLS_LABEL_VALIDATION_HOST_TEST: PASS\n");
    return 0;
}
