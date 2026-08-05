#include "global.h"

#include "hardware.h"
#include "m4a.h"
#include "soundwrapper.h"
#include "bmio.h"
#include "bmunit.h"
#include "mu.h"
#include "rng.h"
#include "event.h"
#include "opinfo.h"
#include "bm.h"
#include "bmsave.h"
#include "ending_details.h"
#include "bmlib.h"
#include "eventinfo.h"
#include "worldmap.h"
#include "savemenu.h"
#include "gamecontrol.h"
#include "sio.h"
#include "constants/chapters.h"
#include "constants/event-flags.h"
#include "constants/songs.h"
#include "expansion_debugtools.h"
#include "expansion_language_menu.h"
#include "expansion_itemtest.h"

/* Reused verbatim from AgbMain's own clean-boot RNG seed (src/main.c) --
 * reseeding to this exact constant immediately before the debug hub's
 * "Fast Boot: Chapter 2" boot (see GameControl_PostIntro below) makes its
 * outcome independent of how many frames/RNG draws already happened
 * before the hotkey was pressed. */
#define DEBUGTOOLS_FASTBOOT_RNG_SEED 0x42D690E9

extern u16 EventScr_Ruin_83[];
extern u16 EventScr_Ruin_84[];
extern u16 EventScr_EirikaModeGameEnd[];
extern u16 EventScr_EphraimModeGameEnd[];

extern struct ProcCmd CONST_DATA ProcScr_GameEarlyStartUI[]; // pre-intro cutscene
extern struct ProcCmd CONST_DATA ProcScr_OpAnim[]; // intro cutscene
extern struct ProcCmd CONST_DATA ProcScr_WorldMapWrapper[];

struct ProcCmd CONST_DATA gUnused_Gamecontrol_0[] =
{
    PROC_CALL(GameControl_0),
    PROC_REPEAT(GameControl_Null_0),

    PROC_END,
};

struct ProcCmd CONST_DATA gProcScr_GameControl[] =
{
    PROC_NAME("GAMECTRL"),
    PROC_MARK(PROC_MARK_GAMECTRL),

    PROC_15,
    PROC_CALL(GameControl_CallEraseSaveEventWithKeyCombo),
    PROC_CALL(GameControl_0),
    PROC_REPEAT(GameControl_Null_0),

    // fallthrough

PROC_LABEL(LGAMECTRL_GAME_INTRO_UI),
    PROC_START_CHILD_BLOCKING(ProcScr_GameEarlyStartUI),

    // fallthrough

#ifdef MODERN
    /* Issue #18 sprint 3: blocking first-start language selector/auto-
     * apply gate -- after early UI/SRAM init (ProcScr_GameEarlyStartUI
     * above has already run), strictly before the intro cutscene/title
     * (ProcScr_OpAnim below). Never touches Title_IDLE or any issue #11
     * debug hotkey; ends immediately (no visible UI) whenever the
     * startup decision is APPLY_ONLY/AUTO_SELECT (see
     * src/expansion_language_menu.c). Guarded because this proc script
     * lives in src/expansion_language_menu.c, which -- like
     * src/expansion_locale.c/src/expansion_save_prefs.c -- is only
     * linked into the modern ROM. */
#if FE8_EXPANSION_ENABLED_LOCALE_COUNT > 1 || FE8_EXPANSION_DEBUG
    PROC_START_CHILD_BLOCKING(ProcScr_ExpansionLanguageSelector),
#endif

