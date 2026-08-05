#include "global.h"

#include <stdio.h>
#include <string.h>

char *GetStringFromIndex(int index);
char *GetStringFromIndexInBufferWithLimit(int index, char *buffer, u32 bufferCapacity);
char *GetStringFromIndexInBuffer(int index, char *buffer);
extern struct MsgBuffer sMsgString;

static int failures = 0;
static int sArmDecompCalls = 0;
static ExpansionLocaleId sCurrentLocale = EXPANSION_LOCALE_EN;
static struct CharacterData sCharacterData = { 4 };

char gBufPrep[0x2000];
struct ActionData gActionData = { 0 };
struct PlaySt gPlaySt = { {0}, {0, 0, 0, 0} };

#define CHECK(cond) do { if (!(cond)) { \
    printf("FAIL: %s:%d: %s\n", __FILE__, __LINE__, #cond); \
    failures++; \
} } while (0)

ExpansionLocaleId ExpansionLocale_GetCurrent(void)
{
    return sCurrentLocale;
}

void CallARM_DecompText(const char *input, char *output)
{
    const u8 *source;
    const u32 *current;
    u32 inputByteIndex;
    u32 bitIndex;
    u32 node;
    u32 childIndex;
    u32 symbol;
    u8 inputByte;

    sArmDecompCalls++;
    source = (const u8 *)input;
    current = gMsgHuffmanTableRoot;
    inputByteIndex = 0;
    bitIndex = 8;
    inputByte = 0;

    for (;;)
    {
        node = *current;
        if (bitIndex == 8)
        {
            inputByte = source[inputByteIndex++];
            bitIndex = 0;
        }

        if ((inputByte >> bitIndex) & 1)
            childIndex = (node >> 16) & 0xFFFF;
        else
            childIndex = node & 0xFFFF;
        bitIndex++;

        current = &gMsgHuffmanTable[childIndex];
        node = *current;
        if ((node & 0xFFFF0000u) != 0xFFFF0000u)
            continue;

        symbol = node & 0xFFFF;
        *output++ = symbol & 0xFF;
        if ((symbol >> 8) & 0xFF)
            *output++ = (symbol >> 8) & 0xFF;
        else if ((symbol & 0xFF) == 0)
            return;

        current = gMsgHuffmanTableRoot;
    }
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

static void ResetHarness(ExpansionLocaleId locale)
{
    memset(&sMsgString, 0, sizeof(sMsgString));
    memset(gBufPrep, 0, sizeof(gBufPrep));
    sCurrentLocale = locale;
    sArmDecompCalls = 0;
    LocalizedGameText_InvalidateCache();
}

static void TestPresentDecode(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndex(0);
    CHECK(strcmp(result, "猫") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_OK);
    CHECK(sArmDecompCalls == 0);
}

static void TestPresentDecodeViaKnownLegacyPrepBuffer(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndexInBuffer(0, gBufPrep);
    CHECK(strcmp(result, "猫") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_OK);
    CHECK(sArmDecompCalls == 0);
}

static void TestAbsentFallback(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndex(1);
    CHECK(strcmp(result, "Fallback") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT);
    CHECK(sArmDecompCalls == 0);
}

static void TestLegacyGlyphFallbackNormalization(void)
{
    static const u8 expectedQuote[] = {
        'R', 'e', 'n', 'n', 'a', 'c', ',', ' ', 'R', 'i', 'c', 'h', ' ',
        '"', 'M', 'e', 'r', 'c', 'h', 'a', 'n', 't', '"', 0
    };
    static const u8 expectedLegacy[] = {
        'A', '-', 'B', 'e', 'C', 0xE3, 0x80, 0x80, 'D', 0
    };
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndex(6);
    CHECK(memcmp(result, expectedQuote, sizeof(expectedQuote)) == 0);
    CHECK(
        LocalizedGameText_GetLastStatus()
        == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT);

    result = GetStringFromIndexInBufferWithLimit(
        7, gBufPrep, (u32)sizeof(gBufPrep));
    CHECK(memcmp(result, expectedLegacy, sizeof(expectedLegacy)) == 0);
    CHECK(
        LocalizedGameText_GetLastStatus()
        == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT);
    CHECK(sArmDecompCalls == 0);
}

static void TestFallbackControlsAndFaceIdsRemainExact(void)
{
    static const u8 expected[] = {0x10, 0x93, 0x94, 0x80, 0xE9, 'X', 0};
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndexInBufferWithLimit(
        8, gBufPrep, (u32)sizeof(gBufPrep));
    CHECK(memcmp(result, expected, sizeof(expected)) == 0);
    CHECK(
        LocalizedGameText_GetLastStatus()
        == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT);
    CHECK(sArmDecompCalls == 0);
}

static void TestMalformedFallbackStreamsFailVisibly(void)
{
    const char *result;
    int index;

    for (index = 9; index <= 12; index++)
    {
        ResetHarness(EXPANSION_LOCALE_JA);
        result = GetStringFromIndexInBufferWithLimit(
            index, gBufPrep, (u32)sizeof(gBufPrep));
        CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_CORRUPT) == 0);
        CHECK(
            LocalizedGameText_GetLastStatus()
            == LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT);
        CHECK(sArmDecompCalls == 0);
    }
}

