# Debug-tools subsystem (issue #11 closure)

This document is the single reference for the debug-tools subsystem built
for issue #11: a release-safe config gate; a fixed-capacity, hardened
contributor action-registration API (capacity/id/label/callback/reentrancy
all explicitly validated); title/map/prep-screen hub hotkeys; two
deterministic launchers (Chapter 2, and Chapter 4 for reaching a real prep
screen); the Weather/Fog actions; a bounded diagnostics foundation (log
ring + non-fatal assert record); five bounded validated tools (unit,
convoy, flag/chapter, RNG, save-state); and the playtest/host-test evidence
that proves all of it. See `reports/debugtools_issue11_closure.md` for the
frozen-checklist-to-code-to-test closure mapping, and "Remaining #11 scope"
at the end of this document for what otherwise remains (only the true
non-goals -- `mgba_printf`/full debugger/arbitrary memory editor).

## Files

| File | Role |
| --- | --- |
| `include/expansion_debugtools.h` | Public contract: config gate, title/map/prep hotkey masks + compile-time collision guards, registration API, pending-request/bootstrap-suppression API, `struct DebugToolsProbe` |
| `src/debugtools_registry.c` | Registry storage, hub menu construction/diagnostics, title/map/prep hotkey checks, `gDebugToolsProbe` |
| `src/debugtools_launcher.c` | The built-in "Fast Boot: Chapter 2" action: arms/consumes the pending launch request, owns the bootstrap-suppression state and its observer proc |
| `src/debugtools_actions.c` (slice 2) | Built-in Weather/Fog actions: registers each as a bounded one-item submenu whose `MenuItemDef` reuses the dormant `DebugMenu_Weather*`/`DebugMenu_Fog*` functions in `src/bmdebug.c` by pointer, with its own Back/B handling |
| `src/titlescreen.c` | The title-screen hotkey call site (`Title_IDLE`); also detects the pending launch request after the hub closes |
| `src/playerphase.c` (slice 2) | The map-phase hotkey call site: `PlayerPhase_MainIdle` calls `DebugTools_MapHotkeyCheck()` and returns immediately while the hub is active, as its first statements |
| `src/prep_sallycursor.c` (slice 2) | The prep-screen hotkey call site: `PrepScreenProc_MapIdle` calls `DebugTools_PrepHotkeyCheck()` and returns immediately while the hub is active, as its first statements |
| `src/gamecontrol.c` | `GameControl_PostIntro` consumes the pending request exactly once and performs the actual deterministic boot |
| `src/bm.c`, `src/playerphase.c`, `src/soundwrapper.c` | Narrow, one-shot bootstrap-suppression guards on the automatic per-phase suspend-save calls (`BmMain_SuspendBeforePhase`, `PlayerPhase_Suspend`) and the song-room unlock write (`UnlockSoundRoomSong`) |
| `tools/gba-playtest/scenarios/debugtools-hub-modern-{debug,release}.json` | Slice 1 title-hub playtest scenarios (input script + probe expectations) |
| `tools/gba-playtest/scenarios/debugtools-map-hub-modern-debug.json` (slice 2) | Live map-phase hub scenario: opens the hub with the map mask on the real, interactive Chapter 2 map, exercises Weather then Fog, and proves the map stays interactive after the hub closes |
| `tools/gba-playtest/scenarios/debugtools-{map,prep}-hub-modern-release.json` (slice 2) | Release mirrors proving both new hotkeys are compiled out (`gDebugToolsProbe` stays all-zero) atop the live opening world map -- semantic `gPlaySt`/cursor progress probes, no framebuffer oracle |
| `tools/gba-playtest/fingerprints/debugtools-{hub,map-hub,prep-hub}-modern-{debug,release}.json` | Captured fingerprints for the scenarios above |
| `src/debugtools_diag.c` (closure) | Diagnostics foundation: bounded log ring (`DebugTools_LogEvent`/`GetLogEntry`/`GetLogCount`) and non-fatal assert record (`DEBUGTOOLS_ASSERT`/`DebugTools_RecordAssertFailure`) |
| `src/debugtools_tools.c` (closure) | The five bounded validated tools: Unit Inspect (heal-to-full), Convoy Inspect (bounded add), Flag/Chapter (bounded flag toggle), RNG Inspect (bounded reseed), Save State (read-only) |
| `src/gamecontrol.c` (closure) | `GameControl_PostIntro` also consumes the second, independent Ch4-Prep pending request and commits the deterministic Chapter 4 boot |
| `tools/gba-playtest/scenarios/debugtools-ch4-prep-launch-modern-{debug,release}.json` (closure) | The Ch4-Prep launcher's own boot-commit lifecycle scenario + release mirror (see "Fast Boot: Chapter 4 (Prep)" below; the live prep-screen arrival itself is proven by the prep-positive scenario in the next row) |
| `tools/gba-playtest/scenarios/debugtools-ch4-prep-positive-modern-debug.json` (closure) | Live prep-screen arrival (debug-only): drives the Chapter 4 world-map traversal + the real `PREP` opcode to a live `PrepScreenProc_MapIdle`, then fires the SELECT+B prep hotkey; proves `prepScreenObservedCount` 0->1 and `PLAY_FLAG_PREPSCREEN` held throughout. Gate: DEBUG branch of `expansion-modern-debugtools-prep-check` |
| `tools/gba-playtest/tests/test_debugtools_registry.py` + `tools/gba-playtest/tests/c/*.c` | Host tests (see "Host tests" below) |

