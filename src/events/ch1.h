#pragma once

/* Begin Ch1-eventudefs.h */
#include "global.h"
#include "muctrl.h"
#include "event.h"
#include "eventinfo.h"
#include "eventcall.h"
#include "constants/characters.h"
#include "constants/classes.h"
#include "constants/items.h"
#include "constants/backgrounds.h"
#include "constants/chapters.h"
#include "constants/faces.h"
#include "EAstdlib.h"
#include "playerphase.h"
#include "worldmap.h"
#include "constants/worldmap.h"
#include "constants/songs.h"
#include "constants/msg.h"
#include "bmguide.h"
#include "bmunit.h"
#include "coSelect.h"
#include "power.h"
#include "bmtrap.h"
#include "constants/event-flags.h"

CONST_DATA EventScr EventScrWM_Ch1_Beginning[] = {
    EVBIT_MODIFY(0x1)
    SKIPWN
    ENDA
};

CONST_DATA EventScr EventScrWM_Ch1_ChapterIntro[] = {
    EVBIT_MODIFY(0x1)
    ENUT(137)
    ENDA
};

/*
#define DefaultAI              0x00,0x00
#define GuardTileAI            0x03,0x03
#define AttackInRangeAI        0x00,0x03
#define ChaseOnceApproachedAI  0x00,0x06
#define HealUnits              0x0E,0x03
#define BrigandAI              0x06,0x04
#define StealingThiefAI        0x10,0x05
#define LootingThiefAI         0x06,0x05
#define MoveWithLeaderAI       0x0D,0x03
#define NeverMoveAI            0x03,0x03,0x04,0x20
#define DemonKingAI            0x14,0x03
*/ 

        // .ai = {DefaultAI, 0x4, 0x0}, // No recovery mode 

CONST_DATA struct UnitDefinition UnitDef_Ch1Allies[] = {
    {
        .charIndex = CHARACTER_SETH,
        .classIndex = CLASS_NOMAD,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 6,
        .yPosition = 0,
        .items = {
            ITEM_BOW_IRON,
            ITEM_VULNERARY,
        },
    },
    {
        .charIndex = CHARACTER_EIRIKA,
        .classIndex = CLASS_LYN_LORD, //CLASS_MYRMIDON_F
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 10,
        .yPosition = 15,
        .items = {
            ITEM_SWORD_MKATTI,
            ITEM_VULNERARY,
        },
    },
    { 0 },
};
// #define DEBUG_TESTING
// 0x88B3C50
CONST_DATA struct UnitDefinition UnitDef_Ch1Enemies[] = {
    // {
        // .charIndex = 0x82,
        // .classIndex = CLASS_SOLDIER,
        // .allegiance = FACTION_ID_RED,
        // .level = 1,
        // .xPosition = 2,
        // .yPosition = 9,
        // .items = {
            // ITEM_LANCE_IRON,
        // },
        // .ai = {0x0, 0x0, 0x0, 0x1},
    // },
    { 0 },
};

CONST_DATA struct REDA REDA_Ch1Ally_Asin[] = {
    {
        .x = 3,
        .y = 2,
    },
};
CONST_DATA struct REDA REDA_Ch1Ally_Archer[] = {
    {
        .x = 3,
        .y = 1,
    },
};
CONST_DATA struct REDA REDA_Ch1Ally_Fighter[] = {
    {
        .x = 2,
        .y = 1,
    },
};


