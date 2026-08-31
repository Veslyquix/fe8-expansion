#include "global.h"
#include "bmlib.h"
#include "functions.h"
#include "variables.h"



/* These should related to status-bar gfx for stat-screen */
#if FE8_CO_POWERS
enum statBarCoTileRows {
    CSB_bonusOutlineTop,
    CSB_outlineTop,
    CSB_highlight,
    CSB_fill,
    CSB_outlineBottom,
    CSB_bonusOutlineShadow,
};
#define OUTLINE_COL_ID 4 // 4 
#define SHADOW_COL_ID 4 // 4 
void DrawCoStatBarCappedCol(u8 *buf, int bufWidth, int col)
{
    buf[CSB_bonusOutlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_outlineTop * bufWidth + col] = 13;
    buf[CSB_highlight * bufWidth + col] = 13;
    buf[CSB_fill * bufWidth + col] = 12;
    // buf[CSB_fill2 * bufWidth + col] = 12;
}
void DrawCoStatBarMinusCol(u8 *buf, int bufWidth, int col)
{
    // buf[CSB_bonusOutlineTop * bufWidth + col] = OUTLINE_COL_ID;
    // buf[CSB_outlineTop * bufWidth + col] = 10;
    // buf[CSB_highlight * bufWidth + col] = 11;
    // buf[CSB_fill * bufWidth + col] = 11;
    
    buf[CSB_bonusOutlineTop * bufWidth + col] = 0;
    buf[CSB_outlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_highlight * bufWidth + col] = 10;
    buf[CSB_fill * bufWidth + col] = 11;
    // buf[CSB_fill2 * bufWidth + col] = 10;
}
void DrawCoStatBarShadow(u8 *buf, int bufWidth, int col)
{
    buf[CSB_highlight * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_fill * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_outlineBottom * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_bonusOutlineShadow * bufWidth + col] = SHADOW_COL_ID;
}

void DrawCoStatBarLeftBorder(u8 *buf, int bufWidth, int col)
{
    buf[CSB_outlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_highlight * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_fill * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_outlineBottom * bufWidth + col] = OUTLINE_COL_ID;
}

void DrawCoStatBarRightBorder(u8 *buf, int bufWidth, int col)
{
    buf[CSB_outlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_highlight * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_fill * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_outlineBottom * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_bonusOutlineShadow * bufWidth + col] = SHADOW_COL_ID;
}

void DrawCoStatBarUnfilledCol(u8 *buf, int bufWidth, int col)
{
    buf[CSB_outlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_highlight * bufWidth + col] = 14;
    buf[CSB_fill * bufWidth + col] = 3;
    // buf[CSB_fill2 * bufWidth + col] = 3;
    buf[CSB_outlineBottom * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_bonusOutlineShadow * bufWidth + col] = SHADOW_COL_ID;
}

void DrawCoStatBarFilledCol(u8 *buf, int bufWidth, int col)
{
    buf[CSB_highlight * bufWidth + col] = 1;
    buf[CSB_fill * bufWidth + col] = 5;
    // buf[CSB_fill2 * bufWidth + col] = 5;
}

void DrawCoStatBarRightBorderMinus(u8 *buf, int bufWidth, int col)
{
    buf[CSB_outlineTop * bufWidth + col] = 0;
    buf[CSB_highlight * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_fill * bufWidth + col] = OUTLINE_COL_ID;
    // buf[CSB_fill2 * bufWidth + col] = 4;
    buf[CSB_outlineBottom * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_bonusOutlineShadow * bufWidth + col] = SHADOW_COL_ID;
}

void DrawCoStatBarLeftBorderPlus(u8 *buf, int bufWidth, int col)
{
    buf[CSB_bonusOutlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_outlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_highlight * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_fill * bufWidth + col] = OUTLINE_COL_ID;
    // buf[CSB_fill2 * bufWidth + col] = OUTLINE_COL_ID;
    buf[CSB_outlineBottom * bufWidth + col] =OUTLINE_COL_ID;
}

