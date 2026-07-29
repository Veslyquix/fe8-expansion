# Starter features (issue #6 foundation)

Three independent, default-off build flags add an opt-in *runtime/config/hook/QoL*
foundation on top of the existing modern build. Everything here is foundation
only: no generated-content example ships in this sprint (that waits for issue
#10's typed expanded IDs -- see the non-goals below).

Every flag defaults to `0`, so a default build (and the legacy agbcc build,
which never receives the modern `-D` flags) links none of these features and is
byte/behaviour identical to today's ROM.

## Build flags

| `config.mk` (Make) | C macro (`include/expansion_config.h`) | Default | Effect |
|---|---|---|---|
| `EXPANSION_MECHANICS_HOOKS` | `FE8_EXPANSION_MECHANICS_HOOKS` | `0` | Link the public battle-stat mechanics hook registry. |
| `EXPANSION_MECHANICS_SAMPLE` | `FE8_EXPANSION_MECHANICS_SAMPLE` | `0` | Register the bundled sample mechanic. **Requires `EXPANSION_MECHANICS_HOOKS=1`.** |
| `EXPANSION_DANGER_OVERLAY_MENU` | `FE8_EXPANSION_DANGER_OVERLAY_MENU` | `0` | Expose the player-facing danger/range overlay map-menu surface. |

Opt in on the `make` command line, e.g.:

```bash
make expansion-modern-rom EXPANSION_MECHANICS_HOOKS=1 EXPANSION_MECHANICS_SAMPLE=1
make expansion-modern-rom EXPANSION_DANGER_OVERLAY_MENU=1
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

### Config identity and save format

The three flags are folded into the SHA-256 config-identity fingerprint
(`FE8_EXPANSION_CONFIG_FINGERPRINT`, embedded in every modern ROM's
`ExpansionMetadata`) and appear as explicit fields in the generated
`expansion_build_metadata.json`. Toggling any flag therefore changes the
fingerprint deterministically.

The flags are **diagnostic identity only**. They never touch the save format:
`EXPANSION_SAVE_COMPAT_EPOCH` stays `1`, the `ExpansionSaveMeta`/save-block
layout is unchanged, and the fingerprint is deliberately *not* part of the save
compatibility key -- a flag change can never make an existing save look
incompatible. The embedded `ExpansionMetadata` struct layout is unchanged (no
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

* **No generated-content example -- issue #10 is NOT complete.** Sprint 1
  delivers the mechanics seam and the player QoL overlay only; it ships no new
  chapters, units, classes, items or scripted events, and nothing here should
  be read as content coverage. Content waits for issue #10's typed expanded IDs
  landing on `master`; no unmerged code is copied. See
  `reports/issue6_foundation_evidence.md` for the #10 dependency and the
  read-only monitor SHA. The sample mechanic is content-free by construction --
  it exists solely to exercise the public registration API.
* No raw numeric content IDs, no second router, no range-math rewrite, no
  UI/convoy/debug-editor growth, no persisted option, no save-epoch bump.
