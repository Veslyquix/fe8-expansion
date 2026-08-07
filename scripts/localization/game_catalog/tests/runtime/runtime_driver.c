#include "global.h"

#include <stdio.h>
#include <string.h>

#include "bmitem.h"

char *GetStringFromIndex(int index);
char *GetStringFromIndexInBufferWithLimit(int index, char *buffer, u32 bufferCapacity);
char *GetStringFromIndexInBuffer(int index, char *buffer);
char *StringInsertSpecialPrefixByCtrl(void);
char *StrInsertTact(void);
char *InsertPrefix(char *str, const char *prefix, bool capital);
extern struct MsgBuffer sMsgString;

static int failures = 0;
static int sArmDecompCalls = 0;
static ExpansionLocaleId sCurrentLocale = EXPANSION_LOCALE_EN;
static struct CharacterData sCharacterData = { 15 };
static struct ItemData sItemData = { 18 };
static const char *sTacticianNameOverride;

char gBufPrep[0x2000];
struct ActionData gActionData = { 0 };
struct PlaySt gPlaySt = { {0}, {0, 0, 0, 0} };

#define CHECK(cond) do { if (!(cond)) { \
    printf("FAIL: %s:%d: %s\n", __FILE__, __LINE__, #cond); \
    failures++; \
} } while (0)

struct RuntimeSupportScreenUnit
{
    u8 charId;
    u8 classId;
    u8 supportLevel[7];
    u8 partnerClassId[7];
    s8 partnerIsAlive[7];
};

static u8 sPrepGuardSnapshot[sizeof(gBufPrep)];

static void SeedSupportScreenRecords(void)
{
    struct RuntimeSupportScreenUnit *units;
    u32 i;
    u32 j;

    memset(gBufPrep, 0xA5, sizeof(gBufPrep));
    units = (struct RuntimeSupportScreenUnit *)gBufPrep;
    for (i = 0; i < 16; i++)
    {
        units[i].charId = (u8)(0x20 + i);
        units[i].classId = (u8)(0x40 + i);
        for (j = 0; j < 7; j++)
        {
            units[i].supportLevel[j] = (u8)(i + j);
            units[i].partnerClassId[j] = (u8)(0x60 + i + j);
            units[i].partnerIsAlive[j] = (s8)(j - 3);
        }
    }
    memcpy(sPrepGuardSnapshot, gBufPrep, sizeof(gBufPrep));
}

static void CheckSupportScreenRecordsUnchanged(void)
{
    CHECK(memcmp(
        gBufPrep, sPrepGuardSnapshot, sizeof(gBufPrep)) == 0);
}

ExpansionLocaleId ExpansionLocale_GetCurrent(void)
{
    return sCurrentLocale;
}

void CallARM_DecompText(const char *input, char *output)
{
#if 0
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
#endif
    sArmDecompCalls++;
    (void)input;
    (void)output;
}

void CopyString(void *dst, const void *src)
{
    strcpy((char *)dst, (const char *)src);
}

char *GetTacticianName(void)
{
    if (sTacticianNameOverride != NULL)
        return (char *)sTacticianNameOverride;
    if (sCurrentLocale == EXPANSION_LOCALE_JA)
        return "\xE8\xBB\x8D\xE5\xB8\xAB";
    if (sCurrentLocale == EXPANSION_LOCALE_ZH_HANS)
        return "\xE5\x86\x9B\xE5\xB8\x88";
    return "Tact";
}

char *GetItemName(int item)
{
    (void)item;
    if (sCurrentLocale == EXPANSION_LOCALE_JA)
        return "\xE5\x89\xA3";
    if (sCurrentLocale == EXPANSION_LOCALE_ZH_HANS)
        return "\xE5\x89\x91";
    return "Item";
}

int GetItemIndex(int item)
{
    return item;
}

