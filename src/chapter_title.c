#include "global.h"

#include "hardware.h"
#include "chap_title.h"
#include "chapterdata.h"
#include "bmlib.h"
#include "helpbox.h"
#include "worldmap.h"
#include "fontgrp.h"

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
/* Modern-build port of a FEBuilder-style ROM patch (by circleseverywhere)
 * that replaces the pre-rendered chapter-title graphic banner with the
 * chapter's actual title text, drawn with a bitmap font, so any chapter
 * name reads correctly instead of needing a hand-drawn banner per
 * chapter. Ported using this project's existing sprite-text primitives
 * (InitSpriteTextFont/Text_InsertDrawString, already used throughout the
 * UI) rather than the original patch's own hand-rolled per-pixel VRAM
 * plotter and custom font/glyph-metrics format, since those cannot be
 * exercised without visually rendering the result. NEEDS VISUAL
 * VERIFICATION IN AN EMULATOR: text color/palette selection in
 * particular is a best-effort default (colorId 1), not verified against
 * how this screen's palette is actually laid out.
 *
 * The original patch's save-select-screen per-slot chapter name preview
 * (reading a chapter id directly out of SRAM save data) is intentionally
 * NOT ported: its address didn't resolve to any recognizable field of
 * this project's (byte-identical-to-vanilla) save layout, and guessing
 * at a raw save-data offset is a correctness risk this project treats
 * carefully (see EXPANSION_SAVE_COMPAT_EPOCH in config.mk). */

/* Message ids for the few titleId sentinels that are not real chapter
 * indices (see chapter_text/nodata_text/epilogue_text/postgame_text in
 * the original patch). */
enum
{
    CHAPTER_TITLE_ID_NO_DATA = 0x4A,
    CHAPTER_TITLE_ID_EPILOGUE = 0x55,
    CHAPTER_TITLE_ID_POSTGAME = 0x57,
};

static u16 GetChapterTitleTextMsgId(u32 titleId)
{
    const struct ROMChapterData* chapter;
    bool8 altRoute;

    switch (titleId)
    {
    case CHAPTER_TITLE_ID_NO_DATA:
        return 0xCC; // "--NO DATA--"
    case CHAPTER_TITLE_ID_EPILOGUE:
        return 0x7CF; // "Epilogue"
    case CHAPTER_TITLE_ID_POSTGAME:
        return 0x7D0;
    }

    altRoute = (titleId >> 7) & 1;
    chapter = GetROMChapterStruct(titleId & 0x7F);

    return altRoute ? chapter->chapTitleTextIdInHectorStory : chapter->chapTitleTextId;
}

static void DrawChapterTitleText(int chr, u32 titleId)
{
    struct Font font;
    struct Text text;
    const char* str;
    int width, xStart;

    str = GetStringFromIndex(GetChapterTitleTextMsgId(titleId));

    InitSpriteTextFont(&font, (void*)((chr * TILE_SIZE_4BPP) + VRAM), 0);
    InitSpriteText(&text);
    SpriteText_DrawBackground(&text);

    width = GetStringTextLen(str);
    xStart = (0xC0 - width) / 2;
    if (xStart < 0)
        xStart = 0;

    Text_InsertDrawString(&text, xStart, 1, str);

    SetTextFont(0);
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
