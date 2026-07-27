# Fire Emblem 8U Quick Start

> Part of the [documentation index](README.md). This is the setup guide for
> both the supported modern framework (default) and the archival agbcc
> lane (`--legacy`) — see [`framework-support.md`](framework-support.md)
> for the full supported-host/toolchain/target matrix and
> [`archival-decomp.md`](archival-decomp.md) for manual archival setup
> steps and the decompiling workflow itself.

Get a working build of this ROM-hack base with a single command using the
bundled `scripts/quickstart.sh` helper. If you run on an unsupported
package manager, see "Unsupported distro" under Troubleshooting below, or
[`framework-support.md`](framework-support.md) for exactly which hosts are
auto-installed vs. CI-verified.

## Prerequisites

- _(Optional)_ A legally obtained copy of **Fire Emblem: The Sacred Stones
  (USA)**. The build does **not** need it; it is only used by `asmdiff.sh` for
  disassembly comparison. If you have one, place it at the repo root as
  `baserom.gba`, or pass `--rom /path/to/rom.gba` (or
  `FIREEMBLEM8U_ROM=/path/to/rom.gba`).
- Ubuntu/WSL (apt), Arch Linux/pacman, or macOS/Homebrew with sudo/admin access. The script only auto-installs dependencies for these package managers; other environments can still run manually.
- ~2.5 GB of free disk space and up to 15 minutes for the first full build.

## One-command setup

From the repo root, run:

```bash
./scripts/quickstart.sh [--rom /path/to/baserom.gba] [--legacy] [--refresh-agbcc]
```

What the script now does by default (no `--legacy`) — **no agbcc of any kind
is installed or invoked on this path**:

1. Copies `baserom.gba` from the `--rom` path (or `FIREEMBLEM8U_ROM`) if you provided one. A missing ROM is fine — it is optional and not required to build.
2. Detects your package manager (`apt`, `pacman`, or `brew`) and installs the prerequisites only when they’re not already available:
   - Toolchain (`arm-none-eabi-binutils`, `arm-none-eabi-gcc`, and newlib headers; the official Arm cask on macOS)
   - The libmGBA playtest backend (`libmgba-dev` on apt, `mgba` on pacman/Homebrew) used by the boot-check step below
   - `pkg-config` / `pkgconf`
   - `libpng`
   - `python3`, `pip3`, `numpy`, `pillow`
