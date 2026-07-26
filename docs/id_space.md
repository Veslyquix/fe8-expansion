# Extensible ID space (Issue #10)

This framework turns "expandable IDs" into a configurable, auditable,
fail-early platform. It is built around one single source of truth --
`scripts/generated_data/idspace.py` -- that describes every extensible ID
domain (character, class, item, chapter, unit, event) and every consumer
(runtime tables, event operands, save fields, UI buffers, lookup tables,
link/network representations, external interfaces) that must never silently
truncate an expanded ID.

## What the single source produces

Running `python3 -m scripts.generated_data.idspace generate` deterministically
renders three committed surfaces from that one description:

- `include/id_space.h` -- C89 / agbcc-safe typed aliases plus
  width/signedness/sentinel/technical-max/configured-cap macros and
  compile-time `ID_SPACE_STATIC_ASSERT` cap-fits-storage guarantees.
- `reports/id_space_audit.json` -- machine-readable consumer audit (with a
  stable sha256 digest).
- `reports/id_space_audit.md` -- the human audit, generated from the exact
  same rows so the two never disagree.

`python3 -m scripts.generated_data.idspace check` re-renders in memory and
fails on any configured-cap violation or committed-output drift. It is folded
into `make generated-data-check`, so the existing umbrella CI gate covers it
with no workflow edits.

## Per-domain caps and cost

Each domain declares a storage width, signedness, sentinel, technical maximum
(what the storage can physically hold) and a configured cap (the finite value
actually enabled today). See `reports/id_space_audit.md` for the full table
and per-domain ROM/RAM/on-media budget notes. Summary:

| Domain | Storage | Technical max | Configured cap | Status |
|---|---|---|---|---|
| character | u8 | 0xFF | 0xFF | at storage max (256-record padding) |
| class | 7-bit jid save field | 0x7F | 0x7F | frozen (0x80 truncates on save) |
| item | u8 index / 14-bit save | 0xFF | 0xCD (opt-in 0xCE..0xFF) | expandable |
| chapter | s8 | 0x7F | 0x7F | frozen (negatives reserved) |
| unit | u8, 0x40 faction stride | 0x3F | 0x3F | frozen (partition collision) |
| event | 16-bit operand lane | 0xFFFF | 0xFF | adequate headroom |

## Choosing a cap

1. Read the domain row in `reports/id_space_audit.md` for its technical max
   and the reason a frozen domain cannot grow.
2. A cap must satisfy `validate_domain_cap`: it may not exceed the technical
   max, collide with a partition stride/sentinel, or overflow a fixed record
   capacity. Invalid caps fail at generation (Python) and, where the cap is
   compiled in, at compile time via the static assertions in `include/id_space.h`.
3. Class cannot be raised past 0x7F without changing the 7-bit `jid` save
   bitfield -- that requires a save layout/epoch change and is out of scope
   here (see the closure report non-goals).

## Item expansion pilot: 0xCD -> 0xCE

The item domain is the worked, real end-to-end expansion. It is opt-in and
default-disabled so vanilla/archival output stays byte-for-byte compatible.

- Default (no override): item cap is 0xCD, the 206 vanilla records generate,
  and the generated `gItemData[]` round-trips byte-for-byte against
  `src/data_items.c`.
- Opt-in: set `FE8_ITEM_ID_CAP=0xCE` (up to 0xFF). Generation then merges the
  overlay `src/data/items_expansion.json`, the enum constant in
  `include/constants/items_expansion.h` becomes resolvable, and
  `gItemData[]` emits the `[ITEM_EXPANSION_CE]` record with
  `#include "constants/items_expansion.h"`.
- An expansion record referenced without opting in is rejected early with an
  actionable diagnostic (`... beyond the configured item cap 0xCD; raise
  FE8_ITEM_ID_CAP to opt this ID in`).

### Why 0xCE is safe with zero layout change

The item save fields are already 14-bit (`GameSavePackedUnit.item1..item5`,
mask 0x3FFF) and 16-bit (`SuspendSavePackedUnit.item1..item3`); the runtime
index is masked to 8 bits (`ITEM_INDEX`); event operand lanes are 16-bit; the
unit inventory slots are `u16`. So 0xCE (and any ID up to 0xFF) round-trips
bit-exactly through save, suspend, and multi-arena/link representations with
no serialized layout, meaning, packing, checksum, or epoch change. The only
cost of 0xCD -> 0xCE is one extra `struct ItemData` record in ROM.

## Adding a supported item record

1. Add the enum constant to `include/constants/items_expansion.h`.
2. Add the record to `src/data/items_expansion.json` (original/blank text only
   -- do not introduce copyrighted names/descriptions; author real names via
   the `texts/` pipeline as a follow-on).
3. Raise `FE8_ITEM_ID_CAP` to at least the new ID.
4. Regenerate and test (no `--no-roundtrip`: the vanilla 206-record round
   trip stays fully enforced; overlay-only IDs are verified separately):
   - `FE8_ITEM_ID_CAP=0xCE make -f generated_data.mk generated-data-check`
     (opt-in gate: validates 207 records, keeps the archival inventory/manifest
     at 206, exits 0)
   - `make -f generated_data.mk generated-data-check` (default gate stays
     vanilla-clean at 206)
   - `python3 -m unittest scripts.generated_data.tests.test_items_expansion
     scripts.generated_data.tests.test_items_roundtrip_regression`

