#include "global.h"

#include <stdio.h>
#include <string.h>

#include "localized_font.h"
#include "text_utf8.h"

#define GUARD_VALUE 0xA5
#define FALLBACK_WIDTH 7

static int CheckToken(
    const u8 *bytes,
    enum TextUtf8TokenKind kind,
    u32 scalar,
    u8 length,
    u8 control,
    u8 payload)
{
    struct TextUtf8Token token;
    const char *next;

    next = TextUtf8_Next((const char *)bytes, &token);
    return token.kind == kind
        && token.scalar == scalar
        && token.length == length
        && token.control == control
        && token.payload == payload
        && next == (const char *)bytes + length;
}

static int CheckInvalid(const u8 *bytes)
{
    return CheckToken(bytes, TEXT_UTF8_TOKEN_INVALID, 0, 1, 0, 0);
}

static int TestValidUtf8AndControls(void)
{
    static const u8 ascii[] = {'A', 0};
    static const u8 twoByte[] = {0xC2, 0x80, 0};
    static const u8 threeByte[] = {0xE8, 0xA8, 0xBA, 0};
    static const u8 fourByte[] = {0xF0, 0x9F, 0x98, 0x80, 0};
    static const u8 control[] = {0x10, 0x02, 0};
    static const u8 extended[] = {0x80, 0x21, 0};
    static const u8 collision[] = {0xC2, 0x80, 0x80, 0x21, 0};
    struct TextUtf8Token token;
    const char *next;

    if (!CheckToken(ascii, TEXT_UTF8_TOKEN_SCALAR, 'A', 1, 0, 0))
        return 0;
    if (!CheckToken(twoByte, TEXT_UTF8_TOKEN_SCALAR, 0x80, 2, 0, 0))
        return 0;
    if (!CheckToken(threeByte, TEXT_UTF8_TOKEN_SCALAR, 0x8A3A, 3, 0, 0))
        return 0;
    if (!CheckToken(fourByte, TEXT_UTF8_TOKEN_SCALAR, 0x1F600, 4, 0, 0))
        return 0;
    if (!CheckToken(control, TEXT_UTF8_TOKEN_CONTROL, 0, 1, 0x10, 0))
        return 0;
    if (!CheckToken(extended, TEXT_UTF8_TOKEN_EXTENDED_CONTROL, 0, 2, 0x80, 0x21))
        return 0;

    next = TextUtf8_Next((const char *)collision, &token);
    if (token.kind != TEXT_UTF8_TOKEN_SCALAR || token.scalar != 0x80)
        return 0;
    if (next != (const char *)collision + 2)
        return 0;
    next = TextUtf8_Next(next, &token);
    if (token.kind != TEXT_UTF8_TOKEN_EXTENDED_CONTROL || token.payload != 0x21)
        return 0;
    if (next != (const char *)collision + 4)
        return 0;

    next = TextUtf8_Next((const char *)collision + 4, &token);
    return token.kind == TEXT_UTF8_TOKEN_END
        && token.length == 0
        && next == (const char *)collision + 4;
}

static int TestMalformedUtf8(void)
{
    static const u8 strayContinuation[] = {0x81, 0};
    static const u8 overlongTwo[] = {0xC0, 0x80, 0};
    static const u8 overlongThree[] = {0xE0, 0x80, 0x80, 0};
    static const u8 overlongFour[] = {0xF0, 0x80, 0x80, 0x80, 0};
    static const u8 badTwo[] = {0xC2, 'A', 0};
    static const u8 badThree[] = {0xE1, 0x80, 'A', 0};
    static const u8 badFour[] = {0xF1, 0x80, 0x80, 'A', 0};
    static const u8 surrogate[] = {0xED, 0xA0, 0x80, 0};
    static const u8 aboveMaximum[] = {0xF4, 0x90, 0x80, 0x80, 0};
    static const u8 invalidLead[] = {0xF5, 0x80, 0x80, 0x80, 0};
    static const u8 truncatedTwo[] = {0xC2, 0};
    static const u8 truncatedThree[] = {0xE1, 0x80, 0};
    static const u8 truncatedFour[] = {0xF1, 0x80, 0x80, 0};
    static const u8 truncatedExtended[] = {0x80, 0};

    return CheckInvalid(strayContinuation)
        && CheckInvalid(overlongTwo)
        && CheckInvalid(overlongThree)
        && CheckInvalid(overlongFour)
        && CheckInvalid(badTwo)
        && CheckInvalid(badThree)
        && CheckInvalid(badFour)
        && CheckInvalid(surrogate)
        && CheckInvalid(aboveMaximum)
        && CheckInvalid(invalidLead)
        && CheckInvalid(truncatedTwo)
        && CheckInvalid(truncatedThree)
        && CheckInvalid(truncatedFour)
        && CheckInvalid(truncatedExtended);
}

