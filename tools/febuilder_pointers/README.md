# FEBuilderGBA custom-pointer export

Regenerates `fireemblem8.custom_pointer.txt` on every `make sync-win`, so
FEBuilderGBA can be pointed at this recompiled ROM instead of a vanilla one.

Gated behind `FEBUILDER_POINTERS` (config.mk, default 1). No gameplay or
save-format impact — it only adds one `const u32[]` to the ROM.

## Why an in-ROM pointer array is needed

FEBuilderGBA's `ROMFE8U.cs` (vendored here for reference) hardcodes, for each
of ~425 named fields, a **vanilla** ROM address. For most fields that address
is not the data table itself — it's an inline **literal-pool word** inside some
vanilla function, holding the table's address, which FEBuilder dereferences.

A from-scratch recompiled ROM has no equivalent literal pool at any stable
address, so `src/febuilder_pointers.c` supplies purpose-built pointer cells:
`gFebuilderPointers[]`. Each `slot` entry *is* a pointer cell, and
`scripts/gen_custom_pointer_txt.py` writes that cell's own ROM offset into the
output file for FEBuilder to dereference exactly as it would in vanilla.

## Entry kinds

`field_order.txt` pairs each field name with its kind, in the same order as the
C array:

| kind | vanilla meaning | emitted value |
| --- | --- | --- |
| `slot` | address of a literal-pool pointer cell | ROM offset of that array entry |
| `direct` | address of the data itself | the stored address, as a ROM offset |
| `scalar` | a size/count/id constant | the stored value verbatim |

`direct` vs `slot` is disambiguated by whether the vanilla address *is itself*
exactly a data symbol (⇒ `direct`) or points at one (⇒ `slot`).

## How the mapping was derived

1. Dereference each vanilla address in `baserom.gba`.
2. Resolve the target through `reference/fe8u_symbols.txt` (a symbol dump of
   the sibling byte-matching decomp at `/mnt/c/devkitPro/decomp`) to a vanilla
   symbol **name**.
3. Confirm that same name exists in this repo (this repo shares decomp lineage,
   so names match verbatim where both have decompiled the same thing).

`mapping.json` records the resulting field→symbol/kind decisions and
`deref_analysis.json` the raw dereference results, so the pass is reproducible
and auditable.

Scalars use `sizeof()` / `offsetof()` / real `ITEM_*`/`TERRAIN_*` constants
rather than copied vanilla literals, so they track this repo's actual layout.

## Deliberately excluded

**~103 of 425 fields are omitted**, and that is the intended outcome — an
omitted field simply leaves FEBuilder on its vanilla default rather than
pointing it somewhere wrong. Categories:

- **In-function ASM patch points** (`*_switch1_address`, `*_switch2_address`,
  `weapon_rank_s_bonus_address`, …). These are byte offsets *inside* a vanilla
  function that FEBuilder pokes. This repo's recompiled functions have entirely
  different layouts, so no equivalent offset exists.
- **Targets with no symbol even in the vanilla decomp** — the dereference lands
  mid-blob or mid-function, so there is no name to carry over.
- **ROM/RAM space mismatches** — e.g. `font_default_begin`, whose vanilla target
  is ROM data but whose same-named symbol here lives in EWRAM. Emitting it would
  point FEBuilder past the end of the ROM file.
- **Vanilla-count constants that this repo may have changed** (`map_default_count`),
  where copying the vanilla literal would actively mislead.

The 8 `map_config/obj/pal/tileanime*/mapchange/event_pointer` fields are also
excluded: vanilla keeps eight separate per-category arrays, whereas this repo
consolidated them into one heterogeneous `gChapterDataAssetTable[]`, which is
not a drop-in substitute for FEBuilder's per-category indexing.

## Regenerating after adding a mapping

Edit `mapping.json`, then rerun the generator that produced
`src/febuilder_pointers.c` and `field_order.txt`. Verify with a round-trip
check: read each `slot` offset out of the built ROM, dereference it, and confirm
it lands on the intended symbol (all 322 current entries pass).
