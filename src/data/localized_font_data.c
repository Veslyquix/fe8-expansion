#include "global.h"

#if defined(MODERN) && ((FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x02u) != 0)

const u8 gLocalizedFontJaSystemCodepoints[]
    SECTION(".locale_data.font.ja.system.codepoints") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/ja.system.codepoints.u32le");
const u8 gLocalizedFontJaSystemWidths[]
    SECTION(".locale_data.font.ja.system.widths") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/ja.system.widths.u8");
const u8 gLocalizedFontJaSystemBitmaps[]
    SECTION(".locale_data.font.ja.system.bitmaps") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/ja.system.glyphs.2bpp");

const u8 gLocalizedFontJaTalkCodepoints[]
    SECTION(".locale_data.font.ja.talk.codepoints") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/ja.talk.codepoints.u32le");
const u8 gLocalizedFontJaTalkWidths[]
    SECTION(".locale_data.font.ja.talk.widths") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/ja.talk.widths.u8");
const u8 gLocalizedFontJaTalkBitmaps[]
    SECTION(".locale_data.font.ja.talk.bitmaps") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/ja.talk.glyphs.2bpp");

#endif

#if defined(MODERN) && ((FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x04u) != 0)

const u8 gLocalizedFontZhHansSystemCodepoints[]
    SECTION(".locale_data.font.zh_hans.system.codepoints") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/zh-Hans.system.codepoints.u32le");
const u8 gLocalizedFontZhHansSystemWidths[]
    SECTION(".locale_data.font.zh_hans.system.widths") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/zh-Hans.system.widths.u8");
const u8 gLocalizedFontZhHansSystemBitmaps[]
    SECTION(".locale_data.font.zh_hans.system.bitmaps") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/zh-Hans.system.glyphs.2bpp");

const u8 gLocalizedFontZhHansTalkCodepoints[]
    SECTION(".locale_data.font.zh_hans.talk.codepoints") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/zh-Hans.talk.codepoints.u32le");
const u8 gLocalizedFontZhHansTalkWidths[]
    SECTION(".locale_data.font.zh_hans.talk.widths") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/zh-Hans.talk.widths.u8");
const u8 gLocalizedFontZhHansTalkBitmaps[]
    SECTION(".locale_data.font.zh_hans.talk.bitmaps") __attribute__((aligned(4))) =
    INCBIN_U8("graphics/fonts/cjk/zh-Hans.talk.glyphs.2bpp");

#endif
