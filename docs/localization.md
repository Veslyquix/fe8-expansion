# In-game localization framework (issue #18)

Status: English/pseudo plus Japanese (`ja`) and Simplified Chinese
(`zh-Hans`) are production-configurable. The default remains English-only
and 16 MiB; any profile enabling either real CJK locale is an explicit
32 MiB build. Expansion and full-game catalogs, CJK fonts, UTF-8 rendering,
locale preference persistence, and cache switching share the same validated
profile. Focused CJK gba-playtest scenarios and committed fingerprints cover
first start, Japanese/Chinese choice, Config switching, and soft-reset
persistence.
This is an architecture/authoring/testing reference, not a GitHub issue-state
or closure claim; historical English/pseudo sprint evidence remains in
`reports/issue18_localization_closure.md`.

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
   UTF-8 text. The authored mapping currently contains `en`, `ja`, and
   `zh-Hans`; `qps-ploc` is derived from English. Validation rejects invalid
   Unicode scalars, control/format/private-use text, whitespace controls
   other than `\n`, malformed placeholders, placeholder/newline drift,
   surface-width overflow, and UTF-8 decoded-byte overflow.
   `scripts/localization/generate.py` compiles this into
   `expansion_locale_catalog.c` (ROM data) and `expansion_msg_ids.h`
   (generated header), write-if-unchanged. Its descriptor table is indexed
   by stable `ExpansionLocaleId`: populated locales point to their tables and
   unpopulated slots are explicit null descriptors. The budget reports actual
   authored/generated locales, populated descriptor count, missing entries,
   UTF-8 string bytes, pointer/descriptor bytes, decoded-max scratch, and
   Unicode scalar/glyph usage.
3. **Runtime resolver** (`src/expansion_locale.c`,
   `include/expansion_locale.h`): `ExpansionLocale_GetCurrent()` /
   `_SetCurrent()` / `_Resolve()` / `_InvalidateCache()`. Holds the
   current locale, a decoded-string cache (locale+msg-id keyed,
   invalidated on any locale change), and a small decode scratch buffer --
   all in `EWRAM_DATA` (see "The EWRAM-placement bug" below for why this
   matters). Resolution uses the generated descriptor indexed by stable
   locale ID, then performs at most one English lookup when the descriptor
   or requested entry is absent. Never reads/writes vanilla `GetLang()`/`SetLang()`/
   `gLanguageMode`/`gMsgTable`; entirely independent of the vanilla
   multi-language ROM mechanism. `ExpansionLocale_InvalidateCache()` also
   invalidates the full-game localized message cache in CJK profiles, so
   expansion UI and `GetStringFromIndex()` cannot disagree after a switch.
4. **User preferences** (`include/expansion_save_prefs.h`,
   versioned/checksummed `ExpansionUserPrefs`, Sprint 2): a small SRAM
   record (locale choice + validity state) with its own version/checksum,
   read via `ExpansionUserPrefs_Load()`/classified via `_Normalize()` into
   `ExpansionUserPrefsState` (`UNSET` / `VALID` / `MIGRATED` / `CORRUPT` /
   `UNKNOWN_LOCALE` / `DISABLED_LOCALE`), and written via `_Store()`.
   Deliberately excludes vanilla `struct SoundRoomSaveData` and every
   other pre-existing SRAM field -- see the "no-wipe" contract below.
