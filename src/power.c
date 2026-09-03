#include "global.h"

#if FE8_CO_POWERS

#include "proc.h"
#include "hardware.h"
#include "fontgrp.h"
#include "bmunit.h"
#include "bm.h"
#include "bmio.h"
#include "bmlib.h"
#include "bmudisp.h"
#include "bmdifficulty.h"
#include "sysutil.h"
#include "savemenu.h"
#include "soundwrapper.h"
#include "uiutils.h"
#include "uimenu.h"
#include "face.h"
#include "constants/characters.h"
#include "constants/classes.h"
#include "constants/songs.h"
#include "constants/msg.h"
#include "bg.h"
#include "scene.h"
#include "power.h"
#include "mapanim.h"
#include "statscreen.h"
#include "ctc.h"
#include "ap.h"
#include "eventinfo.h"
#include "efxbattle.h"
#include "constants/items.h"
#include "constants/video-global.h"
#include "icon.h"
#include "player_interface.h" // Start/EndPlayerPhaseSideWindows
#include "savemenu.h"
#if FE8_AW2_ASSETS
#include "aw2_gfx.h"
#include "phasechangefx.h" // gProcScr_PhaseIntroSquares/BlendBox, Img_PhaseChangeSquares
#endif


/* Define this to make the CO screen's Up/Down scroll (CoScreen_KeyListener)
 * cycle through every defined CO, including ones no faction is currently
 * using -- useful for browsing/debugging all COs regardless of the actual
 * match. Left undefined by default: scrolling only reaches a CO that some
 * faction's gPlaySt.commanderId[] is actually set to (see IsCoInUse/
 * FindNextUsedCoId below), so e.g. Blue using Ishkode and Red using
 * O'Neill won't also scroll past unused COs like Francis. */
// #define SCROLL_ALL_COS

#define CO_POWERS_UNIT_DISPLAY_FRAMES 5

/* Which power state (none/normal/super) each faction's CO currently has
 * active. A CO Power in this system lasts until its own faction's *next*
 * turn -- it stays active through every other faction's phase in between
 * (Advance Wars rules -- using either power drains the whole gauge, see
 * CoPowersMenuCommandCommon), so this is set the moment the gauge gets
 * spent (CoPowersMenuCommandCommon for the player, CoPowers_OnAiPhaseStart
 * for the AI) and cleared right as that faction's own phase starts again
 * (CoPowers_OnPhaseStart, called from BmMain_ChangePhase, src/bm.c, right
 * after SwitchPhases() flips gPlaySt.faction to the newly-starting phase).
 * Transient, not saved -- EWRAM_DATA like gAiState (src/
 * cp_phase.c), not gPlaySt (which IS saved and would need a save-compat
 * epoch bump for a new field).
 *
 * Read through GetCoActivePowerStateForCo below by coId rather than
 * faction, matching AdjustStatForCo/GetCoClassMovBonus/GetCoClassRangeBonus's
 * existing (coId, classId) signature -- a coId is always commanding at
 * most one faction at a time, so the reverse lookup there is unambiguous. */
enum {
    CO_POWER_STATE_NONE,
    CO_POWER_STATE_NORMAL,
    CO_POWER_STATE_SUPER,
};

EWRAM_DATA static u8 sCoActivePowerState[4] = {0};

/* See declaration comment (include/power.h). */
void CoPowers_OnPhaseStart(int faction)
{
    sCoActivePowerState[faction >> 6] = CO_POWER_STATE_NONE;
}

/* coId's active power state, if it's any faction's current commander right
 * now (CO_POWER_STATE_NONE if it isn't commanding anyone -- shouldn't
 * normally happen for a live call, but a safe default). */
static int GetCoActivePowerStateForCo(int coId)
{
    int f;

    for (f = 0; f < 4; ++f) {
        if (gPlaySt.commanderId[f] == coId)
            return sCoActivePowerState[f];
    }

    return CO_POWER_STATE_NONE;
}

// moves the camera onto each of faction's units, applying that faction's CO's
// power (or super, if isSuper) to whichever ones CoPower_AppliesToClass says
// it targets -- used both for the player's own menu commands (faction always
// FACTION_BLUE there) and for an AI faction's power at its phase start (see
// CoPowers_OnAiPhaseStart)
struct CoPowersProc
{
    PROC_HEADER;

    u8 unitIndex; // current unit
    u8 faction; // FACTION_BLUE/GREEN/RED/PURPLE (bmunit.h)
    bool8 isSuper; // set by the caller right after Proc_Start, see below
#if FE8_AW2_ASSETS
    s8 bannerTimer; // CoPowerBanner_Init/_Loop -- frames left showing the intro banner
#endif
};

static void CoPowers_LockIfPlayerPhase(struct CoPowersProc* proc);
static void CoPowers_UnlockIfPlayerPhase(struct CoPowersProc* proc);
static void CoPowers_ReopenSideWindowsIfPlayerPhase(struct CoPowersProc* proc);
static void CoPowers_Init(struct CoPowersProc* proc);
static void CoPowers_Step(struct CoPowersProc* proc);
static void CoPowers_Anim(struct CoPowersProc* proc);
static void CoPowers_ReturnCamera(struct CoPowersProc* proc);
static bool8 CoPower_AppliesToClass(int coId, bool8 isSuper, int classId);
static void CoPower_ApplyEffect(int coId, bool8 isSuper, struct Unit* unit);
struct ProcCmd CONST_DATA ProcScr_MapAnimBarrierfx2[];
#if FE8_AW2_ASSETS
static void CoPowerBanner_Init(struct CoPowersProc* proc);
static void CoPowerBanner_Loop(struct CoPowersProc* proc);
static void CoPowerBanner_Cleanup(struct CoPowersProc* proc);
#endif

CONST_DATA struct ProcCmd gProcScr_CoPowers[] = {
    PROC_NAME("COPOWERS"),
    /* Proc_Start/Proc_StartBlocking run the script synchronously up to its
     * first blocking command before returning, so this leading sleep has
     * to come before ANYTHING that reads a caller-set field -- both
     * proc->faction (CoPowers_Init, and now CoPowers_LockIfPlayerPhase
     * below) and, transitively, proc->isSuper -- since neither
     * CoPowersMenuCommandCommon nor CoPowers_OnAiPhaseStart get a chance
     * to set them on the pointer Proc_Start/Proc_StartBlocking hands back
     * until AFTER that call returns. Same hazard gProcScr_CoCommanderFade's
     * leading PROC_SLEEP(0) guards against. */
    PROC_SLEEP(0),
    /* LockGame skips PROC_TREE_2 entirely for as long as it's held (see
     * src/bm.c) -- correct here for the player's own menu command, which
     * CoPowersMenuCommandCommon starts on its own PROC_TREE_3 (freezing
     * the map/cursor under it is exactly the point). But gProc_BMapMain
     * (the whole map main loop, AI phase included) is itself rooted on
     * PROC_TREE_2 -- CoPowers_OnAiPhaseStart starts this proc as a CHILD
     * of an AI-phase proc that's already running ON tree 2, so calling
     * LockGame there stops this proc's own tree from ever being ticked
     * again, permanently deadlocking it one frame in. There's no player
     * cursor to protect during an AI turn anyway, so only lock when
     * faction is FACTION_BLUE -- see CoPowers_LockIfPlayerPhase below. */
    PROC_CALL(CoPowers_LockIfPlayerPhase),
    PROC_CALL(EndPlayerPhaseSideWindows),
#if FE8_AW2_ASSETS
    /* POWER/SUPER banner, styled after the phase-change intro (see
     * src/phasechangefx.c) -- CoPowerBanner_Init reads proc->isSuper
     * (already valid past the PROC_SLEEP(0) above) to pick which graphic,
     * starts the borrowed squares-wipe/blend-box decoration as its own
     * children, and seeds the hold timer CoPowerBanner_Loop counts down
     * (twice as fast with B held -- see its own comment). */
    PROC_CALL(CoPowerBanner_Init),
    PROC_REPEAT(CoPowerBanner_Loop),
    PROC_CALL(CoPowerBanner_Cleanup),
#endif
    PROC_CALL(CoPowers_Init),

PROC_LABEL(0),
    PROC_CALL(CoPowers_Step),
    PROC_WHILE_EXISTS(ProcScr_CamMove),
    PROC_CALL(CoPowers_Anim),
    PROC_SLEEP(1),
    PROC_WHILE_EXISTS(ProcScr_MapAnimBarrierfx2),
    // PROC_SLEEP(CO_POWERS_UNIT_DISPLAY_FRAMES),
    PROC_GOTO(0),
PROC_LABEL(99),
    PROC_CALL(CoPowers_ReturnCamera),
    PROC_WHILE_EXISTS(ProcScr_CamMove),
    PROC_CALL(CoPowers_UnlockIfPlayerPhase),
    PROC_CALL(CoPowers_ReopenSideWindowsIfPlayerPhase),
    PROC_END,
};

/* See the leading-comment block on gProcScr_CoPowers above: only lock for
 * the player's own menu command (always FACTION_BLUE, and started on its
 * own PROC_TREE_3) -- locking during an AI faction's turn would freeze
 * PROC_TREE_2, which this proc itself is running on there, deadlocking it. */
static void CoPowers_LockIfPlayerPhase(struct CoPowersProc* proc)
{
    if (proc->faction == FACTION_BLUE)
        LockGame();
}
static void CoPowers_UnlockIfPlayerPhase(struct CoPowersProc* proc)
{
    if (proc->faction == FACTION_BLUE)
        UnlockGame();
}

/* EndPlayerPhaseSideWindows (above, this proc's leading steps) tears down
 * the goal/terrain/MMB windows before the roll-call starts, but nothing
 * ever restarted them once it's done -- StartPlayerPhaseSideWindows is the
 * same call playerphase.c itself makes at the start of a player phase.
 * AI/CP phase's own goal window (gProcScr_AiGoalDisplay, src/player_
 * interface.c) is a separate proc EndPlayerPhaseSideWindows above doesn't
 * touch, so this only needs to act for the player's own turn. */
static void CoPowers_ReopenSideWindowsIfPlayerPhase(struct CoPowersProc* proc)
{
    if (proc->faction == FACTION_BLUE)
        StartPlayerPhaseSideWindows();
}

static void CoPowers_Init(struct CoPowersProc* proc)
{
    proc->unitIndex = proc->faction;
}
static void CoPowers_ReturnCamera(struct CoPowersProc* proc)
{
    EnsureCameraOntoPosition(proc, gBmSt.playerCursor.x, gBmSt.playerCursor.y);
}

#if FE8_AW2_ASSETS
/* ~1 second at 60fps; CoPowerBanner_Loop halves this (rounding down, so an
 * odd leftover frame at 2x) whenever B is held. */
#define CO_POWER_BANNER_HOLD_FRAMES 60

/* Sets up the borrowed phase-change squares-wipe/blend-box decoration
 * (src/phasechangefx.c) -- started as our own children rather than the
 * bundled ProcScr_PhaseIntro, since that one is tied to Player/Enemy/Other
 * phase text and pulls in a VCount-interrupt gradient this banner doesn't
 * need. Pal_PhaseChange_0 is the one variant of that palette not already
 * tied to a specific faction's tint. */
static void CoPowerBanner_Init(struct CoPowersProc* proc)
{
    LoadAw2PowerBannerGfx(proc->isSuper);

    Decompress(Img_PhaseChangeSquares, BG_CHR_ADDR(BGCHR_PHASE_CHANGE_SQUARES));
    ApplyPalette(Pal_PhaseChange_0, BGPAL_PHASE_CHANGE);

    BG_SetPosition(BG_0, 0, 0);
    BG_SetPosition(BG_1, 0, 0);

    SetWinEnable(1, 0, 0);
    SetWin0Box(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT);
    SetWin0Layers(1, 0, 1, 1, 1);
    SetWOutLayers(1, 1, 1, 1, 1);
    gLCDControlBuffer.wincnt.win0_enableBlend = 1;
    gLCDControlBuffer.wincnt.wout_enableBlend = 1;

    gBmSt.altBlendBCa = 0;
    gBmSt.altBlendBCb = 0x10;
    SetBlendConfig(1, gBmSt.altBlendBCa, gBmSt.altBlendBCb, 0);
    SetBlendTargetA(0, 1, 0, 0, 0);
    SetBlendTargetB(0, 0, 1, 1, 1);

    Proc_Start(gProcScr_PhaseIntroSquares, proc);
    Proc_Start(gProcScr_PhaseIntroBlendBox, proc);

    proc->bannerTimer = CO_POWER_BANNER_HOLD_FRAMES;
}

