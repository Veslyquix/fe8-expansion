#ifndef GUARD_CONSTANTS_BACKGROUNDS_H
#define GUARD_CONSTANTS_BACKGROUNDS_H

enum {
    BG_HOUSE                   = 0x00,
    BG_CAER_PELYN              = 0x01,
    BG_NORMAL_VILLAGE          = 0x02,
    BG_VILLAGE_CLEAR           = 0x03,
    BG_VILLAGE_SUNSET          = 0x04,
    BG_SERAFEW_VILLAGE         = 0x05,
    BG_SERAFEW_FLASHBACK       = 0x06,
    BG_PORT                    = 0x07,
    BG_SHIP                    = 0x08,
    BG_FIREPLACE               = 0x09,
    BG_CASTLE_INTERIOR         = 0x0A,
    BG_CASTLE_NIGHT            = 0x0B,
    BG_GRADO_CHAMBER           = 0x0C,
    BG_GRADO_CHAMBER_FLASHBACK = 0x0D,
    BG_THRONE_NORMAL           = 0x0E,
    BG_THRONE_FLASHBACK        = 0x0F,
    BG_CASTLE_BRIGHT           = 0x10,
    BG_CASTLE_DARK             = 0x11,
    BG_GATE                    = 0x12,
    BG_GARDEN                  = 0x13,
    BG_GARDEN_FLASHBACK        = 0x14,
    BG_MANSE_BACK              = 0x15,
    BG_MANSE_FLASHBACK         = 0x16,
    BG_CELL                    = 0x17,
    BG_PLAIN_1                 = 0x18,
    BG_PLAIN_1_SUNSET          = 0x19,
    BG_PLAIN_1_FOG             = 0x1A,
    BG_GRASS_PLAINS_2          = 0x1B,
    BG_GRASS_PLAINS            = 0x1C,
    BG_PLAIN_2                 = 0x1D,
    BG_PLAIN_2_FOG             = 0x1E,
    BG_PLAIN_2_SUNSET          = 0x1F,
    BG_PLAIN_2_NIGHT           = 0x20,
    BG_STREAM                  = 0x21,
    BG_TREES                   = 0x22,
    BG_FOREST                  = 0x23,
    BG_TOWN                    = 0x24,
    BG_CASTLE_BACK             = 0x25,
    BG_INTERIOR_BLACK          = 0x26,
    BG_INTERIOR_BROWN          = 0x27,
    BG_FORT_SUNSET             = 0x28,
    BG_FORT                    = 0x29,
    BG_PASSAGE                 = 0x2A,
    BG_BURNING_CASTLE          = 0x2B,
    BG_STONE_CHAMBER           = 0x2C,
    BG_STONE_FLASHBACK         = 0x2D,
    BG_RENAIS_CHAMBER          = 0x2E,
    BG_WHITE_CHAMBER           = 0x2F,
    BG_DESERT                  = 0x30,
    BG_DARKLING_WOODS          = 0x31,
    BG_VOLCANO                 = 0x32,
    BG_BLACK_TEMPLE_OUTSIDE    = 0x33,
    BG_BLACK_TEMPLE_INSIDE     = 0x34,
    BG_BLANK                   = 0x35,
    // 0x36 is a second gConvoBackgroundData entry that's just another copy
    // of BG_BLANK, padding the array out so the entries below start safely
    // past BG_RANDOM's fixed sentinel value -- see the comment there.

    BG_RANDOM                  = 0x37, // never a real array index -- see NextRN_N(BG_BLANK) in eventscr.c

#if FE8_MULTIPALETTE_BG
    /* Multipalette (224/256-colour, 8bpp) test backgrounds -- see
     * FE8_MULTIPALETTE_BG in gConvoBackgroundData, src/eventscr2.c. Start at
     * 0x38, one past BG_RANDOM, so a future addition here can never collide
     * with it by accident (BG_RANDOM itself is deliberately never moved). */
    BG_ALTAR_NIGHT_256          = 0x38,
    BG_KH_224            = 0x39,
#endif
};

#endif // GUARD_CONSTANTS_BACKGROUNDS_H
