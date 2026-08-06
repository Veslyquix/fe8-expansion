#include "global.h"

#include <stdio.h>
#include <string.h>

#include "localized_game_text.h"
#include "scene.h"
#include "text_utf8.h"

void GetCgTextDimensions(const char *str, u8 *wOut, u8 *hOut);
void GetCgTextBoxDimensions(const char *str, int *wOut, int *hOut);
s8 DoesStringContainTact(const char *str);
int CgText_TestCopyName(char *buffer, u32 capacity, const char **source);
void GetBoxDialogueSize(const char *str, int *wOut, int *hOut);
void DialogBoxGetGlyphLen(const char *str, u8 *xOut);
extern struct TalkState *sTalkState;

static int sFailures;

#define CHECK(condition) do { \
    if (!(condition)) { \
        printf("FAIL: %s:%d: %s\n", __FILE__, __LINE__, #condition); \
        sFailures++; \
    } \
} while (0)

static u32 GetTestTokenWidth(const char *str)
{
    struct TextUtf8Token token;

    TextUtf8_Next(str, &token);
    if (token.kind == TEXT_UTF8_TOKEN_INVALID)
        return 7;
    if (token.kind != TEXT_UTF8_TOKEN_SCALAR)
        return 0;
    if (token.scalar == 0x3000)
        return 16;
    if (token.scalar < 0x80)
        return 8;
    return 12;
}

const char *GetCharTextLen(const char *str, u32 *width)
{
    struct TextUtf8Token token;
    const char *next;

    next = TextUtf8_Next(str, &token);
    *width = GetTestTokenWidth(str);
    return next;
}

int GetStringTextLen(const char *str)
{
    struct TextUtf8Token token;
    const char *next;
    int width;

    width = 0;
    for (;;)
    {
        next = TextUtf8_Next(str, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
            return width;
        if (token.kind == TEXT_UTF8_TOKEN_CONTROL
            && token.control == CHFE_L_NL)
            return width;
        width += GetTestTokenWidth(str);
        str = next;
    }
}

void SetTextFontGlyphs(int glyphSet)
{
    (void)glyphSet;
}

void NumberToStringAscii(int number, char *buffer)
{
    sprintf(buffer, "%d", number);
}

char *GetTacticianName(void)
{
    return "\xE8\xBB\x8D\xE5\xB8\xAB";
}

static void TestCgDimensionsAndControlCollision(void)
{
    static const char text[] = {
        (char)0xE5, (char)0x80, (char)0x99,
        (char)0x80, (char)0x21,
        (char)0xE8, (char)0xA8, (char)0xBA,
        CHFE_L_NL,
        (char)0xE3, (char)0x80, (char)0x80,
        CHFE_L_A,
        CHFE_L_X
    };
    u8 width;
    u8 height;
    int boxWidth;
    int boxHeight;

    width = 0;
    height = 0;
    GetCgTextDimensions(text, &width, &height);
    CHECK(width == 16);
    CHECK(height == 16);

    GetCgTextBoxDimensions(text, &boxWidth, &boxHeight);
    CHECK(boxWidth == 24);
    CHECK(boxHeight == 32);

    CHECK(DoesStringContainTact(text) == FALSE);
    CHECK(DoesStringContainTact("\xE5\x80\x99\x80\x20") == TRUE);
}

static void TestHelpDimensionsAndGlyphAdvance(void)
{
    static const char text[] = {
        (char)0xE7, (char)0x8C, (char)0xAB,
        (char)0xE3, (char)0x80, (char)0x80,
        CHFE_L_Pause8,
        CHFE_L_NL,
        (char)0xE8, (char)0xA8, (char)0xBA,
        CHFE_L_A,
        CHFE_L_X
    };
    int width;
    int height;
    u8 glyphLen;

    GetBoxDialogueSize(text, &width, &height);
    CHECK(width == 28);
    CHECK(height == 32);

    DialogBoxGetGlyphLen(text, &glyphLen);
    CHECK(glyphLen == 14);
}

static void TestTalkLengthControlsAndSpacing(void)
{
    static const char text[] = {
        (char)0xE7, (char)0x8C, (char)0xAB,
        (char)0xE3, (char)0x80, (char)0x80,
        (char)0x80, (char)0x21,
        CHFE_L_NL,
        (char)0xE8, (char)0xA8, (char)0xBA,
        CHFE_L_A,
        CHFE_L_X
    };
    static const char faceText[] = {
        CHFE_L_OpenFarLeft,
        CHFE_L_LoadFace, (char)0x93, (char)0x94,
        (char)0xE5, (char)0x80, (char)0x99,
        CHFE_L_X
    };
    static const char tactText[] = {
        (char)0x80, (char)0x20,
        CHFE_L_X
    };

    sTalkState->speakingFaceSlot = 0xFF;
    sTalkState->activeFaceSlot = 0xFF;
    CHECK(GetStrTalkLen(text, FALSE) == 28);
    CHECK(GetStrTalkLen(faceText, FALSE) == 24);
    CHECK(GetStrTalkLen(tactText, FALSE) == 24);
}

static void TestNameCopyBounds(void)
{
    static const char name[] = {
        (char)0xE5, (char)0x80, (char)0x99,
        (char)0x80, (char)0x21,
        (char)0xE7, (char)0x8C, (char)0xAB,
        CHFE_L_NL,
        'Z',
        CHFE_L_X
    };
    static const char expected[] = {
        (char)0xE5, (char)0x80, (char)0x99,
        (char)0x80, (char)0x21,
        (char)0xE7, (char)0x8C, (char)0xAB,
        0
    };
    const char *cursor;
    u8 guarded[14];
    static const char malformed[] = {(char)0xE8, 0};

    memset(guarded, 0xA5, sizeof(guarded));
    cursor = name;
    CHECK(CgText_TestCopyName(
        (char *)(guarded + 1), 9, &cursor) == TRUE);
    CHECK(memcmp(guarded + 1, expected, sizeof(expected)) == 0);
    CHECK(*cursor == 'Z');
    CHECK(guarded[0] == 0xA5);
    CHECK(guarded[10] == 0xA5);

    memset(guarded, 0xA5, sizeof(guarded));
    cursor = name;
    CHECK(CgText_TestCopyName(
        (char *)(guarded + 1), 8, &cursor) == FALSE);
    CHECK(strcmp((char *)(guarded + 1), "<!LOC_O") == 0);
    CHECK(*cursor == 'Z');
    CHECK(guarded[0] == 0xA5);
    CHECK(guarded[9] == 0xA5);

    memset(guarded, 0xA5, sizeof(guarded));
    cursor = malformed;
    CHECK(CgText_TestCopyName(
        (char *)(guarded + 1), 12, &cursor) == FALSE);
    CHECK(strcmp(
        (char *)(guarded + 1), LOCALIZED_GAME_TEXT_MARKER_CORRUPT) == 0);
    CHECK(guarded[0] == 0xA5);
    CHECK(guarded[13] == 0xA5);
}

int main(void)
{
    TestCgDimensionsAndControlCollision();
    TestHelpDimensionsAndGlyphAdvance();
    TestTalkLengthControlsAndSpacing();
    TestNameCopyBounds();

    if (sFailures == 0)
    {
        puts("text_consumer_host_test: ok");
        return 0;
    }

    printf("%d failure(s)\n", sFailures);
    return 1;
}