3. Fetches submodules (`git submodule update --init --recursive`). The FE6 SIO link payload is built from source via the [mgfembp](https://github.com/StanHash/mgfembp) submodule using modern GCC — no agbcc variant of any kind is fetched/built on this path.
4. Builds helper tools via `./build_tools.sh`.
5. Runs `make expansion-modern-toolchain-check` then `make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs -j"${jobs}"` (using `nproc`, `sysctl -n hw.logicalcpu`, or 1 job in that order), which builds the full modern object/ELF/ROM chain and verifies all three boot checkpoints (frames 0/60/120).

On success you’ll see:

```
[✓] Modern build complete: /path/to/fireemblem8-expansion/build/expansion-modern/release/aapcs/fireemblem8.gba
```

### Archival `--legacy` path

Pass `--legacy` (or `--refresh-agbcc`, which implies it) to build the
archival agbcc-based `fireemblem8.gba` instead — this is the path used for
decomp-matching work (see `CONTRIBUTING.md`), not the default/supported
build. With `--legacy`, the script additionally:

1. Checks whether `tools/agbcc/bin/agbcc` already exists. If it does, the script reuses it; otherwise it clones and builds [`pret/agbcc`](https://github.com/pret/agbcc) inside `.deps/agbcc` (ignored by git), installs it into `tools/agbcc`, and you can force a refresh any time with `--refresh-agbcc`.
2. Runs `make legacy -j"${jobs}"` (the explicit, clearly-named archival alias -- identical to the pre-existing `make fireemblem8.gba -j"${jobs}"`) to produce `fireemblem8.gba` instead of the modern boot-check. A bare `make`/`make all` always builds the modern release lane unconditionally (issue #15); there is no environment variable or `make` command-line variable that redirects it to the archival build instead, so quickstart names the `legacy` target directly rather than relying on any such override. The first build also fetches/builds mgfembp's own agbcc variant (`010110-ThumbPatch`) for its FE6 SIO sub-build, which is only exercised by this archival path.

On success you’ll see:

```
[✓] Legacy build complete: /path/to/fireemblem8-expansion/fireemblem8.gba
```

## Troubleshooting

- **No ROM** – `baserom.gba` is optional; the build works without it. Provide
  `--rom /path/to/rom.gba` (or `FIREEMBLEM8U_ROM=/path/to/rom.gba`) only if you
  want to use `asmdiff.sh`.
- **No sudo/root** – apt/pacman installs require elevated privileges. Without
  sudo the script stops and asks you to install the prerequisites manually.
  Homebrew installs keep working without sudo.
- **Unsupported distro** – Install the prerequisites manually (arm-none-eabi toolchain, libmGBA, pkg-config, libpng, python3, pip, numpy, pillow) then rerun the script; it’ll skip package installs once the tools are on your PATH.
- **Already-installed toolchain** – The script detects `arm-none-eabi-*` binaries and skips reinstalling them. `--legacy`'s existing `tools/agbcc` installs are reused too; run `./scripts/quickstart.sh --legacy --refresh-agbcc` if you need a fresh copy.
- **Stale Arch package database** – The script never performs a partial
  `pacman` upgrade. Complete a full
  `sudo pacman --sync --refresh --sysupgrade`, then rerun it.
- **Slower rebuilds** – Subsequent runs are faster. For incremental modern
  work, run `make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs -j4`
  (or choose another suitable job count) manually, or just a bare `make -j4`/
  `make all -j4` (equivalent, since that is now the default release lane);
  for `--legacy` rebuilds, use `make legacy -j4` (or the pre-existing
  `make fireemblem8.gba -j4`) by name.

After the script finishes, launch your preferred emulator with the printed ROM
path or start modifying the source.

## Modern GCC compile-only object cohort

The modern bootstrap compiles a verified set of C files (reproduce the
current count against this worktree with `make print-MODERN_COHORT_C_OBJECTS`,
rather than trusting a number written here) and a small, fixed set of
handwritten assembly files (named below) to ARM relocatable objects only.
This cohort target itself does **not** link an ELF or a ROM — the fuller modern chain
(`expansion-modern-elf` → `expansion-modern-rom` → `expansion-modern-boot-check`,
documented below) is what the default quickstart path now builds and
boot-verifies as the supported release ROM, superseding the legacy ROM as the
default/supported output; `--legacy` remains available for archival/decomp
work. A bare `make`/`make all` (issue #15) builds and boot-verifies this same
modern release ROM directly, with no quickstart script required and no
`tools/agbcc` executable or library ever needed or resolved; `make legacy`
(equivalent to the pre-existing `make fireemblem8.gba`) is the named,
explicit way to reach the archival lane instead. The modern
`ap.o`, the save objects (`bmsave-misc.o`, `bmsave-gmap.o`,
`bmsave-lib.o`, `bmsave.o`, and `bmsave-xmap.o`), the convoy/container object
(`bmcontainer.o`, which defines `ClearSupplyItems` and `GetConvoyItemArray` for
save dependency closure but is not itself one of the save objects), the Proc
scheduler object (`proc.o`), the hardware/input object (`hardware.o`, which
calls into `proc.o`'s `Proc_Start`), and the object defining `AgbMain` are
compile-only *under this target*: `expansion-modern-cohort` itself never
links an ELF or a ROM, so none of them is linked or executed as part of
running this target. That is not the same as saying these objects are
never linked at all -- the cohort's C sources are a strict subset of
`MODERN_ALL_C_SOURCES`, and the cohort and full/linked targets share the
same isolated `build/expansion-modern/<config>/<abi>/` output tree, so an
already-built cohort object for a given `MODERN_CONFIG`/`MODERN_ABI` is
reused, not recompiled, by a later `expansion-modern-elf`/`-rom`/
`-boot-check` run with a matching `MODERN_CONFIG` and
`MODERN_ABI=aapcs` (the only ABI those linked targets accept) -- meaning
these same objects are among the ones that do get linked into, and
executed by, the modern AAPCS ROM once that fuller chain runs.
`proc.o` and
`hardware.o` are neither save nor container objects; they close prior
cohort-internal Proc and key/VBlank dependencies but do not claim OAM,
software-reset, callback, ABI, SRAM, EWRAM-overlay, or any other runtime
readiness on their own. Cross-ABI layout probes cover the world-map save structures, but
this does not claim callback, ABI, SRAM, EWRAM-overlay, or save-persistence
readiness.

The cohort also assembles the handwritten files that must not be
decompiled (see `CONTRIBUTING.md`): `libagbsyscall.o` is a self-contained set
of BIOS SWI trampolines (`SoftReset`, `SoundBiasReset`, `SoundBiasSet`, and
others), while `arm.o` and `arm_call.o` are a coupled ARM/Thumb interwork
pair — `arm_call.o`'s Thumb trampolines branch directly into `arm.o`'s
ARM-mode functions, so they are promoted together. Adding these closes 17
prior cohort-unsatisfied symbols (the debug/aapcs unsatisfied set moves from
139 to 131), including `ClearOAMBuffer`, `SoftReset`, `SoundBiasReset`, and
`SoundBiasSet`, while exposing nine new IWRAM/ROM data
globals that `arm.o` references but does not define: `gBmMapTerrain`, `gBmMapUnit`,
`gMovMapFillStPool1`, `gMovMapFillStPool2`, `gMovMapFillState`,
`gMsgHuffmanTable`, `gMsgHuffmanTableRoot`, `gWorkingBmMap`, and
`gWorkingTerrainMoveCosts`. `arm.s`'s 13 exported functions are not yet typed
in `include/functions.h` (most are placeholder `// ??? Name(???);` comments);
this cohort promotion assembles the handwritten source as-is and does not
type those exports, link, boot, or otherwise claim runtime readiness.

Install GCC, binutils, and newlib headers for `arm-none-eabi`. Package names are
`gcc-arm-none-eabi`, `binutils-arm-none-eabi`, and
`libnewlib-arm-none-eabi` on Ubuntu/WSL; `arm-none-eabi-gcc`,
`arm-none-eabi-binutils`, and `arm-none-eabi-newlib` on Arch; and
the official `gcc-arm-embedded` Homebrew cask on macOS:

```bash
brew install --cask gcc-arm-embedded
```

Do not use Homebrew core's `arm-none-eabi-gcc` formula for this cohort: it is
configured without target headers. If it is already installed and takes
precedence, run `brew uninstall arm-none-eabi-gcc`, install the cask above, and
rerun the quickstart. The script checks both `<stdlib.h>` and `global.h` after
installation.

The system toolchain selected by the existing `PREFIX` (default
`arm-none-eabi-`) is used by default. Ubuntu's `/usr/include/newlib` is detected
automatically when present, so apt users can run the plain commands:

```bash
make expansion-modern-toolchain-check
make expansion-modern-cohort
```

Outputs are isolated under
`build/expansion-modern/<config>/<abi>/` (C objects under `src/`, the
handwritten assembly objects under `src/` and `asm/`, matching each source's
own directory) as one `.o`/`.d` pair per cohort source file; reproduce the
current C, assembly, and combined object counts against this worktree with
`make print-MODERN_COHORT_C_OBJECTS`, `make print-MODERN_COHORT_ASM_OBJECTS`,
and `make print-MODERN_COHORT_OBJECTS` rather than trusting a number written
here. Select `MODERN_CONFIG=debug` (`-Og -g3`, the default) or `MODERN_CONFIG=release`
(`-O2 -g0 -DNDEBUG`). Select `MODERN_ABI=aapcs` (GCC's default ABI, the
supported choice for linked outputs) or `MODERN_ABI=apcs-gnu` (compile-only
layout comparison, incompatible with EABI5 runtime libraries).
The language mode stays `-std=gnu11` with `-fgnu89-inline` added solely so
that plain (non-static) `inline` definitions keep emitting an external
symbol the way legacy agbcc always did, not a broader GNU89 language switch.

For unpacked/local toolchains, use generic overrides rather than editing the
makefile. Paths containing spaces are supported:

```bash
make expansion-modern-cohort \
  MODERN_TOOLCHAIN_ROOT="/path with spaces/toolchain/usr" \
  MODERN_BINUTILS_DIR="/path with spaces/binutils" \
  MODERN_NEWLIB_INCLUDE="/path with spaces/newlib"
```

`MODERN_BINUTILS_DIR` is passed to GCC as `-B<dir>/`, and
`MODERN_NEWLIB_INCLUDE` is optional when GCC already finds its target headers.
`MODERN_CC` and `MODERN_OBJDUMP` provide direct executable overrides.
Run `make expansion-modern-clean` to remove only `build/expansion-modern`
(this also removes the full-source outputs described below, since both
targets share the same isolated output tree).

### Full-source modern compilation target

`expansion-modern-all` compiles every currently supported translation unit —
every authoritative C file (normal `src/*.c` sources, including the generated
`src/msg_data.c`, plus the preprocessed data files under `src/data/**`; reproduce
the current split with `make print-MODERN_ALL_C_OBJECTS` and
`make print-MODERN_ALL_DATA_OBJECTS`) and the same handwritten assembly files as
the fast cohort (`make print-MODERN_ALL_ASM_OBJECTS`) — to relocatable
objects only. Like `expansion-modern-cohort`, it does not link an ELF or a
modern ROM. `expansion-modern-cohort` remains the fast, default,
dependency-closure-focused migration target; `expansion-modern-all` is the
comprehensive target proving the complete currently-supported source set
still compiles under modern GCC as the source tree grows.

```bash
make expansion-modern-toolchain-check
make expansion-modern-all
```

Outputs land in the same isolated `build/expansion-modern/<config>/<abi>/`
tree as the fast cohort (objects already built by `expansion-modern-cohort`
are not recompiled, since the cohort's C sources are a strict subset of the
full `MODERN_ALL_C_SOURCES` list) as one `.o`/primary `.d` pair per source;
reproduce the current combined object/dependency count against this worktree
with `make print-MODERN_ALL_OBJECTS` rather than trusting a number written
here. `MODERN_CONFIG`, `MODERN_ABI`, and the toolchain override variables
above all apply the same way.

Data files under `src/data/**` embed `INCBIN_U8`/`INCBIN_U16` binary and
graphics assets that modern GCC cannot consume directly. Each one is compiled
in two steps: `tools/preproc` expands the `INCBIN_*` macros into an
intermediate `<name>.pre.c` file (leaving `#include` directives untouched),
and modern GCC then compiles that intermediate with its own `-MMD`/`-MP`
header tracking. Because `expansion-modern-all` is one of the modern goals
that forces `NODEP=1` to skip the legacy dependency machinery, it does not
gate its own asset tracking on `NODEP` — doing so would silently disable
INCBIN rebuild detection for the modern build itself. Instead, for every data
C source `tools/scaninc` scans the original, un-preprocessed source once and
generates a deterministic `<name>.assets.d` file declaring `<name>.pre.c`'s
real prerequisites (`<name>.c` plus every scanned `INCBIN_*`/`#include`
path); ordinary (non-data) C sources get a parallel `<name>.headers.d` file
generated with GCC's own `cpp -MM -MG` ("assume missing headers are
generated"), since scaninc's `#include` scan silently skips any header that
does not exist on disk yet and therefore cannot discover a not-yet-generated
header (for example a JSON-derived header from `json_data_rules.mk`) at all.
Both `.assets.d`/`.headers.d` files are `include`d directly (not through
`$(wildcard ...)`), so GNU Make's own "remake included makefiles, then
restart" semantics resolve any missing generated asset or header as an
ordinary prerequisite — built via the top-level `Makefile`'s existing
generation/compression rules (already active in the same invocation, since
that `Makefile` `include`s `modern.mk`) — before any `.pre.c`/`.o` recipe
ever runs, on the very first invocation, with no prior build required. Some
referenced assets (for example `.4bpp.lz` graphics) are themselves generated
by these same rules from checked-in, uncompressed sources. A data or normal
C source whose reference has no matching file and no generation rule still
fails immediately and actionably with GNU Make's own "No rule to make
target" error naming the missing asset or header. This target still only
produces relocatable objects — it never links an ELF or ROM.
`MODERN_ALL_C_SOURCES`, `MODERN_ALL_DATA_C_SOURCES`, and
`MODERN_ALL_ASM_SOURCES` (a separate list from `MODERN_COHORT_ASM_SOURCES`,
so overriding one does not blank the other) default to the full supported
source set and can be overridden the same way as the cohort variables.

### Modern expansion ELF target

`expansion-modern-elf` links a full modern ELF using every modern object
(reproduce the current count against this worktree with
`make print-MODERN_ALL_OBJECTS`), modern runtime libraries
(`-lc -lnosys -lgcc`), and no agbcc libraries.
The clean section-oriented `linker/expansion.ld` owns ROM, IWRAM, persistent
EWRAM, and mutually exclusive EWRAM overlays. Persistent EWRAM begins after
the largest overlay, and linker assertions reject orphan sections, overlap,
and memory overflow.

```bash
make expansion-modern-elf MODERN_CONFIG=debug MODERN_ABI=aapcs
```

Outputs land under `build/expansion-modern/<config>/<abi>/`:
- `fireemblem8.elf` — linked modern ELF (entry `Init` at `0x08000000`)
- `fireemblem8.map` — linker map
- `link/` — deterministic object list and link-settings stamp

The target discovers modern `libgcc.a`, `libc.a`, and `libnosys.a` paths
from the configured `MODERN_CC` at recipe time. Override `MODERN_NEWLIB_LIB`
to point at a specific newlib library directory if auto-discovery fails.
`MODERN_LD` defaults to `$(PREFIX)ld` or
`$(MODERN_TOOLCHAIN_ROOT)/bin/$(PREFIX)ld`.

The FE6 SIO multiboot payload is built from the `mgfembp` submodule source
using modern GCC (`expansion-modern-mgfembp`). The modern binary differs from
the historical SHA by design (different compiler/optimization) but parent boot
behavior is verified. SIO link-cable protocol timing remains a documented
residual risk since no automated multiboot test exists. The legacy archival
path through mgfembp's own build system may still produce the original
byte-matching binary separately.

The ELF target alone proves a complete link with zero undefined symbols.
Use the ROM/runtime targets below for behavior validation.

**IWRAM symbol placement**: eight performance-critical symbols
(`ReadSramFast`, `VerifySramFast`, `gSoundInfo`, `gMPlayJumpTable`,
`gCgbChans`, `gMPlayMemAccArea`, `SoundMainRAM_Buffer`, `gText_GoldBox`)
are placed at their exact legacy IWRAM offsets via per-symbol BSS sections.
The source files that need this treatment receive
`-fdata-sections` so modern GCC emits the named `.bss.<symbol>` sections
the clean linker places at pinned offsets. `modern.mk`'s "IWRAM-placed
symbols need per-symbol BSS sections" block is the current source of truth
for which sources carry the override and may grow as more symbols move to
IWRAM; search that file for `-fdata-sections` (e.g.
`grep -n -- '-fdata-sections' modern.mk`) rather than trusting a fixed list
written here.
`src/agb_sram.o` additionally receives `-fno-toplevel-reorder
-fno-reorder-functions`: `SetSramFastFunc()` copies `ReadSramFast_Core`/
`VerifySramFast_Core` into IWRAM scratch buffers at runtime by subtracting
adjacent function addresses, a legacy-agbcc idiom that assumes those
functions stay contiguous in source-declaration order. Modern GCC's default
`-O2` `-freorder-functions` reorders them, corrupting the computed copy size
and eventually crashing at runtime; the two flags restore source order.

### Modern ROM and deterministic boot-check targets

`expansion-modern-rom` converts the modern ELF to an isolated 16 MiB or
32 MiB GBA ROM and verifies its header; `expansion-modern-boot-check` runs
the repository's existing behavior-policy playtest fingerprint against that
ROM, proving deterministic runtime progress (not just a successful link) at
frames 0/60/120.

```bash
make expansion-modern-rom MODERN_CONFIG=debug MODERN_ABI=aapcs
make expansion-modern-rom MODERN_CONFIG=release MODERN_ABI=aapcs
make expansion-modern-boot-check MODERN_CONFIG=debug MODERN_ABI=aapcs
make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs
make expansion-modern-linker-check MODERN_CONFIG=debug MODERN_ABI=aapcs
make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs
```

Outputs land under `build/expansion-modern/<config>/<abi>/`:
- `fireemblem8.gba` — flat, padded, header-verified modern ROM

`expansion-modern-rom` objcopies `$(MODERN_ELF)` with the same
`--strip-debug -O binary --pad-to 0x9000000 --gap-fill=0xff` flags as the
legacy `%.gba` rule, then verifies the result in place with
`scripts/modernize/verify_rom_header.py`: exact 16 MiB size, title/game
code/maker code/fixed byte, and the checksum byte at offset `0xBD`
recomputed over `0xA0..0xBC`. A failed verification deletes the ROM so a
stale, invalid image is never silently reused. `MODERN_OBJCOPY` resolves
in parallel to `MODERN_LD`/`MODERN_OBJDUMP` (`$(PREFIX)objcopy` or
`$(MODERN_TOOLCHAIN_ROOT)/bin/$(PREFIX)objcopy`) and can be overridden
directly.

`expansion-modern-boot-check` first runs `expansion-modern-boot-preflight`,
which checks that `tools/gba-playtest/scenarios/boot.json` and
`tools/gba-playtest/fingerprints/boot.json` exist and that the libmGBA
playtest backend is available (`gba_playtest.py backend-check`), failing
with an actionable error (including the exact backend-check command to
rerun) rather than a confusing downstream crash. It then builds the ROM and
runs `gba_playtest.py verify --policy behavior` against all three
checkpoints (frames 0/60/120) — never weakened to a frame-0-only check.
`--policy behavior` is required (not `--policy exact-rom`) because the
modern ROM is not byte-identical to the legacy ROM referenced by the
checked-in fingerprint's own `rom` stanza; this target makes no ROM
byte-identity claim, only that both ROMs reach the same deterministic
runtime state.

Setting up the libmGBA playtest backend follows the same bootstrap as any
other `tools/gba-playtest` consumer — see that tool's own documentation for
compiler/library prerequisites. `expansion-modern-linker-check` adds
configuration-specific title fingerprints, deterministic budget drift,
retained-relocation cross-overlay analysis, raw-address scans, and a shifted
`+0x40000` boot/title run while keeping startup and battle-animation pins fixed.
