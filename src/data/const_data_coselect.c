#include "global.h"

#if FE8_CO_POWERS

/* CO select's own OBJ sprite sheet (src/coSelect.c). Everything else on that
 * screen is shared with Mode Select and lives in const_data_modeselect.c;
 * only this sheet differs, because its sprite labels say "CO"/"Select"
 * rather than "Mode"/"Select".
 *
 * Same shape as ModeSelectObjFrame: 128 tiles (256x32, 32 tiles wide),
 * decompressed to OBJ VRAM at 0x06010000, and authored against OBJ palette
 * 0xB -- which is Pal_084150C0 (graphics/modeselect/ModeSelectChapterPal),
 * already applied by CoSelect_Init. So there is deliberately no palette
 * INCBIN here: the sheet reuses that palette rather than shipping a
 * duplicate of it. The generic %.4bpp / %.lz Makefile rules build it and
 * scaninc picks up the dependency from the INCBIN path below. */
const u8 __attribute__((aligned(4))) Img_CoSelectObjFrame[] = INCBIN_U8("graphics/modeselect/CoSelectObjFrame.4bpp.lz");

#endif // FE8_CO_POWERS