static void CoPowerBanner_Loop(struct CoPowersProc* proc)
{
    SetBlendConfig(1, gBmSt.altBlendBCa, gBmSt.altBlendBCb, 0);

    DrawAw2PowerBannerSprite(proc->isSuper);

    proc->bannerTimer -= (gKeyStatusPtr->heldKeys & B_BUTTON) ? 2 : 1;

    if (proc->bannerTimer <= 0)
        Proc_Break(proc);
}

static void CoPowerBanner_Cleanup(struct CoPowersProc* proc)
{
    Proc_EndEach(gProcScr_PhaseIntroSquares);
    Proc_EndEach(gProcScr_PhaseIntroBlendBox);

    SetWinEnable(0, 0, 0);
    SetDefaultColorEffects();

    ClearBg0Bg1();

    BG_SetPosition(BG_0, 0, 0);
    BG_SetPosition(BG_1, 0, 0);
}
#endif

static void CoPowers_Step(struct CoPowersProc* proc)
{
    int i;
    struct Unit* unit = NULL;

    for (i = proc->unitIndex + 1; i < proc->faction + 0x40; ++i) {
        struct Unit* candidate = GetUnit(i);

        if (UNIT_IS_VALID(candidate) && !(candidate->state & (US_DEAD | US_HIDDEN | US_NOT_DEPLOYED))) {
            unit = candidate;
            break;
        }
    }

    if (!unit) {
        Proc_Goto(proc, 99);
        return;
    }

    proc->unitIndex = i;

    EnsureCameraOntoPosition(proc, unit->xPos, unit->yPos);
    // SetCursorMapPosition(unit->xPos, unit->yPos);
}

// display a glowy animation on each unit
void MapAnimBarrierfx_Loop2(struct MAEffectProc * proc)
{
    static u8 const unk_param_list[] =
    {
        0, 0, 1, 1, 1, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1,
        // 1, 1, 1, 1, 1, 1, 1, 1,
        // 1, 1, 1, 1, 1, 1, 1, 1,
        // 1, 1, 1, 1, 1, 1, 1, 1,
        // 1, 1, 1, 1, 0, 0,

        UINT8_MAX, // end
    };
    int steps = 1;

#if FE8_AW2_ASSETS
    /* Holding B during a CO power/super power roll-call (see gProcScr_
     * CoPowers, CoPower_ApplyEffect's caller) plays this same animation
     * twice as fast on every unit it targets -- two real steps per tick
     * instead of one, so it finishes in half the frames. Bounds-checked the
     * same way each single step already was: never take a second step past
     * one that just hit the terminator. */
    if (gKeyStatusPtr->heldKeys & B_BUTTON)
        steps = 2;
#endif

    while (steps-- > 0)
    {
        PutTmAnimFrameFromTsa(
            gBG2TilemapBuffer,
            proc->xDisplay / 8 - 2, proc->yDisplay / 8 - 8,
            TILEREF(BGCHR_MANIM_160, BGPAL_MANIM_4),
            4, 10, Tsa_Mapnightmare,
            unk_param_list[proc->unk48++]);

        if (unk_param_list[proc->unk48] == UINT8_MAX)
        {
            BG_EnableSyncByMask(BG2_SYNC_BIT);
            Proc_Break(proc);
            return;
        }
    }

    BG_EnableSyncByMask(BG2_SYNC_BIT);
}
struct ProcCmd CONST_DATA ProcScr_MapAnimBarrierfx2[] = {
    PROC_SLEEP(1),
    PROC_CALL(MapAnimBarrierfx_Init),
    PROC_REPEAT(MapAnimBarrierfx_Loop2),
    PROC_CALL(MapSpellAnim_CommonEnd),
    PROC_END,
};
void MapAnimCallSpellAssocBarrierfx2(struct Unit * unit)
{
    struct MAEffectProc * proc;

    proc = Proc_Start(ProcScr_MapAnimBarrierfx2, PROC_TREE_3);

    proc->xDisplay = (SCREEN_TILE_X(unit->xPos) * 2 + 1) * 8;
    proc->yDisplay = (SCREEN_TILE_Y(unit->yPos) * 2 + 1) * 8;
}
static void CoPowers_Anim(struct CoPowersProc* proc)
{
    struct Unit* unit = GetUnit(proc->unitIndex);
    int coId;

    if (!UNIT_IS_VALID(unit))
        return;

    coId = gPlaySt.commanderId[proc->faction >> 6];

    /* Units of a class the power/super doesn't target are skipped
     * silently -- no effect, no barrier animation on them either, so the
     * roll-call only visibly stops on units it's actually doing something
     * to. */
    if (!CoPower_AppliesToClass(coId, proc->isSuper, unit->pClassData->number))
        return;

    CoPower_ApplyEffect(coId, proc->isSuper, unit);

    MapAnimCallSpellAssocBarrierfx2(unit);
}

/* Greyed out (visible, not selectable) until the player faction's CO
 * gauge has charged up to their commander's powerStars requirement --
 * gPlaySt.commanderId/coGauge are per-faction (FACTION_BLUE/GREEN/RED/
 * PURPLE, bmunit.h; see include/types.h), and this is always the map
 * menu's own player-side command, so FACTION_BLUE. */
u8 CoPowers_IsAvailable(const struct MenuItemDef* def, int number)
{
    int coId = gPlaySt.commanderId[FACTION_BLUE >> 6];
    int needed = CoScreen_GetCoPowerStars(coId) * CO_GAUGE_PER_STAR;

    if (CoGauge_Get(FACTION_BLUE) < needed)
        return MENU_DISABLED;

    return MENU_ENABLED;
}



/* Same as CoPowers_IsAvailable, gated on superPowerStars instead. */
u8 CoSuperPowers_IsAvailable(const struct MenuItemDef* def, int number)
{
    int coId = gPlaySt.commanderId[FACTION_BLUE >> 6];
    int needed = CoScreen_GetCoSuperPowerStars(coId) * CO_GAUGE_PER_STAR;

    if (CoGauge_Get(FACTION_BLUE) < needed)
        return MENU_DISABLED;

    return MENU_ENABLED;
}

/* Shared by both menu commands below: spends the whole gauge (matching
 * Advance Wars -- using either power drains it completely, not just the
 * star cost) and starts the roll-call/effect proc, telling it via isSuper
 * which of the two just got used. */
static u8 CoPowersMenuCommandCommon(bool8 isSuper)
{
    struct CoPowersProc* proc;

    CoGauge_OnPowerUsed(FACTION_BLUE);
    sCoActivePowerState[FACTION_BLUE >> 6] = isSuper ? CO_POWER_STATE_SUPER : CO_POWER_STATE_NORMAL;

    proc = (struct CoPowersProc*)Proc_Start(gProcScr_CoPowers, PROC_TREE_3);
    proc->faction = FACTION_BLUE;
    proc->isSuper = isSuper;

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

u8 CoPowers_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    if (CoPowers_IsAvailable(NULL, 0) != MENU_ENABLED) { 
        return MENU_ACT_SND6B; 
    } 
    return CoPowersMenuCommandCommon(FALSE);
}

u8 CoSuperPowers_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    if (CoSuperPowers_IsAvailable(NULL, 0) != MENU_ENABLED) { 
        return MENU_ACT_SND6B; 
    } 
    return CoPowersMenuCommandCommon(TRUE);
}

/* ---------------------------------------------------------------------- *
 * CO profile screen ("CO" map-menu entry): a full-screen, 4-page
 * commander bio, laid out with the same portrait+name header on every
 * page (like the unit stat screen's left panel, src/statscreen.c). 
 * ---------------------------------------------------------------------- */

#define CO_AFFINITY_ROW_MAX 7

enum {
    CO_SCREEN_PAGE_INFO,
    CO_SCREEN_PAGE_POWER,
    CO_SCREEN_PAGE_SUPER,
    CO_SCREEN_PAGE_AFFINITY,
    CO_SCREEN_PAGE_COUNT,
};

