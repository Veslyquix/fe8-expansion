#include "global.h"

#if FE8_ANIMS_FAST_FORWARD

#include "anims_fast_forward.h"
#include "hardware.h"
#include "ekrbattle.h"

/* Ported from a standalone Lyn-hooked ASM patch (asm/AnimsFastForward on
 * disk, ported from its Data/FE8.c / C_Code.c): the original also gated
 * both of these behind an event flag (PlayerPhaseOnlyFlag/
 * SpeedupAnimsFlag) so they could be toggled on permanently rather than
 * only while a button is held -- neither flag was ever wired to a real
 * game flag in the source being ported (both defaulted to flag 0, i.e.
 * "unused"), so that half isn't ported here; only the held-button
 * controls are. */

bool8 ShouldReverseShowAnim(void)
{
    u16 keys = gKeyStatusPtr->newKeys | gKeyStatusPtr->heldKeys;

    if (keys & ANIMS_FAST_FORWARD_HELD_ANIM_OFF)
        return TRUE;

    return FALSE;
}

bool8 ShouldSpeedupAnims(void)
{
    u16 keys;

    /* Promotion animations don't hold up per-unit combat, and skipping
     * their build-up looks broken rather than just fast, so they're never
     * eligible no matter what's held. */
    if (gEkrDistanceType == EKR_DISTANCE_PROMOTION)
        return FALSE;

    keys = gKeyStatusPtr->newKeys | gKeyStatusPtr->heldKeys;

    if (keys & ANIMS_FAST_FORWARD_HELD_SPEEDUP)
        return TRUE;

    return FALSE;
}

#endif
