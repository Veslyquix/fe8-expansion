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
 * no dedicated unarmed animation was provided (LynLord, both Mage packs
 * had no "Unarmed" subfolder in their source pack) -- same convention
 * vanilla AnimConf_36 (Mage) already uses for all 4 of its wtypes. */
CONST_DATA struct BattleAnimDef AnimConf_101[] = { // LynLord
    {
        .wtype = 0x0100 | ITYPE_SWORD,
        .index = 0x00EF,
    },
    {
        .wtype = 0x0100 | ITYPE_ITEM,
        .index = 0x00EF,
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
