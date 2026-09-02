#ifndef GUARD_AW2_GFX_H
#define GUARD_AW2_GFX_H

#if FE8_AW2_ASSETS

/* BG palette bank the CO-mini goal-window replacement draws with (see
 * src/aw2_gfx.c) -- exposed here so other files (src/player_interface.c's
 * palette-cycle call) don't need their own copy of the constant. */
#define AW2_COMINI_PAL_ID 3 // now 1 is mmb. 

/* Loads all 5 Advance Wars 2 UI graphics (star/rank icons, POWER/SUPER
 * labels, debug font) into OBJ VRAM, back to back starting at 0x6013000. */
void LoadAw2Gfx(void);

/* Goal-window replacement (src/player_interface.c, DrawGoalDisplayWindow).
 * LoadAw2CoMiniGfx decompresses the tile graphics + palette once; call it
 * from GoalDisplay_Init. DrawAw2CoMini writes the 8x4 tile block itself into
 * a BG tilemap (dst is expected to already be TILEMAP_INDEX-offset to the
 * desired top-left tile, same convention as PutText/CallARM_FillTileRect). */
void LoadAw2CoMiniGfx(void);
void DrawAw2CoMini(u16* dst);

/* AI-phase-only OBJ sprite version of the same panel -- BG1 doesn't
 * reliably show during AI/CP phase, so that phase draws this as a single
 * 64x32 OBJ instead (see the big comment in src/aw2_gfx.c). Call
 * LoadAw2CoMiniObjGfx once (GoalDisplay_Init, alongside LoadAw2CoMiniGfx)
 * and DrawAw2CoMiniObjSprite once a frame while it should be visible,
 * same as DrawAw2PowerBannerSprite below. Player phase is unaffected and
 * still goes through DrawAw2CoMini above. */
void LoadAw2CoMiniObjGfx(void);
void DrawAw2CoMiniObjSprite(int x, int y);

/* Gold amount overlaid on the OBJ panel above -- LoadAw2CoMiniObjGfx already
 * calls LoadAw2GoldDigitsObjGfx, so that's only exposed for symmetry; call
 * DrawAw2GoldDigitsObjSprite once a frame right after DrawAw2CoMiniObjSprite
 * (same layer, so the digits land on top -- see its comment in
 * src/aw2_gfx.c) with the amount to show, right-aligned at (rightX, y). */
void LoadAw2GoldDigitsObjGfx(void);
void DrawAw2GoldDigitsObjSprite(int rightX, int y, int gold);

/* Cycles the CO-mini panel's color 11 between orange and yellow, one step
 * per call -- call once a frame (see GoalDisplay_Loop_Display,
 * src/player_interface.c) for the whole 32-frame back-and-forth. */
void UpdateAw2CoMiniPaletteCycle(void);

/* Same cycle, for the AI-phase OBJ copy -- call once a frame from
 * AiGoalDisplay_Loop (src/player_interface.c) instead of
 * UpdateAw2CoMiniPaletteCycle, which only touches the BG palette bank the
 * OBJ copy doesn't use. */
void UpdateAw2CoMiniObjPaletteCycle(void);

/* The currently active phase faction's (gPlaySt.faction) CO gauge in
 * half-star units (3 == one and a half stars filled). OverlapStars merges
 * that gauge onto the panel's tiles as the CO's small "normal power" stars
 * followed by its big "super" ones -- DrawAw2CoMini already calls it, so
 * this is only for drawing the gauge again on its own. Both are no-ops
 * unless FE8_CO_POWERS is also on, since the gauge itself lives in that
 * feature. */
int GetActiveFactionStars(void);
void OverlapStars(void);

/* CO power/super power intro banner (src/power.c, gProcScr_CoPowers) --
 * decompresses whichever of power_tiles/super_tiles is needed into OBJ
 * VRAM slots near where LoadAw2Gfx reserves for it (unused elsewhere,
 * since nothing currently calls LoadAw2Gfx), then DrawAw2PowerBannerSprite
 * puts it on screen centred at 4x native size (via an affine OBJ), one
 * call per frame like any other OBJ sprite. SUPER is 48x8, which isn't a
 * single valid OBJ shape even before scaling, so it's drawn as two
 * adjacent sprites (32x8 + 16x8 native, each scaled 4x). */
void LoadAw2PowerBannerGfx(bool8 isSuper);
void DrawAw2PowerBannerSprite(bool8 isSuper);

#endif

#endif // GUARD_AW2_GFX_H
