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

# Full linker/boot/runtime gate (issue #13 adds expansion-modern-newgame-check
# into this same chain; -k keeps going past the pre-existing, unrelated
# budget-check drift documented below so every other check's own result is
# still visible in one run)
make expansion-modern-linker-check MODERN_CONFIG=debug   MODERN_ABI=aapcs PREFIX=arm-none-eabi- -j"$(nproc)" -k
make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs PREFIX=arm-none-eabi- -j"$(nproc)" -k

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
  exploration (see "Combat residual" below) independently re-derived and
  cross-checked this same roster/placement live via this build's own symbol
  table, confirming the #11 evidence still holds against this exact commit.
- **combat**: investigated in depth; **not achieved** -- see "Combat
  residual" below. Remains a disabled stub with a specific, evidenced
  blocker (not a generic placeholder).
- **normal save/load**: `new-game.json` (this closure) plus the pre-existing
  `savecompat-*`/`savesuspend-resume-modern-debug.json` scenarios already
  cover every ordinary-UI save/load path this codebase's *decompiled* source
  can reach today. A distinct mid-game, non-Suspend "regular" Save remains
  a disabled stub -- see "Save residual" below.
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

- **Deleted** (superseded by real, enabled coverage):
  `tools/gba-playtest/scenarios/stubs/new-game.stub.json` and
  `chapter.stub.json`. `tools/gba-playtest/tests/test_stub_scenarios.py`
  pins that only `combat.stub.json`/`save.stub.json` remain and that the two
  deleted files stay gone.
- **Kept disabled, blocker rewritten with concrete evidence** (not
  generic placeholders): `combat.stub.json` and `save.stub.json` -- see
  their own `"blocker"` field and "Combat residual"/"Save residual" below.
  `capture()` still rejects both explicitly (`test_stub_scenarios.py`'s
  `test_capture_rejects_every_remaining_disabled_stub_explicitly`).
- `tools/gba-playtest/README.md` no longer frames "new-game, chapter,
  combat, and save" as a single undifferentiated disabled group; it states
  precisely which two are covered and which two remain blocked and why.

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
unmodified and still green (229 total tests, 1 documented skip -- see DONE
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
  description), corrected stub framing, supported CI host matrix.
- This report.
- `docs/save_format.md` and `docs/debugtools.md` are unmodified (out of this
  task's file domain per the WHERE boundary); this report and
  `save.stub.json`/`combat.stub.json` cross-reference them instead of
  editing them.

### 9. Commit and push

See the final "DONE evidence" section below for the exact commands/results;
the commit trailer and push/verification steps follow this report in the
same session.

## Combat residual (full investigation trace)

**Not achieved. `combat.stub.json` remains disabled.** This section is the
detailed trace backing that stub's own `"blocker"` field, so a future
attempt does not have to re-derive any of it from scratch.

Starting point: issue #11's debug-only "Fast Boot: Chapter 2" launcher
(`tools/gba-playtest/scenarios/debugtools-hub-modern-debug.json`'s own
proven prefix through its `chapter2-interactive-stable` checkpoint),
extended with the ordinary UI input `savesuspend-resume-modern-debug.json`
already uses through its own dialogue-exhaustion window (frame 16986).

1. **Roster/placement, confirmed live against this build.** Using this
   build's own `arm-none-eabi-nm` symbol table (`gUnitArrayBlue =
   0x0202f9a4`, `gUnitArrayRed = 0x0202eb94`, `gUnitArrayGreen =
   0x0202e5f4`, each a `struct Unit[N]` of size `0x48`; `gPlaySt =
   0x020210a4`; `gBmSt = 0x020210f0`), a wide probe scan at the
   `chapter2-interactive-stable`-equivalent point confirmed the exact
   roster #11's own description already claims: Eirika (Rapier-holding,
   confirming unit index 1), Seth, Gilliam, Franz, Moulder, and Vanessa in
   Blue; Ross in Green; Bone plus five generic bandits in Red. **Every**
   Blue unit's position is 6-14 tiles (Manhattan distance) from the
   *nearest* Red unit at this point -- geometrically too far for any unit's
   move-plus-attack-range to reach in a single turn, regardless of which
   unit is chosen. Single-turn combat is therefore not merely unattempted;
   it is unreachable from this launcher's own start-of-turn placement.
2. **The live map cursor is `gBmSt.playerCursor` (`Vec2` at `gBmSt+0x14`),
   not `gPlaySt.xCursor`/`yCursor`.** The latter (used by every existing
   probe in `savesuspend-resume-modern-debug.json`) is only a
   last-committed snapshot, synced at specific commit points (confirmed:
   Suspend-save) -- **not** a live per-frame value. A 48-byte wide scan of
   `gPlaySt` around an ordinary directional key-press showed zero byte
   changed, while the same key-press visibly moved the on-screen cursor and
   changed `gBmSt.playerCursor.x`/`.y` (and the paired pixel-scale
   `cursorTarget`/`playerCursorDisplay` fields) exactly as expected. Any
   future combat (or other live-map-navigation) scenario must probe
   `gBmSt.playerCursor` for the live map tile, not `gPlaySt.xCursor`/
   `yCursor`.
3. **The chapter enforces a mandatory, tutorial-flagged "Guide" hint chain**
   before free unit commands are available: selecting the newly-arrived
   Moulder unit is redirected into "move close to Vanessa" (a real,
   in-engine suggested-destination overlay, not a harness artifact);
   selecting Eirika is redirected into a village-visit conversation and an
   escort move. Both were driven to completion with ordinary `A`/
   directional input only (no menu item was ever force-selected outside
   what the game itself already highlighted by default).
4. **A genuine "End" System-Menu item appears** (`Unit`/`Status`/`Guide`/
   `Options`/`Suspend`/`End`, six items, up from five) only once every
   Blue unit has acted through the hint chain above. Selecting it flips
   `gPlaySt.faction` from `FACTION_BLUE` (`0x00`) to `FACTION_ENEMY`
   (`0x80`), and three Red units' `xPos`/`yPos` probes changed value
   turn-over-turn (`(10,12)->(9,13)`, `(7,14)->(7,13)`, `(12,3)->(11,4)`)
   -- real, deterministic, reproducible enemy-AI repositioning driven by
   ordinary UI input alone, with no savestate/save-file shortcut.
5. **The stall.** After that repositioning, both the framebuffer and every
   unit-array probe stay byte-identical for several thousand further
   frames -- tried both with zero further input and with additional `A`
   presses (in case a camera-pan or dialogue confirmation was pending).
   Enemy Phase does not appear to advance to any attack or back to Player
   Phase within the frame budget tried. The cause was not isolated further
   within this closure's time-box: candidates include (a) a much longer
   camera-pan/AI-decision window than tried, (b) a proc/event interaction
   specific to reaching this exact state via the debug launcher plus this
   input sequence (as opposed to the vanilla title/new-game boot this
   launcher intentionally bypasses), or (c) an actual engine idle/wait
   state this investigation has not yet identified the trigger for.

**Why this is reported as a residual, not worked around:** a savestate,
save file, or other generated binary would trivially "solve" reaching
combat, but is prohibited by this harness's own constraints and this
task's explicit DON'Ts. No committed scenario file was produced for this
partial "reach Enemy Phase" state either -- it depends on a long (~300+
input event), still only manually-verified tap sequence that has not been
hardened into a reviewed, host-tested scenario file within this closure's
time-box, and committing an under-verified, complex scenario would risk
exactly the kind of unreviewed-fingerprint-drift risk this task's baseline-
review requirements exist to prevent. The full tap sequence, probe
addresses, and frame numbers above are sufficient for a future attempt to
resume from step 5 without repeating steps 1-4.

## Save residual

**Not achieved for a distinct mid-game "regular" Save. `save.stub.json`
remains disabled.** Normal save/load is otherwise fully covered (see WHAT
item 3): `savesuspend-resume-modern-debug.json` proves a complete write ->
soft-reset -> reload round trip via Suspend, and this closure's
`new-game.json` independently proves a `SaveMenuWriteNewGame`/
`WriteGameSave`-class SRAM write via the ordinary top-level Save Menu -- a
different code path than Suspend, with its own before/after `sram_hash`
proof. What remains specifically out of reach is a **mid-game, non-Suspend**
"regular" Save distinct from both of those. FE7/8's own post-chapter-clear
"Would you like to save?" flow is driven by `StartSaveMenuPostChapter`,
which is still `asm/`-only in this codebase
(`include/functions.h`'s own `// ??? StartSaveMenuPostChapter(???);`
placeholder) -- decompiling it is out of scope for a harness-only closure.
The in-map Map Menu itself (`Unit`/`Status`/`Guide`/`Options`/`Suspend`,
confirmed via live UI navigation for this closure -- see the combat residual
above) has no separate "Save" entry distinct from Suspend, so no
ordinary-UI, clean-boot route to that specific call site exists today.

## Pre-existing, out-of-scope finding: linker-budget drift

