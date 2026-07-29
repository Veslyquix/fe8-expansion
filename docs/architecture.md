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

- `tools/gba-playtest/` replays a JSON input scenario through libmGBA and
  verifies deterministic framebuffer/RAM-checkpoint fingerprints bound to
  ROM provenance (SHA-1, size, header title/game code). See its own
  `README.md` for scenario/fingerprint format and host tests.
- `expansion-modern-boot-check` verifies the `boot.json` scenario at frames
  0/60/120 with `--policy behavior` (not byte-identity — the modern ROM is
  not byte-identical to the legacy ROM). `expansion-modern-linker-check`
  adds budget-drift, shift, and overlay-audit gates on top.
- **This is single-scenario, targeted verification, not a general
  regression suite.** A complete regression-scenario library, a supported
  host matrix for runtime verification, and a documented verification
  policy are **issue #13 follow-up work**, not current fact — do not read
  the existing scenarios/fingerprints as that broader guarantee.

## Upstream-port tooling

`scripts/upstream_port/` (issue #12) is read-only-by-default tooling that
tracks drift against the canonical upstream decomp repository
(`https://github.com/laqieer/fireemblem8u.git`), classifies unreviewed
commits, and lets a human maintainer explicitly select, review, and
manually apply patches. Nothing in it auto-applies, merges, commits,
branches, pushes, or fetches without an explicit subcommand. Full
reference: [`docs/upstream-porting.md`](upstream-porting.md).

## Public extension boundaries — merged (#10/#11/#13) vs. active (#6/#9/#18)

**Merged, supported today** (see [`docs/framework-support.md`](framework-support.md#merged-framework-contracts-issues-10-11-13) and each closure report for exact bounds — this section only summarizes):

- **Issue #10 — typed IDs / extensible content-ID contracts, limits.** The
  DEFAULT/ACTIVE ID-space contract (`include/id_space.h`, `docs/id_space.md`,
  `reports/id_space_audit.md`) is the current public interface. Migrations
  for domains beyond the item-ID cap raise are not built — see
  `reports/issue10_closure.md`'s explicit non-goals before assuming otherwise.
- **Issue #11 — debug-tools extension/config/safety interface.** The
  registration API, hotkey hub entry points, five bounded validated tools,
  and structured diagnostics are the current, supported surface (see above
  and `docs/debugtools.md`). `mgba_printf`/interactive-debugger/memory-editor
  remain explicit non-goals, not a gap in this closure.
- **Issue #13 — regression-scenario library, host matrix, runtime-verification
  policy.** `tools/gba-playtest` now provides the full deterministic
  scenario suite, host-only vs. normal run modes, and retry/timeout/
  provenance policy described in its own `README.md`; the supported CI host
  matrix is Ubuntu + `arm-none-eabi` (see `docs/framework-support.md`).

**Active/unmerged — do not read as current support:**

- **Issue #6** (starter expansion feature bundle), **issue #9** (versioned
  releases/downstream upgrades), and **issue #18** (in-game multilingual
  support) are open. No public hook-registry, release/versioning, or
  language-selection API exists in this baseline; this document makes no
  current-stability or completeness claim for any of them, and no GitHub
  issue-state (open/closed) claim either.

## See also

- [`docs/README.md`](README.md) — full docs index and learning paths.
- [`docs/framework-support.md`](framework-support.md) — hosts, toolchains,
  targets, outputs.
- [`docs/project-governance.md`](project-governance.md) — contribution,
  security, provenance, and compatibility governance.
