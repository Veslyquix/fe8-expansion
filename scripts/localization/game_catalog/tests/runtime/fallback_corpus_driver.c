#include "global.h"

#include <stdio.h>
#include <string.h>

#include "fallback_corpus_ids.h"
#include "game_localization_catalog.h"
#include "localized_text_codec.h"

ExpansionLocaleId ExpansionLocale_GetCurrent(void)
{
    return EXPANSION_LOCALE_JA;
}

static int IsContinuation(u8 byte)
{
    return byte >= 0x80 && byte <= 0xBF;
}

static int IsRendererValid(const u8 *text, u32 capacity)
{
    u32 index;
    u32 length;
    u8 first;
    u8 second;

    index = 0;
    while (index < capacity)
    {
        first = text[index];
        if (first == 0)
            return index + 1 == capacity;

        if (first < 0x20)
        {
            length = first == 0x10 ? 3 : 1;
            if (length > capacity - index)
                return FALSE;
            if (first == 0x10
                && (text[index + 1] == 0 || text[index + 2] == 0))
                return FALSE;
            index += length;
            continue;
        }

        if (first < 0x7F)
        {
            index++;
            continue;
        }
        if (first == 0x7F)
            return FALSE;

        if (first == 0x80)
        {
            if (index + 1 >= capacity || text[index + 1] == 0)
                return FALSE;
            index += 2;
            continue;
        }

        if (first >= 0xC2 && first <= 0xDF)
            length = 2;
        else if (first >= 0xE0 && first <= 0xEF)
            length = 3;
        else if (first >= 0xF0 && first <= 0xF4)
            length = 4;
        else
            return FALSE;

        if (length > capacity - index)
            return FALSE;
        if (!IsContinuation(text[index + 1]))
            return FALSE;
        if (length >= 3 && !IsContinuation(text[index + 2]))
            return FALSE;
        if (length == 4 && !IsContinuation(text[index + 3]))
            return FALSE;

        second = text[index + 1];
        if ((first == 0xE0 && second < 0xA0)
            || (first == 0xED && second >= 0xA0)
            || (first == 0xF0 && second < 0x90)
            || (first == 0xF4 && second >= 0x90))
            return FALSE;

        index += length;
    }

    return FALSE;
}

int main(void)
{
    char actual[FE8_LOCALIZED_GAME_TEXT_REQUIRED_STORAGE_BYTES];
    char expected[FE8_LOCALIZED_GAME_TEXT_REQUIRED_STORAGE_BYTES];
    const struct GameLocalizationCatalogEntry *entry;
    enum LocalizedGameTextStatus status;
    enum LocalizedTextCodecStatus codecStatus;
    u32 actualLength;
    u32 expectedLength;
    u32 index;
    int msgId;

    if (ARRAY_COUNT(sFallbackIds) != 1806)
        return 1;

    for (index = 0; index < ARRAY_COUNT(sFallbackIds); index++)
    {
        msgId = sFallbackIds[index];
        memset(actual, 0xA5, sizeof(actual));
        memset(expected, 0x5A, sizeof(expected));
        actualLength = 0;
        expectedLength = 0;

        status = LocalizedGameText_ResolveCurrentToBuffer(
            msgId, actual, (u32)sizeof(actual), &actualLength);
        if (status != LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT)
        {
            printf("fallback status MSG_%03X=%d\n", msgId, status);
            return 2;
        }

        entry = &gGameLocalizationEnglishEntries[msgId];
        codecStatus = LocalizedTextCodec_Decode(
            gGameLocalizationEnglishCatalog.nodes,
            gGameLocalizationEnglishCatalog.nodeCount,
            gGameLocalizationEnglishCatalog.rootIndex,
            entry->data,
            entry->compressedSize,
            entry->bitLength,
            (u8 *)expected,
            (u32)sizeof(expected),
            &expectedLength);
        if (codecStatus != LOCALIZED_TEXT_CODEC_OK)
        {
            printf("English decode MSG_%03X=%d\n", msgId, codecStatus);
            return 3;
        }

        if (actualLength != expectedLength
            || memcmp(actual, expected, actualLength) != 0)
        {
            printf("fallback mismatch MSG_%03X\n", msgId);
            return 4;
        }
        if (!IsRendererValid((const u8 *)actual, actualLength))
        {
            printf("invalid renderer stream MSG_%03X\n", msgId);
            return 5;
        }
    }

    puts("fallback_corpus_driver: 1806 exact shared-English streams");
    return 0;
}
