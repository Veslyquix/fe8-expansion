#ifndef GUARD_ANIMS_FAST_FORWARD_H
#define GUARD_ANIMS_FAST_FORWARD_H

#if FE8_ANIMS_FAST_FORWARD

/* Held to force the OPPOSITE of the current battle animation setting for
 * just this fight (full animation forces map-only, map/off forces full) --
 * see ShouldReverseShowAnim, used by GetSoloAnimPreconfType/
 * GetBattleAnimPreconfType (src/bmbattle.c). */
#define ANIMS_FAST_FORWARD_HELD_ANIM_OFF (L_BUTTON | R_BUTTON)

/* Held to run the battle animation as fast as the hardware allows, by
 * skipping the normal VBlankIntrWait pacing at the end of each battle
 * main-loop tick for as long as it's held -- see ShouldSpeedupAnims, used
 * by InBattleMainRoutine (src/banim-ekrbattle.c). */
#define ANIMS_FAST_FORWARD_HELD_SPEEDUP (B_BUTTON)

bool8 ShouldReverseShowAnim(void);
bool8 ShouldSpeedupAnims(void);

#endif

#endif // GUARD_ANIMS_FAST_FORWARD_H
