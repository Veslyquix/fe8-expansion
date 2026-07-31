# Issue #18 sprint 4 closure evidence -- "host+semantic libmGBA localization
# scenarios, runtime probes, budget/headroom, real fingerprint captures"

Status: **candidate closure evidence for reviewer/verifier. GitHub issue
#18 is OPEN at time of writing; this report does not close it, and does
not claim any CI run URL or merged state.** It maps every item of this
sprint's frozen contract (the WHAT/DONE sections of the task that produced
this commit) to concrete code, scenarios, tests, and explicit non-goals,
so a reviewer can verify closure claim-by-claim. It builds on Sprint 1
(`5436ec27`), Sprint 2 (`795d2abd`, `6b9fe068`), and Sprint 3 (`b746df2c`,
`92ed1b6b`) rather than duplicating their host-only test coverage.

**Sprint 5 addendum (this commit)**: fixed every Harness review/verifier
finding raised against this report's sprint-4 claims, closing all three
previously-descoped items for real (see the WHAT #2-3 section above and
"Non-applicable items" below) plus four additional real defects:

1. **Multi-locale clean-build header-path DAG bug**: a clean, uncached,
   non-`-j` multi-locale build could race two configs'/output roots'
   generated-header prerequisites against each other. Root-caused to
   `modern.mk`'s `MODERN_LOCALIZATION_ROOT`/`MODERN_LOCALE_MULTI_BUILD_
   ROOT` not being config/output-root-specific; fixed by deriving both
   from `$(MODERN_BUILD_ROOT)`, and locked in with a new cold debug/release
   `expansion-modern-localization-runtime-multi-check` regression run with
   no cache and no `-j` (`scripts/modernize/tests/test_modern_
   localization_header_bootstrap.py`'s `ModernLocalizationMultiCheckColdCleanTests`).
2. **Prefs-corruption "no-wipe" SRAM-hash false red**: root-caused an
   undocumented, vanilla `SramInit()` hardware self-test scratch-pad
   write (`gSram->reserved`, offset `0x73A0`, 4 bytes) as a second
   locale-unrelated noise source beyond the already-known `SoundRoomSaveData`
   struct. Fixed by adding it as a third, explicit `sram_hash_exclude_
   ranges` entry (never by deleting the whole-SRAM comparison) plus new,
   real per-byte probes covering it, `ExpansionSaveMeta`'s own magic/
   checksum, and the untouched XMAP region's magic/checksum/`save_magic32`
   -- proving these regions are stable/known rather than silently masked.
3. **Real settings navigation / real soft-reset persistence / visible
   pseudo marker**: implemented for real (see WHAT #2-3 above); no longer
   descoped.
4. **Shifted-check success log printed the wrong path**: `expansion-
   modern-localization-runtime-shifted-check`'s success `printf` referenced
   `$(MODERN_LOCALE_MULTI_ROM)` instead of the actual shifted-build output
   path; fixed to print `$(MODERN_SHIFTED_OUTDIR)`.

No fixture is described as a reboot; no whole-framebuffer/whole-SRAM
comparison was deleted to hide unexplained drift; every fingerprint this
sprint touched was captured via a real `gba_playtest.py capture` run
against a real, freshly-built ROM, never hand-written.

Tool versions used to produce every command/output below:

- `arm-none-eabi-gcc (15:13.2.rel1-2) 13.2.1 20231009` (Ubuntu package)
- host `cc`/`gcc`: `13.3.0` (Ubuntu 13.3.0-6ubuntu2~24.04.1)
- `libmgba-dev 0.10.2+dfsg-1.1build3` (Ubuntu package; libmGBA 0.10.2)
- `Python 3.12.3`
- Base commit: `92ed1b6b` ("fix(issue18): clean parallel modern build no
  longer races on expansion_msg_ids.h")

Run the evidence locally:

```sh
# Host suite (localization + gba-playtest + everything else this repo
# tracks under tests/, excluding two pre-existing, unrelated collection
# errors -- see "Host suite" below)
python3 -m pytest -q --ignore=tests/upstream_port --ignore=scripts/texttools/huffman_test.py