struct CoClassAffinity {
    const char* className; // unused for display now (SMS icon + bar replace name+hearts); kept for reference/tooling
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
    u16 nameMsg;
    int faceId;
    u16 titleMsg; // shown on the info page (e.g. their epithet)
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
- 




*/ 
 
/* Wakwi is a critical hit specialist */ 
// issue: classes not shown here don't get the crit bonus 
 static const struct CoClassAffinity sWakwiAffinities[] = {
    { "Soldier",        CLASS_SOLDIER,          30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Knight",         CLASS_ARMOR_KNIGHT,     30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Brigand",        CLASS_BRIGAND,          30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Archer",         CLASS_ARCHER,           30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Fighter",        CLASS_FIGHTER,          30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Mercenary",      CLASS_MERCENARY,        30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Cavalier",       CLASS_CAVALIER,         30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Monk",           CLASS_MONK,             30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Mage",           CLASS_MAGE,             30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Shaman",         CLASS_SHAMAN,           30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Cleric",         CLASS_CLERIC,           30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Thief",          CLASS_THIEF,            30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Pegasus Kn.",   CLASS_PEGASUS_KNIGHT,    30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
    { "Wyvern Rider",  CLASS_WYVERN_RIDER,      30, .critBon = 10, .critBonPow = 40, .critBonSup = 100 },
};

/* Ishkode is a ranged specialist */
static const struct CoClassAffinity sIshkodeAffinities[] = {
    { "Soldier",    CLASS_SOLDIER,       30 },
    { "Knight",     CLASS_ARMOR_KNIGHT,  30 },
    { "Brigand",    CLASS_BRIGAND,       30 },
    { "Archer",     CLASS_ARCHER,        36, .ratingPow = 6, .ratingSup = 12, .rangeBon = +1, .rangeBonPow = +2, .rangeBonSup = +3 },
    // { "Nomad",     CLASS_ARCHER,        36, .ratingPow = 6, .ratingSup = 12, .rangeBon = +1, .rangeBonPow = +2, .rangeBonSup = +3 }, // todo: add nomad/nomad trpr eventually 
    { "Fighter",    CLASS_FIGHTER,       30 },
    { "Mercenary",  CLASS_MERCENARY,     30 },
    { "Cavalier",   CLASS_CAVALIER,      30 },
    { "Monk",       CLASS_MONK,          30 },
    { "Mage",       CLASS_MAGE,          30 },
    { "Shaman",     CLASS_SHAMAN,        30 },
    { "Cleric",     CLASS_CLERIC,        30 },
    { "Thief",      CLASS_THIEF,         30 },
    { "Pegasus Kn.",   CLASS_PEGASUS_KNIGHT,      30 },
    { "Wyvern Rider",  CLASS_WYVERN_RIDER,      30 },
};

/* Francis is a soldier specialist, with weak magic units. */
static const struct CoClassAffinity sFrancisAffinities[] = {
    { "Soldier",    CLASS_SOLDIER,       36, .ratingPow = 3, .ratingSup = 6, .movBon = +1, .movBonPow = +2, .movBonSup = +3 },
    { "Knight",     CLASS_ARMOR_KNIGHT,  36, .ratingPow = 3, .ratingSup = 6, .movBon = +1, .movBonPow = +2, .movBonSup = +3 },
    { "Brigand",    CLASS_BRIGAND,       30 },
    { "Archer",     CLASS_ARCHER,        30 },
    { "Fighter",    CLASS_FIGHTER,       30 },
    { "Mercenary",  CLASS_MERCENARY,     30 },
    { "Cavalier",   CLASS_CAVALIER,      39, .ratingPow = 3, .ratingSup = 6, .movBon = +1, .movBonPow = +2, .movBonSup = +3 },
    { "Monk",       CLASS_MONK,          24 },
    { "Mage",       CLASS_MAGE,          24 },
    { "Shaman",     CLASS_SHAMAN,        24 },
    { "Cleric",     CLASS_CLERIC,        24 },
    { "Thief",      CLASS_THIEF,         30 },
    { "Pegasus Kn.",   CLASS_PEGASUS_KNIGHT,      30 },
    { "Wyvern Rider",  CLASS_WYVERN_RIDER,      33 },
};

/* Kargan is an axe specialist, but weak with anything magical. */
static const struct CoClassAffinity sKarganAffinities[] = {
    { "Soldier",    CLASS_SOLDIER,       30, .ratingPow = 3, .ratingSup = 6 },
    { "Knight",     CLASS_ARMOR_KNIGHT,  30, .ratingPow = 3, .ratingSup = 6 },
    { "Brigand",    CLASS_BRIGAND,       42, .ratingPow = 3, .ratingSup = 6, .movBon = +1 },
    { "Archer",     CLASS_ARCHER,        24, .ratingPow = 3, .ratingSup = 6 },
    { "Fighter",    CLASS_FIGHTER,       45, .ratingPow = 3, .ratingSup = 6, .movBon = +1 },
    { "Mercenary",  CLASS_MERCENARY,     24, .ratingPow = 3, .ratingSup = 6 },
    { "Cavalier",   CLASS_CAVALIER,      30, .ratingPow = 3, .ratingSup = 6 },
    { "Monk",       CLASS_MONK,          24, .ratingPow = 3, .ratingSup = 6, .rangeBon = -1 },
    { "Mage",       CLASS_MAGE,          24, .ratingPow = 3, .ratingSup = 6, .rangeBon = -1 },
    { "Shaman",     CLASS_SHAMAN,        24, .ratingPow = 3, .ratingSup = 6, .rangeBon = -1 },
    { "Cleric",     CLASS_CLERIC,        24 },
    { "Thief",      CLASS_THIEF,         27, .ratingPow = 3, .ratingSup = 6 },
    { "Pegasus Kn.",   CLASS_PEGASUS_KNIGHT,      27 },
    { "Wyvern Rider",  CLASS_WYVERN_RIDER,      30 },
};


static const struct CoDefinition sCoDefinitions[CO_COUNT] = {
    
    [CO_WAKWI] = {
        .nameMsg = MSG_CO_WAKWI_NAME,
        .faceId = 2,
        .titleMsg = MSG_CO_WAKWI_TITLE,
        .infoMsg = MSG_CO_WAKWI_INFO,
        .powerNameMsg = MSG_CO_WAKWI_POWER_NAME,
        .powerDescMsg = MSG_CO_WAKWI_POWER_DESC,
        .superPowerNameMsg = MSG_CO_WAKWI_SUPER_NAME,
        .superPowerDescMsg = MSG_CO_WAKWI_SUPER_DESC,
        .powerStars = 2,
        .superPowerStars = 6,
        .powerTargetGroup = CO_POWER_TARGET_ALL,
        .superPowerTargetGroup = CO_POWER_TARGET_ALL,
        .affinities = sWakwiAffinities,
        .affinityCount = ARRAY_COUNT(sIshkodeAffinities),
    },
    [CO_ISHKODE] = {
        .nameMsg = MSG_CO_ISHKODE_NAME,
        .faceId = 4,
        .titleMsg = MSG_CO_ISHKODE_TITLE,
        .infoMsg = MSG_CO_ISHKODE_INFO,
        .powerNameMsg = MSG_CO_ISHKODE_POWER_NAME,
        .powerDescMsg = MSG_CO_ISHKODE_POWER_DESC,
        .superPowerNameMsg = MSG_CO_ISHKODE_SUPER_NAME,
        .superPowerDescMsg = MSG_CO_ISHKODE_SUPER_DESC,
        .powerStars = 3,
        .superPowerStars = 5,
        .powerTargetGroup = CO_POWER_TARGET_ALL,
        .superPowerTargetGroup = CO_POWER_TARGET_ALL,
        .affinities = sIshkodeAffinities,
        .affinityCount = ARRAY_COUNT(sIshkodeAffinities),
    },
    [CO_FRANCIS] = {
        .nameMsg = MSG_CO_FRANCIS_NAME,
        .faceId = 4,
        .titleMsg = MSG_CO_FRANCIS_TITLE,
        .infoMsg = MSG_CO_FRANCIS_INFO,
        .powerNameMsg = MSG_CO_FRANCIS_POWER_NAME,
        .powerDescMsg = MSG_CO_FRANCIS_POWER_DESC,
        .superPowerNameMsg = MSG_CO_FRANCIS_SUPER_NAME,
        .superPowerDescMsg = MSG_CO_FRANCIS_SUPER_DESC,
        .powerStars = 3,
        .superPowerStars = 5,
        .powerTargetGroup = CO_POWER_TARGET_POSITIVE_NEUTRAL,
        .superPowerTargetGroup = CO_POWER_TARGET_POSITIVE_NEUTRAL,
        .affinities = sFrancisAffinities,
        .affinityCount = ARRAY_COUNT(sFrancisAffinities),
    },
    [CO_KARGAN] = {
        .nameMsg = MSG_CO_KARGAN_NAME,
        .faceId = 0x30,
        .titleMsg = MSG_CO_KARGAN_TITLE,
        .infoMsg = MSG_CO_KARGAN_INFO,
        .powerNameMsg = MSG_CO_KARGAN_POWER_NAME,
        .powerDescMsg = MSG_CO_KARGAN_POWER_DESC,
        .superPowerNameMsg = MSG_CO_KARGAN_SUPER_NAME,
        .superPowerDescMsg = MSG_CO_KARGAN_SUPER_DESC,
        .powerStars = 2,
        .superPowerStars = 4,
        .powerTargetGroup = CO_POWER_TARGET_ALL,
        .superPowerTargetGroup = CO_POWER_TARGET_ALL,
        .affinities = sKarganAffinities,
        .affinityCount = ARRAY_COUNT(sKarganAffinities),
    },
};

struct CoScreenSt {
    u8 coId;
    u16 bgFogX; // BG3 fog scroll, see CoScreen_UpdateBgScroll (ported from SaveDraw_ScrollFogBG)
    u16 bgFogY;
};

/* Group 0 -- shared/aliased with gStatScreen, gUiTmScratchA/B/C
 * (src/statscreen.c) and other group-0 EWRAM_OVERLAY users. Safe: the CO
 * screen and the unit stat screen can never be open at the same time. */
EWRAM_OVERLAY(0) struct CoScreenSt gCoScreen = {};

/* True only during CoCommanderFade_* (Up/Down brightness fade), never
 * during a page slide -- lets CoScreen_DrawAffinitySprites tell the two
 * transitions apart (see its comment). */
static bool8 sCoCommanderFading = FALSE;

static const struct CoDefinition* GetCoDefinition(int coId)
{
    if (coId < 0 || coId >= CO_COUNT)
        coId = CO_ISHKODE;

    return &sCoDefinitions[coId];
}

/* A class with no explicit struct CoClassAffinity entry for this CO is
 * neutral -- same default the affinity page's bars use (they draw
 * entirely yellow, no green/red overlay, for anything at exactly
 * CO_AFFINITY_NEUTRAL_RATING, see DrawCoInfoBar). */
static int GetClassAffinityRating(const struct CoDefinition* co, int classId)
{
    int i;

    for (i = 0; i < co->affinityCount; ++i) {
        if (co->affinities[i].classId == classId)
            return co->affinities[i].rating;
    }

    return CO_AFFINITY_NEUTRAL_RATING;
}

/* rating, plus ratingPow/ratingSup on top if coId's power/super is
 * currently active for whichever faction it commands (see
 * GetCoActivePowerStateForCo) -- used by AdjustStatForCo's stat scaling
 * below. CoPower_AppliesToClass's own targeting check deliberately keeps
 * using GetClassAffinityRating's plain base rating instead of this:
 * which classes a power targets shouldn't shift just because the power
 * itself is the thing that's now active. */
static int GetEffectiveClassAffinityRating(const struct CoDefinition* co, int coId, int classId)
{
    int i;

    for (i = 0; i < co->affinityCount; ++i) {
        if (co->affinities[i].classId == classId) {
            int rating = co->affinities[i].rating;

            switch (GetCoActivePowerStateForCo(coId)) {
            case CO_POWER_STATE_NORMAL:
                rating += co->affinities[i].ratingPow;
                break;

            case CO_POWER_STATE_SUPER:
                rating += co->affinities[i].ratingSup;
                break;
            }

            return rating;
        }
    }

    return CO_AFFINITY_NEUTRAL_RATING;
}

/* See declaration comment (include/power.h) -- returns the delta to add to
 * baseValue, not the adjusted total. */
int AdjustStatForCo(int coId, int classId, int baseValue)
{
    const struct CoDefinition* co = GetCoDefinition(coId);
    int rating = GetEffectiveClassAffinityRating(co, coId, classId);
    int adjusted;

    if (rating == CO_AFFINITY_NEUTRAL_RATING)
        return 0;

    adjusted = (baseValue * rating + CO_AFFINITY_NEUTRAL_RATING / 2) / CO_AFFINITY_NEUTRAL_RATING;

    // Proportional scaling can round to no change (e.g. small base values) --
    // a non-neutral affinity must still move the stat by at least 1 point.
    if (adjusted == baseValue)
        adjusted += (rating > CO_AFFINITY_NEUTRAL_RATING) ? 1 : -1;

    if (adjusted < 0)
        adjusted = 0;

    return adjusted - baseValue;
}

/* See declaration comment (include/power.h). movBonPow/movBonSup REPLACE
 * movBon while coId's power/super is active (unlike rating above, which
 * ratingPow/ratingSup add on top of) -- a flat movement shift doesn't have
 * a sensible "stack the two" reading the way a proportional stat bonus
 * does. */
int GetCoClassMovBonus(int coId, int classId)
{
    const struct CoDefinition* co = GetCoDefinition(coId);
    int i;

    for (i = 0; i < co->affinityCount; ++i) {
        if (co->affinities[i].classId == classId) {
            switch (GetCoActivePowerStateForCo(coId)) {
            case CO_POWER_STATE_NORMAL:
                return co->affinities[i].movBonPow;

            case CO_POWER_STATE_SUPER:
                return co->affinities[i].movBonSup;

            default:
                return co->affinities[i].movBon;
            }
        }
    }

    return 0;
}

#if FE8_RANGE_REWORK
/* See declaration comment (include/power.h). rangeBonPow/rangeBonSup
 * REPLACE rangeBon while active, same as GetCoClassMovBonus's movBon. */
int GetCoClassRangeBonus(int coId, int classId)
{
    const struct CoDefinition* co = GetCoDefinition(coId);
    int i;

    for (i = 0; i < co->affinityCount; ++i) {
        if (co->affinities[i].classId == classId) {
            switch (GetCoActivePowerStateForCo(coId)) {
            case CO_POWER_STATE_NORMAL:
                return co->affinities[i].rangeBonPow;

            case CO_POWER_STATE_SUPER:
                return co->affinities[i].rangeBonSup;

            default:
                return co->affinities[i].rangeBon;
            }
        }
    }

    return 0;
}
#endif

/* See declaration comment (include/power.h). critBonPow/critBonSup
 * REPLACE critBon while active, same as GetCoClassMovBonus's movBon --
 * applied in src/bmbattle.c's ComputeBattleUnitCritRate. */
int GetCoClassCritBonus(int coId, int classId)
{
    const struct CoDefinition* co = GetCoDefinition(coId);
    int i;

    for (i = 0; i < co->affinityCount; ++i) {
        if (co->affinities[i].classId == classId) {
            switch (GetCoActivePowerStateForCo(coId)) {
            case CO_POWER_STATE_NORMAL:
                return co->affinities[i].critBonPow;

            case CO_POWER_STATE_SUPER:
                return co->affinities[i].critBonSup;

            default:
                return co->affinities[i].critBon;
            }
        }
    }

    return 0;
}

/* Does coId's power (or its super, if isSuper) affect a unit of classId?
 * Checked once per surveyed unit by CoPowers_Anim to decide whether that
 * unit gets CoPower_ApplyEffect and the barrier animation, or is skipped
 * silently -- see gProcScr_CoPowers below. */
static bool8 CoPower_AppliesToClass(int coId, bool8 isSuper, int classId)
{
    const struct CoDefinition* co = GetCoDefinition(coId);
    int rating = GetClassAffinityRating(co, classId);
    int group = isSuper ? co->superPowerTargetGroup : co->powerTargetGroup;

    switch (group) {
    case CO_POWER_TARGET_POSITIVE:
        return rating > CO_AFFINITY_NEUTRAL_RATING;

    case CO_POWER_TARGET_POSITIVE_NEUTRAL:
        return rating >= CO_AFFINITY_NEUTRAL_RATING;

    case CO_POWER_TARGET_NEGATIVE:
        return rating < CO_AFFINITY_NEUTRAL_RATING;

    case CO_POWER_TARGET_NEGATIVE_NEUTRAL:
        return rating <= CO_AFFINITY_NEUTRAL_RATING;

    case CO_POWER_TARGET_NEGATIVE_POSITIVE:
        return rating != CO_AFFINITY_NEUTRAL_RATING;

    case CO_POWER_TARGET_ALL:
    default:
        return TRUE;
    }
}

/* Amount Francis' power heals a matching unit for; his super heals them
 * to full instead (see CoPower_ApplyEffect). */
#define CO_FRANCIS_POWER_HEAL_AMOUNT 10

/* The actual effect a CO's power/super has on a unit CoPower_AppliesToClass
 * has already said it targets. Only Francis has one implemented so far --
 * everyone else is a no-op, leaving the roll-call/barrier animation as the
 * only visible effect (see CoPower_ApplyEffect's caller, CoPowers_Anim). */
static void CoPower_ApplyEffect(int coId, bool8 isSuper, struct Unit* unit)
{
    switch (coId) {
    case CO_FRANCIS:
        if (isSuper) {
            unit->curHP = GetUnitMaxHp(unit);
        } else {
            unit->curHP += CO_FRANCIS_POWER_HEAL_AMOUNT;

            if (unit->curHP > GetUnitMaxHp(unit))
                unit->curHP = GetUnitMaxHp(unit);
        }
        break;

    default:
        break;
    }
}

int CoScreen_GetCoCount(void)
{
    return CO_COUNT;
}

#ifndef SCROLL_ALL_COS
/* Is coId the commander of any faction right now? gPlaySt.commanderId[]
 * has one entry per faction (Blue/Green/Red/Purple, see include/types.h),
 * same array CoGauge_Get/aw2_gfx.c's mini gauge read. */
static bool8 IsCoInUse(int coId)
{
    int i;

    for (i = 0; i < 4; ++i) {
        if (gPlaySt.commanderId[i] == coId)
            return TRUE;
    }

    return FALSE;
}

/* Steps coId by direction (+1/-1), wrapping through CoScreen_GetCoCount(),
 * until landing on one IsCoInUse says a faction is actually using. If none
 * are (shouldn't happen outside of a debug/test setup with commanderId
 * left unset), this just walks all the way around back to the original
 * coId rather than looping forever. */
static int FindNextUsedCoId(int coId, int direction)
{
    int count = CoScreen_GetCoCount();
    int i;

    for (i = 0; i < count; ++i) {
        coId = (coId + direction + count) % count;

        if (IsCoInUse(coId))
            return coId;
    }

    return coId;
}
#endif

const char* CoScreen_GetCoName(int coId)
{
    return GetStringFromIndex(GetCoDefinition(coId)->nameMsg);
}

int CoScreen_GetCoPowerStars(int coId)
{
    return GetCoDefinition(coId)->powerStars;
}

int CoScreen_GetCoSuperPowerStars(int coId)
{
    const struct CoDefinition* co = GetCoDefinition(coId);

    /* The super is a top-up of the normal power's charge, never cheaper
     * than it -- a table typo the other way round would otherwise make
     * the gauge draw a negative number of big stars. */
    if (co->superPowerStars < co->powerStars)
        return co->powerStars;

    return co->superPowerStars;
}

#define CO_GAUGE_MAX 9999

void CoGauge_OnDamage(int faction, int amount)
{
    int slot = faction >> 6;
    int value;

    if (slot < 0 || slot >= 4 || amount <= 0)
        return;

    value = gPlaySt.coGauge[slot] + amount;

    if (value > CO_GAUGE_MAX)
        value = CO_GAUGE_MAX;

    gPlaySt.coGauge[slot] = value;
}

s16 CoGauge_Get(int faction)
{
    int slot = faction >> 6;

    if (slot < 0 || slot >= 4)
        return 0;

    return gPlaySt.coGauge[slot];
}

void CoGauge_Set(int faction, s16 value)
{
    int slot = faction >> 6;

    if (slot < 0 || slot >= 4)
        return;

    if (value < 0)
        value = 0;
    else if (value > CO_GAUGE_MAX)
        value = CO_GAUGE_MAX;

    gPlaySt.coGauge[slot] = value;
}

void CoGauge_OnPowerUsed(int faction)
{
    CoGauge_Set(faction, 0);
}

void SetFactionCo(int faction, int coId)
{
    int slot = faction >> 6;

    if (slot < 0 || slot >= 4)
        return;

    if (coId < 0 || coId >= CO_COUNT)
        return;

    gPlaySt.commanderId[slot] = coId;
}

/* Called from AiPhaseInit (src/cp_phase.c) at the start of each AI-
 * controlled phase (FACTION_RED/FACTION_GREEN), before that faction's own
 * turn actions (Proc_StartBlocking(gProcScr_CpOrder, ...)) begin. Mirrors
 * the player's own CoPowersMenuCommandCommon, but the AI decides *whether*
 * to use a power for itself, on gauge fullness alone:
 *   - super power, if the gauge has reached (or passed) superPowerStars
 *     worth of half-stars -- "full stars".
 *   - regular power, but only if the gauge is sitting at exactly
 *     powerStars worth of half-stars -- once it's a half star or more
 *     past that (and still short of the super), the AI holds out for the
 *     super instead of spending early.
 *   - otherwise, no power is used this phase.
 * parent is AiPhaseInit's own proc, so the roll-call/effect proc
 * (gProcScr_CoPowers) runs to completion -- including its camera return --
 * before the caller's own AI turn logic starts. */
int CoPowers_OnAiPhaseStart(struct Proc* parent)
{
    int faction = gPlaySt.faction;
    int coId = gPlaySt.commanderId[faction >> 6];
    const struct CoDefinition* co = GetCoDefinition(coId);
    int halfStars = CoGauge_Get(faction) / (CO_GAUGE_PER_STAR / 2);
    bool8 isSuper;
    struct CoPowersProc* proc;

    if (halfStars >= co->superPowerStars * 2)
        isSuper = TRUE;
    else if (halfStars == co->powerStars * 2)
        isSuper = FALSE;
    else
        return 1;

    CoGauge_OnPowerUsed(faction);
    sCoActivePowerState[faction >> 6] = isSuper ? CO_POWER_STATE_SUPER : CO_POWER_STATE_NORMAL;

    proc = (struct CoPowersProc*)Proc_StartBlocking(gProcScr_CoPowers, parent);
    proc->faction = faction;
    proc->isSuper = isSuper;
    return 0; // yield
}

/* gStatScreen.text[] slots this screen borrows (see the EWRAM_OVERLAY(0)
 * comment on gCoScreen above -- safe since this screen and the unit stat
 * screen never run at the same time). Every simultaneously-visible string
 * needs its OWN slot/handle: LINE0-3 used to share one CO_TEXT_LINE1
 * handle across up to 3 lines at once, which meant they all pointed at the
 * same VRAM glyph range -- whichever line drew last would visually bleed
 * into the others. See memory: feedback_text_add_workflow. */
enum {
    CO_TEXT_HEADER,
    CO_TEXT_LABEL,
    CO_TEXT_SUBTITLE,
    CO_TEXT_LINE0,
    CO_TEXT_LINE1,
    CO_TEXT_LINE2,
    CO_TEXT_LINE3,
    CO_TEXT_LINE4,
    CO_TEXT_LINE5,
    CO_TEXT_LINE6,
    CO_TEXT_COUNT,
};

/* Fixed tileWidth per the text-adding schema (memory:
 * feedback_text_add_workflow): short labels/names get 10 tiles, full
 * description lines get 20. Never size a Text handle from
 * GetStringTextLen(str) -- that recomputes a *different* width every
 * redraw depending on what string happens to be current, which shifts
 * where neighboring handles' VRAM ranges start and corrupts them. */
#define CO_TEXT_WIDTH_SHORT 10
#define CO_TEXT_WIDTH_LINE 20

/* Class-affinity row layout (page 4): local tile y of the first row and
 * the spacing between rows, in the gUiTmScratchA/C page-region coordinate
 * space CoScreen_DrawPageAffinity uses for the stat bars. The class SMS
 * icons are OBJ sprites instead (see CoScreen_DrawAffinitySprites), drawn
 * in real screen pixel coordinates every frame -- sprites aren't part of
 * the BG tile scratch buffers, same as how the page-number arrows/mu
 * platform are also plain OBJ sprites unaffected by the page slide. */
#define CO_TEXT_Y 1
#define CO_AFFINITY_ROW_Y0 (CO_TEXT_Y+1)
#define CO_AFFINITY_ROW_STEP 2
#define CO_AFFINITY_ICON_TILE_X (CO_PAGE_X + 1)
#define CO_AFFINITY_BAR_TILE_X 6

#if FE8_AW2_ASSETS
/* Class movement/range bonus icons (struct CoClassAffinity's movBon/
 * rangeBon -- e.g. CO_ISHKODE's sIshkodeAffinities below), drawn on the
 * one free tile row between one class's affinity bar (row
 * CO_AFFINITY_ROW_Y0 + i*CO_AFFINITY_ROW_STEP + 1, see DrawCoInfoBar) and
 * the next class's row -- i.e. +2 from the bar-drawing loop's own
 * (pre-increment) y, directly below that bar without touching the next
 * entry's row. gGfx_CoAffinityBonusIcons_tiles (src/data/data_aw2.c),
 * dumped from C:\devkitPro\feex\aw2dmp\new -- see graphics/aw2/
 * gGfx_CoAffinityBonusIcons.png for the source and CoScreen_Setup for
 * where this gets decompressed/palette-applied.
 *
 * VRAM placement: BG0/BG1 share char base 0x0000 (see CoScreen_Setup's
 * bgConfig) with the common UI-frame sheet (128 tiles) and, further up,
 * CoScreen_DrawHeader's face graphic at tile 0x280 (~90 tiles, ending
 * ~0x2DA) -- this sheet's 7 tiles start right after that, at 0x2E0, well
 * clear of BG0's own map data at byte 0x6000 (tile index 0x300). Palette
 * bank 5 is otherwise unused anywhere else in this file. Both are a
 * judgment call made without being able to render this screen -- if
 * either turns out already claimed by something this file's other
 * Decompress/ApplyPalette calls didn't make obvious, adjust
 * CO_AFFINITY_BONUS_ICON_TILE_BASE/_PAL_SLOT below to a clear
 * region/bank. */
#define CO_AFFINITY_BONUS_ICON_TILE_BASE 0x220
#define CO_AFFINITY_BONUS_ICON_PAL_SLOT 5

enum {
    CO_BONUS_ICON_ARROW,  // range
    CO_BONUS_ICON_FOOT,   // movement
    CO_BONUS_ICON_PLUS,
    CO_BONUS_ICON_MINUS,
    CO_BONUS_ICON_DIGIT1,
    CO_BONUS_ICON_DIGIT2,
    CO_BONUS_ICON_DIGIT3,
};

extern const u8 gGfx_CoAffinityBonusIcons_tiles[];
extern const u16 gGfx_CoAffinityBonusIcons_palette[];

static void CoScreen_LoadAffinityBonusIcons(void)
{
    Decompress(gGfx_CoAffinityBonusIcons_tiles,
        (void*)(VRAM + GetBackgroundTileDataOffset(0) + CO_AFFINITY_BONUS_ICON_TILE_BASE * 0x20));
    ApplyPalette(gGfx_CoAffinityBonusIcons_palette, CO_AFFINITY_BONUS_ICON_PAL_SLOT);
}

/* Draws [type icon][sign icon][magnitude digit] at (x, y) in the
 * gUiTmScratchA page-region coordinate space (same space DrawCoInfoBar's
 * bars use). movBon takes priority if a class somehow has both set (no
 * current CO does) -- only one row is free per class without further
 * restructuring CO_AFFINITY_ROW_STEP, so only one bonus type can be shown
 * per class for now. Draws nothing if both are 0. */
static void CoScreen_DrawAffinityBonusIcon(int x, int y, const struct CoClassAffinity* affinity)
{
    int bon;
    int typeIcon;
    int signIcon;
    int digitIcon;

    if (affinity->movBon != 0) {
        bon = affinity->movBon;
        typeIcon = CO_BONUS_ICON_FOOT;
    } else if (affinity->rangeBon != 0) {
        bon = affinity->rangeBon;
        typeIcon = CO_BONUS_ICON_ARROW;
    } else {
        return;
    }

    signIcon = (bon > 0) ? CO_BONUS_ICON_PLUS : CO_BONUS_ICON_MINUS;
    digitIcon = CO_BONUS_ICON_DIGIT1 + (ABS(bon) - 1); // 1/2/3 -> DIGIT1/2/3

    gUiTmScratchA[TILEMAP_INDEX(x + 1, y)] = TILEREF(CO_AFFINITY_BONUS_ICON_TILE_BASE + typeIcon, CO_AFFINITY_BONUS_ICON_PAL_SLOT);
    gUiTmScratchA[TILEMAP_INDEX(x + 2, y)] = TILEREF(CO_AFFINITY_BONUS_ICON_TILE_BASE + signIcon, CO_AFFINITY_BONUS_ICON_PAL_SLOT);
    gUiTmScratchA[TILEMAP_INDEX(x + 3, y)] = TILEREF(CO_AFFINITY_BONUS_ICON_TILE_BASE + digitIcon, CO_AFFINITY_BONUS_ICON_PAL_SLOT);
}
#endif // FE8_AW2_ASSETS

/* Page-content area, same footprint statscreen.c's own page region uses
 * (see gUiTmScratchA/C, sized exactly for an 18x18 area) -- screen tile
 * (CO_PAGE_X, CO_PAGE_Y) is scratch-buffer-local (0, 0). Sits on the LEFT
 * side of the screen; the portrait sits on the right (see CO_PORTRAIT_X
 * below), outside this rect entirely, which is why the header survives
 * page/commander slides untouched, exactly like statscreen.c's own left
 * panel survives its (mirror-image, portrait-on-the-left) page slides. */
#define CO_PAGE_X 0
#define CO_PAGE_Y 0
#define CO_PAGE_W 18
#define CO_PAGE_H 20

/* Portrait + name, right of the page-content area (see CO_PAGE_X/_W). */
#define CO_PORTRAIT_X (CO_PAGE_X + CO_PAGE_W+1)



/* Text-adding schema (memory: feedback_text_add_workflow), steps 4-9 per
 * string: (4) InitText with a fixed tileWidth (also clears the handle);
 * (6) Text_SetParams for x-offset/color; (7) Text_DrawString the string,
 * fetched only via GetStringFromIndex, never a raw literal; (8)
 * TileMap_FillRect to erase the destination tiles the string will land
 * on; (9) PutText to place it. Steps 1-2 (texts.txt entry +
 * GetStringFromIndex) are satisfied by every caller passing a MSG_ id.
 * Step 3 (InitSystemTextFont/ResetText) happens once in CoScreen_Setup,
 * not per string. */
static void CoScreen_PutText(int slot, u16* tm, int tileWidth, int color, int msgId)
{
    struct Text* text = &gStatScreen.text[slot];

    InitText(text, tileWidth);
    Text_SetParams(text, 0, color);
    Text_DrawString(text, GetStringFromIndex(msgId));
    TileMap_FillRect(tm, tileWidth, 2, 0);
    PutText(text, tm);
}

/* Vanilla's own answer to "how do you draw a multi-line string": ONE
 * texts.txt entry holds the whole block with [LF] separating lines (not
 * one entry per line) -- Text_DrawString/Text_DrawStringASCII
 * (src/fontgrp.c) stop at the first [LF] they hit, and PutText only ever
 * places a single row, so a multi-line source string still needs one
 * struct Text handle per line. PrintStringToTexts (src/scene.c, used by
 * the dialogue box) is the vanilla helper that reconciles the two: it
 * walks the single source string, and on each [LF] PutTexts whatever
 * accumulated in the current line's handle before moving to the next
 * handle in the array. tm here is line 0's destination; PrintStringToTexts
 * advances by a tilemap row pair (0x40) per line internally. */
 #define MULTILINE_MAX 7 
static void CoScreen_PutMultilineText(u16* tm, int color, int msgId)
{
    struct Text* texts[MULTILINE_MAX];
    int i;

    for (i = 0; i < MULTILINE_MAX; ++i) {
        struct Text* text = &gStatScreen.text[CO_TEXT_LINE0 + i];

        InitText(text, CO_TEXT_WIDTH_LINE);
        Text_SetParams(text, 0, color);
        texts[i] = text;
    }

    TileMap_FillRect(tm, CO_TEXT_WIDTH_LINE, MULTILINE_MAX * 2, 0);

    PrintStringToTexts(texts, GetStringFromIndex(msgId), tm, MULTILINE_MAX);
}

static void CoScreen_DrawHeader(void)
{
    const struct CoDefinition* co = GetCoDefinition(gCoScreen.coId);
    int fid = co->faceId;

    PutFace80x72(NULL, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PORTRAIT_X, 1), fid, 0x280, 11);

    if (GetPortraitData(fid)->img)
        ApplyPalette(Pal_FaceDisplayPortrait, 2);
    else
        ApplyPalette(Pal_FaceDisplayGenericCard, 2);

    EnablePaletteSync();
    CoScreen_PutText(CO_TEXT_HEADER, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PORTRAIT_X + 2, 10),
        CO_TEXT_WIDTH_SHORT, TEXT_COLOR_SYSTEM_WHITE, co->nameMsg); // CoScreen_GetCoName
}

