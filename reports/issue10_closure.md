# Issue #10 closure evidence: Extend IDs and engine limits safely

Candidate handoff. Every claim below was produced by running the command
shown in this worktree; nothing is inferred. Final pass/fail remains with the
independent verifier -- this report only records what has actually been
executed and observed.

Environment: `mgfembp` submodule initialized (`git submodule update --init
--recursive`), repository tools built (`./build_tools.sh`), `tools/agbcc`
present for the archival build, libmGBA playtest backend available
(`gba_playtest.py backend-check` -> "libmGBA backend: available"). All of
those are ignored/untracked build inputs; nothing of the sort is committed.

## Issue #10 checklist and acceptance criteria mapping (verbatim)

Quoted verbatim from the GitHub issue body (`gh issue view 10 --json body`)
so nothing is paraphrased away. Every row states a status, not just a
pointer -- "audited unchanged / not triggered" is used only where the
underlying mechanism was actually inspected and found not to apply to this
phase's change, and is never used as a stand-in for "not done".

### Scope checklist (7/7 addressed)

| # | Checklist item (verbatim) | Status | Evidence |
|---|---|---|---|
| 1 | "Introduce typed IDs and generated counts/registries." | **Done** | `include/id_space.h` typedefs (`ItemId`/`ClassId`/`ChapterId`/`UnitId`/...) + `*_TECHNICAL_MAX`/`*_CONFIGURED_CAP` macros, rendered from the single-source `scripts/generated_data/idspace.py`; `make generated-data-check` verifies the header and audit stay in sync with that source. |
| 2 | "Audit every event operand, save field, UI buffer, lookup table, and network/link representation." | **Done** | `reports/id_space_audit.{json,md}` enumerate every domain x consumer-class pair (runtime-macro, runtime-struct, save-field, event-operand, lookup-table, ui-buffer, link-network, external-interface) with a `runtime_evidence` column. The item domain's rows are the ones exercised live: event operand via `EV_CMD_GIVEITEM`, save field via game-save + suspend packed fields, UI buffer via menu/stat-screen tile writes, link/network via the MultiArena SRAM roundtrip -- see "Runtime evidence" below. |
| 3 | "Define explicit configurable caps constrained by GBA memory and data formats." | **Done** | `idspace.py`'s `validate_domain_cap` + per-domain technical max/configured cap in `include/id_space.h`; item cap raised to `0xCE`, validated against the `ItemId` u8 storage type and the `0xFF` sentinel/`0x100` wrap boundary. |
| 4 | "Extend event encodings only through versioned/audited mechanisms." | **Audited unchanged, not triggered this phase** | Item IDs already travel the existing 16-bit event-operand lane (`docs/id_space.md` line 43: `event \| 16-bit operand lane \| 0xFFFF \| 0xFF`). Raising the item cap to `0xCE` stays inside that lane's existing width, so no operand encoding change was required or made -- confirmed live: the runtime probe's `eventItem = 0x01CE` comes back through the engine's unmodified `EV_CMD_GIVEITEM` decoder. This is **not** a substitute for "done": no new versioned event-encoding mechanism was built. A domain whose raised cap does *not* fit its current operand encoding (i.e. widening the encoding itself) is genuinely unimplemented; that is why class/chapter/unit widening is deferred (see "Explicit non-goals" and acceptance criterion 1 below), not silently folded into this item's cap raise. |
| 5 | "Add save migrations for widened serialized identifiers." | **Audited unchanged, not triggered this phase** | The item cap raise (`0xCD` -> `0xCE`) changes zero serialized bytes: `GameSavePackedUnit`/`SuspendSavePackedUnit` item fields are already wide enough (14/16-bit lanes, `docs/id_space.md` lines 76-78) to hold `0xCE` without any layout change, and `EXPANSION_SAVE_COMPAT_EPOCH` was left untouched (`config.mk`, verified by diff). Confirmed live: the probe's `gameSaveItem`/`suspendItem` roundtrip `0x01CE` bit-exact through the *existing* pack/unpack code, and the legacy `0x00CD` value and empty `0x0000` slot roundtrip unchanged next to it. No migration code was written because none is needed for a value that already fits its field -- this is an audited absence, not an implemented one. `ClassId`'s 7-bit `jid` save field is deliberately capped at `CLASS_ID_CONFIGURED_CAP = 0x7F` in `include/id_space.h` for exactly this reason: raising it further *would* need a real migration + `EXPANSION_SAVE_COMPAT_EPOCH` bump, and that work is not done -- called out as an explicit non-goal, never marked complete. |
| 6 | "Add compile-time and generator range/budget diagnostics." | **Done** | See "Compile-time contracts" below: `ID_SPACE_STATIC_ASSERT` failures when a cap exceeds its storage type or technical max; `manifest.py` budget diagnostics; a malformed `FE8_ITEM_ID_CAP` fails at `make` parse time with `$(error ...)`. |
| 7 | "Cover legacy decoder behavior and boundary values." | **Done** | `scripts/generated_data/tests/test_idspace.py` + `test_items_expansion.py` cover host-side boundaries `0`/`0xCD`/`0xCE`/`0xFF`/`0x100`; the runtime probe covers `0xCD` (legacy) and `0x0000` (empty slot) side by side with `0xCE` in every one of its six stages, in a real booted ROM. |

