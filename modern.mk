# Opt-in modern GCC object cohort and clean expansion ELF target.

MODERN_GOALS := \
	expansion-modern-toolchain-check \
	expansion-modern-cohort \
	expansion-modern-all \
	expansion-modern-elf \
	expansion-modern-rom \
	expansion-modern-boot-check \
	expansion-modern-savefmt-check \
	expansion-modern-title-check \
	expansion-modern-debugtools-check \
	expansion-modern-debugtools-timer-check \
	expansion-modern-debugtools-map-check \
	expansion-modern-debugtools-prep-check \
	expansion-modern-debugtools-ch4prep-check \
	expansion-modern-budget \
	expansion-modern-budget-check \
	expansion-modern-relocs \
	expansion-modern-overlay-audit \
	expansion-modern-shifted-check \
	expansion-modern-linker-check \
	expansion-modern-clean
ifneq (,$(filter $(MODERN_GOALS),$(MAKECMDGOALS)))
  NODEP := 1
endif

MODERN_CONFIG ?= debug
MODERN_ABI ?= aapcs

MODERN_CONFIGS := debug release
MODERN_ABIS := aapcs apcs-gnu

# MODERN_TEXT_SHIFT: link-time shift padding (bytes, 4-aligned, default 0).
# Link settings are tracked below so changing this value invalidates the
# ELF/ROM without requiring a clean rebuild.
MODERN_TEXT_SHIFT ?= 0
MODERN_TEXT_SHIFT_IS_NUM := $(shell printf '%s\n' '$(MODERN_TEXT_SHIFT)' | python3 -c "import re, sys; v = sys.stdin.read().strip(); sys.stdout.write('ok' if re.fullmatch(r'(0x[0-9a-fA-F]+|[0-9]+)', v) else '')")
ifeq ($(MODERN_TEXT_SHIFT_IS_NUM),)
  $(error MODERN_TEXT_SHIFT '$(MODERN_TEXT_SHIFT)' is not a valid number)
endif
MODERN_TEXT_SHIFT_IS_ALIGNED := $(shell printf '%s\n' '$(MODERN_TEXT_SHIFT)' | python3 -c "import sys; v = sys.stdin.read().strip(); sys.stdout.write('ok' if int(v, 0) % 4 == 0 else '')")
ifeq ($(MODERN_TEXT_SHIFT_IS_ALIGNED),)
  $(error MODERN_TEXT_SHIFT '$(MODERN_TEXT_SHIFT)' must be 4-byte aligned)
endif

ifeq (,$(filter $(MODERN_CONFIG),$(MODERN_CONFIGS)))
  $(error modern.mk: unsupported MODERN_CONFIG '$(MODERN_CONFIG)'; expected debug or release)
endif
ifeq (,$(filter $(MODERN_ABI),$(MODERN_ABIS)))
  $(error modern.mk: unsupported MODERN_ABI '$(MODERN_ABI)'; expected aapcs or apcs-gnu)
endif

# config.mk: the committed, central configuration surface for the
# expansion framework's semantic version and default GBA ROM identity
# (issue #8). It intentionally does not duplicate MODERN_CONFIG/
# MODERN_ABI/MODERN_ROM_SIZE/MODERN_TEXT_SHIFT, which remain owned here.
# `-include` (not `include`): this repository always commits config.mk, but
# some existing tests build a minimal synthetic tree that copies in only
# modern.mk (plus a throwaway Makefile) to exercise unrelated cohort/all/
# elf/fetsatool-lock/budget behavior in isolation, without config.mk. A
# missing config.mk there must not hard-fail an unrelated test; the
# MODERN_EXPANSION_CONFIG_AVAILABLE gate further below skips issue #8's own
# resolution logic gracefully in exactly that situation.
-include config.mk

MODERN_TOOLCHAIN_ROOT ?=
MODERN_BINUTILS_DIR ?=

# Debian/Ubuntu package newlib's target headers here rather than in GCC's
# built-in search path. An explicitly set (even empty) value always wins.
ifeq ($(origin MODERN_NEWLIB_INCLUDE),undefined)
  ifneq ($(wildcard /usr/include/newlib/stdlib.h),)
    MODERN_NEWLIB_INCLUDE := /usr/include/newlib
  else
    MODERN_NEWLIB_INCLUDE :=
  endif
endif

ifeq ($(MODERN_TOOLCHAIN_ROOT),)
  MODERN_CC ?= $(PREFIX)gcc$(EXE)
  MODERN_OBJDUMP ?= $(PREFIX)objdump$(EXE)
else
  MODERN_CC ?= $(MODERN_TOOLCHAIN_ROOT)/bin/$(PREFIX)gcc$(EXE)
  MODERN_OBJDUMP ?= $(MODERN_TOOLCHAIN_ROOT)/bin/$(PREFIX)objdump$(EXE)
endif

# Quotes are part of the recipe text after make expansion, preserving spaces.
# Do not treat user-supplied paths as make word lists.
MODERN_BINUTILS_FLAG = $(if $(MODERN_BINUTILS_DIR),"-B$(MODERN_BINUTILS_DIR)/")
MODERN_NEWLIB_FLAG = $(if $(MODERN_NEWLIB_INCLUDE),-isystem "$(MODERN_NEWLIB_INCLUDE)")
MODERN_DRIVER_FLAGS := $(MODERN_BINUTILS_FLAG) $(MODERN_NEWLIB_FLAG)

MODERN_ARCH_FLAGS := -mcpu=arm7tdmi -mthumb -mthumb-interwork
# -fgnu89-inline restores legacy-compatible emission for plain (non-static,
# non-extern) `inline` definitions: under -std=gnu11 alone, GCC may elide the
# external definition of such a function once every internal call site is
# inlined, silently breaking any other translation unit that still calls it.
# agbcc always emitted these externally; this flag matches that behavior.
MODERN_LANGUAGE_FLAGS := -std=gnu11 -fgnu89-inline
MODERN_RUNTIME_FLAGS := \
	-ffreestanding -fno-builtin -fno-common \
	-fno-pic -fno-pie \
	-fno-unwind-tables -fno-asynchronous-unwind-tables
MODERN_LAYOUT_FLAGS := \
	-fno-function-sections -fno-data-sections \
	-fno-merge-constants -fno-merge-all-constants
MODERN_DEFINE_FLAGS := -DMODERN=1 -DNONMATCHING=1
MODERN_INCLUDE_FLAGS := -Iinclude -I.
MODERN_WARNING_FLAGS := \
	-Wall -Wextra \
	-Werror=strict-prototypes \
	-Werror=implicit-function-declaration \
	-Werror=incompatible-pointer-types

ifeq ($(MODERN_CONFIG),debug)
  MODERN_CONFIG_FLAGS := -Og -g3
else
  MODERN_CONFIG_FLAGS := -O2 -g0 -DNDEBUG
endif

# aapcs uses GCC's default ABI and is the supported choice for linked
# outputs.  apcs-gnu remains available for compile-only layout comparison.
ifeq ($(MODERN_ABI),aapcs)
  MODERN_ABI_FLAGS :=
else
  MODERN_ABI_FLAGS := -mabi=apcs-gnu
endif

MODERN_CFLAGS := \
	$(MODERN_DRIVER_FLAGS) \
	$(MODERN_ARCH_FLAGS) \
	$(MODERN_LANGUAGE_FLAGS) \
	$(MODERN_RUNTIME_FLAGS) \
	$(MODERN_LAYOUT_FLAGS) \
	$(MODERN_DEFINE_FLAGS) \
	$(MODERN_INCLUDE_FLAGS) \
	$(MODERN_WARNING_FLAGS) \
	$(MODERN_CONFIG_FLAGS) \
	$(MODERN_ABI_FLAGS)

MODERN_BUILD_ROOT := build/expansion-modern
MODERN_OUTPUT_DIR := $(MODERN_BUILD_ROOT)/$(MODERN_CONFIG)/$(MODERN_ABI)

MODERN_COHORT_SOURCES ?= \
	src/fe3_dummy.c \
	src/unit_facing.c \
	src/time.c \
	src/ramfunc.c \
	src/agb_sram.c \
	src/bmlib-math.c \
	src/rng.c \
	src/irq.c \
	src/main.c \
	src/ap.c \
	src/bmsave-misc.c \
	src/bmsave-gmap.c \
	src/bmsave-lib.c \
	src/bmsave.c \
	src/bmsave-xmap.c \
	src/bmcontainer.c \
	src/proc.c \
	src/hardware.c \
	src/debugtools_registry.c \
	src/debugtools_launcher.c \
	src/debugtools_actions.c \
	src/debugtools_diag.c \
	src/debugtools_tools.c

# Handwritten assembly that must not be decompiled (see CONTRIBUTING.md).
# libagbsyscall.s is a self-contained set of BIOS SWI trampolines; arm.s and
# arm_call.s are a coupled pair (arm_call.s's Thumb trampolines branch into
# arm.s's ARM-mode functions) and must stay together in this cohort.
MODERN_COHORT_ASM_SOURCES ?= \
	src/libagbsyscall.s \
	asm/arm.s \
	asm/arm_call.s

MODERN_ASFLAGS := \
	$(MODERN_DRIVER_FLAGS) \
	$(MODERN_ARCH_FLAGS) \
	$(MODERN_INCLUDE_FLAGS) \
	$(MODERN_ABI_FLAGS)

MODERN_COHORT_C_OBJECTS := $(addprefix $(MODERN_OUTPUT_DIR)/,$(MODERN_COHORT_SOURCES:.c=.o))
MODERN_COHORT_ASM_OBJECTS := $(addprefix $(MODERN_OUTPUT_DIR)/,$(MODERN_COHORT_ASM_SOURCES:.s=.o))
MODERN_COHORT_OBJECTS := $(MODERN_COHORT_C_OBJECTS) $(MODERN_COHORT_ASM_OBJECTS)
MODERN_COHORT_DEPS := $(MODERN_COHORT_OBJECTS:.o=.d)

