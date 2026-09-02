#include "gbafe.h"
#include "expansion_config.h"

#if FE8_CREDITS

#include "proc.h"
#include "fontgrp.h"
#include "ctc.h"
#include "hardware.h"
#include "bmio.h"
#include "bmlib.h"
#include "bm.h"
#include "event.h"
#include "statscreen.h"
#include "helpbox.h"
#include "gba/syscall.h"
#include "gba/macro.h"

/* Not declared in any header -- src/eventscr.c. */
void ConvoBackgroundFade_Init(struct ConvoBackgroundFadeProc* proc);
void ConvoBackgroundFade_CopyBg3ToBg2(struct ConvoBackgroundFadeProc* proc);
void ConvoBackgroundFade_LoadBg3(struct ConvoBackgroundFadeProc* proc);
void ConvoBackgroundFade_Loop(struct ConvoBackgroundFadeProc* proc);
void ConvoBackgroundFade_End(struct ConvoBackgroundFadeProc* proc);

/* Modern-build port of a credits-sequence patch (by Vesly), reusing the
 * existing "class name intro letter" big-font system (src/opinfo.c) for
 * scrolling header text and this project's own sprite-text system for
 * body text, with per-screen background/CG crossfades.
 *
 * StartCreditsProc() is exposed for whatever event script or game-flow
 * point should start the credits (e.g. after the final chapter's ending
 * event) -- the original patch only wired up a build-time-disabled test
 * hook for this (TESTING_CREDITS in its Installer.event, off by default),
 * not a real trigger point, so there is nothing to port for "when credits
 * start"; that is a game-content decision for whoever calls this.
 *
 * Three simplifications from the original patch, none of which change
 * the credits actually shown, both isolated to internal implementation
 * details:
 * - Body/header glyph drawing uses this project's existing
 *   Text_DrawCharacterAscii instead of the original's own hand-unrolled
 *   "fast path" reimplementation of the exact same thing (DrawHalfRow /
 *   DrawSpriteTextGlyph_BL and friends) -- a performance optimization
 *   this project's existing primitive already provides safely, without
 *   needing to trust a second, unverified bit-manipulation routine for a
 *   one-time, non-performance-critical sequence.
 * - IsImg256Col's CG-side branch is simplified to always return false:
 *   every real entry in gCGDataTable (src/cg.c) has a valid non-null tsa
 *   pointer, so the original's "is this CG a different, TSA-less 256-
 *   color format" check can never be true for any real CG index -- this
 *   is the actual behavior, not an approximation of it.
 * - The credits data's "random background" sentinel (0x37) is out of
 *   range for gConvoBackgroundData (54 entries, valid indices 0-0x35) in
 *   the original patch's own table -- using it as given would read past
 *   the end of that array. Substituted with a fixed, valid background
 *   (bg_House, index 0) for the one credits entry that used it. */

#define BG_Type 1
#define CG_Type 2

struct CreditsStruct
{
    const signed char* header;
    const signed char* body;
    u8 bg;
    u8 type;
    u8 darkenAmount;
    u8 pad;
};

#define LinesOnScreen 11
#define LinesBuffered 13

typedef struct
{
    PROC_HEADER;
    s8 slotIndex[LinesBuffered];
    u8 strLen[LinesBuffered];
    s8 textType;
    u8 bottomHalf;
    s8 strLine;
    u8 slot;
    u8 id;
    u8 bg;
    u8 holding;
    u8 bgType;
    u8 darkenAmount;
    u8 prevDarkenAmount;
    u16 usedRows;
    u16 textTypeBitfield;
    u16 indentBitfield;
    int firstLineIndex;
    int y;
    u32 clock;
    int totalSprites;
} CreditsTextProc;

int ShouldAdvanceFrame(CreditsTextProc* proc);

#define SPRITE_OFFSCREEN_Y -16

#define HeaderType 0
#define BodyType 1

