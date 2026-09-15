# Adding classes, battle animations, map sprites, and portraits

A brief map of the four related pipelines for adding new visual content.
None of these go through the `scripts/generated_data` JSON-authoring flow
described in [`generated_data_tutorial.md`](generated_data_tutorial.md)
except classes' base stat/growth/rank *data* — art assets are their own
scripts and hand-spliced source files.

## Classes (`src/data/classes.json`)

1. Add a `CLASS_*` id to `include/constants/classes.h` (hand-written, not
   generated) — its value must equal the new record's 1-based position in
   `classes.json`'s array.
2. `nameTextId`/`descTextId` need a real message: add `## MSG_YOUR_NAME`
   text to the end of `texts/texts.txt` first, then use the resulting
   `include/constants/msg.h` value as a **decimal integer** — classes.json
   does not accept the symbolic `MSG_*` string form items.json does.
3. Set `"promotion"` for every class, even top-tier ones — it's a paired
   link, not "promotes into": an unpromoted class points forward
   (`CLASS_MYRMIDON → CLASS_SWORDMASTER`), a maxed-out class points
   *backward* to its own base (`CLASS_SWORDMASTER → CLASS_MYRMIDON`).
4. `python3 -m scripts.generated_data validate --table classes`, then
   `generate --table classes --no-roundtrip` (`--no-roundtrip` is
   required for a genuinely new class — the default flow also parses the
   hand-written `src/data_classes.c`, which doesn't have your class yet).
5. **The generated output is not linked into the build.**
   `GENERATED_DATA_LINKED_HAND_SOURCES` in `generated_data.mk` no longer
   includes `classes` — the ROM ships whatever's checked into
   `src/data_classes.c` by hand (it carries real hand-tuned stat
   deviations from `classes.json`). Splice **only your new class's**
   `[CLASS_X - 1] = { ... }` block(s) from the generated output into
   `src/data_classes.c` (append before the closing `};`) — never
   overwrite the whole file, that clobbers every other class's tuning.
   `GetClassData()` has no bounds check, so skipping this step doesn't
   error — it silently reads garbage for the new class instead.
6. Wire an animation: add an `AnimConf_N[]` table (`include/ekrbattle.h`
   has every `extern`) whose `.index` fields point at the class's
   `banim_data[]` slot(s) (one-based — see below), then reference that
   table by name from `classes.json`'s `"battleAnim"` field.

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
  `smsId` (`classes.json`).
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
`unit_icon_move_table[]` rows in the same order as their `classes.json`
records — indexing is positional, so only appending at the end is safe.

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

Watch the indexing: `characters.json`'s `"portrait"` field is **1-indexed**
against `portrait_data.c`'s 0-indexed array (array slot `N` is
`"portrait": N+1`) — confirm the real resolved slot before editing it,
rather than trusting the array's own trailing `// N` comment number to
match the JSON field directly.
