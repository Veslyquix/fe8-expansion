#include "global.h"

#if FE8_AW2_ASSETS

#include "aw2_gfx.h"
#include "hardware.h"
#include "bmlib.h"
#include "variables.h"
#include "bmunit.h" // FACTION_BLUE
#include "ctc.h" // PutSprite, gObject_32x8/16x8, OAM2_CHR/OAM2_PAL
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

/* --- CO power/super power intro banner (src/power.c) ----------------------
 * Reuses the power/super OBJ tile slot LoadAw2Gfx above reserves (nothing
 * calls LoadAw2Gfx, so it's otherwise sitting unused) -- only one of power
 * or super is ever shown at a time, so both just decompress into the same
 * slot(s) and share AW2_POWER_PAL_ID.
 *
 * Drawn at 4x native size via an affine OBJ, which needs GBA's "double
 * size" affine mode to avoid the hardware clipping the scaled-up image to
 * its unscaled bounding box -- double size doubles that box relative to
 * the sprite's OWN shape, so the shape has to be big enough that doubling
 * it comfortably covers the 4x content, and any of that shape's tiles
 * past the real graphic have to be blanked (zeroed = transparent) rather
 * than showing whatever else happens to be sitting in that VRAM range.
 *
 * OBJ character VRAM defaults to 2D mapping in this engine (obj1dMap is 0
 * everywhere except a couple of screens that switch to it temporarily and
 * switch back -- see src/opanim-main.c), which means a shape more than
 * one tile TALL doesn't read its rows out of a linear block: row N of a
 * W-tile-wide shape lives at (base + N * 0x20) tiles, 0x20 being a fixed
 * VRAM tile-ROW's width regardless of the shape's own W (same stride
 * Copy2dChr, src/bmlib.c, advances by per source row). ClearAw2BannerSlot
 * below zeroes each row at its own strided address for exactly this
 * reason -- a single linear fill only zeroed row 0 correctly and left
 * rows 1+ (for slot A's 4-tall shape) pointing at whatever else was
 * already sitting 0x20/0x40/0x60 tiles later.
 *
 * SUPER's 48x8 doesn't match any single OBJ shape (GBA sizes only go up to
 * 64x64 in powers-of-two-ish steps -- 8/16/32/64) even before scaling, so
 * -- same as the native-size version before this -- it's split into two:
 * a 32x8-native-sized left half (the graphic's first 4 tiles) in slot A,
 * and a 16x8-native-sized right half (the last 2 tiles) in slot B, placed
 * side by side. POWER only ever uses slot A. Slot B sits far enough past
 * slot A (0x200, vs. slot A's last row at 0x180 + 3*0x20 = 0x1E0) that
 * none of slot A's four 2D-mapped rows land inside it. */
#define AW2_POWER_BANNER_TILE_ROW_STRIDE 0x20 // one VRAM tile-row in 2D OBJ mapping

#define AW2_POWER_BANNER_SLOTA_TILE_DECOMPRESS 0x1a2 // (AW2_VRAM_BASE - OBJ_VRAM_BASE) / CHR_SIZE
#define AW2_POWER_BANNER_SLOTA_TILE 0x180 // (AW2_VRAM_BASE - OBJ_VRAM_BASE) / CHR_SIZE
#define AW2_POWER_BANNER_SLOTA_TILE_W 8 // 64x32 shape: doubles to a 128x64 box,
#define AW2_POWER_BANNER_SLOTA_TILE_H 4 // comfortably covering 128x32 (32x8 native x4)

#define AW2_POWER_BANNER_SLOTB_TILE 0x200
#define AW2_POWER_BANNER_SLOTB_TILE_DECOMPRESS 0x222
#define AW2_POWER_BANNER_SLOTB_TILE_W 8 // 32x16 shape: doubles to exactly 64x32,
#define AW2_POWER_BANNER_SLOTB_TILE_H 4 // matching 64x32 (16x8 native x4) with no slack

#define AW2_POWER_BANNER_SCALE 0x400 // SetObjAffineAuto units, 0x100 == 1x (see include/ctc.h)

