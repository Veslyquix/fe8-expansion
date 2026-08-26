#ifndef GUARD_AW2_GFX_H
#define GUARD_AW2_GFX_H

#if FE8_AW2_ASSETS

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

#endif

#endif // GUARD_AW2_GFX_H
