#ifndef GUARD_POWER_H
#define GUARD_POWER_H

#if FE8_CO_POWERS

/* CO ids -- also the index into sCoDefinitions (src/power.c). Public so
 * event scripts (e.g. src/events/prologue-eventscript.h) can name a CO
 * when setting up a faction's commander via SetFactionCo. */
enum {
    CO_NONE = 0, 
    CO_WAKWI,
    CO_ISHKODE,
    CO_ASIN,
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

/* Open the CO info page on a specific CO, blocking `parent` until B closes it.
 * Unlike the map-menu entry above, this hands the screen back still faded out
 * and does not redraw the map, so the caller must put its own display back --
 * see src/coSelect.c, where R opens this and B returns to the carousel. */
void StartCoScreenForCo(ProcPtr parent, int coId);

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
 * power lasts until its own faction's *next* turn (Advance Wars rules), so
 * call this once right as that faction's own phase starts again. Currently
 * called from BmMain_ChangePhase (src/bm.c), right after SwitchPhases(),
 * for whichever faction's phase is starting. Safe to call even if that
 * faction had no power active. */
void CoPowers_OnPhaseStart(int faction);

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

/* struct CoDefinition accessors for the CO select screen (src/coSelect.c),
 * which cannot see the static sCoDefinitions table directly.
 * Co_GetDisplayClassId returns the CO's real unit's current class if that unit
 * is on the map, else the character's defaultClass. */
int Co_GetCharId(int coId);
int Co_GetBriefMsg(int coId);
int Co_GetDisplayClassId(int coId);

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




#define CO_AFFINITY_ROW_MAX 7

enum {
    CO_SCREEN_PAGE_INFO,
    CO_SCREEN_PAGE_POWER,
    CO_SCREEN_PAGE_SUPER,
    CO_SCREEN_PAGE_AFFINITY,
    CO_SCREEN_PAGE_COUNT,
};

struct CoClassAffinity {
    u8 classId;
    /* rating: the class's baseline affinity (CO_AFFINITY_NEUTRAL_RATING ==
     * neutral), proportionally scaling POW same as a weapon's own Pow bonus
     * -- see AdjustStatForCo. ratingPow/ratingSup ADD to rating while
     * coId's power/super is active (see GetCoActivePowerStateForCo,
     * GetEffectiveClassAffinityRating) -- unlike the *Bon fields below,
     * this one stacks rather than replaces, since it's already a
     * proportional adjustment rather than a flat shift. */
    u8 rating;
    u8 ratingPow;
    u8 ratingSup;

    /* -3..+3, drawn as [type icon][sign icon][magnitude digit] directly
     * below the class's affinity bar (see
     * CoScreen_DrawPageAffinityClassBonusIcons). 0 draws nothing.
     * movBon: applied unconditionally (FE8_CO_POWERS alone) to actual
     * unit movement -- see GetCoClassMovBonus, GetUnitMovement
     * (src/bmunit.c). rangeBon: applied to actual weapon attack range
     * only when FE8_RANGE_REWORK is also on -- see GetCoClassRangeBonus,
     * GetUnitItemEffectiveMaxRange (src/bmitem.c); with RANGE_REWORK off,
     * this still draws the icon but doesn't change what the unit can
     * actually hit (the vanilla reach-bits system it would need to feed
     * into can't represent a shifted range at all -- see RANGE_REWORK's
     * config.mk comment). critBon: applied unconditionally (FE8_CO_POWERS
     * alone) to battle crit rate -- see GetCoClassCritBonus,
     * ComputeBattleUnitCritRate (src/bmbattle.c).
     *
     * movBonPow/rangeBonPow/critBonPow REPLACE their plain field while
     * coId's power is active, and movBonSup/rangeBonSup/critBonSup REPLACE
     * it while coId's super is active -- unlike rating above, these don't
     * stack with the plain value, since a flat +/-N shift doesn't have a
     * sensible "add both" reading. None of the icon drawing reflects the
     * Pow/Sup variants -- the affinity page always shows the plain
     * movBon/rangeBon regardless of whether a power happens to be active. */
    s8 movBon;
    s8 movBonPow;
    s8 movBonSup;
    s8 rangeBon;
    s8 rangeBonPow;
    s8 rangeBonSup;
    s8 critBon;
    s8 critBonPow;
    s8 critBonSup;
};

/* CoScreen_DrawPageAffinity's bar base: a class's affinity bar (and
 * CoPower_ClassAffinityGroup below) is green/positive above this, red/
 * negative below it, plain yellow/neutral exactly at it. */
#define CO_AFFINITY_NEUTRAL_RATING 30

/* Which classes a CO power affects, by their affinity rating relative to
 * CO_AFFINITY_NEUTRAL_RATING -- struct CoDefinition's powerTargetGroup/
 * superPowerTargetGroup (the two needn't match: a power and its super
 * don't have to target the same classes). A class the CO has no explicit
 * struct CoClassAffinity entry for defaults to neutral (see
 * CoPower_ClassAffinityGroup). */
enum CoPowerTargetGroup {
    CO_POWER_TARGET_ALL,
    CO_POWER_TARGET_POSITIVE,
    CO_POWER_TARGET_POSITIVE_NEUTRAL,
    CO_POWER_TARGET_NEGATIVE,
    CO_POWER_TARGET_NEGATIVE_NEUTRAL,
    CO_POWER_TARGET_NEGATIVE_POSITIVE,
};


struct CoDefinition {
    /* The real character this CO is. Every CO has one. Their display name
     * and portrait come from it (GetCharacterData()->nameTextId /
     * ->portraitId) rather than being duplicated here, and the CO select
     * screen (src/coSelect.c) uses it to find the CO's unit on the map so
     * it can show that unit's actual class in the carousel, falling back to
     * ->defaultClass when the unit isn't deployed. */
    u16 charId;
    u16 titleMsg; // shown on the info page (e.g. their epithet)
    u16 briefMsg; 
    u16 infoMsg; // single texts.txt entry, [LF]-separated (see PrintStringToTexts, src/scene.c)
    u16 powerNameMsg;
    u16 powerDescMsg; // single texts.txt entry, [LF]-separated
    u16 superPowerNameMsg;
    u16 superPowerDescMsg; // single texts.txt entry, [LF]-separated
    /* CO gauge stars each power costs. The mini CO gauge (src/aw2_gfx.c)
     * draws powerStars small stars followed by the
     * (superPowerStars - powerStars) big ones that top it up to the super,
     * so superPowerStars must be >= powerStars. */
    u8 powerStars;
    u8 superPowerStars;
    /* enum CoPowerTargetGroup -- which classes the power/super actually
     * affects when used (see CoPower_AppliesToClass). Defaults to
     * CO_POWER_TARGET_ALL (0) if left off a CoDefinition. */
    u8 powerTargetGroup;
    u8 superPowerTargetGroup;
    const struct CoClassAffinity* affinities;
    u8 affinityCount;
};

/* Mirrors the classes actually sellable in sPurchaseGenericDefinitions
 * (src/purchase_generics.c) -- keep the class list in sync if that table
 * changes. */
 
/* Co power ideas: 
- Spawn generics in empty controlled properties + adjacent to camp
- Spawn generics of x class in forests within x tiles from controlled properties 
- Grant x classes +n movement or attack range 
- */ 






#endif // FE8_CO_POWERS

#endif // GUARD_POWER_H
