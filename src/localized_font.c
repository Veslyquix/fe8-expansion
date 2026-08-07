#include "global.h"

#include "expansion_locale.h"
#include "localized_font.h"

#ifdef FE8_LOCALIZED_FONT_ENABLED

#define LOCALIZED_FONT_JA_GLYPH_COUNT 1848u
#define LOCALIZED_FONT_ZH_HANS_GLYPH_COUNT 2460u
#define LOCALIZED_FONT_BITMAP_STRIDE 64u
#define LOCALIZED_FONT_IDEOGRAPHIC_SPACE 0x3000u
#define LOCALIZED_FONT_IDEOGRAPHIC_SPACE_WIDTH 16u
#define LOCALIZED_FONT_MISSING_COUNT_MAX 0xFFFFu

struct LocalizedFontDescriptor
{
    const u8 *codepoints;
    const u8 *widths;
    const u8 *bitmaps;
    u32 glyphCount;
};

#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x02u) != 0
extern const u8 gLocalizedFontJaSystemCodepoints[];
extern const u8 gLocalizedFontJaSystemWidths[];
extern const u8 gLocalizedFontJaSystemBitmaps[];
extern const u8 gLocalizedFontJaTalkCodepoints[];
extern const u8 gLocalizedFontJaTalkWidths[];
extern const u8 gLocalizedFontJaTalkBitmaps[];
#endif

#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x04u) != 0
extern const u8 gLocalizedFontZhHansSystemCodepoints[];
extern const u8 gLocalizedFontZhHansSystemWidths[];
extern const u8 gLocalizedFontZhHansSystemBitmaps[];
extern const u8 gLocalizedFontZhHansTalkCodepoints[];
extern const u8 gLocalizedFontZhHansTalkWidths[];
extern const u8 gLocalizedFontZhHansTalkBitmaps[];
#endif

static EWRAM_DATA u16 sLocalizedFontMissingGlyphCount;
static EWRAM_DATA u32 sLocalizedFontLastMissingScalar;

static u32 LocalizedFont_ReadScalar(const u8 *data)
{
    return (u32)data[0]
        | ((u32)data[1] << 8)
        | ((u32)data[2] << 16)
        | ((u32)data[3] << 24);
}

static bool8 LocalizedFont_GetDescriptor(
    ExpansionLocaleId locale,
    enum LocalizedFontStyle style,
    struct LocalizedFontDescriptor *out)
{
    if (out == 0)
        return FALSE;

#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x02u) != 0
    if (locale == EXPANSION_LOCALE_JA)
    {
        out->glyphCount = LOCALIZED_FONT_JA_GLYPH_COUNT;
        if (style == LOCALIZED_FONT_STYLE_SYSTEM)
        {
            out->codepoints = gLocalizedFontJaSystemCodepoints;
            out->widths = gLocalizedFontJaSystemWidths;
            out->bitmaps = gLocalizedFontJaSystemBitmaps;
            return TRUE;
        }
        if (style == LOCALIZED_FONT_STYLE_TALK)
        {
            out->codepoints = gLocalizedFontJaTalkCodepoints;
            out->widths = gLocalizedFontJaTalkWidths;
            out->bitmaps = gLocalizedFontJaTalkBitmaps;
            return TRUE;
        }
        return FALSE;
    }
#endif

#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x04u) != 0
    if (locale == EXPANSION_LOCALE_ZH_HANS)
    {
        out->glyphCount = LOCALIZED_FONT_ZH_HANS_GLYPH_COUNT;
        if (style == LOCALIZED_FONT_STYLE_SYSTEM)
        {
            out->codepoints = gLocalizedFontZhHansSystemCodepoints;
            out->widths = gLocalizedFontZhHansSystemWidths;
            out->bitmaps = gLocalizedFontZhHansSystemBitmaps;
            return TRUE;
        }
        if (style == LOCALIZED_FONT_STYLE_TALK)
        {
            out->codepoints = gLocalizedFontZhHansTalkCodepoints;
            out->widths = gLocalizedFontZhHansTalkWidths;
            out->bitmaps = gLocalizedFontZhHansTalkBitmaps;
            return TRUE;
        }
        return FALSE;
    }
#endif

    return FALSE;
}

bool8 LocalizedFont_IsLocale(ExpansionLocaleId locale)
{
#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x02u) != 0
    if (locale == EXPANSION_LOCALE_JA)
        return TRUE;
#endif
#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x04u) != 0
    if (locale == EXPANSION_LOCALE_ZH_HANS)
        return TRUE;
#endif
    return FALSE;
}

bool8 LocalizedFont_Lookup(
    ExpansionLocaleId locale,
    enum LocalizedFontStyle style,
    u32 scalar,
    struct LocalizedFontGlyph *out)
{
    struct LocalizedFontDescriptor descriptor;
    u32 low;
    u32 high;
    u32 middle;
    u32 candidate;

    if (out == 0 || !LocalizedFont_IsLocale(locale))
        return FALSE;

    if (scalar == LOCALIZED_FONT_IDEOGRAPHIC_SPACE)
    {
        out->bitmap = 0;
        out->scalar = scalar;
        out->width = LOCALIZED_FONT_IDEOGRAPHIC_SPACE_WIDTH;
        return TRUE;
    }

    if (scalar < 0x80)
        return FALSE;

    if (!LocalizedFont_GetDescriptor(locale, style, &descriptor))
        return FALSE;

    low = 0;
    high = descriptor.glyphCount;
    while (low < high)
    {
        middle = low + (high - low) / 2;
        candidate = LocalizedFont_ReadScalar(descriptor.codepoints + middle * 4);
        if (candidate < scalar)
            low = middle + 1;
        else
            high = middle;
    }

    if (low >= descriptor.glyphCount)
        return FALSE;
    if (LocalizedFont_ReadScalar(descriptor.codepoints + low * 4) != scalar)
        return FALSE;

    out->bitmap = descriptor.bitmaps + low * LOCALIZED_FONT_BITMAP_STRIDE;
    out->scalar = scalar;
    out->width = descriptor.widths[low];
    return TRUE;
}

void LocalizedFont_RecordMissing(u32 scalar)
{
    if (sLocalizedFontMissingGlyphCount < LOCALIZED_FONT_MISSING_COUNT_MAX)
        sLocalizedFontMissingGlyphCount++;
    sLocalizedFontLastMissingScalar = scalar;
}

void LocalizedFont_ResetDiagnostics(void)
{
    sLocalizedFontMissingGlyphCount = 0;
    sLocalizedFontLastMissingScalar = 0;
}

u16 LocalizedFont_GetMissingGlyphCount(void)
{
    return sLocalizedFontMissingGlyphCount;
}

u32 LocalizedFont_GetLastMissingScalar(void)
{
    return sLocalizedFontLastMissingScalar;
}

#endif /* FE8_LOCALIZED_FONT_ENABLED */
