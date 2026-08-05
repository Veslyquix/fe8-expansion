#ifndef GUARD_LOCALIZED_TEXT_CODEC_H
#define GUARD_LOCALIZED_TEXT_CODEC_H

/*
 * Modern CJK-profile explicit-table Huffman decoder.
 * Include global.h before this header, following the repository's C include
 * convention, so u8/u32 and FE8_EXPANSION_ENABLED_LOCALE_MASK are available.
 *
 * Nodes use the existing engine convention:
 *   leaf:     0xFFFF0000 | u16 symbol
 *   internal: (right child index << 16) | left child index
 *
 * Input bits are consumed least-significant bit first. A symbol whose high
 * byte is nonzero emits low then high; generated catalogs never pair a zero
 * byte. A single-byte zero symbol is the only successful terminator.
 *
 * inputBitLength is the exact meaningful bit count and must fit within
 * inputByteLength. The terminating NUL must consume the final meaningful bit;
 * a NUL followed by bits inside inputBitLength is trailing-data corruption.
 * Byte padding outside inputBitLength is never consumed. outDecodedLength
 * includes the terminating NUL on success and on trailing-data failure. On
 * other failures it is the number of bytes safely written before the failure.
 * outputCapacity also includes space for the NUL.
 */

/*
 * Stable locale-mask bits 1 and 2 are ja and zh-Hans respectively. English
 * and ASCII pseudo-locale profiles use the uncompressed catalog path and must
 * not pay for this decoder.
 */
#if defined(MODERN) && ((FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x06u) != 0)

#define FE8_LOCALIZED_TEXT_CODEC_ENABLED 1

enum LocalizedTextCodecStatus
{
    LOCALIZED_TEXT_CODEC_OK = 0,
    LOCALIZED_TEXT_CODEC_INVALID_ARGUMENT = 1,
    LOCALIZED_TEXT_CODEC_INVALID_ROOT = 2,
    LOCALIZED_TEXT_CODEC_INVALID_NODE = 3,
    LOCALIZED_TEXT_CODEC_INVALID_SYMBOL = 4,
    LOCALIZED_TEXT_CODEC_TRUNCATED_INPUT = 5,
    LOCALIZED_TEXT_CODEC_MISSING_TERMINATOR = 6,
    LOCALIZED_TEXT_CODEC_OUTPUT_OVERFLOW = 7,
    LOCALIZED_TEXT_CODEC_TRAILING_DATA = 8
};

enum LocalizedTextCodecStatus LocalizedTextCodec_Decode(
    const u32 *nodes,
    u32 nodeCount,
    u32 rootIndex,
    const u8 *input,
    u32 inputByteLength,
    u32 inputBitLength,
    u8 *output,
    u32 outputCapacity,
    u32 *outDecodedLength);

#endif /* modern build with a CJK locale */

#endif /* GUARD_LOCALIZED_TEXT_CODEC_H */
