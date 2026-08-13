#include "gbafe.h"
#include "expansion_config.h"

#if FE8_DISPLAY_OBTAINABLE_ITEM

#include <string.h>

#include "bmunit.h"
#include "bmitem.h"
#include "bmmind.h"
#include "bm.h"
#include "ctc.h"
#include "constants/items.h"

/* Modern-build port of a FEBuilder-style ROM patch that draws a small icon
 * over enemy units carrying either a droppable item (US_DROP_ITEM, already
 * a vanilla flag) or a stealable item, so the player can see at a glance
 * which enemies are worth attacking/stealing from without opening each
 * unit's inventory. "Danger radius" icon support from the original patch
 * is intentionally not ported: it shipped disabled by default there too
 * (its own config table's flag was False), so it was dead code.
 *
 * gGfx_ObtainableItemIcons replaces the misc UI icon sheet LoadObjUIGfx
 * normally loads (graphics/misc/gGfx_MiscUiGraphics.4bpp.lz) with a
 * superset sheet that adds the stealable/droppable icon tiles this file
 * draws via IconID_Stealable/IconID_Droppable -- copied byte-for-byte from
 * the original patch's own precompiled/tested LZ77 asset rather than
 * re-exported from its source PNG, so the exact compressed bitstream (and
 * therefore in-VRAM tile layout) is unchanged from what that patch shipped
 * and tested. NEEDS VISUAL VERIFICATION IN AN EMULATOR: this swaps a
 * shared graphics sheet used by other UI (cursor hand, etc. -- see
 * LoadObjUIGfx's Copy2dChr call), and this file cannot render GBA output
 * to confirm every existing icon still looks right afterward. The asset
 * itself is embedded from src/data/ui/obtainable_item_icons.c (INCBIN_U8
 * is only preprocessed for src/data/{...} sources -- see modern.mk's
 * MODERN_ALL_DATA_C_SOURCES). */
extern u8 gGfx_ObtainableItemIcons[];

enum
{
    IconID_Stealable = 0x65 | 0x800,
    IconID_Droppable = 0x69 | 0x800,
};

/* One bit per enemy unit index (0x80-0xBF, i.e. index & 0x3F -> bit). */
static u8 sStealableItemCache[8];

static bool IsUnitOnFieldForStealCache(struct Unit* unit)
{
    if (!UNIT_IS_VALID(unit))
        return false;

    if (unit->state & US_UNAVAILABLE)
        return false;

    return true;
}

static void SetUnitStealableItemBit(const struct Unit* unit)
{
    u8 index = unit->index & 0x3F;
    sStealableItemCache[index >> 3] |= 1 << (index & 7);
}

/* Called once per phase change (ClearActiveFactionGrayedStates) and again
 * right after any steal action resolves (HandlePostActionTraps), so the
 * cache never shows an already-stolen item as still stealable. */
void SetupCacheForStealableItems(void)
{
    int i;

    memset(sStealableItemCache, 0, sizeof(sStealableItemCache));

    for (i = 0x80; i < 0xC0; i++)
    {
        struct Unit* unit = GetUnit(i);
        int slot;

        if (!IsUnitOnFieldForStealCache(unit))
            continue;

        for (slot = 0; slot < UNIT_ITEM_COUNT; slot++)
        {
            if (unit->items[slot] == ITEM_NONE)
                continue;

            if (IsItemStealable(unit->items[slot]))
            {
                SetUnitStealableItemBit(unit);
                break;
            }
        }
    }
}

static bool DoesUnitHaveStealableItem(const struct Unit* unit)
{
    u8 index;

    if (!(unit->index & 0x80)) /* enemies only */
        return false;

    index = unit->index & 0x3F;
    return (sStealableItemCache[index >> 3] >> (index & 7)) & 1;
}

/* Called once per on-screen unit from PutUnitSpriteIconsOam. */
void DrawObtainableItemIcon(struct Unit* unit)
{
    int x, y, oam2;

    if (unit->state & US_DROP_ITEM)
        oam2 = IconID_Droppable;
    else if (DoesUnitHaveStealableItem(unit))
        oam2 = IconID_Stealable;
    else
        return;

    x = unit->xPos * 16 - 8 - gBmSt.camera.x;
    y = unit->yPos * 16 + 7 - gBmSt.camera.y;

    if (x < -16 || x > DISPLAY_WIDTH)
        return;

    if (y < -16 || y > DISPLAY_HEIGHT)
        return;

    CallARM_PushToSecondaryOAM(OAM1_X(x + 0x209), OAM0_Y(y + 0x100), gObject_8x8, oam2);
}

#endif /* FE8_DISPLAY_OBTAINABLE_ITEM */