The compiled consumer sees the same cap: `include/id_space.h` emits
`ITEM_ID_CONFIGURED_CAP` as `FE8_ITEM_ID_CAP` (default `0xCD`), the modern
build passes `-DFE8_ITEM_ID_CAP=<n>` (see `modern.mk`), and `src/bmitem.c`
includes `id_space.h` with a compile-time `ITEM_ID_CONFIGURED_CAP <=
ITEM_ID_TECHNICAL_MAX` assertion, so a stray `0x100` fails the compile.

## Runtime probe (`expansion-modern-itemexpansion-check`)

The host tests above model the ID space; this gate proves it inside a real,
booted expansion ROM. `src/expansion_itemtest.c` (opt-in, gated by
`FE8_EXPANSION_ITEMTEST_ENABLED`, default 0) sequences *production* calls and
records what they returned into `gItemExpansionProbe`; it re-implements
nothing. `tools/gba-playtest/run_item_expansion_checks.py` resolves that
symbol's address from the linked ELF, replays a scripted scenario through
libmGBA and asserts every recorded value.

```sh
FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1 \
  make expansion-modern-itemexpansion-check MODERN_CONFIG=debug MODERN_ABI=aapcs -j"$(nproc)"
FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1 \
  make expansion-modern-itemexpansion-check MODERN_CONFIG=release MODERN_ABI=aapcs -j"$(nproc)"
```

What the debug run proves, all with 0xCE and with the legacy 0xCD and the
empty (0x0000) slot unchanged beside it:

| Stage | Production path exercised | Observed |
| --- | --- | --- |
| item record | `GetItemData` / `MakeNewItem` / `GetItemIndex` / `GetItemUses` | `number=0xCE`, `weaponType=ITYPE_ITEM`, `maxUses=1`, `MakeNewItem=0x01CE` |
| event | a real `SVAL`+`GIVEITEMTO` script through `CallEvent` -> the engine's own `EV_CMD_GIVEITEM` handler -> the "got item" popup | Eirika's live inventory slot 3 holds `0x01CE`; the same script's `0xCD` item holds `0x00CD` |
| UI | `GetItemName` / `GetItemIconId` / `GetItemDescId`, `DrawItemMenuLine`, `DrawItemStatScreenLine` | name resolves to a real string; icon/name/uses tiles written into the live BG0 tilemap; both draw paths place the same icon |
| link / MultiArena | `WriteMultiArenaSaveTeam` -> `ReadMultiArenaSaveTeam` (through real SRAM) | `0x01CE` bit-exact |
| game save | `WriteGameSavePackedUnit` -> `LoadSavedUnit` | `0x01CE` bit-exact, and the packed 14-bit field itself reads back `0x01CE` |
| suspend save | `EncodeSuspendSavePackedUnit` -> `ReadSuspendSavePackedUnit` | `0x01CE` bit-exact |

The whole-block save/suspend cycle (manual Suspend through the ordinary Map
Menu, soft reset, Resume) is separately verified on the same expanded-cap ROM
by `expansion-modern-savefmt-check`, which passes at `FE8_ITEM_ID_CAP=0xCE`
for both configurations. The probe deliberately does not add a
`WriteGameSave`-class call site to `src/` (see the baseline recorded in
`tools/gba-playtest/tests/test_savesuspend_resume_scenario.py`).

### Release-configuration limitation

`MODERN_CONFIG=release` runs the same probe with `--require-stages boot`: the
running release ROM's own `GetItemData`/`MakeNewItem`/`GetItemIndex`/
`GetItemUses` are asserted to resolve `0xCE` to the expanded record with
`0xCD` unchanged, and the map-dependent stages are proven on the debug ROM.

The reason is a pre-existing property of the release configuration, not of the
ID space: a modern release ROM does not reach a battle map in this headless
harness at all. Reproduced with a *plain release ROM containing no probe code*,
driven through the ordinary New Game route with A/L/direction input for 29000
frames: the world map stays alive (`GmapCursor`, `Gmap MU prim`,
`Gmap Line Fade` procs) and `gProc_BMapMain` never starts. The repository's
own committed release scenarios likewise stop at title/save-menu depth, and
the deep Chapter 2 scenarios (`debugtools-*`, `savesuspend-resume`) are
debug-only. Investigating that release-build world-map stall is out of scope
for issue #10 and is reported as a separate finding.

### Layout note for expanded-cap ROMs

Growing `gItemData[]` moves every ROM object placed after it. The committed
deep-runtime fingerprints (`debugtools-hub`, `debugtools-map-hub`, ...) probe
absolute ROM pointers that live in EWRAM at fixed addresses, so they are
default-cap oracles by construction and are not run against a 0xCE ROM. The
layout-tolerant official gates are run at 0xCE instead (boot, title, shifted
boot/title at `MODERN_SHIFT_AMOUNT=0x40000`, save-format, budget, overlay
audit), and this probe resolves its own symbol from the ELF so it pins no
layout at all.

## Migration impact

None for the item pilot: no serialized save layout, meaning, packing,
checksum, or epoch changes. Legacy decoders keep reading old values. Widening
class/chapter/unit is deliberately NOT done here; those require a versioned
save/runtime change and a future epoch bump, documented as non-goals in
`reports/issue10_closure.md`.
