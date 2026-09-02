#ifndef GUARD_POWER_H
#define GUARD_POWER_H

#if FE8_CO_POWERS

/* CO ids -- also the index into sCoDefinitions (src/power.c). Public so
 * event scripts (e.g. src/events/prologue-eventscript.h) can name a CO
 * when setting up a faction's commander via SetFactionCo. */
enum {
    CO_WAKWI,
    CO_ISHKODE,
    CO_FRANCIS,
    CO_KARGAN,
    CO_COUNT,
};

struct MenuProc;
struct MenuItemProc;

/* Map-menu ("Unit"/"Status"/"Guide"/... command list) entry points -- see
 * gMapMenuItems, src/menu_def.c. An Advance Wars-style "CO Powers" roll
 * call: pans the camera onto every one of the player's units in turn,
 * applying the commander's power (or super, for the second one) to
 * whichever ones CoPower_AppliesToClass (src/power.c) says it targets --
 * see also CO_FRANCIS_POWER_HEAL_AMOUNT there for the one CO with an
 * effect implemented so far. */
u8 CoPowers_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem);
u8 CoSuperPowers_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem);

/* Menu usability checks for the two entries above: MENU_DISABLED (greyed
 * out, still visible) until the player faction's CO gauge reaches their
 * commander's powerStars/superPowerStars requirement (respectively),
 * MENU_ENABLED once it has. */
struct MenuItemDef;
u8 CoPowers_IsAvailable(const struct MenuItemDef* def, int number);
u8 CoSuperPowers_IsAvailable(const struct MenuItemDef* def, int number);

/* Map-menu "CO" entry point -- a full-screen, 4-page commander profile
 * (Info / CO Power / Super CO Power / class affinities), reusing the
 * EWRAM_OVERLAY(0) group (statscreen.c and others) since it can never be
 * open at the same time as the unit stat screen. See src/power.c. */
u8 CoScreen_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem);

/* CO gauge points one star (struct CoDefinition's powerStars/
 * superPowerStars, and the CO gauge stat screen/mini-gauge UI) is worth.
 * The one place this belongs, shared by src/aw2_gfx.c (which star of the
 * gauge to fill in) and src/VeslyDebugger.c (its CO editor's +/- gauge
 * step and heart display) -- previously each had their own copy of this
 * same number (AW2_GAUGE_PER_STAR, CoGaugeStep). */
#define CO_GAUGE_PER_STAR 50

/* CO gauge: gPlaySt.coGauge[faction >> 6] (see include/types.h). Called
 * from BattleGenerateHitEffects (src/bmbattle.c) for every point of
 * battle damage dealt or received by a faction's units. CoGauge_OnPowerUsed
 * is the depletion hook for using either CO power (see
 * CoPowersMenuCommandCommon, src/power.c) -- resets to 0, matching Advance
 * Wars: using a power drains the whole gauge, not just its star cost. */
void CoGauge_OnDamage(int faction, int amount);
s16 CoGauge_Get(int faction);
void CoGauge_Set(int faction, s16 value);
void CoGauge_OnPowerUsed(int faction);

/* Called from AiPhaseCoPowersHook (src/cp_phase.c), its own step in
 * gProcScr_CpPhase, right after AiPhaseInit and before the faction's own
 * turn logic (gProcScr_CpOrder) starts. gPlaySt.faction is already the AI
 * faction (FACTION_RED/FACTION_GREEN) by this point. Decides, from gauge
 * fullness alone, whether to use the super power (gauge at or past
 * superPowerStars), the regular power (gauge at exactly powerStars, no
 * more), or neither (gauge short of powerStars, or past it but still
 * short of the super -- the AI holds out rather than spending early).
 * parent must be the caller's own proc, so the roll-call/effect proc this
 * starts (when it does) blocks the caller until it fully finishes. */
struct Proc;
int CoPowers_OnAiPhaseStart(struct Proc* parent);

/* Marks faction's CO power/super as no longer active (see the *Pow/*Sup
 * fields of struct CoClassAffinity, src/power.c, and AdjustStatForCo/
 * GetCoClassMovBonus/GetCoClassRangeBonus/GetCoClassCritBonus below) -- a
 * power lasts only for the rest of its own faction's turn (Advance Wars
 * rules), so call this once at that faction's own phase end. Currently
 * called from BmMain_ChangePhase (src/bm.c), for whichever faction's phase
 * is ending. Safe to call even if that faction had no power active. */
