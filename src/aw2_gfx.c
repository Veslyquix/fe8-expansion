#include "global.h"

#if FE8_AW2_ASSETS

#include "aw2_gfx.h"
#include "hardware.h"
#include "bmlib.h"
#include "variables.h"

/* Defined in src/data/data_aw2.c (INCBIN_U8/U16 only expand for files under
 * src/data/, which go through tools/preproc -- see modern.mk). */
extern const u8 aw2uiStars_tiles[];
extern const u16 aw2uiStars_palette[];
extern const u8 aw2uiStarsBig_tiles[];
extern const u16 aw2uiStarsBig_palette[];
extern const u8 power_tiles[];
extern const u16 power_palette[];
extern const u8 super_tiles[];
extern const u16 super_palette[];
extern const u8 aw2debugFont_tiles[];
extern const u16 aw2debugFont_palette[];
extern const u8 aw2uiCoMini_tiles[];
extern const u16 aw2uiCoMini_palette[];

/* Dimensions in tiles (8x8px each), matching each PNG's actual size. */
#define AW2_STARS_W     3  // 24x8
#define AW2_STARS_H     1
#define AW2_STARSBIG_W  2  // 16x48
#define AW2_STARSBIG_H  6
#define AW2_POWER_W     4  // 32x8
#define AW2_POWER_H     1
#define AW2_SUPER_W     6  // 48x8
#define AW2_SUPER_H     1
#define AW2_FONT_W      8  // 64x64
#define AW2_FONT_H      8

/* OBJ palette banks (flat 0-31 numbering: 0-15 BG, 16-31 OBJ, see
 * ApplyPalette/hardware.h) -- placeholders, adjust if they collide with
 * something else once this is wired into an actual screen. */
#define AW2_STARS_PAL_ID     20
#define AW2_STARSBIG_PAL_ID  21
#define AW2_POWER_PAL_ID     22
#define AW2_SUPER_PAL_ID     23
#define AW2_FONT_PAL_ID      24

/* Base OBJ VRAM address for the whole strip; each image is placed back to
 * back after the previous one, in this order. Copy2dChr (src/bmlib.c)
 * advances the destination by a full 32-tile row (CHR_SIZE * 0x20 bytes)
 * per source row, so each image occupies exactly `height` such rows
 * regardless of its own width -- the next image's base address is offset
 * by (own height * 0x400) bytes accordingly. */
#define AW2_VRAM_BASE ((void*)0x06013000)

static void LoadAw2Image(
    const void* tiles, const u16* palette, int tileWidth, int tileHeight,
    void* dst, int palId)
{
    Decompress(tiles, gGenericBuffer);
    Copy2dChr(gGenericBuffer, dst, tileWidth, tileHeight);
    ApplyPalette(palette, palId);
}

static void OverlapVram(
    const void* tiles, const u16* palette, int tileWidth, int tileHeight,
    void* dst, int palId, int xOffset)
{
    Decompress(tiles, gGenericBuffer);
    Copy2dChrTransparent(gGenericBuffer, dst, tileWidth, tileHeight, xOffset);
}

void LoadAw2Gfx(void)
{
    u8* dst = AW2_VRAM_BASE;

    LoadAw2Image(aw2uiStars_tiles, aw2uiStars_palette,
        AW2_STARS_W, AW2_STARS_H, dst, AW2_STARS_PAL_ID);
    dst += AW2_STARS_H * CHR_SIZE * 0x20;

    LoadAw2Image(aw2uiStarsBig_tiles, aw2uiStarsBig_palette,
        AW2_STARSBIG_W, AW2_STARSBIG_H, dst, AW2_STARSBIG_PAL_ID);
    dst += AW2_STARSBIG_H * CHR_SIZE * 0x20;

    LoadAw2Image(power_tiles, power_palette,
        AW2_POWER_W, AW2_POWER_H, dst, AW2_POWER_PAL_ID);
    dst += AW2_POWER_H * CHR_SIZE * 0x20;

    LoadAw2Image(super_tiles, super_palette,
        AW2_SUPER_W, AW2_SUPER_H, dst, AW2_SUPER_PAL_ID);
    dst += AW2_SUPER_H * CHR_SIZE * 0x20;

    LoadAw2Image(aw2debugFont_tiles, aw2debugFont_palette,
        AW2_FONT_W, AW2_FONT_H, dst, AW2_FONT_PAL_ID);
}