#define HEADER_X_OFFSET 0
#define BODY_X_OFFSET 14
#define INDENT_BODY_X_OFFSET 32
#define MAX_LINE_WIDTH (240 - INDENT_BODY_X_OFFSET)
#define CHAR_NEWLINE 0x01

static int HeldButtonSpeed = 1;
static int DefaultSpeed = 3;
int Width_BigChar = 8;
int DarkenAmount = 0x60;
static int SkipWithStartEnabled = 0;

static int Modulo(int a, int b)
{
    if (b == 0)
        return 0;
    return a % b;
}

extern u8* CONST_DATA gOpinfo_1[]; /* class-intro-letter font glyph bitmaps, src/opinfo.c */
extern struct Font* gActiveFont;

u16 const sSprite_CreditsHeader_new[] = {
    1,
    OAM0_SHAPE_16x32 | OAM0_DOUBLESIZE | OAM0_AFFINE_ENABLE,
    OAM1_SIZE_32x32,
    0,
};

u16 const sSprite_CreditsHeader_works[] = {
    1,
    OAM0_SHAPE_16x16 | OAM0_DOUBLESIZE | OAM0_AFFINE_ENABLE,
    OAM1_SIZE_16x16,
    0,
};

u32 BigFontInit(CreditsTextProc* proc, const signed char* str, int rowID)
{
    u16 offset = gActiveFont->chr_counter << 5;
    CpuFastFill(0, (void*)(offset + OBJ_VRAM0), 0x800);
    ApplyPalette(gPal_ClassIntroLetterFont, 0x10);
    int bufferAdd = 0;

    if (proc->bottomHalf)
    {
        bufferAdd = 0x80;
        proc->textType = BodyType;
    }
    else
    {
        proc->textType = HeaderType;
    }
    proc->bottomHalf ^= 1;
    int len = 0;
    while (*str != 0)
    {
        Decompress((gOpinfo_1[(u8)*str] != 0) ? gOpinfo_1[(u8)*str] : gOpinfo_1[0x58], gGenericBuffer);
        Copy2dChr(gGenericBuffer + bufferAdd, (void*)(offset + OBJ_VRAM0), 2, 2);
        len++;

        str++;
        offset += 0x40;
        if ((offset & 0x3FF) == 0)
            offset += 0x400;

        if ((int)(offset) >= 0x6018000)
            offset = 0;
    }
    proc->strLen[rowID] = len;

    offset += 0x800;
    offset &= 0xF800;
    if ((int)(offset + VRAM) >= 0x6018000)
        offset = 0;

    gActiveFont->chr_counter = offset >> 5;
    return offset;
}

void InitCreditsBodyText(CreditsTextProc* proc, const signed char* str, int rowID)
{
    const signed char* iter;
    int line = 0;
    int curX = 0;
    struct Text* th = gStatScreen.text;

    if (str && *str)
    {
        InitSpriteText(&th[line]);
        SpriteText_DrawBackgroundExt(&th[line], 0);
        Text_SetColor(&th[line], 0);
        iter = str;

        int nextWordWidth = 0;
        while (*iter == CHAR_NEWLINE)
            iter++;

        while (*iter > CHAR_NEWLINE)
        {
            curX = Text_GetCursor(&th[line]);

            if (*iter == ' ')
            {
                const signed char* lookahead = iter + 1;
                nextWordWidth = gActiveFont->glyphs[(u8)*iter]->width;

                while (*lookahead > CHAR_NEWLINE && *lookahead != ' ' && *lookahead != CHAR_NEWLINE)
                {
                    struct Glyph* glyph = gActiveFont->glyphs[(u8)*lookahead++];
                    nextWordWidth += glyph->width;
                }

                if (curX + nextWordWidth > MAX_LINE_WIDTH)
                    break;
            }
            if (curX > MAX_LINE_WIDTH || *iter == CHAR_NEWLINE)
                break;

            iter = (const signed char*)Text_DrawCharacterAscii(&th[line], (const char*)iter);
        }
    }
    proc->strLen[rowID] = curX;
}

