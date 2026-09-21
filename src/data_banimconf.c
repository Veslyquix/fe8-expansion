#include "global.h"
#include "bmitem.h"
#include "ekrbattle.h"
#include "constants/items.h"

CONST_DATA struct BattleAnimDef AnimConf_0[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0001,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0002,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_1[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0003,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0004,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_2[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0005,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0007,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_3[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0008,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x000A,
    },
    { 0 }
};

/* FE8_NEW_ANIMS: custom animation set from an FE-Repo pack (see CREDITS.md).
 * NOTE: .index is ONE-BASED -- GetBattleAnimationId (src/banim-ekrcmd.c)
 * returns idx - 1, so banim_data[] slot == .index - 1. Ranged axes match on
 * exact item id (wtype < 0x100, first pass) rather than weapon type. */
CONST_DATA struct BattleAnimDef AnimConf_4[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
#if FE8_NEW_ANIMS
        .index = 0x00DD,
#else
        .index = 0x0034,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
#if FE8_NEW_ANIMS
        .index = 0x00DE,
#else
        .index = 0x0035,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00E2,
#else
        .index = 0x0036,
#endif
    },
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x00DF,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x00E1,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x00E0,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x00E0,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x00E0,
    },
#endif
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_5[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0037,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0038,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0039,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_6[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x003A,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x003B,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x003C,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_7[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x003D,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x003E,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x003F,
    },
    { 0 }
};

/* FE8_NEW_ANIMS: custom animation set from an FE-Repo pack (see CREDITS.md).
 * NOTE: .index is ONE-BASED -- GetBattleAnimationId (src/banim-ekrcmd.c)
 * returns idx - 1, so banim_data[] slot == .index - 1. Ranged axes match on
 * exact item id (wtype < 0x100, first pass) rather than weapon type. */
CONST_DATA struct BattleAnimDef AnimConf_8[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
#if FE8_NEW_ANIMS
        .index = 0x00D4,
#else
        .index = 0x0040,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00D8,
#else
        .index = 0x0041,
#endif
    },
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00D3,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x00D5,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x00D7,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x00D6,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x00D6,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x00D6,
    },
#endif
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_9[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0042,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0043,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_10[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0045,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0046,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x0047,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x0047,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0048,
    },
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0044,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x0047,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_11[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x004A,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x004B,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x004C,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x004C,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x004D,
    },
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0049,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x004C,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_12[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0089,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x008A,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_13[] = {
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00C7,
    },
    {
        .wtype = ITEM_DIVINESTONE,
        .index = 0x00C7,
    },
    { 0 }
};

/* FE8_NEW_ANIMS: custom animation set from an FE-Repo pack (see CREDITS.md).
 * NOTE: .index is ONE-BASED -- GetBattleAnimationId (src/banim-ekrcmd.c)
 * returns idx - 1, so banim_data[] slot == .index - 1. Ranged axes match on
 * exact item id (wtype < 0x100, first pass) rather than weapon type. */
CONST_DATA struct BattleAnimDef AnimConf_14[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
#if FE8_NEW_ANIMS
        .index = 0x00D9,
#else
        .index = 0x000B,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00DA,
#else
        .index = 0x000C,
#endif
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_15[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x000B,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x000C,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_16[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x000D,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x000E,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x000F,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x000F,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0010,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x000F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_17[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x000D,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x000E,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x000F,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x000F,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0010,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x000F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_18[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0011,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0012,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_19[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0013,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0014,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_20[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0015,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0016,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_21[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0017,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0018,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_22[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x008B,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x008C,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_23[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x008D,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x008E,
    },
    { 0 }
};

/* FE8_NEW_ANIMS: custom animation set from an FE-Repo pack (see CREDITS.md).
 * NOTE: .index is ONE-BASED -- GetBattleAnimationId (src/banim-ekrcmd.c)
 * returns idx - 1, so banim_data[] slot == .index - 1. Ranged axes match on
 * exact item id (wtype < 0x100, first pass) rather than weapon type. */
CONST_DATA struct BattleAnimDef AnimConf_24[] = { // CLASS_ARCHER
    {
        .wtype = 0x0100 | ITYPE_BOW,
#if FE8_NEW_ANIMS
        .index = 0x00E9, // derarcm bow -- [Archer-Variant] Der's Improved [M]
#else
        .index = 0x0026,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00EA, // derarcm unarmed
#else
        .index = 0x0027,
#endif
    },
    {
        .wtype = ITEM_BALLISTA_REGULAR,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_LONG,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_KILLER,
        .index = 0x009F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_25[] = { // CLASS_ARCHER_F
    {
        .wtype = 0x0100 | ITYPE_BOW,
#if FE8_NEW_ANIMS
        .index = 0x00EB, // derarcf bow -- [Archer-Variant] Der's Improved [F]
#else
        .index = 0x0028,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00EC, // derarcf unarmed
#else
        .index = 0x0029,
#endif
    },
    {
        .wtype = ITEM_BALLISTA_REGULAR,
        .index = 0x00CA,
    },
    {
        .wtype = ITEM_BALLISTA_LONG,
        .index = 0x00CA,
    },
    {
        .wtype = ITEM_BALLISTA_KILLER,
        .index = 0x00CA,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_26[] = {
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x002A,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x002B,
    },
    {
        .wtype = ITEM_BALLISTA_REGULAR,
        .index = 0x00CB,
    },
    {
        .wtype = ITEM_BALLISTA_LONG,
        .index = 0x00CB,
    },
    {
        .wtype = ITEM_BALLISTA_KILLER,
        .index = 0x00CB,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_27[] = {
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x002C,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x002D,
    },
    {
        .wtype = ITEM_BALLISTA_REGULAR,
        .index = 0x00CC,
    },
    {
        .wtype = ITEM_BALLISTA_LONG,
        .index = 0x00CC,
    },
    {
        .wtype = ITEM_BALLISTA_KILLER,
        .index = 0x00CC,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_28[] = {
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x002F,
    },
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x002E,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0030,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_29[] = {
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x0032,
    },
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0031,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0033,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_30[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0058,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0059,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_31[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x005A,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x005B,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_32[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x005D,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x005E,
    },
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x005C,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_33[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0060,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0061,
    },
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x005F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_34[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0062,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0063,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_35[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0062,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0063,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_36[] = { // CLASS_MAGE
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
#if FE8_NEW_ANIMS
        .index = 0x00ED, // gaidenmage_framefix magic -- [Mage-Custom] Gaiden-Style Frame Fix [F] by Gamma
#else
        .index = 0x006B,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
#if FE8_NEW_ANIMS
        .index = 0x00ED,
#else
        .index = 0x006B,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
#if FE8_NEW_ANIMS
        .index = 0x00ED,
#else
        .index = 0x006B,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00ED,
#else
        .index = 0x006B,
#endif
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_37[] = { // CLASS_MAGE_F
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
#if FE8_NEW_ANIMS
        .index = 0x00EE, // gaidenmage_ponytail magic -- [Mage-Custom] Gaiden-Style Ponytail [F] by Gamma
#else
        .index = 0x006C,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
#if FE8_NEW_ANIMS
        .index = 0x00EE,
#else
        .index = 0x006C,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
#if FE8_NEW_ANIMS
        .index = 0x00EE,
#else
        .index = 0x006C,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00EE,
#else
        .index = 0x006C,
#endif
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_38[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x006D,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x006D,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x006D,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x006D,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x006E,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_39[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x006F,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x006F,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x006F,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x006F,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0070,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_40[] = {
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0072,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0071,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0071,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0071,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0071,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_41[] = {
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0074,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0073,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0073,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0073,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0073,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_42[] = {
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0082,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0082,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0082,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0082,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0081,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_43[] = {
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0083,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0083,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0083,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0083,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0084,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_44[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0075,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0075,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0075,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0075,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_45[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0076,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0076,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0076,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0076,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_46[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0077,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0077,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0077,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0077,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0078,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_47[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0079,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0079,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0079,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0079,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x007A,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_48[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x007B,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x007B,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x007B,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x007B,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x007C,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_49[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x007B,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x007B,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x007B,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x007B,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x007C,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_50[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x008F,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0090,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_51[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x004E,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x004F,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0052,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0050,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x0051,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x0051,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x0051,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_52[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0053,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0054,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0057,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0055,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x0056,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x0056,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x0056,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_53[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0096,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0097,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_54[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0092,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0094,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x0093,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x0093,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x0093,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_55[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0095,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0095,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0095,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0095,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_56[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0096,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0097,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_57[] = {
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00C9,
    },
    {
        .wtype = ITEM_MONSTER_WRETCHAIR,
        .index = 0x00C9,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_58[] = {
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00C7,
    },
    {
        .wtype = ITEM_DIVINESTONE,
        .index = 0x00C7,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_59[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0092,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0094,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x0093,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x0093,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x0093,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_60[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0095,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0095,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0095,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0095,
    },
    { 0 }
};

/* FE8_NEW_ANIMS: custom animation set from an FE-Repo pack (see CREDITS.md).
 * NOTE: .index is ONE-BASED -- GetBattleAnimationId (src/banim-ekrcmd.c)
 * returns idx - 1, so banim_data[] slot == .index - 1. Ranged axes match on
 * exact item id (wtype < 0x100, first pass) rather than weapon type. */
CONST_DATA struct BattleAnimDef AnimConf_61[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
#if FE8_NEW_ANIMS
        .index = 0x00D0,
#else
        .index = 0x0019,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00D2,
#else
        .index = 0x001B,
#endif
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
#if FE8_NEW_ANIMS
        .index = 0x00D1,
#else
        .index = 0x001A,
#endif
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
#if FE8_NEW_ANIMS
        .index = 0x00D1,
#else
        .index = 0x001A,
#endif
    },
    {
        .wtype = ITEM_AXE_HATCHET,
#if FE8_NEW_ANIMS
        .index = 0x00D1,
#else
        .index = 0x001A,
#endif
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_62[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x001C,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x001F,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x001E,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x001D,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x001D,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x001D,
    },
    { 0 }
};

/* FE8_NEW_ANIMS: custom animation set from an FE-Repo pack (see CREDITS.md).
 * NOTE: .index is ONE-BASED -- GetBattleAnimationId (src/banim-ekrcmd.c)
 * returns idx - 1, so banim_data[] slot == .index - 1. Ranged axes match on
 * exact item id (wtype < 0x100, first pass) rather than weapon type. */
CONST_DATA struct BattleAnimDef AnimConf_63[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
#if FE8_NEW_ANIMS
        .index = 0x00CD,
#else
        .index = 0x0020,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00CF,
#else
        .index = 0x0022,
#endif
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
#if FE8_NEW_ANIMS
        .index = 0x00CE,
#else
        .index = 0x0021,
#endif
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
#if FE8_NEW_ANIMS
        .index = 0x00CE,
#else
        .index = 0x0021,
#endif
    },
    {
        .wtype = ITEM_AXE_HATCHET,
#if FE8_NEW_ANIMS
        .index = 0x00CE,
#else
        .index = 0x0021,
#endif
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_64[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x009A,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x009C,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x009B,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x009B,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x009B,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_65[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0023,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0025,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x0024,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x0024,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x0024,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_66[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x007D,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x007D,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x007D,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x007D,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_67[] = {
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x007F,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x007E,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_68[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0096,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0097,
    },
    { 0 }
};

/* FE8_NEW_ANIMS: custom animation set from an FE-Repo pack (see CREDITS.md).
 * NOTE: .index is ONE-BASED -- GetBattleAnimationId (src/banim-ekrcmd.c)
 * returns idx - 1, so banim_data[] slot == .index - 1. Ranged axes match on
 * exact item id (wtype < 0x100, first pass) rather than weapon type. */
CONST_DATA struct BattleAnimDef AnimConf_69[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
#if FE8_NEW_ANIMS
        .index = 0x00E4,
#else
        .index = 0x0066,
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00E8,
#else
        .index = 0x0067,
#endif
    },
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00E3,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x00E5,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x00E7,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x00E7,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x00E7,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x00E6,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x00E6,
    },
#endif
#if FE8_NEW_ANIMS
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x00E6,
    },
#endif
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_70[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0069,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x006A,
    },
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0068,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_71[] = {
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0080,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00C8,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_72[] = {
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0086,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0085,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_73[] = {
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0088,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0087,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0087,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0087,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0087,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_74[] = {
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0091,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0091,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0091,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0091,
    },
    { 0 }
};

/* CLASS_SOLDIER (src/data_classes.c, generated from src/data/classes.json,
 * references this symbol by name -- not by index -- so it cannot itself be
 * made conditional; this array's *contents* can be, since this file is
 * hand-maintained, not generated). Indices 0x0098/0x0099 are vanilla.
 *
 * FE8_NEW_ANIMS=1 swaps in a community-sourced custom animation set (FE-Repo
 * "[Soldier-Custom] FE10-Style [M] by Flasuban", see CREDITS.md) instead --
 * resolved at compile time, since gClassData/AnimConf_75 link
 * execute-in-place from ROM (no .data->RAM copy exists in this codebase's
 * startup path, see src/crt0.s and src/main.c's AgbMain) and so cannot be
 * runtime-patched.
 *
 * NOTE: `.index` is ONE-BASED. GetBattleAnimationId (src/banim-ekrcmd.c)
 * ends with `return (idx - 1)`, so the banim_data[] (src/banim_data.c) slot
 * actually loaded is `.index - 1` -- e.g. vanilla `.index = 0x0098` below
 * resolves to banim_data[0x97] == "solm_sp1". The custom entries live at
 * banim_data[0xC9..0xCB], hence `.index` 0xCA..0xCC. */
CONST_DATA struct BattleAnimDef AnimConf_75[] = {
#if FE8_NEW_ANIMS
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00CA, /* banim_data[0xC9] "newsldsw1" */
    },
#endif
    {
        .wtype = 0x0100 | ITYPE_LANCE,
#if FE8_NEW_ANIMS
        .index = 0x00CB, /* banim_data[0xCA] "newsldln1" */
#else
        .index = 0x0098, /* banim_data[0x97] "solm_sp1" */
#endif
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
#if FE8_NEW_ANIMS
        .index = 0x00CC, /* banim_data[0xCB] "newsldun1" */
#else
        .index = 0x0099, /* banim_data[0x98] "solm_sp1" */
#endif
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_76[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x009D,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x009D,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x009D,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x009D,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x009E,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_77[] = {
    {
        .wtype = 0x0100 | ITYPE_MONSTER,
        .index = 0x00A0,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00A0,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_78[] = {
    {
        .wtype = 0x0100 | ITYPE_MONSTER,
        .index = 0x00A1,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00A1,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_79[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00A2,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00A4,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x00A3,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_80[] = {
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x00A5,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00A6,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_81[] = {
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00A7,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00A9,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x00A8,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_82[] = {
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x00AA,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00AB,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_83[] = {
    {
        .wtype = 0x0100 | ITYPE_MONSTER,
        .index = 0x00AC,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00AC,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_84[] = {
    {
        .wtype = 0x0100 | ITYPE_MONSTER,
        .index = 0x00AD,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00AD,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_85[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x00AE,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00B0,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x00AF,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x00AF,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x00AF,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_86[] = {
    {
        .wtype = 0x0100 | ITYPE_MONSTER,
        .index = 0x00B1,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00B1,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_87[] = {
    {
        .wtype = 0x0100 | ITYPE_MONSTER,
        .index = 0x00B2,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00B2,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_88[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x00B3,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00B5,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x00B4,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x00B4,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x00B4,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_89[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x00B6,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00B9,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x00B7,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x00B7,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x0051,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x00B8,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_90[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x00BA,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x00BA,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x00BA,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00BA,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_91[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x00BB,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x00BB,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x00BB,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00BB,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_92[] = {
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00BC,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x00BC,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x00BC,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x00BC,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_93[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x00BD,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00BE,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_94[] = {
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x00BF,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00C0,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_95[] = {
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00C1,
    },
    {
        .wtype = ITEM_MONSTER_WRETCHAIR,
        .index = 0x00C1,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_96[] = {
    {
        .wtype = 0x0100 | ITYPE_MONSTER,
        .index = 0x00C2,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x00C3,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x00C3,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x00C3,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00C2,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_97[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x00AE,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00B0,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x00AF,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x00AF,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x00AF,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_98[] = {
    {
        .wtype = 0x0100 | ITYPE_MONSTER,
        .index = 0x00AD,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00AD,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_99[] = {
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0092,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0094,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x0093,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x0093,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x0093,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_100[] = {
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0095,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0095,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0095,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0095,
    },
    { 0 }
};

/* New classes (2026-09 FE-Repo pack import): LynLord, Nomad(_F), Nomad
 * Trooper(_F) -- see scripts/banim_packs.json / src/banim_data.c slots
 * 0xEE-0xF8. Unlike AnimConf_24 (Archer)/_36 (Mage) above, which the
 * import left untouched on purpose (their existing custom/vanilla anims
 * stay wired), these ARE the new classes' only anim, so .index isn't
 * #if FE8_NEW_ANIMS-gated the way Archer's is -- these classes don't
 * exist without FE8_NEW_ANIMS's animation data to draw them with in the
 * first place. ITYPE_ITEM (unarmed) reuses the weapon's own index where
 * no dedicated unarmed animation was provided (both Mage packs
 * had no "Unarmed" subfolder in their source pack) -- same convention
 * vanilla AnimConf_36 (Mage) already uses for all 4 of its wtypes. */
CONST_DATA struct BattleAnimDef AnimConf_101[] = { // LynLord
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00EF,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01AC,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_102[] = { // Nomad
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x00F0,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00F1,
    },
    {
        .wtype = ITEM_BALLISTA_REGULAR,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_LONG,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_KILLER,
        .index = 0x009F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_103[] = { // Nomad_F
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x00F2,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00F3,
    },
    {
        .wtype = ITEM_BALLISTA_REGULAR,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_LONG,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_KILLER,
        .index = 0x009F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_104[] = { // Nomad Trooper
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00F4,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x00F5,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00F6,
    },
    {
        .wtype = ITEM_BALLISTA_REGULAR,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_LONG,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_KILLER,
        .index = 0x009F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_105[] = { // Nomad Trooper_F
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00F7,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x00F8,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00F9,
    },
    {
        .wtype = ITEM_BALLISTA_REGULAR,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_LONG,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_KILLER,
        .index = 0x009F,
    },
    { 0 }
};
/* Batch2 custom classes (2026-09 import). */
CONST_DATA struct BattleAnimDef AnimConf_106[] = { // Swashbuckler_F
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00FA,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x00FB,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x00FD,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x00FE,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x00FE,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x00FE,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00FE,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_107[] = { // Swashbuckler
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00FF,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0100,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0102,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0103,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0103,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0103,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0103,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_108[] = { // Leo_Berserker
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0104,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0106,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_109[] = { // Grand_Mahout
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0107,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x0108,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0109,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_110[] = { // Arcanist_Nuramon
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x010A,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x010B,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x010B,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x010B,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x010B,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_111[] = { // Halberdier_Custom
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x010C,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x010D,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x010F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_112[] = { // Miko
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0110,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x0111,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0112,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0114,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0113,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0113,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0113,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_113[] = { // War_Cleric
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0115,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0117,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0117,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0117,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0117,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_114[] = { // Witch
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0118,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0119,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0119,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0119,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0119,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_115[] = { // Angel
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x011A,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x011A,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x011A,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x011A,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_116[] = { // Brighid
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x011B,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x011D,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_117[] = { // Arcanist_Devisian
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x011E,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x011E,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x011E,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x011E,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_118[] = { // Magician
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0120,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x011F,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x011F,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x011F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_119[] = { // Occultist
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0121,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0121,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0121,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0121,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_120[] = { // Blader_F
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0122,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0123,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_121[] = { // Harbinger
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0124,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0125,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0126,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0128,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x012A,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0129,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0129,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0129,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_122[] = { // Executioner
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x01C8,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01CA,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x01C9,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x01C9,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x01C9,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_123[] = { // Heavy_Infantry
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x012B,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x012C,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x012D,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x012F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_124[] = { // Baron_Custom
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0130,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0131,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0132,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x0134,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0135,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0136,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0136,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0136,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0136,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_125[] = { // Shield_General
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0137,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0138,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0139,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x013C,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x013B,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x013B,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x013B,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_126[] = { // Black_Dragon
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x013D,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_127[] = { // Djinn
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x013F,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0141,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0140,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0140,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0140,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_128[] = { // Living_Armor
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0142,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0143,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0145,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_129[] = { // Fellbeast
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0147,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0146,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0146,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0146,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_130[] = { // Samurai_F
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0148,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0149,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_131[] = { // Master_Ninja
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x014A,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x014B,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_132[] = { // Hooded_Ninja
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x014C,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x014D,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_133[] = { // Myrmidon_FE15_F
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x014E,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x014F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_134[] = { // Myrmidon_FE15
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0150,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0151,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_135[] = { // Katarina_Fencer
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0152,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0153,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_136[] = { // Thug
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0154,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0155,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_137[] = { // Dread_Fighter
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0156,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0158,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0157,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0157,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0157,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_138[] = { // Fir_Swordmaster
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0159,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x015A,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x015B,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_139[] = { // Trueblade
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x015C,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x015D,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_140[] = { // Red_Mage
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x015E,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x015F,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0160,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0160,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0160,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0160,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_141[] = { // Moloch
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0161,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0162,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0164,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0163,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0163,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0163,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_142[] = { // Tactician_Custom
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0165,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0165,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0165,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0165,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_143[] = { // Trickster_F
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0166,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x0167,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x0168,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0169,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0169,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0169,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0169,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_144[] = { // Trickster
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x016A,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x016B,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x016C,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x016D,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x016D,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x016D,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x016D,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_145[] = { // Villager_F
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x016E,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x016F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_146[] = { // Villager
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0170,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0171,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_147[] = { // Legion_King
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0172,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0173,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0174,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0177,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x0176,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x0176,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x0176,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_148[] = { // Oni_Chieftain
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0178,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x017A,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x017A,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x017A,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x017A,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_149[] = { // Elffin_Fancy
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x017C,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x017B,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x017B,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x017B,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_150[] = { // Mounted_Marauder
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x017D,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x017F,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0180,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_151[] = { // Mechanist
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x0181,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0182,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_152[] = { // Dragoon_Custom
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0183,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0184,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_153[] = { // Lancer_Custom
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0185,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0186,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_154[] = { // Militia
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0187,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0188,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_155[] = { // Sentinel
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0189,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x018A,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x018B,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x018D,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_156[] = { // T1_Lancer
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x018E,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x018F,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0190,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_157[] = { // Gladiator
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x0191,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0192,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0194,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_158[] = { // Horn_Brigand
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x0195,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0195,
    },
    // Explicit wiring (FE8_SKILLSYSTEM) for ITEM_CALL: the Call command's
    // cosmetic solo animation (src/unitcall.c) uses this class's own real
    // attack pose, same index as the ITYPE_AXE/ITYPE_ITEM entries above.
    {
        .wtype = 0x0100 | ITYPE_DANCE,
        .index = 0x0195,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_159[] = { // Horn_Soldier
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0196,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0196,
    },
    // Explicit wiring (FE8_SKILLSYSTEM) for ITEM_CALL: see AnimConf_158 above.
    {
        .wtype = 0x0100 | ITYPE_DANCE,
        .index = 0x0196,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_160[] = { // Hunter
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x0197,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0198,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_161[] = { // Supplier_Anna
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x0199,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x019A,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x019B,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x0199,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_162[] = { // Sandworm
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x019C,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_163[] = { // Cursed_Sword
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x019D,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x019D,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_164[] = { // Magical_Tomes
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x019E,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x019E,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x019E,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x019E,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_165[] = { // Mimic_Chest
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x019F,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x019F,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x019F,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x019F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_166[] = { // Mosquito
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01A0,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_167[] = { // Phantom_Custom
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x01A1,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01A3,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_168[] = { // Slime
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x01A4,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x01A5,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x01A5,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x01A5,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01A5,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_169[] = { // Warbird
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x01A6,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x01A7,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01A8,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_170[] = { // Adventurer
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x01A9,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x01AA,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01AB,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_171[] = { // LynGreatLord
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x01AD,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01AE,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_172[] = { // Elder
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x01AF,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x01AF,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x01AF,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x01B0,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01B1,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_173[] = { // Arbalest
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x01B2,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x01B3,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01B4,
    },
    {
        .wtype = ITEM_BALLISTA_REGULAR,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_LONG,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_KILLER,
        .index = 0x009F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_174[] = { // Arbalest_F
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x01B5,
    },
    {
        .wtype = 0x0100 | ITYPE_BOW,
        .index = 0x01B6,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01B7,
    },
    {
        .wtype = ITEM_BALLISTA_REGULAR,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_LONG,
        .index = 0x009F,
    },
    {
        .wtype = ITEM_BALLISTA_KILLER,
        .index = 0x009F,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_175[] = { // Fellbeast_Knight
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x01B8,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01B9,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_176[] = { // Griffon
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x01BA,
    },
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x01BB,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01BD,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x01BC,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x01BC,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x01BC,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_177[] = { // Archsage
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x01BE,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x01BE,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x01BE,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x01BF,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01BE,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_178[] = { // Malig_Queen
    {
        .wtype = 0x0100 | ITYPE_AXE,
        .index = 0x01C0,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x01C2,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x01C2,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x01C2,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01C0,
    },
    {
        .wtype = ITEM_AXE_HANDAXE,
        .index = 0x01C1,
    },
    {
        .wtype = ITEM_AXE_TOMAHAWK,
        .index = 0x01C1,
    },
    {
        .wtype = ITEM_AXE_HATCHET,
        .index = 0x01C1,
    },
    { 0 }
};

CONST_DATA struct BattleAnimDef AnimConf_179[] = { // Seraph_Knight
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x01C3,
    },
    {
        .wtype = 0x0100 | ITYPE_LANCE,
        .index = 0x01C4,
    },
    {
        .wtype = 0x0100 | ITYPE_ANIMA,
        .index = 0x01C5,
    },
    {
        .wtype = 0x0100 | ITYPE_LIGHT,
        .index = 0x01C5,
    },
    {
        .wtype = 0x0100 | ITYPE_DARK,
        .index = 0x01C5,
    },
    {
        .wtype = 0x0100 | ITYPE_STAFF,
        .index = 0x01C6,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x01C7,
    },
    { 0 }
};
