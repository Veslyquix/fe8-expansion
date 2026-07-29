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
  tests ... OK` (against default-cap ROMs; in **normal mode** this suite
  reads the ROMs in `build/expansion-modern/`, so it must be run with
  default-cap builds present). Since fix D below, the CI host lane instead
  runs `GBA_PLAYTEST_HOST_ONLY=1 python3 -m unittest discover -s
  tools/gba-playtest/tests -v`, which is artifact-independent by
  construction; the ROM-backed coverage is unchanged and stays with the
  runtime/build gates.
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

## Post-merge verifier fixes (RCA + two-layer defenses)

After the upstream-master merge (`4405c653`) an independent verifier flagged
two deterministic failures. Both are fixed here at the production layer, not
only in the tests, and each has a regression that reproduces the original
failure chain.

### A. Item-cap CLI check leaked a wrong-cap object into the shared build tree

Root cause: `scripts/generated_data/tests/test_items_roundtrip_regression.py`
`CliCheckRegressionTests` ran `python -m scripts.generated_data check --table
items` at `FE8_ITEM_ID_CAP=0xCE` with **no** `--out-dir`. `check` self-heals
the ephemeral generated C write-if-changed, so that run wrote a 207-record
`build/generated/data/data_items.c` into the real shared tree. The Make cap
stamp (`build/generated/data/.item_id_cap.stamp`) still recorded the default
`0xCD`, and the poisoned `.c` mtime outranked every tracked input -- so a
subsequent plain/default `make` treated the 207-record file as up to date by
ordinary mtime staleness, silently compiled and linked it, and exited 0. Only
a `clean` rebuild restored 206.

Two-layer fix:

1. **Test/CLI isolation.** `CliCheckRegressionTests._run_check` now runs every
   invocation inside a `tempfile.TemporaryDirectory()` passed as `--out-dir`,
   so the item-cap CLI checks never touch the shared `build/generated/data`
   tree. The committed-inventory drift comparison is unaffected (it always
   reads the real `reports/` copy).
2. **Content-addressed build self-heal.** The `$(GENERATED_DATA_ITEM_CAP_STAMP)`
   recipe (`generated_data.mk`) now re-runs the items generator through
   `check --table items --out-dir build/generated/data` (write-if-changed,
   never writes any committed file). Because `FE8_ITEM_ID_CAP` is an
   env/config input, an out-of-band wrong-cap `.c` -- even one whose mtime
   outranks every tracked input -- is content-healed back to the resolved
   cap: a mtime-preserving no-op when already correct (no downstream
   recompile, no tracked drift), a single rewrite recompiling exactly the
   affected object when it was stale. `generated-data-check` stays the
   authoritative validation/drift gate.

Regression: `make generated-data-cap-heal-check` (generated_data.mk,
local/manual like `generated-data-link-check` because the object half needs
the archival agbcc pipeline CI does not install) reproduces the exact chain --
stamp at default cap + a poisoned 207-record `.c` with a newer mtime -> a
plain default object build restores the 206-record `.c` **and** recompiles
the object to byte-match the clean baseline -- then proves the already-correct
no-op, a 206 -> 207 -> 206 cap flip, and that running the item-cap CLI check
tests leaves the shared default-cap build `.c` untouched. `make
generated-data-link-check` still passes unchanged (its touched-JSON no-op and
up-to-date assertions are not perturbed by the silent heal).

Verified fresh: legacy object `md5` and modern
`build/expansion-modern/release/aapcs/src/data_items.o` `md5` both return to
the 206 baseline after a poison + default rebuild; `make generated-data-check`
reports items `206 record(s)` and manifest `722 record(s)`; the full
`scripts/generated_data/tests` suite (544 passed) leaves
`build/generated/data/data_items.c` at 206 records.

### B. upstream_port `verify` mirrored only 6 of the workflow gates

Root cause: `tests/upstream_port/test_verify.py`
`VerifyGatesMirrorWorkflowTests` re-derives the expected gate list from the
live `.github/workflows/build.yml` on every run (issue #15 literal-mirror
contract). After the merge added the item-expansion runtime gate,
`scripts/upstream_port/verify.py` `gates()` still returned 6 gates while the
workflow had 8 command gates -- the two `expansion-modern-itemexpansion-check`
(`debug`/`release`) steps were missing.

Fix: `gates()` now returns all 8 in workflow order, adding
`modern-itemexpansion-check-debug` and `modern-itemexpansion-check-release`
with the argv-identical command
`FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1 make
expansion-modern-itemexpansion-check MODERN_CONFIG=<debug|release>
MODERN_ABI=aapcs -j{jobs}`. The leading `NAME=VALUE` tokens are kept verbatim
in `command` (so the literal mirror stays argv-identical to the workflow) and
`run_gates` gained `_split_env_prefix`, which peels a leading run of
`NAME=VALUE` env-assignments off the front and applies them to the child
environment instead of exec-ing them -- make-variable overrides such as
`MODERN_CONFIG=debug`, which appear after `make`, stay in argv. No YAML is
parsed to synthesize the gates (that would defeat the #15 literal contract),
and the closure-integrity tests forbidding any gate-selection/subset
capability are untouched. The `test_verify.py` counts that pinned the old
6-gate set were updated to the correct 8 (and the two new gate names added to
the full ordered-name assertion) -- a faithful mirror update, not a weakening.

Verified: `tests/upstream_port` 139 passed / 8 subtests;
`python3 -m scripts.upstream_port verify --dry-run` lists all 8 gates in
order, the item-expansion gates rendering their `FE8_ITEM_ID_CAP=0xCE
FE8_EXPANSION_ITEMTEST=1 make ...` prefix exactly as in `build.yml`.

Merge update (integrating the finalized issue #11/#13 runtime harness
`master`): that master split CI into two jobs and added a host-only
`host-tests` lane with two further gate steps (`Run gba-playtest host test
suite`, `Run upstream-port tooling test suite`), so the literal mirror is now
**10** gates, not 8 -- the two host-lane gates first, then the eight steps of
the ROM `build` job ending with the two item-expansion gates. Git merged both
sides of `test_verify.py` without a conflict while each side independently
still asserted `8`, so the three hardcoded counts
(`test_dry_run_never_executes_subprocess`,
`test_dry_run_lists_full_ordered_gate_set_never_a_subset`,
`test_cli_verify_dry_run_lists_full_ordered_gate_set`) were corrected to
`10`; the exact-count and full-ordered-name assertions themselves were kept
exactly as strict. `tests/upstream_port` passes 139/139 on the merge result.

### C. Archival lane silently accepted an expanded item cap (parse-time guard)

Root cause: `FE8_ITEM_ID_CAP` is threaded into the compile only by the modern
lane (`modern.mk` -> `MODERN_DEFINE_FLAGS += -DFE8_ITEM_ID_CAP=<n>`). The
archival agbcc lane -- the `legacy` alias and the direct `fireemblem8.gba` /
`fireemblem8.elf` / `fireemblem8.map` targets -- deliberately does **not**
thread the define. So `FE8_ITEM_ID_CAP=0xCE make fireemblem8.gba` (and `make
legacy`) planned a 207-record `gItemData[]` table (the cap stamp resolves
`item_id_cap=0xCE`) while every archival object still compiled
`include/id_space.h`'s built-in `ITEM_ID_CONFIGURED_CAP` at the vanilla
`0xCD`: a silent generated-vs-compiled contract divergence. The pre-existing
per-recipe cap stamp/self-heal (finding A) cannot catch this because it lives
in a recipe, and `make -n` (and Make goal resolution generally) never runs a
recipe -- confirmed reproduced: `FE8_ITEM_ID_CAP=0xCE make -n fireemblem8.gba`
exited 0 with **zero** agbcc compile lines carrying `-DFE8_ITEM_ID_CAP` yet a
planned `item_id_cap=0xCE` stamp write.

Strategic decision (frozen): the archival lane is **unsupported for item
expansion**; it must fail early and actionably rather than be threaded the
define. Item ID expansion is modern-only.

Initial fix (superseded by finding C-follow-up below): a parse-time
`$(error)` gated on a literal `MAKECMDGOALS` whitelist
(`legacy fireemblem8.gba fireemblem8.elf fireemblem8.map`) plus a `$(shell)`
resolver forwarding `FE8_ITEM_ID_CAP='$(FE8_ITEM_ID_CAP)'` for command-line
precedence. A fresh review flagged **two** defects in this first cut, both
fixed in C-follow-up: (P2) the literal whitelist caught only those four goal
spellings and silently let every *indirect* archival entry
(`fireemblem8_relocs.elf`, the whole `shiftcheck` family, `objects.lst`, and
any future target reaching the archival objects) through at an expanded cap
under `make -n`; and (P1) interpolating the raw `FE8_ITEM_ID_CAP` value into the
`$(shell)` command was a **shell-injection** vector.

Evidence mapping:

| Scenario | Command | Result |
|---|---|---|
| Repro (silent divergence) | `FE8_ITEM_ID_CAP=0xCE make -n fireemblem8.gba` (pre-fix) | exit 0; 0 agbcc lines with `-DFE8_ITEM_ID_CAP`; stamp plans `item_id_cap=0xCE` |
| Env expanded, direct ROM | `FE8_ITEM_ID_CAP=0xCE make -n fireemblem8.gba` | exit 2, actionable `*** Archival lane target(s) 'fireemblem8.gba' only support ... FE8_ITEM_ID_CAP=0xCD ... modern-only ...` |
| Env expanded, alias | `FE8_ITEM_ID_CAP=0xCE make -n legacy` | exit 2, same diagnostic naming `legacy` |
| Command-line expanded | `make -n legacy FE8_ITEM_ID_CAP=0xCE` | exit 2 |
| Precedence (CLI beats env) | `FE8_ITEM_ID_CAP=0xCD make -n legacy FE8_ITEM_ID_CAP=0xCE` | exit 2 |
| Precedence (CLI beats env, permissive) | `FE8_ITEM_ID_CAP=0xCE make -n legacy FE8_ITEM_ID_CAP=0xCD` | exit 0 |
| Default cap | `make -n legacy` / `make -n fireemblem8.gba` | exit 0 (archival lane reachable) |
| Explicit vanilla / legal equivalent | `FE8_ITEM_ID_CAP=0xCD make -n legacy` / `FE8_ITEM_ID_CAP=205 make -n fireemblem8.gba` | exit 0 |
| Modern unaffected | `FE8_ITEM_ID_CAP=0xCE make -n` (bare) | exit 0, modern release AAPCS boot-check, no agbcc |
| Generated-data unaffected | `FE8_ITEM_ID_CAP=0xCE make -n generated-data-check` / `... make generated-data-check` | exit 0 |
| Modern define consistency | `FE8_ITEM_ID_CAP=0xCE make -rR -p` | `MODERN_DEFINE_FLAGS := ... -DFE8_ITEM_ID_CAP=0xCE` |

Regression tests: see finding C-follow-up (the test module was rewritten to
pin the dependency-graph guard).

### C-follow-up. Guard was a fragile goal whitelist + shell-injection-prone (dependency-graph refactor)

Fresh-reviewer reproduction (P2): with the initial fix in place,
`FE8_ITEM_ID_CAP=0xCE make -n shiftcheck{,-static,-offsets,-diff,-run}` and
`FE8_ITEM_ID_CAP=0xCE make -n fireemblem8_relocs.elf` still **exited 0** -- the
literal `MAKECMDGOALS` whitelist only matched four hand-listed goal spellings,
so every indirect archival entry (the shiftability harness, the reloc ELF,
`objects.lst`, and any future target that reaches the archival objects) bypassed
the same silent generated-vs-compiled divergence.

Root cause: the strategy is that the *entire archival lane* is unsupported for
expansion, but the guard was pinned to four goal names instead of to the
archival dependency graph.

Fix -- dependency-graph-level guard (`generated_data.mk` + one Makefile
attachment):

* `generated_data.mk` defines a single `.PHONY` target
  `generated-data-archival-item-cap-guard` whose *recipe* body is a make
  `$(error ...)` that fires only at an expanded resolved cap
  (`GENERATED_DATA_ITEM_CAP_EXPANDED := $(filter-out $(default),$(resolved))`).
  Because the assertion is a make function in the recipe, make expands (and
  fires) it whenever the guard target is pulled into the active build graph --
  under `make -n` (a dry run still expands recipe text) and even when the
  archival products are already up to date (the target is `.PHONY`, always
  reconsidered). It is *lazy*: expanded only when an archival target is actually
  requested.
* The `Makefile` attaches that guard as an **order-only prerequisite** of the
  archival link/list/artifact boundary --
  `objects.lst / fireemblem8.elf / fireemblem8.gba / fireemblem8.map /
  fireemblem8_relocs.elf`. Every archival artifact (incl. the whole shiftcheck
  family) funnels through at least one of these, and none is built by the
  modern or standalone generated-data lanes, so the guard is inherited through
  the graph by any archival target -- named, indirect, or added later -- with
  no goal list to maintain. Order-only means the always-out-of-date `.PHONY`
  guard never forces an archival relink at the vanilla cap (a no-op `:` there).

The attachment is deliberately at the link/list/artifact boundary, **not** on
the individual `$(ALL_OBJECTS)`: several `src/data/*.o` data objects are
*shared* -- `expansion-modern-boot-check` builds them via its own `make NODEP=0
<objects>` sub-make -- so guarding objects would wrongly block the modern lane
at an expanded cap (caught by `test_bare_make_stays_modern_even_at_expanded_cap`
before this report was written).

Injection sub-fix (P1): GNU Make (4.3) does not export makefile/command-line
variables into a `$(shell)` subprocess, and a `make FE8_ITEM_ID_CAP=...`
assignment is not in make's own environment, so the resolver must pass the
value on the command. Interpolating the *raw* value was a shell-injection
vector -- reproduced: `FE8_ITEM_ID_CAP="'; touch /tmp/pwned; echo '" make -n
legacy` created `/tmp/pwned`. The `$(shell)` now POSIX-single-quote-escapes the
value (`'` -> `'\''`) so it is always one literal shell word; the same payload
now yields the invalid-cap error and no side effect. (A value containing make
`$(...)` syntax is still expanded by make when it evaluates the user's own
command line -- inherent GNU Make behaviour, upstream of this file, and not a
shell escape out of the resolver.) CLI-over-env precedence and the normalized
resolver are preserved.

Evidence mapping (post-follow-up):

| Scenario | Command | Result |
|---|---|---|
| P2 repro (indirect entries) | `FE8_ITEM_ID_CAP=0xCE make -n shiftcheck` / `... shiftcheck-static/-offsets/-diff/-run` / `... fireemblem8_relocs.elf` / `... objects.lst` | pre-follow-up exit 0; now **exit 2**, actionable guard diagnostic |
| Direct products + alias | `FE8_ITEM_ID_CAP=0xCE make -n legacy / fireemblem8.gba / fireemblem8.elf / fireemblem8.map` | exit 2 |
| Command-line cap | `make -n shiftcheck FE8_ITEM_ID_CAP=0xCE` | exit 2 |
| Precedence (CLI beats env) | `FE8_ITEM_ID_CAP=0xCD make -n legacy FE8_ITEM_ID_CAP=0xCE` | exit 2 |
| Precedence (permissive) | `FE8_ITEM_ID_CAP=0xCE make -n legacy FE8_ITEM_ID_CAP=0xCD` | exit 0 |
| Future/indirect target inheritance | `make -f Makefile -f <frag> -n <ad-hoc>: $(ELF)` at `0xCE` | exit 2 (graph-inherited, named nowhere) |
| Real build, before any link | `FE8_ITEM_ID_CAP=0xCE make fireemblem8.map` (non `-n`) | exit 2 in ~1.5s; no `arm-none-eabi-ld`/`objcopy` |
| Vanilla / legal equivalents | `make -n legacy` / `FE8_ITEM_ID_CAP=205` / `0xcd` / `0o315` | exit 0 (archival reachable) |
| Modern unaffected | `FE8_ITEM_ID_CAP=0xCE make -n` (bare) / `... expansion-modern-boot-check ...` | exit 0 |
| Generated-data unaffected | `FE8_ITEM_ID_CAP=0xCE make -n generated-data-check` / `... make generated-data-check` | exit 0 |
| Modern define consistency | `FE8_ITEM_ID_CAP=0xCE make -rR -p` | `MODERN_DEFINE_FLAGS := ... -DFE8_ITEM_ID_CAP=0xCE` |
| Shell injection (env + CLI) | `FE8_ITEM_ID_CAP="'; touch M; echo '" make -n generated-data-check` | no `M` created; exit 2 invalid-cap error |

Regression tests (rewritten):
`scripts/modernize/tests/test_archival_lane_item_cap_guard.py` (21 tests, 42
subtests, all green) pins: every archival entry (direct/alias/relocs/shiftcheck
aggregate+each sub-target/objects.lst) blocked under `make -n` via env and CLI;
CLI-over-env precedence both directions; normalized vanilla/expanded spellings
(`205`/`0xcd`/`0o315` vs `206`/`0xce`/`0o316`); the modern + generated lanes and
bare/default modern staying green at `0xCE`; the modern lane threading a
consistent `-DFE8_ITEM_ID_CAP`; **dependency-graph inheritance** by ad-hoc
future targets depending on `$(ELF)`/`$(OBJECTS_LST)`/`$(RELOCS_ELF)`; a real
(non `-n`) `fireemblem8.map` blocking before any link; and shell-injection
safety for env + command-line metacharacter payloads. No archival compiler flags
were changed to support expansion; no test/CI gate was weakened.

### C-final. "Fail early" gap: known archival goals churned the object graph before failing (parse-time gate added)

Fresh-reviewer finding: the dependency-graph guard (C-follow-up) was **safe**
(it always blocked the archival *link*) but not **early**. Its attachment is an
*order-only* prerequisite, and GNU Make updates order-only prerequisites *after*
a target's regular prerequisites. So a real `make legacy` / `make
fireemblem8.gba` at an expanded cap first ran mgfembp's `$(MAKE)` sub-build and
assembled hundreds of agbcc objects (the regular prerequisites of `$(ROM)`) and
only then hit the order-only guard -- violating the user's explicit "the
legacy/direct target must fail early" requirement. The prior regression suite
masked this by only ever exercising a *real* build of `fireemblem8.map`, whose
sole prerequisite is the order-only guard (no object graph), so it could never
prove the "don't churn the graph first" property.

Fix -- add **Gate 1**, a parse-time known-goal fast-fail, and keep the graph
guard as **Gate 2** (backstop for unknown/indirect/future entries). Both gates
share one diagnostic, factored into `GENERATED_DATA_ARCHIVAL_ITEM_CAP_DIAG` in
`generated_data.mk`, so they cannot drift:

* `Makefile` builds `ARCHIVAL_KNOWN_GOALS` from the Make variables (verified
  against the Makefile / `make -p`, not guessed): `legacy $(ROM) $(ELF) $(MAP)
  $(RELOCS_ELF) $(OBJECTS_LST)` + the `shiftcheck` aggregate and each
  `shiftcheck-{static,offsets,diff,run}` sub-target. `shiftcheck-build` is
  intentionally excluded -- it only scans build-system addresses and reaches no
  archival product.
* At an expanded resolved cap, `$(if $(filter $(ARCHIVAL_KNOWN_GOALS),
  $(MAKECMDGOALS)), ...)` fires `$(error ...)` during parse, before any recipe,
  sub-make, or agbcc/arm-none-eabi command is planned or run.

Evidence mapping (finding C-final):

| Scenario | Command | Result |
|---|---|---|
| Repro (fail-late) | `FE8_ITEM_ID_CAP=0xCE make legacy` (non `-n`, pre-C-final) | ran mgfembp sub-build + agbcc objects, then aborted at link |
| **Parse-time, zero recipe** | `FE8_ITEM_ID_CAP=0xCE make -n legacy` (and `fireemblem8.gba/.elf/.map`, `fireemblem8_relocs.elf`, `objects.lst`, `shiftcheck{,-static,-offsets,-diff,-run}`) | exit 2; output is **only** the `Makefile:NNN: *** ...` diagnostic + `Stop.` -- no `mgfembp` / `arm-none-eabi-*` / assemble / link line planned |
| **Real high-prereq build, no work done** | `FE8_ITEM_ID_CAP=0xCE make legacy` / `fireemblem8.gba` / `objects.lst` / `shiftcheck` (non `-n`) | exit 2 at parse; **no** `Entering directory` / `mgfembp` / `arm-none-eabi-as` / `arm-none-eabi-ld` / `arm-none-eabi-objcopy` |
| Command-line cap | `make -n legacy FE8_ITEM_ID_CAP=0xCE` | exit 2 (Gate 1) |
| Precedence (CLI beats env) | `FE8_ITEM_ID_CAP=0xCD make -n legacy FE8_ITEM_ID_CAP=0xCE` | exit 2 |
| Precedence (permissive) | `FE8_ITEM_ID_CAP=0xCE make -n legacy FE8_ITEM_ID_CAP=0xCD` | exit 0 |
| **Unknown/indirect still blocked (Gate 2)** | `make -f Makefile -f <frag> -n <ad-hoc>: $(ELF)/$(OBJECTS_LST)/$(RELOCS_ELF)` at `0xCE` (named nowhere in `ARCHIVAL_KNOWN_GOALS`) | exit 2 via graph backstop (`generated_data.mk:NNN`) |
| Vanilla / legal equivalents | `make -n legacy` / `FE8_ITEM_ID_CAP=205` / `0xcd` / `0o315` | exit 0 |
| Modern unaffected | `FE8_ITEM_ID_CAP=0xCE make -n` (bare) / `... expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs` | exit 0 |
| Generated-data unaffected | `FE8_ITEM_ID_CAP=0xCE make -n generated-data-check` | exit 0 |
| Modern define consistency | `FE8_ITEM_ID_CAP=0xCE make -rR -p` | `MODERN_DEFINE_FLAGS := ... -DFE8_ITEM_ID_CAP=0xCE` |
| Shell injection (env + CLI) | `FE8_ITEM_ID_CAP="'; touch M; echo '" make -n generated-data-check` | no `M` created; exit 2 invalid-cap error |

Regression tests: `scripts/modernize/tests/test_archival_lane_item_cap_guard.py`
now **26 tests / 53 subtests, all green**. New coverage over C-follow-up:
`KnownGoalParseTimeFastFailTests` (every known goal fails under `make -n` with
**zero** recipe/sub-make/compile marker), and
`RealArchivalBuildPreemptedBeforeAnyWorkTests` (real, non `-n` `legacy` /
`fireemblem8.gba` / `objects.lst` / `shiftcheck` -- each depending on all of
`$(ALL_OBJECTS)` -- abort at parse before any object assemble, mgfembp
sub-build, or link). The `DependencyGraphInheritanceTests` continue to pin the
Gate-2 backstop for ad-hoc targets named nowhere in the goal list. No archival
compiler flags were changed to support expansion; no test/CI gate was weakened;
the graph backstop was **not** removed.


### D. Host lane ran live ROM integration opportunistically (artifact-timing-controlled gate)

**Symptom.** In an artifact-rich local worktree at this branch head, the host
gate `python3 -m unittest discover -s tools/gba-playtest/tests` failed with
exactly six failures, all in
`SaveCompatScenarioTests_modern_release.test_each_non_current_state_shows_distinct_dialog_and_preserves_sram`
(subtests `valid-legacy`, `header-corrupt`, `metadata-corrupt`, `older`,
`newer`, `config-incompatible`), each a `checkpoints[2].framebuffer_hash`
mismatch. A clean CI checkout passed the same command. Reproduced verbatim
before the fix: `Ran 270 tests ... FAILED (failures=6)`.

**RCA.** The failures are not about the commit under test at all:

1. Why did the host gate fail? The release save-compat scenarios were captured
   live against `build/expansion-modern/release/aapcs/fireemblem8.gba` and
   compared to the committed release fingerprints.
2. Why did a *host* gate boot a ROM? Each live TestCase decided
   live-run-vs-skip from `rom.exists()`.
3. Why is that unreliable? `build/` is git-ignored and user-owned. It can hold
   a stale ROM, a mid-rebuild ROM, or (after `verify` gates 9-10) an
   expanded-cap `FE8_ITEM_ID_CAP=0xCE` ROM, none of which the committed
   default-cap fingerprints describe.
4. Why is that a design defect and not just bad luck? It made host-gate
   coverage a function of local artifact timing instead of an explicit
   contract: CI (clean) skipped, a local worktree ran, and
   `python3 -m scripts.upstream_port verify --jobs 2` is the worst case,
   because its own later gates rewrite exactly those artifacts.
5. Root fix. The host lane must be decided by an explicit mode, and live
   coverage must be owned by the gates that build the ROM they boot.

**Fix (no fingerprint, baseline or budget touched, nothing cleaned/deleted).**

- New single public contract `GBA_PLAYTEST_HOST_ONLY` in
  `tools/gba-playtest/tests/host_mode.py`: strict boolean (default off,
  unrecognized value refused, never guessed), the single source of truth for
  repository ROM/ELF paths, one `require_built_rom()` existence check, one
  `capture_live_or_skip()` live entry point, and a
  `live_artifact_testcase()` class decorator that skips at *run* time, before
  any `setUpClass`/`setUp` body can probe an artifact.
- All nine live TestCase classes across the seven ROM-dependent modules are
  registered in `host_mode.LIVE_TEST_CLASSES` and guarded; the six duplicated
  copies of the backend-unavailable marker list and the ad-hoc
  `_capture_or_skip` helpers were deleted in favor of the central ones.
- Every test module is explicitly classified Category A (host-only safe,
  always runs) or Category B (live, skipped in host-only mode) in
  `host_mode.py`; `tools/gba-playtest/tests/test_host_only_mode.py` (22 tests)
  enforces the classification, the strict env parsing, the
  skip-before-probe/mid-run-appearance behavior and normal-mode preservation.
- `.github/workflows/build.yml` `host-tests` runs
  `GBA_PLAYTEST_HOST_ONLY=1 python3 -m unittest discover -s tools/gba-playtest/tests -v`;
  the ROM `build` job never sees the variable.
  `scripts/upstream_port/verify.py` mirrors that argv literally as a leading
  inline env assignment, so `_split_env_prefix` applies it to that one child
  process only.

**Evidence (all run this session, same worktree).**

| Check | Command | Result |
|---|---|---|
| Defect reproduced (before fix) | `python3 -m unittest discover -s tools/gba-playtest/tests` | `Ran 270 tests ... FAILED (failures=6)` (stale release ROM) |
| Host-only, artifact-rich worktree (all ROMs/ELFs present, release ROM stale) | `GBA_PLAYTEST_HOST_ONLY=1 python3 -m unittest discover -s tools/gba-playtest/tests -v` | `Ran 271 tests in 52.576s ... OK (skipped=9)` |
| Artifacts untouched by that run | sha256 + size + `st_mtime_ns` of both modern ROMs, both modern ELFs, the legacy ROM and the debugtools SRAM fixture | all six byte-, size- and mtime-identical; none deleted |
| Normal mode unchanged (stale ROM present) | `python3 -m unittest discover -s tools/gba-playtest/tests` | `Ran 292 tests ... FAILED (failures=6)` -- the *same* six pre-existing failures, i.e. live behavior preserved |
| Normal mode against fresh, current default-cap ROMs | same command, after the two `expansion-modern-linker-check` gates rebuilt both configs | `Ran 292 tests in 158.663s ... OK` (zero skips: all 21 live tests really ran) |
| Clean-checkout equivalence (hermetic copy, no artifacts) | live classes, both modes | host-only `OK (skipped=9)` with the host-only reason; normal `OK (skipped=11)` with `ROM not built` -- CI outcome unchanged |
| Stale/mismatched artifacts staged at the expected paths (hermetic tree) | `test_host_only_mode.HostOnlyStagedWorktreeSubprocessTests` | host-only: `Ran 0 tests ... OK (skipped=9)`, all six staged files unchanged; the same tree in normal mode really opens the stale ROM and fails loudly |
| Host-only contract regression suite | `python3 -m unittest test_host_only_mode -v` | `Ran 22 tests ... OK` |
| Mutation check (guard removed from one live class in a throwaway copy) | same suite | 4 independent regression tests fail, including the staged-tree run |
| Workflow <-> verify mirror + env isolation | `python3 -m unittest discover -s tests/upstream_port -v` | `Ran 144 tests ... OK` (5 new: literal gate argv, prefix split, no other gate carries it, workflow host-job-only, run_gates injects it into that child only and never mutates `os.environ`) |
| Gate list | `python3 -m scripts.upstream_port verify --dry-run --jobs 2` | 10 gates, order unchanged; gate 1 is `GBA_PLAYTEST_HOST_ONLY=1 python3 -m unittest discover -s tools/gba-playtest/tests -v` |
| Full local CI | `python3 -m scripts.upstream_port verify --jobs 2` | all 10 gates `[PASS]` in `10m25.811s` -- host gate deterministic while gates 7-10 rebuilt the very ROMs it used to read |

**Why coverage is not reduced.** Every live scenario the host lane used to run
opportunistically is already a hard prerequisite of the ROM gates that build
the ROM they boot: `expansion-modern-linker-check` (boot/title/debugtools/
timer/map/tools/prep/ch4prep/newgame/combat/saveload/savefmt/shifted plus the
budget, overlay, shift-offset and raw-pointer audits) for `debug` and
`release`, then `expansion-modern-itemexpansion-check` at cap `0xCE` for both
configs. Those four gates are unchanged and were re-run green above. A
concrete illustration of the hazard being removed: immediately after
`verify --jobs 2`, `build/expansion-modern/*` holds the expanded-cap ROMs, so
a *normal-mode* host suite run fails (`combat` probe `0x0f` vs `0x00`) --
while the host-only lane stays green, because it never reads those files.

**Out of scope by construction.** No fingerprint, baseline, budget or scoring
artifact was refreshed or edited; no git-ignored user output was cleaned or
deleted; no gate was removed, reordered or weakened (gate count stays 10, and
the mirror test still parses the live workflow); the ROM `build` job does not
inherit host-only mode; local runtime debugging keeps the previous
artifact-driven behavior in normal mode.


## Post-review batch: ACTIVE build contract + source-driven consumer census

Two review findings were closed in this batch. Neither changed a gameplay
feature, a fingerprint, a budget, a save epoch or any protected artifact.

### Finding A -- the reports claimed a cap the build never published

`FE8_ITEM_ID_CAP=0xCE` really did generate a 207-record `gItemData[]`, but
every *reported* surface still said `0xCD`/`206`: `idspace.DOMAINS` carries a
module-level `configured_cap` of `0xCD`, and `manifest_record_count()`
deliberately holds the committed manifest at 206. There was no build-local
surface that said what the build actually resolved.

Fix: keep every committed surface exactly as stable as it was, and add three
**build-local** ACTIVE surfaces rendered from the same model:

| Surface | Path | Default build | `FE8_ITEM_ID_CAP=0xCE` |
|---|---|---|---|
| Machine audit | `build/generated/data/id_space_active_audit.json` | cap `0xCD`, 206 records | cap `0xCE`, 207 records |
| Human audit | `build/generated/data/id_space_active_audit.md` | cap `0xCD`, 206 records | cap `0xCE`, 207 records |
| C contract | `build/generated/data/id_space_active.h` | `ITEM_ID_ACTIVE_CONFIGURED_CAP 0xCD`, `ITEM_ID_ACTIVE_RECORD_COUNT 206` | `0xCE` / `207` |
| Committed default audit | `reports/id_space_audit.{json,md}` | `0xCD` / `206` | **unchanged, byte-identical** |
| Committed manifest | `reports/generated_data_manifest.md` | items 206 | **unchanged, 206** |

Every domain reports `default_cap`, `active_configured_cap` and either both
record counts or an explicit `record_count_status: n/a` plus a written reason
(chapter/unit/event have no single record table). The active record count is
the number of records actually loaded, not a hand-maintained constant.

Observed:

```console
$ FE8_ITEM_ID_CAP=0xCE make generated-data-check
OK: no manifest drift (13 table(s), 722 record(s))
consumer census clean: 1070 hit(s), 1046 audited, 24 reviewed-exclusion, digest 11e8a358...
id-space contract up-to-date (3 outputs)
active id-space contract up-to-date (3 outputs); item cap 0xCE, 207 record(s)
$ git status --porcelain        # no tracked drift from the configured run
```

**The header is compiled, not decorative.** The generated item table now
includes `id_space.h` + `id_space_active.h` and carries two
`ID_SPACE_STATIC_ASSERT`s: the compiler cap must equal the generator cap, and
`sizeof(gItemData)/sizeof(gItemData[0])` must equal the active record count.
`make expansion-modern-idspace-active-check` proves all three directions with
the real modern toolchain:

```console
--- default cap: generated table and ACTIVE header must both say 0xCD / 206 ---
OK: default-cap generated table compiles against the ACTIVE contract (0xCD / 206)
--- configured cap: FE8_ITEM_ID_CAP=0xCE must move both to 0xCE / 207 ---
OK: configured generated table compiles against the ACTIVE contract (0xCE / 207)
--- negative: the 0xCE table compiled without the cap flag must FAIL ---
OK: cap/count divergence is a hard compile error, not a silent truncation
PASS: expansion-modern-idspace-active-check
```

The archival agbcc lane remains default-only and keeps its existing parse-time
fast-fail (re-verified: `FE8_ITEM_ID_CAP=0xCE make -n fireemblem8.gba` still
stops at `Makefile:308` with the actionable archival diagnostic); the active
header is generated into the same directory as the generated table, so the
quoted include resolves in both lanes with no new `-I`.

**Linked, not just compiled.** A real modern release ELF was linked at both
caps and the linked table size was read back from the ELF, not assumed:

```console
$ FE8_ITEM_ID_CAP=0xCE make -j4 expansion-modern-elf MODERN_CONFIG=release MODERN_ABI=aapcs
Linked modern ELF: build/expansion-modern/release/aapcs/fireemblem8.elf
$ arm-none-eabi-nm -S build/expansion-modern/release/aapcs/fireemblem8.elf | grep " gItemData$"
08909498 00001d1c T gItemData      # 7452 bytes = 207 records x 36

$ make -j4 expansion-modern-elf MODERN_CONFIG=release MODERN_ABI=aapcs   # default cap again
08909498 00001cf8 T gItemData      # 7416 bytes = 206 records x 36
```

The build tree was left at the default cap (206-record ELF, ACTIVE header back
to `0xCD`/`206`) so no later normal-mode host run inherits an expanded-cap
artifact.

### Finding B -- the consumer audit was a curated sample, not a census

The previous audit contained 18 hand-written evidence rows and the tests only
asserted that each of 8 categories appeared *at least once*. Real consumers
were missing: `BonusClaimEnt.itemId`, `UnitDefinition.{charIndex,classIndex,
items}`, the shop lists, `gDefaultShopInventory`, the convoy array plus
`Write/ReadSupplyItems`, `ArenaData.{playerClassId,opponentClassId}`, the class
reel/opinfo/uisupport UI, the monster lookup table and the worldmap interfaces.

Fix: `scripts/generated_data/consumer_census.py` scans the real source tree and
`scripts/generated_data/consumer_classification.json` maps **every** hit 1:1 to
a category or to a `reviewed-exclusion` with a written reason.

- Scanned surface: `include/**` (`.h`), `src/**` (`.c`/`.h`), `asm/**`
  (`.s`/`.inc`), `tools/gba-playtest/**` (`.py`). Exclusions (`build/`,
  `mgfembp/`, `tools/agbcc/`, `src/data/`) are configuration and are printed
  inside the audits, together with the coverage limitations the rule set
  structurally cannot resolve.
- Current census: **1070 hits -- 1046 audited, 24 reviewed exclusions**
  (11 chapter-number sprites, 4 prep-screen tile/palette assets, and 9
  menu-machinery `item` symbols where "item" means a menu entry, not a game
  item ID). See Finding C for the fresh-review scope-tracking fix that removed
  60 fabricated function-body hits from the earlier 1130 figure.
- Hit identity is `path|kind|domain|symbol`; line numbers are evidence only, so
  re-indenting a file does not churn the classification.
- The curated runtime-proven evidence rows are kept as their own section --
  they prove *what a booted ROM exercised*; the census proves *nobody was
  missed*. The two now live in the same generated audits.

Verifier-named consumers, all present in both audits (spot check):

| Consumer | Path | Category |
|---|---|---|
| `BonusClaimEnt.itemId` | `include/bonusclaim.h` | runtime-struct |
| `UnitDefinition.charIndex` / `.classIndex` / `.items` | `include/bmunit.h` | runtime-struct |
| `gDefaultShopInventory` + 37 `ShopList_*` | `include/bmshop.h`, `include/eventcall.h` | lookup-table |
| `ItemList_WM_*` (worldmap shops, 87 symbols) | `include/worldmap.h`, `src/worldmap_shop_data.c` | lookup-table |
| `gConvoyItemArray`, `gConvoyItemCount`, `Write/ReadSupplyItems` | `include/variables.h`, `include/bmsave.h` | lookup-table / save-field |
| `ArenaData.playerClassId` / `.opponentClassId` | `include/bmarena.h` | runtime-struct |
| `ClassReelEnt.classId`, `OpInfoIconProc.classId`, `OpInfoViewProc.charIndex` | `include/opinfo.h` | ui-buffer |
| `GetSupportScreenCharIdAt`, `GetSupportClassForCharId` | `include/uisupport.h` | ui-buffer |
| `MonsterItemsByClassEntry.classId`, `gMonsterItemTable` | `include/monstergen.h`, `src/monstergen_data.c` | runtime-struct / lookup-table |
| `GMapNodeData.chapteridx_eirika`, `GmapTimeMonsConf.jid` | `include/worldmap.h` | runtime-struct |

Enforcement is machine-side, not review-side: a new unclassified consumer fails
with its key and `path:line`; a classified row whose declaration disappeared
fails as stale; a duplicate key or an exclusion without a reason is fatal at
load. `scripts/generated_data/tests/test_consumer_census.py` proves this with
temporary-fixture mutations (new consumer -> unclassified failure, removed
consumer -> stale failure, edited file -> same key, different evidence line),
not by asserting that a category appears once.

### Finding C -- the scanner fabricated struct fields out of function-body locals (fresh review P2)

The first census landed at **1130 hits**, but a fresh review found the scope
tracker was structurally unsound: `_track_braces` pushed *every* `{` onto the
struct stack and reused the last-seen `struct X` token as the owner. A function
signature whose parameter is a struct type therefore made the whole function
**body** "owned" by that struct, and ordinary body locals were minted into
struct fields that do not exist:

| Fabricated hit | Real source | Truth |
|---|---|---|
| `MenuItemDef.pid` | `src/bmmenu.c:1611` `int pid;` inside `SupplyUsability(const struct MenuItemDef * def, ...)` | a loop-local character index, not a `MenuItemDef` field |
| `ProcShop.item` | `src/bmshop.c:388` `u16 item;` inside `ShopDrawBuyItemLine(struct ProcShop * proc, ...)` | a local, not a `ProcShop` field |
| `anonymous.item` (x9) | `int item;` / `u16 item;` in nine function bodies | plain locals; no struct at all |
| `MenuItemProc.item` | `src/bmmenu.c` local | previously *hidden* as a `reviewed-exclusion`, i.e. the classification was being used to launder a fake hit |

This violated the module's own stated boundary ("function bodies are not
analysed") and inflated every reported count, so the 1130 figure could not be
trusted.

**Root cause:** brace nesting was conflated with struct-definition nesting. A
`{` only opens a field-bearing scope when a `struct`/`union` keyword (optionally
a tag) is *immediately* followed by `{`; a use as a parameter, variable, cast,
forward declaration or `sizeof(struct X)` always inserts another token first.

**Fix:** `consumer_census._ScopeTracker` replaces `_track_braces`. It opens a
struct scope only for a real definition head, treats function/`if`/`for`
/initializer/`enum` braces as plain blocks, harvests `struct-field` hits **only**
when the innermost open scope is a struct/union definition, and restricts
`data-symbol`/`function-signature` detection to file scope. Owners are stable:
a tag before the brace names the fields, a `typedef struct { .. } Alias;` uses
the closing alias, and a nested anonymous struct/union inherits its nearest
named ancestor.

**Before / after (TRF):**

| Metric | Before (fabricating) | After (fixed) |
|---|---|---|
| Total scanned hits | 1130 | 1070 |
| `struct-field` hits | 177 | 117 |
| `data-symbol` / `function-signature` / `macro` | 328 / 468 / 154 | 328 / 468 / 154 (unchanged) |
| Audited / reviewed-exclusion | 1105 / 25 | 1046 / 24 |
| Fabricated function-body struct fields | 60 | 0 |
| Census digest (sha256) | `f43cb69f...` | `11e8a3582f0f05e7de3b453a20fdb6e2f97737ec72e39dfa7f837ad85b476433` |

All 60 removed rows are function-body locals in `src/**.c`; **zero** header
struct fields were dropped, and every verifier-named real consumer above is
still audited (non-exclusion). The classification diff is removal-only (60
stale struct-field rows dropped, 0 added, 0 recategorised). New RCA fixtures in
`test_consumer_census.py::ScopeTrackingTests` reproduce the fabrications (they
fail on the old tracker) and pin the corrected behaviour, including a fresh
unclassified fixture that still fails the gate.

### Host-only workflow fix: untouched

The `GBA_PLAYTEST_HOST_ONLY=1` gate-1 fix, the 10-gate count, the normal/live
runtime build coverage and every fingerprint/budget artifact are unchanged in
this batch (`git status --porcelain` lists only the census/active-contract
files, the two makefiles, the two audits and the docs).

## Cap-flip follow-up: ACTIVE-header stamp/header desync self-heal

A final verifier recommended pass but its log reproduced a real first-fail that
is **not** hidden here: any modern configured/default build must self-heal to
its own resolved cap before compiling the consumer, and one sequence did not.

### First-fail reproduced (before)

```
$ make generated-data-check                              # default baseline: header 0xCD/206
$ FE8_ITEM_ID_CAP=0xCE make generated-data-check         # leaves ACTIVE header at 0xCE/207, stamp stays 0xCD
$ stat -c '%Y %n' build/generated/data/{id_space_active.h,.item_id_cap.stamp}
1785238039 build/generated/data/id_space_active.h        # 0xCE, newest
1785237943 build/generated/data/.item_id_cap.stamp       # still 0xCD, older
$ make build/expansion-modern/debug/aapcs/src/data_items.o   # plain default, no manual fix
include/id_space.h:12: error: size of array
  'id_space_static_assert_generated_items_record_count_matches_active_contract' is negative
make: *** [modern.mk:607: build/expansion-modern/debug/aapcs/src/data_items.o] Error 1
```

### Root cause

The build-local ACTIVE header is re-rendered **only** by the stamp-driven
grouped rule, which fires purely on `.item_id_cap.stamp`'s mtime. An
out-of-band `FE8_ITEM_ID_CAP=0xCE make generated-data-check` write-if-changes
the header to 0xCE (advancing *its* mtime) but never touches the stamp. On the
next plain/default build the resolved cap is unchanged (0xCD==0xCD), so the
stamp mtime does not advance; the 0xCE header now looks newer than the stamp,
the grouped rule is judged up to date and never re-renders -- yet
`data_items.c` (which lists the header as a prerequisite) *does* regenerate at
the default cap, so a 206-record table `#include`s a 207-record header: the
negative static assert on the first consumer compile, previously only
recoverable with a manual `make generated-data-check`. Hard-fail beats silent
corruption, but a build must never require a manual pre-step to recover.

### Fix (single-command, parallel-safe self-heal)

`generated_data.mk`, the `$(GENERATED_DATA_ITEM_CAP_STAMP)` recipe (a `FORCE`
prerequisite of `data_items.c`, so it runs on every build): heal the ACTIVE
surfaces with `idspace active-check` the same write-if-changed way the items
table is already healed, keyed off *this* make process's own resolved cap. The
header is therefore restored to the resolved cap **before** any consumer
compiles, in every direction, including `-j`. It is a mtime-preserving no-op at
the correct cap (no rebuild storm) and a single rewrite when stale. The
grouped rule still owns the ordinary cap-flip path; this closes only the
out-of-band stamp/header desync. No static assert was removed, no `clean` is
relied on, no oracle/gold artifact was touched.

### After (single command heals, first compile passes)

```
# desync staged exactly as above (header 0xCE, stamp 0xCD)
$ make build/expansion-modern/debug/aapcs/src/data_items.o          # plain default, exit 0
$ grep ITEM_ID_ACTIVE_ build/generated/data/id_space_active.h
#define ITEM_ID_ACTIVE_CONFIGURED_CAP 0xCD
#define ITEM_ID_ACTIVE_RECORD_COUNT 206
# full modern ELF from the same desync also self-heals + links:
$ FE8_ITEM_ID_CAP=0xCE make generated-data-check >/dev/null   # re-stage 0xCE header
$ make expansion-modern-elf MODERN_CONFIG=debug MODERN_ABI=aapcs   # exit 0
Modern ELF ready: build/expansion-modern/debug/aapcs/fireemblem8.elf   # header healed to 0xCD/206
```

### Regression coverage (both real-run)

- `make generated-data-active-heal-check` (generated_data.mk, host-only, no
  agbcc/arm toolchain -- CI-friendly): stages the exact stamp/header desync and
  asserts one plain default build re-syncs header+table to 0xCD/206; covers the
  reverse default->0xCE flip, a correct-cap no-op (proves no rebuild storm), and
  never cleans. Verified to **fail** with the fix reverted (negative control:
  "the stale 0xCE header did not self-heal on the first plain default build")
  and PASS with it in place.
- The "desync recovery" leg of `make expansion-modern-idspace-active-check`
  (modern.mk): the same recovery proven with a **real modern compile** so the
  stale-header negative assert can never silently return, alongside the existing
  default/configured/negative legs.

### Performance follow-up: the every-build heal is now a sub-second probe

The first version of this self-heal called `idspace active-check` from the
`FORCE`-driven `.item_id_cap.stamp` recipe. That recipe runs on **every** build,
and `active-check` re-renders the ACTIVE surfaces through the full consumer
census -- a ~15 MB source walk (658 files / ~1070 hits) -- so a *warm, already
correct* no-op build paid a fixed ~8-11 s tax for work it did not need to do.

The recipe now calls a new `idspace active-heal` instead. `active-heal` runs a
census-free probe first: it computes only the resolved cap and the real record
counts (`_active_domain_entries`, the same census-free model `active_contract`
layers the census on top of, so the two can never disagree) and compares them to
the cap/count/schema metadata already on disk in the header, JSON and Markdown.
If every surface already agrees it returns immediately -- no census, no write,
no mtime change. Only a missing/unparseable/schema-outdated/cap-count-mismatched
surface falls through to one full `active-generate`. Errors are **not** swallowed
(the old line ended in `|| true`): a bad `FE8_ITEM_ID_CAP` or a schema/IO error
now fails the build loudly at the probe.

Measured on this host (`/usr/bin/time -v`):

```
idspace active-check  (removed from the recipe)   0:08.10   full census / 658-file walk
idspace active-heal   (new warm no-op)            0:00.32   census-free probe, no write
check --table items   (pre-existing recipe heal)  0:00.82   unchanged neighbour
warm no-op `make build/generated/data/data_items.c`:  ~8-11 s  ->  ~2.6 s (x3 runs)
```

The warm heal is now on par with the neighbouring items-table self-heal instead
of dominating the build; the numbers are recorded as evidence, not asserted as a
wall-clock gate (the tests assert the *mechanism* -- the poisoned-scan no-op
contract -- so they stay deterministic across machines). `generated-data-check`
still runs the authoritative full-census `active-check`; the cheap probe changes
only the per-build FORCE path.

Regression coverage for the probe itself: `ActiveHealProbeTests` in
`scripts/generated_data/tests/test_idspace_active.py` proves (a) a warm no-op
never runs the census scan (a poisoned `consumer_census.scan` would raise), (b)
detection is itself census-free, (c) a stale cap flip regenerates all three
surfaces, (d) an out-of-band 0xCE header on a default build heals back to
0xCD/206, (e) missing/corrupt-JSON/corrupt-header/schema-bump surfaces are
flagged stale, and (f) a bad cap raises loudly (no swallowed exit-1). The
`make generated-data-active-heal-check` and modern "desync recovery" legs above
exercise the same recovery end-to-end through the real recipe.

**Follow-up: header/Markdown decode errors (`OSError`/`UnicodeDecodeError`) now
heal too, not just JSON.** `active_heal_reasons` already caught `(ValueError,
OSError)` around the JSON `json.load` (a `UnicodeDecodeError` is itself a
`ValueError` subclass, so corrupt JSON bytes were already covered), but the
header and Markdown reads were bare `open(...).read()` calls with nothing
catching a decode failure or a permission error -- a truncated/binary-corrupt
header or Markdown file, or one the process can no longer read, raised an
unhandled exception straight out of the probe instead of being reported as an
actionable, healable reason. Both reads are now wrapped the same way as JSON:
`except (OSError, UnicodeDecodeError)` records `unparseable: <file> (...)` and
skips that surface's field checks (the same "reasons, not a crash" contract
JSON already had), then falls through to one full regen exactly as any other
stale surface would. The regen path needed the matching fix: `write_if_changed`
unconditionally decoded the pre-existing file to decide whether a write was
necessary, so a corrupt on-disk file would crash the *regen* it was supposed to
repair. That decode is now best-effort (`existing = None` on `OSError`/
`UnicodeDecodeError`, meaning "assume it differs, write it") -- the actual
write is untouched, so a genuine write failure (permission denied, read-only
filesystem) still raises straight out rather than being swallowed into a false
"healed" success. New regression coverage: `test_corrupt_header_invalid_utf8_
triggers_regen_not_a_crash`, `test_corrupt_md_invalid_utf8_triggers_regen_not_
a_crash`, `test_all_three_surfaces_corrupt_recover_in_one_heal` (header +
Markdown poisoned with raw non-UTF-8 bytes and JSON poisoned with invalid JSON,
all at once, one heal call restores all three), and
`test_unreadable_header_is_reported_honestly_and_write_error_propagates` (a
permission-denied header is diagnosed as an actionable reason without
crashing, but the follow-up regen's write still raises rather than reporting a
false success). `python3 -m unittest discover -s scripts/generated_data/tests`
now runs 613 tests (598 baseline + 15 new `ActiveHealProbeTests`), OK; `make generated-data-active-heal-check` and
`make generated-data-check` both still PASS unchanged.

### Verification run for this follow-up

```
make generated-data-active-heal-check            # PASS
make generated-data-cap-heal-check               # PASS
make generated-data-check                        # PASS (item cap 0xCD, 206 record(s))
make expansion-modern-idspace-active-check ...   # PASS (incl. desync-recovery leg, real compile)
python3 -m unittest discover -s scripts/generated_data/tests   # Ran 613 tests, OK
make -j4 build/expansion-modern/debug/aapcs/src/data_items.o (from staged desync)  # exit 0, header healed to 0xCD/206
idspace active-heal warm no-op / active-check    # 0.32 s vs 8.10 s (per /usr/bin/time -v)
```
