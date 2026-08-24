#ifndef GUARD_MAPGEN_CHUNKS_DATA_H
#define GUARD_MAPGEN_CHUNKS_DATA_H

#include "global.h"

#if FE8_MAPGEN

/* Data shape for the .tmx chunk library src/mapgen_chunks_data.c is generated
 * from (scripts/mapgen_build_chunks.py, run at build time from every .tmx
 * under scripts/map_gen/chunks/ -- one category folder per subdirectory, a
 * tmx/ folder of chunks in each). See src/mapgen.c for how a chunk is fitted
 * to size and placed. */

enum
{
    // Edges the SOURCE map's crop touched, parsed from the chunk's filename
    // (e.g. "..._edgeTL.tmx"). A chunk is placed flush against whichever of
    // these edges it carries, so a piece that was itself cut off the side of
    // someone's map goes back against a map edge here too, rather than
    // stranding a cut mid-field. See MapGen_ChunkPosition.
    MAPGEN_EDGE_T = 1 << 0,
    MAPGEN_EDGE_B = 1 << 1,
    MAPGEN_EDGE_L = 1 << 2,
    MAPGEN_EDGE_R = 1 << 3,
};

// One non-background cell of a chunk, in the chunk's own local coordinates.
// `tile` is a raw FE8 tile index (already -1 from the .tmx gid, and already
// <<2 is NOT applied -- MapGen_SetTile does that), never 0: index 0 is the
// tileset's "undefined" placeholder and chunks never legitimately place it,
// which is what lets the generator reuse it as an empty-map sentinel.
struct MapGenChunkTile
{
    u8 x;
    u8 y;
    u16 tile;
};

// One chunk, as authored -- width/height here are the RAW .tmx dimensions,
// before MapGen_ChunkMaxX/Y/Tiles cropping, which happens at placement time
// (not baked in), so those limits stay editable without regenerating this
// table. `tiles` are gMapGenChunkTiles[tileOffset .. tileOffset+tileCount).
struct MapGenChunk
{
    u8 width;
    u8 height;
    u8 edgeMask;
    u8 tileCount;
    u16 tileOffset;
};

extern const struct MapGenChunk gMapGenChunks[];
extern const struct MapGenChunkTile gMapGenChunkTiles[];
extern const u16 gMapGenChunkCount;

#endif // FE8_MAPGEN

#endif // GUARD_MAPGEN_CHUNKS_DATA_H