    // fallthrough

#endif /* MODERN */
PROC_LABEL(LGAMECTRL_OP_ANIM),
    PROC_CALL(GameControl_EnableSoundEffects),
    PROC_START_CHILD_BLOCKING(ProcScr_OpAnim),
    PROC_CALL(GameControl_PostIntro),
    PROC_YIELD,
    PROC_GOTO(4),

PROC_LABEL(LGAMECTRL_CLASS_REEL),
    PROC_CALL_2(GamceControl_StartClassReel),
    PROC_CALL(GameControl_PostClassReel),
    PROC_YIELD,
    PROC_GOTO(LGAMECTRL_OP_ANIM),

PROC_LABEL(3),
    PROC_YIELD,
    PROC_CALL(GameControl_ClearPaletteAndReset),
    PROC_CALL(GameControl_PostClassReel),
    PROC_YIELD,
    PROC_GOTO(LGAMECTRL_OP_ANIM),

PROC_LABEL(LGAMECTRL_TITLE_DIRECT),
    PROC_CALL(GameControl_EnableSoundEffects),
    PROC_CALL(StartTitleScreen_WithMusic),
    PROC_GOTO(LGAMECTRL_POST_TITLE_IDLE),

PROC_LABEL(24),
    PROC_CALL(GameControl_EnableSoundEffects),
    PROC_CALL(StartTitleScreen_FlagTrue),
    PROC_GOTO(LGAMECTRL_POST_TITLE_IDLE),

PROC_LABEL(25),
    PROC_CALL(GameControl_EnableSoundEffects),
    PROC_CALL(StartTitleScreen_FlagFalse),
    PROC_GOTO(LGAMECTRL_POST_TITLE_IDLE),

PROC_LABEL(LGAMECTRL_POST_TITLE_IDLE),
    PROC_YIELD,
    PROC_CALL(GameControl_PostIntro),
    PROC_YIELD,
    PROC_GOTO(LGAMECTRL_OP_ANIM),

PROC_LABEL(LGAMECTRL_EXEC_SAVEMENU),
    PROC_CALL(GameControl_EnableSoundEffects),
    PROC_CALL(StartSaveMenu),
    PROC_YIELD,
    PROC_CALL(GameControl_SwitchPostSaveMenu),
    PROC_YIELD,
    PROC_GOTO(LGAMECTRL_EXEC_BM),

PROC_LABEL(LGAMECTRL_EXEC_BM_EXT),
    PROC_CALL(GameControl_RememberChapterId),
    PROC_YIELD,
    PROC_CALL(StartBattleMap),
    PROC_YIELD,
    PROC_GOTO(9),

PROC_LABEL(LGAMECTRL_EXEC_BM),
    PROC_CALL(GameCtrl_CheckNewGameAndBranch),
    PROC_CALL(GameCtrl_CheckGameCompleteAndBranch),
    PROC_CALL(GameControl_RememberChapterId),
    PROC_CALL(GameCtrlStartIntroMonologue),
    PROC_YIELD,
    PROC_START_CHILD_BLOCKING(ProcScr_WorldMapWrapper),
    PROC_CALL(EndWM),
    PROC_CALL(GameControl_SetupBackdropBlend),
    PROC_YIELD,
    PROC_CALL(StartBattleMap),
    PROC_YIELD,

    // fallthrough

PROC_LABEL(LGAMECTRL_POST_NORMAL_CHAPTER),
    PROC_YIELD,

    PROC_CALL(GameControl_PostChapterSwitch),
    PROC_YIELD,
    PROC_CALL(GameControl_RestoreChapterId),

    // fallthrough

PROC_LABEL(19),
    PROC_CALL(GameControl_ChapterSwitch),
    PROC_CALL(GameControl_CallPostChapterSaveMenu),
    PROC_YIELD,
    PROC_GOTO(LGAMECTRL_EXEC_BM),

PROC_LABEL(8),
    PROC_CALL(GameControl_SetupBackdropBlend),
    PROC_CALL(GameCtrl_StartResumedGame),
    PROC_YIELD,
    PROC_CALL(GameControl_RememberChapterId),
    PROC_CALL(GameControlHandlePostNormalOrExtraChapter),

