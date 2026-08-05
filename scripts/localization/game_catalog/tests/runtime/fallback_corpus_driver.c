#include "global.h"

#include <stdio.h>
#include <string.h>

#include "fallback_corpus_ids.h"

char *GetStringFromIndexInBufferWithLimit(int index, char *buffer, u32 bufferCapacity);

char gBufPrep[0x2000];
struct ActionData gActionData = { 0 };
struct PlaySt gPlaySt = { {0}, {0, 0, 0, 0} };

static struct CharacterData sCharacterData = { 4 };

ExpansionLocaleId ExpansionLocale_GetCurrent(void)
{
    return EXPANSION_LOCALE_JA;
}

enum LocalizedGameTextStatus LocalizedGameText_ResolveCurrentToBuffer(
    int msgIndex,
    char *buffer,
    u32 bufferCapacity,
    u32 *outDecodedLength)
{
    (void)buffer;
    (void)bufferCapacity;

    if (outDecodedLength != NULL)
        *outDecodedLength = 0;
    if (msgIndex < 0 || (u32)msgIndex >= FE8_GAME_LOCALIZATION_TARGET_COUNT)
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;
    return LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT;
}

void CallARM_DecompText(const char *input, char *output)
{
    (void)input;
    (void)output;
}

void CopyString(void *dst, const void *src)
{
    strcpy((char *)dst, (const char *)src);
}

char *GetTacticianName(void)
{
    return "Tact";
}

char *GetItemName(int item)
{
    (void)item;
    return "Item";
}

const struct CharacterData *GetCharacterData(int id)
{
    (void)id;
    return &sCharacterData;
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
            return TRUE;

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
    static const char expectedMsg809[] = "Rennac, Rich \"Merchant\"";
    char buffer[FE8_LOCALIZED_GAME_TEXT_REQUIRED_STORAGE_BYTES];
    const char *result;
    u32 index;
    int msgId;

    if (ARRAY_COUNT(sFallbackIds) != 1828)
        return 1;

    for (index = 0; index < ARRAY_COUNT(sFallbackIds); index++)
    {
        msgId = sFallbackIds[index];
        memset(buffer, 0xA5, sizeof(buffer));
        result = GetStringFromIndexInBufferWithLimit(
            msgId, buffer, (u32)sizeof(buffer));
        if (result != buffer || !IsRendererValid((const u8 *)buffer, sizeof(buffer)))
        {
            printf(
                "invalid fallback MSG_%03X status=%d bytes=%02X %02X %02X %02X %02X\n",
                msgId,
                LocalizedGameText_GetLastStatus(),
                (u8)buffer[0],
                (u8)buffer[1],
                (u8)buffer[2],
                (u8)buffer[3],
                (u8)buffer[4]);
            return 2;
        }
    }

    result = GetStringFromIndexInBufferWithLimit(
        0x809, buffer, (u32)sizeof(buffer));
    if (strcmp(result, expectedMsg809) != 0)
        return 3;

    puts("fallback_corpus_driver: 1828 renderer-valid streams");
    return 0;
}