5. **First-start selector + Config language row**
   (`src/expansion_language_menu.c`, `include/expansion_language_menu.h`,
   Sprint 3): `ExpansionLanguageMenu_DecideStartupAction()` is a pure,
   host-testable function mapping `(prefs state, enabled locale count)` to
   one of `SHOW_MENU` / `AUTO_SELECT` / `APPLY_ONLY`. The blocking first-start
   selector Proc script runs this decision once per boot, immediately
   after `ProcScr_GameEarlyStartUI` and before `ProcScr_OpAnim` (`#ifdef
   MODERN`-guarded call site in `src/gamecontrol.c`); with exactly one
   enabled locale it silently auto-selects and never shows a UI. The
   Config row selects all enabled locales inline when there are at most
   three. With more than three it shows the first two compact locale labels
   plus `More`; only `More` opens `ExpansionLanguageMenu_OpenSettings()`.
   Inline or submenu selection calls `ExpansionUserPrefs_Store()` and
   invalidates the resolver cache only when the locale actually changes;
   `Back` leaves everything untouched. A
   `struct ExpansionLanguageMenuProbe gExpansionLanguageMenuProbe` (EWRAM,
   `include/expansion_language_menu.h`) exposes `active`/`settingsActive`/
   `promptShown`/`autoSelected`/`promptReason`/`prefsState`/
   `selectedLocale`/`currentLocale`/`enabledLocaleCount`/`cacheGeneration`/
   `startupRunCount`/`settingsOpenCount`/`settingsChangeCount` for exactly
   this kind of diagnostic read -- a plain, bounded, fixed-layout struct,
   never a raw/arbitrary pointer oracle.

   Host-native tests resolve exact Japanese/Chinese expansion strings,
   sparse-entry English fallback, invalid/unpopulated slots, and both
   expansion/full-game cache invalidation. Production CJK profiles use the
   upper bank at 32 MiB. Captured CJK scenarios cover first start,
   Japanese/Chinese choice, Config switching, and soft-reset persistence.

## Config

Set at `modern.mk`/`make` invocation time (see
`scripts/modernize/expansion_config.py` for validation):

- `EXPANSION_ENABLED_LOCALES` -- comma-separated subset of the production
  allowlist `en`, `ja`, `zh-Hans`, and `qps-ploc` (default: `en`), always
  including `en` for fallback. Input order is normalized to stable locale-ID
  order.
- `EXPANSION_DEFAULT_LOCALE` -- must be a member of
  `EXPANSION_ENABLED_LOCALES` (default: `en`).
- `EXPANSION_PSEUDO_LOCALE` -- `1` enables `qps-ploc`, and requires
  `qps-ploc` to actually be present in `EXPANSION_ENABLED_LOCALES` (the two
  can never silently disagree -- `validate_pseudo_locale` rejects that
  combination outright).
- `MODERN_ROM_SIZE` -- remains `16M` by default. Enabling `ja` or `zh-Hans`
  requires exactly `32M`; English-only and English+pseudo remain valid at
  either size.

Profile examples:

```bash
# Supported default: unchanged English-only 16 MiB ROM.
make expansion-modern-rom

# Existing pseudo-locale test profile, still 16 MiB.
make expansion-modern-rom \
  EXPANSION_ENABLED_LOCALES=en,qps-ploc \
  EXPANSION_PSEUDO_LOCALE=1

# Named 32 MiB production profiles (MODERN_CONFIG=debug or release).
make expansion-modern-localization-profile-en-ja
make expansion-modern-localization-profile-en-zh-hans
make expansion-modern-localization-profile-en-ja-zh-hans

# Optional four-locale profile; Config shows EN, JA, More.
make expansion-modern-localization-profile-en-ja-zh-hans-qps
```

Equivalent direct builds may set `EXPANSION_ENABLED_LOCALES`,
`EXPANSION_DEFAULT_LOCALE`, and `MODERN_ROM_SIZE=32M` explicitly. A CJK
profile with `MODERN_ROM_SIZE=16M` fails before compilation. The named targets
use private build roots so their generated catalogs, fonts, metadata, and
objects cannot cross-contaminate one another.

These are baked into the ROM's embedded `ExpansionMetadata` (build-commit,
enabled-locale mask, default-locale id, pseudo-locale flag) so a given ROM's
config is always recoverable from the binary itself, never only from the
build invocation.


`modern.mk` derives `FE8_EXPANSION_ENABLED_LOCALE_MASK`,
`FE8_EXPANSION_ENABLED_LOCALE_COUNT`, `FE8_EXPANSION_DEFAULT_LOCALE_ID`, and
`FE8_EXPANSION_PSEUDO_LOCALE_ENABLED` from these validated inputs. The
normalized enabled list/default/pseudo setting also enters the config
fingerprint, so configuration changes are diagnosable without becoming save-
compatibility keys.

