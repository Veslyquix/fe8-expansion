#include "global.h"
#include <string.h>
#include "fontgrp.h"
#include "hardware.h"
#include "proc.h"
#include "sio.h"
#include "bmunit.h"
#include "sio_core.h"
#include "bmlib.h"
#include "bmsave.h"
#include "bmio.h"
#include "expansion_locale.h"
#include "prepscreen.h"
#include "uiutils.h"
#include "text_utf8.h"
#include "constants/characters.h"

struct ProcCmd CONST_DATA ProcScr_TacticianNameSelection[] = {
    PROC_YIELD,
    PROC_CALL(Tactician_InitScreen),
    PROC_CALL(FadeInBlackSpeed20),
    PROC_YIELD,
    PROC_CALL(ClearLinkArenaUiBlendWindow),
PROC_LABEL(0),
    PROC_REPEAT(Tactician_Loop),
    PROC_GOTO(2),
PROC_LABEL(1),
    PROC_CALL(Tactician_PageFade_Init),
    PROC_REPEAT(Tactician_PageFadeOut_Loop),
    PROC_CALL(Tactician_SwapPage),
    PROC_REPEAT(Tactician_PageFadeIn_Loop),
    PROC_GOTO(0),
PROC_LABEL(3),
    PROC_CALL(NameSelect_DrawName),
    PROC_REPEAT(NameSelect_ConfirmLoop),
    PROC_GOTO(0),
PROC_LABEL(2),
    PROC_CALL(SetLinkArenaUiBlendWindow),
    PROC_CALL(FadeOutBlackSpeed20Locking),
    PROC_YIELD,
    PROC_CALL(Tactician_OnEnd),
    PROC_END,
};

