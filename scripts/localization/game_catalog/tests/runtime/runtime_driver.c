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

static const u8 sEnglish0[] = "Cat\x1F";
static const u8 sEnglish1[] = "Fallback\x1F";
static const u8 sEnglish2[] = "Long English\x1F";
static const u8 sEnglish3[] = "Broken\x1F";
static const u8 sEnglish4[] = "Plain English\x1F";
static const u8 sEnglish5[] = "Space\x1F";
const u8 *const gMsgTable[] = {
    sEnglish0,
    sEnglish1,
    sEnglish2,
    sEnglish3,
    sEnglish4,
    sEnglish5,
};

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
    sArmDecompCalls++;
    strcpy(output, input);
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
    CHECK(sArmDecompCalls == 1);
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
    CHECK(sArmDecompCalls == 1);

    memset(storage, 0xA5, sizeof(storage));
    result = GetStringFromIndexInBufferWithLimit(1, (char *)(storage + 1), 8);
    CHECK(strcmp(result, "<!LOC_O") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW);
    CHECK(storage[0] == 0xA5);
    CHECK(storage[9] == 0xA5);
    CHECK(sArmDecompCalls == 2);
}

static void TestQpsFallback(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_QPS_PLOC);
    result = GetStringFromIndex(0);
    CHECK(strcmp(result, "Cat") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT);
    CHECK(sArmDecompCalls == 1);
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
    CHECK(sArmDecompCalls == 1);
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
    CHECK(sArmDecompCalls == 1);

    strcpy((char *)sMsgString.storage.localized, "stale-en");
    LocalizedGameText_InvalidateCache();
    result = GetStringFromIndex(0);
    CHECK(strcmp(result, "Cat") == 0);
    CHECK(sArmDecompCalls == 2);
}

static void TestDefaultEnglishBehavior(void)
{
    const char *result;

    ResetHarness(EXPANSION_LOCALE_EN);
    result = GetStringFromIndex(4);
    CHECK(strcmp(result, "Plain English") == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT);
    CHECK(sArmDecompCalls == 1);
}

static void TestInvalidIndicesDoNotReadEnglishTable(void)
{
    char local[32];
    const char *result;

    ResetHarness(EXPANSION_LOCALE_EN);
    result = GetStringFromIndex(6);
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_INVALID) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID);
    CHECK(sArmDecompCalls == 0);

    ResetHarness(EXPANSION_LOCALE_JA);
    result = GetStringFromIndexInBufferWithLimit(-1, local, sizeof(local));
    CHECK(strcmp(result, LOCALIZED_GAME_TEXT_MARKER_INVALID) == 0);
    CHECK(LocalizedGameText_GetLastStatus() == LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID);
    CHECK(sArmDecompCalls == 0);

    result = GetStringFromIndexInBuffer(6, local);
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
    TestAbsentFallbackHonorsBufferCapacity();
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