void PutBigLetter(int layer, u8 charId, int x, int y, u16 xScale, u16 yScale, const u16* object, int oam2)
{
    int palID = 0;
    if (x > 240)
        return;
    if (yScale <= 8)
        return;
    if (xScale < 8)
        xScale = 8;

    int adjustedCharId = ((charId >> 4) * 0x30) + charId;
    int matrixId = charId & 0x1F;

    SetObjAffine(
        matrixId, Div(+COS(0) << 4, xScale), Div(-SIN(0) << 4, yScale), Div(+SIN(0) << 4, xScale),
        Div(+COS(0) << 4, yScale));

    oam2 += adjustedCharId * 2 + OAM2_LAYER(layer) + OAM2_PAL(palID);
    PutSpriteExt(4, (x & 0x1FF) + (matrixId << 9), y & 0x1FF, object, oam2);
}

static const u16 sBodyTileLut[] = {
    0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20,
};

void PrintBigString(int len, int layer, int x, int y, const u16* object, int oam2)
{
    if (y > 160)
        return;

    for (int i = 0; i < len; i++)
    {
        int ix = x + (i * Width_BigChar);
        PutBigLetter(layer, i, ix, y, 0x100, 0x100, object, oam2);
    }
}

void PutNormalSpriteText(int len, int layer, int x, int y, const u16* object, int oam2)
{
    if (y > 160 || y < -16)
        return;

    len >>= 4;

    for (int i = 0; i < 9; i++)
    {
        int ix = x + (i * 32);
        PutSprite(layer, ix, y, object, oam2 + sBodyTileLut[i]);
    }
}

extern struct CreditsStruct CONST_DATA gCreditsData[];

int TryAdvanceID(CreditsTextProc* proc);
struct ProcCmd const ProcScr_CreditsText[];

int GetDarkenAmount(void)
{
    return DarkenAmount;
}

int GetPrevDarkenAmount(void)
{
    return DarkenAmount;
}

struct ProcCmd const gCreditsFadeBGs[];
struct ProcCmd const gCreditsFade256Cols[];

void CreditsTextLoop(CreditsTextProc* proc)
{
    if (!Proc_Find(gCreditsFadeBGs) && !Proc_Find(gCreditsFade256Cols))
    {
        int darkenAmount = GetDarkenAmount();
        WriteFadedPaletteFromArchive(darkenAmount, darkenAmount, darkenAmount, 0x0000FFFF);
    }

    proc->y -= ShouldAdvanceFrame(proc);

    if (!gCreditsData[proc->id].header && !gCreditsData[proc->id].body)
    {
        Proc_Break(proc);
        return;
    }
    TryAdvanceID(proc);

    int x = 0;
    int bodySprites = 0;
    int headerSprites = 0;

    for (int line = proc->firstLineIndex; line < proc->firstLineIndex + LinesBuffered; ++line)
    {
        int slot = proc->slotIndex[Modulo(line, LinesBuffered)];
        if (slot < 0)
            continue;
        int isBody = proc->textTypeBitfield & (1 << slot);
        int nextLine = Modulo((line + 1), LinesBuffered);
        int nextSlot = proc->slotIndex[nextLine];
        int nextLineIsTop = nextSlot == 0;

        int nextBody = proc->textTypeBitfield & (1 << nextSlot);
        int nextIndent = !((((proc->indentBitfield >> slot) & 1) ^ ((proc->indentBitfield >> nextSlot) & 1)));

        int ix = x;
        int palID = 0;
        if (proc->indentBitfield & (1 << slot))
            ix += INDENT_BODY_X_OFFSET - BODY_X_OFFSET;

        if (isBody)
        {
            ix += BODY_X_OFFSET;
            palID = 1;
        }
        else
        {
            ix += HEADER_X_OFFSET;
        }

        int spriteY = proc->y + (line * 16);

        if (spriteY >= SPRITE_OFFSCREEN_Y && spriteY < 160)
        {
            if (isBody)
            {
                if (spriteY < -16)
                    continue;

                if (nextBody && nextIndent && !nextLineIsTop)
                {
                    int len = proc->strLen[slot] > proc->strLen[nextSlot] ? proc->strLen[slot] : proc->strLen[nextSlot];
                    PutNormalSpriteText(len, 2, ix, spriteY, gObject_32x32, OAM2_PAL(palID) + (slot * 0x40));
                    line++;
                }
                else
                {
                    PutNormalSpriteText(proc->strLen[slot], 2, ix, spriteY, gObject_32x16, OAM2_PAL(palID) + (slot * 0x40));
                }
                bodySprites += proc->strLen[slot] >> 4;
            }
            else
            {
                if (nextBody || nextLineIsTop)
                {
                    PrintBigString(proc->strLen[slot], 2, ix, spriteY - 8, sSprite_CreditsHeader_works, (slot * 0x40));
                }
                else
                {
                    PrintBigString(proc->strLen[slot], 2, ix, spriteY - 16, sSprite_CreditsHeader_new, (slot * 0x40));
                    line++;
                }
                headerSprites += proc->strLen[slot];
            }
        }
    }

    proc->totalSprites = headerSprites + bodySprites;
}

