#include "global.h"

#include "text_utf8.h"

#ifdef FE8_TEXT_UTF8_ENABLED

static void TextUtf8_SetToken(
    struct TextUtf8Token *out,
    enum TextUtf8TokenKind kind,
    u32 scalar,
    u8 length,
    u8 control,
    u8 payload)
{
    out->kind = kind;
    out->scalar = scalar;
    out->length = length;
    out->control = control;
    out->payload = payload;
}

static const char *TextUtf8_Invalid(const char *text, struct TextUtf8Token *out)
{
    TextUtf8_SetToken(out, TEXT_UTF8_TOKEN_INVALID, 0, 1, 0, 0);
    return text + 1;
}

const char *TextUtf8_Next(const char *text, struct TextUtf8Token *out)
{
    const u8 *bytes;
    u32 scalar;
    u8 first;
    u8 second;
    u8 third;
    u8 fourth;

    if (out == 0)
        return text;

    if (text == 0)
    {
        TextUtf8_SetToken(out, TEXT_UTF8_TOKEN_END, 0, 0, 0, 0);
        return 0;
    }

    bytes = (const u8 *)text;
    first = bytes[0];

    if (first == 0)
    {
        TextUtf8_SetToken(out, TEXT_UTF8_TOKEN_END, 0, 0, 0, 0);
        return text;
    }

    if (first < 0x20)
    {
        TextUtf8_SetToken(out, TEXT_UTF8_TOKEN_CONTROL, 0, 1, first, 0);
        return text + 1;
    }

    if (first < 0x80)
    {
        TextUtf8_SetToken(out, TEXT_UTF8_TOKEN_SCALAR, first, 1, 0, 0);
        return text + 1;
    }

    if (first == 0x80)
    {
        if (bytes[1] == 0)
            return TextUtf8_Invalid(text, out);

        TextUtf8_SetToken(
            out, TEXT_UTF8_TOKEN_EXTENDED_CONTROL, 0, 2, first, bytes[1]);
        return text + 2;
    }

    second = bytes[1];

    if (first >= 0xC2 && first <= 0xDF)
    {
        if (second < 0x80 || second > 0xBF)
            return TextUtf8_Invalid(text, out);

        scalar = ((u32)(first & 0x1F) << 6) | (second & 0x3F);
        TextUtf8_SetToken(out, TEXT_UTF8_TOKEN_SCALAR, scalar, 2, 0, 0);
        return text + 2;
    }

    if (first >= 0xE0 && first <= 0xEF)
    {
        if (second == 0)
            return TextUtf8_Invalid(text, out);

        third = bytes[2];
        if (third == 0)
            return TextUtf8_Invalid(text, out);

        if (second < 0x80 || second > 0xBF || third < 0x80 || third > 0xBF)
            return TextUtf8_Invalid(text, out);
        if (first == 0xE0 && second < 0xA0)
            return TextUtf8_Invalid(text, out);
        if (first == 0xED && second >= 0xA0)
            return TextUtf8_Invalid(text, out);

        scalar = ((u32)(first & 0x0F) << 12)
            | ((u32)(second & 0x3F) << 6)
            | (third & 0x3F);
        TextUtf8_SetToken(out, TEXT_UTF8_TOKEN_SCALAR, scalar, 3, 0, 0);
        return text + 3;
    }

    if (first >= 0xF0 && first <= 0xF4)
    {
        if (second == 0)
            return TextUtf8_Invalid(text, out);

        third = bytes[2];
        if (third == 0)
            return TextUtf8_Invalid(text, out);

        fourth = bytes[3];
        if (fourth == 0)
            return TextUtf8_Invalid(text, out);

        if (second < 0x80 || second > 0xBF
            || third < 0x80 || third > 0xBF
            || fourth < 0x80 || fourth > 0xBF)
            return TextUtf8_Invalid(text, out);
        if (first == 0xF0 && second < 0x90)
            return TextUtf8_Invalid(text, out);
        if (first == 0xF4 && second > 0x8F)
            return TextUtf8_Invalid(text, out);

        scalar = ((u32)(first & 0x07) << 18)
            | ((u32)(second & 0x3F) << 12)
            | ((u32)(third & 0x3F) << 6)
            | (fourth & 0x3F);
        TextUtf8_SetToken(out, TEXT_UTF8_TOKEN_SCALAR, scalar, 4, 0, 0);
        return text + 4;
    }

    return TextUtf8_Invalid(text, out);
}

#endif /* FE8_TEXT_UTF8_ENABLED */