const struct TacticianTextConf gTacticianTextConf[] = {
    [0] = {
        .str = { "", "","","","","","","","","","","",},
        .x = 0x0,
        .y = 0x0,
        .adj_idx = { 0, 0, 0, 0 },
    },
    [1] = {
        .str = { " ", "",""," ","",""," ","",""," ","","",},
        .x = 0xCA,
        .y = 0x48,
        .kind = 1,
        .adj_idx = { 5, 2, 60, 6 },
        .action = 1
    },
    [2] = {
        .str = { " ", "",""," ","",""," ","",""," ","","",},
        .x = 0xCA,
        .y = 0x58,
        .kind = 1,
        .adj_idx = { 1, 3, 65, 11 },
        .action = 2
    },
    [3] = {
        .str = { " ", "",""," ","",""," ","",""," ","","",},
        .x = 0xCA,
        .y = 0x68,
        .kind = 1,
        .adj_idx = { 2, 4, 70, 16 },
        .action = 3
    },
    [4] = {
        .str = { " ", "",""," ","",""," ","",""," ","","",},
        .x = 0xCA,
        .y = 0x78,
        .kind = 1,
        .adj_idx = { 5, 5, 75, 21 },
        .action = 4
    },
    [5] = {
        .str = { " ", "",""," ","",""," ","",""," ","","",},
        .x = 0xCA,
        .y = 0x88,
        .kind = 1,
        .adj_idx = { 4, 4, 80, 26 },
        .action = 5
    },
    [6] = {
        .str = { "A", "","","A","","","A","","","A","","",},
        .x = 0x10,
        .y = 0x48,
        .adj_idx = { 26, 11, 4, 7 },
    },
    [7] = {
        .str = { "B", "","","B","","","B","","","B","","",},
        .x = 0x1A,
        .y = 0x48,
        .adj_idx = { 27, 12, 6, 8 },
    },
    [8] = {
        .str = { "C", "","","C","","","C","","","C","","",},
        .x = 0x24,
        .y = 0x48,
        .adj_idx = { 28, 13, 7, 9 },
    },
    [9] = {
        .str = { "D", "","","D","","","D","","","D","","",},
        .x = 0x2E,
        .y = 0x48,
        .adj_idx = { 29, 14, 8, 10 },
    },
    [10] = {
        .str = { "E", "","","E","","","E","","","E","","",},
        .x = 0x38,
        .y = 0x48,
        .adj_idx = { 30, 15, 9, 31 },
    },
    [11] = {
        .str = { "P", "","","P","","","P","","","P","","",},
        .x = 0x10,
        .y = 0x58,
        .adj_idx = { 6, 16, 4, 12 },
    },
    [12] = {
        .str = { "Q", "","","Q","","","Q","","","Q","","",},
        .x = 0x1A,
        .y = 0x58,
        .adj_idx = { 7, 17, 11, 13 },
    },
    [13] = {
        .str = { "R", "","","R","","","R","","","R","","",},
        .x = 0x24,
        .y = 0x58,
        .adj_idx = { 8, 18, 12, 14 },
    },
    [14] = {
        .str = { "S", "","","S","","","S","","","S","","",},
        .x = 0x2E,
        .y = 0x58,
        .adj_idx = { 9, 19, 13, 15 },
    },
    [15] = {
        .str = { "T", "","","T","","","T","","","T","","",},
        .x = 0x38,
        .y = 0x58,
        .adj_idx = { 10, 20, 14, 36 },
    },
    [16] = {
        .str = { "a", "","","a","","","a","","","a","","",},
        .x = 0x10,
        .y = 0x68,
        .adj_idx = { 11, 21, 4, 17 },
    },
    [17] = {
        .str = { "b", "","","b","","","b","","","b","","",},
        .x = 0x1A,
        .y = 0x68,
        .adj_idx = { 12, 22, 16, 18 },
    },
    [18] = {
        .str = { "c", "","","c","","","c","","","c","","",},
        .x = 0x24,
        .y = 0x68,
        .adj_idx = { 13, 23, 17, 19 },
    },
    [19] = {
        .str = { "d", "","","d","","","d","","","d","","",},
        .x = 0x2E,
        .y = 0x68,
        .adj_idx = { 14, 24, 18, 20 },
    },
    [20] = {
        .str = { "e", "","","e","","","e","","","e","","",},
        .x = 0x38,
        .y = 0x68,
        .adj_idx = { 15, 25, 19, 41 },
    },
    [21] = {
        .str = { "p", "","","p","","","p","","","p","","",},
        .x = 0x10,
        .y = 0x78,
        .adj_idx = { 16, 26, 4, 22 },
    },
    [22] = {
        .str = { "q", "","","q","","","q","","","q","","",},
        .x = 0x1A,
        .y = 0x78,
        .adj_idx = { 17, 27, 21, 23 },
    },
    [23] = {
        .str = { "r", "","","r","","","r","","","r","","",},
        .x = 0x24,
        .y = 0x78,
        .adj_idx = { 18, 28, 22, 24 },
    },
    [24] = {
        .str = { "s", "","","s","","","s","","","s","","",},
        .x = 0x2E,
        .y = 0x78,
        .adj_idx = { 19, 29, 23, 25 },
    },
    [25] = {
        .str = { "t", "","","t","","","t","","","t","","",},
        .x = 0x38,
        .y = 0x78,
        .adj_idx = { 20, 30, 24, 46 },
    },
    [26] = {
        .str = { "1", "","","1","","","1","","","1","","",},
        .x = 0x10,
        .y = 0x88,
        .adj_idx = { 21, 6, 5, 27 },
    },
    [27] = {
        .str = { "2", "","","2","","","2","","","2","","",},
        .x = 0x1A,
        .y = 0x88,
        .adj_idx = { 22, 7, 26, 28 },
    },
    [28] = {
        .str = { "3", "","","3","","","3","","","3","","",},
        .x = 0x24,
        .y = 0x88,
        .adj_idx = { 23, 8, 27, 29 },
    },
    [29] = {
        .str = { "4", "","","4","","","4","","","4","","",},
        .x = 0x2E,
        .y = 0x88,
        .adj_idx = { 24, 9, 28, 30 },
    },
    [30] = {
        .str = { "5", "","","5","","","5","","","5","","",},
        .x = 0x38,
        .y = 0x88,
        .adj_idx = { 25, 10, 29, 51 },
    },
    [31] = {
        .str = { "F", "","","F","","","F","","","F","","",},
        .x = 0x50,
        .y = 0x48,
        .adj_idx = { 51, 36, 10, 32 },
    },
    [32] = {
        .str = { "G", "","","G","","","G","","","G","","",},
        .x = 0x5A,
        .y = 0x48,
        .adj_idx = { 52, 37, 31, 33 },
    },
    [33] = {
        .str = { "H", "","","H","","","H","","","H","","",},
        .x = 0x64,
        .y = 0x48,
        .adj_idx = { 53, 38, 32, 34 },
    },
    [34] = {
        .str = { "I", "","","I","","","I","","","I","","",},
        .x = 0x6E,
        .y = 0x48,
        .adj_idx = { 54, 39, 33, 35 },
    },
    [35] = {
        .str = { "J", "","","J","","","J","","","J","","",},
        .x = 0x78,
        .y = 0x48,
        .adj_idx = { 55, 40, 34, 56 },
    },
    [36] = {
        .str = { "U", "","","U","","","U","","","U","","",},
        .x = 0x50,
        .y = 0x58,
        .adj_idx = { 31, 41, 15, 37 },
    },
    [37] = {
        .str = { "V", "","","V","","","V","","","V","","",},
        .x = 0x5A,
        .y = 0x58,
        .adj_idx = { 32, 42, 36, 38 },
    },
    [38] = {
        .str = { "W", "","","W","","","W","","","W","","",},
        .x = 0x64,
        .y = 0x58,
        .adj_idx = { 33, 43, 37, 39 },
    },
    [39] = {
        .str = { "X", "","","X","","","X","","","X","","",},
        .x = 0x6E,
        .y = 0x58,
        .adj_idx = { 34, 44, 38, 40 },
    },
    [40] = {
        .str = { "Y", "","","Y","","","Y","","","Y","","",},
        .x = 0x78,
        .y = 0x58,
        .adj_idx = { 35, 45, 39, 61 },
    },
    [41] = {
        .str = { "f", "","","f","","","f","","","f","","",},
        .x = 0x50,
        .y = 0x68,
        .adj_idx = { 36, 46, 20, 42 },
    },
    [42] = {
        .str = { "g", "","","g","","","g","","","g","","",},
        .x = 0x5A,
        .y = 0x68,
        .adj_idx = { 37, 47, 41, 43 },
    },
    [43] = {
        .str = { "h", "","","h","","","h","","","h","","",},
        .x = 0x64,
        .y = 0x68,
        .adj_idx = { 38, 48, 42, 44 },
    },
    [44] = {
        .str = { "i", "","","i","","","i","","","i","","",},
        .x = 0x6E,
        .y = 0x68,
        .adj_idx = { 39, 49, 43, 45 },
    },
    [45] = {
        .str = { "j", "","","j","","","j","","","j","","",},
        .x = 0x78,
        .y = 0x68,
        .adj_idx = { 40, 50, 44, 66 },
    },
    [46] = {
        .str = { "u", "","","u","","","u","","","u","","",},
        .x = 0x50,
        .y = 0x78,
        .adj_idx = { 41, 51, 25, 47 },
    },
    [47] = {
        .str = { "v", "","","v","","","v","","","v","","",},
        .x = 0x5A,
        .y = 0x78,
        .adj_idx = { 42, 52, 46, 48 },
    },
    [48] = {
        .str = { "w", "","","w","","","w","","","w","","",},
        .x = 0x64,
        .y = 0x78,
        .adj_idx = { 43, 53, 47, 49 },
    },
    [49] = {
        .str = { "x", "","","x","","","x","","","x","","",},
        .x = 0x6E,
        .y = 0x78,
        .adj_idx = { 44, 54, 48, 50 },
    },
    [50] = {
        .str = { "y", "","","y","","","y","","","y","","",},
        .x = 0x78,
        .y = 0x78,
        .adj_idx = { 45, 55, 49, 71 },
    },
    [51] = {
        .str = { "6", "","","6","","","6","","","6","","",},
        .x = 0x50,
        .y = 0x88,
        .adj_idx = { 46, 31, 30, 52 },
    },
    [52] = {
        .str = { "7", "","","7","","","7","","","7","","",},
        .x = 0x5A,
        .y = 0x88,
        .adj_idx = { 47, 32, 51, 53 },
    },
    [53] = {
        .str = { "8", "","","8","","","8","","","8","","",},
        .x = 0x64,
        .y = 0x88,
        .adj_idx = { 48, 33, 52, 54 },
    },
    [54] = {
        .str = { "9", "","","9","","","9","","","9","","",},
        .x = 0x6E,
        .y = 0x88,
        .adj_idx = { 49, 34, 53, 55 },
    },
    [55] = {
        .str = { "0", "","","0","","","0","","","0","","",},
        .x = 0x78,
        .y = 0x88,
        .adj_idx = { 50, 35, 54, 76 },
    },
    [56] = {
        .str = { "K", "","","K","","","K","","","K","","",},
        .x = 0x90,
        .y = 0x48,
        .adj_idx = { 76, 61, 35, 57 },
    },
    [57] = {
        .str = { "L", "","","L","","","L","","","L","","",},
        .x = 0x9A,
        .y = 0x48,
        .adj_idx = { 77, 62, 56, 58 },
    },
    [58] = {
        .str = { "M", "","","M","","","M","","","M","","",},
        .x = 0xA4,
        .y = 0x48,
        .adj_idx = { 78, 63, 57, 59 },
    },
    [59] = {
        .str = { "N", "","","N","","","N","","","N","","",},
        .x = 0xAE,
        .y = 0x48,
        .adj_idx = { 79, 64, 58, 60 },
    },
    [60] = {
        .str = { "O", "","","O","","","O","","","O","","",},
        .x = 0xB8,
        .y = 0x48,
        .adj_idx = { 80, 65, 59, 4 },
    },
    [61] = {
        .str = { "Z", "","","Z","","","Z","","","Z","","",},
        .x = 0x90,
        .y = 0x58,
        .adj_idx = { 56, 66, 40, 62 },
    },
    [62] = {
        .str = { "!", "","","!","","","!","","","!","","",},
        .x = 0x9A,
        .y = 0x58,
        .adj_idx = { 57, 67, 61, 63 },
    },
    [63] = {
        .str = { "?", "","","?","","","?","","","?","","",},
        .x = 0xA4,
        .y = 0x58,
        .adj_idx = { 58, 68, 62, 64 },
    },
    [64] = {
        .str = { ",", "","",",","","",",","","",",","","",},
        .x = 0xAE,
        .y = 0x58,
        .adj_idx = { 59, 69, 63, 65 },
    },
    [65] = {
        .str = { ".", "","",".","","",".","","",".","","",},
        .x = 0xB8,
        .y = 0x58,
        .adj_idx = { 60, 70, 64, 4 },
    },
    [66] = {
        .str = { "k", "","","k","","","k","","","k","","",},
        .x = 0x90,
        .y = 0x68,
        .adj_idx = { 61, 71, 45, 67 },
    },
    [67] = {
        .str = { "l", "","","l","","","l","","","l","","",},
        .x = 0x9A,
        .y = 0x68,
        .adj_idx = { 62, 72, 66, 68 },
    },
    [68] = {
        .str = { "m", "","","m","","","m","","","m","","",},
        .x = 0xA4,
        .y = 0x68,
        .adj_idx = { 63, 73, 67, 69 },
    },
    [69] = {
        .str = { "n", "","","n","","","n","","","n","","",},
        .x = 0xAE,
        .y = 0x68,
        .adj_idx = { 64, 74, 68, 70 },
    },
    [70] = {
        .str = { "o", "","","o","","","o","","","o","","",},
        .x = 0xB8,
        .y = 0x68,
        .adj_idx = { 65, 75, 69, 4 },
    },
    [71] = {
        .str = { "z", "","","z","","","z","","","z","","",},
        .x = 0x90,
        .y = 0x78,
        .adj_idx = { 66, 76, 50, 72 },
    },
    [72] = {
        .str = { ":", "","",":","","",":","","",":","","",},
        .x = 0x9A,
        .y = 0x78,
        .adj_idx = { 67, 77, 71, 73 },
    },
    [73] = {
        .str = { "/", "","","/","","","/","","","/","","",},
        .x = 0xA4,
        .y = 0x78,
        .adj_idx = { 68, 78, 72, 74 },
    },
    [74] = {
        .str = { "&", "","","&","","","&","","","&","","",},
        .x = 0xAE,
        .y = 0x78,
        .adj_idx = { 69, 79, 73, 75 },
    },
    [75] = {
        .str = { "-", "","","-","","","-","","","-","","",},
        .x = 0xB8,
        .y = 0x78,
        .adj_idx = { 70, 80, 74, 4 },
    },
    [76] = {
        .str = { " ", "",""," ","",""," ","",""," ","","",},
        .x = 0x90,
        .y = 0x88,
        .adj_idx = { 71, 56, 55, 77 },
    },
    [77] = {
        .str = { " ", "",""," ","",""," ","",""," ","","",},
        .x = 0x9A,
        .y = 0x88,
        .adj_idx = { 72, 57, 76, 78 },
    },
    [78] = {
        .str = { " ", "",""," ","",""," ","",""," ","","",},
        .x = 0xA4,
        .y = 0x88,
        .adj_idx = { 73, 58, 77, 79 },
    },
    [79] = {
        .str = { " ", "",""," ","",""," ","",""," ","","",},
        .x = 0xAE,
        .y = 0x88,
        .adj_idx = { 74, 59, 78, 80 },
    },
    [80] = {
        .str = { " ", "",""," ","",""," ","",""," ","","",},
        .x = 0xB8,
        .y = 0x88,
        .adj_idx = { 75, 60, 79, 5 },
    },
};

