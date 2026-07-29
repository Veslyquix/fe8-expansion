# In-game localization framework (issue #18)

Status: implementation + real libmGBA runtime evidence exist (Sprints 1-4);
**issue #18 remains open**. This document is architecture/authoring/testing
reference, not a closure claim -- see
`reports/issue18_localization_closure.md` for the sprint 4 evidence mapping.

## Architecture

The framework is layered, each layer independently testable:

1. **Stable ID contract** (`scripts/localization/schema.py`,
   `include/expansion_locale.h`): an append-only `ExpansionLocaleId` list
   (`en, ja, zh-Hans, fr, de, es, it, qps-ploc`) and a 16-bit
   `ExpansionMsgId` space (`0xFFFF` reserved as "no such message"). Never
   renumbered; a retired slot's index is never reused. The Python and C
   sides are kept in sync by hand and cross-checked by
   `scripts/localization/tests/test_schema.py` plus host C driver tests.
2. **Source catalog + registry** (`texts/expansion/registry.json`,
   `texts/expansion/catalog.<locale>.json`, `scripts/localization/catalog.py`):
   the source of truth for which message IDs exist and their per-locale
   text. `scripts/localization/generate.py` compiles this into
   `expansion_locale_catalog.c` (ROM data) and `expansion_msg_ids.h`
   (generated header), write-if-unchanged, and reports a source-catalog
   budget (string bytes, index bytes, decoded-max scratch, glyph/codepoint
   usage).
3. **Runtime resolver** (`src/expansion_locale.c`,
   `include/expansion_locale.h`): `ExpansionLocale_GetCurrent()` /
   `_SetCurrent()` / `_Resolve()` / `_InvalidateCache()`. Holds the
   current locale, a decoded-string cache (locale+msg-id keyed,
   invalidated on any locale change), and a small decode scratch buffer --
   all in `EWRAM_DATA` (see "The EWRAM-placement bug" below for why this
   matters). Never reads/writes vanilla `GetLang()`/`SetLang()`/
   `gLanguageMode`/`gMsgTable`; entirely independent of the vanilla
   multi-language ROM mechanism.
4. **User preferences** (`include/expansion_save_prefs.h`,
   versioned/checksummed `ExpansionUserPrefs`, Sprint 2): a small SRAM
   record (locale choice + validity state) with its own version/checksum,
   read via `ExpansionUserPrefs_Load()`/classified via `_Normalize()` into
   `ExpansionUserPrefsState` (`UNSET` / `VALID` / `CORRUPT` /
   `UNKNOWN_LOCALE` / `DISABLED_LOCALE`), and written via `_Store()`.
   Deliberately excludes vanilla `struct SoundRoomSaveData` and every
   other pre-existing SRAM field -- see the "no-wipe" contract below.
5. **First-start selector + settings submenu**
   (`src/expansion_language_menu.c`, `include/expansion_language_menu.h`,
   Sprint 3): `ExpansionLanguageMenu_DecideStartupAction()` is a pure,
   host-testable function mapping `(prefs state, enabled locale count)` to
   one of `PROMPT` / `AUTO_SELECT` / `APPLY_ONLY`. The blocking first-start
   selector Proc script runs this decision once per boot, immediately
   after `ProcScr_GameEarlyStartUI` and before `ProcScr_OpAnim` (`#ifdef
   MODERN`-guarded call site in `src/gamecontrol.c`); with exactly one
   enabled locale it silently auto-selects and never shows a UI. The
   independent settings submenu (`ExpansionLanguageMenu_OpenSettings`) is
   reachable from the Config screen and only calls `ExpansionUserPrefs_
   Store()`/invalidates the resolver cache when the chosen locale actually
   differs from the current one; `Back` leaves everything untouched. A
   `struct ExpansionLanguageMenuProbe gExpansionLanguageMenuProbe` (EWRAM,
   `include/expansion_language_menu.h`) exposes `active`/`settingsActive`/
   `promptShown`/`autoSelected`/`promptReason`/`prefsState`/
   `selectedLocale`/`currentLocale`/`enabledLocaleCount`/`cacheGeneration`/
   `startupRunCount`/`settingsOpenCount`/`settingsChangeCount` for exactly
   this kind of diagnostic read -- a plain, bounded, fixed-layout struct,
   never a raw/arbitrary pointer oracle.

## Config

Set at `modern.mk`/`make` invocation time (see
`scripts/modernize/expansion_config.py` for validation):

- `EXPANSION_ENABLED_LOCALES` -- comma-separated subset of the stable
  locale-ID list (default: `en`). Sprint 1-4 only ship real content for
  `en`, plus the derived pseudo locale.
- `EXPANSION_DEFAULT_LOCALE` -- must be a member of
  `EXPANSION_ENABLED_LOCALES` (default: `en`).