static void TestAbsentFallbackHonorsBufferCapacity(void)
{
    u8 storage[18];
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    memset(storage, 0xA5, sizeof(storage));
    result = GetStringFromIndexInBufferWithLimit(1, (char *)(storage + 1), 16);
    CHECK(strcmp(result, "Fallback") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT);
    CHECK(storage[0] == 0xA5);
    CHECK(storage[17] == 0xA5);
    CHECK(sArmDecompCalls == 0);

    memset(storage, 0xA5, sizeof(storage));
    result = GetStringFromIndexInBufferWithLimit(1, (char *)(storage + 1), 8);
    CHECK(strcmp(result, "<!LOC_O") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);
    CHECK(storage[0] == 0xA5);
    CHECK(storage[9] == 0xA5);
    CHECK(sArmDecompCalls == 0);
}

static void TestNormalizedFallbackOverflowIsVisible(void)
{
    u8 storage[12];
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    memset(storage, 0xA5, sizeof(storage));
    result = GetStringFromIndexInBufferWithLimit(7, (char *)(storage + 1), 9);
    CHECK(strcmp(result, "<!LOC_OV") == 0);
    CHECK(
        LocalizedGameText_GetLastStatus()
        == LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);
    CHECK(storage[0] == 0xA5);
    CHECK(storage[10] == 0xA5);
    CHECK(storage[11] == 0xA5);
    CHECK(sArmDecompCalls == 0);
}

static void TestInBufferPreservesActivePointer(void)
{
    char local[32];
    const char *active;
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    active = GetStringFromIndex(0);
    CHECK(strcmp(active, "猫") == 0);

    result = GetStringFromIndexInBufferWithLimit(1, local, sizeof(local));
    CHECK(strcmp(result, "Fallback") == 0);
    CHECK(strcmp(active, "猫") == 0);
    CHECK(GetStringFromIndex(0) == active);
    CHECK(strcmp(active, "猫") == 0);
    CHECK(sArmDecompCalls == 0);
}

static void TestNormalizedFallbackCacheSurvivesInBuffer(void)
{
    char local[32];
    const char *active;
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    active = GetStringFromIndex(6);
    CHECK(strcmp(active, "Rennac, Rich \"Merchant\"") == 0);

    result = GetStringFromIndexInBufferWithLimit(7, local, sizeof(local));
    CHECK(strcmp(result, "A-BeC\xE3\x80\x80" "D") == 0);
    CHECK(GetStringFromIndex(6) == active);
    CHECK(strcmp(active, "Rennac, Rich \"Merchant\"") == 0);
    CHECK(sArmDecompCalls == 0);
}

static void TestQpsFallback(void)
{
    static const u8 legacyBytes[] = {
        'A', 0x7F, 'B', 0xE9, 'C', 0x81, 0x40, 'D', 0
    };
    const char *result;

    ResetHarness(EXPANSION_LOCALE_QPS_PLOC);
    result = GetStringFromIndex(0);
    CHECK(strcmp(result, "Cat") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT);
    CHECK(sArmDecompCalls == 0);

    result = GetStringFromIndexInBufferWithLimit(
        7, gBufPrep, (u32)sizeof(gBufPrep));
    CHECK(memcmp(result, legacyBytes, sizeof(legacyBytes)) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT);
    CHECK(sArmDecompCalls == 0);
}

static void TestUnpopulatedFallback(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_ZH_HANS);
    result = GetStringFromIndex(0);
    CHECK(strcmp(result, "Cat") == 0);
    CHECK(
        LocalizedGameText_GetLastStatus()
        == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_UNPOPULATED);
    CHECK(sArmDecompCalls == 0);

    result = GetStringFromIndex(6);
    CHECK(strcmp(result, "Rennac, Rich \"Merchant\"") == 0);
    CHECK(
        LocalizedGameText_GetLastStatus()
        == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_UNPOPULATED);
    CHECK(sArmDecompCalls == 0);
}