const s16 SioTacticianIndexMap[] = {
    0x06, 0x07, 0x08, 0x09, 0x0A,
    0x1F, 0x20, 0x21, 0x22, 0x23,
    0x38, 0x39, 0x3A, 0x3B, 0x3C,
    0x0B, 0x0C ,0x0D, 0x0E, 0x0F,
    0x24, 0x25, 0x26, 0x27, 0x28,
    0x3D, 0x3E, 0x3F, 0x40, 0x41,
    0x10, 0x11, 0x12, 0x13, 0x14,
    0x29, 0x2A, 0x2B, 0x2C, 0x2D,
    0x42, 0x43, 0x44, 0x45, 0x46,
    0x15, 0x16, 0x17, 0x18, 0x19,
    0x2E, 0x2F, 0x30, 0x31, 0x32,
    0x47, 0x48, 0x49, 0x4A, 0x4B,
    0x1A, 0x1B, 0x1C, 0x1D, 0x1E,
    0x33, 0x34, 0x35, 0x36, 0x37,
    0x4C, 0x4D, 0x4E, 0x4F, 0x50,
};

const int gLinkArenaStatusMsg[] = {
    0x76D, // Not Linked
    0x76E, // Connecting
    0x76F, // Link Error
    0x770, // Done
    0x770, // Done
};

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
#define TACTICIAN_LOCALE_GRID_ENTRY_COUNT 75
#define TACTICIAN_LOCALE_GRID_COLUMN_COUNT 15
#define TACTICIAN_LOCALE_GRID_X_BASE 0x10
#define TACTICIAN_LOCALE_GRID_X_STEP 12
#define TACTICIAN_LOCALE_GRID_SCALAR_CAPACITY 5

#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x02u) != 0
static const char sTacticianGridJaHiragana[] =
    "あいうえおかきくけこさしすせそ"
    "たちつてとなにぬねのはひふへほ"
    "まみむめもやゆよらりるれろわを"
    "んがぎぐげござじずぜぞだづでど"
    "ばびぶべぼぱぴぷぺぽぁっゃゅょ";

static const char sTacticianGridJaKatakana[] =
    "アイウエオカキクケコサシスセソ"
    "タチツテトナニヌネノハヒフヘホ"
    "マミムメモヤユヨラリルレロワー"
    "ンガギグゲゴザジズゼゾダヅデド"
    "バビブベボパピプペポァッャュョ";
#endif

#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x04u) != 0
static const char sTacticianGridZhHansFrequent[] =
    "的是我了不你这一在那么人有就啊"
    "要来也们为会可到好个吧样能以说"
    "还没下对子什真战王和过弗时斯大"
    "利事拉吗想都尔魔起然后之很国出"
    "里话现上所去着他得如看但艾行心";