### Acceptance criteria (4/4 addressed)

| # | Acceptance criterion (verbatim) | Status | Evidence |
|---|---|---|---|
| 1 | "Expanded IDs cannot silently truncate in events, saves, UI, or runtime tables." | **Done for the item domain exercised** | Runtime probe asserts `0xCE` bit-exact through `GetItemData`, `EV_CMD_GIVEITEM`, item menu/stat UI tile writes, MultiArena SRAM, and both game-save and suspend packed fields (table in "Runtime evidence" below). `ID_SPACE_STATIC_ASSERT`s reject any cap that would not fit its storage type at compile time, so a domain cannot be silently misconfigured to truncate. Domains not widened this phase (class/chapter/unit) are unchanged, not silently truncating, and explicitly flagged as out of scope (checklist items 4-5 above). |
| 2 | "Unsupported limits fail at generation or compile time." | **Done** | `-DFE8_ITEM_ID_CAP=0x100` fails compilation (static-assert diagnostics below); a malformed `FE8_ITEM_ID_CAP` fails `make` parsing; `idspace.py`'s `validate_domain_cap` fails generation for an out-of-range cap. |
| 3 | "Memory and ROM costs are reported for each configured cap." | **Done** | `manifest.py` budget diagnostics report per-table byte cost; the linked-ELF `gItemData` size via `nm -S` is recorded fresh below for both configurations at both the default cap (206 records, `0x1cf8` = 7416 bytes) and `0xCE` (207 records, `0x1d1c` = 7452 bytes) -- the one new record costs exactly 36 bytes (`sizeof(ItemData)`), reported not assumed. |
| 4 | "Boundary, serialization, and migration tests gate CI." | **Fixed in this phase (previously an orphan gate)** | Before this fix, `expansion-modern-itemexpansion-check` -- the only gate that runs the boundary+serialization runtime probe -- was defined in `modern.mk` but never invoked by `.github/workflows/build.yml` or by `expansion-modern-linker-check`; an independent review confirmed CI never actually ran it, so this criterion was unmet despite the probe existing and passing locally. `.github/workflows/build.yml` now runs it for both `debug` and `release` at `FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1`, additively, immediately after the existing linker-check step, with no existing step modified, reordered, or removed -- see "CI wiring" below for the local-equivalent evidence that the cap flip is not served stale. Migration tests specifically: none exist yet because no migration is needed for this phase's change (checklist item 5); this is flagged as a real, open gap for whichever future phase adds a genuine migration, not silently closed here. |


## Runtime evidence in a real ROM (the core of this phase)

Gate: `expansion-modern-itemexpansion-check` (modern.mk) ->
`tools/gba-playtest/run_item_expansion_checks.py`. The probe
(`src/expansion_itemtest.c`, opt-in `FE8_EXPANSION_ITEMTEST_ENABLED`, default
0) only *sequences production calls and records their results*; the runner
resolves `gItemExpansionProbe` from the linked ELF (no hardcoded address, no
committed frame oracle) and asserts every value.

```
FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1 make expansion-modern-itemexpansion-check MODERN_CONFIG=debug   MODERN_ABI=aapcs -j16
FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1 make expansion-modern-itemexpansion-check MODERN_CONFIG=release MODERN_ABI=aapcs -j16
```

Debug (all stages) -> PASS. Observed, in the running ROM:

| Field | Value | Production path |
|---|---|---|
| `magic` / `stagesCompleted` | `0x49584345` / `0x3F` | all six stages completed |
| `dataNumber` / `dataWeaponType` / `dataMaxUses` | `0xCE` / `0x09` / `1` | `GetItemData(ITEM_EXPANSION_CE)` |
| `madeItem` / `lookupIndex` / `lookupUses` | `0x01CE` / `0xCE` / `1` | `MakeNewItem`, `GetItemIndex`, `GetItemUses` |
| `legacyDataNumber` | `0xCD` | `GetItemData(ITEM_UNK_CD)` unchanged |
| `eventUnitPid` / `eventItemSlot` / `eventItem` | `0x01` / `3` / `0x01CE` | real `SVAL`+`GIVEITEMTO` script -> `CallEvent` -> `EV_CMD_GIVEITEM` handler -> "got item" popup -> Eirika's live inventory |
| `eventLegacyItem` | `0x00CD` | same script, legacy boundary value, same decoder |
| `uiNamePtr` / `uiIconId` / `uiDescId` | real string ptr / `0` / `0` | `GetItemName`, `GetItemIconId`, `GetItemDescId` |
| `uiMenuIconTile` / `uiMenuNameTile` / `uiMenuUsesTile` | `0x42FC` / `0x0080` / `0x0098` | `DrawItemMenuLine` into the live BG0 tilemap |
| `uiStatIconTile` / `uiStatSlashTile` | `0x42FC` / `0x00AE` | `DrawItemStatScreenLine` |
| `arenaItem` / `arenaLegacyItem` / `arenaEmptySlot` | `0x01CE` / `0x00CD` / `0x0000` | `WriteMultiArenaSaveTeam` -> `ReadMultiArenaSaveTeam` through real SRAM |
| `gameSaveItem` / `gameSavePackedField` | `0x01CE` / `0x01CE` | `WriteGameSavePackedUnit` -> `LoadSavedUnit` (14-bit on-media field) |
| `suspendItem` / `suspendPackedField` | `0x01CE` / `0x01CE` | `EncodeSuspendSavePackedUnit` -> `ReadSuspendSavePackedUnit` |
| `gameSaveLegacyItem` / `suspendLegacyItem` | `0x00CD` / `0x00CD` | legacy value unchanged by both roundtrips |
| `gameSaveEmptySlot` / `suspendEmptySlot` | `0x0000` / `0x0000` | empty slot stays `ITEM_NONE` |

Release -> PASS with `--require-stages boot`: the running release ROM's own
`GetItemData`/`MakeNewItem`/`GetItemIndex`/`GetItemUses` resolve `0xCE`
(`configuredCap=0xCE`, `dataNumber=0xCE`, `madeItem=0x01CE`,
`lookupIndex=0xCE`, `legacyDataNumber=0xCD`).

**Release limitation, reproduced and root-caused as pre-existing.** A modern
release ROM does not reach a battle map in this headless harness. Control
experiment with a **plain release ROM containing no probe code at all**,
driven through the ordinary New Game route with A/L/direction input to frame
29000: live procs stay `GAMECTRL`, `GmapCursor`, `Gmap MU prim`,
`Gmap Line Fade`; `gProc_BMapMain` never starts. The repository's own deep
Chapter 2 scenarios (`debugtools-*`, `savesuspend-resume`) are debug-only for
the same reason. This is unrelated to the ID space and is reported as a
separate finding, not worked around inside issue #10.

The whole-block save/suspend cycle *is* covered on the expanded-cap ROM by
`expansion-modern-savefmt-check` (ordinary-UI manual Suspend -> soft reset ->
Resume, plus all 8 `SaveCompatState` values), which passes at
`FE8_ITEM_ID_CAP=0xCE` for both configurations -- see below.

## Full modern ELF/ROM at cap 0xCE

`FE8_ITEM_ID_CAP=0xCE make expansion-modern-boot-check expansion-modern-title-check expansion-modern-savefmt-check expansion-modern-budget-check expansion-modern-overlay-audit expansion-modern-shifted-check MODERN_CONFIG=<debug|release> MODERN_ABI=aapcs -j16`

Both configurations: **PASS** for every one of those gates --
`boot-check`, `title-check`, `SHIFTED BOOT/TITLE (shift=0x40000)`,
`savefmt-check` (all 8 save-compat states + host migration + Suspend/soft
reset/Resume on debug), `budget-check`, `overlay audit`.

