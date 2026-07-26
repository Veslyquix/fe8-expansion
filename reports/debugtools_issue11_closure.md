# Issue #11 closure evidence -- "Phase 4: Productize supported debug tools"

Status: candidate closure evidence for reviewer/verifier. **GitHub issue
#11 is OPEN at time of writing; this report does not close it, and does
not claim any CI run URL or merged state.** It maps every item of this
sprint's frozen closure contract (the WHAT/DONE sections of the task that
produced this commit) to concrete code, tests, and explicit non-goals/
residual risks, so a reviewer can verify closure claim-by-claim. It
supersedes the "Remaining #11 scope" framing in earlier revisions of
`docs/debugtools.md` (slices 1-2 landed on `master` as `bead9606`); this
report covers what changed in *this* closure pass on top of that
foundation.

Run the evidence locally:

```sh
# Host tests (debugtools-focused; run the full suite when time allows)
python3 -m unittest discover -s tools/gba-playtest/tests -v

# Modern debug/release build + link for the affected surface
make expansion-modern-rom PREFIX=arm-none-eabi- MODERN_CONFIG=debug
make expansion-modern-rom PREFIX=arm-none-eabi- MODERN_CONFIG=release

# Runtime scenarios (libmGBA-backed; both configs)
make expansion-modern-debugtools-check           PREFIX=arm-none-eabi- MODERN_CONFIG=debug
make expansion-modern-debugtools-check           PREFIX=arm-none-eabi- MODERN_CONFIG=release
make expansion-modern-debugtools-map-check       PREFIX=arm-none-eabi- MODERN_CONFIG=debug
make expansion-modern-debugtools-map-check       PREFIX=arm-none-eabi- MODERN_CONFIG=release
make expansion-modern-debugtools-timer-check     PREFIX=arm-none-eabi- MODERN_CONFIG=debug
make expansion-modern-debugtools-timer-check     PREFIX=arm-none-eabi- MODERN_CONFIG=release
# prep-check DEBUG branch now runs the live prep-positive scenario
# (debugtools-ch4-prep-positive-modern-debug.json): live prep + SELECT+B
# hotkey. RELEASE branch verifies the compiled-out prep-hub negative.
make expansion-modern-debugtools-prep-check      PREFIX=arm-none-eabi- MODERN_CONFIG=debug
make expansion-modern-debugtools-prep-check      PREFIX=arm-none-eabi- MODERN_CONFIG=release
make expansion-modern-debugtools-ch4prep-check   PREFIX=arm-none-eabi- MODERN_CONFIG=debug
make expansion-modern-debugtools-ch4prep-check   PREFIX=arm-none-eabi- MODERN_CONFIG=release

# Direct verify of the live prep-positive scenario (debug branch of prep-check)
python3 tools/gba-playtest/gba_playtest.py verify \
  --rom build/expansion-modern/debug/aapcs/fireemblem8.gba \
  --scenario tools/gba-playtest/scenarios/debugtools-ch4-prep-positive-modern-debug.json \
  --expected tools/gba-playtest/fingerprints/debugtools-ch4-prep-positive-modern-debug.json \
  --policy behavior
```

## WHAT checklist

### 1. Public action registry: capacity/id/label/callback/inputs/reentrancy validation
- Code: `src/debugtools_registry.c` `DebugTools_RegisterAction()` --
  ordered checks: NULL action/label/`onSelected` ->
  `DEBUGTOOLS_ERR_INVALID_ACTION` (pre-existing); `id == 0` (new) ->
  `DEBUGTOOLS_ERR_ID_INVALID`; empty or over-`DEBUGTOOLS_LABEL_MAX_LENGTH`
  (24, new) label -> `DEBUGTOOLS_ERR_LABEL_INVALID`; duplicate id/label
  (pre-existing) -> `DEBUGTOOLS_ERR_DUPLICATE`; capacity full (pre-existing)
  -> `DEBUGTOOLS_ERR_CAPACITY_FULL`. Both new codes appended at the *end*
  of `enum DebugToolsResult` (`include/expansion_debugtools.h`) so no
  existing scenario-hardcoded raw-integer probe value is renumbered.
  Label lifetime: the registry only ever stores the pointer
  (`sActions[sActionCount] = *action`), never copies bytes; the contract
  (label must have static/persistent storage duration -- every shipped
  action already passes a string literal) is documented at the struct/
  function declaration and re-stated at the result-code table in
  `docs/debugtools.md`. Reentrancy: `DebugTools_OpenHub()`'s pre-existing
  single-authoritative-guard (`DEBUGTOOLS_ERR_ALREADY_ACTIVE`) is
  unchanged and re-verified below.