- `EXPANSION_PSEUDO_LOCALE` -- `1` enables `qps-ploc`, and requires
  `qps-ploc` to actually be present in `EXPANSION_ENABLED_LOCALES` (the two
  can never silently disagree -- `validate_pseudo_locale` rejects that
  combination outright).

These are baked into the ROM's embedded `ExpansionMetadata` (build-commit,
enabled-locale mask, default-locale id, pseudo-locale flag) so a given ROM's
config is always recoverable from the binary itself, never only from the
build invocation.

## Pseudo locale (`qps-ploc`) -- legal/non-goals

`qps-ploc` (`scripts/localization/pseudo.py`) is a deterministic, purely
mechanical transform of the English catalog (accenting/padding/bracketing
ASCII test markers), generated at build time from `catalog.en.json` --
**never a translation, never hand-authored foreign text, and never
represents any real language**. Every user-facing surface that can display
it (the selector list, the settings submenu, `ExpansionLanguageMenu_
GetCurrentLocaleDisplayName`) labels it `"Pseudo (Test)"`, never a language
name. Its own display name is resolved against `EXPANSION_LOCALE_EN` (a
proper noun), never through itself. This repository has authored **no**
foreign-language content anywhere in this framework; every non-English
stable locale ID beyond `en`/`qps-ploc` is a reserved, unpopulated slot for
future sprints.

## Authoring

1. Add/edit entries in `texts/expansion/registry.json` (id name, never
   renumbering or reusing a retired id) and `texts/expansion/catalog.en.
   json` (the English text).
2. `make expansion-localization-generate` (or let any modern build target
   depend on it) regenerates `expansion_locale_catalog.c`/
   `expansion_msg_ids.h`/the localization budget JSON, write-if-unchanged.
3. `python3 -m pytest scripts/localization/tests` / `make
   localization-test` re-validates the schema, catalog parsing, pseudo
   transform, and the generated header.
4. To enable another real (non-English) locale in the future: populate its
   `catalog.<locale>.json`, add it to `EXPANSION_ENABLED_LOCALES`, and
   extend the runtime/host test matrix analogous to `en`/`qps-ploc` --
   never hand-copy or paraphrase copyrighted third-party translation text
   into this repository (see issue #18's own non-goals; also see
   `CONTRIBUTING.md`/#6/#10's manual-copy prohibition, which this sprint
   does not touch).

## Testing -- real libmGBA runtime evidence (Sprint 4)

Sprint 4 adds `tools/gba-playtest` scenario/fingerprint pairs that boot the
**actual compiled ROM** under libmGBA and assert real, reached runtime
states via `gExpansionLanguageMenuProbe` + SRAM-hash + framebuffer-hash
checkpoints -- not host-only input replay. All scenarios reach the real
selector using the same boot-timing recipe as the existing `boot.json`
family: skip the vanilla title/intro sequence with an explicit
`SKIP_HS`-style key-hold window, since a longer generic intro-mash sequence
can accidentally auto-dismiss the selector before its checkpoint frame.

Scenarios (`tools/gba-playtest/scenarios/locale-*.json`,
fingerprints in the matching `tools/gba-playtest/fingerprints/` file):

| Scenario | Proves |
|---|---|
| `locale-blank-sram-no-selector-default-modern-{debug,release}` | Blank SRAM, single enabled locale (`en`): selector auto-selects silently, reachable before intro/title. |
| `locale-blank-sram-no-selector-multi-modern-{debug,release}` | Blank SRAM, multi-locale build (`en,qps-ploc`): selector prompt path is genuinely reachable pre-title. |
| `locale-auto-select-single-locale-modern-{debug,release}` | An `UNSET` prefs sub-state (real reachable fixture, not blank SRAM) with one enabled locale: `AUTO_SELECT`, `promptShown=0`, never a visible selector -- contract item "one enabled en auto-select no visible selector". |
| `locale-selector-multi-switch-qps-modern-debug` | Real selector navigation choosing `qps-ploc`; persisted via `ExpansionUserPrefs_Store` (`cacheGeneration` bump visible in probe). |
| `locale-prefs-corrupt-no-wipe-modern-debug` | Corrupt `ExpansionUserPrefs` -> re-prompt; full-SRAM hash (minus two justified exclusions below) is unchanged frame-5 to frame-600: no wipe. |
| `locale-prefs-unknown-locale-no-wipe-modern-debug` | Same, for an unknown-locale-id prefs record. |
| `locale-prefs-disabled-locale-no-wipe-modern-debug` | Same, for a prefs record naming a locale not compiled into this build. |

Every save/load and suspend/resume regression coverage for locale prefs
reuses the existing, unmodified `expansion-modern-saveload-check`/
`expansion-modern-savefmt-check` gates (see the `-runtime-save-check`
Make target below) rather than duplicating that harness.

### The "no-wipe" SRAM-hash exclusions

The three prefs-safety scenarios' `sram_hash_exclude_ranges` are exactly:

- `{"offset": "0x7224", "length": "0x24"}` -- vanilla
  `struct SoundRoomSaveData soundRoomSave` (`include/bmsave.h`), which
  legitimately rewrites 2 of its own bytes on every boot as ordinary
  pre-existing sound-room bookkeeping, **unrelated to locale/expansion
  code or prefs state** (confirmed identical across all three fixtures via
  a full 0x8000-byte SRAM diff, chunked at the backend's 1024-probe/
  checkpoint cap).
- `{"offset": "0x73D4", "length": "0x0C"}` -- the `ExpansionUserPrefs`
  record itself, which is *expected* to be rewritten (its own checksum/
  version bookkeeping) even when the effective locale choice is unchanged
  by a rejected corrupt/unknown/disabled value.

No other byte anywhere in the 0x8000-byte SRAM image differs between the
pre- and post-boot checkpoints for any of the three fixtures -- this is
the real, capture-verified evidence for the "corrupt/unknown/disabled
prefs never wipe SRAM" contract item, not an assumption.

### Probe schema/bounds host tests

`tools/gba-playtest/tests/test_locale_probe_schema.py` compiles and runs a
small driver (`tools/gba-playtest/tests/c/
expansion_language_menu_probe_offsets_driver.c`) against the real,
unmodified `include/expansion_language_menu.h` to get the compiler's own
`offsetof()`/`sizeof()` for every `gExpansionLanguageMenuProbe` field, then
cross-checks every `locale-*.json` scenario's hardcoded probe address
against `base + offsetof(field)` and every probe's `(address, size)`
against the struct's real bounds/field width. A future header edit that
reorders, resizes, or removes a field fails this suite instead of silently
producing a wrong-field (or out-of-bounds) pinned fingerprint.

### XMAP / region-magic

`scripts/shiftcheck/scan_build_addrs.py` and the existing shifted-link
gate (`expansion-modern-shifted-check`) are unchanged by this sprint;
`expansion-modern-localization-runtime-shifted-check` (below) additionally
proves the locale resolver/selector-probe scenarios still pass under a
`__text_shift=0x40000` relink, i.e. no hardcoded/build-address-dependent
behavior was introduced by this feature.

### Make targets

- `expansion-modern-localization-runtime-debug-check` /
  `-release-check`: blank-SRAM-selector + auto-select scenarios, per
  config.
- `expansion-modern-localization-runtime-multi-check`: builds an
  independent `en,qps-ploc` ROM (own build root, `EXPANSION_ENABLED_
  LOCALES`/`EXPANSION_PSEUDO_LOCALE` overrides -- a real, separate ROM
  build/fingerprint set, never conflated with the single-locale metadata/
  budget numbers) and verifies the multi-locale blank-SRAM + selector-
  switch-to-qps scenarios.
- `expansion-modern-localization-runtime-prefs-check`: the three
  corrupt/unknown/disabled-locale no-wipe scenarios.
- `expansion-modern-localization-runtime-save-check`: depends on the
  existing `expansion-modern-saveload-check` + `expansion-modern-
  savefmt-check` (regression coverage only, no new save-format scenarios).
- `expansion-modern-localization-runtime-shifted-check`: reruns the
  blank-SRAM + auto-select scenarios through `scripts/shiftcheck/
  modern_shifted_boot.sh` under a `__text_shift=0x40000` relink.

All six are wired into `expansion-modern-linker-check`'s dependency list
(both `MODERN_CONFIG=debug` and `=release` pass end-to-end, run
sequentially -- `-j` parallel runs of the full gate have shown spurious,
non-reproducible failures in a complex multi-target graph with several
sub-`$(MAKE)` invocations; always verify the full gate sequentially).

## Budgets

`make expansion-modern-localization-budget`/`-budget-check`
(`scripts/linker_report/localization_budget.py`,
`reports/linker-budget/modern-localization-{debug,release}.json`) reports:

- `rom_catalog_index` / `rom_catalog_strings`: real `nm -S` sizes for the
  generated catalog/index ROM symbols.
- `ewram_ui_state` / `ewram_resolver_state`: real `nm -S` sizes for
  `gExpansionLanguageMenuProbe` and the resolver's EWRAM cache/scratch
  symbols.
- `source_catalog_budget`: the source-side string/index/decoded-max/
  glyph-usage numbers from `scripts/localization/generate.py`.
- `regions_headroom`: per-region (`rom`/`ewram`/`iwram`) `capacity_bytes`/
  `occupied_bytes`/`free_bytes`/`overflow`, computed from the **real**
  linker `.map` for this exact build -- including the floating `.data`/
  `.bss` tail up to `__floating_end` and whatever pinned symbol follows
  it. `--check` only fails on a real `overflow: true` reported by the map
  itself; there is no fixed byte threshold anywhere in this tool (in
  particular, no hardcoded "2820"/"3508" pass criterion from earlier
  research notes -- those numbers were never load-bearing here).