    PROC_GOTO(9),

PROC_LABEL(14),
    PROC_YIELD,
    // fallthrough

PROC_LABEL(LGAMECTRL_POST_EXTRA_MAP),
    PROC_YIELD,
    PROC_GOTO(LGAMECTRL_TITLE_DIRECT),

PROC_LABEL(LGAMECTRL_EXEC_BM_),
    PROC_GOTO(LGAMECTRL_EXEC_BM),

PROC_LABEL(12),
    PROC_CALL(StartLinkArenaMainMenu),
    PROC_YIELD,
    PROC_CALL(GameControl_StartMainTheme),
    PROC_GOTO(LGAMECTRL_EXEC_SAVEMENU),

PROC_LABEL(16),
    PROC_CALL(ClearTemporaryUnits),
    PROC_CALL(GameCtrl_DeclareCompletedChapter),
    PROC_CALL(Make6C_SaveMenuPostChapter),
    PROC_YIELD,

    // fallthrough

PROC_LABEL(LGAMECTRL_EXEC_ENDING_SCENE),
    PROC_CALL(GameCtrl_SavePlayThroughData),

    PROC_CALL(CallGameEndingEvent),
    PROC_YIELD,

    PROC_WHILE(EventEngineExists),

    PROC_CALL(StartFinScreen),
    PROC_CALL(_SetGameEndFlag),

    PROC_SLEEP(30),

    PROC_GOTO(4),

PROC_LABEL(LGAMECTRL_ERASE_SAVE),
    PROC_CALL(GameControl_CallEraseMural),
    PROC_CALL(StartMidFadeFromBlack),
    PROC_REPEAT(WaitForFade),
    PROC_CALL(CallEraseSaveEvent),
    PROC_WHILE(EventEngineExists),
    PROC_YIELD,
    PROC_CALL(StartMidFadeToBlack),
    PROC_REPEAT(WaitForFade),
    PROC_CALL(EndMuralBackground),
    PROC_GOTO(LGAMECTRL_GAME_INTRO_UI),

    PROC_END,
};

int GetRealChaperIndex(int chapterId)
{

    switch (chapterId) {
    case CHAPTER_L_2:
        return 1;

    case CHAPTER_L_3:
        return 2;

    case CHAPTER_L_4:
        return 3;

    case CHAPTER_L_5X:
    case CHAPTER_L_5:
        return 4;

    case CHAPTER_L_6:
        return 5;

    case CHAPTER_L_7:
        return 6;

    case CHAPTER_L_8:
    case CHAPTER_CASTLE_FRELIA:
        return 7;

    case CHAPTER_E_9:
    case CHAPTER_I_9:
        return 8;

    case CHAPTER_E_10:
    case CHAPTER_I_10:
        return 9;

    case CHAPTER_E_12:
    case CHAPTER_I_12:
    case CHAPTER_E_11:
    case CHAPTER_I_11:
        return 10;

    case CHAPTER_E_13:
    case CHAPTER_I_13:
        return 11;

    case CHAPTER_E_14:
    case CHAPTER_I_14:
        return 12;

    case CHAPTER_E_15:
    case CHAPTER_I_15:
        return 13;

    case CHAPTER_E_16:
    case CHAPTER_I_16:
        return 14;

    case CHAPTER_E_17:
    case CHAPTER_I_17:
        return 15;

    case CHAPTER_E_18:
    case CHAPTER_I_18:
        return 16;

    case CHAPTER_E_19:
    case CHAPTER_I_19:
        return 17;

    case CHAPTER_E_20:
    case CHAPTER_I_20:
        return 18;

    case CHAPTER_E_21:
    case CHAPTER_E_21X:
    case CHAPTER_I_21:
    case CHAPTER_I_21X:
        return 19;

    case CHAPTER_L_PROLOGUE:
    case CHAPTER_L_1:
    default:
        return 0;
    }
}