## Save compatibility, migration, and precedence

Issue #18 uses `SAVE_FORMAT_VERSION_CURRENT=2` and the repository default
`EXPANSION_SAVE_COMPAT_EPOCH=2`. `ExpansionUserPrefs` occupies a fixed
0x0C-byte subregion of `ExpansionSaveMeta.reserved`, has independent magic,
version and checksum, and leaves 0x20 bytes of reserved-tail headroom. The
outer metadata layout and neighboring XMAP offset do not move.

Classifier precedence matters: an older `formatVersion` resolves to
`SAVE_COMPAT_MIGRATABLE_OLDER` before the epoch comparison, so a genuine
version-1/epoch-1 save is migratable older, not config-incompatible. The host
`save_format_tool.py migrate` path is out-of-place, preserves an older/current
record's reserved bytes (including valid prefs), verifies before atomic
publication, and never rewrites the source. Runtime normalization falls back
to the configured default and requests repair for unset/corrupt/unknown/
disabled prefs; only a verified bounded store mutates the prefs window. The
full record, migration, no-wipe, and menu limitations are authoritative in
[`save_format.md`](save_format.md).

## Pseudo locale (`qps-ploc`) -- legal/non-goals

`qps-ploc` (`scripts/localization/pseudo.py`) is a deterministic, purely
mechanical transform of the English catalog (accenting/padding/bracketing
ASCII test markers), generated at build time from `catalog.en.json` --
**never a translation, never hand-authored foreign text, and never
represents any real language**. Every user-facing surface that can display
it (the selector list and the More submenu) labels it `"Pseudo (Test)"`;
the compact Config-row label is the cataloged code `QPS`. Locale proper
names/codes remain resolved against `EXPANSION_LOCALE_EN`
(`Japanese`/`Simplified Chinese`, `JA`/`ZH`) so every first-start row is
readable before a locale is chosen. Most Japanese/Chinese expansion-catalog
text is original expansion-framework UI/debug text.
The two `raw_surface.unit_action.*` keys are the deliberate exception: they are
semantic modern adapters for two regional game commands that share one FE8U
message ID. Their Japanese/Chinese strings retain authorized raw-source
provenance documented in `docs/game_locale_sources.md`; the raw address/import
ID never becomes the runtime key.
All current-locale labels/help/back/debug
strings, including Japanese and Chinese text, render through UTF-8-aware
`Text_DrawString`; no expansion-resolved framework surface uses
`Text_DrawStringASCII`. `ja`/`zh-Hans` are production-configurable for explicit
32 MiB builds as described above; `fr`/`de`/`es`/`it` remain unpopulated null
descriptor slots.

## Authoring

1. Add/edit entries in `texts/expansion/registry.json` (append-only IDs,
   never renumbering or reusing a retired id) and each authored
   `texts/expansion/catalog.<locale>.json`. English is the required fallback.
   The committed `ja`/`zh-Hans` catalogs intentionally cover every active
   key, although the generic resolver also handles a missing non-English
   entry with one deterministic English fallback.
   Raw-only game surfaces must use a semantic `raw_surface.*` key, not a ROM
   address or `fe8cn.raw.import-*` identifier, and must be recorded in the raw
   closure ledger.
2. `make localization-generate` (or let any modern build target
   depend on it) regenerates `expansion_locale_catalog.c`/
   `expansion_msg_ids.h`/the localization budget JSON, write-if-unchanged.
3. `python3 -m unittest discover -s scripts/localization/tests -p
   'test_*.py' -v` (or `make localization-test`) re-validates schema,
   strict UTF-8/control, surface-width and UTF-8 byte budgets, placeholder/
   newline parity, pseudo transform, descriptor generation, host-native
   exact/fallback/cache behavior, and vanilla-isolation audits.
