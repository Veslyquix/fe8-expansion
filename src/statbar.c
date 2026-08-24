#include "global.h"
#include "bmlib.h"
#include "functions.h"
#include "variables.h"

/* These should related to status-bar gfx for stat-screen */

void UnusedDrawOutline(u8 *buf, int bufWidth, int col)
{
    buf[0 * bufWidth + col] = 4;
    buf[1 * bufWidth + col] = 4;
    buf[2 * bufWidth + col] = 4;
    buf[3 * bufWidth + col] = 4;
    buf[4 * bufWidth + col] = 4;
}

void DrawStatBarLeftBorder(u8 *buf, int bufWidth, int col)
{
    buf[0 * bufWidth + col] = 4;
    buf[1 * bufWidth + col] = 4;
    buf[2 * bufWidth + col] = 4;
    buf[3 * bufWidth + col] = 4;
}

void DrawStatBarShadow(u8 *buf, int bufWidth, int col)
{
    buf[1 * bufWidth + col] = 4;
    buf[2 * bufWidth + col] = 4;
    buf[3 * bufWidth + col] = 4;
    buf[4 * bufWidth + col] = 4;
}

void DrawStatBarRightBorder(u8 *buf, int bufWidth, int col)
{
    buf[0 * bufWidth + col] = 4;
    buf[1 * bufWidth + col] = 4;
    buf[2 * bufWidth + col] = 4;
    buf[3 * bufWidth + col] = 4;
    buf[4 * bufWidth + col] = 4;
}

void DrawStatBarUnfilledCol(u8 *buf, int bufWidth, int col)
{
    buf[0 * bufWidth + col] = 4;
    buf[1 * bufWidth + col] = 14;
    buf[2 * bufWidth + col] = 3;
    buf[3 * bufWidth + col] = 4;
    buf[4 * bufWidth + col] = 4;
}

void DrawStatBarFilledCol(u8 *buf, int bufWidth, int col)
{
    buf[1 * bufWidth + col] = 1;
    buf[2 * bufWidth + col] = 5;
}

void DrawStatBarCappedCol(u8 *buf, int bufWidth, int col)
{
    buf[1 * bufWidth + col] = 13;
    buf[2 * bufWidth + col] = 12;
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
void DrawStatBarMinusCol(u8 *buf, int bufWidth, int col)
{
    buf[1 * bufWidth + col] = 10;
    buf[2 * bufWidth + col] = 11;
}

/* CO screen variant of DrawStatBar: draws a `minusLength`-wide run of red
 * ("lost") columns via DrawStatBarMinusCol, right after the filled
 * (progressLength) columns, for a stat whose total has dropped below its
 * base -- vanilla DrawStatBar has no notion of a stat going backwards, only
 * capped (cappedLength, green, total > max) and filled (progressLength,
 * yellow). progressLength and minusLength are mutually exclusive with
 * cappedLength in practice (a stat is either capped-over or shortfallen,
 * never both at once), same as progressLength/cappedLength already are in
 * DrawStatBar -- callers are expected to only pass one of cappedLength or
 * minusLength as nonzero. */
void DrawStatBarCo(
    int tile, int padding, int bufWidth, int barWidth, int progressLength, int cappedLength, int minusLength)
{
    int i;
    u8 *buf = gGenericBuffer;
    CpuFastFill(0, buf, 0x40 * bufWidth);

    for (i = 1; i < barWidth + 1; i++)
        DrawStatBarUnfilledCol(buf, 8 * bufWidth, i + (padding + 1));

    DrawStatBarLeftBorder(buf, 8 * bufWidth, padding + 1);
    DrawStatBarRightBorder(buf, 8 * bufWidth, padding + barWidth + 2);
    DrawStatBarShadow(buf, 8 * bufWidth, padding + barWidth + 3);

    for (i = 0; i < progressLength; i++)
        DrawStatBarFilledCol(buf, 8 * bufWidth, i + (padding + 2));

    for (i = 0; i < cappedLength; i++)
        DrawStatBarCappedCol(buf, 8 * bufWidth, i + progressLength + padding + 2);

    for (i = 0; i < minusLength; i++)
        DrawStatBarMinusCol(buf, 8 * bufWidth, i + progressLength + padding + 2);

    ApplyBitmap(buf, (void*)(32 * tile + VRAM), bufWidth, 1);
}

// bufWidth: The width of the allocated buffer canvas
// barWidth: The width of the bar itself (in tiles)
// progressLength: The length of the "progress" of the bar (the yellow part)
// cappedLength: Same as above, controls the part that flashes green when stat capped
// minusLength: Same as above, controls the part drawn red when total < base
void DrawStatBarGfxCo(
    int tile, int bufWidth, u16* buf, int tileBase,
    int barWidth, int progressLength, int cappedLength, int minusLength)
{
    DrawStatBarCo(tile, 2, bufWidth, barWidth, progressLength, cappedLength, minusLength);
    PutAppliedBitmap(buf, tileBase + (tile & 0x3FF), bufWidth, 1);
}
#endif