static const char sTacticianGridZhHansExtended[] =
    "力多珂瑞德内姆已军生哈中定道将"
    "鲁古法物用家哥怎自经前伊主列亚"
    "呢只使士回地而些被斗知请嗯公小"
    "给塞石先雷无从谢成开圣天您再发"
    "实当进敌做果身把等帝因让才动情";
#endif

static int TacticianName_UsesLocaleGrid(void)
{
    ExpansionLocaleId locale;

    locale = ExpansionLocale_GetCurrent();
#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x02u) != 0
    if (locale == EXPANSION_LOCALE_JA)
        return TRUE;
#endif
#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x04u) != 0
    if (locale == EXPANSION_LOCALE_ZH_HANS)
        return TRUE;
#endif
    return FALSE;
}

static const char *TacticianName_GetLocalePage(u32 page)
{
    ExpansionLocaleId locale;

    if (page > 1)
        return NULL;

    locale = ExpansionLocale_GetCurrent();
#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x02u) != 0
    if (locale == EXPANSION_LOCALE_JA)
        return page == 0
            ? sTacticianGridJaHiragana
            : sTacticianGridJaKatakana;
#endif
#if (FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x04u) != 0
    if (locale == EXPANSION_LOCALE_ZH_HANS)
        return page == 0
            ? sTacticianGridZhHansFrequent
            : sTacticianGridZhHansExtended;
#endif

    return NULL;
}

static int TacticianName_GetGridSlot(s16 confIdx)
{
    int columnGroup;
    int local;
    int row;

    if (confIdx < 6 || confIdx > 80)
        return -1;

    local = confIdx - 6;
    columnGroup = local / 25;
    local %= 25;
    row = local / 5;
    return row * TACTICIAN_LOCALE_GRID_COLUMN_COUNT
        + columnGroup * 5
        + local % 5;
}

static const char *TacticianName_GetGridEntry(
    s16 confIdx,
    u32 page,
    u32 variant,
    char *buffer)
{
    struct TextUtf8Token token;
    const char *cursor;
    const char *grid;
    const char *next;
    u32 length;
    int i;
    int slot;

    grid = TacticianName_GetLocalePage(page);
    slot = TacticianName_GetGridSlot(confIdx);
    if (grid == NULL || slot < 0 || variant != 0)
        return (const char *)gTacticianTextConf[confIdx].str[page * 3 + variant];

    cursor = grid;
    for (i = 0; i < slot; i++)
    {
        next = TextUtf8_Next(cursor, &token);
        if (token.kind != TEXT_UTF8_TOKEN_SCALAR || next == cursor)
            return "";
        cursor = next;
    }

    next = TextUtf8_Next(cursor, &token);
    if (token.kind != TEXT_UTF8_TOKEN_SCALAR || next == cursor)
        return "";

    length = (u32)(next - cursor);
    if (length >= TACTICIAN_LOCALE_GRID_SCALAR_CAPACITY)
        return "";

    memcpy(buffer, cursor, length);
    buffer[length] = '\0';
    return buffer;
}

static int TacticianName_GetGridX(s16 confIdx)
{
    int slot;

    if (!TacticianName_UsesLocaleGrid())
        return gTacticianTextConf[confIdx].x;

    slot = TacticianName_GetGridSlot(confIdx);
    if (slot < 0)
        return gTacticianTextConf[confIdx].x;

    return TACTICIAN_LOCALE_GRID_X_BASE
        + (slot % TACTICIAN_LOCALE_GRID_COLUMN_COUNT)
            * TACTICIAN_LOCALE_GRID_X_STEP;
}
#endif


