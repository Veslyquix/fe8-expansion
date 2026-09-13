#pragma once

/* Begin prologue-eventudefs.h */
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

CONST_DATA EventScr EventScrWM_Prologue_Beginning[] = {
    EVBIT_MODIFY(0x1)
    WmEvtNoFade // ENOSUPP in EAstdlib
    WM_SPAWNLORD(WM_MU_0, CHARACTER_EIRIKA, WM_NODE_BorderMulan)
    WM_CENTERCAMONLORD(WM_MU_0)

    MUSCFAST(SONG_SILENT)
    STAL(32)
    MUSC(SONG_THE_BEGINNING)
    WM_SHOWDRAWNMAP(0, 0, 0x10)
    STAL(2)
    WM_FADEOUT(0)
    WM_TEXTDECORATE // WaitFade
    EVBIT_MODIFY(0x0)
    WM_SHOWPORTRAIT(0, FID_WAKWI, 0x02BC, 0)
    STAL(60)

    WM_SHOWTEXTWINDOW(40, 0x0001)
    WM_WAITFORTEXT
    WM_TEXTSTART
    WM_TEXT(MSG_WM_INTRO, 0)

    // wait for talk locked
    TEXTEND
    WM_CREATENEXTDESTINATION
    WM_WAITFORFX
    SKIPWN
    ENDA
};

CONST_DATA EventScr EventScrWM_Prologue_ChapterIntro[] = {
    EVBIT_MODIFY(0x1)
    ENUT(137)
    ENDA
};





CONST_DATA struct UnitDefinition UnitDef_PrologueAllies[] = {
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
        .xPosition = 1,
        .yPosition = 2,
        .items = {
            ITEM_SWORD_MKATTI,
            ITEM_VULNERARY,
        },
    },
    { 0 },
};
// #define DEBUG_TESTING
// 0x88B3C50
CONST_DATA struct UnitDefinition UnitDef_PrologueEnemies[] = {
    // {
        // .charIndex = CHARACTER_ONEILL,
        // .classIndex = CLASS_FIGHTER,
        // .allegiance = FACTION_ID_RED,
        // .level = 4,
        // .xPosition = 17,
        // .yPosition = 12,
        // .items = {
            // ITEM_AXE_IRON,
        // },
        // .ai = {0x6, 0x3, 0x0, 0x1},
    // },
    {
        .charIndex = 0x82,
        .classIndex = CLASS_SOLDIER,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 18,
        .yPosition = 10,
        .items = {
            ITEM_LANCE_IRON,
        },
        .ai = {0x0, 0x0, 0x0, 0x1},
    },
    { 0 },
};

CONST_DATA EventListScr EventScr_Prologue_BeginningScene[] = {
    SVAL(EVT_SLOT_1, FACTION_BLUE)
    SVAL(EVT_SLOT_2, CO_ISHKODE)
    ASMC(SetFactionCoFromSlots)

    SVAL(EVT_SLOT_1, FACTION_RED)
    SVAL(EVT_SLOT_2, CO_KARGAN)
    ASMC(SetFactionCoFromSlots)

#if FE8_CO_POWERS
    SVAL(EVT_SLOT_1, 0) // All COs right now.
    SVAL(EVT_SLOT_3, FACTION_BLUE)
    ASMC(StartCoSelect)
#endif

    LOAD1(1, UnitDef_PrologueAllies)
    ENUN
    FADU(16)

    MUSI
    BROWNBOXTEXT(MSG_CUSTOM_CAMPAIGN_PROLOGUE_LOCATION, 8, 8)
    MUNO

    ENUT(0x7)
    ENUT(0x8)

    FlashCursor(CHARACTER_EIRIKA, 20)
    MOVE(4, CHARACTER_SETH, 10, 0)
    MOVE(1, CHARACTER_EIRIKA, 1, 3)
    ENUN
    MOVE(3, CHARACTER_SETH, 5, 1)


    // MOVE(3, CHARACTER_EIRIKA, 3, 1)
    MOVE(3, CHARACTER_EIRIKA, 4, 1)
    ENUN

    FlashCursor(CHARACTER_EIRIKA, 60)

    MUSI
    Text_BG(BG_ALEXANDER_LAWRIE_HILLSIDE_192, MSG_CUSTOM_CAMPAIGN_PROLOGUE_OPENING)
    MUNO

    MUSI
    Text_BG(BG_ALEXANDER_LAWRIE_HILLSIDE_192, MSG_CUSTOM_CAMPAIGN_PROLOGUE_KARGAN)
    MUNO

    /* Color distortion test - working fine with 192 col BGs.
    SetBackground(BG_TOBIAS_SPENCE_RIVER_FOREST_192)
    SVAL(EVT_SLOT_3, ITEM_SWORD_RAPIER)
    GIVEITEMTO(CHARACTER_EIRIKA)
    FADI(16)
    CLEAN
    */


    // Text(MSG_CUSTOM_CAMPAIGN_PROLOGUE_OPENING)
    FlashCursor(CHARACTER_SETH, 20)
    MOVE(0, CHARACTER_SETH, 1, 2)
    ENUN
    DISA(CHARACTER_SETH)

    LOAD1(1, UnitDef_PrologueEnemies)
    ENUN
    NoFade
    ENDA
};


