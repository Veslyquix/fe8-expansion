#include "global.h"

#include <stdio.h>
#include <string.h>

#include "bmsave.h"
#include "classchg.h"
#include "classdisplayfont.h"
#include "fontgrp.h"
#include "opinfo.h"
#include "sio.h"
#include "text_utf8.h"

void ClassStatsDisplay_Init(struct OpInfoGaugeDrawProc *proc);
void ClassStatsDisplay_Loop(struct OpInfoGaugeDrawProc *proc);
int Tactician_TestTokensEqual(const char *left, const char *right);

static int sFailures;
static const char *sClassName;
static ExpansionLocaleId sLocale;
static u32 sLastResolveCapacity;
static int sResolveCalls;
static int sClassDisplayFontCalls;
static int sTextDrawCharacterCalls;
static int sTextDrawStringCalls;
static int sLastTextWidth;
static char sLastDrawnText[128];
static struct MultiArenaSaveBlock sArenaSave;
static struct ClassData sClassData;

u16 gBG0TilemapBuffer[32 * 32];
u16 gBG1TilemapBuffer[32 * 32];
u16 gBG2TilemapBuffer[32 * 32];
u16 gBG3TilemapBuffer[32 * 32];
struct Text Text_0;
struct Text Texts_1[10];
u8 Img_ClassReelFont[1];
u8 Pal_ClassReelFont[1];

#define CHECK(condition) do { \
    if (!(condition)) { \
        printf("FAIL: %s:%d: %s\n", __FILE__, __LINE__, #condition); \
        sFailures++; \
    } \
} while (0)

