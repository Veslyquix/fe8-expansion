/* Danger Radius: fog-of-war-aware enemy attack range overlay.
 * Original hack ("FE8U_FogDR") by Huichelaar; ported to native C here. */
#include "global.h"

#include "expansion_config.h"

#if FE8_DANGER_RADIUS

#include "dangerradius.h"
#include "bmunit.h"
#include "hardware.h"

/* Number of enemy units currently flagged with US_SHOWRANGE (mirrors
 * DRCountByte in the original hack). */
static int sDangerRadiusActiveCount = 0;

int DangerRadius_GetActiveCount(void)
{
    return sDangerRadiusActiveCount;
}

/* Port of Graphics/TilesetFogFilter.py's per-color transform: background
 * palette rows 0x6-0xA (5 rows x 16 colors = 80 colors) are copied to rows
 * 0xB-0xF with red boosted and green/blue lowered, each channel clamped to
 * the valid 5-bit [0, 31] range. GBA colors are BGR555 in gPaletteBuffer:
 * bits 0-4 red, 5-9 green, 10-14 blue (see RED_MASK/GREEN_MASK/BLUE_MASK
 * in include/hardware.h), matching the script's bit layout exactly. */
#define DR_FOG_RED_MOD 4
#define DR_FOG_GREEN_MOD (-16)
#define DR_FOG_BLUE_MOD (-16)

static inline int DangerRadius_ClampChannel(int value)
{
    if (value < 0)
        return 0;
    if (value > 31)
        return 31;
    return value;
}

void DangerRadius_GenerateFogPalette(void)
{
    int srcPal, color;

    for (srcPal = 0x6; srcPal <= 0xA; srcPal++)
    {
        int dstPal = srcPal + 0x5; /* 0x6->0xB, ..., 0xA->0xF */

        for (color = 0; color < 16; color++)
        {
            u16 src = PAL_BG_COLOR(srcPal, color);
            int red = DangerRadius_ClampChannel((src & RED_MASK) + DR_FOG_RED_MOD);
            int green = DangerRadius_ClampChannel(((src & GREEN_MASK) >> 5) + DR_FOG_GREEN_MOD);
            int blue = DangerRadius_ClampChannel(((src & BLUE_MASK) >> 10) + DR_FOG_BLUE_MOD);

            PAL_BG_COLOR(dstPal, color) = (u16)(red | (green << 5) | (blue << 10));
        }
    }
}

static void DangerRadius_SetUnitShown(struct Unit* unit, bool shown)
{
    if (shown)
        unit->state |= US_SHOWRANGE;
    else
        unit->state &= ~US_SHOWRANGE;
}

/* Clears US_SHOWRANGE from every enemy unit and resets the active count.
 * Equivalent to EndDR.asm / UnsetAllDR. */
void DangerRadius_End(void)
{
    int i;

    if (sDangerRadiusActiveCount == 0)
        return;

    for (i = 0; i < 50; i++)
    {
        struct Unit* unit = &gUnitArrayRed[i];

        if (unit->pCharacterData != NULL)
            DangerRadius_SetUnitShown(unit, false);
    }

    sDangerRadiusActiveCount = 0;
}

static void DangerRadius_SetAll(void)
{
    int i;
    int count = 0;

    for (i = 0; i < 50; i++)
    {
        struct Unit* unit = &gUnitArrayRed[i];

        if (unit->pCharacterData != NULL)
        {
            DangerRadius_SetUnitShown(unit, true);
            count++;
        }
    }

    sDangerRadiusActiveCount = count;
}

/* Toggles danger radius display. When called while the cursor is over a
 * live enemy unit, only that unit's overlay is toggled; otherwise this
 * clears an already-active overlay, or (when inactive) shows every enemy's
 * range at once -- matches NonEnemySELECT=AllDR, the original hack's own
 * default (see FogDR.event). NearbyDR is not implemented. See
 * DetermineDR.asm for the original branch structure this mirrors. */
void DangerRadius_Determine(struct Unit* hoveredEnemy)
{
    if (hoveredEnemy != NULL && UNIT_FACTION(hoveredEnemy) == FACTION_RED)
    {
        bool wasShown = (hoveredEnemy->state & US_SHOWRANGE) != 0;

        DangerRadius_SetUnitShown(hoveredEnemy, !wasShown);
        sDangerRadiusActiveCount += wasShown ? -1 : 1;
        DangerRadius_Refresh();
        return;
    }

    if (sDangerRadiusActiveCount > 0)
        DangerRadius_End();
    else
        DangerRadius_SetAll();

    DangerRadius_Refresh();
}

/* Mirrors ClearDR1-4.asm: called whenever a unit is being permanently
 * removed from play (or has its allegiance/state fields about to be
 * overwritten), so US_SHOWRANGE and the active count stay consistent. Must
 * be called BEFORE the caller clears/overwrites the unit's state or
 * allegiance fields. */
void DangerRadius_UnitRemoved(struct Unit* unit)
{
    if (UNIT_FACTION(unit) != FACTION_RED)
        return;

    if (!(unit->state & US_SHOWRANGE))
        return;

    unit->state &= ~US_SHOWRANGE;

    if (sDangerRadiusActiveCount > 0)
        sDangerRadiusActiveCount--;
}

/* TODO(danger-radius-tier2): stub. See include/dangerradius.h's doc comment
 * for exactly what's not yet ported (MapAddInRange/SetFog/InvertFog/
 * RefreshFog/DisplayDR/DisplayMarker/DisplayIcon/InitializeDR). */
void DangerRadius_Refresh(void)
{
}

#endif /* FE8_DANGER_RADIUS */
