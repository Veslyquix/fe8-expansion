# Map authoring: .tmx vs .mar

A chapter's map layout (the terrain grid FEBuilderGBA's own Map Editor
draws) can be sourced from either of two file formats under
`graphics/map/layout/`:

- **`.mar`** — FEBuilderGBA's own map-editor save format. Every vanilla
  map ships this way; editing one means opening this ROM in FEBuilderGBA,
  redrawing the map, and re-exporting the `.mar` (plus its `.json`
  sidecar) back into the repo.
- **`.tmx`** — a [Tiled](https://www.mapeditor.org/) map, edited directly
  in this repo (or any Tiled install) with no FEBuilder round-trip. This
  is how **custom** maps (map layouts that don't exist in vanilla FE8) are
  authored going forward.

A given map is sourced from exactly one of the two — never both at once
for the same map name. Vanilla maps stay `.mar` and are not expected to
change format. A map can be converted from one format to the other at any
time (see below); nothing about which format a map uses is hardcoded
anywhere else in the build.

## Build pipeline

Both formats compile to the same `graphics/map/layout/<Name>.bin` (then
`.bin.lz`) the game actually reads — the Makefile has one pattern rule per
format (`%.bin: %.mar` and `%.bin: %.tmx`), both landing on the identical
on-disk layout: 1 byte width, 1 byte height, then `width*height` raw
tile values (u16, little-endian).

- `scripts/mar_to_map.py` — `.mar` (+ a `<Name>.json` sidecar holding
  `{"width": W, "height": H}`) → `.bin`. The original, long-established
  path every vanilla map still uses.
- `scripts/tmx_to_map.py` — `.tmx` → `.bin`, no sidecar needed (Tiled's
  XML already carries width/height). Requires `orientation="orthogonal"`,
  `infinite="0"`, and a single `<layer>` whose `<data>` is either Tiled's
  plain per-tile XML form or `encoding="csv"` (not base64/gzip/zlib — in
  Tiled, Map Properties > Tile Layer Format, use "CSV" or "XML").

### The tile-value transform

A raw stored tile value is `(gid - tileset_firstgid) * 4` (gid 0 → value
0). This isn't a guess: `src/mapgen.c`'s own comment states it directly
(`gBmMapBaseTiles stores tileIndex * 4`, `MAPGEN_TILE(index)` computes
`index << 2`) — the same convention `src/VeslyDebugger.c`'s tileset editor
writes with. `scripts/tmx_to_map.py` applies the `* 4` immediately (there
being no further runtime stage that owns it, unlike `FE8_MAPGEN`'s chunk
tiles, which store the raw `gid - 1` in `gMapGenChunkTiles[]` and defer the
shift to placement time). Independently confirmed by round-tripping every
committed `.mar` through both directions and diffing the compiled `.bin`
byte-for-byte (`scripts/maptools_tests/test_map_conversion.py`).

## Converting a map between formats

**`.mar` → `.tmx`** (to start editing an existing/vanilla map in Tiled):

```bash
python3 scripts/mar_to_tmx.py graphics/map/layout/SomeMap.mar graphics/map/layout/SomeMap.tmx \
    --tileset-image path/to/a/real/tileset/spritesheet.png
```

`--tileset-image` is optional but recommended — without it, the `.tmx`'s
`<tileset><image>` is a placeholder path Tiled can't resolve, so it'll
show a "file not found" tileset (the tile *data* is correct either way,
since `tmx_to_map.py` never reads image data — only `<tile gid="N"/>`
values). Delete the old `.mar`/`.json` once you're happy with the `.tmx`
(only one should exist per map — see above).

**`.tmx` → `.mar`**: not currently supported (nothing in this repo needs
to re-import a `.tmx` back into FEBuilderGBA's own editor). If you need
this, FEBuilderGBA can import a flat tile-value grid directly through its
own map editor UI.

## Wiring a new custom map into a chapter

Adding a brand-new map (not converting an existing one) still needs the
usual two-step: declare the `INCBIN_U8` in
`src/data/const_data_chapter_maps.c` (`"graphics/map/layout/<Name>.bin.lz"`)
and reference that symbol from wherever the chapter's map pointer is set
(see `src/data/data_8B363C.c`'s prologue-map swap for a worked,
`FE8_CUSTOM_CAMPAIGN`-gated example — gate any new custom-campaign map
the same way, matching every other custom-campaign asset).