static u16 CONST_DATA sAw2PowerBannerObjectA[] = {
    // 1, OAM0_SHAPE_64x32 + OAM0_AFFINE_ENABLE + OAM0_DOUBLESIZE, OAM1_SIZE_64x32, 0,
    1, OAM0_SHAPE_16x8 + OAM0_AFFINE_ENABLE + OAM0_DOUBLESIZE, OAM1_SIZE_64x32, 0,
};
static u16 CONST_DATA sAw2PowerBannerObjectB[] = {
    1, OAM0_SHAPE_16x8 + OAM0_AFFINE_ENABLE + OAM0_DOUBLESIZE, OAM1_SIZE_64x32, 0,
};

/* Zeroes a tileW x tileH OBJ shape's worth of VRAM, one 2D-mapped row at a
 * time -- see the big comment above for why a single linear fill across
 * the whole shape is wrong for anything more than 1 tile tall. */
static void ClearAw2BannerSlot(int baseTile, int tileW, int tileH)
{
    int row;

    for (row = 0; row < tileH; ++row)
        CpuFastFill(0, OBJ_CHR_ADDR(baseTile + row * AW2_POWER_BANNER_TILE_ROW_STRIDE), tileW * CHR_SIZE);
}

void LoadAw2PowerBannerGfx(bool8 isSuper)
{
    ClearAw2BannerSlot(AW2_POWER_BANNER_SLOTA_TILE,
        AW2_POWER_BANNER_SLOTA_TILE_W, AW2_POWER_BANNER_SLOTA_TILE_H);

    if (isSuper) {
        ClearAw2BannerSlot(AW2_POWER_BANNER_SLOTB_TILE,
            AW2_POWER_BANNER_SLOTB_TILE_W, AW2_POWER_BANNER_SLOTB_TILE_H);

        /* super_tiles compresses all 6 tiles as one 6x1 image, but the two
         * halves now live in separately-padded slots -- decompress once
         * into the scratch buffer, then split it into the real slots.
         * Both halves are a single tile tall, so this linear copy (unlike
         * the zeroing above) is fine: it lands entirely within each
         * slot's own row 0. */
        Decompress(super_tiles, gGenericBuffer);
        CpuFastCopy(gGenericBuffer, OBJ_CHR_ADDR(AW2_POWER_BANNER_SLOTA_TILE_DECOMPRESS), 4 * CHR_SIZE);
        CpuFastCopy((u8*)gGenericBuffer + 4 * CHR_SIZE,
            OBJ_CHR_ADDR(AW2_POWER_BANNER_SLOTB_TILE_DECOMPRESS), 2 * CHR_SIZE);
        ApplyPalette(super_palette, AW2_POWER_PAL_ID);
    } else {
        Decompress(power_tiles, OBJ_CHR_ADDR(AW2_POWER_BANNER_SLOTA_TILE_DECOMPRESS));
        ApplyPalette(power_palette, AW2_POWER_PAL_ID);
    }
}

