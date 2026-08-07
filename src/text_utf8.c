#include "global.h"

#include "text_utf8.h"

#ifdef FE8_TEXT_UTF8_ENABLED

static void TextUtf8_SetToken(
    struct TextUtf8Token *out,
    enum TextUtf8TokenKind kind,
    u32 scalar,
    u16 argument,
    u8 length,
    u8 control,
    u8 payload,
    u8 flags)
{
    out->kind = kind;
    out->scalar = scalar;
    out->argument = argument;
    out->length = length;
    out->control = control;
    out->payload = payload;
    out->flags = flags;
}

static const char *TextUtf8_Invalid(
    const char *text,
    struct TextUtf8Token *out,
    u8 flags)
{
    TextUtf8_SetToken(
        out, TEXT_UTF8_TOKEN_INVALID, 0, 0, 1, 0, 0, flags);
    return text + 1;
}

static const char *TextUtf8_NextInternal(
    const char *text,
    u32 available,
    int bounded,
    struct TextUtf8Token *out)
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
        TextUtf8_SetToken(
            out, TEXT_UTF8_TOKEN_END, 0, 0, 0, 0, 0,
            TEXT_UTF8_TOKEN_FLAG_NONE);
        return 0;
    }

    if (bounded && available == 0)
    {
        TextUtf8_SetToken(
            out, TEXT_UTF8_TOKEN_INVALID, 0, 0, 0, 0, 0,
            TEXT_UTF8_TOKEN_FLAG_TRUNCATED);
        return text;
    }

    bytes = (const u8 *)text;
    first = bytes[0];

    if (first == 0)
    {
        TextUtf8_SetToken(
            out, TEXT_UTF8_TOKEN_END, 0, 0, 0, 0, 0,
            TEXT_UTF8_TOKEN_FLAG_NONE);
        return text;
    }

    if (first < 0x20)
    {
        if (first == 0x10)
        {
            if (bounded && available < 3)
                return TextUtf8_Invalid(
                    text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);

            TextUtf8_SetToken(
                out,
                TEXT_UTF8_TOKEN_CONTROL,
                0,
                (u16)bytes[1] | ((u16)bytes[2] << 8),
                3,
                first,
                0,
                TEXT_UTF8_TOKEN_FLAG_FACE_PAYLOAD);
            return text + 3;
        }

        TextUtf8_SetToken(
            out, TEXT_UTF8_TOKEN_CONTROL, 0, 0, 1, first, 0,
            TEXT_UTF8_TOKEN_FLAG_NONE);
        return text + 1;
    }

    if (first < 0x80)
    {
        TextUtf8_SetToken(
            out, TEXT_UTF8_TOKEN_SCALAR, first, 0, 1, 0, 0,
            TEXT_UTF8_TOKEN_FLAG_NONE);
        return text + 1;
    }

    if (first == 0x80)
    {
        if (bounded && available < 2)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);

        second = bytes[1];
        if (second <= 3)
        {
            if (bounded && available < 3)
                return TextUtf8_Invalid(
                    text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);

            TextUtf8_SetToken(
                out,
                TEXT_UTF8_TOKEN_EXTENDED_CONTROL,
                0,
                bytes[2],
                3,
                first,
                second,
                TEXT_UTF8_TOKEN_FLAG_EXTENDED_ARGUMENT);
            return text + 3;
        }

        TextUtf8_SetToken(
            out, TEXT_UTF8_TOKEN_EXTENDED_CONTROL, 0, 0, 2, first, second,
            TEXT_UTF8_TOKEN_FLAG_NONE);
        return text + 2;
    }

    if (first == 0x81)
    {
        if (bounded && available < 2)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);
        if (bytes[1] == 0x40)
        {
            TextUtf8_SetToken(
                out, TEXT_UTF8_TOKEN_SCALAR, 0x3000, 0, 2, 0, 0,
                TEXT_UTF8_TOKEN_FLAG_LEGACY_SPACE);
            return text + 2;
        }
    }

    if (bounded && available < 2)
        return TextUtf8_Invalid(
            text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);
    second = bytes[1];

    if (first >= 0xC2 && first <= 0xDF)
    {
        if (second < 0x80 || second > 0xBF)
            return TextUtf8_Invalid(
                text,
                out,
                second == 0
                    ? TEXT_UTF8_TOKEN_FLAG_TRUNCATED
                    : TEXT_UTF8_TOKEN_FLAG_NONE);

        scalar = ((u32)(first & 0x1F) << 6) | (second & 0x3F);
        TextUtf8_SetToken(
            out, TEXT_UTF8_TOKEN_SCALAR, scalar, 0, 2, 0, 0,
            TEXT_UTF8_TOKEN_FLAG_NONE);
        return text + 2;
    }

    if (first >= 0xE0 && first <= 0xEF)
    {
        if (second == 0)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);

        if (bounded && available < 3)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);
        third = bytes[2];
        if (third == 0)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);

        if (second < 0x80 || second > 0xBF || third < 0x80 || third > 0xBF)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_NONE);
        if (first == 0xE0 && second < 0xA0)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_NONE);
        if (first == 0xED && second >= 0xA0)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_NONE);

        scalar = ((u32)(first & 0x0F) << 12)
            | ((u32)(second & 0x3F) << 6)
            | (third & 0x3F);
        TextUtf8_SetToken(
            out, TEXT_UTF8_TOKEN_SCALAR, scalar, 0, 3, 0, 0,
            TEXT_UTF8_TOKEN_FLAG_NONE);
        return text + 3;
    }

    if (first >= 0xF0 && first <= 0xF4)
    {
        if (second == 0)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);

        if (bounded && available < 3)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);
        third = bytes[2];
        if (third == 0)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);

        if (bounded && available < 4)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);
        fourth = bytes[3];
        if (fourth == 0)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_TRUNCATED);

        if (second < 0x80 || second > 0xBF
            || third < 0x80 || third > 0xBF
            || fourth < 0x80 || fourth > 0xBF)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_NONE);
        if (first == 0xF0 && second < 0x90)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_NONE);
        if (first == 0xF4 && second > 0x8F)
            return TextUtf8_Invalid(
                text, out, TEXT_UTF8_TOKEN_FLAG_NONE);

        scalar = ((u32)(first & 0x07) << 18)
            | ((u32)(second & 0x3F) << 12)
            | ((u32)(third & 0x3F) << 6)
            | (fourth & 0x3F);
        TextUtf8_SetToken(
            out, TEXT_UTF8_TOKEN_SCALAR, scalar, 0, 4, 0, 0,
            TEXT_UTF8_TOKEN_FLAG_NONE);
        return text + 4;
    }

    return TextUtf8_Invalid(text, out, TEXT_UTF8_TOKEN_FLAG_NONE);
}

const char *TextUtf8_Next(const char *text, struct TextUtf8Token *out)
{
    return TextUtf8_NextInternal(text, 0, FALSE, out);
}

const char *TextUtf8_NextBounded(
    const char *text,
    u32 available,
    struct TextUtf8Token *out)
{
    return TextUtf8_NextInternal(text, available, TRUE, out);
}

#endif /* FE8_TEXT_UTF8_ENABLED */
