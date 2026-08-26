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

bool AiShouldCaptureBaseInsteadOfAttacking(void);
bool AiFindClosestCapturableBase(struct Vec2* out, u8* distanceOut);

/* The gold price a generic of this class would cost to (re)purchase, or 0
 * if classId has no sPurchaseGenericDefinitions entry -- used by
 * ActionMerge (src/bmmind.c) to price the gold a merge's HP overflow
 * converts to. */
int GetPurchaseGenericPrice(int classId);

#endif

#endif // GUARD_PURCHASE_GENERICS_H
