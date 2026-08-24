#include "gbafe.h"
#include "EAstdlib.h"
#include "chapterdata.h"
#include "face.h"
#include "mu.h"
#include "scene.h"
#include "unit_icon_data.h"

#if FE8_VESLY_DEBUGGER

enum
{
    DEBUGGER_FLAG = 0xEC,
    DEBUGGER_MENU_COLOR_NORMAL = 0,
    DEBUGGER_MENU_OVERRIDE_ID = 0x4E,
};

int DebuggerTurnedOff_Flag = DEBUGGER_FLAG;
int KeyComboToDisableFlag = DPAD_UP | DPAD_LEFT | L_BUTTON;
int KonamiCodeEnabled = 1;
int NumberOfPages = 4;
int POKEMBLEM_EXISTS = 0;

extern struct ROMChapterData CONST_DATA gChapterDataTable[];
extern u8 CONST_DATA gPromoJidLut[][2];
extern struct gfx_set CONST_DATA gConvoBackgroundData[];
extern UnitIconWait unit_icon_wait_table[];
extern const struct FaceData portrait_data[];
extern CONST_DATA struct MuInfo unit_icon_move_table[];

struct CGDataEnt;
extern char CONST_DATA gCGDataTable[];

struct ROMChapterData const * const sChapterDataTable = gChapterDataTable;
struct FaceData const * const sPortrait_data = portrait_data;
UnitIconWait const * const sUnit_icon_wait_table = unit_icon_wait_table;
struct MuInfo const * const sUnit_icon_move_table = unit_icon_move_table;
struct gfx_set const * const sConvoBackgroundData = gConvoBackgroundData;
struct CGDataEnt const * const sCGDataTable = (struct CGDataEnt const *)gCGDataTable;
u8 * pPromoJidLut = (u8 *)gPromoJidLut;
struct TalkState sTalkStateCore;

int sStatusNameTextIdLookup[] = {
    [UNIT_STATUS_NONE]     = 0x536,
    [UNIT_STATUS_POISON]   = 0x514,
    [UNIT_STATUS_SLEEP]    = 0x515,
    [UNIT_STATUS_SILENCED] = 0x516,
    [UNIT_STATUS_BERSERK]  = 0x517,
    [UNIT_STATUS_ATTACK]   = 0x51B,
    [UNIT_STATUS_DEFENSE]  = 0x51C,
    [UNIT_STATUS_CRIT]     = 0x51D,
    [UNIT_STATUS_AVOID]    = 0x51E,
    [UNIT_STATUS_SICK]     = 0x518,
    [UNIT_STATUS_RECOVER]  = 0x519,
    [UNIT_STATUS_PETRIFY]  = 0x51A,
    [UNIT_STATUS_12]       = 0,
    [UNIT_STATUS_13]       = 0x51A,
};

const EventListScr DebuggerFlagEvent[] = {
    ENDA
};

struct ProcCmd * get_pProc_FromMiscActionProc[] = {
    NULL
};

int Mod(int a, int b)
{
    if (b == 0)
        return 0;

    return a % b;
}

void WfxInit(void) {}

void SkillDebugCommand_OnSelect(void * proc) {}

u8 MenuAlwaysEnabled(const struct MenuItemDef * def, int number);
u8 CanActiveUnitPromoteMenu(const struct MenuItemDef * def, int number);
u8 CallArenaIsUnitAllowed(const struct MenuItemDef * def, int number);

int DebuggerMenuItemDraw(struct MenuProc * menu, struct MenuItemProc * menuItem);
int PageMenuItemDraw(struct MenuProc * menu, struct MenuItemProc * menuItem);
int GodmodeDrawText(struct MenuProc * menu, struct MenuItemProc * menuItem);
int ControlAiDrawText(struct MenuProc * menu, struct MenuItemProc * menuItem);
int BootmodeDrawText(struct MenuProc * menu, struct MenuItemProc * menuItem);
int AiControlRemainingUnitsDrawText(struct MenuProc * menu, struct MenuItemProc * menuItem);