# Full-source cohort: every currently supported translation unit, not just the
# fast/default 18-file cohort above. Self-contained $(wildcard ...) defaults so
# this works when modern.mk is included standalone by test fixtures (which
# override these variables with small synthetic lists rather than relying on
# the top-level Makefile's own CFILES/DATA_SRC_C_FILES).
MODERN_ALL_C_SOURCES ?= $(wildcard src/*.c)
ifeq (,$(findstring src/msg_data.c,$(MODERN_ALL_C_SOURCES)))
MODERN_ALL_C_SOURCES += src/msg_data.c
endif

# Issue #5 Batch 2c-1: same swap as the legacy Makefile's CFILES filtering
# (generated_data.mk) -- a hand C table superseded by a linked
# generated-data equivalent is filtered out of MODERN_ALL_C_SOURCES here
# (true removal, not a rename/substitution): the generated equivalent's
# object is reinstated afterwards below (once MODERN_ALL_C_OBJECTS exists)
# via MODERN_ALL_C_OBJECTS +=, using the *original* hand object's own
# output path, not one derived from the generated .c's own (differently
# prefixed) location -- see the comment there for why. A safe no-op when
# modern.mk is included standalone (e.g. by test fixtures that don't
# `include generated_data.mk`): GENERATED_DATA_LINKED_HAND_SOURCES is then
# simply empty/undefined, so this filters out nothing.
MODERN_ALL_C_SOURCES := $(filter-out $(GENERATED_DATA_LINKED_HAND_SOURCES),$(MODERN_ALL_C_SOURCES))

MODERN_ALL_DATA_C_SOURCES ?= $(wildcard src/data/*.c src/data/mapanim/*.c src/data/menu/*.c src/data/ending/*.c src/data/worldmap/*.c src/data/ui/*.c)

# A separate default list from MODERN_COHORT_ASM_SOURCES (not derived from
# it), so a caller overriding one does not silently blank out the other.
MODERN_ALL_ASM_SOURCES ?= \
	src/libagbsyscall.s \
	asm/arm.s \
	asm/arm_call.s

# tools/preproc expands INCBIN_U8/INCBIN_U16 macros into inline literal byte
# arrays but leaves #include directives untouched; tools/scaninc reports both
# the header includes and the INCBIN binary/graphics asset paths of a raw,
# un-preprocessed data source file.
MODERN_PREPROC ?= tools/preproc/preproc$(EXE)
MODERN_SCANINC ?= tools/scaninc/scaninc$(EXE)

# Explicit host build rule for the default tools/scaninc/scaninc$(EXE),
# parallel to the top-level Makefile's own $(PREPROC) rule. Without this,
# the .assets.d rule below's own "$(MODERN_SCANINC)" prerequisite would be
# reachable, when missing, only through GNU Make's built-in implicit rule
# chain (%: %.o, %.o: %.cpp): that chain compiles just scaninc.cpp (missing
# c_file.cpp/asm_file.cpp/source_file.cpp) with default host flags plus any
# CPPFLAGS already exported for the legacy agbcc pipeline (e.g. -nostdinc),
# producing a broken link or a "cstdio: No such file or directory" failure
# instead of a correct scaninc binary. This exact-path explicit rule always
# takes precedence over that implicit chain and builds scaninc the correct
# way, using its own Makefile's host C++ flags. An overridden MODERN_SCANINC
# pointing elsewhere never matches this literal target path, so it is
# unaffected. The prerequisite list is $(wildcard)-based (evaluated once at
# parse time) rather than literal filenames, so a prebuilt/stubbed scaninc
# binary sitting next to no (or different) sources -- e.g. test fixtures --
# is still treated as already up to date instead of failing with "No rule
# to make target tools/scaninc/scaninc.cpp".
tools/scaninc/scaninc$(EXE): $(wildcard tools/scaninc/*.cpp tools/scaninc/*.h tools/scaninc/Makefile)
	$(MAKE) -C tools/scaninc

MODERN_ALL_C_OBJECTS := $(addprefix $(MODERN_OUTPUT_DIR)/,$(MODERN_ALL_C_SOURCES:.c=.o))

# Reinstate a linked table's object at exactly its *original* (hand
# source's) output path, e.g. $(MODERN_OUTPUT_DIR)/src/data_classes.o --
# not $(MODERN_OUTPUT_DIR)/build/generated/data/data_classes.o (which is
# what deriving it from GENERATED_DATA_LINKED_C via the ordinary
# addprefix/:.c=.o substitution above would give). This is deliberate, not
# cosmetic: MODERN_ELF_OBJECTS_LST/MANIFEST (further below) both
# alphabetically $(sort) the full object-path list before writing the
# linker's response file, so the modern ELF's final .data/.bss placement
# is controlled by each object's path string, not by MODERN_ALL_C_SOURCES'
# list order -- a "build/generated/data/..." object would sort before
# every "src/..." object regardless of position in the sources list,
# shifting every other object's address and spuriously breaking the
# debugtools/savefmt runtime checkpoint fixtures' recorded absolute
# addresses even though no code changed. Reusing the exact original path
# keeps the linked table's object in precisely the same sorted slot the
# hand object always occupied. An explicit (non-pattern) rule for that
# same literal path is defined further below, after $(MODERN_CC)/
# $(MODERN_CFLAGS) exist; GNU Make always prefers an explicit rule over
# the generic `$(MODERN_OUTPUT_DIR)/%.o: %.c` pattern rule for the same
# target, so this never falls back to (re)compiling the real, on-disk
# src/data_classes.c. A safe no-op when GENERATED_DATA_LINKED_HAND_SOURCES
# is undefined (modern.mk included standalone).
MODERN_ALL_C_OBJECTS += $(addprefix $(MODERN_OUTPUT_DIR)/,$(GENERATED_DATA_LINKED_HAND_SOURCES:.c=.o))

# Issue #5 Batch 3a: $(GENERATED_DATA_CH2_UNITS_OBJECT) (generated_data.mk)
# is additive, not a replacement -- src/events_udefs.c has no "original
# hand path" to reuse the way GENERATED_DATA_LINKED_HAND_SOURCES does
# above, since it stays fully linked itself (only its Chapter 2 prefix
# slice is guarded out, internally, by the macro described in
# generated_data.mk). Reinstating it at its own build/generated/data/
# path would sort ("build/..." < "src/...") before every "src/..."
# object once $(sort) orders MODERN_ELF_OBJECTS_LST/MANIFEST (see the
# comment above this one), shifting far more than just Chapter 2's
# data. Instead it's reinstated at a synthetic slot path chosen so it
# sorts immediately between src/events_trapdata.o and src/events_udefs.o
# -- the same adjacency ldscript.txt gives it in the legacy build (see
# generated_data.mk's own comment for the full reasoning) -- so no other
# object's relative order changes. A safe no-op when
# GENERATED_DATA_CH2_UNITS_OBJECT is undefined (modern.mk included
# standalone). An explicit (non-pattern) rule for this literal target
# path is defined further below, alongside GENERATED_DATA_MODERN_OVERRIDE_RULES.
ifneq ($(strip $(GENERATED_DATA_CH2_UNITS_OBJECT)),)
MODERN_ALL_C_OBJECTS += $(MODERN_OUTPUT_DIR)/src/events_u-ch2units.o
endif

# Issue #5 Batch 3b: $(GENERATED_DATA_CH2_TRAPS_OBJECT) (generated_data.mk)
# is the same kind of additive object as the units one just above --
# src/events_trapdata.c has no "original hand path" to reuse (it stays
# fully linked, only its two non-adjacent Ch2 blocks are guarded out).
# Unlike units, this generated object itself defines its two symbols in
# two different sections (.data for TrapData_Event_Ch2, .data.trapch2hard
# for TrapData_Event_Ch2Hard) so legacy's ldscript.txt can place each at
# its own exact original address -- but modern's build links whole
# objects (not per-input-section) and only needs a single, deterministic,
# adjacency-preserving sort slot, so one synthetic path suffices here,
# chosen so it sorts immediately before src/events_trapdata.o (same
# "-" < any alnum trick as the units slot above) and therefore doesn't
# shift any other object's relative order. A safe no-op when
# GENERATED_DATA_CH2_TRAPS_OBJECT is undefined (modern.mk included
# standalone). An explicit (non-pattern) rule for this literal target
# path is defined further below, alongside GENERATED_DATA_MODERN_OVERRIDE_RULES.
ifneq ($(strip $(GENERATED_DATA_CH2_TRAPS_OBJECT)),)
MODERN_ALL_C_OBJECTS += $(MODERN_OUTPUT_DIR)/src/events_t-ch2traps.o
endif

# Issue #5 Batch 3c: $(GENERATED_DATA_CH2_SHOPS_OBJECT) (generated_data.mk)
# is the same kind of additive object as units/traps just above --
# src/events_shoplist.c has no "original hand path" to reuse (it stays
# fully linked, only its single ShopList_Event_Ch2Armory array is guarded
# out). A single synthetic path suffices here, chosen so it sorts
# immediately before src/events_shoplist.o (same "-" < any alnum trick as
# the units/traps slots above) and therefore doesn't shift any other
# object's relative order. A safe no-op when GENERATED_DATA_CH2_SHOPS_OBJECT
# is undefined (modern.mk included standalone). An explicit (non-pattern)
# rule for this literal target path is defined further below, alongside
# GENERATED_DATA_MODERN_OVERRIDE_RULES.
ifneq ($(strip $(GENERATED_DATA_CH2_SHOPS_OBJECT)),)
MODERN_ALL_C_OBJECTS += $(MODERN_OUTPUT_DIR)/src/events_sh-ch2shops.o
endif

# Issue #5 Batch 3d: $(GENERATED_DATA_CH2_EVENTLISTS_OBJECT)
# (generated_data.mk) is the same kind of additive object as units/
# traps/shops just above -- src/events_info.c has no "original hand
# path" to reuse (it stays fully linked, only its guarded
# "events/ch2-eventinfo.h" include is excluded). A single synthetic path
# suffices here, chosen so it sorts immediately before src/events_info.o
# (same "-" < any alnum trick as the units/traps/shops slots above,
# using "events_i-" so it still sorts ahead of "events_info") and
# therefore doesn't shift any other object's relative order. A safe
# no-op when GENERATED_DATA_CH2_EVENTLISTS_OBJECT is undefined (modern.mk
# included standalone). An explicit (non-pattern) rule for this literal
# target path is defined further below, alongside
# GENERATED_DATA_MODERN_OVERRIDE_RULES.
ifneq ($(strip $(GENERATED_DATA_CH2_EVENTLISTS_OBJECT)),)
MODERN_ALL_C_OBJECTS += $(MODERN_OUTPUT_DIR)/src/events_i-ch2eventlists.o
endif

# Issue #5 Batch 1 (mechanics): $(GENERATED_DATA_TERRAINSTATS_OBJECT)
# (generated_data.mk) is the same kind of additive object as units/
# traps/shops/eventlists just above -- src/data_terrains.c has no
# "original hand path" to reuse (it stays fully linked, only its two
# non-adjacent groups of 8 terrain combat/heal stat arrays are guarded
# out). Unlike units, this generated object itself defines its symbols
# in two different sections (.data for the 6 Avo/Def/Res arrays,
# .data.terrainheal for HealAmount/HealsStatus) so legacy's ldscript.txt
# can place each group at its own exact original address -- but modern's
# build links whole objects (not per-input-section) and only needs a
# single, deterministic, adjacency-preserving sort slot, so one synthetic
# path suffices here, chosen so it sorts immediately before
# src/data_terrains.o (same "-" < any alnum trick as the units/traps/
# shops/eventlists slots above) and therefore doesn't shift any other
# object's relative order. A safe no-op when
# GENERATED_DATA_TERRAINSTATS_OBJECT is undefined (modern.mk included
# standalone). An explicit (non-pattern) rule for this literal target
# path is defined further below, alongside
# GENERATED_DATA_MODERN_OVERRIDE_RULES.
ifneq ($(strip $(GENERATED_DATA_TERRAINSTATS_OBJECT)),)
MODERN_ALL_C_OBJECTS += $(MODERN_OUTPUT_DIR)/src/data_t-terrainstats.o
endif

# Issue #5 Batch 2 (mechanics): $(GENERATED_DATA_MOVECOST_OBJECT)
# (generated_data.mk) is the same kind of additive object, sharing
# src/data_terrains.c with terrainstats just above -- its two generated
# sections (.data for the 32 Normal/DemonKing/Ballista/Rain arrays,
# .data.movecostsnow for the 15 Snow arrays) collapse to a single
# synthetic sort slot here, same as terrainstats' own slot. Chosen as
# "data_t-movecost.o" so it sorts immediately before
# "data_t-terrainstats.o" (both share the "data_t-" prefix; 'm' < 't'),
# which itself already sorts immediately before src/data_terrains.o --
# forming a stable three-in-a-row cluster (movecost, terrainstats,
# terrains) that doesn't shift any other object's relative order. A safe
# no-op when GENERATED_DATA_MOVECOST_OBJECT is undefined (modern.mk
# included standalone). An explicit (non-pattern) rule for this literal
# target path is defined further below, alongside
# GENERATED_DATA_MODERN_OVERRIDE_RULES.
ifneq ($(strip $(GENERATED_DATA_MOVECOST_OBJECT)),)
MODERN_ALL_C_OBJECTS += $(MODERN_OUTPUT_DIR)/src/data_t-movecost.o
endif

# Issue #5 Batch 3 (mechanics): $(GENERATED_DATA_WEAPONTRIANGLE_OBJECT)
# (generated_data.mk) is the same kind of additive object as
# terrainstats/movecost above -- src/bmbattle.c has no "original hand
# path" to reuse (it stays fully linked, only its single
# sWeaponTriangleRules[] table is guarded out). Unlike terrainstats/
# movecost, this generated object defines just one symbol in a single
# section, so one synthetic sort slot suffices, chosen as
# "src/bmb-weapontriangle.o" so it sorts immediately before
# src/bmbattle.o (the only other src/bmb*.o object; "-" < any alnum, so
# "bmb-" sorts ahead of "bmbattle") and therefore doesn't shift any
# other object's relative order. A safe no-op when
# GENERATED_DATA_WEAPONTRIANGLE_OBJECT is undefined (modern.mk included
# standalone). An explicit (non-pattern) rule for this literal target
# path is defined further below, alongside
# GENERATED_DATA_MODERN_OVERRIDE_RULES.
ifneq ($(strip $(GENERATED_DATA_WEAPONTRIANGLE_OBJECT)),)
MODERN_ALL_C_OBJECTS += $(MODERN_OUTPUT_DIR)/src/bmb-weapontriangle.o
endif
MODERN_ALL_DATA_PRE := $(addprefix $(MODERN_OUTPUT_DIR)/,$(MODERN_ALL_DATA_C_SOURCES:.c=.pre.c))
MODERN_ALL_DATA_OBJECTS := $(addprefix $(MODERN_OUTPUT_DIR)/,$(MODERN_ALL_DATA_C_SOURCES:.c=.o))
MODERN_ALL_ASM_OBJECTS := $(addprefix $(MODERN_OUTPUT_DIR)/,$(MODERN_ALL_ASM_SOURCES:.s=.o))
MODERN_ALL_OBJECTS := $(MODERN_ALL_C_OBJECTS) $(MODERN_ALL_DATA_OBJECTS) $(MODERN_ALL_ASM_OBJECTS)
MODERN_ALL_DEPS := $(MODERN_ALL_C_OBJECTS:.o=.d) $(MODERN_ALL_DATA_OBJECTS:.o=.d) $(MODERN_ALL_ASM_OBJECTS:.o=.d)

# One deterministic, scaninc-derived asset dependency file per data C
# source (mirroring the .pre.c/.o naming), generated and `include`d (see
# the asset dependency bootstrap section below the .pre.c/.o rules) before
# any .pre.c/.o recipe is ever considered, so missing INCBIN graphics/
# binary assets become ordinary prerequisites on the very first
# invocation instead of surfacing only after a failed build.
MODERN_ALL_DATA_ASSET_DEPS := $(addprefix $(MODERN_OUTPUT_DIR)/,$(MODERN_ALL_DATA_C_SOURCES:.c=.assets.d))

# A related but distinct first-invocation gap: ordinary (non-data)
# MODERN_ALL_C_SOURCES files can #include a *generated* header that is not
# an INCBIN asset (e.g. src/chapterdata.c includes the JSON-generated
# src/data/chapter_settings.h from json_data_rules.mk). scaninc cannot
# discover this: it silently drops any #include it cannot fopen() on disk
# (see tools/scaninc/scaninc.cpp), so it never reports a not-yet-generated
# header at all. GCC/cpp's own "-MM -MG" ("assume missing headers are
# generated") is the correct tool here instead -- it is what the legacy
# Makefile's own $(MAKEDEP)/-MG step already relies on for exactly this
# case. One dependency file per normal C source, targeting its .o directly
# (there is no .pre.c stage for these sources).
MODERN_ALL_C_HEADER_DEPS := $(addprefix $(MODERN_OUTPUT_DIR)/,$(MODERN_ALL_C_SOURCES:.c=.headers.d))

# Only these goals ever touch the full data/normal C source lists;
# expansion-modern-cohort, expansion-modern-toolchain-check, and
# expansion-modern-clean must stay untouched by (and not pay the cost of)
# scanning sources they do not build.
MODERN_ALL_SOURCE_GOALS := \
	expansion-modern-all \
	expansion-modern-elf \
	expansion-modern-rom \
	expansion-modern-boot-check \
	expansion-modern-savefmt-check \
	expansion-modern-title-check \
	expansion-modern-debugtools-check \
	expansion-modern-debugtools-timer-check \
	expansion-modern-debugtools-map-check \
	expansion-modern-debugtools-prep-check \
	expansion-modern-debugtools-ch4prep-check \
	expansion-modern-budget \
	expansion-modern-budget-check \
	expansion-modern-relocs \
	expansion-modern-overlay-audit \
	expansion-modern-shifted-check \
	expansion-modern-linker-check

CLEAN_DIRS += $(MODERN_BUILD_ROOT)

.PHONY: $(MODERN_GOALS)

expansion-modern-toolchain-check:
	@set -eu; \
	cc='$(MODERN_CC)'; \
	cc_path=$$(command -v "$$cc" 2>/dev/null || true); \
	if [ -z "$$cc_path" ] || [ ! -x "$$cc_path" ]; then \
		printf '%s\n' "error: modern compiler not found: $$cc" >&2; \
		printf '%s\n' "Install gcc-arm-none-eabi or set MODERN_TOOLCHAIN_ROOT/MODERN_CC." >&2; \
		exit 1; \
	fi; \
	version=$$("$$cc" $(MODERN_BINUTILS_FLAG) --version 2>&1) || { \
		printf '%s\n' "error: failed to run modern compiler: $$cc" >&2; \
		exit 1; \
	}; \
	printf 'Modern compiler: %s\n' "$$(printf '%s\n' "$$version" | sed -n '1p')"; \
	target=$$("$$cc" $(MODERN_BINUTILS_FLAG) -dumpmachine 2>&1) || { \
		printf '%s\n' "error: could not query modern compiler target: $$cc" >&2; \
		exit 1; \
	}; \
	if [ "$$target" != arm-none-eabi ]; then \
		printf "error: modern compiler targets '%s'; expected 'arm-none-eabi'\n" "$$target" >&2; \
		exit 1; \
	fi; \
	printf 'Modern target: %s\n' "$$target"; \
	assembler=$$("$$cc" $(MODERN_BINUTILS_FLAG) -print-prog-name=as 2>&1) || { \
		printf '%s\n' "error: could not resolve the assembler used by modern GCC" >&2; \
		exit 1; \
	}; \
	case "$$assembler" in \
		/*) resolved_as="$$assembler" ;; \
		*) resolved_as=$$(command -v "$$assembler" 2>/dev/null || true) ;; \
	esac; \
	if [ -z "$$resolved_as" ] || [ ! -x "$$resolved_as" ]; then \
		printf "error: modern GCC resolved assembler '%s', but it is not executable\n" "$$assembler" >&2; \
		printf '%s\n' "Install binutils-arm-none-eabi or set MODERN_BINUTILS_DIR." >&2; \
		exit 1; \
	fi; \
	printf 'Modern assembler: %s\n' "$$resolved_as"; \
	if ! printf '%s\n' '#include "global.h"' | \
		"$$cc" $(MODERN_DRIVER_FLAGS) $(MODERN_ARCH_FLAGS) $(MODERN_LANGUAGE_FLAGS) \
		$(MODERN_DEFINE_FLAGS) $(MODERN_INCLUDE_FLAGS) -fsyntax-only -x c -; then \
		printf '%s\n' "error: modern GCC cannot parse include/global.h and its standard headers." >&2; \
		printf '%s\n' "Install newlib headers (Ubuntu: libnewlib-arm-none-eabi) or set MODERN_NEWLIB_INCLUDE." >&2; \
		exit 1; \
	fi; \
	if ! printf '%s\n' 'void modern_arm7tdmi_thumb_probe(void) {}' | \
		"$$cc" $(MODERN_DRIVER_FLAGS) $(MODERN_ARCH_FLAGS) $(MODERN_ABI_FLAGS) \
		-ffreestanding -fno-pic -fno-pie -c -x c -o /dev/null -; then \
		printf '%s\n' "error: ARM7TDMI Thumb/interwork compile probe failed." >&2; \
		printf '%s\n' "Check the GCC/binutils pairing and MODERN_BINUTILS_DIR." >&2; \
		exit 1; \
	fi; \
	printf 'Modern flags: ARM7TDMI Thumb/interwork; config=%s; ABI=%s\n' \
		'$(MODERN_CONFIG)' '$(MODERN_ABI)'

expansion-modern-cohort: expansion-modern-toolchain-check $(MODERN_COHORT_OBJECTS)
	@printf 'Built %s modern relocatable objects in %s\n' \
		'$(words $(MODERN_COHORT_OBJECTS))' '$(MODERN_OUTPUT_DIR)'

$(MODERN_COHORT_OBJECTS): | expansion-modern-toolchain-check

# Full-source cohort target. Builds every currently supported C translation
# unit (normal + preprocessed data) and the three supported handwritten
# assembly files to relocatable objects only. This does not link, boot, or
# claim runtime readiness, and it does not replace expansion-modern-cohort,
# which remains the fast/default migration target.
expansion-modern-all: expansion-modern-toolchain-check $(MODERN_ALL_OBJECTS)
	@printf 'Built %s modern relocatable objects in %s\n' \
		'$(words $(MODERN_ALL_OBJECTS))' '$(MODERN_OUTPUT_DIR)'

$(MODERN_ALL_OBJECTS): | expansion-modern-toolchain-check

$(MODERN_OUTPUT_DIR)/%.o: %.c
	@mkdir -p "$(@D)"
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"

# Issue #5 Batch 2c-1: explicit (non-pattern) compile rule for each linked
# table's reinstated object (see the MODERN_ALL_C_OBJECTS += comment
# above for why its target path is the *original* hand-source object path,
# e.g. $(MODERN_OUTPUT_DIR)/src/data_classes.o, not one under
# $(GENERATED_DATA_OUT_DIR)). GNU Make always prefers an explicit rule
# over the generic `$(MODERN_OUTPUT_DIR)/%.o: %.c` pattern rule above for
# the same target, so this compiles from the generated .c unconditionally
# -- it is never satisfied by falling back to the pattern rule against the
# real, on-disk (and no longer even source-listed) hand file. Reuses the
# `src/data_<table>.c`/`data_<table>.c` naming convention already relied
# on elsewhere in generated_data.mk, so this generalizes to any future
# linked table without needing to pair up two parallel lists positionally.
define GENERATED_DATA_MODERN_OVERRIDE_RULES
$(MODERN_OUTPUT_DIR)/src/data_$(1).o: $(GENERATED_DATA_OUT_DIR)/data_$(1).c
	@mkdir -p $$(@D)
	"$$(MODERN_CC)" $$(MODERN_CFLAGS) -MMD -MP -MF "$$(@:.o=.d)" -MQ "$$@" -c "$$<" -o "$$@"
endef

$(foreach t,$(GENERATED_DATA_LINKED_TABLES),$(eval $(call GENERATED_DATA_MODERN_OVERRIDE_RULES,$(t))))

# Issue #5 Batch 3a: explicit (non-pattern) compile rule for the `units`
# table's synthetic slot object (see the MODERN_ALL_C_OBJECTS +=
# comment above for why this target's path is a synthetic
# adjacency-preserving slot, not $(GENERATED_DATA_OUT_DIR)/data_ch2_units.o
# reinstated at some "original" path -- there is no original path, since
# this object is additive). GNU Make always prefers this explicit rule
# over the generic `$(MODERN_OUTPUT_DIR)/%.o: %.c` pattern rule above for
# the same target, so it compiles the real generated .c unconditionally
# -- there is no on-disk src/events_u-ch2units.c for it to ever fall back
# to. A safe no-op target when GENERATED_DATA_CH2_UNITS_C is undefined
# (modern.mk included standalone): the rule is simply never reachable,
# since nothing adds this path to MODERN_ALL_C_OBJECTS in that case.
$(MODERN_OUTPUT_DIR)/src/events_u-ch2units.o: $(GENERATED_DATA_CH2_UNITS_C)
	@mkdir -p $(@D)
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"

# Issue #5 Batch 3b: same reasoning as the units synthetic-slot rule just
# above, for the traps table's synthetic slot object. A safe no-op target
# when GENERATED_DATA_CH2_TRAPS_C is undefined (modern.mk included
# standalone): the rule is simply never reachable, since nothing adds
# this path to MODERN_ALL_C_OBJECTS in that case.
$(MODERN_OUTPUT_DIR)/src/events_t-ch2traps.o: $(GENERATED_DATA_CH2_TRAPS_C)
	@mkdir -p $(@D)
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"

# Issue #5 Batch 3c: same reasoning as the units/traps synthetic-slot
# rules above, for the shops table's synthetic slot object. A safe no-op
# target when GENERATED_DATA_CH2_SHOPS_C is undefined (modern.mk included
# standalone): the rule is simply never reachable, since nothing adds
# this path to MODERN_ALL_C_OBJECTS in that case.
$(MODERN_OUTPUT_DIR)/src/events_sh-ch2shops.o: $(GENERATED_DATA_CH2_SHOPS_C)
	@mkdir -p $(@D)
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"

# Issue #5 Batch 3d: same reasoning as the units/traps/shops
# synthetic-slot rules above, for the eventlists table's synthetic slot
# object. A safe no-op target when GENERATED_DATA_CH2_EVENTLISTS_C is
# undefined (modern.mk included standalone): the rule is simply never
# reachable, since nothing adds this path to MODERN_ALL_C_OBJECTS in that
# case.
$(MODERN_OUTPUT_DIR)/src/events_i-ch2eventlists.o: $(GENERATED_DATA_CH2_EVENTLISTS_C)
	@mkdir -p $(@D)
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"

# Issue #5 Batch 1 (mechanics): same reasoning as the units/traps/shops/
# eventlists synthetic-slot rules above, for the terrainstats table's
# synthetic slot object. A safe no-op target when
# GENERATED_DATA_TERRAINSTATS_C is undefined (modern.mk included
# standalone): the rule is simply never reachable, since nothing adds
# this path to MODERN_ALL_C_OBJECTS in that case.
$(MODERN_OUTPUT_DIR)/src/data_t-terrainstats.o: $(GENERATED_DATA_TERRAINSTATS_C)
	@mkdir -p $(@D)
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"

# Issue #5 Batch 2 (mechanics): same reasoning as the terrainstats
# synthetic-slot rule above, for the movecost table's synthetic slot
# object. A safe no-op target when GENERATED_DATA_MOVECOST_C is
# undefined (modern.mk included standalone): the rule is simply never
# reachable, since nothing adds this path to MODERN_ALL_C_OBJECTS in
# that case.
$(MODERN_OUTPUT_DIR)/src/data_t-movecost.o: $(GENERATED_DATA_MOVECOST_C)
	@mkdir -p $(@D)
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"

# Issue #5 Batch 3 (mechanics): same reasoning as the terrainstats/
# movecost synthetic-slot rules above, for the weapontriangle table's
# synthetic slot object. A safe no-op target when
# GENERATED_DATA_WEAPONTRIANGLE_C is undefined (modern.mk included
# standalone): the rule is simply never reachable, since nothing adds
# this path to MODERN_ALL_C_OBJECTS in that case.
$(MODERN_OUTPUT_DIR)/src/bmb-weapontriangle.o: $(GENERATED_DATA_WEAPONTRIANGLE_C)
	@mkdir -p $(@D)
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"

# IWRAM-placed symbols need per-symbol BSS sections.
$(MODERN_OUTPUT_DIR)/src/agb_sram.o: MODERN_CFLAGS += -fdata-sections -fno-toplevel-reorder -fno-reorder-functions
$(MODERN_OUTPUT_DIR)/src/m4a.o: MODERN_CFLAGS += -fdata-sections
$(MODERN_OUTPUT_DIR)/src/bmshop.o: MODERN_CFLAGS += -fdata-sections

# GAS's own --MD tracks uppercase .INCLUDE directives (e.g. macro.inc,
# gba.inc), so no cpp preprocessing or scaninc invocation is needed here.
$(MODERN_OUTPUT_DIR)/%.o: %.s
	@mkdir -p "$(@D)"
	"$(MODERN_CC)" $(MODERN_ASFLAGS) -Wa,--MD,"$(@:.o=.d)" -c "$<" -o "$@"

# Data C sources embed INCBIN_U8/INCBIN_U16 binary/graphics assets and cannot
# be handed to modern GCC directly. This explicit static pattern rule (bound
# to the exact MODERN_ALL_DATA_PRE/MODERN_ALL_DATA_OBJECTS target lists) takes
# precedence over the generic $(MODERN_OUTPUT_DIR)/%.o: %.c rule above for
# these same target names, so data files never reach the modern C compiler
# unpreprocessed.
#
# Every data source's INCBIN/graphics asset prerequisites are declared as
# real prerequisites of its .pre.c target by the generated
# $(MODERN_OUTPUT_DIR)/%.assets.d file `include`d below (see the asset
# dependency bootstrap section), so a missing asset is resolved by the
# top-level Makefile's own generation rules (e.g. %.4bpp: %.png) before
# preproc is ever invoked, on the very first invocation -- rather than
# preproc failing hard on the first unresolved INCBIN it hits.
$(MODERN_ALL_DATA_PRE): $(MODERN_OUTPUT_DIR)/%.pre.c: %.c $(MODERN_PREPROC)
	@mkdir -p "$(@D)"
	@if [ ! -x "$(MODERN_PREPROC)" ]; then \
		printf '%s\n' "error: modern preprocessor not found or not executable: $(MODERN_PREPROC)" >&2; \
		exit 1; \
	fi
	"$(MODERN_PREPROC)" "$<" > "$@" || { rm -f "$@"; exit 1; }

$(MODERN_ALL_DATA_OBJECTS): $(MODERN_OUTPUT_DIR)/%.o: $(MODERN_OUTPUT_DIR)/%.pre.c
	@mkdir -p "$(@D)"
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"

# ---------------------------------------------------------------------------
# Asset dependency bootstrap (issue #3): first-invocation INCBIN readiness
#
# Generates one deterministic dependency file per data C source (mirroring
# the .pre.c/.o naming), scanning the raw, un-preprocessed source with
# scaninc for every INCBIN_* asset path (and #include) it references, and
# declaring them as prerequisites of that source's .pre.c target above.
#
# These files are `include`d directly below with no $(wildcard ...)
# filtering (unlike the plain "-include $(wildcard ...)" of MODERN_ALL_DEPS
# at the bottom of this file), so a missing or stale .assets.d is itself a
# real prerequisite that GNU Make remakes using the rule below, then
# restarts and re-reads all makefiles -- the standard "remake included
# makefiles" behavior described in the GNU Make manual's "Generating
# Prerequisites Automatically" section. The practical effect: the very
# first `make expansion-modern-all/-elf/-rom/-boot-check` invocation
# already resolves missing graphics/binary assets as ordinary
# prerequisites (built via the top-level Makefile's existing asset rules)
# before any .pre.c/.o recipe is attempted, instead of only self-healing
# one build later.
#
# Deliberately not gated on NODEP, for the same reason this scaninc-based
# tracking never was: every modern goal above forces NODEP=1, so gating
# this on NODEP would permanently disable INCBIN readiness tracking for
# the modern build. A data source whose INCBIN references no derivable
# source (no matching .png/.bin and no rule to build one) fails with GNU
# Make's own actionable "No rule to make target '<asset>', needed by
# '<pre.c>'" error, naming both the missing asset and the .pre.c that
# needed it.
#
# Old-style FETSATOOL rules in graphics_file_rules.mk produce a raw
# "<name>.feimgN.bin"/"<name>.fetsaN.bin" (N=1..4) pair from a single
# recipe invocation, using a multi-target explicit rule (not GNU Make 4.3+
# grouped "&:" targets). GNU Make treats each target of such a rule as an
# independent goal with its own copy of the recipe: if two different data
# sources' .assets.d files each list only one sibling of the pair (one
# lists the feimg, another the fetsa) as an independent prerequisite
# elsewhere in the graph, Make can decide both need building and invoke
# the same recipe twice in one run, instead of once. Since neither
# graphics_file_rules.mk nor GNU Make's grouped-target syntax may be
# touched here, every raw/.lz "fetsaN.bin" asset scaninc reports below is
# also given an explicit "<raw fetsaN.bin>: <sibling raw feimgN.bin>"
# ordering edge (deduplicated and sorted for determinism), so a sequential
# (-j1) build always resolves the feimg half of the pair first.
#
# That ordering edge alone is *not* sufficient once a parallel (-j>1)
# build is in play, confirmed with an isolated GNU Make 4.3 reproduction:
# when both siblings are still missing, Make's scheduler evaluates the
# fetsa target's own staleness (file absent) and can dispatch its copy of
# the shared recipe as soon as the feimg build job is merely "already
# being made" (pruned from re-traversal), not once it has actually
# finished writing output -- so both copies of the recipe can still run
# concurrently even with the edge present. Since the shared recipe itself
# (in graphics_file_rules.mk) can't be touched, FETSATOOL is redefined
# below -- only for modern goals, so the legacy agbcc build is untouched
# -- as a small idempotent wrapper: it takes a portable mkdir-based
# advisory lock keyed by the pair's own feimg output path, so whichever
# invocation loses the race blocks until the winner's real generation
# finishes, then finds both outputs already newer than the source and
# skips re-running the real tool. The ordering edge above still forces
# sequential builds to resolve deterministically without ever taking the
# lock, and remains useful documentation of the intended feimg-first
# generation order; the wrapper is what actually makes -j builds safe.
#
# Stale-lock recovery is PID-liveness-based, not mtime-based: the lock
# holder writes its own shell PID into "<lockdir>/pid" immediately after
# the mkdir succeeds, and stays alive (blocked on the real tool) for as
# long as it holds the lock. A waiter that finds the lock already taken
# reads that PID and checks it with "kill -0": if the PID is still alive,
# the waiter just sleeps and rechecks, *regardless of how old the lock
# directory is* -- a slow real generation must never have its lock stolen
# out from under it. Only once "kill -0" confirms the PID is dead does a
# waiter reclaim the lock (immediately, no extra age wait, since a dead
# PID is unambiguous evidence the holder crashed mid-generation). The one
# case a PID can't resolve liveness is the brief window between mkdir
# succeeding and the pid file actually being written (or a holder killed
# in exactly that window, leaving no pid file at all): a missing or
# unparsable pid file falls back to the previous conservative mtime
# threshold (only reclaim once the lock directory itself is older than a
# couple of minutes), so a genuinely fresh lock is never mistaken for an
# abandoned one just because its pid file hasn't landed yet. The holder
# also traps EXIT/INT/TERM to remove its own lock directory and pid file
# on any of its own exit paths (skip-if-fresh, tool success, or tool
# failure), leaving PID-liveness/mtime reclamation only for the crash
# case an uncatchable SIGKILL can still produce.
#
# NOTE: a clean build already logs "make: Circular X <- X dependency
# dropped" lines for some of these old-style multi-target rules' outputs.
# This is pre-existing GNU Make behavior from graphics_file_rules.mk's/
# Makefile's own multi-target recipes (confirmed unchanged in count and
# content on baseline commit 9e938633, i.e. with neither the ordering
# edge above nor the FETSATOOL wrapper present) and is not introduced or
# affected by either mechanism here; Make drops the spurious self-edge
# and proceeds, so it does not affect build correctness.
#
# A related but distinct GNU Make limitation affects the generic
# "%.lz: %" compression rule (Makefile) whenever its raw prerequisite is
# itself one half of an old-style multi-target FETSATOOL pair that is
# still missing on a clean build: reproduced and isolated with GNU Make
# 4.3 "--debug=v" tracing, Make's prerequisite check for the ".lz"
# target evaluates its raw prerequisite as a bare file-existence test
# rather than recursively resolving it through the multi-target rule
# that would actually build it, concludes "does not exist" / "No need to
# remake" for the ".lz" target on the spot, and never revisits that
# verdict later in the same invocation even after the multi-target rule
# successfully creates the raw file moments afterward -- so a fresh
# ".lz" recompression is deferred to the *next* invocation instead of
# happening in the same pass. This reproduces regardless of whether the
# raw pair's rule is the generic pattern or an explicit per-file rule,
# and regardless of prerequisite ordering *within* the existing ".pre.c"
# dependency line below, so it cannot be fixed by reordering that single
# line or by giving ".lz" its own explicit rule -- nor by attaching an
# order-only prerequisite to the ".assets.d" file itself: that file is
# only ever consumed as an *included makefile* (never as a normal graph
# node any other target depends on), so Make's "remake included
# makefiles" pass regenerates its *content* but never walks prerequisites
# declared *inside* that freshly-generated content until the later main
# graph walk begins -- by which point the same buggy ".lz" verdict above
# has already been cached. What *does* work: giving ".pre.c" itself (a
# real, normally-walked graph node) a *separate, earlier* order-only
# prerequisite line -- listed as its own "TARGET: | deps" line placed
# *before* the existing "TARGET: normal-deps..." line in the generated
# file -- naming every compressed asset's raw (uncompressed) sibling.
# Make concatenates multiple prerequisite lines for the same target in
# the order they are read, so this earlier order-only line is considered,
# and its raw sibling built via the multi-target rule if missing, before
# ".lz" is ever reached later in the same combined prerequisite list.
ifneq (,$(filter $(MODERN_GOALS),$(MAKECMDGOALS)))
  MODERN_FETSATOOL_REAL := $(FETSATOOL)
  # $0 is "_"; $1 is the real tool path; $2.. are the tool's own args
  # (src, feimg-out, fetsa-out, then any recipe-specific extra flags).
  MODERN_FETSATOOL_LOCK := sh -c '\
		real="$$1"; shift; \
		src="$$1"; out1="$$2"; out2="$$3"; \
		lockdir="$$out1.fetsalock.d"; \
		pidfile="$$lockdir/pid"; \
		while :; do \
			if mkdir "$$lockdir" 2>/dev/null; then \
				break; \
			fi; \
			lockpid=""; \
			if [ -f "$$pidfile" ]; then \
				lockpid=$$(cat "$$pidfile" 2>/dev/null); \
				case "$$lockpid" in \
					""|*[!0-9]*) lockpid="" ;; \
				esac; \
			fi; \
			if [ -n "$$lockpid" ]; then \
				if kill -0 "$$lockpid" 2>/dev/null; then \
					sleep 1; \
					continue; \
				fi; \
				rm -f "$$pidfile" 2>/dev/null; \
				rmdir "$$lockdir" 2>/dev/null; \
				continue; \
			fi; \
			stale=$$(find "$$lockdir" -maxdepth 0 -mmin +2 2>/dev/null); \
			if [ -n "$$stale" ]; then \
				rm -f "$$pidfile" 2>/dev/null; \
				rmdir "$$lockdir" 2>/dev/null; \
				continue; \
			fi; \
			sleep 1; \
		done; \
		printf "%s\n" "$$$$" > "$$pidfile"; \
		trap "rm -f \"$$pidfile\"; rmdir \"$$lockdir\" 2>/dev/null" EXIT INT TERM; \
		if [ -e "$$out1" ] && [ -e "$$out2" ] && [ "$$out1" -nt "$$src" ] && [ "$$out2" -nt "$$src" ]; then \
			exit 0; \
		fi; \
		"$$real" "$$@"; \
		exit $$? \
	' _
  FETSATOOL = $(MODERN_FETSATOOL_LOCK) $(MODERN_FETSATOOL_REAL)
endif
$(MODERN_ALL_DATA_ASSET_DEPS): $(MODERN_OUTPUT_DIR)/%.assets.d: %.c $(MODERN_SCANINC)
	@mkdir -p "$(@D)"
	@if [ ! -x "$(MODERN_SCANINC)" ]; then \
		printf '%s\n' "error: modern scaninc not found or not executable: $(MODERN_SCANINC)" >&2; \
		exit 1; \
	fi
	@assets=$$("$(MODERN_SCANINC)" -I include -I "" "$<") || { \
		printf '%s\n' "error: scaninc failed while scanning $< for INCBIN assets" >&2; \
		exit 1; \
	}; \
	fetsa_pairs=$$(printf '%s\n' "$$assets" | while IFS= read -r asset; do \
	    [ -n "$$asset" ] || continue; \
	    case "$$asset" in \
	      *.fetsa[1-9]*.bin|*.fetsa[1-9]*.bin.lz) ;; \
	      *) continue ;; \
	    esac; \
	    match=$$(printf '%s\n' "$$asset" | sed -n -E 's/^(.*)\.fetsa([1-4])\.bin(\.lz)?$$/\1|\2/p'); \
	    if [ -z "$$match" ]; then \
	      printf '%s\n' "error: malformed FETSA asset pair name: $$asset" >&2; \
	      exit 1; \
	    fi; \
	    prefix=$${match%|*}; \
	    n=$${match#*|}; \
	    printf '%s:%s\n' "$${prefix}.fetsa$${n}.bin" "$${prefix}.feimg$${n}.bin"; \
	  done) || exit 1; \
	lz_raw_siblings=$$(printf '%s\n' "$$assets" | while IFS= read -r asset; do \
	    [ -n "$$asset" ] || continue; \
	    case "$$asset" in \
	      *.feimg[1-9]*.bin.lz|*.fetsa[1-9]*.bin.lz) ;; \
	      *) continue ;; \
	    esac; \
	    match=$$(printf '%s\n' "$$asset" | sed -n -E 's/^(.*\.(feimg|fetsa)[1-4]\.bin)\.lz$$/\1/p'); \
	    if [ -z "$$match" ]; then \
	      printf '%s\n' "error: malformed compressed FEIMG/FETSA asset name: $$asset" >&2; \
	      exit 1; \
	    fi; \
	    printf '%s\n' "$$match"; \
	  done | sort -u) || exit 1; \
	{ if [ -n "$$lz_raw_siblings" ]; then \
	    printf '%s: |' "$(MODERN_OUTPUT_DIR)/$*.pre.c"; \
	    printf '%s\n' "$$lz_raw_siblings" | while IFS= read -r raw; do \
	      [ -n "$$raw" ] || continue; \
	      escaped_raw=$$(printf '%s' "$$raw" | sed -e 's/\\/\\\\/g' -e 's/ /\\ /g'); \
	      printf ' %s' "$$escaped_raw"; \
	    done; \
	    printf '\n'; \
	  fi; \
	  printf '%s: %s' "$(MODERN_OUTPUT_DIR)/$*.pre.c" "$<"; \
	  printf '%s\n' "$$assets" | while IFS= read -r asset; do \
	    [ -n "$$asset" ] || continue; \
	    escaped=$$(printf '%s' "$$asset" | sed -e 's/\\/\\\\/g' -e 's/ /\\ /g'); \
	    printf ' %s' "$$escaped"; \
	  done; \
	  printf '\n'; \
	  printf '%s\n' "$$fetsa_pairs" | sort -u | while IFS=: read -r fetsa_raw feimg_raw; do \
	    [ -n "$$fetsa_raw" ] || continue; \
	    escaped_fetsa=$$(printf '%s' "$$fetsa_raw" | sed -e 's/\\/\\\\/g' -e 's/ /\\ /g'); \
	    escaped_feimg=$$(printf '%s' "$$feimg_raw" | sed -e 's/\\/\\\\/g' -e 's/ /\\ /g'); \
	    printf '%s: %s\n' "$$escaped_fetsa" "$$escaped_feimg"; \
	  done; \
	} > "$@.tmp"
	@mv -f "$@.tmp" "$@"

ifneq (,$(filter $(MODERN_ALL_SOURCE_GOALS),$(MAKECMDGOALS)))
include $(MODERN_ALL_DATA_ASSET_DEPS)
endif

# Generated-header bootstrap for ordinary (non-data) C sources: see the
# MODERN_ALL_C_HEADER_DEPS comment above for why GCC's own "-MM -MG" is
# used here instead of scaninc. Same `include`d-for-real-remake-restart
# wiring, gated by the same goal set, and equally exempt from NODEP for
# the same first-invocation reason.
#
# GNU Make remakes stale/missing `include`d makefiles (this rule's own
# targets) before it ever evaluates expansion-modern-all's own
# "expansion-modern-toolchain-check" prerequisite -- that check runs far
# too late to help here. Without this order-only prerequisite, a missing
# or misconfigured MODERN_CC would instead surface as a raw
# "$(MODERN_CC): not found"-style shell error from this recipe. Adding
# expansion-modern-toolchain-check as an order-only prerequisite makes
# its own actionable diagnostic run first every time any .headers.d needs
# remaking. Being .PHONY, it always runs when it's a goal or prerequisite
# in the makefile currently being read; on a clean/first invocation this
# means it runs *twice* -- once here during the pre-restart remake of the
# stale .headers.d files, then again after Make's remake-restart re-reads
# the (now up to date) makefiles and reaches expansion-modern-all's own
# explicit prerequisite on it -- confirmed empirically (two "Modern
# compiler: ..." lines on a clean build, one on a rebuild where no
# .headers.d needs remaking and no restart occurs). This is a harmless,
# cheap diagnostic re-run, not a correctness issue, so it is left as-is
# rather than adding a persistent "already checked" stamp file, which
# would risk hiding a real toolchain change made between the two runs.
$(MODERN_ALL_C_HEADER_DEPS): | expansion-modern-toolchain-check

$(MODERN_ALL_C_HEADER_DEPS): $(MODERN_OUTPUT_DIR)/%.headers.d: %.c
	@mkdir -p "$(@D)"
	@"$(MODERN_CC)" $(MODERN_CFLAGS) -MM -MG -MT "$(MODERN_OUTPUT_DIR)/$*.o" "$<" > "$@.tmp" || { \
		rm -f "$@.tmp"; \
		printf '%s\n' "error: failed to pre-scan $< for generated header dependencies" >&2; \
		exit 1; \
	}
	@mv -f "$@.tmp" "$@"

ifneq (,$(filter $(MODERN_ALL_SOURCE_GOALS),$(MAKECMDGOALS)))
include $(MODERN_ALL_C_HEADER_DEPS)
endif

expansion-modern-clean:
	$(RM) -r "$(MODERN_BUILD_ROOT)"

# ---------------------------------------------------------------------------
# Transitional modern ELF target (issue #3)
#
# Links a full modern ELF using the reviewed prepare_modern_link.py
# generator, modern runtime libraries (-lc -lnosys -lgcc), and no
# tools/agbcc libraries.  AAPCS is the selected supported ABI for
# linked outputs; APCS-GNU remains available for compile-only layout
# comparison via expansion-modern-cohort/all but is incompatible with
# the EABI5 runtime libraries.
#
# asm/fe6sio.o is assembled by the modern build from a generated
# FE6 SIO payload built from the mgfembp submodule with modern GCC.
# ---------------------------------------------------------------------------

# Enforce AAPCS for linked outputs. expansion-modern-elf is the only target
# that actually links, but expansion-modern-rom/-boot-check both transitively
# depend on it (via $(MODERN_ELF)) without naming "expansion-modern-elf"
# literally in MAKECMDGOALS themselves, so the guard must recognize the
# whole linked-output goal set, not just the elf target, or a direct
# `make expansion-modern-rom MODERN_ABI=apcs-gnu` would silently slip past
# this check and proceed toward an incompatible EABI link.
MODERN_LINKED_GOALS := \
	expansion-modern-elf \
	expansion-modern-rom \
	expansion-modern-boot-check \
	expansion-modern-savefmt-check \
	expansion-modern-title-check \
	expansion-modern-debugtools-check \
	expansion-modern-debugtools-timer-check \
	expansion-modern-debugtools-map-check \
	expansion-modern-debugtools-prep-check \
	expansion-modern-debugtools-ch4prep-check \
	expansion-modern-budget \
	expansion-modern-budget-check \
	expansion-modern-relocs \
	expansion-modern-overlay-audit \
	expansion-modern-shifted-check \
	expansion-modern-linker-check
MODERN_REQUESTED_LINKED_GOALS := $(filter $(MODERN_LINKED_GOALS),$(MAKECMDGOALS))
ifneq (,$(MODERN_REQUESTED_LINKED_GOALS))
  ifneq ($(MODERN_ABI),aapcs)
    $(error $(MODERN_REQUESTED_LINKED_GOALS) requires MODERN_ABI=aapcs; \
      all modern linked outputs (expansion-modern-elf, expansion-modern-rom, \
      expansion-modern-boot-check) require AAPCS -- apcs-gnu objects are \
      incompatible with EABI5 newlib/libgcc)
  endif
endif

# Link-only assembly objects not in expansion-modern-all.
MODERN_ELF_EXTRA_ASM_SOURCES := src/rom_header.s src/crt0.s src/m4a_1.s
MODERN_ELF_EXTRA_ASM_OBJECTS := \
	$(addprefix $(MODERN_OUTPUT_DIR)/,$(MODERN_ELF_EXTRA_ASM_SOURCES:.s=.o))

# Modern FE6 SIO payload build.
MODERN_MGFEMBP_DIR := $(MODERN_OUTPUT_DIR)/mgfembp
MODERN_MGFEMBP_PAYLOAD := $(MODERN_MGFEMBP_DIR)/fe6sio_payload.bin.lz
MODERN_FE6SIO_OBJ := $(MODERN_OUTPUT_DIR)/asm/fe6sio.o
MODERN_MGFEMBP_BUILDER := $(PYTHON) scripts/modernize/build_mgfembp.py

# All assembly sources replaced by modern objects (source-relative names).
MODERN_ELF_REPLACED_ASM := \
	$(MODERN_ALL_ASM_SOURCES:.s=.o) $(MODERN_ELF_EXTRA_ASM_SOURCES:.s=.o) \
	$(MODERN_FE6SIO_OBJ:$(MODERN_OUTPUT_DIR)/%=%)

MODERN_ELF_FE6SIO := $(MODERN_FE6SIO_OBJ)

# Non-C assembled objects from the legacy pipeline (sound, data asm, midi).
# Filter out every C object, every modern-replaced assembly, and prebuilts.
MODERN_ELF_LEGACY_ASM := $(filter-out \
	$(C_OBJECTS) $(DATA_SRC_C_OBJECTS) \
	$(MODERN_ELF_FE6SIO) $(BANIM_OBJECT) \
	$(MODERN_ELF_REPLACED_ASM), \
	$(ASM_OBJECTS))
MODERN_ELF_LEGACY_MIDI := $(MID_OBJECTS)

MODERN_ELF_LINK_DIR := $(MODERN_OUTPUT_DIR)/link
MODERN_ELF_MANIFEST := $(MODERN_ELF_LINK_DIR)/manifest.txt
MODERN_ELF_OBJECTS_LST := $(MODERN_ELF_LINK_DIR)/objects.lst
MODERN_ELF_LINK_SETTINGS := $(MODERN_ELF_LINK_DIR)/settings.txt
MODERN_ELF := $(MODERN_OUTPUT_DIR)/fireemblem8.elf
MODERN_MAP := $(MODERN_OUTPUT_DIR)/fireemblem8.map
MODERN_ELF_BANIM_SYM := $(BANIM_OBJECT).sym.o

# Clean linker script (issue #4/#16) — replaces the transitional generator.
MODERN_CLEAN_LDSCRIPT := linker/expansion.ld
MODERN_CLEAN_IWRAM := linker/iwram.ld
$(MODERN_CLEAN_LDSCRIPT) $(MODERN_CLEAN_IWRAM): ;

# ROM size configuration: 16M (default) or 32M.
MODERN_ROM_SIZE ?= 16M
ifeq ($(MODERN_ROM_SIZE),16M)
  MODERN_ROM_SIZE_BYTES := 0x01000000
  MODERN_PAD_TO := 0x09000000
else ifeq ($(MODERN_ROM_SIZE),32M)
  MODERN_ROM_SIZE_BYTES := 0x02000000
  MODERN_PAD_TO := 0x0A000000
else
  $(error Unsupported MODERN_ROM_SIZE '$(MODERN_ROM_SIZE)'; expected 16M or 32M)
endif

# --- Framework configuration and ROM identity (issue #8) --------------------
# Validates config.mk plus MODERN_CONFIG/MODERN_ABI/MODERN_ROM_SIZE/
# MODERN_TEXT_SHIFT before any modern C/assembly compilation or linking is
# attempted, resolves the deterministic build commit and config identity
# fingerprint, and feeds both into modern C sources (via MODERN_CFLAGS -D
# defines, consumed by include/expansion_config.h) and into the embedded
# ExpansionMetadata record (include/expansion_metadata.h,
# src/expansion_metadata.c).
MODERN_EXPANSION_CONFIG_TOOL := scripts/modernize/expansion_config.py

# Whether this checkout actually has the issue #8 framework files (config.mk
# plus the tool itself). True for the real repository always (both are
# committed); false only for the minimal synthetic modern.mk-only fixture
# trees some existing tests build to exercise unrelated cohort/all/elf/
# fetsatool-lock/budget behavior in isolation (they intentionally copy just
# modern.mk plus a throwaway Makefile, not config.mk or scripts/). Resolution
# below is skipped gracefully in that case -- compiled C still gets
# expansion_config.h's own #ifndef fallback macros, just not this build's
# live-resolved version/commit/fingerprint -- rather than hard-failing a
# fixture that was never exercising issue #8 in the first place. A real
# build (this repository) always has both files, so this never masks an
# actually-missing/misconfigured config.mk there.
MODERN_EXPANSION_CONFIG_AVAILABLE := $(and $(wildcard config.mk),$(wildcard $(MODERN_EXPANSION_CONFIG_TOOL)))

# Deterministic per-build metadata (issue #8 deliverable 3), generated under
# the build tree -- never a committed source directory -- and kept in sync
# via the same write-if-unchanged + FORCE idiom as MODERN_ELF_LINK_SETTINGS
# above. Declared unconditionally (like MODERN_ROM_SIZE/MODERN_PAD_TO above,
# not gated behind MODERN_GOALS): $(MODERN_ROM) unconditionally depends on
# this target, and tests/callers may legitimately invoke $(MODERN_ROM) (or
# any literal path matching it) directly without MAKECMDGOALS containing a
# MODERN_GOALS name. Because the target is unconditional, its recipe body
# (not an outer goal-based gate, which a direct-path invocation would
# bypass entirely) is what must branch on MODERN_EXPANSION_CONFIG_AVAILABLE:
# a real build with config.mk + the tool present shells out to Python exactly
# as before; a config-less synthetic fixture (see MODERN_EXPANSION_CONFIG_AVAILABLE
# above) instead writes an inert placeholder JSON with no Python/tooling
# invocation at all, so reaching this file's path in such a fixture no longer
# hard-fails on missing config.mk/scripts/modernize -- while any build with
# the framework files present still always requires and verifies the real
# generated metadata. Uses a hardcoded `python3` (not $(PYTHON)) since this
# may be pulled in by a minimal including Makefile that never defines
# $(PYTHON) -- matching the existing MODERN_TEXT_SHIFT validation's own
# convention just above.
MODERN_GENERATED_DIR := $(MODERN_OUTPUT_DIR)/generated
MODERN_BUILD_METADATA_JSON := $(MODERN_GENERATED_DIR)/expansion_build_metadata.json

.PHONY: FORCE_MODERN_BUILD_METADATA
FORCE_MODERN_BUILD_METADATA:

$(MODERN_BUILD_METADATA_JSON): FORCE_MODERN_BUILD_METADATA
	@mkdir -p "$(MODERN_GENERATED_DIR)"
ifneq (,$(MODERN_EXPANSION_CONFIG_AVAILABLE))
	@python3 "$(MODERN_EXPANSION_CONFIG_TOOL)" generate \
		--config-mk config.mk \
		--config "$(MODERN_CONFIG)" \
		--abi "$(MODERN_ABI)" \
		--rom-size "$(MODERN_ROM_SIZE)" \
		--text-shift "$(MODERN_TEXT_SHIFT)" \
		--build-id "$(EXPANSION_BUILD_ID)" \
		--version-major "$(EXPANSION_VERSION_MAJOR)" \
		--version-minor "$(EXPANSION_VERSION_MINOR)" \
		--version-patch "$(EXPANSION_VERSION_PATCH)" \
		--title "$(EXPANSION_ROM_TITLE)" \
		--game-code "$(EXPANSION_ROM_GAME_CODE)" \
		--maker-code "$(EXPANSION_ROM_MAKER_CODE)" \
		--revision "$(EXPANSION_ROM_REVISION)" \
		--output-dir "$(MODERN_GENERATED_DIR)"
else
	@printf '%s\n' '{"expansion_config_available": false}' > "$@"
endif

# The eager $(shell ...) resolution below (needed only to feed MODERN_CFLAGS
# -D defines for actual C compilation) stays gated on
# MODERN_CONFIG_RESOLVE_GOALS -- MODERN_GOALS with expansion-modern-clean
# excluded -- like NODEP above (so a legacy-only invocation of `make` never
# shells out to Python for it), and on MODERN_EXPANSION_CONFIG_AVAILABLE (so
# the minimal synthetic modern.mk-only fixtures described above are
# unaffected). expansion-modern-clean must be excluded from this gate: it
# only removes build output, never compiles or embeds anything
# expansion-config-related, so an invalid EXPANSION_* value (e.g. an
# over-length title) must not block `make expansion-modern-clean` -- clean
# has to keep working precisely so a bad config's build tree can be
# recovered from without hand-deleting it.
MODERN_CONFIG_RESOLVE_GOALS := $(filter-out expansion-modern-clean,$(MODERN_GOALS))

# Whether this invocation's MODERN_CFLAGS actually receives the
# FE8_EXPANSION_* -D defines below (both gates below hold). Used again
# further down to keep MODERN_COMPILE_SETTINGS -- the content-addressed
# recompilation stamp for every modern C/data object that observes
# include/expansion_config.h -- a single source of truth with the defines
# it is stamping, instead of re-deriving the same two gates a second time.
MODERN_EXPANSION_DEFINES_ACTIVE :=
ifneq (,$(filter $(MODERN_CONFIG_RESOLVE_GOALS),$(MAKECMDGOALS)))
 ifneq (,$(MODERN_EXPANSION_CONFIG_AVAILABLE))
  MODERN_EXPANSION_DEFINES_ACTIVE := 1
  # Every version/ROM-identity value is passed explicitly here as the
  # *current* Make variable value (config.mk's ?= default, or a
  # command-line/environment override -- Make itself resolves which wins).
  # This is what keeps this tool, the -D defines below, and the generated
  # metadata JSON as a single source of truth: whatever `make ...
  # EXPANSION_ROM_TITLE=...` resolves to is exactly what gets validated,
  # embedded in the ROM, and checked by the verifier -- never re-derived
  # from config.mk alone (which would silently ignore a command-line
  # override and desync the compiled ROM from the generated metadata).
  MODERN_EXPANSION_CONFIG_RESOLVE := $(shell python3 "$(MODERN_EXPANSION_CONFIG_TOOL)" resolve \
	--config-mk config.mk \
	--config "$(MODERN_CONFIG)" \
	--abi "$(MODERN_ABI)" \
	--rom-size "$(MODERN_ROM_SIZE)" \
	--text-shift "$(MODERN_TEXT_SHIFT)" \
	--build-id "$(EXPANSION_BUILD_ID)" \
	--version-major "$(EXPANSION_VERSION_MAJOR)" \
	--version-minor "$(EXPANSION_VERSION_MINOR)" \
	--version-patch "$(EXPANSION_VERSION_PATCH)" \
	--title "$(EXPANSION_ROM_TITLE)" \
	--game-code "$(EXPANSION_ROM_GAME_CODE)" \
	--maker-code "$(EXPANSION_ROM_MAKER_CODE)" \
	--revision "$(EXPANSION_ROM_REVISION)" \
	--save-compat-epoch "$(EXPANSION_SAVE_COMPAT_EPOCH)" 2>&1)
  ifneq (,$(filter error:%,$(MODERN_EXPANSION_CONFIG_RESOLVE)))
    $(error $(MODERN_EXPANSION_CONFIG_RESOLVE))
  endif
  MODERN_BUILD_COMMIT := $(patsubst MODERN_BUILD_COMMIT=%,%,$(filter MODERN_BUILD_COMMIT=%,$(MODERN_EXPANSION_CONFIG_RESOLVE)))
  MODERN_CONFIG_FINGERPRINT := $(patsubst MODERN_CONFIG_FINGERPRINT=%,%,$(filter MODERN_CONFIG_FINGERPRINT=%,$(MODERN_EXPANSION_CONFIG_RESOLVE)))
  MODERN_VERSION_PACKED := $(patsubst MODERN_VERSION_PACKED=%,%,$(filter MODERN_VERSION_PACKED=%,$(MODERN_EXPANSION_CONFIG_RESOLVE)))
  MODERN_VERSION_STRING := $(patsubst MODERN_VERSION_STRING=%,%,$(filter MODERN_VERSION_STRING=%,$(MODERN_EXPANSION_CONFIG_RESOLVE)))
  # Issue #2 slice 1 (review fix #4): the save-compatibility epoch is a
  # separate compatibility gate from the #8 fingerprint above (see
  # docs/config_identity.md) -- resolved the exact same way (config.mk
  # default, or a command-line/environment MODERN_CONFIG_RESOLVE_GOALS
  # override) so `make ... EXPANSION_SAVE_COMPAT_EPOCH=2` changes the
  # embedded ROM metadata without requiring `make clean` first.
  MODERN_SAVE_COMPAT_EPOCH := $(patsubst MODERN_SAVE_COMPAT_EPOCH=%,%,$(filter MODERN_SAVE_COMPAT_EPOCH=%,$(MODERN_EXPANSION_CONFIG_RESOLVE)))
  ifeq ($(strip $(MODERN_BUILD_COMMIT)),)
    $(error modern.mk: failed to resolve MODERN_BUILD_COMMIT from '$(MODERN_EXPANSION_CONFIG_TOOL) resolve'; got: $(MODERN_EXPANSION_CONFIG_RESOLVE))
  endif
  ifeq ($(strip $(MODERN_SAVE_COMPAT_EPOCH)),)
    $(error modern.mk: failed to resolve MODERN_SAVE_COMPAT_EPOCH from '$(MODERN_EXPANSION_CONFIG_TOOL) resolve'; got: $(MODERN_EXPANSION_CONFIG_RESOLVE))
  endif

  # Modern-only compiler defines feeding include/expansion_config.h. These
  # are never added to the legacy Makefile's CFLAGS, so the legacy build
  # keeps that header's hardcoded #ifndef fallbacks (today's exact ROM
  # identity) unchanged.
  MODERN_CFLAGS += \
	-DFE8_EXPANSION_VERSION_MAJOR=$(EXPANSION_VERSION_MAJOR) \
	-DFE8_EXPANSION_VERSION_MINOR=$(EXPANSION_VERSION_MINOR) \
	-DFE8_EXPANSION_VERSION_PATCH=$(EXPANSION_VERSION_PATCH) \
	-DFE8_EXPANSION_VERSION_STRING='"$(MODERN_VERSION_STRING)"' \
	-DFE8_EXPANSION_BUILD_COMMIT='"$(MODERN_BUILD_COMMIT)"' \
	-DFE8_EXPANSION_CONFIG_FINGERPRINT='"$(MODERN_CONFIG_FINGERPRINT)"' \
	-DFE8_EXPANSION_CONFIG_PRESET='"$(MODERN_CONFIG)"' \
	-DFE8_EXPANSION_ABI='"$(MODERN_ABI)"' \
	-DFE8_EXPANSION_ROM_TITLE='"$(EXPANSION_ROM_TITLE)"' \
	-DFE8_EXPANSION_ROM_GAME_CODE='"$(EXPANSION_ROM_GAME_CODE)"' \
	-DFE8_EXPANSION_ROM_MAKER_CODE='"$(EXPANSION_ROM_MAKER_CODE)"' \
	-DFE8_EXPANSION_ROM_REVISION=$(EXPANSION_ROM_REVISION) \
	-DFE8_EXPANSION_ROM_SIZE_BYTES=$(MODERN_ROM_SIZE_BYTES) \
	-DFE8_EXPANSION_SAVE_COMPAT_EPOCH=$(MODERN_SAVE_COMPAT_EPOCH)
 endif
endif

# Compile-settings stamp: a content-addressed prerequisite of every modern
# C/data object that can observe include/expansion_config.h (global.h
# includes it unconditionally, and every MODERN_ALL_C_SOURCES/
# MODERN_ALL_DATA_C_SOURCES file starts with #include "global.h" per this
# repository's include-order convention -- see MODERN_ALL_C_OBJECTS/
# MODERN_ALL_DATA_OBJECTS below), following the exact same
# write-if-unchanged + FORCE idiom as MODERN_ELF_LINK_SETTINGS above.
#
# Without this, changing a config.mk/EXPANSION_* value (title, version,
# build id, fingerprint, ROM size, save-compat epoch, ...) between two
# builds sharing the same MODERN_OUTPUT_DIR only changes MODERN_CFLAGS's
# -D flag *content* -- never
# a *file* GNU Make's dependency graph tracks -- so src/expansion_metadata.c
# (and any other translation unit reading FE8_EXPANSION_* macros) is not
# considered stale and keeps its previously-compiled object, silently
# embedding the *old* values in the next ROM and failing verify_rom_header.py
# against the freshly regenerated (and now mismatched) metadata JSON/header.
#
# Content mirrors MODERN_EXPANSION_DEFINES_ACTIVE exactly (the same single
# source of truth gating the -D flags themselves above), so the stamp only
# changes when the actual compiled defines would change: the trivial
# constant "unsupported" whenever those defines are not being added at all
# (config-less fixture, or a direct object-path invocation bypassing
# MODERN_CONFIG_RESOLVE_GOALS), and the real resolved values otherwise.
MODERN_COMPILE_SETTINGS := $(MODERN_GENERATED_DIR)/compile_settings.txt

.PHONY: FORCE_MODERN_COMPILE_SETTINGS
FORCE_MODERN_COMPILE_SETTINGS:

$(MODERN_COMPILE_SETTINGS): FORCE_MODERN_COMPILE_SETTINGS
	@mkdir -p "$(@D)"
ifneq (,$(MODERN_EXPANSION_DEFINES_ACTIVE))
	@{ \
		printf '%s\n' 'version_major=$(EXPANSION_VERSION_MAJOR)'; \
		printf '%s\n' 'version_minor=$(EXPANSION_VERSION_MINOR)'; \
		printf '%s\n' 'version_patch=$(EXPANSION_VERSION_PATCH)'; \
		printf '%s\n' 'version_string=$(MODERN_VERSION_STRING)'; \
		printf '%s\n' 'build_commit=$(MODERN_BUILD_COMMIT)'; \
		printf '%s\n' 'config_fingerprint=$(MODERN_CONFIG_FINGERPRINT)'; \
		printf '%s\n' 'config_preset=$(MODERN_CONFIG)'; \
		printf '%s\n' 'abi=$(MODERN_ABI)'; \
		printf '%s\n' 'rom_title=$(EXPANSION_ROM_TITLE)'; \
		printf '%s\n' 'rom_game_code=$(EXPANSION_ROM_GAME_CODE)'; \
		printf '%s\n' 'rom_maker_code=$(EXPANSION_ROM_MAKER_CODE)'; \
		printf '%s\n' 'rom_revision=$(EXPANSION_ROM_REVISION)'; \
		printf '%s\n' 'rom_size_bytes=$(MODERN_ROM_SIZE_BYTES)'; \
		printf '%s\n' 'save_compat_epoch=$(MODERN_SAVE_COMPAT_EPOCH)'; \
	} > "$@.tmp"
else
	@printf '%s\n' 'unsupported' > "$@.tmp"
endif
	@if [ ! -f "$@" ] || ! cmp -s "$@.tmp" "$@"; then \
		mv -f "$@.tmp" "$@"; \
	else \
		rm -f "$@.tmp"; \
	fi

# Every modern C/data object depends on the stamp above as a normal (not
# order-only) prerequisite, so a real content change bumps the object stale
# and forces a recompile; a no-op rebuild leaves the stamp's mtime (and
# therefore the object) untouched. Assembly objects (MODERN_ALL_ASM_OBJECTS)
# and the self-contained mgfembp sources are intentionally excluded: neither
# includes global.h, so neither can observe expansion_config.h.
$(MODERN_ALL_C_OBJECTS) $(MODERN_ALL_DATA_OBJECTS): $(MODERN_COMPILE_SETTINGS)


# Resolve modern LD consistently with the toolchain root.
ifeq ($(MODERN_TOOLCHAIN_ROOT),)
  MODERN_LD ?= $(PREFIX)ld$(EXE)
else
  MODERN_LD ?= $(MODERN_TOOLCHAIN_ROOT)/bin/$(PREFIX)ld$(EXE)
endif

# Resolve modern OBJCOPY consistently with the toolchain root, parallel to
# MODERN_OBJDUMP/MODERN_LD above.
ifeq ($(MODERN_TOOLCHAIN_ROOT),)
  MODERN_OBJCOPY ?= $(PREFIX)objcopy$(EXE)
  MODERN_READELF ?= $(PREFIX)readelf$(EXE)
  MODERN_NM ?= $(PREFIX)nm$(EXE)
else
  MODERN_OBJCOPY ?= $(MODERN_TOOLCHAIN_ROOT)/bin/$(PREFIX)objcopy$(EXE)
  MODERN_READELF ?= $(MODERN_TOOLCHAIN_ROOT)/bin/$(PREFIX)readelf$(EXE)
  MODERN_NM ?= $(MODERN_TOOLCHAIN_ROOT)/bin/$(PREFIX)nm$(EXE)
endif

# Library discovery at recipe time (space-safe, no xargs).
MODERN_LIBGCC_DIR = $(shell p=$$("$(MODERN_CC)" $(MODERN_BINUTILS_FLAG) \
	$(MODERN_ARCH_FLAGS) -print-libgcc-file-name 2>/dev/null) \
	&& dirname "$$p")
MODERN_NEWLIB_LIB ?=
ifeq ($(MODERN_NEWLIB_LIB),)
  MODERN_LIBC_DIR = $(shell p=$$("$(MODERN_CC)" $(MODERN_BINUTILS_FLAG) \
	$(MODERN_ARCH_FLAGS) -print-file-name=libc.a 2>/dev/null) \
	&& dirname "$$p")
else
  MODERN_LIBC_DIR = $(MODERN_NEWLIB_LIB)
endif

# Modern FE6 SIO payload: compile mgfembp submodule with modern GCC.
# Prerequisites are explicit file targets for correct incrementality.
MODERN_MGFEMBP_C_SRCS := $(sort $(wildcard mgfembp/src/*.c))
MODERN_MGFEMBP_S_SRCS := $(sort $(wildcard mgfembp/src/*.s))
MODERN_MGFEMBP_HEADERS := $(sort $(wildcard mgfembp/include/*.h))
MODERN_MGFEMBP_LDS := mgfembp/mgfembp.lds
MODERN_MGFEMBP_EMBED_ASSETS := \
	mgfembp/data/debug_font.png \
	mgfembp/data/message_gfx.png \
	mgfembp/data/message_tm_1.bin \
	mgfembp/data/message_tm_2.bin \
	mgfembp/data/message_tm_3.bin

$(MODERN_MGFEMBP_PAYLOAD): scripts/modernize/build_mgfembp.py \
		$(MODERN_MGFEMBP_LDS) $(MODERN_MGFEMBP_C_SRCS) \
		$(MODERN_MGFEMBP_S_SRCS) $(MODERN_MGFEMBP_HEADERS) \
		$(MODERN_MGFEMBP_EMBED_ASSETS) \
		$(GBAGFX) | expansion-modern-toolchain-check
	$(MODERN_MGFEMBP_BUILDER) \
		--submodule-root mgfembp \
		--output-dir "$(MODERN_MGFEMBP_DIR)" \
		--cc "$(MODERN_CC)" \
		--ld "$(MODERN_LD)" \
		--objcopy "$(MODERN_OBJCOPY)" \
		--gbagfx "$(GBAGFX)" \
		$(if $(MODERN_BINUTILS_DIR),--binutils-dir "$(MODERN_BINUTILS_DIR)") \
		$(if $(MODERN_NEWLIB_LIB),--newlib-lib "$(MODERN_NEWLIB_LIB)") \
		$(foreach a,$(MODERN_MGFEMBP_EMBED_ASSETS),--embed-asset "$a")

.PHONY: expansion-modern-mgfembp
expansion-modern-mgfembp: $(MODERN_MGFEMBP_PAYLOAD)

# Assemble fe6sio.s from the modern payload directory so
# .incbin "fe6sio_payload.bin.lz" resolves to the modern payload,
# not a potentially stale root artifact.  The compiler path is
# resolved before cd: absolute paths pass through; bare command
# names are resolved via PATH using command -v.
$(MODERN_FE6SIO_OBJ): asm/fe6sio.s $(MODERN_MGFEMBP_PAYLOAD)
	@mkdir -p "$(@D)"
	@set -eu; \
	cc="$(MODERN_CC)"; \
	case "$$cc" in /*) ;; */*) cc="$(CURDIR)/$$cc" ;; \
	*) cc=$$(command -v "$$cc" 2>/dev/null) || { \
		printf '%s\n' "error: cannot resolve modern CC: $(MODERN_CC)" >&2; \
		exit 1; } ;; esac; \
	cd "$(abspath $(MODERN_MGFEMBP_DIR))" && \
	"$$cc" \
		$(MODERN_DRIVER_FLAGS) $(MODERN_ARCH_FLAGS) \
		-I"$(CURDIR)/include" -I"$(CURDIR)" \
		$(MODERN_ABI_FLAGS) \
		-Wa,--MD,"$(abspath $(@:.o=.d))" \
		-c "$(CURDIR)/$<" -o "$(abspath $@)"
	@$(MODERN_MGFEMBP_BUILDER) --filter-depfile "$(abspath $(@:.o=.d))"