CONST_DATA struct UnitDefinition UnitDef_Event_Ch1Asin[] = {
    {
        .charIndex = CHARACTER_MOULDER,
        .classIndex = CLASS_PRIEST,
        .allegiance = FACTION_ID_GREEN,
        .level = 1,
        .xPosition = 5,
        .yPosition = 0,
        .redaCount = 1,
        .redas = REDA_Ch1Ally_Asin,
        .ai = {GuardTileAI, 0x0, 0x0},
        .items = {
            ITEM_STAFF_NOSTAL,
            ITEM_STAFF_HEAL,
            ITEM_VULNERARY,
        },
    },
    {
        .charIndex = CHARACTER_CITIZEN,
        .classIndex = CLASS_ARCHER,
        .allegiance = FACTION_ID_GREEN,
        .level = 1,
        .xPosition = 4,
        .yPosition = 0,
        .redaCount = 1,
        .redas = REDA_Ch1Ally_Archer,
        .ai = {GuardTileAI, 0x0, 0x0},
        .items = {
            ITEM_BOW_IRON,
        },
    },
    {
        .charIndex = CHARACTER_CITIZEN,
        .classIndex = CLASS_FIGHTER,
        .allegiance = FACTION_ID_GREEN,
        .level = 1,
        .xPosition = 4,
        .yPosition = 0,
        .redaCount = 1,
        .redas = REDA_Ch1Ally_Fighter,
        .ai = {AttackInRangeAI, 0x0, 0x0},
        .items = {
            ITEM_AXE_IRON,
        },
    },
    { 0 },
};

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

    LOAD1(1, UnitDef_Ch1Enemies)
    ENUN

    LOAD2(1, UnitDef_Ch1Allies)
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

CONST_DATA EventListScr EventScr_Ch1_Turn_AllyReinforceArrive[] = {
    MUSC(SONG_54)
    CAMERA(5,0)
    STAL(10)
    LOAD1(1, UnitDef_Event_Ch1Asin)
    ENUN
    
    FlashCursor(CHARACTER_MOULDER, 30)
    Text(MSG_CC_CH1A_REINFORCEMENT)

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




CONST_DATA EventListScr EventListScr_Ch1_Turn[] = {
    TURN(0x0, EventScr_Ch1_Turn_AllyReinforceArrive, 2, 2, FACTION_RED)
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Ch1_Character[] = {
    CharacterEventBothWays(0x8, EventScr_Ch1_Talk_SethFranz, CHARACTER_SETH, CHARACTER_MOULDER)
    CharacterEventBothWays(0x9, EventScr_Ch1_Talk_EirikaFranz, CHARACTER_EIRIKA, CHARACTER_MOULDER)
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Ch1_Location[] = {
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Ch1_Misc[] = {
    DefeatBoss(EventScr_Ch1_EndingScene)
    CauseGameOverIfLordDies
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Ch1_SelectUnit[] = {
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Ch1_SelectDestination[] = {
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Ch1_UnitMove[] = {
    END_MAIN
};

CONST_DATA EventListScr * EventListScr_Ch1_Tutorial[] = {
    NULL
};

CONST_DATA struct ChapterEventGroup Ch1Events = {
    .turnBasedEvents               = EventListScr_Ch1_Turn,
    .characterBasedEvents          = EventListScr_Ch1_Character,
    .locationBasedEvents           = EventListScr_Ch1_Location,
    .miscBasedEvents               = EventListScr_Ch1_Misc,
    .specialEventsWhenUnitSelected = EventListScr_Ch1_SelectUnit,
    .specialEventsWhenDestSelected = EventListScr_Ch1_SelectDestination,
    .specialEventsAfterUnitMoved   = EventListScr_Ch1_UnitMove,
    .tutorialEvents                = EventListScr_Ch1_Tutorial,

    .traps            = TrapData_Event_Ch1,
    .extraTrapsInHard = TrapData_Event_Ch1Hard,

    .playerUnitsInNormal = UnitDef_Ch1Allies,
    .playerUnitsInHard   = UnitDef_Ch1Allies,

    .playerUnitsChoice1InEncounter = NULL,
    .playerUnitsChoice2InEncounter = NULL,
    .playerUnitsChoice3InEncounter = NULL,

    .enemyUnitsChoice1InEncounter = NULL,
    .enemyUnitsChoice2InEncounter = NULL,
    .enemyUnitsChoice3InEncounter = NULL,

    .beginningSceneEvents = EventScr_Ch1_BeginningScene,
    .endingSceneEvents    = EventScr_Ch1_EndingScene,
};


/* End ch1-eventinfo.h */