static int BitmapIsVisible(const u8 *bitmap)
{
    int i;

    for (i = 0; i < 64; i++)
    {
        if (bitmap[i] != 0)
            return 1;
    }
    return 0;
}

static int TestGlyphAnchorsAndStyles(void)
{
    struct LocalizedFontGlyph jaSystemCandidate;
    struct LocalizedFontGlyph jaTalkCandidate;
    struct LocalizedFontGlyph jaSystemDiagnosis;
    struct LocalizedFontGlyph zhSystemCandidate;
    struct LocalizedFontGlyph zhTalkCandidate;
    struct LocalizedFontGlyph zhSystemDiagnosis;
    struct LocalizedFontGlyph spacing;

    if (!LocalizedFont_Lookup(
            EXPANSION_LOCALE_JA, LOCALIZED_FONT_STYLE_SYSTEM, 0x5019,
            &jaSystemCandidate))
        return 0;
    if (!LocalizedFont_Lookup(
            EXPANSION_LOCALE_JA, LOCALIZED_FONT_STYLE_TALK, 0x5019,
            &jaTalkCandidate))
        return 0;
    if (!LocalizedFont_Lookup(
            EXPANSION_LOCALE_JA, LOCALIZED_FONT_STYLE_SYSTEM, 0x8A3A,
            &jaSystemDiagnosis))
        return 0;
    if (!LocalizedFont_Lookup(
            EXPANSION_LOCALE_ZH_HANS, LOCALIZED_FONT_STYLE_SYSTEM, 0x5019,
            &zhSystemCandidate))
        return 0;
    if (!LocalizedFont_Lookup(
            EXPANSION_LOCALE_ZH_HANS, LOCALIZED_FONT_STYLE_TALK, 0x5019,
            &zhTalkCandidate))
        return 0;
    if (!LocalizedFont_Lookup(
            EXPANSION_LOCALE_ZH_HANS, LOCALIZED_FONT_STYLE_SYSTEM, 0x8BCA,
            &zhSystemDiagnosis))
        return 0;

    if (jaSystemCandidate.width != 11 || jaTalkCandidate.width != 9)
        return 0;
    if (jaSystemDiagnosis.width != 11)
        return 0;
    if (zhSystemCandidate.width != 10 || zhTalkCandidate.width != 8)
        return 0;
    if (zhSystemDiagnosis.width != 11)
        return 0;
    if (!BitmapIsVisible(jaSystemDiagnosis.bitmap)
        || !BitmapIsVisible(zhSystemDiagnosis.bitmap))
        return 0;
    if (jaSystemCandidate.bitmap == jaTalkCandidate.bitmap)
        return 0;
    if (zhSystemCandidate.bitmap == zhTalkCandidate.bitmap)
        return 0;
    if (memcmp(jaSystemCandidate.bitmap, jaTalkCandidate.bitmap, 64) == 0)
        return 0;
    if (memcmp(zhSystemCandidate.bitmap, zhTalkCandidate.bitmap, 64) == 0)
        return 0;

    if (!LocalizedFont_Lookup(
            EXPANSION_LOCALE_JA, LOCALIZED_FONT_STYLE_SYSTEM, 0x3000, &spacing))
        return 0;
    if (spacing.width != 16 || spacing.bitmap != NULL)
        return 0;
    if (!LocalizedFont_Lookup(
            EXPANSION_LOCALE_ZH_HANS, LOCALIZED_FONT_STYLE_TALK, 0x3000, &spacing))
        return 0;
    return spacing.width == 16 && spacing.bitmap == NULL;
}

