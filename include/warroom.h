#ifndef GUARD_WARROOM_H
#define GUARD_WARROOM_H

#include "proc.h"

#if FE8_WAR_ROOM
/* Game-mode select screen shown right after the title screen in place of
 * jumping straight to the ordinary save menu (see LGAMECTRL_MODE_SELECT,
 * src/gamecontrol.c). Blocking: loops showing the mode list until the
 * player picks "Campaign" or "Link Arena" (which Proc_Goto the parent
 * GameCtrlProc to the matching vanilla entry point and end this screen)
 * -- "War Room" is handled entirely inside this same screen's own proc
 * tree (see src/warroom.c): picking a chapter there bootstraps a fresh
 * throwaway game state and Proc_Gotos the parent straight into battle
 * (LGAMECTRL_WAR_ROOM_EXEC_BM), also ending this screen. */
void StartWarRoomMainMenu(ProcPtr parent);
#endif

#endif // GUARD_WARROOM_H