//! FE8U = 0x08044550
const struct TacticianTextConf * GetTacticianTextConf(s16 idx)
{
    return gTacticianTextConf + idx;
}

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
static int TacticianName_GetInfo(
    const char *str,
    u32 *outByteLength,
    u32 *outTokenCount)
{
    struct TextUtf8Token token;
    const char *cursor;
    const char *next;
    u32 tokenCount;

    cursor = str;
    tokenCount = 0;
    for (;;)
    {
        next = TextUtf8_Next(cursor, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
        {
            *outByteLength = (u32)(cursor - str);
            *outTokenCount = tokenCount;
            return TRUE;
        }
        if (token.kind != TEXT_UTF8_TOKEN_SCALAR || next == cursor)
            return FALSE;

        tokenCount++;
        cursor = next;
    }
}

static int TacticianName_CopyBounded(
    char *dst,
    u32 capacity,
    const char *src,
    u32 maxTokens)
{
    u32 byteLength;
    u32 tokenCount;

    if (!TacticianName_GetInfo(src, &byteLength, &tokenCount)
        || tokenCount > maxTokens
        || byteLength >= capacity)
    {
        if (capacity != 0)
            dst[0] = '\0';
        return FALSE;
    }

    memcpy(dst, src, byteLength + 1);
    return TRUE;
}

static int TacticianName_TokensEqual(
    const char *left,
    const char *right)
{
    struct TextUtf8Token leftToken;
    struct TextUtf8Token rightToken;
    const char *leftNext;
    const char *rightNext;
    u32 leftLength;
    u32 rightLength;

    leftNext = TextUtf8_Next(left, &leftToken);
    rightNext = TextUtf8_Next(right, &rightToken);
    if (leftToken.kind != TEXT_UTF8_TOKEN_SCALAR
        || rightToken.kind != TEXT_UTF8_TOKEN_SCALAR
        || *rightNext != '\0')
        return FALSE;

    leftLength = (u32)(leftNext - left);
    rightLength = (u32)(rightNext - right);
    return leftLength == rightLength
        && memcmp(left, right, leftLength) == 0;
}

#ifdef FE8_TEXT_CONSUMER_HOST_TEST
int Tactician_TestTokensEqual(const char *left, const char *right)
{
    return TacticianName_TokensEqual(left, right);
}

int Tactician_TestGetGridScalar(
    int page,
    int slot,
    char *out,
    u32 capacity)
{
    char buffer[TACTICIAN_LOCALE_GRID_SCALAR_CAPACITY];
    const char *source;
    u32 length;

    if (slot < 0 || slot >= TACTICIAN_LOCALE_GRID_ENTRY_COUNT)
        return FALSE;

    source = TacticianName_GetGridEntry(
        SioTacticianIndexMap[slot], page, 0, buffer);
    length = strlen(source);
    if (length == 0 || length >= capacity)
        return FALSE;

    memcpy(out, source, length + 1);
    return TRUE;
}

int Tactician_TestGetGridX(int slot)
{
    if (slot < 0 || slot >= TACTICIAN_LOCALE_GRID_ENTRY_COUNT)
        return -1;

    return TacticianName_GetGridX(SioTacticianIndexMap[slot]);
}
#endif

static char *TacticianName_GetLastToken(char *str)
{
    struct TextUtf8Token token;
    char *cursor;
    char *last;
    const char *next;

    cursor = str;
    last = str;
    for (;;)
    {
        next = TextUtf8_Next(cursor, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
            return last;
        if (token.kind != TEXT_UTF8_TOKEN_SCALAR || next == cursor)
            return NULL;

        last = cursor;
        cursor = (char *)next;
    }
}
#endif

void Tactician_MapNameToConfIndices(struct ProcTactician * proc, u8 * str_buf)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    struct TextUtf8Token token;
    const char *cursor;
    const char *next;
#endif
    int i;
    int j;
    int k;

    int idx = 0;

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    cursor = (const char *)str_buf;
    for (;;)
    {
        next = TextUtf8_Next(cursor, &token);
        if (token.kind == TEXT_UTF8_TOKEN_END)
            break;
        if (token.kind != TEXT_UTF8_TOKEN_SCALAR || next == cursor)
            break;

        for (i = 0; i <= 0x50; i++)
        {
            for (j = 0; j < 3; j++)
            {
                for (k = 0; k < 3; k++)
                {
                    char candidateBuffer[
                        TACTICIAN_LOCALE_GRID_SCALAR_CAPACITY];
                    const char *candidate;

                    candidate = TacticianName_GetGridEntry(
                        i, j, k, candidateBuffer);

                    if (TacticianName_TokensEqual(cursor, candidate))
                    {
                        if (idx < (int)ARRAY_COUNT(proc->unk4C))
                        {
                            proc->unk4C[idx] =
                                ((j & 3) << 14) | (i & 0x3FFF);
                            proc->unk39 = k;
                            idx++;
                        }
                        goto next_token;
                    }
                }
            }
        }

    next_token:
        cursor = next;
    }
#else
    for (; *str_buf != 0 ; str_buf += 2)
    {
        for (i = 0; i <= 0x50; i++)
        {
            const struct TacticianTextConf * conf = GetTacticianTextConf(i);

            for (j = 0; j < 3; j++)
            {
                for (k = 0; k < 3; k++)
                {
                    u16 * str = (u16 *)(conf->str + j * 3)[k];

                    if (*str == *(u16 *)str_buf)
                    {
                        proc->unk4C[idx] = ((j & 3) << 0xe) | (i & 0x3FFF);
                        proc->unk39 = k;

                        idx++;

                        goto _080445F8;
                    }
                }
            }
        }

    _080445F8:
        // need a semi-colon for modern compilers
        ; // exit loop
    }
#endif

    return;
}

void Tactician_DrawCharGrid(struct ProcTactician * proc)
{
    int i, j;

    for (i = 0; i < 5; i++)
    {
        ClearText(Texts_1 + (i + proc->text_idx * 5));
        Text_SetColor(Texts_1 + (i + proc->text_idx * 5), TEXT_COLOR_SYSTEM_WHITE);

        for (j = 0; j < 0xF; j++)
        {
            int idx = SioTacticianIndexMap[i * 15 + j];
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
            char gridBuffer[TACTICIAN_LOCALE_GRID_SCALAR_CAPACITY];
            const char *str = TacticianName_GetGridEntry(
                idx, proc->line_idx, 0, gridBuffer);
#else
            const struct TacticianTextConf * conf = gTacticianTextConf + idx;
            u8 * str = conf->str[proc->line_idx * 3];
#endif

            if (*str != '\0')
            {
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
                Text_SetCursor(
                    Texts_1 + (i + proc->text_idx * 5),
                    TacticianName_GetGridX(idx));
#else
                Text_SetCursor(Texts_1 + (i + proc->text_idx * 5), conf->x);
#endif
                Text_DrawString(
                    Texts_1 + (i + proc->text_idx * 5),
                    str
                );
            }
        }

        PutText(
            Texts_1 + (i + proc->text_idx * 5),
            TILEMAP_LOCATED(gBG1TilemapBuffer, 0, i * 2 + 9)
        );
    }
}

void TacticianDrawCharacters(struct ProcTactician * proc)
{
#if !FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    int x;
#endif
    struct Text * text;
    const char * str = proc->str;

    ClearText(&Text_0);

    if (*str != '\0')
    {
        text = &Text_0;
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
        Text_SetCursor(text, 0);
        Text_DrawString(text, str);
#else
        x = 0;
    
        while (*str != '\0')
        {
            Text_SetCursor(text, x);
            str = Text_DrawCharacter(text, str);
            x = x + 7;
        }
#endif
    }
    PutText(&Text_0, TILEMAP_LOCATED(gBG0TilemapBuffer, 12, 5));
    BG_EnableSyncByMask(BG0_SYNC_BIT);
}

int StrLen(u8 * buf)
{
    int i = 0;
    while (*buf != '\0')
    {
        i++;
        buf++;
    }
    return i;
}

void Tactician_InitScreen(struct ProcTactician * proc)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    int i;
#else
    int i, char_cnt;
#endif
    char * str;
#if !FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    u8 str_buf[0x10];
#endif
    const struct TacticianTextConf * conf;

    ClearSioBG();
    InitSioBG();
    StartMuralBackgroundExt(proc, 0, 0, 0, 0);
    Decompress(Img_TacticianSelObj, (void *)0x06014800);
    ApplyPalette(Pal_TacticianSelObj, 0x13);
    ApplyPalette(Pal_TacticianNameInputBg, 0x14);
    CallARM_FillTileRect(TILEMAP_LOCATED(gBG2TilemapBuffer, 0, 8), Tsa_TacticianNameInputBg, 0x1000);
    SetTextFont(&Font_0);
    InitSystemTextFont();
    ResetTextFont();

    if (CheckInLinkArena())
    {
        proc->max_len = 7;
    }
    else
    {
        gLinkArenaSt.unk_00 = 0;;
        proc->max_len = 5;
    }

    for (i = 0; i < (int)sizeof(proc->str); i++)
        proc->str[i] = '\0';

    for (i = 0; i < (int)ARRAY_COUNT(proc->unk4C); i++)
        proc->unk4C[i] = 0;

    if (CheckInLinkArena())
        proc->max_len = 9;

    proc->cur_len = 0;
    InitText(&Text_0, 8);
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    proc->line_idx = TacticianName_UsesLocaleGrid() ? 0 : 1;
#else
    proc->line_idx = 1;
#endif
    proc->conf_idx = 6;

    conf = GetTacticianTextConf(6);
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    proc->child1 = StartNameEntrySpriteDraw(
        proc, TacticianName_GetGridX(6) - 4, conf->y + 1);
#else
    proc->child1 = StartNameEntrySpriteDraw(proc, conf->x - 4, conf->y + 1);
#endif
    proc->unk39 = 0;

    for (i = 0; i < 10; i++)
        InitText(Texts_1 + i, 0x1A);

    InitText(&Texts_0, 0xC);
    StartLinkArenaTitleBanner(proc->child1, 3, 0x500);
    SetLinkArenaUiBlendAndWindowOff();
    gUnk_Sio_12 = 0;
    proc->text_idx = 0;
    Tactician_DrawCharGrid(proc);

    /* 80448DE */
    if (proc->unk32 != 0)
    {
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
        str = GetTacticianName();
        if (TacticianName_CopyBounded(
                proc->str,
                TACTICIAN_NAME_CAPACITY,
                str,
                proc->max_len))
        {
            u32 byteLength;
            u32 tokenCount;

            TacticianName_GetInfo(
                proc->str, &byteLength, &tokenCount);
            proc->cur_len = byteLength;
            Tactician_MapNameToConfIndices(proc, (u8 *)proc->str);
            TacticianDrawCharacters(proc);
            proc->child1->unk40 = GetStringTextLen(proc->str);
        }
#else
        i = 0;
        str = GetTacticianName();
        while (*str != '\0')
        {
            proc->str[i] = *str;
            str_buf[i] = *str;

            str++;
            i++;

            char_cnt = proc->cur_len + 1;
            if (char_cnt < proc->unk33)
                proc->cur_len = char_cnt;
        }
        Tactician_MapNameToConfIndices(proc, str_buf);
        TacticianDrawCharacters(proc);
        proc->child1->unk40 = proc->cur_len * 7;
#endif
    }
    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT | BG2_SYNC_BIT | BG3_SYNC_BIT);
}