void DrawAw2PowerBannerSprite(bool8 isSuper)
{
    /* Content height is 32 (8px native x4) either way; slot A's double-size
     * box is 64 tall (32x8 native shape, doubled), so its OAM y needs
     * pulling up by the 16px of letterboxing above the visible content --
     * slot B's box matches its content exactly, no adjustment needed. */
    int y = (DISPLAY_HEIGHT - 8 * 4) / 2 + 4;

    SetObjAffineAuto(0, 0, AW2_POWER_BANNER_SCALE, AW2_POWER_BANNER_SCALE);

    if (isSuper) {
        int totalW = AW2_SUPER_W * 8 * 4;
        int x = (DISPLAY_WIDTH - totalW) / 2 + 16;

        PutSprite(2, x, y, sAw2PowerBannerObjectA,
            OAM2_CHR(AW2_POWER_BANNER_SLOTA_TILE) | OAM2_PAL(AW2_POWER_PAL_ID));
        PutSprite(2, x + AW2_POWER_W * 8 * 4, y, sAw2PowerBannerObjectB,
            OAM2_CHR(AW2_POWER_BANNER_SLOTB_TILE) | OAM2_PAL(AW2_POWER_PAL_ID));
    } else {
        int x = (DISPLAY_WIDTH - AW2_POWER_W * 8 * 4) / 2;

        PutSprite(2, x, y, sAw2PowerBannerObjectA,
            OAM2_CHR(AW2_POWER_BANNER_SLOTA_TILE) | OAM2_PAL(AW2_POWER_PAL_ID));
    }
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
/* AW2_COMINI_PAL_ID itself lives in include/aw2_gfx.h now -- src/player_
 * interface.c's palette-cycle call needs it too. */

static u8* GetCoMiniTileBase(void)
{
    return (u8*)(VRAM + GetBackgroundTileDataOffset(1) + AW2_COMINI_TILE_BASE * CHR_SIZE);
}

void LoadAw2CoMiniGfx(void)
{
    Decompress(aw2uiCoMini_tiles, GetCoMiniTileBase());
    ApplyPalette(aw2uiCoMini_palette, AW2_COMINI_PAL_ID);
}

/* Cycles the panel's color 11 through this exact 14-entry table, one step
 * every 2 frames (28-frame loop) -- called once a frame from
 * GoalDisplay_Loop_Display. Traced directly from the source rather than
 * approximated: it isn't a clean fade between a few named colors (blue
 * ramps up first while red/green hold, then green pulls back down while
 * blue holds, then blue drops out while green climbs back to yellow), so
 * there's no shorter formula to reconstruct it from -- this table is the
 * actual behavior. RGB(r, g, b) (include/gba/defines.h) packs a color the
 * same way the source art's own palette is already stored. As with any
 * other gPaletteBuffer write, this only takes effect once
 * EnablePaletteSync has flagged it for the next VBlank copy
 * (SetBackdropColor, include/hardware.h, is the one-line version of that
 * same pattern for the backdrop color). */
#define AW2_COMINI_CYCLE_COLOR 11
#define AW2_COMINI_CYCLE_STEP_FRAMES 2

static const u16 sAw2CominiCycleColors[] = {
    RGB(0x1F, 0x1F, 0x03),
    RGB(0x1F, 0x1F, 0x08),
    RGB(0x1F, 0x1F, 0x0D),
    RGB(0x1F, 0x1F, 0x11),
    RGB(0x1F, 0x1F, 0x16),
    RGB(0x1F, 0x1D, 0x1A),
    RGB(0x1F, 0x1B, 0x16),
    RGB(0x1F, 0x19, 0x11),
    RGB(0x1F, 0x14, 0x08),
    RGB(0x1F, 0x10, 0x00),
    RGB(0x1F, 0x13, 0x00),
    RGB(0x1F, 0x16, 0x00),
    RGB(0x1F, 0x1B, 0x00),
    RGB(0x1F, 0x1F, 0x00),
};
#define AW2_COMINI_CYCLE_FRAMES \
    (ARRAY_COUNT(sAw2CominiCycleColors) * AW2_COMINI_CYCLE_STEP_FRAMES)

void UpdateAw2CoMiniPaletteCycle(void)
{
    static u8 sTimer = 0;

    PAL_BG_COLOR(AW2_COMINI_PAL_ID, AW2_COMINI_CYCLE_COLOR) =
        sAw2CominiCycleColors[sTimer / AW2_COMINI_CYCLE_STEP_FRAMES];
    EnablePaletteSync();

    sTimer = (sTimer + 1) % AW2_COMINI_CYCLE_FRAMES;
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

/* CO gauge points per star (include/power.h's CO_GAUGE_PER_STAR --
 * CoGauge_Get returns raw points, see CO_GAUGE_MAX, src/power.c). */
#define AW2_GAUGE_PER_HALF_STAR (CO_GAUGE_PER_STAR / 2)

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

/* The currently active phase's faction (gPlaySt.faction -- FACTION_BLUE
 * during the player's own turn, FACTION_RED/GREEN during an AI-controlled
 * one) CO gauge in half-star units, so 3 means one and a half stars are
 * filled. */
int GetActiveFactionStars(void)
{
#if FE8_CO_POWERS
    return CoGauge_Get(gPlaySt.faction) / AW2_GAUGE_PER_HALF_STAR;
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

/* Draws the active phase faction's CO gauge onto the panel: one small star
 * per star the CO's normal power costs, then big ones for the extra charge
 * its super needs on top (Francis at 3/5 gives three small then two big),
 * each drawn empty, half or full to match the gauge. */
void OverlapStars(void)
{
#if FE8_CO_POWERS
    u8* smallSheet = gGenericBuffer;
    u8* bigSheet = gGenericBuffer + AW2_STARS_W * AW2_STARS_H * CHR_SIZE;
    int coId = gPlaySt.commanderId[gPlaySt.faction >> 6];
    int powerStars = CoScreen_GetCoPowerStars(coId);
    int superStars = CoScreen_GetCoSuperPowerStars(coId);
    int halfStars = GetActiveFactionStars();
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
