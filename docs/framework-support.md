# Framework support matrix

This is the authoritative reference for **which hosts, toolchains, build
targets, and outputs are actually supported** by this repository, and where
to go for setup steps and troubleshooting. It intentionally does not
duplicate command-by-command instructions that already live in
[`docs/quickstart.md`](quickstart.md) and [`docs/config_identity.md`](config_identity.md) —
it links to them.

## Supported hosts

| Host | Package manager | Auto-installed by `scripts/quickstart.sh` | CI-verified |
| --- | --- | --- | --- |
| Ubuntu / Debian / WSL | `apt` | Yes | Yes — `.github/workflows/build.yml` runs on `ubuntu-latest` |
| Arch Linux | `pacman` | Yes | No (community-supported; same script path as Ubuntu) |
| macOS | Homebrew (`brew`) | Yes | No (community-supported) |

Source: `scripts/quickstart.sh` detects `apt-get`, `pacman`, or `brew` (in
that order) and stops with an actionable message on any other package
manager — see the "Unsupported distro" entry in
[`docs/quickstart.md`](quickstart.md#troubleshooting). There is no native
Windows package-manager path; Windows users go through WSL (which is the
Ubuntu/`apt` path above). Do not read this as a native-Windows guarantee —
none of `scripts/quickstart.sh`, the Makefile, or CI target Windows
directly.

**CI is the only host this repository automatically re-verifies on every
push/PR.** Arch and macOS support is exercised by the same script logic but
is not re-run in CI; treat regressions there as community-reported, not
CI-caught.

## Supported toolchains

| Toolchain | Status | Used for |
| --- | --- | --- |
| `arm-none-eabi` GCC (modern, AAPCS) | **Supported release lane** | The default `make`/`make all` target, every `expansion-modern-*` target, and CI's linker/boot gates |
| agbcc (original GBA-era GCC 2.95 fork) | **Archival only, not a supported release lane** | `make legacy` (`make fireemblem8.gba`) — decomp-matching work only; see [`docs/archival-decomp.md`](archival-decomp.md) |

A bare `make`/`make all` never requires, builds, or resolves to a
`tools/agbcc` executable or library (issue #15; see `Makefile`'s `all:`
target and `docs/quickstart.md`'s "Modern GCC compile-only object cohort"
section). agbcc is fetched and built **only** when `make legacy`,
`make fireemblem8.gba`, or `./scripts/quickstart.sh --legacy` is invoked by
name.

## Build targets and outputs

| Command | What it produces | Builds a ROM? | Needs libmGBA? |
| --- | --- | --- | --- |
| `make` / `make all` | Modern release AAPCS ROM, boot-verified: `build/expansion-modern/release/aapcs/fireemblem8.gba` | Yes | Yes |
| `make expansion-modern-toolchain-check` | Verifies the modern compiler/assembler/flags resolve; no build output | No | No |
| `make expansion-modern-cohort` | Compile-only modern objects for the fast dependency-closure subset (`MODERN_COHORT_OBJECTS` in `modern.mk`, a `src/*.c` subset plus a small set of handwritten-assembly objects; reproduce the current split with `make print-MODERN_COHORT_C_OBJECTS`/`print-MODERN_COHORT_ASM_OBJECTS`/`print-MODERN_COHORT_OBJECTS` -- treat those commands, not any number written here, as authoritative). Accepts `MODERN_ABI=aapcs` (default) or `MODERN_ABI=apcs-gnu`; neither ABI choice links here, so both are safe compile-only comparisons -- see the ABI contract note below the table. | No | No |
| `make expansion-modern-all` | Compile-only modern objects for the full currently-supported source set (`MODERN_ALL_OBJECTS` in `modern.mk`, `wildcard`-derived from `src/*.c`/`src/data/**/*.c` + handwritten asm; reproduce the current split with `make print-MODERN_ALL_C_OBJECTS`/`print-MODERN_ALL_DATA_OBJECTS`/`print-MODERN_ALL_ASM_OBJECTS`/`print-MODERN_ALL_OBJECTS`); this drifts as source files are added/removed and is not re-verified on every unrelated edit -- treat the command, not any number, as authoritative. Accepts `MODERN_ABI=apcs-gnu` for the same compile-only comparison use as `expansion-modern-cohort` above. | No | No |
| `make expansion-modern-elf MODERN_CONFIG=<debug\|release> MODERN_ABI=aapcs` | Linked modern ELF + map. `aapcs` is the only ABI this (or any other linked/ROM/runtime target below) accepts -- `MODERN_ABI=apcs-gnu` fails fast in `modern.mk`'s linked-goal guard instead of producing an EABI5-incompatible link; see the ABI contract note below the table. | No | No |
| `make expansion-modern-rom MODERN_CONFIG=... MODERN_ABI=aapcs` | Header-verified modern ROM | Yes | No |
| `make expansion-modern-boot-check MODERN_CONFIG=... MODERN_ABI=aapcs` | Modern ROM + deterministic boot-fingerprint verification (frames 0/60/120) | Yes | Yes |
| `make expansion-modern-linker-check MODERN_CONFIG=... MODERN_ABI=aapcs` | Boot-check plus budget/shift/overlay/title-fingerprint gates | Yes | Yes |
| `make legacy` / `make fireemblem8.gba` | Archival agbcc `fireemblem8.gba` | Yes | No (agbcc, fetched on first use) |
| `make clean` / `make clean_fast` | Removes build artifacts (see [`README.md`](../README.md)) | — | — |
| `make generated-data-validate` / `-generate` / `-check` / `-test` | Structured content authoring (see [`docs/generated_data_tutorial.md`](generated_data_tutorial.md)) | No | No |
| `make localization-validate` / `make localization-generate` / `make localization-check` / `make localization-test` | Expansion locale registry/catalog authoring and host tests (see [`localization.md`](localization.md)) | No | No |
| `make expansion-modern-starter-runtime-check MODERN_CONFIG=... MODERN_ABI=aapcs` | Issue #6 enabled/disabled mechanics + Threat Range runtime matrix | Yes | Yes |
| `make expansion-modern-localization-budget-check MODERN_CONFIG=... MODERN_ABI=aapcs` | Issue #18 catalog/resolver/UI source+linker budget and real region headroom | No new ROM beyond its linked prerequisite | No |
| `python3 -m scripts.upstream_port {scan,drift,report,verify,...}` | Upstream-drift tracking (see [`docs/upstream-porting.md`](upstream-porting.md)) | No for `scan`/`drift`/`report`; `verify` builds the full gate set | No for `scan`/`drift`/`report`; depends on the gate set for `verify` |

**ABI contract:** `MODERN_ABI=aapcs` is the only supported choice for every
linked, ROM-producing, or runtime-gate target above (`expansion-modern-elf`,
`-rom`, `-boot-check`, `-linker-check`, and every target that transitively
depends on them, e.g. `-savefmt-check`/`-title-check`/`-debugtools-*-check`/
`-budget`/`-budget-check`/`-relocs`/`-overlay-audit`/`-shifted-check`).
Requesting `MODERN_ABI=apcs-gnu` for any of them fails fast in `modern.mk`
(`... requires MODERN_ABI=aapcs; ... apcs-gnu objects are incompatible with
EABI5 newlib/libgcc`) rather than silently producing a broken link --
reproduce this yourself with
`make -n expansion-modern-elf MODERN_CONFIG=debug MODERN_ABI=apcs-gnu`
(dry-run; the error still fires before any recipe would run). The **only**
targets that accept `MODERN_ABI=apcs-gnu` are the compile-only
`expansion-modern-cohort`/`expansion-modern-all` object targets above, for
cross-ABI struct-layout comparison (see
[`docs/save_format.md`](save_format.md#cross-compiler-persisted-struct-layout-compatibility));
neither of those targets links, so apcs-gnu objects never reach a linker
there.

Every `make TARGET` invocation on this page is checked by
[`scripts/check_docs.py`](../scripts/check_docs.py) (`parse_make_targets`/
`make_target_exists`, a static parse of the `Makefile`/`modern.mk`/
`generated_data.mk` include graph -- see
[`reports/issue17_documentation_audit.md`](../reports/issue17_documentation_audit.md#stale-reference-and-command-existence-evidence)
for how that check works) so a renamed/removed target fails
`scripts/check_docs.py --check` before merge. To reproduce target
resolution or object counts yourself against the current worktree, run
`make -n <target>` (dry-run, never invokes a compiler) or
`make print-<VARIABLE>` (e.g. `make print-MODERN_COHORT_OBJECTS`) --
no ROM build or network access is required for either.

### Fast (no-ROM) vs. full (ROM, optionally + libmGBA) commands

- **Fast / no-ROM**: `expansion-modern-toolchain-check`, `expansion-modern-cohort`,
  `expansion-modern-all`, `expansion-modern-elf`,
  `generated-data-validate`/`-generate`/`-check`/`-test`,
  `scripts.upstream_port scan`/`drift`/`report`, `scripts/artifact_guard.py`,
  any `python3 -m unittest discover -s .../tests`.
- **Full / builds a ROM**: `expansion-modern-rom` (no libmGBA needed),
  `make legacy`/`make fireemblem8.gba` (no libmGBA needed), the bare
  `make`/`make all` default, `expansion-modern-boot-check`,
  `expansion-modern-linker-check`, `expansion-modern-debugtools-*-check`,
  `expansion-modern-savefmt-check` (these five need libmGBA too), and
  `scripts.upstream_port verify`.

## Configuration surface

The full settings reference (versions, ROM identity, `MODERN_CONFIG`/
`MODERN_ABI`/`MODERN_ROM_SIZE`/`MODERN_TEXT_SHIFT`, the config-identity
fingerprint, and what is/isn't save-compatibility-relevant) lives in
[`docs/config_identity.md`](config_identity.md); this document does not
duplicate it.

## Troubleshooting

Setup troubleshooting (missing sudo, stale Arch package DB, already-installed
toolchain, slow rebuilds) is maintained in one place:
[`docs/quickstart.md`](quickstart.md#troubleshooting). Modern-toolchain
compile-probe failures and the Homebrew cask-vs-formula pitfall are covered
in [`docs/quickstart.md`](quickstart.md#modern-gcc-compile-only-object-cohort).

## Merged framework contracts

Issues **#6**, **#10**, **#11**, **#13**, and **#18** have implementation
merged into the current source tree. This is not an issue-closure action; each
surface remains bounded by its live reference and evidence report.

- **#6 starter features:**
  `EXPANSION_MECHANICS_HOOKS`, `EXPANSION_MECHANICS_SAMPLE`,
  `EXPANSION_DANGER_OVERLAY_MENU`, and `EXPANSION_STARTER_CONTENT` all default
  to `0`. Sample requires hooks; starter content requires hooks and
  `FE8_ITEM_ID_CAP>=0xCE`. The mechanics registry has typed callbacks, eight
  slots, copied key/label storage, deterministic order, explicit error codes,
  and a reentrancy guard. Debug and release both run enabled and default-
  disabled runtime negatives; the content profile rides the existing item-
  expansion gates. See [`starter_features.md`](starter_features.md).
- **#10 typed IDs:** DEFAULT committed and ACTIVE build-local contracts,
  consumer census, and modern-only item cap `0xCE` pilot are supported; its
  debug/release runtime commands are gates 10-11 of the current-master
  11-gate upstream-port verifier. There is no class/chapter/unit/character
  widening
  or implied save migration. See
  [`id_space.md`](id_space.md).
- **#11 debug tools:** release-safe config gate, fixed-capacity action API,
  title/map/prep entry points, five bounded tools, and scalar diagnostics are
  supported. No full debug-print protocol, arbitrary memory editor, or
  interactive debugger is claimed. See [`debugtools.md`](debugtools.md).
- **#13 runtime harness:** deterministic JSON scenarios/fingerprints,
  `GBA_PLAYTEST_HOST_ONLY=1`, timeout/retry/provenance policy, and live ROM
  verification are supported. Ubuntu + `arm-none-eabi` is the only CI matrix;
  macOS/Homebrew remains documented local support, not CI evidence.
- **#18 localization:** append-only locale/message IDs, English and generated
  `qps-ploc`, build config/derived defines, resolver/cache, independently
  checksummed prefs, save format/epoch 2 migration precedence, first-start
  selector/repair, settings and soft-reset persistence, source/linker budgets,
  and host/debug/release/shifted/save runtime matrices are supported. Reserved
  locale slots have no catalog content and pseudo is not a translation. See
  [`localization.md`](localization.md) and [`save_format.md`](save_format.md).

The archival agbcc lane remains explicit and default-only for these expansion
features. Modern output is judged by link/boot/runtime behavior, never vanilla
ROM byte identity.

## Future versioned release work (issue #9)

No release automation, semantic-version/tag/changelog contract, versioned
artifact publication, or downstream updater exists in the current tree.
[`release-migration-template.md`](release-migration-template.md) is unfilled
future scaffolding, not a current release procedure.
