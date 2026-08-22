#include "global.h"

#include "hardware.h"
#include "chap_title.h"
#include "chapterdata.h"
#include "bmlib.h"
#include "helpbox.h"
#include "worldmap.h"
#include "fontgrp.h"
#include "constants/chapters.h"
#include "constants/msg.h"

EWRAM_DATA struct ChapterTitleFxSt gChapterTitleFxSt = { 0 };

void ApplyChapterTitlePal(int config, int palId)
{
    u16 * pal;
    pal = (config & 1)
        ? Pal_ChapterTitleAlt
        : Pal_ChapterTitleMain;

    if ((config & 0x80) == 0)
    {
        if ((config & 8) != 0)
        {
            pal = pal + 0xA0;
        }
        else
        {
            if ((config & 0x10) == 0)
            {
                if ((config & 0x20) != 0)
                    pal = pal + 0x20;
                if ((config & 0x40) != 0)
                    pal = pal + 0x40;
                if ((config & 4) != 0)
                    pal = pal + 0x40;
            }
        }
    }

    if ((config & 2) != 0) {
        pal = pal + 0x10;
    }

    ApplyPalette(pal, palId);
}

#if FE8_TEXT_CHAPTER_NAMES
/* Modern-build port of the Pokemblem/TextChNames FEBuilder-style ROM patch
 * by circleseverywhere, with extended Latin support by hypergammaspaces.
 * It replaces the pre-rendered chapter-title graphic banner with title text
 * drawn into the same 32x2 BG tile block used by the vanilla title images. */

extern u8 Img_ChapterTitleTextFont[];
extern u8 gChapterTitleTextFontDimensions[];

/* PutChapterTitleGfx's titleId is the old chapter-title graphics table index,
 * not a text id. Resolve that graphics id back to the matching chapter data
 * entry, then use the chapter's text id. */
enum
{
    CHAPTER_TITLE_ID_NO_DATA = 0x54,
    CHAPTER_TITLE_ID_EPILOGUE = 0x55,
    CHAPTER_TITLE_ID_POSTGAME = 0x57,

    CHAPTER_TITLE_TEXT_WIDTH = 0xC0,
    CHAPTER_TITLE_TILE_WIDTH = 0x20,
    CHAPTER_TITLE_TILE_HEIGHT = 2,
    CHAPTER_TITLE_TILE_BYTES = CHAPTER_TITLE_TILE_WIDTH * CHAPTER_TITLE_TILE_HEIGHT * CHR_SIZE,
    CHAPTER_TITLE_FONT_ROW_BYTES = 0x400,
    CHAPTER_TITLE_FONT_ENTRY_SIZE = 8,
    CHAPTER_TITLE_SPACE = 0x80,
};

struct ChapterTitleFontDimensions
{
    u8 leftBearing;
    u8 rightBearing;
    u8 leftAdvance;
    u8 rightAdvance;
    u8 sourceWidth;
    u8 drawWidth;
    u8 yStart;
    u8 yEnd;
};

static const struct ChapterTitleFontDimensions *GetChapterTitleFontDimensions(int glyph)
{
    return (const struct ChapterTitleFontDimensions *)(
        gChapterTitleTextFontDimensions + glyph * CHAPTER_TITLE_FONT_ENTRY_SIZE);
}

static u16 GetChapterTitleTextMsgId(u32 titleId)
{
    int i;
    u8 graphicTitleId = titleId & 0x7F;

    switch (graphicTitleId)
    {
    case CHAPTER_TITLE_ID_NO_DATA:
        return MSG_0CC; // "NO DATA"
    case CHAPTER_TITLE_ID_EPILOGUE:
        return MSG_7CF; // "Epilogue"
    case CHAPTER_TITLE_ID_POSTGAME:
        return MSG_7D0; // "?????"
    }

    for (i = 0; i <= CHAPTER_4E; i++)
    {
        const struct ROMChapterData* chapter = GetROMChapterStruct(i);

        if (chapter->chapTitleId != graphicTitleId)
            continue;

        if (chapter->chapTitleTextId != 0)
            return chapter->chapTitleTextId;
    }

    return MSG_7D0;
}