u8 GetTitleClassReelSet(void)
{
    int furthestChapter;
    int chapter;
    int i;
    struct PlaySt chapterData;

    if (GetGlobalCompletionCount() != 0)
        return 9;

    furthestChapter = 0;

    for (i = 0; i < 3; i++)
    {
        if (IsSaveValid(i) == 0)
            continue;

        ReadGameSavePlaySt(i, &chapterData);

        if (chapterData.unk_2C_2 != 0)
            return 9;

        chapter = GetRealChaperIndex(chapterData.chapterIndex);

        if (furthestChapter < chapter)
            furthestChapter = chapter;
    }

    if (furthestChapter > 17)
        return 8;
    else if (furthestChapter > 15)
        return 7;
    else if (furthestChapter > 13)
        return 6;
    else if (furthestChapter > 11)
        return 5;
    else if (furthestChapter > 9)
        return 4;
    else if (furthestChapter > 7)
        return 3;
    else if (furthestChapter > 5)
        return 2;
    else if (furthestChapter > 3)
        return 1;

    return 0;
}

bool GamceControl_StartClassReel(ProcPtr proc)
{
    StartClassReel(GetTitleClassReelSet(), proc);
    return false;
}

void GameControl_CallEraseSaveEventWithKeyCombo(ProcPtr proc)
{
    if (gKeyStatusPtr->heldKeys == (L_BUTTON | DPAD_RIGHT | SELECT_BUTTON))
        Proc_Goto(proc, LGAMECTRL_ERASE_SAVE);
}

void GameControl_CallEraseMural(ProcPtr proc)
{
    SetupBackgrounds(0);
    LoadGameCoreGfxLegacyFrame();
    gPlaySt.config.textSpeed = 1;
    StartMuralBackground(PROC_TREE_3, 0, -1);
}

void GameControl_0(struct GameCtrlProc * proc)
{
    proc->unk_2E = 20;
}

void GameControl_Null_0(ProcPtr proc)
{
    Proc_Break(proc);
}

void EndProcIfNotMarkedB(ProcPtr proc)
{
    if (((struct Proc*)proc)->proc_mark != PROC_MARK_GAMECTRL)
        Proc_End(proc);
}

void GameControl_ClearPaletteAndReset(ProcPtr proc)
{
    CpuFastFill16(0, gPaletteBuffer, 0x400);
    EnablePaletteSync();
    Proc_ForAll(EndProcIfNotMarkedB);
    SetMainUpdateRoutine(OnMain);
}

void GameControl_StartMainTheme(ProcPtr proc)
{
    StartBgmCore(SONG_MAIN_THEME, 0);
    StartBgmVolumeChange(0, 0xC0, 0x3C, 0);
}


void GameControl_FadeBgmVolume(ProcPtr proc)
{
    StartBgmVolumeChange(0x100, 0xC0, 0x20, 0);
}