# Manifest: source-relative paths of every modern-built object.
$(MODERN_ELF_MANIFEST): $(MODERN_ALL_OBJECTS) $(MODERN_ELF_EXTRA_ASM_OBJECTS) $(MODERN_ELF_FE6SIO)
	@mkdir -p "$(@D)"
	@printf '%s\n' $(sort \
		$(patsubst $(MODERN_OUTPUT_DIR)/%,%, \
			$(MODERN_ALL_OBJECTS) \
			$(MODERN_ELF_EXTRA_ASM_OBJECTS) \
			$(MODERN_ELF_FE6SIO))) > "$@"

# Link response file for the clean, section-oriented linker path.
$(MODERN_ELF_OBJECTS_LST): $(MODERN_ALL_OBJECTS) $(MODERN_ELF_EXTRA_ASM_OBJECTS) $(MODERN_ELF_FE6SIO)
	@mkdir -p "$(@D)"
	@printf '%s\n' $(sort \
		$(MODERN_ALL_OBJECTS) \
		$(MODERN_ELF_EXTRA_ASM_OBJECTS) \
		$(MODERN_ELF_FE6SIO) \
		$(MODERN_ELF_LEGACY_ASM) \
		$(MODERN_ELF_LEGACY_MIDI) \
		$(BANIM_OBJECT)) > "$@"

