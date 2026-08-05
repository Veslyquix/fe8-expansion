#include "global.h"

#include "localized_game_text.h"

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED

#include "game_localization_catalog.h"
#include "localized_text_codec.h"

static int LocalizedGameText_UsesCjkCatalog(ExpansionLocaleId locale)
{
    return locale == EXPANSION_LOCALE_JA || locale == EXPANSION_LOCALE_ZH_HANS;
}

static void LocalizedGameText_WriteMarker(
    char *buffer,
    u32 bufferCapacity,
    const char *marker,
    u32 *outDecodedLength)
{
    u32 i;

    if (outDecodedLength != 0)
        *outDecodedLength = 0;

    if (buffer == 0 || bufferCapacity == 0)
        return;

    i = 0;
    while (i + 1 < bufferCapacity && marker[i] != '\0')
    {
        buffer[i] = marker[i];
        i++;
    }

    buffer[i] = '\0';
    if (outDecodedLength != 0)
        *outDecodedLength = i + 1;
}

static const struct GameLocalizationLocaleCatalog *LocalizedGameText_GetCatalog(
    ExpansionLocaleId locale)
{
    const struct GameLocalizationLocaleCatalog *catalog;
    u32 catalogIndex;

    if (!LocalizedGameText_UsesCjkCatalog(locale))
        return 0;

    if (locale == EXPANSION_LOCALE_JA)
        catalogIndex = GAME_LOCALIZATION_LOCALE_JA;
    else
        catalogIndex = GAME_LOCALIZATION_LOCALE_ZH_HANS;

    catalog = gGameLocalizationCatalogs[catalogIndex];
    if (catalog == 0 || catalog->entries == 0 || catalog->entryCount == 0)
        return 0;

    return catalog;
}

static enum LocalizedGameTextStatus LocalizedGameText_MapCodecStatus(
    enum LocalizedTextCodecStatus status)
{
    switch (status)
    {
    case LOCALIZED_TEXT_CODEC_OK:
        return LOCALIZED_GAME_TEXT_STATUS_OK;

    case LOCALIZED_TEXT_CODEC_OUTPUT_OVERFLOW:
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW;

    case LOCALIZED_TEXT_CODEC_INVALID_ARGUMENT:
    case LOCALIZED_TEXT_CODEC_INVALID_ROOT:
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;

    case LOCALIZED_TEXT_CODEC_INVALID_NODE:
    case LOCALIZED_TEXT_CODEC_INVALID_SYMBOL:
    case LOCALIZED_TEXT_CODEC_TRUNCATED_INPUT:
    case LOCALIZED_TEXT_CODEC_MISSING_TERMINATOR:
    default:
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT;
    }
}

enum LocalizedGameTextStatus LocalizedGameText_ResolveCurrentToBuffer(
    int msgIndex,
    char *buffer,
    u32 bufferCapacity,
    u32 *outDecodedLength)
{
    ExpansionLocaleId locale;
    const struct GameLocalizationLocaleCatalog *catalog;
    const struct GameLocalizationCatalogEntry *entry;
    enum LocalizedTextCodecStatus codecStatus;
    enum LocalizedGameTextStatus mappedStatus;
    u32 localDecodedLength;
    u32 *decodedLengthOut;

    if (outDecodedLength != 0)
        *outDecodedLength = 0;

    if (msgIndex < 0 || (u32)msgIndex >= FE8_GAME_LOCALIZATION_TARGET_COUNT)
    {
        LocalizedGameText_WriteMarker(
            buffer, bufferCapacity, LOCALIZED_GAME_TEXT_MARKER_INVALID, outDecodedLength);
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;
    }

    locale = ExpansionLocale_GetCurrent();
    if (!LocalizedGameText_UsesCjkCatalog(locale))
        return LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT;

    catalog = LocalizedGameText_GetCatalog(locale);
    if (catalog == 0)
        return LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_UNPOPULATED;

    if (buffer == 0 || bufferCapacity == 0)
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;

    if ((u32)msgIndex >= catalog->entryCount)
        return LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT;

    entry = &catalog->entries[msgIndex];
    if (!entry->present || entry->data == 0)
        return LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT;

    if (entry->compressedSize == 0 || entry->bitLength == 0
        || entry->maxDecodedBytes == 0 || catalog->nodes == 0
        || catalog->nodeCount == 0 || catalog->rootIndex >= catalog->nodeCount)
    {
        LocalizedGameText_WriteMarker(
            buffer, bufferCapacity, LOCALIZED_GAME_TEXT_MARKER_INVALID, outDecodedLength);
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;
    }

    if (entry->maxDecodedBytes > bufferCapacity)
    {
        LocalizedGameText_WriteMarker(
            buffer, bufferCapacity, LOCALIZED_GAME_TEXT_MARKER_OVERFLOW, outDecodedLength);
        return LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW;
    }

    decodedLengthOut = outDecodedLength;
    if (decodedLengthOut == 0)
        decodedLengthOut = &localDecodedLength;

    codecStatus = LocalizedTextCodec_Decode(
        catalog->nodes,
        catalog->nodeCount,
        catalog->rootIndex,
        entry->data,
        entry->compressedSize,
        entry->bitLength,
        (u8 *)buffer,
        bufferCapacity,
        decodedLengthOut);

    mappedStatus = LocalizedGameText_MapCodecStatus(codecStatus);
    if (mappedStatus == LOCALIZED_GAME_TEXT_STATUS_OK)
        return mappedStatus;

    if (mappedStatus == LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW)
    {
        LocalizedGameText_WriteMarker(
            buffer, bufferCapacity, LOCALIZED_GAME_TEXT_MARKER_OVERFLOW, outDecodedLength);
        return mappedStatus;
    }

    if (mappedStatus == LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT)
    {
        LocalizedGameText_WriteMarker(
            buffer, bufferCapacity, LOCALIZED_GAME_TEXT_MARKER_CORRUPT, outDecodedLength);
        return mappedStatus;
    }

    LocalizedGameText_WriteMarker(
        buffer, bufferCapacity, LOCALIZED_GAME_TEXT_MARKER_INVALID, outDecodedLength);
    return mappedStatus;
}

#endif /* FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED */
