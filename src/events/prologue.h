#pragma once

/* Begin prologue-eventudefs.h */
#include "global.h"
#include "muctrl.h"
#include "eventcall.h"
#include "constants/characters.h"
#include "constants/classes.h"
#include "constants/items.h"

CONST_DATA struct REDA REDAs_PrologueAlly1[] = {
    /* Seth */
    {
        .x = 13,
        .y = 8,
        .flags = 0x18,
        .b = 0xffff,
    },
    {
        .x = 10,
        .y = 8,
        .flags = 0x18,
        .b = 0xffff,
    },
    {
        .x = 10,
        .y = 7,
        .flags = 0x18,
        .b = 0xffff,
    },
    {
        .x = 9,
        .y = 7,
        .flags = 0x18,
        .b = 0xffff,
    },
    {
        .x = 9,
        .y = 5,
        .flags = 0x18,
        .b = 0xffff,
    },
    {
        .x = 8,
        .y = 5,
        .flags = 0x18,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDAs_PrologueAlly2[] = {
    /* Eirika */
    {
        .x = 9,
        .y = 5,
        .flags = 0x10,
        .a = 0x2,
        .b = 0xffff,
    },
};

CONST_DATA struct REDA REDAs_PrologueEnemy1[] = {
    /* ONEILL */
    {
        .x = 10,
        .y = 8,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDAs_PrologueEnemy2[] = {
    /* Enemy2 */
    {
        .x = 8,
        .y = 6,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDAs_PrologueEnemy3[] = {
    /* Enemy3 */
    {
        .x = 9,
        .y = 6,
        .b = 0xffff,
        .delayFrames = 16,
    },
};

// 0x88B3C14
CONST_DATA struct UnitDefinition UnitDef_Event_PrologueAlly[] = {
    {
        .charIndex = CHARACTER_SETH,
        .classIndex = CLASS_PALADIN,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 13,
        .yPosition = 9,
        .redaCount = 6,
        .redas = REDAs_PrologueAlly1,
        .items = {
            ITEM_SWORD_STEEL,
            ITEM_LANCE_SILVER,
            ITEM_VULNERARY,
        },
    },
    {
        .charIndex = CHARACTER_EIRIKA,
        .classIndex = CLASS_EIRIKA_LORD,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 8,
        .yPosition = 5,
        .redaCount = 1,
        .redas = REDAs_PrologueAlly2,
        .items = {
            ITEM_VULNERARY,
        },
    },
    { 0 },
};

// 0x88B3C50
CONST_DATA struct UnitDefinition UnitDef_Event_PrologueEnemy[] = {
    {
        .charIndex = CHARACTER_ONEILL,
        .classIndex = CLASS_FIGHTER,
        .allegiance = FACTION_ID_RED,
        .level = 4,
        .xPosition = 14,
        .yPosition = 8,
        .redaCount = 1,
        .redas = REDAs_PrologueEnemy1,
        .items = {
            ITEM_AXE_IRON,
        },
        .ai = {0x6, 0x3, 0x0, 0x0},
    },
    {
        .charIndex = 0x82,
        .classIndex = CLASS_FIGHTER,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 14,
        .yPosition = 7,
        .redaCount = 1,
        .redas = REDAs_PrologueEnemy2,
        .items = {
            ITEM_AXE_IRON,
        },
        .ai = {0x0, 0xa, 0x0, 0x0},
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_FIGHTER,
        .allegiance = FACTION_ID_RED,
        .level = 2,
        .xPosition = 14,
        .yPosition = 7,
        .redaCount = 1,
        .redas = REDAs_PrologueEnemy3,
        .items = {
            ITEM_AXE_IRON,
        },
        .ai = {0x0, 0x12, 0x2, 0x0},
    },
    { 0 },
};

CONST_DATA struct REDA REDAs_PrologueMessager[] = {
    {
        .x = 9,
        .y = 11,
        .b = 0xffff,
    },
    {
        .x = 13,
        .y = 11,
        .b = 0xffff,
    },
    {
        .x = 13,
        .y = 6,
        .b = 0xffff,
    },
};

CONST_DATA struct REDA REDAs_PrologueGradoRoyals1[] = {
    {
        .x = 13,
        .y = 6,
        .flags = 0xc,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDAs_PrologueGradoRoyals2[] = {
    {
        .x = 12,
        .y = 7,
        .flags = 0xc,
        .b = 0xffff,
    },
};

CONST_DATA struct REDA REDA_PrologueGradoShamans0[] = {
    {
        .x = 7,
        .y = 4,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_PrologueGradoShamans1[] = {
    {
        .x = 6,
        .y = 6,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_PrologueGradoShamans2[] = {
    {
        .x = 19,
        .y = 3,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_PrologueGradoShamans3[] = {
    {
        .x = 20,
        .y = 6,
        .b = 0xffff,
    },
};

CONST_DATA struct REDA REDA_PrologueGradoCavalry0[] = {
    {
        .x = 10,
        .y = 4,
        .flags = 0x10,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_PrologueGradoCavalry1[] = {
    {
        .x = 16,
        .y = 4,
        .flags = 0x10,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_PrologueGradoCavalry2[] = {
    {
        .x = 10,
        .y = 6,
        .flags = 0x10,
        .b = 0xffff,
        .delayFrames = 40,
    },
};
CONST_DATA struct REDA REDA_PrologueGradoCavalry3[] = {
    {
        .x = 16,
        .y = 6,
        .flags = 0x10,
        .b = 0xffff,
        .delayFrames = 40,
    },
};
CONST_DATA struct REDA REDA_PrologueGradoCavalry4[] = {
    {
        .x = 10,
        .y = 8,
        .flags = 0x10,
        .a = 0x83,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_PrologueGradoCavalry5[] = {
    {
        .x = 16,
        .y = 8,
        .flags = 0x10,
        .a = 0x83,
        .b = 0xffff,
    },
};

// 0x88B3D18
CONST_DATA struct UnitDefinition UnitDef_Event_PrologueThroneRoomUnits[] = {
    {
        .charIndex = CHARACTER_FADO,
        .classIndex = CLASS_PEER,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 13,
        .yPosition = 3,
    },
    {
        .charIndex = CHARACTER_EIRIKA,
        .classIndex = CLASS_EIRIKA_LORD,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 14,
        .yPosition = 4,
    },
    {
        .charIndex = CHARACTER_SETH,
        .classIndex = CLASS_PALADIN,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 15,
        .yPosition = 4,
    },
    {
        .charIndex = CHARACTER_MOULDER,
        .classIndex = CLASS_GENERAL,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 11,
        .yPosition = 7,
    },
    {
        .charIndex = CHARACTER_VANESSA,
        .classIndex = CLASS_GENERAL,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 15,
        .yPosition = 7,
    },
    {
        .charIndex = CHARACTER_GILLIAM,
        .classIndex = CLASS_ARMOR_KNIGHT,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 7,
        .yPosition = 14,
    },
    {
        .charIndex = CHARACTER_FRELIAN,
        .classIndex = CLASS_ARMOR_KNIGHT,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 10,
        .yPosition = 14,
    },
    {
        .charIndex = CHARACTER_FRANZ,
        .classIndex = CLASS_CAVALIER,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 11,
        .yPosition = 4,
    },
    { 0 },
};

// 0x88B3DCC
CONST_DATA struct UnitDefinition UnitDef_Event_PrologueMessager[] = {
    {
        .charIndex = CHARACTER_EPHRAIM,
        .classIndex = CLASS_SOLDIER,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 9,
        .yPosition = 15,
        .redaCount = 3,
        .redas = REDAs_PrologueMessager,
    },
    { 0 },
};

// 0x88B3DF4
CONST_DATA struct UnitDefinition UnitDef_Event_PrologueGradoRoyals[] = {
    {
        .charIndex = CHARACTER_VIGARDE,
        .classIndex = CLASS_GENERAL,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 13,
        .yPosition = 10,
        .redaCount = 1,
        .redas = REDAs_PrologueGradoRoyals1,
    },
    {
        .charIndex = CHARACTER_LYON,
        .classIndex = CLASS_NECROMANCER,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 12,
        .yPosition = 11,
        .redaCount = 1,
        .redas = REDAs_PrologueGradoRoyals2,
    },
    { 0 },
};

CONST_DATA struct UnitDefinition UnitDef_Event_PrologueGradoShamans[] = {
    {
        .charIndex = 0x80,
        .classIndex = CLASS_SHAMAN,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 5,
        .yPosition = 1,
        .redaCount = 1,
        .redas = REDA_PrologueGradoShamans0,
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_SHAMAN,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 5,
        .yPosition = 2,
        .redaCount = 1,
        .redas = REDA_PrologueGradoShamans1,
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_DRUID,
        .autolevel = 1,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 19,
        .yPosition = 10,
        .redaCount = 1,
        .redas = REDA_PrologueGradoShamans2,
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_DRUID,
        .autolevel = 1,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 20,
        .yPosition = 10,
        .redaCount = 1,
        .redas = REDA_PrologueGradoShamans3,
    },
    { 0 },
};

// 0x88B3E94
CONST_DATA struct UnitDefinition UnitDef_Event_PrologueGradoCavalry[] = {
    {
        .charIndex = CHARACTER_SOLDIER_83,
        .classIndex = CLASS_GREAT_KNIGHT,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 10,
        .yPosition = 10,
        .redaCount = 1,
        .redas = REDA_PrologueGradoCavalry0,
    },
    {
        .charIndex = CHARACTER_SOLDIER_83,
        .classIndex = CLASS_GREAT_KNIGHT,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 16,
        .yPosition = 10,
        .redaCount = 1,
        .redas = REDA_PrologueGradoCavalry1,
    },
    {
        .charIndex = 0x84,
        .classIndex = CLASS_PALADIN,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 10,
        .yPosition = 10,
        .redaCount = 1,
        .redas = REDA_PrologueGradoCavalry2,
    },
    {
        .charIndex = 0x84,
        .classIndex = CLASS_PALADIN,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 16,
        .yPosition = 10,
        .redaCount = 1,
        .redas = REDA_PrologueGradoCavalry3,
    },
    {
        .charIndex = 0x85,
        .classIndex = CLASS_MAGE_KNIGHT,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 10,
        .yPosition = 10,
        .redaCount = 1,
        .redas = REDA_PrologueGradoCavalry4,
    },
    {
        .charIndex = 0x85,
        .classIndex = CLASS_MAGE_KNIGHT,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 16,
        .yPosition = 10,
        .redaCount = 1,
        .redas = REDA_PrologueGradoCavalry5,
    },
    { 0 },
};

CONST_DATA struct REDA REDA_PrologueEscapees0[] = {
    {
        .x = 9,
        .y = 5,
        .b = 0xffff,
    },
    {
        .x = 6,
        .y = 5,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_PrologueEscapees2[] = {
    {
        .x = 9,
        .y = 4,
        .b = 0xffff,
        .delayFrames = 16,
    },
    {
        .x = 6,
        .y = 4,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_PrologueEscapees4[] = {
    {
        .x = 7,
        .y = 5,
        .flags = 0x10,
        .a = 0x2,
        .b = 0xffff,
        .delayFrames = 16,
    },
};

CONST_DATA struct REDA REDA_PrologueValterGroup0[] = {
    {
        .x = 10,
        .y = 5,
        .b = 0xffff,
    },
    {
        .x = 9,
        .y = 5,
        .flags = 0x10,
        .b = 0xffff,
        .delayFrames = 16,
    },
};
CONST_DATA struct REDA REDA_PrologueValterGroup2[] = {
    {
        .x = 11,
        .y = 4,
        .b = 0xffff,
        .delayFrames = 16,
    },
};
CONST_DATA struct REDA REDA_PrologueValterGroup3[] = {
    {
        .x = 11,
        .y = 6,
        .b = 0xffff,
        .delayFrames = 16,
    },
};

// 0x88B3F68
CONST_DATA struct UnitDefinition UnitDef_Event_PrologueEscapees[] = {
    {
        .charIndex = CHARACTER_SETH,
        .classIndex = CLASS_PALADIN,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 9,
        .yPosition = 3,
        .redaCount = 2,
        .redas = REDA_PrologueEscapees0,
        .items = {
            ITEM_SWORD_STEEL,
        },
    },
    {
        .charIndex = CHARACTER_FRANZ,
        .classIndex = CLASS_CAVALIER,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 9,
        .yPosition = 3,
        .redaCount = 2,
        .redas = REDA_PrologueEscapees2,
    },
    {
        .charIndex = CHARACTER_EIRIKA,
        .classIndex = CLASS_EIRIKA_LORD,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 6,
        .yPosition = 5,
        .redaCount = 1,
        .redas = REDA_PrologueEscapees4,
    },
    { 0 },
};

// 0x88B3FB8
CONST_DATA struct UnitDefinition UnitDef_Event_PrologueValterGroup[] = {
    {
        .charIndex = CHARACTER_VALTER_PROLOGUE,
        .classIndex = CLASS_WYVERN_KNIGHT,
        .allegiance = FACTION_ID_RED,
        .level = 5,
        .xPosition = 14,
        .yPosition = 5,
        .redaCount = 2,
        .redas = REDA_PrologueValterGroup0,
        .items = {
            ITEM_LANCE_SILVER,
        },
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_WYVERN_RIDER,
        .autolevel = 1,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 14,
        .yPosition = 4,
        .redaCount = 1,
        .redas = REDA_PrologueValterGroup2,
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_WYVERN_RIDER,
        .autolevel = 1,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 14,
        .yPosition = 6,
        .redaCount = 1,
        .redas = REDA_PrologueValterGroup3,
    },
    { 0 },
};
/* End prologue-eventudefs.h */

/* Begin prologue-tutorials.h */
#include "global.h"
#include "event.h"
#include "eventinfo.h"
#include "eventcall.h"
#include "EAstdlib.h"
#include "playerphase.h"
#include "constants/characters.h"

CONST_DATA EventListScr EventScr_Prologue_ExecTut[] = {
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x919)
    TEXTEND
    REMA

    CURSOR_FLASHING_CHAR(CHARACTER_EIRIKA)
    STAL(60)
    CURE

    /* Not in stdlib */
    EvtEnqueueConditionalTutCall(
        EventScr_Prologue_Tutorial0,
        TUTORIAL_EVT_TYPE_ONSELECT)

    /* This may end all events! Directly end the parent event! */
    NoFade
    ENDB
};

CONST_DATA EventListScr EventScr_Prologue_Tutorial0[] = {
    NoFade

    TutEventExecType0(
        CHARACTER_EIRIKA,
        4, 5,
        0x91B,
        0x00080058,
        0x91A,
        0x00080058,
        EventScr_Prologue_Tutorial1,
        EventScr_Prologue_Tutorial0
    )
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Tutorial1[] = {
    NoFade
    IGNORE_KEYS(0)

    TutEventExecType1(
        4, 5,
        0x91C,
        0x00080058,
        EventScr_Prologue_Tutorial2,
        EventScr_Prologue_Tutorial1
    )
    DISABLEOPTIONS(~EVENT_MENUOVERRIDE_WAIT)
    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Tutorial2[] = {
    NoFade

    EvtEnqueueConditionalTutCall(
        EventScr_Prologue_Tutorial3,
        TUTORIAL_EVT_TYPE_POSTACTION)

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Tutorial3[] = {
    NoFade
    IGNORE_KEYS(0)
    CALL(EventScr_Prologue_GiveRapier)
    SET_ENDTURN(CHARACTER_SETH)
    ENUT(0xB7) /* Guide:Movement Range */
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_TutMessageTurn1[] = {
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x91D)
    TEXTEND
    REMA

    ENUT(0xB4) /* Guide:Viewing Units */
    ENUT(0xB5) /* Guide:Game Flow */

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_TutMessageTurn2[] = {
    FlashCursor(CHARACTER_SETH, 60)
    Text(0x911)

    StartBattle
    NormalDamage(0, 0)
    MissedAttack(1, 0)
    NormalDamage(0, 0)
    EndAttack
    FIGHT_SCRIPT

    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x922)
    TEXTEND
    REMA

    ENUF(0x66) /* Disable objective window */
    ENUT(0xDC) /* Guide:Defeat a Boss */

    CURSOR_FLASHING_CHAR(CHARACTER_EIRIKA)
    STAL(60)
    CURE

    EvtEnqueueConditionalTutCall(
        EventScr_Prologue_Tutorial4,
        TUTORIAL_EVT_TYPE_ONSELECT)

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Tutorial4[] = {
    NoFade
    IGNORE_KEYS(0)

    TutEventExecType0(
        CHARACTER_EIRIKA,
        4, 5,
        0x91E,      /* It's time to attack the enemy. Place the cursor on Eirika and press the A Button. */
        0x00080058,
        0x91F,      /* The cursor is now on Eirika. Press the A Button. */
        0x00080058,
        EventScr_Prologue_Tutorial5,
        EventScr_Prologue_Tutorial4
    )

    IGNORE_KEYS(
        L_BUTTON | R_BUTTON
        | DPAD_DOWN | DPAD_UP | DPAD_LEFT | DPAD_RIGHT
        | START_BUTTON | SELECT_BUTTON | B_BUTTON)

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Tutorial5[] = {
    NoFade
    ASMC(PlayPhaseForcePressAButtonInRangeDisp)
    DISABLEOPTIONS(~EVENT_MENUOVERRIDE_ATTACK)
    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)

    EvtEnqueueConditionalTutCall(
        EventScr_Prologue_Tutorial6,
        TUTORIAL_EVT_TYPE_AFTERMOVE)

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Tutorial6[] = {
    NoFade
    IGNORE_KEYS(0)

    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, 0x00380018)
    TEXTSHOW(0x920)
    TEXTEND
    REMA

    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)

    EvtEnqueueConditionalTutCall(
        EventScr_Prologue_Tutorial7,
        TUTORIAL_EVT_TYPE_FORECAST)

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Tutorial7[] = {
    NoFade
    IGNORE_KEYS(R_BUTTON)

    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, 0x0020000C)
    TEXTSHOW(0x921)
    TEXTEND
    REMA

    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)

    EvtEnqueueConditionalTutCall(
        EventScr_Prologue_Tutorial8,
        TUTORIAL_EVT_TYPE_POSTACTION)

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Tutorial8[] = {
    IGNORE_KEYS(0)
    FlashCursor(CHARACTER_EIRIKA, 60)
    Text(0x912)

    EvtEnqueueConditionalTutCall(
        EventScr_Prologue_Tutorial9,
        TUTORIAL_EVT_TYPE_PLAYERPHASE)

    ENUT(0xB9) /* Guide:Attack Range */
    ENUT(0xC2) /* Guide:Strategic Battle Info */
    ENUT(0xC3) /* Guide:Detailed Battle Info */

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Tutorial9[] = {
    MOVE(0, CHARACTER_SETH, 9, 5)
    ENUN

    StartBattle
    NormalDamage(0, 20)
    EndAttack
    SVAL(EVT_SLOT_B, 0x60009)
    FIGHT(CHARACTER_SETH, -1, 0, 0)

    _3427(CHARACTER_SETH)

    SVAL(EVT_SLOT_B, 0x00060009)
    KILL(-2)
    DISA_IF(-2)

    ENUT(EVFLAG_TMP(7)) /* trigger event: EventScr_Prologue_OneEnemyLeft */
    CALL(EventScr_Prologue_OneEnemyLeft)
    SET_ENDTURN(CHARACTER_SETH)

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_OneillSethBattle[] = {
    MOVE(0, CHARACTER_ONEILL, 9, 6)
    ENUN

    StartBattle
    NormalDamage(0, 0)
    MissedAttack(1, 0)
    EndAttack
    FIGHT(CHARACTER_ONEILL, CHARACTER_SETH, 0, 0)

    FlashCursor(CHARACTER_SETH, 60)
    Text(0x915)
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_TutEirikaAttack[] = {
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x923) /* Place the cursor on Eirika and press the A Button. */
    TEXTEND
    REMA

    CURSOR_FLASHING_CHAR(CHARACTER_EIRIKA)
    STAL(60)
    CURE

    StartBattle
    NormalDamage(0, 0)
    NormalDamage(1, 0)
    CriticalHit(0, 0)
    EndAttack
    FIGHT_SCRIPT

    EvtEnqueueConditionalTutCall(
        EventScr_Prologue_TutorialA,
        TUTORIAL_EVT_TYPE_ONSELECT)

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_TutorialA[] = {
    NoFade

    TutEventExecType0(
        CHARACTER_EIRIKA,
        8, 6,
        0x925,      /* Move next to the enemy and press the A Button. */
        0x00080058,
        0x924,      /* The cursor is now on Eirika. Press the A Button. */
        0x00080058,
        EventScr_Prologue_TutorialB,
        EventScr_Prologue_TutorialA
    )
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_TutorialB[] = {
    NoFade
    IGNORE_KEYS(0)
    TutEventExecType1(
        8, 6,
        0x925,      /* Move next to the enemy and press the A Button. */
        0x00080058,
        EventScr_Prologue_TutorialC,
        EventScr_Prologue_TutorialB
    )
    DISABLEOPTIONS(~EVENT_MENUOVERRIDE_ATTACK)
    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_TutorialC[] = {
    NoFade

    EvtEnqueueConditionalTutCall(
        EventScr_Prologue_TutorialD,
        TUTORIAL_EVT_TYPE_FORECAST)

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_TutorialD[] = {
    NoFade
    IGNORE_KEYS(R_BUTTON)

    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, 0x00200050)
    TEXTSHOW(0x926)
    TEXTEND
    REMA

    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)

    EvtEnqueueConditionalTutCall(
        EventScr_Prologue_TutorialE,
        TUTORIAL_EVT_TYPE_POSTACTION)

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_TutorialE[] = {
    NoFade
    IGNORE_KEYS(0)

    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x927) /* Eirika gained over 100 experience points and has leveled up. */
    TEXTEND
    REMA

    ENUT(0xE7) /* Guide:Leveling Up */
    DISABLEOPTIONS(0)
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_9EF828[] = {
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x928) /* You've received a rapier from Seth. All weapons have a durability rating... */
    TEXTEND
    REMA

    ENUT(0xC9) /* Guide:Weapon Durability */
    ENDA
};
/* End prologue-tutorials.h */

/* Begin prologue-wm.h */
#include "global.h"
#include "event.h"
#include "eventinfo.h"
#include "eventcall.h"
#include "eventscript.h"
#include "EAstdlib.h"
#include "worldmap.h"
#include "constants/characters.h"
#include "constants/classes.h"
#include "constants/worldmap.h"
#include "constants/songs.h"
#include "constants/msg.h"

CONST_DATA EventScr EventScrWM_Prologue_Beginning[] = {
    EVBIT_MODIFY(0x1)
    WmEvtNoFade // ENOSUPP in EAstdlib
    WM_SPAWNLORD(WM_MU_0, CHARACTER_EIRIKA, WM_NODE_BorderMulan)
    WM_CENTERCAMONLORD(WM_MU_0)
#if FE8_SKIP_OPENING
            /* Skip the "The continent of Magvel..." narration when first
             * arriving at the prologue on New Game. Other chapters' world-
             * map beginning events are unaffected. */
    MUSCFAST(SONG_SILENT)
    STAL(32)
    MUSC(SONG_THE_BEGINNING)
    WM_SHOWDRAWNMAP(0, 0, 0x10)
    STAL(2)
    WM_FADEOUT(0)
    WM_TEXTDECORATE // WaitFade
    EVBIT_MODIFY(0x0)
    WM_SHOWPORTRAIT(0, 0x2, 0x02BC, 0)
    STAL(60)

    WM_SHOWTEXTWINDOW(40, 0x0001)
    WM_WAITFORTEXT
    WM_TEXTSTART
    WM_TEXT(MSG_WM_INTRO, 0)

    // wait for talk locked
    TEXTEND

    SKIPWN
    ENDA
#endif
    MUSCFAST(SONG_SILENT)
    STAL(32)
    MUSC(SONG_THE_BEGINNING)
    WM_SHOWDRAWNMAP(0, 0, 0x10)
    STAL(2)
    WM_FADEOUT(0)
    WM_TEXTDECORATE // WaitFade
    EVBIT_MODIFY(0x0)
    STAL(60)
    WM_SHOWTEXTWINDOW(40, 0x0001)
    WM_WAITFORTEXT
    WM_TEXTSTART
    WM_TEXT(0x08DB, 0)

    // wait for talk locked
    TEXTEND
    WM_MOVECAM2(0, 0, 0, 24, 60, 0)
    STAL(60)
    WM_SHOWPORTRAIT(0, 0x0051, 0x02BC, 0)
    STAL(6)
    STAL(26)
    WM_HIGHLIGHT(WM_NATION_Renais)
    TEXTCONT

    // wait for talk locked
    TEXTEND
    STAL(30)
    WM_HIGHLIGHTCLEAR1(WM_NATION_Renais)
    WM_HIGHLIGHTCLEAR2(WM_NATION_Renais)
    WM_CLEARPORTRAIT(0, 0x0100, 0)
    STAL(32)
    WM_MOVECAM2(0, 24, 0, -8, 60, 0)
    STAL(60)
    WM_SHOWPORTRAIT(0, 0x0052, 0x02BC, 0)
    STAL(6)
    STAL(26)
    WM_HIGHLIGHT(WM_NATION_Frelia)
    TEXTCONT

    // wait for talk locked
    TEXTEND
    STAL(30)
    WM_HIGHLIGHTCLEAR1(WM_NATION_Frelia)
    WM_HIGHLIGHTCLEAR2(WM_NATION_Frelia)
    WM_CLEARPORTRAIT(0, 0x0100, 0)
    STAL(32)
    WM_MOVECAM2(0, -8, 0, 30, 60, 0)
    STAL(60)
    WM_SHOWPORTRAIT(0, 0x0056, 0x0534, 0)
    STAL(6)
    STAL(26)
    WM_HIGHLIGHT(WM_NATION_Jehanna)
    TEXTCONT

    // wait for talk locked
    TEXTEND
    STAL(30)
    WM_HIGHLIGHTCLEAR1(WM_NATION_Jehanna)
    WM_HIGHLIGHTCLEAR2(WM_NATION_Jehanna)
    WM_CLEARPORTRAIT(0, 0x0200, 0)
    STAL(32)
    WM_MOVECAM2(0, 30, 0, -8, 60, 0)
    STAL(60)
    WM_SHOWPORTRAIT(0, 0x0053, 0x0534, 0)
    STAL(6)
    STAL(26)
    WM_HIGHLIGHT(WM_NATION_Rausten)
    TEXTCONT

    // wait for talk locked
    TEXTEND
    STAL(30)
    WM_HIGHLIGHTCLEAR1(WM_NATION_Rausten)
    WM_HIGHLIGHTCLEAR2(WM_NATION_Rausten)
    WM_CLEARPORTRAIT(0, 0x0200, 0)
    STAL(32)
    WM_MOVECAM2(0, -8, 0, 48, 60, 0)
    STAL(60)
    WM_SHOWPORTRAIT(0, 0x0040, 0x02BC, 0)
    STAL(6)
    STAL(26)
    WM_HIGHLIGHT(WM_NATION_Grado)
    TEXTCONT

    // wait for talk locked
    TEXTEND
    STAL(30)
    WM_HIGHLIGHTCLEAR1(WM_NATION_Grado)
    WM_HIGHLIGHTCLEAR2(WM_NATION_Grado)
    WM_CLEARPORTRAIT(0, 0x0100, 0)
    STAL(32)
    TEXTCONT

    // wait for talk locked
    TEXTEND
    STAL(30)
    WM_MOVECAM2(0, 48, 0, 0, 60, 0)
    STAL(60)
    WM_SHOWPORTRAIT(0, 0x0054, 0x02BC, 0)
    STAL(6)
    STAL(26)
    WM_HIGHLIGHT(WM_NATION_Carcino)
    TEXTCONT

    // wait for talk locked
    TEXTEND
    STAL(30)
    WM_HIGHLIGHTCLEAR1(WM_NATION_Carcino)
    WM_HIGHLIGHTCLEAR2(WM_NATION_Carcino)
    WM_CLEARPORTRAIT(0, 0x0100, 0)
    STAL(32)
    TEXTCONT
    TEXTEND
    STAL(30)
    TEXTCONT
    TEXTEND
    STAL(30)
    TEXTCONT
    TEXTEND
    STAL(30)
    WM_MOVECAM2(0, 0, 0, 48, 60, 0)
    STAL(60)
    WM_SHOWPORTRAIT(0, 0x0040, 0x02BC, 0)
    STAL(6)
    STAL(26)
    WM_HIGHLIGHT(WM_NATION_Grado)
    TEXTCONT
    TEXTEND
    TEXTCONT
    TEXTEND
    WM_HIGHLIGHTCLEAR1(WM_NATION_Grado)
    WM_HIGHLIGHTCLEAR2(WM_NATION_Grado)
    WM_CLEARPORTRAIT(0, 0x0100, 0)
    STAL(32)
    WM_MOVECAM2(0, 48, 0, 24, 60, 0)
    STAL(60)
    WM_SHOWPORTRAIT(0, 0x0051, 0x02BC, 0)
    STAL(6)
    STAL(26)
    WM_HIGHLIGHT(WM_NATION_Renais)
    TEXTCONT
    TEXTEND
    WM_HIGHLIGHTCLEAR1(WM_NATION_Renais)
    WM_HIGHLIGHTCLEAR2(WM_NATION_Renais)
    WM_CLEARPORTRAIT(0, 0x0100, 0)
    STAL(32)
    WM_MOVECAM2(0, 24, 0, 40, 52, 0)
    STAL(62)
    WM_PLACEDOT(0, 0, WM_NODE_RenaisCastle, 1)
    WM_PLACEDOT(0, 1, WM_NODE_GradoKeep, 1)
    STAL(60)
    PUTSPRITE(WM_MU_2, CLASS_SOLDIER, WM_FACTION_RED, WM_NODE_GradoKeep)
    PUTSPRITE(WM_MU_3, CLASS_SOLDIER, WM_FACTION_RED, WM_NODE_GradoKeep)
    PUTSPRITE(WM_MU_4, CLASS_SOLDIER, WM_FACTION_RED, WM_NODE_GradoKeep)
    WM_PUTMOVINGSPRITE(WM_MU_2, 0, 0x73, 0x84, 0x55, 0x41, 210, 0x3, 10)
    WM_PUTMOVINGSPRITE(WM_MU_3, 0, 0x84, 0x84, 0x76, 0x57, 170, 0x3, 10)
    WM_PUTMOVINGSPRITE(WM_MU_4, 0, 0x95, 0x84, 0x86, 0x64, 150, 0x3, 10)
    STAL(20)
    TEXTCONT
    TEXTEND
    WM_WAITFORSPRITES(WM_MU_ANY)
    WM_REMSPRITE(WM_MU_2)
    WM_REMSPRITE(WM_MU_3)
    WM_REMSPRITE(WM_MU_4)
    STAL(30)
    WM_SHOWPORTRAIT(0, 0x0014, 0x0534, 0)
    STAL(6)
    STAL(60)
    PUTSPRITE(WM_MU_2, CLASS_EPHRAIM_LORD, WM_FACTION_BLUE, WM_NODE_AdlasPlains)
    WM_PUTMOVINGSPRITE(WM_MU_2, 0, 0x5c, 0x64, 0x5c, 0x6c, 180, 0x3, 16)
    TEXTCONT
    TEXTEND
    WM_WAITFORSPRITES(WM_MU_ANY)
    WM_REMSPRITE(WM_MU_2)
    WM_CLEARPORTRAIT(0, 0x0200, 0)
    STAL(46)
    PUTSPRITE(WM_MU_6, CLASS_EIRIKA_LORD, WM_FACTION_BLUE, WM_NODE_RenaisCastle)
    PUTSPRITE(WM_MU_5, CLASS_PEER, WM_FACTION_BLUE, WM_NODE_RenaisCastle)
    PUTSPRITE(WM_MU_2, CLASS_GENERAL, WM_FACTION_RED, WM_NODE_GradoKeep)
    PUTSPRITE(WM_MU_3, CLASS_MAGE_KNIGHT_F, WM_FACTION_RED, WM_NODE_GradoKeep)
    PUTSPRITE(WM_MU_4, CLASS_WYVERN_KNIGHT, WM_FACTION_RED, WM_NODE_GradoKeep)
    WM_PUTMOVINGSPRITE(WM_MU_2, 0, 0x84, 0x84, 0x6c, 0x5c, 210, 0x1, 0)
    WM_PUTMOVINGSPRITE(WM_MU_3, 0, 0x73, 0x92, 0x5b, 0x56, 210, 0x1, 0)
    WM_PUTMOVINGSPRITE(WM_MU_4, 0, 0x95, 0x92, 0x7d, 0x56, 210, 0x1, 0)
    TEXTCONT
    TEXTEND
    WM_WAITFORSPRITES(WM_MU_ANY)
    STAL(26)
    WM_PUTSPRITE(WM_MU_6, 0x63, 0x45)
    WM_PUTSPRITE(WM_MU_5, 0x6c, 0x4c)
    WM_FADEINSPRITE(WM_MU_6, 60)
    WM_FADEINSPRITE(WM_MU_5, 60)
    TEXTCONT
    TEXTEND
    WM_WAITFORSPRITELOAD
    WM_REMOVETEXT
    STAL(2)
    FADI(16)
    SKIPWN
    WM_FXCLEAR1(-0x1)
    WM_FXCLEAR2(-0x1)
    WM_REMSPRITE(WM_MU_2)
    WM_REMSPRITE(WM_MU_3)
    WM_REMSPRITE(WM_MU_4)
    WM_REMSPRITE(WM_MU_5)
    WM_REMSPRITE(WM_MU_6)
    ENDA
};

CONST_DATA EventScr EventScrWM_Prologue_ChapterIntro[] = {
    EVBIT_MODIFY(0x1)
    ENUT(137)
    ENDA
};
/* End prologue-wm.h */

/* Begin prologue-eventscript.h */
#include "global.h"
#include "bmguide.h"
#include "bmunit.h"
#include "event.h"
#include "eventinfo.h"
#include "eventcall.h"
#include "coSelect.h"
#include "EAstdlib.h"
#include "constants/characters.h"
#include "constants/classes.h"
#include "constants/backgrounds.h"
#include "constants/items.h"
#include "constants/songs.h"
#include "constants/chapters.h"
#include "constants/msg.h"
#include "power.h"

#if FE8_CUSTOM_CAMPAIGN



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
#if DEBUG_TESTING
    {
        .charIndex = 0x80,
        .classIndex = CLASS_SOLDIER,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 0,
        .yPosition = 3,
        .items = {
            ITEM_LANCE_IRON,
        },
        .ai = {0x0, 3, 0x2, 0x1},
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_MAGE,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 1,
        .yPosition = 3,
        .items = {
            ITEM_ANIMA_FIRE,
        },
        .ai = {0x0, 3, 0x2, 0x1},
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_ARCHER,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 2,
        .yPosition = 3,
        .items = {
            ITEM_BOW_IRON,
        },
        .ai = {0x0, 3, 0x2, 0x1},
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_CAVALIER,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 3,
        .yPosition = 3,
        .items = {
            ITEM_SWORD_IRON,
            ITEM_LANCE_IRON,
        },
        .ai = {0x0, 3, 0x2, 0x1},
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_ARMOR_KNIGHT,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 4,
        .yPosition = 2,
        .items = {
            ITEM_LANCE_IRON,
        },
        .ai = {0x0, 3, 0x2, 0x1},
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_FIGHTER,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 4,
        .yPosition = 1,
        .items = {
            ITEM_AXE_IRON,
        },
        .ai = {0x0, 3, 0x2, 0x1},
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_MERCENARY,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 4,
        .yPosition = 0,
        .items = {
            ITEM_SWORD_IRON,
        },
        .ai = {0x0, 3, 0x2, 0x1},
    },
#endif

    { 0 },
};

static void SetFactionCoFromSlots(void)
{
    SetFactionCo(gEventSlots[EVT_SLOT_1], gEventSlots[EVT_SLOT_2]);
}

CONST_DATA EventListScr EventScr_Prologue_BeginningScene_Custom[] = {
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
#endif

CONST_DATA EventListScr EventScr_Prologue_BeginningScene[] = {
    CALL(EventScr_Prologue_RenaisThroneCutscene)
    SVAL(EVT_SLOT_2, EventScr_Prologue_EirikaAttacked)
    CALL(EventScr_CallOnTutorialMode)
    CHECK_TUTORIAL
    BNE(0x0, EVT_SLOT_C, EVT_SLOT_0)
    ASMC(BmGuideTextSetAllGreen)

LABEL(0x0)
    ENUT(0x8)
    LOAD1(1, UnitDef_Event_PrologueAlly)
    ENUN
    SVAL(EVT_SLOT_1, 13)
    SET_HP(CHARACTER_SETH)
    FlashCursor(CHARACTER_EIRIKA, 60)
    MUSI
    Text_BG(BG_PLAIN_2, 0x90D)
    MUNO
    MOVE(0x18, CHARACTER_SETH, 4, 4)
    ENUN
    FlashCursor(CHARACTER_SETH, 60)
    Text(0x90E)
    SVAL(EVT_SLOT_2, EventScr_Prologue_ExecTut) /* This scr ends at ENDB! */
    CALL(EventScr_CallOnTutorialMode)

    /* Not exec if tutorial */
    MOVE_CLOSEST(0x0, CHARACTER_EIRIKA, 4, 5)
    ENUN
    CALL(EventScr_Prologue_GiveRapier)
    CALL(EventScr_Prologue_ONeillSpawn)
    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_RenaisThroneCutscene[] = {
    SVAL(EVT_SLOT_B, 0x000A000E)
    LOMA(CHAPTER_E_16)
    LOAD2(1, UnitDef_Event_PrologueThroneRoomUnits)
    ENUN
    FADU(16)
    MUSC(SONG_RAID)
    BROWNBOXTEXT(0x664, 8, 8)

    /* WTF we load Ephraim as the messager... */
    LOAD1(1, UnitDef_Event_PrologueMessager)
    ENUN
    CAMERA(0xE, 0x0)
    FlashCursor(CHARACTER_EPHRAIM, 60)
    Text(0x903)
    MOVE(0, CHARACTER_EPHRAIM, 0xD, 0xB)
    ENUN
    DISA(CHARACTER_EPHRAIM)

    MOVE_1STEP(0, CHARACTER_EIRIKA, FACING_LEFT)
    ENUN
    FlashCursor(CHARACTER_EIRIKA, 60)
    Text(0x904)

    /* Seth pick Eirika and run */
    MOVEONTO(0, CHARACTER_SETH, CHARACTER_EIRIKA)
    ENUN
    DISA(CHARACTER_EIRIKA)
    FlashCursor(CHARACTER_SETH, 60)
    Text(0x905)
    MOVE(0, CHARACTER_SETH, 0xD, 0xB)

    /* sD is used as queue length */
    SVAL(EVT_SLOT_D, 0)
    SVAL(EVT_SLOT_1, 0x010C)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x0)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x2CC)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x0)
    SAVETOQUEUE
    MOVE_DEFINED(CHARACTER_FRANZ)
    ENUN

    DISA(CHARACTER_SETH)
    DISA(CHARACTER_FRANZ)

    /* generals move in to protect the king */
    MOVE(0, CHARACTER_MOULDER, 11, 4)
    MOVE(0, CHARACTER_VANESSA, 15, 4)
    ENUN
    MOVE_1STEP(0, CHARACTER_MOULDER, FACING_RIGHT)
    MOVE_1STEP(0, CHARACTER_VANESSA, FACING_LEFT)
    ENUN

    LOAD1(1, UnitDef_Event_PrologueGradoShamans)
    ENUN
    LOAD1(1, UnitDef_Event_PrologueGradoCavalry)
    ENUN
    LOAD1(1, UnitDef_Event_PrologueGradoRoyals)
    ENUN

    FlashCursor(CHARACTER_FADO, 60)
    TEXTSTART
    TEXTSHOW(0x906) /* Ephraim, Eirika...You must survive. */
    TEXTEND
    FADI(2)
    REMA

    /* Load to new map */
    EVBIT_F(0x2)
    CLEA CLEE CLEN
    SVAL(EVT_SLOT_B, 0x00000000)
    LOMA(CHAPTER_40)
    FADU(16)

    LOAD2(1, UnitDef_Event_PrologueEscapees)
    ENUN
    FlashCursor(CHARACTER_SETH, 60)
    Text_BG(BG_PLAIN_2, 0x907)

    /* Franz run */
    SVAL(EVT_SLOT_D, 0)
    SVAL(EVT_SLOT_1, 0x104)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x0)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x84)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x0)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x80)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x0)
    SAVETOQUEUE
    MOVE_DEFINED(CHARACTER_FRANZ)
    ENUN
    DISA(CHARACTER_FRANZ)

    FlashCursor(CHARACTER_SETH, 60)
    Text_BG(BG_PLAIN_2, 0x908) /* behind me */

    LOAD1(1, UnitDef_Event_PrologueValterGroup)
    ENUN
    MOVE_1STEP(0, CHARACTER_SETH, FACING_RIGHT)
    ENUN
    MOVE_1STEP(0, CHARACTER_EIRIKA, FACING_LEFT)
    ENUN

    FlashCursor(CHARACTER_VALTER_PROLOGUE, 60)
    Text_BG(BG_PLAIN_2, 0x909)
    MOVE_1STEP(0, CHARACTER_VALTER_PROLOGUE, FACING_LEFT)
    ENUN

    StartBattle
    MissedAttack(0, 0)
    NormalDamage(1, 0)
    EndAttack
    FIGHT(CHARACTER_SETH, CHARACTER_VALTER_PROLOGUE, 0, false)

    FlashCursor(CHARACTER_SETH, 60)
    Text(0x90B)

    /* Seth 'rescues' Eirika */
    MOVE_1STEP(8, CHARACTER_SETH, FACING_LEFT)
    ENUN
    DISA(CHARACTER_EIRIKA)

    SVAL(EVT_SLOT_D, 0)
    SVAL(EVT_SLOT_1, 0x18104)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x0)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x18084)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x0)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x18080)
    SAVETOQUEUE
    SVAL(EVT_SLOT_1, 0x0)
    SAVETOQUEUE
    MOVE_DEFINED(CHARACTER_SETH)
    ENUN
    DISA(CHARACTER_SETH)

    FlashCursor(CHARACTER_VALTER_PROLOGUE, 60)
    Text(0x90C)

    /* Load to new map */
    FADI(16)
    EVBIT_F(0x2)
    CLEA CLEE CLEN
    SVAL(EVT_SLOT_B, 0x00000000)
    LOMA(CHAPTER_L_PROLOGUE)
    FADU(16)

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_GiveRapier[] = {
    FlashCursor(CHARACTER_SETH, 60)
    Text(0x90F)
    CALL(EventScr_RemoveBGIfNeeded)

    /* Give item via slot3 */
    SVAL(EVT_SLOT_3, ITEM_SWORD_RAPIER)
    GIVEITEMTO(CHARACTER_EIRIKA)

    SVAL(EVT_SLOT_2, EventScr_Prologue_9EF828)
    CALL(EventScr_CallOnTutorialMode)
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_ONeillSpawn[] = {
    LOAD1(1, UnitDef_Event_PrologueEnemy)
    ENUN
    FlashCursor(CHARACTER_ONEILL, 60)
    MUSC(SONG_SHADOW_OF_THE_ENEMY)
    Text(0x910)
    ENUF(EVFLAG_BGM_CHANGE)
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_OneEnemyLeft[] = {
    CHECK_ENEMIES
    SVAL(EVT_SLOT_7, 1)
    BNE(0x0, EVT_SLOT_C, EVT_SLOT_7)

    CUMO_CHAR(CHARACTER_SETH)
    STAL(60)
    CURE
    TEXTSTART
    TEXTSHOW(0x913)
    TEXTEND
    REMA
    /* this unsets the event ID so the next turn Oneill will agro (see TURN events) */
    ENUF(EVFLAG_TMP(8))
    GOTO(0x1)

LABEL(0x0)
    CHECK_EVENTID_
    SADD(EVT_SLOT_2, EVT_SLOT_C, EVT_SLOT_0)
    ENUF_SLOT2

LABEL(0x1)
    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_ONeillAttack[] = {
    MUSC(SONG_SHADOW_OF_THE_ENEMY)
    Text(0x914)
    CHECK_TUTORIAL
    BNE(0x0, EVT_SLOT_C, EVT_SLOT_0)

    /* slot1 saves the (u8)( (AI1 << 8) | AI2 ) */
    SVAL(EVT_SLOT_1, 0x0)
    CHAI(CHARACTER_ONEILL)

LABEL(0x0)
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

    ENUT(0xE0)
    ENUT(0xE1)
    ENUT(0xB7)
    ENUT(0xB4)
    ENUT(0xB5)
    ENUT(0xDC)
    ENUT(0xB9)
    ENUT(0xC2)
    ENUT(0xC3)
    ENUT(0xE7)
    ENUT(0xC9)

    MNC2(0x1)
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_EirikaAttacked[] = {
    DISABLEOPTIONS(EVENT_MENUOVERRIDE_OPTIONS | EVENT_MENUOVERRIDE_END)
    ENUT(0x66) /* Disable objective window */
    ENUT(0xE0) /* Guide:Suspend */
    ENUT(0xE1) /* Guide:Save */
    ENUT(EVFLAG_BGM_CHANGE)

    StartBattle
    MissedAttack(0, 0)
    NormalDamage(1, 0)
    NormalDamage(1, 0)
    EndAttack
    FIGHT_SCRIPT

    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Turn1[] = {
    SVAL(EVT_SLOT_2, EventScr_Prologue_ONeillSpawn)
    CALL(EventScr_CallOnTutorialMode)

    SVAL(EVT_SLOT_2, EventScr_Prologue_TutMessageTurn1)
    CALL(EventScr_CallOnTutorialMode)

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Turn2[] = {
    SVAL(EVT_SLOT_2, EventScr_Prologue_TutMessageTurn2)
    CALL(EventScr_CallOnTutorialMode)

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Prologue_Turn3[] = {
    SVAL(EVT_SLOT_2, EventScr_Prologue_OneillSethBattle)
    CALL(EventScr_CallOnTutorialMode)

    SVAL(EVT_SLOT_2, EventScr_Prologue_TutEirikaAttack)
    CALL(EventScr_CallOnTutorialMode)

    NoFade
    ENDA
};
/* End prologue-eventscript.h */

/* Begin prologue-eventinfo.h */
#include "global.h"
#include "bmtrap.h"
#include "bmunit.h"
#include "chapterdata.h"
#include "eventinfo.h"
#include "eventcall.h"
#include "EAstdlib.h"
#include "constants/event-flags.h"

CONST_DATA EventListScr EventListScr_Prologue_Turn[] = {
    TURN(0x0, EventScr_Prologue_Turn1, 1, 0, FACTION_RED)
    TURN(0x0, EventScr_Prologue_Turn2, 2, 0, FACTION_BLUE)
    TURN(0x0, EventScr_Prologue_Turn3, 3, 0, FACTION_BLUE)
    TURN(EVFLAG_TMP(8), EventScr_Prologue_ONeillAttack, 1, 255, FACTION_RED)
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
    AFEV(EVFLAG_TMP(7), EventScr_Prologue_OneEnemyLeft, 0)
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
    EventScr_Prologue_Tutorial0,
    EventScr_Prologue_Tutorial1,
    EventScr_Prologue_Tutorial2,
    EventScr_Prologue_Tutorial3,
    EventScr_Prologue_Tutorial4,
    EventScr_Prologue_Tutorial5,
    EventScr_Prologue_Tutorial6,
    EventScr_Prologue_Tutorial7,
    EventScr_Prologue_Tutorial8,
    EventScr_Prologue_Tutorial9,
    EventScr_Prologue_TutorialA,
    EventScr_Prologue_TutorialB,
    EventScr_Prologue_TutorialC,
    EventScr_Prologue_TutorialD,
    EventScr_Prologue_TutorialE,
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

    .playerUnitsInNormal = UnitDef_Event_PrologueAlly,
    .playerUnitsInHard   = UnitDef_Event_PrologueAlly,

    .playerUnitsChoice1InEncounter = NULL,
    .playerUnitsChoice2InEncounter = NULL,
    .playerUnitsChoice3InEncounter = NULL,

    .enemyUnitsChoice1InEncounter = NULL,
    .enemyUnitsChoice2InEncounter = NULL,
    .enemyUnitsChoice3InEncounter = NULL,

#if FE8_CUSTOM_CAMPAIGN
    .beginningSceneEvents = EventScr_Prologue_BeginningScene_Custom,
#else
    .beginningSceneEvents = EventScr_Prologue_BeginningScene,
#endif
    .endingSceneEvents    = EventScr_Prologue_EndingScene,
};
/* End prologue-eventinfo.h */
