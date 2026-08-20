#include "global.h"

#include "bmmap.h"
#include "bmtrick.h"
#include "bmunit.h"
#include "constants/terrains.h"
#include "hardware.h"
#include "mapgen.h"
#include "mapgen_chunks_data.h"
#include "mapgen_save_seed.h"

#if FE8_MAPGEN

/*
 * Procedural chapter maps: randomly place pre-made tile chunks (the .tmx
 * library under scripts/map_gen/chunks/, converted to gMapGenChunks by
 * scripts/mapgen_build_chunks.py -> src/mapgen_chunks_data.c) and fill
 * whatever no chunk claims with plains. Bases are placed independently, in
 * opposite quadrants, unrelated to where the chunks land.
 *
 * THE DETERMINISM CONTRACT
 * ------------------------
 * The generator is split in two halves that run at different times, because
 * FE8 rebuilds map terrain far more often than it creates entities:
 *
 *   InitChapterMap() (src/bmmap.c) runs on a fresh chapter start, on loading a
 *   save, AND on suspend/resume (all three call sites in src/bmio.c). Terrain
 *   therefore cannot be generated from gRNSeeds -- drawing from the live RN
 *   state would both desync the chapter's RNG and hand a resumed game a
 *   different map than the one the player suspended on. So the terrain half is
 *   a pure function of (chapterId, MapGen_SessionSeed()), regenerated
 *   identically every load -- including across a power cycle, since
 *   MapGen_SessionSeed persists its roll into struct MapGenSaveSeed
 *   (include/mapgen_save_seed.h), which round-trips through SRAM the same
 *   way the rest of the save does.
 *
 *   Traps, by contrast, are written to and restored from SRAM (WriteTraps /
 *   ReadTraps, src/bmsave.c). Creating the tents on every map load would stack
 *   duplicates onto a resumed game, so the entity half runs once, at chapter
 *   start only.
 *
 * The two halves never share state; both call MapGen_GetLayout() and get the
 * same answer from the same seed.
 */

// Bounds of the tile-index space addressed by gBmMapBaseTiles. sTilesetConfig
// (src/bmmap.c) is 0x1000 u16 of per-tile config -- 4 u16 per tile -- followed
// by 0x200 u16 of terrain lookup, i.e. 0x400 bytes for 0x400 tiles.
#define MAPGEN_TILE_INDEX_COUNT 0x400

// gBmMapBaseTiles stores tileIndex * 4; RefreshTerrainBmMap()/GetTrueTerrainAt()
// recover the index with >> 2. Same convention the debugger's tileset editor
// writes with (src/VeslyDebugger.c). Index 0 doubles as this generator's
// "cell not yet written" sentinel -- see MapGen_CanPlaceChunk.
#define MAPGEN_TILE(index) ((u16)((index) << 2))

// Keep bases off the outermost ring so a tent always has somewhere to stand.
#define MAPGEN_EDGE_INSET 2

// A map smaller than this has no room for two separated quadrants.
#define MAPGEN_MIN_SIZE 8

static CONST_DATA u8 sMapGenBaseOwner[MAPGEN_BASE_COUNT] = {
    [MAPGEN_BASE_PLAYER] = FACTION_ID_BLUE,
    [MAPGEN_BASE_ENEMY]  = FACTION_ID_RED,
};

/* ---- deterministic value source ---------------------------------------- */

// djb2-derived, then avalanched so that neighbouring salts (which is all we
// ever vary within one map) don't produce visibly correlated results. Values
// come from here rather than NextRN_* for the reason given up top.
static u32 MapGen_Hash(u32 seed, u32 salt)
{
    u32 hash = 5381;

    hash = ((hash << 5) + hash) ^ seed;
    hash = ((hash << 5) + hash) ^ salt;
    hash = ((hash << 5) + hash) ^ (seed >> 16);

    // xorshift finisher: cheap on ARM7 and enough to decorrelate low bits,
    // which matters because every consumer below takes hash % small_number.
    hash ^= hash << 13;
    hash ^= hash >> 17;
    hash ^= hash << 5;

    return hash;
}