/* Everything below draws into the gUiTmScratchA/C page-region scratch
 * buffers (statscreen.c) at coordinates local to that 18x18 region, not
 * the real screen -- CoScreen_DrawPage/CoPageSlide_OnLoop below copy the
 * finished scratch content onto the real BG0/BG2 at (CO_PAGE_X, CO_PAGE_Y),
 * same two-buffer approach DisplayPage0/1/2 + PageSlide_OnLoop use. */

static void CoScreen_DrawPageInfo(const struct CoDefinition* co)
{
    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(1, CO_TEXT_Y), CO_TEXT_WIDTH_SHORT, TEXT_COLOR_SYSTEM_GOLD, MSG_CO_LABEL_INFO);
    CoScreen_PutText(CO_TEXT_SUBTITLE, gUiTmScratchA + TILEMAP_INDEX(1, CO_TEXT_Y+2), CO_TEXT_WIDTH_LINE, TEXT_COLOR_SYSTEM_BLUE, co->titleMsg);
    CoScreen_PutMultilineText(gUiTmScratchA + TILEMAP_INDEX(1, CO_TEXT_Y+4), TEXT_COLOR_SYSTEM_WHITE, co->infoMsg);
}

static void CoScreen_DrawPagePower(const struct CoDefinition* co)
{
    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(1, CO_TEXT_Y), CO_TEXT_WIDTH_SHORT, TEXT_COLOR_SYSTEM_GOLD, MSG_CO_LABEL_POWER);
    CoScreen_PutText(CO_TEXT_SUBTITLE, gUiTmScratchA + TILEMAP_INDEX(1, CO_TEXT_Y+2), CO_TEXT_WIDTH_LINE, TEXT_COLOR_SYSTEM_BLUE, co->powerNameMsg);
    CoScreen_PutMultilineText(gUiTmScratchA + TILEMAP_INDEX(1, CO_TEXT_Y+4), TEXT_COLOR_SYSTEM_WHITE, co->powerDescMsg);
}