void GameControl_PostIntro(struct GameCtrlProc * proc)
{
    int tmp;

    switch (proc->nextAction) {
    case GAME_ACTION_USR_SKIPPED:
        Proc_Goto(proc, LGAMECTRL_TITLE_DIRECT);
        break;

    case GAME_ACTION_EVENT_RETURN:
#if FE8_EXPANSION_ITEMTEST_ENABLED
        /* Issue #10 opt-in runtime item-expansion probe (compiled out, and
         * this whole block absent, in every ordinary build -- see
         * include/expansion_itemtest.h). Consumed at most once, before the
         * debug-hub handoff and the ordinary StartSaveMenu branch below;
         * the bootstrap itself is the ordinary production new-game
         * sequence and this proc continues its own normal lifecycle
         * straight into the ordinary LGAMECTRL_EXEC_BM transition. */
        if (ItemExpansionTest_ConsumeChapterBootRequest())
        {
            ItemExpansionTest_PrepareChapterBoot();
            proc->nextChapter = CHAPTER_L_2;

            /* The ordinary chapter-start state: the world map and the
             * chapter's own unit loading/beginning event all run completely
             * unmodified from here, exactly as they do for the debug hub's
             * Chapter 2 launcher. */
            Proc_Goto(proc, LGAMECTRL_EXEC_BM);
            break;
        }
#endif

        /* Debug hub "Fast Boot: Chapter 2" handoff (see
         * src/debugtools_launcher.c, include/expansion_debugtools.h):
         * consumed at most once per armed request, and only here, before
         * the ordinary StartSaveMenu branch below. No proc tree is torn
         * down or recreated -- this is the exact same GameCtrlProc,
         * continuing its own normal lifecycle straight into the ordinary
         * LGAMECTRL_EXEC_BM transition. */
        if (DebugTools_ConsumePendingChapter2Launch())
        {
            SetLCGRNValue(DEBUGTOOLS_FASTBOOT_RNG_SEED);
            InitRN(AdvanceGetLCGRNValue());

            /* Same new-game bootstrap sequence GameControl_InitTutorialGame
             * uses below -- InitPlayConfig, ResetPermanentFlags,
             * ResetChapterFlags, InitUnits -- for a normal (non-tutorial)
             * chapter boot. InitPlayConfig zeroes gPlaySt (EWRAM only);
             * none of these calls touch SRAM. */
            InitPlayConfig(0, 0);
            gPlaySt.chapterModeIndex = CHAPTER_MODE_COMMON;
            ResetPermanentFlags();
            ResetChapterFlags();
            InitUnits();
            gPlaySt.chapterIndex = CHAPTER_L_2;
            proc->nextChapter = CHAPTER_L_2;

            GmDataInit();

            /* GmDataInit() places the world map party at NODE_BORDER_MULAN
             * (the Prologue rest node) by default. The normal
             * LGAMECTRL_EXEC_BM path below runs through
             * WorldMap_CallBeginningEvent (src/worldmap_main.c), which
             * unconditionally recomputes gPlaySt.chapterIndex from
             * WMLoc_GetNextLocId(gGMData.units[0].location) -- so without
             * this, the chapterIndex/nextChapter set above would be
             * silently overwritten back to the Prologue. Placing the party
             * at NODE_CASTLE_FRELIA (the same rest stop the normal Chapter
             * 1 -> Chapter 2 progression passes through) lets the ordinary
             * world-map node traversal resolve to NODE_IDE / CHAPTER_L_2 on
             * its own, exactly as it would for a real playthrough -- no
             * chapter-specific event or battle logic is bypassed.
             */
            gGMData.units[0].location = NODE_CASTLE_FRELIA;

            /* One-shot persistent-write suppression for the boot window
             * ahead (see BmMain_SuspendBeforePhase in src/bm.c and
             * UnlockSoundRoomSong in src/soundwrapper.c); also starts the
             * bootstrap observer proc that clears it at the first stable
             * Player Phase. */
            DebugTools_ArmBootstrapSuppression();

            /* Committed-to-boot evidence for playtest probes (see
             * gDebugToolsProbe.launcherArmed, include/expansion_debugtools.h):
             * written here, once, the same frame the pending request is
             * consumed and this deterministic boot is committed to. */
            gDebugToolsProbe.launcherArmed = DEBUGTOOLS_LAUNCHER_ARMED_MAGIC;

            Proc_Goto(proc, LGAMECTRL_EXEC_BM);
            break;
        }

        /* Debug hub "Fast Boot: Ch4 Prep" handoff (issue #11 closure --
         * see src/debugtools_launcher.c, include/expansion_debugtools.h).
         * Same exact contract as the Chapter 2 branch above -- consumed
         * at most once per armed request, before the ordinary
         * StartSaveMenu branch, no proc torn down or recreated -- just a
         * different target chapter/node so the resulting boot reaches a
         * chapter whose own beginning event script
         * (EventScr_Ch4_BeginningScene, src/events/ch4-eventscript.h)
         * calls CALL(EventScr_CommonPrep) partway through, unlike
         * Chapter 2's. */
        if (DebugTools_ConsumePendingChapter4PrepLaunch())
        {
            SetLCGRNValue(DEBUGTOOLS_FASTBOOT_RNG_SEED);
            InitRN(AdvanceGetLCGRNValue());

            InitPlayConfig(0, 0);
            gPlaySt.chapterModeIndex = CHAPTER_MODE_COMMON;
            ResetPermanentFlags();
            ResetChapterFlags();
            InitUnits();
            gPlaySt.chapterIndex = CHAPTER_L_4;
            proc->nextChapter = CHAPTER_L_4;

            GmDataInit();

            /* Same node-placement idiom as the Chapter 2 branch above,
             * one node earlier in the same linear node chain:
             * NODE_BORGO_RIDGE's own WMLoc_GetNextLocId resolves to
             * NODE_ZAHA_WOODS / CHAPTER_L_4 (src/worldmap_node_data.c),
             * exactly as NODE_CASTLE_FRELIA resolves to NODE_IDE /
             * CHAPTER_L_2 -- so the ordinary world-map traversal (an L
             * cursor-jump + A node-confirm) reaches Chapter 4 without
             * skipping any chapter-specific event/battle logic. */
            gGMData.units[0].location = NODE_BORGO_RIDGE;

            DebugTools_ArmBootstrapSuppression();

            gDebugToolsProbe.ch4PrepLauncherArmed = DEBUGTOOLS_LAUNCHER_ARMED_MAGIC;

            Proc_Goto(proc, LGAMECTRL_EXEC_BM);
            break;
        }

        Proc_Goto(proc, LGAMECTRL_EXEC_SAVEMENU);
        GameControl_FadeBgmVolume(proc);
        break;

    case GAME_ACTION_CLASS_REEL:
        tmp = proc->idle_status;
        switch (tmp & 1) {
        case 0:
            Proc_Goto(proc, LGAMECTRL_CLASS_REEL);
            break;

        case 1:
            Proc_Goto(proc, LGAMECTRL_OP_ANIM);
            break;
        }

        proc->idle_status++;
        break;

    case GAME_ACTION_PLAYED_THROUGH:
        Proc_Goto(proc, 24);
        break;
    }
}

