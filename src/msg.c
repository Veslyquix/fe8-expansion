#include "global.h"
#include <string.h>
#include "proc.h"
#include "bmio.h"
#include "bmitem.h"
#include "bmunit.h"
#include "bmlib.h"
#include "bmmind.h"
#include "expansion_starter_content.h"
#include "localized_game_text.h"
#include "scene.h"
#include "text_utf8.h"

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
#undef GetStringFromIndexInBuffer
#define MSG_BUFFER1 (sMsgString.storage.legacy.buffer1)
#define MSG_BUFFER2 (sMsgString.storage.legacy.buffer2)
#define MSG_BUFFER3 (sMsgString.storage.legacy.buffer3)
#define MSG_BUFFER4 (sMsgString.storage.legacy.buffer4)
#define MSG_BUFFER5 (sMsgString.storage.legacy.buffer5)
#define MSG_LOCALIZED_STORAGE (sMsgString.storage.localized)
#define MSG_TRANSFORM_OUTPUT_CAPACITY \
    FE8_LOCALIZED_GAME_TEXT_TRANSFORM_OUTPUT_BYTES
#define MSG_TRANSFORM_INSERTION_CAPACITY \
    FE8_LOCALIZED_GAME_TEXT_TRANSFORM_INSERTION_BYTES
#else
#define MSG_BUFFER1 (sMsgString.buffer1)
#define MSG_BUFFER2 (sMsgString.buffer2)
#define MSG_BUFFER3 (sMsgString.buffer3)
#define MSG_BUFFER4 (sMsgString.buffer4)
#define MSG_BUFFER5 (sMsgString.buffer5)
#endif

EWRAM_DATA struct MsgBuffer sMsgString = {0};
EWRAM_DATA int sActiveMsg = 0;

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
struct MsgTransformScratch
{
    char output[MSG_TRANSFORM_OUTPUT_CAPACITY];
    char insertion[MSG_TRANSFORM_INSERTION_CAPACITY];
};

/* msg.c owns this CJK-only workspace. The active decode cache remains in
 * sMsgString, while derived help-box/Tact/Item text uses these disjoint
 * regions and cannot alias prep/support overlay state. */
static EWRAM_DATA struct MsgTransformScratch sMsgTransformScratch = {0};
#define MSG_TRANSFORM_OUTPUT (sMsgTransformScratch.output)
#define MSG_TRANSFORM_INSERTION (sMsgTransformScratch.insertion)

static EWRAM_DATA bool8 sActiveMsgValid = FALSE;
static EWRAM_DATA ExpansionLocaleId sActiveMsgLocale;
static EWRAM_DATA enum LocalizedGameTextStatus sActiveMsgStatus;
static EWRAM_DATA enum LocalizedGameTextStatus sLastMsgStatus;
LOCALIZED_GAME_TEXT_STATIC_ASSERT(
    sizeof(sMsgTransformScratch.output)
        == MSG_TRANSFORM_OUTPUT_CAPACITY,
    transform_output_capacity_is_exact);
LOCALIZED_GAME_TEXT_STATIC_ASSERT(
    sizeof(sMsgTransformScratch.insertion)
        == MSG_TRANSFORM_INSERTION_CAPACITY,
    transform_insertion_capacity_is_exact);
#endif

const char *gStrPrefix[][2] =
{
    {"a ", "A "},
    {"an ", "An "},
};

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
static ExpansionLocaleId GetMsgLocale(void)
{
    return ExpansionLocale_GetCurrent();
}

static int SetLocalizedMsgTerminator(char *buffer, u32 decodedLength);

#if 0
/* Legacy gMsgTable fallback decoding is intentionally dead in CJK profiles.
 * Every English/default/fallback entry is generated with exact byte and bit
 * bounds in gGameLocalizationEnglishCatalog. */
static int LocalizedGameText_ShouldUseEnglish(enum LocalizedGameTextStatus status)
{
    switch (status)
    {
    case LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT:
    case LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT:
    case LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_UNPOPULATED:
    case LOCALIZED_GAME_TEXT_STATUS_LEGACY_BUFFER_UNBOUNDED:
        return TRUE;

    default:
        return FALSE;
    }
}

static int LocalizedGameText_ShouldNormalizeEnglish(
    enum LocalizedGameTextStatus status)
{
    return status == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT
        || status == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_UNPOPULATED;
}

static char *DecodeEnglishString(int index, char *buffer)
{
    CallARM_DecompText((const char *)gMsgTable[index], buffer);
    SetMsgTerminator((signed char *)buffer);
    return buffer;
}

