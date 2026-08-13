#include "gbafe.h"
#include "expansion_config.h"

#if FE8_HP_BARS

#if !FE8_DISPLAY_OBTAINABLE_ITEM
#error "FE8_HP_BARS requires FE8_DISPLAY_OBTAINABLE_ITEM=1 (its icon sheet also carries the HP-bar segment/warning-icon tiles this feature draws)"
#endif

#include "bmunit.h"
#include "bm.h"
#include "bmitem.h"
#include "bmreliance.h"
#include "eventinfo.h"
#include "ctc.h"
#include "constants/items.h"

/* Modern-build port of a FEBuilder-style ROM patch (by circleseverywhere,
 * with additions by Tequila and Vesly) that draws a partial-fill bar over
 * each visible unit showing HP lost, plus a small icon over enemies the
 * currently-selected unit could hit for bonus (weapon-triangle/slayer)
 * effectiveness, land a high crit on, or start a support/talk event with.
 *
 * Requires FE8_DISPLAY_OBTAINABLE_ITEM: the bar-segment and icon tiles
 * this draws (sHpBarFrames/sWarningIcon*) live in the same extended UI
 * icon sheet that feature loads (see src/DisplayObtainableItem.c and
 * LoadObjUIGfx in src/bm.c) -- confirmed present by inspecting that
 * sheet's source image, not merely assumed.
 *
 * Two simplifications from the original patch, both isolated to the
 * warning-icon (not the HP bar) path:
 *
 * - The original recomputes each unit's effectiveness/crit/talk-or-support
 *   status incrementally across multiple frames (an explicit cache, filled
 *   one unit per frame, to spread the cost out) and only recomputes when
 *   the selected unit changes. This port recomputes fresh every frame
 *   instead: simpler and lower-risk to get right, and cheap enough at GBA
 *   scale (this file's unit loop is already no larger than the vanilla
 *   per-frame unit-icon loop it hooks into).
 * - The original additionally gates warning-icon display on two functions
 *   (HpBarIsFMUActive, a "trainer flag" check) that are called but never
 *   defined anywhere in the source this was ported from -- not resolvable
 *   to a real address, so not guessable. Their checks are omitted (treated
 *   as not applicable) rather than reimplemented blind; this can only
 *   result in a warning icon showing in a narrow case where the original
 *   would have suppressed it, never a missing icon or incorrect stats. */

#define HP_BAR_CRIT_WARNING_CUTOFF 24

static CONST_DATA u16 sHpBarFrames[12][4] = {
    { 1, 0x400F, 0x01FF, 0x0812 },
    { 1, 0x400F, 0x01FF, 0x0814 },
    { 1, 0x400F, 0x01FF, 0x0816 },
    { 1, 0x400F, 0x01FF, 0x0832 },
    { 1, 0x400F, 0x01FF, 0x0834 },
    { 1, 0x400F, 0x01FF, 0x0836 },
    { 1, 0x400F, 0x01FF, 0x0852 },
    { 1, 0x400F, 0x01FF, 0x0854 },
    { 1, 0x400F, 0x01FF, 0x0856 },
    { 1, 0x400F, 0x01FF, 0x0872 },
    { 1, 0x400F, 0x01FF, 0x0874 },
    { 1, 0x400F, 0x01FF, 0x0876 },
};

static CONST_DATA u16 sWarningIconEffective[4] = { 1, 0x000F, 0x01FF, 0x0876 };
static CONST_DATA u16 sWarningIconCrit[4] = { 1, 0x000F, 0x01FF, 0x0877 };
static CONST_DATA u16 sWarningIconTalk[4] = { 1, 0x400F, 0x01EE, 0x0870 };

static void DrawHpBarsSprite(int x, int y, const u16* sprite)
{
    CallARM_PushToSecondaryOAM(OAM1_X(x + 0xB), OAM0_Y(y + 0xEE), sprite, 0);
}

static void DrawUnitHpBar(struct Unit* unit, int x, int y)
{
    int maxHp = unit->maxHP;
    int curHp = unit->curHP;
    int index;

    if (curHp <= 0 || curHp >= maxHp)
        return;

    index = (maxHp - curHp) * 11 / maxHp;
    if (index > 11)
        index = 11;

    DrawHpBarsSprite(x, y, sHpBarFrames[index]);
}

static bool IsUnitEffectiveOrCritty(struct Unit* activeUnit, struct Unit* unit, bool* outCritty)
{
    int slot;

    *outCritty = false;

    if (IsUnitEffectiveAgainst(activeUnit, unit))
        return true;

    for (slot = 0; slot < UNIT_ITEM_COUNT; slot++)
    {
        u16 item = unit->items[slot];

        if (item == ITEM_NONE)
            continue;

        if (!CanUnitUseWeapon(unit, item))
            continue;

        if (IsItemEffectiveAgainst(item, activeUnit) == 4)
            return true;

        if (GetItemCrit(item) > HP_BAR_CRIT_WARNING_CUTOFF)
            *outCritty = true;
    }

    return false;
}

static bool UnitHasSupportOrTalkWithActive(struct Unit* activeUnit, struct Unit* unit)
{
    int slot;
    u8 activeCharId = UNIT_CHAR_ID(activeUnit);
    u8 unitCharId = UNIT_CHAR_ID(unit);

    if (CheckForCharacterEvents(activeCharId, unitCharId))
        return true;

    if (UNIT_FACTION(unit) == FACTION_BLUE)
        return false;

    for (slot = 0; slot < UNIT_SUPPORT_MAX_COUNT; slot++)
    {
        if (unit->supports[slot] != unitCharId)
            continue;

        return CanUnitSupportNow(activeUnit, slot) != 0;
    }

    return false;
}

static void DrawUnitWarningIcons(struct Unit* unit, int x, int y)
{
    struct Unit* activeUnit = gActiveUnit;
    bool critty;
    bool effective;

    if (activeUnit == NULL || UNIT_FACTION(activeUnit) != FACTION_BLUE)
        return;

    /* Only draw while the selected unit's own map sprite is hidden (menu
     * open / cursor stopped on them), matching the original's intent to
     * not clutter the screen while a unit is actively walking -- see this
     * file's header comment on the two checks not ported here. */
    if (!(activeUnit->state & US_HIDDEN))
        return;

    if (unit->index & 0x80) /* enemies only */
    {
        effective = IsUnitEffectiveOrCritty(activeUnit, unit, &critty);

        if (effective)
        {
            DrawHpBarsSprite(x, y, sWarningIconEffective);
            return;
        }

        if (critty)
        {
            DrawHpBarsSprite(x, y, sWarningIconCrit);
            return;
        }
    }

    if (UnitHasSupportOrTalkWithActive(activeUnit, unit))
        DrawHpBarsSprite(x, y, sWarningIconTalk);
}

/* Called once per visible unit from PutUnitSpriteIconsOam. */
void DisplayHpBarAndWarningIcons(struct Unit* unit)
{
    int x = unit->xPos * 16 - gBmSt.camera.x;
    int y = unit->yPos * 16 - gBmSt.camera.y;

    if (x < -16 || x > DISPLAY_WIDTH)
        return;

    if (y < -16 || y > DISPLAY_HEIGHT)
        return;

    DrawUnitHpBar(unit, x, y);
    DrawUnitWarningIcons(unit, x, y);
}

#endif /* FE8_HP_BARS */