static void CoScreen_DrawPageSuper(const struct CoDefinition* co)
{
    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(1, CO_TEXT_Y), CO_TEXT_WIDTH_SHORT, TEXT_COLOR_SYSTEM_GOLD, MSG_CO_LABEL_SUPER);
    CoScreen_PutText(CO_TEXT_SUBTITLE, gUiTmScratchA + TILEMAP_INDEX(1, CO_TEXT_Y+2), CO_TEXT_WIDTH_LINE, TEXT_COLOR_SYSTEM_BLUE, co->superPowerNameMsg);
    CoScreen_PutMultilineText(gUiTmScratchA + TILEMAP_INDEX(1, CO_TEXT_Y+4), TEXT_COLOR_SYSTEM_WHITE, co->superPowerDescMsg);
}
#define BAR_VRAM_WIDTH 5
void DrawCoInfoBar(int num, int x, int y, int base, int total, int max)
{
    // PutNumberOrBlank(gUiTmScratchA + TILEMAP_INDEX(x, y),
        // (base == max) ? TEXT_COLOR_SYSTEM_GREEN : TEXT_COLOR_SYSTEM_BLUE, base);

    // PutNumberBonus(total - base, gUiTmScratchA + TILEMAP_INDEX(x + 1, y));

    // if (total > 30)
        // total = 30;

    /* The whole bar is filled yellow, then DrawStatBarGfxCo (src/statbar.c)
     * overlays green from the left (total above base) or red from the
     * right (total below base) to show how far off base total is. */
    DrawStatBarGfxCo(0x1C0 + num*BAR_VRAM_WIDTH, BAR_VRAM_WIDTH,
        gUiTmScratchA + TILEMAP_INDEX(x - 2, y + 1),
        TILEREF(0, STATSCREEN_BGPAL_6), max, total, base);
        // TILEREF(0, STATSCREEN_BGPAL_6), max * 41 / 30, total * 41 / 30, base * 41 / 30);
}
static void CoScreen_DrawPageAffinity(const struct CoDefinition* co)
{
    int i;
    int y = CO_AFFINITY_ROW_Y0;

    CoScreen_PutText(CO_TEXT_LABEL, gUiTmScratchA + TILEMAP_INDEX(2, CO_TEXT_Y), CO_TEXT_WIDTH_SHORT, TEXT_COLOR_SYSTEM_GOLD, MSG_CO_LABEL_AFFINITY);

    // pixels long. base in yellow. if total is higher, those pixels in green. if max, all green.
    /* GetEffectiveClassAffinityRating (not the plain co->affinities[].rating)
     * so this bar reflects ratingPow/ratingSup while gCoScreen.coId's power/
     * super happens to be active (browsing to a DIFFERENT CO than the one
     * with an active power still shows their own plain rating, same as
     * always -- the effective lookup is per-coId, not global). */
    for (i = 0; i < co->affinityCount && i < CO_AFFINITY_ROW_MAX; ++i) {
        DrawCoInfoBar(i, CO_AFFINITY_BAR_TILE_X, y, 30,
            GetEffectiveClassAffinityRating(co, gCoScreen.coId, co->affinities[i].classId), 30);
#if FE8_AW2_ASSETS
        CoScreen_DrawAffinityBonusIcon(CO_AFFINITY_BAR_TILE_X - 2, y + 2, &co->affinities[i]);
#endif
        y += CO_AFFINITY_ROW_STEP;
    }
    int offset = i;
    y = CO_AFFINITY_ROW_Y0;
    for (i = 0; i < co->affinityCount && i < CO_AFFINITY_ROW_MAX; ++i) {
        DrawCoInfoBar(i+offset, CO_AFFINITY_BAR_TILE_X+9, y, 30,
            GetEffectiveClassAffinityRating(co, gCoScreen.coId, co->affinities[i+offset].classId), 30);
#if FE8_AW2_ASSETS
        CoScreen_DrawAffinityBonusIcon(CO_AFFINITY_BAR_TILE_X + 9 - 2, y + 2, &co->affinities[i+offset]);
#endif
        y += CO_AFFINITY_ROW_STEP;
    }

}