enum EnglishFallbackNormalizeState
{
    ENGLISH_FALLBACK_NORMALIZE_TEXT = 0,
    ENGLISH_FALLBACK_NORMALIZE_FACE_ID_LOW = 1,
    ENGLISH_FALLBACK_NORMALIZE_FACE_ID_HIGH = 2,
    ENGLISH_FALLBACK_NORMALIZE_EXTENDED_PAYLOAD = 3,
    ENGLISH_FALLBACK_NORMALIZE_SPACE_TRAIL = 4
};

static enum LocalizedGameTextStatus AppendNormalizedEnglishBytes(
    char *buffer,
    u32 bufferCapacity,
    u32 *outputLength,
    const u8 *bytes,
    u32 count)
{
    u32 i;

    if (*outputLength > bufferCapacity || count > bufferCapacity - *outputLength)
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW;

    for (i = 0; i < count; i++)
        buffer[(*outputLength)++] = bytes[i];

    return LOCALIZED_GAME_TEXT_STATUS_OK;
}

static enum LocalizedGameTextStatus NormalizeEnglishFallbackByte(
    u8 byte,
    char *buffer,
    u32 bufferCapacity,
    u32 *outputLength,
    enum EnglishFallbackNormalizeState *state)
{
    static const u8 sUtf8IdeographicSpace[] = {0xE3, 0x80, 0x80};
    u8 replacement;

    switch (*state)
    {
    case ENGLISH_FALLBACK_NORMALIZE_FACE_ID_LOW:
        if (byte == 0)
            return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;
        *state = ENGLISH_FALLBACK_NORMALIZE_FACE_ID_HIGH;
        return AppendNormalizedEnglishBytes(
            buffer, bufferCapacity, outputLength, &byte, 1);

    case ENGLISH_FALLBACK_NORMALIZE_FACE_ID_HIGH:
    case ENGLISH_FALLBACK_NORMALIZE_EXTENDED_PAYLOAD:
        if (byte == 0)
            return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;
        *state = ENGLISH_FALLBACK_NORMALIZE_TEXT;
        return AppendNormalizedEnglishBytes(
            buffer, bufferCapacity, outputLength, &byte, 1);

    case ENGLISH_FALLBACK_NORMALIZE_SPACE_TRAIL:
        if (byte != MSG_ENGLISH_LEGACY_SPACE_TRAIL)
            return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;
        *state = ENGLISH_FALLBACK_NORMALIZE_TEXT;
        return AppendNormalizedEnglishBytes(
            buffer,
            bufferCapacity,
            outputLength,
            sUtf8IdeographicSpace,
            ARRAY_COUNT(sUtf8IdeographicSpace));

    case ENGLISH_FALLBACK_NORMALIZE_TEXT:
    default:
        break;
    }

    if (byte == 0)
        return AppendNormalizedEnglishBytes(
            buffer, bufferCapacity, outputLength, &byte, 1);

    if (byte < 0x20)
    {
        if (byte == CHFE_L_LoadFace)
            *state = ENGLISH_FALLBACK_NORMALIZE_FACE_ID_LOW;
        return AppendNormalizedEnglishBytes(
            buffer, bufferCapacity, outputLength, &byte, 1);
    }

    if (byte < MSG_ENGLISH_LEGACY_DASH)
        return AppendNormalizedEnglishBytes(
            buffer, bufferCapacity, outputLength, &byte, 1);

    switch (byte)
    {
    case MSG_ENGLISH_LEGACY_DASH:
        replacement = '-';
        break;

    case 0x80:
        *state = ENGLISH_FALLBACK_NORMALIZE_EXTENDED_PAYLOAD;
        return AppendNormalizedEnglishBytes(
            buffer, bufferCapacity, outputLength, &byte, 1);

    case MSG_ENGLISH_LEGACY_SPACE_LEAD:
        *state = ENGLISH_FALLBACK_NORMALIZE_SPACE_TRAIL;
        return LOCALIZED_GAME_TEXT_STATUS_OK;

    case MSG_ENGLISH_LEGACY_LEFT_QUOTE:
    case MSG_ENGLISH_LEGACY_RIGHT_QUOTE:
        replacement = '"';
        break;

    case MSG_ENGLISH_LEGACY_ACCENTED_E:
        replacement = 'e';
        break;

    default:
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;
    }

    return AppendNormalizedEnglishBytes(
        buffer, bufferCapacity, outputLength, &replacement, 1);
}

