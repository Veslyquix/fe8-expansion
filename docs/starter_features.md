# Starter features (issue #6)

Four independent, default-off build flags add an opt-in
*runtime/config/hook/QoL/content* starter surface on top of the existing modern
build. Sprint 1 delivered the mechanics seam and the player QoL overlay;
Sprint 2 adds the bundled **generated-data content example** now that issue
#10's typed expanded item IDs are on `master`.

Every flag defaults to `0`, so a default build (and the legacy agbcc build,
which never receives the modern `-D` flags) links none of these features and
keeps vanilla behaviour.

## Build flags

| `config.mk` (Make) | C macro (`include/expansion_config.h`) | Default | Effect |
|---|---|---|---|
| `EXPANSION_MECHANICS_HOOKS` | `FE8_EXPANSION_MECHANICS_HOOKS` | `0` | Link the public battle-stat mechanics hook registry. |
| `EXPANSION_MECHANICS_SAMPLE` | `FE8_EXPANSION_MECHANICS_SAMPLE` | `0` | Register the bundled sample mechanic. **Requires `EXPANSION_MECHANICS_HOOKS=1`.** |
| `EXPANSION_DANGER_OVERLAY_MENU` | `FE8_EXPANSION_DANGER_OVERLAY_MENU` | `0` | Expose the player-facing danger/range overlay map-menu surface. |
| `EXPANSION_STARTER_CONTENT` | `FE8_EXPANSION_STARTER_CONTENT` | `0` | Link the bundled generated-data content example. **Requires `EXPANSION_MECHANICS_HOOKS=1` and `FE8_ITEM_ID_CAP >= 0xCE`.** |

Opt in on the `make` command line, e.g.:

```bash
make expansion-modern-rom EXPANSION_MECHANICS_HOOKS=1 EXPANSION_MECHANICS_SAMPLE=1
make expansion-modern-rom EXPANSION_DANGER_OVERLAY_MENU=1
FE8_ITEM_ID_CAP=0xCE make expansion-modern-rom \
    EXPANSION_STARTER_CONTENT=1 EXPANSION_MECHANICS_HOOKS=1
```

### Validation

`scripts/modernize/expansion_config.py` validates every flag before any modern
compile or link:

* each flag must be exactly `0` or `1`; `-1`, `2`, and non-numeric text each
  fail with a specific, actionable message;
* `EXPANSION_MECHANICS_SAMPLE=1` with `EXPANSION_MECHANICS_HOOKS=0` is a hard
  error (the sample is registered *through* the registry, which is not linked
  when hooks are off). The same relationship is a compile-time `#error` in
  `include/expansion_config.h` as defence in depth.
* `EXPANSION_STARTER_CONTENT=1` carries **two** dependencies, each rejected
  with its own actionable message and each also a compile-time `#error`:
  * `EXPANSION_MECHANICS_HOOKS=1` (`include/expansion_config.h`) -- the
    bundled content mechanic is registered through the same public registry;
  * an active item ID cap that actually reaches `ITEM_EXPANSION_CE`
    (`include/expansion_starter_content.h`, which owns the `id_space.h`
    include). `modern.mk` passes the build's live `FE8_ITEM_ID_CAP` to
    `expansion_config.py` as `--item-id-cap`, so Python, Make and C all fail
    the same way.

  The dependency is deliberately **one-way**: nothing in the issue #10
  ID-space platform depends on this flag, so an expanded-cap build with
  `EXPANSION_STARTER_CONTENT=0` is still a valid, independently testable
  platform build at any cap.

### Config identity and save format

All four flags are folded into the SHA-256 config-identity fingerprint
(`FE8_EXPANSION_CONFIG_FINGERPRINT`, embedded in every modern ROM's
`ExpansionMetadata`) and appear as explicit fields in the generated
`expansion_build_metadata.json`. Toggling any flag therefore changes the
fingerprint deterministically.

The flags are **diagnostic identity only**. None of these four flags touches
the save format: flipping any of them never changes `EXPANSION_SAVE_COMPAT_EPOCH`
or the `ExpansionSaveMeta`/save-block layout, and the fingerprint is deliberately
*not* part of the save compatibility key -- a flag change can never make an
existing save look incompatible. (`EXPANSION_SAVE_COMPAT_EPOCH` itself has since
been bumped independently, `1` -> `2`, by issue #18 sprint 2's unrelated
`struct ExpansionUserPrefs` change -- see `docs/save_format.md` and
`docs/migration_registry.md` for its current value/history; that bump has
nothing to do with, and was not caused by, any flag documented on this page.) The embedded `ExpansionMetadata` struct layout is unchanged (no
new bitmask), so `verify_rom_header.py` needs no layout change.