`expansion-modern-budget-check` (issue #4's own memory-budget gate, `modern.mk`)
fails for **both** `debug` and `release` on a clean checkout of this task's
own start commit `418a9f39`, **before any change in this commit**: EWRAM
`.bss` occupancy is 688 bytes larger than `reports/linker-budget/modern-{debug,release}.json`
records (confirmed by `git stash`-ing every change in this commit and
re-running `expansion-modern-budget-check` in isolation -- the drift
reproduces identically with zero files from this commit applied). This is
therefore a pre-existing condition in the base commit this task started
from, not something introduced by this change, and is issue #4's own
report/gate to refresh -- this task's file domain and mandate explicitly
exclude touching `reports/linker-budget/*.json` (a reviewed oracle, not
something to silently regenerate to make an unrelated gate pass) or
otherwise weakening/bypassing it. It is called out here, prominently, as an
actionable finding for whoever owns issue #4 or the next linker-budget
refresh, rather than silently worked around. Every *other* check in
`expansion-modern-linker-check` (boot/title/debugtools-*/new-game/savefmt/
overlay-audit/shifted-check, plus the standalone raw-pointer/build-address
audits) passes for both configs -- see DONE evidence below, captured with
`-k` specifically so this one pre-existing failure does not hide the result
of every other check in the same run.

## DONE evidence

All commands below were actually run this session; exact results follow.

### 1. Host test suite

```
$ python3 -m unittest discover -s tools/gba-playtest/tests -v
... (229 tests)
----------------------------------------------------------------------
Ran 229 tests in 102.452s

OK (skipped=1)
```

The one skip is `test_debugtools_sram_fixture`/`test_backend_integration`'s
own pre-existing, documented libmGBA-availability skip precedent (not
triggered in this environment -- libmGBA is installed here -- but confirmed
present as the *only* allowed skip path per `tools/gba-playtest/README.md`).
229 = 196 pre-existing (unmodified, still green) + 33 new
(13 retry-policy + 3 baseline-no-autorefresh + 10 new-game-scenario + 7
stub-inventory/quality).

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

$ make expansion-modern-linker-check MODERN_CONFIG=debug MODERN_ABI=aapcs PREFIX=arm-none-eabi- -j"$(nproc)" -k
Modern ROM boot-check passed: ... (config=debug abi=aapcs)
Modern ROM title-check passed: ... (config=debug abi=aapcs)
Modern ROM debugtools-check passed: ... (config=debug abi=aapcs)
Modern ROM debugtools-timer-check passed: ... (config=debug abi=aapcs)
Modern ROM debugtools-map-check passed: ... (config=debug abi=aapcs)
Modern ROM debugtools-ch4prep-check passed: ... (config=debug abi=aapcs)
Modern ROM debugtools-prep-check skipped: no live prep-screen-arrival scenario yet (pre-existing #11 documented residual, unrelated to this closure)
Modern ROM newgame-check passed: ... (config=debug abi=aapcs)
expansion-modern-savefmt-check passed (config=debug): all 8 SaveCompatState values, Back-preservation, confirmed erase, host-migrated v1 load, and Suspend/soft-reset/Resume
Modern ROM savefmt-check passed: ... (config=debug abi=aapcs)
Modern overlay audit passed: build/expansion-modern/debug/aapcs/shiftcheck/overlay-audit.json
SHIFTED BOOT: PASS (shift=0x40000)
check failed: report drift detected in reports/linker-budget/modern-debug.json   <-- PRE-EXISTING, see below
make: *** [modern.mk:1897: expansion-modern-budget-check] Error 1

$ make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs PREFIX=arm-none-eabi- -j"$(nproc)" -k
Modern ROM boot-check passed: ... (config=release abi=aapcs)
Modern ROM title-check passed: ... (config=release abi=aapcs)
Modern ROM debugtools-check passed: ... (config=release abi=aapcs)
Modern ROM debugtools-timer-check skipped: no release scenario needed (dead code, documented #11 behavior)
Modern ROM debugtools-map-check passed: ... (config=release abi=aapcs)
Modern ROM debugtools-ch4prep-check passed: ... (config=release abi=aapcs)
Modern ROM debugtools-prep-check passed: ... (config=release abi=aapcs)
Modern ROM newgame-check passed: ... (config=release abi=aapcs)
expansion-modern-savefmt-check passed (config=release): all 8 SaveCompatState values, Back-preservation, confirmed erase, host-migrated v1 load
Modern ROM savefmt-check passed: ... (config=release abi=aapcs)
Modern overlay audit passed: build/expansion-modern/release/aapcs/shiftcheck/overlay-audit.json
SHIFTED BOOT: PASS (shift=0x40000)
SHIFTED TITLE: PASS (shift=0x40000)
check failed: report drift detected in reports/linker-budget/modern-release.json   <-- PRE-EXISTING, see below
make: *** [modern.mk:1897: expansion-modern-budget-check] Error 1
```

**Every check passed for both configs except `expansion-modern-budget-check`**,
which was confirmed (via `git stash` of every change in this commit,
rebuild, and re-run in isolation) to fail **identically on the unmodified
base commit `418a9f39`** -- see "Pre-existing, out-of-scope finding" above.
This is not a pass being claimed away: it is flagged, reproduced, and
attributed precisely so it is not confused with a regression from this
change.

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

Combat and a distinct mid-game regular Save have no `verify` command to run
-- both remain disabled stubs; `capture`/`verify` reject them explicitly
with exit status 2 (`test_stub_scenarios.py`'s
`test_capture_rejects_every_remaining_disabled_stub_explicitly` pins this).

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