void CoPowers_OnPhaseEnd(int faction);

/* Sets which CO (a CO_* id above) is faction's commander --
 * gPlaySt.commanderId[faction >> 6] (see include/types.h; faction is a
 * raw FACTION_BLUE/GREEN/RED/PURPLE byte, not a FACTION_ID_*, same
 * convention as CoGauge_Get/_Set above). Called from event setup code
 * (e.g. ASMC in an EventListScr) to assign each side's commander before
 * the map starts -- see src/events/prologue-eventscript.h. */
void SetFactionCo(int faction, int coId);

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

/* A CO's class affinity (struct CoClassAffinity, sFrancisAffinities etc.)
 * scales a class's power the same way a weapon's Pow bonus does: this
 * returns the delta to add to baseValue (POW only -- other stats are
 * unaffected), not the adjusted total, so callers use it exactly like
 * GetItemPowBonus (src/bmunit.c's GetUnitPower, purchase_generics.c's
 * class-preview stat). A rating != CO_AFFINITY_NEUTRAL_RATING (30) always
 * moves the stat by at least 1 point, even when proportional scaling would
 * round to no change; the result is never allowed to bring the stat below
 * 0. While coId's power/super is active (see CoPowers_OnPhaseEnd above),
 * ratingPow/ratingSup are added on top of rating first -- unlike the
 * *Bon fields below, these stack rather than replace. An out-of-range
 * coId falls back to CO_FRANCIS, same as every other lookup through
 * GetCoDefinition. */
int AdjustStatForCo(int coId, int classId, int baseValue);

/* A CO's class-affinity movBon (struct CoClassAffinity) for classId, or 0
 * if coId has no explicit entry for that class. Like GetCoClassRangeBonus/
 * GetCoClassCritBonus below, this is the raw signed shift already -- not
 * proportionally scaled against a base value the way AdjustStatForCo's
 * rating is, since a movement shift is a flat +/-N. See GetUnitMovement
 * (src/bmunit.c) for how this actually gets applied. Unconditional on
 * FE8_CO_POWERS alone (not FE8_RANGE_REWORK) -- movement isn't a
 * range-mechanic fix, just another CO-driven stat adjustment alongside
 * AdjustStatForCo's POW. An out-of-range coId falls back the same way
 * GetCoDefinition always does.
 *
 * While coId's power/super is active, this returns movBonPow/movBonSup
 * INSTEAD of movBon -- unlike AdjustStatForCo's rating, a flat +/-N shift
 * doesn't have a sensible "stack both" reading, so the Pow/Sup value
 * replaces the plain one rather than adding to it. */
int GetCoClassMovBonus(int coId, int classId);

#if FE8_RANGE_REWORK
/* A CO's class-affinity rangeBon (struct CoClassAffinity) for classId, or
 * 0 if coId has no explicit entry for that class. Unlike AdjustStatForCo's
 * rating, this is the raw signed shift already -- not proportionally
 * scaled against a base value, since a range shift is a flat +/-N, not a
 * stat-growth-style percentage. See GetUnitItemEffectiveMaxRange
 * (src/bmitem.c) for how this actually gets applied to a weapon's max
 * range. An out-of-range coId falls back the same way GetCoDefinition
 * always does. Replaced (not added to) by rangeBonPow/rangeBonSup while
 * coId's power/super is active -- same rule as GetCoClassMovBonus. */
int GetCoClassRangeBonus(int coId, int classId);
#endif

/* A CO's class-affinity critBon (struct CoClassAffinity) for classId, or 0
 * if coId has no explicit entry for that class -- same raw-flat-shift,
 * Pow/Sup-replaces-not-adds convention as GetCoClassMovBonus. Applied to
 * battle crit rate in ComputeBattleUnitCritRate (src/bmbattle.c).
 * Unconditional on FE8_CO_POWERS alone, same as movBon (crit isn't a
 * range mechanic either). */
int GetCoClassCritBonus(int coId, int classId);

#endif // FE8_CO_POWERS

#endif // GUARD_POWER_H