int GetFreeRow(CreditsTextProc* proc)
{
    for (int i = 0; i < LinesBuffered; ++i)
    {
        if (!(proc->usedRows & (1 << i)))
        {
            proc->usedRows |= (1 << i);
            return i;
        }
    }
    return -1;
}

void FreeRow(CreditsTextProc* proc, int i)
{
    i = Modulo(i, LinesBuffered);
    proc->slotIndex[i] = -1;
    proc->usedRows &= ~(1 << i);
    CpuFastFill(0, (void*)(0x800 * i + OBJ_VRAM0), 0x800);
}

void SetIndent(CreditsTextProc* proc, int slot)
{
    proc->indentBitfield |= (1 << (Modulo(slot, LinesBuffered)));
}

void UnsetIndent(CreditsTextProc* proc, int slot)
{
    proc->indentBitfield &= ~(1 << (Modulo(slot, LinesBuffered)));
}

const signed char* GetStringAtLine(const signed char* str, int targetLine, CreditsTextProc* proc, int slot)
{
    UnsetIndent(proc, slot);
    if (!str || targetLine < 0)
        return NULL;

    int currentLine = 0;

    while (*str)
    {
        if (currentLine == targetLine)
            return str;

        int width = 0;
        const signed char* lastSpace = NULL;

        while (*str > 1)
        {
            if (*str == ' ')
                lastSpace = str;

            struct Glyph* glyph = gActiveFont->glyphs[(u8)*str];
            width += glyph->width;
            str++;

            if (width > MAX_LINE_WIDTH)
            {
                if (currentLine + 1 == targetLine)
                    SetIndent(proc, slot);
                if (lastSpace)
                    str = lastSpace + 1;
                break;
            }
        }

        if (*str == CHAR_NEWLINE)
            str++;

        currentLine++;
    }

    return NULL;
}

int GetNextLineNum(const signed char* str, int num)
{
    if (!str || num < -1)
        return -1;

    int currentLine = 0;

    while (*str)
    {
        if (currentLine == num + 1)
            return currentLine;

        int width = 0;
        const signed char* lastSpace = NULL;

        while (*str > 1)
        {
            if (*str == ' ')
                lastSpace = str;

            struct Glyph* glyph = gActiveFont->glyphs[(u8)*str];
            width += glyph->width;
            str++;

            if (width > MAX_LINE_WIDTH)
            {
                if (lastSpace)
                    str = lastSpace + 1;
                break;
            }
        }

        if (*str == CHAR_NEWLINE)
            str++;

        currentLine++;
    }

    return -1;
}