## Public mechanics hook registry

`include/expansion_mechanics.h` + `src/expansion_mechanics.c`. A small,
fixed-capacity registry that lets a contributor extend the vanilla battle-stat
computation through one narrow, typed seam instead of hand-editing
`src/bmbattle.c`. It shares no storage, router, or menu wiring with the
debug-tools registry.

### API contract

```c
enum ExpansionMechanicsResult ExpansionMechanicsRegister(
    const char* key, const char* label,
    ExpansionMechanicsBattleStatFunc callback);

int         ExpansionMechanicsCount(void);
const char* ExpansionMechanicsKeyAt(int index);   /* NULL out of range */
const char* ExpansionMechanicsLabelAt(int index); /* NULL out of range */
enum ExpansionMechanicsResult ExpansionMechanicsLastResult(void);
int         ExpansionMechanicsIsApplying(void);
void        ExpansionMechanicsReset(void);
void        ExpansionMechanicsInstallBuiltins(void);
void        ExpansionMechanicsApplyBattleStats(
                struct BattleUnit* subject,
                const struct BattleUnit* opponent, u16 battleConfig);
```

The callback is fully typed -- a mutable `struct BattleUnit* subject` plus a
read-only `struct ExpansionMechanicsContext` (const opponent + `BATTLE_CONFIG_*`
flags). No `void*` and no raw item/character IDs ever cross the boundary.

| Property | Contract |
|---|---|
| Capacity | `EXPANSION_MECHANICS_MAX = 8`; the ninth register returns `ERR_CAPACITY`. |
| Order | Deterministic registration (append) order; `KeyAt`/`LabelAt` expose it. |
| Errors | Distinct codes: `DISABLED` / `NULL_ARG` / `KEY_LENGTH` / `LABEL_LENGTH` / `DUPLICATE` / `CAPACITY` / `REENTRANT`. On any non-OK code the registry is unchanged. |
| Lifetime | `key`/`label` are copied into fixed internal buffers, so the caller's strings need not outlive the call. Both must be non-empty and NUL-terminate within `EXPANSION_MECHANICS_KEY_SIZE` (24) / `_LABEL_SIZE` (32). |
| Reentrancy | Registration during an apply is rejected (`ERR_REENTRANT`); a mechanic cannot grow the table it is being walked from. |
| Disabled | With `HOOKS=0` every entry point is a trivial stub returning `ERR_DISABLED` / a no-op; the always-linked `gExpansionMechanicsProbe` (semantic counters only) stays all-zero. |

### The seam

`ComputeBattleUnitStats()` (`src/bmbattle.c`) calls
`ExpansionMechanicsApplyBattleStats()` exactly once per subject, after every
vanilla base stat is computed and before the effective-stat pass. The call is
wrapped in `#if FE8_EXPANSION_MECHANICS_HOOKS`, so a default/legacy build has
zero references to the seam and computes **identical vanilla battle stats**.
(That is a behaviour/stat-identity claim proven by the host tests and the
default-disabled runtime negatives -- not a claim that the ROM is byte-identical
to any other build. Per `docs/issue-resolution-policy.md` the supported modern
path has no byte-identical requirement, and every build embeds its own commit
and config fingerprint, so ROM bytes legitimately differ.) When enabled,
built-ins are installed on first use and every registered mechanic runs in order.

### Sample mechanic ("Full-HP Guard")

`EXPANSION_MECHANICS_SAMPLE=1` registers -- through the public
`ExpansionMechanicsRegister()` API, never by special-casing a stat -- a generic,
content-free mechanic: when the subject is at full HP it grants exactly `+1`
`battleDefense`, clamped at a cap so the bonus is strictly bounded. It reads
only the subject's own HP (no numeric IDs) and applies in every context
`ComputeBattleUnitStats()` runs in (real combat, UI-forecast simulation, and
arena), so a forecast matches the real bout.

### Extending it

1. Write a `static void MyMechanic(struct BattleUnit* subject, const struct ExpansionMechanicsContext* ctx)` that adjusts `subject`'s already-computed battle stats within bounds.
2. Register it (once, at init) via `ExpansionMechanicsRegister("my.key", "My Label", MyMechanic)`.
3. Gate it behind your own build flag; do **not** edit `ComputeBattleUnitStats()` directly.

## Bundled content example (Sprint 2)