/* --- Goal-window replacement (src/player_interface.c) --------------------
 * The goal window is drawn as BG tiles, not an OBJ sprite: its frame comes
 * from gTSA_GoalBox_OneLine/TwoLines (src/data/data_A167C8.c), referenced as
 * TILEREF(0x0, 1) on gUiTmScratchB -- which maps to BG1, and in the default
 * map-screen bgConfig (src/hardware.c) BG0/BG1/BG2 all share char base 0x0
 * with the common UI frame sheet (gUiFrameImage, graphics/misc/, 256x32px =
 * 128 tiles). So this needs its own tiles decompressed into that SAME
 * shared char block, at a tile offset past that sheet's 128 tiles, and
 * referenced through the same TILEREF/gUiTmScratchB mechanism the goal
 * window already uses -- not the separate OBJ VRAM region LoadAw2Gfx uses
 * above, and not a spare BG palette bank the map screen's UI already claims
 * (banks 0-2 are all live there; this uses bank 3, unverified past a visual
 * check in-game -- adjust AW2_COMINI_PAL_ID if colors look wrong). */
#define AW2_COMINI_W        8  // 64x32
#define AW2_COMINI_H        4
#define AW2_COMINI_TILE_BASE 0x180  
#define AW2_COMINI_PAL_ID   4 // 3 is mmb 

void LoadAw2Stars(void) 
{ 
    u8* dst = (void*)(VRAM + GetBackgroundTileDataOffset(1) + AW2_COMINI_TILE_BASE * CHR_SIZE);
    
    Decompress(aw2uiCoMini_tiles, dst);
    dst += AW2_COMINI_H * AW2_COMINI_W * 0x20; 

    LoadAw2Image(aw2uiStars_tiles, aw2uiStars_palette,
        AW2_STARS_W, AW2_STARS_H, dst, AW2_COMINI_PAL_ID);
    dst += AW2_STARS_H * CHR_SIZE * 0x20;

    LoadAw2Image(aw2uiStarsBig_tiles, aw2uiStarsBig_palette,
        AW2_STARSBIG_W, AW2_STARSBIG_H, dst, AW2_COMINI_PAL_ID);
    dst += AW2_STARSBIG_H * CHR_SIZE * 0x20;

    
} 


void LoadAw2CoMiniGfx(void)
{
    LoadAw2Stars(); 
    
    // Decompress(aw2uiCoMini_tiles,
        // (void*)(VRAM + GetBackgroundTileDataOffset(1) + AW2_COMINI_TILE_BASE * CHR_SIZE));
    ApplyPalette(aw2uiCoMini_palette, AW2_COMINI_PAL_ID);
}




void GetStarsPlayer(void) { 
    int faction = 0; // Player 
    const struct CoDefinition* co = GetCoDefinition(gPlaySt.commanderId[sCoFactionIds[faction]]);
    int gauge = gPlaySt.coGauge[sCoFactionIds[faction]]; 
    int stars = gauge / 50; 
    int halfStar = (gauge + 25) / 50; 
    return halfStar; 
} 
// the co definition needs to include the number of stars required for co power and super co power. 
// then we need to draw those stars to the ui. 
// for example, Francis may require 3 stars for co power and 5 for super co power. So we draw 
// 3 little stars, then 2 big stars. 
// If his gauge has 1.5 stars filled, then we draw full little star, half little star, empty little star 
// empty big star, empty big star. 



void OverlapStars(u16* dst) { 
    u8* dest = (void*)(VRAM + GetBackgroundTileDataOffset(1) + AW2_COMINI_TILE_BASE * CHR_SIZE);
    dest += AW2_COMINI_H * 2 * 0x20; // this dest is for just the top 2 pixels of the star. 
    OverlapVram(aw2uiStars_tiles, aw2uiStars_palette,
        1, AW2_STARS_H, dest, AW2_COMINI_PAL_ID, 3);
    dest += AW2_COMINI_H * 2 * 0x20; // this dest is for the main part (the rest) of the star. 
    OverlapVram(aw2uiStars_tiles, aw2uiStars_palette,
        1, AW2_STARS_H, dest, AW2_COMINI_PAL_ID, 3);
    // AW2_STARS_W is for all 3 stars 
    // we need to decompress the 3 types of small stars: empty, half filled, and filled. 
    // we also need to decompress the 3 types of large stars: empty, half filled, and filled. 
    // then with all of these decompressed into the generic buffer, we need to overlap them onto the 
    // UI using this function. 
    


} 

void DrawAw2CoMini(u16* dst)
{
    int x, y;

    for (y = 0; y < AW2_COMINI_H; ++y) {
        for (x = 0; x < AW2_COMINI_W; ++x) {
            dst[TILEMAP_INDEX(x, y)] =
                TILEREF(AW2_COMINI_TILE_BASE + y * AW2_COMINI_W + x, AW2_COMINI_PAL_ID);
        }
    }
    OverlapStars(dst); 
}

#endif
