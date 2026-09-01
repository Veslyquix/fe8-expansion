/* Danger Radius: fog-of-war-aware enemy attack range overlay.
 * Original hack ("FE8U_FogDR") by Huichelaar. Ported to native C here. */
#ifndef GUARD_DANGERRADIUS_H
#define GUARD_DANGERRADIUS_H

#include "expansion_config.h"

#if FE8_DANGER_RADIUS

struct Unit;

/* Computes background palette slots 0xB-0xF ("fog palette") from slots
 * 0x6-0xA ("normal palette") of the currently-loaded map/tileset palette,
 * by boosting red and lowering green/blue (matches
 * Graphics/TilesetFogFilter.py's default modifiers: r=+4, g=-16, b=-16,
 * clamped to [0, 31] -- confirmed against the original hack's README, which
 * documents these exact values as its own defaults). Call this whenever the
 * map palette is (re)loaded, so palette 0xB-0xF is always a valid "no fog"
 * tint of 0x6-0xA even when Fog of War is disabled for the chapter (Danger
 * Radius repurposes the otherwise-idle fog palette banks to draw its
 * overlay -- see DangerRadius_Refresh). */
void DangerRadius_GenerateFogPalette(void);

/* Toggles the danger radius overlay. Mirrors DetermineDR.asm: if cursor is
 * over a live enemy unit, only that unit's overlay is toggled; otherwise
 * this clears an already-active overlay, or (when inactive) shows every
 * enemy's range at once, matching the original hack's default
 * NonEnemySELECT=AllDR config (NearbyDR is not implemented -- this repo
 * exposes no build-time equivalent of that choice). Pass NULL for
 * hoveredEnemy if the cursor isn't over a unit, or the unit under the
 * cursor isn't an enemy (only FACTION_RED units toggle; passing an ally is
 * equivalent to passing NULL). Callers must gate this on
 * gPlaySt.chapterVisionRange == 0 (Fog of War off) themselves -- Danger
 * Radius reuses the FOW palette banks and is unavailable whenever FOW
 * would otherwise be using them (see original hack's LIMITATIONS section;
 * FOW-active maps keep vanilla Danger Zone behaviour instead). */
void DangerRadius_Determine(struct Unit* hoveredEnemy);

/* Clears US_SHOWRANGE from every unit and resets the DR unit counter.
 * Called on any phase switch while player phase is ending (see EndDR.asm,
 * called from BmMain_ChangePhase). */
void DangerRadius_End(void);

/* Clears US_SHOWRANGE and decrements the active count for a single unit
 * being removed from play (death, RAM-slot clear, faction change).
 * Idempotent: safe to call on a unit that never had US_SHOWRANGE set, or
 * isn't an enemy. Mirrors ClearDR1-4.asm; call before any code clears or
 * overwrites the unit's state/allegiance fields, since this reads them.
 * NOTE: because this repo's ClearUnit() (src/bmunit.c) is the single
 * primitive underlying unit-slot clearing, unit death cleanup, and
 * UnitChangeFaction (which itself calls ClearUnit), one call site inside
 * ClearUnit covers three of the four original hooks (ClearDR2/3/4); only
 * UnitKill's enemy-death path (ClearDR1) needs its own separate call. */
void DangerRadius_UnitRemoved(struct Unit* unit);

/* Returns the number of units currently showing their range (DRCountByte
 * in the original hack). Danger Radius is "active" whenever this is > 0. */
int DangerRadius_GetActiveCount(void);

/* Draws the blinking Danger Radius marker over a unit with US_SHOWRANGE
 * set. Mirrors DisplayIcon.asm; call once per on-screen unit from
 * PutUnitSpriteIconsOam (see src/bmudisp.c), guarded the same way that
 * function already gates its other blinking per-unit icons (poison/sleep/
 * rescue/boss/DrawObtainableItemIcon) on its displayRescueIcon timer --
 * DisplayIcon.asm itself has no blink timing of its own, so this reuses
 * that existing cadence rather than inventing a new one. Caller must
 * check unit->state & US_SHOWRANGE first. */
void DangerRadius_DrawIcon(struct Unit* unit);

/* Recalculates and redraws the danger radius overlay for every unit
 * currently flagged with US_SHOWRANGE, by writing into gBmMapFog (see the
 * .c file's doc comment for exactly how) and forcing a tile redraw.
 * Mirrors InitializeDR.lyn.event's FOW-off branch. Call sites that trigger
 * a recalc (ActionCommitDR/ActionCancelDR/UpdateDRMove in the original
 * hack) should only call this when DangerRadius_GetActiveCount() > 0 --
 * DangerRadius_Determine/_End call it unconditionally themselves since
 * they also need to redraw an overlay that just became empty.
 *
 * NOT YET PORTED: the blinking enemy-sprite icon (DisplayIcon.asm) needs a
 * new graphics asset this port hasn't brought in yet. Everything else
 * (the fog-palette tile tint itself, and the escape-tile-marker fix so it
 * isn't hidden by DR's fog-palette repurposing) is implemented. */
void DangerRadius_Refresh(void);

#endif /* FE8_DANGER_RADIUS */

#endif /* GUARD_DANGERRADIUS_H */
