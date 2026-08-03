# Copilot Instructions — fireemblem8-expansion

This is a ROM-hack base derived from the **Fire Emblem: The Sacred Stones**
(GBA) decompilation. The expansion output is not required to be byte-identical
to the original ROM.

## Build

This repository's default, supported path is the **modern
`arm-none-eabi` GCC/AAPCS release framework** (see `docs/quickstart.md`
and `docs/framework-support.md`). A bare `make`/`make all` always builds
and boot-verifies the modern release ROM and never requires, builds, or
resolves to a `tools/agbcc` executable or library. The original agbcc-
based decompilation build is preserved as an explicit, separate
**archival** lane (`make legacy` / `make fireemblem8.gba`) for byte-for-
byte decomp-matching work only — see `docs/archival-decomp.md`.

First-time setup: `./scripts/quickstart.sh` installs/probes the modern
toolchain (and libmGBA) by default, **no agbcc of any kind**; pass
`--legacy` (or `--refresh-agbcc`) only when you need the archival lane,
which installs agbcc instead. A legally obtained `baserom.gba` is
optional and only needed by `asmdiff.sh`.


For generated content use `docs/generated_data_tutorial.md`; for the four
validated, default-off starter flags and typed mechanics registry use
`docs/starter_features.md`; for stable locale/message IDs, catalog authoring,
prefs and selector behavior use `docs/localization.md`. Never hand-edit
build-local generated output.

```bash
# Default, supported path: modern release ROM (no agbcc involved)
make

# Archival lane: agbcc-based fireemblem8.gba, explicit target required
make fireemblem8.gba -j$(nproc)   # equivalently: make legacy

# Clean all build artifacts (slow — recompresses battle animations)
make clean

# Clean everything except battle animation compression outputs
make clean_fast
```

A successful build exits cleanly. Modern ROM correctness is judged by
successful link, boot, and runtime behavior, not by equality with the
vanilla ROM; the archival lane remains judged by byte-identical matching.
`./asmdiff.sh <hex_addr> <byte_len>` remains available for legacy matching
investigations when `baserom.gba` is present.

## Architecture

### Compiler & toolchain
- **agbcc**: a modified GCC 2.95 targeting ARM7TDMI (Thumb/ARM interwork). Located at `tools/agbcc/`. This is C89-era — no `//` comments in compiled code, no C99 features.
- Compiler flags: `-mthumb-interwork -Wimplicit -Wparentheses -Werror -O2 -fhex-asm`
- Source is preprocessed with `cpp`, piped through `iconv` (UTF-8 → CP932), then compiled with `agbcc`.
- Some files use the older compiler (`old_agbcc`) or different flags — see per-file overrides in `Makefile`.

### Decompilation workflow
Assembly lives in `asm/` (only `arm.s` and `arm_call.s` remain, plus data files in `data/`). Decompiled C goes in `src/`. The linking order in `ldscript.txt` determines ROM layout — when decompiling a function, you add `src/x.o(.text)` **before** `asm/x.o(.text)` and remove the function from the `.s` file. Keep **both** the `src/` and `asm/` linker entries until `asm/x.s` is fully empty; leaving a function in both places causes a `multiple definition` link error. For undeclared symbols, locate the type with `git grep "<symbol>" include/` and add the owning header (functions still living in `asm/` get a bare forward declaration, not `extern`). The decomp tutorial that walks a full function end-to-end now lives in `docs/archival-decomp.md` (this is archival-lane-only guidance, not the default modern framework path).

### Files that must NOT be decompiled
These are handwritten assembly, already commented, and stay in `asm/`: `crt0.s`, `libagbsyscall.s`, `libgcnmultiboot.s`, `m4a_1.s`, `m4a_3.s`, `arm.s`, `arm_call.s`.

### Proc system (cooperative multitasking)
The engine uses a **Proc** system (`include/proc.h`, `src/proc.c`) — a tree-based cooperative scheduler. Game entities are `struct Proc` with script tables (`struct ProcCmd[]`) that define behavior as sequences of commands: `PROC_CALL`, `PROC_REPEAT`, `PROC_SLEEP`, `PROC_YIELD`, `PROC_START_CHILD_BLOCKING`, etc. Local proc structs embed `PROC_HEADER` at offset 0 and add custom fields after.

### Memory sections
- `EWRAM_DATA` — variables placed in external work RAM (256 KB). Used for all large/global game state.
- `CONST_DATA` — data that *should* be `const` but was placed in `.data` in the original binary (use `SECTION(".data")`).
- `EWRAM_OVERLAY(id)` — overlaid EWRAM sections for memory reuse between screens.

