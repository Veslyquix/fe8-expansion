#include "global.h"

#if FE8_MODE_SELECT || FE8_CO_POWERS

/* FE7 "Mode Select" assets, converted from the installer's dumped
 * Img_, Pal_, and Tsa_ .bin files via scripts/modeselect_bin_to_source.py
 * -- see graphics/modeselect/ for the editable PNG and .pal sources this
 * compiles from (generic %.4bpp, %.gbapal, and %.lz Makefile rules, no
 * special-casing needed). Names here match the FE7 source's own Img_,
 * Pal_, and Tsa_ names for traceability back to the original dump. */

// Outer spinning spell-circle background (BG0) + its own multi-row palette.
const u8 __attribute__((aligned(4))) Img_08418E44[] = INCBIN_U8("graphics/modeselect/ModeSelectBg0.4bpp.lz");
const u16 __attribute__((aligned(4))) Pal_0840F9A0[] = INCBIN_U16("graphics/modeselect/ModeSelectBg0.gbapal");

// Outer spell-circle "claw" frame background (BG3) + its own multi-row palette.
const u8 __attribute__((aligned(4))) Img_0840FEB4[] = INCBIN_U8("graphics/modeselect/ModeSelectBg3.4bpp.lz");
const u16 __attribute__((aligned(4))) Pal_084138F0[] = INCBIN_U16("graphics/modeselect/ModeSelectBg3.gbapal");

// Inner "claw menu" UI frame (BG1) + its 16-colour palette.
const u8 __attribute__((aligned(4))) Img_08415594[] = INCBIN_U8("graphics/modeselect/ModeSelectClawMenu.4bpp.lz");
const u16 __attribute__((aligned(4))) Pal_08415AA0[] = INCBIN_U16("graphics/modeselect/ModeSelectClawMenu.gbapal");

/* OBJ palette 0xA. Shared -- CO select applies it too, even though its own
 * sprite sheet (src/data/const_data_coselect.c) is authored against OBJ
 * palette 0xB. The sheet this palette is named after is Mode Select's own and
 * lives in the MODE_SELECT-only block below. */
const u16 __attribute__((aligned(4))) Pal_0841625C[] = INCBIN_U16("graphics/modeselect/ModeSelectObjFrame.gbapal");

/* The claw menu's own tilemap (BG1) -- LZ77-compressed in the original
 * dump (unlike the other two Tsa_* tables below, which are raw), and
 * decompressed at load time via ModeSelect_Init's own Decompress() call. */
const u8 __attribute__((aligned(4))) Tsa_08415AC0[] = INCBIN_U8("graphics/modeselect/Tsa_08415AC0.bin.lz");

/* BG0/BG3's own tilemaps -- small enough, and applied directly via
 * CallARM_FillTileRect with no decompression step, that vanilla (and this
 * port) simply bakes them in uncompressed. */
const u8 __attribute__((aligned(4))) Tsa_0840FA00[] = INCBIN_U8("graphics/modeselect/Tsa_0840FA00.bin");
const u8 __attribute__((aligned(4))) Tsa_08411F34[] = INCBIN_U8("graphics/modeselect/Tsa_08411F34.bin");

/* The claw menu's inner chapter-select frame tilemap. Replaces the
 * original installer's misaligned/glitched dummy Tsa_084150E0 with
 * Jester's corrected, complete 30x20 tilemap. */
const u8 __attribute__((aligned(4))) Tsa_084150E0_Full[] = INCBIN_U8("graphics/modeselect/Tsa_084150E0_Full.bin");

/* The 12 chapter-range OBJ quadrant icons (4 per lord: top-left/bottom-left/
 * top-right/bottom-right), all sharing one palette (ModeSelectChapterPal,
 * loaded once via ApplyPalette(Pal_084150C0, 0x1B) -- see
 * LoadModeSelectChapterGfx in src/modeselect.c). */
const u16 __attribute__((aligned(4))) Pal_084150C0[] = INCBIN_U16("graphics/modeselect/ModeSelectChapterPal.gbapal");

#if FE8_MODE_SELECT
/* Mode Select only. CO select uses its own OBJ sheet
 * (src/data/const_data_coselect.c) and has no chapter-range display, so
 * neither of these is referenced when MODE_SELECT is off. */
const u8 __attribute__((aligned(4))) Img_08414940[] = INCBIN_U8("graphics/modeselect/ModeSelectObjFrame.4bpp.lz");

const u8 __attribute__((aligned(4))) Img_08415BE8[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter0TopLeft.4bpp.lz");
const u8 __attribute__((aligned(4))) Img_08415CB0[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter0BottomLeft.4bpp.lz");
const u8 __attribute__((aligned(4))) Img_08415DC4[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter0TopRight.4bpp.lz");
const u8 __attribute__((aligned(4))) Img_08415E04[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter0BottomRight.4bpp.lz");

const u8 __attribute__((aligned(4))) Img_08415E54[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter1TopLeft.4bpp.lz");
const u8 __attribute__((aligned(4))) Img_08415F14[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter1BottomLeft.4bpp.lz");
const u8 __attribute__((aligned(4))) Img_08415FF0[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter1TopRight.4bpp.lz");
const u8 __attribute__((aligned(4))) Img_0841601C[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter1BottomRight.4bpp.lz");

const u8 __attribute__((aligned(4))) Img_08416058[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter2TopLeft.4bpp.lz");
const u8 __attribute__((aligned(4))) Img_08416118[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter2BottomLeft.4bpp.lz");
const u8 __attribute__((aligned(4))) Img_084161F4[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter2TopRight.4bpp.lz");
const u8 __attribute__((aligned(4))) Img_08416220[] = INCBIN_U8("graphics/modeselect/ModeSelectChapter2BottomRight.4bpp.lz");
#endif // FE8_MODE_SELECT

#endif // FE8_MODE_SELECT || FE8_CO_POWERS