CONST_DATA EventListScr EventScr_Prologue_EndingScene[] = {
    MUSC(SONG_VICTORY)

    MUSI
    SetBackground(BG_ALEXANDER_LAWRIE_HILLSIDE_192)
    TEXTSHOW(MSG_CUSTOM_CAMPAIGN_PROLOGUE_ENDING)
    TEXTEND
    FADI(16)
    REMA
    MUNO

    MNCH(0x1)
    // WmEvtSetUnitOnNode(WM_MU_0, WM_NODE_BorderMulan) // doesn't seem to help here 
    ENDA
};




CONST_DATA EventListScr EventListScr_Prologue_Turn[] = {
    // TURN(0x0, EventScr_Prologue_Turn1, 1, 0, FACTION_RED)
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Prologue_Character[] = {
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Prologue_Location[] = {
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Prologue_Misc[] = {
    DefeatBoss(EventScr_Prologue_EndingScene)
    CauseGameOverIfLordDies
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Prologue_SelectUnit[] = {
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Prologue_SelectDestination[] = {
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Prologue_UnitMove[] = {
    END_MAIN
};

CONST_DATA EventListScr * EventListScr_Prologue_Tutorial[] = {
    NULL
};

CONST_DATA struct ChapterEventGroup PrologueEvents = {
    .turnBasedEvents               = EventListScr_Prologue_Turn,
    .characterBasedEvents          = EventListScr_Prologue_Character,
    .locationBasedEvents           = EventListScr_Prologue_Location,
    .miscBasedEvents               = EventListScr_Prologue_Misc,
    .specialEventsWhenUnitSelected = EventListScr_Prologue_SelectUnit,
    .specialEventsWhenDestSelected = EventListScr_Prologue_SelectDestination,
    .specialEventsAfterUnitMoved   = EventListScr_Prologue_UnitMove,
    .tutorialEvents                = EventListScr_Prologue_Tutorial,

    .traps            = TrapData_Event_Prologue,
    .extraTrapsInHard = TrapData_Event_PrologueHard,

    .playerUnitsInNormal = UnitDef_PrologueAllies,
    .playerUnitsInHard   = UnitDef_PrologueAllies,

    .playerUnitsChoice1InEncounter = NULL,
    .playerUnitsChoice2InEncounter = NULL,
    .playerUnitsChoice3InEncounter = NULL,

    .enemyUnitsChoice1InEncounter = NULL,
    .enemyUnitsChoice2InEncounter = NULL,
    .enemyUnitsChoice3InEncounter = NULL,

    .beginningSceneEvents = EventScr_Prologue_BeginningScene,
    .endingSceneEvents    = EventScr_Prologue_EndingScene,
};
/* End prologue-eventinfo.h */