static enum LocalizedGameTextStatus DecodeEnglishStringBounded(
    int index,
    char *buffer,
    u32 bufferCapacity,
    int normalize,
    u32 *outDecodedLength)
{
    const u8 *input;
    const u32 *current;
    u32 rootIndex;
    u32 nodeCount;
    u32 inputByteIndex;
    u32 bitIndex;
    u32 decodedInputLength;
    u32 outputLength;
    u32 steps;
    u32 node;
    u32 childIndex;
    u32 symbol;
    u32 needed;
    u8 inputByte;
    u8 bit;
    u8 low;
    u8 high;
    enum EnglishFallbackNormalizeState normalizeState;
    enum LocalizedGameTextStatus status;

    if (buffer == NULL || bufferCapacity == 0)
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;

    if (outDecodedLength != NULL)
        *outDecodedLength = 0;

    input = gMsgTable[index];
    if (input == NULL || gMsgHuffmanTableRoot < gMsgHuffmanTable)
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;

    rootIndex = (u32)(gMsgHuffmanTableRoot - gMsgHuffmanTable);
    if (rootIndex >= 0xFFFFu)
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;

    nodeCount = rootIndex + 1;
    current = gMsgHuffmanTableRoot;
    inputByteIndex = 0;
    bitIndex = 8;
    decodedInputLength = 0;
    outputLength = 0;
    inputByte = 0;
    normalizeState = ENGLISH_FALLBACK_NORMALIZE_TEXT;

    for (;;)
    {
        steps = 0;
        for (;;)
        {
            if (steps++ >= nodeCount)
                return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;

            node = *current;
            if ((node & MSG_HUFFMAN_LEAF_MASK) == MSG_HUFFMAN_LEAF_MASK)
                return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;

            if (bitIndex == 8)
            {
                if (inputByteIndex >= MSG_ENGLISH_INPUT_LIMIT_BYTES)
                    return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;

                inputByte = input[inputByteIndex++];
                bitIndex = 0;
            }

            bit = (inputByte >> bitIndex) & 1;
            bitIndex++;
            if (bit)
                childIndex = (node >> 16) & 0xFFFF;
            else
                childIndex = node & 0xFFFF;

            if (childIndex >= nodeCount)
                return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;

            current = &gMsgHuffmanTable[childIndex];
            node = *current;
            if ((node & MSG_HUFFMAN_LEAF_MASK) == MSG_HUFFMAN_LEAF_MASK)
                break;
        }

        symbol = node & 0xFFFF;
        low = symbol & 0xFF;
        high = (symbol >> 8) & 0xFF;
        needed = high ? 2 : 1;

        if (high && low == 0)
            return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;

        if (decodedInputLength > MSG_ENGLISH_OUTPUT_LIMIT_BYTES
            || needed > MSG_ENGLISH_OUTPUT_LIMIT_BYTES - decodedInputLength)
            return LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW;

        decodedInputLength++;
        if (normalize)
        {
            status = NormalizeEnglishFallbackByte(
                low,
                buffer,
                bufferCapacity,
                &outputLength,
                &normalizeState);
        }
        else
        {
            status = AppendNormalizedEnglishBytes(
                buffer, bufferCapacity, &outputLength, &low, 1);
        }
        if (status != LOCALIZED_GAME_TEXT_STATUS_OK)
            return status;

        if (high)
        {
            decodedInputLength++;
            if (normalize)
            {
                status = NormalizeEnglishFallbackByte(
                    high,
                    buffer,
                    bufferCapacity,
                    &outputLength,
                    &normalizeState);
            }
            else
            {
                status = AppendNormalizedEnglishBytes(
                    buffer, bufferCapacity, &outputLength, &high, 1);
            }
            if (status != LOCALIZED_GAME_TEXT_STATUS_OK)
                return status;
        }
        else if (low == 0)
        {
            if (normalizeState != ENGLISH_FALLBACK_NORMALIZE_TEXT)
                return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;
            if (outDecodedLength != NULL)
                *outDecodedLength = outputLength;
            return LOCALIZED_GAME_TEXT_STATUS_OK;
        }

        current = gMsgHuffmanTableRoot;
    }
}

static void WriteBoundedMsgMarker(
    char *buffer,
    u32 bufferCapacity,
    const char *marker)
{
    u32 i;

    if (buffer == NULL || bufferCapacity == 0)
        return;

    i = 0;
    while (i + 1 < bufferCapacity && marker[i] != '\0')
    {
        buffer[i] = marker[i];
        i++;
    }

    buffer[i] = '\0';
}

