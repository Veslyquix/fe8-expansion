# Fire Emblem 8 Expansion

[![Build CI](https://github.com/laqieer/fireemblem8-expansion/actions/workflows/build.yml/badge.svg)](https://github.com/laqieer/fireemblem8-expansion/actions/workflows/build.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
[![Code](https://decomp.dev/laqieer/fireemblem8u/us.svg?mode=shield&measure=matched_code_percent&label=Code)](https://decomp.dev/laqieer/fireemblem8u/us)
[![Data](https://decomp.dev/laqieer/fireemblem8u/us.svg?mode=shield&measure=matched_data_percent&label=Data)](https://decomp.dev/laqieer/fireemblem8u/us)
[![Functions](https://decomp.dev/laqieer/fireemblem8u/us.svg?mode=shield&measure=matched_functions_percent&label=Functions)](https://decomp.dev/laqieer/fireemblem8u/us)

[Wiki](https://github.com/laqieer/fireemblem8u/wiki) · [FE Decomp Portal](https://laqieer.github.io/fe-decomp-portal/) · [decomp.dev](https://decomp.dev/laqieer/fireemblem8u/us)

This is a ROM-hack base derived from the Fire Emblem: The Sacred Stones (U)
decompilation. The expansion ROM is built from source and is not required to be
byte-identical to the original game.

## Used by

Projects powered by this decomp:

* [**fe-maps**](https://github.com/laqieer/fe-maps) ([site](https://laqieer.github.io/fe-maps/)) — browsable ROM/RAM data maps extracted from this decomp's ELF with `readelf`/`nm -l`.
* [**FE_GBA_Function_Library**](https://github.com/laqieer/FE_GBA_Function_Library) ([site](https://laqieer.github.io/FE_GBA_Function_Library/)) — cross-game function documentation using `nm -l` for signatures and `source:line` links.
* [**FE-Clib-Decomp**](https://github.com/laqieer/FE-Clib-Decomp) — ROM-hacking linker scripts, `lyn` reference assembly, and Event Assembler defines generated from this decomp's ELF.

### Quick Start

If you just want to get the repo building quickly (Ubuntu/WSL, Arch Linux, or macOS/Homebrew), run:

```
./scripts/quickstart.sh [--rom /path/to/baserom.gba] [--legacy] [--refresh-agbcc]
```

By default this installs the modern `arm-none-eabi` GCC toolchain and the
libmGBA playtest backend (no agbcc of any kind), then builds and
boot-verifies the **supported modern AAPCS release ROM**
(`build/expansion-modern/release/aapcs/fireemblem8.gba`). Pass `--legacy` to
build the archival agbcc-based `fireemblem8.gba` instead (used for
decomp-matching work; see [`CONTRIBUTING.md`](CONTRIBUTING.md)).

The build does **not** require the original ROM. A `baserom.gba` is only needed
if you want to use `asmdiff.sh` for disassembly comparison; pass it with `--rom`
(or `FIREEMBLEM8U_ROM=...`) if you have one.

See [`docs/quickstart.md`](docs/quickstart.md) for full details, flags, and troubleshooting tips.

### Building

To build and boot-verify the supported modern release ROM:
```bash
make expansion-modern-toolchain-check
make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs -j$(nproc)
```
Output lands at `build/expansion-modern/release/aapcs/fireemblem8.gba`. See
[`docs/quickstart.md`](docs/quickstart.md) for debug builds, the compile-only
object cohort, and other `expansion-modern-*` targets.

A bare `make` (or `make all`) from the repository root does exactly this
(deterministically pinning `MODERN_CONFIG=release MODERN_ABI=aapcs`
regardless of any ambient override) and never requires, builds, or resolves
to a `tools/agbcc` executable or library -- this is the project's single
supported release lane.

To clean all build artifacts:
```bash
make clean
```
To clean all build artifacts **except** the extremely slow battle animation compression outputs:
```bash
make clean_fast
```

### Authoring generated data

Structured JSON under `src/data/` is the supported way to author FE8
content (characters, classes, items, supports, and the Chapter 2 unit/
shop/trap/event/bundle slice, plus terrain/movement/weapon-triangle
mechanics). The deterministic pipeline validates, generates typed C89
into `build/generated/data/`, and drift-checks committed public outputs:

```bash
make generated-data-validate   # actionable file:line:column diagnostics
make generated-data-generate   # write build/generated/data/*.c + inventories + manifest
make generated-data-check      # CI drift + record-budget gate
make generated-data-test       # unit tests
```

Start from the walkthrough in
[`docs/generated_data_tutorial.md`](docs/generated_data_tutorial.md); the
discoverable registry of every table and its record count lives in
[`reports/generated_data_manifest.md`](reports/generated_data_manifest.md).
Full design/reference: [`docs/generated_data.md`](docs/generated_data.md).

### Archival/decomp agbcc build

The original agbcc-based `fireemblem8.gba` target remains available,
unbroken and unchanged, for decomp-matching work (see
[`CONTRIBUTING.md`](CONTRIBUTING.md)); it is not the default/supported
release lane -- a bare `make`/`make all` never builds it and never touches
`tools/agbcc`. This project ships two tracks by design (not one, with the
archival compiler literally removed): a single supported modern GCC AAPCS
release lane by default, plus this explicit, unsupported archival side door
for matching work that inherently depends on the original compiler's
codegen. `./scripts/quickstart.sh --legacy` sets it up automatically; to
build it manually, use the clearly-named alias or the pre-existing target
(both produce the identical `fireemblem8.gba`):
```bash
make legacy -j$(nproc)
# equivalently:
make fireemblem8.gba -j$(nproc)
```

### Setting up the repository manually (archival agbcc build)

1. Install [devkitPro](https://devkitpro.org/wiki/Getting_Started) or [GNU Arm Embedded Toolchain](https://developer.arm.com/tools-and-software/open-source-software/developer-tools/gnu-toolchain/gnu-rm).
```
# for Ubuntu/WSL users
apt install binutils-arm-none-eabi
```
2. Install [agbcc](https://github.com/pret/agbcc) to this project.
```
cd /path/to/agbcc
./build.sh
./install.sh /path/to/fireemblem8u
```
3. Fetch submodules. The FE6 SIO link payload is built from source via the
   [mgfembp](https://github.com/StanHash/mgfembp) submodule (not a committed blob);
   the first `make legacy` also fetches/builds its own agbcc variant for it.
```
cd /path/to/fireemblem8u
git submodule update --init --recursive
```
4. Build tools.
```
./build_tools.sh
```
5. Build the project (a bare `make`/`make all` instead builds the supported
   modern release ROM -- see "Building" above -- so the archival lane must be
   named explicitly here).
```
make legacy
```
6. A successful command produces `fireemblem8.gba`.

Q: `fatal error: png.h: No such file or directory`

A: Install [libpng](http://www.libpng.org/pub/png/libpng.html) to build `tools/gbagfx`.

Q: `make: *** No rule to make target 'baserom.gba', needed by 'xxx'.  Stop.`

A: The current tree builds without the original ROM, so this should not happen
on an up-to-date checkout. If you hit it on an older revision, update first.

Q: `unrecognized option '--add-symbol'`

A: Update your devkitPro or embedded toolchain. Read [this](https://github.com/bminor/binutils-gdb/blob/3451a2d7a3501e9c3fc344cbc4950c495f30c16d/binutils/ChangeLog-2015#L120) for more info.

Q: `.dep/src/xxx.d:2: *** missing separator.  Stop.`

A: `rm -rf .dep` or disable [VSCode Extension: Makefile Tools](https://marketplace.visualstudio.com/items?itemName=ms-vscode.makefile-tools) if installed.

Check [INSTALL.md](https://github.com/pret/pokeruby/blob/master/INSTALL.md) and [INSTALL.md](https://github.com/pret/pokeemerald/blob/master/INSTALL.md) if you have trouble in setting up.

Check [remove_tools](https://github.com/laqieer/fireemblem8u/tree/remove_tools) branch if you don't want to build agbcc and other tools by yourself. It uses docker to make setting up easier. Follow its [README.md](https://github.com/laqieer/fireemblem8u/blob/remove_tools/README.md) instead.
