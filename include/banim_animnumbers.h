#ifndef GUARD_BANIM_ANIMNUMBERS_H
#define GUARD_BANIM_ANIMNUMBERS_H

#include "global.h"
#include "anime.h"
#include "efxbattle.h"
#include "expansion_config.h"

#define BATTLE_ANIMATION_NUMBERS_FLAG 0xEE

#if FE8_BATTLE_ANIMATION_NUMBERS
int AnimNumbers_DisplayDamage(struct Anim * anim, bool useCappedValue, int previousX, int previousDigitCount);
void AnimNumbers_DisplayAttack(struct Anim * anim);
void AnimNumbers_DisplayHeal(struct Anim * anim);
void AnimNumbers_DisplayNosferatuHeal(struct Anim * anim);
void AnimNumbers_KillDigits(void);
void AnimNumbers_StartDelayedMissNoDamageGfx(void);
void AnimNumbers_ReloadMissNoDamagePalette(struct Anim * anim);
void AnimNumbers_EndDamageMojiSubProc(struct ProcEfxDamageMojiEffectOBJ * proc);
#endif /* FE8_BATTLE_ANIMATION_NUMBERS */

#endif /* GUARD_BANIM_ANIMNUMBERS_H */