static char *DecodeEnglishStringWithLimit(
    int index,
    char *buffer,
    u32 bufferCapacity,
    int normalize)
{
    enum LocalizedGameTextStatus status;
    u32 decodedLength;

    decodedLength = 0;
    status = DecodeEnglishStringBounded(
        index, buffer, bufferCapacity, normalize, &decodedLength);
    if (status == LOCALIZED_GAME_TEXT_STATUS_OK)
    {
        if (normalize)
            SetLocalizedMsgTerminator(buffer, decodedLength);
        else
            SetMsgTerminator((signed char *)buffer);
        return buffer;
    }

    sLastMsgStatus = status;
    if (status == LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW)
    {
        WriteBoundedMsgMarker(
            buffer, bufferCapacity, LOCALIZED_GAME_TEXT_MARKER_OVERFLOW);
        return buffer;
    }

    if (status == LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT)
    {
        WriteBoundedMsgMarker(
            buffer, bufferCapacity, LOCALIZED_GAME_TEXT_MARKER_CORRUPT);
        return buffer;
    }

    WriteBoundedMsgMarker(
        buffer, bufferCapacity, LOCALIZED_GAME_TEXT_MARKER_INVALID);
    return buffer;
}
#endif

static void WriteBoundedMsgMarker(
    char *buffer,
    u32 bufferCapacity,
    const char *marker)
{
    u32 i;

    if (buffer == NULL || bufferCapacity == 0)
        return;

    i = 0;
    while (i + 1 < bufferCapacity && marker[i] != '\0')
    {
        buffer[i] = marker[i];
        i++;
    }
    buffer[i] = '\0';
}

