#pragma once

#include "global.h"
#include "event.h"
#include "eventinfo.h"
#include "eventcall.h"
#include "EAstdlib.h"
#include "constants/characters.h"
#include "constants/backgrounds.h"
#include "constants/songs.h"

CONST_DATA EventListScr EventScr_Ch1_BeginningScene[] = {
#if FE8_CO_POWERS
    SVAL(EVT_SLOT_1, 0) // All COs right now. 
    SVAL(EVT_SLOT_3, FACTION_BLUE)
    ASMC(StartCoSelect)
#endif
    MUSI
    Text_BG(BG_GUSTAVE_DORE_MOUNTAINS_DUSK_192, MSG_CUSTOM_CAMPAIGN_CH1A_START)
    MUNO
    
    SVAL(EVT_SLOT_1, FACTION_RED)
    SVAL(EVT_SLOT_2, CO_KARGAN)
    ASMC(SetFactionCoFromSlots)
    
    LOAD1(1, UnitDef_Event_Ch1Enemy)
    ENUN

    LOAD2(1, UnitDef_Event_Ch1Ally)
    ENUN

    // FlashCursor(CHARACTER_EIRIKA, 60)




    /**
     * Temporary flag(11) is used for triggering event: EventScr_Ch1_Turn_EnemyReinforceArrive,
     * this flag will be unset by event: EventScr_Ch1_Misc_Area
     */
    // ENUT(EVFLAG_TMP(11))

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1_Turn1Player[] = {
    SVAL(EVT_SLOT_2, EventScr_Ch1Tut_ChooseSethTurn1)
    CALL(EventScr_CallOnTutorialMode)

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1_Turn1Enemy[] = {
    MUSC(SONG_SHADOW_OF_THE_ENEMY)
    FlashCursor(CHARACTER_BREGUET, 60)
    Text(0x930)

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1_Turn_AllyReinforceArrive[] = {
    MUSC(SONG_54)
    LOAD1(1, UnitDef_Event_Ch1AllyReinforce)
    ENUN
    FlashCursor(CHARACTER_FRANZ, 60)
    Text(0x931)

    SVAL(EVT_SLOT_2, EventScr_Ch1Tut_GilliamBattle)
    CALL(EventScr_CallOnTutorialMode)

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1_Misc_DefeatBoss[] = {
    SVAL(EVT_SLOT_2, EventScr_Ch1Tut_GuideMsgSeize)
    CALL(EventScr_CallOnTutorialMode)

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1_EndingScene[] = {
    MUSC(SONG_VICTORY)
    // MUSI
    // Text_BG(BG_GUSTAVE_DORE_MOUNTAINS_DUSK_192, MSG_CUSTOM_CAMPAIGN_CH1A_END)
    // MUNO
    MUSI
    SetBackground(BG_GUSTAVE_DORE_MOUNTAINS_DUSK_192)
    TEXTSHOW(MSG_CUSTOM_CAMPAIGN_CH1A_END)
    TEXTEND
    FADI(16)
    REMA
    MUNO
    FADI(16)
    ENUT(0xBA)
    ENUT(0xCF)
    ENUT(0xCE)
    ENUT(0xB6)
    ENUT(0xD7)
    ENUT(0xD6)
    ENUT(0xC7)
    ENUT(0xC8)
    ENUT(0xDD)

    // REVEAL(CHARACTER_SETH)
    MoveToChapter(0x38)
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1_Talk_SethFranz[] = {
    ConvoEvent(0x93A)
};

CONST_DATA EventListScr EventScr_Ch1_Talk_EirikaFranz[] = {
    ConvoEvent(0x939)
};

CONST_DATA EventListScr EventScr_Ch1_Loca_Visit1[] = {
    IGNORE_KEYS(0)
    HouseEvent(0x93B, 0x0)
};

CONST_DATA EventListScr EventScr_Ch1_Loca_Visit2[] = {
    HouseEvent(0x93C, 0x0)
};

CONST_DATA EventListScr EventScr_Ch1_Misc_Area[] = {
    SVAL(EVT_SLOT_2, CHARACTER_EIRIKA)
    CALL(EventScr_UnTriggerIfNotUnit)   /* This event may directly ENDB if the condition is not matched */

    ENUF(EVFLAG_TMP(11))
    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1_Turn_EnemyReinforceArrive[] = {
    MUSI
    SVAL(EVT_SLOT_2, UnitDef_Event_Ch1EnemyReinforce)
    CALL(EventScr_LoadReinforce)

    FlashCursor(CHARACTER_SOLDIER_83, 60)
    Text(0x934)

    MUNO
    NoFade
    ENDA
};