`EXPANSION_STARTER_CONTENT=1` links the framework's one shipped demonstration
that the three public seams compose with **nothing special-cased**:

| Seam | What it contributes |
|---|---|
| **config** | `FE8_EXPANSION_STARTER_CONTENT`, a strict 0/1 flag with the two dependencies above. |
| **data** | The framework-authored item record `ITEM_EXPANSION_CE`, authored in `src/data/items_expansion.json` and emitted into `gItemData[ITEM_EXPANSION_CE]` by the ordinary generated-data pipeline. No generated C is ever hand-edited. |
| **hook** | One mechanic registered through the public `ExpansionMechanicsRegister()` API from the single existing `ExpansionMechanicsInstallBuiltins()` install point. `src/bmbattle.c` is untouched. |

### The authored record

| Field | Value | Why |
|---|---|---|
| `item` | `ITEM_EXPANSION_CE` | The typed, symbolic expansion ID; no raw `0xCE` appears in any issue #6 implementation source. |
| `authoringName` | `"Sample Charm"` | The **original** display name, authored as literal text in the record itself and generated into a build-local, content-profile-only text table (see below). |
| `authoringDescription` / `authoringUseDescription` | original text | Authoring/audit text, emitted only into the generated catalog -- see "What the description does *not* do" below. |
| `nameTextId` / `descTextId` / `useDescTextId` | *unset* (`0`) | The record binds **no** message: a framework-authored record must not append to the shared, Huffman-compressed message table (see below). |
| `weaponType` | `ITYPE_ITEM` | A real non-weapon item, not a blank slot. |
| `attributes` | `IA_UNSELLABLE` | A real, meaningful attribute bit. |
| `maxUses` | `3` | Observable end-to-end: `MakeNewItem()` packs it, so every runtime item halfword is `0x03CE`. |
| `iconId` | `222` | An **existing** icon slot. |

**Copyright hygiene.** No vanilla message index, item name or icon artwork is
reused as a shortcut, and **no new graphics asset is added**: `iconId 222` is
the vanilla data's own unused, purely geometric placeholder tile
(`item_icon_unused_9`, a hollow box with a diagonal cross), chosen
deliberately because it depicts nothing.

**Why the record binds no message.** `texts/texts.txt` is unconditional and
compiles into ONE shared, Huffman-compressed blob (`src/msg_data.c`). Adding
a content-only message therefore re-encodes the text blob of **every** build,
default and feature-free ones included -- a default-identity regression that
an opt-in feature must never cause. An earlier revision of this branch did
exactly that and then re-derived 14 savecompat baselines to match; both are
reverted (see "Policy remediation" in `reports/issue6_closure.md`). The
item's original display text is authored instead through the config-gated
content path described below.

### Config-gated content text

The item's display name is real, original, authored content -- and it costs a
default build exactly nothing:

```
src/data/items_expansion.json          "authoringName": "Sample Charm"
  -> scripts/generated_data/items/content_text.py   (EXPANSION_STARTER_CONTENT=1 only)
     -> build/generated/data/items_expansion_content_text.h    (typed, ItemId-keyed)
        -> src/expansion_starter_content.c : ExpansionStarterContentItemName(ItemId)
           -> src/bmitem.c : GetItemName()  (#if FE8_EXPANSION_STARTER_CONTENT)
```

| Property | Contract |
|---|---|
| Authoring input | The ordinary supported JSON authoring surface. `authoringName` is schema-validated: expansion records only, printable 7-bit ASCII, no surrounding whitespace, bounded length; it may never coexist with a `nameTextId`. |
| Generation | `python3 -m scripts.generated_data content-text` (wired into `generated_data.mk`, with the same FORCE + write-if-changed stamp idiom `FE8_ITEM_ID_CAP` uses, since the flag is an env/config value). At `EXPANSION_STARTER_CONTENT=0` it writes **nothing** and deletes any artifact a previous content build left behind. |
| Generated output | Build-local only (`build/generated/data/`), never committed, never hand-edited. |
| Include path | `modern.mk` adds `build/generated/data` to `-I` **only** in the content profile, so a default build cannot even see the header -- and its compile flags, and therefore its objects, are unchanged. |
| Production read | One narrow, typed, public accessor (`char *ExpansionStarterContentItemName(ItemId)`), called from `GetItemName()` -- the single function every item-name consumer (item menu, trade, shop, stat screen, popups, the `[Item]` text substitution) already goes through. `NULL` means "not a content record": the vanilla path runs unchanged. |
| Default build | The accessor is not declared, not defined, not called and not linked; `GetItemName()` preprocesses back to its exact vanilla body. Proven per-object by `tools/gba-playtest/tests/test_expansion_starter_content.py` (no `ExpansionStarterContent*` symbol and no authored bytes in a default `bmitem.o`/content object) and per-ROM by the starter gate's content-disabled artifact negative. |
| Bound | The generated table publishes `EXPANSION_CONTENT_TEXT_NAME_CAPACITY`; the module statically asserts it fits `EXPANSION_STARTER_CONTENT_NAME_BUFFER`, so over-long authoring text is a build error, not a truncated name on screen. |