void GameControl_PostClassReel(struct GameCtrlProc * proc)
{
    switch (proc->nextAction) {
    case GAME_ACTION_EVENT_RETURN:
        Proc_Goto(proc, LGAMECTRL_TITLE_DIRECT);
        break;

    case GAME_ACTION_CLASS_REEL:
        Proc_Goto(proc, LGAMECTRL_OP_ANIM);
        break;
    }
}

void GameControl_SwitchPostSaveMenu(struct GameCtrlProc * proc)
{
    switch (proc->nextAction) {
    case GAME_ACTION_EVENT_RETURN:
        GmDataInit();

        // fallthrough

    case GAME_ACTION_CLASS_REEL:
    case GAME_ACTION_USR_SKIPPED:
    case GAME_ACTION_PLAYED_THROUGH:
        Proc_Goto(proc, LGAMECTRL_EXEC_BM);
        return;

    case GAME_ACTION_4:
        Proc_Goto(proc, 8);
        return;

    case GAME_ACTION_5:
        Proc_Goto(proc, 25);
        return;

    case GAME_ACTION_6:
        Proc_Goto(proc, 12);
        return;

    case GAME_ACTION_EXTRA_MAP:
        Proc_Goto(proc, 14);
        return;

    case GAME_ACTION_C:
        Proc_Goto(proc, 15);
        return;

    case GAME_ACTION_8:
    case GAME_ACTION_9:
    case GAME_ACTION_A:
    case GAME_ACTION_B:
    default:
        return;
    }

    return;
}

void GameControl_GotoTitleIfAction5(struct GameCtrlProc * proc)
{
    if (proc->nextAction == GAME_ACTION_5)
        Proc_Goto(proc, LGAMECTRL_TITLE_DIRECT);
}