static int SetLocalizedMsgTerminator(char *buffer, u32 decodedLength)
{
    struct TextUtf8Token token;
    const char *cursor;
    const char *next;
    char *trailingTerminator;
    u32 remaining;

    if (buffer == NULL || decodedLength == 0)
        return FALSE;

    cursor = buffer;
    remaining = decodedLength;
    trailingTerminator = NULL;
    for (;;)
    {
        next = TextUtf8_NextBounded(cursor, remaining, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
        {
            if (trailingTerminator != NULL)
                *trailingTerminator = '\0';
            return TRUE;
        }

        if (token.kind == TEXT_UTF8_TOKEN_INVALID || next == cursor)
            return FALSE;

        if (token.kind == TEXT_UTF8_TOKEN_CONTROL
            && token.control == 0x1F)
        {
            if (trailingTerminator == NULL)
                trailingTerminator = (char *)cursor;
        }
        else
        {
            trailingTerminator = NULL;
        }

        remaining -= (u32)(next - cursor);
        cursor = next;
    }
}

static int LocalizedGameText_DecodeSucceeded(
    enum LocalizedGameTextStatus status)
{
    switch (status)
    {
    case LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT:
    case LOCALIZED_GAME_TEXT_STATUS_OK:
    case LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT:
    case LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_UNPOPULATED:
        return TRUE;

    default:
        return FALSE;
    }
}

static char *ResolveStringIntoBuffer(int index, char *buffer, u32 bufferCapacity)
{
    enum LocalizedGameTextStatus status;
    u32 decodedLength;

    if (buffer == NULL || bufferCapacity == 0)
    {
        sLastMsgStatus = LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;
        return buffer;
    }

    decodedLength = 0;
    status = LocalizedGameText_ResolveCurrentToBuffer(
        index, buffer, bufferCapacity, &decodedLength);

    if (LocalizedGameText_DecodeSucceeded(status))
    {
        if (!SetLocalizedMsgTerminator(buffer, decodedLength))
        {
            status = LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;
            WriteBoundedMsgMarker(
                buffer, bufferCapacity, LOCALIZED_GAME_TEXT_MARKER_CORRUPT);
        }
    }

    sLastMsgStatus = status;
    return buffer;
}

static char *ResolveStringIntoUnboundedBuffer(char *buffer)
{
    if (buffer == NULL)
    {
        sLastMsgStatus = LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;
        return buffer;
    }

    sLastMsgStatus = LOCALIZED_GAME_TEXT_STATUS_LEGACY_BUFFER_UNBOUNDED;
    return (char *)LOCALIZED_GAME_TEXT_MARKER_UNBOUNDED;
}
#endif

const char * GetStrPrefix(s8 * str, bool capital)
{
    switch (str[0])
    {
    case 'A':
    case 'E':
    case 'I':
    case 'O':
    case 'U':
    case 'a':
    case 'e':
    case 'i':
    case 'o':
    case 'u':
        return gStrPrefix[1][capital];
    default:
        return gStrPrefix[0][capital];
    }
}

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
struct MsgStreamWriter
{
    char *buffer;
    u32 capacity;
    u32 length;
};

static void MsgStreamWriter_Init(
    struct MsgStreamWriter *writer,
    char *buffer,
    u32 capacity)
{
    writer->buffer = buffer;
    writer->capacity = capacity;
    writer->length = 0;
    if (capacity != 0)
        buffer[0] = '\0';
}

static int MsgStreamWriter_AppendBytes(
    struct MsgStreamWriter *writer,
    const char *source,
    u32 count)
{
    u32 i;

    if (writer->capacity == 0 || writer->length >= writer->capacity
        || count > writer->capacity - writer->length - 1)
        return FALSE;

    for (i = 0; i < count; i++)
        writer->buffer[writer->length++] = source[i];
    writer->buffer[writer->length] = '\0';
    return TRUE;
}

static int MsgStreamWriter_AppendStream(
    struct MsgStreamWriter *writer,
    const char *source,
    u32 sourceCapacity)
{
    struct TextUtf8Token token;
    const char *cursor;
    const char *next;
    u32 remaining;

    cursor = source;
    remaining = sourceCapacity;
    for (;;)
    {
        if (sourceCapacity == 0)
            next = TextUtf8_Next(cursor, &token);
        else
            next = TextUtf8_NextBounded(cursor, remaining, &token);

        if (token.kind == TEXT_UTF8_TOKEN_END)
            return TRUE;
        if (token.kind == TEXT_UTF8_TOKEN_INVALID || next == cursor)
            return FALSE;
        if (!MsgStreamWriter_AppendBytes(
                writer, cursor, (u32)(next - cursor)))
            return FALSE;

        if (sourceCapacity != 0)
            remaining -= (u32)(next - cursor);
        cursor = next;
    }
}

static int MsgStreamWriter_AppendTactStream(
    struct MsgStreamWriter *writer,
    const char *source,
    u32 sourceCapacity)
{
    struct TextUtf8Token token;
    const char *cursor;
    const char *next;
    u32 remaining;

    cursor = source;
    remaining = sourceCapacity;
    for (;;)
    {
        if (sourceCapacity == 0)
            next = TextUtf8_Next(cursor, &token);
        else
            next = TextUtf8_NextBounded(cursor, remaining, &token);

        if (token.kind == TEXT_UTF8_TOKEN_END)
            return TRUE;
        if (token.kind == TEXT_UTF8_TOKEN_INVALID || next == cursor)
            return FALSE;

        if (token.kind == TEXT_UTF8_TOKEN_EXTENDED_CONTROL
            && token.payload == 0x20)
        {
            if (!MsgStreamWriter_AppendStream(
                    writer, GetTacticianName(), 0))
                return FALSE;
        }
        else if (!MsgStreamWriter_AppendBytes(
                     writer, cursor, (u32)(next - cursor)))
        {
            return FALSE;
        }

        if (sourceCapacity != 0)
            remaining -= (u32)(next - cursor);
        cursor = next;
    }
}

static int MsgStream_GetLength(
    const char *source,
    u32 sourceCapacity,
    u32 *outLength)
{
    struct TextUtf8Token token;
    const char *cursor;
    const char *next;
    u32 remaining;

    cursor = source;
    remaining = sourceCapacity;
    *outLength = 0;
    for (;;)
    {
        if (sourceCapacity == 0)
            next = TextUtf8_Next(cursor, &token);
        else
            next = TextUtf8_NextBounded(cursor, remaining, &token);

        if (token.kind == TEXT_UTF8_TOKEN_END)
            return TRUE;
        if (token.kind == TEXT_UTF8_TOKEN_INVALID || next == cursor)
            return FALSE;

        *outLength += (u32)(next - cursor);
        if (sourceCapacity != 0)
            remaining -= (u32)(next - cursor);
        cursor = next;
    }
}

static char *MsgTransformFailure(
    char *buffer,
    u32 capacity,
    enum LocalizedGameTextStatus status)
{
    sLastMsgStatus = status;
    if (status == LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW)
        WriteBoundedMsgMarker(
            buffer, capacity, LOCALIZED_GAME_TEXT_MARKER_OVERFLOW);
    else
        WriteBoundedMsgMarker(
            buffer, capacity, LOCALIZED_GAME_TEXT_MARKER_CORRUPT);
    return buffer;
}

void InsertPrefixWithLimit(
    char *str,
    u32 capacity,
    const char *prefix,
    bool capital)
{
    const char *selectedPrefix;
    u32 prefixLength;
    u32 stringLength;
    u32 i;

    if (str == NULL || capacity == 0)
    {
        sLastMsgStatus = LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;
        return;
    }

    if (prefix == NULL)
        selectedPrefix = GetStrPrefix((s8 *)str, capital);
    else
        selectedPrefix = prefix;

    if (!MsgStream_GetLength(selectedPrefix, 0, &prefixLength))
    {
        MsgTransformFailure(
            str, capacity, LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT);
        return;
    }
    if (!MsgStream_GetLength(str, capacity, &stringLength))
    {
        MsgTransformFailure(
            str, capacity, LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT);
        return;
    }
    if (prefixLength > capacity - 1
        || stringLength > capacity - prefixLength - 1)
    {
        MsgTransformFailure(
            str, capacity, LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);
        return;
    }

    i = stringLength + 1;
    while (i != 0)
    {
        i--;
        str[i + prefixLength] = str[i];
    }
    for (i = 0; i < prefixLength; i++)
        str[i] = selectedPrefix[i];
}
#endif

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
char *
#else
void
#endif
InsertPrefix(char *str, const char *prefix, bool capital)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    struct MsgStreamWriter writer;
    char *output;
    u32 capacity;

    if (str == NULL)
    {
        sLastMsgStatus = LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;
        return str;
    }

    output = str;
    capacity = MSG_TRANSFORM_OUTPUT_CAPACITY;
    if (str != MSG_TRANSFORM_OUTPUT)
    {
        MsgStreamWriter_Init(
            &writer, MSG_TRANSFORM_OUTPUT, MSG_TRANSFORM_OUTPUT_CAPACITY);
        if (!MsgStreamWriter_AppendStream(&writer, str, 0))
            return MsgTransformFailure(
                MSG_TRANSFORM_OUTPUT,
                MSG_TRANSFORM_OUTPUT_CAPACITY,
                LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);
        output = MSG_TRANSFORM_OUTPUT;
    }

    InsertPrefixWithLimit(output, capacity, prefix, capital);
    return output;
#else
    const char * _prefix;
    u8 len_prefix;
    s16 i;

    if (prefix == NULL)
        _prefix = GetStrPrefix((s8 *)str, capital);
    else
        _prefix = prefix;

    len_prefix = strlen(_prefix);
    for (i = strlen(str); i >= 0; i--)
        str[i + len_prefix] = str[i];

    for (i = 0; i < len_prefix; i++)
        str[i] = _prefix[i];
#endif
}

