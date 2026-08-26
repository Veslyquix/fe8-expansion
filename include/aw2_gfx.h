#ifndef GUARD_AW2_GFX_H
#define GUARD_AW2_GFX_H

#if FE8_AW2_ASSETS

/* BG palette bank the CO-mini goal-window replacement draws with (see
 * src/aw2_gfx.c) -- exposed here so other files (src/player_interface.c's
 * palette-cycle call) don't need their own copy of the constant. */
#define AW2_COMINI_PAL_ID 15 // 3 is mmb. This will need to be changed later because it conflicts with fog. 

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

/* Cycles the CO-mini panel's color 11 between orange and yellow, one step
 * per call -- call once a frame (see GoalDisplay_Loop_Display,
 * src/player_interface.c) for the whole 32-frame back-and-forth. */
void UpdateAw2CoMiniPaletteCycle(void);

/* The player's CO gauge in half-star units (3 == one and a half stars
 * filled). OverlapStars merges that gauge onto the panel's tiles as the
 * CO's small "normal power" stars followed by its big "super" ones --
 * DrawAw2CoMini already calls it, so this is only for drawing the gauge
 * again on its own. Both are no-ops unless FE8_CO_POWERS is also on,
 * since the gauge itself lives in that feature. */
int GetStarsPlayer(void);
void OverlapStars(void);

#endif

#endif // GUARD_AW2_GFX_H