static void TestCorruptMarker(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndex(3);
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_CORRUPT) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT);
    CHECK(sArmDecompCalls == 0);
}

static void TestOverflowMarkerAndGuards(void)
{
    u8 storage[18];
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    memset(storage, 0xA5, sizeof(storage));
    result = GetStringFromIndexInBufferWithLimit(2, (char *)(storage + 1), 16);
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_OVERFLOW) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);
    CHECK(storage[0] == 0xA5);
    CHECK(storage[17] == 0xA5);
    CHECK(sArmDecompCalls == 0);
}

static void TestLegacyUnknownBufferStatus(void)
{
    char local[32];
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndexInBuffer(0, local);
    CHECK(strcmp(result, "Cat") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_LEGACY_BUFFER_UNBOUNDED);
    CHECK(sArmDecompCalls == 1);
}

static void TestCacheLocaleSwitchAndExplicitInvalidation(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndex(0);
    CHECK(strcmp(result, "猫") == 0);
    CHECK(sArmDecompCalls == 0);

    strcpy((char *)sMsgString.storage.localized, "stale-ja");
    sCurrentLocale = EXPANSION_LOCALE_EN;
    result = GetStringFromIndex(0);
    CHECK(strcmp(result, "Cat") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT);
    CHECK(sArmDecompCalls == 0);

    strcpy((char *)sMsgString.storage.localized, "stale-en");
    LocalizedGameText_InvalidateCache();
    result = GetStringFromIndex(0);
    CHECK(strcmp(result, "Cat") == 0);
    CHECK(sArmDecompCalls == 0);
}

static void TestDefaultEnglishBehavior(void)
{
    static const u8 legacyBytes[] = {
        'A', 0x7F, 'B', 0xE9, 'C', 0x81, 0x40, 'D', 0
    };
    const char *result;

    ResetHarness(EXPANSION_LOCALE_EN);
    result = GetStringFromIndex(4);
    CHECK(strcmp(result, "Plain English") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT);
    CHECK(sArmDecompCalls == 0);

    result = GetStringFromIndexInBufferWithLimit(
        7, gBufPrep, (u32)sizeof(gBufPrep));
    CHECK(memcmp(result, legacyBytes, sizeof(legacyBytes)) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT);
    CHECK(sArmDecompCalls == 0);
}

static void TestInvalidIndicesDoNotReadEnglishTable(void)
{
    char local[32];
    const char *result;

    ResetHarness(EXPANSION_LOCALE_EN);
    result = GetStringFromIndex(13);
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_INVALID) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID);
    CHECK(sArmDecompCalls == 0);

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndexInBufferWithLimit(-1, local, sizeof(local));
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_INVALID) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID);
    CHECK(sArmDecompCalls == 0);

    result = GetStringFromIndexInBuffer(13, local);
    CHECK(strcmp(result, "") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID);
    CHECK(sArmDecompCalls == 0);
}

static void TestUtf8ContinuationTailIsBounded(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndex(5);
    CHECK(strcmp(result, "\xE3\x80\x80") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_OK);
    CHECK(sArmDecompCalls == 0);
}

int main(void)
{
    TestPresentDecode();
    TestPresentDecodeViaKnownLegacyPrepBuffer();
    TestAbsentFallback();
    TestLegacyGlyphFallbackNormalization();
    TestFallbackControlsAndFaceIdsRemainExact();
    TestMalformedFallbackStreamsFailVisibly();
    TestAbsentFallbackHonorsBufferCapacity();
    TestNormalizedFallbackOverflowIsVisible();
    TestInBufferPreservesActivePointer();
    TestNormalizedFallbackCacheSurvivesInBuffer();
    TestQpsFallback();
    TestUnpopulatedFallback();
    TestCorruptMarker();
    TestOverflowMarkerAndGuards();
    TestLegacyUnknownBufferStatus();
    TestCacheLocaleSwitchAndExplicitInvalidation();
    TestDefaultEnglishBehavior();
    TestInvalidIndicesDoNotReadEnglishTable();
    TestUtf8ContinuationTailIsBounded();

    if (failures == 0)
    {
        puts("localized_game_text_runtime_driver: ok");
        return 0;
    }

    printf("%d failure(s)\n", failures);
    return 1;
}