void SetMsgTerminator(signed char * str)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    struct TextUtf8Token token;
    const char *cursor;
    const char *next;
    signed char *trailingTerminator;

    cursor = (const char *)str;
    trailingTerminator = NULL;
    for (;;)
    {
        next = TextUtf8_Next(cursor, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
        {
            if (trailingTerminator != NULL)
                *trailingTerminator = '\0';
            return;
        }
        if (token.kind == TEXT_UTF8_TOKEN_INVALID || next == cursor)
            return;

        if (token.kind == TEXT_UTF8_TOKEN_CONTROL
            && token.control == 0x1F)
        {
            if (trailingTerminator == NULL)
                trailingTerminator = (signed char *)cursor;
        }
        else
        {
            trailingTerminator = NULL;
        }
        cursor = next;
    }
#else
    short off = 0;
    u8 ch;

    while (str[off] != 0)
    {
        ch = str[off];
        if (ch == CHFE_L_LoadFace)   /* [LoadFace] */
            off += 2;

        if (ch == 0x80)   /* [HalfCloseEyes] */
            off += 1;
        off++;
    }

    off--;
    while (off >= 0)
    {
        ch = str[off];
        if (ch != 0x1F)   /* [.] */
            return;

        /* <!> [.] --> \x0 */
        ch = str[off - 1];
        if (ch != 0x80)   /* [HalfCloseEyes] */
            str[off] = '\0';

        off--;
    }
#endif
}

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
void LocalizedGameText_InvalidateCache(void)
{
    sActiveMsgValid = FALSE;
    sActiveMsg = 0;
    sActiveMsgLocale = EXPANSION_LOCALE_INVALID;
    sActiveMsgStatus = LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT;
    sLastMsgStatus = LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT;
}

enum LocalizedGameTextStatus LocalizedGameText_GetLastStatus(void)
{
    return sLastMsgStatus;
}

char * GetStringFromIndex(int index)
{
    ExpansionLocaleId locale;

    locale = GetMsgLocale();
    if (sActiveMsgValid && index == sActiveMsg && locale == sActiveMsgLocale)
    {
        sLastMsgStatus = sActiveMsgStatus;
        return (char *)MSG_LOCALIZED_STORAGE;
    }

    ResolveStringIntoBuffer(index, (char *)MSG_LOCALIZED_STORAGE,
        (u32)sizeof(MSG_LOCALIZED_STORAGE));
    sActiveMsg = index;
    sActiveMsgLocale = locale;
    sActiveMsgStatus = sLastMsgStatus;
    sActiveMsgValid = TRUE;
    return (char *)MSG_LOCALIZED_STORAGE;
}