// Returns a value in [0, max). max <= 0 always returns 0, rather than
// crashing on a degenerate range -- callers that can hit a zero-width range
// (e.g. a chunk exactly as wide as the map) rely on this.
static int MapGen_Value(u32 seed, u32 salt, int max)
{
    if (max <= 0)
        return 0;

    return MapGen_Hash(seed, salt) % max;
}

// A value that varies between real playthroughs but, once rolled for a given
// save, survives a save/resume (including a power cycle) as long as the
// game has written that save at least once since: mixes GetGameClock()
// (frames elapsed since the last SetGameTime(0) reset, i.e. since New Game --
// or since boot, for a save loaded without starting a new one first) with
// whatever the player's controller state happens to be the first time this
// runs for the save. Both vary with real human timing, so two playthroughs
// land on different maps even with identical menu choices.
//
// Persisted via struct MapGenSaveSeed (include/mapgen_save_seed.h), a
// versioned/checksummed record living in struct ExpansionSaveMeta's
// `reserved` tail right after struct ExpansionUserPrefs -- so it round-trips
// through SRAM the same way the rest of the save does, with no risk of an
// unrelated field (e.g. Link Arena's tactician name) colliding with it.
//
// Rolled lazily -- read back if SRAM already has a valid record for this
// save, rolled and stored if not -- rather than hooked at a single call site
// (WriteNewGameSave, "Continue", debug chapter-jump...) so every path that
// can start play is covered by construction, not by enumeration. If
// MapGenSaveSeed_Store() fails (SRAM not confirmed working, or writes not
// yet allowed this boot -- see gSramBootFlags), the roll is still used for
// this call but is not latched, so it is retried -- and, once storable,
// stored -- on the next call.
static u32 MapGen_SessionSeed(void)
{
    struct MapGenSaveSeed rec;
    u32 seed;

    if (MapGenSaveSeed_Load(&rec) == MAPGEN_SAVE_SEED_VALID)
        return rec.seed;

    seed = GetGameClock();

    if (gKeyStatusPtr != NULL)
    {
        seed ^= (u32)gKeyStatusPtr->heldKeys << 16;
        seed ^= (u32)gKeyStatusPtr->prevKeys;
        seed ^= (u32)gKeyStatusPtr->LastPressState << 8;
        seed ^= (u32)gKeyStatusPtr->TimeSinceStartSelect << 3;
    }

    seed = MapGen_Hash(seed, 0xC0FFEE);

    MapGenSaveSeed_Store(seed);

    return seed;
}

static u32 MapGen_SeedForChapter(int chapterId)
{
    // Chapter id mixed with the session seed, mirroring srr_aw2's per-chapter
    // hash but no longer fixed run to run -- see MapGen_SessionSeed.
    return MapGen_Hash((u32)chapterId, MapGen_SessionSeed());
}

static void MapGen_SetTile(int x, int y, int tileIndex)
{
    if (tileIndex < 0)
        return;

    if (x < 0 || y < 0 || x >= gBmMapSize.x || y >= gBmMapSize.y)
        return;

    gBmMapBaseTiles[y][x] = MAPGEN_TILE(tileIndex);
}

/* ---- layout (bases only -- unrelated to chunk placement) ----------------- */

// Places one point inside the given half-open quadrant, inset from the map
// edge. qx/qy are 0 or 1 and select which half of each axis.
static struct MapGenPoint MapGen_PointInQuadrant(u32 seed, u32 salt, int qx, int qy)
{
    struct MapGenPoint point;

    int halfX = gBmMapSize.x / 2;
    int halfY = gBmMapSize.y / 2;

    int minX = (qx ? halfX : 0) + MAPGEN_EDGE_INSET;
    int minY = (qy ? halfY : 0) + MAPGEN_EDGE_INSET;

    int maxX = (qx ? gBmMapSize.x : halfX) - MAPGEN_EDGE_INSET;
    int maxY = (qy ? gBmMapSize.y : halfY) - MAPGEN_EDGE_INSET;

    if (maxX <= minX)
        maxX = minX + 1;

    if (maxY <= minY)
        maxY = minY + 1;

    point.x = minX + MapGen_Value(seed, salt + 0, maxX - minX);
    point.y = minY + MapGen_Value(seed, salt + 1, maxY - minY);

    return point;
}