const signed char* GetNextLineOfType(CreditsTextProc* proc, int type, int slot)
{
    int id = proc->id;
    int strLine = proc->strLine;
    const signed char* str;
    const signed char* originalStr;

    if (type == HeaderType)
        str = gCreditsData[id].header;
    else
        str = gCreditsData[id].body;
    originalStr = str;

    strLine = GetNextLineNum(str, strLine);
    str = GetStringAtLine(str, strLine, proc, slot);
    if (!str || !*str)
    {
        proc->strLine = -1;
        return NULL;
    }

    int nextLine = GetNextLineNum(originalStr, strLine);
    proc->strLine = strLine;

    if (nextLine < 0)
        proc->strLine = nextLine;

    return str;
}

void InitNextBG(CreditsTextProc* proc, int slot);

const signed char* GetNextStrLine(CreditsTextProc* proc, int slot)
{
    int id = proc->id;
    const signed char* str;

    switch (proc->textType)
    {
    case HeaderType:
        str = GetNextLineOfType(proc, HeaderType, slot);
        if (proc->strLine == -1)
            proc->textType = BodyType;
        return str;

    case BodyType:
        str = GetNextLineOfType(proc, BodyType, slot);
        if (proc->strLine == -1)
        {
            proc->textType = HeaderType;
            proc->id++;
            InitNextBG(proc, slot);
        }
        return str;
    }
    return gCreditsData[id].header;
}

/* Every real entry in gCGDataTable (src/cg.c) has a valid tsa pointer, so
 * this can never be true for a real CG index -- see this file's header
 * comment. */
static bool IsCgImg256Col(int id)
{
    (void)id;
    return false;
}

static bool IsBgImg256Col(int id)
{
    return (int)gConvoBackgroundData[id].tsa <= 1;
}

int IsImg256Col(int type, int id)
{
    switch (type)
    {
    case BG_Type:
        return IsBgImg256Col(id);
    case CG_Type:
        return IsCgImg256Col(id);
    }
    return false;
}

void fadePalettesOut(struct ConvoBackgroundFadeProc* proc)
{
    int currentFadeStep = (proc->fadeTimer += proc->fadeSpeed);
    int startLevel = GetPrevDarkenAmount();
    int totalSteps = startLevel;

    if (currentFadeStep > totalSteps)
        currentFadeStep = totalSteps;

    int darkenAmount = startLevel - ((currentFadeStep * startLevel) / totalSteps);
    WriteFadedPaletteFromArchive(darkenAmount, darkenAmount, darkenAmount, 0x0000FFFF);

    if (currentFadeStep >= totalSteps)
    {
        proc->fadeTimer = 0;
        Proc_Break(proc);
    }
}

void fadePalettesIn(struct ConvoBackgroundFadeProc* proc)
{
    int currentFadeStep = (proc->fadeTimer += proc->fadeSpeed);
    int finalLevel = GetDarkenAmount();
    int totalSteps = finalLevel;

    if (currentFadeStep > totalSteps)
        currentFadeStep = totalSteps;

    int darkenAmount = (currentFadeStep * finalLevel) / totalSteps;
    WriteFadedPaletteFromArchive(darkenAmount, darkenAmount, darkenAmount, 0x0000FFFF);

    if (currentFadeStep >= totalSteps)
        Proc_Break(proc);
}

struct ProcCmd const gCreditsFade256Cols[] = {
    PROC_YIELD,
    PROC_REPEAT(fadePalettesOut),
    PROC_CALL(ConvoBackgroundFade_End),
    PROC_CALL(ConvoBackgroundFade_LoadBg3),
    PROC_REPEAT(fadePalettesIn),
    PROC_END,
};

struct ProcCmd const gCreditsFadeBGs[] = {
    PROC_YIELD,

    PROC_CALL(ConvoBackgroundFade_Init),
    PROC_YIELD,

    PROC_CALL(ConvoBackgroundFade_CopyBg3ToBg2),
    PROC_YIELD,

