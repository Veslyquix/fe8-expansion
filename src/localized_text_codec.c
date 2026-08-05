#include "global.h"

#include "localized_text_codec.h"

/*
 * This source is discovered by both source globs, but MODERN is defined only
 * by modern.mk. The archival compiler therefore sees an empty translation
 * unit, and ldscript.txt does not link this new object into fireemblem8.gba.
 */
#ifdef MODERN

#define LOCALIZED_TEXT_CODEC_LEAF_MASK 0xFFFF0000u
#define LOCALIZED_TEXT_CODEC_MAX_NODES 0x00010000u

static int LocalizedTextCodec_IsLeaf(u32 node)
{
    return (node & LOCALIZED_TEXT_CODEC_LEAF_MASK) == LOCALIZED_TEXT_CODEC_LEAF_MASK;
}

enum LocalizedTextCodecStatus LocalizedTextCodec_Decode(
    const u32 *nodes,
    u32 nodeCount,
    u32 rootIndex,
    const u8 *input,
    u32 inputByteLength,
    u8 *output,
    u32 outputCapacity,
    u32 *outDecodedLength)
{
    u32 byteIndex;
    u32 bitIndex;
    u32 currentIndex;
    u32 outputLength;
    u32 node;
    u32 childIndex;
    u32 symbol;
    u32 needed;
    u8 bit;
    u8 low;
    u8 high;

    if (outDecodedLength == 0)
        return LOCALIZED_TEXT_CODEC_INVALID_ARGUMENT;

    *outDecodedLength = 0;

    if (nodes == 0 || input == 0 || output == 0)
        return LOCALIZED_TEXT_CODEC_INVALID_ARGUMENT;

    if (nodeCount == 0 || nodeCount > LOCALIZED_TEXT_CODEC_MAX_NODES)
        return LOCALIZED_TEXT_CODEC_INVALID_ARGUMENT;

    if (rootIndex >= nodeCount || LocalizedTextCodec_IsLeaf(nodes[rootIndex]))
        return LOCALIZED_TEXT_CODEC_INVALID_ROOT;

    byteIndex = 0;
    bitIndex = 0;
    currentIndex = rootIndex;
    outputLength = 0;

    for (;;)
    {
        if (byteIndex >= inputByteLength)
        {
            *outDecodedLength = outputLength;
            if (currentIndex == rootIndex)
                return LOCALIZED_TEXT_CODEC_MISSING_TERMINATOR;
            return LOCALIZED_TEXT_CODEC_TRUNCATED_INPUT;
        }

        node = nodes[currentIndex];
        if (LocalizedTextCodec_IsLeaf(node))
        {
            *outDecodedLength = outputLength;
            return LOCALIZED_TEXT_CODEC_INVALID_NODE;
        }

        bit = (input[byteIndex] >> bitIndex) & 1;
        bitIndex++;
        if (bitIndex == 8)
        {
            bitIndex = 0;
            byteIndex++;
        }

        if (bit)
            childIndex = (node >> 16) & 0xFFFF;
        else
            childIndex = node & 0xFFFF;

        if (childIndex >= nodeCount)
        {
            *outDecodedLength = outputLength;
            return LOCALIZED_TEXT_CODEC_INVALID_NODE;
        }

        currentIndex = childIndex;
        node = nodes[currentIndex];
        if (!LocalizedTextCodec_IsLeaf(node))
            continue;

        symbol = node & 0xFFFF;
        low = symbol & 0xFF;
        high = (symbol >> 8) & 0xFF;
        needed = high ? 2 : 1;

        if (high && low == 0)
        {
            *outDecodedLength = outputLength;
            return LOCALIZED_TEXT_CODEC_INVALID_SYMBOL;
        }

        if (outputCapacity - outputLength < needed)
        {
            *outDecodedLength = outputLength;
            return LOCALIZED_TEXT_CODEC_OUTPUT_OVERFLOW;
        }

        output[outputLength++] = low;
        if (high)
        {
            output[outputLength++] = high;
        }
        else if (low == 0)
        {
            *outDecodedLength = outputLength;
            return LOCALIZED_TEXT_CODEC_OK;
        }

        currentIndex = rootIndex;
    }
}

#endif /* MODERN */