# New locale probe schema/bounds lock-in test
python3 -m pytest -q tools/gba-playtest/tests/test_locale_probe_schema.py

# Modern debug/release build + link for both configs
make expansion-modern-rom PREFIX=arm-none-eabi- MODERN_CONFIG=debug
make expansion-modern-rom PREFIX=arm-none-eabi- MODERN_CONFIG=release

# Full linker/boot/runtime gate, including all six new localization
# runtime-check targets. Must be run sequentially (no -j) -- see
# "A real Make-parallelism false alarm" below.
make expansion-modern-linker-check MODERN_CONFIG=debug   MODERN_ABI=aapcs PREFIX=arm-none-eabi-
make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs PREFIX=arm-none-eabi-

# Any single new runtime-check target standalone
make expansion-modern-localization-runtime-debug-check   MODERN_CONFIG=debug   MODERN_ABI=aapcs PREFIX=arm-none-eabi-
make expansion-modern-localization-runtime-release-check MODERN_CONFIG=release MODERN_ABI=aapcs PREFIX=arm-none-eabi-
make expansion-modern-localization-runtime-multi-check   MODERN_ABI=aapcs PREFIX=arm-none-eabi-
make expansion-modern-localization-runtime-prefs-check   MODERN_ABI=aapcs PREFIX=arm-none-eabi-
make expansion-modern-localization-runtime-save-check    MODERN_ABI=aapcs PREFIX=arm-none-eabi-
make expansion-modern-localization-runtime-shifted-check MODERN_ABI=aapcs PREFIX=arm-none-eabi-