void SioUpdateTeam(char * str, int team)
{
    int i;
    struct Unit * buffer = GetUnit(FACTION_RED + 1);
    for (i = 0; i < 5; i++)
        ClearUnit(buffer + i);

    for (i = 0; i < 5; i++)
    {
        u8 pid = gSioPidPool.pids[i];
        if (pid != 0)
        {
            struct Unit * unit = GetUnitFromCharId(pid);
            if (!(unit->state & US_NOT_DEPLOYED))
            {
                SetUnitStatus(unit, UNIT_STATUS_NONE);
                unit->state = 0;
                MemCpy(unit, buffer + i, sizeof(struct Unit));
            }
        }
    }
    WriteMultiArenaSaveTeam(team, buffer, str);
}

void Tactician_MoveHand(struct ProcTactician * proc, int pos, const struct TacticianTextConf * conf)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    char gridBuffer[TACTICIAN_LOCALE_GRID_SCALAR_CAPACITY];
#else
    int str_idx;
#endif
    u16 adj_idx;
    const struct TacticianTextConf * adj_conf;

    adj_idx  = conf->adj_idx[pos];
    adj_conf = gTacticianTextConf + conf->adj_idx[pos];

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    while (*TacticianName_GetGridEntry(
            adj_idx, proc->line_idx, 0, gridBuffer) == '\0')
#else
    str_idx = proc->line_idx * 3;
    while (*adj_conf->str[str_idx] == '\0')
#endif
    {
        adj_idx  = adj_conf->adj_idx[pos];
        adj_conf = gTacticianTextConf + adj_conf->adj_idx[pos];
    }
    proc->conf_idx = adj_idx;
}

void TacticianTryAppendChar(struct ProcTactician * proc, const struct TacticianTextConf * conf)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    char gridBuffer[TACTICIAN_LOCALE_GRID_SCALAR_CAPACITY];
    const char *source;
    u32 byteLength;
    u32 sourceByteLength;
    u32 sourceTokenCount;
    u32 tokenCount;

    source = TacticianName_GetGridEntry(
        proc->conf_idx, proc->line_idx, 0, gridBuffer);
    if (TacticianName_GetInfo(
            proc->str, &byteLength, &tokenCount)
        && TacticianName_GetInfo(
            source, &sourceByteLength, &sourceTokenCount)
        && sourceTokenCount == 1
        && tokenCount < proc->max_len
        && byteLength + sourceByteLength <= TACTICIAN_NAME_MAX_BYTES)
    {
        SioPlaySoundEffect(2);
        memcpy(
            proc->str + byteLength, source, sourceByteLength + 1);
        proc->unk4C[tokenCount] =
            (0x3FFF & proc->conf_idx)
            | ((3 & proc->line_idx) << 14);
        proc->cur_len = byteLength + sourceByteLength;

        if (tokenCount + 1 >= proc->max_len)
            proc->conf_idx = 5;

        TacticianDrawCharacters(proc);
        proc->unk39 = 0;
    }
    else
    {
        SioPlaySoundEffect(0);
    }
#else
    int cur_len;

    if (proc->cur_len < proc->max_len)
    {
        SioPlaySoundEffect(2);
        SioStrCpy(conf->str[proc->line_idx * 3], &proc->str[proc->cur_len]);

        proc->unk4C[proc->cur_len] = (0x3FFF & proc->conf_idx) | ((3 & proc->line_idx) << 14);
        cur_len = proc->cur_len + 1;

        if (cur_len < proc->max_len)
            proc->cur_len = cur_len;
        else
            proc->conf_idx = 5;

        TacticianDrawCharacters(proc);
        proc->unk39 = 0;
    }
    else
    {
        SioPlaySoundEffect(0);
    }
#endif
}

void TacticianTryDeleteChar(struct ProcTactician * proc, const struct TacticianTextConf * conf)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    char *last;
    u32 byteLength;
    u32 tokenCount;

    (void)conf;
    if (TacticianName_GetInfo(
            proc->str, &byteLength, &tokenCount)
        && tokenCount != 0)
    {
        SioPlaySoundEffect(2);
        last = TacticianName_GetLastToken(proc->str);
        if (last != NULL)
        {
            *last = '\0';
            proc->cur_len = (u32)(last - proc->str);
            proc->unk4C[tokenCount - 1] = 0;
            proc->unk39 = 0;
            TacticianDrawCharacters(proc);
        }
    }
    else
    {
        SioPlaySoundEffect(0);
    }
#else
    int cur_len;

    if (proc->cur_len != 0)
    {
        SioPlaySoundEffect(2);

        if (proc->unk4C[proc->cur_len] == 0)
            proc->cur_len--;

        *(proc->str + proc->cur_len) = 0;
        proc->unk4C[proc->cur_len] = 0;
        proc->unk39 = 0;

        TacticianDrawCharacters(proc);
    }
    else
    {
        SioPlaySoundEffect(0);
    }
#endif
}

