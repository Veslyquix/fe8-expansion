#ifndef GUARD_TEXT_UTF8_H
#define GUARD_TEXT_UTF8_H

/*
 * Strict UTF-8 and engine-control iteration for modern CJK profiles.
 * Include global.h before this header so u8/u32 and the generated locale
 * mask are available.
 */
#if defined(MODERN) && ((FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x06u) != 0)

#define FE8_TEXT_UTF8_ENABLED 1

enum TextUtf8TokenKind
{
    TEXT_UTF8_TOKEN_END = 0,
    TEXT_UTF8_TOKEN_CONTROL = 1,
    TEXT_UTF8_TOKEN_EXTENDED_CONTROL = 2,
    TEXT_UTF8_TOKEN_SCALAR = 3,
    TEXT_UTF8_TOKEN_INVALID = 4
};

struct TextUtf8Token
{
    enum TextUtf8TokenKind kind;
    u32 scalar;
    u8 length;
    u8 control;
    u8 payload;
};

/*
 * Decodes exactly one token at a token boundary and returns the first byte
 * after it. END returns the input pointer unchanged. INVALID always consumes
 * one non-NUL byte, guaranteeing progress without swallowing a later valid
 * token. A standalone 0x80 begins the engine's two-byte extended control;
 * 0x80 reached while decoding a valid scalar remains its continuation byte.
 */
const char *TextUtf8_Next(const char *text, struct TextUtf8Token *out);

#endif /* modern build with a CJK locale */

#endif /* GUARD_TEXT_UTF8_H */
