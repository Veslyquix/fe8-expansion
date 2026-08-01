# Generated-data platform (Issue #5 Chapter 2 slice -- Batch A + B + C; global `items`/`classes` Batch 1; `characters` Batch 2a + 2b; `classes` linked Batch 2c-1; `items` linked Batch 2c-2; `supports` linked Batch 2c-3; `characters` linked Batch 2c-4; `units`/Chapter 2 `UnitDefinition`/`REDA` linked Batch 3a; `traps`/Chapter 2 trap arrays linked Batch 3b; `shops`/Chapter 2 armory linked Batch 3c; `eventlists`/Chapter 2 event-list composition linked Batch 3d; `terrainstats`/global terrain combat+heal stat arrays linked, Issue #5 mechanics Batch 1; `movecost`/global weather-triplet movement-cost + DemonKing/Ballista tables linked, Issue #5 mechanics Batch 2; `weapontriangle`/global `sWeaponTriangleRules[]` linked, Issue #5 mechanics Batch 3)

## Status

**Slice 0** proved out the deterministic schema/validation/generation/
build/drift plumbing on a single canary table (`SupportData`), end to
end, without replacing or linking any hand-written table.

**Batch A** generalized that framework from supports-only hardcoding to
per-table dispatch, and extended it with the Chapter 2 vertical slice's
pure-data tables:

* `units` -- `UnitDefinition` groups + their `REDA` position arrays for
  all 7 Chapter 2 unit groups.
* `shops` -- `ShopList_Event_Ch2Armory`.
* `traps` -- `TrapData_Event_Ch2`/`TrapData_Event_Ch2Hard`.
* `eventscripts` -- a **metadata-only** inventory of the 43
  `EventScr`/`EventListScr` symbols the Chapter 2 vertical slice depends
  on, and the first real production consumer of the `CSymbolRefField`
  escape hatch (see below).

**Batch B** (this update) adds the chapter *composition* layer on top of
Batch A's leaf tables:

* `eventlists` -- the 7 `EventListScr_Ch2_*` event-list arrays (turn/
  character/location/misc/select-unit/select-destination/unit-move),
  the 30-symbol `EventListScr_Ch2_Tutorial` pointer array, and the full
  `struct ChapterEventGroup Ch2Events` manifest (20 designated fields).
  Event-list entries are modeled **structurally** as macro calls (macro
  name + typed ordered arguments -- `TURN`, `CHAR`, `Village`, `Armory`,
  `DefeatAll`, `CauseGameOverIfLordDies`), never expanding/reimplementing
  the underlying event-script bytecode the macros generate; the
  generator emits the identical C macro-call text `ch2-eventinfo.h`
  hand-writes. `eventlists` cross-validates against Batch A's own
  `units`/`shops`/`traps`/`eventscripts` JSON records (not just "is this
  symbol declared somewhere in a header", which would trivially accept
  any chapter's symbol) via a new, generalized
  `TableSchema.dependency_tables()` mechanism (see below).

None of these tables replace or link any hand-written source yet.
`src/data_supports.c`, `src/events_udefs.c`, `src/events_shoplist.c`,
`src/events_trapdata.c`, `include/eventcall.h`, and
`src/events/ch2-eventinfo.h` all remain the canonical, linked/
authoritative sources. Issue #5 itself is **not closed** by Batch A/B.

**Batch C** (this update) closes that gap: a `chapterbundle` table
(`src/data/ch2_bundle.json`) is a **metadata-only, cross-table view**
tying every Batch A/B Chapter 2 table together into one bundle, plus the
`chapter_settings.json`/`gChapterDataAssetTable` wiring that actually
selects Chapter 2 at runtime:

* Cross-checks `chapter.id`/`chapterSettingsIndex`/`internalName`/
  `mapEventDataId` against `include/constants/chapters.h`,
  `src/data/chapter_settings.json`, and `src/data/data_8B363C.c`'s
  `gChapterDataAssetTable`, proving `mapEventDataId` really does resolve
  to the `eventlists` table's own `Ch2Events` manifest symbol.
* Proves every `units`/`shops`/`traps`/`eventscripts` record this bundle
  declares is reachable -- from the `eventlists` manifest/list-entry
  macro arguments, or from an explicitly-cited hand-written reference
  (`externalReferences`, verified by literal whole-word search, never by
  expanding event-script bytecode) -- so there is no orphan Ch2-owned
  record.
* Cross-checks Chapter 2's required `SupportData` owners (every
  non-enemy unit character) both exist and reciprocate.
* Declares the `CHARACTER_*`/`CLASS_*`/`ITEM_*` IDs Chapter 2's own unit/
  shop/support data actually uses as a **reference-only** dependency set
  -- cross-checked against the live enum headers and against exactly
  what Chapter 2's data references (both directions: undeclared and
  unused), but explicitly **not** claimed as authored by this slice.
* Proves the whole multi-table dependency graph (every registered
  table's `dependency_tables()` edges, not just this one table's own) is
  acyclic and has a deterministic topological order.
* Ships a committed whole-bundle inventory/report
  (`reports/generated_data_bundle_inventory.md`) with per-table record
  counts/digests, the external-reference table, the reference-only
  dependency sets, the full dependency-graph digest/topo-order, and one
  overall bundle digest.
* `generated-data-check` is now wired into
  `.github/workflows/build.yml`, once per job, before the modern debug/
  release linker checks -- see "Make targets" below.

See "## chapterbundle schema (Batch C whole-bundle manifest)" below for
the full write-up, and "Issue #5 completion boundary and status" at the end of this
document for what's still open.

