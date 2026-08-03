# Architecture overview

This is a concise map of the expansion framework's architecture. Each
section links to the source paths and deep docs that are the actual
authority — this document does not restate their full contents.

## Build & linker

- **Modern lane (supported release)**: `Makefile`'s `all:` target
  unconditionally builds `expansion-modern-boot-check MODERN_CONFIG=release
  MODERN_ABI=aapcs`. The modern build rules live in `modern.mk`; the linker
  script is `linker/expansion.ld` (section-oriented ROM/IWRAM/persistent
  EWRAM/mutually-exclusive EWRAM overlays, with linker assertions against
  orphan sections, overlap, and overflow).
- **Archival lane**: `make legacy` (`make fireemblem8.gba`) uses the
  original `ldscript.txt` and agbcc. See
  [`docs/archival-decomp.md`](archival-decomp.md).
- Deep reference: [`docs/quickstart.md`](quickstart.md) (targets, flags,
  IWRAM pinning rationale) and [`docs/framework-support.md`](framework-support.md)
  (target/output matrix).

## Generated data platform

Structured JSON under `src/data/` (characters, classes, items, supports,
terrain/movement/weapon-triangle mechanics, and the Chapter 2 slice) is
validated and compiled to typed C89 by `scripts/generated_data/` (driven by
`generated_data.mk`). This is the supported way to author FE8 content —
hand-editing generated C under `build/generated/data/` is not.

- Full design/reference: [`docs/generated_data.md`](generated_data.md)
- Contributor walkthrough: [`docs/generated_data_tutorial.md`](generated_data_tutorial.md)
- Discoverable table/record registry: [`reports/generated_data_manifest.md`](../reports/generated_data_manifest.md)


## Starter extension layer (issue #6)

Four independent, fingerprinted flags default to off: mechanics hooks, the
content-free sample mechanic, the Threat Range menu, and starter content.
`include/expansion_mechanics.h` exposes the typed fixed-capacity battle-stat
registry; callbacks receive a mutable subject plus a read-only opponent/config
context, with explicit capacity, lifetime-copy, duplicate, length, disabled,
and reentrancy behavior. The typed `ITEM_EXPANSION_CE` example is authored by
the generated-data/content-text pipeline and requires both the hooks flag and
an active item cap of at least `0xCE`. Full API, dependency, debug/release,
positive/negative runtime, budget, save, and legal boundaries:
[`starter_features.md`](starter_features.md).

## Localization layer (issue #18)

`texts/expansion/registry.json` and `catalog.en.json` are the stable source of
truth for append-only `ExpansionMsgId` values and English strings;
`ExpansionLocaleId` reserves stable locale slots. The modern runtime links the
English catalog and the derived `qps-ploc` QA transform, an EWRAM resolver
cache, checksummed locale preferences inside the existing save metadata,
first-start selection/repair, and a Config settings submenu. This is
independent of vanilla `MSG_*`/`GetLang()` state. Full authoring, save
precedence/migration, runtime/shifted/budget matrices, and legal non-goals:
[`localization.md`](localization.md) and [`save_format.md`](save_format.md).

## Config identity & save format

- `config.mk` (root, committed) plus `modern.mk`'s `MODERN_CONFIG`/
  `MODERN_ABI`/`MODERN_ROM_SIZE`/`MODERN_TEXT_SHIFT` presets define the
  framework's version, ROM identity, and ABI/layout choices, folded into a
  deterministic config-identity fingerprint embedded in every modern ROM
  (`struct ExpansionMetadata`, `include/expansion_metadata.h`). Full
  reference: [`docs/config_identity.md`](config_identity.md).
- Save-format compatibility (on-media record, raw-byte classifier,
  save-menu compatibility gate/UI) is a **separate**, narrower key
  (`EXPANSION_SAVE_COMPAT_EPOCH`) from the config fingerprint above — see
  [`docs/save_format.md`](save_format.md) for exactly when to bump it and
  what it gates.

## Proc system, runtime, and debug tooling

- The engine's cooperative multitasking core is the **Proc** system
  (`include/proc.h`, `src/proc.c`): tree-based scheduler, `struct Proc`
  entities, `struct ProcCmd[]` script tables (`PROC_CALL`, `PROC_REPEAT`,
  `PROC_SLEEP`, `PROC_YIELD`, `PROC_START_CHILD_BLOCKING`, etc).
