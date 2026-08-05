#ifndef GUARD_LOCALIZED_GAME_TEXT_RUNTIME_HOST_GLOBAL_H
#define GUARD_LOCALIZED_GAME_TEXT_RUNTIME_HOST_GLOBAL_H

#include <limits.h>

#if UCHAR_MAX != 0xFF
#error "host test requires 8-bit bytes"
#endif

typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef signed short s16;
typedef unsigned int u32;
typedef signed int s32;
typedef u8 bool8;
typedef s8 bool;

#define TRUE 1
#define FALSE 0
#define true 1
#define false 0
#define EWRAM_DATA
#define ARRAY_COUNT(array) (sizeof(array) / sizeof((array)[0]))
#define CHFE_L_LoadFace 0x10

#include "expansion_config.h"
#include "localized_game_text.h"

struct MsgBuffer
{
#if FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED
    union
    {
        struct
        {
            u8 buffer1[FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER1_BYTES];
            u8 buffer2[FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER2_BYTES];
            u8 buffer3[FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER3_BYTES];
            u8 buffer4[FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER4_BYTES];
            u8 buffer5[FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER5_BYTES];
        } legacy;
        u8 localized[FE8_LOCALIZED_GAME_TEXT_REQUIRED_STORAGE_BYTES];
    } storage;
#else
    u8 buffer1[FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER1_BYTES];
    u8 buffer2[FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER2_BYTES];
    u8 buffer3[FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER3_BYTES];
    u8 buffer4[FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER4_BYTES];
    u8 buffer5[FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER5_BYTES];
#endif
};

struct ActionData
{
    int item;
};

struct PlaySt
{
    u8 pad[0x1C];
    u8 unk1C[4];
};

struct CharacterData
{
    int nameTextId;
};

extern char gBufPrep[0x2000];
extern const u32 gMsgHuffmanTable[];
extern const u32 *const gMsgHuffmanTableRoot;
extern const u8 *const gMsgTable[];
extern struct ActionData gActionData;
extern struct PlaySt gPlaySt;

const char *GetStrPrefix(s8 *str, bool capital);
void SetMsgTerminator(signed char *str);
char *GetStringFromIndex(int index);
void CallARM_DecompText(const char *input, char *output);
void CopyString(void *dst, const void *src);
char *GetTacticianName(void);
char *GetItemName(int item);
const struct CharacterData *GetCharacterData(int id);

#endif /* GUARD_LOCALIZED_GAME_TEXT_RUNTIME_HOST_GLOBAL_H */
