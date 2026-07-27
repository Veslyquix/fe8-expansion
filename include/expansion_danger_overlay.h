#ifndef GUARD_EXPANSION_DANGER_OVERLAY_H
#define GUARD_EXPANSION_DANGER_OVERLAY_H

/*
 * Always-linked semantic probe for the issue #6 player danger/range overlay
 * (see docs/starter_features.md). Zero-initialized EWRAM in every build; only
 * ever written on the enabled feature path (guarded by
 * FE8_EXPANSION_DANGER_OVERLAY_MENU), so a default/disabled build leaves it
 * all-zero for negative-control scenarios. Records semantic counters only --
 * never a pointer value. Expects global.h (u32) to have been included first.
 */

#include "expansion_config.h"

struct ExpansionDangerOverlayProbe
{
    /* 00 */ u32 menuSelectCount;     /* overlay map-menu command selections */
    /* 04 */ u32 dangerDisplayCount;  /* danger-range displays entered */
    /* 08 */ u32 lastRangeTileCount;  /* nonzero danger-range tiles, last display */
    /* 0C */ u32 rangeGraphicsActive; /* 1 while the range graphics are shown, else 0 */
    /* 10 */ u32 cancelReturnCount;   /* range-display cancels that returned to the map */
};

extern struct ExpansionDangerOverlayProbe gExpansionDangerOverlayProbe;

#endif /* GUARD_EXPANSION_DANGER_OVERLAY_H */