void SaveTactician(struct ProcTactician * proc, const struct TacticianTextConf * conf)
{
#if defined(MODERN)
    u32 byteLength;
    u32 tokenCount;

    (void)conf;
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    if (!TacticianName_GetInfo(proc->str, &byteLength, &tokenCount))
    {
        SioPlaySoundEffect(0);
        return;
    }
#else
    byteLength = strlen(proc->str);
#endif
    if (proc->str[0] == '\0' || byteLength > TACTICIAN_NAME_MAX_BYTES)
    {
        SioPlaySoundEffect(0);
        return;
    }

    if (CheckInLinkArena())
    {
        SioUpdateTeam(proc->str, gLinkArenaSt.unk_03);
    }
    else if (!TrySetTacticianName(proc->str))
    {
        SioPlaySoundEffect(0);
        return;
    }

    SioPlaySoundEffect(2);
    Proc_Break(proc);
#else
    if (proc->str[0] != '\0')
    {
        SioPlaySoundEffect(2);

        if (CheckInLinkArena())
            SioUpdateTeam(proc->str, gLinkArenaSt.unk_03);
        else
            SetTacticianName(proc->str);

        Proc_Break(proc);
    }
    else
    {
        SioPlaySoundEffect(0);
    }
#endif
}

bool Tactician_TryChangeLastCharVariant(struct ProcTactician * proc, const struct TacticianTextConf * conf, u32 c, int d)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    char replacementBuffer[TACTICIAN_LOCALE_GRID_SCALAR_CAPACITY];
    const char *replacement;
    char *last;
    u16 conf_idx;
    u32 byteLength;
    u32 lastLength;
    u32 line_idx;
    u32 replacementLength;
    u32 replacementTokens;
    u32 tokenCount;

    if (proc->line_idx > 1 && d == 0)
    {
        SioPlaySoundEffect(2);
        TacticianTryAppendChar(proc, conf);
        return false;
    }

    if (!TacticianName_GetInfo(
            proc->str, &byteLength, &tokenCount)
        || tokenCount == 0)
    {
        if (d == 0)
            SioPlaySoundEffect(0);
        return false;
    }

    conf_idx = 0x3FFF & proc->unk4C[tokenCount - 1];
    line_idx = proc->unk4C[tokenCount - 1] >> 14;
    replacement = TacticianName_GetGridEntry(
        conf_idx, line_idx, c, replacementBuffer);
    if (!TacticianName_GetInfo(
            replacement, &replacementLength, &replacementTokens)
        || replacementTokens != 1)
    {
        if (d == 0)
            SioPlaySoundEffect(0);
        return false;
    }

    last = TacticianName_GetLastToken(proc->str);
    if (last == NULL)
        return false;
    lastLength = byteLength - (u32)(last - proc->str);
    if (byteLength - lastLength + replacementLength
        > TACTICIAN_NAME_MAX_BYTES)
    {
        if (d == 0)
            SioPlaySoundEffect(0);
        return false;
    }

    SioPlaySoundEffect(2);
    memcpy(last, replacement, replacementLength);
    last[replacementLength] = '\0';
    proc->cur_len =
        (u32)(last - proc->str) + replacementLength;
    TacticianDrawCharacters(proc);
    proc->unk39 = c;
    return true;
#else
    if (proc->line_idx > 1 && d == 0)
    {
        SioPlaySoundEffect(2);
        TacticianTryAppendChar(proc, conf);
        return false;
    }

    if (proc->cur_len != 0)
    {
        const struct TacticianTextConf * conf2;
        int r8, line_idx;
        u16 conf_idx;

        if (0x3FFF & proc->unk4C[proc->cur_len / 2])
            r8 = 0;
        else
            r8 = 1;

        conf_idx = 0x3FFF & proc->unk4C[proc->cur_len / 2 - r8];
        conf2 = GetTacticianTextConf(conf_idx);
        line_idx = proc->unk4C[proc->cur_len / 2 - r8] >> 14;

        if (*conf2->str[line_idx * 3 + c] != '\0')
        {
            SioPlaySoundEffect(2);
            SioStrCpy(conf2->str[line_idx * 3 + c], &proc->str[proc->cur_len] - r8 * 2);
            TacticianDrawCharacters(proc);
            proc->unk39 = c;
            return true;
        }
        else if (d == 0)
            SioPlaySoundEffect(0);
    }
    else if (d == 0)
        SioPlaySoundEffect(0);

    return false;
#endif
}

//! FE8U = 0x08044C54
void Tactician_LoopCore(struct ProcTactician * proc, const struct TacticianTextConf * conf)
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    char gridBuffer[TACTICIAN_LOCALE_GRID_SCALAR_CAPACITY];
#endif
    char var;

    if ((gKeyStatusPtr->repeatedKeys & DPAD_UP) != 0)
    {
        Tactician_MoveHand(proc, 0, conf);
    }

    if ((gKeyStatusPtr->repeatedKeys & DPAD_DOWN) != 0)
    {
        Tactician_MoveHand(proc, 1, conf);
    }

    if ((gKeyStatusPtr->repeatedKeys & DPAD_LEFT) != 0)
    {
        Tactician_MoveHand(proc, 2, conf);
    }

    if ((gKeyStatusPtr->repeatedKeys & DPAD_RIGHT) != 0)
    {
        Tactician_MoveHand(proc, 3, conf);
    }

    if ((gKeyStatusPtr->newKeys & A_BUTTON) != 0)
    {
        switch (conf->action) {
        case 0:
            TacticianTryAppendChar(proc, conf);
            break;

        case 4:
            TacticianTryDeleteChar(proc, conf);
            break;

        case 5:
            SaveTactician(proc, conf);
            break;

        case 6:
            Tactician_TryChangeLastCharVariant(proc, conf, 1, 0);

            break;

        case 7:
            Tactician_TryChangeLastCharVariant(proc, conf, 2, 0);

            break;

        case 1:
            if (proc->line_idx != 0)
            {
                SioPlaySoundEffect(2);
                proc->line_idx = 0;
                proc->unk39 = 0;

                Proc_Goto(proc, 1);
                return;
            }

            SioPlaySoundEffect(0);
            break;

        case 2:
            if (proc->line_idx != 1)
            {
                SioPlaySoundEffect(2);

                proc->line_idx = 1;
                proc->unk39 = 0;

                Proc_Goto(proc, 1);
                return;
            }

            SioPlaySoundEffect(0);
            break;

        case 3:
            if (proc->line_idx < 2 || proc->line_idx > 3)
            {
                SioPlaySoundEffect(2);

                proc->line_idx = 2;

                if (proc->unk32 != 0)
                {
                    proc->line_idx = 3;
                }

                proc->unk39 = 0;

                Proc_Goto(proc, 1);
                return;
            }

            SioPlaySoundEffect(0);

            break;
        }
    }

    if ((gKeyStatusPtr->newKeys & R_BUTTON) != 0)
    {
        var = proc->unk39;

        do
        {
            proc->unk39++;
            proc->unk39 = (proc->unk39 % 3);

            if (var == proc->unk39)
                break;

        } while (Tactician_TryChangeLastCharVariant(proc, conf, proc->unk39, 1) == 0);
    }

    if ((gKeyStatusPtr->newKeys & L_BUTTON) != 0)
    {
        TacticianTryDeleteChar(proc, conf);
    }

    if ((gKeyStatusPtr->newKeys & START_BUTTON) != 0)
    {
        SioPlaySoundEffect(3);
        proc->conf_idx = 5;
    }

    if ((gKeyStatusPtr->newKeys & SELECT_BUTTON) != 0)
    {
        SioPlaySoundEffect(2);

        proc->line_idx++;

        if ((proc->line_idx == 2) && (proc->unk32 != 0))
        {
            proc->line_idx++;
        }

        proc->line_idx %= 4;

        if (proc->line_idx == 3 && proc->unk32 == 0)
        {
            proc->line_idx = 0;
        }

#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
        if (*TacticianName_GetGridEntry(
                proc->conf_idx, proc->line_idx, 0, gridBuffer) == 0)
#else
        if (*conf->str[proc->line_idx * 3] == 0)
#endif
        {
            Tactician_MoveHand(proc, 2, conf);
        }

        Proc_Goto(proc, 1);
        return;
    }

    if ((gKeyStatusPtr->newKeys & B_BUTTON) != 0)
    {
        if (proc->cur_len != 0)
        {
            TacticianTryDeleteChar(proc, conf);
            return;
        }

        if (CheckInLinkArena() != 0)
        {
            SioPlaySoundEffect(1);
            Proc_Goto(proc, 3);
        }
    }

    return;
}

