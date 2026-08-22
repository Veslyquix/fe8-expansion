#ifndef GUARD_PROMOTE_COMMAND_H
#define GUARD_PROMOTE_COMMAND_H

#include "global.h"

#if FE8_PROMOTE_COMMAND

#include "uimenu.h"
#include "proc.h"

u8 PromoteCommandUsability(const struct MenuItemDef* def, int number);
int PromoteCommandDraw(struct MenuProc* menu, struct MenuItemProc* menuItem);
u8 PromoteCommandEffect(struct MenuProc* menu, struct MenuItemProc* menuItem);

void PromoteCommand_ActionPromote(ProcPtr proc);

#endif /* FE8_PROMOTE_COMMAND */

#endif /* GUARD_PROMOTE_COMMAND_H */
