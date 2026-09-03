/* RNG Randomizer: see include/rng_randomizer.h for the overall design.
 * Original hack ("RNG Randomizer") by TR143
 * (https://feuniverse.us/t/gba-rng-randomizer/3175), ported from its GBA
 * ASM hooks (rngbodyFE8.asm / BootHackFE8.asm / ResumeHackFE8.asm) to
 * native C, traced against a vanilla FE8U decomp:
 *
 * - rngbodyFE8.asm hooks ExecMainUpdate (src/hardware.c) at its very
 *   first instruction (vanilla 0x08001336, right after ExecMainUpdate's
 *   `push {lr}`), before it dispatches through gMainCallback. Its
 *   "AttackerData" (0x0203A4EC) is gBattleActor's own first field
 *   (gBattleActor.unit.pCharacterData); its "PhasePointer" (0x0202BCFF)
 *   is gPlaySt.faction; its "ActiveUnitDeploymentNumber" (0x03004E6A) is
 *   gMovMapFillState.unitId (offset 0xA of vanilla gMovMapFillState,
 *   0x03004E60 -- see struct MovMapFillState, include/bmidoten.h); its
 *   "GetRandomNumberFunction" (0x08000C64) is NextRN_100.
 * - BootHackFE8.asm hooks AgbMain (src/main.c) right after `sw_rst =
 *   (REG_WAITCNT != 0)` (vanilla 0x08000A4C), setting the two fields
 *   above to out-of-band sentinel values so the per-frame hook can't
 *   fire before real gameplay state exists.
 * - ResumeHackFE8.asm hooks LoadRNState (src/rng.c) itself, near its own
 *   tail (vanilla 0x08000C3C, inside LoadRNState, not any one specific
 *   caller), clearing those sentinels back to "no battle / no unit
 *   selected" -- unless they're still at the exact boot sentinel, in
 *   which case it leaves them alone.
 *
 * The two fields are repurposed purely as sentinel/flag storage here --
 * not their normal meanings -- matching the original hack exactly rather
 * than adding a dedicated new flag, so this stays a faithful port. */
#include "global.h"

#include "expansion_config.h"

#if FE8_RNG_RANDOMIZER

#include "rng_randomizer.h"
#include "rng.h"
#include "bmbattle.h"
#include "bmidoten.h"
#include "bmunit.h"

#define RNG_RANDOMIZER_BOOT_ATTACKER_SENTINEL ((const struct CharacterData*)0xFFFFFFFF)
#define RNG_RANDOMIZER_BOOT_UNIT_ID_SENTINEL 0xFF

void RngRandomizer_OnMainUpdate(void)
{
    if (gPlaySt.faction != FACTION_BLUE)
        return;

    if (gBattleActor.unit.pCharacterData != NULL || gMovMapFillState.unitId != 0)
        NextRN_100();
}

void RngRandomizer_OnBoot(void)
{
    gBattleActor.unit.pCharacterData = RNG_RANDOMIZER_BOOT_ATTACKER_SENTINEL;
    gMovMapFillState.unitId = RNG_RANDOMIZER_BOOT_UNIT_ID_SENTINEL;
}

void RngRandomizer_OnLoadRNState(void)
{
    if (gBattleActor.unit.pCharacterData != RNG_RANDOMIZER_BOOT_ATTACKER_SENTINEL)
        gBattleActor.unit.pCharacterData = NULL;

    if (gMovMapFillState.unitId != RNG_RANDOMIZER_BOOT_UNIT_ID_SENTINEL)
        gMovMapFillState.unitId = 0;
}

#endif // FE8_RNG_RANDOMIZER
