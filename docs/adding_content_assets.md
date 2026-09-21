# Adding classes, battle animations, map sprites, and portraits

A brief map of the four related pipelines for adding new visual content.
All of these are hand-spliced directly into their source files — there is
no JSON-authoring/generation step for any of them.

Whenever adding graphics, update both credit surfaces before calling the
asset done: `CREDITS.md` for full source/artist attribution and
`src/Credits.c` for the in-game credits scroll. Keep the matching section
names in sync with the existing tables/comments instead of creating a
one-off root note.

## Classes (`src/data_classes.c`)

1. Add a `CLASS_*` id to `include/constants/classes.h` — its value must
   equal the new record's 1-based position in `gClassData[]`'s array
   (`src/data_classes.c`).
2. `nameTextId`/`descTextId` need a real message: add `## MSG_YOUR_NAME`
   text to the end of `texts/texts.txt` first, then use the resulting
   `include/constants/msg.h` value.
3. Set `.promotion` for every class, even top-tier ones — it's a paired
   link, not "promotes into": an unpromoted class points forward
   (`CLASS_MYRMIDON → CLASS_SWORDMASTER`), a maxed-out class points
   *backward* to its own base (`CLASS_SWORDMASTER → CLASS_MYRMIDON`).
4. Append a new `[CLASS_X - 1] = { ... }` designated-initializer block to
   `gClassData[]` in `src/data_classes.c`, before the closing `};`. Follow
   the shape of a neighboring record for field names (base/max/growth/
   promotion-gain stat blocks, terrain-lookup fields, etc.) — never
   overwrite the whole file, that clobbers every other class's tuning.
   `GetClassData()` has no bounds check, so skipping this step doesn't
   error — it silently reads garbage for the new class instead.
5. Wire an animation: add an `AnimConf_N[]` table (`include/ekrbattle.h`
   has every `extern`) whose `.index` fields point at the class's
   `banim_data[]` slot(s) (one-based — see below), then reference that
   table by name from the new record's `.battleAnim` field.

## Battle animations (`banim_new*`, gated `FE8_NEW_ANIMS`)

Source: an FE-Repo pack folder (one subfolder per weapon, `Weapon.txt` +
numbered `Weapon_NNN.png` frames — ignore the rest).

1. `scripts/banim_import_pack.py <pack_dir> <tag> --credit "..." --weapons
   Bow,Unarmed --class-tag <≤5 chars>` — copies the script+frames into
   `banim/src/<tag>_<weapon>/` and registers the pack in
   `scripts/banim_packs.json`.
2. `scripts/banim_event_to_source.py --only <tag>,...` — compiles via the
   local pure-Python `tools/aaa/AAA.py` (no Windows/AA.exe needed) into
   `banim/banim_new<tag>_<weapon>_*` + `graphics/banim/banim_new<tag>_<weapon>_*`,
   and writes three scratch files at repo root to splice in by hand:
   `_snip_manifest.txt` → append into `linker_script_banim.txt`,
   `_snip_pointers.h` → append into `include/banim_pointer.h`,
   `_snip_struct.c` → append into `src/banim_data.c`'s `banim_data[]`.
   Each snip file regenerates entries for *every* registered pack — only
   splice the new tail (find where your tag's first entry starts). Delete
   the `_snip_*` files afterward; they're not committed.
3. Importing a pack alone wires nothing to any class — a class only picks
   up the new animation once its own `AnimConf_N[].index` points at the
   new `banim_data[]` slot (`.index` is one-based; slot = `.index - 1`).
4. Add/update the battle-animation credit in `CREDITS.md` and the compact
   in-game credit in `src/Credits.c`.

Two things that will bite you:
- **`banim/data_banim.o` is pinned to a fixed base address**
  (`MODERN_BANIM_DATA_BASE` in `modern.mk`, matched by
  `. = __banim_data_base_abs - __text_start;` in `linker/expansion.ld`)
  because it's a fully pre-linked binary blob, not relocatable code — its
  internal pointers are baked in at that exact address. If a large import
  overflows it, the link fails loudly (`not within region 'rom'`); bump
  `MODERN_BANIM_DATA_BASE` and rebuild, don't try to shrink the import.
- **`make clean_fast` passing is not proof `make clean` also works** —
  they're separate sweep implementations in the Makefile. Test both after
  touching anything under `banim/`.

## Map sprites

Two separate, confusingly-named systems:
- `unit_icon_wait_table[]` (standing icon) — indexed by a class's own
  `smsId` (`src/data_classes.c`).
- `unit_icon_move_table[]`/`gMuInfoTable` (walk animation) — indexed by
  **`classId - 1`**, not `smsId`.

`scripts/insert_map_sprite.py <stand.png> <walk.png> <Name> --motion-template
<ExistingSameSizeClass>` copies the two PNGs into `graphics/unit_icon/`,
clones the template class's motion timing table, and applies one uniform
corrective X shift (median of each frame's own bbox-center delta vs. the
template's art) — then prints every row/extern to splice in by hand,
without writing any source file itself. It never edits anything for you.

**The X offset must be the exact same single value across every frame in
a class's motion table — never computed per-frame.** A walk cycle's
smoothness comes from constant frame-to-frame spacing; per-frame
"corrections" (even when each frame looks better in isolation) produce a
visible side-to-side wobble. If the new class's art is a direct reskin of
the template's, prefer the template's unmodified value (delta 0) over
whatever the script suggests — always eyeball the result in-game before
trusting a nonzero suggested shift.

If adding several classes' sprites in one pass, append their
`unit_icon_move_table[]` rows in the same order as their `gClassData[]`
records (`src/data_classes.c`) — indexing is positional, so only
appending at the end is safe.

Add/update the map-sprite credit in both `CREDITS.md` and `src/Credits.c`;
the source filename's `{...}` artist tag is usually the safest attribution
to preserve.

## Portraits (gated `FE8_CUSTOM_CAMPAIGN`)

`scripts/insert_portrait.py <source.png> <Name>` converts a standard
128×112 FEBuilder portrait sheet into this repo's
`portrait_<Name>_{tileset,chibi,mouth}.png` + `_palette.agbpal` source
files under `graphics/portrait/`, auto-detecting the `xMouth`/`yMouth`/
`xEye`/`yEye` tile offsets `src/portrait_data.c` needs (don't reuse
another character's calibrated offsets — different art always needs its
own detected values).

Splice the result into, all behind `#if FE8_CUSTOM_CAMPAIGN` /
`#else <original> #endif` at the relevant array slot:
- `src/portrait_data.c` — the new `struct FaceData` entry.
- `src/data/data_portrait.c` — the new asset's `INCBIN_U8` lines, inside
  the file's existing `FE8_CUSTOM_CAMPAIGN` block.
- `include/portrait_pointer.h` — matching externs, same block.
- `src/Credits.c` / `CREDITS.md` — artist credit, in the existing "Custom
  Campaign Portraits" table (don't create a new section for it).

Watch the indexing: `src/data_characters.c`'s `.portrait` field is
**1-indexed** against `portrait_data.c`'s 0-indexed array (array slot `N`
is `.portrait = N+1`) — confirm the real resolved slot before editing it,
rather than trusting the array's own trailing `// N` comment number to
match the field directly.