char * GetStringFromIndexInBufferWithLimit(int index, char *buffer, u32 bufferCapacity)
{
    return ResolveStringIntoBuffer(index, buffer, bufferCapacity);
}

char * GetStringFromIndexInBuffer(int index, char *buffer)
{
    (void)index;
    return ResolveStringIntoUnboundedBuffer(buffer);
}
#else
char * GetStringFromIndex(int index)
{
    if (index == sActiveMsg)
        return (char *)MSG_BUFFER1;
    CallARM_DecompText((const char *)gMsgTable[index], (char *)MSG_BUFFER1);
    SetMsgTerminator((signed char *)MSG_BUFFER1);
    sActiveMsg = index;
    return (char *)MSG_BUFFER1;
}

char * GetStringFromIndexInBuffer(int index, char *buffer)
{
    CallARM_DecompText((const char *)gMsgTable[index], buffer);
    SetMsgTerminator((signed char *)buffer);
    return buffer;
}
#endif

char * StringInsertSpecialPrefixByCtrl(void)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    struct MsgStreamWriter writer;
    struct TextUtf8Token token;
    enum LocalizedGameTextStatus sourceStatus;
    enum LocalizedGameTextStatus nestedStatus;
    const char *cursor;
    const char *next;
    const char *replacement;
    u32 replacementCapacity;
    u32 remaining;
    int characterSlot;

    sourceStatus = sLastMsgStatus;
    MsgStreamWriter_Init(
        &writer, MSG_TRANSFORM_OUTPUT, MSG_TRANSFORM_OUTPUT_CAPACITY);
    cursor = (const char *)MSG_LOCALIZED_STORAGE;
    remaining = (u32)sizeof(MSG_LOCALIZED_STORAGE);
    for (;;)
    {
        next = TextUtf8_NextBounded(cursor, remaining, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
        {
            sLastMsgStatus = sourceStatus;
            return writer.buffer;
        }
        if (token.kind == TEXT_UTF8_TOKEN_INVALID || next == cursor)
            return MsgTransformFailure(
                MSG_TRANSFORM_OUTPUT,
                MSG_TRANSFORM_OUTPUT_CAPACITY,
                LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT);

        replacement = NULL;
        replacementCapacity = 0;
        characterSlot = -1;
        if (token.kind == TEXT_UTF8_TOKEN_EXTENDED_CONTROL)
        {
            switch (token.payload)
            {
            case 0x12:
            case 0x13:
            case 0x14:
            case 0x15:
                characterSlot = token.payload - 0x12;
                break;

            case 0x20:
                replacement = GetTacticianName();
                break;

            case 0x22:
#if FE8_EXPANSION_STARTER_CONTENT
                replacement = ExpansionStarterContentItemName(
                    (ItemId)GetItemIndex(gActionData.item));
#endif
                if (replacement == NULL)
                {
                    GetStringFromIndexInBufferWithLimit(
                        GetItemData(GetItemIndex(gActionData.item))->nameTextId,
                        MSG_TRANSFORM_INSERTION,
                        MSG_TRANSFORM_INSERTION_CAPACITY);
                    nestedStatus = sLastMsgStatus;
                    if (!LocalizedGameText_DecodeSucceeded(nestedStatus))
                        return MsgTransformFailure(
                            MSG_TRANSFORM_OUTPUT,
                            MSG_TRANSFORM_OUTPUT_CAPACITY,
                            nestedStatus);
                    replacement = MSG_TRANSFORM_INSERTION;
                    replacementCapacity =
                        MSG_TRANSFORM_INSERTION_CAPACITY;
                }
                break;
            }
        }

        if (characterSlot >= 0)
        {
            GetStringFromIndexInBufferWithLimit(
                GetCharacterData(gPlaySt.unk1C[characterSlot])->nameTextId,
                MSG_TRANSFORM_INSERTION,
                MSG_TRANSFORM_INSERTION_CAPACITY);
            nestedStatus = sLastMsgStatus;
            if (!LocalizedGameText_DecodeSucceeded(nestedStatus))
                return MsgTransformFailure(
                    MSG_TRANSFORM_OUTPUT,
                    MSG_TRANSFORM_OUTPUT_CAPACITY,
                    nestedStatus);
            replacement = MSG_TRANSFORM_INSERTION;
            replacementCapacity = MSG_TRANSFORM_INSERTION_CAPACITY;
        }

        if (replacement != NULL)
        {
            if (!MsgStreamWriter_AppendTactStream(
                    &writer, replacement, replacementCapacity))
                return MsgTransformFailure(
                    MSG_TRANSFORM_OUTPUT,
                    MSG_TRANSFORM_OUTPUT_CAPACITY,
                    LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);
        }
        else if (!MsgStreamWriter_AppendBytes(
                     &writer, cursor, (u32)(next - cursor)))
        {
            return MsgTransformFailure(
                MSG_TRANSFORM_OUTPUT,
                MSG_TRANSFORM_OUTPUT_CAPACITY,
                LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);
        }

        remaining -= (u32)(next - cursor);
        cursor = next;
    }
#else
    u8 * r5 = MSG_BUFFER2;
    u8 * dst = MSG_BUFFER3;

    CopyString((char *)r5, (const char *)MSG_BUFFER1);
    while (*r5 != 0)
    {
        if (*r5 < '\x20')
            *dst++ = *r5++;
        else if (*r5 != 0x80) /* Normal string */
            *dst++ = *r5++;
        else
        {
            int r1;

            r5++;
            switch (*r5)
            {
            case '\x12':    /* wh:1280 */
                r1 = 0;
                break;
            case '\x13':    /* wh:1380 */
                r1 = 1;
                break;
            case '\x14':    /* wh:1480 */
                r1 = 2;
                break;
            case '\x15':    /* wh:1580 */
                r1 = 3;
                break;
            case '\x20':    /* [Tact]: "\x20\x80" */
                CopyString((char *)dst, GetTacticianName());
                goto label;
            case '\x22':    /* [Item]: "\x22\x80" */
                CopyString((char *)dst, GetItemName(gActionData.item));
                goto label;
            default:
                *dst++ = 0x80;
                *dst++ = *r5++;
                continue;
            }
            CopyString(
                (char *)dst,
                GetStringFromIndex(GetCharacterData(gPlaySt.unk1C[r1])->nameTextId));
        label:
            while (*dst != 0)
                dst++;
            r5++;
        }
    }
    *dst = 0;
    return (char *)MSG_BUFFER3;
#endif
}