void MapGen_GetLayout(int chapterId, struct MapGenLayout * out)
{
    u32 seed = MapGen_SeedForChapter(chapterId);

    // One quadrant for the player, the diagonally opposite one for the enemy,
    // so the two bases are always about as far apart as the map allows.
    int qx = MapGen_Value(seed, 0x10, 2);
    int qy = MapGen_Value(seed, 0x11, 2);

    out->base[MAPGEN_BASE_PLAYER] = MapGen_PointInQuadrant(seed, 0x20, qx, qy);
    out->base[MAPGEN_BASE_ENEMY]  = MapGen_PointInQuadrant(seed, 0x30, !qx, !qy);
}

/* ---- chunk-placement tunables ---------------------------------------------
 * Each knob from the design is its own function, rather than a #define, so it
 * can be changed -- or later made chapter-dependent -- by editing one return
 * value, without touching the placement code around it. */

// Target grid the generator fills. Clamped to the chapter's actual authored
// map size in MapGen_GenerateTerrain, so a chapter smaller than this is not
// written out of bounds.
static int MapGen_MapWidth(void)
{
    return 32;
}

static int MapGen_MapHeight(void)
{
    return 32;
}

// A chunk is rejected for one placement attempt if it has fewer than this
// many filled tiles left after MapGen_ChunkMaxX/Y/Tiles cropping -- otherwise
// a chunk that got cropped down to almost nothing could still be "placed" as
// a near-invisible speck.
static int MapGen_ChunkMinTiles(void)
{
    return 2;
}

// A chunk wider than this is cropped to it, keeping the left MapGen_ChunkMaxX
// columns and dropping the rest; taller than this, the top rows are kept.
// Either crop forces the chunk against the matching map edge (see
// MapGen_ChunkPosition) -- the only placement that hides an arbitrary
// mid-chunk cut rather than stranding it out in the field.
static int MapGen_ChunkMaxX(void)
{
    return 13;
}

static int MapGen_ChunkMaxY(void)
{
    return 13;
}

// If a chunk still has more filled tiles than this after the X/Y crop, rows
// are dropped from the bottom (forcing edge B, same reasoning as above) until
// it fits.
static int MapGen_ChunkMaxTiles(void)
{
    return 80;
}

// Target chunk count for one map is (mapWidth * mapHeight / 10), divided by a
// value rolled in this range each generation -- so chunk density varies map
// to map. Widen the range for more variation, narrow it (both to the same
// value) to fix the density.
static int MapGen_MinChunksDiv(void)
{
    return 1;
}

static int MapGen_MaxChunksDiv(void)
{
    return 2;
}

// Placement gives up after targetChunkCount * this many failed attempts.
static int MapGen_ChunkPlaceAttempts(void)
{
    return 300;
}

// Raw FE8 tile index used to fill whatever cell no chunk claims. 99 is
// Fields' established base plains tile (see scripts/mapgen_data/README.md).
static int MapGen_PlainsFillTile(void)
{
    return 99;
}

/* ---- chunk fitting and placement ------------------------------------------
 * Mirrors scripts/map_gen's own Python reference (fit_chunk_to_limits /
 * chunk_position / can_place_chunk / place_chunk), reimplemented here because
 * this has to run on-console rather than at authoring time. */

struct MapGenFittedChunk
{
    const struct MapGenChunk * chunk;
    int width;
    int height;
    int edgeMask;
};

// Crops a chunk to MapGen_ChunkMaxX/Y/Tiles and records which edges that
// forces. Returns FALSE if the fitted chunk has fewer than
// MapGen_ChunkMinTiles filled cells left -- e.g. everything useful in it got
// cropped away -- in which case *out is left unset and this attempt should be
// treated as failed.
static bool MapGen_FitChunk(const struct MapGenChunk * chunk, struct MapGenFittedChunk * out)
{
    int width = chunk->width;
    int height = chunk->height;
    int edgeMask = chunk->edgeMask;
    int filled;
    int i;

    if (width > MapGen_ChunkMaxX())
    {
        width = MapGen_ChunkMaxX();
        edgeMask |= MAPGEN_EDGE_R;
    }

    if (height > MapGen_ChunkMaxY())
    {
        height = MapGen_ChunkMaxY();
        edgeMask |= MAPGEN_EDGE_B;
    }

    for (;;)
    {
        filled = 0;

        for (i = 0; i < chunk->tileCount; ++i)
        {
            const struct MapGenChunkTile * tile = &gMapGenChunkTiles[chunk->tileOffset + i];

            if (tile->x < width && tile->y < height)
                filled++;
        }

        if (filled <= MapGen_ChunkMaxTiles() || height <= 1)
            break;

        height--;
        edgeMask |= MAPGEN_EDGE_B;
    }

    if (filled < MapGen_ChunkMinTiles())
        return FALSE;

    out->chunk = chunk;
    out->width = width;
    out->height = height;
    out->edgeMask = edgeMask;
    return TRUE;
}