**What the description does *not* do (honest boundary).** The vanilla
item-description/help UI is addressed **exclusively** by message ID
(`GetItemDescId()` -> the shared message table), and this framework does not
add messages. Building a config-specific message table just for one bundled
example would be a large, risky change to the text pipeline for no framework
value, so it is deliberately out of scope. Consequently:

* the item's `descTextId`/`useDescTextId` stay `0` and its in-game help box
  shows no text -- and **no vanilla description is borrowed** to fake one;
* the authored descriptions are still real, original authoring input: they
  are emitted into the generated audit catalog
  (`build/generated/data/items_expansion_content_text.json`) for
  documentation/review, and are explicitly labelled there as not shown in
  game.

Only the **name** travels the raw-string supported path, because that is the
one production text path a record can feed without a message ID.

### The bundled mechanic

`include/expansion_starter_content.h` + `src/expansion_starter_content.c`.
While the subject carries the bundled item, "Content Sample Evade" grants a
fixed `+5` `battleAvoidRate`, clamped at `120` so the bonus is strictly
bounded. Inventory membership is read with the production accessor
`GetUnitItemSlot()`; the item is named symbolically and held in a typed
`ItemId`.

| Property | Contract |
|---|---|
| Registration | Only through the public `ExpansionMechanicsRegister()`. It never touches the registry's internals. |
| Install point | The one existing `ExpansionMechanicsInstallBuiltins()`. No second router, no second registry. |
| Stat | `battleAvoidRate` -- deliberately **different** from the content-free sample's `battleDefense`, so both are independently observable in one apply and the pre-existing sample keeps its exact previous standalone semantics. |
| Apply-order safety | Reads only the subject's own inventory and its own already-computed stat, never `context->opponent->battle*`, so it is correct under both apply orders. |
| Disabled | The whole translation unit compiles to stubs with **zero** data/bss/rodata, so a default build's RAM layout -- and every committed scenario probe address -- is unchanged. |
| Save format | Untouched. The item ID travels in the existing 14-bit item fields; no new save field, no epoch bump. |

### Runtime evidence

The content example rides the **existing** issue #10 item-expansion gate
(`expansion-modern-itemexpansion-check`) and its existing ROM build -- no
second harness, no second ROM, no extra CI command. `run_item_expansion_checks.py`
reads every expected value from the authored source of truth
(`src/data/items_expansion.json` through the generated-data schema, the
`ITYPE_*`/`IA_*`/`CHARACTER_*` headers, and the content module's own bonus
constants), so ROM-vs-data drift fails the gate.

| Config | Proves |
|---|---|
| debug (`--require-stages all`) | The authored record end to end (`GetItemData`, `MakeNewItem`, event `GIVEITEM`, item menu + stat-screen draw, MultiArena/link, game-save and suspend roundtrips, all carrying `0x03CE`), the **original authored name the production `GetItemName()` returned** (its length and FNV-1a 32 hash, recomputed from `authoringName` -- scalars only, never a pointer), **plus** the content flag, the typed item ID, both mechanics registered through the public API, and the mechanic firing for the item's bearer only. |
| release (`--require-stages boot`) | The item cap and record count actually compiled in, the whole authored record as `GetItemData()` returns it, the content flag, the typed item ID and the public registry's post-install contents -- in a real release ROM. It deliberately does **not** claim a live-map chain: that release limitation predates this work (see `docs/id_space.md`, "Release-configuration limitation"), and the frozen mechanics/QoL runtime proof in a release ROM is carried by the starter runtime scenarios instead. |

The in-run negative control is a second **deployed** unit that never receives
the item: same apply, `+0` avoid, while the content-free sample's `+1` defence
lands on both.

The **content-disabled** negative control needs no extra ROM: the starter
profile ROM (`EXPANSION_MECHANICS_HOOKS/SAMPLE/DANGER_OVERLAY_MENU=1`,
content `0`, vanilla item cap) that the `starter-hook-*` scenarios already
build carries it in both configs:

* the scenarios assert `registerOkCount=1` on that ROM -- exactly one built-in
  registered -- versus `contentMechanicsCount=2`/`contentRegisterOk=2` in the
  content profile, so the registry count itself distinguishes the two; and
* `expansion-modern-starter-hook-check` then asserts, on that same already
  built ELF/ROM, that the content callback and the content name accessor are
  **not linked at all**, that the authored display text appears **nowhere** in
  the ROM image, and that `gItemData` is still the vanilla-cap table.

## Player danger/range overlay

`EXPANSION_DANGER_OVERLAY_MENU=1` promotes the vanilla but previously
unreferenced `MapMenu_DangerZone_UnusedEffect` into a real, player-reachable
map-menu command.

* **Surface**: one gated `gMapMenuItems` entry (`src/menu_def.c`) with an
  original, copyright-free label ("Threat Range") drawn via `def->name`
  (`nameMsgId 0`), the exact pattern the debug hub already uses. The disabled
  build's compiled `gMapMenuItems` object is byte-for-byte the vanilla table
  (asserted on the real compiled object by the host tests -- a table-level, not
  ROM-level, claim); the enabled table adds exactly one `MenuItemDef`, staying
  within `MENU_ITEM_MAX`.
* **Availability / effect contract**: shown and enabled whenever the map menu
  is open. Selecting it closes the menu and enters the danger-range display,
  reusing the existing path unchanged (`PlayerPhase` label `0xC` ->
  `PlayerPhase_DisplayDangerZone` -> `GenerateDangerZoneRange` ->
  `DisplayMoveRangeGraphics`); no range math is rewritten and no second router
  is introduced.
* **Cancel/return**: the vanilla cancel path is untouched, so `B` or a normal
  cancel returns to the map with the cursor and interactivity intact; the entry
  is safe to open and exit repeatedly.
* **No persistence**: the surface is a compile-time build flag only. It
  persists no option bit and no save field.

### QoL semantic probe

`include/expansion_danger_overlay.h` declares a zero-init EWRAM
`gExpansionDangerOverlayProbe` recording semantic counters only (never a
pointer): menu-select count, danger-display count, last nonzero danger-range
tile count, a range-graphics-active flag, and cancel/return count. It is always
linked in every **modern** build -- defined when `FE8_EXPANSION_MODERN_BUILD`
(which `modern.mk` sets for every modern translation unit) *or* the feature
flag is set -- so the modern default/profile ROMs keep the same
`src/playerphase.o` at the same address. The legacy default build (no modern
`-D` flags, feature off) defines it nowhere, so `src/playerphase.o` emits no
`ewram_data` section and cannot become a silent orphan under `ldscript.txt`'s
per-object `ewram_data` enumeration, which does not list `src/playerphase.o`.
Every write is guarded by `FE8_EXPANSION_DANGER_OVERLAY_MENU`, so a
default-disabled *modern* build keeps vanilla `playerphase`/`bmmenu`
**behaviour** while the probe symbol still links (all-zero) for
negative-control scenarios. The default-disabled runtime negatives prove
exactly that: the same clean route reaches the same interactive map with every
probe field 0.

## Runtime evidence

The issue #13 gba-playtest harness is reused (no new framework), and every
committed probe is a semantic scalar -- never a pointer, never a framebuffer or
timing oracle (the pointer-oracle audit reports zero pointer oracles).

### Clean-boot route

The Sprint 1 scenarios reach a **real Prologue battle map through an ordinary
clean boot**: no save/savestate fixture, no debug Fast Boot launcher, no debug
tools, no test-only entry point. The route is the proven title/save-menu
`A`/`START` cadence, `New Game`, one `DOWN` to select **Normal** difficulty, the
first empty slot, then eleven `START` presses on the engine's own event-skip
path (`EventEngine_CanStartSkip`/`EventEngine_StartSkip`, `src/event.c`) through
the intro monologue, the world-map tour and the Prologue opening event. That
reaches player phase turn 1 on the 15x10 Prologue map at frame ~3.4k -- bounded
and deterministic (each scenario is verified twice).

Normal difficulty is proven, not assumed. `SaveMenuWriteNewGame()` maps
Easy/Normal/Difficult to `(isTutorial, isDifficult)` = `(0,0)`/`(1,0)`/`(1,1)`,
and `InitPlayConfig()` stores `isTutorial` in `PlaySt.config.controller`. The
scenarios assert `gPlaySt+0x42 == 0x20` (controller set) **and**
`chapterStateBits`' `PLAY_FLAG_HARD` (`0x40`) clear, which identifies Normal
uniquely.