This feature deliberately does **not** touch `src/bmdebug.c`, `src/uidebug.c`,
or `src/menu_def.c` -- those dormant tools stay unreachable, and the
Weather/Fog actions only ever reference their existing
`DebugMenu_WeatherDraw/Idle`/`DebugMenu_FogDraw/Idle` functions **by
pointer** from `src/debugtools_actions.c`. `src/debugtools_diag.c` and
`src/debugtools_tools.c` (issue #11 closure) follow the identical
by-pointer/never-copy discipline for the engine helpers they call
(`SetUnitHp`, `AddItemToConvoy`, `SetFlag`/`ClearFlag`, `SetLCGRNValue`,
`ClassifySramSaveCompat`, etc. -- see "Five bounded validated tools" below).

## Config gate

`FE8_EXPANSION_DEBUGTOOLS_ENABLED` mirrors issue #8's own
`FE8_EXPANSION_DEBUG`/`NDEBUG` convention exactly:

```c
#ifndef FE8_EXPANSION_DEBUGTOOLS_ENABLED
#define FE8_EXPANSION_DEBUGTOOLS_ENABLED FE8_EXPANSION_DEBUG
#endif
```

- A supported modern **debug** build (`MODERN_CONFIG=debug`, no `-DNDEBUG`,
  `FE8_EXPANSION_DEBUG=1`) enables the subsystem by default.
- A supported modern **release** build (`MODERN_CONFIG=release`, `-DNDEBUG`,
  `FE8_EXPANSION_DEBUG=0`) disables it: every function in
  `src/debugtools_registry.c`/`src/debugtools_launcher.c` compiles to a
  trivial disabled-result stub under `#else /* !FE8_EXPANSION_DEBUGTOOLS_ENABLED */`,
  and the hub menu table (`gDebugToolsHubMenuDef`), every hub-internal static
  function, and the launcher's action body **do not exist in the link at
  all** -- not merely unreachable at runtime. Verified by `nm` on the linked
  release ELF (no `DebugToolsHub_*`/`gDebugToolsHubMenuDef`/
  `DebugToolsLauncher_*` symbols) and by an equivalent host-compiled check
  (`test_registry_disabled_path_behavior_and_symbol_omission`).
- The legacy agbcc build never defines `NDEBUG`, so it keeps compiling with
  the subsystem enabled -- same as every other `FE8_EXPANSION_*` gate today.
  This is not a new or contradictory release model.

`gDebugToolsProbe` (see "Playtest probe surface" below) is the one exception:
it is always linked, in every build, so a release scenario can assert it
stays all-zero for a whole run.

## Registration API

Fits the existing `MenuProc`/`MenuItemDef` engine (`include/uimenu.h`,
`src/uimenu.c`) rather than replacing it:

- `MENU_ITEM_MAX` is 11, and `StartMenuCore` has **no bounds check** when it
  appends to `MenuProc::menuItems` -- writing a 12th live item would corrupt
  adjacent `MenuProc` fields. The hub menu therefore reserves one live slot
  for a Back/Exit entry, leaving exactly `DEBUGTOOLS_ACTION_MAX` (9) slots
  for contributor actions, with 1 of the 11 total live slots kept as an
  untouched safety margin.
- Contributors register through `DebugTools_RegisterAction()` only -- they
  never edit an engine-owned `const MenuItemDef` table. A RAM-resident
  `MenuItemDef` adapter (`sHubMenuItemDefs`, sized
  `DEBUGTOOLS_HUB_MENU_SLOTS = DEBUGTOOLS_ACTION_MAX + 2`) is rebuilt from
  the registry every time the hub opens; raw string labels are supported
  directly (`nameMsgId == 0`, the same path `Text_DrawString` already takes
  for other raw-string menu items -- no text-asset/msg-id involvement).
- The array is fully zeroed before every rebuild, so the first unused slot
  (and everything after it) reads as an all-zero `MenuItemsEnd` -- exactly
  what stops `StartMenuCore`'s scan loop. The reserved Back entry is always
  written at `sHubMenuItemDefs[sActionCount]`, immediately after the last
  registered action; the terminator is the slot after that.
- Storage is a fixed-size EWRAM array (`sActions[DEBUGTOOLS_ACTION_MAX]`) --
  no heap allocation anywhere in this subsystem.
- Registration order is preserved exactly (append-only, no sorting/
  compaction) -- deterministic ordering.

### Result codes

`DebugTools_RegisterAction()` always returns one of `enum DebugToolsResult`;
a registration failure is never silently dropped:

| Code | Meaning |
| --- | --- |
| `DEBUGTOOLS_OK` | Registered successfully |
| `DEBUGTOOLS_ERR_DISABLED` | Subsystem compiled out (release build) |
| `DEBUGTOOLS_ERR_INVALID_ACTION` | `NULL` action pointer, `label`, or `onSelected` |
| `DEBUGTOOLS_ERR_DUPLICATE` | `id` or `label` already registered |
| `DEBUGTOOLS_ERR_CAPACITY_FULL` | `DEBUGTOOLS_ACTION_MAX` (9) already reached |
| `DEBUGTOOLS_ERR_ALREADY_ACTIVE` | `DebugTools_OpenHub()` called while the hub is already open |
| `DEBUGTOOLS_ERR_ID_INVALID` (closure) | `action->id == 0` (reserved/uninitialized-looking sentinel; every shipped action uses ids 1-9) |
| `DEBUGTOOLS_ERR_LABEL_INVALID` (closure) | `label` is empty (`""`) or longer than `DEBUGTOOLS_LABEL_MAX_LENGTH` (24) |

Both closure codes are appended at the **end** of `enum DebugToolsResult` so
every pre-existing named value keeps its original integer -- several
scenario JSON files probe `gDebugToolsProbe.lastRegisterResult` by raw
integer, so no existing value may ever be renumbered. Label validation does
not copy or retain any bytes beyond the pointer itself (`sActions[sActionCount]
= *action` in `src/debugtools_registry.c` still only stores the pointer) --
contributors remain responsible for passing a label with static/persistent
storage duration, which every action in this codebase already does by using
a plain C string literal; the length bound is a rendering/policy contract,
not a lifetime check C89 can perform at runtime. See
`tools/gba-playtest/tests/c/debugtools_registry_label_validation_driver.c`
for the host-executed proof of both new codes (including the exact
boundary: a label of exactly `DEBUGTOOLS_LABEL_MAX_LENGTH` characters is
accepted, one character over is rejected).

`DebugTools_GetLastRegistrationResult()` always mirrors the most recent call.
`gDebugToolsProbe.lastRegisterResult` mirrors the same value for playtest
probes.

### Introspection

`DebugTools_GetRegisteredCount()` / `DebugTools_GetRegisteredAction(index)`
(bounds-checked, `NULL` outside `[0, count)`) let host tests and future
contributor code inspect the registry without touching its internals.

## Diagnostics / visible feedback

Registration/input failures are not silent: `DebugToolsHub_ShowDiagnostics()`
reuses the existing on-screen debug font (`SetupDebugFontForBG`/
`PrintDebugStringToBG`, `src/fontgrp.c` -- the same mechanism already proven
by the dormant debug menus) to print either `"DBGTOOLS ERR <code>"` (last
registration result was not `DEBUGTOOLS_OK`) or `"DBGTOOLS <n>/<max>"` on BG2
every time the hub opens. A full `mgba_printf`/AGB print-protocol
implementation was judged too broad for this slice and is explicitly
deferred (see "Remaining #11 scope"); this on-screen line is the retained,
always-visible feedback mechanism for now.

## Title-screen hub hotkey

Exactly one global hub entry path in this slice: `Title_IDLE`
(`src/titlescreen.c`), the single title-screen-only idle call site,
calls `DebugTools_TitleHotkeyCheck()` once per frame. Default mask is
`SELECT_BUTTON | R_BUTTON`, overridable via
`FE8_EXPANSION_DEBUGTOOLS_HOTKEY_MASK`:

```c
#ifndef FE8_EXPANSION_DEBUGTOOLS_HOTKEY_MASK
#define FE8_EXPANSION_DEBUGTOOLS_HOTKEY_MASK (SELECT_BUTTON | R_BUTTON)
#endif
```

Compile-time guardrails (`#error`, checked unconditionally, even in release
builds, so a misconfigured override is caught at compile time rather than
silently shipped):

- Must not be `0`.
- Must not exactly equal `L_BUTTON | R_BUTTON | A_BUTTON | B_BUTTON` (the
  existing soft-reset combo checked every frame by
  `SoftResetIfKeyComboPressed`, `src/hardware.c`).
- Must not exactly equal
  `A_BUTTON | B_BUTTON | SELECT_BUTTON | START_BUTTON` (the other existing
  soft-reset combo).

The hotkey fires exactly once, on the frame the combo *completes* (at least
one bit of the mask newly pressed while every bit is held) -- not every frame
the combo stays held. Entry is impossible in release builds:
`DebugTools_TitleHotkeyCheck()` compiles to an empty stub (no key read, no
`DebugTools_OpenHub()` call) when the subsystem is disabled.

### Sibling-proc race and `DebugTools_IsHubActive()`

`Title_IDLE` lives inside `gProcScr_GameControl`'s own proc tree
(`src/gamecontrol.c`'s script directly `PROC_CALL`s `StartTitleScreen_WithMusic`).
The hub's menu (`StartOrphanMenu`) is started *from inside* `Title_IDLE`, so
once open, the hub's menu proc and `Title_IDLE` are **independent sibling
procs** under that same tree -- both still read `newKeys` every frame. Without
a guard, an "A" press meant to select a hub action would also be seen, on the
same frame, by `Title_IDLE`'s own unconditional `A_BUTTON | START_BUTTON`
check below it, racing the vanilla title-to-gameplay transition against the
hub action.

`DebugTools_IsHubActive()` (backed by a static flag, set in
`DebugTools_OpenHub`, cleared in the hub's `MenuDef::onEnd`) closes this gap:
`Title_IDLE` returns immediately after the hotkey check for as long as the
hub is active, skipping its own vanilla A/START handling entirely. Always
returns 0 in a release build.

### Reentrancy guard: a repeated hotkey pulse can never spawn a second hub

`DebugTools_OpenHub()` is the single authoritative reentrancy guard for the
whole hub-entry surface: it checks `sHubActive` at the very top, before any
side effect (builtin-action registration, menu-item construction,
diagnostics, `hubOpenCount` increment, or `StartOrphanMenu()`), and returns
`DEBUGTOOLS_ERR_ALREADY_ACTIVE` as a pure no-op if the hub is already open.

This matters because `DebugTools_TitleHotkeyCheck()`'s edge-detection only
requires the mask to be *newly completed* -- releasing and re-pressing
`SELECT + R` while the hub remains open re-triggers `newKeys` exactly the
same as the original press, and therefore calls `DebugTools_OpenHub()` again.
Without the guard, that second call would unconditionally rebuild the menu
and start a second, concurrent `MenuProc` (a real defect reproduced during
review: `hubOpenCount` reached 2 from two separate hotkey pulses at frames
600-606 and 650-656 while the hub was still open from the first). The guard
lives in `DebugTools_OpenHub()` itself -- not duplicated in each caller -- so
every current (`DebugTools_TitleHotkeyCheck`) and future (map/prep) entry
point is protected automatically; a caller never needs its own busy check.

`tools/gba-playtest/scenarios/debugtools-hub-modern-debug.json` and the host
test `test_debugtools_registry.DebugToolsRegistryHostTests
.test_registry_capacity_order_and_errors` both exercise this directly: the
scenario replays two separate hotkey pulses before ever pressing A, and
asserts `hubOpenCount` stays exactly `1` after both; the host test calls
`DebugTools_OpenHub()` three times in a row and asserts the first returns
`DEBUGTOOLS_OK` (count becomes 1) while the second and third both return
`DEBUGTOOLS_ERR_ALREADY_ACTIVE` (count stays 1).

## Map/prep-screen hub entry points (slice 2)

Slice 2 adds two more, equally narrow, entry paths -- one per phase --
both routed through the same `DebugTools_OpenHub()` reentrancy guard
documented above, so no new busy-check is needed at either call site:

```c
#ifndef FE8_EXPANSION_DEBUGTOOLS_MAP_HOTKEY_MASK
#define FE8_EXPANSION_DEBUGTOOLS_MAP_HOTKEY_MASK (SELECT_BUTTON | L_BUTTON)
#endif
#ifndef FE8_EXPANSION_DEBUGTOOLS_PREP_HOTKEY_MASK
#define FE8_EXPANSION_DEBUGTOOLS_PREP_HOTKEY_MASK (SELECT_BUTTON | B_BUTTON)
#endif
```

- `PlayerPhase_MainIdle` (`src/playerphase.c`) calls
  `DebugTools_MapHotkeyCheck()` as its **first** statement, then
  `if (DebugTools_IsHubActive()) return;` immediately after -- before any of
  its own cursor/menu handling runs -- so a triggering keypress can never
  also be seen by the ordinary map controls on the same frame.
- `PrepScreenProc_MapIdle` (`src/prep_sallycursor.c`) follows the identical
  pattern with `DebugTools_PrepHotkeyCheck()`, ahead of
  `HandlePlayerCursorMovement()`.
- Each mask has its own full set of compile-time `#error` guards, checked
  unconditionally (even in release builds): must not be `0`; must not equal
  either existing soft-reset combo (`L+R+A+B` or `A+B+SELECT+START`); must
  not equal bare `R_BUTTON` (map/prep stat screen), bare `L_BUTTON`
  (view-unit swap), or bare `START_BUTTON` (minimap) at that phase; and must
  not equal the title mask nor **each other** -- so no two of the three
  hotkeys can ever be confused for one another by a single keypress.
- Both defaults (`SELECT+L`, `SELECT+B`) are deliberately distinct from the
  title mask (`SELECT+R`) and from each other, and from both existing
  soft-reset combos.
- Both compile to an empty, explicit disabled/release stub -- no key read,
  no `DebugTools_OpenHub()` call -- when the subsystem is disabled, exactly
  like `DebugTools_TitleHotkeyCheck()`.
- Registration remains idempotent regardless of which phase opens the hub:
  `DebugTools_OpenHub()` calls `DebugTools_RegisterBuiltinActions()` then
  `DebugTools_RegisterWeatherFogActions()`, both of which return
  `DEBUGTOOLS_ERR_DUPLICATE` (not a silent no-op, and never a second
  registration) on every subsequent hub open. Total registered actions stay
  well under the fixed capacity of 9 (Chapter 2 launcher + Weather + Fog +
  Back = 4 hub menu items today).

## Weather/Fog debug actions (slice 2)

`src/debugtools_actions.c` is a new file that registers two built-in
actions, id `2` ("Weather") and id `3` ("Fog"), through the same public
`DebugTools_RegisterAction()` API any contributor action uses -- no direct
edits to `gDebugToolsHubMenuDef`/`sHubMenuItemDefs`, `src/bmdebug.c`,
`src/menu_def.c`, or `src/uidebug.c`.

Because registry actions are `onSelected`-only (a single callback fired when
the hub's own menu selects that row), and the dormant `DebugMenu_Weather*`/
`DebugMenu_Fog*` functions in `src/bmdebug.c` are themselves full
`MenuItemDef` callback sets (`onDraw`/`onIdle`), each action's
`onSelected` handler (`DebugToolsActions_WeatherSelected`/
`DebugToolsActions_FogSelected`) opens a **bounded, one-item submenu**
(`StartOrphanMenu` over a single-entry `MenuDef`) whose one `MenuItemDef`
reuses the existing dormant `DebugMenu_WeatherDraw`/`DebugMenu_WeatherIdle`
(or `DebugMenu_FogDraw`/`DebugMenu_FogIdle`) function pointers directly --
the dormant code itself is never edited, copied, or reimplemented. Each
submenu adds its own `B`/Back handling (`onCancel`/the submenu's own "Back"
row) that closes the submenu and reopens the hub via `DebugTools_OpenHub()`,
matching every other hub submenu's `onEnd` convention.

### Two proven, honest, pre-existing dormant-code/data limitations

Both Weather and Fog are visibly **dormant** in practice -- toggling them
produces no on-screen change on Chapter 2 -- for two different, fully
root-caused, pre-existing reasons that this slice does not (and, per its
WHERE constraints, cannot) fix:

- **Weather**: `DebugMenu_WeatherIdle`/`DebugMenu_WeatherDraw`
  (`src/bmdebug.c`) both dereference `Proc_Find(ProcScr_DebugMonitor)`, a
  proc the same file's `DebugMenu_WeatherSelected` (or, here, this slice's
  submenu open) starts via `Proc_Start(ProcScr_DebugMonitor, PROC_TREE_3)`.
  `ProcScr_DebugMonitor`'s own script (`src/bmdebug.c`) is a single
  `PROC_END` command; `Proc_Start()` runs the script synchronously before
  returning, and `PROC_END`'s handler (`ProcCmd_DELETE`, `src/proc.c`) ends
  the proc immediately -- so the proc is created *and* destroyed within the
  same `Proc_Start()` call, before `Proc_Find()` can ever see it non-`NULL`.
  This is a genuine, pre-existing defect in untouchable `bmdebug.c` (the
  identical `ProcScr_DebugMonitor` pattern is also used, and has the same
  effect, in `src/sio_menu.c` and `src/mapanim_debug.c`) -- not something
  this slice introduces or can fix without editing `bmdebug.c`.
- **Fog**: `DebugMenu_FogIdle` (`src/bmdebug.c`) recomputes vision range
  from `GetROMChapterStruct(gPlaySt.chapterIndex)->initialFogLevel` on
  non-skirmish maps. Chapter 2's `initialFogLevel` is `0` in
  `src/data/chapter_settings.h` (a handful of other chapters use `3`) -- so
  toggling fog on Chapter 2 legitimately settles back to its unchanged data
  value. This is pre-existing chapter data, not a code defect.

Both are documented here, proven via the playtest evidence below (probes
stay at their pre-toggle value across a Weather/Fog cycle, exactly as this
root-cause analysis predicts), and left exactly as-is -- fixing either is
out of this slice's WHERE/HOW MUCH ("Weather/Fog... dormant, non-persistent"
was itself given as the reason these two were chosen as safe to expose).

## Deterministic launcher: "Fast Boot: Chapter 2"

An earlier version of this launcher tore down and restarted the whole
`GameCtrlProc` tree (`Proc_EndEach(gProcScr_GameControl)` + `Proc_Start` +
`Proc_Goto(..., LGAMECTRL_EXEC_BM_EXT)`) from inside its own orphan
`MenuProc` `onSelected` callback -- proc-tree lifecycle corruption that hung
later prologue/Chapter 1/Chapter 2 experiments at unrelated event/fade
stages. The launcher is now a three-stage **pending-request handoff**
across the existing proc lifecycle, with no proc torn down or recreated
anywhere:

1. **Hub action arms only a flag** (`src/debugtools_launcher.c`,
   `DebugToolsLauncher_FastBootChapter2`). Selecting "Fast Boot: Chapter 2"
   calls `DebugTools_RequestChapter2Launch()` (idempotent -- a duplicate arm
   changes nothing observable) and returns `MENU_ACT_END` to close the hub.
   It never touches `gProcScr_GameControl`/`gProc_BMapMain`, never calls
   `Proc_EndEach`/`Proc_Start` on the game-control proc, never loads units,
   and never manipulates events.
2. **`Title_IDLE` detects the pending request only after the hub has fully
   closed** (`src/titlescreen.c`): `DebugTools_IsHubActive()` is checked
   (with an early return while still active) strictly before
   `DebugTools_IsChapter2LaunchPending()`. When pending, it reacts with the
   exact same `SetNextGameActionId(GAME_ACTION_EVENT_RETURN); Proc_Break(proc);`
   pair the ordinary `A`/`START` branch uses -- the normal fade/end/
   parent-unblock lifecycle of this `TitleScreen` proc runs completely
   unmodified. No `A`/`START` keypress is ever synthesized.
3. **`GameControl_PostIntro` consumes the request exactly once**
   (`src/gamecontrol.c`), before its ordinary `StartSaveMenu` branch:
   `DebugTools_ConsumePendingChapter2Launch()` gates a branch that seeds a
   fixed deterministic RNG (`SetLCGRNValue(DEBUGTOOLS_FASTBOOT_RNG_SEED)` +
   `InitRN`), reuses the same `InitPlayConfig`/`ResetPermanentFlags`/
   `ResetChapterFlags`/`InitUnits` bootstrap sequence
   `GameControl_InitTutorialGame` uses (`CHAPTER_MODE_COMMON`, non-tutorial),
   sets `gPlaySt.chapterIndex`/`proc->nextChapter = CHAPTER_L_2`, calls
   `GmDataInit()`, places the world-map party at `NODE_CASTLE_FRELIA` (the
   same rest stop the normal Chapter 1 -> Chapter 2 progression passes
   through -- `GmDataInit()` otherwise defaults to `NODE_BORDER_MULAN`, the
   Prologue's own rest node, and the ordinary `LGAMECTRL_EXEC_BM` path's own
   `WorldMap_CallBeginningEvent` unconditionally recomputes `chapterIndex`
   from the party's node, so without this the chapter set above would be
   silently overwritten back to the Prologue), arms the one-shot
   persistent-write suppression (`DebugTools_ArmBootstrapSuppression()`),
   and finally `Proc_Goto(proc, LGAMECTRL_EXEC_BM)` -- the **ordinary**
   proc-script state, on the **same** `GameCtrlProc` that has been running
   since boot. No proc tree is torn down or recreated, and no
   chapter-specific event/battle logic is bypassed: the real
   `EventScr_Ch2_BeginningScene`, the real interactive world map (including
   the player's own `L`-cursor-jump + `A`-node-confirm navigation to Ide),
   and the real Chapter 2 battle map all run completely unmodified from this
   point on.

### One-shot persistent-write suppression

Between the boot committing (`DebugTools_ArmBootstrapSuppression()`) and the
first stable Player Phase, a small **singleton** bootstrap observer proc
(`DebugToolsObserver_WaitForStablePlayerPhase`, `PROC_TREE_3`,
`src/debugtools_launcher.c`) is responsible for clearing the suppression
flag. `DebugTools_ArmBootstrapSuppression()` is idempotent: it first calls
`DebugTools_CleanupBootstrapObserver()` to end any stale observer/flag from a
prior, possibly-abandoned run, and only then `Proc_Start`s exactly one new
observer -- so repeated arming (or arming after an abandoned run) can never
leave two observers alive or a suppression flag stuck from a previous boot.

The observer's own per-frame poll body has exactly **two** termination
branches, each ending via `Proc_Break(proc)`:

- **success** -- `gPlaySt.faction == FACTION_BLUE && Proc_Find(gProcScr_PlayerPhase)
  != NULL` (first stable Player Phase reached), or
- **timeout** -- `DEBUGTOOLS_BOOTSTRAP_OBSERVER_TIMEOUT_FRAMES` (21600 frames,
  safely above any normal Chapter 2 boot-to-interactive duration) elapses
  without success, guaranteeing suppression can never be stuck on forever
  even if the boot hangs or the Player Phase is never reached.

A **third**, event-driven path handles returning to the title screen before
the boot completes (e.g. the player cancels out): `src/titlescreen.c`'s three
`StartTitleScreen_*` functions (`_WithMusic`, `_FlagFalse`, `_FlagTrue` --
the only call sites that ever (re)start `gProcScr_TitleScreen` as a blocking
child of `gProcScr_GameControl`) each call
`DebugTools_NotifyTitleScreenStarting()`, a no-op unless suppression is
active. This is deliberately **not** implemented as a `Proc_Find
(gProcScr_TitleScreen)` poll inside the observer: `FreeProcess` (`src/proc.c`)
never clears a freed proc's `proc_script` pointer, so a `Proc_Find` scan can
report a stale, already-ended proc's slot as a false-positive match on the
very frame it naturally ends -- which is exactly what happens to the real
`TitleScreen` proc around the time the observer starts. An earlier revision
of this feature used that poll and it produced a real regression (the
observer cleared suppression almost immediately, letting
`BmMain_SuspendBeforePhase` write mid-boot and stall Chapter 2 progression).
The direct function-call notification has no such staleness window.

All three termination paths funnel through a single end callback
(`DebugToolsObserver_OnEnd`, installed via `PROC_SET_END_CB`) that
unconditionally clears `sBootstrapSuppressionActive` -- so every way the
observer can stop (its own `Proc_Break`, or an external
`DebugTools_CleanupBootstrapObserver()` call) clears suppression exactly the
same way; there is exactly one place in the code that clears the flag. The
observer never redirects `gProcScr_PlayerPhase`, `gProc_BMapMain`, or any
other proc.

While suppression is active, `DebugTools_IsBootstrapSuppressionActive()`
gates three otherwise-unconditional automatic persistent-write call sites
that would otherwise fire during the deterministic boot's own opening
NPC-phase-into-Player-phase transition (proven necessary empirically: without
all three, the whole-SRAM hash changes between the pre-launch and
first-interactive checkpoints even though the boot performs no *user-visible*
save action):

- `BmMain_SuspendBeforePhase` (`src/bm.c`) -- the automatic suspend-save at
  the start of every battle-map phase.
- `PlayerPhase_Suspend` (`src/playerphase.c`) -- the analogous automatic
  suspend-save at the very start of every Player Phase (`PROC_LABEL(0)` of
  `gProcScr_PlayerPhase`), which runs before the observer proc above can
  possibly have cleared suppression on the same frame `gProcScr_PlayerPhase`
  first exists.
- `UnlockSoundRoomSong` (`src/soundwrapper.c`) -- the sound-room-unlock SRAM
  write triggered by songs that play during the boot sequence.

Outside this narrow one-shot boot window (before it's armed, and forever
after the observer clears it), all three call sites behave exactly as
before -- ordinary user-triggered Suspend saves and song-room unlocks are
never suppressed. `src/playerphase.c`'s guard is a deliberate, narrowly-
scoped extension of the same pattern already used by `src/bm.c`/
`src/soundwrapper.c`: it was not part of this feature's original allowed-file
list, but is required to satisfy the hard "zero SRAM diff" bar below --
without it, `PlayerPhase_Suspend`'s own unconditional write is reachable
inside the suppression window on any deterministic Chapter 2 boot that
reaches a real Player Phase at all (which this one always does).

## Playtest evidence

No existing scenario/fingerprint in this repository used address-based
probes before this slice -- every prior scenario relied solely on
`framebuffer_hash`/`sram_hash`. `struct DebugToolsProbe` (always linked, both
builds, zero-initialized EWRAM) is the new stable state-evidence surface:

```c
struct DebugToolsProbe
{
    u32 hubOpenCount;
    u32 registeredActionCount;
    u32 lastRegisterResult;         /* enum DebugToolsResult */
    u32 launcherArmed;              /* DEBUGTOOLS_LAUNCHER_ARMED_MAGIC ("DBL1") once the boot commits */
    u32 titleIdleTimerSample;       /* mirrors proc->timer_idle every Title_IDLE frame */
    u32 pendingLaunchRequest;       /* DEBUGTOOLS_LAUNCH_REQUEST_MAGIC ("DBL2") while armed, 0 once consumed */
    u32 launchRequestConsumedCount; /* increments once per GameControl_PostIntro consume */
    u32 bootstrapSuppressionActive; /* 1 while the one-shot suppression window is open */
    u32 playerPhaseObservedCount;   /* increments once, on the success termination path */
    u32 bootstrapObserverArmCount;  /* increments once per DebugTools_ArmBootstrapSuppression() call */
    u32 observerTitleReturnCount;   /* increments once per DebugTools_NotifyTitleScreenStarting() cleanup */
    u32 observerTimeoutCount;       /* increments once, on the timeout termination path */
};
extern struct DebugToolsProbe gDebugToolsProbe;
```

`tools/gba-playtest/scenarios/debugtools-hub-modern-{debug,release}.json`
probe this struct directly by its link address (different per
`MODERN_CONFIG` -- confirm with
`nm build/expansion-modern/<config>/aapcs/fireemblem8.elf | grep gDebugToolsProbe`
before touching either scenario). Unlike the shared
`title-progression.json` scenario (only its *fingerprint* path is
`$(MODERN_CONFIG)`-suffixed in `modern.mk`), **both** the scenario and the
fingerprint paths for this check are config-suffixed
(`MODERN_DEBUGTOOLS_SCENARIO`/`MODERN_DEBUGTOOLS_FINGERPRINT`), because the
debug and release scenarios assert genuinely different outcomes (hub really
opens vs. stays permanently absent), not just different addresses for the
same assertion.

### Input timing (why the hotkey pulse is not at frame 0)

Both scenarios replay the identical frame-for-frame input script:

1. The Health & Safety warning screen (`src/opanim-healthsafetyscreen.c`)
   masks all input except the hardcoded `A+B+START+SELECT` unlock combo via
   `SetKeyStatus_IgnoreMask(0x3FF)` until the intro sequence clears it.
2. `Title_IDLE` itself is only reachable after replaying the same
   intro-advance `A`/`START` taps `title-progression.json` already uses
   (its own "early-title-sequence" -> "title-input-progression" ->
   "intro-menu-progression" checkpoints).
3. The hotkey (`SELECT + R`) is pulsed at frame 600, then a **second** time
   at frame 650-656 (reentrancy-guard regression coverage -- see
   "Reentrancy guard" above), before an `A` press at frame 700 selects the
   hub's one entry and arms the pending Chapter 2 launch request.
4. From frame 750 onward, ordinary `A` taps (every 30 frames through the
   `EventScr_Ch2_BeginningScene` dialogue, then every 60 frames through the
   chapter-intro event and opening NPC phase) advance the real, unmodified
   Chapter 2 flow, plus one `L` (world-map cursor jump Castle Frelia -> Ide)
   and one `A` (node confirm) at frames 1650/1700 to enter the real battle
   map, and a final `RIGHT`/`DOWN` pair at frames 14700/14760 proving the
   battle-map cursor responds to ordinary input once the map is interactive.

The debug scenario has 7 checkpoints: a pre-hotkey baseline (frame 300, all
4 basic probes zero), one right after the first hotkey pulse (frame 630,
`hubOpenCount == 1`), one right after the second, repeated pulse (frame 680,
`hubOpenCount` still `== 1` -- the reentrancy regression-proof checkpoint),
`pre-launch` (frame 706, right after the request is armed and the hub
closes -- `pendingLaunchRequest == DEBUGTOOLS_LAUNCH_REQUEST_MAGIC`, whole-
SRAM hash captured), `gamecontrol-consumed-launch` (frame 950,
`launcherArmed == DEBUGTOOLS_LAUNCHER_ARMED_MAGIC`,
`launchRequestConsumedCount == 1`, `bootstrapSuppressionActive == 1`,
`chapterIndex == CHAPTER_L_2`), `chapter2-interactive-stable` (frame 14000,
`bootstrapSuppressionActive == 0`, `playerPhaseObservedCount == 1`, the full
Blue/Green/Red unit roster present by character ID -- Eirika, Seth, Gilliam,
Franz, Moulder, Vanessa in Blue; Ross in Green; Bone + generic Bandits in
Red -- Eirika's `items[0]` low byte `== ITEM_SWORD_RAPIER`, and a whole-SRAM
hash that is **byte-for-byte identical** to `pre-launch`'s, with zero
exclusions), and `post-interactive-cursor-response` (frame 14900, after the
`RIGHT`/`DOWN` taps, proving the battle-map cursor moved -- this checkpoint's
SRAM hash is expected to differ from the first two, since ordinary
suspend-saves are no longer suppressed once past
`chapter2-interactive-stable`).

The **release** scenario (`debugtools-hub-modern-release.json`) replays the
exact same frame-for-frame input (all 259 frame entries, identical to the
debug scenario) against a release build, where the whole debugtools
subsystem is compiled out, so `gDebugToolsProbe` stays all-zero at all 7
checkpoints (the compiled-out proof). It carries **no** framebuffer oracle.
An earlier revision asserted the frozen-screen hash
`fnv1a64-rgb24:d11078d0ec60076d` at its last two checkpoints, but that was
vacuous: the world-map UB (a `Proc_FindNext` NULL-deref the `-O2` release
build mis-optimised into an infinite loop, fixed in `src/worldmap_rm.c` /
`src/worldmap_automu.c`; see `reports/issue6_foundation_evidence.md`) had
frozen the screen, so a frozen-screen hash matched whether or not
debugtools linked -- and once the fix unfroze the screen the hash became a
false negative. Because the debug hotkeys are inert in release, the same
`START`/`A` taps simply drive the vanilla title-to-new-game path into the
game's **live opening world-map sequence**, and the checkpoints now assert
relocation-independent semantic `gPlaySt`/cursor scalars for it:
`chapterIndex` advances from `0x00` (title, frames 300-950) to a real
non-title `0x10` with `faction == 0x40` (NPC phase) and the map cursor
initialised to `0x0e` by frames 14000-14900. That title->world-map
progression is impossible on the pre-fix build (which locked with
`chapterIndex` stuck at `0x00`), so the scenario genuinely **fails on the
frozen build and passes on the fixed one**, instead of passing vacuously on
both. This world-map sequence is the plain vanilla path -- **not** a debug
hub and **not** a real chapter map (`gBmSt`'s tactical main loop is not
active) -- so the release checkpoints were renamed
(`title-idle-preboot-inert`, `title-hotkey-pulse{1,2}-inert`,
`title-a-press-inert`, `newgame-intro-pre-worldmap-inert`,
`worldmap-intro-live-progress`, `worldmap-intro-live-progress-sustained`)
from the old, misleading debug-shaped names.

### Title-idle-timer freeze (`titleIdleTimerSample`)

`gDebugToolsProbe.titleIdleTimerSample` (written every `Title_IDLE` frame by
`DebugTools_RecordTitleIdleTimer()`, the sole writer, mirroring the pattern
used for every other probe field) proves the review-fix MEDIUM defect stays
fixed: `Title_IDLE`'s `proc->timer_idle`/`proc->timer` increment is now
wrapped in `if (!DebugTools_IsHubActive())`, so the counter simply does not
advance for as long as the hub is open, rather than the vanilla `== 815`
attract-mode-transition check merely being skipped *after* the counter has
already sailed past 815 (which would permanently disable the transition for
the rest of that title-screen instance, since the check is an exact
equality against a monotonically increasing value).

`tools/gba-playtest/scenarios/debugtools-timer-freeze-modern-debug.json`
opens the hub once (frame 600-606), holds it open with no further input
across a hub-free run's empirically observed `timer_idle == frame - 477`
crossing of the 815 threshold (around frame 1292), and asserts
`titleIdleTimerSample` is byte-for-byte identical at frame 620 and again at
frame 1290 -- proving it did not advance at all while blocked. It then
closes the hub with a B press (`MenuCancelSelect`'s `MENU_ACT_END` path,
frame 1300-1306) and asserts a higher value at frame 1450, proving idle
progress resumes once the hub closes. `hubOpenCount` is asserted `== 1`
throughout: opening once, holding, and closing must never spawn or require a
second hub. This is the cheaper, explicitly-permitted evidence bar ("at
minimum the timer did not advance while blocked") rather than running all
the way to the actual attract-mode transition.

No release counterpart is needed: `DebugTools_IsHubActive()` compiles out to
a constant `0` in a release build, so the freeze branch in `Title_IDLE` is
provably dead code there, and `debugtools-hub-modern-release.json` already
demonstrates `gDebugToolsProbe` stays all-zero across an equivalent-length
input window.

### Deterministic pre-launch SRAM fixture

`expansion-modern-debugtools-check` (both configs, in `modern.mk`) boots the
hub scenario with `--sram-image` pointing at a generated
`debugtools-current.sav` under `$(MODERN_OUTPUT_DIR)/debugtools-fixtures/`,
instead of genuinely blank SRAM. Without this, `EnsureGlobalSaveInfoLoaded()`
(`src/bmsave-lib.c`) sees `SAVE_COMPAT_EMPTY` on first touch and calls
`BuildCurrentExpansionSaveMeta()`, which stamps the *live*
`FE8_EXPANSION_BUILD_COMMIT` into `ExpansionSaveMeta.buildCommitShort` --
changing the `pre-launch`/`chapter2-interactive-stable` whole-SRAM hashes on
every commit even though the hub scenario deliberately keeps zero
`sram_hash_exclude_ranges` (unlike `savecompat-current.json`, which
normalizes that field away instead). The fixture is generated by
`tools/gba-playtest/tests/sram_fixture.py write-deterministic-current
<path>`: it builds a `SAVE_COMPAT_CURRENT` image identical to the ordinary
`STATE_CURRENT` fixture except `buildCommitShort` is overridden to a fixed
sentinel (`00000000`) with the checksum recomputed, so SRAM already
classifies as non-empty and `BuildCurrentExpansionSaveMeta()` never runs.
The resulting whole-SRAM hash is therefore stable across commits by
construction -- no binary fixture is committed to the repository. It is a
normal `modern.mk` build-tree file target (`MODERN_DEBUGTOOLS_SRAM_FIXTURE`):
generated once under `build/` and then cached, and only regenerated when
missing or when one of its declared prerequisites changes --
`sram_fixture.py` itself, its real generation-logic imports
(`scripts/modernize/save_format_tool.py`,
`scripts/modernize/expansion_config.py`,
`scripts/modernize/tests/test_save_format_tool.py`), or `config.mk`. Both
configs of `expansion-modern-debugtools-check` are seeded with it (the
release scenario's own fingerprint is unaffected, since it has no
`sram_hash` checkpoints to begin with); `expansion-modern-debugtools-timer-check`
is deliberately NOT seeded, since that scenario never observes SRAM either
and seeding it would only add unnecessary WipeSram-timing risk for zero
benefit.

### Regenerating scenario/fingerprint files

```sh
python3 tools/gba-playtest/gba_playtest.py capture \
  --rom build/expansion-modern/<debug|release>/aapcs/fireemblem8.gba \
  --scenario tools/gba-playtest/scenarios/debugtools-hub-modern-<config>.json \
  --sram-image build/expansion-modern/<debug|release>/aapcs/debugtools-fixtures/debugtools-current.sav \
  -o tools/gba-playtest/fingerprints/debugtools-hub-modern-<config>.json
```

The timer-freeze scenario (debug-only) is regenerated the same way:

```sh
python3 tools/gba-playtest/gba_playtest.py capture \
  --rom build/expansion-modern/debug/aapcs/fireemblem8.gba \
  --scenario tools/gba-playtest/scenarios/debugtools-timer-freeze-modern-debug.json \
  -o tools/gba-playtest/fingerprints/debugtools-timer-freeze-modern-debug.json
```

Then verify:

```sh
make expansion-modern-debugtools-check MODERN_CONFIG=<debug|release> PREFIX=arm-none-eabi-
make expansion-modern-debugtools-timer-check MODERN_CONFIG=<debug|release> PREFIX=arm-none-eabi-
```

`expansion-modern-debugtools-check` and `expansion-modern-debugtools-timer-check`
are both wired into `expansion-modern-linker-check` alongside
`expansion-modern-boot-check`/`-title-check`/`-savefmt-check`, so the
existing CI linker-check workflow picks them up without any workflow-file
edit. `expansion-modern-debugtools-timer-check` is a documented no-op (a
printed skip message, not a missing/skipped-silently check) for
`MODERN_CONFIG=release`.

### Map/prep hub playtest evidence (slice 2)

`tools/gba-playtest/scenarios/debugtools-map-hub-modern-debug.json` (13
checkpoints, debug-only, live) reuses the same intro/Chapter-2-launch prefix
as the title hub scenario, then once Chapter 2's map is interactive: pulses
the *map* hotkey mask twice (reentrancy-guard proof, same pattern as the
title hub), selects the Weather action, cycles it through
`DebugMenu_WeatherEffect`/`Idle`/`Draw` and asserts the underlying weather
state actually changes, returns (`B`) to the action list, selects Fog,
cycles it and asserts the vision/fog state changes, returns again, closes
the hub, and finally proves the battle map is still fully interactive
afterward (cursor move probes identical in shape to the title-hub scenario's
`post-interactive-cursor-response`). This is the concrete evidence that
Weather/Fog are reachable and functional through the registry-backed
adapters in `src/debugtools_actions.c`, and that opening/closing the map hub
never desyncs ordinary map-phase input handling.

`debugtools-map-hub-modern-release.json` and
`debugtools-prep-hub-modern-release.json` are release-mirror scenarios: each
replays `debugtools-hub-modern-release.json`'s own exact input script
verbatim, then appends a hotkey tail (map mask + `B`/direction taps, or prep
mask + `B`/direction taps respectively). In a release build the map/prep
hotkey masks are compiled out, so `gDebugToolsProbe` -- including the
prep-specific `pendingCh4PrepLaunchRequest`/`ch4PrepLauncherArmed`/
`ch4PrepLaunchRequestConsumedCount`/`prepScreenObservedCount` fields --
stays all-zero across the pulses. These scenarios carry **no** framebuffer
oracle. An earlier revision asserted the frozen-screen hash
`fnv1a64-rgb24:d11078d0ec60076d` at every checkpoint, reasoning the tail
input "changes nothing further"; but that hash was frozen only because the
world-map UB had locked the screen, so it proved nothing about debugtools
being compiled out (and became a false negative once the fix unfroze it).
The shared prefix has already driven the vanilla path into the live opening
world-map sequence (`gPlaySt.chapterIndex == 0x10`, `faction == 0x40` NPC,
map cursor `== 0x0e`); the appended hotkey tail leaves each of those
semantic progress scalars **unchanged** across all four checkpoints, which
is the real proof that the map/prep hotkey tail is inert on top of a
genuinely running, unfrozen world map (the pre-fix build locked here with
`chapterIndex` stuck at `0x00`). **Honest scope:** this release input
reaches the opening world-map cinematic, never a debug hub and never a real
prep screen (`gPlaySt.chapterStateBits` never sets `PLAY_FLAG_PREPSCREEN`);
the checkpoint names reflect that.

A live prep-screen scenario reaching a real, engine-active prep screen is
now **achieved** in this closure via Chapter 4 (see "Fast Boot: Chapter 4
(Prep)" below). `hasPrepScreen` is `FALSE` for all 79 chapters in
`src/data/chapter_settings.h` (a vestigial FE7-only field), but the `PREP`
event-script command (`src/eventscr.c`'s `EventScr_CommonPrep`) is **not**
dead code -- it is genuinely `CALL`ed from many linked, compiled-in chapter
scripts (e.g. `ch4`/`ch5`/`ch6`/`ch7`/`tower`/`ruin`-eventscript.h and
others), so a real prep screen is reachable through ordinary gameplay. This
slice's own launcher was Chapter 2 only, and Chapter 2's own event script
(`src/events/ch2-eventscript.h`) never calls `EventScr_CommonPrep`; the
closure's second launcher targets Chapter 4, whose
`EventScr_Ch4_BeginningScene` does call it, so the live prep screen is
reached deterministically without a chapter-data edit or skirmish selector.
`PrepScreenProc_MapIdle`'s hotkey entry point is added and unit-tested
(call-site ordering, mask collision checks, disabled/release stubs), its
release-mirror scenario proves the hotkey is inert on a release build, and
the live, in-ROM debug playtest proof against a real prep screen is now
provided by `debugtools-ch4-prep-positive-modern-debug.json`.

## Fast Boot: Chapter 4 (Prep) (issue #11 closure)

Chapter 2's own event script (`EventScr_Ch2_BeginningScene`) never calls the
`PREP` event opcode, so the Chapter 2 launcher above cannot exercise
`DebugTools_PrepHotkeyCheck()`/`PrepScreenProc_MapIdle` against a real, live
prep screen -- the gap this repository's docs previously described as
deferred, now closed by the Chapter 4 launcher and the prep-positive
scenario below. `EventScr_Ch4_BeginningScene` (`src/events/ch4-eventscript.h`) is
self-contained (its own `LOAD1`/`LOAD2` ally+enemy unit definitions, no
`CALL` into another chapter's own sub-script) and calls
`CALL(EventScr_CommonPrep)` partway through -- so a second, independent
deterministic launcher targeting Chapter 4 reaches a genuine, unmodified,
engine-driven `PrepScreenProc` (`gProcScr_SALLYCURSOR`) through the real
`PREP` event opcode (`Event3E_PrepScreenCall`, `src/eventscr.c`), not a
hand-rolled substitute.

### Mechanism: a second, independent pending-request pair

`DebugTools_RequestChapter4PrepLaunch()` / `DebugTools_IsChapter4PrepLaunchPending()`
/ `DebugTools_ConsumePendingChapter4PrepLaunch()` (`src/debugtools_launcher.c`)
mirror the Chapter 2 request's exact one-shot arm/pending/consume contract,
entirely independently: arming or consuming one never observably affects
the other (`gDebugToolsProbe.pendingCh4PrepLaunchRequest`/
`ch4PrepLauncherArmed`/`ch4PrepLaunchRequestConsumedCount` are separate
fields from the Chapter 2 request's own). Both share the exact same
`DebugTools_ArmBootstrapSuppression()`/`DebugToolsObserver_WaitForStablePlayerPhase`
machinery -- that machinery was already chapter-agnostic (it only ever
polls `gPlaySt.faction`/`gProcScr_PlayerPhase`, never a specific chapter
index), so no changes were needed there for a second launch target.

`GameControl_PostIntro` (`src/gamecontrol.c`) consumes the Ch4-Prep request
at its own call site, textually after the Chapter 2 branch and before the
ordinary `StartSaveMenu` branch, and commits an equivalent deterministic
boot targeting `CHAPTER_L_4`: the same `InitPlayConfig`/`ResetPermanentFlags`/
`ResetChapterFlags`/`InitUnits`/`GmDataInit` bootstrap, the same fixed debug
RNG reseed, and the same one-shot bootstrap-suppression arming. The only
difference is the world-map placement: `gGMData.units[0].location =
NODE_BORGO_RIDGE` (instead of `NODE_CASTLE_FRELIA`) -- `NODE_BORGO_RIDGE`'s
own `WMLoc_GetNextLocId` resolves to `NODE_ZAHA_WOODS` / `CHAPTER_L_4`
(`src/worldmap_node_data.c`), exactly as `NODE_CASTLE_FRELIA` resolves to
`NODE_IDE` / `CHAPTER_L_2` -- so the ordinary world-map traversal (an `L`
cursor-jump + `A` node-confirm) reaches Chapter 4 without skipping any
chapter-specific event/battle logic, and no chapter-specific event/battle
logic is bypassed.

### Hub menu ordering: Weather/Fog keep their pre-existing row indices

`DebugTools_RegisterChapter4PrepAction()` is registered from its own call in
`DebugTools_OpenHub()`, deliberately **after** `DebugTools_RegisterWeatherFogActions()`
and **not** bundled into `DebugTools_RegisterBuiltinActions()` (which
continues to register only the Chapter 2 launcher, completely unchanged).
An earlier revision of this closure bundled both launchers into one
registration call, which silently shifted Weather (index 1) and Fog (index
2) down by one row -- breaking `debugtools-map-hub-modern-debug.json`'s own
already-proven cursor-navigation input script (it would have landed one row
early after the extra registration). Registering in this order keeps
Weather/Fog at their pre-existing indices 1/2, so every already-committed
map/prep-hub scenario's own input script keeps working unmodified; "Fast
Boot: Ch4 Prep" and the five bounded tools below land at indices 3-8. The
final hub menu order is: Chapter 2 (0), Weather (1), Fog (2), Ch4 Prep (3),
Unit Inspect (4), Convoy Inspect (5), Flag/Chapter (6), RNG Inspect (7),
Save State (8), Back (9) -- exactly `DEBUGTOOLS_ACTION_MAX` (9) actions.

### Playtest evidence and its explicit, honest scope boundary

`tools/gba-playtest/scenarios/debugtools-ch4-prep-launch-modern-debug.json`
(4 checkpoints, live, debug-only) replays the same intro prefix as the
title-hub scenario, pulses the title hotkey once, navigates down three rows
to "Fast Boot: Ch4 Prep", selects it, and proves via `gDebugToolsProbe` that:
the request arms independently (`pendingCh4PrepLaunchRequest ==
DEBUGTOOLS_LAUNCH_REQUEST_MAGIC`), and `GameControl_PostIntro` consumes it
exactly once and commits `gPlaySt.chapterIndex` to `CHAPTER_L_4`
(`ch4PrepLauncherArmed == DEBUGTOOLS_LAUNCHER_ARMED_MAGIC`,
`ch4PrepLaunchRequestConsumedCount == 1`). This is genuine, live-executed
mGBA runtime evidence -- not a host-only or structural proof -- that the
second launcher's pending-request handoff mechanism works end to end on
real emulation, exactly like the Chapter 2 launcher's own
`gamecontrol-consumed-launch` checkpoint.
`debugtools-ch4-prep-launch-modern-release.json` replays the identical
frame-for-frame input and asserts every probe stays `0x00000000`,
confirming the second launcher is compiled out too (mirroring the Chapter 2
release proof).

**Scope of this launch scenario, and the separate positive scenario that
completes it**: `debugtools-ch4-prep-launch-modern-debug.json` deliberately
ends at the boot-commit checkpoint captured above -- it asserts the
pending-request handoff and `gPlaySt.chapterIndex == CHAPTER_L_4`, and does
**not** itself assert `gPlaySt.chapterStateBits & PLAY_FLAG_PREPSCREEN` or
`gDebugToolsProbe.prepScreenObservedCount`. Reaching Chapter 4's actual
live `PrepScreenProc` requires further world-map navigation (an `L`
cursor-jump + `A` node-confirm once the world map becomes interactive)
followed by skipping `EventScr_Ch4_BeginningScene`'s beginning
event/scripted `FIGHT()` battle to its own `CALL(EventScr_CommonPrep)`,
then navigating the prep at-menu. That remaining segment is now proven by a
**separate, enabled** live scenario,
`debugtools-ch4-prep-positive-modern-debug.json` (see "Live prep-screen
arrival" below and `reports/debugtools_issue11_closure.md`), which rests
`gProcScr_SALLYCURSOR` in `PrepScreenProc_MapIdle` and fires the SELECT+B
hotkey there -- so the live prep-screen arrival is achieved, split cleanly
across two focused scenarios.

### Live prep-screen arrival: `DebugTools_PrepHotkeyCheck`'s observation (achieved)

Independently of the launcher above, `DebugTools_PrepHotkeyCheck()`
(`src/debugtools_registry.c`) now observes `gPlaySt.chapterStateBits &
PLAY_FLAG_PREPSCREEN` (`include/types.h`) at the exact moment the prep
hotkey fires, incrementing `gDebugToolsProbe.prepScreenObservedCount` only
when it is genuinely set. `PLAY_FLAG_PREPSCREEN` is set by the real engine
prep-screen lifecycle (`InitPrepScreenUnitsAndCamera`,
`src/prep_sallycursor.c`) for as long as a genuine `PrepScreenProc`
(`gProcScr_SALLYCURSOR`) is active -- so this counter is concrete,
host/runtime-provable evidence *of the hotkey call site itself*: it can
never read nonzero unless the hub was opened while a real, live prep
screen was running. The committed live scenario
`debugtools-ch4-prep-positive-modern-debug.json` now drives a real prep
screen far enough to exercise this path: it observes
`gDebugToolsProbe.prepScreenObservedCount` (`0x02031854`) transition
`0 -> 1` on the SELECT+B hotkey while `gPlaySt.chapterStateBits`
(`0x020210b8`) holds `PLAY_FLAG_PREPSCREEN` (`0x10`), the hub opens
(`hubOpenCount` `0x02031818` `1 -> 2`, `sHubActive` `0x02031614`
`0 -> 1`), a 2nd SELECT+B is idempotent (`hubOpenCount` stays `2`), and the
hub then closes (`sHubActive -> 0`) with prep still live -- a safe return
to prep. The field is always-linked and mirrors every other probe's
zero-by-default contract in a release build.

## Diagnostics: structured probe/log ring + non-fatal assert record (issue #11 closure)

Issue #11 closure requirement 6: "emulator logging/assertion/
crash-diagnostic/memory-inspection foundations". `src/debugtools_diag.c` is
explicitly **not** an `mgba_printf`/AGB-print-protocol implementation,
**not** an interactive debugger, and **not** an arbitrary memory editor --
seethe explicit non-goals in `reports/debugtools_issue11_closure.md`. What
it provides instead:

- **A bounded log ring** (`DEBUGTOOLS_LOG_RING_SIZE` = 8 entries of
  `struct DebugToolsLogEntry { code; a; b; }`) -- `DebugTools_LogEvent(code,
  a, b)` always succeeds; the oldest entry is silently overwritten once
  full (bounded by construction, never a growing allocation).
  `DebugTools_GetLogCount()`/`DebugTools_GetLogEntry(index)` give bounded,
  read-only, index-0-is-most-recent introspection (`NULL`/0 outside
  range). `gDebugToolsProbe.logEventCount` mirrors the unbounded running
  total (proving eviction doesn't stop counting) and
  `gDebugToolsProbe.lastLogCode` mirrors the most recent code.
- **A non-fatal assert record** -- `DEBUGTOOLS_ASSERT(cond, code)` evaluates
  `cond` and, on failure, calls `DebugTools_RecordAssertFailure(code)`:
  increments `gDebugToolsProbe.assertFailureCount`, sets
  `gDebugToolsProbe.lastAssertCode`, and itself appends a
  `DEBUGTOOLS_LOG_ASSERT_FAILURE` ring entry carrying the failing code.
  This **never aborts, crashes, or halts the game** -- every call site in
  `src/debugtools_tools.c` uses the "assert then bail out" idiom (skip the
  mutation, return normally), matching every tool's own safe-return-to-game
  contract. This is the bounded "crash-diagnostic" foundation: a record of
  what would have gone wrong, not a debugger break or a fatal stop.
- **Bounded, read-only, whitelisted introspection** --
  `DebugTools_GetLogEntry`/`DebugTools_GetLogCount`/
  `DebugTools_GetAssertFailureCount`/`DebugTools_GetLastAssertCode` are the
  only read surface; there is no address parameter anywhere in this API,
  so it is structurally impossible to use it as an arbitrary memory reader.

No dedicated hub menu row is spent on a "Diagnostics" viewer: doing so would
have consumed one of the fixed `DEBUGTOOLS_ACTION_MAX` (9) slots (already
exactly filled by the nine actions listed in "Hub menu ordering" above) and
would have changed the hub's own rendered content at moments several
already-committed scenarios assert an exact framebuffer hash. The ring/
assert state is instead exposed purely through `gDebugToolsProbe` fields and
the plain introspection functions above, which is sufficient for both host
tests (`DebugToolsDiagHostTests`, `tools/gba-playtest/tests/test_debugtools_registry.py`)
and future runtime scenarios to assert against.

Every one of the five bounded tools below calls `DebugTools_LogEvent`
for both its inspect and (if applicable) confirm steps, and
`DEBUGTOOLS_ASSERT` immediately before any mutation whose target/index
needs a defensive bounds re-check beyond what its own fixed constant
already guarantees at compile time (the Unit and Flag tools; see below).

Release-inert: every function in `src/debugtools_diag.c` compiles to a
trivial disabled stub (returning 0/`NULL`, recording nothing) when
`FE8_EXPANSION_DEBUGTOOLS_ENABLED` is 0 -- confirmed by `nm` (the disabled
translation unit defines exactly the six public entry points, no
`sLogRing`/`sLogRingTotalWrites` storage at all).

## Five bounded validated tools (issue #11 closure)

Issue #11 closure requirement 5. Each is a single registry action
(`src/debugtools_tools.c`) registered through the same public
`DebugTools_RegisterAction()` API every other action uses -- no direct
edits to `gDebugToolsHubMenuDef`/`sHubMenuItemDefs`. Each samples/displays
read-only state immediately on selection (logged via
`DEBUGTOOLS_LOG_*_INSPECT`), then -- for the four that can mutate anything
-- opens a bounded two-item "Confirm `<action>`" / "Back" submenu (the
exact same `StartOrphanMenu` idiom Weather/Fog already use in
`src/debugtools_actions.c`) so a mutation only ever happens after an
explicit, separate confirmation input, never on the initial hub selection
alone. No tool ever performs a raw/arbitrary address write or accepts an
unvalidated numeric index from outside this one fixed source file: every
target is either a fixed, documented, in-range constant, or produced by an
existing engine lookup helper that itself returns `NULL`/a safe sentinel on
failure, re-checked via `UNIT_IS_VALID`/`DEBUGTOOLS_ASSERT` immediately
before any mutation. None of the five ever touches SRAM or any save-block
struct directly (RNG/flags/units/convoy are ordinary EWRAM runtime state;
the fifth tool is read-only).

1. **Unit Inspect** (id 5) -- target `GetUnitFromCharId(CHARACTER_EIRIKA)`
   (a fixed, well-known character, always present on the Chapter 2 map this
   session's launcher proves; `NULL` when not deployed/present on the
   current map). Inspect samples `GetUnitCurrentHp`/`GetUnitMaxHp` into
   `gDebugToolsProbe.unitInspectLastCurHp`/`unitInspectLastMaxHp`/
   `unitInspectTargetFound`. Confirm re-checks `UNIT_IS_VALID` via
   `DEBUGTOOLS_ASSERT(..., DEBUGTOOLS_ASSERT_UNIT_TARGET_INVALID)`
   immediately before mutating; on a valid target it calls
   `SetUnitHp(unit, GetUnitMaxHp(unit))` (the exact same full-heal idiom
   already used by `src/bmsave.c`/`src/bmio.c`/`src/bmarena.c`/
   `src/eventcall.c`/`src/bmusemind.c`) and `SetUnitStatus(unit, 0)`
   (clears any status ailment), incrementing
   `gDebugToolsProbe.unitHealTransactionCount`. On an invalid/missing
   target, it is a safe, logged (`DEBUGTOOLS_LOG_UNIT_HEAL_SKIPPED_INVALID`),
   assert-recorded no-op -- never a crash, never a mutation of an invalid
   pointer.
2. **Convoy Inspect** (id 6) -- inspect samples `GetConvoyItemCount()` into
   `gDebugToolsProbe.convoyLastItemCount`. Confirm calls
   `AddItemToConvoy(ITEM_VULNERARY)` (a fixed, safe consumable constant);
   `AddItemToConvoy` (`src/bmcontainer.c`) already bounds-checks capacity
   internally and returns `-1` without mutating anything when full -- a
   full convoy is therefore a safe, logged
   (`DEBUGTOOLS_LOG_CONVOY_ADD_SKIPPED_FULL`) no-op, never an overflow.
   A successful add increments `gDebugToolsProbe.convoyAddTransactionCount`.
3. **Flag/Chapter** (id 7) -- inspect samples `gPlaySt.chapterIndex` into
   `gDebugToolsProbe.chapterIndexSample` (read-only) and
   `CheckFlag(DEBUGTOOLS_DEBUG_EVENT_FLAG_ID)` into
   `gDebugToolsProbe.debugFlagLastValue`. `DEBUGTOOLS_DEBUG_EVENT_FLAG_ID`
   (39) is a single fixed, documented, chapter-scoped (never permanent)
   event-flag index, deliberately within `include/constants/event-flags.h`'s
   documented "free"/scratch range (indices 7-40; 0-6 are real gameplay
   flags) and never a caller-supplied index. Confirm re-validates
   `DEBUGTOOLS_DEBUG_EVENT_FLAG_ID < GetChapterFlagBitsSize() * 8` via
   `DEBUGTOOLS_ASSERT(..., DEBUGTOOLS_ASSERT_FLAG_ID_OUT_OF_RANGE)` --
   defense in depth, since `SetFlag`/`ClearFlag` (`src/eventinfo.c`) do not
   themselves bounds-check a chapter-scoped index -- then toggles it
   (`ClearFlag` if currently set, else `SetFlag`), incrementing
   `gDebugToolsProbe.debugFlagToggleCount`.
4. **RNG Inspect** (id 8) -- inspect calls `StoreRNState(seeds)` (`src/rng.c`)
   and samples `seeds[0]` into `gDebugToolsProbe.rngInspectSeedSample0`
   (the real, current LCG/Fibonacci generator state -- never reimplemented).
   Confirm calls `SetLCGRNValue(DEBUGTOOLS_TOOLS_RNG_SEED)` +
   `InitRN(AdvanceGetLCGRNValue())` -- the exact same fixed-reseed idiom
   `GameControl_PostIntro`'s own Chapter 2/4 launchers already use for
   their deterministic boot (`DEBUGTOOLS_TOOLS_RNG_SEED` is a distinct
   constant from `DEBUGTOOLS_FASTBOOT_RNG_SEED`, so the two are never
   confused in logs/tests) -- incrementing
   `gDebugToolsProbe.rngReseedTransactionCount`.
5. **Save State** (id 9) -- **read-only**, no Confirm item at all (nothing
   to confirm): calls `ClassifySramSaveCompat()` (`src/bmsave-lib.c`),
   which only inspects the global save header/expansion metadata record and
   never mutates SRAM or any save-block struct, sampling the result into
   `gDebugToolsProbe.saveCompatLastState` and incrementing
   `gDebugToolsProbe.saveCompatInspectCount`. This tool never calls
   `BuildCurrentExpansionSaveMeta` against a live SRAM target,
   `InitGlobalSaveInfodata`, or any writer -- the safest of the five by
   construction.

### Host-executed evidence

`DebugToolsExtendedToolsHostTests` (`tools/gba-playtest/tests/test_debugtools_registry.py`)
compiles+links+executes the real, unmodified `src/debugtools_tools.c`
together with the real `src/debugtools_registry.c` and `src/debugtools_diag.c`
against `tools/gba-playtest/tests/c/debugtools_tools_driver.c` and
`debugtools_tools_host_stubs.c` (small, test-controllable fakes for the
engine subsystems each tool calls into -- `GetUnitFromCharId`,
`GetConvoyItemCount`/`AddItemToConvoy`, `SetFlag`/`ClearFlag`/`CheckFlag`,
`StoreRNState`/`SetLCGRNValue`/`InitRN`, `ClassifySramSaveCompat` -- mirroring
`GetUnitMaxHp`/`SetUnitHp`/`SetUnitStatus`'s own real, simple clamping logic
from `src/bmunit.c` exactly, so the host test proves real behavioral
semantics, not just call wiring), proving: registration (ids 5-9,
deterministic order, idempotent); each tool's inspect semantics; each
mutating tool's confirm transaction actually applying (and incrementing its
own probe counter exactly once); the two invalid/edge-case paths (missing
Unit target, full Convoy) resulting in a safe, logged, assert-recorded
no-op with the transaction counter unchanged; and Save State's read-only
contract (no Confirm item, `Back` only). A second test compiles the
disabled path and proves both behavior and physical symbol omission -- the
disabled object defines exactly the one no-op
`DebugTools_RegisterExtendedToolActions()` entry point and links clean with
**no** engine/menu/hardware stub of any kind (an undefined reference there
would mean the disabled path grew a real runtime dependency). A live
runtime scenario driving all five tools through the map hub (mirroring
`debugtools-map-hub-modern-debug.json`'s own live Weather/Fog proof) is now
included: `debugtools-tools-modern-debug.json` (gate
`expansion-modern-debugtools-tools-check`, host test
`tools/gba-playtest/tests/test_tools_scenario.py`) drives all five tools live
from the real Chapter 2 map hub, each with an asserted semantic state effect
and a safe return to the hub -- see "Remaining #11 scope" below for the
per-tool mapping. The host-executed evidence above remains the byte-exact
mutation proof (e.g. a wounded unit healed to full) that complements it.


## Host tests

`tools/gba-playtest/tests/test_debugtools_registry.py` (run via
`python3 -m unittest discover -s tools/gba-playtest/tests -v`) exercises the
real, unmodified sources with a native host compiler rather than
re-implementing or pattern-matching their logic. Issue #11 closure added
`DebugToolsDiagHostTests` (log ring/assert record), `DebugToolsExtendedToolsHostTests`
(the five bounded tools), `test_registry_id_and_label_validation` (the two
new `DebugToolsResult` codes), and `DebugToolsCh4PrepLaunchScenarioSchemaTests`
(the Ch4-Prep-launch scenarios) alongside the slice 1/2 classes below --
see "Fast Boot: Chapter 4 (Prep)"/"Diagnostics"/"Five bounded validated
tools" above for what each proves.

- **`DebugToolsRegistryHostTests`** compiles+links+executes the real
  `src/debugtools_registry.c` (enabled path) against a small driver
  (`tools/gba-playtest/tests/c/debugtools_registry_driver.c`) through the
  exact public API (`include/expansion_debugtools.h`), proving: capacity is
  exactly 9, deterministic append order, `NULL`-out-of-range reads,
  duplicate id/label rejection, invalid-action (`NULL` action/label/callback)
  rejection, and capacity-full rejection on the 10th attempt -- all without
  silently dropping a registration or changing the count on a rejected call.
  A second test compiles the same source with
  `-DFE8_EXPANSION_DEBUGTOOLS_ENABLED=0` and proves both behavior (every
  entry point degrades to its disabled stub, `gDebugToolsProbe` stays
  all-zero) and physical symbol omission (`nm` finds no
  `gDebugToolsHubMenuDef`/`DebugToolsHub_*` in the disabled object). Host
  compilation uses only `-I include -I include/generated` -- deliberately
  **not** `tools/agbcc/include`, whose newlib `stdio.h` shadows the system
  one and produces an unresolvable `_impure_ptr` link error against host
  libc.
- **`DebugToolsHotkeyCollisionHostTests`** compiles small snippets against
  the real `include/expansion_debugtools.h`, proving its `#error` guards
  actually fire (zero mask, both reserved soft-reset combos) and that the
  default and a legitimate custom mask still compile cleanly.
- **`DebugToolsOneEntryPathTests`** greps the real sources to prove exactly
  one call site of `DebugTools_TitleHotkeyCheck()` (in `titlescreen.c`) and
  exactly one enabled + one disabled definition, and that
  `bmdebug.c`/`uidebug.c`/`menu_def.c` remain untouched (no `DebugTools_`
  references).
- **`DebugToolsScenarioSchemaTests`** validates both hub scenario JSON files
  against `gba_playtest`'s own schema parser, and asserts the debug/release
  scenarios use the identical (now doubled-pulse) input script while probing
  their own config-specific addresses with complementary (not identical)
  expectations; asserts the debug scenario replays exactly two separate
  `SELECT + R` pulses before the `A` press (the reviewer's exact
  release-and-repress repro shape); and asserts `hubOpenCount` reads `1` at
  the checkpoint right after both the first and the second pulse (the
  critical regression-proof assertion for the reentrancy-guard fix).
- **`DebugToolsTimerFreezeTests`** proves the idle-timer-freeze fix two ways:
  structurally, by grepping `Title_IDLE`'s function body to confirm the
  `DebugTools_IsHubActive()` guard textually precedes, and actually wraps,
  the `proc->timer_idle++` statement (so the increment is truly conditional,
  not merely preceded by an unrelated check); and via the timer-freeze
  scenario's own JSON, parsing `titleIdleTimerSample`'s expected hex values
  as integers to assert the two "hub held open" checkpoints are exactly
  equal (frozen) and the post-close checkpoint is strictly greater (resumed)
  -- reasoning the scenario JSON schema itself cannot express (no relational
  operators), so it is asserted here in the host test instead.
- **`DebugToolsChapter2LaunchLifecycleHostTests`** proves the pending-request
  handoff itself, combining host-executed behavior with link-time and
  structural (comment-stripped, so explanatory prose about what the code
  must *not* do can never itself satisfy or fail an assertion) proofs:
  - `test_launcher_pending_request_lifecycle_host_executed` compiles+links+
    executes the real `src/debugtools_launcher.c` (enabled path) -- driven
    by `tools/gba-playtest/tests/c/debugtools_launcher_driver.c` calling
    the real public API directly -- against
    `tools/gba-playtest/tests/c/debugtools_launcher_host_stubs.c`, which
    instruments (call-counts) `Proc_Start`/`Proc_Find`/`Proc_Break` but
    **deliberately never defines** `Proc_EndEach`, `gProcScr_GameControl`,
    or `gProc_BMapMain` -- so any reference to them anywhere in the linked
    object graph would itself be a link failure, not just a missed
    assertion. It proves: arming the request never calls
    `Proc_Start`/`Proc_Break`; a duplicate arm changes nothing observable;
    consuming is one-shot (`DebugTools_ConsumePendingChapter2Launch()`
    returns true exactly once per arm, then false); consuming an empty
    request is a no-op; arming bootstrap suppression starts exactly one
    proc (the observer); and the whole cycle is re-armable across repeated
    boots.
  - `test_launcher_disabled_path_is_noop` compiles+links+executes
    `tools/gba-playtest/tests/c/debugtools_launcher_disabled_driver.c`
    standalone (no stubs/registry needed) with
    `-DFE8_EXPANSION_DEBUGTOOLS_ENABLED=0`, proving every public
    pending-request/suppression entry point degrades to an inert stub, and
    `nm` confirms the hub-internal symbols are physically omitted.
  - `test_launcher_never_references_gamectrl_or_proc_endeach` and
    `test_gamecontrol_chapter2_boot_never_bypasses_events_or_manually_loads_units`
    grep the real source text (with C comments stripped first) to
    structurally confirm `src/debugtools_launcher.c` never mentions
    `Proc_EndEach`/`gProcScr_GameControl`/`gProc_BMapMain` in code, and that
    `GameControl_PostIntro`'s Chapter 2 boot branch only ever writes
    `gGMData.units[0].location` (the single, documented, ordinary-world-map-
    traversal placement) and no other `gGMData.units[]` field.
  - `test_title_idle_defers_pending_request_check_until_hub_inactive` and
    `test_title_idle_pending_branch_never_synthesizes_input` grep
    `Title_IDLE`'s function body to confirm `DebugTools_IsHubActive()` is
    checked (with an early return) strictly before
    `DebugTools_IsChapter2LaunchPending()`, and that the pending branch
    reacts with the same `SetNextGameActionId`/`Proc_Break` pair the
    ordinary `A`/`START` branch uses, never a synthesized keypress.
  - `test_gamecontrol_consumes_pending_launch_exactly_once_before_savemenu`
    confirms `DebugTools_ConsumePendingChapter2Launch()` is called exactly
    once in `src/gamecontrol.c`, textually before the ordinary
    `LGAMECTRL_EXEC_SAVEMENU` branch.
- **Observer lifecycle-safety host tests** (added after a review gate found
  the original design could leak suppression/observers on an abandoned run)
  drive the same real `src/debugtools_launcher.c` through
  `tools/gba-playtest/tests/c/debugtools_launcher_driver.c` and prove, purely
  via the public API and `gDebugToolsProbe` counters:
  - arming twice in a row starts exactly one observer proc alive at a time
    (`bootstrapObserverArmCount` increments each call, but `Proc_Start`'s
    net-alive-observer count never exceeds one -- the second arm's internal
    `DebugTools_CleanupBootstrapObserver()` ends the first before starting
    the second) and suppression is active after both;
  - an explicit `DebugTools_CleanupBootstrapObserver()` call ends the
    observer and clears `bootstrapSuppressionActive` to false;
  - `DebugTools_NotifyTitleScreenStarting()` is a no-op while suppression is
    inactive, clears suppression (and increments `observerTitleReturnCount`)
    while active, and is safe to call repeatedly;
  - re-arming after a cleanup starts a fresh observer and suppression
    becomes active again (proving the cycle is not a one-shot-forever
    latch).
  - `test_wait_for_stable_player_phase_never_polls_title_screen_via_proc_find`,
    `test_observer_has_exactly_two_poll_termination_conditions_each_ending_via_proc_break`,
    and `test_notify_title_screen_starting_is_a_noop_unless_suppression_active`
    grep the real source text to structurally confirm the observer's poll
    body never references `gProcScr_TitleScreen`/`Proc_Find` for title
    detection (only the success/timeout branches remain, each ending via
    `Proc_Break`), and that title-return detection is exclusively the
    event-driven `DebugTools_NotifyTitleScreenStarting()` no-op-when-inactive
    entry point.
  - `test_titlescreen_calls_notify_title_screen_starting_from_all_three_start_functions`
    greps `src/titlescreen.c` to confirm all three `StartTitleScreen_*`
    functions call `DebugTools_NotifyTitleScreenStarting()` before starting
    `gProcScr_TitleScreen` -- so every real path that (re)shows the title
    screen is covered, not just one.

### Slice 2 host tests: map/prep masks and Weather/Fog actions

- **`DebugToolsMapPrepHotkeyCollisionHostTests`** mirrors
  `DebugToolsHotkeyCollisionHostTests` for the new
  `FE8_EXPANSION_DEBUGTOOLS_MAP_HOTKEY_MASK`/`_PREP_HOTKEY_MASK` guards:
  proves the zero-mask and both soft-reset-combo `#error`s fire for each
  mask, proves each mask's own bare `R`/`L`/`START` collision guard fires
  (the map/prep phases' own vanilla controls), proves both masks reject a
  collision against the title mask, proves the prep mask additionally
  rejects a collision against the map mask, and proves a legitimate custom
  override of either still compiles cleanly.
- **`DebugToolsMapPrepOneEntryPathTests`** mirrors
  `DebugToolsOneEntryPathTests` for the two new call sites: greps for
  exactly one call site each of `DebugTools_MapHotkeyCheck()`
  (`src/playerphase.c`) and `DebugTools_PrepHotkeyCheck()`
  (`src/prep_sallycursor.c`), exactly one enabled + one disabled definition
  of each in `src/debugtools_registry.c`, and -- the WHERE constraint's
  "first statement, immediately returning while hub active" requirement --
  parses `PlayerPhase_MainIdle`'s and `PrepScreenProc_MapIdle`'s function
  bodies to confirm the hotkey check is textually the first statement and
  `DebugTools_IsHubActive()` appears in the guard immediately after it.
  Also re-asserts `bmdebug.c`/`uidebug.c`/`menu_def.c` stay untouched.
- **`DebugToolsWeatherFogActionsHostTests`** compiles+links+executes the
  real, unmodified `src/debugtools_actions.c` (enabled path) together with
  the real `src/debugtools_registry.c` against
  `tools/gba-playtest/tests/c/debugtools_actions_driver.c`, proving:
  idempotent registration of both actions (ids 2/3, "Weather"/"Fog"), the
  combined registry stays within the `DEBUGTOOLS_ACTION_MAX` (9) capacity
  alongside a simulated Chapter-2-launcher-sized filler set, exact
  `MenuDef`/`MenuItemDef` sentinel and `onDraw`/`onIdle`/`onSelected`
  callback wiring for both one-item submenus (reusing the real dormant
  `DebugMenu_Weather*`/`DebugMenu_Fog*` function pointers, never a
  hand-rolled copy), `ProcScr_DebugMonitor` lifecycle ownership (Weather
  starts it only if not already alive and ends it only if this module
  started it; Fog never touches it at all), and Back/`B` returning to the
  hub's action list. A second test compiles the disabled path and proves
  every adapter internal (both static action/menu-item tables, both
  `MenuDef`s, both `*Selected`/`BuildMenuItems`/`OnEnd` functions, the
  monitor-ownership flag) is physically omitted -- the disabled object
  defines exactly the one no-op `DebugTools_RegisterWeatherFogActions()`
  entry point, and links clean with **no** menu/proc/hardware stub at all
  (an undefined reference there would mean the disabled path grew a real
  runtime dependency). A third, structural test greps the real source
  (comments stripped) to confirm it never mentions
  `SaveGame`/`Sram`/`WriteSaveBlock`/`Proc_Break`/`Proc_End`/`Proc_Delete`,
  and that its only `Proc_EndEach` target is `ProcScr_DebugMonitor`. A
  fourth confirms `src/debugtools_actions.o`/`src/debugtools_actions.c`
  are wired into both `ldscript.txt` (legacy) and `modern.mk` (modern).
- **`DebugToolsMapPrepScenarioSchemaTests`** mirrors
  `DebugToolsScenarioSchemaTests` for the three new scenario files:
  validates all three against `gba_playtest`'s schema parser; confirms
  `debugtools-map-hub-modern-debug.json`'s two hotkey pulses reuse the
  same reentrancy-guard shape as the title hub (`hubOpenCount` unchanged
  across the repeated pulse) and that its final checkpoints prove the map
  remains cursor-interactive after the hub closes; confirms both
  `-modern-release.json` mirror scenarios reuse
  `debugtools-hub-modern-release.json`'s own frame script verbatim as a
  prefix (not a hand-authored approximation) and carry no framebuffer
  oracle -- instead asserting all-zero `gDebugToolsProbe` fields plus the
  live world-map semantic progress scalars (`chapterIndex`/`faction`/
  cursor) held constant across the appended hotkey tail (a dedicated
  standing guard,
  `test_release_negatives_forbid_any_framebuffer_and_require_semantic_probes`,
  also rejects any reintroduced framebuffer or pointer oracle); and
  confirms the map/prep masks used in the input scripts match
  the header's actual configured default masks (so the scenario can never
  silently drift from the real compiled-in hotkey).

Test-only fixture sources under `tools/gba-playtest/tests/c/` (stub
implementations of the handful of hardware/menu-engine symbols the
registration logic references but a registration-focused host test never
needs to execute) are never referenced by `modern.mk`/`Makefile` and are not
part of the shipped feature.

## Safety boundaries / extension rules

- Contributors add debug actions **exclusively** through
  `DebugTools_RegisterAction()`. Never edit `gDebugToolsHubMenuDef` or
  `sHubMenuItemDefs` directly, and never add a second title-screen (or any
  other) hotkey call site -- this slice's one entry path is a hard
  constraint, not a starting convention.
- `src/bmdebug.c`, `src/uidebug.c`, and `src/menu_def.c` remain untouched and
  unreachable in this slice. No save/gold/unit/convoy/flag/event/RNG editors
  are exposed.
- No proc is ever torn down/recreated by this feature (no
  `Proc_EndEach`/`Proc_Start` on `gProcScr_GameControl`, no `gProc_BMapMain`
  redirect) -- the hub only arms/consumes a pending-request flag, and both
  `Title_IDLE`'s `Proc_Break` and `GameControl_PostIntro`'s `Proc_Goto` act
  on procs that already exist and keep running their own ordinary
  lifecycle.
- The one-shot bootstrap-suppression window (`src/bm.c`,
  `src/playerphase.c`, `src/soundwrapper.c`) only ever gates the automatic
  per-phase/song-unlock persistent writes that happen to fall inside the
  deterministic Chapter 2 boot's own opening transition; it is armed once
  per boot and is guaranteed to clear via one of three bounded paths: the
  first stable Player Phase, an abandoned run returning to the title screen
  (`DebugTools_NotifyTitleScreenStarting()`), or a timeout safely above any
  normal boot duration -- so no abandoned/failed launch can leave
  suppression (or its observer proc) stuck active for a later, real user
  session. Re-arming is idempotent: it always cleans up any stale
  observer/flag before starting exactly one new one. Outside the
  suppression window, and for every ordinary user-triggered Suspend or song
  unlock, nothing in this slice performs a persistent SRAM write, uses
  wall-clock/time-based state, or introduces nondeterministic RNG.

## Downstream usage: issue #2's deep write -> reload proof

This launcher is the general clean-boot game-state fixture issue #2's
save-format work depended on but did not own. `tools/gba-playtest/
scenarios/savesuspend-resume-modern-debug.json` reuses the hub scenario's
own frames verbatim (Fast Boot: Chapter 2 hotkey -> hub -> launcher) as
its prefix, then drives an ordinary manual Map Menu **Suspend**, a real
**soft-reset** combo, and the ordinary title/save-menu **Resume** path to
prove genuine SRAM write/read persistence through the engine's normal
save paths -- see `docs/save_format.md`'s "Save/load acceptance status"
section for the full proof and probes. This closes issue #2's
previously-deferred write -> reload acceptance gap, and is why the
launcher above stays debug-only rather than release-eligible: release
builds have no equivalent deterministic entry point to drive this
scenario from, so this proof (like the launcher itself) does not exist
for `MODERN_CONFIG=release`.

## Remaining #11 scope (issue #11 closure)

Issue #11's frozen closure checklist is addressed end to end -- see
`reports/debugtools_issue11_closure.md` for the full item-by-item mapping
to code and test/command evidence. The previously-open live prep-screen
arrival is now **achieved** (first bullet). What otherwise remains
explicitly, honestly open is narrow:

- **Live prep-screen arrival -- ACHIEVED.** Both halves are proven live:
  the "Fast Boot: Ch4 Prep" launcher's pending-request/boot-commit
  lifecycle (`debugtools-ch4-prep-launch-modern-debug.json`: the request
  arms independently, `GameControl_PostIntro` consumes it and commits
  `gPlaySt.chapterIndex` to `CHAPTER_L_4`), and the
  world-map-to-prep-screen arrival plus the SELECT+B hotkey
  (`debugtools-ch4-prep-positive-modern-debug.json`, host test
  `tools/gba-playtest/tests/test_prep_positive_scenario.py`). The positive
  scenario does the world-map `L` cursor-jump + `A` node-confirm, skips the
  beginning event/scripted `FIGHT()` battle to `CALL(EventScr_CommonPrep)`,
  rests `gProcScr_SALLYCURSOR` in `PrepScreenProc_MapIdle` and fires SELECT+B
  there: `DebugTools_PrepHotkeyCheck()`'s
  `PLAY_FLAG_PREPSCREEN` observation
  (`gDebugToolsProbe.prepScreenObservedCount`, `0x02031854`) is observed
  `0 -> 1` at runtime while `gPlaySt.chapterStateBits` (`0x020210b8`) holds
  `PLAY_FLAG_PREPSCREEN` (`0x10`), with an idempotent second SELECT+B and a
  safe return to the still-live prep. Gate: the DEBUG branch of
  `expansion-modern-debugtools-prep-check` (RELEASE verifies the
  compiled-out mirror). Debug-only because the launcher + hotkey are
  compiled out of a release build.
- **A live runtime scenario driving all five bounded tools through the map
  hub -- ACHIEVED.** `debugtools-tools-modern-debug.json` (gate
  `expansion-modern-debugtools-tools-check`, host test
  `tools/gba-playtest/tests/test_tools_scenario.py`) reuses the proven Fast
  Boot: Chapter 2 map-hub prefix, opens the real map hub
  (`registeredActionCount == 9`), and drives every tool from its real hub row,
  each with an asserted semantic effect AND a safe hub return (all
  relocation-independent `gDebugToolsProbe`/`gPlaySt`/`gBmSt` scalars):
  Unit inspect resolves Eirika (16/16) then a separate confirm applies
  Heal-to-Full (`unitHealTransactionCount 0 -> 1`; the byte-exact wounded->full
  HP delta stays the host proof since Eirika starts full); Convoy count
  `0 -> 1` across inspect/confirm-add/re-inspect; Flag `0 -> 1` on
  inspect/confirm-toggle (`chapterIndex == 2`); RNG seed `0x0000ee77 ->
  0x0000690b` across inspect/confirm-reseed/re-inspect; Save State classifies
  `SAVE_COMPAT_CURRENT` read-only (inspect count `0 -> 1`, unchanged on Back).
  After the last tool a final `B` closes the hub and the map is still
  interactive (player cursor `0x06 -> 0x07`). The host-executed tests remain
  the byte-exact mutation/invalid-input proof (real, unmodified
  `src/debugtools_tools.c`) that complements the live runtime; the
  config-parametrized release sibling proves the identical input is a
  compiled-out all-zero no-op.
- **A complete `mgba_printf`/AGB debug print-protocol implementation, an
  interactive debugger, and an arbitrary memory editor** remain explicit,
  deliberate non-goals (never attempted) -- see
  `reports/debugtools_issue11_closure.md`'s "Explicit non-goals" section
  for the reasoning. The on-screen BG2 diagnostic line plus the bounded
  log ring/assert record (`src/debugtools_diag.c`) are this subsystem's
  retained, always-visible/queryable substitutes.
- **Migrating the remaining dormant chapter-selector/BGM-commit tools** out
  of `bmdebug.c`/`uidebug.c`/`menu_def.c` into the new registration API
  (Weather/Fog were migrated first; a chapter/skirmish selector specifically
  would also unlock the live-prep-screen gap above) is not part of this
  closure's WHAT and remains available as clearly-scoped future work.