u8 PickupUnitNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 LevelupNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 EditStatsNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 EditMiscNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 EditItemsNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 EditStateNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 EditWExpNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 EditSupportNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 PageIdler(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 StartGodmodeNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 ControlAiNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 EditMapNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 EditTrapNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 ChStateNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 CallEndEventNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 LoadUnitsNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 ToggleBootNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 SupplyNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 ListNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 StartPromotionNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 StartArenaNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 AiControlRemainingUnitsNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 EditAiNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 GfxViewerNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
u8 EditBgmNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
#if FE8_CO_POWERS
u8 EditCoNow(struct MenuProc * menu, struct MenuItemProc * menuItem);
#endif

#define DEBUGGER_MENU_ITEM(draw, effect) \
    { \
        " ", 0x505, 0x505, DEBUGGER_MENU_COLOR_NORMAL, DEBUGGER_MENU_OVERRIDE_ID, \
        MenuAlwaysEnabled, draw, effect, PageIdler, NULL, NULL \
    }

#define DEBUGGER_MENU_ITEM_AVAILABLE(available, draw, effect) \
    { \
        " ", 0x505, 0x505, DEBUGGER_MENU_COLOR_NORMAL, DEBUGGER_MENU_OVERRIDE_ID, \
        available, draw, effect, PageIdler, NULL, NULL \
    }

const struct MenuItemDef gDebuggerMenuItems[] = {
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, PickupUnitNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, LevelupNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditStatsNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditMiscNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditItemsNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditStateNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditWExpNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditSupportNow),
    DEBUGGER_MENU_ITEM(PageMenuItemDraw, PageIdler),
    MenuItemsEnd,
};

const struct MenuItemDef gDebuggerMenuItemsPage2[] = {
    DEBUGGER_MENU_ITEM(GodmodeDrawText, StartGodmodeNow),
    DEBUGGER_MENU_ITEM(ControlAiDrawText, ControlAiNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditMapNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditTrapNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, ChStateNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, CallEndEventNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, LoadUnitsNow),
    DEBUGGER_MENU_ITEM(BootmodeDrawText, ToggleBootNow),
    DEBUGGER_MENU_ITEM(PageMenuItemDraw, PageIdler),
    MenuItemsEnd,
};

const struct MenuItemDef gDebuggerMenuItemsPage3[] = {
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, SupplyNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, ListNow),
    DEBUGGER_MENU_ITEM_AVAILABLE(CanActiveUnitPromoteMenu, DebuggerMenuItemDraw, StartPromotionNow),
    DEBUGGER_MENU_ITEM_AVAILABLE(CallArenaIsUnitAllowed, DebuggerMenuItemDraw, StartArenaNow),
    DEBUGGER_MENU_ITEM(AiControlRemainingUnitsDrawText, AiControlRemainingUnitsNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditAiNow),
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, GfxViewerNow),
    DEBUGGER_MENU_ITEM(PageMenuItemDraw, PageIdler),
    MenuItemsEnd,
};

const struct MenuItemDef gDebuggerMenuItemsPage4[] = {
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditBgmNow),
#if FE8_CO_POWERS
    DEBUGGER_MENU_ITEM(DebuggerMenuItemDraw, EditCoNow),
#endif
    DEBUGGER_MENU_ITEM(PageMenuItemDraw, PageIdler),
    MenuItemsEnd,
};

const struct MenuItemDef * ggDebuggerMenuItems[] = {
    gDebuggerMenuItems,
    gDebuggerMenuItemsPage2,
    gDebuggerMenuItemsPage3,
    gDebuggerMenuItemsPage4,
    NULL,
};

char * gDebuggerMenuText[] = {
    " Pickup", "Pickup a unit and\nplace them anywhere.",
    " Level up", "Level up\nthe unit.",
    " Stats", "Edit a unit's stats.",
    " Misc", "Edit unit's ID, class,\nbonuses, and more.",
    " Items", "Edit a unit's items.",
    " State", "Edit unit state.",
    " WExp", "Edit WExp\nfor the unit.",
    " Supports", "Edit support levels\nfor the unit.",
    " Page", "Swap pages in\nthis debugger.",
    NULL, NULL,

    " Godmode off", "Make your units\nwin every battle.",
    " Enemy Ctrl off", "Control just players\nor control everyone.",
    " Edit Map", "Edit tiles on the\nmap with the tileset.",
    " Traps", "Edit trap slots\nand trap data.",
    " Ch. State", "Edit things about\nthe chapter.",
    " Clear Ch.", "Clear the current\nchapter.",
    " Load units", "Load units.\nPossibly useful.",
    " Boot title", "Change debugger\nboot mode.",
    " Page", "Swap pages in\nthis debugger.",
    NULL, NULL,

    " Supply", "Open the convoy\nto access items.",
    " List", "Open the list\nof everyone's items.",
    " Promote", "Promote the unit\ninto an advanced\nclass.",
    " Arena", "Enter the arena\nand fight for glory.",
    " Autoplay off", "Control remaining\nunits automatically.",
    " AI", "Edit unit's AI.",
    " Gfx viewer", "Preview graphics.",
    " Page", "Swap pages in\nthis debugger.",
    NULL, NULL,

    " BGM", "Change the current\nmusic track.",
#if FE8_CO_POWERS
    " Co", "Edit each faction's\ncommander, CO gauge,\nand chapter gold.",
#endif
    " Page", "Swap pages in\nthis debugger.",
};

#endif /* FE8_VESLY_DEBUGGER */