**Why this section uses a formula, not a pinned address.** `gItemData`'s ROM
address moves whenever anything linked before it changes size -- including
the opt-in `FE8_EXPANSION_ITEMTEST_ENABLED` probe object itself. A prior
version of this report hardcoded one build's absolute record addresses;
those had already drifted (by 0x10) from a fresh rebuild by the time this
was checked, which is exactly the failure mode a hardcoded ROM address
invites. The formula below is resolved fresh from the linked ELF every time
instead of being treated as a standing contract:

```
record_addr(item_id) = nm_base_of("gItemData") + item_id * sizeof(ItemData)   # sizeof(ItemData) == 36 bytes
```

Linked-ELF proof that the expansion record is in the final image, not an
isolated object -- fresh, this run, `FE8_ITEM_ID_CAP=0xCE` with the runtime
probe **disabled** (`FE8_EXPANSION_ITEMTEST` unset), i.e. the plain
production cap-raise with no probe object linked in:

```
$ FE8_ITEM_ID_CAP=0xCE make expansion-modern-rom MODERN_CONFIG=debug MODERN_ABI=aapcs -j16
$ arm-none-eabi-nm -S build/expansion-modern/debug/aapcs/fireemblem8.elf   | grep -w gItemData
08902a48 00001d1c T gItemData          # 0x1d1c = 7452 = 207 * 36
$ FE8_ITEM_ID_CAP=0xCE make expansion-modern-rom MODERN_CONFIG=release MODERN_ABI=aapcs -j16
$ arm-none-eabi-nm -S build/expansion-modern/release/aapcs/fireemblem8.elf | grep -w gItemData
08909418 00001d1c T gItemData
```

Uniqueness check, using the correct per-config modern map (not the
legacy archival `fireemblem8.map` at repo root, which is a different,
gitignored build with `gItemData` at an unrelated address `0x0880a930` --
citing that file for the modern ELF's address was itself a mismatched-file
bug in a prior version of this report, fixed here alongside the stale
address):

```
$ grep -c gItemData build/expansion-modern/debug/aapcs/fireemblem8.map
1
```

Applying the formula to those fresh bases and reading the resulting bytes
directly out of the produced ROM images, record 0xCE is byte-exact in both
configurations:

```
debug   record 0xCD @ 0x0890471c: 0304ab040000cd0c...  number=0xCD weaponType=0x0C (unchanged vanilla record)
debug   record 0xCE @ 0x08904740: 000000000000ce09000000000000000000000000010000000000000000000000
                                  number=0xCE weaponType=0x09 (ITYPE_ITEM) maxUses=1 iconId=0
release record 0xCD @ 0x0890b0ec: 0304ab040000cd0c...  number=0xCD weaponType=0x0C (unchanged vanilla record)
release record 0xCE @ 0x0890b110: 000000000000ce09000000000000000000000000010000000000000000000000
                                  number=0xCE weaponType=0x09 (ITYPE_ITEM) maxUses=1 iconId=0
```

(For context, not as a pinned value: the `FE8_EXPANSION_ITEMTEST=1` probe
build used for the runtime-probe section above links in `src/expansion_itemtest.c`,
which is placed before `gItemData` and shifts its base further --
`0x089030c8` debug / `0x08909a88` release, confirmed the same run. The probe
never reads that address by assumption either: `run_item_expansion_checks.py`
resolves `gItemExpansionProbe`'s own address from the ELF via `nm` at check
time. Only the numbers above -- from the probe-free, cap-only build -- are
the intended "final production ROM layout" evidence for this table.)

Default cap keeps 206 records, reconfirmed fresh in both configurations at
the *same* `gItemData` base as the 0xCE builds above (only the size grows,
proving the one new record is a pure append, not a relayout):

```
$ make expansion-modern-elf MODERN_CONFIG=debug   MODERN_ABI=aapcs -j16 && arm-none-eabi-nm -S build/expansion-modern/debug/aapcs/fireemblem8.elf   | grep -w gItemData
08902a48 00001cf8 T gItemData
$ make expansion-modern-elf MODERN_CONFIG=release MODERN_ABI=aapcs -j16 && arm-none-eabi-nm -S build/expansion-modern/release/aapcs/fireemblem8.elf | grep -w gItemData
08909418 00001cf8 T gItemData
```

Flipping `FE8_ITEM_ID_CAP` with no source-file touch regenerates the table
and relinks (cap stamp) -- see "CI wiring" below for the rebuild-count proof
that this is a real recompile, not a stale reuse.

