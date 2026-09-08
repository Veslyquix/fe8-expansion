#include "global.h"

#include "bmunit.h"
#include "bmitem.h"
#include "ekrbattle.h"
#include "class_preview.h"

#include "constants/classes.h"
#include "constants/items.h"

/* See include/class_preview.h. Bodies moved verbatim from
 * GetDebuggerDefaultSpellItem / GetDebuggerDefaultPreviewWeapon /
 * GetDebuggerBanimId (src/VeslyDebugger.c), which now delegate here. */

static int GetClassPreviewSpellItem(const struct ClassData * class)
{
    bool promoted = (class->attributes & CA_PROMOTED) != 0;

    if (class->baseRanks[ITYPE_ANIMA])
        return promoted ? ITEM_ANIMA_ELFIRE : ITEM_ANIMA_FIRE;
    if (class->baseRanks[ITYPE_LIGHT])
        return promoted ? ITEM_LIGHT_SHINE : ITEM_LIGHT_LIGHTNING;
    if (class->baseRanks[ITYPE_DARK])
        return promoted ? ITEM_DARK_LUNA : ITEM_DARK_FLUX;
    if (class->baseRanks[ITYPE_STAFF])
        return promoted ? ITEM_STAFF_MEND : ITEM_STAFF_HEAL;

    return ITEM_NONE;
}

int GetClassPreviewWeapon(int classId)
{
    const struct ClassData * class = GetClassData(classId);

    if (class == NULL)
        return ITEM_NONE;

    if (classId == CLASS_MANAKETE || classId == CLASS_MANAKETE_2)
        return ITEM_DEMONSTONE;
    if (classId == CLASS_MANAKETE_MYRRH)
        return ITEM_DIVINESTONE;
    if (classId == CLASS_DEMON_KING)
        return ITEM_RAVAGER;
    if (classId == CLASS_DRACO_ZOMBIE)
        return ITEM_MONSTER_WRETCHAIR;
    if (classId == CLASS_MOGALL || classId == CLASS_ARCH_MOGALL)
        return ITEM_DARK_FLUX;

    if (class->baseRanks[ITYPE_SWORD])
        return ITEM_SWORD_IRON;
    if (class->baseRanks[ITYPE_LANCE])
        return ITEM_LANCE_IRON;
    if (class->baseRanks[ITYPE_AXE])
        return ITEM_AXE_IRON;
    if (class->baseRanks[ITYPE_BOW])
        return ITEM_BOW_IRON;
    if (class->attributes & CA_LOCK_3)
        return ITEM_MONSTER_ROTTENCLW;
    if (class->baseRanks[ITYPE_ANIMA] || class->baseRanks[ITYPE_LIGHT] || class->baseRanks[ITYPE_DARK])
        return GetClassPreviewSpellItem(class);
    if (class->baseRanks[ITYPE_STAFF])
        return ITEM_STAFF_HEAL;

    return ITEM_NONE;
}

int GetClassPreviewBanimId(int classId, int weapon)
{
    const struct ClassData * class;
    const struct BattleAnimDef * animDef;
    int expectedType;
    int i;

    class = GetClassData(classId);
    if (class == NULL || class->pBattleAnimDef == NULL)
        return 0;

    animDef = class->pBattleAnimDef;
    expectedType = weapon != ITEM_NONE ? (GetItemType(weapon) + 0x100) : SPECIAL_BANIM_WTYPE;

    for (i = 0; animDef[i].index != 0; ++i)
        if (animDef[i].wtype == expectedType)
            return animDef[i].index - 1;

    for (i = 0; animDef[i].index != 0; ++i)
        if (animDef[i].wtype == SPECIAL_BANIM_WTYPE)
            return animDef[i].index - 1;

    return animDef[0].index != 0 ? animDef[0].index - 1 : 0;
}
