#include "global.h"

extern u8 gUnk_68[];  // buffer to copy the code to

// pointers to the loaded functions
extern void (*gUnk_67)(u16 *, u32 *, u32 *, int);
extern void (*DecodeStringRAMFunc)(const char *, char *);
extern void (*gUnk_66)(int, int, const u16 *, int);
extern void (*gUnk_69)(int, int, const u16 *, int);
extern void (*gUnk_70)(int, int, int);
extern void (*gUnk_65)(void);

// arm.s symbols
extern const u8 ARMCodeToCopy_Start[];
extern const u8 DrawGlyph[];
extern const u8 DecodeString[];
extern const u8 PutOamHi[];
extern const u8 PutOamLo[];
extern const u8 MapFloodCoreStep[];
extern const u8 MapFloodCore[];
extern const u8 ARMCodeToCopy_End[];

void StoreRoutinesToIRAM(void)
{
    size_t armCodeSize = (ARMCodeToCopy_End - ARMCodeToCopy_Start);

    // Copy all of the ARM code into RAM
    CpuCopy16(ARMCodeToCopy_Start, gUnk_68, armCodeSize + (armCodeSize >> 31));

    // Set pointers to each of the functions
    gUnk_67 = (void *)(gUnk_68 + (DrawGlyph    - ARMCodeToCopy_Start));
    DecodeStringRAMFunc = (void *)(gUnk_68 + (DecodeString - ARMCodeToCopy_Start));
    gUnk_66 = (void *)(gUnk_68 + (PutOamHi - ARMCodeToCopy_Start));
    gUnk_69 = (void *)(gUnk_68 + (PutOamLo   - ARMCodeToCopy_Start));
    gUnk_70 = (void *)(gUnk_68 + (MapFloodCoreStep              - ARMCodeToCopy_Start));
    gUnk_65 = (void *)(gUnk_68 + (MapFloodCore    - ARMCodeToCopy_Start));
}

void DrawGlyphRam(u16 *pal, u32 *dest, u32 *src, int subx)
{
// #if FE8_OVERFLOW_SAFETY_CHECKS
//     uintptr_t pal_addr = (uintptr_t)pal;
//     uintptr_t dest_addr = (uintptr_t)dest;
//     uintptr_t src_addr = (uintptr_t)src;
//     uintptr_t glyph_addr = (uintptr_t)gUnk_67;
//     uintptr_t code_start = (uintptr_t)gUnk_68;
//     uintptr_t code_end = code_start + (ARMCodeToCopy_End - ARMCodeToCopy_Start);

//     /* DrawGlyph performs word loads from a u16 LUT at pal + index * 2.
//      * Requiring a word-aligned LUT prevents the ARM ldr at 0x03003AB4 from
//      * turning a corrupted/half-aligned palette pointer into a bad-alignment
//      * access. Bound the other operands too: the routine reads 0x40 bytes from
//      * src and writes through 0xBC bytes from dest. */
//     if (gUnk_67 == NULL || (glyph_addr & 3) != 0 ||
//         glyph_addr < code_start || glyph_addr >= code_end ||
//         pal == NULL || (pal_addr & 3) != 0 ||
//         !((pal_addr >= 0x02000000 && pal_addr + 0x200 <= 0x02040000) ||
//           (pal_addr >= 0x03000000 && pal_addr + 0x200 <= 0x03008000) ||
//           (pal_addr >= 0x08000000 && pal_addr + 0x200 <= 0x0A000000)) ||
//         dest == NULL || (dest_addr & 3) != 0 ||
//         dest_addr < 0x06000000 || dest_addr + 0xC0 > 0x06018000 ||
//         src == NULL || (src_addr & 3) != 0 ||
//         !((src_addr >= 0x02000000 && src_addr + 0x40 <= 0x02040000) ||
//           (src_addr >= 0x03000000 && src_addr + 0x40 <= 0x03008000) ||
//           (src_addr >= 0x08000000 && src_addr + 0x40 <= 0x0A000000)) ||
//         subx < 0 || subx > 7)
//         return;
// #endif

    gUnk_67(pal, dest, src, subx);
}

void CallARM_DecompText(const char *a, char *b)
{
    DecodeStringRAMFunc(a, b);
}

void CallARM_PushToSecondaryOAM(int a, int b, const u16 *c, int d)
{
    gUnk_66(a, b, c, d);
}

void CallARM_PushToPrimaryOAM(int a, int b, const u16 *c, int d)
{
    gUnk_69(a, b, c, d);
}

void CallARM_Func5(int a, int b, int c)
{
    gUnk_70(a, b, c);
}

void CallARM_FillMovementMap(void)
{
    gUnk_65();
}
