# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a ROM-hack base derived from the **Fire Emblem: The Sacred Stones**
(GBA) decompilation. The expansion output is not required to be
byte-identical to the original ROM.

This repository's default, supported contribution path is the **modern
`arm-none-eabi` GCC/AAPCS release framework** (see
[`docs/quickstart.md`](docs/quickstart.md) and
[`docs/framework-support.md`](docs/framework-support.md)). The original
agbcc-based decompilation build is preserved as an explicit, separate
**archival** lane (`make legacy` / `make fireemblem8.gba`) for
byte-for-byte decomp-matching work only — see
[`docs/archival-decomp.md`](docs/archival-decomp.md). Start from the
[documentation index](docs/README.md) or
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contributor workflow;
this file only covers what an AI agent needs while editing code in this
repository.

## Build Commands

```bash
# Default, supported path: modern release ROM, boot-verified (no agbcc involved)
make

# Equivalent explicit form
make all

# Archival lane: agbcc-based fireemblem8.gba, explicit target required
make legacy -j$(nproc)   # equivalently: make fireemblem8.gba -j$(nproc)

# Clean all build artifacts (slow — recompresses battle animations)
make clean

# Clean everything except battle animation compression outputs (preferred)
make clean_fast
```

A bare `make`/`make all` always builds and boot-verifies the modern
release ROM and never requires, builds, or resolves to a `tools/agbcc`
executable or library. Modern ROM correctness is judged by successful
link, boot, and runtime behavior, not by equality with the vanilla ROM;
the archival lane remains judged by byte-identical matching.

First-time setup: `./scripts/quickstart.sh` installs/probes the modern
toolchain (and libmGBA) by default, **no agbcc of any kind**; pass
`--legacy` (or `--refresh-agbcc`) only when you need the archival lane,
which installs agbcc instead. A legally obtained `baserom.gba` is
optional and only needed by `asmdiff.sh`. See
[`docs/quickstart.md`](docs/quickstart.md) for full setup/troubleshooting
and [`docs/framework-support.md`](docs/framework-support.md) for exactly
which hosts/toolchains/targets are supported vs. archival-only.

Authoring game content (characters/classes/items/supports/etc.) goes
through the generated-data platform rather than hand-written C tables —
see [`docs/generated_data_tutorial.md`](docs/generated_data_tutorial.md)
(`make generated-data-validate`, `-generate`, `-check`, `-test`).

## Compiler & Toolchain

- **Modern (default release lane)**: `arm-none-eabi` GCC targeting AAPCS.
  No agbcc of any kind is involved in `make`/`make all`.
- **agbcc (archival lane only)**: a modified GCC 2.95 targeting ARM7TDMI
  (Thumb/ARM interwork), located at `tools/agbcc/`, used only by
  `make legacy` / `make fireemblem8.gba`. This is **C89-era** — no `//`
  comments in compiled code, no C99 features.
  - Compiler flags: `-mthumb-interwork -Wimplicit -Wparentheses -Werror -O2 -fhex-asm`
  - Source is preprocessed with `cpp`, piped through `iconv` (UTF-8 → CP932), then compiled with `agbcc`
  - Some files use `old_agbcc` or different flags — see per-file overrides in `Makefile`

## Architecture

### Archival decomp workflow

Assembly lives in `asm/`, decompiled C goes in `src/`. The linking order
in `ldscript.txt` determines ROM layout. When decompiling a function: add
`src/x.o(.text)` **before** `asm/x.o(.text)` in `ldscript.txt`, remove the
function from the `.s` file, and write the C equivalent in `src/x.c`. The
full tutorial, rules, setup steps, and asset-extraction references live
in [`docs/archival-decomp.md`](docs/archival-decomp.md) — this is
archival-lane-only guidance for byte-for-byte matching work, not the
default modern framework path described above.

### Proc System (Cooperative Multitasking)

The engine uses a **Proc** system (`include/proc.h`, `src/proc.c`) — a tree-based cooperative scheduler. Game entities are `struct Proc` with script tables (`struct ProcCmd[]`) defining behavior as command sequences: `PROC_CALL`, `PROC_REPEAT`, `PROC_SLEEP`, `PROC_YIELD`, `PROC_START_CHILD_BLOCKING`, etc. Local proc structs embed `PROC_HEADER` at offset 0 and add custom fields after.

### Memory Sections

- `EWRAM_DATA` — variables in external work RAM (256 KB), used for large/global game state
- `CONST_DATA` / `SECTION(".data")` — data that logically should be `const` but was in `.data` in the original binary
- `EWRAM_OVERLAY(id)` — overlaid EWRAM sections for memory reuse between screens

### Key Subsystems

- **Units**: `struct Unit` / `struct CharacterData` / `struct ClassData` in `bmunit.h`. Arrays: `gUnitArrayBlue` (player), `gUnitArrayRed` (enemy), `gUnitArrayGreen` (NPC), `gUnitArrayPurple`
- **Events**: scripted cutscenes via event engine (`src/event.c`, `src/eventscr*.c`)
- **Battle animations**: `src/banim-*.c` — largest subsystem. Data in `banim/` with custom compression linker (`scripts/arm_compressing_linker.py`)
- **World map**: `src/worldmap_*.c`
- **Text system**: source in `texts/*.txt`, processed by `scripts/texttools/` into `src/msg_data.c` and `include/constants/msg.h`

## Code Conventions

### Include Order

Every `.c` file starts with `#include "global.h"` as the **first** include. This pulls in GBA types, `prelude.h`, `types.h`, `variables.h`, and `functions.h`. Then constants headers (`constants/*.h`), then module headers.

### Naming

- Functions and types: `PascalCase` (`Proc_Start`, `struct Unit`, `GetItemAttributes`)
- Global variables: `gCamelCase` (`gActiveUnitId`, `gPaletteBuffer`)
- Static/local variables: `sCamelCase` (`sProcArray`, `sKeyStatusBuffer`)
- Constants/enums: `UPPER_SNAKE_CASE` (`UNIT_LEVEL_MAX`, `PROC_MARK_EVENT`)
- Many functions retain `sub_XXXXXXXX` placeholder names from ROM addresses (renaming these to descriptive names is part of the archival decompilation effort)

### Struct Layout

Struct fields are annotated with byte offset comments: `/* 0C */ struct Vec2 camera;`

### Header Guards

All headers use `#ifndef GUARD_FILENAME_H` / `#define GUARD_FILENAME_H`.

### Formatting

`.clang-format` configured: Allman braces, 4-space indent, 100-column limit, no tabs. `global.h` is always sorted first in includes.

### Legacy Layout Constraints

The current migration still relies on original ABI and data-layout details:
- Preserve register-sensitive code only where the legacy compiler still requires it
- `STRUCT_PAD(from, to)` pads struct fields to preserve explicit layout
- `SHOULD_BE_CONST` marks data that must stay writable for legacy placement
