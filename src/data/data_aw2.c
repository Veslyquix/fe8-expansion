#include "global.h"

#if FE8_AW2_ASSETS

/* Advance Wars 2 UI graphics, dumped from VRAM in no$gba. Tile data is
 * LZ77-compressed; palettes are the raw 16-color dump (uncompressed, same
 * convention as this repo's other .gbapal assets). See src/aw2_gfx.c. */
const u8 __attribute__((aligned(4))) aw2uiStars_tiles[] = INCBIN_U8("graphics/aw2/aw2uiStars.4bpp.lz");
const u16 __attribute__((aligned(4))) aw2uiStars_palette[] = INCBIN_U16("graphics/aw2/aw2uiStars.gbapal");
const u8 __attribute__((aligned(4))) aw2uiStarsBig_tiles[] = INCBIN_U8("graphics/aw2/aw2uiStarsBig.4bpp.lz");
const u16 __attribute__((aligned(4))) aw2uiStarsBig_palette[] = INCBIN_U16("graphics/aw2/aw2uiStarsBig.gbapal");
const u8 __attribute__((aligned(4))) power_tiles[] = INCBIN_U8("graphics/aw2/power.4bpp.lz");
const u16 __attribute__((aligned(4))) power_palette[] = INCBIN_U16("graphics/aw2/power.gbapal");
const u8 __attribute__((aligned(4))) super_tiles[] = INCBIN_U8("graphics/aw2/super.4bpp.lz");
const u16 __attribute__((aligned(4))) super_palette[] = INCBIN_U16("graphics/aw2/super.gbapal");
const u8 __attribute__((aligned(4))) aw2debugFont_tiles[] = INCBIN_U8("graphics/aw2/aw2debugFont.4bpp.lz");
const u16 __attribute__((aligned(4))) aw2debugFont_palette[] = INCBIN_U16("graphics/aw2/aw2debugFont.gbapal");

/* Goal-window replacement (see src/player_interface.c, DrawGoalDisplayWindow,
 * #if FE8_AW2_ASSETS) -- 64x32px / 8x4 tiles. */
const u8 __attribute__((aligned(4))) aw2uiCoMini_tiles[] = INCBIN_U8("graphics/aw2/aw2uiCoMini.4bpp.lz");
const u16 __attribute__((aligned(4))) aw2uiCoMini_palette[] = INCBIN_U16("graphics/aw2/aw2uiCoMini.gbapal");

/* CO screen class-affinity movement/range bonus icons (see src/power.c,
 * CoScreen_DrawAffinityBonusIcon) -- dumped from C:\devkitPro\feex\aw2dmp\new,
 * one 8x8 tile each, left-to-right: range-arrow, foot (movement), '+',
 * '-', '1', '2', '3'. All share one palette (aw2plus.gbapal in that dump,
 * renamed here to match this sheet). */
const u8 __attribute__((aligned(4))) gGfx_CoAffinityBonusIcons_tiles[] = INCBIN_U8("graphics/aw2/gGfx_CoAffinityBonusIcons.4bpp.lz");
const u16 __attribute__((aligned(4))) gGfx_CoAffinityBonusIcons_palette[] = INCBIN_U16("graphics/aw2/gGfx_CoAffinityBonusIcons.gbapal");

/* AI-phase gold digits drawn over the OBJ copy of the CO-mini panel (see
 * DrawAw2GoldDigitsObjSprite, src/aw2_gfx.c) -- the same digit glyph sheet
 * src/draw_mapanim.c uses for battle damage numbers (that file's own copy
 * is gated behind FE8_DRAW_MAP_ANIMS; this is the same source asset dumped
 * from the vanilla save screen, included independently of that flag).
 * Raw, uncompressed dump -- CpuFastCopy it, don't Decompress. */
const u8 __attribute__((aligned(4))) gAw2GoldDigits_tiles[] = INCBIN_U8("graphics/mapanim/draw/dmp/NumbersFromSaveScreen.dmp");
const u16 __attribute__((aligned(4))) gAw2GoldDigits_palette[] = INCBIN_U16("graphics/mapanim/draw/dmp/NumbersFromSaveScreen_pal.dmp");

#endif