4. CJK builds must use `MODERN_ROM_SIZE=32M`; English/qps-only builds may
   remain 16 MiB. Other real locale IDs must first gain populated catalogs,
   fonts, game-text providers, and configuration validation. Never hand-copy
   or paraphrase copyrighted
   third-party translation text into this repository (see issue #18's own
   non-goals; also see `CONTRIBUTING.md`/#6/#10's manual-copy prohibition,
   which this sprint does not touch).

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
| `locale-blank-sram-selector-multi-modern-{debug,release}` | Blank SRAM, multi-locale build (`en,qps-ploc`): issue #18 sprint 6 fixed `BuildCurrentExpansionSaveMeta()` unconditionally auto-stamping a syntactically VALID prefs record on a blank-SRAM boot regardless of enabled-locale count; the selector now genuinely shows (`active=1`, `needsPreferenceRepair=1`) and stays shown pre-title, matching a real `UNSET` fixture's own behavior. Supersedes the pre-fix `locale-blank-sram-no-selector-multi-modern-{debug,release}` pair, which had encoded the bug itself as "expected" and has been deleted. |
| `locale-auto-select-single-locale-modern-{debug,release}` | An `UNSET` prefs sub-state (real reachable fixture, not blank SRAM) with one enabled locale: `AUTO_SELECT`, `promptShown=0`, never a visible selector -- contract item "one enabled en auto-select no visible selector". |
| `locale-selector-multi-switch-qps-modern-debug` | Real selector navigation choosing `qps-ploc`; persisted via `ExpansionUserPrefs_Store` (`cacheGeneration` bump visible in probe). |
| `locale-prefs-corrupt-no-wipe-modern-debug` | Corrupt `ExpansionUserPrefs` -> re-prompt; full-SRAM hash (minus three justified exclusions below) is unchanged frame-5 to frame-600: no wipe. |
| `locale-prefs-unknown-locale-no-wipe-modern-debug` | Same, for an unknown-locale-id prefs record. |
| `locale-prefs-disabled-locale-no-wipe-modern-debug` | Same, for a prefs record naming a locale not compiled into this build. |
| `locale-repair-{unset,corrupt,unknown,disabled}-multi-modern-{debug,release}` | Issue #18 sprint 7: the real 4x2 repair matrix. Unlike the three `-no-wipe-modern-debug` rows above (single-locale build, debug-only, repair collapses to silent `AUTO_SELECT`), these 8 scenarios boot the same `en,qps-ploc` multi-locale ROM as the rest of this table, in **both** debug and release, so the real blocking selector (`active=1`, `autoSelected=0`, `needsPreferenceRepair=1`, per-state `promptReason`/`prefsState`) is what actually gets exercised and repaired. Each scenario: hashes the whole SRAM image at boot; shows the prompt; explicitly navigates down to `qps-ploc` and back up to `en` (proving a real cursor round-trip, not a scripted single keypress) before confirming the *default* English row -- the sprint-6 `mustRepair` fix (`src/expansion_language_menu.c`) is what makes `ExpansionUserPrefs_Store()` fire even though the chosen locale equals the runtime own current fallback; re-hashes the whole SRAM image (minus the same three exclusions as the no-wipe rows) to prove no-wipe across the repair; then sends a real `A+B+SELECT+START` soft reset and, on the resulting genuine second boot, proves the persisted record now classifies `VALID` and the selector/prompt stay suppressed. Superseding claim: the pre-existing `-no-wipe-modern-debug` scenarios remain honestly named (they still real-capture their own single-locale/debug/no-wipe claim) but are not, and never were, a substitute for this matrix. |
| `locale-settings-inline-single-modern-release` | Real release navigation to the single-locale Language row; Right is a no-op and never opens a redundant submenu (`settingsActive`/`settingsOpenCount` stay zero). |
| `locale-settings-real-navigation-multi-modern-debug` | Real Prep Map -> Options -> Configuration navigation in the two-locale build. RIGHT/LEFT/RIGHT selects `QPS`/`EN`/`QPS` inline, persists every change, and proves `settingsActive`/`settingsOpenCount` stay zero. |
| `locale-softreset-persistence-multi-modern-debug` | Real first-run selector chooses `qps-ploc`, then a genuine A+B+SELECT+START soft-reset key combo (held ~20-24 frames through libmGBA's own HLE BIOS -- a real hardware reboot, not a fixture swap) reboots the ROM; continuous, never-swapped SRAM: selector is skipped post-reset (`promptShown`/`active` stay 0) and `currentLocale` is `qps-ploc` again without re-selection. |
| `locale-cjk-first-start-{ja,zh-hans}-modern-debug` | Captured three-locale `en,ja,zh-Hans` first-start selector evidence with bounded probes for choosing locale id 1 or 2. |
| `locale-cjk-settings-inline-modern-debug` | Captured real Config navigation for inline EN -> JA -> ZH switching; `settingsOpenCount` stays zero because three locales fit inline. |
| `locale-cjk-softreset-persistence-modern-debug` | Captured Simplified Chinese first-start choice plus real soft-reset persistence. |

Every save/load and suspend/resume regression coverage for locale prefs
reuses the existing, unmodified `expansion-modern-saveload-check`/
`expansion-modern-savefmt-check` gates (see the `-runtime-save-check`
Make target below) rather than duplicating that harness.

Run the captured production CJK matrix with:

```bash
make expansion-modern-localization-runtime-cjk-check MODERN_CONFIG=debug
```

### The "no-wipe" SRAM-hash exclusions

The three prefs-safety scenarios' `sram_hash_exclude_ranges` are exactly:

- `{"offset": "0x7224", "length": "0x24"}` -- vanilla
  `struct SoundRoomSaveData soundRoomSave` (`include/bmsave.h`), which
  legitimately rewrites 2 of its own bytes on every boot as ordinary
  pre-existing sound-room bookkeeping, **unrelated to locale/expansion
  code or prefs state** (confirmed identical across all three fixtures via
  a full 0x8000-byte SRAM diff, chunked at the backend's 1024-probe/
  checkpoint cap).
- `{"offset": "0x73A0", "length": "0x04"}` -- the vanilla `SramInit()`
  hardware self-test scratch pad (`gSram->reserved`, `include/bmsave.h`),
  which the console's own boot-time SRAM self-test legitimately rewrites
  on every boot, **unrelated to locale/expansion code or prefs state**.
- `{"offset": "0x73D4", "length": "0x0C"}` -- the `ExpansionUserPrefs`
  record itself, which is *expected* to be rewritten (its own checksum/
  version bookkeeping) even when the effective locale choice is unchanged
  by a rejected corrupt/unknown/disabled value.

Each of these three excluded regions is additionally probed byte-by-byte
(GBA SRAM is 8-bit-wide hardware -- multi-byte reads alias a single byte
across all lanes, so every probe here uses `size: 1`) at both the pre-
runtime-init baseline and the post-decision-settled checkpoint, alongside
`ExpansionSaveMeta`'s own magic/checksum and the untouched XMAP save
header's magic/checksum/`save_magic32` -- proving these regions are
stable/known rather than silently masked by the exclusion, without hand-
writing any of their expected values (only the two genuinely vanilla,
locale-independent fields above -- the SoundRoom struct and the SRAM
self-test pad -- have inline `expected` values at all; `ExpansionSaveMeta`/
XMAP checksums are commit-dependent and therefore captured, never
hand-typed).

No other byte anywhere in the 0x8000-byte SRAM image differs between the
pre- and post-boot checkpoints for any of the three fixtures -- this is
the real, capture-verified evidence for the "corrupt/unknown/disabled
prefs never wipe SRAM" contract item, not an assumption.

### The real multi-locale repair matrix (issue #18 sprint 7)

The three `-no-wipe-modern-debug` scenarios above are real, but they only
ever run the single-locale (default `en`-only) build: with exactly one
enabled locale, `ExpansionLanguageMenu_RuntimeInit()`'s own selector logic
has nothing to prompt over, so a corrupt/unknown/disabled prefs record is
"repaired" by silent `AUTO_SELECT` -- the blocking selector itself is
never actually shown or driven. That leaves the contract's real
multi-locale prompt/choose-default repair path (and its release-build
counterpart) unproven. `tools/gba-playtest/scenarios/locale-repair-
{unset,corrupt,unknown,disabled}-multi-modern-{debug,release}.json` (8
files, all real-captured, `fingerprints/` matched, `--policy behavior`
verified) close that gap:

- **Same `en,qps-ploc` ROM as the rest of this table**, in both `debug`
  and `release` -- the release half is mandatory, never skipped.
- **Baseline**: whole-SRAM hash (minus the same three "no-wipe" exclusion
  ranges documented above -- `0x7224`/`0x24`, `0x73A0`/`0x04`,
  `0x73D4`/`0x0C`) taken before `RuntimeInit()` even runs, from the
  state-specific fixture (`unset.sav`/`corrupt.sav`/`unknown.sav`/
  `disabled_on_multi.sav` -- the last one is new this sprint, built with
  `--disabled-locale-id 1` since `qps-ploc`'s own id, 7, is *enabled* on
  this multi-locale build and therefore can no longer name a disabled
  locale here).
- **Prompt checkpoint**: `active=1`, `autoSelected=0` (never
  `AUTO_SELECT` -- this is the exact silent-repair collapse this sprint
  closes), `needsPreferenceRepair=1`, and a `promptReason`/`prefsState`
  pair matching the fixture's own real classification (`UNSET`/`CORRUPT`/
  `UNKNOWN_LOCALE`/`DISABLED_LOCALE`).
