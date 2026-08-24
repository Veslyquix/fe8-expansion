#include "global.h"
#include "expansion_config.h"

#if FE8_NEW_ANIMS

#include "banim_data.h"
#include "banim_new_anims.h"

/*
 * C port of the community "Anim_AutoGenLeftOAM" ASM patch (originally hooked
 * at FE8U 0x059ACC), used by FE8_NEW_ANIMS.
 *
 * Vanilla battle animations ship two separate OAM blobs, one per facing
 * (struct BattleAnim::oam_r / ::oam_l, include/banim_data.h). AA.exe -- the
 * assembler that produces the FE-Repo packs converted by
 * scripts/banim_event_to_source.py -- only emits ONE, and its installer
 * points both fields at it, on the assumption that this patch is present to
 * derive the left-facing set at runtime. Without it the left-hand combatant
 * draws the right-facing sprite, i.e. the unit faces backwards.
 *
 * So: decompress as usual, and only when both pointers are literally the
 * same object (never true for a vanilla animation, always true for an
 * AA.exe-built one) mirror the decompressed copy in place.
 *
 * The OAM stream is a run of 12-byte entries. Per entry: byte 0 == 1 marks
 * the terminator, and halfword 2 == 0xFFFF marks an affine/rotation entry --
 * both are skipped rather than mirrored. Otherwise the sprite's on-screen x
 * (signed halfword 6) is reflected about its own width and the horizontal
 * flip bit (0x10 of byte 3) is toggled on.
 */

/* Sprite width in tiles, indexed by (align >> 6) | (area >> 4) -- i.e. the
 * OAM shape/size bit pairs packed into 4 bits. Verbatim from the original
 * patch's LookupAlignAreaToWidth table. */
static CONST_DATA u8 sOamAlignAreaToWidth[16] = {
    1, 2, 1, 0,
    2, 4, 1, 0,
    4, 4, 2, 0,
    8, 8, 4, 0,
};

void ExpansionNewAnims_UncompOamLeft(const struct BattleAnim * anim, void * dst)
{
    u8 * entry;
    u8 * end;
    u32 size;

    LZ77UnCompWram(anim->oam_l, dst);

    /* A real two-blob animation: nothing to derive. */
    if (anim->oam_l != anim->oam_r)
        return;

    /* LZ77 header: 0x10 then a 24-bit decompressed size. */
    size = (*(const u32 *)anim->oam_l) >> 8;

    entry = dst;
    end = entry + size;

    for (; entry < end; entry += 12)
    {
        s16 * vramX;
        u32 width;

        if (entry[0] == 1)
            continue; /* terminator */

        if (*(u16 *)(entry + 2) == 0xFFFF)
            continue; /* affine/rotation entry */

        width = sOamAlignAreaToWidth[((entry[1] & 0xC0) >> 6) | ((entry[3] & 0xC0) >> 4)];

        vramX = (s16 *)(entry + 6);
        *vramX = -(s16)(width * 8) - *vramX;

        entry[3] |= 0x10;
    }
}

#endif /* FE8_NEW_ANIMS */
