#ifndef GUARD_LOCALIZED_FONT_H
#define GUARD_LOCALIZED_FONT_H

/*
 * Compact CJK font lookup for modern profiles that explicitly enable ja or
 * zh-Hans. Include global.h before this header.
 */
#if defined(MODERN) && ((FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x06u) != 0)

#define FE8_LOCALIZED_FONT_ENABLED 1

#include "expansion_locale.h"

enum LocalizedFontStyle
{
    LOCALIZED_FONT_STYLE_SYSTEM = 0,
    LOCALIZED_FONT_STYLE_TALK = 1
};

struct LocalizedFontGlyph
{
    const u8 *bitmap;
    u32 scalar;
    u8 width;
};

bool8 LocalizedFont_IsLocale(ExpansionLocaleId locale);

/*
 * Returns TRUE for an embedded glyph or the explicit U+3000 spacing glyph.
 * Spacing glyphs have a NULL bitmap and a nonzero width. ASCII intentionally
 * returns FALSE because it remains owned by the existing engine font.
 */
bool8 LocalizedFont_Lookup(
    ExpansionLocaleId locale,
    enum LocalizedFontStyle style,
    u32 scalar,
    struct LocalizedFontGlyph *out);

/*
 * The renderer calls this when it visibly substitutes '?'. The counter
 * saturates rather than wrapping so a malformed string cannot erase evidence.
 */
void LocalizedFont_RecordMissing(u32 scalar);
void LocalizedFont_ResetDiagnostics(void);
u16 LocalizedFont_GetMissingGlyphCount(void);
u32 LocalizedFont_GetLastMissingScalar(void);

#endif /* modern build with a CJK locale */

#endif /* GUARD_LOCALIZED_FONT_H */