- **Real cursor round-trip**: navigates `DOWN` to `qps-ploc` (framebuffer-
  hashed) then back `UP` to `en` (framebuffer hash byte-identical to the
  original prompt checkpoint's -- proof this is a real second keypress
  landing back on the same row, not a scripted single confirm) before
  pressing `A`.
- **Explicit default-choice repair**: confirming `en` here is the
  runtime's own current fallback locale, so this exercises the sprint-6
  `mustRepair = active && needsPreferenceRepair` fix in
  `ExpansionLanguageMenu_RowSelected()` (`src/expansion_language_menu.c`)
  -- without it, choosing the row that already equals the fallback would
  short-circuit and never call `ExpansionUserPrefs_Store()`.
- **Commit checkpoint**: `active=0`, `needsPreferenceRepair=0`,
  `cacheGeneration=1` (proving `Store()` fired), the persisted record
  reads `magic=0xA5`/`version=0x01`/`localeId=0x00`(`en`)/`flags=0x01`
  (`EXPLICIT`), and the whole-SRAM hash (same three exclusions) is
  byte-identical to the baseline hash -- no wipe across the repair.
- **Real soft reset, not a fixture swap**: the literal `A+B+SELECT+START`
  combo is held on the same, never-replaced SRAM image, exactly like
  `locale-softreset-persistence-multi-modern-debug` above.