char * StrInsertTact(void)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    struct MsgStreamWriter writer;
    struct TextUtf8Token token;
    enum LocalizedGameTextStatus sourceStatus;
    const char *cursor;
    const char *next;
    u32 remaining;

    sourceStatus = sLastMsgStatus;
    MsgStreamWriter_Init(
        &writer, MSG_TRANSFORM_OUTPUT, MSG_TRANSFORM_OUTPUT_CAPACITY);
    cursor = (const char *)MSG_LOCALIZED_STORAGE;
    remaining = (u32)sizeof(MSG_LOCALIZED_STORAGE);
    for (;;)
    {
        next = TextUtf8_NextBounded(cursor, remaining, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
        {
            sLastMsgStatus = sourceStatus;
            return writer.buffer;
        }
        if (token.kind == TEXT_UTF8_TOKEN_INVALID || next == cursor)
            return MsgTransformFailure(
                MSG_TRANSFORM_OUTPUT,
                MSG_TRANSFORM_OUTPUT_CAPACITY,
                LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT);

        if (token.kind == TEXT_UTF8_TOKEN_EXTENDED_CONTROL
            && token.payload == 0x20)
        {
            if (!MsgStreamWriter_AppendStream(
                    &writer, GetTacticianName(), 0))
                return MsgTransformFailure(
                    MSG_TRANSFORM_OUTPUT,
                    MSG_TRANSFORM_OUTPUT_CAPACITY,
                    LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);
        }
        else if (!MsgStreamWriter_AppendBytes(
                     &writer, cursor, (u32)(next - cursor)))
        {
            return MsgTransformFailure(
                MSG_TRANSFORM_OUTPUT,
                MSG_TRANSFORM_OUTPUT_CAPACITY,
                LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);
        }

        remaining -= (u32)(next - cursor);
        cursor = next;
    }
#else
    u8 * r5 = MSG_BUFFER4;
    u8 * r4 = MSG_BUFFER5;
    u8 r1;
    u32 r0;

    CopyString((char *)r5, (const char *)MSG_BUFFER1);

    while ((r0 = *r5))
    {
        r1 = r0;
        while (0) ;
        if (r1 < 0x20)
        {
            *r4 = r0;
            ++r5;
            ++r4;
        }
        else if (r1 != 0x80)
        {
            *r4 = r0;
            ++r5;
            ++r4;
        }
        else
        {
            /* "\xxx\x80" */
            r5++;
            if (*r5 != 0x20)
            {
                *r4++ = r1;
                *r4++ = *r5++;
            }
            else
            {
                /* [Tact]: "\x20\x80" */
                CopyString((char *)r4, GetTacticianName());
                while (*r4 != 0)
                    r4++;
                r5++;
            }
        }
    }
    *r4 = 0;
    return (char *)MSG_BUFFER5;
#endif
}
