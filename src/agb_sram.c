#include "global.h"
#include "agb_sram.h"

const char AgbLibSramVersion[] = "SRAM_F_V103";

static u16 verifySramFast_Work[80]; // buffer to hold code of VerifySramFast_Core
static u16 readSramFast_Work[64];  // buffer to hold code of ReadSramFast_Core
#ifdef MODERN
static u16 verifySramValueFast_Work[80];
#endif

u32 (* VerifySramFast)(void const * src, void * dest, u32 size);    // pointer to verifySramFast_Work
void (* ReadSramFast)(void const * src, void * dest, u32 size);     // pointer to readSramFast_Work
#ifdef MODERN
u32 (* VerifySramValueFast)(void const * src, u8 value, u32 size);
#endif

void ReadSramFast_Core(const u8 *src, u8 *dest, u32 size)
{
    REG_WAITCNT = (REG_WAITCNT & ~3) | 3;
    while (--size != -1)
        *dest++ = *src++;
}

void WriteSramFast(const u8 *src, u8 *dest, u32 size)
{
    REG_WAITCNT = (REG_WAITCNT & ~3) | 3;
    while (--size != -1)
        *dest++ = *src++;
}

u32 VerifySramFast_Core(const u8 *src, u8 *dest, u32 size)
{
    REG_WAITCNT = (REG_WAITCNT & ~3) | 3;
    while (--size != -1)
    {
        if (*dest++ != *src++)
            return (u32)(dest - 1);
    }
    return 0;
}

#ifdef MODERN
u32 VerifySramValueFast_Core(void const *data, u8 value, u32 size)
{
    u8 const *src = data;
    u32 mismatch = 0;

    REG_WAITCNT = (REG_WAITCNT & ~3) | 3;

    while (size >= 8)
    {
        mismatch |= (src[0] ^ value)
            | (src[1] ^ value)
            | (src[2] ^ value)
            | (src[3] ^ value)
            | (src[4] ^ value)
            | (src[5] ^ value)
            | (src[6] ^ value)
            | (src[7] ^ value);
        src += 8;
        size -= 8;
    }

    while (size != 0)
    {
        mismatch |= *src++ ^ value;
        size--;
    }

    return mismatch;
}
#endif

void SetSramFastFunc(void)
{
    u16 *src;
    u16 *dest;
    u16 size;

    src = (u16 *)ReadSramFast_Core;
    // clear the least significant bit so that we get the actual start address of the function
    src = (u16 *)((uintptr_t)src & ~1);
    dest = readSramFast_Work;
    // get the size of the function by subtracting the address of the next function
    size = ((uintptr_t)WriteSramFast - (uintptr_t)ReadSramFast_Core) / 2;
    // copy the function into the WRAM buffer
    while (size != 0)
    {
        *dest++ = *src++;
        size--;
    }
    // add 1 to the address of the buffer so that we stay in THUMB mode when bx-ing to the address
    ReadSramFast = (void *)((uintptr_t)readSramFast_Work + 1);

    src = (u16 *)VerifySramFast_Core;
    // clear the least significant bit so that we get the actual start address of the function
    src = (u16 *)((uintptr_t)src & ~1);
    dest = verifySramFast_Work;
    // get the size of the function by subtracting the address of the next function
#ifdef MODERN
    size = ((uintptr_t)VerifySramValueFast_Core - (uintptr_t)VerifySramFast_Core) / 2;
#else
    size = ((uintptr_t)SetSramFastFunc - (uintptr_t)VerifySramFast_Core) / 2;
#endif
    // copy the function into the WRAM buffer
    while (size != 0)
    {
        *dest++ = *src++;
        size--;
    }
    // add 1 to the address of the buffer so that we stay in THUMB mode when bx-ing to the address
    VerifySramFast = (void *)((uintptr_t)verifySramFast_Work + 1);

#ifdef MODERN
    src = (u16 *)VerifySramValueFast_Core;
    src = (u16 *)((uintptr_t)src & ~1);
    dest = verifySramValueFast_Work;
    size = ((uintptr_t)SetSramFastFunc - (uintptr_t)VerifySramValueFast_Core) / 2;
    if (size <= sizeof(verifySramValueFast_Work) / sizeof(verifySramValueFast_Work[0]))
    {
        while (size != 0)
        {
            *dest++ = *src++;
            size--;
        }
        VerifySramValueFast = (void *)((uintptr_t)verifySramValueFast_Work + 1);
    }
    else
    {
        VerifySramValueFast = VerifySramValueFast_Core;
    }
#endif

    REG_WAITCNT = (REG_WAITCNT & ~3) | 3;
}

u32 WriteAndVerifySramFast(void const * src, void * dest, u32 size)
{
    u8 i;
    u32 errorAddr;

    // try writing and verifying the data 3 times
    for (i = 0; i < 3; i++)
    {
        WriteSramFast(src, dest, size);
        errorAddr = VerifySramFast(src, dest, size);
        if (errorAddr == 0)
            break;
    }

    return errorAddr;
}