void GameControl_GotoTitle(struct GameCtrlProc * proc)
{
    Proc_Goto(proc, LGAMECTRL_TITLE_DIRECT);
}

void GameControl_GotoChapterSwitchIfClassReel(struct GameCtrlProc * proc)
{
    if (proc->nextAction == GAME_ACTION_EVENT_RETURN)
        return;

    if (proc->nextAction == GAME_ACTION_CLASS_REEL)
        Proc_Goto(proc, 19);
}

void GameControl_InitTutorialGame(struct GameCtrlProc * proc)
{
    if (proc->nextAction == GAME_ACTION_5)
    {
        Proc_Goto(proc, 5);
        return;
    }

    InitPlayConfig(0, 0);
    gPlaySt.chapterStateBits |= PLAY_FLAG_TUTORIAL;
    ResetPermanentFlags();
    ResetChapterFlags();
    InitUnits();
    gPlaySt.chapterIndex = proc->nextChapter;
}

void GameCtrlStartExtraMap(ProcPtr proc)
{
    NullBmMapHidden_();
    ClearPidStats();
    ChapterChangeUnitCleanup();
    gPlaySt.chapterIndex = 0x7F;

}

void GameControl_InvalidateSuspendSave(ProcPtr proc)
{
    InvalidateSuspendSave(SAVE_ID_SUSPEND);
    gPlaySt.config.disableBgm = 0;
}

void GameControl_PostChapterSwitch(struct GameCtrlProc* proc) {

    EndAllMus();

    switch (proc->nextAction) {
    case GAME_ACTION_EVENT_RETURN:
        Proc_Goto(proc, LGAMECTRL_TITLE_DIRECT);
        break;

    case GAME_ACTION_PLAYED_THROUGH:
        Proc_Goto(proc, 16);
        break;

    case GAME_ACTION_CLASS_REEL:
    case GAME_ACTION_USR_SKIPPED:
    default:
        break;
    }

    return;
}

void GameCtrl_CheckNewGameAndBranch(struct GameCtrlProc* proc) {
    if ((gPlaySt.save_menu_type == 2) || (gPlaySt.save_menu_type == 4)) {
        Proc_Goto(proc, LGAMECTRL_EXEC_BM_EXT);
    }

    return;
}

void GameCtrl_CheckGameCompleteAndBranch(struct GameCtrlProc* proc) {
    if (gPlaySt.chapterStateBits & PLAY_FLAG_POSTGAME) {
        return;
    }

    if (!(gPlaySt.chapterStateBits & PLAY_FLAG_COMPLETE)) {
        return;
    }

    Proc_Goto(proc, LGAMECTRL_EXEC_ENDING_SCENE);

    return;
}

void GameControlHandlePostNormalOrExtraChapter(struct GameCtrlProc* proc) {
    if (gPlaySt.chapterStateBits & PLAY_FLAG_EXTRA_MAP)
        Proc_Goto(proc, 10);
    else
        Proc_Goto(proc, 9);
}

void GameControl_ChapterSwitch(struct GameCtrlProc* proc) {
    int i;

    for (i = 0; i <= 2; i++) {
        NextRN();
    }

    StoreRNState(gGmMonsterRnState);

    if (CheckFlag(3) != 0) {
        RegisterChapterTimeAndTurnCount(&gPlaySt);
    }

    ComputeChapterRankings();

    gPlaySt.chapterIndex = proc->nextChapter;

    ChapterChangeUnitCleanup();

    return;
}

void GameControl_CallPostChapterSaveMenu(struct GameCtrlProc* proc) {
    if (gPlaySt.chapterIndex != 0x38) {
        Make6C_SaveMenuPostChapter(proc);
    }

    return;
}

void GameCtrlStartIntroMonologue(struct GameCtrlProc * proc)
{
    if (gPlaySt.chapterStateBits & PLAY_FLAG_POSTGAME)
        return;

    if (gPlaySt.chapterIndex != 0)
        return;

    StartIntroMonologue(proc);
}

