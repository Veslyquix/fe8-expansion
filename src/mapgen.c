#include "global.h"

#include "bmmap.h"
#include "bmtrick.h"
#include "bmunit.h"
#include "constants/terrains.h"
#include "hardware.h"
#include "mapgen.h"
#include "mapgen_chunks_data.h"

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
 *   MapGen_SessionSeed persists its roll into gPlaySt.mapGenSeed
 *   (include/types.h, #if FE8_MAPGEN), which is per-save-slot and
 *   round-trips through SRAM with the rest of the save.
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
    [MAPGEN_BASE_GREEN]  = FACTION_ID_GREEN, // never auto-placed; see MAPGEN_BASE_GREEN
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

// Free-running frame counter fed by MapGen_TickBootFrames() (include/mapgen.h),
// called from OnVBlank (src/bm.c) as early in boot as the interrupt handler is
// installed. Deliberately NOT GetGameClock()/gGameClock: that clock gets
// reset by SetGameTime() on paths that run before MapGen_SessionSeed ever
// gets to read it -- in particular WriteNewGameSave's own SetGameTime(0),
// which fires before chapter 0's map (and so this generator) ever loads on a
// new game, discarding exactly the boot-to-New-Game menu-navigation entropy
// this needs. Confirmed by observation: GetGameClock() read back as
// essentially constant here, since every real path zeroes it first. This
// counter is never reset by anything, so it keeps whatever it accumulated
// from real elapsed time since boot.
static EWRAM_DATA u32 sMapGenBootFrames = 0;

void MapGen_TickBootFrames(void)
{
    sMapGenBootFrames++;
}

// gPlaySt.mapGenSeed (include/types.h, #if FE8_MAPGEN) is a dedicated field
// appended to struct PlaySt for exactly this. It is PER-SAVE-SLOT (struct
// PlaySt is embedded separately in each of the 3 struct GameSaveBlock/
// SuspendSaveBlock entries) and round-trips through SRAM with the rest of
// that slot automatically -- no new save-format record, and no borrowing an
// unrelated field (an earlier version of this lived in gPlaySt.playerName,
// which worked but meant a Link Arena tactician name could in principle
// collide with it; that is no longer a concern). 0 means "no seed rolled
// yet for this save" -- WriteNewGameSave (src/bmsave.c) resets the field to
// 0 on every new-game creation, which is what makes starting a new game
// in-game reroll the seed, the same way it already does for the rest of a
// fresh save's state.
//
// A value that varies between real playthroughs but, once rolled for a given
// save, survives a save/resume (including a power cycle) as long as the
// game has written that save at least once since: mixes sMapGenBootFrames
// (see above) with whatever the player's controller state happens to be the
// first time this runs for the save. Both vary with real human timing, so
// two playthroughs land on different maps even with identical menu choices.
//
// Rolled lazily -- read back if gPlaySt.mapGenSeed is already nonzero, rolled
// and written into it if not -- rather than hooked at a single call site
// ("Continue", debug chapter-jump...) so every path that can start play is
// covered by construction, not by enumeration. Until whatever roll happens is
// included in an actual SRAM write, it only lives in RAM, same as the rest of
// gPlaySt.
static u32 MapGen_SessionSeed(void)
{
    u32 seed;

    if (gPlaySt.mapGenSeed != 0)
        return gPlaySt.mapGenSeed;

    seed = sMapGenBootFrames;

    if (gKeyStatusPtr != NULL)
    {
        seed ^= (u32)gKeyStatusPtr->heldKeys << 16;
        seed ^= (u32)gKeyStatusPtr->prevKeys;
        seed ^= (u32)gKeyStatusPtr->LastPressState << 8;
        seed ^= (u32)gKeyStatusPtr->TimeSinceStartSelect << 3;
    }

    seed = MapGen_Hash(seed, 0xC0FFEE);

    // 0 means "unrolled" (see gPlaySt.mapGenSeed's own comment above), so a
    // hash that happens to land on exactly 0 (1 in 2^32) is nudged off it --
    // still deterministic given the same inputs, just not the sentinel.
    if (seed == 0)
        seed = 1;

    gPlaySt.mapGenSeed = seed;

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

    // Green gets one of the two remaining (non-diagonal) quadrants -- always
    // computed, same as Player/Enemy, even though MapGen_PlaceBases never
    // places a trap there; see MAPGEN_BASE_GREEN.
    int greenOnXAxis = MapGen_Value(seed, 0x12, 2);
    int gqx = greenOnXAxis ? qx : !qx;
    int gqy = greenOnXAxis ? !qy : qy;

    out->base[MAPGEN_BASE_PLAYER] = MapGen_PointInQuadrant(seed, 0x20, qx, qy);
    out->base[MAPGEN_BASE_ENEMY]  = MapGen_PointInQuadrant(seed, 0x30, !qx, !qy);
    out->base[MAPGEN_BASE_GREEN]  = MapGen_PointInQuadrant(seed, 0x40, gqx, gqy);
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


// NOTE: the tmx file GIDs are these values +1, so take those values and subtract 1 for here 
#define PLAIN_TILE       99
#define HOUSE_TILE       804
#define FORT_TILE        933
#define WOODS_TILE       720
#define THICKET_TILE     721
#define HILL_TILE        685
#define MOUNTAIN_A_TILE  679
#define MOUNTAIN_B_TILE  711

#define PLAIN_WEIGHT       50
#define HOUSE_WEIGHT       0
#define FORT_WEIGHT        0
#define WOODS_WEIGHT       3
#define THICKET_WEIGHT     1
#define HILL_WEIGHT        1
#define MOUNTAIN_A_WEIGHT  1
#define MOUNTAIN_B_WEIGHT  1

struct FillTileWeight
{
    u16 tile;
    u16 weight;
};

static const struct FillTileWeight TileWeights[] =
{
    { PLAIN_TILE,      PLAIN_WEIGHT      },
    { HOUSE_TILE,      HOUSE_WEIGHT      },
    { FORT_TILE,       FORT_WEIGHT       },
    { WOODS_TILE,      WOODS_WEIGHT      },
    { THICKET_TILE,    THICKET_WEIGHT    },
    { HILL_TILE,       HILL_WEIGHT       },
    { MOUNTAIN_A_TILE, MOUNTAIN_A_WEIGHT },
    { MOUNTAIN_B_TILE, MOUNTAIN_B_WEIGHT },
};

#define NUM_TILE_WEIGHTS (sizeof(TileWeights) / sizeof(TileWeights[0]))

static void MapGen_FillRemainingTiles(u32 seed, int mapWidth, int mapHeight)
{
    int totalWeight = 0;
    int ix, iy;
    u32 i;

    for (i = 0; i < NUM_TILE_WEIGHTS; ++i)
        totalWeight += TileWeights[i].weight;

    for (iy = 0; iy < mapHeight; ++iy)
    {
        for (ix = 0; ix < mapWidth; ++ix)
        {
            int roll;
            int accumulatedWeight = 0;
            int tile = PLAIN_TILE;

            if (gBmMapBaseTiles[iy][ix] != MAPGEN_TILE(0))
                continue;

            roll = MapGen_Value(
                seed,
                0x6000 + iy * mapWidth + ix,
                totalWeight
            );

            for (i = 0; i < NUM_TILE_WEIGHTS; ++i)
            {
                accumulatedWeight += TileWeights[i].weight;

                if (roll < accumulatedWeight)
                {
                    tile = TileWeights[i].tile;
                    break;
                }
            }

            MapGen_SetTile(ix, iy, tile);
        }
    }
}

void MapGen_GenerateTerrain(int chapterId)
{
    u32 seed;
    int mapWidth, mapHeight;
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

    MapGen_FillRemainingTiles(seed, mapWidth, mapHeight);

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

    // Player and Enemy always get a base. Green does not -- it's created
    // lazily by MapGen_OverrideUnitSpawnPosition only if the chapter's start
    // event actually loads a Green unit; see MAPGEN_BASE_GREEN.
    for (i = MAPGEN_BASE_PLAYER; i <= MAPGEN_BASE_ENEMY; ++i)
    {
        struct MapGenPoint point = layout.base[i];

        // Never stack a second base onto an occupied tile -- AddTentTrap does
        // not check, and a chapter's own authored traps are loaded before this.
        if (GetTrapAt(point.x, point.y) != NULL)
            continue;

        // AddTentTrap(point.x, point.y, sMapGenBaseOwner[i]);
        AddCampTrap(point.x, point.y, sMapGenBaseOwner[i]);
        // AddTentTrap(0, 0, 1);
        // AddCampTrap(1, 1, 0x80);

    }
}

// Nearest-first search order, matching FindSpawnPositionFrom's convention in
// src/purchase_generics.c (the other place a unit gets placed next to a
// base). Kept as its own copy rather than shared -- purchase_generics.c's
// spawner is FE8_PURCHASE_GENERICS-only and this file must stand alone under
// FE8_MAPGEN alone.
static bool MapGen_FindSpawnTileNear(int baseX, int baseY, int classId, s8 * xOut, s8 * yOut)
{
    static const s8 offsets[][2] =
    {
        { 0, -1 },
        { 1, 0 },
        { 0, 1 },
        { -1, 0 },
        { 1, -1 },
        { 1, 1 },
        { -1, 1 },
        { -1, -1 },
    };

    const struct ClassData * class = GetClassData(classId);
    const s8 * movCost = class->pMovCostTable[0];
    int i;

    for (i = 0; i < (int)(sizeof(offsets) / sizeof(offsets[0])); ++i)
    {
        int x = baseX + offsets[i][0];
        int y = baseY + offsets[i][1];
        int terrain;

        if (x < 0 || y < 0 || x >= gBmMapSize.x || y >= gBmMapSize.y)
            continue;

        if (gBmMapUnit[y][x] != 0)
            continue;

        terrain = gBmMapTerrain[y][x];

        if (movCost[terrain] < 0)
            continue;

        *xOut = x;
        *yOut = y;
        return true;
    }

    return false;
}

bool MapGen_OverrideUnitSpawnPosition(int factionId, int classId, s8 * xPos, s8 * yPos)
{
    struct MapGenLayout layout;
    struct MapGenPoint base;

    if (!MapGen_IsEnabledForChapter(gPlaySt.chapterIndex))
        return false;

    if (factionId != FACTION_ID_BLUE && factionId != FACTION_ID_RED && factionId != FACTION_ID_GREEN)
        return false; // Purple has no MapGen base to spawn beside.

    MapGen_GetLayout(gPlaySt.chapterIndex, &layout);

    if (factionId == FACTION_ID_BLUE)
        base = layout.base[MAPGEN_BASE_PLAYER];
    else if (factionId == FACTION_ID_RED)
        base = layout.base[MAPGEN_BASE_ENEMY];
    else
    {
        // Green has no base from MapGen_PlaceBases -- create one here, the
        // first time a Green unit is actually spawned this chapter, so a
        // chapter whose start event never loads a Green unit never gets one.
        // Idempotent: a later Green spawn this chapter finds the trap this
        // call created and reuses it.
        struct Trap * trap;

        base = layout.base[MAPGEN_BASE_GREEN];
        trap = GetTrapAt(base.x, base.y);

        if (trap == NULL)
            AddCampTrap(base.x, base.y, FACTION_ID_GREEN);
        else if (!IsCampOrTentTrap(trap, PURCHASE_BASE_KIND_CAMP))
            return false; // Tile already held by some other authored trap.
    }

    return MapGen_FindSpawnTileNear(base.x, base.y, classId, xPos, yPos);
}

#endif // FE8_MAPGEN
