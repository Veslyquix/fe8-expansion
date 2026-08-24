#include "global.h"
#include "promote_command.h"

#if FE8_PROMOTE_COMMAND

#include "bmunit.h"
#include "bmmind.h"
#include "bmio.h"
#include "mu.h"
#include "classchg.h"
#include "uimenu.h"
#include "hardware.h"

/* Minimum level to manually promote without a promotion item. Ported from
 * the community "PromoteCommand" patch's default PromotionMenuList entry
 * (anyone can promote at level 20+). The reference patch's data-driven
 * table also supported per-unit/per-class overrides, chapter ranges, and
 * event-flag gating (including a campaign-specific "Eirika can't promote
 * unless Amelia is alive" example rule) -- none of that is ported, only
 * the general level-gated mechanism. */
#define PROMOTE_COMMAND_MIN_LEVEL 20

extern CONST_DATA struct ProcCmd ProcScr_PromoHandler[];

static bool ClassHasPromotion(u8 classId)
{
    return gPromoJidLut[classId][0] != 0 || gPromoJidLut[classId][1] != 0;
}

u8 PromoteCommandUsability(const struct MenuItemDef* def, int number)
{
    (void)def;
    (void)number;

    if (gActiveUnit->state & US_HAS_MOVED)
        return MENU_NOTSHOWN;

    if (!ClassHasPromotion(gActiveUnit->pClassData->number))
        return MENU_NOTSHOWN;

    if (gActiveUnit->level < PROMOTE_COMMAND_MIN_LEVEL)
        return MENU_NOTSHOWN;

    return MENU_ENABLED;
}

int PromoteCommandDraw(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    const char* text = "Promote";

    PutDrawText(
        &menuItem->text,
        TILEMAP_LOCATED(BG_GetMapBuffer(menu->frontBg), menuItem->xTile, menuItem->yTile),
        menuItem->availability == MENU_DISABLED ? TEXT_COLOR_SYSTEM_GRAY : TEXT_COLOR_SYSTEM_WHITE,
        0, menu->rect.w - 1, text);

    return 0;
}

u8 PromoteCommandEffect(struct MenuProc* menu, struct MenuItemProc* menuItem)
{
    (void)menu;
    (void)menuItem;

    gActionData.unitActionType = UNIT_ACTION_PROMOTE;
    gActionData.subjectIndex = gActiveUnit->index;

    return MENU_ACT_SKIPCURSOR | MENU_ACT_END | MENU_ACT_SND6A | MENU_ACT_CLEAR;
}

/* Mirrors StartBmPromotion (src/classchg-handler.c, vanilla 0x080CCA14),
 * the handler vanilla's promotion-item usage flow already uses to kick off
 * the class-change proc (class-choice popup if the class has two promotion
 * options, then the usual promotion animation/stat-growth screen). The
 * only difference: item_slot is set to -1 (this repo's real "no item"
 * sentinel, checked in ExecClassChgReal) rather than routed through
 * gActionData.itemSlotIndex, whose u8 storage can't represent -1. The
 * reference ASM patch instead reused the unit's hidden 5th item slot
 * (items[4]) as a scratch "always empty" slot to avoid consuming a real
 * item -- that assumption doesn't hold if a unit's 5th slot happens to be
 * occupied (a real, usable slot in this repo -- see bmtrade.c's trade
 * menu), so it isn't ported. */
void PromoteCommand_ActionPromote(ProcPtr proc)
{
    struct Unit* unit = GetUnit(gActionData.subjectIndex);
    struct ProcPromoHandler* newProc = Proc_StartBlocking(ProcScr_PromoHandler, proc);

    newProc->bmtype = PROMO_HANDLER_TYPE_PREP;
    newProc->u32 = 0;
    newProc->pid = unit->pCharacterData->number;
    newProc->unit = unit;
    newProc->item_slot = -1;

    BMapDispSuspend();
    EndAllMus();
}

#endif /* FE8_PROMOTE_COMMAND */
