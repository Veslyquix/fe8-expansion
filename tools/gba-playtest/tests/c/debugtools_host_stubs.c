/*
 * Issue #11 slice 1 -- host-test-only stub implementations for the small
 * set of GBA-hardware/menu-engine symbols that src/debugtools_registry.c
 * references but this host test never actually needs to execute (menu
 * construction/rendering, hardware key polling). These stubs exist ONLY
 * so the real, unmodified src/debugtools_registry.c can be compiled and
 * linked with a native host compiler (see
 * tools/gba-playtest/tests/test_debugtools_registry.py) to exercise its
 * registration logic (capacity/order/duplicate/error behavior) with real
 * executed code instead of source-text pattern matching alone.
 *
 * This file is never compiled into the actual GBA ROM (not referenced by
 * modern.mk/Makefile) and is not itself part of the debug-tools feature.
 */
#include "global.h"
#include "hardware.h"
#include "fontgrp.h"
#include "uimenu.h"

struct KeyStatusBuffer gDebugToolsTestKeyStatus = {0};
struct KeyStatusBuffer * CONST_DATA gKeyStatusPtr = &gDebugToolsTestKeyStatus;

struct LCDControlBuffer gLCDControlBuffer = {0};

/* Issue #11 closure: DebugTools_PrepHotkeyCheck (src/debugtools_registry.c)
 * now reads gPlaySt.chapterStateBits to observe a live prep screen --
 * a plain zero-initialized instance is enough for this registration-
 * focused driver (PLAY_FLAG_PREPSCREEN simply reads as unset). */
struct PlaySt gPlaySt = {0};

static u16 sStubBgMap[32 * 32];

u16* BG_GetMapBuffer(int bg)
{
    (void)bg;
    return sStubBgMap;
}

void SetupDebugFontForBG(int bg, int tileDataOffset)
{
    (void)bg;
    (void)tileDataOffset;
}

void PrintDebugStringToBG(u16* bg, const char* asciiStr)
{
    (void)bg;
    (void)asciiStr;
}

u8 MenuAlwaysEnabled(const struct MenuItemDef* def, int number)
{
    (void)def;
    (void)number;
    return 1;
}

u8 MenuCancelSelect(struct MenuProc* menu, struct MenuItemProc* item)
{
    (void)menu;
    (void)item;
    return 0;
}

struct MenuProc* StartOrphanMenu(const struct MenuDef* def)
{
    (void)def;
    /* The registration-focused host test never opens the real hub menu
     * (that requires the full Proc/rendering engine); it only calls
     * DebugTools_RegisterAction et al. directly. */
    return NULL;
}

void DebugTools_RegisterBuiltinActions(void)
{
    /* The real implementation (src/debugtools_launcher.c) depends on the
     * full Proc/game-control engine, well outside what a registration-
     * behavior host test needs; this test drives DebugTools_RegisterAction
     * directly instead of going through DebugTools_OpenHub's lazy
     * registration path. */
}

void DebugTools_RegisterChapter4PrepAction(void)
{
    /* Issue #11 closure: the real implementation (src/debugtools_launcher.c)
     * has its own dedicated host tests and is deliberately not linked
     * here; src/debugtools_registry.c's DebugTools_OpenHub calls this
     * function unconditionally, so a stand-in is needed here too. */
}

void DebugTools_RegisterWeatherFogActions(void)
{
    /* The real implementation (src/debugtools_actions.c, slice 2) has its
     * own dedicated host tests (debugtools_actions_driver.c); this
     * registration-focused driver only needs DebugTools_OpenHub() to
     * remain linkable, not to actually register Weather/Fog. */
}

void DebugTools_RegisterExtendedToolActions(void)
{
    /* Issue #11 closure: the real implementation (src/debugtools_tools.c)
     * has its own dedicated host tests; this registration-focused driver
     * only needs DebugTools_OpenHub() to remain linkable, not to actually
     * register the five extended tools. */
}