static int MapChapterTitleCharToFont(const u8 *str)
{
    u8 c = str[0];

    if (c >= 'A' && c <= 'Z')
        return c - 'A';

    if (c >= 'a' && c <= 'z')
        return c - 0x47;

    if (c >= '0' && c <= '9')
        return c + 4;

    if (c == '&')
        return 0x3E;

    if (c == '\'')
        return 0x3F;

    if (c >= ',' && c <= '.')
        return c + 0x14;

    if (c == ':')
        return 0x43;

    switch (c)
    {
    case 0xCD:
        return 0x44;
    case 0x9C:
        return 0x45;
    case 0xE0:
        return 0x46;
    case 0xE1:
        return 0x47;
    case 0xE2:
        return 0x48;
    case 0xE4:
        return 0x49;
    case 0xE8:
        return 0x4A;
    case 0xE9:
        return 0x4B;
    case 0xEA:
        return 0x4C;
    case 0xED:
        return 0x4D;
    case 0xEE:
        return 0x4E;
    case 0xF1:
        return 0x56;
    case 0xF2:
        return 0x4F;
    case 0xF3:
        return 0x50;
    case 0xF4:
        return 0x51;
    case 0xF6:
        return 0x52;
    case 0xFC:
        return 0x53;
    case '(':
        return 0x54;
    case ')':
        return 0x55;
    }

    return CHAPTER_TITLE_SPACE;
}

static int GetChapterTitleFontSourceOffset(int glyph)
{
    int i;
    int offset = 0;

    for (i = 0; i < glyph; i++)
        offset += GetChapterTitleFontDimensions(i)->sourceWidth;

    return offset;
}

static u8 GetChapterTitleFontPixel(const u8 *tiles, int x, int y)
{
    int offset = ((y >> 3) * CHAPTER_TITLE_FONT_ROW_BYTES)
        + ((x >> 3) * CHR_SIZE)
        + ((y & 7) * 4)
        + ((x & 7) >> 1);
    u8 byte = tiles[offset];

    if (x & 1)
        return byte >> 4;

    return byte & 0xF;
}

static void PutChapterTitleFontPixel(u8 *tiles, int x, int y, u8 pixel)
{
    int offset;
    u8 *dst;

    if (x < 0 || x >= 0x100 || y < 0 || y >= CHAPTER_TITLE_TILE_HEIGHT * 8)
        return;

    offset = ((y >> 3) * CHAPTER_TITLE_FONT_ROW_BYTES)
        + ((x >> 3) * CHR_SIZE)
        + ((y & 7) * 4)
        + ((x & 7) >> 1);
    dst = tiles + offset;

    if (x & 1)
        *dst |= pixel << 4;
    else
        *dst |= pixel;
}

static void AdvanceChapterTitleSpace(int *left, int *right)
{
    int x = (*left > *right) ? *left : *right;

    x += 3;
    *left = x;
    *right = x;
}

static void SyncChapterTitleGlyphCursors(
    const struct ChapterTitleFontDimensions *dim,
    int *left,
    int *right)
{
    if ((*left - dim->leftBearing) > (*right - dim->rightBearing))
        *right = *left;
    else
        *left = *right;
}

static void AdvanceChapterTitleGlyphCursors(
    const struct ChapterTitleFontDimensions *dim,
    int *left,
    int *right)
{
    *left += dim->leftAdvance - 1;
    *right += dim->rightAdvance - 1;
}

static int GetChapterTitleTextCenteredX(const char *str)
{
    int left = 0;
    int right = 0;

    while (*str != 0 && *str != 0x1F)
    {
        int glyph = MapChapterTitleCharToFont((const u8 *)str);

        if (glyph == CHAPTER_TITLE_SPACE)
        {
            AdvanceChapterTitleSpace(&left, &right);
        }
        else
        {
            const struct ChapterTitleFontDimensions *dim = GetChapterTitleFontDimensions(glyph);

            SyncChapterTitleGlyphCursors(dim, &left, &right);
            AdvanceChapterTitleGlyphCursors(dim, &left, &right);
        }

        str++;
    }

    return (CHAPTER_TITLE_TEXT_WIDTH - ((left + right) >> 1)) >> 1;
}

static void DrawChapterTitleGlyph(u8 *dest, const u8 *font, int glyph, int x)
{
    const struct ChapterTitleFontDimensions *dim = GetChapterTitleFontDimensions(glyph);
    int sourceOffset = GetChapterTitleFontSourceOffset(glyph);
    int sourceX = sourceOffset & 0xFF;
    int sourceY = (sourceOffset >> 8) * 16;
    int y;

    for (y = dim->yStart; y < dim->yEnd; y++)
    {
        int pixelX;

        for (pixelX = 0; pixelX < dim->drawWidth; pixelX++)
        {
            u8 pixel = GetChapterTitleFontPixel(font, sourceX + pixelX, sourceY + y);

            if (pixel != 0)
                PutChapterTitleFontPixel(dest, x + pixelX, y, pixel);
        }
    }
}