// Chooses where a fitted chunk goes: pinned to whichever map edge(s) its
// edgeMask carries (source edge, or one MapGen_FitChunk's crop forced),
// random on any axis with no such constraint. L beats R and T beats B when a
// chunk somehow carries both of a pair, same precedence as the axis-by-axis
// checks below.
static void MapGen_ChunkPosition(u32 seed, u32 salt, const struct MapGenFittedChunk * fitted,
                                 int mapWidth, int mapHeight, int * outX, int * outY)
{
    int edgeMask = fitted->edgeMask;

    if (edgeMask & MAPGEN_EDGE_L)
        *outX = 0;
    else if (edgeMask & MAPGEN_EDGE_R)
        *outX = mapWidth - fitted->width;
    else
        *outX = MapGen_Value(seed, salt + 0, mapWidth - fitted->width + 1);

    if (edgeMask & MAPGEN_EDGE_T)
        *outY = 0;
    else if (edgeMask & MAPGEN_EDGE_B)
        *outY = mapHeight - fitted->height;
    else
        *outY = MapGen_Value(seed, salt + 1, mapHeight - fitted->height + 1);
}

// x0/y0 already come from MapGen_ChunkPosition, which never proposes a chunk
// past a map it fits in size-wise; the bounds check here is what catches a
// chunk that does not fit at all (e.g. a chapter's authored map smaller than
// MapGen_ChunkMaxX/Y) rather than trusting that invariant blindly.
static bool MapGen_CanPlaceChunk(const struct MapGenFittedChunk * fitted, int x0, int y0,
                                 int mapWidth, int mapHeight)
{
    const struct MapGenChunk * chunk = fitted->chunk;
    int i;

    if (x0 < 0 || y0 < 0 || x0 + fitted->width > mapWidth || y0 + fitted->height > mapHeight)
        return FALSE;

    for (i = 0; i < chunk->tileCount; ++i)
    {
        const struct MapGenChunkTile * tile = &gMapGenChunkTiles[chunk->tileOffset + i];

        if (tile->x >= fitted->width || tile->y >= fitted->height)
            continue;               // cropped away by MapGen_FitChunk

        // MAPGEN_TILE(0) is the "not yet written" sentinel MapGen_GenerateTerrain
        // primes every cell to before placing any chunk. Tile index 0 never
        // appears as real chunk content -- scripts/mapgen_build_chunks.py drops
        // it at the source, since it is the tileset's reserved "undefined"
        // marker -- so reusing it as the occupancy check is safe.
        if (gBmMapBaseTiles[y0 + tile->y][x0 + tile->x] != MAPGEN_TILE(0))
            return FALSE;
    }

    return TRUE;
}

static void MapGen_PlaceChunkAt(const struct MapGenFittedChunk * fitted, int x0, int y0)
{
    const struct MapGenChunk * chunk = fitted->chunk;
    int i;

    for (i = 0; i < chunk->tileCount; ++i)
    {
        const struct MapGenChunkTile * tile = &gMapGenChunkTiles[chunk->tileOffset + i];

        if (tile->x >= fitted->width || tile->y >= fitted->height)
            continue;

        MapGen_SetTile(x0 + tile->x, y0 + tile->y, tile->tile);
    }
}