# Link-affecting command-line settings are a content-addressed prerequisite.
# The FORCE recipe runs every invocation, but preserves this file's timestamp
# when settings are unchanged, so only a real setting change relinks the ELF.
.PHONY: FORCE_MODERN_ELF_LINK_SETTINGS
FORCE_MODERN_ELF_LINK_SETTINGS:

$(MODERN_ELF_LINK_SETTINGS): FORCE_MODERN_ELF_LINK_SETTINGS
	@mkdir -p "$(@D)"
	@{ \
		printf '%s\n' 'rom_size=$(MODERN_ROM_SIZE_BYTES)'; \
		printf '%s\n' 'text_shift=$(MODERN_TEXT_SHIFT)'; \
		printf '%s\n' 'ld=$(MODERN_LD)'; \
		printf '%s\n' 'ldscript=$(MODERN_CLEAN_LDSCRIPT)'; \
	} > "$@.tmp"
	@if [ ! -f "$@" ] || ! cmp -s "$@.tmp" "$@"; then \
		mv -f "$@.tmp" "$@"; \
	else \
		rm -f "$@.tmp"; \
	fi

# Ensure legacy non-C objects are fresh with full scaninc tracking.
# The outer expansion-modern-elf runs under NODEP=1 which disables
# scaninc for legacy rules.  This phony step invokes a single recursive
# $(MAKE) with NODEP=0 to rebuild only the non-C assembly and MIDI
# objects with proper asset dependency tracking, using jobserver
# propagation (+).  No legacy C objects or mgfembp are invoked.
.PHONY: expansion-modern-legacy-ready
expansion-modern-legacy-ready:
	+$(MAKE) NODEP=0 $(MODERN_ELF_LEGACY_ASM) $(MODERN_ELF_LEGACY_MIDI)

