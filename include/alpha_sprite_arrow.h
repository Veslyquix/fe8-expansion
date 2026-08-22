#ifndef GUARD_ALPHA_SPRITE_ARROW_H
#define GUARD_ALPHA_SPRITE_ARROW_H

#include "expansion_config.h"

#if FE8_ALPHA_SPRITE_ARROW
/* Draws a translucent copy of the active unit's map sprite at the cursor,
 * facing the direction it last moved from, standing in for the vanilla
 * dotted movement-path arrow (which this feature otherwise suppresses --
 * see DrawUpdatedPathArrow, src/bmpatharrowdisp.c). A no-op whenever the
 * cursor isn't sitting at the tip of the unit's currently pathfound route,
 * or the unit's map sprite isn't up and walking. */
void AlphaSpriteArrow_DrawUnitGhost(void);
#endif

#endif /* GUARD_ALPHA_SPRITE_ARROW_H */