static void MapGen_PlaceRandomChunks(u32 seed, int mapWidth, int mapHeight)
{
    int divisorRange;
    int divisor;
    int targetCount;
    int placed;
    int attempts;
    int maxAttempts;

    if (gMapGenChunkCount == 0)
        return;

    divisorRange = MapGen_MaxChunksDiv() - MapGen_MinChunksDiv() + 1;
    divisor = MapGen_MinChunksDiv() + MapGen_Value(seed, 0x4000, divisorRange);
    if (divisor < 1)
        divisor = 1;

    // Nearest-integer (mapWidth * mapHeight / 10) / divisor without floats.
    targetCount = (mapWidth * mapHeight + 5 * divisor) / (10 * divisor);
    if (targetCount < 1)
        targetCount = 1;

    maxAttempts = targetCount * MapGen_ChunkPlaceAttempts();

    placed = 0;
    attempts = 0;

    while (placed < targetCount && attempts < maxAttempts)
    {
        u32 salt = 0x5000 + (u32)attempts * 4;
        const struct MapGenChunk * chunk;
        struct MapGenFittedChunk fitted;
        int x0, y0;

        attempts++;

        chunk = &gMapGenChunks[MapGen_Value(seed, salt, gMapGenChunkCount)];

        if (!MapGen_FitChunk(chunk, &fitted))
            continue;

        MapGen_ChunkPosition(seed, salt + 1, &fitted, mapWidth, mapHeight, &x0, &y0);

        if (!MapGen_CanPlaceChunk(&fitted, x0, y0, mapWidth, mapHeight))
            continue;

        MapGen_PlaceChunkAt(&fitted, x0, y0);
        placed++;
    }
}

/* ---- entry points -------------------------------------------------------- */

bool MapGen_IsEnabledForChapter(int chapterId)
{
    (void)chapterId;

    // Deliberately not per-chapter yet: gate real chapters in here (or behind a
    // flag) once there is content to protect. A map too small for two separated
    // quadrants is refused outright so the hand-authored map survives intact.
    if (gBmMapSize.x < MAPGEN_MIN_SIZE || gBmMapSize.y < MAPGEN_MIN_SIZE)
        return FALSE;

    return TRUE;
}

void MapGen_GenerateTerrain(int chapterId)
{
    u32 seed;
    int mapWidth, mapHeight;
    int plainsTile;
    int ix, iy;

    if (!MapGen_IsEnabledForChapter(chapterId))
        return;

    seed = MapGen_SeedForChapter(chapterId);

    mapWidth = MapGen_MapWidth();
    if (mapWidth > gBmMapSize.x)
        mapWidth = gBmMapSize.x;

    mapHeight = MapGen_MapHeight();
    if (mapHeight > gBmMapSize.y)
        mapHeight = gBmMapSize.y;

    // Prime every cell to the "not yet written" sentinel (MAPGEN_TILE(0)) so
    // chunk placement can tell what it may still write to -- see
    // MapGen_CanPlaceChunk.
    for (iy = 0; iy < mapHeight; ++iy)
        for (ix = 0; ix < mapWidth; ++ix)
            MapGen_SetTile(ix, iy, 0);

    MapGen_PlaceRandomChunks(seed, mapWidth, mapHeight);

    // Whatever no chunk claimed becomes plains.
    plainsTile = MapGen_PlainsFillTile();

    for (iy = 0; iy < mapHeight; ++iy)
    {
        for (ix = 0; ix < mapWidth; ++ix)
        {
            if (gBmMapBaseTiles[iy][ix] == MAPGEN_TILE(0))
                MapGen_SetTile(ix, iy, plainsTile);
        }
    }

    // Caller is responsible for RefreshTerrainBmMap(); see the hook in
    // InitChapterMap (src/bmmap.c), which already runs it right after us.
}

void MapGen_PlaceBases(int chapterId)
{
    int i;
    struct MapGenLayout layout;

    if (!MapGen_IsEnabledForChapter(chapterId))
        return;

    MapGen_GetLayout(chapterId, &layout);

    for (i = 0; i < MAPGEN_BASE_COUNT; ++i)
    {
        struct MapGenPoint point = layout.base[i];

        // Never stack a second base onto an occupied tile -- AddTentTrap does
        // not check, and a chapter's own authored traps are loaded before this.
        if (GetTrapAt(point.x, point.y) != NULL)
            continue;

        AddTentTrap(point.x, point.y, sMapGenBaseOwner[i]);
    }
}

#endif // FE8_MAPGEN