## CI wiring: closing acceptance criterion 4

`expansion-modern-itemexpansion-check` existed and passed locally (above)
but, before this fix, was never invoked by CI: `.github/workflows/build.yml`
called only `expansion-modern-linker-check` for each configuration, and
`expansion-modern-linker-check` itself does not depend on
`expansion-modern-itemexpansion-check` (checked directly in `modern.mk`: its
prerequisite list is `budget-check overlay-audit boot-check title-check
debugtools-check debugtools-timer-check debugtools-map-check
debugtools-prep-check savefmt-check shifted-check`, with no itemexpansion
entry). An independent reviewer flagged this as an orphan gate against
acceptance criterion 4 ("Boundary, serialization, and migration tests gate
CI"). Fixed additively: `.github/workflows/build.yml` gained one new step
after the existing linker-check step, calling
`FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1 make expansion-modern-itemexpansion-check MODERN_CONFIG=<debug|release> MODERN_ABI=aapcs -j2`
for both configurations. No existing step was edited, reordered, or removed
(`git diff -- .github/workflows/build.yml` is purely additive lines at
end-of-file); `actionlint` reports no findings.

**Proof the cap flip is not served stale (local equivalent of the new CI
order: default-cap linker-check, then the 0xCE item gate, same
MODERN_OUTPUT_DIR):**

```
$ make expansion-modern-linker-check MODERN_CONFIG=debug MODERN_ABI=aapcs -j16
... Modern expansion linker checks passed (config=debug abi=aapcs)
$ FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1 make expansion-modern-itemexpansion-check MODERN_CONFIG=debug MODERN_ABI=aapcs -j16
... Built 451 modern relocatable objects in build/expansion-modern/debug/aapcs
... Linked modern ELF: build/expansion-modern/debug/aapcs/fireemblem8.elf
... item-expansion runtime probe passed (config=debug): runtime item record, event GIVEITEM decoder, item UI draw, MultiArena/link, and the game-save/suspend pack+unpack all carry 0xCE bit-exact, with 0x00CD and 0x0000 unchanged
```

All 451 objects were rebuilt and the ELF relinked -- driven by
`MODERN_COMPILE_SETTINGS`, the content-addressed stamp every modern C/data
object depends on (it embeds `FE8_ITEM_ID_CAP`/`FE8_EXPANSION_ITEMTEST`), so
changing those variables between the two `make` invocations above forces a
real rebuild instead of reusing the prior default-cap ELF. The reverse
direction was also verified (cap 0xCE -> default, same output dir):

```
$ make expansion-modern-elf MODERN_CONFIG=debug MODERN_ABI=aapcs -j16   # FE8_ITEM_ID_CAP unset again
... Linked modern ELF: build/expansion-modern/debug/aapcs/fireemblem8.elf
$ arm-none-eabi-nm -S build/expansion-modern/debug/aapcs/fireemblem8.elf | grep -w gItemData
08902a48 00001cf8 T gItemData   # back to 206 records
```

Release was verified the same way: `expansion-modern-linker-check
MODERN_CONFIG=release` (default cap, PASS) followed by
`FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1 expansion-modern-itemexpansion-check
MODERN_CONFIG=release` (PASS, `--require-stages boot`, matching the
release-configuration limitation documented above).

## Default-cap and legacy compatibility

- `make expansion-modern-linker-check MODERN_CONFIG=debug MODERN_ABI=aapcs -j16`
  -> `Modern expansion linker checks passed (config=debug abi=aapcs)`.
- `make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs -j16`
  -> `Modern expansion linker checks passed (config=release abi=aapcs)`.
  These are exactly CI's two commands, and they include the deep
  `debugtools-hub`/`map`/`prep`/`timer` fingerprints, `savefmt`, `shifted`,
  budget/overlay and the build-address/raw-cast scans.
- `make fireemblem8.gba -j16` (archival agbcc build) -> ROM produced;
  `gItemData` stays `0x1cf8` (206 records) and
  `arm-none-eabi-size src/expansion_itemtest.o` -> `0 0 0` (the opt-in probe
  contributes no text/data/bss to an ordinary build).
- `python3 scripts/artifact_guard.py --revision HEAD` -> exit 0;
  `--index` with the whole candidate staged -> exit 0 (then unstaged again).
- `make generated-data-check` -> no drift, 206-record items, manifest 722
  records, `id-space contract up-to-date (3 outputs)`.
- `FE8_ITEM_ID_CAP=0xCE make generated-data-check` -> `OK: no drift for table
  'items' (207 record(s))`, manifest unchanged at 722 (archival inventory
  stays vanilla).
- `make generated-data-test` -> `Ran 544 tests ... OK`.
- `python3 -m unittest discover -s tools/gba-playtest/tests` -> `Ran 184
  tests ... OK` (against default-cap ROMs; this suite reads the ROMs in
  `build/expansion-modern/`, so it must be run with default-cap builds
  present).
- `python3 -m unittest discover -s scripts/modernize/tests` -> `Ran 358 tests
  ... OK`.

### Default-cap layout regression found and fixed in this phase

The previous candidate's `src/bmitem.c` change re-masked the lookup index
inside the inline `GetItemData` (`ItemId index = (ItemId) itemIndex;`). That
changed emitted code and shifted ROM data by 0x10, which broke the committed
`debugtools-hub` fingerprint **at the default cap**
(`expected '0x088fc5f8', actual '0x088fc608'`). Verified by reverting only
that file to `HEAD` (gate passed) and then keeping the fix. The typed contract
is now expressed where it costs nothing: `src/bmitem.c` keeps
`#include "id_space.h"` and three live `ID_SPACE_STATIC_ASSERT`s
(configured cap fits storage, `sizeof(ItemId) == 1`, technical max fits u8),
and the lookup body is byte-identical to the archival one again. No committed
fingerprint was touched.

## Compile-time contracts (negative tests)

- `-DFE8_ITEM_ID_CAP=0x100` compiling `src/bmitem.c` ->
  `error: size of array 'id_space_static_assert_item_cap_fits' is negative`
  and `... 'id_space_static_assert_bmitem_configured_cap_fits_storage' ...`.
- `-DFE8_ITEM_ID_CAP=0xCE` -> compiles cleanly.
- `-DFE8_EXPANSION_ITEMTEST_ENABLED=1` without an expanded cap ->
  `#error "FE8_EXPANSION_ITEMTEST_ENABLED requires an expanded item cap ..."`.
- `make expansion-modern-itemexpansion-check` without the probe env ->
  actionable failure printing the exact command to use.
- `FE8_ITEM_ID_CAP=0x100` / `=xyz` -> `$(error ...)` at make parse time.

## Explicit non-goals (unchanged)

- No class save-layout or save epoch change; `GameSavePackedUnit.jid` stays a
  7-bit field, class stays capped at 0x7F, 0x80 is rejected.
- No serialized save layout, meaning, packing, checksum or epoch change of any
  kind. `EXPANSION_SAVE_COMPAT_EPOCH` is untouched.
- No new event-command encodings; existing 16-bit operand lanes already carry
  item IDs.
- Chapter/unit/character widening is not attempted (documented per domain in
  the audit).
- No localized item name/description authored for 0xCE: it stays an original,
  blank, reserved slot with `maxUses = 1` so it behaves as a real, non-broken
  item at runtime. No text asset was added, so `MSG_COUNT` and every ROM
  layout that depends on it are unchanged.

## Known gaps / risks handed to the verifier

1. Release-configuration battle-map stall (above): pre-existing, reproduced
   with a probe-free ROM, out of scope here. The release runtime probe is
   therefore scoped to boot-reachable stages.
2. Deep committed fingerprints (`debugtools-*`) are default-cap oracles by
   construction (they probe absolute ROM pointers). They are run at the
   default cap, not at 0xCE; the layout-tolerant official gates are run at
   0xCE instead. No fingerprint was regenerated or relaxed.
3. The runtime probe's boot route uses spaced A taps plus world-map cursor
   jumps; if a future engine change alters that timeline, the probe reports
   the exact stage/diagnostic (`phaseTimedOut`, `procStateNow`,
   `phaseWaitFrames`) instead of silently passing.
4. No save-migration test exists yet, and none was added in this phase: the
   item cap raise needed no migration (checklist item 5), so there is
   nothing for a migration test to exercise today. The CI gate added in this
   phase (`expansion-modern-itemexpansion-check` at `FE8_ITEM_ID_CAP=0xCE`)
   covers boundary and serialization, not migration -- acceptance criterion
   4's "migration tests gate CI" clause stays open until a future phase
   both adds a real migration (e.g. widening a save-serialized field beyond
   its current width) and a test for it. Recorded here so it cannot be
   mistaken for closed.