void DrawCoStatBar(
    int tile, int padding, int bufWidth, int barWidth, int progressLength, int cappedLength)
{
    int i, j, val, val1;
    u8 *buf = gGenericBuffer;
    CpuFastFill(0, buf, 0x40 * bufWidth);

    for (i = 1; i < barWidth + 1; i++)
        DrawCoStatBarUnfilledCol(buf, 8 * bufWidth, i + ({padding + 1;}));

    DrawCoStatBarLeftBorder(buf, 8 * bufWidth, padding + 1);
    DrawCoStatBarRightBorder(buf, 8 * bufWidth, padding + barWidth + 2);
    DrawCoStatBarShadow(buf, 8 * bufWidth, padding + barWidth + 3);

    for (i = 0; i < progressLength; i++)
        DrawCoStatBarFilledCol(buf, 8 * bufWidth, i + ({padding + 2;}));

    for (i = 0; i < cappedLength; i++)
        DrawCoStatBarCappedCol(buf, 8 * bufWidth, i + progressLength + padding + 2);

    ApplyBitmap(buf, (void*)(32 * tile + VRAM), bufWidth, 1);
}

// bufWidth: The width of the allocated buffer canvas
// barWidth: The width of the bar itself (in tiles)
// progressLength: The length of the "progress" of the bar (the yellow part)
// cappedLength: Same as above, controls the part that flashes green when stat capped
void DrawCoStatBarGfx(
    int tile, int bufWidth, u16* buf, int tileBase,
    int barWidth, int progressLength, int cappedLength)
{
    DrawCoStatBar(tile, 2, bufWidth, barWidth, progressLength, cappedLength);
    PutAppliedBitmap(buf, tileBase + (tile & 0x3FF), bufWidth, 1);
}


#endif 


enum statBarTileRows {
    SB_outlineTop,
    SB_highlight,
    SB_fill,
    SB_outlineBottom,
    SB_bonusOutlineShadow,
};

void DrawStatBarCappedCol(u8 *buf, int bufWidth, int col)
{
    buf[SB_highlight * bufWidth + col] = 13;
    buf[SB_fill * bufWidth + col] = 12;
}

void DrawStatBarUnfilledCol(u8 *buf, int bufWidth, int col)
{
    buf[SB_outlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_highlight * bufWidth + col] = 14;
    buf[SB_fill * bufWidth + col] = 3;
    buf[SB_outlineBottom * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_bonusOutlineShadow * bufWidth + col] = SHADOW_COL_ID;
}

void DrawStatBarFilledCol(u8 *buf, int bufWidth, int col)
{
    buf[SB_highlight * bufWidth + col] = 1;
    buf[SB_fill * bufWidth + col] = 5;
}



void UnusedDrawOutline(u8 *buf, int bufWidth, int col)
{
    buf[SB_outlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_highlight * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_fill * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_outlineBottom * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_bonusOutlineShadow * bufWidth + col] = SHADOW_COL_ID;
}

void DrawStatBarLeftBorder(u8 *buf, int bufWidth, int col)
{
    buf[SB_outlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_highlight * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_fill * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_outlineBottom * bufWidth + col] = OUTLINE_COL_ID;
}

void DrawStatBarShadow(u8 *buf, int bufWidth, int col)
{
    buf[SB_highlight * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_fill * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_outlineBottom * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_bonusOutlineShadow * bufWidth + col] = SHADOW_COL_ID;
}

void DrawStatBarRightBorder(u8 *buf, int bufWidth, int col)
{
    buf[SB_outlineTop * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_highlight * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_fill * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_outlineBottom * bufWidth + col] = OUTLINE_COL_ID;
    buf[SB_bonusOutlineShadow * bufWidth + col] = SHADOW_COL_ID;
}





void DrawStatBar(
    int tile, int padding, int bufWidth, int barWidth, int progressLength, int cappedLength)
{
    int i, j, val, val1;
    u8 *buf = gGenericBuffer;
    CpuFastFill(0, buf, 0x40 * bufWidth);

    for (i = 1; i < barWidth + 1; i++)
        DrawStatBarUnfilledCol(buf, 8 * bufWidth, i + ({padding + 1;}));

    DrawStatBarLeftBorder(buf, 8 * bufWidth, padding + 1);
    DrawStatBarRightBorder(buf, 8 * bufWidth, padding + barWidth + 2);
    DrawStatBarShadow(buf, 8 * bufWidth, padding + barWidth + 3);

    for (i = 0; i < progressLength; i++)
        DrawStatBarFilledCol(buf, 8 * bufWidth, i + ({padding + 2;}));

    for (i = 0; i < cappedLength; i++)
        DrawStatBarCappedCol(buf, 8 * bufWidth, i + progressLength + padding + 2);

    ApplyBitmap(buf, (void*)(32 * tile + VRAM), bufWidth, 1);
}

