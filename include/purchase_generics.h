#ifndef GUARD_PURCHASE_GENERICS_H
#define GUARD_PURCHASE_GENERICS_H

#include "uimenu.h"

#if FE8_PURCHASE_GENERICS

extern CONST_DATA struct MenuDef gPurchaseGenericsMenuDef;

u8 PurchaseGenericsCommandUsability(const struct MenuItemDef* def, int number);
int PurchaseGenericsCommandDraw(struct MenuProc* menu, struct MenuItemProc* menuItem);
u8 PurchaseGenericsCommandEffect(struct MenuProc* menu, struct MenuItemProc* menuItem);
void PurchaseGenerics_OnNewPhase(void);
bool PurchaseGenerics_TryStartTileMenu(int x, int y);

#endif

#endif // GUARD_PURCHASE_GENERICS_H