/* Class SMS icons for the affinity page -- OBJ sprites, so they need
 * redrawing every frame (see gProcScr_CoPageNumCtrl below), not just once
 * like the tile-based bars above. */
static void CoScreen_DrawAffinitySprites(ProcPtr proc)
{
    const struct CoDefinition* co;
    int i;
    int y;

    if (gStatScreen.page != CO_SCREEN_PAGE_AFFINITY)
        return;

    /* Suppressed during a page slide (content underneath is shifting
     * position, and these sprites don't slide with it -- see the comment
     * above), but NOT during a commander fade: that's a pure brightness
     * blend over everything already on screen (SetBlendTargetA includes
     * the OBJ layer), so keeping these sprites drawn each frame during it
     * is what makes them fade along with the portrait instead of just
     * vanishing. */
    if (gStatScreen.inTransition && !sCoCommanderFading)
        return;

    co = GetCoDefinition(gCoScreen.coId);
    y = CO_AFFINITY_ROW_Y0+1;

    for (i = 0; i < co->affinityCount && i < CO_AFFINITY_ROW_MAX; ++i) {
        PutUnitSpriteForClassId(0,
            CO_AFFINITY_ICON_TILE_X * 8,
            (CO_PAGE_Y + y) * 8 + gStatScreen.yDispOff,
            0xC800,
            co->affinities[i].classId);

        y += CO_AFFINITY_ROW_STEP;
    }
    int offset = i; 
    y = CO_AFFINITY_ROW_Y0+1;

    for (i = 0; i < co->affinityCount && i < CO_AFFINITY_ROW_MAX; ++i) {
        PutUnitSpriteForClassId(0,
            (CO_AFFINITY_ICON_TILE_X+10) * 8 + gStatScreen.xDispOff,
            (CO_PAGE_Y + y) * 8 + gStatScreen.yDispOff,
            0xC800,
            co->affinities[i+offset].classId);

        y += CO_AFFINITY_ROW_STEP;
    }
    
    
    ForceSyncUnitSpriteSheet();
}

static void CoScreen_DrawPage(void)
{
    const struct CoDefinition* co = GetCoDefinition(gCoScreen.coId);

    ResetText();
    CoScreen_DrawHeader();

    CpuFastFill(0, gUiTmScratchA, sizeof(u16) * 0x280);
    CpuFastFill(0, gUiTmScratchB, sizeof(u16) * 0x280);

    switch (gStatScreen.page) {
    case CO_SCREEN_PAGE_INFO:
        CoScreen_DrawPageInfo(co);
        break;

    case CO_SCREEN_PAGE_POWER:
        CoScreen_DrawPagePower(co);
        break;

    case CO_SCREEN_PAGE_SUPER:
        CoScreen_DrawPageSuper(co);
        break;

    case CO_SCREEN_PAGE_AFFINITY:
        CoScreen_DrawPageAffinity(co);
        break;
    }
}

/* Page/commander transition slide -- a port of statscreen.c's
 * PageSlide_OnLoop/StartPageSlide (sPageSlideOffsetLut, gProcScr_SSPageSlide),
 * reusing the same gUiTmScratchA/C double-buffer approach and struct
 * StatScreenEffectProc, but redrawing via CoScreen_DrawHeader/DrawPage
 * instead of the unit-stat-screen-specific DisplayLeftPanel/DisplayPage
 * (those are hardwired to gStatScreen.unit, so can't be reused directly).
 * DPAD_LEFT/RIGHT move to the next page; DPAD_UP/DOWN move to the next
 * commander -- both drive this same slide, just updating gStatScreen.page
 * or gCoScreen.coId beforehand (see CoScreen_KeyListener). The header
 * (portrait+name) is cheap to redraw unconditionally on every slide, so
 * there's no need to special-case "page only" vs. "commander changed". */
static s8 CONST_DATA sCoPageSlideOffsetLut[] = {
    // transition page out
    -4, -7, -10, -12, -14,

    INT8_MAX, // draw new page

    // transition page in
    13, 9, 7, 5, 3, 2, 1, 0,

    INT8_MIN, // end
};

static void CoPageSlide_OnLoop(struct StatScreenEffectProc* proc)
{
    int off;
    int len, dstOff, srcOff;

    TileMap_FillRect(gBG0TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W-1, CO_PAGE_H, 0);
    TileMap_FillRect(gBG1TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W-1, CO_PAGE_H, 0);

    off = sCoPageSlideOffsetLut[proc->timer];

    if (off == INT8_MAX) {
        CoScreen_DrawPage();

        proc->timer++;
        off = sCoPageSlideOffsetLut[proc->timer];
    }

    if (proc->key & (DPAD_LEFT | DPAD_UP))
        off = -off;

    len = CO_PAGE_W - (off < 0 ? -off : off);

    if (off < 0) {
        dstOff = 0;
        srcOff = -off;
    } else {
        dstOff = off;
        srcOff = 0;
    }

    TileMap_CopyRect(
        gUiTmScratchA + srcOff,
        gBG0TilemapBuffer + dstOff + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y),
        len, CO_PAGE_H);
        
    // TileMap_CopyRect(
        // gUiTmScratchB + srcOff,
        // gBG1TilemapBuffer + dstOff + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y),
        // len, CO_PAGE_H);

    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT);

    proc->timer++;
    off = sCoPageSlideOffsetLut[proc->timer];

    if (off == INT8_MIN)
        Proc_Break(proc);
}

static void CoPageSlide_OnEnd(struct StatScreenEffectProc* proc)
{
    gStatScreen.inTransition = FALSE;
}

CONST_DATA struct ProcCmd gProcScr_CoPageSlide[] = {
    PROC_REPEAT(CoPageSlide_OnLoop),
    PROC_CALL(CoPageSlide_OnEnd),

    PROC_END,
};

static void CoStartSlide(u16 key, struct Proc* parent)
{
    struct StatScreenEffectProc* proc;

    if (Proc_Find(gProcScr_CoPageSlide))
        return;

    PlaySoundEffect(SONG_6F);
    ResetUnitSpriteHover();

    proc = (void*)Proc_StartBlocking(gProcScr_CoPageSlide, parent);

    proc->timer = 0;
    proc->key = key;

    gStatScreen.pageSlideKey = key;
    gStatScreen.inTransition = TRUE;
}

/* Commander (Up/Down) transition -- ported from statscreen.c's
 * "unit slide" (UnitSlide_InitFadeOut/FadeOutLoop/InitFadeIn/FadeInLoop,
 * StartUnitSlide/gProcScr_SSUnitSlide), which is a *different* mechanism
 * from the page slide above: on a unit change, vanilla doesn't shift
 * tiles -- it fades the whole panel to black via the GBA's brightness
 * blend effect (SetBlendConfig effect 3), redraws everything at the
 * midpoint (UnitSlide_SetNewUnit calls StatScreen_Display fresh, which
 * includes the portrait), then fades back in. That's what makes the
 * portrait "slide": vanilla's version also drifts gStatScreen.mu (the
 * little walking map-sprite icon) up/down during the fade via
 * SetMuScreenPosition, but the CO screen has no equivalent on-map sprite
 * to move, so only the brightness fade is ported here -- the portrait and
 * page both redraw together at the blackout point, same as vanilla. */
static void CoCommanderFade_InitOut(struct StatScreenEffectProc* proc)
{
    gStatScreen.inTransition = TRUE;
    sCoCommanderFading = TRUE;

    proc->timer = 4;


    // gLCDControlBuffer.bg0cnt.priority = 2;
    // gLCDControlBuffer.bg1cnt.priority = 3;
    // gLCDControlBuffer.bg2cnt.priority = 0;
    // gLCDControlBuffer.bg3cnt.priority = 1;
    gLCDControlBuffer.bg0cnt.priority = 1;
    gLCDControlBuffer.bg1cnt.priority = 2;
    gLCDControlBuffer.bg2cnt.priority = 0;
    gLCDControlBuffer.bg3cnt.priority = 3;

    SetBlendTargetA(0, 0, 1, 0, 0);
    SetBlendTargetB(1, 1, 0, 0, 1);
    
    SetBlendBackdropB(0);

    /* Same vertical bounce as vanilla's UnitSlide_InitFadeOut: the panel
     * drifts off toward the direction the new commander is "coming from"
     * while it blends to black. proc->direction is set by
     * CoStartCommanderFade from whichever of DPAD_UP/DOWN triggered this. */
    if (proc->direction > 0) {
        proc->yDispInit  = 0;
        proc->yDispFinal = -60;
    } else {
        proc->yDispInit  = 0;
        proc->yDispFinal = +60;
    }
}

static void CoCommanderFade_OutLoop(struct StatScreenEffectProc* proc)
{
    SetBlendConfig(1, proc->timer, 0x10 - proc->timer, 0);

    gStatScreen.yDispOff = Interpolate(2, proc->yDispInit, proc->yDispFinal, proc->timer, 0x10);

    proc->timer += 3;

    if (proc->timer > 0x10) {
        Proc_Break(proc);
    }
}

static void CoCommanderFade_SetNewCo(struct StatScreenEffectProc* proc)
{
    CoScreen_DrawPage();

    TileMap_CopyRect(gUiTmScratchA, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);
    // TileMap_CopyRect(gUiTmScratchB, gBG1TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);
    // TileMap_CopyRect(gUiTmScratchC, gBG2TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);

    BG_EnableSyncByMask(BG0_SYNC_BIT);
    // BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT);
}

static void CoCommanderFade_InitIn(struct StatScreenEffectProc* proc)
{
    proc->timer = 1;
    gLCDControlBuffer.bg0cnt.priority = 1;
    gLCDControlBuffer.bg1cnt.priority = 2;
    gLCDControlBuffer.bg2cnt.priority = 0;
    gLCDControlBuffer.bg3cnt.priority = 3;

    SetBlendTargetA(0, 0, 1, 0, 0);
    SetBlendTargetB(1, 1, 0, 0, 1);
    /* New content bounces in from the opposite side it faded out toward. */
    if (proc->direction > 0) {
        proc->yDispInit  = +60;
        proc->yDispFinal = 0;
    } else {
        proc->yDispInit  = -60;
        proc->yDispFinal = 0;
    }
}

static void CoCommanderFade_InLoop(struct StatScreenEffectProc* proc)
{
    SetBlendConfig(1, 0x10 - proc->timer, proc->timer, 0);
    gStatScreen.yDispOff = Interpolate(5, proc->yDispInit, proc->yDispFinal, proc->timer, 0x10);

    // proc->timer -= 2;
    proc->timer += 3;

    // if (proc->timer <= 0) {
    if (proc->timer >= 0x10) {
        Proc_Break(proc);
        return;
    }

    // SetBlendConfig(3, 0, 0, proc->timer);
}
static void CoScreen_Setup(ProcPtr proc); 
void ClearCoSlide(struct Proc* proc)
{
    SetDefaultColorEffects();
    gLCDControlBuffer.bg0cnt.priority = 0;
    gLCDControlBuffer.bg1cnt.priority = 1;
    gLCDControlBuffer.bg2cnt.priority = 2;
    gLCDControlBuffer.bg3cnt.priority = 3;
    

    gStatScreen.yDispOff = 0;
    gStatScreen.inTransition = FALSE;
    sCoCommanderFading = FALSE;
    // SetBlendConfig(3, 0, 0, 0x10);
    SetBlendTargetA(0, 0, 1, 0, 0); // transparent ui
    SetBlendTargetB(0, 0, 0, 1, 0); // BG3, so BG2 blends against it 
    SetBlendBackdropA(1);
    SetBlendAlpha(13, 3);
    // CoScreen_Setup((void*)proc->proc_parent);

    
}
CONST_DATA struct ProcCmd gProcScr_CoCommanderFade[] = {
    /* Proc_Start runs the script synchronously up to its first blocking
     * command before returning, so without this sleep,
     * CoCommanderFade_InitOut would read proc->direction before
     * CoStartCommanderFade (below) gets a chance to set it -- same
     * leading PROC_SLEEP(0) vanilla's gProcScr_SSUnitSlide uses ahead of
     * UnitSlide_InitFadeOut for the same reason. */
    PROC_SLEEP(0),
    PROC_CALL(CoCommanderFade_InitOut),
    PROC_REPEAT(CoCommanderFade_OutLoop),
    PROC_CALL(CoCommanderFade_SetNewCo),
    PROC_CALL(CoCommanderFade_InitIn),
    PROC_REPEAT(CoCommanderFade_InLoop),
    PROC_CALL(ClearCoSlide),
    PROC_END,
};