    PROC_CALL(ConvoBackgroundFade_LoadBg3),
    PROC_CALL(ArchiveCurrentPalettes),
    PROC_YIELD,

    PROC_REPEAT(ConvoBackgroundFade_Loop),
    PROC_CALL(ConvoBackgroundFade_End),

    PROC_END,
};

void InitNextBG(CreditsTextProc* proc, int slot)
{
    int bg = gCreditsData[proc->id].bg;
    int type = gCreditsData[proc->id].type;
    int darkenAmount = gCreditsData[proc->id].darkenAmount;
    if (!darkenAmount)
        darkenAmount = DarkenAmount;
    if (type != BG_Type && type != CG_Type)
        return;

    if (bg == 0xFF || bg == proc->bg)
        return;

    int canFadeBetweenImgs = true;
    if (IsImg256Col(type, bg) || IsImg256Col(proc->bgType, proc->bg))
        canFadeBetweenImgs = false;

    proc->prevDarkenAmount = proc->darkenAmount;
    proc->bgType = type;
    proc->bg = bg;
    proc->darkenAmount = darkenAmount;
    Proc_EndEach(gCreditsFadeBGs);
    Proc_EndEach(gCreditsFade256Cols);

    if (canFadeBetweenImgs)
    {
        struct ConvoBackgroundFadeProc* otherProc = Proc_Start(gCreditsFadeBGs, (void*)PROC_TREE_3);
        otherProc->fadeType = 0;
        otherProc->unkType = type;
        otherProc->bgIndex = bg;
        otherProc->fadeSpeed = 2;
        otherProc->fadeTimer = 0;
        otherProc->pEventEngine = (void*)proc;
    }
    else
    {
        struct ConvoBackgroundFadeProc* otherProc = Proc_Start(gCreditsFade256Cols, (void*)PROC_TREE_3);
        otherProc->fadeType = 0;
        otherProc->unkType = type;
        otherProc->bgIndex = bg;
        otherProc->fadeSpeed = 5;
        otherProc->fadeTimer = 0;
        otherProc->pEventEngine = (void*)proc;
    }
}

int InitNextLine(CreditsTextProc* proc, int slot)
{
    int type = proc->textType;

    proc->slot = slot;
    int rowID = GetFreeRow(proc);
    if (rowID < 0)
        return false;

    const signed char* str = GetNextStrLine(proc, rowID);

    if (!str || !*str)
    {
        str = GetNextStrLine(proc, slot);
        if (!str || !*str)
            return false;
    }

    proc->slotIndex[slot] = rowID;

    switch (type)
    {
    case HeaderType:
        proc->textTypeBitfield &= ~(1 << rowID);
        BigFontInit(proc, str, rowID);
        return true;

    case BodyType:
        proc->textTypeBitfield |= (1 << rowID);
        InitCreditsBodyText(proc, str, rowID);
        return true;
    }
    return false;
}

int TryAdvanceID(CreditsTextProc* proc)
{
    for (int i = 0; i < LinesBuffered; ++i)
    {
        int lineIndex = proc->firstLineIndex + i;
        int spriteY = proc->y + (lineIndex * 16);
        int slot = Modulo(lineIndex, LinesBuffered);
        if (spriteY < SPRITE_OFFSCREEN_Y && proc->slotIndex[slot] >= 0)
        {
            FreeRow(proc, slot);
            if (!slot)
                gActiveFont->chr_counter = 0;
        }
        if (spriteY >= SPRITE_OFFSCREEN_Y && spriteY < 160)
        {
            if (proc->slotIndex[slot] < 0)
                InitNextLine(proc, slot);
        }
    }

    return false;
}

void InitCreditsText(CreditsTextProc* proc)
{
    ResetText();
    ResetTextFont();
    InitSpriteTextFont(&gHelpBoxSt.font, OBJ_VRAM0, 0x11);
    SetTextFontGlyphs(1);
    ApplyPalette(Pal_TalkText, 0x11);
}