**Issue #5 Batch 1** (this update) adds the first **global, non-chapter-
scoped** table: `items` (`src/data/items.json`), authoring all 206
vanilla `gItemData[]` records (`ITEM_NONE`..`ITEM_UNK_CD`) field-for-field
against `struct ItemData` (`include/bmitem.h`). Unlike every Batch A/B/C
table, `items` is not part of the Chapter 2 vertical slice or the
`chapterbundle` manifest -- it is scoped to schema/generate/round-trip
only, per Issue #5 Batch 1's explicit "no link swap" boundary. See "##
`items` schema (Issue #5 Batch 1: full global item table)" below for the
full write-up.

**Issue #5 Batch 1, continued** (this update) adds the second global
table: `classes` (`src/data/classes.json`), authoring all 127 vanilla
`gClassData[]` records (`CLASS_EPHRAIM_LORD`..`CLASS_PUPIL_T1`)
field-for-field against `struct ClassData` (`include/bmunit.h`). Like
`items`, `classes` is scoped to schema/generate/round-trip only -- no
link swap, no Chapter 2/`chapterbundle` participation. See "##
`classes` schema (Issue #5 Batch 1: full global class table)" below for
the full write-up.

**Issue #5 Batch 2a** added the **schema/dependency-validation
foundation only** for the third global table: `characters`
(`gCharacterData[]`/`struct CharacterData`, `include/bmunit.h`). That
batch did not author any real, complete `src/data/characters.json`
source, nor add `generate.py`/`parser.py`/`inventory.py` -- no C89
emission, no round-trip, no committed inventory, not wired into
`generated_data.mk`/CI. What it provided: `CharactersTableSchema`,
registered in `registry.py`, modeling `gCharacterData[]`'s unique
256-slot dual symbolic (`CHARACTER_*`)/raw-integer (unnamed
generic-template) designator model, every authorable `CharacterData`
field/range/reference, the `supportData` cross-table reference into
`supports`, and a `dependency_tables()` cross-check against `classes`.

**Issue #5 Batch 2b** (this update) completes `characters` to parity
with `items`/`classes`: a real, committed, **all-256-record**
`src/data/characters.json` (`fullCoverage: true` -- 94 symbolic
`CHARACTER_*` records and 162 raw numeric-designator records, including
the unreachable `[0x100 - 1]` padding slot), plus `generate.py`
(deterministic C89 `gCharacterData[]` emission), `parser.py`
(hand-written round-trip parsing, keyed by resolved designator rather
than symbol, since raw records have no symbolic name), and
`inventory.py` (the committed
`reports/generated_data_characters_inventory.md` summary). `characters`
is now in `generated_data.mk`'s `GENERATED_DATA_TABLES` (not the
Chapter-2-scoped `GENERATED_DATA_CH2_TABLES` list, since it's a global
table like `items`/`classes`, not chapter-scoped data), so
`generated-data-check`/`generated-data-generate`/`generated-data-test`
all cover it. The full **256/256** hand-table round trip against the
real `src/data_characters.c` passes with zero diagnostics, and the
generated `build/generated/data/data_characters.c` compiles and
assembles cleanly through the real `cpp | iconv | agbcc | as` pipeline
(mirroring the Makefile's own `$(C_OBJECTS)` recipe) -- like `classes`/
`items`/`supports` (Issue #5 Batch 2c-1 + 2c-2 + 2c-3), it is now also
linked in place
of `src/data_characters.c`
(Issue #5 **Batch 2c-4**, see "Linking a generated table in place of
its hand-written counterpart" below). See "## `characters` schema
(Issue #5 Batch 2a + 2b: full global character table)" below for the
full write-up. Issue #5's other remaining mechanics scope
stays open -- see "Issue #5 completion boundary and status" at the end of this
document.

As of Issue #5 **Batch 3a**, `units` -- the first Chapter-2-*owned*
(not global) table to be linked -- is also linked, in place of its
prefix slice of `src/events_udefs.c` (a much larger multi-chapter hand
file, unlike Batch 2c's whole-file swaps), with zero ROM/ELF address
shift. See "## Linking a Chapter-2-owned partial-file table (Batch 3a:
`units`)" below for the full write-up.

As of Issue #5 **Batch 3b**, `traps` is also linked, in place of its two
symbols in `src/events_trapdata.c` (`TrapData_Event_Ch2` and
`TrapData_Event_Ch2Hard`), also with zero ROM/ELF address shift --
structurally like `units` but with the added wrinkle that its two Chapter
2 symbols live in two non-adjacent hand-written blocks (a normal-mode
block and a hard-mode block, ~1850 lines apart), requiring a
per-symbol-sectioned generated object and a four-piece (not three-piece)
`ldscript.txt` split. See "## Linking two non-adjacent Chapter-2-owned
symbols in one partial-file table (Batch 3b: `traps`)" below for the
full write-up.

As of Issue #5 **Batch 3c**, `shops` is also linked, in place of its one
symbol in `src/events_shoplist.c` (`ShopList_Event_Ch2Armory`), also with
zero ROM/ELF address shift -- structurally like `units` (a single guard,
a single `CONST_DATA` section redirect, a three-piece `ldscript.txt`
split), except the guarded array sits in the *interior* of the shared
shop-list file rather than a prefix: both a still-hand prefix
(`ShopList_Tower*`/`ShopList_Ruin*`) and a still-hand suffix (starting
with `ShopList_Event_Ch5Armory`) must stay glued together, unshifted, on
either side of the generated symbol. See "## Linking a single
Chapter-2-owned interior symbol in a shared shop-list file (Batch 3c:
`shops`)" below for the full write-up.

As of Issue #5 **Batch 3d**, `eventlists` is also linked, in place of
the entire (guarded) `#include "events/ch2-eventinfo.h"` in
`src/events_info.c` -- its 7 `EventListScr_Ch2_*` arrays, the
`EventListScr_Ch2_Tutorial` pointer list, and the `Ch2Events` manifest
(9 symbols total) -- also with zero ROM/ELF address shift. Structurally
like `units` (a single guard, a single `CONST_DATA` section redirect, a
three-piece `ldscript.txt` split), except the guard wraps the whole
`#include` directive rather than any inline array/struct content:
Chapter 2's event-list composition lives entirely in its own header,
`src/events/ch2-eventinfo.h`, never inline in `src/events_info.c`
itself, so that header (not `src/events_info.c`) stays the round-trip
reference the `eventlists/parser.py` check reads. See "## Linking a
Chapter-2-owned table with header-only content (Batch 3d:
`eventlists`)" below for the full write-up.

As of Issue #5 **mechanics Batch 1**, `terrainstats` -- the first
**mechanics-domain** table, and the first *global* (not Chapter-2-owned)
table to use the partial-file-splice pattern `units`/`traps`/`shops`/
`eventlists` established -- is also linked, in place of two non-adjacent
groups of symbols in `src/data_terrains.c` (the 6 `Avo`/`Def`/`Res`
arrays, then, after 5 untouched `Unk_TerrainTable_N` escape-hatch
arrays, the 2 heal arrays), also with zero ROM/ELF address shift.
Structurally like `traps` (two non-adjacent guarded blocks sharing one
guard macro, a per-symbol-sectioned generated object, a five-piece
`ldscript.txt` split with no internal `ALIGN(4)`), except it is
consumed by another authored table rather than the reverse:
`classes/schema.py` now cross-validates its `terrainAvoid`/
`terrainDefense`/`terrainResistance` fields against real `terrainstats`
records instead of plain header-declaration presence. This does **not**
close Issue #5's mechanics scope (movement costs, weapon triangle, and
every other combat/growth/AI formula and table remain untouched) nor
Issue #5 overall -- see "## `terrainstats` schema (Issue #5 Batch 1
mechanics: terrain combat/heal stat arrays)" and "Linking two
non-adjacent groups of terrain combat/heal stat arrays in one
partial-file table (Batch 1 mechanics: `terrainstats`)" below for the
full write-up, and "Issue #5 completion boundary and status" at the end of this
document for the explicit list of what remains open.

As of Issue #5 **mechanics Batch 2**, `movecost` completes the other
clean terrain-mechanics domain: all 45 named Normal/Rain/Snow mobility-
profile arrays plus `TerrainTable_MovCost_DemonKing`/
`TerrainMoveCost_Ballista` (47 arrays total) are authored and linked, in
place of two non-adjacent groups of symbols in `src/data_terrains.c`
(the 32 Normal/DemonKing/Ballista/Rain arrays that open the file, then,
after the untouched `Unk_TerrainTable_1` escape hatch, the 15 Snow
arrays -- immediately preceding the untouched `Unk_TerrainTable_2`
escape hatch and `terrainstats`' own splice), also with zero ROM/ELF
address shift. Structurally like `terrainstats` (two non-adjacent
guarded blocks sharing one guard macro, a per-symbol-sectioned generated
object, no internal `ALIGN(4)`), spliced in as the new canonical `.data`
prefix immediately before `terrainstats`' own splice: `classes/schema.py`
now also cross-validates every non-null `movCostTable` triplet entry
against real `movecost` records (matching normal/rain/snow profile
identity), on top of its existing `terrainstats` cross-validation. This
still does **not** close Issue #5's mechanics scope (the 7
`Unk_TerrainTable_N` escape hatches, weapon triangle, and every other
combat/growth/AI formula and table remain untouched) nor Issue #5
overall -- see "## `movecost` schema (Issue #5 mechanics Batch 2:
weather-triplet movement-cost + DemonKing/Ballista tables)" and "Linking
a weather-triplet movement-cost table split around one non-adjacent
escape hatch (Issue #5 mechanics Batch 2: `movecost`)" below for the
full write-up, and "Issue #5 completion boundary and status" at the end of this
document for the explicit list of what remains open.

As of Issue #5 **mechanics Batch 3**, `weapontriangle` closes out the
last clean vanilla mechanics *table*: the 12 directed weapon-triangle
advantage/disadvantage rules (`sWeaponTriangleRules[]` in
`src/bmbattle.c`) consumed by `BattleApplyWeaponTriangleEffect` -- the
Sword/Axe/Lance physical triangle and Anima/Light/Dark magic triangle,
2 closed 3-type groups x 3 members x 2 directions -- are authored and
canonically linked, in place of a single guarded block at the literal
start of `src/bmbattle.c`'s `.data` section, also with zero ROM/ELF
address shift. Unlike `terrainstats`/`movecost` (partial-file splices
around non-adjacent hand-owned escape hatches inside a shared data
file), `weapontriangle` is a **single, self-contained guarded block**
in a file that is otherwise entirely procedural code (`src/bmbattle.c`
has no other authored data table and no escape hatches to preserve
around it), so its `ldscript.txt` splice is the simplest two-piece
shape yet: the generated object, then the untouched remainder of
`src/bmbattle.o`'s `.data` (redirected to its own
`.data.bmbattletail` section, currently just
`sProcScr_BattleAnimSimpleLock`). The `struct WeaponTriangleRule` type
itself moved from a private definition inside `src/bmbattle.c` to
`include/bmbattle.h`, so both the guarded hand block and the generated
object can share the exact same layout without redefinition -- see "##
Linking a single-block global weapon-triangle rule table (Issue #5
mechanics Batch 3: `weapontriangle`)" below for the full write-up.
`BattleApplyWeaponTriangleEffect` and `BattleApplyReaverEffect`
themselves (the procedural hit/damage-bonus application and the
reaver-weapon inversion formula that consumes this table's *output*)
remain untouched, hand-written code -- only the table is modeled here.
This closes Issue #5's remaining clean-table mechanics scope; every
other combat/growth/AI formula and its bespoke data representation
remains explicitly out of scope -- see "## `weapontriangle` schema
(Issue #5 mechanics Batch 3: `sWeaponTriangleRules[]`)" and "Remaining
Issue #5 scope" at the end of this document for the explicit list of
what remains open.

## Source vs. generated vs. committed-public artifacts

**This table's "Linked into the ROM?" column reflects current status,
not each table's original as-generated-only starting point.** Of the 12
tables in `GENERATED_DATA_TABLES`, 10 produce real compiled C data and are
now **canonically linked**, protected by a table-specific `*-link-check`
Make target (`generated-data-link-check` for the 4 whole-file global
tables, `generated-data-ch2-<table>-link-check` for the 4 Chapter-2-owned
partial-file tables, `generated-data-terrainstats-link-check` for the 1
global partial-file table) that fails the build if the generated object
and its ldscript/Makefile/modern.mk wiring ever drift out of sync. The
remaining 2 tables (`eventscripts`, `chapterbundle`) are
**metadata/schema-only**:
they validate cross-references against real symbols/headers but never
render `struct`/array C initializers of their own, so there is no
generated `.c` for them to link -- their existing hand-written
declaration files remain the sole, unchanged, always-canonical source.

**Canonically linked, whole-file (global tables; Issue #5 Batch 2c-1..2c-4):**

| Artifact | Path | Committed? | Linked into the ROM? |
|---|---|---|---|
| Structured source (classes) | `src/data/classes.json` | Yes | No (not compiled directly) |
| Hand-written C (round-trip reference only, no longer linked) | `src/data_classes.c` | Yes | No -- superseded by the generated object (Batch 2c-1) |
| Generated C89 (bulky) | `build/generated/data/data_classes.c` | **No** (gitignored, `build/`) | **Yes** -- canonical, linked in place of `src/data_classes.c` (`gClassData`) |
| Committed inventory/summary | `reports/generated_data_classes_inventory.md` | Yes (small) | N/A |
| Structured source (items) | `src/data/items.json` | Yes | No |
| Hand-written C (round-trip reference only, no longer linked) | `src/data_items.c` | Yes | No -- superseded by the generated object (Batch 2c-2) |
| Generated C89 (bulky) | `build/generated/data/data_items.c` | **No** (gitignored) | **Yes** -- canonical, linked in place of `src/data_items.c` (`gItemData`) |
| Committed inventory/summary | `reports/generated_data_items_inventory.md` | Yes (small) | N/A |
| Structured source (supports) | `src/data/supports.json` | Yes | No |
| Hand-written C (round-trip reference only, no longer linked) | `src/data_supports.c` | Yes | No -- superseded by the generated object (Batch 2c-3) |
| Generated C89 (bulky) | `build/generated/data/data_supports.c` | **No** (gitignored) | **Yes** -- canonical, linked in place of `src/data_supports.c` (33 `SupportData` symbols) |
| Committed inventory/summary | `reports/generated_data_supports_inventory.md` | Yes (small) | N/A |
| Structured source (characters) | `src/data/characters.json` | Yes | No |
| Hand-written C (round-trip reference only, no longer linked) | `src/data_characters.c` | Yes | No -- superseded by the generated object (Batch 2c-4) |
| Generated C89 (bulky) | `build/generated/data/data_characters.c` | **No** (gitignored) | **Yes** -- canonical, linked in place of `src/data_characters.c` (`gCharacterData`) |
| Committed inventory/summary | `reports/generated_data_characters_inventory.md` | Yes (small) | N/A |

**Canonically linked, Chapter-2-owned partial-file slices (Issue #5 Batch 3a..3d):**

| Artifact | Path | Committed? | Linked into the ROM? |
|---|---|---|---|
| Structured source (units) | `src/data/ch2_units.json` | Yes | No |
| Hand-written C (guarded block, round-trip reference only) | `src/events_udefs.c` | Yes | No -- Chapter 2 slice superseded by the generated object (Batch 3a); rest of the file (other chapters) still hand-linked |
| Generated C89 (bulky) | `build/generated/data/data_ch2_units.c` | **No** (gitignored) | **Yes** -- canonical, linked at the exact original Chapter 2 address, zero shift |
| Committed inventory/summary | `reports/generated_data_units_inventory.md` | Yes (small) | N/A |
| Structured source (traps) | `src/data/ch2_traps.json` | Yes | No |
| Hand-written C (2 guarded blocks, round-trip reference only) | `src/events_trapdata.c` | Yes | No -- both Ch2 symbols (`TrapData_Event_Ch2`/`Ch2Hard`) superseded by the generated object (Batch 3b) |
| Generated C89 (bulky) | `build/generated/data/data_ch2_traps.c` | **No** (gitignored) | **Yes** -- canonical, linked via a 4-piece ldscript split (2 non-adjacent symbols), zero shift |
| Committed inventory/summary | `reports/generated_data_traps_inventory.md` | Yes (small) | N/A |
| Structured source (shops) | `src/data/ch2_shops.json` | Yes | No |
| Hand-written C (guarded block, round-trip reference only) | `src/events_shoplist.c` | Yes | No -- `ShopList_Event_Ch2Armory` superseded by the generated object (Batch 3c) |
| Generated C89 (bulky) | `build/generated/data/data_ch2_shops.c` | **No** (gitignored) | **Yes** -- canonical, linked at the exact original interior address, zero shift |
| Committed inventory/summary | `reports/generated_data_shops_inventory.md` | Yes (small) | N/A |
| Structured source (eventlists) | `src/data/ch2_eventlists.json` | Yes | No |
| Hand-written header (guarded include, round-trip reference only) | `src/events/ch2-eventinfo.h` | Yes | No -- all 9 symbols superseded by the generated object (Batch 3d); header itself left verbatim as the parser's reference |
| Generated C89 (bulky) | `build/generated/data/data_ch2_eventlists.c` | **No** (gitignored) | **Yes** -- canonical, linked at the exact original Chapter 2 address, zero shift |
| Committed inventory/summary | `reports/generated_data_eventlists_inventory.md` | Yes (small) | N/A |

**Canonically linked, global partial-file slice (Issue #5 mechanics Batch 1: `terrainstats`):**

| Artifact | Path | Committed? | Linked into the ROM? |
|---|---|---|---|
| Structured source (terrainstats) | `src/data/terrainstats.json` | Yes | No |
| Hand-written C (2 non-adjacent guarded blocks, round-trip reference only) | `src/data_terrains.c` | Yes | No -- all 8 terrain combat/heal symbols superseded by the generated object (mechanics Batch 1); the 5 `Unk_TerrainTable_N` escape hatches and every movement-cost/graphics array in the same file stay hand-linked, untouched |
| Generated C89 (bulky) | `build/generated/data/data_terrainstats.c` | **No** (gitignored) | **Yes** -- canonical, linked via a 5-piece ldscript split (2 non-adjacent symbol groups), zero shift |
| Committed inventory/summary | `reports/generated_data_terrainstats_inventory.md` | Yes (small) | N/A |

**Canonically linked, global partial-file slice (Issue #5 mechanics Batch 2: `movecost`):**

| Artifact | Path | Committed? | Linked into the ROM? |
|---|---|---|---|
| Structured source (movecost) | `src/data/movecost.json` | Yes | No |
| Hand-written C (2 non-adjacent guarded blocks, round-trip reference only, same file as `terrainstats`) | `src/data_terrains.c` | Yes | No -- all 47 movement-cost symbols superseded by the generated object (mechanics Batch 2); the `Unk_TerrainTable_1`/`_2` escape hatches, `terrainstats`' own 8 symbols, and every graphics array in the same file stay hand-linked, untouched |
| Generated C89 (bulky) | `build/generated/data/data_movecost.c` | **No** (gitignored) | **Yes** -- canonical, spliced in as the new `.data` prefix immediately before `terrainstats`' own splice, via a 4-piece ldscript split (2 non-adjacent symbol groups), zero shift |
| Committed inventory/summary | `reports/generated_data_movecost_inventory.md` | Yes (small) | N/A |

**Metadata/schema-only (no generated C ever produced; existing hand file remains the sole canonical source):**

| Artifact | Path | Committed? | Linked into the ROM? |
|---|---|---|---|
| Structured source (eventscripts) | `src/data/ch2_eventscripts.json` | Yes | No |
| Header declaring the referenced symbols (existing, unchanged) | `include/eventcall.h` | Yes | **Yes** -- unchanged, still canonical (no generated C exists to link) |
| Generated C89 | *(none -- metadata-only table)* | N/A | N/A |
| Committed inventory/summary | `reports/generated_data_eventscripts_inventory.md` | Yes (small) | N/A |
| Structured source (chapterbundle) | `src/data/ch2_bundle.json` | Yes | No |
| Cross-table manifest of the tables above (existing, unchanged) | *(no single dedicated hand file -- validates `units`/`shops`/`traps`/`eventscripts`/`eventlists`/`supports` reachability)* | N/A | N/A |
| Generated C89 | *(none -- metadata-only table)* | N/A | N/A |
| Committed inventory/summary | `reports/generated_data_chapterbundle_inventory.md` | Yes (small) | N/A |

Because the 9 linked tables' generated C is validated byte-for-byte
identical (in compiled `.data` bytes) to the hand-written file/blocks it
replaced, *before* being wired into `ldscript.txt`/`Makefile`/`modern.mk`,
and each stays behind its own `*-link-check` regression gate afterward,
this work cannot introduce `multiple definition` link errors and cannot
silently change gameplay behavior -- ROM output is unchanged (see the
byte-identical rebuild evidence cited in each batch's own write-up
section below). The still-unlinked `eventscripts`/`chapterbundle` tables
have no generated C of their own to link; their validation instead proves
every referenced symbol genuinely exists as declared, so that a future
slice modeling their underlying data (not just references to it) could
extend this same pattern with confidence.

## Package layout

```
scripts/generated_data/
  diagnostics.py     SourceLocation, GeneratedDataError, DiagnosticCollector
  json_loader.py      hand-rolled JSON parser preserving order + file:line:column
  schema.py           SchemaRegistry (name/version dispatch) + DependencyGraph
  validators.py       reusable checks: unique ids, references, ranges,
                       fixed capacities, enum-header symbol extraction
  escape_hatch.py     CSymbolRefField -- typed hand-written-C escape hatch
  cgen.py             C89 emission helpers + write_if_changed
  cparse.py           shared brace-depth-aware C block/initializer parsing
                       helpers reused by the units/traps round-trip parsers
  registry.py         registers every table schema (import this to dispatch)
  cli.py              validate / generate / check subcommands (fully
                       generic -- no per-table `if table == ...:` branches)
  supports/
    schema.py          SupportRecord, load_records(), validate()
    generate.py         C89 emission for SupportData
    parser.py           round-trip parser for src/data_supports.c + comparer
    inventory.py        builds the committed inventory/summary report
  units/
    schema.py           UnitDefinition/REDA records, load_records(), validate()
    generate.py         C89 emission (REDA arrays + UnitDefinition literals)
    parser.py           round-trip parser for src/events_udefs.c + comparer
                         (expands AI helper macros, resolves symbolic/raw
                         charIndex/classIndex)
    inventory.py        builds the committed inventory/summary report
  shops/
    schema.py           ShopRecord (ordered ITEM_* refs), load_records(), validate()
    generate.py         C89 emission (u16[] + auto-appended ITEM_NONE)
    parser.py           round-trip parser for src/events_shoplist.c + comparer
    inventory.py        builds the committed inventory/summary report
  traps/
    schema.py           TrapArray/TrapEntry (flat 6-field u8[] format),
                        load_records(), validate()
    generate.py         C89 emission (auto-appended bare TRAP_NONE terminator)
    parser.py           round-trip parser for src/events_trapdata.c + comparer
    inventory.py        builds the committed inventory/summary report
  eventscripts/
    schema.py           EventScriptRecord (metadata-only), load_records(),
                        validate() -- the first production CSymbolRefField
                        consumer
    inventory.py        builds the committed inventory/summary report
                        (no generate.py/parser.py -- nothing to generate or
                        round-trip for a metadata-only table)
  eventlists/
    schema.py           MacroArg/MacroCall/EventList/TutorialList/Manifest
                        records, load_records(), validate() -- the first
                        production dependency_tables() consumer
                        (units/shops/traps/eventscripts)
    generate.py         C89 emission of the same macro-call text
                        ch2-eventinfo.h hand-writes (no bytecode expansion)
    parser.py           round-trip parser for src/events/ch2-eventinfo.h +
                        comparer -- a paren-depth-aware macro-call
                        tokenizer (no top-level commas between entries,
                        unlike the other tables' array literals)
    inventory.py        builds the committed inventory/summary report
  items/
    schema.py           ItemRecord (full struct ItemData -- 19 authored
                        fields + derived .number), load_records(),
                        validate() -- the first global (non-chapter-scoped)
                        table, covering all 206 vanilla ITEM_* records
                        with full contiguous 0..205 coverage validation
    generate.py         C89 emission of gItemData[] matching the hand
                        file's own default-omission convention field for
                        field (only .weaponType/.iconId always emitted)
    parser.py           round-trip parser for src/data_items.c + comparer
                        (a bespoke offset-preserving entry splitter, since
                        gItemData[] is one 206-entry array needing
                        per-entry line numbers for diagnostics)
    inventory.py        builds the committed inventory/summary report
                        (weapon-type histogram, IA_* attribute usage,
                        pStatBonuses/pEffectiveness pointer-symbol usage)
  classes/
    schema.py           ClassRecord (full struct ClassData -- ~20 authored
                        fields/sub-objects + derived .number), load_records(),
                        validate() -- the second global (non-chapter-scoped)
                        table, covering all 127 vanilla CLASS_* records
                        with full contiguous 1..127 coverage validation
                        (excluding CLASS_NONE/the CLASS_OBSTACLE alias)
    generate.py         C89 emission of gClassData[] matching the hand
                        file's own default-omission convention field for
                        field, including the literal (void *)0x00000000
                        null-pointer cast for immobile classes' movCostTable
    parser.py           round-trip parser for src/data_classes.c + comparer
                        (reuses the same offset-preserving entry splitter
                        pattern as items/parser.py, since gClassData[] is
                        one 127-entry array needing per-entry line numbers)
    inventory.py        builds the committed inventory/summary report
                        (CA_* attribute usage, baseRanks weapon-type
                        histogram, battleAnim symbol usage)
  characters/
    schema.py           CharacterRecord (full struct CharacterData -- ~20
                        authored fields + derived .number), load_records(),
                        validate() -- the third global (non-chapter-scoped)
                        table, covering all 256 vanilla designators (94
                        symbolic CHARACTER_* + 162 raw/generic-template)
                        with full 1..256 coverage validation via the
                        opt-in fullCoverage flag, including the
                        unreachable [0x100 - 1] padding slot
    generate.py         C89 emission of gCharacterData[] matching the
                        hand file's own default-omission convention field
                        for field, deriving .number from the designator
                        (symbol, lowercase-hex raw literal, or the bare
                        wraparound 0 for the padding slot)
    parser.py           round-trip parser for src/data_characters.c +
                        comparer -- keyed by resolved integer designator
                        rather than symbol name (unlike every other
                        table's parser), since raw records have no
                        symbol; normalizes s8 fields the hand file spells
                        as their unsigned decimal equivalent
    inventory.py        builds the committed inventory/summary report
                        (symbolic/raw/reachable/dead-padding counts,
                        defaultClass/affinity/attributes/baseRanks usage
                        histograms, supportData usage, dependency digest)
  chapterbundle/
    schema.py           ChapterBundleRecord (metadata-only whole-bundle
                        view), load_records(), validate() -- cross-checks
                        chapter_settings.json/gChapterDataAssetTable wiring,
                        reachability/orphans, support owners, and
                        character/class/item dependency sets across all 6
                        other dependency_tables(); full_dependency_graph()
                        merges every registered schema's own dependency
                        edges to prove the whole system's table DAG is
                        acyclic (no generate.py/parser.py -- nothing to
                        generate or round-trip for a metadata-only,
                        cross-table bundle)
    inventory.py        builds the committed whole-bundle inventory/
                        summary report (per-table counts/digests,
                        external references, dependency sets, full
                        dependency-graph digest/topo-order, one bundle
                        digest)
  tests/               stdlib unittest suite (see "Testing" below)
```

## Why a hand-rolled JSON parser?

Python's `json` module discards source positions once a value is
decoded. Diagnostics for duplicate/invalid records need to point at
`file:line:column`, so `json_loader.py` implements a small, dependency-free
recursive-descent parser that:

* preserves key/array insertion order (never re-sorted);
* records a `SourceLocation` for every object, array, key, and scalar;
* rejects duplicate object keys at parse time, citing both the first
  definition's location and the duplicate's.

It intentionally supports only the JSON subset this project's data files
use (objects, arrays, strings, numbers, `true`/`false`/`null`, and `//`
line comments) -- it is not a general-purpose JSON5 parser.

## Schema/version dispatch and dependency graph

`schema.SchemaRegistry` maps `(table_name, version)` to a `TableSchema`.
`registry.py` is the single place every table registers itself -- now
`supports`, `units`, `shops`, `traps`, `eventscripts`, `eventlists`, and
`chapterbundle` (all v1); the CLI resolves `--table NAME` through this
registry instead of hardcoding imports, so `cli.py` has zero per-table
branches -- adding a table means adding a package + one line in
`registry.py`, nothing else.

`schema.DependencyGraph` records which headers/tables a schema depends on
(`supports` depends on `constants/characters.h` and
`UNIT_SUPPORT_MAX_COUNT` from `types.h`). It provides a deterministic
topological order (Kahn's algorithm with alphabetical tie-breaking, for
future multi-table generation ordering) and a stable sha256 digest that
is embedded in the committed inventory report -- so a change in a table's
dependencies is visible as a one-line diff, not silent.

### `TableSchema.dependency_tables()` (Batch B: cross-table validation)

Batch A's tables validate purely against headers (enum constants, item
lists, `CSymbolRefField`). `eventlists` is the first table that needs to
validate against *other tables' own JSON records* -- e.g. "does this
`playerUnitsInNormal` symbol actually exist as a `units` group in this
chapter" is a stronger, more meaningful check than "is this symbol
declared anywhere in `include/eventcall.h`", which would trivially
accept any chapter's unit-group symbol.

A schema declares the *other registered table names* it needs loaded by
overriding `dependency_tables()` (default: `()`, i.e. no cross-table
dependency). `cli.py`'s `_load_dependency_records()` loads each declared
dependency deterministically, in declaration order, through the same
schema registry and each dependency's own `default_source` -- so
`eventlists` always cross-checks against the *current* `units`/`shops`/
`traps`/`eventscripts` JSON, not a stale snapshot. Each dependency's
source can be overridden independently with a repeatable
`--dep-source NAME=PATH` CLI flag, which is how this table's own test
fixtures validate in isolation against small fixture-only
`units`/`shops`/`traps`/`eventscripts` records instead of the real
Chapter 2 data (see `tests/fixtures/eventlists/deps_*.json`). When a
schema declares no dependencies, `validate(records, diagnostics)` is
still called with its original 2-argument signature -- Batch A's
5 tables are completely unaffected by this generalization.

## Validation helpers (`validators.py`)

Generic, reusable, and covered independently of any one table:

* `extract_enum_constants(header, name_prefix)` -- regex-scans a C header
  for `NAME = <value>,` enum entries across the *whole file*, filtered
  only by name prefix (used against `include/types.h` to read
  `UNIT_SUPPORT_MAX_COUNT` so the fixed-capacity check can't silently go
  stale if the struct's array size changes, and similarly for other
  single-enum headers). It is **not** used for `CHARACTER_*` references
  anywhere in this framework: `include/constants/characters.h` contains a
  second, separate `event_autoload_pid_idx` enum sharing the same
  `CHARACTER_` textual prefix, so a whole-file prefix scan would wrongly
  admit its event-engine slot sentinels as if they were valid
  `CharacterData` designators. Every table that reads `CHARACTER_*`
  symbols instead delegates to `character_refs.read_character_
  designators()` (see "`characters` schema" below), which scopes strictly
  to the primary designator enum block.
* `validate_unique` -- duplicate-key detection with the first
  definition's location in the message.
* `validate_reference` -- membership in an allowed symbol set.
* `validate_range` -- inclusive numeric range (used for `u8` fields: 0..255).
* `validate_fixed_capacity` -- a count against a fixed C array capacity.
* `validate_parallel_arrays` -- parallel-array length agreement (the
  `characters[]`/`supportExpBase[]`/`supportExpGrowth[]` triple).

## `SupportData` schema (the canary table)

Source: `src/data/supports.json`, one object per owner under `"records"`:

```json
{
  "owner": "CHARACTER_EIRIKA",
  "symbol": "SupportData_Eirika",
  "characters": ["CHARACTER_EPHRAIM", "CHARACTER_SETH", ...],
  "supportExpBase": [30, 25, ...],
  "supportExpGrowth": [4, 3, ...],
  "supportCount": 7
}
```

This mirrors `struct SupportData` in `include/bmreliance.h` field-for-field
(parallel arrays + count), so the round-trip checker needs no semantic
reinterpretation. All 33 vanilla records (every character with a
`SupportData_*` symbol in `src/data_supports.c`) are present, preserving
symbolic character IDs and support values exactly -- no invented content.

Validations enforced (`supports/schema.py: validate()`):

* unique owner IDs and unique generated symbol names across records;
* unique partners within a single owner's record;
* every owner/partner is a defined `CHARACTER_*` constant;
* `characters[]`/`supportExpBase[]`/`supportExpGrowth[]` agree in length,
  and `supportCount` matches that length;
* `supportCount` (and thus partner count) never exceeds
  `UNIT_SUPPORT_MAX_COUNT` (7), read live from `include/types.h`;
* `supportExpBase`/`supportExpGrowth` are in `u8` range (0..255);
* no record lists its own owner as a partner;
* **reciprocal support pairs**: if A lists B as a partner, B must have a
  record, must list A back, and both directions' `supportExpBase`/
  `supportExpGrowth` must match exactly. This is enforced unconditionally
  because every one of the 33 vanilla records satisfies it (verified by
  direct inspection of `src/data_supports.c` before writing this
  validator) -- vanilla Sacred Stones supports are always mutual.

Every diagnostic carries the JSON source's `file:line:column` and a
reference-path breadcrumb (e.g. `records[owner=CHARACTER_EIRIKA]
.characters[2]=CHARACTER_NOT_A_REAL_CHARACTER`).

## Round-trip checker (`supports/parser.py`)

`parse_hand_written(path)` is a small regex-based parser tailored
specifically to the designated-initializer shape used in
`src/data_supports.c` (not a general C parser). `compare_records()`
diffs the generated model (built from the JSON source) against every
parsed hand-written record -- **all 33**, not a sample -- field for field
(owner, characters, supportExpBase, supportExpGrowth, supportCount).
Formatting differences (whitespace, line breaks) are irrelevant since
comparison happens on parsed values, not text; any semantic difference
(missing record, extra record, or a differing value) is reported with the
hand file's line number.

As of Issue #5 **Batch 2c-3**, `supports` is no longer schema/round-trip
only: `build/generated/data/data_supports.c` is linked in place of
`src/data_supports.c` in both the legacy ROM build and the modern object
cohort (`src/data_supports.c` itself stays in the repo, untouched, purely
as this round-trip reference) -- see "## Linking a generated table in
place of its hand-written counterpart (Batch 2c-1 + 2c-2 + 2c-3 +
2c-4)" below
for the full write-up.

## `units` schema (Chapter 2 `UnitDefinition`/`REDA`)

Source: `src/data/ch2_units.json`, one object per `UnitDefinition` group
under `"groups"`; each group has a `symbol` and an ordered `"units"` list.
Covers exactly the 7 vanilla Chapter 2 groups referenced from
`src/events_udefs.c`: `UnitDef_Event_Ch2Ally`, `UnitDef_Ch2Enemy_0`,
`UnitDef_LordSplitAlly`, `UnitDef_Ch2Ally`, `UnitDef_Ch2NPC`,
`UnitDef_Ch2Enemy_1`, `UnitDef_Ch2Enemy_2` (5/6/2/1/2/2/1 units
respectively).

Each unit record mirrors `struct UnitDefinition` (`include/bmunit.h`)
field-for-field: `charIndex`/`classIndex`/`leaderCharIndex` (accept either
a symbolic `CHARACTER_*`/`CLASS_*` constant or a raw integer -- generic
filler units use raw indices that don't have a named constant, exactly
as `src/events_udefs.c` does), `level`/`autolevel`, `allegiance`,
`xPos`/`yPos`, an ordered `items[]` (bounded by `UNIT_DEFINITION_ITEM_COUNT`,
read live from `include/bmunit.h`), `ai[]` (bounded by `UDEF_AIIDX_MAX`,
also read live), and an ordered `redas[]` list of `{x, y}` points
(each becomes a `REDA_<group>_<index>` sub-array; `redaCount` is never
stored in JSON -- it's always derived as `len(redas)`).

`ai[]` values are always the **resolved raw integers** in JSON -- the
round-trip parser (not the JSON source) expands the hand-written file's
AI helper macros (`DefaultAI`, `AttackInRangeAI`, etc., `#define`d in
`include/EA_Standard_Library/AI_Helpers.h`) into the same raw integers
for comparison, so the JSON source itself never needs macro-awareness.

Validations enforced (`units/schema.py: validate()`): unique group
symbols and unique per-unit generated identifiers; every symbolic
`charIndex`/`classIndex`/`leaderCharIndex`/item reference is a defined
constant; `level`/`xPos`/`yPos`/REDA point coordinates are in range;
`items[]`/`ai[]` never exceed their header-derived fixed capacities.

As of Issue #5 **Batch 3a**, `units` is no longer schema/round-trip
only: `build/generated/data/data_ch2_units.o` is linked in place of the
7 `UnitDefinition`/`REDA` groups' prefix slice of `src/events_udefs.c`
(the rest of that hand file -- every other chapter -- stays canonical,
untouched) in both the legacy ROM build and the modern object cohort --
see "## Linking a Chapter-2-owned partial-file table (Batch 3a:
`units`)" below for the full write-up.

## `shops` schema (Chapter 2 armory)

Source: `src/data/ch2_shops.json`, one object per shop list under
`"shops"`: `symbol` and an ordered `items[]` of `ITEM_*` references.
Covers `ShopList_Event_Ch2Armory` -- a plain `u16[]` of item symbols (no
price pairing, unlike some other shop-list shapes in
`src/events_shoplist.c`), terminated by `ITEM_NONE`. The terminator is
never stored in JSON: it's auto-appended by the generator and stripped
before round-trip comparison; explicitly including `ITEM_NONE` in the
JSON `items[]` is a validation error (it would be ambiguous whether the
author meant an early terminator or a literal item reference).

Validations enforced (`shops/schema.py: validate()`): unique shop
symbols; every item is a defined `ITEM_*` constant; `items[]` is
non-empty; `ITEM_NONE` is rejected if present explicitly.

As of Issue #5 **Batch 3c**, `shops` is no longer schema/round-trip
only: `build/generated/data/data_ch2_shops.o` is linked in place of
`ShopList_Event_Ch2Armory` -- a single interior symbol in
`src/events_shoplist.c` (the rest of that hand file -- every other shop
list -- stays canonical, untouched) in both the legacy ROM build and the
modern object cohort -- see "## Linking a single Chapter-2-owned
interior symbol in a shared shop-list file (Batch 3c: `shops`)" below
for the full write-up.

## `traps` schema (Chapter 2 trap arrays)

Source: `src/data/ch2_traps.json`, one object per trap array under
`"traps"`: `symbol` and an ordered `entries[]`. Covers
`TrapData_Event_Ch2`/`TrapData_Event_Ch2Hard` (both trivial -- empty
`entries[]`, matching the vanilla `{ TRAP_NONE }`-only data), but the
schema/generator/round-trip parser support the full flat 6-field-per-entry
`u8[]` format generally (`type, xPos, yPos, subtype, turnCounter, turn`,
per the inline comments in `src/events_trapdata.c`), proven against the
real, non-trivial `TrapData_Event_Ch7` (2 ballista entries) via this
table's test fixtures/round-trip tests.

The array is terminated by a **bare single `TRAP_NONE` token**, not a
zeroed 6-byte entry (confirmed via `TrapData_Event_Ch7`); like the
`items[]` terminator in `shops`, it's auto-appended/stripped, and
explicitly including `TRAP_NONE` as an entry's `type` is a validation
error. `subtype` accepts either a symbolic `ITEM_*` reference (for
`TRAP_BALLISTA`) or a raw `u8` integer (e.g. plain `0` for
`TRAP_GORGON_EGG`), exactly like `UnitDefinition.charIndex`.

Validations enforced (`traps/schema.py: validate()`): unique trap array
symbols; entries-per-array bounded by `TRAP_MAX_COUNT` (=64, read live
from `include/bmtrick.h`); `type` is a defined trap-type enum constant
(scoped precisely to the `TRAP_NONE = 0, ...` enum block, not the
unrelated `TRAP_MAX_COUNT`/`TRAP_EXTDATA_*` constants sharing the
`TRAP_` prefix); `xPosition`/`yPosition`/`subtype`(when raw)/
`turnCounter`/`turn` are in `u8` range.

As of Issue #5 **Batch 3b**, `traps` is no longer schema/round-trip
only: `build/generated/data/data_ch2_traps.o` is linked in place of
`TrapData_Event_Ch2` and `TrapData_Event_Ch2Hard` -- two non-adjacent
symbols in `src/events_trapdata.c` (the rest of that hand file -- every
other chapter/difficulty's traps -- stays canonical, untouched) in both
the legacy ROM build and the modern object cohort -- see "## Linking two
non-adjacent Chapter-2-owned symbols in one partial-file table (Batch
3b: `traps`)" below for the full write-up.

## `eventscripts` schema (metadata-only; the escape-hatch consumer)

Source: `src/data/ch2_eventscripts.json`, one object per script under
`"scripts"`: `owner` (the `struct ChapterEventGroup` category from
`src/events/ch2-eventinfo.h`'s `Ch2Events` -- `turn_based`,
`character_based`, `location_based`, `misc_based`, `tutorial`,
`beginning_scene` -- or `world_map` for the 3 scripts wired from
`src/events/ch2-wm.h` instead), `symbol`, `kind`
(`event_list_scr`/`event_scr_wm`), and `header` (always
`include/eventcall.h` for this slice). All 43 Chapter 2 + Chapter 2
world-map `EventScr_Ch2_*`/`EventScrWM_Ch2_*` symbols required by the
vertical slice are present.

This table is **deliberately metadata-only**: it does not generate,
parse, or reinterpret any event-script/macro body, and it does not model
the higher-level `EventListScr_Ch2_*`/`Ch2Events` composition (those live
only in `.c`/implementation-only `.h` files, never `extern`-declared, so
they're out of `CSymbolRefField`'s header-declared scope by construction
-- that composition is exactly what the `eventlists` table below adds).
It only proves that each of the 43 leaf symbols this slice depends on is
genuinely declared where expected. `default_output_name`/`generate_c`
are left unset, so `cli.py generate` explicitly prints `skip: table
'eventscripts' is metadata-only; no C output generated` rather than
emitting a meaningless empty file.

Validations enforced (`eventscripts/schema.py: validate()`): unique
symbols; `owner`/`kind` are one of the valid enum values; every
`(symbol, header)` pair is checked with `CSymbolRefField` -- the header
file must exist, and the symbol must be found as an `extern`-declared
object in it. This is the first real production use of the escape hatch
(see next section), not just its own test fixtures.

## `eventlists` schema (Chapter 2 event-list composition + `Ch2Events`)

Source: `src/data/ch2_eventlists.json`, three top-level sections:

```json
{
  "$schema": "fe8.eventlists.v1",
  "lists": [
    {
      "field": "turnBasedEvents",
      "symbol": "EventListScr_Ch2_Turn",
      "entries": [
        { "macro": "TURN", "args": [0, "EventScr_Ch2_Turn1Player", 1, 0, "FACTION_ID_BLUE"] }
      ]
    }
  ],
  "tutorial": {
    "field": "tutorialEvents",
    "symbol": "EventListScr_Ch2_Tutorial",
    "entries": ["EventScr_Ch2Tutorial1", "...", "EventScr_Ch2Tutorial30"]
  },
  "manifest": {
    "symbol": "Ch2Events",
    "fields": { "turnBasedEvents": "EventListScr_Ch2_Turn", "...": "..." }
  }
}
```

* **`lists`** covers exactly the 7 `EventListScr_Ch2_*` arrays
  (`turnBasedEvents`/`characterBasedEvents`/`locationBasedEvents`/
  `miscBasedEvents`/`specialEventsWhenUnitSelected`/
  `specialEventsWhenDestSelected`/`specialEventsAfterUnitMoved`), each an
  ordered list of **macro calls**, not plain values -- every entry is
  `{"macro": NAME, "args": [...]}`, where each argument is a bare JSON
  int (C integer literal), a bare JSON string (C symbol/token), or a
  nested `{"macro": ..., "args": [...]}` object (currently only
  `EVFLAG_TMP(n)`, the free chapter-scoped temp-flag range documented in
  `include/constants/event-flags.h`, read live rather than hardcoded).
  This is what "typed ordered args" means in the Issue #5 WHAT section --
  every argument keeps its int/symbol/nested-call shape instead of
  collapsing to an opaque string, so `MacroArg`/`MacroCall.as_tuple()`
  can structurally compare generated vs. hand-parsed calls. Supported
  macros (`MACRO_SPECS` in `eventlists/schema.py`) are exactly the ones
  Chapter 2's hand source uses: `TURN`, `CHAR`, `Village`, `Armory`,
  `DefeatAll`, and the zero-arg, bare (no-parens) `CauseGameOverIfLordDies`
  -- no event-script bytecode is ever expanded or reimplemented; the
  generator emits the identical C macro-call text (see
  `include/EAstdlib.h`/`include/EA_Standard_Library/Main_Code_Helpers.h`
  for the macro definitions this structurally encodes). Each list also
  has a per-field macro allow-list (`ALLOWED_MACROS_BY_FIELD`) and a
  per-field required `event_scr` owner (`EVENT_SCR_OWNER_BY_FIELD`), so
  e.g. a `CHAR(...)` call can't sneak into `turnBasedEvents`, and a
  `TURN(...)` call's script argument must resolve to an `eventscripts`
  record whose `owner` is `"turn_based"`. The bare `END_MAIN` terminator
  is never stored in JSON -- like `ITEM_NONE`/`TRAP_NONE` in
  `shops`/`traps`, it's auto-appended at generation and explicitly
  including it is a validation error.
* **`tutorial`** is the `EventListScr_Ch2_Tutorial[]` pointer array --
  exactly 30 ordered, unique `EventScr_Ch2TutorialN` symbols (each must
  resolve in the `eventscripts` dependency table with `owner ==
  "tutorial"`), terminated by a `NULL` pointer that (like `END_MAIN`
  above) is auto-appended, never stored explicitly.
* **`manifest`** is the full `struct ChapterEventGroup Ch2Events`
  designated initializer -- all 20 fields from `include/chapterdata.h`
  are required (`MANIFEST_FIELD_SPECS`), each tagged with how it's
  resolved: the 7 list fields and `tutorialEvents` must be non-`NULL` and
  match the corresponding declared `lists`/`tutorial` symbol exactly;
  `traps`/`extraTrapsInHard` and the 6 encounter-choice unit fields are
  nullable and, when set, must resolve into the `traps`/`units`
  dependency tables; `beginningSceneEvents` must resolve in
  `eventscripts` with `owner == "beginning_scene"`; `endingSceneEvents`
  must resolve in `eventscripts` (owner unconstrained, since
  `EventScr_Ch2_EndingScene`'s real owner is `"misc_based"` -- it's also
  reused as `DefeatAll`'s argument in `miscBasedEvents`). `NULL` fields
  stay explicit (`null` in JSON, not simply omitted).

Cross-table validation (unit/shop/trap/event-script references) is
resolved against Batch A's own `units`/`shops`/`traps`/`eventscripts`
JSON records, loaded via the new `dependency_tables()` mechanism (see
above) -- not just header declarations, which would trivially accept any
chapter's symbol.

Validations enforced (`eventlists/schema.py: validate()`): exactly the 7
known list fields present, no duplicates/missing/extras; every list/
tutorial symbol pairwise unique; every macro allow-listed for its list;
macro arity and per-argument type (`flag`/`event_scr`/`character`/
`faction`/`shop_symbol`/`int`) checked against `MACRO_SPECS`; `EVFLAG_TMP`
range-checked against the header-derived free range and **unique
chapter-wide** (not just per-list, since temp flags are a shared
chapter-scoped array); duplicate `(x, y)` location coordinates rejected
within `locationBasedEvents`; explicit `END_MAIN`/`NULL` terminators
rejected; the tutorial list is exactly 30 entries, unique, each resolving
to an `owner == "tutorial"` eventscript; every `Ch2Events` designated
field present/known and resolved per its `MANIFEST_FIELD_SPECS` kind.

### Round-trip parsing (`eventlists/parser.py`)

Unlike every other table's array literals, the 7 `EventListScr_Ch2_*`
arrays have **no top-level commas between entries** -- each macro's
expansion already supplies its own trailing comma internally (see
`_EvtParams2`/`_EvtParams4` in `include/eventscript.h`), so
`cparse.split_top_level_entries` (comma-splitting) doesn't apply. Instead
`parser.py` implements a small paren-depth-aware macro-call tokenizer:
read an identifier, optionally followed by a balanced `(...)` argument
list (itself recursively parsed for nested calls like `EVFLAG_TMP(9)`),
repeated until the bare `END_MAIN` sentinel. The tutorial pointer array
and the `Ch2Events` struct *are* plain comma-separated/designated-
initializer literals, so those reuse `cparse.find_matching_brace`/
`extract_designated_fields` directly. `compare_records()` then
structurally diffs (via `MacroCall.as_tuple()`) every generated macro
call, the tutorial list, and every manifest field against
`src/events/ch2-eventinfo.h` -- **100%**, not a sample (Issue #5 Batch B
DONE criterion).

As of Issue #5 **Batch 3d**, `eventlists` is no longer schema/round-trip
only: `build/generated/data/data_ch2_eventlists.o` is linked in place of
the entire (guarded) `#include "events/ch2-eventinfo.h"` in
`src/events_info.c` -- all 9 symbols (the 7 `EventListScr_Ch2_*` arrays,
`EventListScr_Ch2_Tutorial`, and `Ch2Events`) -- in both the legacy ROM
build and the modern object cohort, with zero ROM/ELF address shift; the
hand header itself stays in place, verbatim, as the round-trip
reference `parser.py` (above) reads -- see "## Linking a Chapter-2-owned
table with header-only content (Batch 3d: `eventlists`)" below for the
full write-up.

## `chapterbundle` schema (Batch C whole-bundle manifest)

Source: `src/data/ch2_bundle.json`. Like `eventscripts`, this table is
**metadata-only**: there is no single hand-written C file that *is* "the
bundle" to round-trip against, so `default_hand_source`/
`default_output_name` are both `None` (`generate`/`check` skip C output,
same as `eventscripts`). The bundle is a cross-table *view* over Batch
A/B's own tables, each of which is still independently round-tripped by
its own schema.

```json
{
  "$schema": "fe8.chapterbundle.v1",
  "chapter": {
    "id": "CHAPTER_L_2", "name": "Ch2", "chapterSettingsIndex": 2,
    "internalName": "L02", "mapEventDataId": 13
  },
  "manifest": { "table": "eventlists", "symbol": "Ch2Events" },
  "tables": {
    "units": { "source": "src/data/ch2_units.json", "symbols": ["..."] },
    "shops": { "source": "src/data/ch2_shops.json", "symbols": ["..."] },
    "traps": { "source": "src/data/ch2_traps.json", "symbols": ["..."] },
    "eventscripts": { "source": "src/data/ch2_eventscripts.json", "symbols": ["..."] },
    "eventlists": { "source": "src/data/ch2_eventlists.json", "symbols": ["..."] }
  },
  "supportOwners": { "source": "src/data/supports.json", "required": ["CHARACTER_EIRIKA", "..."] },
  "externalReferences": [
    { "table": "units", "symbol": "UnitDef_Ch2Enemy_0", "file": "src/events/ch2-eventscript.h" }
  ],
  "dependencies": { "characters": ["..."], "classes": ["..."], "items": ["..."] }
}
```

* **`chapter`** is the row this bundle claims to be: `id` must resolve
  in `include/constants/chapters.h`'s `chapter_idx` enum, and its enum
  value must equal `chapterSettingsIndex`; that index's
  `chapter_settings.json` row's `internalName`/`mapEventDataId` must
  match exactly.
* **`manifest`** is which table/symbol `mapEventDataId` resolves to via
  `gChapterDataAssetTable` (parsed from `src/data/data_8B363C.c` with
  `cparse.find_c_array_blocks`/`split_top_level_entries`, the same
  brace-depth-aware helpers `eventlists/parser.py` uses) -- and is
  cross-checked to equal the `eventlists` dependency table's own
  `manifest.symbol`, so the bundle and the `eventlists` table can never
  silently disagree about which array *is* `Ch2Events`.
* **`tables`** covers exactly the 5 registered per-symbol Chapter 2
  tables (`units`/`shops`/`traps`/`eventscripts`/`eventlists` --
  `supports` is chapter-agnostic and is referenced only via
  `supportOwners`, never listed here). Each entry's `symbols` must
  exactly match that table's real records: any declared symbol that
  isn't a real record is an error (a bogus/renamed reference); any real
  record missing from `symbols` is also an error ("stale bundle
  manifest" -- content-level drift distinct from the CLI's own
  committed-inventory drift check).
* **Reachability / orphan check**: every declared `units`/`shops`/
  `traps`/`eventscripts` symbol must be reachable from the `eventlists`
  manifest -- unit/trap fields and shop/event-script macro arguments
  (reusing `eventlists/schema.py`'s own `MACRO_SPECS`) -- or explicitly
  declared in `externalReferences`. An `externalReferences` entry is
  only accepted if its cited symbol literally appears (whole-word) in
  its cited file -- proving the citation is genuine without parsing or
  reimplementing event-script bytecode. (There is no equivalent "orphan
  eventlist": an `eventlists` table's own list/tutorial/manifest symbols
  *are* the manifest, so they're trivially always reachable.) The real
  Ch2 bundle needs external references for the 6 unit groups and 3
  world-map event scripts only reachable from hand-written event-script/
  world-map wiring (`src/events/ch2-eventscript.h`,
  `src/events/lordsplit-eventscript.h`, `src/events/ch2-wm.h`) rather
  than the typed `eventlists` macros.
* **`supportOwners.required`** must equal the *computed* set of every
  Ch2 unit character with a symbolic `charIndex` and
  `allegiance != FACTION_ID_RED` (i.e. every ally/NPC unit, not the red
  faction's boss characters) -- each must have its own `SupportData`
  record in the `supports` dependency table, and every partner that
  record lists must itself have a `SupportData` record (reciprocal
  support required).
* **`dependencies`** is the `characters`/`classes`/`items` this bundle's
  own `units`/`shops`/`supportOwners` data references -- scoped
  deliberately narrowly (not the transitive closure of support
  reciprocal partners or `eventlists` macro-argument characters, which
  are already validated by their own tables) -- cross-checked for
  uniqueness, existence in the live `characters.h`/`classes.h`/
  `items.h` headers, and an exact two-way match against what's actually
  used (undeclared-but-used and declared-but-unused are both errors).
  This is explicitly **reference-only**: it does not claim these
  characters/classes/items are themselves authored by this slice.
* Finally, `full_dependency_graph()` merges *every* registered table
  schema's `dependency_tables()` edges (not just `chapterbundle`'s own)
  into one combined `DependencyGraph` and calls `topo_order()`, proving
  the whole multi-table system -- not just this one table's direct
  dependencies -- is acyclic and deterministic.

Cross-table validation loads `units`/`shops`/`traps`/`eventscripts`/
`eventlists`/`supports` via `dependency_tables()` (same mechanism
`eventlists` uses); the chapter-settings/asset-table/chapters-enum
cross-check instead reads those pre-existing, read-only repo assets
directly (`read_chapter_settings_row()`/`read_asset_table_entries()`),
since they're consumed, not owned, by this schema.

### Committed inventory (`chapterbundle/inventory.py`)

`reports/generated_data_bundle_inventory.md` is the committed,
CI-checked whole-bundle report: per-table symbol counts and a stable
digest of each table's declared symbol list, the `externalReferences`
table (symbol/table/cited file), the `dependencies` sets marked
reference-only, the `full_dependency_graph()` digest and deterministic
topological order, and one overall bundle digest combining all of the
above -- so any drift in any of it (a symbol added/removed anywhere in
the bundle's view, a dependency added/removed, the table graph's shape
changing) fails `generated-data-check`.

## `items` schema (Issue #5 Batch 1: full global item table)

Source: `src/data/items.json` (schema `fe8.items.v1`), one object per
`ITEM_*` record under `"items"`, mirroring `struct ItemData`
(`include/bmitem.h`) field for field: `nameTextId`/`descTextId`/
`useDescTextId`, `weaponType` (`ITYPE_*`), `attributes` (a validated
`IA_*` bitmask list), nullable `statBonuses`/`effectiveness` (C-symbol
references into `ItemBonus_*`/`ItemEffectiveness_*` via
`CSymbolRefField`), `maxUses`/`might`/`hit`/`weight`/`crit`, `range`
(`{min, max}` nibbles, packed into the struct's single `.encodedRange`
byte), `costPerUse`, `requiredWexp` (a `WPN_EXP_*` symbolic threshold --
this is the struct's misleadingly-named `.weaponRank` field; see
`GetItemRequiredExp` in `src/bmitem.c`), `iconId`, `useEffect` (a bare
`u8`; the codebase defines no `USE_EFFECT_*` enum for it), `weaponEffect`
(`WPN_EFFECT_*`), and `weaponExp`. `.number` is **never authored** -- it
always equals the record's own `[ITEM_X]` designator symbol in every one
of the 206 vanilla records, so the generator derives it directly from
each record's own `item` key.

Unlike every Batch A/B/C table, `items` is **global, not chapter-scoped**:
it is not part of `chapterbundle` and covers the entire vanilla `ITEM_*`
enum (`ITEM_NONE`..`ITEM_UNK_CD`, 206 contiguous entries, indices 0..205)
in one flat, index-designated array, rather than a per-chapter group.

Validations enforced (`items/schema.py: validate()`): unique item
entries; **full contiguous `ITEM_*` coverage** (every enum value from 0
to the live max, no gaps or strays -- the one full-coverage check none of
the other tables need, since they only reference a subset of their
enums); `weaponType`/`requiredWexp`/`weaponEffect` are defined enum
constants; `attributes` is a validated, duplicate-free `IA_*` bitmask
list (scoped to the `IA_NONE = 0, ...` block, deliberately excluding the
`// Helpers` combo constants `IA_REQUIRES_WEXP`/`IA_LOCK_ANY`, which no
vanilla record references directly); nullable `statBonuses`/
`effectiveness` via `CSymbolRefField` against `include/bmitem.h`/
`include/variables.h` respectively; all numeric fields' widths/ranges
(`u8`/`u16`, and the `range.min`/`range.max` nibble bounds of `[0, 15]`);
`nameTextId`/`descTextId`/`useDescTextId` bounded by the live
`MSG_COUNT` (read via the new generic `extract_define_constant()`
helper, since `MSG_COUNT` is a `#define`, not an enum entry) and
optionally authored as symbolic `MSG_*` names resolved through the
companion `extract_define_constants()` helper against
`include/constants/msg.h` -- for records that point at an **existing**
message; a framework-authored expansion record must add none (see
"Config-gated content text" below and
`docs/generated_data_tutorial.md`); the optional
`authoringName`/`authoringDescription`/`authoringUseDescription`
literal-text fields (expansion records only, printable 7-bit ASCII,
bounded, never combined with the matching `*TextId`); `iconId`
bounded by a count of `u8 item_icon_*[] = INCBIN_U8(".../*.4bpp")`
declarations in `src/data/data_item_icon.c` -- the strongest
deterministic *source-level* bound available, since the real built
item-icon asset table only exists after `gbagfx` decompresses these
tiles during the build.

The generator (`items/generate.py`) matches the hand file's own
default-omission convention field for field: only `.weaponType` and
`.iconId` are unconditionally emitted (206/206 hand records, including an
explicit `.iconId = 0x0` for `ITEM_NONE`); every other field is omitted
when it equals its default (confirmed there are zero explicit-zero/
`NONE`/`null` occurrences for any conditional field across the entire
206-record hand file). Multi-flag `.attributes` combos are always emitted
in ascending bit-position order, matching every one of the 25 distinct
combos observed in the hand file (verified with zero violations),
regardless of the JSON's own authoring order.

### Round-trip checker (`items/parser.py`)

`gItemData[]` is one large, single, 206-entry designated-initializer
array (not many small per-symbol arrays like the other tables), so the
round-trip parser uses a bespoke, offset-preserving top-level-entry
splitter (`_split_entries_with_offsets`) to keep each `[ITEM_X] = { ... }`
entry's own absolute character offset -- needed for accurate
`file:line:column` diagnostics per entry, since a single offset for the
whole array would be far too coarse. Every field is resolved to the same
symbol-blind canonical tuple (`ItemRecord.as_tuple()`): every enum-valued
field -- `weaponType` (`ITYPE_*`) included, alongside `attributes`/
`requiredWexp`/`weaponEffect` -- reduces to its live integer value, so
JSON authoring order or which of two equal-valued symbolic constants the
hand file happens to use never cause a false mismatch -- only the actual
encoded bytes matter.
`python3 -m unittest scripts.generated_data.tests.test_items_roundtrip`
proves all 206/206 records match `src/data_items.c` exactly with zero
diagnostics.

### Committed inventory (`items/inventory.py`)

`reports/generated_data_items_inventory.md` is the committed, CI-checked
report: total record count and index range, a weapon-type histogram, an
`IA_*` attribute-usage histogram, `pStatBonuses`/`pEffectiveness`
pointer-symbol usage tables, and the table's own dependency-graph digest.

### Config-gated content text (issue #6)

`texts/texts.txt` is unconditional and compiles into ONE shared,
Huffman-compressed blob (`src/msg_data.c`), so appending a content-only
message re-encodes the text of **every** build -- default, feature-free ones
included. A framework-authored (expansion overlay) record therefore adds no
message: it leaves `nameTextId`/`descTextId`/`useDescTextId` unset and
authors its original display text literally, in the record, as
`authoringName` (plus the audit-only `authoringDescription`/
`authoringUseDescription`).

`scripts/generated_data/items/content_text.py` +
`python3 -m scripts.generated_data content-text` turn that authoring input
into two BUILD-LOCAL artifacts, and only in the content profile
(`EXPANSION_STARTER_CONTENT=1`, which also requires an item cap that reaches
the expansion IDs):

| Artifact | Contents |
|---|---|
| `build/generated/data/items_expansion_content_text.h` | A C89, `ItemId`-keyed table of the authored **names** plus `EXPANSION_CONTENT_TEXT_COUNT`/`EXPANSION_CONTENT_TEXT_NAME_CAPACITY`. `src/expansion_starter_content.c` includes it (the include path is extended only in that profile) and publishes the narrow typed accessor the production `GetItemName()` reads. |
| `build/generated/data/items_expansion_content_text.json` | An audit catalog of the same authored text *including* the descriptions, which the vanilla message-ID-addressed help UI cannot show and which are explicitly labelled as such. |

At `EXPANSION_STARTER_CONTENT=0` the command writes nothing and removes any
artifact a previous content build left behind, so a default build can neither
generate nor link a content string. Neither artifact is ever committed, and
the generated table is never hand-edited. `gItemData[]` itself is
byte-identical with or without the authoring fields -- they never reach the
item table.

## `classes` schema (Issue #5 Batch 1: full global class table)

Source: `src/data/classes.json` (schema `fe8.classes.v1`), one object per
`CLASS_*` record under `"classes"`, mirroring `struct ClassData`
(`include/bmunit.h`) field for field: `nameTextId`/`descTextId`,
`promotion` (a self-referential `CLASS_*` symbol, default `CLASS_NONE`
meaning "does not promote"), `smsId`, `slowWalking` (authored as a JSON
boolean -- only 2 valid states, `UNIT_WALKSPEED_FAST`/`_SLOW`),
`defaultPortraitId`, `sortOrder`, nested `base`/`max`/`growth`/
`promotionGain` stat sub-objects (mirroring `items`' `range: {min, max}`
pattern), `classRelativePower`, `attributes` (a validated `CA_*` bitmask
list), `baseRanks` (a sparse `{ITYPE_*: WPN_EXP_*}` map, keyed by weapon
type), nullable `battleAnim` (a `CSymbolRefField` reference into
`AnimConf_*`, `include/ekrbattle.h`), a required 3-entry `movCostTable`
(`[normal, rain, snow]`, each either a `TerrainTable_MovCost_*`
`CSymbolRefField` reference or JSON `null` for the 9/127 fully-immobile
vanilla records that use a literal `(void *)0x00000000` null-pointer cast
instead of a named table -- gorgon-egg forms, spent/empty ballistae,
`CLASS_UNK77`), required `terrainAvoid`/`terrainDefense`/
`terrainResistance` (`CSymbolRefField` references into
`TerrainTable_{Avo,Def,Res}_*`), and nullable `reservedTerrainTable`
(models the struct's unresearched `._pU50` escape-hatch field, a
`CSymbolRefField` reference into `Unk_TerrainTable_*`). `.number` is
**never authored** -- it always equals the record's own `[CLASS_X - 1]`
designator symbol in every one of the 127 vanilla records, so the
generator derives it directly from each record's own `class` key.

Like `items`, `classes` is **global, not chapter-scoped**: it is not part
of `chapterbundle` and covers the entire vanilla `CLASS_*` enum
(`CLASS_EPHRAIM_LORD`..`CLASS_PUPIL_T1`, 127 contiguous entries, indices
1..127) in one flat, index-designated array. `CLASS_NONE` (index 0, the
sentinel "no class" value) and the `CLASS_OBSTACLE` alias
(`#define`-like `CLASS_OBSTACLE = CLASS_EPHRAIM_LORD`, not its own enum
value) are both excluded from the required-coverage set.

Validations enforced (`classes/schema.py: validate()`): unique class
entries; **full contiguous `CLASS_*` coverage** (1..127, excluding
`CLASS_NONE`/`CLASS_OBSTACLE`); `promotion` is a defined `CLASS_*`
constant; `attributes` is a validated, duplicate-free `CA_*` bitmask list
(scoped to the `CA_NONE = 0, ...` block, deliberately excluding the
`// Helpers` combo constants `CA_REFRESHER`/`CA_FLYER`/
`CA_TRIANGLEATTACK_ANY`, which no vanilla record references directly);
`baseRanks` entries are validated `ITYPE_*` -> `WPN_EXP_*` pairs, bounded
to the struct's own live `baseRanks[8]` capacity (read from
`include/bmunit.h`, not hardcoded); all numeric fields' widths/ranges at
their **actual C type** bounds (`s8` stats validated against the full
`[-128, 127]` range, not just the narrower all-non-negative range every
vanilla value happens to use; `promotionGain`/`sortOrder` against `u8`'s
`[0, 255]`); `nameTextId`/`descTextId` bounded by the live `MSG_COUNT`;
`defaultPortraitId` bounded by the live count of numbered entries in
`src/portrait_data.c`'s `portrait_data[]` (172 entries, 0..171) and
`smsId` bounded by the live count of numbered entries in
`src/unit_icon_wait_data.c`'s `unit_icon_wait_table[]` (107 entries,
0..106) -- both the strongest deterministic *source-level* bounds
available, and, for `smsId`, provably **stronger** than the runtime
`GetInfo()` macro's raw 7-bit mask (`(id) & ((1<<7)-1)`, i.e. 0..127):
indices 107..127 would read past the real table's end, so validating
against the table's actual length (not the mask width) is the correct
bound; the exact `movCostTable` triplet capacity (read from
`include/bmunit.h`, not hardcoded); and every C-symbol-reference field
(`battleAnim`, non-null `movCostTable` entries, the three terrain
lookups, `reservedTerrainTable`) via `CSymbolRefField` against
`include/ekrbattle.h`/`include/variables.h` -- no new header declarations
were needed since every required symbol already has a public `extern`.

As of Issue #5 **Batch 1 (mechanics)**, `terrainAvoid`/`terrainDefense`/
`terrainResistance` are validated more strongly than plain
`CSymbolRefField` header presence: `ClassesTableSchema.validate()` now
accepts an optional `dependency_records` map (supplied automatically by
the CLI via the same `dependency_tables()` mechanism `eventlists`/
`chapterbundle` already use, now returning `("terrainstats", "movecost")`,
extended in **Batch 2** to add `movecost`) and, when `terrainstats`
records are supplied, cross-checks each of the three referenced symbols
against the authored `src/data/terrainstats.json` records: the symbol
must exist as a `terrainstats` record, **and** that record's own `field`
metadata (`terrainAvoid`/`terrainDefense`/`terrainResistance`) must match
the `ClassData` field referencing it -- a class cannot, for example,
reference a `terrainDefense`-tagged array through its `terrainAvoid`
field. `ClassData` records have no explicit "mobility" (`Common` vs.
`Fly`) field of their own, so this check is symbol-identity-based, not
role-based: it does not (and does not need to) know or care whether a
class is a flier. As of Issue #5 **mechanics Batch 2**, `movCostTable`
entries are validated the same way against authored `movecost` records
(see "### `classes` cross-validation against `movecost`" under "##
`movecost` schema" below for the full write-up); `reservedTerrainTable`
remains the one field **not** covered by cross-table validation and
stays a plain `CSymbolRefField` escape hatch (its target
`Unk_TerrainTable_*` arrays are unresearched and explicitly out of
scope). When `dependency_records` is omitted (e.g. standalone unit
tests), `validate()` falls back to the original `CSymbolRefField`-only
check for all four fields, so the schema stays usable without wiring up
the full dependency-graph machinery.

The generator (`classes/generate.py`) matches the hand file's own
default-omission convention field for field (confirmed per-field
presence statistics across all 127 hand records): `smsId` and all
base/max/growth/promotionGain stats, `pMovCostTable`, and the three
terrain lookups are unconditionally emitted; every other field
(`nameTextId`/`descTextId`, `promotion`, `slowWalking`,
`defaultPortraitId`, `sortOrder`, `classRelativePower`, `attributes`,
`baseRanks`, `battleAnim`, `reservedTerrainTable`) is omitted when it
equals its default. Multi-flag `.attributes` combos and `.baseRanks`
entries are always emitted in ascending bit-value/weapon-type-index
order, matching the hand file's own convention regardless of the JSON's
own authoring order. Null `movCostTable` entries emit the literal
`(void *)0x00000000` cast back verbatim, byte-for-byte matching the hand
file's own convention for immobile classes; `reservedTerrainTable` is the
only pointer field emitted with an explicit `&` prefix (its C type is
`const void*`, not `const s8*`, so a bare array-decay wouldn't have the
right type -- exactly mirroring `items`' `pStatBonuses` (`&`-prefixed)
vs. `pEffectiveness` (bare) asymmetry).

### Round-trip checker (`classes/parser.py`)

Like `items/parser.py`, `gClassData[]` is one large, single, 127-entry
designated-initializer array, so the round-trip parser reuses the same
offset-preserving top-level-entry splitter for accurate `file:line:column`
diagnostics per `[CLASS_X - 1] = { ... }` entry. Every field is resolved
to the same symbol-blind canonical tuple (`ClassRecord.as_tuple()`):
`promotion`/`attributes`/`baseRanks` reduce to their live integer
value(s); `battleAnim`/`movCostTable` entries/terrain lookups/
`reservedTerrainTable` are compared as bare token strings (no further
numeric encoding exists to resolve) -- and the literal
`(void *)0x00000000` null-pointer cast is recognized as the same "no
table" sentinel as JSON `null`, not a mismatched symbol.
`python3 -m unittest scripts.generated_data.tests.test_classes_roundtrip`
proves all 127/127 records match `src/data_classes.c` exactly with zero
diagnostics.

### Committed inventory (`classes/inventory.py`)

`reports/generated_data_classes_inventory.md` is the committed,
CI-checked report: total record count and index range, promotion/
slow-walking/no-battle-anim/reserved-terrain-table counts, a `CA_*`
attribute-usage histogram, a `baseRanks` weapon-type histogram,
`battleAnim` symbol-usage table, and the table's own dependency-graph
digest.

## `terrainstats` schema (Issue #5 Batch 1 mechanics: terrain combat/heal stat arrays)

Source: `src/data/terrainstats.json` (schema `fe8.terrainstats.v1`), one
object per terrain-stat array under `"tables"`: `symbol`, `field` (one
of `terrainAvoid`/`terrainDefense`/`terrainResistance`/`healAmount`/
`healsStatus` -- the same `terrainAvoid`/`terrainDefense`/
`terrainResistance` vocabulary `classes/schema.py` uses for its own
`ClassData` pointer fields, so the two schemas share one naming axis
without either importing the other), `mobility` (`common`/`fly`, or
JSON `null` for the two heal arrays, which have no `_Common`/`_Fly`
variant), and an ordered `entries[]` keyed by `TERRAIN_*` constant.
Covers exactly 8
vanilla arrays -- `TerrainTable_Avo_Common`/`Def_Common`/`Res_Common`,
`TerrainTable_Avo_Fly`/`Def_Fly`/`Res_Fly`, `TerrainTable_HealAmount`,
`TerrainTable_HealsStatus` -- deliberately excluding the 5 unrelated
`Unk_TerrainTable_3`..`Unk_TerrainTable_7` escape-hatch arrays and every
movement-cost/graphics table that also lives in `src/data_terrains.c`;
none of those are part of this batch's scope (see "Issue #5 completion boundary and status" at the end of this document).

Validations enforced (`terrainstats/schema.py: validate()`): unique
array symbols; **full contiguous `TERRAIN_*` coverage** for every array
(every terrain key from the live `TERRAIN_*` enum in
`include/constants/terrains.h` must appear exactly once per array, in
enum order -- no gaps, no duplicates, no keys outside the enum, and no
array may cover a different key set than any other); the exact `s8`
range (`[-128, 127]`) for every entry value; `field` is one of the 5
valid enum values and matches the array's role (an `Avo_*` symbol must
use `terrainAvoid`, etc.); `mobility` matches the symbol's own
`_Common`/`_Fly` suffix (or `none` for the two heal arrays, which carry
no suffix). The header read is scoped to just the plain `TERRAIN_*`
enum block (not any `TERRAIN_COUNT`-style trailing sentinel, which is
read separately purely to size the coverage check, mirroring `traps`'
scoped-enum-block pattern for `TRAP_*` vs. `TRAP_MAX_COUNT`).

The generator (`terrainstats/generate.py`) splits the 8 arrays across
two storage classes, matching the hand file's own convention exactly:
the 6 `Avo`/`Def`/`Res` arrays are `CONST_DATA` (the default `.data`
placement `src/data_terrains.c` already uses for every other array in
the file), while `TerrainTable_HealAmount`/`TerrainTable_HealsStatus`
are emitted under a dedicated `SECTION(".data.terrainheal")` -- required
so the same generated object can be spliced into two independent,
non-adjacent `ldscript.txt` slots (see "## Linking two non-adjacent
groups of terrain combat/heal stat arrays in one partial-file table
(Batch 1 mechanics: `terrainstats`)" below for the full write-up). Each
array is emitted as a flat C89 designated initializer,
`[TERRAIN_X] = value`, in ascending declared-entry order (not
necessarily enum-numeric order, though for this table's 8 fully-covered
arrays the two always coincide).

### Round-trip checker (`terrainstats/parser.py`)

A regex-based parser scoped precisely to the 8 expected symbols (it
never matches `Unk_TerrainTable_*` or any movement-cost/graphics array
sharing the same file, confirmed by a dedicated non-confusion test).
Every entry resolves to a bare `(terrain_key, value)` pair -- no symbol
references or nested structs exist in this table, unlike `classes`/
`items` -- so the comparison is a simple ordered-tuple-list equality per
array. `python3 -m unittest
scripts.generated_data.tests.test_terrainstats_roundtrip` proves all
**8/8** arrays match the real `src/data_terrains.c` exactly with zero
diagnostics.

### Committed inventory (`terrainstats/inventory.py`)

`reports/generated_data_terrainstats_inventory.md` is the committed,
CI-checked report: total array count, the terrain-key coverage count
per array, a `field`/`mobility` usage breakdown, and the table's own
dependency-graph digest (this table has no dependencies of its own --
it is a leaf that `classes` depends on, not the reverse).

## `movecost` schema (Issue #5 mechanics Batch 2: weather-triplet movement-cost + DemonKing/Ballista tables)

Source: `src/data/movecost.json` (schema `fe8.movecost.v1`), one object
per named **mobility profile** under `"profiles"`: `profile` (a unique
name -- the 15 named triplet profiles are `CommonT2`/`CommonT1`/`Armor`/
`Fighter`/`Berserker`/`Brigand`/`Pirate`/`Thief`/`Magic`/`Civilian`/
`HorseT1`/`HorseT2`/`AnimalT1`/`AnimalT2`/`Fly`, plus the two
single-variant profiles `DemonKing`/`Ballista`), and three **direct**
sibling keys -- `normal`, `rain`, `snow` -- each either JSON `null` or an
object with `symbol` (the array's C symbol name) and `values` (an
ordered mapping keyed by `TERRAIN_*` constant, identical shape to
`terrainstats`' own per-array entry mapping). There is no intermediate
`variants` wrapper -- `normal`/`rain`/`snow` sit directly on the profile
object alongside `profile`:

```json
{
  "$schema": "fe8.movecost.v1",
  "profiles": [
    {
      "profile": "CommonT2",
      "normal": {
        "symbol": "TerrainTable_MovCost_CommonT2Normal",
        "values": { "TERRAIN_NONE": -1, "...": "...", "TERRAIN_MAST": -1 }
      },
      "rain": {
        "symbol": "TerrainTable_MovCost_CommonT2Rain",
        "values": { "...": "..." }
      },
      "snow": {
        "symbol": "TerrainTable_MovCost_CommonT2Snow",
        "values": { "...": "..." }
      }
    },
    {
      "profile": "DemonKing",
      "normal": {
        "symbol": "TerrainTable_MovCost_DemonKing",
        "values": { "...": "..." }
      },
      "rain": null,
      "snow": null
    },
    {
      "profile": "Ballista",
      "normal": {
        "symbol": "TerrainMoveCost_Ballista",
        "values": { "...": "..." }
      },
      "rain": null,
      "snow": null
    }
  ]
}
```

The `profile` named `DemonKing`'s `normal.symbol` is
`TerrainTable_MovCost_DemonKing` (no weather suffix, since only one
array exists for that class); the `profile` named `Ballista`'s
`normal.symbol` is `TerrainMoveCost_Ballista` -- note the divergent
`TerrainMoveCost_` prefix (missing the `Table` segment every other
symbol in this table has), confirmed verbatim against
`src/data_terrains.c` and preserved exactly, **not** a typo to normalize
away. Both `DemonKing` and `Ballista` are **single-variant**: they author
only `normal` (`rain`/`snow` are JSON `null`), matching the vanilla
source's own single array for each (no separate weather-specific
DemonKing/Ballista tables exist). Covers exactly the 15 named
Normal/Rain/Snow triplets (45 arrays) plus the `DemonKing`/`Ballista`
profiles' single `normal` arrays (2 more) -- **47 arrays total** --
deliberately excluding the 2 unrelated `Unk_TerrainTable_1`/
`Unk_TerrainTable_2` escape-hatch arrays and every graphics/non-movement
table that also lives in `src/data_terrains.c`; none of those are part
of this batch's scope (see "Issue #5 completion boundary and status" at the end of this
document).

Validations enforced (`movecost/schema.py: validate()`): unique profile
names; unique symbols across the whole table (no two profiles, or two
weather slots of the same profile, may share a symbol); **full
contiguous `TERRAIN_*` coverage** for every authored `values` mapping
(same enum-order, no-gap, no-duplicate rule as `terrainstats`); the
exact `s8` range (`[-128, 127]`) for every value; `symbol` is validated
against a closed, self-describing expectation derived from `profile` and
slot (named profiles must spell
`TerrainTable_MovCost_{profile}{Normal,Rain,Snow}`; `DemonKing`'s lone
slot must be `TerrainTable_MovCost_DemonKing`; `Ballista`'s lone slot
must be `TerrainMoveCost_Ballista`) rather than an open
`CSymbolRefField` header scan; `DemonKing`/`Ballista` must leave
`rain`/`snow` as JSON `null`, and no profile may reuse a name already
claimed by another.

The generator (`movecost/generate.py`) emits arrays in the hand file's
own declaration order -- all 15 named profiles' `normal` array, then
`TerrainTable_MovCost_DemonKing`, then `TerrainMoveCost_Ballista`, then
all 15 named profiles' `rain` array, then all 15 named profiles' `snow`
array -- and splits storage across two classes to match the hand file's
own layout exactly: the 32 Normal/DemonKing/Ballista/Rain arrays are
ordinary `CONST_DATA` (`.data`, the file's default placement, since they
are the literal first content of `src/data_terrains.c` and need no
redirect), while the 15 Snow arrays (separated from the first 32 by the
hand-owned `Unk_TerrainTable_1` escape hatch) are emitted under a
dedicated `SECTION(".data.movecostsnow")` so the same generated object
can be spliced into `ldscript.txt` at an independent, later point (see
"## Linking a weather-triplet movement-cost table split around one
non-adjacent escape hatch (Issue #5 mechanics Batch 2: `movecost`)"
below for the full write-up). Each array is emitted as a flat C89
designated initializer, `[TERRAIN_X] = value`, in ascending
declared-entry order.

### Round-trip checker (`movecost/parser.py`)

A regex-based parser scoped precisely to the 47 expected symbols (it
never matches `Unk_TerrainTable_*` or any terrain-combat/heal/graphics
array sharing the same file, confirmed by a dedicated non-confusion
test). Every entry resolves to a bare `(terrain_key, value)` pair, so
the comparison is a simple ordered-tuple-list equality per array, same
as `terrainstats`. `python3 -m unittest
scripts.generated_data.tests.test_movecost_roundtrip` proves all
**47/47** arrays match the real `src/data_terrains.c` exactly with zero
diagnostics.

### Committed inventory (`movecost/inventory.py`)

`reports/generated_data_movecost_inventory.md` is the committed,
CI-checked report: total profile/array counts, the terrain-key coverage
count per array, a single-variant-vs-triplet profile breakdown, and the
table's own dependency-graph digest (this table has no dependencies of
its own -- it is a leaf that `classes` depends on, not the reverse).

### `classes` cross-validation against `movecost`

As of this batch, `classes/schema.py`'s `dependency_tables()` returns
`("terrainstats", "movecost")`, and `ClassesTableSchema.validate()`
cross-checks every non-null `movCostTable` triplet entry
(`normal`/`rain`/`snow`) against the authored `movecost` records when
`dependency_records["movecost"]` is supplied: each non-null entry must
resolve to a symbol that is actually one of the arrays authored in
`movecost`, **and** all non-null entries within one `ClassData` record's
triplet must resolve to the *same* movecost profile at their own
matching slot -- a class cannot, for example, pair one profile's
`normal` symbol with a different profile's `rain` symbol. The
single-variant `DemonKing`/`Ballista` profiles register their lone
`normal` symbol under all three slot keys in the lookup index
(`movecost/schema.py`'s `build_slot_symbol_index()`), so a triplet that
legitimately repeats the same weather-invariant symbol three times (as
`CLASS_DEMON_KING` and the ballista-consuming classes do) resolves
cleanly rather than being flagged as a cross-profile mismatch. A `null`
triplet entry remains valid regardless (immobile classes are
unaffected). `movCostTable` entries have no explicit "mobility profile"
field of their own on the `ClassData` side, so -- like the
`terrainstats` cross-check -- this is a symbol-identity/profile-identity
check, not a semantic role check. `reservedTerrainTable` is **not** part
of this change and remains a plain `CSymbolRefField` escape hatch. When
`dependency_records["movecost"]` is omitted (e.g. standalone unit
tests), `validate()` falls back to the original `CSymbolRefField`-only
check for `movCostTable`, so the schema stays usable without wiring up
the full dependency-graph machinery. See `ClassesMovecostDependencyTests`
in `test_classes_schema.py` for the full set of covered cases (valid
triplet resolution, null-triplet validity, single-variant
weather-invariant resolution, unresolvable-symbol detection,
mixed-profile-triplet detection, no-movecost-dependency fallback).

## `weapontriangle` schema (Issue #5 mechanics Batch 3: `sWeaponTriangleRules[]`)

Source: `src/data/weapontriangle.json` (schema `fe8.weapontriangle.v1`),
one object per **directed** weapon-triangle rule under `"rules"`:
`attacker`/`defender` (`ITYPE_*` weapon-type designators from
`include/bmitem.h`), and `hitBonus`/`atkBonus` (the `s8` hit-rate/
attack-power modifiers `BattleApplyWeaponTriangleEffect` applies to the
attacker; the defender receives the exact negation of both, computed by
that same function -- not separately authored here):

```json
{
    "$schema": "fe8.weapontriangle.v1",
    "rules": [
        { "attacker": "ITYPE_SWORD", "defender": "ITYPE_LANCE", "hitBonus": -15, "atkBonus": -1 },
        { "attacker": "ITYPE_SWORD", "defender": "ITYPE_AXE",   "hitBonus": 15,  "atkBonus": 1 },

        { "attacker": "ITYPE_LANCE", "defender": "ITYPE_AXE",   "hitBonus": -15, "atkBonus": -1 },
        { "attacker": "ITYPE_LANCE", "defender": "ITYPE_SWORD", "hitBonus": 15,  "atkBonus": 1 },

        { "attacker": "ITYPE_AXE",   "defender": "ITYPE_SWORD", "hitBonus": -15, "atkBonus": -1 },
        { "attacker": "ITYPE_AXE",   "defender": "ITYPE_LANCE", "hitBonus": 15,  "atkBonus": 1 },

        { "attacker": "ITYPE_ANIMA", "defender": "ITYPE_DARK",  "hitBonus": -15, "atkBonus": -1 },
        { "attacker": "ITYPE_ANIMA", "defender": "ITYPE_LIGHT", "hitBonus": 15,  "atkBonus": 1 },

        { "attacker": "ITYPE_LIGHT", "defender": "ITYPE_ANIMA", "hitBonus": -15, "atkBonus": -1 },
        { "attacker": "ITYPE_LIGHT", "defender": "ITYPE_DARK",  "hitBonus": 15,  "atkBonus": 1 },

        { "attacker": "ITYPE_DARK",  "defender": "ITYPE_LIGHT", "hitBonus": -15, "atkBonus": -1 },
        { "attacker": "ITYPE_DARK",  "defender": "ITYPE_ANIMA", "hitBonus": 15,  "atkBonus": 1 }
    ]
}
```

The generated `sWeaponTriangleRules[]` C array appends one final,
implicit `{ -1 }` terminator record after the 12 authored rules --
never present in the JSON itself (`BattleApplyWeaponTriangleEffect`
scans the array until it finds `attackerWeaponType < 0`).

`attacker`/`defender` are restricted to exactly the 6 weapon types that
actually participate in a weapon triangle -- the 3 physical types
(`ITYPE_SWORD`/`ITYPE_LANCE`/`ITYPE_AXE`) and the 3 magic types
(`ITYPE_ANIMA`/`ITYPE_LIGHT`/`ITYPE_DARK`) -- not every `ITYPE_*`
constant in `include/bmitem.h` (`ITYPE_BOW`/`ITYPE_STAFF`/`ITYPE_BLLST`/
etc. never participate in a weapon triangle and are rejected, even
though they are otherwise valid weapon-type constants). This is a
closed list (like `movecost`'s `EXPECTED_PROFILES`), not a wildcard/
prefix scan of the header: only these 6 names are in scope, and each
forms one of exactly 2 closed, non-overlapping 3-type groups (the
"physical" triangle and the "magic" triangle) -- every rule's
`attacker`/`defender` pair must belong to the *same* group (cross-group
pairs, e.g. `ITYPE_SWORD` vs. `ITYPE_ANIMA`, are rejected), and every
ordered non-self pair *within* a group must be authored exactly once: 2
groups x 3 members x 2 directions (each member beats one groupmate and
loses to the other) = exactly **12 rules**, matching
`sWeaponTriangleRules`' 12 real records.

Validations enforced (`weapontriangle/schema.py: validate()`): unique
directed `(attacker, defender)` pairs; every `attacker`/`defender`
resolves to a real `ITYPE_*` constant (rejecting unknown names) *and* is
restricted to the 6 in-scope weapon types (rejecting valid-but-out-of-
scope ones like `ITYPE_BOW`); no self-pairs (`attacker == defender`);
every pair belongs to the same closed 3-type group (rejecting
cross-group pairs); the exact `s8` range (`[-128, 127]`) for both
`hitBonus`/`atkBonus`; exactly `EXPECTED_RULE_COUNT` (12) records; and
**full reciprocal closure** -- every `(A, B)` rule must have a matching
`(B, A)` rule with both bonuses exactly negated (mirroring
`BattleApplyWeaponTriangleEffect`'s own `-hitBonus`/`-atkBonus`
computation for the defender), checked independently rather than
derived at generation time, since the vanilla table itself authors both
directions explicitly.

The generator (`weapontriangle/generate.py`) emits
`sWeaponTriangleRules[]` as a flat C89 array of `struct
WeaponTriangleRule` positional initializers (`{ attacker, defender,
hitBonus, atkBonus }`), in the JSON's own `rules` order (which matches
the hand table's declaration order: Sword/Lance/Axe physical group
first, then Anima/Light/Dark magic group), followed by the implicit
`{ -1 }` terminator. `struct WeaponTriangleRule` itself lives in
`include/bmbattle.h` (not privately in `src/bmbattle.c`), so the
generated object and the guarded hand block in `src/bmbattle.c` can
both reference the exact same layout without redefinition -- see "##
Linking a single-block global weapon-triangle rule table (Issue #5
mechanics Batch 3: `weapontriangle`)" below.

### Round-trip checker (`weapontriangle/parser.py`)

A regex-based parser scoped precisely to the single guarded
`sWeaponTriangleRules[]` block in `src/bmbattle.c` -- it never matches
`BattleApplyWeaponTriangleEffect`, `BattleApplyReaverEffect`, or any
other procedural function in the same file, confirmed by a dedicated
non-confusion test. Each hand entry resolves to a
`(attacker, defender, hit_bonus, atk_bonus)` tuple; the final `{ -1 }`
entry is recognized as the terminator (required to be the array's last
entry) rather than compared as a data record. `python3 -m unittest
scripts.generated_data.tests.test_weapontriangle_roundtrip` proves all
**12/12** rules match the real `src/bmbattle.c` table exactly, with the
terminator shape validated separately (missing terminator, wrong
shape, extra/duplicate terminator, and data-after-terminator are all
rejected -- see the parser's dedicated malformed-hand-file test
fixtures).

### Committed inventory (`weapontriangle/inventory.py`)

`reports/generated_data_weapontriangle_inventory.md` is the committed,
CI-checked report: total rule count, a per-group breakdown (physical/
magic), and the table's own dependency-graph digest (`bmitem.ITYPE`;
this table has no table dependencies of its own and no table currently
depends on it).

## `characters` schema (Issue #5 Batch 2a + 2b: full global character table)

**Batch 2b completes this table to parity with `items`/`classes`.**
Batch 2a provided the schema/dependency-validation foundation described
throughout most of this section (the 256-slot designator model, field/
range/reference validation, cross-table checks) with no real committed
source and no generation/round-trip machinery. Batch 2b adds the
missing pieces: a real, committed `src/data/characters.json` with
`"fullCoverage": true` authoring all 256 records (94 symbolic + 162
raw, including the `[0x100 - 1]` padding slot), `generate.py` (C89
emission), `parser.py` (hand-file round-trip parsing keyed by resolved
designator), `inventory.py` (the committed inventory report), and an
entry in `generated_data.mk`'s `GENERATED_DATA_TABLES`. At this point
(Batch 2a + 2b), `src/data_characters.c` remained the sole hand-written,
linked source for `gCharacterData[]` -- Batch 2b proved semantic parity
against it but did not yet link the generated file in its place (linking
was explicit Batch 2c scope). **It has since been linked** (Issue #5
**Batch 2c-4**) -- the generated `build/generated/data/data_characters.c`
is now the canonical, compiled/linked source for `gCharacterData[]`,
with `src/data_characters.c` itself kept only as the round-trip
reference; see "Linking a generated table in place of its hand-written
counterpart" below.
`python3 -m scripts.generated_data validate --table characters` (no
`--source` override needed now) validates the full committed table,
including `--dep-source classes=PATH`/`--dep-source supports=PATH`
overrides for the two cross-table checks described below.

`gCharacterData[]` has a model unlike every other table this platform
covers: a fixed **256-slot** array (confirmed against
`src/data_characters.c`, which has exactly 256 top-level designated
initializers) addressed by a 1-based **designator** (`[designator - 1]`,
mirroring the hand file's own `[CHARACTER_X - 1]`/`[0x1B - 1]`
indexing), where each slot is *either*:

* **symbolic** (JSON key `"character"`, a named `CHARACTER_*` constant
  from `include/constants/characters.h`, excluding the `CHARACTER_NONE`
  sentinel -- its implied array index would be `-1`, never a valid
  entry) -- roughly 96 of the 256 designators have one; or
* **raw/generic-template** (JSON key `"characterId"`, a bare integer
  designator) for the remaining unnamed enemy/filler templates the hand
  file indexes with a raw hex literal (e.g. `[0x1B - 1]`).

Exactly one of the two keys is required per record (`load_records()`
raises immediately, like every other table's required-key checks, if a
record has both or neither). Designator `256` (`0x100`) is the single
**unreachable padding slot**: no real `u8` character byte can ever equal
256, so it can never be reached by `GetCharacterData()` at runtime, but
it is still a real, authored 256th array entry -- only `characterId`
(never `character`, since no `CHARACTER_*` constant is or could be
`256`) can designate it. `.number` is **never authored**: it is always
derived as `designator & 0xFF` -- for designators `1..255` that's the
designator itself; for the padding slot the `u8` truncation naturally
yields `0`, exactly matching the hand file's own explicit
`.number = 0` for that one entry with no special case needed.

`character` is deliberately **not** resolved with the generic,
whole-file `extract_enum_constants(header, name_prefix="CHARACTER_")`
scan every other reference field in this schema uses -- it delegates to
`scripts/generated_data/character_refs.py`'s `read_character_designators()`,
a dedicated reader scoped strictly to the *primary*, anonymous designator
enum (the block that opens with `CHARACTER_NONE = 0x00` and closes with
`CHARACTER_SNAG = 0xFF`). `include/constants/characters.h` also declares
a wholly separate, *named* sibling enum immediately after that block,
`event_autoload_pid_idx` (`CHARACTER_EVT_LEADER`/`ACTIVE`/`SLOTB`/`SLOT2`
= `0`/`-1`/`-2`/`-3`) -- event-engine "active unit slot" indices that
happen to share the same `CHARACTER_` textual prefix but are never valid
`CharacterData` designators (two of them aren't even representable as
one, being negative). A prefix-only scan cannot tell the two enums apart
and would wrongly accept all four as designators; `read_character_
designators()` instead matches only the primary block's own text
(bounded by its own `CHARACTER_NONE =`/closing `};`), so the sibling
enum's members -- or any other same-prefix collision -- are excluded
structurally rather than by name, and are reported as an ordinary
`undefined character reference` diagnostic if authored.

`character_refs.py` is a **shared, cross-table module** (living directly
under `scripts/generated_data/`, not nested in any single table's own
package) rather than a `characters`-schema-specific helper: every table
that references `CHARACTER_*` symbols -- `characters` (the record's own
designator), `units` (`charIndex`/`leaderCharIndex`), `supports` (`owner`/
`characters` partners), `eventlists` (`CHAR()` macro's `pid1`/`pid2`
arguments), and `chapterbundle` (`dependencies.characters`) -- delegates
to the same `read_character_designators()` to read `CHARACTERS_HEADER`,
so the same primary-block/sibling-enum scoping fix applies everywhere a
`CHARACTER_*` reference is validated, not just in `characters` itself.
The reader intentionally **includes** `CHARACTER_NONE` in its returned
mapping (it's a genuine primary-block member); each table's own
`validate()` decides independently whether `CHARACTER_NONE` is a valid
value for its own specific field -- only `characters`' own
record-designator field rejects it explicitly (a record can't be *about*
"no character"), while `units`/`supports`/`eventlists`/`chapterbundle`
accept it exactly as they did before this fix (none of their real
committed data uses it today, so no new nullability semantics were
introduced by consolidating the reader).

Unlike `classes`' coverage check (always on, range derived from the
live header's max value), the full dense `1..256` coverage domain here
is a **fixed module constant** (`DESIGNATOR_MIN`/`DESIGNATOR_MAX`, not
derived from `characters.h`, since raw/generic-template records fill in
every unnamed designator) and coverage enforcement itself is an
opt-in, top-level JSON boolean, `"fullCoverage"` (default `false`):
the real, committed `src/data/characters.json` (Batch 2b) sets it
`true` and authors all 256 designators; small hand-authored fixtures
that only cover a handful of designators (used throughout this
section's own tests) leave it `false` and are checked purely for
uniqueness/reference/range correctness, not completeness.

Every other `CharacterData` field is modeled and validated: `nameTextId`/
`descTextId` against the live `MSG_COUNT`; `defaultClass` both as a live
`CLASS_*` reference *and* -- when the `classes` dependency table is
loaded (`--dep-source classes=PATH`, or the CLI's own `dependency_tables()`
wiring) -- present among that table's own loaded `ClassData` records (two
distinct failure modes: undefined constant vs. valid-but-unauthored
class); `portrait` against the live count of numbered entries in
`src/portrait_data.c`'s `portrait_data[]` (same live table `classes`
already validates `defaultPortraitId` against); `miniPortrait` against a
**stronger-than-`u8`** bound proven live from `src/face.c`'s
`sGenericChibiImgLut[]` array literal (traced through
`GetUnitMiniPortraitId()`/`GetGenericChibiImg()` in `src/bmunit.c`/
`src/face.c`: `miniPortrait` indexes that array directly, so its entry
count -- not the raw `u8` width -- is the real bound); `affinity` as an
optional `UNIT_AFFIN_*` reference (read with a bespoke sequential-value
reader, `read_unit_affinities()`, since that enum only assigns its first
member explicitly and lets the rest auto-increment -- the generic
`extract_enum_constants()` helper cannot parse that); signed `base` stats
at the full `s8` range and unsigned `growth` stats at `u8`; `baseRanks`
(a sparse `{ITYPE_*: WPN_EXP_*}` map, bounded to the struct's own live
`baseRanks[8]` capacity, exactly like `classes`); `attributes` as a
validated `CA_*` bitmask list (the same enum `classes` reads, shared at
runtime via `UNIT_CATTRIBUTES()`); `visitGroup`/`baseLevel` at plain
`u8` (no stronger invariant found for either); `sortOrder` (JSON key
`sortOrder`, struct field `sort_order`) at plain `u8`, added in Batch 2b
after transcribing the real hand file revealed it is a genuine,
sometimes-nonzero field (46 of the 256 real records set it explicitly)
that Batch 2a's schema had never modeled -- a real gap, not a stylistic
omission, since without it those 46 records could never round-trip; and
the reserved `_u23`/`_u24`/`_u25`/`_u27` struct fields, which are
**rejected outright if authored at all** (a new pattern for this
platform -- every other table silently ignores unrecognized JSON keys,
but these four are never authorable, not merely defaulted).

`supportData` (optional, most records and *all* raw/generic-template
records have none) is modeled as a genuine cross-table reference, not
just a header-string check: when the `supports` dependency table is
loaded, a non-null `supportData` value must match some loaded
`SupportData` record's own `symbol`, *and* that record's `owner` must
equal this record's own `character` (reciprocal, like `chapterbundle`'s
support-owner check) -- raw/generic-template records referencing
`supportData` at all is rejected unconditionally (no proven
generic-template record has one). Both cross-table checks
(`defaultClass`-presence and `supportData`) degrade gracefully to
header-only/skipped when the corresponding dependency table isn't
loaded, via `dependency_tables() = ("classes", "supports")`.

### Generation, round trip, and compile verification (Batch 2b)

`generate.py` mirrors `classes/generate.py`: it emits the C89
`gCharacterData[]` array with symbolic (`[CHARACTER_X - 1]`) or
lowercase-hex raw (`[0x1b - 1]`, matching the hand file's own lowercase
convention throughout) designators, derives the required `.number`
literal itself from the designator (the record's own symbol name for
symbolic records, the lowercase-hex designator for raw records, or the
bare literal `0` for the single `[0x100 - 1]` padding record -- the
`u8` wraparound is computed once in Python and emitted directly, so the
generated C source never relies on the target compiler to truncate an
out-of-range `.number = 256` initializer), omits zero/default-valued
fields, and orders every field to match the single canonical field
order confirmed across all 256 real records (`nameTextId`, `descTextId`,
`number`, `defaultClass`, `portraitId`, `miniPortrait`, `affinity`,
`sort_order`, `baseLevel`, the 8 base stats, `baseRanks`, the 7 growth
stats, `attributes`, `pSupportData`, `visit_group`).

`parser.py` mirrors `classes/parser.py` but is keyed by resolved
**designator** (an integer), not by symbol name -- unlike every other
table's parser, raw/generic-template records have no symbol to key by.
It parses `gCharacterData[]` entries from the hand file, validates each
entry's `.number` literal against its own designator (symbol-name match
for symbolic records, `& 0xFF` truncation check for raw records,
including the `[0x100 - 1]` record's `.number = 0`), and normalizes
signed `s8` fields the hand file spells as their unsigned-looking
decimal equivalent (`_parse_s8_token()`: two real records write
`.baseSkl = 255`/`.baseSpd = 253` rather than `-1`/`-3` -- both are
legitimate C literals that truncate identically into `s8`, but must be
normalized (`value - 256` when `value > 127`) before comparison, or a
false round-trip mismatch would be reported against semantically
identical data).

`inventory.py` mirrors `classes/inventory.py`, reporting: total/
symbolic/raw record counts; the reachable-designator vs. dead-padding
count (255 vs. 1); `defaultClass`/`affinity`/`attributes`/`baseRanks`
usage histograms; `supportData` usage count; and the table's own
`dependency_tables()` digest (`classes`, `supports`).

The real, committed `src/data/characters.json` (94 symbolic + 162 raw
= 256 records, `fullCoverage: true`) round-trips **256/256** against
the real `src/data_characters.c` with zero diagnostics (`python3 -m
scripts.generated_data validate --table characters`, and
`test_characters_roundtrip.py`'s `FullRoundTripTests`). `generate
--table characters` writes `build/generated/data/data_characters.c`
and the committed `reports/generated_data_characters_inventory.md`;
`check --table characters` (and the `generated-data-check`/
`generated-data-test` Make targets, now that `characters` is in
`GENERATED_DATA_TABLES`) confirm no drift. The generated
`build/generated/data/data_characters.c` was also compiled end-to-end
through the real `cpp | iconv | agbcc` pipeline and assembled with
`arm-none-eabi-as` with zero errors/warnings (mirroring the Makefile's
own `$(C_OBJECTS)` recipe, same flags), confirming it is valid,
compilable C89 -- at this point (Batch 2a + 2b) it was not yet linked in
place of `src/data_characters.c` (no `ldscript.txt` change; linking was
explicit Batch 2c scope, see "Issue #5 completion boundary and status" below). **It has
since been linked** (Issue #5 **Batch 2c-4**; see "Linking a generated
table in place of its hand-written counterpart" below) -- `gCharacterData`
is the single generated top-level symbol now canonically compiled/linked
in `src/data_characters.c`'s place, with `src/data_characters.c` itself
kept only as the round-trip reference.

### Fixtures and tests

`scripts/generated_data/tests/fixtures/characters/` holds fixture
sources using the real repository headers/enums throughout (`CHARACTER_
EIRIKA`/`CLASS_MYRMIDON`/etc.) so they validate identically whether run
directly (`characters_schema.validate()`) or via the CLI (which has no
header-override mechanism for a table's own headers, only for
`--dep-source`-loaded dependency tables) -- plus a small set of `mini_*`
header/source fixtures used only to unit-test the individual live-source
reader functions (`read_msg_count`, `read_portrait_count`,
`read_mini_portrait_capacity`, `read_character_data_array_capacity`,
`read_character_attributes`, `read_unit_affinities`) against small,
exact expected numbers. `python3 -m unittest
scripts.generated_data.tests.test_characters_schema` covers the record
model, structural/duplicate/coverage/reference/range/reserved-field/
support-data/class-dependency checks (including the
`CHARACTER_EVT_LEADER`/`ACTIVE`/`SLOTB`/`SLOT2` sentinel-rejection
regression and a synthetic sibling-enum-collision regression wired
through `characters_schema.validate()`'s own `characters_header=`
override parameter), and the header readers in isolation; `test_
characters_generate.py` covers deterministic C89 generation (default-
field omission, ascending attribute-flag ordering regardless of JSON
order, lowercase-hex raw designators, the `[0x100 - 1]` `.number = 0`
wraparound with no overflow/warning); `test_characters_roundtrip.py`
covers fixture-based round-trip match/mismatch/missing-record/extra-
record detection plus the full **256/256** round trip against the real
`src/data_characters.c`; `CliCharactersTests` in `test_cli_new_tables.py`
covers `validate`/`generate`/`check` end to end through the CLI against
both fixtures and the real committed `src/data/characters.json`
(drift-free), `--dep-source` overrides, and the sentinel-rejection
regression.

`scripts/generated_data/character_refs.py`'s own `read_character_
designators()` -- being shared across five tables -- has its own
dedicated test module, `test_character_refs.py`, independent of any
single table's fixtures: one set of tests runs it against the real
`characters.h` (confirming `CHARACTER_NONE`/`CHARACTER_EIRIKA`/
`CHARACTER_SNAG` are present and all four `CHARACTER_EVT_*` sentinels
are absent), and a second set runs it against a minimal synthetic
fixture, `scripts/generated_data/tests/fixtures/character_refs/
mini_characters_sibling_enum.h`, that reproduces the real header's
primary-enum/named-sibling-enum, same-prefix collision shape in
miniature (down to a negative-valued sibling member), proving the
scoping mechanism itself -- anchored on the primary block's own opening/
closing braces -- independent of the real header's current contents.
Each of the four other affected tables (`units`, `supports`,
`chapterbundle`, plus `eventlists` as an additional table found to share
the same bug class) additionally carries its own `char_evt_sentinels.json`
fixture (proving its own real-header call site rejects all four EVT_*
sentinels) and its own synthetic-sibling-enum-collision regression test
wired through that table's own `characters_header=` `validate()`
parameter override -- so the fix is proven at the wiring level in each
table, not only inside the shared reader.

## The C-symbol escape hatch (`escape_hatch.py`)

Originally implemented and tested as a generic, reusable mechanism ahead
of a real consumer; the Chapter 2 slice's `eventscripts` table (above) is
now that first production consumer:

* A schema field can declare it references a symbol that must be
  **declared in a specific header** (`CSymbolRefField(header_path)`).
  The header acts as an allowlist by construction -- only symbols its
  author chose to declare (function declarations/definitions or `extern`
  object declarations) are acceptable.
* `validate(symbol, loc, reference_path)` rejects: malformed identifiers
  (not a valid C token), and symbols not found declared in the header
  (with the header path and the list of symbols that *are* declared, in
  the error message).
* `emit(symbol)` returns the symbol **unquoted** -- the generator writes
  it as a bare C token (e.g. a function-pointer field initializer), not a
  JSON string, so it compiles as a real reference.

See `tests/test_escape_hatch.py` and
`tests/fixtures/escape_hatch/demo_header.h` for the original
fixture-driven proof (valid function reference, valid extern-object
reference, malformed identifier, undeclared symbol), and
`eventscripts/schema.py` + `tests/test_eventscripts_schema.py` for the
production usage against the real `include/eventcall.h`.

## CLI

```bash
python3 -m scripts.generated_data validate --table supports
python3 -m scripts.generated_data generate  --table supports
python3 -m scripts.generated_data check     --table supports

# Same three subcommands work identically for every registered table --
# cli.py has no per-table dispatch logic:
python3 -m scripts.generated_data validate --table units
python3 -m scripts.generated_data generate  --table units
python3 -m scripts.generated_data check     --table units

python3 -m scripts.generated_data validate --table shops
python3 -m scripts.generated_data generate  --table shops
python3 -m scripts.generated_data check     --table shops

python3 -m scripts.generated_data validate --table traps
python3 -m scripts.generated_data generate  --table traps
python3 -m scripts.generated_data check     --table traps

# eventscripts is metadata-only: `generate`/`check` skip C output but
# still write/compare the committed inventory.
python3 -m scripts.generated_data validate --table eventscripts
python3 -m scripts.generated_data generate  --table eventscripts
python3 -m scripts.generated_data check     --table eventscripts

# eventlists cross-validates against units/shops/traps/eventscripts
# (via dependency_tables()); --dep-source NAME=PATH overrides one
# dependency's source, e.g. to validate a fixture in isolation:
python3 -m scripts.generated_data validate --table eventlists
python3 -m scripts.generated_data generate  --table eventlists
python3 -m scripts.generated_data check     --table eventlists
python3 -m scripts.generated_data validate --table eventlists \
  --source scripts/generated_data/tests/fixtures/eventlists/valid.json --no-roundtrip \
  --dep-source units=scripts/generated_data/tests/fixtures/eventlists/deps_units.json \
  --dep-source shops=scripts/generated_data/tests/fixtures/eventlists/deps_shops.json \
  --dep-source traps=scripts/generated_data/tests/fixtures/eventlists/deps_traps.json \
  --dep-source eventscripts=scripts/generated_data/tests/fixtures/eventlists/deps_eventscripts.json

# chapterbundle (metadata-only, like eventscripts) cross-validates against
# units/shops/traps/eventscripts/eventlists/supports; without --dep-source
# each falls back to its own real, committed default_source, so validating
# the real bundle needs no extra flags at all:
python3 -m scripts.generated_data validate --table chapterbundle
python3 -m scripts.generated_data generate  --table chapterbundle
python3 -m scripts.generated_data check     --table chapterbundle
```

Common flags: `--source PATH` (JSON source, default per-table, e.g.
`src/data/supports.json`/`src/data/ch2_units.json`/
`src/data/ch2_shops.json`/`src/data/ch2_traps.json`/
`src/data/ch2_eventscripts.json`/`src/data/ch2_eventlists.json`/
`src/data/ch2_bundle.json`), `--hand-source PATH` (round-trip comparison
target, default per-table, e.g. `src/data_supports.c`/
`src/events_udefs.c`/`src/events_shoplist.c`/`src/events_trapdata.c`/
`src/events/ch2-eventinfo.h`; `eventscripts`/`chapterbundle` have none --
both are metadata-only), `--no-roundtrip` (skip it), `--out-dir DIR`
(generated C output directory, default `build/generated/data`),
`--inventory PATH` (committed inventory/summary path, default per-table
under `reports/`), `--dep-source NAME=PATH` (repeatable; overrides one
declared table dependency's JSON source -- only meaningful for schemas
that declare `dependency_tables()`, currently `eventlists` and
`chapterbundle`).

* `validate` -- load + validate; prints **every** diagnostic (not just the
  first), each with `file:line:column`.
* `generate` -- validate, then write-if-changed the generated C89 (or
  print the metadata-only skip message) and the committed inventory.
  Fails (writing nothing) if validation or the round-trip check fails.
* `check` -- the CI-suitable gate. Self-heals the ephemeral `build/`
  output (write-if-changed, since it's gitignored and there is nothing
  committed to have drifted against), but only *compares* the committed
  inventory report -- it never rewrites it. Fails with a `DRIFT:` message
  if the committed inventory is stale relative to the current JSON
  source, in addition to failing on any validation/round-trip error.

## Make targets (`generated_data.mk`)

Still never wired into `all` as a link-time dependency, but as of Batch
2c-1 + 2c-2 + 2c-3 + 2c-4, `classes`, `items`, `supports`, and
`characters` **are** linked in
place of `src/data_classes.c`/`src/data_items.c`/`src/data_supports.c`/
`src/data_characters.c`
in both the legacy ROM build (`ldscript.txt`) and the modern object
cohort (`modern.mk`) -- see "Linking a generated table in place of its
hand-written counterpart (Batch 2c-1 + 2c-2 + 2c-3 + 2c-4)" below.
`generated-data-check`
**is** wired into
`.github/workflows/build.yml`, once per job, as an actionable pre-flight
gate ahead of the modern debug/release linker checks -- a stale/
inconsistent generated-data source now fails CI fast, with
`file:line:column` diagnostics, instead of only being caught (or masked)
by a much slower linker failure. `GENERATED_DATA_TABLES` now lists all 10
registered tables (Issue #5 Batch 1 added `items`, then `classes`; Batch
2b added `characters`), so the loop-based targets below cover `supports
units shops traps items classes characters eventscripts eventlists
chapterbundle`. None of `items`, `classes`, or `characters` is added to
`GENERATED_DATA_CH2_TABLES` -- all three are global tables, not part of
the Chapter 2 bundle, so `generated-data-ch2-check`
is unaffected:

```bash
make generated-data-validate      # validate only, all tables
make generated-data-generate      # validate + write build/ output + inventory, all tables
make generated-data-check         # CI-suitable: fails on drift, from a clean tree, all tables (wired into CI)
make generated-data-test          # python3 -m unittest discover -s scripts/generated_data/tests

# Batch C convenience aliases:
make generated-data-ch2-check     # check just the tables the Ch2 bundle composes + the bundle itself
make generated-data-bundle-validate  # validate just the chapterbundle table (fast iteration)
make generated-data-bundle-check     # check just the chapterbundle table (fast iteration)

# Batch 2c-1 + 2c-2 + 2c-3 + 2c-4: local-only (not CI-wired -- CI cannot
# build agbcc, see make_tools.mk), proves every linked table's (classes,
# items, supports, characters) link swap end to end against the real
# legacy pipeline plus both modern MODERN_CONFIG values' object lists:
make generated-data-link-check

# Batch 3a: local-only, proves the units/Ch2 UnitDefinition+REDA guard,
# CONST_DATA(".data.ch2tail") split, and three-piece ldscript.txt
# ordering end to end against the real legacy pipeline plus both modern
# MODERN_CONFIG values' object lists:
make generated-data-ch2-units-link-check

# Batch 3b: local-only, proves the traps/Ch2 TrapData_Event_Ch2 +
# TrapData_Event_Ch2Hard dual non-adjacent guards, the
# CONST_DATA(".data.trapch2mid")/CONST_DATA(".data.traptail") splits,
# the generated object's per-symbol section split
# (.data/.data.trapch2hard), and four-piece ldscript.txt ordering end
# to end against the real legacy pipeline plus both modern
# MODERN_CONFIG values' object lists:
make generated-data-ch2-traps-link-check

# Batch 3c: local-only, proves the shops/Ch2 ShopList_Event_Ch2Armory
# interior guard, the CONST_DATA(".data.shopch2tail") split, and
# three-piece ldscript.txt ordering end to end against the real legacy
# pipeline plus both modern MODERN_CONFIG values' object lists:
make generated-data-ch2-shops-link-check
```

## Linking a generated table in place of its hand-written counterpart (Batch 2c-1 + 2c-2 + 2c-3 + 2c-4)

Issue #5 Batch 2c-1 made `classes` the first generated table actually
**linked** into the real builds, in place of `src/data_classes.c`; Batch
2c-2 extended the exact same plumbing to `items`, in place of
`src/data_items.c`; Batch 2c-3 extended it again to `supports`, in place
of `src/data_supports.c`; Batch 2c-4 (this update) extends it to
`characters`, in place of `src/data_characters.c` -- all four, both the
legacy agbcc ROM build and the modern GCC object cohort, with zero
legacy ROM byte shift and zero modern ELF/ROM address shift, and without
editing or deleting any hand source (`src/data_classes.c`/
`src/data_items.c`/`src/data_supports.c`/`src/data_characters.c` all stay
in the repo, still used for `generated-data-check`'s own round-trip
drift proof). Unlike `classes`/`items`, `supports` has no single
top-level array symbol -- its generated object instead defines 33
independent `SupportData_<Owner>` symbols, one per record (see the
"multi-symbol table" bullet below for how `generated-data-link-check`
was generalized to verify that shape without weakening the
single-symbol case). `characters` (Batch 2c-4) is back to the
single-top-level-symbol shape: its generated object defines exactly one
`gCharacterData` (the 256-record global table), the same way
`gClassData`/`gItemData` do.

* **`GENERATED_DATA_LINKED_HAND_SOURCES`** (`generated_data.mk`) is the
  single source of truth for which hand C tables are superseded by a
  linked generated equivalent -- now
  `src/data_classes.c src/data_items.c src/data_supports.c src/data_characters.c`.
  `GENERATED_DATA_LINKED_TABLES`/`_C`/`_OBJECTS` are derived from it. Two
  further per-table maps are required for a linked table:
  `GENERATED_DATA_CONFIG_INPUTS_<table>` (the generator's non-JSON,
  non-script "config" inputs -- live enum/struct-layout headers, hand
  data-source tables read for live counts, etc.) and
  `GENERATED_DATA_LINKED_SYMBOL_<table>` (that table's own top-level
  generated C symbol name(s), e.g. `gClassData`/`gItemData`/
  `gCharacterData`, or -- for `supports` -- a space-separated list of all
  33 `SupportData_*` symbols, derived at `make`-parse time straight from
  the committed `src/data/supports.json` via `$(PYTHON) -c ...` so the
  expected list can never silently drift from what the table actually
  authors -- used by `generated-data-link-check` to prove exactly one
  definition of each links from the generated object; this cannot be
  derived generically from the table name, since `gClassData`/
  `gItemData`/`gCharacterData` are singular while the table names are
  plural, and `supports` has no single top-level symbol at all).
  Everything else -- the legacy generation/compile rules, the modern
  object-cohort filtering/reinstatement, and `generated-data-link-check`
  itself -- is fully generic over `GENERATED_DATA_LINKED_TABLES`, so
  Batch 2c-2 required no changes beyond adding `items` to
  `GENERATED_DATA_LINKED_HAND_SOURCES` and defining its two per-table
  maps plus the `ldscript.txt` swap; Batch 2c-3 required the same for
  `supports`, plus generalizing `generated-data-link-check`'s
  symbol-verification loop (see below) to handle a table with more than
  one top-level symbol; Batch 2c-4 required only the same two per-table
  maps plus the `ldscript.txt` swap for `characters` -- its single
  `gCharacterData` top-level symbol needed no further generalization of
  `generated-data-link-check`.
* **Multi-symbol table verification (`supports`, Batch 2c-3).**
  `GENERATED_DATA_LINKED_SYMBOL_<table>` may now hold more than one
  space-separated symbol; `generated-data-link-check`'s symbol-check
  loop iterates every symbol in the list and still asserts each links
  exactly once, so the `classes`/`items` single-symbol behavior is
  unchanged. For `supports` specifically, an additional optional
  `GENERATED_DATA_LINKED_SYMBOL_PREFIX_<table>` (set to `SupportData_`)
  drives a second, stricter check: every `SupportData_*`-prefixed
  top-level symbol actually defined in the generated object is collected
  via `arm-none-eabi-nm` and compared, as an exact sorted set, against
  the expected 33-symbol list -- not just "each expected symbol appears
  once" but "no hand object remains and no extra/unexpected
  `SupportData_*` definition exists beyond those exact 33". `classes`/
  `items` leave the prefix unset (a lone array symbol has no "family" to
  over/under-count), so their check is exactly what it was before Batch
  2c-3.
* **Bare `make` still builds the ROM.** `include generated_data.mk` has
  to happen in `Makefile` before `CFILES`/`ALL_OBJECTS` (and, via
  `include modern.mk`, `MODERN_ALL_C_SOURCES`) are computed, i.e. before
  `all:` -- but GNU Make's implicit default goal is the target of the
  *first* rule read across all (recursively included) makefiles, so
  without countermeasures `generated_data.mk`'s own first target
  (`generated-data-validate`) would silently become the default goal
  instead of `all`, breaking bare `make`/`make -n`. `Makefile` pins
  `.DEFAULT_GOAL := all` explicitly, immediately before the
  `include generated_data.mk` line, so this can never regress
  regardless of what any included makefile defines first;
  `generated-data-link-check` asserts, from a single build-state-
  independent `make -rR -p` database dump (a nonexistent probe target
  keeps it from executing or recursing into any sub-make, and `-rR`
  --no-builtin-rules/--no-builtin-variables keeps GNU Make's own
  implicit suffix-rule search from matching the bogus probe name and
  spawning a real, if harmlessly failing, assembler invocation -- our
  own `:=`-assigned `AS`/`CC1`/etc. variables are untouched by `-R`),
  both that `.DEFAULT_GOAL := all` and that the `all:` rule still
  depends on `fireemblem8.gba` -- deliberately not a `make -n` dry-run
  diff, since that only prints recipes for currently-stale targets and
  would give a false pass/fail depending on whether the tree happened
  to already be up to date.
* **Legacy build** (`Makefile`, `ldscript.txt`): each linked table's hand
  source (`src/data_classes.c`, `src/data_items.c`, `src/data_supports.c`,
  `src/data_characters.c`) is filtered out of `CFILES` (so it's never
  compiled as a hand object); `build/generated/data/data_classes.o`/
  `data_items.o`/`data_supports.o`/`data_characters.o` are appended to
  `ALL_OBJECTS` instead (each compiled from its generated `.c` through
  the exact same cpp -> CP932 (`iconv`) -> `agbcc` -> `as` pipeline as
  every other legacy object); and `ldscript.txt`'s
  `src/data_classes.o(.data);`/`src/data_items.o(.data);`/
  `src/data_supports.o(.data);`/`src/data_characters.o(.data);` lines are
  each swapped, in place, for their
  `build/generated/data/data_classes.o(.data);`/`data_items.o(.data);`/
  `data_supports.o(.data);`/`data_characters.o(.data);` equivalents.
  Since the legacy ROM's final section layout is controlled explicitly,
  entry by entry, by `ldscript.txt` (not by `ALL_OBJECTS`/`objects.lst`
  order), these swaps cannot shift any other object's address.
* **Modern build** (`modern.mk`): each linked table's hand source is
  filtered out of `MODERN_ALL_C_SOURCES` (and therefore out of
  `MODERN_ALL_C_HEADER_DEPS`'s `.headers.d` scan) -- but the generated
  `.c` is **not** reinserted into that sources list. Instead, each
  generated table's object is reinstated directly onto
  `MODERN_ALL_C_OBJECTS`, reusing the **original hand object's own
  path** (`$(MODERN_OUTPUT_DIR)/src/data_classes.o`,
  `$(MODERN_OUTPUT_DIR)/src/data_items.o`,
  `$(MODERN_OUTPUT_DIR)/src/data_supports.o`,
  `$(MODERN_OUTPUT_DIR)/src/data_characters.o`), paired with an explicit
  (non-pattern) compile rule for each exact path that compiles
  `build/generated/data/data_classes.c`/`data_items.c`/`data_supports.c`/
  `data_characters.c` instead. This is necessary, not cosmetic:
  `MODERN_ELF_OBJECTS_LST`/`MODERN_ELF_MANIFEST` both alphabetically
  `$(sort)` the full object-path list before writing the linker's
  response file, so the modern ELF's `.data`/`.bss` layout is controlled
  purely by each object's path *string*, never by `MODERN_ALL_C_SOURCES`/
  `MODERN_ALL_C_OBJECTS` list order -- a `build/generated/data/...`
  object would sort before every `src/...` object regardless of list
  position, shifting every other object's address and spuriously
  breaking the debugtools/savefmt runtime checkpoint fixtures' recorded
  absolute addresses even though no code changed. Reusing the exact
  original object path string keeps each linked table's object in
  precisely the same sorted slot its hand object always occupied, and
  GNU Make's explicit-rule-over-pattern-rule precedence guarantees that
  path always compiles from the generated source, never falling back to
  the (no-longer-source-listed, still untouched) hand file. Both the
  compile rule and the object reinstatement already generalize over
  `GENERATED_DATA_LINKED_TABLES` (`GENERATED_DATA_MODERN_OVERRIDE_RULES`
  in `modern.mk`), so Batch 2c-2 required no `modern.mk` changes at all,
  and Batch 2c-3/2c-4 required none either.
* **Verification**: `make generated-data-link-check` proves the swap end
  to end for every linked table (`classes`, `items`, `supports`,
  `characters`) -- exactly `src/data_classes.c src/data_items.c
  src/data_supports.c src/data_characters.c` filtered from both the
  legacy and modern cohorts (no other table affected), each generated
  object present exactly once in `ALL_OBJECTS`/`MODERN_ALL_C_OBJECTS`,
  each table's own `ldscript.txt` swap is exact, each table's own
  top-level symbol(s) (`gClassData`, `gItemData`, `gCharacterData`, or
  `supports`' 33 `SupportData_*` per-owner symbols) each link exactly
  once from its generated object -- and, for `supports`, that the
  generated object's `SupportData_*` symbol family is *exactly* those
  33, no more, no fewer (see the "Multi-symbol table verification"
  bullet above) -- every hand source is preserved untouched,
  `clean`/`clean_fast` cover the generated output directory, and, for
  each linked table in turn (serially -- never overlapping two tables'
  rm+touch+rebuild windows in the same `$(MAKE)` invocation), a
  touched-but-content-unchanged JSON input re-invokes that table's
  generator without an unnecessary downstream recompile (checked via
  captured build-log evidence -- the generator's own invocation must
  appear but the legacy compile/assemble pipeline must not -- and
  object-content MD5 stability, deliberately not filesystem mtime
  comparisons, which proved flaky), and a from-scratch parallel (`-j4`)
  build of every linked table's shared generated `.c`/`.o` pair is
  race-free. It is
  **local-only**, not CI-wired, because CI's tool
  install (`make_tools.mk`) deliberately excludes `tools/agbcc/Makefile`
  and cannot run the legacy pipeline; the modern half of this same swap
  is exercised automatically by CI's existing
  `expansion-modern-linker-check` for both `MODERN_CONFIG` values, no
  workflow changes required. A full clean legacy rebuild after this
  swap reproduces the pre-batch ROM MD5 exactly, `gClassData`'s
  address/size are unchanged, the generated `gItemData` object's `.data`
  bytes are byte-identical to the hand `src/data_items.c` object's own
  `.data` bytes, the generated `supports` object's `.data` bytes
  (792 bytes -- 33 24-byte records) are byte-identical to the hand
  `src/data_supports.c` object's own `.data` bytes, and the generated
  `characters` object's `.data` bytes (13,312 bytes -- 256 52-byte
  records) are byte-identical to the hand `src/data_characters.c`
  object's own `.data` bytes; both modern debug and release
  `expansion-modern-linker-check` runs (including
  `expansion-modern-debugtools-check`/`expansion-modern-savefmt-check`,
  which compare against address-sensitive checked-in fixtures) pass
  cleanly.
* All four Batch 1/2's global tables (`classes`, `items`, `supports`,
  `characters`) are now linked; extending this pattern to a future
  table means adding it to `GENERATED_DATA_LINKED_HAND_SOURCES` plus its
  own `GENERATED_DATA_CONFIG_INPUTS_<table>` (the generator's non-JSON,
  non-script "config" inputs) and `GENERATED_DATA_LINKED_SYMBOL_<table>`
  (that table's own top-level generated C symbol name(s) -- one, like
  `classes`/`items`/`characters`, or several space-separated, like
  `supports`' 33 -- plus, for a multi-symbol table, an optional
  `GENERATED_DATA_LINKED_SYMBOL_PREFIX_<table>` if an exact-family "no
  extra symbol" check is wanted) -- the modern-side reinstatement in
  `modern.mk`, and `generated-data-link-check` itself (generalized in
  Batch 2c-3 to handle either shape), already generalize over
  `GENERATED_DATA_LINKED_TABLES` via the
  `src/data_<table>.c`/`data_<table>.c` naming convention shared by
  every currently-linked table, with no further `modern.mk`/
  `generated-data-link-check` edits needed.
* **`$(OBJECTS_LST)` staleness fix (class-wide, found during Batch 2c-4
  review).** `objects.lst` (`$(OBJECTS_LST)` in `Makefile`) is the
  linker's `@objects.lst`-style response file: `echo $(ALL_OBJECTS) >
  $@`, one space-separated line. Its rule used to be a plain
  `$(OBJECTS_LST): $(ALL_OBJECTS)`, which relies on GNU Make's normal
  prerequisite *file mtime* tracking -- but `$(ALL_OBJECTS)` is a
  *variable*, and every linked-table swap (Batch 2c-1..2c-4) changes
  that variable's resolved *value* (filtering out `src/data_<table>.o`,
  appending `build/generated/data/data_<table>.o`) without necessarily
  touching any object *file*'s timestamp. If a stale `objects.lst` from
  before a swap (or from a branch/stash switch, or a stale pulled
  worktree) already exists and happens to be newer than every file in
  the current `$(ALL_OBJECTS)`, Make considers the target already up to
  date and **never re-runs the recipe** -- so a bare, incremental
  `make fireemblem8.gba` links against the old manifest, which still
  lists the hand object *and* the linker still finds the generated
  object also linked in, producing
  `arm-none-eabi-ld: multiple definition of 'g<Table>Data'`. This is a
  class-wide risk for every currently- and future-linked table, not
  specific to `characters`. Fixed by making the rule
  `$(OBJECTS_LST): $(ALL_OBJECTS) FORCE` (`FORCE` is the pre-existing
  generic always-run `.PHONY` target also used by `mgfembp.bin`) so the
  recipe *always* re-evaluates the current `$(ALL_OBJECTS)`, but writes
  through a temp file and only replaces `objects.lst` when the content
  actually differs (`echo ... > $@.tmp; cmp -s $@.tmp $@ && rm -f
  $@.tmp || mv -f $@.tmp $@`) -- so a content-stable rebuild still
  leaves `objects.lst`'s own mtime untouched and does not spuriously
  invalidate `$(ELF)`/`shiftcheck-diff`/`shiftcheck-run` (all of which
  depend on `$(OBJECTS_LST)` as a Make target, so they transparently
  benefit from the fix with no changes of their own). `generated-data-
  link-check` gained a matching regression test: it stages a corrupted
  `objects.lst` (every linked table's generated path swapped back to its
  hand-object path, mimicking the pre-swap/stale state) with its mtime
  pushed a day into the future -- deliberately the worst case for any
  mtime-based staleness check -- invokes `$(MAKE) $(OBJECTS_LST)`, and
  asserts every generated object now appears exactly once, every stale
  hand object appears zero times, the total object count and an
  unrelated anchor entry (`src/data_terrains.o`) are unchanged, and a
  second, already-correct invocation leaves the file's mtime unchanged.
  Verified manually beyond the automated test: a full incremental (non-
  clean) `make fireemblem8.gba` run with the same staged-stale
  `objects.lst` (plus the old `src/data_characters.o` still present on
  disk) self-heals the manifest, relinks with no multiple-definition
  error, recompiles no objects (only the link/strip/objcopy steps
  re-run), and reproduces the exact pre-batch ROM MD5; a further bare
  rebuild once the manifest is already correct touches none of
  `objects.lst`/`fireemblem8.elf`/`fireemblem8.gba` (no spurious
  relink); `shiftcheck-build` and `shiftcheck-static` (which build
  `$(RELOCS_ELF)`, itself depending on `$(OBJECTS_LST)`) both still
  pass; and a full `clean_fast` + from-scratch rebuild, `generated-data-
  check` (zero drift, all 10 tables), and both modern
  `expansion-modern-linker-check` configs (`debug`/`release`) all pass
  unchanged.

```bash
python3 -m unittest discover -s scripts/generated_data/tests -v
```

Covers, for `supports`: valid generation, deterministic/repeatable
generation, write-if-changed semantics, duplicate owner/partner/symbol
detection, missing character references, self-references, out-of-range
values, parallel-array/count mismatches, fixed-capacity overflow,
reciprocal mismatch and reciprocal-missing detection, `file:line:column`
source locations, the escape-hatch mechanism (valid/malformed/undeclared
symbols against its own test fixtures), the full 33-record hand-table
round trip (plus injected mismatch detection), and CLI-level drift
detection (including against the real committed
`src/data/supports.json` and inventory report).

`test_chapterbundle_schema.py` covers, for Batch C's `chapterbundle`
table (reusing the "EL" fixture family already established by
`tests/fixtures/eventlists/`, plus a small `deps_supports.json` and tiny
fixture `chapters.h`/`chapter_settings.json`/`data_8B363C.c` stand-ins):
mismatched chapter index/internalName/mapEventDataId, a `mapEventDataId`
resolving to the wrong manifest symbol, an unknown chapter id, a required
support owner missing from `supportOwners.required`, a required support
owner with no `SupportData` record of its own, a required support
owner's un-reciprocated partner, an orphan unit/shop/trap/event-script
record (declared but unreachable and uncited), undeclared/duplicate
character/class/item dependencies, a stale bundle manifest (both a real
record missing from `tables.*.symbols` and a declared symbol that isn't a
real record), the full multi-table dependency graph's acyclic/
deterministic topological order plus a synthetic injected-cycle
detection test, and an end-to-end test loading all 6 real dependency
tables + the real `chapter_settings.json` and validating the exact
committed `src/data/ch2_bundle.json` with zero diagnostics.
`test_cli_new_tables.py`'s `CliChapterBundleTests` covers the same
table's `validate`/`generate`/`check` CLI subcommands (including the
metadata-only C-output skip message and committed-inventory drift
detection) against both a fixture copy and the real committed bundle.

Additionally covers, for the Batch A tables (`test_units_schema.py`,
`test_units_roundtrip.py`, `test_units_generate.py`,
`test_shops_schema.py`, `test_shops_roundtrip.py`,
`test_shops_generate.py`, `test_traps_schema.py`,
`test_traps_roundtrip.py`, `test_traps_generate.py`,
`test_eventscripts_schema.py`, and the new-table cases in
`test_cli_new_tables.py`):

* `units`: duplicate group symbols, missing character/class/item
  references, out-of-range level/position/REDA values, item-capacity
  overflow, wrong AI-array length, header-derived constant reads
  (`UNIT_DEFINITION_ITEM_COUNT`, `UDEF_AIIDX_MAX`), generic filler units'
  raw-int `charIndex`, deterministic generation, and the full 7-group
  hand-table round trip against `src/events_udefs.c` (plus fixture-based
  match/mismatch and injected-mismatch detection).
* `shops`: duplicate shop symbols, missing item references, empty
  `items[]`, explicit `ITEM_NONE` terminator rejection, deterministic
  generation, and the full hand-table round trip against
  `src/events_shoplist.c` (plus fixture-based match/mismatch detection).
* `traps`: duplicate trap array symbols, undefined trap-type references,
  explicit `TRAP_NONE` terminator rejection, out-of-range
  position/subtype values, capacity-override overflow detection,
  header-derived constant reads (`TRAP_MAX_COUNT`, the scoped trap-type
  enum), deterministic generation, the full hand-table round trip against
  the (trivial) Chapter 2 arrays in `src/events_trapdata.c`, and a general
  non-trivial round trip against the real `TrapData_Event_Ch7` (2 ballista
  entries) proving the full 6-field format works beyond Chapter 2's own
  trivial data.
* `eventscripts`: duplicate symbols, unknown owner/kind values, undeclared
  symbol detection, missing header detection, and the full 43-record
  validation against the real `include/eventcall.h`.
* CLI: `validate`/`generate`/`check` for all 4 Batch A new tables against
  both fixtures and the real committed Chapter 2 JSON sources, including
  the `eventscripts` metadata-only skip message and drift-free checks
  against all 4 tables' real inventories.

Additionally covers, for Batch B (`test_eventlists_schema.py`,
`test_eventlists_generate.py`, `test_eventlists_roundtrip.py`, and the
`CliEventListsTests` cases in `test_cli_new_tables.py`):

* `eventlists`: missing unit/shop/trap/event-script cross-table
  references (each resolved against fixture-only
  `units`/`shops`/`traps`/`eventscripts` dependency records via
  `--dep-source`, proving isolation from the real Chapter 2 data), wrong
  macro arity/argument type, duplicate chapter-wide `EVFLAG_TMP(n)` use,
  duplicate `locationBasedEvents` coordinates, a macro used in a list
  that doesn't allow it, explicit `END_MAIN`/`NULL` terminator rejection,
  a missing required list field, an `EVFLAG_TMP` value outside the
  header-documented free range, duplicate list symbols, tutorial
  wrong-count/duplicate/explicit-terminator/wrong-owner detection,
  manifest missing/extra/mismatched-reference field detection,
  deterministic C89 generation (including that every list still
  terminates in a bare, un-comma'd `END_MAIN` and the tutorial array
  renders as a `NULL`-terminated pointer array), and the full hand-table
  round trip against `src/events/ch2-eventinfo.h` -- **100%** of macro
  invocations/order/arguments, the tutorial list, and every `Ch2Events`
  designated field (plus fixture-based match/mismatch and
  injected-mismatch detection for missing lists, tutorial entries, and
  manifest fields). CLI tests additionally cover `validate`/`generate`/
  `check` against the real committed `src/data/ch2_eventlists.json`
  (drift-free) and the fixture-plus-`--dep-source` isolation path.

Additionally covers, for Issue #5 Batch 1 (`test_items_schema.py`,
`test_items_generate.py`, `test_items_roundtrip.py`, the two new generic
`validators.py` helper tests -- `ExtractDefineConstantTests`,
`ResolveBitmaskFlagsTests` -- and the `CliItemsTests` cases in
`test_cli_new_tables.py`):

* `items`: duplicate item entries, a gap in `ITEM_*` coverage (validated
  against small fixture headers -- `mini_items.h`/`mini_bmitem.h`/
  `mini_variables.h`/`mini_msg.h`/`mini_item_icon.c` -- so the mandatory
  full-coverage check can be exercised in isolation, without every test
  also having to author all 206 real records), undefined item/weapon-
  type/weapon-exp-threshold/weapon-effect references, undefined and
  duplicate `IA_*` attribute flags, out-of-range text IDs/range nibbles/
  icon IDs/`useEffect`, undeclared `statBonuses`/`effectiveness` C-symbol
  references, header-derived constant reads (the scoped `IA_*` block
  excluding the `// Helpers` combos, live `MSG_COUNT`, live item-icon
  count), deterministic C89 generation (default-field omission, ascending
  attribute-flag ordering regardless of JSON order), fixture-based
  round-trip match/mismatch/missing/extra-item detection, and the full
  **206/206** hand-table round trip against the real `src/data_items.c`
  with zero diagnostics. CLI tests cover `validate`/`generate`/`check`
  against both an invalid fixture and the real committed
  `src/data/items.json` (drift-free). The generated
  `build/generated/data/data_items.c` was also compiled end-to-end
  through the real `cpp | iconv | agbcc` pipeline (mirroring the
  Makefile's `$(C_OBJECTS)` recipe) and assembled with `arm-none-eabi-as`
  with zero errors/warnings, confirming it is valid, compilable C89 --
  at this point (Batch 1) it was not yet linked in place of
  `src/data_items.c` (linking was out of Batch 1 scope). **It has since
  been linked** (Issue #5 **Batch 2c-2**; see "Linking a generated table
  in place of its hand-written counterpart" below) -- `gItemData` is now
  the canonical, compiled/linked symbol, with `src/data_items.c` itself
  kept only as the round-trip reference.

Additionally covers, for Issue #5 Batch 1's `classes` table
(`test_classes_schema.py`, `test_classes_generate.py`,
`test_classes_roundtrip.py`, and the `CliClassesTests` cases in
`test_cli_new_tables.py`):

* `classes`: duplicate class entries, a gap in `CLASS_*` coverage
  (validated against small fixture headers -- `mini_classes.h`/
  `mini_bmunit.h`/`mini_bmitem.h`/`mini_ekrbattle.h`/`mini_variables.h`/
  `mini_msg.h`/`mini_portrait_data.c`/`mini_sms_data.c` -- so the
  mandatory full-coverage check can be exercised in isolation), undefined
  class/promotion/weapon-type/weapon-exp-threshold references, undefined
  and duplicate `CA_*` attribute flags, out-of-range text IDs/SMS IDs/
  portrait IDs/base-stat (`s8`) and promotion-gain (`u8`) values,
  undeclared `battleAnim`/`movCostTable`/terrain-lookup/
  `reservedTerrainTable` C-symbol references, an incorrect
  `movCostTable` entry count, header-derived constant reads (the scoped
  `CA_*` block excluding the `// Helpers` combos, live `MSG_COUNT`, live
  portrait/SMS counts, live `baseRanks`/`pMovCostTable` array
  capacities), deterministic C89 generation (default-field omission,
  ascending attribute-flag/base-rank ordering regardless of JSON order,
  the literal `(void *)0x00000000` null-pointer cast for immobile
  classes' `movCostTable` entries), fixture-based round-trip match/
  mismatch/missing/extra-class detection, and the full **127/127**
  hand-table round trip against the real `src/data_classes.c` with zero
  diagnostics. CLI tests cover `validate`/`generate`/`check` against both
  an invalid fixture and the real committed `src/data/classes.json`
  (drift-free). The generated `build/generated/data/data_classes.c` was
  also compiled end-to-end through the real `cpp | iconv | agbcc`
  pipeline and assembled with `arm-none-eabi-as` with zero errors,
  confirming it is valid, compilable C89 -- at this point (Batch 1) it
  was not yet linked in place of `src/data_classes.c` (linking was out of
  Batch 1 scope). **It has since been linked** (Issue #5 **Batch 2c-1**;
  see "Linking a generated table in place of its hand-written
  counterpart" below) -- `gClassData` is now the canonical,
  compiled/linked symbol, with `src/data_classes.c` itself kept only as
  the round-trip reference.

All fixtures and scratch directories live under
`scripts/generated_data/tests/` (never `/tmp`).

## Linking a Chapter-2-owned partial-file table (Batch 3a: `units`)

Batch 2c-1..2c-4 each swapped out one *entire* hand-written
`src/data_<table>.c` file, viable because each of those files contains
nothing but that one global table. `units` (Batch 3a, the first
Chapter-2-*owned* table to link) is structurally different: its hand
definitions (the 7 `UnitDefinition` group symbols --
`UnitDef_Event_Ch2Ally`/`UnitDef_Ch2Enemy_0`/`UnitDef_LordSplitAlly`/
`UnitDef_Ch2Ally`/`UnitDef_Ch2NPC`/`UnitDef_Ch2Enemy_1`/
`UnitDef_Ch2Enemy_2`, plus their private `REDA` sub-arrays) are only a
*textual* prefix slice of `src/events_udefs.c` -- a 75k+ line file that
also defines every other chapter's units and must stay hand-linked
untouched, so this slice can't be excluded from compilation by filtering
a whole file out of `CFILES`/`MODERN_ALL_C_SOURCES` the way
`GENERATED_DATA_LINKED_*` does.

**The in-source guard.** `src/events_udefs.c` carries its own
self-contained guard: `#define GENERATED_DATA_UNITS_CH2_LINKED 1`
immediately above the Chapter 2 block, which is itself wrapped in
`#if !GENERATED_DATA_UNITS_CH2_LINKED` / `#endif`. Since the macro is
unconditionally defined to 1 right there in the source, that block is
permanently excluded from compilation -- but its source text is left
completely untouched, because `generated-data-check`'s own round-trip
parser (`units/parser.py`) reads `src/events_udefs.c`'s raw text
directly (brace-depth-aware regex, never the compiler) to keep proving
the generated table byte-for-byte identical in meaning to it;
preprocessor directives are invisible to that text-based parser, so the
guard cannot desync the two. Never hand-edit the guarded block -- edit
`src/data/ch2_units.json` and regenerate instead.

**Not a binary-layout prefix.** The excluded block is a prefix of
`src/events_udefs.c`'s own top-level definitions, but *not* of the
translation unit's compiled `.data` layout: the file's own
`#include "events/prologue-eventudefs.h"` and
`#include "events/ch1-eventudefs.h"`, just above the guard, emit
Prologue/Chapter-1 `REDA`/`UnitDefinition` data first, ahead of Chapter
2, all still compiled into the same `events_udefs.o`. So
`build/generated/data/data_ch2_units.o` must land, address-wise,
*between* that still-hand Prologue/Ch1 data and `events_udefs.c`'s own
Chapter 3+ data -- not merely before the whole object (an earlier
attempt at "insert before `events_udefs.o(.data)`" built successfully
but produced a ROM that was **not** byte-identical to a pre-change
baseline: it shifted Prologue/Ch1's addresses forward by the size of
the inserted object, while leaving Chapter 3+ correctly placed only by
coincidence of matching total size -- diagnosed via `cmp -l` against a
saved baseline ROM plus `objdump -h`/`nm -S` section-size arithmetic on
both the baseline and rebuilt `events_udefs.o`).

Since a single input section is placed by the linker as one atomic
unit, right after the guard's closing `#endif` `src/events_udefs.c`
redirects everything from Chapter 3 onward into a second,
distinctly-named section:

```c
#endif /* !GENERATED_DATA_UNITS_CH2_LINKED */

#undef CONST_DATA
#define CONST_DATA SECTION(".data.ch2tail")

CONST_DATA struct REDA REDA_Event_Ch3Ally_EIRIKA[] = {
    ...
```

splitting `events_udefs.o`'s `.data` into two independently-placeable
pieces of the *same* object file (verified via `objdump -h
src/events_udefs.o`, which shows both a `.data` section, 0x680 bytes --
exactly the Prologue+Ch1 content -- and a `.data.ch2tail` section
holding the rest).

**Legacy (`ldscript.txt`).** Three lines, in order, in place of the
original single `src/events_udefs.o(.data)` line:

```
. = ALIGN(4); src/events_udefs.o(.data);
. = ALIGN(4); build/generated/data/data_ch2_units.o(.data);
. = ALIGN(4); src/events_udefs.o(.data.ch2tail);
```

`src/events_udefs.o(.data)` (Prologue/Ch1, unchanged) lands at the
original address; the generated object lands immediately after, at the
exact original Chapter 2 address; `src/events_udefs.o(.data.ch2tail)`
(Chapter 3+, unchanged) resumes immediately after that, at its own
original address. Verified via `cmp` against a saved pre-change ROM:
byte-identical (zero differing bytes), including after a full
`clean_fast` + from-scratch rebuild and after the `objects.lst`
self-heal path.

**Modern (`modern.mk`).** Modern's own
`MODERN_ELF_OBJECTS_LST`/`MANIFEST` rules `$(sort)` the full object list
to decide floating-`.data` placement order (see the
`GENERATED_DATA_LINKED_C` reinstatement comment in `modern.mk`) -- there
is no "original hand path" to reuse here since this object is additive,
not a replacement, so it is instead reinstated at a synthetic slot path
(`$(MODERN_OUTPUT_DIR)/src/events_u-ch2units.o`) deliberately chosen to
sort immediately between `src/events_trapdata.o` and `src/events_udefs.o`
-- the same adjacency `ldscript.txt` gives it in the legacy build.
Modern's per-*object* (not per-input-section) sort keeps
`events_udefs.o`'s own two sections (`.data` and `.data.ch2tail`)
adjacent to each other regardless of the split, so the synthetic slot
ends up immediately before `events_udefs.o` as a whole rather than truly
between its two pieces -- an acceptable, deliberate divergence from
legacy's byte layout. It is also compiler-enforced rather than merely
theoretical: `arm-none-eabi-gcc` (unlike legacy's `agbcc`/GCC 2.95) warns
`ignoring attribute 'section (".data.ch2tail")' because it conflicts
with previous 'section (".data")'` for every Chapter-3+ symbol that also
has an `extern CONST_DATA ...` declaration in `include/eventcall.h`
(declared with the *original*, unmodified `CONST_DATA` before
`events_udefs.c`'s local redefinition takes effect) -- so modern
compiles the whole of `events_udefs.o`'s data into a single `.data`
section with no `.data.ch2tail` split at all (confirmed via `objdump -h`
on the modern-built object: one `.data` section, no
`.data.ch2tail`). This is a mere warning, not a build failure (`modern.mk`
does not pass `-Werror` broadly, only `-Werror=strict-prototypes
-Werror=implicit-function-declaration -Werror=incompatible-pointer-types`),
and does not affect field *values* -- only section placement -- so it
does not corrupt modern's build; it simply means modern's `.data` layout
for this object differs slightly from legacy's, which is within modern's
already-established requirement (a successful, shiftable build, not
literal re-derivation of legacy's exact byte layout -- see
`scripts/shiftcheck/`, which checks relocation-safety, not byte identity
against a prior build).

**Verification performed for Batch 3a:**

* `generated-data-check --table units` -- zero drift against the
  (guard-preserved) hand block's source text (7 records).
* `generated-data-ch2-units-link-check` (new `generated_data.mk`
  target, mirroring `generated-data-link-check`'s rigor for this
  differently-shaped migration): guard presence, hand block preserved
  verbatim, the `CONST_DATA` `.data.ch2tail` redirect present, the
  three-line `ldscript.txt` ordering and adjacency, legacy
  `ALL_OBJECTS` presence (both the generated object and the
  still-required `events_udefs.o`), the modern synthetic-slot adjacency,
  the generated object's exactly-one-each 7 group symbols, a rebuild of
  `src/events_udefs.o` proving it now defines zero Chapter 2 group
  symbols while still defining Chapter 1/3 symbols untouched, clean
  coverage, touched-but-unchanged-input no-op-regenerate behavior, and a
  from-scratch parallel (`-j4`) build.
* `generated-data-link-check` (Batch 2c-1..2c-4 regression) and
  `generated-data-check` (all 10 tables) both still pass unchanged.
* `python3 -m unittest discover -s scripts/generated_data/tests` -- all
  398 tests pass, including a new regression test
  (`test_all_reda_arrays_precede_all_unitdefinition_arrays` in
  `test_units_generate.py`) that locks in the exact hand-file emission
  order (every `REDA` array across all groups before any
  `UnitDefinition` group array -- getting this backwards was the actual
  root cause of the byte-diff described above, since `generate.py`
  originally interleaved each group's `REDA` arrays with its own
  `UnitDefinition` array).
* A full legacy rebuild (`make fireemblem8.gba`, including a from-clean
  rebuild and a rebuild through a deliberately-staged stale
  `objects.lst`) is byte-identical (`cmp`, zero differing bytes; MD5
  match) to a saved pre-change baseline ROM.
* Both modern configs (`MODERN_CONFIG=debug` and `MODERN_CONFIG=release`)
  build cleanly end to end (`expansion-modern-rom`) and pass the full
  `expansion-modern-linker-check` (budget, overlay-audit, boot-check,
  title-check, debugtools-check, debugtools-timer-check, savefmt-check,
  shifted-check, `scan_build_addrs.py`, `scan_raw_casts.sh`).

## Linking two non-adjacent Chapter-2-owned symbols in one partial-file table (Batch 3b: `traps`)

`traps` is structurally like `units` (Batch 3a, above): its two Chapter 2
symbols (`TrapData_Event_Ch2`, `TrapData_Event_Ch2Hard`) are only a
slice of `src/events_trapdata.c`, a translation unit that also defines
every other chapter's (and every other difficulty's) trap arrays, which
must stay hand-linked untouched.

**Not adjacent, unlike `units`.** `src/events_trapdata.c` is laid out as
one normal-mode block (`TrapData_Event_Prologue` .. `TrapData_Event_Ch19B_0`,
where `TrapData_Event_Ch2` lives, right after `TrapData_Event_Ch1`)
followed by one hard-mode block (`TrapData_Event_PrologueHard` ..
`TrapData_Event_DebugMap_22`, where `TrapData_Event_Ch2Hard` lives,
~1850 lines later, right after `TrapData_Event_Ch1Hard`). Unlike
`units`' single contiguous prefix, these two symbols cannot be excluded
from compilation by one `#if !GUARD` / `#endif` region; instead
`src/events_trapdata.c` wraps each in its own such region, sharing one
guard macro (`GENERATED_DATA_TRAPS_CH2_LINKED`, defined once,
immediately above the first region):

```c
#define GENERATED_DATA_TRAPS_CH2_LINKED 1

#if !GENERATED_DATA_TRAPS_CH2_LINKED
CONST_DATA u8 TrapData_Event_Ch2[] = {
    TRAP_NONE
};
#endif /* !GENERATED_DATA_TRAPS_CH2_LINKED */
...
#if !GENERATED_DATA_TRAPS_CH2_LINKED
CONST_DATA u8 TrapData_Event_Ch2Hard[] = {
    /* type */ TRAP_NONE
};
#endif /* !GENERATED_DATA_TRAPS_CH2_LINKED */
```

Both blocks are left in place, verbatim -- never hand-edit either one,
edit `src/data/ch2_traps.json` and regenerate instead.

**Per-symbol sectioning (the actual structural difference from `units`).**
Since a single input section is placed by the linker as one atomic unit,
and the two symbols must land at addresses roughly 1850 hand-written
trap-array lines apart, splicing in one generated object with both
symbols in the *same* default section (the `units` approach) would force
one of the two to jump far from its original address. Instead,
`scripts/generated_data/traps/generate.py` places `TrapData_Event_Ch2Hard`
alone into its own dedicated section (`.data.trapch2hard`), distinct
from `TrapData_Event_Ch2`'s ordinary `.data`:

```c
CONST_DATA u8 TrapData_Event_Ch2[] = {
    /* type */ TRAP_NONE
};

SECTION(".data.trapch2hard") u8 TrapData_Event_Ch2Hard[] = {
    /* type */ TRAP_NONE
};
```

so the *same* generated object (`build/generated/data/data_ch2_traps.o`)
can be spliced into `ldscript.txt` at two independent points. Combined
with two `#undef CONST_DATA` / `#define CONST_DATA SECTION(...)`
redirects in `src/events_trapdata.c` (right after each guard's closing
`#endif` -- first to `.data.trapch2mid` for Chapter 3 through
`TrapData_Event_Ch1Hard`, then to `.data.traptail` for
`TrapData_Event_Ch3Hard` through end-of-file), this produces a
four-piece split.

**No `ALIGN(4)` at the internal seams -- the actual pitfall hit during
verification.** An initial version of this split used
`. = ALIGN(4);` before each of the four pieces, mirroring `units`'
three-piece split exactly. That built successfully but produced a ROM
that was **not** byte-identical to a pre-change baseline (diagnosed via
`cmp -l` showing ~1.18M differing bytes from a small offset onward, plus
the ROM's own trailing `0xFF` pad region shrinking) -- because unlike
`units`' `REDA`/`UnitDefinition` structs (which happen to land on
naturally 4-byte-aligned boundaries), these `u8[]` trap arrays are
packed by the compiler with **no** alignment padding between them at
all: `TrapData_Event_Ch2Hard` sits at ROM address `0x89EDE9D` and
`TrapData_Event_Ch3Hard` immediately follows at `0x89EDE9E` (a 1-byte
gap, `0x9D mod 4 == 1`, nowhere near 4-aligned). Adding `. = ALIGN(4);`
at internal split points that don't naturally fall on a 4-byte boundary
inserts up to 3 padding bytes at *every* such seam, shifting everything
after it. The fix: keep `. = ALIGN(4);` only on the very first line
(`src/events_trapdata.o(.data)`, which existed before this batch, at the
section's original single entry point) and drop it entirely from the
three new internal seams, so the originally-single, compiler-packed byte
stream is re-spliced across the two objects with zero extra bytes
anywhere.

**Legacy (`ldscript.txt`).** Five lines, in order, in place of the
original single `src/events_trapdata.o(.data)` line:

```
. = ALIGN(4); src/events_trapdata.o(.data);
build/generated/data/data_ch2_traps.o(.data);
src/events_trapdata.o(.data.trapch2mid);
build/generated/data/data_ch2_traps.o(.data.trapch2hard);
src/events_trapdata.o(.data.traptail);
```

`src/events_trapdata.o(.data)` (Prologue..Ch1, unchanged) lands at the
original address; the generated `TrapData_Event_Ch2` lands immediately
after, at the exact original Chapter 2 address;
`src/events_trapdata.o(.data.trapch2mid)` (Ch3..Ch1Hard, unchanged)
resumes immediately after that; the generated `TrapData_Event_Ch2Hard`
lands next, at the exact original Chapter 2 Hard address; then
`src/events_trapdata.o(.data.traptail)` (Ch3Hard..EOF, unchanged) resumes
at its own original address. Verified via `cmp` against a saved
pre-change ROM: byte-identical (zero differing bytes).

**Modern (`modern.mk`).** Same reasoning as the `units` synthetic slot --
modern links whole objects, not per-input-section, and this object is
additive (no "original hand path" to reuse), so it is reinstated at a
synthetic slot path (`$(MODERN_OUTPUT_DIR)/src/events_t-ch2traps.o`)
chosen to sort immediately before `src/events_trapdata.o` -- an
acceptable, already-established divergence for the modern build (modern's
requirement is a successful, shiftable build, not literal re-derivation
of legacy's byte layout).

**Verification performed for Batch 3b:**

* `generated-data-check --table traps` -- zero drift against the
  (guard-preserved) hand blocks' source text (2 records).
* `generated-data-ch2-traps-link-check` (new `generated_data.mk` target,
  mirroring `generated-data-ch2-units-link-check`'s rigor for this
  two-non-adjacent-block migration): both guards present, both hand
  blocks preserved verbatim, both `CONST_DATA` redirects
  (`.data.trapch2mid`, `.data.traptail`) present, the five-line
  `ldscript.txt` ordering and adjacency, legacy `ALL_OBJECTS` presence
  (both the generated object and the still-required
  `events_trapdata.o`), the modern synthetic-slot adjacency, the
  generated object's exactly-one-each 2 trap symbols each in their
  expected section, a rebuild of `src/events_trapdata.o` proving it now
  defines zero Chapter 2 trap symbols while still defining the
  surrounding chapters' traps untouched, clean coverage,
  touched-but-unchanged-input no-op-regenerate behavior, and a
  from-scratch parallel (`-j4`) build.
* `generated-data-ch2-units-link-check` (Batch 3a regression),
  `generated-data-link-check` (Batch 2c-1..2c-4 regression), and
  `generated-data-check` (all 10 tables) all still pass unchanged.
* `python3 -m unittest discover -s scripts/generated_data/tests` -- all
  400 tests pass, including 2 new regression tests
  (`Ch2SectionSplitTests` in `test_traps_generate.py`) that lock in
  `TrapData_Event_Ch2` staying in the default `CONST_DATA`/`.data`
  section while `TrapData_Event_Ch2Hard` gets its own
  `.data.trapch2hard` section.
* A full legacy rebuild (`make fireemblem8.gba`) is byte-identical
  (`cmp`, zero differing bytes; MD5 match) to a saved pre-change
  baseline ROM.
* `make shiftcheck` (build/static/offsets/diff layers) passes with no
  high-confidence hardcoded-pointer findings.
* Both modern configs (`MODERN_CONFIG=debug` and `MODERN_CONFIG=release`)
  pass the full `expansion-modern-linker-check` (budget, overlay-audit,
  boot-check, title-check, debugtools-check, debugtools-timer-check,
  savefmt-check, shifted-check, `scan_build_addrs.py`,
  `scan_raw_casts.sh`).

## Linking a single Chapter-2-owned interior symbol in a shared shop-list file (Batch 3c: `shops`)

`shops` is structurally like `units` (Batch 3a, above): its one Chapter
2 symbol (`ShopList_Event_Ch2Armory`) is only a slice of
`src/events_shoplist.c`, a translation unit that also defines every
other shop's item list, which must stay hand-linked untouched -- so this
slice can't be excluded from compilation by filtering a whole file out
of `CFILES`/`MODERN_ALL_C_SOURCES` the way `GENERATED_DATA_LINKED_*`
does.

**Interior, not a prefix, unlike `units`.** `ShopList_Event_Ch2Armory`
sits in the *middle* of `src/events_shoplist.c`: still-hand
`ShopList_Tower*`/`ShopList_Ruin*` arrays precede it, and
`ShopList_Event_Ch5Armory` (followed by every later chapter's shop) comes
right after it. The same single-guard, single-section-redirect technique
as `units` still applies -- one `#if !GENERATED_DATA_SHOPS_CH2_LINKED /
#endif` region around the array, then one `#undef CONST_DATA` /
`#define CONST_DATA SECTION(".data.shopch2tail")` redirect right after
the guard's closing `#endif` -- just with a real prefix *and* a real
suffix to preserve on either side, rather than only a suffix:

```c
#define GENERATED_DATA_SHOPS_CH2_LINKED 1

#if !GENERATED_DATA_SHOPS_CH2_LINKED
CONST_DATA u16 ShopList_Event_Ch2Armory[] = {
    ITEM_SWORD_SLIM,
    ...
    ITEM_NONE,
};
#endif /* !GENERATED_DATA_SHOPS_CH2_LINKED */

#undef CONST_DATA
#define CONST_DATA SECTION(".data.shopch2tail")

CONST_DATA u16 ShopList_Event_Ch5Armory[] = {
    ...
```

The array is left in place, verbatim -- never hand-edit it, edit
`src/data/ch2_shops.json` and regenerate instead; `generated-data-check`'s
round-trip parser (`shops/parser.py`) reads this exact source text
directly (regex-based, never the compiler), so the preprocessor guard
around it is invisible to that check and cannot desync the two.

**No per-symbol sectioning needed, unlike `traps`.** `shops` currently
has exactly one Chapter-2-owned symbol, so the generated object
(`build/generated/data/data_ch2_shops.o`) contains only that one array,
in the default `CONST_DATA`/`.data` section -- there is no second symbol
requiring its own dedicated section the way `traps`' non-adjacent
`TrapData_Event_Ch2Hard` did.

**`ALIGN(4)` at every seam is safe, unlike `traps`.** Both the array's
start (`0x89ED7CC`) and end (`0x89ED7D8`) addresses fall on natural
4-byte boundaries: a 6-entry `u16[]` (5 items + 1 `ITEM_NONE`
terminator) is always a multiple of 4 bytes. So, unlike the `traps`
table's packed `u8[]` split (which required dropping internal
`ALIGN(4)` to avoid padding), this three-piece split keeps
`. = ALIGN(4);` at every piece, exactly like the `units` table's
three-piece split.

**Legacy (`ldscript.txt`).** Three lines, in order, in place of the
original single `src/events_shoplist.o(.data)` line:

```
. = ALIGN(4); src/events_shoplist.o(.data);
. = ALIGN(4); build/generated/data/data_ch2_shops.o(.data);
. = ALIGN(4); src/events_shoplist.o(.data.shopch2tail);
```

`src/events_shoplist.o(.data)` (the still-hand Tower/Ruin prefix,
unchanged) lands at the original address; the generated object lands
immediately after, at the exact original Chapter 2 address;
`src/events_shoplist.o(.data.shopch2tail)` (Ch5Armory onward, unchanged)
resumes immediately after that, at its own original address. Verified
via `cmp` against a saved pre-change ROM: byte-identical (zero differing
bytes).

**Modern (`modern.mk`).** Same reasoning as the `units`/`traps`
synthetic slots -- modern links whole objects, not per-input-section,
and this object is additive (no "original hand path" to reuse), so it
is reinstated at a synthetic slot path
(`$(MODERN_OUTPUT_DIR)/src/events_sh-ch2shops.o`) chosen to sort
immediately before `src/events_shoplist.o`. Unlike `units`'/`traps`'
slot names (`events_u-ch2units.o`, `events_t-ch2traps.o`, each the only
`events_<letter>*` object in their respective alphabetic neighborhoods),
`src/events_shoplist.c`'s own `events_s*` neighborhood also contains
`events_script.o` and `events_script_utils.o`, both of which sort
between a naively-named `events_s-ch2shops.o` and `events_shoplist.o`;
the slot is instead named `events_sh-ch2shops.o` (matching one more
character of the target name) so it sorts immediately after
`events_script_utils.o` and immediately before `events_shoplist.o`,
preserving the same adjacency `ldscript.txt` gives it in the legacy
build with zero disruption to any other object's relative order.

**Verification performed for Batch 3c:**

* `generated-data-check --table shops` -- zero drift against the
  (guard-preserved) hand array's source text (1 record).
* `generated-data-ch2-shops-link-check` (new `generated_data.mk` target,
  mirroring `generated-data-ch2-units-link-check`'s rigor for this
  interior-symbol migration): guard present, hand array preserved
  verbatim, the `CONST_DATA` `.data.shopch2tail` redirect present, the
  three-line `ldscript.txt` ordering and adjacency, legacy
  `ALL_OBJECTS` presence (both the generated object and the
  still-required `events_shoplist.o`), the modern synthetic-slot
  adjacency, the generated object's exactly-one shop symbol, a rebuild
  of `src/events_shoplist.o` proving it now defines zero Chapter 2 shop
  symbols while still defining its immediate neighbors
  (`ShopList_Ruin10_0`, `ShopList_Event_Ch5Armory`) untouched, clean
  coverage, touched-but-unchanged-input no-op-regenerate behavior, and a
  from-scratch parallel (`-j4`) build.
* `generated-data-ch2-units-link-check` (Batch 3a regression),
  `generated-data-ch2-traps-link-check` (Batch 3b regression),
  `generated-data-link-check` (Batch 2c-1..2c-4 regression), and
  `generated-data-check` (all 10 tables) all still pass unchanged.
* `python3 -m unittest discover -s scripts/generated_data/tests` -- all
  400 tests pass unchanged (no new per-symbol-section test was needed,
  since `shops` has only the one Chapter-2-owned symbol and needs no
  section split inside the generated object itself).
* A full legacy rebuild (`make fireemblem8.gba`, including a rebuild
  after `generated-data-ch2-shops-link-check`'s own
  `src/events_shoplist.o` rebuild step) is byte-identical (`cmp`, zero
  differing bytes; MD5 match) to a saved pre-change baseline ROM.
* `make shiftcheck` (build/static/offsets/diff layers) passes with no
  high-confidence hardcoded-pointer findings.
* Both modern configs (`MODERN_CONFIG=debug` and `MODERN_CONFIG=release`)
  pass the full `expansion-modern-linker-check` (budget, overlay-audit,
  boot-check, title-check, debugtools-check, debugtools-timer-check,
  savefmt-check, shifted-check, `scan_build_addrs.py`,
  `scan_raw_casts.sh`), and `objdump -h` on the modern-built
  `src/events_shoplist.o` confirms the expected `.data`/
  `.data.shopch2tail` section split.

## Linking a Chapter-2-owned table with header-only content (Batch 3d: `eventlists`)

`eventlists` is structurally like `units`/`traps`/`shops` (Batch
3a/3b/3c, above): its Chapter 2 content is only a slice of a
translation unit (`src/events_info.c`) that also composes every other
chapter's own event-list data, which must stay hand-linked untouched --
so it can't be excluded from compilation by filtering a whole file out
of `CFILES`/`MODERN_ALL_C_SOURCES` the way `GENERATED_DATA_LINKED_*`
does.

**A guarded `#include`, not a guarded inline block, unlike `units`/
`traps`/`shops`.** `src/events_info.c` is nothing but a long sequence of
per-chapter `#include "events/<chapter>-eventinfo.h"` directives -- it
never defines any `EventListScr`/`ChapterEventGroup` data directly.
Chapter 2's entire contribution (the 7 `EventListScr_Ch2_*` arrays, the
`EventListScr_Ch2_Tutorial` pointer list, and the `Ch2Events` manifest --
9 symbols total) lives entirely in its own header,
`src/events/ch2-eventinfo.h`. So instead of wrapping inline array/struct
definitions in `#if !GUARD / #endif` (as `units`/`traps`/`shops` do),
`src/events_info.c` wraps the *`#include` directive itself*:

```c
#include "events/prologue-eventinfo.h"
#include "events/ch1-eventinfo.h"

#define GENERATED_DATA_EVENTLISTS_CH2_LINKED 1

#if !GENERATED_DATA_EVENTLISTS_CH2_LINKED
#include "events/ch2-eventinfo.h"
#endif /* !GENERATED_DATA_EVENTLISTS_CH2_LINKED */

#undef CONST_DATA
#define CONST_DATA SECTION(".data.ch2eventtail")

#include "events/ch3-eventinfo.h"
...
```

`src/events/ch2-eventinfo.h` itself is left in place, verbatim, on
disk -- never deleted, never hand-edited (edit
`src/data/ch2_eventlists.json` and regenerate instead) -- even though it
is no longer actually `#include`d into the compiled translation unit
once the guard macro is defined to 1. `generated-data-check`'s
round-trip parser (`eventlists/parser.py`) reads that header's exact
source text directly (macro-call/brace-depth-aware parsing, never the
compiler), so the preprocessor guard around its inclusion is invisible
to that check and cannot desync the two.

**Redirect covers Chapter 3 onward to end-of-file, exactly like
`units`.** Right after the guard's closing `#endif`, `#undef CONST_DATA`
/ `#define CONST_DATA SECTION(".data.ch2eventtail")` redirects
*everything* from the `events/ch3-eventinfo.h` include onward (every
later chapter, tower, ruin, and side-map header all the way to
end-of-file) into a second, distinctly-named section -- not just
Chapter 3's own data -- splitting `events_info.o`'s `.data` into two
independently-placeable pieces of the same object file. The section is
named `.data.ch2eventtail` rather than reusing `units`'
`.data.ch2tail`/`shops`' `.data.shopch2tail`: section names are already
fully object-file-qualified in `ldscript.txt` (`FILE.o(SECTION)`), so a
literal name collision across different object files would not actually
break the link, but a distinct name keeps each split's `ldscript.txt`
comments/grep-based checks unambiguous.

**`ALIGN(4)` at every seam is safe, exactly like `units`/`shops`.**
Chapter 2's block spans exactly `[0x89E942C, 0x89E95C4)` -- 0x198 (408)
bytes -- both boundaries falling on natural 4-byte boundaries (every
`EventListScr` array is terminated by the `END_MAIN` macro, which
expands to a whole 4-byte-aligned struct entry, and `Ch2Events` is a
pointer-heavy `struct ChapterEventGroup`), so, unlike the `traps` table's
packed `u8[]` split, this three-piece split keeps `. = ALIGN(4);` at
every piece with zero padding.

**Legacy (`ldscript.txt`).** Three lines, in order, in place of the
original single `src/events_info.o(.data)` line:

```
. = ALIGN(4); src/events_info.o(.data);
. = ALIGN(4); build/generated/data/data_ch2_eventlists.o(.data);
. = ALIGN(4); src/events_info.o(.data.ch2eventtail);
```

`src/events_info.o(.data)` (the still-hand Prologue/Ch1 prefix,
unchanged) lands at the original address; the generated object lands
immediately after, at the exact original Chapter 2 address
(`0x89E942C`); `src/events_info.o(.data.ch2eventtail)` (Chapter 3
onward, unchanged) resumes immediately after that, at its own original
address (`0x89E95C4`). Verified via `cmp` against a saved pre-change
ROM: byte-identical (zero differing bytes; MD5 match).

**Cross-table dependency inputs, unique to `eventlists`.** Unlike
`units`/`traps`/`shops`, `eventlists`' own schema declares
`dependency_tables()` (`units`, `shops`, `traps`, `eventscripts` -- see
`scripts/generated_data/eventlists/schema.py`), so
`GENERATED_DATA_CONFIG_INPUTS_eventlists` additionally lists
`src/data/ch2_units.json`/`ch2_shops.json`/`ch2_traps.json`/
`ch2_eventscripts.json` alongside the header inputs
(`include/constants/characters.h`, `include/bmunit.h`,
`include/constants/event-flags.h`), so a change to any of those also
triggers a regenerate of `data_ch2_eventlists.c`, mirroring the CLI's own
`_load_dependency_records()` behavior.

**Modern (`modern.mk`).** Same reasoning as the `units`/`traps`/`shops`
synthetic slots -- modern links whole objects, not per-input-section,
and this object is additive (no "original hand path" to reuse), so it
is reinstated at a synthetic slot path
(`$(MODERN_OUTPUT_DIR)/src/events_i-ch2eventlists.o`) chosen to sort
immediately before `src/events_info.o` (same `"-"` < any alnum trick as
the units/traps/shops slots above) and therefore doesn't shift any other
object's relative order. `objdump -h` on the modern-built
`src/events_info.o` confirms the expected `.data`/`.data.ch2eventtail`
section split.

**Verification performed for Batch 3d:**

* `generated-data-check --table eventlists` -- zero drift against the
  (guard-preserved) hand header's source text (9 record(s): 7 lists,
  1 tutorial list, 1 manifest).
* `generated-data-ch2-eventlists-link-check` (new `generated_data.mk`
  target, mirroring `generated-data-ch2-units-link-check`'s rigor for
  this header-only migration): guard present around the guarded
  `#include`, the hand header (`src/events/ch2-eventinfo.h`) preserved
  verbatim with all 9 symbol definitions intact, the `CONST_DATA`
  `.data.ch2eventtail` redirect present, the three-line `ldscript.txt`
  ordering and adjacency, legacy `ALL_OBJECTS` presence (both the
  generated object and the still-required `events_info.o`), the modern
  synthetic-slot adjacency, the generated object's exactly-9 symbols, a
  rebuild of `src/events_info.o` proving it now defines zero Chapter 2
  eventlists symbols while still defining its immediate neighbors
  (`EventListScr_Ch1_Tutorial`, `EventListScr_Ch3_Turn`) untouched, clean
  coverage, touched-but-unchanged-input no-op-regenerate behavior, and a
  from-scratch parallel (`-j4`) build.
* `generated-data-ch2-units-link-check` (Batch 3a regression),
  `generated-data-ch2-traps-link-check` (Batch 3b regression),
  `generated-data-ch2-shops-link-check` (Batch 3c regression), and
  `generated-data-check` (all 10 tables) all still pass unchanged.
* `python3 -m unittest discover -s scripts/generated_data/tests` -- all
  400 tests pass unchanged (no eventlists generator/test change was
  needed -- the existing macro-call emission already matches the hand
  header byte-for-byte once compiled, modulo cosmetic whitespace/
  alignment differences that produce identical compiled bytes).
* A full legacy rebuild (`make fireemblem8.gba`) is byte-identical
  (`cmp`, zero differing bytes; MD5 match) to a saved pre-change
  baseline ROM, and `Ch2Events`/`EventListScr_Ch2_Turn`/
  `EventListScr_Ch1_Tutorial`/`EventListScr_Ch3_Turn` all resolve to
  their exact pre-change addresses (`nm fireemblem8.elf`).
* `make shiftcheck` (build/static/offsets/diff layers) passes with no
  high-confidence hardcoded-pointer findings.
* Both modern configs (`MODERN_CONFIG=debug` and `MODERN_CONFIG=release`)
  pass the full `expansion-modern-linker-check` (budget, overlay-audit,
  boot-check, title-check, debugtools-check, debugtools-timer-check,
  savefmt-check, shifted-check, `scan_build_addrs.py`,
  `scan_raw_casts.sh`).
* `generated-data-check --table chapterbundle` still resolves
  `Ch2Events` and the full Chapter 2 bundle with zero drift, proving the
  chapterbundle validation path is unaffected by the eventlists link
  swap (it validates from JSON/records, not from the linked ROM).

## Linking two non-adjacent groups of terrain combat/heal stat arrays in one partial-file table (Batch 1 mechanics: `terrainstats`)

`terrainstats` is the first **global, not Chapter-2-owned**, table to be
linked via the partial-file-splice pattern `units`/`traps`/`shops`/
`eventlists` (Batch 3a-3d) established: its 8 symbols are only a slice
of `src/data_terrains.c`, a translation unit that also defines every
movement-cost table, the 5 `Unk_TerrainTable_3`..`Unk_TerrainTable_7`
escape-hatch arrays, and every `BanimTerrainGround_*`/`gBanimBGLut*`
graphics table -- all of which must stay hand-linked untouched -- so it
can't be excluded from compilation by filtering a whole file out of
`CFILES`/`MODERN_ALL_C_SOURCES` the way `GENERATED_DATA_LINKED_*` does.

**Two non-adjacent groups, structurally like `traps` (Batch 3b).** The 6
`Avo`/`Def`/`Res` arrays sit contiguously together (`TerrainTable_Avo_Common`
immediately after `Unk_TerrainTable_2`, running through
`TerrainTable_Res_Fly`), but the 5 `Unk_TerrainTable_3`..
`Unk_TerrainTable_7` escape-hatch arrays sit immediately after them,
followed only then by the 2 heal arrays
(`TerrainTable_HealAmount`/`TerrainTable_HealsStatus`), immediately
before the `BanimTerrainGround_*`/`gBanimBGLut*` graphics tables begin.
Like `traps`, this cannot be excluded from compilation by one
`#if !GUARD` / `#endif` region; instead `src/data_terrains.c` wraps each
group in its own such region, sharing one guard macro
(`GENERATED_DATA_TERRAINSTATS_LINKED`, defined once, immediately above
the first region):

```c
#define GENERATED_DATA_TERRAINSTATS_LINKED 1

#if !GENERATED_DATA_TERRAINSTATS_LINKED
CONST_DATA s8 TerrainTable_Avo_Common[TERRAIN_COUNT] = {
    ...
};
... /* Def_Common, Res_Common, Avo_Fly, Def_Fly, Res_Fly */
#endif /* !GENERATED_DATA_TERRAINSTATS_LINKED */

#undef CONST_DATA
#define CONST_DATA SECTION(".data.terrainmid")

CONST_DATA s8 Unk_TerrainTable_3[TERRAIN_COUNT] = { ... };
... /* Unk_TerrainTable_4..7, still hand-linked, untouched */

#if !GENERATED_DATA_TERRAINSTATS_LINKED
CONST_DATA s8 TerrainTable_HealAmount[TERRAIN_COUNT] = {
    ...
};
CONST_DATA s8 TerrainTable_HealsStatus[TERRAIN_COUNT] = {
    ...
};
#endif /* !GENERATED_DATA_TERRAINSTATS_LINKED */

#undef CONST_DATA
#define CONST_DATA SECTION(".data.terraintail")

CONST_DATA ... BanimTerrainGroundDefault ... = { ... };
```

Both guarded blocks are left in place, verbatim -- never hand-edit
either one, edit `src/data/terrainstats.json` and regenerate instead.
The 5 `Unk_TerrainTable_3`..`Unk_TerrainTable_7` arrays sitting *between*
the two guarded groups are themselves completely untouched hand data
(they stay real, uncommented-out C in the middle `#undef CONST_DATA` /
`#define CONST_DATA SECTION(".data.terrainmid")` redirect region) --
this batch does not model, generate, or validate them at all, exactly
per the DON'T constraint against touching movement-cost/graphics data.

**A comment-authoring pitfall hit during this migration.** An early
version of the trailing `.data.terraintail` redirect comment described
the following graphics tables as `BanimTerrainGround_*/gBanimBGLut*`.
The literal three-character sequence `*/` embedded mid-sentence
(`_*` immediately followed by `/g`) prematurely closed the enclosing
`/* ... */` block comment, letting the remaining comment text leak into
the preprocessed output as real (uncommented) tokens and produce a C89
syntax error (`missing terminating ' character`, `syntax error before
'*'`) at compile time -- a purely textual authoring hazard, not a
semantic one, but one worth flagging for any future comment mentioning
wildcard-style or pointer-adjacent-to-slash names in this file. Fixed by
rewording to separate the tokens (`BanimTerrainGround_ / gBanimBGLut`).

**Per-symbol sectioning for the heal arrays, structurally like `traps`.**
Since a single input section is placed by the linker as one atomic unit,
and the 6 Avo/Def/Res arrays must land immediately after
`Unk_TerrainTable_2` while the 2 heal arrays must land immediately
before `BanimTerrainGroundDefault` (a much later address), splicing in
one generated object with all 8 symbols in the *same* default section
would force one group to jump far from its original address. Instead,
`scripts/generated_data/terrainstats/generate.py` places the 6 Avo/Def/
Res arrays in the ordinary `CONST_DATA` (`.data`) section and the 2 heal
arrays alone into a dedicated `SECTION(".data.terrainheal")`, so the
*same* generated object
(`build/generated/data/data_terrainstats.c`/`.o`) can be spliced into
`ldscript.txt` at two independent points.

**No `ALIGN(4)` at the internal seams, exactly like `traps`.** Every one
of the ~50 arrays in `src/data_terrains.c` (movement-cost tables, the 8
terrainstats arrays, the 5 `Unk_TerrainTable_N` escape hatches, and the
graphics tables) is a flat `s8[TERRAIN_COUNT]`/similarly-sized array
packed by the compiler with **zero** alignment padding between adjacent
arrays, confirmed via `arm-none-eabi-nm -n src/data_terrains.o` on the
pre-change object: `Unk_TerrainTable_2` (65 bytes) ends exactly at
`0xc71`, where `TerrainTable_Avo_Common` begins; the 6 Avo/Def/Res
arrays run contiguously `0xc71`-`0xdf7` (390 = 6x65 bytes, zero gaps);
`Unk_TerrainTable_3`..`7` run `0xdf7`-`0xf3c` (325 = 5x65 bytes); the 2
heal arrays run `0xf3c`-`0xfbe` (130 = 2x65 bytes);
`BanimTerrainGroundDefault` begins immediately at `0xfbe`. Following the
`traps` precedent, `. = ALIGN(4);` is kept only on the very first line
(`src/data_terrains.o(.data)`, the section's original single entry
point) and dropped entirely from the four new internal seams, so the
originally-single, compiler-packed byte stream is re-spliced across the
two objects with zero extra bytes anywhere.

**Legacy (`ldscript.txt`).** Five lines, in order, in place of the
original single `src/data_terrains.o(.data)` line:

```
. = ALIGN(4); src/data_terrains.o(.data);
build/generated/data/data_terrainstats.o(.data);
src/data_terrains.o(.data.terrainmid);
build/generated/data/data_terrainstats.o(.data.terrainheal);
src/data_terrains.o(.data.terraintail);
```

`src/data_terrains.o(.data)` (movement-cost tables + `Unk_TerrainTable_1`/
`_2`, unchanged) lands at the original address; the generated 6 Avo/Def/
Res arrays land immediately after, at the exact original address;
`src/data_terrains.o(.data.terrainmid)` (`Unk_TerrainTable_3`..`_7`,
unchanged) resumes immediately after that; the generated 2 heal arrays
land next, at the exact original address; then
`src/data_terrains.o(.data.terraintail)` (`BanimTerrainGroundDefault`
onward, unchanged) resumes at its own original address. Verified via
`cmp`/`md5sum` against a saved pre-change ROM: byte-identical (zero
differing bytes; MD5 match).

**Cross-table consumer, unique to `terrainstats`.** Unlike `units`/
`traps`/`shops`/`eventlists` (all consumed only by their own respective
Chapter 2 hand data), `terrainstats` is itself a **dependency** consumed
by `classes`: `ClassesTableSchema.dependencies()` now includes
`terrainstats`, and `ClassesTableSchema.validate()` cross-checks every
`ClassData` record's `terrainAvoid`/`terrainDefense`/
`terrainResistance` symbol reference against the authored
`terrainstats` records' own `field` metadata (see "## `classes` schema"
above for the full write-up) -- the reverse direction of `eventlists`
depending on `units`/`shops`/`traps`/`eventscripts`.

**Modern (`modern.mk`).** Same reasoning as the `units`/`traps`/`shops`/
`eventlists` synthetic slots -- modern links whole objects, not
per-input-section, and this object is additive (no "original hand path"
to reuse), so it is reinstated at a synthetic slot path
(`$(MODERN_OUTPUT_DIR)/src/data_t-terrainstats.o`) chosen to sort
immediately before `src/data_terrains.o` (same `"-"` < any alnum trick
as the units/traps/shops/eventlists slots above) and therefore doesn't
shift any other object's relative order.

**Verification performed for this batch:**

* `generated-data-check --table terrainstats` -- zero drift against the
  (guard-preserved) hand blocks' source text (8 records).
* `generated-data-terrainstats-link-check` (new `generated_data.mk`
  target, mirroring `generated-data-ch2-traps-link-check`'s rigor for
  this two-non-adjacent-block migration): guard present exactly twice,
  both hand blocks preserved verbatim, both `CONST_DATA` redirects
  (`.data.terrainmid`, `.data.terraintail`) present, the five-line
  `ldscript.txt` ordering and adjacency, legacy `ALL_OBJECTS` presence
  (both the generated object and the still-required
  `src/data_terrains.o`), the modern synthetic-slot adjacency, the
  generated object's exactly-one-each 8 terrain symbols each in their
  expected section, a rebuild of `src/data_terrains.o` proving it now
  defines zero of the 8 guarded terrain symbols while still defining the
  surrounding movement-cost/escape-hatch/banim arrays untouched, clean
  coverage, touched-but-unchanged-input no-op-regenerate behavior, and a
  from-scratch parallel (`-j4`) build.
* `generated-data-ch2-units-link-check`/`-ch2-traps-link-check`/
  `-ch2-shops-link-check`/`-ch2-eventlists-link-check` (Batch 3a-3d
  regressions) and `generated-data-check` (all 11 tables) all still
  pass unchanged.
* `python3 -m unittest discover -s scripts/generated_data/tests` -- all
  424 tests pass, including 22 new `terrainstats`-specific tests and 2
  new `classes`-cross-validation tests
  (`ClassesTerrainstatsDependencyTests` in `test_classes_schema.py`).
* A full legacy rebuild (`make fireemblem8.gba`) is byte-identical
  (`cmp`, zero differing bytes; MD5 match) to a saved pre-change
  baseline ROM.
* `make shiftcheck` (build/static/offsets/diff layers) passes with no
  high-confidence hardcoded-pointer findings.
* Both modern configs (`MODERN_CONFIG=debug` and `MODERN_CONFIG=release`)
  pass the full `expansion-modern-linker-check` (budget, overlay-audit,
  boot-check, title-check, debugtools-check, debugtools-timer-check,
  savefmt-check, shifted-check, `scan_build_addrs.py`,
  `scan_raw_casts.sh`).

## Linking a weather-triplet movement-cost table split around one non-adjacent escape hatch (Issue #5 mechanics Batch 2: `movecost`)

`movecost` is the second global mechanics table linked via the
partial-file-splice pattern (after `terrainstats`, Batch 1 mechanics):
its 47 symbols are only a slice of `src/data_terrains.c`, which also
defines the 8 `terrainstats` arrays (already linked), the 2
`Unk_TerrainTable_1`/`Unk_TerrainTable_2` escape-hatch arrays, and every
`BanimTerrainGround_*`/`gBanimBGLut*` graphics table -- all of which
must stay hand-linked untouched.

**Two groups, split by one interior escape hatch.** Unlike `terrainstats`
(two *separate* escape hatches sitting between its two groups),
`movecost`'s 47 arrays are the **literal first content of the file**:
all 15 profiles' Normal variants, then `TerrainTable_MovCost_DemonKing`,
then `TerrainMoveCost_Ballista`, then all 15 profiles' Rain variants (32
arrays total, contiguous from file start) -- then `Unk_TerrainTable_1`
(one hand-owned escape hatch) -- then all 15 profiles' Snow variants (15
arrays, contiguous) -- then `Unk_TerrainTable_2` (a second hand-owned
escape hatch, immediately preceding `terrainstats`' own already-linked
guard). `src/data_terrains.c` wraps each of the two movecost groups in
its own `#if !GUARD` / `#endif` region, sharing one guard macro
(`GENERATED_DATA_MOVECOST_LINKED`, defined once, at the very top of the
file, before the first array):

```c
#define GENERATED_DATA_MOVECOST_LINKED 1

#if !GENERATED_DATA_MOVECOST_LINKED
CONST_DATA s8 TerrainTable_MovCost_CommonT2Normal[TERRAIN_COUNT] = {
    ...
};
... /* all 15 named profiles' normal array, then DemonKing, then Ballista, then all 15 named profiles' rain array */
#endif /* !GENERATED_DATA_MOVECOST_LINKED */

CONST_DATA s8 Unk_TerrainTable_1[TERRAIN_COUNT] = { ... }; /* untouched */

#undef CONST_DATA
#define CONST_DATA SECTION(".data.movecostsnow")

#if !GENERATED_DATA_MOVECOST_LINKED
CONST_DATA s8 TerrainTable_MovCost_CommonT2Snow[TERRAIN_COUNT] = {
    ...
};
... /* all 15 named profiles' snow array */
#endif /* !GENERATED_DATA_MOVECOST_LINKED */

#undef CONST_DATA
#define CONST_DATA SECTION(".data.movecosttail")

CONST_DATA s8 Unk_TerrainTable_2[TERRAIN_COUNT] = { ... }; /* untouched */

/* terrainstats' own pre-existing guard/redirect logic continues unchanged from here */
```

Both guarded blocks are left in place, verbatim -- never hand-edit
either one, edit `src/data/movecost.json` and regenerate instead.
`Unk_TerrainTable_1` sits, untouched, in the plain default `.data`
section (unchanged from before this batch); `Unk_TerrainTable_2` is
redirected to a **new**, uniquely-named `.data.movecosttail` section --
not reverted to plain `.data` -- because a single named
`(object_file, section_name)` pair can only be referenced once in
`ldscript.txt`: `.data` is already claimed (once) by the very first
splice line above (which now resolves to `Unk_TerrainTable_1` only,
since the 32 arrays originally preceding it in that section are
excluded), so `Unk_TerrainTable_2` needs its own distinct section name
to be placed at its own, independent point later in the file. This
choice is zero-cost (the section is a linker-only bookkeeping label, not
a runtime construct) and self-contained per table, matching the
`terrainstats`/`traps` precedent of never reusing a hand block's section
tag across two different splice points.

**Per-symbol sectioning for the Snow group, structurally like
`terrainstats`' heal arrays.** Since a single input section is placed by
the linker as one atomic unit, and the 32 Normal/DemonKing/Ballista/Rain
arrays must land at the file's original entry point while the 15 Snow
arrays must land immediately after `Unk_TerrainTable_1` (a much later
address), splicing in one generated object with all 47 symbols in the
*same* default section would force one group to jump far from its
original address. Instead, `scripts/generated_data/movecost/generate.py`
places the 32 Normal/DemonKing/Ballista/Rain arrays in the ordinary
`CONST_DATA` (`.data`) section and the 15 Snow arrays alone into a
dedicated `SECTION(".data.movecostsnow")`, so the *same* generated
object (`build/generated/data/data_movecost.c`/`.o`) can be spliced into
`ldscript.txt` at two independent points.

**No `ALIGN(4)` at the internal seams, same reasoning as `terrainstats`.**
All the movecost/terrainstats/`Unk_TerrainTable_N` arrays in
`src/data_terrains.c` are flat `s8[TERRAIN_COUNT]` arrays packed by the
compiler with zero alignment padding between adjacent arrays. Following
the `terrainstats` precedent, `. = ALIGN(4);` is kept only on the very
first line of the whole cluster (the file's original entry point) and
dropped entirely from the three internal seams within the movecost
splice and the seam between the movecost and terrainstats splices, so
the originally-single, compiler-packed byte stream is re-spliced across
objects with zero extra bytes anywhere.

**Legacy (`ldscript.txt`).** Four lines, immediately before the existing
`terrainstats` splice, in place of the original single
`src/data_terrains.o(.data)` line:

```
. = ALIGN(4); build/generated/data/data_movecost.o(.data);
src/data_terrains.o(.data);
build/generated/data/data_movecost.o(.data.movecostsnow);
src/data_terrains.o(.data.movecosttail);
build/generated/data/data_terrainstats.o(.data);
src/data_terrains.o(.data.terrainmid);
build/generated/data/data_terrainstats.o(.data.terrainheal);
src/data_terrains.o(.data.terraintail);
```

The generated 32 Normal/DemonKing/Ballista/Rain arrays land at the
original file-start address; `src/data_terrains.o(.data)` (now just
`Unk_TerrainTable_1`) resumes immediately after, at its own original
address; the generated 15 Snow arrays land next, at the exact original
address; `src/data_terrains.o(.data.movecosttail)` (now just
`Unk_TerrainTable_2`, unchanged content/address) resumes immediately
after that -- and `terrainstats`' own splice continues, unchanged,
immediately from there. `terrainstats`' own link-check (and its
`ldscript.txt` explanatory comment) were updated in lockstep: its
"prefix piece" is now `src/data_terrains.o(.data.movecosttail)` (Unk_2),
not the old bare `src/data_terrains.o(.data)`, since the movecost splice
above it absorbed both the original `.data` symbol reference and the
`ALIGN(4)` prefix. Verified via `cmp`/`md5sum` against the saved
pre-change baseline ROM: byte-identical (zero differing bytes; MD5
match).

**Cross-table consumer, unique to `movecost` (alongside `terrainstats`).**
Like `terrainstats`, `movecost` is itself a **dependency** consumed by
`classes`: `ClassesTableSchema.dependency_tables()` now returns
`("terrainstats", "movecost")`, and `ClassesTableSchema.validate()`
cross-checks every non-null `ClassData.movCostTable` triplet entry
against the authored `movecost` records (see "### `classes`
cross-validation against `movecost`" above for the full write-up).
`reservedTerrainTable` remains a plain `CSymbolRefField` escape hatch,
untouched by this batch.

**Modern (`modern.mk`).** Same reasoning as the `terrainstats` synthetic
slot -- modern links whole objects, not per-input-section, and this
object is additive, so it is reinstated at a synthetic slot path
(`$(MODERN_OUTPUT_DIR)/src/data_t-movecost.o`). Unlike every prior
synthetic slot (each checked only for adjacency to
`src/data_terrains.o`), `data_t-movecost.o`'s lexical sort position
required extra care: both `data_t-movecost.o` and
`data_t-terrainstats.o` share the `data_t-` prefix, and `'m' < 't'`
means `data_t-movecost.o` sorts *before* `data_t-terrainstats.o` in
`MODERN_ALL_C_OBJECTS`, forming a **three-in-a-row cluster**
(`data_t-movecost.o`, `data_t-terrainstats.o`, `src/data_terrains.o`),
not a simple two-entry adjacency. The
`generated-data-movecost-link-check` target's modern-adjacency assertion
checks all three positions are consecutive (verified empirically via
`printf '%s\n' ... | sort` before finalizing the check logic), not just
a pair.

**Verification performed for this batch:**

* `generated-data-check --table movecost` -- zero drift against the
  (guard-preserved) hand blocks' source text (17 profile records, 47
  arrays).
* `generated-data-movecost-link-check` (new `generated_data.mk` target,
  mirroring `generated-data-terrainstats-link-check`'s rigor): guard
  present exactly twice, both hand blocks preserved verbatim, both
  `CONST_DATA` redirects (`.data.movecostsnow`, `.data.movecosttail`)
  present, the four-line `ldscript.txt` ordering and adjacency, legacy
  `ALL_OBJECTS` presence, the three-entry modern synthetic-slot
  adjacency (`data_t-movecost.o`/`data_t-terrainstats.o`/
  `src/data_terrains.o`), the generated object's exactly-one-each 47
  movecost symbols each in their expected section, a rebuild of
  `src/data_terrains.o` proving it now defines zero of the 47 guarded
  movecost symbols while still defining the surrounding
  escape-hatch/banim arrays untouched, clean coverage,
  touched-but-unchanged-input no-op-regenerate behavior, and a
  from-scratch parallel (`-j4`) build.
* `generated-data-terrainstats-link-check` was updated (its own prefix
  assertion and one "other unrelated symbol" check both referenced
  content that moved into the new movecost splice) and re-verified
  passing, alongside `generated-data-ch2-units-link-check`/
  `-ch2-traps-link-check`/`-ch2-shops-link-check`/
  `-ch2-eventlists-link-check` (Batch 3a-3d regressions),
  `generated-data-link-check` (the global linked-tables gate), and
  `generated-data-check`/`generated-data-ch2-check` (all 12 registered
  tables) -- all still pass unchanged.
* `python3 -m unittest discover -s scripts/generated_data/tests` -- all
  461 tests pass, including 18 new `movecost`-specific tests
  (schema/generate/roundtrip) and 6 new `classes`-cross-validation tests
  (`ClassesMovecostDependencyTests` in `test_classes_schema.py`).
* A full legacy rebuild (`make fireemblem8.gba`) is byte-identical
  (`cmp`/`md5sum`, zero differing bytes) to a saved pre-change baseline
  ROM.
* `make shiftcheck` (build/static/offsets/diff layers) passes with no
  high-confidence hardcoded-pointer findings.
* Both modern configs (`MODERN_CONFIG=debug` and `MODERN_CONFIG=release`)
  build the full modern object cohort, link, produce a valid ROM header,
  and pass `expansion-modern-boot-check`; `expansion-modern-linker-check`
  passes.

## Linking a single-block global weapon-triangle rule table (Issue #5 mechanics Batch 3: `weapontriangle`)

`weapontriangle` is the third global mechanics table linked via the
guarded-block pattern (after `terrainstats`/`movecost`), but the
simplest structurally: unlike those two (partial-file splices around
non-adjacent hand-owned escape hatches shared with graphics/other
mechanics data), `sWeaponTriangleRules[]` is the **literal first
content** of `src/bmbattle.c`'s `.data` section, in a file that is
otherwise entirely procedural battle-logic code with no other
authored data table and no escape hatches to preserve around it.

**Shared struct declaration, not a private type.** `struct
WeaponTriangleRule` previously lived as a private type inside
`src/bmbattle.c`. It now lives in `include/bmbattle.h` instead, so both
the guarded hand block (still in `src/bmbattle.c`, preserved verbatim
for the round-trip parser) and the canonically-generated
`build/generated/data/data_weapontriangle.c` object can reference the
exact same layout without redefining it:

```c
/* include/bmbattle.h */
struct WeaponTriangleRule {
    s8 attackerWeaponType;
    s8 defenderWeaponType;
    s8 hitBonus;
    s8 atkBonus;
};
```

This is the minimal shared-declaration placement the task calls for:
the type moves to the header (already included by both consumers),
nothing is redeclared inside the guard, and no other struct/function in
`bmbattle.h` is touched.

**Single guard, single splice -- the simplest shape yet.** `src/bmbattle.c`
wraps the hand-written array in one `#if !GUARD` / `#else` / `#endif`
block; the `#else` arm supplies a bare `extern` declaration so
`BattleApplyWeaponTriangleEffect` (which follows, unguarded, later in
the same file) keeps compiling and referencing the same symbol/type
whether the guard is on or off:

```c
#define GENERATED_DATA_WEAPONTRIANGLE_LINKED 1

#if !GENERATED_DATA_WEAPONTRIANGLE_LINKED
static CONST_DATA struct WeaponTriangleRule sWeaponTriangleRules[] = {
    { ITYPE_SWORD, ITYPE_LANCE, -15, -1 },
    ... /* all 12 rules, verbatim */
    { -1 },
};
#else
/* The generated object above supplies the definition; this file only
 * needs the declaration so BattleApplyWeaponTriangleEffect below keeps
 * compiling and referencing the same symbol/type unchanged. */
extern struct WeaponTriangleRule sWeaponTriangleRules[];
#endif /* !GENERATED_DATA_WEAPONTRIANGLE_LINKED */

/* Since sWeaponTriangleRules is the literal first content of this file's
 * .data section, everything from here onward (sProcScr_BattleAnimSimpleLock
 * is currently the only other .data symbol in this file) is redirected
 * into its own section so the generated object above can be spliced in
 * at sWeaponTriangleRules' exact original address with zero shift. */
#undef CONST_DATA
#define CONST_DATA SECTION(".data.bmbattletail")

static CONST_DATA struct ProcCmd sProcScr_BattleAnimSimpleLock[] = { ... };
```

The guard only wraps the hand table's struct/array definition (never
`BattleApplyWeaponTriangleEffect`/`BattleApplyReaverEffect` or any other
procedural code in the file) -- exactly the "guard only struct/table
hand block, preserve text for round-trip" requirement: the `#if
!GENERATED_DATA_WEAPONTRIANGLE_LINKED` block is left in place, verbatim,
so `weapontriangle/parser.py`'s round-trip checker keeps reading and
proving it byte-for-byte identical in meaning to the generated table.

**Legacy (`ldscript.txt`).** Two lines, in place of the original single
`src/bmbattle.o(.data);` line:

```
. = ALIGN(4); build/generated/data/data_weapontriangle.o(.data);
src/bmbattle.o(.data.bmbattletail);
```

The generated object lands at `sWeaponTriangleRules`' exact original
address (the file's own `.data` start); `src/bmbattle.o(.data.bmbattletail)`
(`sProcScr_BattleAnimSimpleLock` onward) resumes immediately after, at
its own original address, with no `ALIGN(4)` needed at that internal
seam (the two arrays are compiler-packed with zero padding between
them in the original single-object layout).

**Legacy `ALL_OBJECTS`.** `$(GENERATED_DATA_WEAPONTRIANGLE_OBJECT)` is
appended once; `src/bmbattle.o` remains present exactly once too (it
still defines `sProcScr_BattleAnimSimpleLock` and every procedural
function in the file -- only `sWeaponTriangleRules` itself moved out).

**Modern (`modern.mk`).** Same synthetic-slot reasoning as
`terrainstats`/`movecost` -- modern links whole objects, not
per-input-section, and this object is additive, so it is reinstated at
a synthetic slot path chosen to sort immediately before
`src/bmbattle.o` in `MODERN_ALL_C_OBJECTS`:
`$(MODERN_OUTPUT_DIR)/src/bmb-weapontriangle.o` (`"bmb-"` sorts ahead
of any alphanumeric continuation, and `src/bmb*.o` has exactly one
other member, `src/bmbattle.o`, so this is a simple two-entry adjacency
check, not a three-in-a-row cluster like `movecost`'s).

**Verification performed for this batch:**

* `generated-data-check --table weapontriangle` -- zero drift against
  the (guard-preserved) hand block's source text (12 rules).
* `generated-data-weapontriangle-link-check` (new `generated_data.mk`
  target, mirroring `terrainstats`/`movecost`'s rigor): guard present
  exactly once, hand block preserved verbatim, shared struct type
  present in `include/bmbattle.h`; the two-line `ldscript.txt` ordering
  (generated object, then `src/bmbattle.o(.data.bmbattletail)`); legacy
  `ALL_OBJECTS` presence of both the generated object and (still
  required) `src/bmbattle.o`; the modern synthetic-slot adjacency
  (`src/bmb-weapontriangle.o` immediately before `src/bmbattle.o`); the
  generated object's exactly-one definition of `sWeaponTriangleRules`;
  a rebuild of `src/bmbattle.o` proving it now defines zero copies of
  `sWeaponTriangleRules` while still defining
  `sProcScr_BattleAnimSimpleLock` untouched; clean coverage;
  touched-but-unchanged-input no-op-regenerate behavior; and a
  from-scratch parallel (`-j4`) build.
* `generated-data-terrainstats-link-check`/`-movecost-link-check` and
  every Chapter-2-owned regression (`-ch2-units-link-check`/
  `-ch2-traps-link-check`/`-ch2-shops-link-check`/
  `-ch2-eventlists-link-check`), `generated-data-link-check` (the
  global linked-tables gate), and `generated-data-check` (all 13
  registered tables) -- all still pass unchanged.
* `python3 -m unittest discover -s scripts/generated_data/tests` -- all
  489 tests pass, including 28 new `weapontriangle`-specific tests
  (schema/generate/roundtrip).
* A full legacy rebuild (`make fireemblem8.gba`) was verified
  byte-identical to an isolated before/after comparison (the
  weapontriangle link flipped on vs. off, with every other concurrent
  change in the tree held constant): `cmp`/`md5sum` match exactly,
  proving zero ROM byte shift from this batch in isolation. The raw
  `sWeaponTriangleRules` symbol address and its 52-byte (`13 * 4`,
  including the `{ -1 }` terminator) content were also decoded directly
  from the final ROM and confirmed to match `src/data/weapontriangle.json`
  exactly, record for record.
* `make shiftcheck` (build/static/offsets/diff layers) passes with no
  high-confidence hardcoded-pointer findings; `data_weapontriangle.o`
  does not appear in any flagged object list.
* Both modern configs (`MODERN_CONFIG=debug` and `MODERN_CONFIG=release`)
  build the full modern object cohort, link, produce a valid ROM header,
  and pass `expansion-modern-boot-check`.

## Issue #5 completion boundary and status

GitHub issue #5 is still **OPEN** (this repository does not close it),
but every clause of the issue's own scope checklist and acceptance
criteria now has code + tests + docs evidence -- mapped claim-by-claim
in `reports/generated_data_issue5_closure.md`. Contributors add or
modify any supported input type via the walkthrough in
`docs/generated_data_tutorial.md`; the discoverable registry of every
registered table + record count + capacity + dependency order lives in
`reports/generated_data_manifest.md` (and, for C tooling, the generated
`build/generated/data/generated_data_manifest.h`). The rest of this
section is the honest boundary: what is **done** vs. the **legitimate
non-goals** deliberately left out of this vertical-slice sprint.

**Done (evidence in the closure report):** deterministic schema/
generation/round-trip pipeline; the 13 registered tables (global +
Chapter 2 slice + clean mechanics); typed C output; the aggregate
symbolic count/registry/dependency surfaces; duplicate-ID/missing-
reference/range/capacity/asset-text/record-budget diagnostics with
`file:line:column` locations; typed C escape hatches; the contributor
tutorial; and CI drift/test gates (`make generated-data-check`,
`make generated-data-test`).

**Legitimate non-goals (explicitly out of scope, not silently dropped):**

Batch A + Batch B + Batch C together are scoped to the Chapter 2
vertical slice's pure-data tables, its event-list/manifest composition
layer, and now (Batch C) proving that whole slice is internally coherent
as one bundle against the chapter-settings row that actually selects it
at runtime -- but this still does **not** close Issue #5. Batch C closes
the gap Batch A/B left open -- `src/data/ch2_bundle.json` (`chapterbundle`
table, this doc's `## chapterbundle schema` section) now proves the
`chapter_settings.json`/`gChapterDataAssetTable` wiring, every
`units`/`shops`/`traps`/`eventscripts` record's reachability, required
support-owner existence/reciprocity, and the referenced character/class/
item dependency sets are all internally consistent as a single bundle,
CI-gated via `generated-data-check` (now wired into
`.github/workflows/build.yml`). The following remain **out of scope**
as deliberate non-goals of this sprint:

* **Global character authoring/generation/linking.** `items` and
  `classes` (Issue #5 Batch 1) are global tables with their own schema/
  generate/round-trip pipelines. `characters` (Issue #5 Batch 2a + 2b,
  this doc's `## characters schema` section) has full parity with them:
  the 256-slot symbolic/raw designator model, full field/range/reference
  validation, cross-table checks against `classes`/`supports` (Batch
  2a), plus a real, committed `src/data/characters.json` authoring all
  256 vanilla records (`fullCoverage: true`), `generate.py`/`parser.py`/
  `inventory.py`, a clean **256/256** round trip against
  `src/data_characters.c`, and an entry in `generated_data.mk`'s
  `GENERATED_DATA_TABLES`/CI (Batch 2b). `characters` is now also
  **linked** in place of `src/data_characters.c` (Issue #5 **Batch
  2c-4**, see "Linking a generated table in place of its hand-written
  counterpart" above) -- `gCharacterData` is the single generated top-
  level symbol, exactly like `gClassData`/`gItemData`. `chapterbundle`
  still only *references* `CHARACTER_*`/`CLASS_*` IDs (as a
  reference-only dependency set, cross-checked for existence against the
  live enum headers) -- it does not fold `characters`/`classes` into its
  own cross-table reachability checks; that remains open scope, not
  part of Batch 2c-4.
* **Linking the global tables.** `classes`, `items`, `supports`, and now
  `characters` are all linked (Issue #5 Batch 2c-1 + 2c-2 + 2c-3 +
  2c-4 -- see "Linking a generated table in place of its hand-written
  counterpart" above): `build/generated/data/data_classes.c`/
  `data_items.c`/`data_supports.c`/`data_characters.c` each
  compile/assemble through the real agbcc pipeline and are linked in
  place of `src/data_classes.c`/`src/data_items.c`/`src/data_supports.c`/
  `src/data_characters.c` in both the legacy ROM build and the modern
  object cohort, with zero ROM/ELF address shift. Folding `items`/
  `classes`/`characters` into `chapterbundle`-style cross-table
  reachability checks remains open scope for a future batch, if ever
  appropriate for a global table.
* **Linking the Chapter-2-owned tables.** `units` (`UnitDefinition`/
  `REDA`, Issue #5 **Batch 3a** -- see "Linking a Chapter-2-owned
  partial-file table" above), `traps` (Issue #5 **Batch 3b** -- see
  "Linking two non-adjacent Chapter-2-owned symbols in one partial-file
  table" above), `shops` (Issue #5 **Batch 3c** -- see "Linking a
  single Chapter-2-owned interior symbol in a shared shop-list file"
  above), and `eventlists` (Issue #5 **Batch 3d** -- see "Linking a
  Chapter-2-owned table with header-only content" above) are now all
  linked in place of their respective slices of `src/events_udefs.c`,
  `src/events_trapdata.c`, `src/events_shoplist.c`, and
  `src/events_info.c` (the last via a guarded `#include`, not a guarded
  inline block, since Chapter 2's event-list composition lives entirely
  in its own header, `src/events/ch2-eventinfo.h`), with zero ROM/ELF
  address shift in the legacy build. Every Chapter-2-owned table
  `eventlists`' own schema tracks (`units`/`shops`/`traps`) is now
  linked; `eventscripts` (the underlying `EventScr_Ch2_*` script bodies
  themselves, as opposed to the list/manifest composition that
  references them by symbol) remains hand-owned and unlinked, and is
  explicitly out of scope here.
* **Mechanics** (combat/growth/AI/etc. formulas and their own data
  tables) is now **partially** started: `terrainstats` (Issue #5
  **Batch 1 mechanics** -- see "## `terrainstats` schema" and "Linking
  two non-adjacent groups of terrain combat/heal stat arrays in one
  partial-file table" above) authors and canonically links exactly the 8
  vanilla terrain combat/heal stat arrays (`TerrainTable_Avo_Common`/
  `Def_Common`/`Res_Common`/`Avo_Fly`/`Def_Fly`/`Res_Fly`/`HealAmount`/
  `HealsStatus`) consumed by `ClassData`'s terrain-lookup pointers and by
  `src/bmmap.c`'s heal-tile logic, in place of their slice of
  `src/data_terrains.c`, with zero ROM/ELF address shift, and
  strengthens `classes/schema.py`'s cross-validation of the three
  terrain-lookup fields to check against real authored `terrainstats`
  records rather than plain header-declaration presence. `movecost`
  (Issue #5 **mechanics Batch 2** -- see "## `movecost` schema" and
  "Linking a weather-triplet movement-cost table split around one
  non-adjacent escape hatch" above) now further authors and canonically
  links all 45 named Normal/Rain/Snow mobility-profile arrays plus
  `TerrainTable_MovCost_DemonKing`/`TerrainMoveCost_Ballista` (47 arrays
  total) consumed by `ClassData`'s `movCostTable`/`pMovCostTable`
  triplet, in place of their (non-adjacent, `Unk_TerrainTable_1`-split)
  slice of `src/data_terrains.c`, with zero ROM/ELF address shift, and
  further strengthens `classes/schema.py`'s cross-validation so every
  non-null `movCostTable` triplet entry resolves against an authored
  `movecost` profile with matching normal/rain/snow slot identity. **This
  does not close Issue #5's mechanics scope, nor Issue #5 overall.**
  Explicitly still open, untouched by these batches:
  * The 2 `Unk_TerrainTable_1`/`Unk_TerrainTable_2` escape-hatch arrays
    that sit between `movecost`'s two guarded groups, and the 5
    `Unk_TerrainTable_3`..`Unk_TerrainTable_7` escape-hatch arrays that
    sit between `terrainstats`' two guarded groups, inside
    `src/data_terrains.c` -- all 7 remain fully hand-owned, unresearched,
    referenced (if at all) only via `ClassData`'s `reservedTerrainTable`
    `CSymbolRefField` escape hatch, untouched by these batches.
  * The `BanimTerrainGround_*`/`gBanimBGLut*` graphics tables in the
    same file -- pure graphics data, not combat/heal/movement mechanics,
    out of scope by construction.
  * **Weapon triangle** is now modeled, authored, and linked (Issue #5
    **mechanics Batch 3** -- see "## `weapontriangle` schema" and
    "Linking a single-block global weapon-triangle rule table" above):
    the 12 directed `sWeaponTriangleRules[]` rules (`src/bmbattle.c`)
    consumed by `BattleApplyWeaponTriangleEffect`, with zero ROM/ELF
    address shift. This closes Issue #5's remaining clean-table
    mechanics scope. `BattleApplyWeaponTriangleEffect` and
    `BattleApplyReaverEffect` themselves (the procedural hit/damage-
    bonus application and reaver-weapon inversion formulas) remain
    untouched, hand-written code -- only the table is modeled.
    Explicitly still out of scope: hit/crit/damage formulas beyond the
    triangle table itself, growth-rate application, AI decision logic,
    and every other combat/mechanics system's own procedural formulas
    and bespoke data representations -- none of these are modeled,
    authored, or linked by any schema in this repository.
* **Additional chapters.** This whole platform -- schemas, the
  `chapterbundle` composition pattern, the CLI, the Make targets, CI
  wiring -- covers Chapter 2 only (`items`/`classes`/`supports`/
  `characters`/`terrainstats`/`movecost`/`weapontriangle` are the
  exceptions, being global by nature); every other chapter's equivalent
  tables/bundle remain to be modeled from scratch.
* **Migrating this pattern to other repository data domains** beyond the
  Chapter 2 slice and the `items`/`classes`/`supports`/`characters`/
  `terrainstats`/`movecost`/`weapontriangle` global tables this Issue
  has scoped so far. Procedural combat/growth/AI formulas themselves
  (as opposed to their clean lookup tables) are explicitly out of data
  scope -- see the `weapontriangle` bullet above.