- **Post-reset checkpoints**: a fresh-EWRAM checkpoint immediately after
  reboot, then a settled checkpoint proving `active=0`, `promptShown=0`
  (selector/prompt genuinely absent, not merely unchecked) and
  `prefsState=0x05` (`VALID`) -- only a genuine second boot's own
  `Load()`+`Normalize()` can produce this classification, since the probe
  field is set once per boot and never refreshed mid-boot after
  `Store()`.

`scripts/modernize/tests/test_modern_localization_header_bootstrap.py`'s
`ModernLocalizationRepairMatrixTests` enumerates this exact 4x2 matrix as
a static host test (file/fingerprint existence, required checkpoint
names, the `A+B+SELECT+START` input, the `autoSelected=0`/prompt-reason/
prefs-state/no-wipe/VALID-after-reboot invariants above, the fixture
mapping, and that `modern.mk` wires all 8 pairs into
`expansion-modern-localization-runtime-multi-check` unconditionally,
never inside the `ifeq ($(MODERN_CONFIG),debug)` guard) -- it fails if a
release pair goes missing or a scenario silently regresses to
`AUTO_SELECT`.

### Real inline settings navigation and soft-reset persistence

`locale-settings-real-navigation-multi-modern-debug` drives the actual,
reachable in-game UI path a player uses -- Prep Map -> `Options` ->
Configuration -> `Language` -- entirely through replayed controller input.
In the two-locale build the row displays compact `EN` and `QPS` choices:
RIGHT/LEFT/RIGHT selects QPS/English/QPS without opening a submenu.
`currentLocale`, `cacheGeneration`, `settingsChangeCount`, and the persisted
prefs bytes move with each real selection, while `settingsActive` and
`settingsOpenCount` remain zero. The release-only
`locale-settings-inline-single-modern-release` route proves Right is a no-op
when English is the sole enabled locale.