static void CoStartCommanderFade(int direction, struct Proc* parent)
{
    struct StatScreenEffectProc* proc;

    if (Proc_Find(gProcScr_CoCommanderFade))
        return;

    PlaySoundEffect(SONG_C8);

    proc = (void*) Proc_StartBlocking(gProcScr_CoCommanderFade, parent);
    proc->direction = direction;
}

enum
{
    // Magical constants

    // Neutral left arrow position
    PAGENUM_LEFTARROW_X = 19,
    PAGENUM_LEFTARROW_Y = 138,

    // Neutral right arrow position
    PAGENUM_RIGHTARROW_X = 217,
    PAGENUM_RIGHTARROW_Y = 138,

    // initial arrow offset on select
    PAGENUM_SELECT_XOFF = 6,

    // arrow animation speeds
    PAGENUM_ANIMSPEED = 4,
    PAGENUM_SELECT_ANIMSPEED = 31,

    PAGENUM_DISPLAY_X = 180, // 215 
    PAGENUM_DISPLAY_Y = 141,

    // name animation scaling time
    PAGENAME_SCALE_TIME = 6,
};

void CoInfoCtrl_OnInit(struct StatScreenPageNameProc* proc)
{
    proc->xLeftCursor  = PAGENUM_LEFTARROW_X;
    proc->xRightCursor = PAGENUM_RIGHTARROW_X;

    proc->animTimerRight = 0;
    proc->animTimerLeft  = 0;

    proc->animSpeedRight = PAGENUM_ANIMSPEED;
    proc->animSpeedLeft = PAGENUM_ANIMSPEED;
}

void CoInfoCtrl_CheckSlide(struct StatScreenPageNameProc* proc)
{
    if (gStatScreen.pageSlideKey & DPAD_LEFT)
    {
        proc->animSpeedLeft = PAGENUM_SELECT_ANIMSPEED;
        proc->xLeftCursor = PAGENUM_LEFTARROW_X - PAGENUM_SELECT_XOFF;
    }

    if (gStatScreen.pageSlideKey & DPAD_RIGHT)
    {
        proc->animSpeedRight = PAGENUM_SELECT_ANIMSPEED;
        proc->xRightCursor = PAGENUM_RIGHTARROW_X + PAGENUM_SELECT_XOFF;
    }

    gStatScreen.pageSlideKey = 0;
}

void CoInfoCtrl_UpdateArrows(struct StatScreenPageNameProc* proc)
{
    int baseref = TILEREF(0x240, STATSCREEN_OBJPAL_4) + OAM2_LAYER(1);

    proc->animTimerLeft  += proc->animSpeedLeft;
    proc->animTimerRight += proc->animSpeedRight;

    if (proc->animSpeedLeft > PAGENUM_ANIMSPEED)
        proc->animSpeedLeft--;

    if (proc->animSpeedRight > PAGENUM_ANIMSPEED)
        proc->animSpeedRight--;

    if ((GetGameClock() % 4) == 0)
    {
        if (proc->xLeftCursor < PAGENUM_LEFTARROW_X)
            proc->xLeftCursor++;

        if (proc->xRightCursor > PAGENUM_RIGHTARROW_X)
            proc->xRightCursor--;
    }

    PutSprite(0,
        gStatScreen.xDispOff + proc->xLeftCursor,
        gStatScreen.yDispOff + PAGENUM_LEFTARROW_Y,
        gObject_8x16, baseref + 0x5A + (proc->animTimerLeft >> 5) % 6);

    PutSprite(0,
        gStatScreen.xDispOff + proc->xRightCursor,
        gStatScreen.yDispOff + PAGENUM_RIGHTARROW_Y,
        gObject_8x16_HFlipped, baseref + 0x5A + (proc->animTimerRight >> 5) % 6);
}

void CoInfoCtrl_UpdatePageNum(struct StatScreenPageNameProc* proc)
{
    int chr = 0x289;

    // page amt
    PutSprite(2,
        gStatScreen.xDispOff + PAGENUM_DISPLAY_X + 17,
        gStatScreen.yDispOff + PAGENUM_DISPLAY_Y,
        gObject_8x8, TILEREF(chr, STATSCREEN_OBJPAL_4) + OAM2_LAYER(2) + gStatScreen.pageAmt);

    // '/'
    PutSprite(2,
        gStatScreen.xDispOff + PAGENUM_DISPLAY_X + 9,
        gStatScreen.yDispOff + PAGENUM_DISPLAY_Y,
        gObject_8x8, TILEREF(chr, STATSCREEN_OBJPAL_4) + OAM2_LAYER(2));

    // page num
    PutSprite(2,
        gStatScreen.xDispOff + PAGENUM_DISPLAY_X,
        gStatScreen.yDispOff + PAGENUM_DISPLAY_Y,
        gObject_8x8, TILEREF(chr, STATSCREEN_OBJPAL_4) + OAM2_LAYER(2) + gStatScreen.page + 1);
}

static void CoScreen_UpdateBgScroll(ProcPtr proc);

CONST_DATA struct ProcCmd gProcScr_CoPageNumCtrl[] = {
    PROC_CALL(CoInfoCtrl_OnInit),

PROC_LABEL(0),
    PROC_SLEEP(0),

    PROC_CALL(CoInfoCtrl_CheckSlide),
    PROC_CALL(CoInfoCtrl_UpdateArrows),
    PROC_CALL(CoInfoCtrl_UpdatePageNum),
    // PROC_CALL(PageNumCtrl_DisplayMuPlatform),
    PROC_CALL(CoScreen_DrawAffinitySprites),
    PROC_CALL(CoScreen_UpdateBgScroll),

    PROC_GOTO(0),

    PROC_END,
};

/* Full 16-color bank for the CO stat bars (src/statbar.c's
 * DrawStatBarCo/DrawStatBarGfxCo). Was a single unreadable, comma-less
 * (and therefore non-compiling) line of raw bytes -- rewritten as one
 * RGB(r, g, b) entry per color (see include/gba/defines.h), decoded
 * little-endian pair by pair from the original bytes, with the original
 * raw u16 value kept as a comment for cross-reference. This bank's index
 * values are the raw 4bpp pixel values src/statbar.c's DrawStatBar*Col
 * helpers write into the bar bitmap: 3/4/14 border/shadow/unfilled
 * (DrawStatBarUnfilledCol/LeftBorder/RightBorder/Shadow), 1/5 yellow fill
 * (DrawStatBarFilledCol), 12/13 green "capped" fill (DrawStatBarCappedCol),
 * 10/11 red "minus" fill (DrawStatBarMinusCol). */
static const u16 NewUiBarPal[] = {
    RGB(19, 26, 25), // 0x6753
    RGB(29, 30, 31), // 0x7FDD
    RGB(23, 25, 27), // 0x6F37
    RGB(16, 17, 19), // 0x4E30
    RGB(10,  9,  8), // 0x212A
    RGB(30, 29, 14), // 0x3BBE
    RGB(23, 19,  6), // 0x1A77
    RGB(17, 13,  6), // 0x19B1
    RGB(31, 15,  4), // 0x11FF
    RGB( 2, 15, 31), // 0x7DE2
    RGB(31, 0, 31), // 0x76F5
    RGB(31, 0, 0), // 0x6238
    RGB( 3, 23,  2), // 0x0AE3
    RGB(15, 31, 18), // 0x4BEF
    RGB(10, 10, 22), // 0x594A
    RGB( 0,  0,  0), // 0x0000
};

void UnpackNewUiBarPalette(int palId)
{
    if (palId < 0)
        palId = STATSCREEN_BGPAL_6;

    ApplyPalette(NewUiBarPal, palId);
}


/* BG3 diagonally-scrolling background (ported from Pokemblem's
 * ChallengeRunMenu frlgUiFrame, see graphics/bg/frlgUiFrame.png and its
 * Makefile rule). frlgUiFrame_map is a flat, uncompressed 32x32 array of
 * bare tile indices (0-7, no palette/flip bits) -- built by hand here
 * rather than via CallARM_FillTileRect, since that decodes the engine's
 * compressed native TSA format (see memory: feedback_bgfill_offset_overflow),
 * which this plain array isn't. Sits behind everything else on screen
 * (lowest BG priority) and always fills the full 32x32-tile screen, so
 * BG_SetPosition's hardware wraparound scrolls it seamlessly. */
#define CO_BG_FRAME_PAL_SLOT 3
#define CO_BG_FRAME_TILE_WIDTH 32
#define CO_BG_FRAME_TILE_HEIGHT 32
#define CO_BG_FRAME_TILE_BYTE_OFFSET 0x4000
#define CO_BG_FRAME_TILE_INDEX_OFFSET (CO_BG_FRAME_TILE_BYTE_OFFSET / 0x20)
static void CoScreen_LoadBgFrame(void)
{
    int x, y;

    gLCDControlBuffer.bg3cnt.priority = 3;
    BG_SetColorBpp(3, 4);

    // Decompress(frlgUiFrame_tiles, (void*)(VRAM + GetBackgroundTileDataOffset(3) + CO_BG_FRAME_TILE_BYTE_OFFSET));
    // ApplyPalette(frlgUiFrame_palette, CO_BG_FRAME_PAL_SLOT);

    // for (y = 0; y < CO_BG_FRAME_TILE_HEIGHT; ++y) {
        // for (x = 0; x < CO_BG_FRAME_TILE_WIDTH; ++x) {
            // gBG3TilemapBuffer[TILEMAP_INDEX(x, y)] = (frlgUiFrame_map[y * CO_BG_FRAME_TILE_WIDTH + x] + CO_BG_FRAME_TILE_INDEX_OFFSET) | (CO_BG_FRAME_PAL_SLOT << 12);
        // }
    // }
    
    // ApplyPalette(Pal_MainMenuBgFog, BGPAL_SAVEMENU_BGFOG);
    // Decompress(Img_MainMenuBgFog, (void*)BG_VRAM + GetBackgroundTileDataOffset(BG_3) + BGCHR_SAVEMENU_BGFOG * TILE_SIZE_4BPP);
    // Decompress(Tsa_MainMenuBgFog, gGenericBuffer);
    // CallARM_FillTileRect(
        // gBG2TilemapBuffer,
        // gGenericBuffer,
        // OBJ_PALETTE(BGPAL_SAVEMENU_BGFOG) + OBJ_PRIORITY(0) + OBJ_CHAR(BGCHR_SAVEMENU_BGFOG));

    
    ApplyPalette(Pal_MainMenuBgFog, 7);

    Decompress(Img_MainMenuBgFog, (void*)(GetBackgroundTileDataOffset(3) + 0x06004C00));

    Decompress(Tsa_MainMenuBgFog, gGenericBuffer);
    CallARM_FillTileRect(gBG3TilemapBuffer, gGenericBuffer, 0x00007260);

    gCoScreen.bgFogX = 0;
    gCoScreen.bgFogY = 0;
    BG_SetPosition(3, 0, 0);

    BG_EnableSyncByMask(BG3_SYNC_BIT);

    /* Per-scanline HBlank scroll for the fog wave, same mechanism
     * SaveDraw_Init sets up for the save-menu fog (channel 0, BG2HOFS) --
     * here targeting BG3HOFS instead. */
    StartBgVerticalScroll(EWRAM_ENTRY);
    SetBgVerticalScrollPosition(0, (void*)REG_ADDR_BG3HOFS);
    ClearBgVerticalScrollChannelFlags(0);
    gpBgVerticalScrollSt->scroll_en = true;
}