struct ProcCmd const ProcScr_CreditsText[] = {
    PROC_NAME("Credits Proc"),
    PROC_SLEEP(0),
    PROC_CALL(LockGame),
    PROC_CALL(BMapDispSuspend),
    PROC_CALL(InitCreditsText),
    PROC_REPEAT(CreditsTextLoop),
    PROC_CALL(StartFastFadeToBlack),
    PROC_REPEAT(WaitForFade),
    PROC_END_EACH(gCreditsFadeBGs),
    PROC_SLEEP(16),

    PROC_CALL(UnlockGame),
    PROC_CALL(BMapDispResume),
    PROC_CALL(RefreshUnitSprites),

    PROC_END,
};

/* Public entry point: start the credits sequence as a blocking child of
 * `parent` (e.g. from an event script's ASMC command). Not wired up to
 * any specific in-game trigger -- see this file's header comment. */
void StartCreditsProc(ProcPtr parent)
{
    CreditsTextProc* proc = (void*)Proc_StartBlocking(ProcScr_CreditsText, parent);

    for (int i = 0; i < LinesBuffered; ++i)
    {
        proc->slotIndex[i] = -1;
        proc->strLen[i] = 0;
    }
    proc->usedRows = 0;
    proc->textTypeBitfield = 0;
    proc->indentBitfield = 0;
    proc->firstLineIndex = 0;
    proc->y = 160;
    proc->clock = GetGameClock();
    proc->textType = 0;
    proc->bottomHalf = 0;
    proc->strLine = -1;
    proc->slot = 0;
    proc->id = 0;
    proc->totalSprites = 0;
    proc->holding = 0;
    proc->bg = 0xFF;
    proc->bgType = 0xFF;
    proc->darkenAmount = 0;
    proc->prevDarkenAmount = 0;
    ArchiveCurrentPalettes();
    InitNextBG(proc, 0);
}

int ShouldAdvanceFrame(CreditsTextProc* proc)
{
    u32 clock = GetGameClock();
    u16 keys = gKeyStatusPtr->newKeys | gKeyStatusPtr->heldKeys;
    int speed = DefaultSpeed;
    int multiplier = false;

    if (keys & (B_BUTTON | A_BUTTON))
    {
        speed = HeldButtonSpeed;
        multiplier = proc->holding >> 5;

        proc->holding++;
        if (proc->holding > 0x20)
            proc->holding = 0x20;
    }
    else
    {
        proc->holding = 0;
    }

    if ((keys & START_BUTTON) && SkipWithStartEnabled)
        Proc_Break(proc);

    if ((clock - proc->clock) >= (u32)speed)
    {
        proc->clock = clock;
        if (proc->y < -(proc->firstLineIndex * 16 + 16))
            proc->firstLineIndex++;

        return 1 * (1 + multiplier);
    }

    return false;
}

/* --- Credits content ---------------------------------------------------- */

#define NL "\x01"

static const signed char emptyString[] = "  ";
static const signed char emptyStringLong[] = "  " NL "  " NL "  " NL "  " NL "  " NL "  " NL "  " NL "  ";
static const signed char theEnd[] = "  T h e   E n d";

/* Custom-campaign OC portraits (FE8_CUSTOM_CAMPAIGN). Kept in sync with
 * CREDITS.md's "Custom Campaign Portraits" table -- update both when
 * adding/changing a custom-campaign portrait. Hannah/Francis are credited
 * even though src/portrait_data.c no longer uses them (see that file). */
static const signed char header1[] = "Custom Campaign Portraits";
static const signed char body1[] =
    " Hannah portrait by Nickt" NL
    " Francis portrait by Nickt" NL
    " Frederick portrait by Nickt" NL
    " Fox portrait by Nickt" NL
    " Liz portrait by RandomWizard" NL
    " Ishkode portrait by Eden" NL
    " Wakwi portrait by Eden";

