/* Danger Radius: fog-of-war-aware enemy attack range overlay.
 * Original hack ("FE8U_FogDR") by Huichelaar; ported to native C here. */
#include "global.h"

#include "expansion_config.h"

#if FE8_DANGER_RADIUS

#include "dangerradius.h"
#include "bmunit.h"
#include "bmmap.h"
#include "bmidoten.h"
#include "bm.h"
#include "ctc.h"
#include "hardware.h"

/* Shares the merged icon sheet gGfx_ObtainableItemIcons already loads for
 * FE8_DISPLAY_OBTAINABLE_ITEM/FE8_HP_BARS (see LoadObjUIGfx, src/bm.c;
 * DISPLAY_OBTAINABLE_ITEM's own IconID_Stealable already claims the
 * original hack's tile 0x65, so this uses the free slot the sheet's
 * updated source graphics/misc/gGfx_ObtainableItemIcons.png actually
 * places the new icon at instead -- see the port's status notes for how
 * that tile index was derived). */
enum
{
    IconID_DangerRadius = 0x4C | 0x800,
};

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
 * Equivalent to EndDR.asm / UnsetAllDR. Always leaves the overlay redrawn
 * to match (an empty overlay when nothing is left flagged), so every
 * caller (the phase-end hook in BmMain_ChangePhase, and
 * DangerRadius_Determine's "clear an active overlay" branch) gets a
 * consistent result without having to remember to refresh separately. */
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
    DangerRadius_Refresh();
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

/* Sets US_SHOWRANGE on every live enemy and redraws, unconditionally.
 * Called automatically at the start of every player phase -- see
 * include/dangerradius.h. */
void DangerRadius_ActivateAllAtPhaseStart(void)
{
    DangerRadius_SetAll();
    DangerRadius_Refresh();
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
    {
        DangerRadius_End(); /* self-refreshes */
    }
    else
    {
        DangerRadius_SetAll();
        DangerRadius_Refresh();
    }
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

/* Computes the union of every US_SHOWRANGE-flagged enemy's attack range
 * into gBmMapRange (scratch -- reusing the same buffer/primitives vanilla
 * GenerateDangerZoneRange uses for the unused Danger Zone feature, since
 * the two are never active at once), then writes the *inverse* into
 * gBmMapFog: 0 (the engine's "tile is fogged/hidden" value -- see
 * DisplayBmTile's gBmMapFog[y][x] ? paletteBank6 : paletteBank11 palette
 * pick in src/bmmap.c) for every danger tile, 1 ("visible") everywhere
 * else. This gives danger tiles the fog-tinted palette (which
 * DangerRadius_GenerateFogPalette keeps populated) without needing to
 * touch DisplayBmTile at all -- the vanilla FOW rendering path already
 * does exactly what Danger Radius needs, once gBmMapFog holds the right
 * marks. Deliberately reimplements GenerateDangerZoneRange's loop (rather
 * than adding a filter parameter to it) to keep this feature fully
 * additive/isolated from that shared vanilla function; the original
 * hack's SetFog.asm instead redirected MapAddInRange's writes directly
 * with a blunt unconditional "mark 1", which is over-inclusive for any
 * enemy with attack min-range > 1 (it also marks the too-close excluded
 * tiles) -- going through gBmMapRange's normal 0-accumulate-then-
 * threshold semantics here avoids that inaccuracy. */
static void DangerRadius_ComputeOverlay(void)
{
    int i, x, y;
    int hasMagicRank, prevHasMagicRank = -1;
    u8 savedUnitId;

    BmMapFill(gBmMapRange, 0);

    for (i = 0; i < 50; i++)
    {
        struct Unit* unit = &gUnitArrayRed[i];

        if (unit->pCharacterData == NULL)
            continue;

        if (!(unit->state & US_SHOWRANGE))
            continue;

        if (unit->state & US_UNDER_A_ROOF)
            continue;

        GenerateUnitMovementMapExt(unit, UNIT_MOV(unit));

        savedUnitId = gBmMapUnit[unit->yPos][unit->xPos];
        gBmMapUnit[unit->yPos][unit->xPos] = 0;

        hasMagicRank = UnitHasMagicRank(unit);

        if (prevHasMagicRank != hasMagicRank)
        {
            BmMapFill(gBmMapOther, 0);

            if (hasMagicRank)
                GenerateMagicSealMap(1);

            prevHasMagicRank = hasMagicRank;
        }

        SetWorkingBmMap(gBmMapRange);
        GenerateUnitCompleteAttackRange(unit);

        gBmMapUnit[unit->yPos][unit->xPos] = savedUnitId;
    }

    BmMapFill(gBmMapMovement, -1);

    for (y = 0; y < gBmMapSize.y; y++)
        for (x = 0; x < gBmMapSize.x; x++)
            gBmMapFog[y][x] = (gBmMapRange[y][x] == 0);
}

/* Recalculates and redraws the danger radius overlay. Mirrors
 * InitializeDR.lyn.event's FOW-off branch (the FOW-active branch isn't
 * ported -- Danger Radius is unavailable whenever FOW is active, see
 * include/dangerradius.h). Callers are responsible for the
 * chapterVisionRange == 0 gate; this always recomputes unconditionally
 * (including "overlay is now empty" when nothing is flagged), matching
 * DangerRadius_End's need to redraw a cleared overlay. */
void DangerRadius_Refresh(void)
{
    DangerRadius_ComputeOverlay();
    RenderBmMap();
}

/* DisplayIcon.asm. */
void DangerRadius_DrawIcon(struct Unit* unit)
{
    int x, y;

    x = unit->xPos * 16 - 8 - gBmSt.camera.x;
    y = unit->yPos * 16 + 7 - gBmSt.camera.y;

    if (x < -16 || x > DISPLAY_WIDTH)
        return;

    if (y < -16 || y > DISPLAY_HEIGHT)
        return;

    CallARM_PushToSecondaryOAM(OAM1_X(x + 0x209), OAM0_Y(y + 0x100), gObject_8x8, IconID_DangerRadius);
}

#endif /* FE8_DANGER_RADIUS */
