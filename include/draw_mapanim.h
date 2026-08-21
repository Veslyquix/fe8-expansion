#ifndef GUARD_DRAW_MAPANIM_H
#define GUARD_DRAW_MAPANIM_H

#include "global.h"
#include "proc.h"

enum DrawMapAnimId
{
    DRAW_MAP_ANIM_NONE = 0,
    DRAW_MAP_ANIM_BREAK1,
    DRAW_MAP_ANIM_BREAK2,
    DRAW_MAP_ANIM_CIRCLE,
    DRAW_MAP_ANIM_HIT1,
    DRAW_MAP_ANIM_HIT2,
    DRAW_MAP_ANIM_IMPACT1,
    DRAW_MAP_ANIM_IMPACT2,
    DRAW_MAP_ANIM_SHARDS1,
    DRAW_MAP_ANIM_SHARDS2,
    DRAW_MAP_ANIM_SPLASH1,
    DRAW_MAP_ANIM_SPLASH2,
    DRAW_MAP_ANIM_THIN_SLASH,
    DRAW_MAP_ANIM_THICK_SLASH,
    DRAW_MAP_ANIM_FLASH,
    DRAW_MAP_ANIM_FREEZE,
    DRAW_MAP_ANIM_FEATHER,
    DRAW_MAP_ANIM_CAUTERIZE,
    DRAW_MAP_ANIM_HEAL,
    DRAW_MAP_ANIM_FIRE,
    DRAW_MAP_ANIM_THUNDER,
    DRAW_MAP_ANIM_ICE,
    DRAW_MAP_ANIM_WIND,
    DRAW_MAP_ANIM_ELFIRE,
    DRAW_MAP_ANIM_DARK,
    DRAW_MAP_ANIM_MAP_SWORD,
    DRAW_MAP_ANIM_MAP_LANCE,
    DRAW_MAP_ANIM_MAP_AXE,
    DRAW_MAP_ANIM_MAP_BOW,
    DRAW_MAP_ANIM_MAP_MAGIC,
    DRAW_MAP_ANIM_MAP_LIGHT,
    DRAW_MAP_ANIM_MAP_DARK,
    DRAW_MAP_ANIM_MAP_MONSTER,

    DRAW_MAP_ANIM_COUNT,
};

struct DrawMapAnimFrame
{
    u8 duration;
    u16 sfx;
    const u8 * img;
    const u16 * pal;
};

extern CONST_DATA struct ProcCmd ProcScr_DrawMapAnimDefaultItemEffect[];

extern const struct DrawMapAnimFrame * const gDrawMapAnimTable[DRAW_MAP_ANIM_COUNT];
extern const u8 * const gDrawMapAnimNumbersImg;
extern const u16 * const gDrawMapAnimNumbersPal;

#endif /* GUARD_DRAW_MAPANIM_H */