### Key subsystems
- **Units**: `struct Unit` / `struct CharacterData` / `struct ClassData` in `bmunit.h`. Unit arrays: `gUnitArrayBlue` (player), `gUnitArrayRed` (enemy), `gUnitArrayGreen` (NPC), `gUnitArrayPurple`.
- **Events**: scripted cutscenes via an event engine (`src/event.c`, `src/eventscr*.c`). Event scripts are `ProcCmd` tables.
- **Battle animations**: `src/banim-*.c` — the largest subsystem by file count. Battle animation data is in `banim/` with a custom compression linker (`scripts/arm_compressing_linker.py`).
- **World map**: `src/worldmap_*.c` — overworld screen and navigation.
- **Text system**: text source in `texts/*.txt`, processed by `scripts/texttools/` into `src/msg_data.c` and `include/constants/msg.h`.

## Conventions

### Include order
Every `.c` file starts with `#include "global.h"` as the first include. This pulls in GBA types, `prelude.h`, `types.h`, `variables.h`, and `functions.h`. Other includes follow — constants headers (`constants/*.h`), then module headers.

### Naming
- Functions and types use `PascalCase` (`Proc_Start`, `struct Unit`, `GetItemAttributes`).
- Global variables use `gCamelCase` (`gActiveUnitId`, `gPaletteBuffer`).
- Static/local variables use `sCamelCase` (`sProcArray`, `sKeyStatusBuffer`).
- Constants/enums use `UPPER_SNAKE_CASE` (`UNIT_LEVEL_MAX`, `PROC_MARK_EVENT`).
- Many functions still have original `sub_XXXXXXXX` placeholder names from the ROM addresses. Renaming these to descriptive names is part of the decompilation effort.

### Struct layout comments
Struct fields are annotated with byte offset comments: `/* 0C */ struct Vec2 camera;`. This aids matching against the original binary layout.

### Header guards
All headers use `#ifndef GUARD_FILENAME_H` / `#define GUARD_FILENAME_H` style guards.

### Formatting
Configured in `.clang-format`: Allman braces, 4-space indent, 100-column limit, no tabs. `global.h` is always sorted first in includes.

### Legacy layout constraints
The current migration still relies on original ABI and data-layout details:
- Preserve register-sensitive code only where the legacy compiler still requires it.
- `STRUCT_PAD(from, to)` is used to preserve explicit structure layout.
- The `SHOULD_BE_CONST` marker denotes data that must remain writable for legacy placement.

### Asset extraction
Raw data blobs are migrated from `dump/`*.bin into typed source (C arrays, or
`.png`/`.pal`/`.map.bin` tilemap graphics) following `docs/dump_extraction_plan.md`; each
conversion must round-trip byte-identical.

**Two tilemap (TSA) formats** — committed as binary, distinguished by file
extension (the bytes cannot be told apart structurally, only by the engine
consumer):
- `.map.bin` — **headerless** (pokeemerald `GBA_4BPP` style): raw `u16` entries,
  rows top-to-bottom, no header; size = `2*W*H`. Used by banim, scrolling
  backgrounds, and other raw tilemap consumers.
- `.tsa.bin` — **headered** ("FEGBA struct" / tilemap-studio `FEGBA_4BPP`): a
  2-byte header (`u8 width-1`, `u8 height-1`) then `(W*H)` `u16` entries, rows
  **bottom-to-top**; size = `2 + 2*W*H`. Consumed by `TmApplyTsa` /
  `CallARM_FillTileRect` (the FE "TSA" tile arrangement). Symbols use the `Tsa_`
  prefix. A few `.tsa.bin` blobs concatenate multiple TSAs after the first
  header (e.g. `gUnknown_085B0F2C`).

Renaming between these is build-safe (only the file extension and the `.incbin`
path change, not the ROM bytes). LZ-compressed assets are committed
**decompressed** (the build recompresses via `Makefile %.lz` rules) — never
commit `.lz`/`.4bpp`/`.gbapal`/`.map.bin.lz`/`.tsa.bin.lz` artifacts. When a recompressed asset
only prefix-matches the original at the 4-byte LZ header, sweep gbagfx's
minimum match distance (`gbagfx in out.lz -mindist N`, default 2) and pin the
winning value per-target via `LZ_FLAGS := -mindist N` in the `Makefile` — this
is a min-distance mismatch, not incompatible compression. See
`docs/lz_suffix_diagnostic.md`.