/* CO screen static backdrop (BG2), contributed by PatrickHoang -- replaces
 * the DrawUiFrame-drawn header/page borders with a single full-screen
 * picture. Decompressed into BG2's own charblock (0x4000, unshared with
 * any other BG on this screen) and filled once at setup -- BG2 no longer
 * participates in CoPageSlide_OnLoop's per-frame fill/copy, since the
 * picture is a static layer that BG0 (portrait/header text) and BG1 (page
 * text) slide over. */
#define CO_STATUS_BG_PAL_SLOT 4
static void CoScreen_LoadStatusBg(void)
{
    Decompress(bg_CoStatusScreen_tiles, (void*)(VRAM + GetBackgroundTileDataOffset(2)));
    CallARM_FillTileRect(gBG2TilemapBuffer, bg_CoStatusScreen_map, TILEREF(0, CO_STATUS_BG_PAL_SLOT));
    ApplyPalette(bg_CoStatusScreen_palette, CO_STATUS_BG_PAL_SLOT);

    BG_SetPosition(2, 0, 0);
    BG_EnableSyncByMask(BG2_SYNC_BIT);
}

/* Called every frame (see gProcScr_CoPageNumCtrl) -- ported from
 * SaveDraw_ScrollFogBG (src/savedraw.c), targeting BG3/BG3HOFS instead of
 * BG2/BG2HOFS. Advances a base scroll (gCoScreen.bgFogX/Y) and writes a
 * per-scanline sine-wave horizontal offset into the HBlank scroll buffer
 * set up by CoScreen_LoadBgFrame's StartBgVerticalScroll, giving the fog
 * its waviness instead of a flat diagonal scroll. */
static void CoScreen_UpdateBgScroll(ProcPtr proc)
{
    u16* ptr;
    int i;
    s16 x;
    u32 bg_y;
    u32 angle;

    gCoScreen.bgFogX++;
    gCoScreen.bgFogY += 2;

    x = (gCoScreen.bgFogX & 0xfff) >> 3;
    bg_y = (gCoScreen.bgFogY / 8) & 0xff;

    ptr = GetBgVerticalScrollBuffer(0, true);
    angle = bg_y;

    for (i = 0; i < DISPLAY_HEIGHT; i++)
    {
        int v = SIN(angle) / 0x300;
        ptr[i] = (v + x) & 0x1ff;
        angle += 12;
    }

    BG_SetPosition(BG_3, x, bg_y);

    FlipBgVerticalScroll();
}



/* Vertical panel offset applied every frame from gStatScreen.yDispOff --
 * same mechanism as statscreen.c's BgOffCtrl_OnLoop/gProcScr_SSBgOffsetCtrl,
 * driven by the commander-fade's Interpolate calls above. BG0/BG1/BG2 carry
 * the page content and portrait, so they scroll together; BG3 is the
 * diagonal-scrolling frame background and has its own independent
 * BG_SetPosition calls (CoScreen_UpdateBgScroll), so it's left alone. */
static void CoBgOffCtrl_OnLoop(ProcPtr proc)
{
    /* No masking here -- BG_SetPosition's y is a u16 and the GBA's BG
     * scroll register only latches the low 9 bits, so a negative
     * yDispOff already wraps correctly via plain two's complement. An
     * 8-bit mask (0xFF, as used elsewhere for values that stay small and
     * positive) would drop the sign bit this needs and corrupt the
     * direction/magnitude for one side of the +/-60 swing this proc
     * actually reaches. */
    int yBg = -gStatScreen.yDispOff;

    BG_SetPosition(0, 0, yBg);
    // BG_SetPosition(1, 0, yBg);
    // BG_SetPosition(2, 0, yBg);
}

CONST_DATA struct ProcCmd gProcScr_CoBgOffsetCtrl[] = {
    PROC_REPEAT(CoBgOffCtrl_OnLoop),
    PROC_END,
};

static void CoScreen_Setup(ProcPtr proc)
{
    gCoScreen.coId = gPlaySt.commanderId[FACTION_BLUE >> 6];

    gStatScreen.page = CO_SCREEN_PAGE_INFO;
    gStatScreen.pageAmt = CO_SCREEN_PAGE_COUNT;
    gStatScreen.pageSlideKey = 0;
    gStatScreen.xDispOff = 0;
    gStatScreen.yDispOff = 0;
    gStatScreen.inTransition = FALSE;

    u16 bgConfig[12] =
    {
        0x0000, 0x6000, 0,
        0x0000, 0x6800, 0,
        0x8000, 0x7000, 0, 
        0x8000, 0x7800, 0,
    };

    SetupBackgrounds(bgConfig);
    // RegisterBlankTile(0x400);
    
    // LoadGameCoreGfxLegacyFrame();

    LoadUiFrameGraphics();
    ApplyUnitSpritePalettes();
    ApplySystemObjectsPalettes();
    ReadGameSaveCoreGfx();

    // LoadIconPalettes(4);
    LoadIconPalette(1, 0x13);
    LoadIconPalette(1, 0x14);


    /* Arrow/page-number OBJ graphics, same VRAM char offset
     * StatScreen_InitDisplay (src/statscreen.c) decompresses them to --
     * OBJPAL_4 itself is already populated by LoadGameCoreGfxLegacyFrame's
     * LoadObjUIGfx() (see CoScreen_Setup's earlier black-screen fix). */
    Decompress(Img_StatscreenObjs, (void*)(VRAM + 0x10000 + 0x240 * 0x20));

    /* Stat-bar graphics palette -- DrawStatWithBar/DrawStatBarGfx
     * (src/statscreen.c) draw into STATSCREEN_BGPAL_6, same as
     * StatScreen_InitDisplay's own UnpackUiBarPalette call. */
    UnpackNewUiBarPalette(STATSCREEN_BGPAL_6);
    // UnpackUiBarPalette(STATSCREEN_BGPAL_6);

    CoScreen_LoadBgFrame();
    CoScreen_LoadStatusBg();
#if FE8_AW2_ASSETS
    CoScreen_LoadAffinityBonusIcons();
#endif

    CoScreen_DrawPage();
    EnablePaletteSync();

    TileMap_CopyRect(gUiTmScratchA, gBG0TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);
    // TileMap_CopyRect(gUiTmScratchB, gBG1TilemapBuffer + TILEMAP_INDEX(CO_PAGE_X, CO_PAGE_Y), CO_PAGE_W, CO_PAGE_H);

    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT);
    // SetBlendConfig(3, 0, 0, 0x10);
    SetBlendTargetA(0, 0, 1, 0, 0); // transparent ui
    SetBlendTargetB(0, 0, 0, 1, 0); // BG3, so BG2 blends against it 
    SetBlendBackdropA(1);
    SetBlendAlpha(13, 3);
    Proc_Start(gProcScr_CoPageNumCtrl, proc);
    Proc_Start(gProcScr_CoBgOffsetCtrl, proc);
}

static void CoScreen_Teardown(ProcPtr proc)
{
    Proc_EndEach(gProcScr_CoPageNumCtrl);

    EndBgVerticalScroll();

    BG_Fill(gBG0TilemapBuffer, 0);
    BG_Fill(gBG1TilemapBuffer, 0);
    BG_Fill(gBG2TilemapBuffer, 0);
    BG_Fill(gBG3TilemapBuffer, 0);

    BG_EnableSyncByMask(0xF);

    gLCDControlBuffer.dispcnt.bg0_on = 0;
    gLCDControlBuffer.dispcnt.bg1_on = 0;
    gLCDControlBuffer.dispcnt.bg2_on = 0;
    gLCDControlBuffer.dispcnt.bg3_on = 0;
    gLCDControlBuffer.dispcnt.obj_on = 0;

    ResetText();

    CpuFastFill(0, gPaletteBuffer, 0x400);

    EnablePaletteSync();
}

static void CoScreen_KeyListener(ProcPtr proc)
{
    u16 keys = gKeyStatusPtr->newKeys; 
    if (!keys) 
    { 
        keys = gKeyStatusPtr->repeatedKeys; 
    } 
    if (gKeyStatusPtr->newKeys & B_BUTTON) {
        Proc_Break(proc);
        return;
    }


    if (gStatScreen.inTransition)
        return;

    if (keys & DPAD_LEFT) {
        gStatScreen.page = (gStatScreen.page + CO_SCREEN_PAGE_COUNT - 1) % CO_SCREEN_PAGE_COUNT;
        CoStartSlide(DPAD_LEFT, proc);
    } else if (keys & DPAD_RIGHT) {
        gStatScreen.page = (gStatScreen.page + 1) % CO_SCREEN_PAGE_COUNT;
        CoStartSlide(DPAD_RIGHT, proc);
    } else if (keys & DPAD_UP) {
#ifdef SCROLL_ALL_COS
        gCoScreen.coId = (gCoScreen.coId + CoScreen_GetCoCount() - 1) % CoScreen_GetCoCount();
#else
        gCoScreen.coId = FindNextUsedCoId(gCoScreen.coId, -1);
#endif
        CoStartCommanderFade(-1, proc);
    } else if (keys & DPAD_DOWN) {
#ifdef SCROLL_ALL_COS
        gCoScreen.coId = (gCoScreen.coId + 1) % CoScreen_GetCoCount();
#else
        gCoScreen.coId = FindNextUsedCoId(gCoScreen.coId, +1);
#endif
        CoStartCommanderFade(+1, proc);
    }
}
void CoInfo_BlackenScreen(void)
{
    gLCDControlBuffer.dispcnt.bg0_on = FALSE;
    gLCDControlBuffer.dispcnt.bg1_on = FALSE;
    gLCDControlBuffer.dispcnt.bg2_on = FALSE;
    gLCDControlBuffer.dispcnt.bg3_on = FALSE;
    gLCDControlBuffer.dispcnt.obj_on = FALSE;

    SetBlendConfig(3, 0, 0, 0x10);

    SetBlendTargetA(0, 0, 0, 0, 0);
    SetBlendBackdropA(1);
    SetBlendBackdropB(0);

    // TODO: ResetBackdropColor macro?
    gPaletteBuffer[PAL_BACKDROP_OFFSET] = 0;
    EnablePaletteSync();
}


CONST_DATA struct ProcCmd gProcScr_CoScreen[] = {
    PROC_NAME("COSCREEN"),
    PROC_CALL(CoInfo_BlackenScreen),
    PROC_CALL(BMapDispSuspend),
    PROC_CALL(LockGame),

    PROC_SLEEP(2),
    PROC_CALL(CoScreen_Setup),
    
    // PROC_CALL(StartFastFadeToBlack),
    // PROC_REPEAT(WaitForFade),
    // PROC_CALL_ARG(NewFadeOut, 16),
    // PROC_WHILE(FadeOutExists),
    // PROC_CALL(BMapDispSuspend),
    PROC_SLEEP(0),
    
    // PROC_CALL_ARG(NewFadeIn, 16),
    // PROC_WHILE(FadeInExists),
    

    PROC_REPEAT(CoScreen_KeyListener),

    
    PROC_CALL_ARG(NewFadeOut, 16),
    PROC_WHILE(FadeOutExists),

    PROC_CALL(CoScreen_Teardown),
    PROC_SLEEP(0),
    PROC_CALL(BMapDispResume),
    PROC_CALL(RefreshBMapGraphics),
    PROC_CALL(StartFastFadeFromBlack),
    PROC_REPEAT(WaitForFade),
    PROC_CALL(UnlockGame),

    PROC_END,
};

u8 CoScreen_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    Proc_StartBlocking(gProcScr_CoScreen, PROC_TREE_3);

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

#endif // FE8_CO_POWERS
