#ifndef GUARD_CLASS_PREVIEW_H
#define GUARD_CLASS_PREVIEW_H

/* Picking a representative battle animation for a class outside of an actual
 * battle -- for previews and pickers, where there is no real unit with a real
 * equipped weapon to animate.
 *
 * Originally the debugger's graphics viewer only (GetDebuggerDefaultPreviewWeapon
 * / GetDebuggerBanimId in src/VeslyDebugger.c). Lifted here because the CO
 * select carousel (src/coSelect.c) needs the same thing, and VeslyDebugger.c is
 * filtered out of the build entirely when VESLY_DEBUGGER=0 (see modern.mk), so
 * it cannot be depended on from another feature's code. The debugger's own
 * functions now delegate to these, so both paths stay in step. */

/* A sensible weapon for a class to be shown holding: its best-ranked ordinary
 * weapon type, or the appropriate special item for the classes that have one
 * (manaketes, Demon King, mogalls...). ITEM_NONE if the class wields nothing. */
int GetClassPreviewWeapon(int classId);

/* The class's battle animation index for that weapon. Prefers the entry
 * matching the weapon's type, falling back to the class's SPECIAL_BANIM_WTYPE
 * ("unarmed") entry and then to its first entry.
 *
 * Weapon type matters: an unarmed/SPECIAL_BANIM_WTYPE entry is typically the
 * dodge-only animation rather than the class's real combat animation, so pass
 * GetClassPreviewWeapon(classId) unless you specifically want the unarmed one. */
int GetClassPreviewBanimId(int classId, int weapon);

#endif // GUARD_CLASS_PREVIEW_H
