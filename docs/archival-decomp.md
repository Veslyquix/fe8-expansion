# Archival decomp-matching workflow

> ⚠️ **Unsupported for expansion releases.** This entire document describes
> the **archival agbcc lane** (`make legacy` / `make fireemblem8.gba`), kept
> for byte-for-byte decomp-matching work against the original Fire Emblem:
> The Sacred Stones (USA) ROM. It is not the default/supported build — a
> bare `make`/`make all` builds the **modern GCC/AAPCS release lane**
> instead (see [`README.md`](../README.md) and
> [`docs/quickstart.md`](quickstart.md)). If you want to add or change
> gameplay/content in the supported framework, see
> [`docs/architecture.md`](architecture.md) and
> [`docs/generated_data_tutorial.md`](generated_data_tutorial.md) instead.
>
> The historical upstream project repository and its wiki
> ([`fireemblem8u`](https://github.com/laqieer/fireemblem8u.git),
> [`fireemblem8u/wiki`](https://github.com/laqieer/fireemblem8u/wiki)) are
> `[historical upstream]` context only -- provenance and reference
> material for where this codebase originally came from, not this
> repository's source of truth. Only this repository's own tracked docs,
> including this document and
> [`docs/upstream-porting.md`](upstream-porting.md) (the
> canonical-upstream-drift tool), are authoritative for this codebase.

## When to use this lane

Use `make legacy`/`make fireemblem8.gba` only when your goal is
byte-for-byte matching against the original ROM's disassembly (`asm/`), or
when working with tooling that inherently depends on agbcc's exact codegen
(for example the FE6 SIO link payload's own archival sub-build via the
`mgfembp` submodule). For everything else, use the modern lane.

## Setting up the archival build

1. Install [devkitPro](https://devkitpro.org/wiki/Getting_Started) or the
   [GNU Arm Embedded Toolchain](https://developer.arm.com/tools-and-software/open-source-software/developer-tools/gnu-toolchain/gnu-rm).
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
   [mgfembp](https://github.com/StanHash/mgfembp) submodule (not a
   committed blob); the first `make legacy` also fetches/builds its own
   agbcc variant for it.
   ```
   cd /path/to/fireemblem8u
   git submodule update --init --recursive
   ```
4. Build tools.
   ```
   ./build_tools.sh
   ```
5. Build the archival ROM (a bare `make`/`make all` instead builds the
   modern release ROM, so the archival lane must be named explicitly):
   ```
   make legacy
   ```
6. A successful command produces `fireemblem8.gba`.

`./scripts/quickstart.sh --legacy` automates steps 1-6; see
[`docs/quickstart.md`](quickstart.md#archival---legacy-path).

### Archival build FAQ

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

## Decompiling guide

Code starts out in `asm/`. When decompiled to C, it goes into `src/`. The
goal of this archival workflow is to decompile all remaining code so it
matches byte-for-byte under agbcc.

Some of the code in `asm/` is handwritten assembly. It can't and shouldn't
be decompiled. It's already commented, so there's no further work to do on
these files.
* `asm/crt0.s`
* `asm/libagbsyscall.s`
* `asm/libgcnmultiboot.s`
* `asm/m4a_1.s`
* `asm/m4a_3.s`

The rest of the `.s` files in `asm/` are fair game.

The basic decompilation process is:
* Choose a file in `asm/`, i.e. `asm/x.s`. Create a C file called `src/x.c`.
* Translate the first function in `asm/x.s` to C in `src/x.c`.
* `make legacy`, and tweak the function until it matches.
* Clean up the code and comment.
* Repeat for each function until `asm/x.s` is empty.

### For example, let's decompile `asm/cable_car.s`.

#### 1. Create `src/cable_car.c`

```c
#include "global.h"
```

`global.h` contains typedefs for GBA programming and more.
It must be the first include in the file. Other includes will assume you have included it.

#### 2. Include it in the rom

Include `src/cable_car.c` in the rom by adding `src/cable_car.o` to `ld_script.txt`:
```diff
         asm/battle_message.o(.text);
         asm/choose_party.o(.text);
+        src/cable_car.o(.text);
         asm/cable_car.o(.text);
         asm/roulette_util.o(.text);
```
Do not remove `asm/cable_car.o(.text)`. We want both `src/cable_car.c` and `asm/cable_car.s` in the rom.

#### 3. Translate the function to C

Take the first function in `asm/cable_car.s`. Either comment it out or remove it, whichever is easier.

```asm
	thumb_func_start sub_81231EC
sub_81231EC: @ 81231EC
	push {r4,lr}
	lsls r0, 24
	lsrs r4, r0, 24
	ldr r0, _08123210 @ =gPaletteFade
	ldrb r1, [r0, 0x7]
	movs r0, 0x80
	ands r0, r1
	cmp r0, 0
	bne _0812320A
	ldr r0, _08123214 @ =sub_8123244
	bl SetMainCallback2
	adds r0, r4, 0
	bl DestroyTask
_0812320A:
	pop {r4}
	pop {r0}
	bx r0
	.align 2, 0
_08123210: .4byte gPaletteFade
_08123214: .4byte sub_8123244
	thumb_func_end sub_81231EC
```
---

Then, start translating the code to `src/cable_car.c`, bit by bit:

```asm
	lsls r0, 24
	lsrs r4, r0, 24
```
```c
void sub_81231EC(u8 r4) {
```
---
```asm
	ldr r0, _08123210 @ =gPaletteFade
	ldrb r1, [r0, 0x7]
	movs r0, 0x80
	ands r0, r1
```
```c
	r0 = (u8 *)(&gPaletteFade + 7) & 0x80;
```
---

---
```asm
	cmp r0, 0
	bne _0812320A
```
```c
	if (!r0) {
```
---
```asm
	ldr r0, _08123214 @ =sub_8123244
	bl SetMainCallback2
```
```c
		SetMainCallback2(&sub_8123244);
```
---
```asm
	adds r0, r4, 0
	bl DestroyTask
```
```c
		DestroyTask(r4);
```
---
```asm
_0812320A:
```
```c
	}
```
---
```asm
	pop {r4}
	pop {r0}
	bx r0
```
```c
	return;
```
The type signature of the function depends on the return type.
* `bx r0`: `void`
* `bx r1`: `*`
* `bx lr`: `void`, `*`

You will need to look at the caller and the function prologue to determine the exact type if not void.

Since it used `bx r0`, it's `void` for sure.

---

Putting it all together, we get:
```c
void sub_81231EC(u8 r4) {
	r0 = (u8 *)(&gPaletteFade + 7) & 0x80;
	if (!r0) {
		SetMainCallback2(&sub_8123244);
		DestroyTask(r4);
	}
	return;
}
```

#### 4. Simplify and document

This line doesn't look quite right.

```c
	r0 = (u8 *)(&gPaletteFade + 7) & 0x80;
```

What is `gPaletteFade`? You can find out where stuff is with `git grep`:

```sh
git grep "gPaletteFade" include/
```
```grep
include/palette.h:extern struct PaletteFadeControl gPaletteFade;
```

So it's a struct called `PaletteFadeControl`. Let's look in `palette.h`:

```c
struct PaletteFadeControl
{
    u32 multipurpose1;
    u8 delayCounter:6;
    u16 y:5; // blend coefficient
    u16 targetY:5; // target blend coefficient
    u16 blendColor:15;
    u16 active:1;
    u16 multipurpose2:6;
    u16 yDec:1; // whether blend coefficient is decreasing
    u16 bufferTransferDisabled:1;
    u16 mode:2;
    u16 shouldResetBlendRegisters:1;
    u16 hardwareFadeFinishing:1;
    u16 softwareFadeFinishingCounter:5;
    u16 softwareFadeFinishing:1;
    u16 objPaletteToggle:1;
    u8 deltaY:4; // rate of change of blend coefficient
};
```
---

What's the 7th byte in this struct?
```c
    u32 multipurpose1; // 0-3
    u8 delayCounter:6; // 4
    u16 y:5;           // 5
    u16 targetY:5;     // 5-6
    u16 blendColor:15; // 7
    u16 active:1;      // 7
```

Byte 7 has both `.blendColor` and `.active`.

---

Okay, what's 0x80 mean? It's `0b10000000`, which is the highest bit in a byte.

`.active` comes after, which means it's higher, but it's also only one bit, so it's a safe bet.

```c
	r0 = gPaletteFade.active;
```

Much better.

---

```c
void sub_81231EC(u8 r4) {
	r0 = gPaletteFade.active;
	if (!r0) {
		SetMainCallback2(&sub_8123244);
		DestroyTask(r4);
	}
	return;
}
```

Now the temp variable `r0` is a little pointless. We can simplify this to:

```c
void sub_81231EC(u8 taskId) {
	if (!gPaletteFade.active) {
		SetMainCallback2(&sub_8123244);
		DestroyTask(taskId);
	}
}
```

Looks done, right?
This function is pretty simple, so it doesn't need any comments right now.

But what about `sub_8123244`? It's still not obvious what that function does. We can find out by decompiling it later.

#### 5. Build

```sh
make legacy
```
```gcc
src/cable_car.c: In function `sub_81231EC':
src/cable_car.c:4: `gPaletteFade' undeclared (first use in this function)
src/cable_car.c:4: (Each undeclared identifier is reported only once for each function it appears in.)
src/cable_car.c:5: warning: implicit declaration of function `SetMainCallback2'
src/cable_car.c:5: `sub_8123244' undeclared (first use in this function)
src/cable_car.c:6: warning: implicit declaration of function `DestroyTask'
```

We got some errors. We need to tell the compiler what `gPaletteFade`, `SetMainCallback2`, `sub_8123244`, and `DestroyTask` are.

We know `gPaletteFade` is from `palette.h`. We can do the same with the others. Declare them above the function:
```c
#include "palette.h"
#include "main.h"
#include "task.h"
```
The odd one out is `sub_8123244`, which is in `asm/cable_car.s`! What then?
```c
void sub_8123244();
```
Normally, we would do `extern void sub_8123244();`, but it won't be `extern` when we're done this file.

---

Now our file looks like this:
```c
#include "global.h"
#include "palette.h"
#include "main.h"
#include "task.h"

void sub_8123244();

void sub_81231EC(u8 taskId) {
	if (!gPaletteFade.active) {
		SetMainCallback2(&sub_8123244);
		DestroyTask(taskId);
	}
}
```

---

Build again, and we get:
```sh
make legacy
```

This confirms that the source compiles and links. Use the project's disassembly
comparison tools when you need to investigate instruction-level matching.

---

If the build fails, `make legacy` reports the compiler or linker error to fix.

---

If you forgot to remove the function from `asm/cable_car.s`, you will get this error:
```gcc
asm/cable_car.o: In function `sub_81231EC':
(.text+0x0): multiple definition of `sub_81231EC'
src/cable_car.o:(.text+0x0): first defined here
```

#### 6. Repeat until `asm/cable_car.s` is empty

Once you're done, you can delete `asm/cable_car.s`, and remove it from `ld_script.txt`.

## Decompiling rules

* rule 1: when in doubt, scrub C
* rule 2: never assume it won't get optimized out.
* rule 3: when the answer is elusive, never rule out a typo.
* rule 4: always be prepared to cram a square peg into a circle hole.
* rule 5: if you still cant get it to match, its a combination that you think you tried before but you havent
* rule 6: volatile is a dangerous magic sauce that may explode
* rule 7: if you're afraid you need to use math, be
* rule 8: if you think you understand the compiler, the compiler will tell you you don't
* rule 10: rule 9 was optimized out

## Related archival references

These deep-dive reports document earlier binary-asset extraction/typing
passes against the original ROM data and are only relevant to archival/
decomp-matching work, not the supported framework:

- [`docs/dump_extraction_plan.md`](dump_extraction_plan.md) — typing raw
  `dump/` byte-blobs into source form.
- [`docs/lz_suffix_diagnostic.md`](lz_suffix_diagnostic.md) — diagnosing
  concatenated/hidden compressed assets.
- [`docs/tsa_audit.md`](tsa_audit.md) — tilemap (TSA) data audit.
- [`docs/banim_asset_extraction.md`](banim_asset_extraction.md),
  [`docs/Banim_AnimScr_Decompilation_Report.md`](Banim_AnimScr_Decompilation_Report.md),
  [`docs/Banim_TSA_Preservation_Report.md`](Banim_TSA_Preservation_Report.md) —
  battle-animation asset extraction and preservation.

## Resources collection

- [GitHub Help](https://help.github.com/en)
- [Compiler Explorer](https://cexplore.karathan.at/z/KhyRi3) [Source Code](https://github.com/SBird1337/cexplore)
- [Online Decompiler](https://feuniverse.us/t/use-free-online-service-to-assist-the-routine-analysis/3219) (Down now. Try [IDA](https://www.hex-rays.com/products/ida/) / [Ghidra](https://ghidra-sre.org/) / [RetDec](https://retdec.com/) instead.)
- [Decomp Permuter](https://github.com/laqieer/decomp-permuter-arm)
- [datadump & funchash](https://github.com/TwitchPlaysPokemon/pret3)
- [Pokemon Projects](https://github.com/pret/pokeemerald)
- [GCC online documentation](https://gcc.gnu.org/onlinedocs/)
- [GCC 2.95 Features](https://gcc.gnu.org/gcc-2.95/features.html)