# Link preparation: FE6 SIO build output, banim via scheduler, legacy
# freshness, sidecar recovery, then the clean static linker inputs.
# $(BANIM_OBJECT) is a normal prerequisite so the main scheduler builds it
# once with no recursive-make race.
.PHONY: expansion-modern-link-prepare
expansion-modern-link-prepare: $(MODERN_ELF_FE6SIO) \
		expansion-modern-legacy-ready \
		$(MODERN_ELF_OBJECTS_LST) $(BANIM_OBJECT) \
		$(MODERN_CLEAN_LDSCRIPT) $(MODERN_CLEAN_IWRAM)
	@if [ ! -f "$(MODERN_ELF_BANIM_SYM)" ]; then \
		printf '%s\n' \
			"Sidecar missing; forcing banim rebuild..." >&2; \
		rm -f "$(BANIM_OBJECT)" "$(MODERN_ELF_BANIM_SYM)"; \
	fi
	+@if [ ! -f "$(MODERN_ELF_BANIM_SYM)" ]; then \
		$(MAKE) "$(BANIM_OBJECT)"; \
	fi
	@if [ ! -f "$(MODERN_ELF_BANIM_SYM)" ]; then \
		printf '%s\n' \
			"error: $(MODERN_ELF_BANIM_SYM) not produced" >&2; \
		exit 1; \
	fi

