#include "global.h"
#include <string.h>
#include "proc.h"
#include "bmio.h"
#include "bmitem.h"
#include "bmunit.h"
#include "bmlib.h"
#include "bmmind.h"
#include "localized_game_text.h"
#include "scene.h"

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
#undef GetStringFromIndexInBuffer
#define MSG_BUFFER1 (sMsgString.storage.legacy.buffer1)
#define MSG_BUFFER2 (sMsgString.storage.legacy.buffer2)
#define MSG_BUFFER3 (sMsgString.storage.legacy.buffer3)
#define MSG_BUFFER4 (sMsgString.storage.legacy.buffer4)
#define MSG_BUFFER5 (sMsgString.storage.legacy.buffer5)
#define MSG_LOCALIZED_STORAGE (sMsgString.storage.localized)
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
static EWRAM_DATA bool8 sActiveMsgValid = FALSE;
static EWRAM_DATA ExpansionLocaleId sActiveMsgLocale;
static EWRAM_DATA enum LocalizedGameTextStatus sActiveMsgStatus;
static EWRAM_DATA enum LocalizedGameTextStatus sLastMsgStatus;
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

static void SetLocalizedMsgTerminator(char *buffer, u32 decodedLength);

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

static int LocalizedMsgEndsWithUtf8Scalar(const char *buffer, u32 endOffset)
{
    u32 startOffset;
    u32 scalarLength;
    u32 i;
    u8 lead;
    u8 second;

    if (endOffset == 0)
        return FALSE;

    startOffset = endOffset - 1;
    if (((u8)buffer[startOffset] & 0xC0) != 0x80)
        return FALSE;

    while (startOffset > 0
        && ((u8)buffer[startOffset - 1] & 0xC0) == 0x80)
        startOffset--;

    if (startOffset == 0)
        return FALSE;
    startOffset--;

    lead = (u8)buffer[startOffset];
    if (lead >= 0xC2 && lead <= 0xDF)
        scalarLength = 2;
    else if (lead >= 0xE0 && lead <= 0xEF)
        scalarLength = 3;
    else if (lead >= 0xF0 && lead <= 0xF4)
        scalarLength = 4;
    else
        return FALSE;

    if (startOffset + scalarLength != endOffset)
        return FALSE;

    for (i = startOffset + 1; i < endOffset; i++)
        if (((u8)buffer[i] & 0xC0) != 0x80)
            return FALSE;

    second = (u8)buffer[startOffset + 1];
    if ((lead == 0xE0 && second < 0xA0)
        || (lead == 0xED && second >= 0xA0)
        || (lead == 0xF0 && second < 0x90)
        || (lead == 0xF4 && second >= 0x90))
        return FALSE;

    return TRUE;
}

static void SetLocalizedMsgTerminator(char *buffer, u32 decodedLength)
{
    u32 terminatorOffset;

    if (decodedLength == 0)
        return;

    terminatorOffset = decodedLength - 1;
    while (terminatorOffset > 0 && (u8)buffer[terminatorOffset - 1] == 0x1F)
    {
        if (terminatorOffset > 1 && (u8)buffer[terminatorOffset - 2] == 0x80
            && !LocalizedMsgEndsWithUtf8Scalar(buffer, terminatorOffset - 1))
            return;

        terminatorOffset--;
        buffer[terminatorOffset] = '\0';
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
    sLastMsgStatus = status;

    if (LocalizedGameText_DecodeSucceeded(status))
        SetLocalizedMsgTerminator(buffer, decodedLength);

    return buffer;
}

static char *ResolveStringIntoUnboundedBuffer(int index, char *buffer)
{
    enum LocalizedGameTextStatus status;
    u32 decodedLength;

    if (buffer == NULL)
    {
        sLastMsgStatus = LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;
        return buffer;
    }

    if (buffer == gBufPrep)
        return ResolveStringIntoBuffer(index, buffer, (u32)sizeof(gBufPrep));

    decodedLength = 0;
    status = LocalizedGameText_ResolveCurrentToUnboundedBuffer(
        index, buffer, &decodedLength);
    sLastMsgStatus = status;
    if (LocalizedGameText_DecodeSucceeded(status))
        SetLocalizedMsgTerminator(buffer, decodedLength);
    return buffer;
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

void InsertPrefix(char * str, const char * prefix, bool capital)
{
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
}

void SetMsgTerminator(signed char * str)
{
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
        return (char *)MSG_BUFFER1;
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
    return ResolveStringIntoUnboundedBuffer(index, buffer);
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

/* These walkers deliberately remain byte-oriented: 0x80 is still treated as
 * the legacy control prefix, not as a UTF-8 continuation byte. In CJK
 * profiles the full decoded message overlays these historical scratch
 * offsets; callers must not run these walkers over long UTF-8 text until the
 * renderer sprint replaces their byte-wise semantics. */
char * StringInsertSpecialPrefixByCtrl(void)
{
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
}

char * StrInsertTact(void)
{
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
}