static int IsValidUtf8Name(const char *name)
{
    struct TextUtf8Token token;
    const char *cursor;
    const char *next;

    cursor = name;
    for (;;)
    {
        next = TextUtf8_Next(cursor, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
            return TRUE;
        if (token.kind != TEXT_UTF8_TOKEN_SCALAR || next == cursor)
            return FALSE;
        cursor = next;
    }
}

ExpansionLocaleId ExpansionLocale_GetCurrent(void)
{
    return sLocale;
}

const struct ClassData *GetClassData(int classId)
{
    (void)classId;
    return &sClassData;
}

char *GetStringFromIndex(int index)
{
    (void)index;
    return (char *)sClassName;
}

char *GetStringFromIndexInBufferWithLimit(
    int index,
    char *buffer,
    u32 capacity)
{
    static const char *const englishNames[MULTIARENA_MAX_RANKINGS] = {
        "Lord", "Sniper", "Shaman", "Cavalier", "Fighter",
        "Warrior", "Knight", "General", "Archer", "Druid",
    };
    const char *source;
    size_t length;

    sLastResolveCapacity = capacity;
    sResolveCalls++;
    if (index >= 0x2BF && index <= 0x2E2)
    {
        int i;
        static const int ids[MULTIARENA_MAX_RANKINGS] = {
            0x2BF, 0x2CC, 0x2E1, 0x2C1, 0x2DC,
            0x2DD, 0x2C3, 0x2C4, 0x2CB, 0x2E2,
        };

        source = NULL;
        for (i = 0; i < MULTIARENA_MAX_RANKINGS; i++)
            if (ids[i] == index)
                source = englishNames[i];
        if (source == NULL)
            source = "?";
    }
    else
    {
        source = sClassName;
    }

    length = strlen(source);
    if (length >= capacity)
    {
        strncpy(buffer, LOCALIZED_GAME_TEXT_MARKER_OVERFLOW, capacity - 1);
        buffer[capacity - 1] = '\0';
    }
    else
    {
        memcpy(buffer, source, length + 1);
    }
    return buffer;
}

int GetStringTextLen(const char *str)
{
    struct TextUtf8Token token;
    const char *cursor;
    const char *next;
    int width;

    cursor = str;
    width = 0;
    for (;;)
    {
        next = TextUtf8_Next(cursor, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
            return width;
        if (token.kind != TEXT_UTF8_TOKEN_SCALAR || next == cursor)
            return width;
        width += token.scalar < 0x80 ? 7 : 12;
        cursor = next;
    }
}

struct ClassDisplayFont *GetClassDisplayFontInfo(char chr)
{
    (void)chr;
    sClassDisplayFontCalls++;
    return NULL;
}

void InitText(struct Text *text, int tileWidth)
{
    memset(text, 0, sizeof(*text));
    text->tile_width = tileWidth;
}

void ClearText(struct Text *text)
{
    text->x = 0;
}

void Text_SetColor(struct Text *text, int color)
{
    text->colorId = color;
}

void Text_SetCursor(struct Text *text, int x)
{
    text->x = x;
}

void Text_DrawString(struct Text *text, const char *str)
{
    sTextDrawStringCalls++;
    sLastTextWidth = GetStringTextLen(str);
    strncpy(sLastDrawnText, str, sizeof(sLastDrawnText) - 1);
    sLastDrawnText[sizeof(sLastDrawnText) - 1] = '\0';
    text->x += sLastTextWidth;
}

const char *Text_DrawCharacter(struct Text *text, const char *str)
{
    struct TextUtf8Token token;
    const char *next;

    sTextDrawCharacterCalls++;
    next = TextUtf8_Next(str, &token);
    text->x += token.scalar < 0x80 ? 7 : 12;
    return next;
}

void PutText(struct Text *text, u16 *tilemap)
{
    (void)text;
    (void)tilemap;
}

void TileMap_FillRect(u16 *tilemap, int width, int height, int fillValue)
{
    (void)tilemap;
    (void)width;
    (void)height;
    (void)fillValue;
}

void BG_EnableSyncByMask(int mask)
{
    (void)mask;
}

void PutSpriteExt(
    int layer,
    int x,
    int y,
    const u16 *object,
    int oam2)
{
    (void)layer;
    (void)x;
    (void)y;
    (void)object;
    (void)oam2;
}

void Decompress(const void *source, void *target)
{
    (void)source;
    (void)target;
}

void ApplyPalettes(const void *source, int firstPalette, int paletteCount)
{
    (void)source;
    (void)firstPalette;
    (void)paletteCount;
}

void SioPlaySoundEffect(int soundId)
{
    (void)soundId;
}

u32 SioStrCpy(u8 const *src, u8 *dst)
{
    u32 length;

    length = 0;
    while (*src != '\0')
    {
        *dst++ = *src++;
        length++;
    }
    *dst = '\0';
    return length;
}

void *GetSaveWriteAddr(int index)
{
    (void)index;
    return &sArenaSave;
}

u32 WriteAndVerifySramFast(const void *src, void *dst, u32 size)
{
    memcpy(dst, src, size);
    return 0;
}

void WriteSaveBlockInfo(struct SaveBlockInfo *info, int index)
{
    (void)info;
    (void)index;
}

void CpuSet(const void *src, void *dst, u32 control)
{
    u32 count;
    u16 value;
    u16 *out;
    u32 i;

    count = control & 0x1FFFFF;
    value = *(const u16 *)src;
    out = dst;
    for (i = 0; i < count; i++)
        out[i] = value;
}

static void ResetTextSpies(void)
{
    sClassDisplayFontCalls = 0;
    sTextDrawCharacterCalls = 0;
    sTextDrawStringCalls = 0;
    sLastTextWidth = 0;
    sLastDrawnText[0] = '\0';
    sLastResolveCapacity = 0;
}

static void TestOpInfoUsesLocalizedRenderer(void)
{
    struct OpInfoGaugeDrawProc proc;
    struct OpInfoClassDisplayProc parent;
    struct ClassReelEnt entry;

    memset(&proc, 0, sizeof(proc));
    memset(&parent, 0, sizeof(parent));
    memset(&entry, 0, sizeof(entry));
    sClassName =
        "\xE3\x82\xBD\xE3\x82\xB7\xE3\x82\xA2\xE3\x83\xAB"
        "\xE3\x83\x8A\xE3\x82\xA4\xE3\x83\x88";
    sClassData.nameTextId = 1;
    entry.classId = 1;
    parent.classReelEnt = &entry;
    proc.proc_parent = (struct Proc *)&parent;
    proc.unk_30 = &parent;

    ResetTextSpies();
    ClassStatsDisplay_Init(&proc);
    CHECK(proc.unk_34 == 84);
    CHECK(sLastResolveCapacity == 64);
    CHECK(sClassDisplayFontCalls == 0);

    ClassStatsDisplay_Loop(&proc);
    CHECK(strcmp(sLastDrawnText, sClassName) == 0);
    CHECK(sLastTextWidth == 84);
    CHECK(sClassDisplayFontCalls == 0);
}

static void TestClassChangeLongNamesAndGuards(void)
{
    struct
    {
        u8 before;
        struct ProcPromoSel proc;
        u8 after;
    } guarded;

    memset(&guarded, 0, sizeof(guarded));
    guarded.before = 0xA5;
    guarded.after = 0x5A;
    guarded.proc.jid[0] = 1;
    guarded.proc.main_select = 0;
    sClassName =
        "\xE3\x82\xA2\xE3\x83\xBC\xE3\x83\x9E\xE3\x83\xBC"
        "\xE3\x83\x8A\xE3\x82\xA4\xE3\x83\x88";

    ResetTextSpies();
    LoadClassReelFontPalette(&guarded.proc, 1);
    CHECK(guarded.proc.u46 == 84);
    CHECK(sLastResolveCapacity == 64);
    LoadClassNameInClassReelFont(&guarded.proc);
    CHECK(strcmp(sLastDrawnText, sClassName) == 0);
    CHECK(strstr(sLastDrawnText, LOCALIZED_GAME_TEXT_MARKER_OVERFLOW) == NULL);
    CHECK(sClassDisplayFontCalls == 0);
    CHECK(guarded.before == 0xA5);
    CHECK(guarded.after == 0x5A);
}

static void CheckRankingNames(void)
{
    int i;

    for (i = 0; i < MULTIARENA_MAX_RANKINGS; i++)
    {
        const char *name = sArenaSave.rankings[i].name;

        CHECK(strlen(name) <= MULTIARENA_TEAMNAME_SIZE);
        CHECK(IsValidUtf8Name(name));
        CHECK(strstr(name, LOCALIZED_GAME_TEXT_MARKER_OVERFLOW) == NULL);
    }
}

static void TestLocalizedRankingNamesFitSave(void)
{
    memset(&sArenaSave, 0xA5, sizeof(sArenaSave));
    sResolveCalls = 0;
    sLocale = EXPANSION_LOCALE_JA;
    WriteNewMultiArenaSave();
    CheckRankingNames();
    CHECK(strcmp(
        sArenaSave.rankings[0].name,
        "\xE3\x83\xAD\xE3\x83\xBC\xE3\x83\x89") == 0);
    CHECK(sResolveCalls == 0);

    memset(&sArenaSave, 0xA5, sizeof(sArenaSave));
    sResolveCalls = 0;
    sLocale = EXPANSION_LOCALE_ZH_HANS;
    WriteNewMultiArenaSave();
    CheckRankingNames();
    CHECK(strcmp(
        sArenaSave.rankings[9].name,
        "\xE5\xBE\xB7\xE9\xB2\x81\xE4\xBC\x8A") == 0);
    CHECK(sResolveCalls == 0);

    memset(&sArenaSave, 0xA5, sizeof(sArenaSave));
    sResolveCalls = 0;
    sLocale = EXPANSION_LOCALE_EN;
    WriteNewMultiArenaSave();
    CheckRankingNames();
    CHECK(strcmp(sArenaSave.rankings[0].name, "Lord") == 0);
    CHECK(strcmp(sArenaSave.rankings[9].name, "Druid") == 0);
    CHECK(sResolveCalls == MULTIARENA_MAX_RANKINGS);
}

static void TestTacticianTokenTraversalAndWidth(void)
{
    struct ProcTactician proc;
    struct TacticianTextConf conf;
    int i;

    memset(&proc, 0, sizeof(proc));
    memset(&conf, 0, sizeof(conf));
    proc.max_len = 9;
    proc.conf_idx = 6;
    proc.line_idx = 0;
    conf.str[0] = (u8 *)"\xE7\x8C\xAB";
    for (i = 0; i < (int)ARRAY_COUNT(proc.unk4C); i++)
        proc.unk4C[i] = 0xA5A5;

    TacticianTryAppendChar(&proc, &conf);
    TacticianTryAppendChar(&proc, &conf);
    TacticianTryAppendChar(&proc, &conf);
    TacticianTryAppendChar(&proc, &conf);
    CHECK(strlen(proc.str) == 12);
    CHECK(proc.cur_len == 12);
    CHECK(proc.unk4C[4] == 0xA5A5);

    TacticianTryAppendChar(&proc, &conf);
    CHECK(strlen(proc.str) == 12);
    CHECK(proc.cur_len == 12);
    CHECK(proc.unk4C[4] == 0xA5A5);

    sTextDrawCharacterCalls = 0;
    sTextDrawStringCalls = 0;
    TacticianDrawCharacters(&proc);
    CHECK(sTextDrawStringCalls == 1);
    CHECK(sTextDrawCharacterCalls == 0);
    CHECK(sLastTextWidth == 48);

    TacticianTryDeleteChar(&proc, &conf);
    CHECK(strlen(proc.str) == 9);
    CHECK(proc.cur_len == 9);
    CHECK(proc.unk4C[3] == 0);

    memset(&proc, 0, sizeof(proc));
    Tactician_MapNameToConfIndices(&proc, (u8 *)"AB");
    CHECK((proc.unk4C[0] & 0x3FFF) == 6);
    CHECK((proc.unk4C[1] & 0x3FFF) == 7);
    CHECK(Tactician_TestTokensEqual(
        "\xE7\x8C\xAB", "\xE7\x8C\xAB"));
    CHECK(!Tactician_TestTokensEqual(
        "\xE7\x8C\xAB", "\xE7\x8B\x97"));
}

int main(void)
{
    TestOpInfoUsesLocalizedRenderer();
    TestClassChangeLongNamesAndGuards();
    TestLocalizedRankingNamesFitSave();
    TestTacticianTokenTraversalAndWidth();

    if (sFailures == 0)
    {
        puts("text_reviewed_consumers_host_test: ok");
        return 0;
    }

    printf("%d failure(s)\n", sFailures);
    return 1;
}