# Link the modern ELF with the clean, section-oriented expansion linker.
# Legacy objects and banim are owned by expansion-modern-link-prepare.
$(MODERN_ELF): expansion-modern-link-prepare $(MODERN_ELF_LINK_SETTINGS)
	@set -eu; \
	libgcc_dir="$(MODERN_LIBGCC_DIR)"; \
	libc_dir="$(MODERN_LIBC_DIR)"; \
	if [ -z "$$libgcc_dir" ] || [ ! -d "$$libgcc_dir" ]; then \
		printf '%s\n' \
			"error: cannot discover modern libgcc directory" >&2; \
		printf '%s\n' \
			"Check MODERN_CC or set library paths explicitly." >&2; \
		exit 1; \
	fi; \
	if [ -z "$$libc_dir" ] || [ ! -d "$$libc_dir" ]; then \
		printf '%s\n' \
			"error: cannot discover modern libc directory" >&2; \
		printf '%s\n' \
			"Set MODERN_NEWLIB_LIB to the directory containing" \
			"libc.a." >&2; \
		exit 1; \
	fi; \
	"$(MODERN_LD)" \
		--orphan-handling=error \
		--defsym=__rom_size=$(MODERN_ROM_SIZE_BYTES) \
		--defsym=__text_shift=$(MODERN_TEXT_SHIFT) \
		-T "$(MODERN_CLEAN_LDSCRIPT)" \
		-Map "$(MODERN_MAP)" \
		@"$(MODERN_ELF_OBJECTS_LST)" \
		-R "$(MODERN_ELF_BANIM_SYM)" \
		-L "$$libgcc_dir" \
		-L "$$libc_dir" \
		-o "$@" \
		-lc -lnosys -lgcc
	@printf 'Linked modern ELF: %s\n' "$@"