- Every failure is `DebugTools_GetLastRegistrationResult()`/
  `gDebugToolsProbe.lastRegisterResult`-visible -- no silent drop, for any
  of the six now-distinct codes.
- Tests: `test_registry_id_and_label_validation`
  (`tools/gba-playtest/tests/c/debugtools_registry_label_validation_driver.c`,
  host-executed against the real `src/debugtools_registry.c`) proves
  id==0 rejection, empty-label rejection, one-char-over-limit rejection,
  and exactly-at-limit acceptance (the boundary is inclusive).
  `DebugToolsRegistryHostTests.test_registry_capacity_order_and_errors`
  (pre-existing, still green) covers capacity/order/duplicate/NULL and the
  reentrancy guard (`DebugTools_OpenHub()` called three times in a row:
  first `DEBUGTOOLS_OK`, second/third `DEBUGTOOLS_ERR_ALREADY_ACTIVE`,
  `hubOpenCount` stays 1).
- Evidence command: `python3 -m unittest discover -s tools/gba-playtest/tests -v`
  -> `Ran 196 tests ... OK (skipped=1)` (the one skip is the *legacy*
  agbcc-toolchain-dependent save-compat suite, unrelated to this item --
  see "DONE evidence" below).

### 2. Title/map/prep entry points: debug-safe, release-inert, release+behavior negatives
- Title/map hotkeys and their compile-time collision guards, disabled-path
  stubs, and release symbol omission are pre-existing (slice 1/2) and
  re-verified unmodified by the full host-test run and
  `expansion-modern-debugtools-{check,map-check}` for both configs (see
  commands above; both pass, see "DONE evidence").