void GameControl_SetupBackdropBlend(ProcPtr proc)
{
    SetBlendConfig(3, 0, 0, 16);
    SetBlendTargetA(1, 1, 1, 1, 1);
    SetBlendBackdropA(1);
}

void GameControl_StartRuinEvent(ProcPtr proc)
{
    SetupBackgrounds(0);

    switch (gPlaySt.chapterModeIndex) {
        case 2:
            CallEvent(EventScr_Ruin_83, EV_EXEC_CUTSCENE);
            break;

        case 3:
            CallEvent(EventScr_Ruin_84, EV_EXEC_CUTSCENE);
            break;
    }

    SetFlag(EVFLAG_HIDE_BLINKING_ICON);

    return;
}

void CallGameEndingEvent(ProcPtr proc) {
    StartBattleMap(proc);

    ForceScreenToBlack();

    switch (gPlaySt.chapterModeIndex) {
        case 2:
            CallEvent(EventScr_EirikaModeGameEnd, EV_EXEC_CUTSCENE);
            break;

        case 3:
            CallEvent(EventScr_EphraimModeGameEnd, EV_EXEC_CUTSCENE);
            break;
    }

    SetFlag(EVFLAG_HIDE_BLINKING_ICON);

    return;
}

void GameControl_RememberChapterId(struct GameCtrlProc * proc)
{
    proc->ch_index = gPlaySt.chapterIndex;
}

void GameControl_RestoreChapterId(struct GameCtrlProc * proc)
{
    gPlaySt.chapterIndex = proc->ch_index;
}

void _SetGameEndFlag(ProcPtr proc)
{
    SetGameEndFlag();
}

void StartGame(void)
{
    struct GameCtrlProc* proc;

    SetMainUpdateRoutine(OnMain);
    SetInterrupt_LCDVBlank(OnVBlank);

    proc = Proc_Start(gProcScr_GameControl, PROC_TREE_3);
    proc->nextAction = GAME_ACTION_EVENT_RETURN;
    proc->nextChapter = 0;
    proc->idle_status = 0;
}

struct GameCtrlProc *GetGameControl(void)
{
    return Proc_Find(gProcScr_GameControl);
}

void SetNextGameActionId(int id) {
    struct GameCtrlProc* proc = GetGameControl();

    proc->nextAction = id;

    return;
}

void SetNextChapterId(int id) {
    struct GameCtrlProc* proc = GetGameControl();

    proc->nextChapter = id;

    return;
}

s8 HasNextChapter(void)
{
    struct GameCtrlProc* proc = GetGameControl();
    return proc->nextChapter == 0 ? 0 : 1;
}

void RestartGameAndGoto8(void) {
    struct GameCtrlProc* proc;

    Proc_EndEach(gProcScr_GameControl);

    proc = Proc_Start(gProcScr_GameControl, PROC_TREE_3);

    Proc_Goto(proc, 8);

    return;
}

void RestartGameAndGoto12(void) {
    struct GameCtrlProc* proc;

    Proc_EndEach(gProcScr_GameControl);

    proc = Proc_Start(gProcScr_GameControl, PROC_TREE_3);

    Proc_Goto(proc, 18);

    return;
}

void RestartGameAndGoto7(void) {
    return;
}

void Nop_Gamecontrol_0(void)
{
    return;
}

void GameControl_EnableSoundEffects(ProcPtr proc)
{
    gPlaySt.config.disableBgm = 0;
    gPlaySt.config.disableSoundEffects = 0;
}

void GameControl_ResetPlayConfig(ProcPtr proc)
{

    gPlaySt.config.animationType = 0;
    gPlaySt.config.textSpeed = 1;
    gPlaySt.config.gameSpeed = 0;
    gPlaySt.config.disableBgm = 0;
    gPlaySt.config.disableSoundEffects = 1;
    gPlaySt.config.windowColor = 0;
    gPlaySt.config.unitColor = 0;
}