# Budget/headroom (real linker-map-derived, never hardcoded)
make expansion-modern-localization-budget-check MODERN_CONFIG=debug   MODERN_ABI=aapcs PREFIX=arm-none-eabi-
make expansion-modern-localization-budget-check MODERN_CONFIG=release MODERN_ABI=aapcs PREFIX=arm-none-eabi-
```

## WHAT checklist

### 1. Probe/backend/schema extension for `ExpansionLanguage` diagnostics

`src/expansion_language_menu.c` (Sprint 3) already exposes a plain, bounded
EWRAM diagnostic struct, `gExpansionLanguageMenuProbe` (`include/
expansion_language_menu.h`), covering `active`/`settingsActive`/
`promptShown`/`autoSelected`/`promptReason`/`prefsState`/`selectedLocale`/
`currentLocale`/`enabledLocaleCount`/`cacheGeneration`/`startupRunCount`/
`settingsOpenCount`/`settingsChangeCount` -- exactly current locale, cache
generation, prefs status, menu-active, and result, as the contract asks.
`tools/gba-playtest`'s existing generic address+size `Probe` mechanism
(`backend.c`, `gba_playtest.py`'s `Probe` class), already used unchanged
for the issue #11 debugtools probe, reads it: a bounded (`probe_count <=
1024`/checkpoint), plain memory read of a known, fixed-layout struct's
fields, **never a raw/arbitrary pointer dereference or a new pointer-chase
oracle**. No backend.c/schema code change was required to satisfy "safely
read" here -- the smallest-diff, Musk-Algorithm-correct move was reusing
the already-reviewed generic mechanism for a new probe struct, not
building a second one.

**New this sprint**: host tests covering "probe schema/bounds" --
`tools/gba-playtest/tests/test_locale_probe_schema.py` (4 tests) compiles
and runs a small driver (`tools/gba-playtest/tests/c/
expansion_language_menu_probe_offsets_driver.c`) against the real,
unmodified header to get the compiler's own `offsetof()`/`sizeof()` for
every field, then cross-checks:

- every `locale-*.json` scenario's hardcoded probe address against
  `base + offsetof(field)` for a real field (`test_every_locale_scenario_
  probe_address_matches_a_documented_field_offset`);
- every probe's `(address, size)` against `sizeof(struct
  ExpansionLanguageMenuProbe)` (`test_every_locale_scenario_probe_
  stays_within_struct_bounds`);
- every probe's declared byte width against its target field's real width
  (`test_every_locale_scenario_probe_size_matches_its_fields_declared_
  width`).

Verified this test suite is a real regression guard, not a tautology: with
`promptShown` temporarily widened from `u8` to `u16` in a scratch copy of
the header, the offset-match test fails deterministically (`3 not found in
{...}`); reverted, all 4 pass again (`git diff --stat
include/expansion_language_menu.h` empty afterward -- the header itself
was never actually left modified).

### 2-3. Semantic scenarios/targets with real assertions (not frame-only)

`tools/gba-playtest/scenarios/locale-*.json` +
`tools/gba-playtest/fingerprints/locale-*.json` (12 scenario/fingerprint
pairs as of sprint 5, real libmGBA captures):

| Scenario | Config(s) | Contract item |
|---|---|---|
| `locale-blank-sram-no-selector-default` | debug, release | Blank SRAM + single-locale (`en`) config: selector reachable/auto-selects before intro/title. |
| `locale-blank-sram-no-selector-multi` | debug, release | Blank SRAM + multi-locale (`en,qps-ploc`) config: selector prompt path reachable pre-title. |
| `locale-auto-select-single-locale` | debug, release | `UNSET`-prefs real fixture, single enabled locale: `AUTO_SELECT`, `promptShown=0`, no visible selector ("one enabled en auto-select no visible selector" milestone). |
| `locale-selector-multi-switch-qps` | debug | Real selector navigation choosing `qps-ploc`; persisted (`cacheGeneration` bump visible), pseudo path exercised end-to-end. |
| `locale-prefs-corrupt-no-wipe` | debug | Corrupt prefs -> re-prompt; SRAM hash unchanged (see exclusions below): no wipe. |
| `locale-prefs-unknown-locale-no-wipe` | debug | Unknown-locale-id prefs -> re-prompt; SRAM hash unchanged: no wipe. |
| `locale-prefs-disabled-locale-no-wipe` | debug | Prefs naming a locale not compiled into this build -> re-prompt; SRAM hash unchanged: no wipe. |
| `locale-settings-real-navigation-multi` (sprint 5) | debug | Real Prep Map -> Options -> Configuration -> Language -> `RIGHT` navigation opens the real settings submenu; real qps-ploc selection; real Back-cancel-never-mutates-prefs proof; visible pseudo-marker region/pixel checkpoints. |
| `locale-softreset-persistence-multi` (sprint 5) | debug | Real first-run selector chooses qps-ploc; real `A+B+SELECT+START` soft-reset combo reboots via libmGBA's own HLE BIOS; continuous SRAM proves persistence (no selector re-prompt, locale retained). |

Every scenario asserts real `gExpansionLanguageMenuProbe` field values
(via the schema-locked probe addresses above) plus SRAM hash and/or
framebuffer hash at each checkpoint -- semantic milestones proven by
runtime state actually reached, not merely "N frames elapsed with no
crash." Boot timing uses the same `SKIP_HS`-style key-hold recipe as the
existing `boot.json` family; an earlier attempt using a longer generic
intro-mash sequence was found to accidentally auto-dismiss the selector
before its checkpoint frame, and was abandoned in favor of this
minimal-input, semantically-targeted sequence.

**English/pseudo render + explicit pseudo marker (implemented, sprint 5)**:
a prior sprint's `locale-selector-multi-switch-qps` framebuffer-hash-only
evidence has been superseded -- `locale-settings-real-navigation-multi-
modern-debug` now carries a per-checkpoint `back_row_label` framebuffer
**region** hash (never the whole-screen hash alone) plus two individual
**pixel probes** at the settings submenu's `Back` row, the one row in this
menu resolved in the *current* locale (`ExpansionLocale_ResolveCurrent
(EXP_MSG_FRAMEWORK_BACK)`; every locale-name row is always resolved in
English regardless of current locale). Real capture proves this region's
hash, and concrete pixel byte values, differ between the English
(`currentLocale=0`) and qps-ploc checkpoints -- e.g. a dark-ink byte in
English becomes a light-background/white byte in qps-ploc at the same
screen coordinate -- real, screen-region/pixel-level proof the qps-ploc
decoration marker (`scripts/localization/pseudo.py`'s deterministic
`"Back"` -> `"[[BaaCk]]"` transform) is visible and differs from English.
See `tools/gba-playtest/backend.c`/`gba_playtest.py`'s new plan-format-v3
`regions`/`pixel_probes` checkpoint fields and their mandatory host schema
tests, `tools/gba-playtest/tests/test_region_pixel_schema.py` (32 tests)
and `tools/gba-playtest/tests/region_hash_mirror.py`.

**Soft-reboot persistence (implemented, sprint 5)**: a prior sprint's
fresh-cold-boot-from-fixture proof (semantically related but not a
literal reboot) has been superseded -- `locale-softreset-persistence-
multi-modern-debug` now replays the real first-run-selector input
choosing `qps-ploc`, then holds the actual GBA hardware soft-reset key
combo (`A+B+SELECT+START`, ~20-24 frames). libmGBA's default HLE BIOS
implements this combo without any custom backend/game code, producing a
genuine full reboot (fresh EWRAM/BSS -- `startupRunCount` resets to `0`)
while the underlying SRAM image is never swapped/replaced. Post-reboot,
the selector does not reappear and `currentLocale` reads back `qps-ploc`
without re-selection -- real persistence across a real reboot on
continuous SRAM, not a fixture stand-in.

**Real Config settings-submenu live navigation (implemented, sprint 5)**:
a prior sprint's inconclusive live-navigation investigation has been
superseded -- `locale-settings-real-navigation-multi-modern-debug` drives
the actual reachable in-game path (Prep Map -> `Options` -> Configuration
screen -> `Language` row -> `RIGHT`) entirely through replayed controller
input, never calling `ExpansionLanguageMenu_OpenSettings()` directly and
never substituting a fixture for the entry point. Real probe evidence:
`settingsActive` toggles 0->1 on real entry; selecting `qps-ploc` moves
`currentLocale`/`cacheGeneration`/`settingsChangeCount` and auto-closes
the submenu; reopening the submenu and pressing `B` (Back, no selection)
leaves `currentLocale`/`cacheGeneration`/`settingsChangeCount` and all 6
persisted `ExpansionUserPrefs` SRAM bytes byte-identical while
`settingsOpenCount` still increments -- real, capture-verified proof that
Back never mutates prefs.

Debug/release matrix: every scenario with cross-config relevance ships
both a `-modern-debug` and `-modern-release` pair (7 of 10 file pairs);
the three prefs no-wipe scenarios are debug-only, since the classification
logic they exercise (`ExpansionUserPrefs_Normalize`) has no config-
dependent branch and Sprint 3's host tests already prove config-
independence at the pure-function level. The multi-locale config is built
as an entirely separate ROM (own build root
`build/expansion-modern-multi`, own `ExpansionMetadata`/fingerprints) via
`EXPANSION_ENABLED_LOCALES=en,qps-ploc EXPANSION_PSEUDO_LOCALE=1` --
**qps-ploc is never conflated with a real translation or with the
single-locale build's own budget/metadata numbers.**

### 4. New Make targets + `expansion-modern-linker-check` wiring

`modern.mk` adds:

- `expansion-modern-localization-runtime-debug-check`
- `expansion-modern-localization-runtime-release-check`
- `expansion-modern-localization-runtime-multi-check`
- `expansion-modern-localization-runtime-prefs-check`
- `expansion-modern-localization-runtime-save-check`
- `expansion-modern-localization-runtime-shifted-check`

All six (plus the pre-existing `expansion-modern-localization-budget-
check`) are now dependencies of `expansion-modern-linker-check`, so the
existing upstream CI/verify path (which already invokes that target)
picks these six runtime-check targets up automatically -- no `build.yml`
change was needed for *this* wiring specifically, since
`expansion-modern-linker-check` was already a CI/verify gate before this
sprint.

That said, this branch's merge history (`14df9ec3`, merging
`origin/master` in) does contain a separate, explicitly-authorized,
purely additive edit to `.github/workflows/build.yml`: a new
`localization-host-suite` step (`Run localization host test suite (issue
#18)`) appended to the host-tests job, running
`scripts/localization/tests`' own pure-stdlib suite
(`python3 -m unittest discover -s scripts/localization/tests -p
"test_*.py"`). It only appends a new step -- no existing `build.yml` step
was modified, reordered, or removed, and no gate was weakened. The
matching `verify.py`/`verify --dry-run` gate and
`docs/upstream-porting.md` gate list were updated in the same commit so
CI and the local `verify` mirror stay in lockstep (see that commit's
message and `git diff master...HEAD -- .github/workflows/build.yml` for
one additive localization-host-suite step; no existing step modified/reordered/removed).

**Shifted-layout check**: `expansion-modern-localization-runtime-shifted-
check` reruns `blank-sram-no-selector-default` and `auto-select-single-
locale` through `scripts/shiftcheck/modern_shifted_boot.sh` under a
`__text_shift=0x40000` relink, proving the locale resolver/selector-probe
scenarios are unaffected by build-address shifting (no hardcoded/absolute-
address dependency introduced by this feature).

### 5. Budget/headroom -- real, non-hardcoded

`scripts/linker_report/localization_budget.py` (new) +
`reports/linker-budget/modern-localization-{debug,release}.json`:

- `rom_catalog_index` / `rom_catalog_strings`: real `nm -S` sizes for the
  generated catalog/index ROM symbols (`gExpansionLocaleMsgIds`,
  `gExpansionLocaleMsgCount`, `gExpansionLocaleTombstoneCount`,
  `gExpansionCatalog_en`, `gExpansionCatalog_qps_ploc`).
- `ewram_ui_state` / `ewram_resolver_state`: real `nm -S` sizes for
  `gExpansionLanguageMenuProbe` and the resolver's EWRAM state/cache
  symbols (`sCurrentLocale`, `sCurrentLocaleValid`, `sCacheLocale`,
  `sCacheMsgId`, `sCacheValid`, `sScratch`).
- `source_catalog_budget`: source-side string/index/decoded-max/glyph
  usage from `scripts/localization/generate.py`, independent of any
  particular linked ROM.
- `regions_headroom`: `rom`/`ewram`/`iwram` `capacity_bytes`/
  `occupied_bytes`/`free_bytes`/`overflow`, computed from the **real**
  linker `.map` for this exact build (floating `.data`/`.bss` tail up to
  `__floating_end` through whatever pinned symbol follows it). `--check`
  fails only on a real map-reported `overflow: true` -- **no fixed byte
  threshold, and specifically no hardcoded "2820"/"3508" research-note
  number, gates pass/fail anywhere in this tool.**

Both debug and release reports were regenerated this sprint via real
`make expansion-modern-localization-budget-check` runs and pass.

### 6. Real clean builds + captures; drift audit

Debug, release, and the `en,qps-ploc` multi-locale config were all built
via real `arm-none-eabi-gcc` (`MODERN_CONFIG=debug|release`, plus the
separate multi-locale build root) and exercised through the real libmGBA
backend (`libmgba-dev 0.10.2`) for every capture/verify in this report --
no fingerprint in this diff was hand-written. All 12 locale-* scenario/
fingerprint pairs, plus every pre-existing fingerprint this sprint's own
`src/expansion_locale.c` EWRAM fix legitimately drifted, were captured via
`gba_playtest.py capture` and confirmed via `verify --policy behavior`.
Diffs to existing fingerprints touch only the fields the drift actually
changed (SRAM/framebuffer hashes, probe values); no pointer-allowlist
entry, baseline, or TAS file was touched.

**Pre-existing fingerprints this sprint regenerated** (all root-caused to
the EWRAM fix, none fabricated -- see "Bugs found and fixed" below):
`debugtools-hub-modern-debug`, `debugtools-ch4-prep-launch-modern-debug`,
and all 9 `savecompat-*-modern-release` scenarios (`current`,
6x`dialog-back-*`, `erase`, `current-migrated`).

### 7. Host suite / gate results

- **`python3 -m pytest -q --ignore=tests/upstream_port
  --ignore=scripts/texttools/huffman_test.py`: 1372 passed, 5 skipped, 78
  subtests passed** (720s). Both excludes are **pre-existing, unrelated**
  collection errors confirmed present at base commit `92ed1b6b` (`tests/
  upstream_port/*` do `from tests.upstream_port import helpers as h`,
  which fails because `tests/__init__.py` does not exist -- a pre-existing
  package-layout inconsistency, last touched by unrelated commit
  `c74f48e0`; `scripts/texttools/huffman_test.py` similarly). Neither
  `--import-mode=importlib` nor `PYTHONPATH=.` resolves this pre-existing
  issue; it is out of this sprint's file-domain scope to fix (tests/
  modification is not authorized here). **1372 >> the 266-test contract
  floor.**
- `python3 -m pytest -q tools/gba-playtest/tests`: **286 passed, 4
  skipped, 43 subtests passed** (135s) -- includes the new
  `test_locale_probe_schema.py`.
- `make expansion-modern-linker-check MODERN_CONFIG=debug` (sequential, no
  `-j`): **passes completely, no failures.**
- `make expansion-modern-linker-check MODERN_CONFIG=release` (sequential,
  no `-j`): **passes completely, no failures.**
- `python3 scripts/artifact_guard.py --revision HEAD` (unchanged tool):
  no tracked ROM/save/savestate/build output introduced by this sprint's
  diff.
- `scripts/shiftcheck/scan_build_addrs.py` / `scan_raw_casts.sh`
  (unchanged tools, already inside `expansion-modern-linker-check`): clean.

## Bugs found and fixed this sprint

Musk-Algorithm discipline: every one of these was root-caused to an
underlying real defect before being fixed -- none were "worked around" by
editing a fingerprint/baseline/test to hide the symptom.

1. **`MODERN_GOALS` allowlist gap (Makefile correctness bug).**
   `modern.mk`'s `MODERN_GOALS` is a fixed allowlist gating whether the
   `git rev-parse HEAD`-based config-resolution/`-D`-define pipeline runs
   at all for a given `make` invocation. The six new runtime-check target
   names were initially missing from it, so the pipeline silently no-op'd
   and the compiled ROM embedded a hardcoded `"unknown"` `build_commit`
   sentinel, failing `verify_rom_header.py`'s embedded-vs-metadata
   comparison. Root-caused via the pre-existing `print-%` debug target
   (`make print-MODERN_BUILD_COMMIT`); an initial "transient git race"
   hypothesis was a red herring. **Fixed** by adding all eight new target
   names to `MODERN_GOALS`.
