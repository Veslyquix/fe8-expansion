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

## Later integration slots (not yet part of this support matrix)

The following are **explicitly not** part of the current support matrix and
must not be read as stable/complete until their own follow-up documentation
update lands:

- **Issue #10** (extensible ID contracts / limits / migrations) — no final,
  merged public interface exists in this baseline; nothing here should be
  read as a supported content-ID API.
- **Issue #11** (debug-tools extension surface) — slices 1-2 exist (see
  [`docs/debugtools.md`](debugtools.md)) but the document's own "Remaining
  #11 scope" section lists explicitly deferred work; there is no supported,
  final debug-tools extension/config/safety interface yet.
- **Issue #13** (regression/host-matrix policy) — `tools/gba-playtest`
  provides deterministic single-scenario fingerprint verification today
  (see its own `README.md`); a complete regression-scenario suite, a
  supported host matrix, and a runtime-verification policy are follow-up
  work, not current fact.
