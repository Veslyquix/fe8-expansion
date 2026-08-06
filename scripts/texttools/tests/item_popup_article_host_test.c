#include "global.h"

#include <stdio.h>
#include <string.h>

#include "bmitem.h"
#include "localized_game_text.h"
#include "constants/items.h"

enum
{
    TEST_MSG_TRANSLATED = 1,
    TEST_MSG_FALLBACK = 2,
    TEST_MSG_JUNAFRUIT = 3
};

static int sFailures;
static ExpansionLocaleId sLocale;
static enum LocalizedGameTextStatus sStatus;
static const char *sResolvedName;
static int sJunafruitFallback;
static char sPrefixBuffer[128];

struct ItemData gItemData[0x100];

#define CHECK(condition) do { \
    if (!(condition)) { \
        printf("FAIL: %s:%d: %s\n", __FILE__, __LINE__, #condition); \
        sFailures++; \
    } \
} while (0)

ExpansionLocaleId ExpansionLocale_GetCurrent(void)
{
    return sLocale;
}

enum LocalizedGameTextStatus LocalizedGameText_GetLastStatus(void)
{
    return sStatus;
}

static const char *GetTranslatedName(int index)
{
    if (sLocale == EXPANSION_LOCALE_JA)
    {
        if (index == TEST_MSG_TRANSLATED)
            return "\xE9\x89\x84\xE3\x81\xAE\xE5\x89\xA3";
        return "\xE3\x82\xB8\xE3\x83\xA5\xE3\x83\x8A\xE3\x81\xAE\xE5\xAE\x9F";
    }

    if (index == TEST_MSG_TRANSLATED)
        return "\xE9\x93\x81\xE5\x89\x91";
    return "\xE5\x9F\xBA\xE5\xA8\x9C\xE6\x9E\x9C";
}

char *GetStringFromIndex(int index)
{
    if (sLocale == EXPANSION_LOCALE_JA
        || sLocale == EXPANSION_LOCALE_ZH_HANS)
    {
        if (index == TEST_MSG_TRANSLATED
            || (index == TEST_MSG_JUNAFRUIT && !sJunafruitFallback))
        {
            sStatus = LOCALIZED_GAME_TEXT_STATUS_OK;
            sResolvedName = GetTranslatedName(index);
            return (char *)sResolvedName;
        }

        sStatus = LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT;
    }
    else
    {
        sStatus = LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT;
    }

    if (index == TEST_MSG_JUNAFRUIT)
        sResolvedName = "Juna Fruit";
    else if (index == TEST_MSG_FALLBACK)
        sResolvedName = "Iron Axe";
    else
        sResolvedName = "Iron Sword";

    return (char *)sResolvedName;
}

char *StrInsertTact(void)
{
    return (char *)sResolvedName;
}

char *InsertPrefix(char *str, const char *prefix, bool capital)
{
    const char *selected;

    if (prefix != NULL)
    {
        selected = prefix;
    }
    else if (str[0] == 'A' || str[0] == 'E' || str[0] == 'I'
        || str[0] == 'O' || str[0] == 'U' || str[0] == 'a'
        || str[0] == 'e' || str[0] == 'i' || str[0] == 'o'
        || str[0] == 'u')
    {
        selected = capital ? "An " : "an ";
    }
    else
    {
        selected = capital ? "A " : "a ";
    }

    strcpy(sPrefixBuffer, selected);
    strcat(sPrefixBuffer, str);
    return sPrefixBuffer;
}

static void ResetHarness(ExpansionLocaleId locale)
{
    memset(gItemData, 0, sizeof(gItemData));
    gItemData[ITEM_SWORD_IRON].nameTextId = TEST_MSG_TRANSLATED;
    gItemData[ITEM_AXE_IRON].nameTextId = TEST_MSG_FALLBACK;
    gItemData[ITEM_JUNAFRUIT].nameTextId = TEST_MSG_JUNAFRUIT;
    sLocale = locale;
    sStatus = LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID;
    sResolvedName = NULL;
    sJunafruitFallback = FALSE;
    sPrefixBuffer[0] = '\0';
}

static void CheckName(
    ExpansionLocaleId locale,
    int item,
    int capital,
    const char *expected)
{
    const char *name;

    ResetHarness(locale);
    name = GetItemNameWithArticle(item, capital);
    CHECK(strcmp(name, expected) == 0);
}