static void DrawChapterTitleText(int chr, u32 titleId)
{
    const char* str = GetStringFromIndex(GetChapterTitleTextMsgId(titleId));
    

    str = GetStringFromIndex(0x505);
    
    u8 *dest = (u8 *)(VRAM + chr * CHR_SIZE);
    u8 *font = gGenericBuffer;
    int left;
    int right;
    int x;

    Decompress(Img_ChapterTitleTextFont, font);
    CpuFastFill(0, dest, CHAPTER_TITLE_TILE_BYTES);

    x = GetChapterTitleTextCenteredX(str);
    if (x < 0)
        x = 0;

    left = x;
    right = x;

    while (*str != 0 && *str != 0x1F)
    {
        int glyph = MapChapterTitleCharToFont((const u8 *)str);

        if (glyph == CHAPTER_TITLE_SPACE)
        {
            AdvanceChapterTitleSpace(&left, &right);
        }
        else
        {
            const struct ChapterTitleFontDimensions *dim = GetChapterTitleFontDimensions(glyph);

            SyncChapterTitleGlyphCursors(dim, &left, &right);
            DrawChapterTitleGlyph(dest, font, glyph, left);
            AdvanceChapterTitleGlyphCursors(dim, &left, &right);
        }

        str++;
    }
}
#endif

void PutChapterTitleGfx(int chr, u32 titleId)
{
    if (titleId > 0x108)
        titleId = 0x54;

    gChapterTitleFxSt.chr_str = chr & 0x3FF;

#if FE8_TEXT_CHAPTER_NAMES
    DrawChapterTitleText(chr, titleId);
#else
    Decompress(chap_title_data[titleId].save, (void*)((chr * TILE_SIZE_4BPP) + VRAM));
#endif
}

void _PutChapterTitleGfx(int chr, int titleId)
{
    PutChapterTitleGfx(chr, titleId);
}

void PutChapterTitleBG(int chr)
{
    gChapterTitleFxSt.chr_bg = chr & 0x3FF;
    Decompress(Img_ChapterTitleBg, (void*)((chr * TILE_SIZE_4BPP) + VRAM));
}

extern u8 Img_ChapterTitleBgAlt[];

void PutChapterTitleBGAlt(int chr)
{
    gChapterTitleFxSt.chr_bg = chr & 0x3FF;
    Decompress(Img_ChapterTitleBgAlt, (void*)((chr * TILE_SIZE_4BPP) + VRAM));
}

void DrawChapterTitleStr(u16 * tm, int pal)
{
    int i;
    int tile = TILEREF(gChapterTitleFxSt.chr_str, pal);
    for (i = 0; i < 0x40; i++)
        *tm++ = tile++;
}

void DrawChapterTitleStrEx(u16 * tm, int pal, int c)
{
    int i;
    int tile = TILEREF(gChapterTitleFxSt.chr_str, pal);
    for (i = 0; i < 0x40; i++)
        *tm++ = tile++;
}

void DrawChapterTitleBG(u16 * tm, int pal)
{
    int i;
    int tile = TILEREF(gChapterTitleFxSt.chr_bg, pal);
    for (i = 0; i < 0x80; i++)
        *tm++ = tile++;
}

void DrawChapterTitleBGTsa(u16 * tm, int pal)
{
    CallARM_FillTileRect(tm, Tsa_ChapterTitleBg, (u16)TILEREF(gChapterTitleFxSt.chr_bg, pal));
}

int GetChapterTitleExtra(struct PlaySt * chapterData)
{

    if (chapterData == 0)
        return 0x54; // No Data

    if (chapterData->chapterStateBits & PLAY_FLAG_POSTGAME)
        return 0x57; // Creature Campaign

    if (chapterData->chapterStateBits & PLAY_FLAG_COMPLETE)
        return 0x55; // Epilogue

    return GetROMChapterStruct(chapterData->chapterIndex)->chapTitleId;
}

int GetChapterTitleWM(struct PlaySt * chapterData)
{
    int unk;
    int i;

    if (chapterData == 0) {
        return 0x54; // No Data
    }

    unk = GetPlayChapterId(chapterData->chapterIndex);

    if ((chapterData->chapterStateBits & PLAY_FLAG_POSTGAME) || GetNextUnclearedNode(&gGMData) != unk)
    {
        for (i = 0; i < gWMMonsterSpawnsSize; i++)
        {
            if (unk == gWMMonsterSpawnLocations[i])
                return 0x46 + i;
        }
    }

    return GetROMChapterStruct(chapterData->chapterIndex)->chapTitleId;
}