- Prep hotkey call site (`DebugTools_PrepHotkeyCheck`,
  `src/debugtools_registry.c`) gained a concrete behavior-proof addition
  this closure: it now observes `gPlaySt.chapterStateBits &
  PLAY_FLAG_PREPSCREEN` at the exact moment it fires, incrementing the new
  `gDebugToolsProbe.prepScreenObservedCount` only when a genuine, live
  `PrepScreenProc` is active. This directly targets the "特别是当前缺失的
  prep debug 行为证明" (prep debug behavior proof) gap named in this
  sprint's brief -- and that gap is now **ACHIEVED**: the live scenario
  `debugtools-ch4-prep-positive-modern-debug.json` drives a genuine,
  engine-active Chapter 4 prep screen and fires SELECT+B there, so
  `prepScreenObservedCount` (`0x02031854`) is observed transitioning
  `0 -> 1` at runtime (see item 3 and "Live prep-screen arrival --
  ACHIEVED" below).
- Release symbol negative: `arm-none-eabi-nm` on the linked release ELF
  shows every `DebugTools_*` symbol as a trivial disabled stub (see
  "DONE evidence" for the exact command/output); `nm` on
  `debugtools_tools.o`/`debugtools_diag.o` (disabled) shows exactly one
  and six public entry points respectively, no internal storage/logic.
- Release *behavior* negative: `debugtools-hub-modern-release.json`,
  `debugtools-map-hub-modern-release.json`,
  `debugtools-prep-hub-modern-release.json`, and (new)
  `debugtools-ch4-prep-launch-modern-release.json` all replay real input
  scripts against a release build and assert every probe stays
  `0x00000000` and the framebuffer is unaffected.
- **Live positive trigger -- ACHIEVED (was the residual here).** The live
  runtime scenario `debugtools-ch4-prep-positive-modern-debug.json`
  (enabled; host test
  `tools/gba-playtest/tests/test_prep_positive_scenario.py`) reaches an
  actually-active prep screen and fires SELECT+B there, so
  `gDebugToolsProbe.prepScreenObservedCount` (`0x02031854`) is observed
  going `0 -> 1` on the hotkey while `gPlaySt.chapterStateBits`
  (`0x020210b8`) holds `PLAY_FLAG_PREPSCREEN` (`0x10`) throughout. The
  call site's compile-time guards, disabled-path behavior, and
  release-negative behavior remain proven as before; the live positive
  trigger is now proven too. This is the DEBUG branch of
  `expansion-modern-debugtools-prep-check` (see item 3 and "Live
  prep-screen arrival -- ACHIEVED" below).

### 3. Fast boot/scenario launcher: safe lifecycle handoff + exactly-once probe/state evidence
- Pre-existing: "Fast Boot: Chapter 2" (`src/debugtools_launcher.c`,
  `src/gamecontrol.c`) -- unchanged, re-verified via
  `expansion-modern-debugtools-check` (both configs) and
  `DebugToolsChapter2LaunchLifecycleHostTests`.
- New: "Fast Boot: Ch4 Prep" -- a second, independent pending-request pair
  (`DebugTools_RequestChapter4PrepLaunch`/`IsChapter4PrepLaunchPending`/
  `ConsumePendingChapter4PrepLaunch`), consumed by `GameControl_PostIntro`
  at its own call site, committing `gPlaySt.chapterIndex` to `CHAPTER_L_4`
  via the identical bootstrap sequence and node-placement idiom as
  Chapter 2's (`NODE_BORGO_RIDGE` -> `WMLoc_GetNextLocId` ->
  `NODE_ZAHA_WOODS`/`CHAPTER_L_4`, mirroring
  `NODE_CASTLE_FRELIA` -> `NODE_IDE`/`CHAPTER_L_2` exactly). See
  `docs/debugtools.md` "Fast Boot: Chapter 4 (Prep)" for the full
  mechanism and its honest scope boundary.
- **Exactly-once, probe-backed evidence (not just menu input)**: live mGBA
  scenario `debugtools-ch4-prep-launch-modern-debug.json` proves, via
  `gDebugToolsProbe` reads (not framebuffer similarity):
  `pendingCh4PrepLaunchRequest == DEBUGTOOLS_LAUNCH_REQUEST_MAGIC` once
  armed, `== 0` once consumed; `ch4PrepLaunchRequestConsumedCount == 1`
  (never double-applies a single arm); `gPlaySt.chapterIndex == CHAPTER_L_4`
  (intended chapter reached); `ch4PrepLauncherArmed ==
  DEBUGTOOLS_LAUNCHER_ARMED_MAGIC` (intended state/phase committed).
  Structural host tests
  (`test_gamecontrol_consumes_pending_ch4_prep_launch_exactly_once_before_savemenu`,
  `test_gamecontrol_ch4_prep_boot_never_bypasses_events_or_manually_loads_units`)
  additionally grep-prove exactly one consume call site, exactly one
  `Proc_Goto(proc, LGAMECTRL_EXEC_BM)` in that branch, no
  `StartBattleMap`/`CallEvent`/`StartEvent`/`EventScr_*` reference, and the
  only `gGMData.units[]` write is the documented `location` field.
- **Live prep-screen arrival -- ACHIEVED (was the residual here).** A
  second, live scenario `debugtools-ch4-prep-positive-modern-debug.json`
  (enabled; host test
  `tools/gba-playtest/tests/test_prep_positive_scenario.py`) continues
  past this launcher's boot-commit: it does the Chapter 4 world-map
  traversal (an `L` cursor-jump + `A` node-confirm), skips the beginning
  event/scripted battle to the real `CALL(EventScr_CommonPrep)` `PREP`
  opcode, navigates the prep at-menu (`B` = "check map" ends the at-menu,
  then `A` on the on-map menu) to rest `gProcScr_SALLYCURSOR` in
  `PrepScreenProc_MapIdle` (`proc_idleCb` reads
  `PrepScreenProc_MapIdle|Thumb = 0x080905d1`), and fires the SELECT+B
  prep hotkey. Proven by exact EWRAM probes (semantic only,
  `framebuffer:false`): `gPlaySt.chapterStateBits` (`0x020210b8`) `== 0x10`
  (`PLAY_FLAG_PREPSCREEN`) throughout the prep; `prepScreenObservedCount`
  (`0x02031854`) `0 -> 1` on SELECT+B; the hub opens (`hubOpenCount`
  `0x02031818` `1 -> 2`, `sHubActive` `0x02031614` `0 -> 1`); a 2nd
  SELECT+B is idempotent (`hubOpenCount` stays `2`, NOT `3`); the hub then
  closes (`sHubActive -> 0`) with prep still live (`chapterStateBits`
  still `0x10`) -- a safe return to prep. Gate: the DEBUG branch of
  `expansion-modern-debugtools-prep-check`; the RELEASE branch is
  unchanged (still verifies the compiled-out mirror
  `debugtools-prep-hub-modern-release.json`). Debug-only because the
  launcher + hotkey are compiled out of a release build.

### 4. Honest treatment of shipped actions (Weather/Fog)
- Unchanged this closure: Weather/Fog (`src/debugtools_actions.c`) already
  carry real state-effect assertions
  (`debugtools-map-hub-modern-debug.json`'s `weather-cycled-twice`/
  `fog-toggled` checkpoints assert the underlying `gPlaySt.chapterWeatherId`/
  vision-range state actually changes) and safe-return-to-game assertions
  (`map-remains-interactive`). Re-verified green by the full host-test run
  and `expansion-modern-debugtools-map-check` (both configs). No
  placeholder/no-op/dormant action is shipped by this closure either (see
  item 5): every one of the five new tools performs a real, real-effect
  mutation (or, for Save State, a real read) through an existing engine
  helper, never a stub.

### 5. Five bounded validated tools
- Code: `src/debugtools_tools.c` -- Unit Inspect (id 5), Convoy Inspect
  (id 6), Flag/Chapter (id 7), RNG Inspect (id 8), Save State (id 9). Full
  mechanism description, safety rationale, and exact engine helpers called
  are in `docs/debugtools.md` "Five bounded validated tools".
- Scope/reference validation: Unit target via `GetUnitFromCharId` +
  `UNIT_IS_VALID` (re-checked at mutation time via `DEBUGTOOLS_ASSERT`);
  Convoy via `AddItemToConvoy`'s own internal capacity bound; Flag id via
  `DEBUGTOOLS_ASSERT(id < GetChapterFlagBitsSize() * 8, ...)`; RNG reseed
  via the same fixed-constant idiom the launchers already use; Save State
  is read-only (no index/target at all).
- Persistent/dangerous mutation only in development debug: all five
  compile out entirely in a release build (`nm` proof below); none writes
  SRAM/a save-block struct (grep-proved,
  `test_extended_tools_never_touch_dormant_files_or_persistent_apis`).
- Host semantic assertions + probe/state evidence + safe return-to-game:
  `DebugToolsExtendedToolsHostTests.test_extended_tools_lifecycle_host_executed`
  compiles+links+executes the real `src/debugtools_tools.c` +
  `src/debugtools_registry.c` + `src/debugtools_diag.c` against
  `debugtools_tools_driver.c`/`debugtools_tools_host_stubs.c`, proving:
  registration order/idempotency; every tool's inspect sampling; every
  mutating tool's confirm transaction actually applying and its own
  `gDebugToolsProbe` counter incrementing exactly once; the Unit
  invalid-target and Convoy-full paths resulting in a safe, logged,
  assert-recorded no-op (transaction counter unchanged, submenu still
  closes cleanly -- "safe return to game"); Save State's read-only
  contract (no Confirm item). A second test proves the disabled path is
  the one no-op entry point with no engine/menu/hardware dependency at
  all.
- Residual (explicit): a *live* mGBA scenario driving all five through the
  real map hub is not included this closure -- the host-executed evidence
  above already exercises the real, unmodified source end to end; see
  "Explicit non-goals / residual risks".

### 6. Emulator logging/assertion/crash-diagnostic/memory-inspection foundations
- Code: `src/debugtools_diag.c` -- bounded log ring
  (`DEBUGTOOLS_LOG_RING_SIZE` = 8), non-fatal assert record
  (`DEBUGTOOLS_ASSERT`/`DebugTools_RecordAssertFailure`), bounded read-only
  introspection (`DebugTools_GetLogEntry`/`GetLogCount`/
  `GetAssertFailureCount`/`GetLastAssertCode` -- no address parameter
  anywhere in this API).
- Actionable: every one of the five tools' mutation call sites logs via
  `DebugTools_LogEvent`, and the two bounds-re-checked tools (Unit, Flag)
  call `DEBUGTOOLS_ASSERT` immediately before mutating.
- Release-inert: `nm` on the disabled `debugtools_diag.o` defines exactly
  the six public entry points, no `sLogRing`/`sLogRingTotalWrites` storage.
- **Explicit non-goals (never implemented, by design)**: `mgba_printf`/a
  full AGB debug-print-protocol; an interactive debugger; an arbitrary
  memory editor (the introspection API has no address parameter at all --
  structurally incapable of being used as one). See "Explicit non-goals /
  residual risks" below for the reasoning.
- Tests: `DebugToolsDiagHostTests` (ring wraparound/eviction/most-recent-
  first ordering, assert-never-fires-on-true, assert-fires-exactly-once-
  per-false, assert-failure-itself-logs-a-ring-entry, disabled-path
  symbol omission).

### 7. gba-playtest tests/scenarios/fingerprints/Make targets extended for #11 only
- New host test classes/drivers: `DebugToolsDiagHostTests`,
  `DebugToolsExtendedToolsHostTests`, `test_registry_id_and_label_validation`,
  `DebugToolsCh4PrepLaunchScenarioSchemaTests`, plus the two mirrored
  `test_gamecontrol_*_ch4_prep_*` structural tests and the extended
  `debugtools_launcher_driver.c` Ch4-Prep lifecycle section. 6 new/updated
  `tools/gba-playtest/tests/c/*.c` fixture files (never referenced by
  `modern.mk`/`Makefile`, matching the pre-existing convention).
- New scenarios/fingerprints:
  `debugtools-ch4-prep-launch-modern-{debug,release}.json` (+ committed
  fingerprints). No existing scenario file's *committed baseline claim*
  was weakened; where existing debug scenarios needed fingerprint
  regeneration (see "Fingerprint regeneration" below), the change is an
  explicit, reviewed re-capture with the reason documented here, not a
  silent refresh.
- New Make targets: `expansion-modern-debugtools-ch4prep-check` (debug:
  seeded with the same `MODERN_DEBUGTOOLS_SRAM_FIXTURE` the title-hub
  check uses, since it shares that scenario's own title-screen prefix;
  release: unseeded, matching every other release mirror), wired into the
  same aggregate/CI target lists `expansion-modern-debugtools-{check,map-check,timer-check,prep-check}`
  already appear in (5 locations in `modern.mk`), and into
  `expansion-modern-boot-preflight`'s implicit dependency chain via the
  same `expansion-modern-rom` prerequisite every sibling check uses.
- Semantic probes, not framebuffer similarity: every new/changed
  assertion in this closure reads a named `gDebugToolsProbe` field or
  `gPlaySt` field by address, never merely a framebuffer hash (framebuffer
  hashes are still captured as an *additional* signal at the same
  checkpoints, matching the pre-existing convention).
- gba_playtest.py/backend.c themselves: **not modified** (out of this
  task's WHERE) -- confirmed by `git diff --stat` showing no changes to
  either file.

### 8. Documentation
- `docs/debugtools.md`: title/intro reframed from "slices 1-2" to "issue
  #11 closure"; new sections "Fast Boot: Chapter 4 (Prep)" (mechanism +
  hub-ordering rationale + playtest evidence, with the live prep-screen
  arrival now **ACHIEVED** via
  `debugtools-ch4-prep-positive-modern-debug.json`), "Diagnostics:
  structured probe/log ring + non-fatal assert record", "Five bounded
  validated tools" (+ host-executed evidence); Result-codes table
  extended with the two new codes and their renumbering-safety rationale;
  "Remaining #11 scope" updated so the live prep-screen arrival is
  recorded as achieved (only the true non-goals -- `mgba_printf`/full
  debugger/arbitrary editor -- remain) referencing this report.
- `reports/debugtools_issue11_closure.md` (this file).

### 9. DONE verification + fix-before-commit
- See "DONE evidence" below for exact commands/outputs. All fixes found
  during verification (registration-order hub-index regression, scenario
  probe-address drift from EWRAM/ROM layout growth, three host-test
  assumptions invalidated by the new registration order, one broken
  f-string from an editing slip) were fixed before this evidence was
  collected, not after.

## Explicit non-goals / residual risks

Carried over from the sprint's own DON'T list, restated here as durable
record (never attempted, by design, not because of a shortcut):

- **No `mgba_printf`, no interactive debugger, no arbitrary memory editor.**
  `src/debugtools_diag.c`'s introspection API has no address parameter at
  all. `src/debugtools_tools.c` never accepts a raw/arbitrary address or
  an unvalidated numeric index from outside its own fixed constants.
- **No raw address writes; no arbitrary flag/unit/convoy value writes.**
  Every mutation goes through an existing, already-audited engine helper
  (`SetUnitHp`/`SetUnitStatus`/`AddItemToConvoy`/`SetFlag`/`ClearFlag`/
  `SetLCGRNValue`+`InitRN`) with a fixed target/constant, gated by an
  explicit two-step confirm submenu.
- **Release never links debug behavior/data.** `gDebugToolsProbe` is the
  one exception (an always-zero diagnostic struct in every build, by
  design, matching the pre-existing slice-1 precedent) -- re-verified via
  `nm` (see below) for every symbol this closure added.

Previously-disclosed residual from this closure's own scope, now
**ACHIEVED** (recorded here for continuity, not as an open risk):

- **Live prep-screen arrival -- ACHIEVED.** Both halves are now proven
  live: the Ch4-Prep launcher's boot-commit
  (`debugtools-ch4-prep-launch-modern-debug.json`) and the
  world-map-navigation-to-prep-screen half plus the SELECT+B hotkey
  (`debugtools-ch4-prep-positive-modern-debug.json`, host test
  `tools/gba-playtest/tests/test_prep_positive_scenario.py`). The prep
  hotkey's live positive-trigger path is proven by a live positive at
  runtime: `gDebugToolsProbe.prepScreenObservedCount` (`0x02031854`) is
  observed `0 -> 1` on SELECT+B while `gPlaySt.chapterStateBits`
  (`0x020210b8`) holds `PLAY_FLAG_PREPSCREEN` (`0x10`); the hub open is
  idempotent (a 2nd SELECT+B leaves `hubOpenCount` at `2`, not `3`) and
  returns safely to a still-live prep. This is the DEBUG branch of
  `expansion-modern-debugtools-prep-check`; the RELEASE branch still
  verifies the compiled-out mirror. See "Live prep-screen arrival --
  ACHIEVED" (item 3) for the full probe list.

## Fingerprint regeneration (explicit, reviewed)

This closure's new hub actions (six more `DebugToolsAction` registrations,
`src/debugtools_diag.c`, `src/debugtools_tools.c`) legitimately grow both
EWRAM layout (shifting `gDebugToolsProbe`'s own address in **debug** builds
only -- confirmed via `nm`, release strips all of it back to the
pre-existing address) and ROM `.text`/`.rodata` layout (shifting later-
linked ROM data-table addresses referenced by unit-roster pointer checks).
Both are mechanical, uniform-delta consequences of adding code/data earlier
in the link order, verified via `nm` and cross-checked for a *uniform*
delta across every affected probe (a non-uniform delta would have indicated
a real bug, not a layout shift) before being accepted. Regenerated:

```sh
# (after `nm`-confirming the new gDebugToolsProbe/sHubActive addresses)
python3 tools/gba-playtest/gba_playtest.py capture \
  --rom build/expansion-modern/debug/aapcs/fireemblem8.gba \
  --scenario tools/gba-playtest/scenarios/debugtools-hub-modern-debug.json \
  --sram-image build/expansion-modern/debug/aapcs/debugtools-fixtures/debugtools-current.sav \
  -o tools/gba-playtest/fingerprints/debugtools-hub-modern-debug.json

python3 tools/gba-playtest/gba_playtest.py capture \
  --rom build/expansion-modern/debug/aapcs/fireemblem8.gba \
  --scenario tools/gba-playtest/scenarios/debugtools-map-hub-modern-debug.json \
  -o tools/gba-playtest/fingerprints/debugtools-map-hub-modern-debug.json

python3 tools/gba-playtest/gba_playtest.py capture \
  --rom build/expansion-modern/debug/aapcs/fireemblem8.gba \
  --scenario tools/gba-playtest/scenarios/debugtools-timer-freeze-modern-debug.json \
  -o tools/gba-playtest/fingerprints/debugtools-timer-freeze-modern-debug.json
```

Two scenario *source* files (not just fingerprints) also needed address
corrections for the same reason (`debugtools-map-hub-modern-debug.json`'s
`sHubActive` probe, `debugtools-hub-modern-debug.json`'s/
`debugtools-timer-freeze-modern-debug.json`'s `gDebugToolsProbe`-field
probes) -- each address change is `git diff`-visible as a pure
`"address": "0x..."` value edit, no checkpoint added/removed/reordered,
and every corresponding hardcoded address in
`tools/gba-playtest/tests/test_debugtools_registry.py` was updated to
match in the same pass. The four release-mirror scenarios
(`debugtools-{hub,map-hub,prep-hub}-modern-release.json`,
`debugtools-ch4-prep-launch-modern-release.json`) needed **no** changes at
all: release strips this closure's added code back out, so the release
build's own layout is unaffected (`nm`-confirmed:
`gDebugToolsProbe`'s release address is unchanged from before this
closure).

