#include "global.h"
#include "ap.h"
#include "fontgrp.h"
#include "hardware.h"
#include "proc.h"
#include "rng.h"
#include "mu.h"
#include "soundwrapper.h"
#include "gamecontrol.h"
#ifdef MODERN
#include "expansion_language_menu.h"
#endif
#include "bm.h"
#include "bmsave.h"
#include "worldmap.h"

// uninitialized memory in the original build due to changing this call to no longer use __FILE__.
const u16 gUninitializedMemory[] = {0x4641, 0x464A, 0x4653, 0x465C};

const char gBuildDateTime[] = "2005/02/04(FRI) 16:55:40";
const char gYearProjectCreated[] = "_2003";

void StoreIRQToIRAM(void);

void AgbMain(void)
{
    int sw_rst;
#if defined(MODERN) && !FE8_EXPANSION_DEBUG
    int i;
    int syncFrames;
#endif

    // clear RAM
    DmaFill32(3, 0, (void *)IWRAM_START, 0x7F80); // reset the area for the IWRAM ARM section.
    CpuFastFill(0, (void *)EWRAM_START, 0x40000);    

    /* maybe WAITCNT will not reset after SW_RST? */
    sw_rst = (REG_WAITCNT != 0);
    SetSoftwareResetFlag(sw_rst);
    if (sw_rst == TRUE)
        RegisterRamReset(~2);

    REG_WAITCNT = WAITCNT_SRAM_4 |          /* SRAM Wait Control          = 4 cycles */
                  WAITCNT_WS0_N_3 |         /* Wait State 0 First Access  = 3 cycles */
                  WAITCNT_WS0_S_1 |         /* Wait State 0 Second Access = 1 cycle  */
                  WAITCNT_WS1_N_3 |         /* Wait State 1 First Access  = 3 cycles */
                  WAITCNT_WS1_S_1 |         /* Wait State 1 Second Access = 1 cycle  */
                  WAITCNT_WS2_N_3 |         /* Wait State 2 First Access  = 3 cycles */
                  WAITCNT_WS2_S_1 |         /* Wait State 2 Second Access = 1 cycle  */
                  WAITCNT_PHI_OUT_NONE |    /* PHI Terminal Output disabled */
                  WAITCNT_PREFETCH_ENABLE | /* Game Pak Prefetch Buffer enabled */
                  WAITCNT_AGB;

    StoreIRQToIRAM();
    SetInterrupt_LCDVBlank(NULL);

    REG_DISPSTAT = DISPSTAT_VBLANK_INTR;
    REG_IME = INTR_FLAG_VBLANK;
    ResetKeyStatus(gKeyStatusPtr);
    UpdateKeyStatus(gKeyStatusPtr);
    StoreRoutinesToIRAM();
    SramInit();
    Proc_Init();
    AP_ClearAll();
    InitMus();
    SetLCGRNValue(0x42D690E9);
    InitRN(AdvanceGetLCGRNValue());
    DisableKeyComboResetEN();
#ifndef MODERN
    EraseInvalidSaveData();
#endif
    EraseSramDataIfInvalid();
#if defined(MODERN) && !FE8_EXPANSION_DEBUG && FE8_EXPANSION_ENABLED_LOCALE_COUNT <= 1
    ExpansionLanguageMenu_InitializeSingleLocaleBoot();
#endif

    // initialize sound
    m4aSoundInit();
    Sound_SetDefaultMaxNumChannels();

    SetInterrupt_LCDVBlank(OnVBlank);
    GmDataInit();
    SetLang(LANG_ENGLISH);
    ResetText();
#if defined(MODERN) && !FE8_EXPANSION_DEBUG
    /*
     * Modern GCC reaches StartGame seven VBlanks early with an existing
     * save. Full-chip erased-SRAM verification already consumes that
     * route's startup budget, so it gets no additional synthetic VBlank.
     * Remove only synthetic compensation frames from the game clock.
     */
    syncFrames = (gSramBootFlags & SRAM_BOOT_FLAG_DATA_INITIALIZED) ? 0 : 7;
    for (i = 0; i < syncFrames; ++i)
        VBlankIntrWait();
    SetGameTime(GetGameClock() - syncFrames);
#endif
    StartGame();

    // perform the game loop.
    while (1)
    {
        ExecMainUpdate();
        SoftResetIfKeyComboPressed();
    };
}