//! FE8U = 0x08044ED8
void Tactician_Loop(struct ProcTactician * proc)
{
#if !FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    char _cbuf[proc->max_len + 1];
#endif
    const struct TacticianTextConf * conf = GetTacticianTextConf(proc->conf_idx);
    proc->conf_idx_bak = proc->conf_idx;

    Tactician_LoopCore(proc, conf);
    if (proc->conf_idx_bak != proc->conf_idx)
    {
        SioPlaySoundEffect(3);
    }

    conf = GetTacticianTextConf(proc->conf_idx);
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    UpdateNameEntrySpriteDraw(
        proc->child1,
        TacticianName_GetGridX(proc->conf_idx) - 4,
        conf->y + 1,
        GetStringTextLen(proc->str),
        conf->kind,
        (proc->line_idx <= 1) ? proc->line_idx : 2);
#else
    SioStrCpy(proc->str, _cbuf);

    _cbuf[proc->max_len - 1] = 0;

    UpdateNameEntrySpriteDraw(proc->child1, conf->x - 4, conf->y + 1, StrLen(_cbuf) * 7, conf->kind, (proc->line_idx <= 1) ? proc->line_idx : 2);
#endif
}

//! FE8U = 0x08044F84
void Tactician_PageFadeHBlankHandler(void)
{
    u16 vcount = REG_VCOUNT + 1;

    if (vcount > DISPLAY_HEIGHT)
    {
        return;
    }

    if (vcount < 40)
    {
        REG_BLDCNT = 0x840;
        REG_BLDALPHA = 0xF08;
    }
    else
    {
        REG_BLDCNT = 0x442;
        REG_BLDALPHA = ((15 - gUnk_41) << 8) + gUnk_41;
    }

    return;
}

void Tactician_PageFade_Init(struct ProcTactician * proc)
{
    proc->unk3A = 0;
    SetPrimaryHBlankHandler(Tactician_PageFadeHBlankHandler);
    return;
}

//! FE8U = 0x08044FFC
void Tactician_PageFadeOut_Loop(struct ProcTactician * proc)
{
    gUnk_41 = Interpolate(INTERPOLATE_LINEAR, 15, 0, proc->unk3A, 8);
    proc->unk3A++;

    if (proc->unk3A > 8)
    {
        Proc_Break(proc);
    }

    return;
}

//! FE8U = 0x0804503C
void Tactician_SwapPage(struct ProcTactician * proc)
{
    proc->text_idx++;
    proc->text_idx &= 1;

    Tactician_DrawCharGrid(proc);
    BG_EnableSyncByMask(BG1_SYNC_BIT);

    proc->unk3A = 0;

    return;
}

//! FE8U = 0x08045068
void Tactician_PageFadeIn_Loop(struct ProcTactician * proc)
{
    gUnk_41 = Interpolate(INTERPOLATE_LINEAR, 0, 15, proc->unk3A, 8);
    proc->unk3A++;

    if (proc->unk3A > 8)
    {
        SetPrimaryHBlankHandler(NULL);
        Proc_Break(proc);
    }

    return;
}

//! FE8U = 0x080450AC
void NameSelect_DrawName(struct ProcTactician * proc)
{
    proc->unk3B = 1;

    LoadLinkArenaChoiceBoxGfx();

    ClearText(&Texts_0);

    Text_DrawString(&Texts_0, GetStringFromIndex(0x141)); // TODO: msgid "Back"
    Text_SetCursor(&Texts_0, 38);

    Text_DrawString(&Texts_0, GetStringFromIndex(0x146)); // TODO: msgid "Entry"
    PutText(&Texts_0, TILEMAP_LOCATED(gBG0TilemapBuffer, 11, 12));

    BG_EnableSyncByMask(BG0_SYNC_BIT);

    return;
}

//! FE8U = 0x08045108
void NameSelect_ConfirmLoop(struct ProcTactician * proc)
{
    PutLinkArenaChoiceBannerSprite(0x40, 0x58);

    if (((gKeyStatusPtr->newKeys & DPAD_LEFT) != 0) && (proc->unk3B == 1))
    {
        proc->unk3B = 0;
        SioPlaySoundEffect(3);
    }

    if (((gKeyStatusPtr->newKeys & DPAD_RIGHT) != 0) && (proc->unk3B == 0))
    {
        proc->unk3B = 1;
        SioPlaySoundEffect(3);
    }

    DisplayUiHand(proc->unk3B * 40 + 80, 96);

    if ((gKeyStatusPtr->newKeys & B_BUTTON) != 0)
    {
        SioPlaySoundEffect(1);

        TileMap_FillRect(TILEMAP_LOCATED(gBG0TilemapBuffer, 11, 12), 12, 2, 0);
        BG_EnableSyncByMask(BG0_SYNC_BIT);

        Proc_Break(proc);

        return;
    }

    if ((gKeyStatusPtr->newKeys & A_BUTTON) != 0)
    {
        if (proc->unk3B == 0)
        {
            SioPlaySoundEffect(2);
            gUnk_Sio_12 = 1;
            Proc_Goto(proc, 2);
        }
        else
        {
            SioPlaySoundEffect(1);
        }

        TileMap_FillRect(TILEMAP_LOCATED(gBG0TilemapBuffer, 11, 12), 12, 2, 0);
        BG_EnableSyncByMask(BG0_SYNC_BIT);

        Proc_Break(proc);
    }

    return;
}

//! FE8U = 0x080451F0
void Tactician_OnEnd(void)
{
    EndMuralBackground();

    if (!CheckInLinkArena())
    {
        Nop_SioUiutils_0();
    }

    return;
}