`locale-softreset-persistence-multi-modern-debug` proves persistence
across an actual reboot, not a fixture swap: it replays the real
first-run-selector input choosing `qps-ploc` (same proven sequence as
`locale-selector-multi-switch-qps`), then holds the real GBA hardware
soft-reset combo (`A+B+SELECT+START`) for ~20-24 frames. libmGBA's
default HLE BIOS implements this combo without any custom backend/game
code -- holding it triggers a genuine full reboot (fresh EWRAM/BSS,
`startupRunCount` resets to 0), while the underlying SRAM image is never
swapped or replaced. Post-reboot, the selector does not reappear
(`promptShown`/`active` stay 0) and `currentLocale` reads back `qps-ploc`
without any re-selection -- real persistence across a real reboot on
continuous SRAM.

The inline scenario's framebuffer checkpoints visibly distinguish the blue
selected `EN`/`QPS` value while its EWRAM/SRAM probes establish the semantic
selection and persistence contract independently of pixels.

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
  switch-to-qps scenarios *and* -- unconditionally, for both
  `MODERN_CONFIG=debug` and `=release`, never inside the debug-only
  `ifeq` guard that scopes the other per-config-only scenarios below --
  all 8 `locale-repair-{unset,corrupt,unknown,disabled}-multi-modern-
  {debug,release}` real repair-matrix scenarios (issue #18 sprint 7; see
  "The real multi-locale repair matrix" above). The 4 new fixture
  prerequisites (`unset.sav`/`corrupt.sav`/`unknown.sav`/
  `disabled_on_multi.sav`) are declared alongside the pre-existing
  fixtures in this same file.
- `expansion-modern-localization-runtime-prefs-check`: the three,
  honestly-named, single-locale/debug-only corrupt/unknown/disabled-locale
  no-wipe scenarios. These still real-capture their own single-locale
  no-wipe claim and remain in the gate on their own merits, but they are
  **not**, and never were, a substitute for the multi-locale repair
  matrix wired into `-multi-check` above (single enabled locale means
  their repair collapses to silent `AUTO_SELECT`, never the real
  blocking selector).
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
  populated-descriptor, UTF-8 byte, Unicode-scalar, and glyph-usage numbers
  from `scripts/localization/generate.py`.
- `regions_headroom`: per-region (`rom`/`ewram`/`iwram`) `capacity_bytes`/
  `occupied_bytes`/`free_bytes`/`overflow`, computed from the **real**
  linker `.map` for this exact build -- including the floating `.data`/
  `.bss` tail up to `__floating_end` and whatever pinned symbol follows
  it. `--check` only fails on a real `overflow: true` reported by the map
  itself; there is no fixed byte threshold anywhere in this tool (in
  particular, no hardcoded "2820"/"3508" pass criterion from earlier
  research notes -- those numbers were never load-bearing here).
- `locale_bank` (when the current linker map exposes `.locale_data` and/or
  `__locale_bank_start`/`__locale_bank_end`): actual upper-bank start/end,
  occupancy, and headroom to `0x0A000000`. Older reports/maps without those
  symbols remain readable and simply omit this optional field.