No fingerprint was regenerated to make a *failing* assertion pass by
weakening it -- every regeneration above followed a `nm`-verified,
uniform-delta root cause, and every regenerated file was re-`verify`'d
clean afterward (see "DONE evidence").

## DONE evidence

### Host tests (full suite; 196 debugtools-relevant + other pre-existing gba-playtest tests)

```
$ python3 -m unittest discover -s tools/gba-playtest/tests -v
...
Ran 196 tests in ~105-120s
OK (skipped=1)
```

The one skip: `SaveCompatScenarioTests_legacy.setUpClass` --
`skipped "ROM not built for 'legacy': .../fireemblem8.gba"`. This is the
*legacy* (agbcc) archival ROM, unrelated to this closure's scope
(modern-build-only per this task's WHERE); `./scripts/quickstart.sh --legacy`
requires interactive `sudo apt` package installation unavailable
non-interactively in this sandbox (confirmed: it stopped at
`sudo: a password is required`). This is an environment limitation, not a
silently-skipped debugtools requirement -- every debugtools-focused host
test class ran and passed.

### Modern debug/release build + link

```
$ make expansion-modern-rom PREFIX=arm-none-eabi- MODERN_CONFIG=debug   -> exit 0, "Modern ROM ready"
$ make expansion-modern-rom PREFIX=arm-none-eabi- MODERN_CONFIG=release -> exit 0, "Modern ROM ready"
```

Release symbol omission (`arm-none-eabi-nm` on the linked release ELF):
every `DebugTools_*` symbol present is a 4-byte-aligned disabled stub
(`DebugTools_RegisterExtendedToolActions`, `DebugTools_LogEvent`,
`DebugTools_GetLogCount`, `DebugTools_GetLogEntry`,
`DebugTools_RecordAssertFailure`, `DebugTools_GetAssertFailureCount`,
`DebugTools_GetLastAssertCode`, plus every pre-existing slice-1/2 entry
point) and `gDebugToolsProbe` (always-linked diagnostic struct, by
design). No internal action/menu/tool-implementation symbol
(`sUnitInspectAction`, `DebugToolsUnit_ConfirmSelected`, `sLogRing`, etc.)
appears in the release ELF.

### Runtime scenarios (libmGBA backend available in this sandbox: `backend-check` -> "libmGBA backend: available")

```
$ make expansion-modern-debugtools-check         MODERN_CONFIG=debug   -> passed, checkpoints=7
$ make expansion-modern-debugtools-check         MODERN_CONFIG=release -> passed, checkpoints=7
$ make expansion-modern-debugtools-map-check     MODERN_CONFIG=debug   -> passed, checkpoints=13
$ make expansion-modern-debugtools-map-check     MODERN_CONFIG=release -> passed, checkpoints=4
$ make expansion-modern-debugtools-timer-check   MODERN_CONFIG=debug   -> passed, checkpoints=3
$ make expansion-modern-debugtools-timer-check   MODERN_CONFIG=release -> skipped (documented no-op: dead code in release)
$ make expansion-modern-debugtools-prep-check    MODERN_CONFIG=debug   -> passed (live prep MapIdle SELECT+B hotkey; prepScreenObservedCount 0->1)
$ make expansion-modern-debugtools-prep-check    MODERN_CONFIG=release -> passed, checkpoints=4 (compiled-out prep-hub negative)
$ make expansion-modern-debugtools-ch4prep-check MODERN_CONFIG=debug   -> passed, checkpoints=4 (NEW, live boot-commit proof)
$ make expansion-modern-debugtools-ch4prep-check MODERN_CONFIG=release -> passed, checkpoints=4 (NEW)
```

No dependency was silently skipped: the previously-skipped
`debugtools-prep-check` debug branch now runs the live prep-positive
scenario and passes; the one remaining intentional skip
(`debugtools-timer-check` release) is documented dead-code-in-release, not
a silent pass.

### Artifact guard / copyright

```
$ git status --porcelain --ignored | grep -Ei '\.(gba|sav|savestate|state)$'
(no output -- no ROM/save/savestate tracked or newly added)
```

### `git diff --check` and no new `//` in compiled C

```
$ git diff --check
(no output -- no whitespace errors)
$ git diff --name-only -- '*.c' '*.h' | xargs -I{} git diff -- {} | grep -n '^\+.*//' 
(no output -- no added C++-style comments in any changed C source/header)
```

### Working tree / push

```
$ git status --short           # clean after commit
$ git log --oneline -1         # HEAD == this closure's commit
$ git ls-remote --heads origin agent/issues11-13-runtime   # SHA == HEAD
```

(Exact SHAs recorded at commit time; see the commit trailer/push output in
the session transcript for this task.)