2. **`modern_shifted_boot.sh` had no way to supply a non-default SRAM
   fixture.** Its `verify_scenario()` always called `gba_playtest.py
   verify` with no `--sram-image`, silently using blank/default SRAM
   regardless of what a given scenario actually needed --
   `locale-auto-select-single-locale` requires the `UNSET`-prefs fixture,
   not blank SRAM, and initially failed the shifted-check with
   blank-SRAM-shaped probe values. **Fixed** via an optional,
   backward-compatible `SHIFTCHECK_SRAM_IMAGE` env var (empty by default,
   a no-op for every pre-existing caller).
3. **Two debug fingerprints drifted by the EWRAM fix were initially
   regenerated incorrectly** (`debugtools-hub-modern-debug`,
   `debugtools-ch4-prep-launch-modern-debug`): an ad-hoc regeneration
   omitted the `--sram-image build/.../debugtools-fixtures/debugtools-
   current.sav` argument the real Make recipe always passes, so the
   "passing in isolation" fingerprint failed again once exercised through
   the actual Make target. **Fixed** by regenerating with the exact
   Make-recipe arguments; lesson generalized into "always inspect the
   real recipe's arguments before any ad-hoc fingerprint regeneration."
4. **Nine release `savecompat-*` fingerprints were never regenerated** in
   the prior session's debug-only EWRAM-fix fixup pass, and were caught
   by this sprint's full-release-gate run. **Fixed** via a script exactly
   replicating `run_save_compat_checks.py`'s fixture/scenario/fingerprint-
   name conventions; verified by re-running that script directly for
   `--config release`.