static void TestTranslatedCjkNamesHaveNoEnglishArticle(void)
{
    CheckName(
        EXPANSION_LOCALE_JA,
        ITEM_SWORD_IRON,
        TRUE,
        "\xE9\x89\x84\xE3\x81\xAE\xE5\x89\xA3");
    CheckName(
        EXPANSION_LOCALE_ZH_HANS,
        ITEM_SWORD_IRON,
        FALSE,
        "\xE9\x93\x81\xE5\x89\x91");

    ResetHarness(EXPANSION_LOCALE_JA);
    CHECK(strcmp(
        GetItemNameWithArticle(ITEM_JUNAFRUIT, TRUE),
        "\xE3\x82\xB8\xE3\x83\xA5\xE3\x83\x8A\xE3\x81\xAE\xE5\xAE\x9F")
        == 0);
    ResetHarness(EXPANSION_LOCALE_ZH_HANS);
    CHECK(strcmp(
        GetItemNameWithArticle(ITEM_JUNAFRUIT, FALSE),
        "\xE5\x9F\xBA\xE5\xA8\x9C\xE6\x9E\x9C")
        == 0);
}

static void TestEnglishFallbackKeepsEnglishGrammar(void)
{
    CheckName(
        EXPANSION_LOCALE_JA,
        ITEM_AXE_IRON,
        TRUE,
        "An Iron Axe");
    CheckName(
        EXPANSION_LOCALE_ZH_HANS,
        ITEM_AXE_IRON,
        FALSE,
        "an Iron Axe");

    ResetHarness(EXPANSION_LOCALE_JA);
    sJunafruitFallback = TRUE;
    CHECK(strcmp(
        GetItemNameWithArticle(ITEM_JUNAFRUIT, TRUE),
        "Some Juna Fruit") == 0);
    ResetHarness(EXPANSION_LOCALE_ZH_HANS);
    sJunafruitFallback = TRUE;
    CHECK(strcmp(
        GetItemNameWithArticle(ITEM_JUNAFRUIT, FALSE),
        "some Juna Fruit") == 0);
}

static void TestEnglishAndPseudoLocalesKeepPopupBehavior(void)
{
    CheckName(
        EXPANSION_LOCALE_EN,
        ITEM_SWORD_IRON,
        TRUE,
        "An Iron Sword");
    CheckName(
        EXPANSION_LOCALE_QPS_PLOC,
        ITEM_AXE_IRON,
        FALSE,
        "an Iron Axe");
    CheckName(
        EXPANSION_LOCALE_EN,
        ITEM_JUNAFRUIT,
        TRUE,
        "Some Juna Fruit");
    CheckName(
        EXPANSION_LOCALE_QPS_PLOC,
        ITEM_JUNAFRUIT,
        FALSE,
        "some Juna Fruit");
}

static void TestRepeatedCallsDoNotReusePrefixOrStatus(void)
{
    const char *name;

    ResetHarness(EXPANSION_LOCALE_JA);
    name = GetItemNameWithArticle(ITEM_AXE_IRON, TRUE);
    CHECK(strcmp(name, "An Iron Axe") == 0);
    name = GetItemNameWithArticle(ITEM_AXE_IRON, TRUE);
    CHECK(strcmp(name, "An Iron Axe") == 0);
    name = GetItemNameWithArticle(ITEM_SWORD_IRON, TRUE);
    CHECK(strcmp(
        name, "\xE9\x89\x84\xE3\x81\xAE\xE5\x89\xA3") == 0);
    name = GetItemNameWithArticle(ITEM_AXE_IRON, TRUE);
    CHECK(strcmp(name, "An Iron Axe") == 0);
}

int main(void)
{
    TestTranslatedCjkNamesHaveNoEnglishArticle();
    TestEnglishFallbackKeepsEnglishGrammar();
    TestEnglishAndPseudoLocalesKeepPopupBehavior();
    TestRepeatedCallsDoNotReusePrefixOrStatus();

    if (sFailures == 0)
    {
        puts("item_popup_article_host_test: ok");
        return 0;
    }

    printf("%d failure(s)\n", sFailures);
    return 1;
}
