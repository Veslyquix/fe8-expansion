#pragma once

/* Begin ch1-eventudefs.h */
#include "global.h"
#include "muctrl.h"
#include "eventcall.h"
#include "constants/characters.h"
#include "constants/classes.h"
#include "constants/items.h"

CONST_DATA struct REDA REDA_Ch1Ally_Eirika[] = {
    {
        .x = 12,
        .y = 9,
    },
};
CONST_DATA struct REDA REDA_Ch1Ally_Seth[] = {
    {
        .x = 13,
        .y = 8,
    },
};
CONST_DATA struct REDA REDA_Ch1_0[] = {
    {
        .x = 2,
        .y = 5,
        .flags = 0x18,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_Ch1_1[] = {
    {
        .x = 1,
        .y = 6,
        .flags = 0x18,
        .b = 0xffff,
        .delayFrames = 16,
    },
};
CONST_DATA struct REDA REDA_Ch1_2[] = {
    {
        .x = 3,
        .y = 8,
        .flags = 0x18,
        .b = 0xfffe,
        .delayFrames = 16,
    },
    {
        .x = 3,
        .y = 6,
        .flags = 0x18,
        .b = 0xfffe,
    },
};
CONST_DATA struct REDA REDA_Ch1_3[] = {
    {
        .x = 2,
        .y = 7,
        .flags = 0x18,
        .b = 0xffff,
        .delayFrames = 32,
    },
};
CONST_DATA struct REDA REDA_Ch1_4[] = {
    {
        .x = 1,
        .y = 8,
        .flags = 0x18,
        .a = 0x46,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_Ch1_5[] = {
    {
        .x = 3,
        .y = 8,
        .flags = 0x18,
        .a = 0x46,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_Ch1_6[] = {
    {
        .x = 2,
        .y = 9,
        .flags = 0x18,
        .a = 0x46,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_Ch1_Franz[] = {
    {
        .x = 5,
        .y = 1,
    },
};
CONST_DATA struct REDA REDA_Ch1_Gilliam[] = {
    {
        .x = 6,
        .y = 1,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_Ch1_7[] = {
    {
        .x = 13,
        .y = 8,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_Ch1_8[] = {
    {
        .x = 13,
        .y = 9,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_Ch1_9[] = {
    {
        .x = 12,
        .y = 9,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_Ch1_NpcCavalier[] = {
    {
        .x = 2,
        .y = 3,
        .b = 0xffff,
    },
    {
        .x = 0,
        .y = 3,
        .b = 0xffff,
    },
    {
        .x = 0,
        .y = 0,
        .b = 0xffff,
    },
};
CONST_DATA struct REDA REDA_Ch1_NpcMercenary[] = {
    {
        .x = 2,
        .y = 2,
        .a = 0xc1,
    },
};

// 0x88B40A0
CONST_DATA struct UnitDefinition UnitDef_Event_Ch1Ally[] = {
    {
        .charIndex = CHARACTER_EIRIKA,
        .classIndex = CLASS_EIRIKA_LORD,
        .leaderCharIndex = CHARACTER_EIRIKA,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .xPosition = 14,
        .yPosition = 9,
        .redaCount = 1,
        .redas = REDA_Ch1Ally_Eirika,
        .items = {
            ITEM_SWORD_RAPIER,
            ITEM_VULNERARY,
        },
    },
    // {
        // .charIndex = CHARACTER_SETH,
        // .classIndex = CLASS_PALADIN,
        // .leaderCharIndex = CHARACTER_EIRIKA,
        // .allegiance = FACTION_ID_BLUE,
        // .level = 1,
        // .xPosition = 14,
        // .yPosition = 9,
        // .redaCount = 1,
        // .redas = REDA_Ch1Ally_Seth,
        // .items = {
            // ITEM_SWORD_STEEL,
            // ITEM_LANCE_SILVER,
            // ITEM_VULNERARY,
        // },
    // },
    { 0 },
};

// 0x88B40DC
CONST_DATA struct UnitDefinition UnitDef_Event_Ch1Enemy[] = {
    {
        .charIndex = CHARACTER_BREGUET,
        .classIndex = CLASS_ARMOR_KNIGHT,
        .leaderCharIndex = CHARACTER_BREGUET,
        .allegiance = FACTION_ID_RED,
        .level = 4,
        .xPosition = 2,
        .yPosition = 9,
        .redaCount = 1,
        .redas = REDA_Ch1_0,
        .items = {
            ITEM_LANCE_IRON,
        },
        .ai = {0x3, 0x3, 0x9, 0x20},
    },
    // {
        // .charIndex = 0x80,
        // .classIndex = CLASS_SOLDIER,
        // .leaderCharIndex = CHARACTER_BREGUET,
        // .autolevel = 1,
        // .allegiance = FACTION_ID_RED,
        // .level = 2,
        // .xPosition = 1,
        // .yPosition = 9,
        // .redaCount = 1,
        // .redas = REDA_Ch1_1,
        // .items = {
            // ITEM_LANCE_IRON,
        // },
        // .ai = {0x0, 0x3, 0x9, 0x0},
    // },
    // {
        // .charIndex = 0x80,
        // .classIndex = CLASS_SOLDIER,
        // .leaderCharIndex = CHARACTER_BREGUET,
        // .autolevel = 1,
        // .allegiance = FACTION_ID_RED,
        // .level = 2,
        // .xPosition = 2,
        // .yPosition = 9,
        // .redaCount = 2,
        // .redas = REDA_Ch1_2,
        // .items = {
            // ITEM_LANCE_IRON,
        // },
        // .ai = {0x0, 0x3, 0x9, 0x0},
    // },
    // {
        // .charIndex = 0x80,
        // .classIndex = CLASS_SOLDIER,
        // .leaderCharIndex = CHARACTER_BREGUET,
        // .autolevel = 1,
        // .allegiance = FACTION_ID_RED,
        // .level = 3,
        // .xPosition = 2,
        // .yPosition = 9,
        // .redaCount = 1,
        // .redas = REDA_Ch1_3,
        // .items = {
            // ITEM_LANCE_IRON,
        // },
        // .ai = {0x3, 0x12, 0x1, 0x0},
    // },
    // {
        // .charIndex = 0x80,
        // .classIndex = CLASS_FIGHTER,
        // .leaderCharIndex = CHARACTER_BREGUET,
        // .autolevel = 1,
        // .allegiance = FACTION_ID_RED,
        // .level = 2,
        // .xPosition = 1,
        // .yPosition = 9,
        // .redaCount = 1,
        // .redas = REDA_Ch1_4,
        // .items = {
            // ITEM_AXE_IRON,
        // },
        // .ai = {0x0, 0x0, 0x1, 0x0},
    // },
    // {
        // .charIndex = 0x80,
        // .classIndex = CLASS_FIGHTER,
        // .leaderCharIndex = CHARACTER_BREGUET,
        // .autolevel = 1,
        // .allegiance = FACTION_ID_RED,
        // .level = 2,
        // .xPosition = 2,
        // .yPosition = 9,
        // .redaCount = 1,
        // .redas = REDA_Ch1_5,
        // .items = {
            // ITEM_AXE_IRON,
        // },
        // .ai = {0x0, 0x0, 0x1, 0x0},
    // },
    // {
        // .charIndex = 0x80,
        // .classIndex = CLASS_FIGHTER,
        // .leaderCharIndex = CHARACTER_BREGUET,
        // .autolevel = 1,
        // .allegiance = FACTION_ID_RED,
        // .level = 2,
        // .xPosition = 2,
        // .yPosition = 9,
        // .redaCount = 1,
        // .redas = REDA_Ch1_6,
        // .items = {
            // ITEM_AXE_IRON,
        // },
        // .ai = {0x0, 0x12, 0x1, 0x0},
    // },
    { 0 },
};

// 0x88B417C
CONST_DATA struct UnitDefinition UnitDef_Event_Ch1AllyReinforce[] = {
    // {
        // .charIndex = CHARACTER_FRANZ,
        // .classIndex = CLASS_CAVALIER,
        // .leaderCharIndex = CHARACTER_EIRIKA,
        // .allegiance = FACTION_ID_BLUE,
        // .level = 1,
        // .xPosition = 5,
        // .yPosition = 0,
        // .redaCount = 1,
        // .redas = REDA_Ch1_Franz,
        // .items = {
            // ITEM_SWORD_IRON,
            // ITEM_LANCE_IRON,
            // ITEM_VULNERARY,
            // ITEM_VULNERARY,
        // },
    // },
    // {
        // .charIndex = CHARACTER_GILLIAM,
        // .classIndex = CLASS_ARMOR_KNIGHT,
        // .allegiance = FACTION_ID_BLUE,
        // .level = 4,
        // .xPosition = 6,
        // .yPosition = 0,
        // .redaCount = 1,
        // .redas = REDA_Ch1_Gilliam,
        // .items = {
            // ITEM_LANCE_IRON,
        // },
    // },
    { 0 },
};

// 0x88B41B8
CONST_DATA struct UnitDefinition UnitDef_Event_Ch1EnemyReinforce[] = {
    {
        .charIndex = 0x80,
        .classIndex = CLASS_FIGHTER,
        .leaderCharIndex = CHARACTER_BREGUET,
        .autolevel = 1,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 14,
        .yPosition = 9,
        .redaCount = 1,
        .redas = REDA_Ch1_7,
        .items = {
            ITEM_AXE_IRON,
        },
        .ai = {0x0, 0x0, 0x9, 0x0},
    },
    {
        .charIndex = CHARACTER_SOLDIER_83,
        .classIndex = CLASS_SOLDIER,
        .leaderCharIndex = CHARACTER_BREGUET,
        .autolevel = 1,
        .allegiance = FACTION_ID_RED,
        .level = 2,
        .xPosition = 14,
        .yPosition = 9,
        .redaCount = 1,
        .redas = REDA_Ch1_8,
        .items = {
            ITEM_LANCE_IRON,
        },
        .ai = {0x0, 0x0, 0x9, 0x0},
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_FIGHTER,
        .leaderCharIndex = CHARACTER_BREGUET,
        .autolevel = 1,
        .allegiance = FACTION_ID_RED,
        .level = 1,
        .xPosition = 14,
        .yPosition = 9,
        .redaCount = 1,
        .redas = REDA_Ch1_9,
        .items = {
            ITEM_AXE_IRON,
        },
        .ai = {0x0, 0x0, 0x9, 0x0},
    },
    { 0 },
};

// 0x88B4208
CONST_DATA struct UnitDefinition UnitDef_Event_Ch1NPC[] = {
    {
        .charIndex = 0xc1,
        .classIndex = CLASS_CAVALIER,
        .allegiance = FACTION_ID_GREEN,
        .level = 1,
        .xPosition = 2,
        .yPosition = 2,
        .redaCount = 3,
        .redas = REDA_Ch1_NpcCavalier,
        .items = {
            ITEM_LANCE_IRON,
        },
    },
    {
        .charIndex = CHARACTER_FRELIAN,
        .classIndex = CLASS_MERCENARY,
        .allegiance = FACTION_ID_GREEN,
        .level = 1,
        .xPosition = 2,
        .yPosition = 2,
        .redaCount = 1,
        .redas = REDA_Ch1_NpcMercenary,
        .items = {
            ITEM_SWORD_IRON,
        },
    },
    { 0 },
};
/* End ch1-eventudefs.h */

/* Begin ch1-tutorials.h */
#include "global.h"
#include "event.h"
#include "eventinfo.h"
#include "eventcall.h"
#include "EAstdlib.h"
#include "constants/characters.h"
#include "constants/songs.h"

CONST_DATA EventListScr EventScr_Ch1Tut_GuideWTA[] = {
    /**
     * The relationship between swords, lances,
     * and axes is called the weapon triangle...
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x93D)
    TEXTEND
    REMA

    ENUT(0xBA) /* Guide:Weapon Triangle */
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_EirikaVisitHouseInit[] = {
    MUSC(SONG_DISTANT_ROADS)

    /**
     * Seth.
     * I need to know what's happening here.
     * I'm going to visit that home.
     */
    Text(0x92E)

    CURSOR_FLASHING(13, 6)
    STAL(60)
    CURE

    /**
     * It's time to visit a home. First,
     * place the cursor on Eirika
     * and press the A Button.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x93E)
    TEXTEND
    REMA

    CURSOR_FLASHING_CHAR(CHARACTER_EIRIKA)
    STAL(60)
    CURE

    EvtEnqueueConditionalTutCall(
        EventScr_Ch1Tut_EirikaVisitHouseIdle1,
        TUTORIAL_EVT_TYPE_ONSELECT)

    DISABLEOPTIONS(EVENT_MENUOVERRIDE_END)
    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_EirikaVisitHouseIdle1[] = {
    NoFade

    TutEventExecType0(
        CHARACTER_EIRIKA,
        13, 6,
        0x940,      /* Move Eirika to the house... */
        0x00080008,
        0x93F,      /* The cursor is now on Eirika... */
        0x00080008,
        EventScr_Ch1Tut_EirikaVisitHouseIdle2,
        EventScr_Ch1Tut_EirikaVisitHouseIdle1
    )
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_EirikaVisitHouseIdle2[] = {
    NoFade
    IGNORE_KEYS(0)

    TutEventExecType1(
        13, 6,
        0,
        0,
        EventScr_Ch1Tut_EirikaVisitHouseEnd,
        EventScr_Ch1Tut_EirikaVisitHouseIdle2
    )
    DISABLEOPTIONS(~EVENT_MENUOVERRIDE_VISIT)
    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_EirikaVisitHouseEnd[] = {
    NoFade
    IGNORE_KEYS(0)

    /**
     * You can get battle hints and other useful information by
     * talking to people in homes. This can be very beneficial,
     * so be sure to visit houses when you have the chance.
     * Now select Visit and press the A Button.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, _EvtParams2(0x48, 0x38))
    TEXTSHOW(0x941)
    TEXTEND
    REMA

    ENUT(0xCF) /* Guide:Houses */
    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)

    EvtEnqueueConditionalTutCall(
        EventScr_Ch1Tut_GuideTerrainHeal,
        TUTORIAL_EVT_TYPE_POSTACTION)

    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_GuideTerrainHeal[] = {
    IGNORE_KEYS(0)

    CURSOR_FLASHING(7, 7)
    CURSOR_FLASHING(7, 2)
    CURSOR_FLASHING(2, 2)
    STAL(60)
    CURE

    /**
     * Units on gates, forts, and other special areas recover Hit Points (HP) at the
     * beginning of your turn. Currently, the enemy commander, Breguet,
     * is standing on a gate. Even if he takes
     * damage, he'll soon recover some of the HP he lost.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x942)
    TEXTEND
    REMA

    ENUT(0xCE) /* Guide:Fortresses & Castle Gates */
    DISABLEOPTIONS(EVENT_MENUOVERRIDE_TRADE)
    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_OnBeginning[] = {
    FlashCursor(CHARACTER_SETH, 60)

    /**
     * Starting with this chapter, you will control not only Eirika, but also Seth,
     * general of the Knights of Renais. You select and move him in the same way
     * you do Eirika: by placing the cursor on him and pressing the A Button.
     * When all of your units have finished moving, your enemy's turn will begin
     * automatically. If Eirika, the leader of your group, falls
     * in battle, the game is over. You can choose to continue playing if any
     * of your allies fall, but defeated allies will never fight at your side again.
     * Try to move forward with the fewest number of casualties possible.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x943)
    TEXTEND
    REMA

    ENUT(0xB6) /* Guide:Game Over */
    ENUT(0xD7) /* Guide:Retreating from the Front Lines */

    /**
     * Lady Eirika, what are your orders?
     */
    Text(0x92F)
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_GuideMsg944[] = {
    /**
     * Allied units have joined the battle.
     * All allied blue units can be moved
     * in the same manner as Eirika.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x944)
    TEXTEND
    REMA

    ENUT(0xD6) /* Guide:Acquiring Items */
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_GilliamBattle[] = {
    SVAL(EVT_SLOT_1, 19)
    SET_HP(CHARACTER_GILLIAM)

    STAL(60)
    MOVE(0, CHARACTER_GILLIAM, 8, 2)
    ENUN

    StartBattle
    NormalDamage(0, 0)
    MissedAttack(1, 0)
    NormalDamage(1, 2)
    EndAttack
    SVAL(EVT_SLOT_B, _EvtParams2(8, 3))
    FIGHT(CHARACTER_GILLIAM, -1, 0, 0)

    SVAL(EVT_SLOT_2, EventScr_Ch1Tut_GuideMsg944)
    CALL(EventScr_CallOnTutorialMode)

    MOVE(0, CHARACTER_FRANZ, 8, 1)
    ENUN
    FlashCursor(CHARACTER_FRANZ, 60)

    /**
     * Sir Gilliam! Are you all right?
     * It's just a scratch.
     * Wait! I...I have a vulnerary with me.
     * Let me give it to you.
     */
    MUSI
    Text(0x933)
    MUNO

    /**
     * It's time to trade items. First,
     * place the cursor on Gilliam and
     * press the A Button.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x946)
    TEXTEND
    REMA

    CURSOR_FLASHING_CHAR(CHARACTER_GILLIAM)
    STAL(60)
    CURE

    EvtEnqueueConditionalTutCall(
        EventScr_Ch1Tut_TradeSelectGalliamIdle1,
        TUTORIAL_EVT_TYPE_ONSELECT)

    DISABLEOPTIONS(EVENT_MENUOVERRIDE_END)
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_TradeSelectGalliamIdle1[] = {
    NoFade

    TutEventExecType0(
        CHARACTER_GILLIAM,
        8, 2,
        0x947,      /* It's time to trade items... */
        _EvtParams2(0x28, 0x40),
        0x946,      /* The cursor is on Gilliam... */
        _EvtParams2(0x28, 0x40),
        EventScr_Ch1Tut_TradeSelectGalliamIdle2,
        EventScr_Ch1Tut_TradeSelectGalliamIdle1
    )
    IGNORE_KEYS(L_BUTTON | R_BUTTON | DPAD_ANY | START_BUTTON | SELECT_BUTTON | B_BUTTON)
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_TradeSelectGalliamIdle2[] = {
    NoFade
    IGNORE_KEYS(0)

    TutEventExecType1(
        8, 2,
        0,
        0,
        EventScr_Ch1Tut_TradeSelectGalliamEnd,
        EventScr_Ch1Tut_TradeSelectGalliamIdle2
    )
    DISABLEOPTIONS(~EVENT_MENUOVERRIDE_TRADE)
    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_TradeSelectGalliamEnd[] = {
    NoFade
    IGNORE_KEYS(0)

    /**
     * Now select Trade.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, _EvtParams2(72, 56))
    TEXTSHOW(0x948)
    TEXTEND
    REMA

    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)
    ENUT(0x87) /* Tutorial: Item Trade */

    /*
     * Well...
     * I have to admit with no idea how trade tutorial CTRL works...
     * Maybe the msg-0x948 can directly exec msg949 and then msg94A automatically?
     */

    EvtEnqueueConditionalTutCall(
        EventScr_Ch1Tut_AfterTrade,
        TUTORIAL_EVT_TYPE_AFTERMOVE)

    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_AfterTrade[] = {
    NoFade

    /**
     * You can use the vulnerary you received right away.
     * Select the vulnerary from your items and use it.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, _EvtParams2(72, 56))
    TEXTSHOW(0x94D)
    TEXTEND
    REMA

    ENUT(0xC7) /* 辞典:使用方法 */
    ENUT(0xC8) /* 辞典:物品交换 */

    EvtEnqueueConditionalTutCall(
        EventScr_Ch1Tut_PostTradeAndItemUseAction,
        TUTORIAL_EVT_TYPE_POSTACTION)

    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_PostTradeAndItemUseAction[] = {
    FlashCursor(CHARACTER_FRANZ, 60)
    Text(0x932) /* Thanks, lad.Please.. */
    DISABLEOPTIONS(0)
    CALL(EventScr_Ch1Tut_MsgOnGuideOption)
    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_GuideMsgSeize[] = {
    /**
     * You defeated Breguet, commander of Grado's forces in Mulan.
     * All that remains is to seize the castle gate.
     * Only your commander can perform this task.
     * The commander of this group is Eirika.
     * Move her to the castle gate, seize it, and clear this map.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x945)
    TEXTEND
    REMA

    ENUT(0xDD) /* 辞典:占领 */

    CURSOR_FLASHING(2, 2)
    STAL(60)
    CURE

    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_ChooseSethTurn1[] = {
    /**
     * Place the cursor on Seth and press the A Button.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x94E)
    TEXTEND
    REMA

    CURSOR_FLASHING_CHAR(CHARACTER_SETH)
    STAL(60)
    CURE

    StartBattle
    NormalDamage(0, 0)
    NormalDamage(1, 0)
    CriticalHit(0, 0)
    EndAttack
    FIGHT_SCRIPT

    EvtEnqueueConditionalTutCall(
        EventScr_Ch1Tut_SethMoveToEnemy,
        TUTORIAL_EVT_TYPE_ONSELECT)

    DISABLEOPTIONS(EVENT_MENUOVERRIDE_END | EVENT_MENUOVERRIDE_OPTIONS)
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_SethMoveToEnemy[] = {
    NoFade

    TutEventExecType0(
        CHARACTER_SETH,
        9, 6,
        0x950,      /* Seth must move near his foe... */
        _EvtParams2(8, 8),
        0x94F,      /* The cursor is now on Seth... */
        _EvtParams2(8, 8),
        EventScr_Ch1Tut_BeforeSethMoveToEnemy,
        EventScr_Ch1Tut_SethMoveToEnemy
    )
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_BeforeSethMoveToEnemy[] = {
    NoFade
    IGNORE_KEYS(0)

    TutEventExecType1(
        9, 6,
        0x950,
        _EvtParams2(8, 8),
        EventScr_Ch1Tut_AfterSethMoveToEnemy,
        EventScr_Ch1Tut_BeforeSethMoveToEnemy
    )
    DISABLEOPTIONS(~EVENT_MENUOVERRIDE_ATTACK)
    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_AfterSethMoveToEnemy[] = {
    NoFade
    IGNORE_KEYS(0)

    /**
     * The enemy has an axe, so it's best to counter with a sword.
     * Choose Attack and press the A Button.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, _EvtParams2(72, 56))
    TEXTSHOW(0x952)
    TEXTEND
    REMA

    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)
    DISABLEWEAPONS(EVENT_MENUOVERRIDE_WEAPON2)

    EvtEnqueueConditionalTutCall(
        EventScr_Ch1Tut_GuideOnBKSEL,
        TUTORIAL_EVT_TYPE_FORECAST)

    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_GuideOnBKSEL[] = {
    NoFade
    IGNORE_KEYS(R_BUTTON)

    /**
     * This is the combat information window.
     * At the top of the window, next to Seth's name, is a
     * weapon and an arrow pointing up. This is because
     * Seth has a sword, while the soldier has an axe.
     * The weapon triangle states that swords are strong
     * against axes. Seth is at an advantage.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, _EvtParams2(84, 16))
    TEXTSHOW(0x951)
    TEXTEND
    REMA

    IGNORE_KEYS(R_BUTTON | START_BUTTON | B_BUTTON)

    EvtEnqueueConditionalTutCall(
        EventScr_Ch1Tut_AfterSethBattleEirikaVisit,
        TUTORIAL_EVT_TYPE_POSTACTION)

    NoFade
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_AfterSethBattleEirikaVisit[] = {
    NoFade
    IGNORE_KEYS(0)
    EvtEnqueueCallDirectly(EventScr_Ch1Tut_EirikaVisitHouseInit)
    ENDA
};

CONST_DATA EventListScr EventScr_Ch1Tut_MsgOnGuideOption[] = {
    /**
     * Move the cursor to an unoccupied space on the map, and press the
     * A Button to open the map menu. The third item from the top is Guide.
     * Try selecting it.
     * The guide contains lots of useful game-play information.
     * If you run into something that seems unclear, review the guide
     * for a quick reference.
     */
    TUTORIALTEXTBOXSTART
    SVAL(EVT_SLOT_B, -1)
    TEXTSHOW(0x953)
    TEXTEND
    REMA

    ENDA
};
/* End ch1-tutorials.h */

/* Begin ch1-wm.h */
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
/* End ch1-wm.h */

/* Begin ch1-eventscript.h */
#include "global.h"
#include "event.h"
#include "eventinfo.h"
#include "eventcall.h"
#include "EAstdlib.h"
#include "constants/characters.h"
#include "constants/backgrounds.h"
#include "constants/songs.h"


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
        .items = {
            ITEM_STAFF_NOSTAL,
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
        .items = {
            ITEM_BOW_IRON,
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
    LOAD1(1, UnitDef_Event_Ch1Asin)
    ENUN
    FlashCursor(CHARACTER_MOULDER, 60)
    Text(MSG_CC_CH1A_REINFORCEMENT)

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
/* End ch1-eventscript.h */

/* Begin ch1-eventinfo.h */
#include "global.h"
#include "event.h"
#include "eventinfo.h"
#include "eventcall.h"
#include "EAstdlib.h"
#include "bmtrap.h"
#include "chapterdata.h"
#include "constants/event-flags.h"
#include "constants/characters.h"

CONST_DATA EventListScr EventListScr_Ch1_Turn[] = {
    // TURN(0x0, EventScr_Ch1_Turn1Player, 1, 1, FACTION_BLUE)
    // TURN(0x0, EventScr_Ch1_Turn1Enemy, 1, 1, FACTION_RED)
    TURN(0x0, EventScr_Ch1_Turn_AllyReinforceArrive, 2, 2, FACTION_RED)
    // TURN(EVFLAG_TMP(11), EventScr_Ch1_Turn_EnemyReinforceArrive, 1, 255, FACTION_BLUE)
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Ch1_Character[] = {
    // CharacterEventBothWays(0x8, EventScr_Ch1_Talk_SethFranz, CHARACTER_SETH, CHARACTER_FRANZ)
    // CharacterEventBothWays(0x9, EventScr_Ch1_Talk_EirikaFranz, CHARACTER_EIRIKA, CHARACTER_FRANZ)
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Ch1_Location[] = {
    // House(0x0, EventScr_Ch1_Loca_Visit1, 13, 6)
    // House(0x0, EventScr_Ch1_Loca_Visit2, 10, 4)
    // Seize(2, 2)
    END_MAIN
};

CONST_DATA EventListScr EventListScr_Ch1_Misc[] = {
    // AFEV(EVFLAG_TMP(7), EventScr_Ch1_Misc_DefeatBoss, EVFLAG_DEFEAT_BOSS)
    // AREA(EVFLAG_TMP(10), EventScr_Ch1_Misc_Area, 0, 0, 7, 9)
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
    EventScr_Ch1Tut_EirikaVisitHouseIdle1,
    EventScr_Ch1Tut_EirikaVisitHouseIdle2,
    EventScr_Ch1Tut_EirikaVisitHouseEnd,
    EventScr_Ch1Tut_GuideTerrainHeal,
    EventScr_Ch1Tut_TradeSelectGalliamIdle1,
    EventScr_Ch1Tut_TradeSelectGalliamIdle2,
    EventScr_Ch1Tut_TradeSelectGalliamEnd,
    EventScr_Ch1Tut_AfterTrade,
    EventScr_Ch1Tut_PostTradeAndItemUseAction,
    EventScr_Ch1Tut_SethMoveToEnemy,
    EventScr_Ch1Tut_BeforeSethMoveToEnemy,
    EventScr_Ch1Tut_AfterSethMoveToEnemy,
    EventScr_Ch1Tut_GuideOnBKSEL,
    EventScr_Ch1Tut_AfterSethBattleEirikaVisit,
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

    .playerUnitsInNormal = UnitDef_Event_Ch1Ally,
    .playerUnitsInHard   = UnitDef_Event_Ch1Ally,

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