5. **The prefs-safety "no-wipe" SRAM-hash discrepancy** (root cause: an
   entirely vanilla, locale-unrelated `struct SoundRoomSaveData` at SRAM
   offset `0x7224` legitimately rewrites 2 of its own bytes on every
   boot). Root-caused via a full, chunked (1024-byte-limited) byte-by-byte
   SRAM diff across the entire 0x8000-byte image, not just the meta
   struct region initially suspected. **Fixed** (not worked around) by
   adding this pre-existing, unrelated struct's real address range to
   `sram_hash_exclude_ranges` alongside the already-expected
   `ExpansionUserPrefs` record, with an honest scenario description
   documenting why.
6. **`-j$(nproc)` parallel runs of the full `expansion-modern-linker-
   check` gate produced spurious, non-reproducible failures** that never
   reproduced sequentially -- a real hazard in a complex dependency graph
   with several sub-`$(MAKE)` invocations (the multi-locale build) sharing
   `expansion-modern-rom`/`expansion-modern-elf` prerequisites.
   **Mitigated** by documenting (here and in `docs/localization.md`) that
   the full gate must always be verified sequentially; not fixed at the
   Makefile-dependency-graph level (out of scope for this sprint -- no
   scenario/fingerprint/target correctness was affected, only spurious
   `-j` noise).