// bufWidth: The width of the allocated buffer canvas
// barWidth: The width of the bar itself (in tiles)
// progressLength: The length of the "progress" of the bar (the yellow part)
// cappedLength: Same as above, controls the part that flashes green when stat capped
void DrawStatBarGfx(
    int tile, int bufWidth, u16* buf, int tileBase,
    int barWidth, int progressLength, int cappedLength)
{
    DrawStatBar(tile, 2, bufWidth, barWidth, progressLength, cappedLength);
    PutAppliedBitmap(buf, tileBase + (tile & 0x3FF), bufWidth, 1);
}

#if FE8_CO_POWERS


/* CO screen variant of DrawStatBar: instead of a single yellow fill up to
 * some length, the WHOLE bar is filled yellow (DrawStatBarFilledCol), then
 * overlaid with a run of colored columns showing how `progressLength`
 * compares to `base`:
 *   - progressLength > base: the first (progressLength - base) columns,
 *     starting from the LEFT edge and moving right, are overlaid green
 *     (DrawStatBarCappedCol) -- the stat's bonus over its base.
 *   - progressLength < base: the last (base - progressLength) columns,
 *     starting from the RIGHT edge and moving left, are overlaid red
 *     (DrawStatBarMinusCol) -- the stat's shortfall below its base.
 *   - progressLength == base: no overlay, the bar is plain yellow.
 * Both overlay lengths are clamped to barWidth (a stat arbitrarily far
 * from its base still only covers the visible bar). */
void DrawStatBarCo(
    int tile, int padding, int bufWidth, int barWidth, int progressLength, int base)
{
    int i;
    u8 *buf = gGenericBuffer;
    CpuFastFill(0, buf, 0x40 * bufWidth);

    for (i = 1; i < barWidth + 1; i++)
        DrawCoStatBarUnfilledCol(buf, 8 * bufWidth, i + (padding + 1));

    
    if (progressLength > base) { 
    DrawCoStatBarLeftBorderPlus(buf, 8 * bufWidth, padding + 1);
    DrawCoStatBarRightBorder(buf, 8 * bufWidth, padding + barWidth + 2);
    } 
    else { 
    DrawCoStatBarLeftBorder(buf, 8 * bufWidth, padding + 1);
    DrawCoStatBarRightBorderMinus(buf, 8 * bufWidth, padding + barWidth + 2);
    } 
    
    DrawCoStatBarShadow(buf, 8 * bufWidth, padding + barWidth + 3);

    for (i = 0; i < barWidth; i++)
        DrawCoStatBarFilledCol(buf, 8 * bufWidth, i + (padding + 2));

    if (progressLength > base)
    {
        int bonus = progressLength - base;

        if (bonus > barWidth)
            bonus = barWidth;

        for (i = 0; i < bonus; i++)
            DrawCoStatBarCappedCol(buf, 8 * bufWidth, i + (padding + 2));
    }
    else if (progressLength < base)
    {
        int shortfall = base - progressLength;

        if (shortfall > barWidth)
            shortfall = barWidth;

        for (i = 0; i < shortfall; i++)
            DrawCoStatBarMinusCol(buf, 8 * bufWidth, (barWidth - 1 - i) + (padding + 2));
    }

    ApplyBitmap(buf, (void*)(32 * tile + VRAM), bufWidth, 1);
}

// bufWidth: The width of the allocated buffer canvas
// barWidth: The width of the bar itself (in tiles)
// progressLength: The stat's current value, scaled to bar columns
// base: The stat's reference/base value, scaled to bar columns
void DrawStatBarGfxCo(
    int tile, int bufWidth, u16* buf, int tileBase,
    int barWidth, int progressLength, int base)
{
    DrawStatBarCo(tile, 2, bufWidth, barWidth, progressLength, base);
    PutAppliedBitmap(buf, tileBase + (tile & 0x3FF), bufWidth, 1);
}
#endif