const struct ItemData *GetItemData(int item)
{
    (void)item;
    return &sItemData;
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
    sTacticianNameOverride = NULL;
    sCharacterData.nameTextId = 15;
    sItemData.nameTextId = 18;
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

static void TestPresentDecodeViaBoundedPrepBuffer(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndexInBufferWithLimit(
        0, gBufPrep, (u32)sizeof(gBufPrep));
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

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndexInBufferWithLimit(
        9, gBufPrep, (u32)sizeof(gBufPrep));
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_CORRUPT) == 0);
    CHECK(
        LocalizedGameText_GetLastStatus()
        == LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT);
    CHECK(sArmDecompCalls == 0);
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
    static const u8 normalizedBytes[] = {
        'A', '-', 'B', 'e', 'C', 0xE3, 0x80, 0x80, 'D', 0
    };
    const char *result;

    ResetHarness(EXPANSION_LOCALE_QPS_PLOC);
    result = GetStringFromIndex(0);
    CHECK(strcmp(result, "Cat") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT);
    CHECK(sArmDecompCalls == 0);

    result = GetStringFromIndexInBufferWithLimit(
        7, gBufPrep, (u32)sizeof(gBufPrep));
    CHECK(memcmp(result, normalizedBytes, sizeof(normalizedBytes)) == 0);
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
    memset(local, 0xA5, sizeof(local));
    result = GetStringFromIndexInBuffer(0, local);
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_UNBOUNDED) == 0);
    CHECK(
        LocalizedGameText_GetLastStatus()
        == LOCALIZED_GAME_TEXT_STATUS_LEGACY_BUFFER_UNBOUNDED);
    CHECK((u8)local[0] == 0xA5);
    CHECK(sArmDecompCalls == 0);
}

static void TestUtf8ControlSubstitutions(void)
{
    static const u8 expected[] = {
        0xE5, 0x80, 0x99,
        0xE8, 0xBB, 0x8D, 0xE5, 0xB8, 0xAB,
        0xE7, 0x8C, 0xAB,
        0xE5, 0x89, 0xA3,
        0xE8, 0x89, 0xBE, 0xE8, 0x8E, 0x89,
        0x10, 0x93, 0x94,
        0
    };
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    GetStringFromIndex(13);
    result = StringInsertSpecialPrefixByCtrl();
    CHECK(memcmp(result, expected, sizeof(expected)) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_OK);
}

static void TestTactSubstitutionKeepsUtf8Boundaries(void)
{
    static const u8 expected[] = {
        0xE8, 0xA8, 0xBA,
        0xE8, 0xBB, 0x8D, 0xE5, 0xB8, 0xAB,
        0
    };
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    GetStringFromIndex(14);
    result = StrInsertTact();
    CHECK(memcmp(result, expected, sizeof(expected)) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_OK);
}

static void TestDerivedTextDoesNotMutateActiveCache(void)
{
    static const char tactOne[] = "\xE7\x94\xB2";
    static const char tactTwo[] = "\xE4\xB9\x99";
    const char *active;
    const char *derived;
    const char *prefixed;

    ResetHarness(EXPANSION_LOCALE_JA);
    active = GetStringFromIndex(14);
    CHECK(active == (const char *)sMsgString.storage.localized);

    sTacticianNameOverride = tactOne;
    derived = StrInsertTact();
    CHECK(strcmp(derived, "\xE8\xA8\xBA\xE7\x94\xB2") == 0);
    CHECK(derived != gBufPrep);
    CHECK(active == GetStringFromIndex(14));
    CHECK(memcmp(active, "\xE8\xA8\xBA\x80\x20\x00", 6) == 0);

    sTacticianNameOverride = tactTwo;
    derived = StrInsertTact();
    CHECK(strcmp(derived, "\xE8\xA8\xBA\xE4\xB9\x99") == 0);
    CHECK(active == GetStringFromIndex(14));
    CHECK(memcmp(active, "\xE8\xA8\xBA\x80\x20\x00", 6) == 0);

    active = GetStringFromIndex(18);
    prefixed = InsertPrefix((char *)active, "Pre-", FALSE);
    CHECK(strcmp(prefixed, "Pre-\xE5\x89\xA3") == 0);
    CHECK(prefixed != gBufPrep);
    CHECK(strcmp(active, "\xE5\x89\xA3") == 0);
    CHECK(active == GetStringFromIndex(18));
    CHECK(strcmp(active, "\xE5\x89\xA3") == 0);

    prefixed = InsertPrefix((char *)active, "Pre-", FALSE);
    CHECK(strcmp(prefixed, "Pre-\xE5\x89\xA3") == 0);
    CHECK(strcmp(active, "\xE5\x89\xA3") == 0);
}

