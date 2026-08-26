#include "global.h"

#if FE8_AW2_ASSETS

#include "aw2_gfx.h"
#include "hardware.h"
#include "bmlib.h"
#include "variables.h"
#include "bmunit.h" // FACTION_BLUE
#if FE8_CO_POWERS
#include "power.h" // CoGauge_Get, CoScreen_GetCo*Stars
#endif

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

static u8* GetCoMiniTileBase(void)
{
    return (u8*)(VRAM + GetBackgroundTileDataOffset(1) + AW2_COMINI_TILE_BASE * CHR_SIZE);
}

void LoadAw2CoMiniGfx(void)
{
    Decompress(aw2uiCoMini_tiles, GetCoMiniTileBase());
    ApplyPalette(aw2uiCoMini_palette, AW2_COMINI_PAL_ID);
}

/* --- CO gauge stars ------------------------------------------------------
 * Both star sheets hold their three fill states in the same order, so one
 * enum indexes either: aw2uiStars is 3 tiles left-to-right, aw2uiStarsBig
 * is three 2x2-tile stars stacked top-to-bottom. */
enum {
    AW2_STAR_EMPTY = 0,
    AW2_STAR_HALF  = 1,
    AW2_STAR_FULL  = 2,
};

#define AW2_SMALL_STAR_W  1
#define AW2_SMALL_STAR_H  1
#define AW2_BIG_STAR_W    2
#define AW2_BIG_STAR_H    2

/* CO gauge points per star. CoGauge_Get returns raw points (see
 * CO_GAUGE_MAX, src/power.c). */
#define AW2_GAUGE_PER_STAR      50
#define AW2_GAUGE_PER_HALF_STAR (AW2_GAUGE_PER_STAR / 2)

/* Where the gauge sits inside the 64x32 panel and how far apart
 * consecutive stars are, in pixels. The panel's drawn box spans rows 2-18,
 * so both star rows are placed to sit centred inside it (a small star at
 * y=6 and a big one at y=2 share the same midpoint). Pure layout -- tune
 * against the panel art.
 *
 * Mind the width budget when picking a CO's star counts: the gauge needs
 * powerStars*8 + (superPowerStars - powerStars)*16 pixels, and anything
 * that would run past the panel's 64 is dropped by OverlapStarAt rather
 * than wrapping into the next tile row. At AW2_STAR_X=8 that leaves 56px,
 * which is exactly a 3/5 CO -- a 4/6 one would need all 64 and have to
 * start at x=0. */
#define AW2_STAR_X           2
#define AW2_SMALL_STAR_Y     15
#define AW2_BIG_STAR_Y       15
#define AW2_SMALL_STAR_STEP  6
#define AW2_BIG_STAR_STEP   6

/* The player's CO gauge in half-star units, so 3 means one and a half
 * stars are filled. */
int GetStarsPlayer(void)
{
#if FE8_CO_POWERS
    return CoGauge_Get(FACTION_BLUE) / AW2_GAUGE_PER_HALF_STAR;
#else
    return 0;
#endif
}

/* How full the `starIndex`'th star along the gauge is, given how many
 * half-stars are charged: each star swallows two half-steps, so a gauge of
 * 3 leaves star 0 full, star 1 half and everything past it empty. */
static int GetStarFill(int starIndex, int halfStars)
{
    int filled = halfStars - starIndex * 2;

    if (filled >= 2)
        return AW2_STAR_FULL;

    if (filled == 1)
        return AW2_STAR_HALF;

    return AW2_STAR_EMPTY;
}

/* Merges one star, picked out of an already-decompressed sheet, onto the
 * panel's tiles at pixel (px, py) within the panel. */
static void OverlapStarAt(
    const u8* sheet, int fill, int tileWidth, int tileHeight, int px, int py)
{
    const u8* src = sheet + fill * tileWidth * tileHeight * CHR_SIZE;

    /* The panel's tiles are one linear AW2_COMINI_W-wide block (see
     * LoadAw2CoMiniGfx / DrawAw2CoMini), so a star running past its right
     * edge would silently reappear at the start of the row below, and one
     * past the bottom edge would land in whatever unrelated graphics
     * follow the panel in VRAM. Drop it rather than corrupt either. */
    if (px < 0 || py < 0)
        return;

    if (px + tileWidth * 8 > AW2_COMINI_W * 8)
        return;

    if (py + tileHeight * 8 > AW2_COMINI_H * 8)
        return;

    Copy2dChrTransparent(src,
        GetCoMiniTileBase() + ((py / 8) * AW2_COMINI_W + (px / 8)) * CHR_SIZE,
        tileWidth, tileHeight, px & 7, py & 7, AW2_COMINI_W);
}

/* Draws the player's CO gauge onto the panel: one small star per star the
 * CO's normal power costs, then big ones for the extra charge its super
 * needs on top (Francis at 3/5 gives three small then two big), each drawn
 * empty, half or full to match the gauge. */
void OverlapStars(void)
{
#if FE8_CO_POWERS
    u8* smallSheet = gGenericBuffer;
    u8* bigSheet = gGenericBuffer + AW2_STARS_W * AW2_STARS_H * CHR_SIZE;
    int coId = gPlaySt.commanderId[FACTION_BLUE >> 6];
    int powerStars = CoScreen_GetCoPowerStars(coId);
    int superStars = CoScreen_GetCoSuperPowerStars(coId);
    int halfStars = GetStarsPlayer();
    int i, x;

    /* Both sheets at once: they're 3 and 12 tiles against gGenericBuffer's
     * 0x2000 bytes, so each star can just be indexed straight out of them
     * below instead of decompressing again per star. */
    Decompress(aw2uiStars_tiles, smallSheet);
    Decompress(aw2uiStarsBig_tiles, bigSheet);

    x = AW2_STAR_X;

    for (i = 0; i < powerStars; ++i) {
        OverlapStarAt(smallSheet, GetStarFill(i, halfStars),
            AW2_SMALL_STAR_W, AW2_SMALL_STAR_H, x, AW2_SMALL_STAR_Y);

        x += AW2_SMALL_STAR_STEP;
    }
    x -= 3;

    for (; i < superStars; ++i) {
        OverlapStarAt(bigSheet, GetStarFill(i, halfStars),
            AW2_BIG_STAR_W, AW2_BIG_STAR_H, x, AW2_BIG_STAR_Y);

        x += AW2_BIG_STAR_STEP;
    }
#endif
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

    /* After the panel tiles are re-decompressed clean by LoadAw2CoMiniGfx,
     * so the stars are merged onto fresh art rather than onto last frame's
     * stars. */
    OverlapStars();
}

#endif
