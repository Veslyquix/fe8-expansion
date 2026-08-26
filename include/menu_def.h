#ifndef GUARD_MENU_DEF_H
#define GUARD_MENU_DEF_H

struct MenuDef;
struct SelectTarget;

extern struct MenuDef gDebugClearMenuDef;
extern struct MenuDef gDebugChargeMenuDef;
extern struct MenuDef gDebugContinueMenuDef;
extern struct MenuDef gDebugChuudanMenuDef;
extern struct MenuDef gDebugMenuDef;
extern struct MenuDef gMenuInfo_RepairItems;
extern struct MenuDef gStealItemMenuDef;
extern struct MenuDef gYesNoSelectionMenuDef;
extern struct MenuDef gItemSubMenuDef;
extern struct MenuDef gItemMenuDef;
extern struct MenuDef gStaffItemSelectMenuDef;
extern struct MenuDef gItemSelectMenuDef;
extern struct MenuDef gBallistaRangeMenuDef;
extern struct MenuDef gWeaponSelectMenuDef;
extern struct MenuDef gUnitActionMenuDef;

extern struct SelectInfo CONST_DATA gSelectInfo_OffensiveStaff;
extern struct SelectInfo CONST_DATA gSelectInfo_Barrier;
extern struct SelectInfo CONST_DATA gSelectInfo_Restore;
extern struct SelectInfo CONST_DATA gSelectInfo_Heal;
extern struct SelectInfo CONST_DATA gSelectInfo_Dance;
extern struct SelectInfo CONST_DATA gSelectInfo_PutTrap;
extern struct SelectInfo CONST_DATA gSelectInfo_WarpUnit;
extern struct SelectInfo CONST_DATA gSelectInfo_Steal;
extern struct SelectInfo CONST_DATA gSelectInfo_Summon;
extern struct SelectInfo CONST_DATA gSelectInfo_Pick;
extern struct SelectInfo CONST_DATA gSelectInfo_Support;
extern struct SelectInfo CONST_DATA gSelectInfo_Talk;
extern struct SelectInfo CONST_DATA gSelectInfo_Repair;
extern struct SelectInfo CONST_DATA gSelectInfo_Trade;
extern struct SelectInfo CONST_DATA gSelectInfo_Attack;
extern struct SelectInfo CONST_DATA gSelectInfo_Give;
extern struct SelectInfo CONST_DATA gSelectInfo_Take;
extern struct SelectInfo CONST_DATA gSelectInfo_Drop;
extern struct SelectInfo CONST_DATA gSelectInfo_Rescue;
#if FE8_PURCHASE_GENERICS
extern struct SelectInfo CONST_DATA gSelectInfo_Merge;
#endif

#endif // GUARD_MENU_DEF_H