### Matrix

| Scenario | Config | ROM | Proves |
| --- | --- | --- | --- |
| `starter-danger-overlay-modern-{debug,release}` | both | profile | overlay lifecycle |
| `starter-danger-overlay-negative-modern-{debug,release}` | both | default | probe all-zero |
| `starter-hook-clean-modern-release` | release | profile | hook on real bout |
| `starter-hook-clean-negative-modern-release` | release | default | counters all-zero |
| `starter-hook-modern-debug` (+ negative) | debug | profile/default | Ch4 launcher route |

The QoL positive proves `menuSelectCount`/`dangerDisplayCount` `0 -> 1 -> 2`
over two independent selections, `lastRangeTileCount` **exactly 39** non-zero
`gBmMapRange` tiles on *both* displays, `rangeGraphicsActive` toggling `1 -> 0`
on each `B` cancel, `cancelReturnCount` `0 -> 1 -> 2`, and cursor movement
before and after -- the map stays interactive and the enemy stays 23/23. The
debug and release positives assert **identical** semantics.

The release hook positive rides the same clean route: the Prologue opening event
contains a real scripted bout, so `ComputeBattleUnitStats()` genuinely runs.
Seth (`gUnitArrayBlue[0]`) goes 30/30 -> 13/30 from damage the engine resolved,
with `registerOkCount=1`, `registerErrCount=0`, `applyCount=2`,
`lastAppliedCount=1`, `lastDefenseDelta=+1`, `sampleTriggerCount=2`,
`lastResult=0`. Its negative replays the identical input list on the default
ROM: every counter stays 0 while the bout resolves to the same 30/30 -> 13/30,
proving vanilla battle maths is untouched when the seam is compiled out.

All of it runs from one entry point, `expansion-modern-starter-runtime-check`
(wired into `expansion-modern-linker-check`), which builds the
starter-foundation profile ROM once per `(config, abi)` and reuses it for every
positive scenario. Schema/contract tests:
`tools/gba-playtest/tests/test_starter_clean_route_scenarios.py` and
`test_starter_features_scenarios.py`. Captured counters and the full
per-requirement matrix are in `reports/issue6_foundation_evidence.md`.

### A release-only lock found on the way here

Building this route surfaced a genuine, feature-independent bug: eight
world-map helpers dereferenced `Proc_FindNext()`'s result before the NULL check,
so `arm-none-eabi-gcc -O2` deleted the loop exit and `GmapRmBorder1Exists()`
could only ever return 1. `EventBA_WmRemoveHighlightNationPart2()` then yielded
forever and **any** clean-boot New Game on a modern *release* ROM -- including
the default flags-off ROM -- hard-locked on the world map. It is fixed in
`src/worldmap_rm.c`/`src/worldmap_automu.c` and pinned by
`tools/gba-playtest/tests/test_worldmap_proc_iter_null_guard.py`.

## Safety notes

* Shared C is GNU89/C89-safe (agbcc + modern GCC), no new `//` comments.
* No arbitrary/persisted memory: the only new RAM is the two always-zero EWRAM
  probe structs (semantic counters, never pointers).
* Both probes are diagnostic; disabling the feature keeps them all-zero.

## Non-goals (this sprint)

* **Exactly one content example, and it is an example.** Sprint 2 ships the
  single bundled item + its one mechanic. It ships no new chapters, units,
  classes, scripted events or additional items, and nothing here should be read
  as content coverage. The sample mechanic stays content-free by construction;
  the content mechanic is the only item-aware one.
* No growth UI, no convoy feature, no debug editor, no persisted option, no
  additional QoL surface, no broad rewrite.
* No raw numeric content IDs, no hand-edited generated C, no second
  router/registry/harness, no range-math rewrite, no save field and no
  save-epoch bump caused by this content example (`EXPANSION_SAVE_COMPAT_EPOCH`'s
  current value/history is tracked independently in `docs/migration_registry.md`;
  it was later bumped `1` -> `2` by issue #18 sprint 2, for an unrelated reason).
* No new graphics asset and no reuse of a vanilla message/name/icon design for
  the authored content.

Sprint 1's own foundation evidence stays in
`reports/issue6_foundation_evidence.md`; the Sprint 2 content closure mapping
is `reports/issue6_closure.md`.