static void TestHelpBoxTransformsPreserveSupportScreenRecords(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    SeedSupportScreenRecords();

    GetStringFromIndex(13);
    result = StringInsertSpecialPrefixByCtrl();
    CHECK(strstr(result, "\xE8\xBB\x8D\xE5\xB8\xAB") != NULL);
    CheckSupportScreenRecordsUnchanged();

    GetStringFromIndex(14);
    result = StrInsertTact();
    CHECK(strcmp(result, "\xE8\xA8\xBA\xE8\xBB\x8D\xE5\xB8\xAB") == 0);
    CheckSupportScreenRecordsUnchanged();

    result = GetStringFromIndex(18);
    result = InsertPrefix((char *)result, "Pre-", FALSE);
    CHECK(strcmp(result, "Pre-\xE5\x89\xA3") == 0);
    CheckSupportScreenRecordsUnchanged();
}

static void TestRepeatedDynamicSpecialSubstitutions(void)
{
    static const char tactOne[] = "\xE7\x94\xB2";
    static const char tactTwo[] = "\xE4\xB9\x99";
    const char *active;
    const char *derived;

    ResetHarness(EXPANSION_LOCALE_JA);
    active = GetStringFromIndex(13);
    sTacticianNameOverride = tactOne;
    derived = StringInsertSpecialPrefixByCtrl();
    CHECK(strstr(derived, tactOne) != NULL);
    CHECK(strstr(derived, "\xE5\x89\xA3") != NULL);
    CHECK(active == GetStringFromIndex(13));

    sTacticianNameOverride = tactTwo;
    sItemData.nameTextId = 0;
    derived = StringInsertSpecialPrefixByCtrl();
    CHECK(strstr(derived, tactTwo) != NULL);
    CHECK(strstr(derived, "\xE5\x89\xA3") == NULL);
    CHECK(active == GetStringFromIndex(13));
    CHECK(memcmp(active, "\xE5\x80\x99\x80\x20", 5) == 0);
}

static void TestSubstitutionCapacityBoundary(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_JA);
    GetStringFromIndex(16);
    result = StrInsertTact();
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_OVERFLOW) == 0);
    CHECK(
        LocalizedGameText_GetLastStatus()
        == LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);

    ResetHarness(EXPANSION_LOCALE_JA);
    GetStringFromIndex(17);
    result = StrInsertTact();
    CHECK(strlen(result) == 1023u);
    CHECK(memcmp(result + 1020, "\xE7\x8C\xAB", 3) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_OK);
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
    static const u8 normalizedBytes[] = {
        'A', '-', 'B', 'e', 'C', 0xE3, 0x80, 0x80, 'D', 0
    };
    const char *result;

    ResetHarness(EXPANSION_LOCALE_EN);
    result = GetStringFromIndex(4);
    CHECK(strcmp(result, "Plain English") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT);
    CHECK(sArmDecompCalls == 0);

    result = GetStringFromIndexInBufferWithLimit(
        7, gBufPrep, (u32)sizeof(gBufPrep));
    CHECK(memcmp(result, normalizedBytes, sizeof(normalizedBytes)) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT);
    CHECK(sArmDecompCalls == 0);
}

static void TestInvalidIndicesDoNotReadEnglishTable(void)
{
    char local[32];
    const char *result;

    ResetHarness(EXPANSION_LOCALE_EN);
    result = GetStringFromIndex(19);
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_INVALID) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID);
    CHECK(sArmDecompCalls == 0);

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndexInBufferWithLimit(-1, local, sizeof(local));
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_INVALID) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID);
    CHECK(sArmDecompCalls == 0);

    result = GetStringFromIndexInBuffer(19, local);
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_UNBOUNDED) == 0);
    CHECK(
        LocalizedGameText_GetLastStatus()
        == LOCALIZED_GAME_TEXT_STATUS_LEGACY_BUFFER_UNBOUNDED);
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
    TestPresentDecodeViaBoundedPrepBuffer();
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
    TestUtf8ControlSubstitutions();
    TestTactSubstitutionKeepsUtf8Boundaries();
    TestDerivedTextDoesNotMutateActiveCache();
    TestHelpBoxTransformsPreserveSupportScreenRecords();
    TestRepeatedDynamicSpecialSubstitutions();
    TestSubstitutionCapacityBoundary();
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