static u32 Measure(
    ExpansionLocaleId locale,
    enum LocalizedFontStyle style,
    const u8 *text)
{
    struct TextUtf8Token token;
    struct LocalizedFontGlyph glyph;
    const char *cursor;
    const char *next;
    u32 width;

    cursor = (const char *)text;
    width = 0;
    for (;;)
    {
        next = TextUtf8_Next(cursor, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
            break;
        if (token.kind == TEXT_UTF8_TOKEN_CONTROL)
        {
            if (token.control == 1)
                break;
            cursor = next;
            continue;
        }
        if (token.kind == TEXT_UTF8_TOKEN_EXTENDED_CONTROL)
        {
            cursor = next;
            continue;
        }
        if (token.kind == TEXT_UTF8_TOKEN_INVALID)
        {
            LocalizedFont_RecordMissing(0xFFFD);
            width += FALLBACK_WIDTH;
            cursor = next;
            continue;
        }
        if (token.scalar < 0x80)
            width += 8;
        else if (LocalizedFont_Lookup(locale, style, token.scalar, &glyph))
            width += glyph.width;
        else
        {
            LocalizedFont_RecordMissing(token.scalar);
            width += FALLBACK_WIDTH;
        }
        cursor = next;
    }
    return width;
}

static int TestWidthFallbackAndGuards(void)
{
    static const u8 jaText[] = {
        'A', 0xE5, 0x80, 0x99, 0x80, 0x21, 0xE8, 0xA8, 0xBA, 0
    };
    static const u8 zhText[] = {
        0xE5, 0x80, 0x99, 0xE8, 0xAF, 0x8A, 0xE3, 0x80, 0x80, 0
    };
    static const u8 missingText[] = {0xF4, 0x8F, 0xBF, 0xBF, 0};
    static const u8 invalidText[] = {0xC2, 0};
    struct LocalizedFontGlyph glyph;
    u8 storage[66];
    int i;

    LocalizedFont_ResetDiagnostics();
    if (Measure(
            EXPANSION_LOCALE_JA, LOCALIZED_FONT_STYLE_SYSTEM, jaText) != 30)
        return 0;
    if (Measure(
            EXPANSION_LOCALE_ZH_HANS, LOCALIZED_FONT_STYLE_TALK, zhText) != 32)
        return 0;
    if (Measure(
            EXPANSION_LOCALE_JA, LOCALIZED_FONT_STYLE_SYSTEM, missingText)
        != FALLBACK_WIDTH)
        return 0;
    if (LocalizedFont_GetMissingGlyphCount() != 1)
        return 0;
    if (LocalizedFont_GetLastMissingScalar() != 0x10FFFF)
        return 0;
    if (Measure(
            EXPANSION_LOCALE_JA, LOCALIZED_FONT_STYLE_SYSTEM, invalidText)
        != FALLBACK_WIDTH)
        return 0;
    if (LocalizedFont_GetMissingGlyphCount() != 2)
        return 0;
    if (LocalizedFont_GetLastMissingScalar() != 0xFFFD)
        return 0;

    if (!LocalizedFont_Lookup(
            EXPANSION_LOCALE_JA, LOCALIZED_FONT_STYLE_SYSTEM, 0x8A3A, &glyph))
        return 0;
    memset(storage, GUARD_VALUE, sizeof(storage));
    memcpy(storage + 1, glyph.bitmap, 64);
    if (storage[0] != GUARD_VALUE || storage[65] != GUARD_VALUE)
        return 0;
    for (i = 0; i < 64; i++)
    {
        if (storage[i + 1] != glyph.bitmap[i])
            return 0;
    }

    for (i = 0; i < 70000; i++)
        LocalizedFont_RecordMissing((u32)i);
    return LocalizedFont_GetMissingGlyphCount() == 0xFFFF
        && LocalizedFont_GetLastMissingScalar() == 69999u;
}

int main(void)
{
    if (!TestValidUtf8AndControls())
        return 1;
    if (!TestMalformedUtf8())
        return 2;
    if (!TestGlyphAnchorsAndStyles())
        return 3;
    if (!TestWidthFallbackAndGuards())
        return 4;

    puts("text_renderer_host_test: ok");
    return 0;
}
