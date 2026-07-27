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
zero references to the seam -- byte-identical vanilla battle math. When enabled,
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
  table is byte-identical vanilla; the enabled table adds exactly one
  `MenuItemDef`, staying within `MENU_ITEM_MAX`.
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

`include/expansion_danger_overlay.h` declares an always-linked, zero-init EWRAM
`gExpansionDangerOverlayProbe` recording semantic counters only (never a
pointer): menu-select count, danger-display count, last nonzero danger-range
tile count, a range-graphics-active flag, and cancel/return count. Every write
is guarded by `FE8_EXPANSION_DANGER_OVERLAY_MENU`, so the default build keeps
byte-identical vanilla `playerphase`/`bmmenu` behaviour while the probe symbol
still links (all-zero) for negative-control scenarios.

## Runtime evidence

The issue #13 gba-playtest harness is reused (no new framework). See
`tools/gba-playtest/scenarios/starter-hook-modern-debug.json` (+ its negative
control) and `tools/gba-playtest/tests/test_starter_features_scenarios.py`, and
the `expansion-modern-starter-hook-check` Make gate. Captured counters and the
full per-requirement matrix are in `reports/issue6_foundation_evidence.md`.

## Safety notes

* Shared C is GNU89/C89-safe (agbcc + modern GCC), no new `//` comments.
* No arbitrary/persisted memory: the only new RAM is the two always-zero EWRAM
  probe structs (semantic counters, never pointers).
* Both probes are diagnostic; disabling the feature keeps them all-zero.

## Non-goals (this sprint)

* **No generated-content example.** Content (items/characters/generated data)
  waits for issue #10's typed expanded IDs landing on `master`; no unmerged
  code is copied. See `reports/issue6_foundation_evidence.md` for the #10
  dependency and the read-only monitor SHA.
* No raw numeric content IDs, no second router, no range-math rewrite, no
  UI/convoy/debug-editor growth, no persisted option, no save-epoch bump.
