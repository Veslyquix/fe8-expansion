# Issue #13 closure evidence -- "Phase 5: Build the complete regression harness"

Status: candidate closure evidence for reviewer/verifier. **GitHub issue
#13 is OPEN at time of writing; this report does not close it, and does
not claim any CI run URL or merged state.** It maps every item of this
sprint's frozen closure contract (the WHAT/DONE sections of the task that
produced this commit) to concrete code, scenarios, tests, and explicit
non-goals/residual risks, so a reviewer can verify closure claim-by-claim.
It builds on `reports/debugtools_issue11_closure.md` (issue #11) by reusing
its scenarios/fingerprints and `gDebugToolsProbe` surface rather than
duplicating them; this report does not modify and is not a substitute for
that one.

Tool versions used to produce every command/output below (record these
alongside any re-run, since libmGBA/compiler version drift is an intentional
fingerprint difference this harness reports rather than silently absorbs --
see `tools/gba-playtest/README.md`):

- `arm-none-eabi-gcc (15:13.2.rel1-2) 13.2.1 20231009` (Ubuntu package)
- host `cc`: `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`
- `libmgba-dev 0.10.2+dfsg-1.1build3` (Ubuntu package; libmGBA 0.10.2)
- `Python 3.12.3`
- Base commit: `418a9f39885285cd1823ed6d52df7fc40857867e`
  ("debug: harden registry and close issue #11 productization gaps")

Run the evidence locally:

```sh
# Host tests (fast, no ROM/ARM toolchain needed except the one documented
# libmGBA-integration skip precedent)
python3 -m unittest discover -s tools/gba-playtest/tests -v

# libmGBA backend availability
python3 tools/gba-playtest/gba_playtest.py backend-check

# Modern debug/release build + link for both configs
make expansion-modern-rom PREFIX=arm-none-eabi- MODERN_CONFIG=debug
make expansion-modern-rom PREFIX=arm-none-eabi- MODERN_CONFIG=release

# Full linker/boot/runtime gate. Issue #13 adds expansion-modern-newgame-check;
# issue #11 closure adds the five-tools runtime gate
# expansion-modern-debugtools-tools-check. Both configs pass clean end to end,
# expansion-modern-budget-check included -- no -k needed.
make expansion-modern-linker-check MODERN_CONFIG=debug   MODERN_ABI=aapcs PREFIX=arm-none-eabi- -j"$(nproc)"
make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs PREFIX=arm-none-eabi- -j"$(nproc)"

# Artifact guard (no tracked ROM/save/savestate/build output)
python3 scripts/artifact_guard.py --revision HEAD

# Raw-pointer / build-address audits (already inside expansion-modern-linker-check;
# runnable standalone too)
python3 scripts/shiftcheck/scan_build_addrs.py --makefile Makefile --ldscript linker/expansion.ld --banim-ldscript linker_script_banim.txt
scripts/shiftcheck/scan_raw_casts.sh
```

## WHAT checklist

### 1. Generalized libmGBA scenario capture/verify (strict JSON, provenance, bounded retry)

- Strict JSON, provenance (ROM SHA-1/size/title/game code), and per-checkpoint
  hash/probe diagnostics were already in place (issue #13's starting point)
  and are unchanged in shape.
- **New**: a bounded, explicit, transient-only retry policy.
  `tools/gba-playtest/gba_playtest.py` adds `--retries N` (default `0` --
  exactly one attempt, matching every existing invocation's behavior
  unchanged) to `capture`, `verify`, and `backend-check`. `MAX_RETRIES_CAP`
  (5) bounds the *effective* retry count regardless of the requested value
  (`_bounded_retry_count`). The shared `_run_transient_retryable()` helper
  retries **only** a process `subprocess.TimeoutExpired` -- the one
  plausibly-transient condition here (host scheduling/load) -- covering the
  compiler, `pkg-config`, and the libmGBA backend invocation identically. A
  non-zero exit code, a malformed-output diagnostic, and a fingerprint
  mismatch are never retried anywhere in this module: retrying those would
  silently launder a real, reproducible failure into intermittent-looking
  flake, which the task explicitly forbids. Every retried attempt (not just
  the final one) is printed to stderr with its 1-based attempt number out of
  the total planned attempts, so a flaky time-out is always visible even
  when a later attempt succeeds. A negative `--retries` is rejected with an
  actionable `PlaytestError`, not silently clamped.
- Tests: `tools/gba-playtest/tests/test_retry_policy.py` (13 tests) --
  bounded-cap enforcement, transient-only retry with per-attempt stderr
  logging, default-zero-means-one-attempt (proving every pre-existing
  invocation's behavior is unchanged), non-zero-exit is never retried, and
  CLI-level negative-value rejection. `tools/gba-playtest/tests/test_timeouts.py`
  (pre-existing, unmodified, still green) continues to pin the exact
  diagnostic wording for the single-attempt (default) case.
- Every failure path (backend/compiler/pkg-config timeout, non-zero exit,
  malformed backend output, ROM-too-small, SRAM-image-wrong-size) remains
  exit status 2 with an actionable, specific diagnostic; a valid-but-different
  fingerprint remains exit status 1 with the exact JSON path/expected/actual
  values (`compare_fingerprints`/`_recursive_differences`, unchanged).

### 2. Exact-ROM vs. behavior-comparison policy; baseline refresh discipline

- Policy semantics were already implemented (`--policy exact-rom` default,
  `--policy behavior` explicit opt-in, both always printing both ROM
  identities) and are unchanged; `tools/gba-playtest/README.md`'s
  "Verification policy" section documents them, now directly followed by a
  new **"Baseline refresh policy"** section spelling out, in one place, that
  baseline refresh is exclusively a human, explicit `capture -o <path>`
  invocation followed by ordinary review -- `verify` has no
  write/refresh/update/regenerate-shaped flag anywhere, on either a passing
  or failing comparison.
- Test: `tools/gba-playtest/tests/test_baseline_no_autorefresh.py` (3 tests)
  -- proves byte-for-byte and even mtime-for-mtime that `verify` never
  touches its `--expected` file regardless of outcome, and that the `verify`
  subparser carries no flag whose name even suggests a write/refresh path.
- Every scenario added by this closure (`new-game.json`) declares its
  ROM-identity expectations the same way every existing one does: separate
  `-modern-debug.json`/`-modern-release.json` fingerprint files, verified
  with `--policy behavior` (the modern ROM is not byte-identical to any
  legacy baseline), exactly matching `title-progression`/`debugtools-hub`'s
  own precedent -- no new policy branch was introduced.

### 3. Deterministic runtime scenarios from clean boot

See `tools/gba-playtest/README.md`'s new "Deterministic runtime scenario
coverage (issue #13)" table for the full inventory. Summary against the
frozen list:

- **boot/title**: pre-existing, unchanged (`boot.json`,
  `title-progression.json`).
- **new game**: **new** (`tools/gba-playtest/scenarios/new-game.json` +
  `fingerprints/new-game-modern-{debug,release}.json`). Reuses
  `savecompat-current.json`'s own shared A/START title cadence (frames
  0..900, already proven to reach the ordinary Save Menu with no dialog),
  then replays three ordinary A confirmations on the menu's own default
  highlight each time (New Game -> Easy -> first empty save slot) -- never a
  scripted cursor move, never a raw memory write. Proves both the UI flow
  (framebuffer at `new-game-menu-selected`/`empty-slot-list-shown`) and a
  real persistent write (`new-game-created`'s whole-SRAM hash differs from
  `empty-slot-list-shown`'s, normalized over the same build-commit/checksum
  diagnostic bytes `savecompat-current.json` already excludes for the
  identical reason) landing at `gPlaySt.chapterIndex == CHAPTER_L_PROLOGUE
  (0x00)` and `faction == FACTION_BLUE (0x00)` -- semantic arrival, not a
  menu screenshot. Verified for both `debug` and `release` (this flow is
  ordinary gameplay, not a debug-gated feature).
- **chapter/map arrival**: **reused, not reimplemented**, per this task's own
  file-domain boundary (`不重写 #11 action 实现`).
  `tools/gba-playtest/scenarios/debugtools-hub-modern-{debug,release}.json`'s
  `chapter2-interactive-stable` checkpoint already proves a deterministic
  clean-boot chapter/map arrival (real Chapter 2 roster placed via
  `gUnitArrayBlue/Red/Green` probes, first stable Player Phase, a
  byte-identical whole-SRAM hash proving zero incidental persistent writes
  during boot) with a release-negative mirror. This closure's own
  exploration (see "Combat -- achieved" below) independently re-derived and
  cross-checked this same roster/placement live via this build's own symbol
  table, confirming the #11 evidence still holds against this exact commit.
- **combat**: **achieved** (`tools/gba-playtest/scenarios/combat.json`,
  enabled; fingerprint `combat-modern-debug.json`; host test
  `tools/gba-playtest/tests/test_combat_scenario.py`; gate
  `expansion-modern-combat-check`). The chapter's own scripted `FIGHT` is
  resolved by the real battle engine, enemy HP `15 -> 0` at the
  SCRIPT_BATTLE opcode; see "Combat -- achieved" below.
- **normal save/load**: **achieved**
  (`tools/gba-playtest/scenarios/save-load.json`, enabled; fingerprint
  `save-load-modern-debug.json`; host test
  `tools/gba-playtest/tests/test_save_load_scenario.py`; gate
  `expansion-modern-saveload-check`) -- a real SaveMenu New Game -> slot 0
  write, an A+B+SELECT+START soft reset, then the top-level SaveMenu
  RESTART item -> `PostSaveMenuHandler` -> `ReadGameSave` of slot 0 (a
  NORMAL game-save LOAD, distinct from Suspend/`ReadSuspendSave`). This is
  in addition to `new-game.json` and the pre-existing
  `savecompat-*`/`savesuspend-resume-modern-debug.json` coverage. See
  "Normal save/load -- achieved" below.
- **suspend/reset/resume**: pre-existing, unchanged
  (`savesuspend-resume-modern-debug.json`) -- a full write -> soft-reset ->
  reload round trip through the ordinary Map Menu Suspend command and the
  ordinary title Resume path, ending on symbol-derived probes of the
  manually-saved (not auto-saved) state.
- **debug-tool enabled behavior + release-disabled negatives**: pre-existing
  #11 scenarios, reused and re-verified unmodified by this closure's own
  `expansion-modern-linker-check` runs (see DONE evidence).
- **shifted-link runtime**: pre-existing `expansion-modern-shifted-check`
  (behavior policy, excludes any relocated raw pointer as an oracle by
  construction -- it only replays `boot.json`/`title-progression.json`
  against the shifted build), unchanged and re-verified for both configs
  below.

No copyrighted ROM/save/savestate is tracked; every scenario above is
verified against a build produced ROM that exists only in `build/`
(gitignored, never committed) for the duration of `capture`/`verify`.

### 4. Stub disposition

- **All stubs deleted.** The `tools/gba-playtest/scenarios/stubs/`
  directory is gone: `new-game.stub.json`/`chapter.stub.json` (superseded
  earlier) and now `combat.stub.json`/`save.stub.json` (superseded by the
  real, enabled `combat.json`/`save-load.json`) are all deleted. No
  disabled stub scenario remains in the repository.
- `tools/gba-playtest/tests/test_stub_scenarios.py` was rewritten to assert
  that **no** `*.stub.json` files remain and that `combat.json`/
  `save-load.json` are enabled with semantic (non-framebuffer) checkpoints.
  No test treats a stub as success anymore.
- `tools/gba-playtest/README.md` now lists `combat.json` and
  `save-load.json` (plus `debugtools-ch4-prep-positive-modern-debug.json`)
  as enabled, verified scenarios -- no undifferentiated disabled group and
  no stub rows remain.

### 5. Host test coverage

Beyond items 1/2/4's tests: `tools/gba-playtest/tests/test_new_game_scenario.py`
(10 tests) covers schema validity, checkpoint name/order, that the shared
`savecompat-current.json` prefix is reused **verbatim** (byte-for-byte
frame-range equality, not just "looks similar"), that every extra input
window is a bare `A` press (never a scripted directional move -- a
regression guard against silently turning this into a raw-navigation
scenario later), that the final checkpoint's probes are the documented
`gPlaySt.chapterIndex`/`faction` addresses, that both configs' committed
fingerprints exist/validate/parse to 3 checkpoints each with distinct ROM
identities, and (skipping explicitly, never silently, when a config's ROM
is not locally built) a live libmGBA run matching the committed fingerprint
for both `debug` and `release`. Every pre-existing scenario/config/save/
migration/timeout/error-path/deterministic-sorted-output host test file is
unmodified and still green (265 total tests, 1 documented archival skip -- see DONE
evidence).

### 6. CI integration

`.github/workflows/build.yml` now has two jobs:

- `host-tests` (new): `ubuntu-latest`, installs only `build-essential` +
  `libmgba-dev` (no `arm-none-eabi` cross-toolchain), runs
  `python3 -m unittest discover -s tools/gba-playtest/tests -v`. This is the
  fast, host-only lane the task asked to separate out; it is a required
  status like `build`, not merely advisory.
- `build` (pre-existing, extended by reuse not duplication): artifact guard
  -> generated-data-check -> `expansion-modern-linker-check` for
  `MODERN_CONFIG=debug` then `release` (both `MODERN_ABI=aapcs`, the only
  supported ABI for linked outputs -- see `docs/config_identity.md`). Issue
  #13's `expansion-modern-newgame-check` is now one more prerequisite inside
  that *same* chain (`MODERN_GOALS`, `MODERN_ALL_SOURCE_GOALS`,
  `MODERN_LINKED_GOALS`, and the target itself all updated in lock-step in
  `modern.mk`), so no target rebuilds the ELF/ROM a second time -- it reuses
  `expansion-modern-rom`'s own output exactly like `debugtools-check`/
  `savefmt-check` already do. The relocation/raw-pointer/build-address
  audits (`scan_build_addrs.py`, `scan_raw_casts.sh`) and the shifted-link
  check remain in the same `expansion-modern-linker-check` recipe, unmoved
  and unduplicated.
- The exact supported CI host matrix (`ubuntu-latest` only; macOS is
  documented for local dev only) and the archival/decomp `agbcc` path's
  relationship to this gate (continues to build locally, is not part of any
  CI gate, must never be read as a substitute runtime gate) are now stated
  explicitly in `tools/gba-playtest/README.md`'s "Supported CI host matrix"
  section, per `docs/issue-resolution-policy.md`'s existing modern-vs-
  archival framing.

### 7. Make targets

`expansion-modern-newgame-check` (`modern.mk`) added, following the exact
`expansion-modern-title-check`/`-ch4prep-check` pattern: depends on
`expansion-modern-boot-preflight`, `expansion-modern-rom` (reused, not
rebuilt), and the same `MODERN_DEBUGTOOLS_SRAM_FIXTURE` issue #11's own
debugtools-check already generates and depends on (reused as-is: it is
exactly "a deterministic CURRENT-format SRAM image", nothing debug-tools-
specific about its content) -- so this target adds zero new fixture-
generation cost. Wired into `MODERN_GOALS`, `MODERN_ALL_SOURCE_GOALS`,
`MODERN_LINKED_GOALS`, `expansion-modern-linker-check`'s prerequisite list,
and the trailing `.PHONY` block, in the same four places every sibling
`expansion-modern-debugtools-*-check` target already appears.

### 8. Documentation

- `tools/gba-playtest/README.md`: retry policy, baseline refresh policy,
  full runtime-scenario coverage table (with per-scenario proof
  description) -- now including `combat.json`, `save-load.json`, and
  `debugtools-ch4-prep-positive-modern-debug.json` (each debug-only, with
  its own proof), supported CI host matrix, and no stub rows.
- This report.
- `docs/save_format.md` and `docs/debugtools.md` are updated in this
  documentation-closure pass to record that normal save/load (SaveMenu
  RESTART -> `ReadGameSave`) and the live prep-screen arrival are now
  achieved; the deleted `combat.stub.json`/`save.stub.json` are no longer
  referenced anywhere.

### 9. Commit and push

See the final "DONE evidence" section below for the exact commands/results;
the commit trailer and push/verification steps follow this report in the
same session.

## Combat -- achieved

**Achieved.** `tools/gba-playtest/scenarios/combat.json` (enabled;
fingerprint `combat-modern-debug.json`; host test
`tools/gba-playtest/tests/test_combat_scenario.py`; gate
`expansion-modern-combat-check`, which the debug config verifies and the
release config skips honestly -- the launcher is debug-only).

It reuses the same Chapter 4 clean-boot path as the prep scenario and
captures the chapter's own scripted `FIGHT(CHARACTER_ARTUR,
CHAR_EVT_ACTIVE_UNIT, 63, 0)` in `EventScr_Ch4_BeginningScene`
(`src/events/ch4-eventscript.h`). That FIGHT is resolved by the REAL battle
engine `Event3F_ScriptBattle` (`EV_CMD_SCRIPT_BATTLE`, opcode at ROM
`EventScr_Ch4_BeginningScene+0x158`), not by a harness shortcut.

Exact pre/post evidence (fixed EWRAM probes, never framebuffer/timing): the
target enemy `gUnitArrayRed[0]` is alive at full HP before the FIGHT
(`maxHP` `0x0202eba6` and `curHP` `0x0202eba7` both `15`); `curHP` transitions
`15 -> 0` at the resolving SCRIPT_BATTLE frame while `maxHP` stays `15` (a
genuine 15-damage lethal battle hit, captured one resolving frame before the
following `KILL`); then `gUnitArrayRed[0].pCharacterData` (`0x0202eb94`) is
cleared to a null `0x00000000` as the unit is removed (death). So the lethal HP
change is the battle engine's scripted hit, not the `KILL` opcode. All three
oracles are relocation-independent semantic values -- HP scalars and a
null-field marker -- and the scenario asserts NO nonzero `pCharacterData`/
`pEventCurrent` relocated pointer value (see "Pointer-oracle remediation"
below; guarded by `tools/gba-playtest/tests/test_pointer_oracle_audit.py`).

This supersedes the earlier disabled `combat.stub.json` (now deleted). The
stub's prior blocker -- a debug-launcher-plus-ordinary-input route stalling
before reaching interactive single-turn combat -- was resolved by capturing
the chapter's own scripted battle through the real event/battle engine
instead: a legitimate, deterministic, semantic proof that the battle engine
inflicts lethal damage, with no savestate/save-file shortcut.

## Normal save/load -- achieved

**Achieved.** `tools/gba-playtest/scenarios/save-load.json` (enabled;
fingerprint `save-load-modern-debug.json`; host test
`tools/gba-playtest/tests/test_save_load_scenario.py`; gate
`expansion-modern-saveload-check`, which the debug config verifies with the
deterministic CURRENT-format SRAM fixture and the release config skips
honestly -- the soft-reset timing is debug-calibrated).

It reuses `new-game.json`'s clean-boot SaveMenu New Game -> slot 0 write,
then a real A+B+SELECT+START soft reset (RAM reinitialized), then the
top-level SaveMenu RESTART item -> `PostSaveMenuHandler` -> `ReadGameSave`
of slot 0 (`src/savemenu.c`; RESTART is `main_sel_bitfile & 0x82`). This is
a NORMAL game-save LOAD, distinct from Suspend/`ReadSuspendSave`.

Proven by fixed EWRAM probes (never framebuffer/timing): the
`playthroughIdentifier` (`0x020210bc`) and `chapterModeIndex` (`0x020210bf`)
discriminants go `1` (created) -> `0` (soft-reset cleared) -> `1` (loaded);
`gameSaveSlot` (`0x020210b0`) `== 0`; and the before/after whole-SRAM hashes
differ (write proof).

This is a distinct, legitimate proof of a normal (non-Suspend) game-save
write-and-load, so the earlier disabled `save.stub.json` (now deleted) is
superseded. FE7/8's own post-chapter-clear "Would you like to save?" flow
(`StartSaveMenuPostChapter`) is still `asm/`-only in this codebase and was
the stub's original target, but it is **not required**: normal save/load is
now proven a different, legitimate way via the SaveMenu RESTART ->
`ReadGameSave` path. Decompiling `StartSaveMenuPostChapter` remains a
separate, optional path, not a blocker for this coverage.

## Linker-budget status

`expansion-modern-budget-check` (issue #4's memory-budget gate, `modern.mk`)
**passes for both `debug` and `release`** at HEAD. The reviewed EWRAM budget
baselines in `reports/linker-budget/modern-{debug,release}.json` already
account for the debug tooling's `.bss` cost -- a reviewed `+688` bytes on
`debug` and `+84` bytes on `release` -- so the committed baseline matches the
built ELF and the gate is green. This round changed nothing that moves the
EWRAM budget (the five-tools runtime work is scenarios/fingerprints/tests and
a Make gate only, plus probe-list edits and doc updates; no new EWRAM state was
added -- the existing `gDebugToolsProbe` struct already exposes every field the
live scenario reads), so no baseline refresh was needed or performed. The whole
`expansion-modern-linker-check` chain (budget/overlay-audit/boot/title/
debugtools-*/debugtools-tools/new-game/combat/save-load/savefmt/shifted, plus
the standalone raw-pointer/build-address audits) passes for both configs in a
single run with no `-k` -- see DONE evidence below.

## Pointer-oracle remediation (independent-review follow-up)

Independent code review flagged behavior scenarios that asserted raw *relocated
pointer values* as their runtime oracle -- a layout-dependent assertion that
re-encodes where code/data landed after linking, not what the game semantically
did. All 31 such 4-byte pointer-range oracles (mirrored across scenarios and
fingerprints) were removed and replaced with relocation-independent semantic
evidence:
- `combat.json`: dropped `gUnitArrayRed[0].pCharacterData` (`0x088fe4a8`) at the
  two pre-death checkpoints; the proof is now the semantic HP transition plus
  the post-KILL null-field marker (`pCharacterData == 0x00000000`).
- `debugtools-ch4-prep-positive-modern-debug.json`: dropped the
  `gProcScr_SALLYCURSOR` `proc_idleCb` (`0x080905d1`) / `proc_scrCur`
  (`0x08953f40`) pointers; the `prepScreenObservedCount` `0 -> 1` increment
  (reachable only from `PrepScreenProc_MapIdle`) is the relocation-independent
  proof the hotkey fired live in prep.
- `debugtools-hub-modern-debug.json`: dropped 22 `gUnitArray[N].pCharacterData`
  ROM pointers at the two interactive-map checkpoints; interactivity is already
  proven by cursor/phase/map-state/proc-state/hub-count scalars and per-slot
  `struct Unit.state` fields. The fixture-seeded framebuffer/SRAM baselines are
  unchanged (only probe entries removed).
A standing host audit, `tools/gba-playtest/tests/test_pointer_oracle_audit.py`,
scans every checked-in scenario and fingerprint and fails on any 4-byte
value inside a ROM/EWRAM/IWRAM/SRAM range (default reject; the reviewed
allowlist is empty). Fingerprints were regenerated with `capture` (libmGBA
0.10.2) and reviewed diffs, never a `verify` auto-refresh.

## DONE evidence

All commands below were actually run this session; exact results follow.

### 1. Host test suite

```
$ python3 -m unittest discover -s tools/gba-playtest/tests -v
... (265 tests)
----------------------------------------------------------------------
Ran 265 tests in 150.492s

OK (skipped=1)
```

The one skip is the archival legacy (agbcc) save-compat ROM's documented
dependency (`ROM not built for 'legacy'`) -- the only allowed skip path per
`tools/gba-playtest/README.md`. libmGBA is installed here, so every libmGBA
runtime test runs (not skipped), including the new five-tools debug/release
runtime captures. 265 = 246 pre-existing/unmodified (still green) + 19 new
this task (4 test_pointer_oracle_audit + 1 added test_prep_positive_scenario
semantic/no-pointer assertion + 14 test_tools_scenario).

### 2. `backend-check`

```
$ python3 tools/gba-playtest/gba_playtest.py backend-check
libmGBA backend: available
```

### 3. Modern debug/release build + linker/boot/runtime gates

```
$ make expansion-modern-rom PREFIX=arm-none-eabi- MODERN_CONFIG=debug
... Modern ROM ready: build/expansion-modern/debug/aapcs/fireemblem8.gba (config=debug abi=aapcs)

$ make expansion-modern-rom PREFIX=arm-none-eabi- MODERN_CONFIG=release
... Modern ROM ready: build/expansion-modern/release/aapcs/fireemblem8.gba (config=release abi=aapcs)

$ make expansion-modern-linker-check MODERN_CONFIG=debug MODERN_ABI=aapcs PREFIX=arm-none-eabi- -j"$(nproc)"
check passed: reports/linker-budget/modern-debug.json
Modern ROM boot-check passed: ... (config=debug abi=aapcs)
Modern ROM title-check passed: ... (config=debug abi=aapcs)
Modern ROM debugtools-check passed: ... (config=debug abi=aapcs)
Modern ROM debugtools-timer-check passed: ... (config=debug abi=aapcs)
Modern ROM debugtools-map-check passed: ... (config=debug abi=aapcs)
Modern ROM debugtools-tools-check passed (five bounded tools live+confirmed in debug, compiled-out all-zero in release): ... (config=debug abi=aapcs)
Modern ROM debugtools-ch4prep-check passed: ... (config=debug abi=aapcs)
Modern ROM debugtools-prep-check passed (live prep MapIdle SELECT+B hotkey): ... (config=debug abi=aapcs)
Modern ROM combat-check passed (Ch4 scripted FIGHT enemy HP 15->0 + death): ... (config=debug abi=aapcs)
Modern ROM saveload-check passed (SaveMenu RESTART -> ReadGameSave(0)): ... (config=debug abi=aapcs)
Modern ROM newgame-check passed: ... (config=debug abi=aapcs)
expansion-modern-savefmt-check passed (config=debug): all 8 SaveCompatState values, Back-preservation, confirmed erase, host-migrated v1 load, and Suspend/soft-reset/Resume
Modern ROM savefmt-check passed: ... (config=debug abi=aapcs)
Modern overlay audit passed: build/expansion-modern/debug/aapcs/shiftcheck/overlay-audit.json
SHIFTED BOOT: PASS (shift=0x40000)
Modern expansion linker checks passed (config=debug abi=aapcs)

$ make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs PREFIX=arm-none-eabi- -j"$(nproc)"
check passed: reports/linker-budget/modern-release.json
Modern ROM boot-check passed: ... (config=release abi=aapcs)
Modern ROM title-check passed: ... (config=release abi=aapcs)
Modern ROM debugtools-check passed: ... (config=release abi=aapcs)
Modern ROM debugtools-timer-check skipped: no release scenario needed (dead code, documented #11 behavior)
Modern ROM debugtools-map-check passed: ... (config=release abi=aapcs)
Modern ROM debugtools-tools-check passed (release negative: hub/tools compiled out, gDebugToolsProbe all-zero): ... (config=release abi=aapcs)
Modern ROM debugtools-ch4prep-check passed: ... (config=release abi=aapcs)
Modern ROM debugtools-prep-check passed: ... (config=release abi=aapcs)
Modern ROM combat-check skipped: debug-only launcher (release runtime matrix has no separate combat scenario) -- see reports/gba_playtest_issue13_closure.md
Modern ROM saveload-check skipped: debug-calibrated soft-reset; release normal-save coverage = newgame-check (write) + savefmt-check (load classification) -- see reports/gba_playtest_issue13_closure.md
Modern ROM newgame-check passed: ... (config=release abi=aapcs)
expansion-modern-savefmt-check passed (config=release): all 8 SaveCompatState values, Back-preservation, confirmed erase, host-migrated v1 load
Modern ROM savefmt-check passed: ... (config=release abi=aapcs)
Modern overlay audit passed: build/expansion-modern/release/aapcs/shiftcheck/overlay-audit.json
SHIFTED BOOT: PASS (shift=0x40000)
SHIFTED TITLE: PASS (shift=0x40000)
Modern expansion linker checks passed (config=release abi=aapcs)
```

**Every check passed for both configs**, `expansion-modern-budget-check`
included (the reviewed EWRAM baseline already accounts for the debug tooling's
`.bss`; see "Linker-budget status" above), and the new
`expansion-modern-debugtools-tools-check` gate ran and passed in both (live
five-tools proof in debug, compiled-out all-zero negative in release). No `-k`
is needed and no failure is being attributed away.

### 4. Individual scenario `verify` runs (boot/title/new-game/chapter/suspend-resume/debugtools, enabled + release-negative)

All of the following were run standalone (not just inside
`expansion-modern-linker-check`) against the built debug/release ROMs, each
printing `fingerprint verified: policy=behavior ...` and exiting 0:

| Scenario | Config | Result |
| --- | --- | --- |
| `boot.json` | debug | verified, 3 checkpoints |
| `title-progression.json` | debug | verified, 4 checkpoints |
| `title-progression.json` | release | verified, 4 checkpoints |
| `new-game.json` | debug | verified, 3 checkpoints |
| `new-game.json` | release | verified, 3 checkpoints |
| `debugtools-hub-modern-debug.json` (chapter/map arrival, live) | debug | verified, 7 checkpoints |
| `debugtools-hub-modern-release.json` (chapter/map arrival, negative) | release | verified, 7 checkpoints |
| `savesuspend-resume-modern-debug.json` | debug | verified, 3 checkpoints |
| `debugtools-map-hub-modern-debug.json` (enabled, live) | debug | verified, 13 checkpoints |
| `debugtools-map-hub-modern-release.json` (release negative) | release | verified, 4 checkpoints |
| `combat.json` (Ch4 scripted FIGHT, live) | debug | verified, enemy `curHP` 15->0 at SCRIPT_BATTLE + death |
| `save-load.json` (SaveMenu RESTART -> ReadGameSave, live) | debug | verified, `playthroughIdentifier` 1->0->1 + SRAM write |
| `debugtools-ch4-prep-positive-modern-debug.json` (live prep + SELECT+B) | debug | verified, `prepScreenObservedCount` 0->1 |

Combat and normal save/load are now enabled, verified scenarios (rows
above), not stubs. No `*.stub.json` remains in the repository;
`test_stub_scenarios.py` was rewritten to assert none remain and that
`combat.json`/`save-load.json` are enabled with semantic (non-framebuffer)
checkpoints.

### 5. Shiftcheck static/offset/diff/runtime and raw-pointer/relocation audits

Modern path (this task's actual scope, and CI's real gate -- both configs,
already included in item 3's `-k` runs above): `expansion-modern-shifted-check`
(`SHIFTED BOOT: PASS`, `SHIFTED TITLE: PASS` for release; debug's own title
shift-check is embedded the same way), `expansion-modern-overlay-audit`
(passed both configs), and the trailing
`scan_build_addrs.py`/`scan_raw_casts.sh` audits, run standalone too:

```
$ python3 scripts/shiftcheck/scan_build_addrs.py --makefile Makefile --ldscript linker/expansion.ld --banim-ldscript linker_script_banim.txt
... RESULT: PASS (coupled build-system constants are consistent)

$ scripts/shiftcheck/scan_raw_casts.sh
... RESULT: no raw ROM/RAM pointer literals in source (the redas class is clean)
```

Legacy/archival path (`make shiftcheck-build/-static/-offsets/-diff/-run`,
`ldscript.txt`-based): Layer 0 (`shiftcheck-build`, pure Python, no
compilation) passes identically against the legacy `ldscript.txt`. Layers
1-3 (`shiftcheck-static`/`-offsets`/`-diff`/`-run`) require the archival
`agbcc` toolchain (`tools/agbcc/bin/agbcc`), which is **not built in this
environment** (`./scripts/quickstart.sh` was not run this session -- out of
this harness-focused task's scope, and, per
`docs/issue-resolution-policy.md`, the archival path is not part of any CI
gate regardless). This is an actionable, environment-based skip, not a
silent pass: re-running `./scripts/quickstart.sh` then `make shiftcheck`
would exercise it. It does not affect this closure's scope, which is the
supported modern path's own shiftcheck (`expansion-modern-shifted-check`),
fully green above for both configs.

### 6. Artifact guard

```
$ python3 scripts/artifact_guard.py --revision HEAD
(no output; exit 0)
```

### 7. `git diff --check` and compiled-C `//`-comment guard

```
$ git diff --check
(no output; exit 0)
```

No `.c`/`.h` file was added or modified by this change (confirmed via
`git status --short` and `git diff --stat -- tools/gba-playtest/backend.c`
showing no diff) -- this closure's file domain
(`tools/gba-playtest/{gba_playtest.py,README.md}`, its `tests/`,
`scenarios/`/`fingerprints/`, `modern.mk`, the CI workflow, and this report)
never touches compiled C, so the "no `//` in compiled C" requirement has no
new surface to check; `backend.c` remains byte-for-byte as issue #11 left
it.

### 8. Commit, push, and remote verification

See the commit immediately following this report in the same session; its
message records the exact SHA, and `git ls-remote --heads origin
agent/issues11-13-runtime` was run immediately after `git push` to confirm
the remote head matches `HEAD` and the working tree is clean. (Both are
captured in the session's final summary rather than duplicated here, since
this report is itself part of that commit and cannot know its own
resulting SHA in advance.)