/* Kept in sync with CREDITS.md's "Map Tilesets" table. */
static const signed char header2[] = "Map Tilesets";
static const signed char body2[] =
    " Prologue tileset by WAve, RandomWizard, Beast";

/* Song arrangements only -- see CREDITS.md's "Custom BGM" section for the
 * instrument-map attribution (no per-song artist there) and the original
 * compositions' rights holders. */
static const signed char header3[] = "Custom BGM";
static const signed char body3[] =
    " Venus Lighthouse arrangement by AReliableChair" NL
    " Goldenrod City arrangement by AReliableChair";

/* Kept in sync with CREDITS.md's "CO Screen Graphics" table. */
static const signed char header5[] = "CO Screen Graphics";
static const signed char body5[] =
    " CO info screen backdrop by PatrickHoang";

/* Kept in sync with CREDITS.md's "Other Portraits" table. Unconditional
 * (not gated behind any feature flag) since this replaces the vanilla
 * campaign's own CHARACTER_ONEILL portrait, not a custom-campaign OC --
 * see src/portrait_data.c. */
static const signed char header6[] = "Other Portraits";
static const signed char body6[] =
    " Kargan (replaces O'Neill) portrait by Eden";

/* Kept in sync with CREDITS.md's "Ported Code Patches" table. */
static const signed char header4[] = "Ported Patches";
static const signed char body4[] =
    " Debugger, Purchase Generics, Mapgen, Credits," NL
    " Danger Bones, Select View Growths by Vesly" NL
    " Battle Stats No Anims by Tequila, Vesly, Alusq" NL
    " Draw Map Anims by Vesly, Viktor Hahn" NL
    " Battle Animation Numbers by Huichelaar" NL
    " Multipalette BG by Huichelaar" NL
    " MMB by Zane" NL
    " Extend Desc Box by Vesly" NL
    " Display Obtainable Item by Mkol, Huichelaar, Vesly" NL
    " HP Bars by circleseverywhere, Tequila," NL
    "  hypergammaspaces, Alusq" NL
    " Alpha Sprite Arrow by JesterWizard" NL
    " Debuffs, Promote Command, Turn Autosave," NL
    "  Anims Fast Forward by Vesly" NL
    " Group AI by Vesly, PhantomSentine" NL
    " Text Chapter Names by circleseverywhere," NL
    "  hypergammaspaces" NL
    " NIMAP2 patch: community; repo integration by Vesly" NL
    " Rand Bgm / Continue Bgm Battle: ported from SRR;" NL
    "  repo integration by Vesly";

enum
{
    LyonStoneCG = 2,
    DemonKingCG = 5,
};

enum
{
    /* RandomBG (0x37) from the original patch is out of range for
     * gConvoBackgroundData (54 entries) -- substituted with a fixed,
     * valid background here; see this file's header comment. */
    BurningBG = 0x2B,
    BlackBG = 0x35,
    SubstituteRandomBG = 0,
};

struct CreditsStruct CONST_DATA gCreditsData[] = {
#if FE8_CUSTOM_CAMPAIGN
    { header1, body1, LyonStoneCG, CG_Type, 0, 0 },
#endif
#if FE8_NEW_TILESETS
    { header2, body2, SubstituteRandomBG, BG_Type, 0, 0 },
#endif
#if FE8_NIMAP2
    { header3, body3, DemonKingCG, CG_Type, 0x80, 0 },
#endif
#if FE8_CO_POWERS
    { header5, body5, SubstituteRandomBG, BG_Type, 0, 0 },
#endif
    { header6, body6, SubstituteRandomBG, BG_Type, 0, 0 },
    { header4, body4, BurningBG, BG_Type, 0, 0 },
    { emptyString, emptyStringLong, 0xFF, 0, 0, 0 },
    { theEnd, emptyString, BlackBG, BG_Type, 0, 0 },
    { emptyString, emptyStringLong, 0xFF, 0, 0, 0 },
    { NULL, NULL, 0, 0, 0, 0 },
};

#endif /* FE8_CREDITS */