- **Debug tools (issue #11, merged)**: a release-safe config gate
  (`FE8_EXPANSION_DEBUGTOOLS_ENABLED`), a fixed-capacity action-registration
  API, title/map/prep hotkey hub entry points, five bounded validated
  tools (unit/convoy/flags/RNG/save-state), and structured diagnostics
  (probe/log ring, non-fatal assert record) are the supported, merged
  surface — see [`docs/debugtools.md`](debugtools.md) and
  `reports/debugtools_issue11_closure.md`. Its own "Remaining #11 scope"
  section is the current, authoritative list of the few narrow,
  deliberate non-goals that remain (a full `mgba_printf` debug-print
  protocol, an interactive debugger, and an arbitrary memory editor are
  never attempted; migrating the remaining dormant chapter/BGM-commit
  tools out of `bmdebug.c`/`uidebug.c` is clearly-scoped future work) — it does
  not claim a full `mgba_printf`/interactive-debugger/memory-editor surface,
  which was never this issue's scope.

## Runtime verification / test surfaces

- `tools/gba-playtest/` replays JSON input scenarios through libmGBA and
  verifies deterministic framebuffer/RAM-checkpoint fingerprints bound to
  ROM provenance (SHA-1, size, header title/game code). See its own
  `README.md` for scenario/fingerprint format and host tests.
- `expansion-modern-boot-check` verifies the `boot.json` scenario at frames
  0/60/120 with `--policy behavior` (not byte-identity — the modern ROM is
  not byte-identical to the legacy ROM). `expansion-modern-linker-check`
  adds budget-drift, shift, and overlay-audit gates on top.
- **This is issue #13's merged, supported regression harness, not
  single-scenario spot-checking.** `tools/gba-playtest` now provides the
  full deterministic scenario/fingerprint suite (boot, title, new-game,
  chapter load, combat, suspend/resume, save/load, debugtools hub/tools —
  see its README's "Deterministic runtime scenario coverage (issue #13)"
  table), a host-only vs. normal (live-ROM) run mode
  (`GBA_PLAYTEST_HOST_ONLY=1`, also gate 1 of the pinned 10-gate
  `scripts/upstream_port/verify.py`) that keeps scenario/schema/generator/
  config/timeout/retry-policy tests toolchain-free while skipping only the
  live-integration tests, an explicit human-run-only baseline-refresh
  policy (no `verify --write-baseline`-style flag exists anywhere in the
  tool; refreshing a fingerprint is always a reviewed `capture -o <path>`
  commit — see `docs/issue-resolution-policy.md`'s "Baseline and
  fingerprint review"), and relocation-independent probes rather than a
  proc ROM-pointer oracle. The supported CI host matrix is Ubuntu +
  `arm-none-eabi` — see
  [`docs/framework-support.md`](framework-support.md#merged-framework-contracts)
  and `reports/gba_playtest_issue13_closure.md` for the scenario-by-
  scenario DONE evidence.

## Upstream-port tooling

`scripts/upstream_port/` (issue #12) is read-only-by-default tooling that
tracks drift against the canonical upstream decomp repository
(`https://github.com/laqieer/fireemblem8u.git`), classifies unreviewed
commits, and lets a human maintainer explicitly select, review, and
manually apply patches. Nothing in it auto-applies, merges, commits,
branches, pushes, or fetches without an explicit subcommand. Full
reference: [`docs/upstream-porting.md`](upstream-porting.md).

## Public extension boundaries

**Merged into the current source tree** (this is a source-state statement,
not a GitHub issue-state/closure action):

- **#6 starter features:** four default-off flags, typed mechanics registry,
  generated `ITEM_EXPANSION_CE` content-text example, and Threat Range QoL.
  No second registry, persisted option, new graphics, borrowed vanilla text,
  or broad content pack is promised.
- **#10 typed IDs:** DEFAULT/ACTIVE ID-space contracts and the modern-only
  item-cap pilot. Character/class/chapter/unit widening remains out of scope.
- **#11 debug tools:** release-safe registration/hub/five bounded tools and
  scalar diagnostics; no arbitrary memory editor or interactive debugger.
- **#13 regression harness:** deterministic host-only and live libmGBA
  scenarios; Ubuntu is the CI host, while macOS is local-only support.
- **#18 localization:** stable locale/message IDs, English plus derived pseudo
  catalog, resolver/cache, checksummed prefs, first-start/settings UI, runtime
  and budget gates. Reserved locale IDs are not translations; no foreign
  copyrighted catalog is shipped.

**Future-only #9 boundary:** no release automation, tag/changelog contract,
versioned artifacts, or downstream updater exists. The present governance
policy and [`release-migration-template.md`](release-migration-template.md)
are not a release process.

## See also

- [`docs/README.md`](README.md) — full docs index and learning paths.
- [`docs/framework-support.md`](framework-support.md) — hosts, toolchains,
  targets, outputs.
- [`docs/project-governance.md`](project-governance.md) — contribution,
  security, provenance, and compatibility governance.