expansion-modern-elf: expansion-modern-mgfembp expansion-modern-all \
		$(MODERN_ELF_EXTRA_ASM_OBJECTS) $(MODERN_ELF)
	@printf 'Modern ELF ready: %s\n' "$(MODERN_ELF)"

# ---------------------------------------------------------------------------
# Modern ROM and deterministic boot-check targets (issue #3)
#
# expansion-modern-rom converts the modern ELF to an isolated,
# header-verified GBA ROM using the same objcopy flags as the legacy
# %.gba rule (see Makefile). expansion-modern-boot-check runs the existing
# gba-playtest behavior-policy verifier against that ROM and the repository's
# boot scenario/fingerprint, proving deterministic runtime progress (not just
# a successful link) at frames 0/60/120. Neither target claims ROM byte
# identity with the legacy build.
# ---------------------------------------------------------------------------

MODERN_ROM := $(MODERN_OUTPUT_DIR)/fireemblem8.gba
MODERN_ROM_HEADER_VERIFIER := scripts/modernize/verify_rom_header.py
MODERN_ROM_HEADER_FINALIZER := scripts/modernize/finalize_rom_header.py
MODERN_BOOT_SCENARIO := tools/gba-playtest/scenarios/boot.json
MODERN_BOOT_FINGERPRINT := tools/gba-playtest/fingerprints/boot.json
MODERN_TITLE_SCENARIO := tools/gba-playtest/scenarios/title-progression.json
MODERN_TITLE_FINGERPRINT := tools/gba-playtest/fingerprints/title-progression-modern-$(MODERN_CONFIG).json
# Unlike MODERN_TITLE_SCENARIO above, the debugtools scenario path itself
# (not just the fingerprint) is $(MODERN_CONFIG)-suffixed: the release
# scenario probes gDebugToolsProbe expecting it to stay all-zero (issue #11
# slice 1 requirement 7's release fingerprint), while the debug scenario
# probes the same struct expecting the hub/launcher to actually run --
# these are different assertions, not just different link addresses, so a
# single shared scenario file would not correctly express both.
MODERN_DEBUGTOOLS_SCENARIO := tools/gba-playtest/scenarios/debugtools-hub-modern-$(MODERN_CONFIG).json
MODERN_DEBUGTOOLS_FINGERPRINT := tools/gba-playtest/fingerprints/debugtools-hub-modern-$(MODERN_CONFIG).json
# Issue #11 slice 2: the map-phase hub scenario also has both a debug (live,
# on the real interactive Chapter 2 map) and release (compiled-out mirror)
# variant, same $(MODERN_CONFIG)-suffixed-path rationale as
# MODERN_DEBUGTOOLS_SCENARIO above.
MODERN_DEBUGTOOLS_MAP_SCENARIO := tools/gba-playtest/scenarios/debugtools-map-hub-modern-$(MODERN_CONFIG).json
MODERN_DEBUGTOOLS_MAP_FINGERPRINT := tools/gba-playtest/fingerprints/debugtools-map-hub-modern-$(MODERN_CONFIG).json
MODERN_PLAYTEST := tools/gba-playtest/gba_playtest.py

# Convert the linked ELF to a flat, padded ROM image, patch the configured
# ROM identity (title/game code/maker code/revision -- see config.mk
# EXPANSION_ROM_*) into the header and regenerate its checksum, then verify
# the result in-place: configured ROM size, title/game code/maker
# code/revision/fixed byte, the checksum byte at offset 0xBD recomputed over
# 0xA0..0xBC, and the embedded ExpansionMetadata record (issue #8). A failed
# verification deletes the ROM so a stale, invalid image is never left behind
# for expansion-modern-boot-check (or a caller) to pick up silently.
$(MODERN_ROM): $(MODERN_ELF) $(MODERN_BUILD_METADATA_JSON)
	@mkdir -p "$(@D)"
	"$(MODERN_OBJCOPY)" --strip-debug -O binary --pad-to $(MODERN_PAD_TO) --gap-fill=0xff "$<" "$@"
	@if ! "$(PYTHON)" "$(MODERN_ROM_HEADER_FINALIZER)" --metadata-json "$(MODERN_BUILD_METADATA_JSON)" "$@"; then \
		rm -f "$@"; \
		exit 1; \
	fi
	@if ! "$(PYTHON)" "$(MODERN_ROM_HEADER_VERIFIER)" --size "$(MODERN_ROM_SIZE)" --metadata-json "$(MODERN_BUILD_METADATA_JSON)" "$@"; then \
		rm -f "$@"; \
		exit 1; \
	fi

expansion-modern-rom: expansion-modern-elf $(MODERN_ROM)
	@printf 'Modern ROM ready: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'

# Preflight the libmGBA-backed playtest backend before spending time building
# the ROM, with an actionable error pointing at the same backend-check
# subcommand used by tools/gba-playtest's own tests.
.PHONY: expansion-modern-boot-preflight
expansion-modern-boot-preflight:
	@if [ ! -f "$(MODERN_BOOT_SCENARIO)" ] || \
		[ ! -f "$(MODERN_BOOT_FINGERPRINT)" ] || \
		[ ! -f "$(MODERN_TITLE_SCENARIO)" ] || \
		[ ! -f "$(MODERN_TITLE_FINGERPRINT)" ] || \
		[ ! -f "$(MODERN_DEBUGTOOLS_SCENARIO)" ] || \
		[ ! -f "$(MODERN_DEBUGTOOLS_FINGERPRINT)" ] || \
		[ ! -f "$(MODERN_DEBUGTOOLS_MAP_SCENARIO)" ] || \
		[ ! -f "$(MODERN_DEBUGTOOLS_MAP_FINGERPRINT)" ]; then \
		printf '%s\n' \
			"error: missing boot scenario or fingerprint (including title progression and debugtools)" >&2; \
		printf '  boot scenario:        %s\n' "$(MODERN_BOOT_SCENARIO)" >&2; \
		printf '  boot fingerprint:     %s\n' "$(MODERN_BOOT_FINGERPRINT)" >&2; \
		printf '  title scenario:       %s\n' "$(MODERN_TITLE_SCENARIO)" >&2; \
		printf '  title fingerprint:    %s\n' "$(MODERN_TITLE_FINGERPRINT)" >&2; \
		printf '  debugtools scenario:  %s\n' "$(MODERN_DEBUGTOOLS_SCENARIO)" >&2; \
		printf '  debugtools fingerprint: %s\n' "$(MODERN_DEBUGTOOLS_FINGERPRINT)" >&2; \
		printf '  debugtools map scenario:  %s\n' "$(MODERN_DEBUGTOOLS_MAP_SCENARIO)" >&2; \
		printf '  debugtools map fingerprint: %s\n' "$(MODERN_DEBUGTOOLS_MAP_FINGERPRINT)" >&2; \
		exit 1; \
	fi
	@if ! "$(PYTHON)" "$(MODERN_PLAYTEST)" backend-check; then \
		printf '%s\n' \
			"error: libmGBA playtest backend is unavailable" >&2; \
		printf '%s\n' \
			"Install a C compiler and libmgba-dev (or equivalent)," \
			"then rerun: $(PYTHON) $(MODERN_PLAYTEST) backend-check" >&2; \
		exit 1; \
	fi