None of these required editing `src/`/`include/` UI logic beyond the
already-landed EWRAM fix (from a prior session, retained unmodified this
sprint) -- every fix this sprint is confined to `modern.mk`, `scripts/
shiftcheck/modern_shifted_boot.sh`, scenario/fingerprint JSON, and this
sprint's own new files.

## Non-applicable items (explicit, not silently dropped)

The three items previously listed here as descoped in an earlier sprint
-- real Config settings-submenu live navigation, an explicit visible
pseudo-marker pixel/region proof, and a literal soft-reset key-combo
persistence variant -- are **no longer descoped**: all three are now
implemented with real libmGBA evidence (see the WHAT #2-3 section above
and the sprint 5 addendum below). The one remaining item from that list:

- **Docs inventory / checker registry update**: searched for at HEAD;
  no such registry file exists in this worktree's `docs/`/`reports/` tree
  (confirmed via `find`/`ls`), so per the task's own conditional
  instruction ("if present in current master") this item does not apply
  and nothing was added or skipped improperly.

## WHERE / DON'T compliance

- No edits to `baseline.json`, any TAS file, the pointer allowlist,
  content assets, vanilla message tables, `GetLang`/`SetLang`/
  `gLanguageMode`, or XMAP region/magic definitions. `.github/workflows/
  build.yml` *was* edited on this branch (see "New Make targets" above)
  -- one explicitly-authorized, purely additive `localization-host-suite`
  step, with the matching `verify.py` gate and doc update in the same
  commit; no existing CI gate was weakened, reordered, or removed.
- No `#6`/`#10` manual-copy of foreign-language content; no foreign
  content authored anywhere in this diff (`docs/localization.md`'s own
  legal/non-goals section documents this explicitly).
- Every fingerprint touched in this diff is a real, capture-verified
  regeneration (see WHAT #6); none were hand-edited.
- `git log` shows no `--amend`/force-push in this sprint's history; this
  commit is a plain, ordinary append to `agent/issue18-localization`.
- Issue #18 is not closed by this commit.
