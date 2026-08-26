#ifndef GUARD_POWER_H
#define GUARD_POWER_H

#if FE8_CO_POWERS

struct MenuProc;
struct MenuItemProc;

/* Map-menu ("Unit"/"Status"/"Guide"/... command list) entry point -- see
 * gMapMenuItems, src/menu_def.c. An Advance Wars-style "CO Powers" roll
 * call: pans the camera onto every one of the player's units in turn and
 * parks the map cursor on each for CO_POWERS_UNIT_DISPLAY_FRAMES frames. */
u8 CoPowers_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem);

/* Map-menu "CO" entry point -- a full-screen, 4-page commander profile
 * (Info / CO Power / Super CO Power / class affinities), reusing the
 * EWRAM_OVERLAY(0) group (statscreen.c and others) since it can never be
 * open at the same time as the unit stat screen. See src/power.c. */
u8 CoScreen_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem);

/* CO gauge: gPlaySt.coGauge[faction >> 6] (see include/types.h). Called
 * from BattleGenerateHitEffects (src/bmbattle.c) for every point of
 * battle damage dealt or received by a faction's units. CoGauge_OnPowerUsed
 * is the depletion hook for whenever a "use CO power" action is added --
 * no such action exists yet, so nothing calls it today. */
void CoGauge_OnDamage(int faction, int amount);
s16 CoGauge_Get(int faction);
void CoGauge_Set(int faction, s16 value);
void CoGauge_OnPowerUsed(int faction);

/* Small read-only accessors onto the CO definition table (src/power.c),
 * for UI code (the CO screen, the VeslyDebugger CO editor) that needs a
 * CO's display name without depending on struct CoDefinition directly. */
int CoScreen_GetCoCount(void);
const char* CoScreen_GetCoName(int coId);

/* CO gauge stars each of a CO's two powers costs. The mini CO gauge
 * (src/aw2_gfx.c) draws CoScreen_GetCoPowerStars small stars followed by
 * the (super - normal) big ones that top it up to the super power.
 * CoScreen_GetCoSuperPowerStars is clamped to never report fewer stars
 * than the normal power costs. */
int CoScreen_GetCoPowerStars(int coId);
int CoScreen_GetCoSuperPowerStars(int coId);

#endif // FE8_CO_POWERS

#endif // GUARD_POWER_H
