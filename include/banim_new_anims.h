#ifndef GUARD_BANIM_NEW_ANIMS_H
#define GUARD_BANIM_NEW_ANIMS_H

#include "expansion_config.h"

struct BattleAnim;

/*
 * Left-facing OAM for FE8_NEW_ANIMS animations.
 *
 * Vanilla animations carry a distinct oam_l and oam_r; the AA.exe-built
 * FE-Repo packs carry only one and point both fields at it. BANIM_UNCOMP_OAM_L
 * therefore replaces a plain oam_l decompression at every site that loads the
 * left-facing set, deriving the mirrored copy when (and only when) the two
 * pointers are the same object. With FE8_NEW_ANIMS off it compiles down to
 * exactly the original call. See src/banim_autogen_left_oam.c.
 */
#if FE8_NEW_ANIMS

void ExpansionNewAnims_UncompOamLeft(const struct BattleAnim * anim, void * dst);

#define BANIM_UNCOMP_OAM_L(animPtr, dst) ExpansionNewAnims_UncompOamLeft((animPtr), (dst))

#else

#define BANIM_UNCOMP_OAM_L(animPtr, dst) LZ77UnCompWram((animPtr)->oam_l, (dst))

#endif /* FE8_NEW_ANIMS */

#endif /* GUARD_BANIM_NEW_ANIMS_H */
