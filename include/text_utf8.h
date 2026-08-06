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

enum TextUtf8TokenFlags
{
    TEXT_UTF8_TOKEN_FLAG_NONE = 0,
    TEXT_UTF8_TOKEN_FLAG_TRUNCATED = (1 << 0),
    TEXT_UTF8_TOKEN_FLAG_FACE_PAYLOAD = (1 << 1),
    TEXT_UTF8_TOKEN_FLAG_EXTENDED_ARGUMENT = (1 << 2),
    TEXT_UTF8_TOKEN_FLAG_LEGACY_SPACE = (1 << 3)
};

struct TextUtf8Token
{
    enum TextUtf8TokenKind kind;
    u32 scalar;
    u16 argument;
    u8 length;
    u8 control;
    u8 payload;
    u8 flags;
};

/*
 * Decodes exactly one token at a token boundary and returns the first byte
 * after it. END returns the input pointer unchanged. INVALID always consumes
 * one available non-NUL byte, guaranteeing progress without swallowing a
 * later valid token. Low controls are one byte except [LoadFace], which owns
 * its two-byte FID payload. A standalone 0x80 begins an extended control;
 * color controls 0x80 0x00..0x03 own one additional argument byte. The
 * legacy 0x81 0x40 spacing token is normalized to scalar U+3000 and flagged
 * so modern consumers never special-case its bytes. A 0x80 reached while
 * decoding a valid scalar remains its continuation byte.
 */
const char *TextUtf8_Next(const char *text, struct TextUtf8Token *out);

/*
 * Bounded form for validation and scratch-buffer work. available includes
 * every readable byte from text, including a terminating NUL when present.
 * Missing UTF-8 or control payload bytes produce INVALID|TRUNCATED without
 * reading beyond the supplied extent.
 */
const char *TextUtf8_NextBounded(
    const char *text,
    u32 available,
    struct TextUtf8Token *out);

#endif /* modern build with a CJK locale */

#endif /* GUARD_TEXT_UTF8_H */
