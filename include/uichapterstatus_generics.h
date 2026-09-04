#ifndef GUARD_UICHAPTERSTATUS_GENERICS_H
#define GUARD_UICHAPTERSTATUS_GENERICS_H

#include "uimenu.h"

#if FE8_PURCHASE_GENERICS

/* "Faction status" screen -- an Advance Wars-style overview of all four
 * factions (units alive, deaths this chapter, bases owned, income,
 * funds), replacing the normal chapter-status screen's menu entry when
 * FE8_PURCHASE_GENERICS is on. See src/uichapterstatus_generics.c. */

extern CONST_DATA struct ProcCmd gProcScr_FactionStatusScreen[];

u8 FactionStatus_MenuCommand(struct MenuProc* menu, struct MenuItemProc* menuItem);

#endif // FE8_PURCHASE_GENERICS

#endif // GUARD_UICHAPTERSTATUS_GENERICS_H