# Full 3-checkpoint behavior-policy boot gate: proves the modern ROM reaches
# the same deterministic runtime state as the legacy ROM at frames 0/60/120
# (not merely that it links). --policy behavior is required here because the
# modern ROM is not byte-identical to the legacy ROM referenced by the
# checked-in fingerprint's own "rom" stanza; only --policy exact-rom would
# additionally require ROM identity, which this target does not claim.
expansion-modern-boot-check: expansion-modern-boot-preflight expansion-modern-rom
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_BOOT_SCENARIO)" \
		--expected "$(MODERN_BOOT_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM boot-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'

expansion-modern-title-check: expansion-modern-boot-preflight expansion-modern-rom
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_TITLE_SCENARIO)" \
		--expected "$(MODERN_TITLE_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM title-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'

# CI follow-up (issue #11 slice 1): the debugtools-hub scenario's "pre-launch"
# and "chapter2-interactive-stable" checkpoints assert an EXACT
# (zero-exclusion-range) whole-SRAM `fnv1a64-sram` hash. Booting from
# genuinely blank SRAM makes ClassifySramSaveCompat() report
# SAVE_COMPAT_EMPTY, so EnsureGlobalSaveInfoLoaded() (src/bmsave-lib.c)
# calls InitGlobalSaveInfodata() -> BuildCurrentExpansionSaveMeta(), which
# stamps that build's live FE8_EXPANSION_BUILD_COMMIT (see modern.mk's
# MODERN_BUILD_COMMIT below) into ExpansionSaveMeta.buildCommitShort --
# changing on every commit and breaking the exact hash. Seeding SRAM with
# the fixed-diagnostics fixture below keeps SRAM already
# SAVE_COMPAT_CURRENT, so that wipe/stamp path is never taken and the exact
# hash stays invariant across commits. See tools/gba-playtest/tests/
# sram_fixture.py's build_deterministic_current_image() and
# docs/debugtools.md.
MODERN_DEBUGTOOLS_SRAM_FIXTURE_SCRIPT := tools/gba-playtest/tests/sram_fixture.py
MODERN_DEBUGTOOLS_SRAM_FIXTURE_DIR := $(MODERN_OUTPUT_DIR)/debugtools-fixtures
MODERN_DEBUGTOOLS_SRAM_FIXTURE := $(MODERN_DEBUGTOOLS_SRAM_FIXTURE_DIR)/debugtools-current.sav

# The fixture's actual generation logic is not confined to
# MODERN_DEBUGTOOLS_SRAM_FIXTURE_SCRIPT: sram_fixture.py's
# build_deterministic_current_image() is a thin shell that imports and
# calls scripts/modernize/save_format_tool.py's
# build_current_expansion_save_meta()/checksum logic (the byte-exact
# source of truth for the meta layout), which in turn imports
# scripts/modernize/expansion_config.py to parse config.mk's
# EXPANSION_VERSION_*/EXPANSION_SAVE_COMPAT_EPOCH values, and
# sram_fixture.py also imports scripts/modernize/tests/test_save_format_tool.py's
# make_header()/make_image()/make_meta() struct-packing helpers. All four
# are listed explicitly here (not just the entry-point script) so that
# editing any one of them invalidates and regenerates the cached fixture
# instead of silently reusing a stale build/ artifact.
MODERN_DEBUGTOOLS_SRAM_FIXTURE_DEPS := \
	$(MODERN_DEBUGTOOLS_SRAM_FIXTURE_SCRIPT) \
	scripts/modernize/save_format_tool.py \
	scripts/modernize/expansion_config.py \
	scripts/modernize/tests/test_save_format_tool.py \
	config.mk

$(MODERN_DEBUGTOOLS_SRAM_FIXTURE): $(MODERN_DEBUGTOOLS_SRAM_FIXTURE_DEPS)
	@mkdir -p "$(@D)"
	"$(PYTHON)" "$(MODERN_DEBUGTOOLS_SRAM_FIXTURE_SCRIPT)" write-deterministic-current "$@"

# Issue #11 slice 1: proves the title-screen SELECT+R hotkey, the debug hub,
# and its one built-in "Fast Boot: Prologue" launcher all behave as designed
# in a debug build (hub opens, action registers, launcher reaches a stable
# chapter/runtime checkpoint via gDebugToolsProbe), and that the identical
# frame-for-frame input has zero effect in a release build (hub/launcher
# compiled out, gDebugToolsProbe stays all-zero). See docs/debugtools.md.
expansion-modern-debugtools-check: expansion-modern-boot-preflight expansion-modern-rom \
		$(MODERN_DEBUGTOOLS_SRAM_FIXTURE)
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_DEBUGTOOLS_SCENARIO)" \
		--sram-image "$(MODERN_DEBUGTOOLS_SRAM_FIXTURE)" \
		--expected "$(MODERN_DEBUGTOOLS_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM debugtools-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'

# Issue #11 slice 2: proves the map-phase SELECT+L hotkey opens the same hub
# from PlayerPhase_MainIdle on the real, interactive Chapter 2 map (debug
# build), lets Weather and Fog each be cycled through their bounded
# one-item submenus and returned from, and leaves the map interactive after
# the hub closes; and that the identical hotkey tail has zero effect on top
# of debugtools-hub-modern-release.json's own frame script in a release
# build. Unlike expansion-modern-debugtools-check, this scenario has no
# `sram_hash` checkpoints, so it is not seeded with
# MODERN_DEBUGTOOLS_SRAM_FIXTURE. See docs/debugtools.md.
expansion-modern-debugtools-map-check: expansion-modern-boot-preflight expansion-modern-rom
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_DEBUGTOOLS_MAP_SCENARIO)" \
		--expected "$(MODERN_DEBUGTOOLS_MAP_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM debugtools-map-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'

# Issue #11 closure: the "Fast Boot: Ch4 Prep" launcher's own pending-
# request/boot-commit lifecycle -- a second, independent launcher target
# alongside Chapter 2's, added specifically because Chapter 2's own event
# script never reaches the PREP event opcode. This scenario proves the
# hub action arms its own request and GameControl_PostIntro consumes it
# and commits gPlaySt.chapterIndex to CHAPTER_L_4 -- the same verified
# pending-request handoff mechanism as Chapter 2's own
# expansion-modern-debugtools-check, live-executed end to end. It does
# NOT capture the further live-prep-screen arrival (the world-map
# navigation through Chapter 4's own longer beginning script/battle
# sequence) -- see docs/debugtools.md "Remaining #11 scope" and
# reports/debugtools_issue11_closure.md for that explicit, honest
# residual boundary.
MODERN_DEBUGTOOLS_CH4PREP_SCENARIO := tools/gba-playtest/scenarios/debugtools-ch4-prep-launch-modern-$(MODERN_CONFIG).json
MODERN_DEBUGTOOLS_CH4PREP_FINGERPRINT := tools/gba-playtest/fingerprints/debugtools-ch4-prep-launch-modern-$(MODERN_CONFIG).json

ifeq ($(MODERN_CONFIG),debug)
# Debug only: shares the title-screen prefix with
# expansion-modern-debugtools-check, so it needs the same deterministic
# pre-seeded SRAM fixture -- booting from genuinely blank SRAM takes a
# different (WipeSram-driven) boot path with different frame timing,
# which would shift this scenario's own frame-tied checkpoints (see
# docs/debugtools.md "Deterministic pre-launch SRAM fixture"). The
# release mirror has no such dependency (release builds never seed this
# fixture either, see expansion-modern-debugtools-map-check above).
expansion-modern-debugtools-ch4prep-check: expansion-modern-boot-preflight expansion-modern-rom \
		$(MODERN_DEBUGTOOLS_SRAM_FIXTURE)
	@if [ ! -f "$(MODERN_DEBUGTOOLS_CH4PREP_SCENARIO)" ] || \
		[ ! -f "$(MODERN_DEBUGTOOLS_CH4PREP_FINGERPRINT)" ]; then \
		printf '%s\n' \
			"error: missing debugtools Ch4-Prep-launch scenario or fingerprint" >&2; \
		printf '  scenario:    %s\n' "$(MODERN_DEBUGTOOLS_CH4PREP_SCENARIO)" >&2; \
		printf '  fingerprint: %s\n' "$(MODERN_DEBUGTOOLS_CH4PREP_FINGERPRINT)" >&2; \
		exit 1; \
	fi
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_DEBUGTOOLS_CH4PREP_SCENARIO)" \
		--sram-image "$(MODERN_DEBUGTOOLS_SRAM_FIXTURE)" \
		--expected "$(MODERN_DEBUGTOOLS_CH4PREP_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM debugtools-ch4prep-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'
else
expansion-modern-debugtools-ch4prep-check: expansion-modern-boot-preflight expansion-modern-rom
	@if [ ! -f "$(MODERN_DEBUGTOOLS_CH4PREP_SCENARIO)" ] || \
		[ ! -f "$(MODERN_DEBUGTOOLS_CH4PREP_FINGERPRINT)" ]; then \
		printf '%s\n' \
			"error: missing debugtools Ch4-Prep-launch scenario or fingerprint" >&2; \
		printf '  scenario:    %s\n' "$(MODERN_DEBUGTOOLS_CH4PREP_SCENARIO)" >&2; \
		printf '  fingerprint: %s\n' "$(MODERN_DEBUGTOOLS_CH4PREP_FINGERPRINT)" >&2; \
		exit 1; \
	fi
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_DEBUGTOOLS_CH4PREP_SCENARIO)" \
		--expected "$(MODERN_DEBUGTOOLS_CH4PREP_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM debugtools-ch4prep-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'
endif

# Issue #11 slice 2: the prep-phase SELECT+B hotkey has no equivalent live
# scenario yet -- this repository's chapter data has hasPrepScreen=FALSE
# for every chapter (a vestigial FE7 field, see include/chapterdata.h) and
# no in-scope, already-decompiled event script currently drives
# PrepScreenProc_MapIdle from a deterministic boot sequence without a
# chapter/skirmish selector (explicitly out of scope for this slice, see
# docs/debugtools.md "Remaining #11 scope"). The release mirror below and
# the host C test suite (mask distinctness, call-site ordering,
# compile-time validation, idempotent registration) are the available
# deterministic proof for the prep hotkey until a future slice adds an
# in-scope deterministic path to a live prep screen.
MODERN_DEBUGTOOLS_PREP_RELEASE_SCENARIO := tools/gba-playtest/scenarios/debugtools-prep-hub-modern-release.json
MODERN_DEBUGTOOLS_PREP_RELEASE_FINGERPRINT := tools/gba-playtest/fingerprints/debugtools-prep-hub-modern-release.json

ifeq ($(MODERN_CONFIG),release)
expansion-modern-debugtools-prep-check: expansion-modern-boot-preflight expansion-modern-rom
	@if [ ! -f "$(MODERN_DEBUGTOOLS_PREP_RELEASE_SCENARIO)" ] || \
		[ ! -f "$(MODERN_DEBUGTOOLS_PREP_RELEASE_FINGERPRINT)" ]; then \
		printf '%s\n' \
			"error: missing debugtools prep-hub release scenario or fingerprint" >&2; \
		printf '  scenario:    %s\n' "$(MODERN_DEBUGTOOLS_PREP_RELEASE_SCENARIO)" >&2; \
		printf '  fingerprint: %s\n' "$(MODERN_DEBUGTOOLS_PREP_RELEASE_FINGERPRINT)" >&2; \
		exit 1; \
	fi
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_DEBUGTOOLS_PREP_RELEASE_SCENARIO)" \
		--expected "$(MODERN_DEBUGTOOLS_PREP_RELEASE_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM debugtools-prep-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'
else
expansion-modern-debugtools-prep-check:
	@printf 'Modern ROM debugtools-prep-check skipped: no live prep-screen-arrival scenario yet for config=%s -- the Ch4 Prep launchers boot-commit is proven live (see expansion-modern-debugtools-ch4prep-check), but reaching the actual live prep screen still needs undiscovered world-map input timing, an explicit issue #11 closure residual (see docs/debugtools.md "Remaining #11 scope" and reports/debugtools_issue11_closure.md); host C tests cover mask/call-site/registration correctness instead\n' \
		'$(MODERN_CONFIG)'
endif

# Issue #11 slice 1 review-fix regression check: proves proc->timer_idle
# (mirrored into gDebugToolsProbe.titleIdleTimerSample by
# DebugTools_RecordTitleIdleTimer, see Title_IDLE in src/titlescreen.c)
# freezes entirely while the debug hub is active -- holding it open across
# the vanilla `timer_idle == 815` attract-mode-transition threshold and
# proving the sampled value is byte-for-byte identical before and after
# that threshold -- then proving it resumes increasing once the hub is
# closed via a B press. A release build has no separate scenario file:
# DebugTools_IsHubActive() compiles out to a constant 0 there (see
# docs/debugtools.md), so the freeze branch in Title_IDLE is provably dead
# code, and debugtools-hub-modern-release.json already demonstrates
# gDebugToolsProbe stays all-zero across an identical-length input window.
# This target is therefore a documented no-op for MODERN_CONFIG=release
# rather than a missing check.
#
# Unlike expansion-modern-debugtools-check above, this scenario has no
# `sram_hash` checkpoints at all (every checkpoint is framebuffer/probe
# only) -- it never observes SRAM -- so it is deliberately NOT seeded with
# MODERN_DEBUGTOOLS_SRAM_FIXTURE: doing so would risk shifting this
# scenario's own frame-tied probe checkpoints (boot from blank SRAM takes a
# different, WipeSram()-driven code path with different timing) for zero
# benefit, since there is no exact-SRAM assertion here to stabilize.
ifeq ($(MODERN_CONFIG),debug)
MODERN_DEBUGTOOLS_TIMER_SCENARIO := tools/gba-playtest/scenarios/debugtools-timer-freeze-modern-debug.json
MODERN_DEBUGTOOLS_TIMER_FINGERPRINT := tools/gba-playtest/fingerprints/debugtools-timer-freeze-modern-debug.json

expansion-modern-debugtools-timer-check: expansion-modern-boot-preflight expansion-modern-rom
	@if [ ! -f "$(MODERN_DEBUGTOOLS_TIMER_SCENARIO)" ] || \
		[ ! -f "$(MODERN_DEBUGTOOLS_TIMER_FINGERPRINT)" ]; then \
		printf '%s\n' \
			"error: missing debugtools timer-freeze scenario or fingerprint" >&2; \
		printf '  scenario:    %s\n' "$(MODERN_DEBUGTOOLS_TIMER_SCENARIO)" >&2; \
		printf '  fingerprint: %s\n' "$(MODERN_DEBUGTOOLS_TIMER_FINGERPRINT)" >&2; \
		exit 1; \
	fi
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_DEBUGTOOLS_TIMER_SCENARIO)" \
		--expected "$(MODERN_DEBUGTOOLS_TIMER_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM debugtools-timer-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'
else
expansion-modern-debugtools-timer-check:
	@printf 'Modern ROM debugtools-timer-check skipped: no release scenario needed (config=%s) -- DebugTools_IsHubActive() compiles out to 0, so the Title_IDLE freeze branch is dead code; see docs/debugtools.md\n' \
		'$(MODERN_CONFIG)'
endif

# Global save-compatibility gate check (issue #2 slice 2, requirement 9).
# Generates synthetic SRAM fixtures at check time (never committed
# binaries), runs the host-side save-format migration checks
# (scripts/modernize/save_format_tool.py's own CLI), then verifies the
# committed savecompat-current/-dialog-back/-erase runtime scenarios
# against this modern ROM via --policy behavior, matched to the
# config-specific committed fingerprints. Runs all eight SaveCompatState
# values (SAVE_COMPAT_CURRENT/EMPTY plus all six non-CURRENT dialog
# states), confirmed erase, and the host-migrated v0->v1 load against
# whichever ROM is supplied (MODERN_ABI=aapcs here, or the legacy agbcc
# ROM when invoked directly) with no ABI carve-out: the persisted
# struct-layout divergence that previously required scoping this check
# has been root-caused and fixed (see
# scripts/modernize/tests/test_save_format_layout.py and
# include/bmdifficulty.h / include/bmsave.h), so
# tools/gba-playtest/run_save_compat_checks.py is fully ROM/ABI-agnostic.
MODERN_SAVEFMT_CHECKS := tools/gba-playtest/run_save_compat_checks.py
MODERN_SAVEFMT_FIXTURE_DIR := $(MODERN_OUTPUT_DIR)/savefmt-fixtures

expansion-modern-savefmt-check: expansion-modern-boot-preflight expansion-modern-rom
	"$(PYTHON)" "$(MODERN_SAVEFMT_CHECKS)" \
		--rom "$(MODERN_ROM)" \
		--config "$(MODERN_CONFIG)" \
		--fixture-dir "$(MODERN_SAVEFMT_FIXTURE_DIR)"
	@printf 'Modern ROM savefmt-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'

MODERN_BUDGET_REPORT ?= reports/linker-budget/modern-$(MODERN_CONFIG).json
MODERN_BUDGET_SCRIPT := scripts/linker_report/budget.py

# Linker budget report and drift check (issue #4 verification)
expansion-modern-budget: expansion-modern-elf
	READELF="$(MODERN_READELF)" "$(PYTHON)" "$(MODERN_BUDGET_SCRIPT)" \
		--map "$(MODERN_MAP)" \
		--elf "$(MODERN_ELF)" \
		--output "$(MODERN_BUDGET_REPORT)"

expansion-modern-budget-check: expansion-modern-elf
	READELF="$(MODERN_READELF)" "$(PYTHON)" "$(MODERN_BUDGET_SCRIPT)" \
		--map "$(MODERN_MAP)" \
		--elf "$(MODERN_ELF)" \
		--output "$(MODERN_BUDGET_REPORT)" \
		--check

MODERN_SHIFTCHECK_DIR := $(MODERN_OUTPUT_DIR)/shiftcheck
MODERN_RELOCS_ELF := $(MODERN_SHIFTCHECK_DIR)/fireemblem8.relocs.elf
MODERN_OVERLAY_REPORT := $(MODERN_SHIFTCHECK_DIR)/overlay-audit.json
MODERN_RELINK_SCRIPT := scripts/shiftcheck/modern_emit_relocs.sh
MODERN_OVERLAY_SCRIPT := scripts/linker_report/overlay_audit.py
MODERN_SHIFTED_SCRIPT := scripts/shiftcheck/modern_shifted_boot.sh
MODERN_SHIFT_AMOUNT ?= 0x40000
MODERN_SHIFTED_OUTDIR := $(MODERN_SHIFTCHECK_DIR)/shift-$(MODERN_SHIFT_AMOUNT)

$(MODERN_RELOCS_ELF): $(MODERN_ELF) $(MODERN_ELF_OBJECTS_LST) \
		$(MODERN_RELINK_SCRIPT) scripts/shiftcheck/modern_toolchain.sh
	@mkdir -p "$(@D)"
	MODERN_CC="$(MODERN_CC)" \
	MODERN_LD="$(MODERN_LD)" \
	MODERN_NEWLIB_LIB="$(MODERN_NEWLIB_LIB)" \
	OBJECTS_LST="$(MODERN_ELF_OBJECTS_LST)" \
	BANIM_SYM="$(MODERN_ELF_BANIM_SYM)" \
	LDSCRIPT="$(MODERN_CLEAN_LDSCRIPT)" \
	ROM_SIZE_BYTES="$(MODERN_ROM_SIZE_BYTES)" \
	TEXT_SHIFT=0 \
	"$(MODERN_RELINK_SCRIPT)" "$@"

expansion-modern-relocs: $(MODERN_RELOCS_ELF)
	@printf 'Modern retained-relocation ELF ready: %s\n' "$(MODERN_RELOCS_ELF)"

expansion-modern-overlay-audit: expansion-modern-relocs
	READELF="$(MODERN_READELF)" \
	"$(PYTHON)" "$(MODERN_OVERLAY_SCRIPT)" \
		--map "$(MODERN_MAP)" \
		--elf "$(MODERN_RELOCS_ELF)" \
		--output "$(MODERN_OVERLAY_REPORT)" \
		--require-relocations
	@printf 'Modern overlay audit passed: %s\n' "$(MODERN_OVERLAY_REPORT)"

expansion-modern-shifted-check: expansion-modern-boot-preflight expansion-modern-rom
	MODERN_CC="$(MODERN_CC)" \
	MODERN_LD="$(MODERN_LD)" \
	MODERN_OBJCOPY="$(MODERN_OBJCOPY)" \
	MODERN_NM="$(MODERN_NM)" \
	MODERN_NEWLIB_LIB="$(MODERN_NEWLIB_LIB)" \
	SHIFTCHECK_OUTDIR="$(MODERN_SHIFTED_OUTDIR)" \
	SHIFTCHECK_OBJECTS_LST="$(MODERN_ELF_OBJECTS_LST)" \
	SHIFTCHECK_BANIM_SYM="$(MODERN_ELF_BANIM_SYM)" \
	SHIFTCHECK_LDSCRIPT="$(MODERN_CLEAN_LDSCRIPT)" \
	SHIFTCHECK_BASE_ELF="$(MODERN_ELF)" \
	SHIFTCHECK_ROM_SIZE_BYTES="$(MODERN_ROM_SIZE_BYTES)" \
	SHIFTCHECK_ROM_SIZE="$(MODERN_ROM_SIZE)" \
	SHIFTCHECK_PAD_TO="$(MODERN_PAD_TO)" \
	SHIFTCHECK_TITLE_EXPECTED="$(MODERN_TITLE_FINGERPRINT)" \
	"$(MODERN_SHIFTED_SCRIPT)" "$(MODERN_SHIFT_AMOUNT)"

expansion-modern-linker-check: expansion-modern-budget-check \
		expansion-modern-overlay-audit \
		expansion-modern-boot-check \
		expansion-modern-title-check \
		expansion-modern-debugtools-check \
		expansion-modern-debugtools-timer-check \
		expansion-modern-debugtools-map-check \
		expansion-modern-debugtools-prep-check \
		expansion-modern-debugtools-ch4prep-check \
		expansion-modern-savefmt-check \
		expansion-modern-shifted-check
	"$(PYTHON)" scripts/shiftcheck/scan_build_addrs.py \
		--makefile Makefile \
		--ldscript "$(MODERN_CLEAN_LDSCRIPT)" \
		--banim-ldscript linker_script_banim.txt
	scripts/shiftcheck/scan_raw_casts.sh
	@printf 'Modern expansion linker checks passed (config=%s abi=%s)\n' \
		'$(MODERN_CONFIG)' '$(MODERN_ABI)'

.PHONY: \
	expansion-modern-title-check \
	expansion-modern-debugtools-check \
	expansion-modern-debugtools-timer-check \
	expansion-modern-debugtools-map-check \
	expansion-modern-debugtools-prep-check \
	expansion-modern-debugtools-ch4prep-check \
	expansion-modern-savefmt-check \
	expansion-modern-budget \
	expansion-modern-budget-check \
	expansion-modern-relocs \
	expansion-modern-overlay-audit \
	expansion-modern-shifted-check \
	expansion-modern-linker-check

-include $(wildcard $(sort $(MODERN_COHORT_DEPS) $(MODERN_ALL_DEPS) $(MODERN_FE6SIO_OBJ:.o=.d)))
