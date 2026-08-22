#include "global.h"
#include "alpha_sprite_arrow.h"

#if FE8_ALPHA_SPRITE_ARROW

#include "bm.h"
#include "bmpatharrowdisp.h"
#include "bmunit.h"
#include "ctc.h"
#include "hardware.h"
#include "mu.h"
#include "variables.h"

/* PutSpriteExt only keeps a pointer to the OAM piece list it's handed --
 * it doesn't copy it -- so the per-piece blend-mode patch below has to
 * live somewhere that survives until OAM actually gets flushed, not on
 * the stack. One MU sprite piece list is at most a handful of pieces
 * (attr0/attr1/attr2 triples behind a leading piece count), so a small
 * fixed buffer covers every real map sprite. */
#define ALPHA_SPRITE_ARROW_GHOST_PIECES_MAX 8
static EWRAM_DATA u16 sGhostObjBuf[1 + ALPHA_SPRITE_ARROW_GHOST_PIECES_MAX * 3];

/* BG2 carries the move/attack range overlay and BG3 the plain map --
 * blending target A against target B = {BG2, BG3} lets one config serve
 * both a translucent range tile (which composites against the map
 * underneath) and a translucent ghost OBJ (which needs BG2's colour, i.e.
 * the range tile itself, to blend against when the ghost stands on a
 * highlighted square). OBJ is left out of target B on purpose: pulling
 * ordinary sprites into the blend pass causes unrelated units to flicker. */
static void AlphaSpriteArrow_ApplyGhostBlend(void) {
    SetBlendAlpha(8, 8);
    SetBlendTargetA(0, 0, 1, 0, 0);
    SetBlendBackdropA(0);
    SetBlendTargetB(0, 0, 1, 1, 0);
    SetBlendBackdropB(1);
}

static void AlphaSpriteArrow_PutGhostSprite(struct APHandle* ap, int x, int y) {
    const u16* src;
    int pieceCount;
    int i;

    src = ap->pCurrentObjData;
    if (!src)
        return;

    pieceCount = src[0];
    if (pieceCount <= 0 || pieceCount > ALPHA_SPRITE_ARROW_GHOST_PIECES_MAX)
        return;

    sGhostObjBuf[0] = pieceCount;
    for (i = 0; i < pieceCount; i++) {
        const u16* srcPiece = src + 1 + i * 3;
        u16* dstPiece = sGhostObjBuf + 1 + i * 3;

        /* Force this piece's OBJ mode to semi-transparent, leaving shape/
         * size/tile/palette bits untouched. */
        dstPiece[0] = (srcPiece[0] & ~0x0C00) | OAM0_BLEND;
        dstPiece[1] = srcPiece[1];
        dstPiece[2] = srcPiece[2];
    }

    PutSpriteExt(ap->objLayer, OAM1_X(x), OAM0_Y(y) | OAM0_BLEND, sGhostObjBuf, ap->tileBase);
}

void AlphaSpriteArrow_DrawUnitGhost(void) {
    struct MuProc* mu;
    s8 pathLen;
    int facing;
    int dx, dy;
    int x, y;

    mu = gActiveUnit ? GetUnitMu(gActiveUnit) : NULL;
    if (!mu || !mu->sprite_anim || mu->hidden_b)
        return;

    if (mu->facing == MU_FACING_STANDING)
        return;

    AlphaSpriteArrow_ApplyGhostBlend();

    pathLen = gpPathArrowProc->pathLen;
    if (pathLen < 1) {
        /* Standing on the origin tile: nothing to ghost. */
        if (mu->facing != MU_FACING_SELECTED)
            SetMuFacing(mu, MU_FACING_SELECTED);
        return;
    }

    dx = gpPathArrowProc->pathX[pathLen] - gpPathArrowProc->pathX[pathLen - 1];
    dy = gpPathArrowProc->pathY[pathLen] - gpPathArrowProc->pathY[pathLen - 1];

    if (dx > 0)
        facing = MU_FACING_RIGHT;
    else if (dx < 0)
        facing = MU_FACING_LEFT;
    else if (dy < 0)
        facing = MU_FACING_UP;
    else
        facing = MU_FACING_DOWN;

    if (mu->facing != facing)
        SetMuFacing(mu, facing);

    /* Path tip tile -> screen pixel, matching the map sprite's own draw
     * origin convention (centered horizontally, feet-anchored vertically). */
    x = gpPathArrowProc->pathX[pathLen] * 16 - gBmSt.camera.x + 8;
    y = gpPathArrowProc->pathY[pathLen] * 16 - gBmSt.camera.y + 16;

    if (x < -16 || x > 240 + 16)
        return;
    if (y < -32 || y > 160 + 32)
        return;

    AlphaSpriteArrow_PutGhostSprite(mu->sprite_anim, x, y);
}

#endif /* FE8_ALPHA_SPRITE_ARROW */
