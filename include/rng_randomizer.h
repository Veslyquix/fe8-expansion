/* RNG Randomizer: spins the battle RNG once per frame during the
 * player's own turn (while a battle is in progress, or a unit's movement
 * range is currently being displayed), so the exact roll a battle
 * produces depends on real elapsed frames -- not just deterministic
 * turn/action counting -- meaning a reset-and-replay with identical
 * inputs no longer reproduces the same combat results. Original hack
 * ("RNG Randomizer") by TR143
 * (https://feuniverse.us/t/gba-rng-randomizer/3175); ported from its GBA
 * ASM hooks to native C here, against this repo's own decompiled
 * ExecMainUpdate/AgbMain/LoadRNState -- see src/rng_randomizer.c. */
#ifndef GUARD_RNG_RANDOMIZER_H
#define GUARD_RNG_RANDOMIZER_H

#include "expansion_config.h"

#if FE8_RNG_RANDOMIZER

/* Call once per frame from ExecMainUpdate (src/hardware.c), before the
 * real gMainCallback() dispatch -- matches the original hack's hook
 * point exactly (it replaces ExecMainUpdate's own dispatch code, spins
 * the RNG first, then falls through to the same dispatch it replaced). */
void RngRandomizer_OnMainUpdate(void);

/* Call once from AgbMain (src/main.c), during early boot -- seeds the two
 * sentinel values RngRandomizer_OnMainUpdate reads, so it doesn't spin
 * the RNG before any real battle/unit-selection state exists yet. */
void RngRandomizer_OnBoot(void);

/* Call from LoadRNState (src/rng.c), after it loads the RNG state from a
 * saved buffer -- clears the two sentinels back to their "no battle / no
 * unit selected" values, UNLESS they're still at RngRandomizer_OnBoot's
 * exact sentinel (meaning nothing has touched them since boot, so leave
 * them alone). Runs on every LoadRNState call (arena, link battle, world
 * map skirmish, and resuming a suspended chapter all go through it) --
 * matches the original hack, which hooks LoadRNState itself rather than
 * any one specific caller. */
void RngRandomizer_OnLoadRNState(void);

#endif // FE8_RNG_RANDOMIZER

#endif // GUARD_RNG_RANDOMIZER_H
