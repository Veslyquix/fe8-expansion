#ifndef GUARD_PURCHASE_GENERICS_H
#define GUARD_PURCHASE_GENERICS_H

#include "uimenu.h"

#if FE8_PURCHASE_GENERICS

extern CONST_DATA struct MenuDef gPurchaseGenericsMenuDef;

int ActionCapture(ProcPtr proc); 
int ActionCaptured(ProcPtr proc); 
u8 PurchaseGenericsCommandUsability(const struct MenuItemDef* def, int number);
int PurchaseGenericsCommandDraw(struct MenuProc* menu, struct MenuItemProc* menuItem);
u8 PurchaseGenericsCommandEffect(struct MenuProc* menu, struct MenuItemProc* menuItem);
void PurchaseGenerics_OnNewPhase(void);
bool PurchaseGenerics_TryStartTileMenu(int x, int y);

bool AiShouldCaptureBaseInsteadOfAttacking(void);
bool AiFindClosestCapturableBase(struct Vec2* out, u8* distanceOut);
bool AiTryCapturePurchaseBase(struct Unit* unit);

/* The gold price a generic of this class would cost to (re)purchase, or 0
 * if classId has no sPurchaseGenericDefinitions entry -- used by
 * ActionMerge (src/bmmind.c) to price the gold a merge's HP overflow
 * converts to. */
int GetPurchaseGenericPrice(int classId);

/* Read-only preview of the per-turn income factionId currently earns from
 * its owned TRAP_PURCHASE_BASE traps -- same formula as the internal
 * (static) GrantIncomeForFaction, but doesn't mutate any gold total. Used
 * by the faction status screen (uichapterstatus_generics.c). */
int GetFactionIncomePreview(int factionId);

#endif

#endif // GUARD_PURCHASE_GENERICS_H
