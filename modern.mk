# Opt-in modern GCC object cohort and clean expansion ELF target.

MODERN_GOALS := \
	expansion-modern-toolchain-check \
	expansion-modern-cohort \
	expansion-modern-all \
	expansion-modern-elf \
	expansion-modern-rom \
	expansion-modern-boot-check \
	expansion-modern-savefmt-check \
	expansion-modern-itemexpansion-check \
	expansion-modern-title-check \
	expansion-modern-debugtools-check \
	expansion-modern-debugtools-timer-check \
	expansion-modern-debugtools-map-check \
	expansion-modern-debugtools-tools-check \
	expansion-modern-debugtools-prep-check \
	expansion-modern-debugtools-ch4prep-check \
	expansion-modern-newgame-check \
	expansion-modern-combat-check \
	expansion-modern-saveload-check \
	expansion-modern-budget \
	expansion-modern-budget-check \
	expansion-modern-relocs \
	expansion-modern-overlay-audit \
	expansion-modern-shifted-check \
	expansion-modern-linker-check \
	expansion-modern-localization-budget \
	expansion-modern-localization-budget-check \
	expansion-modern-localization-profile-headroom-check \
	expansion-modern-localization-runtime-debug-check \
	expansion-modern-localization-runtime-release-check \
	expansion-modern-localization-runtime-multi-check \
	expansion-modern-localization-runtime-cjk-check \
	expansion-modern-localization-runtime-prefs-check \
	expansion-modern-localization-runtime-save-check \
	expansion-modern-localization-runtime-shifted-check \
	expansion-modern-game-localization-config-check \
	expansion-modern-starter-hook-check \
	expansion-modern-starter-qol-check \
	expansion-modern-starter-runtime-check \
	expansion-modern-idspace-active-check \
	expansion-modern-clean \
	sync-win
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
MODERN_TEXT_SHIFT_IS_NUM := $(shell printf '%s\n' '$(MODERN_TEXT_SHIFT)' | $(PYTHON) -c "import re, sys; v = sys.stdin.read().strip(); sys.stdout.write('ok' if re.fullmatch(r'(0x[0-9a-fA-F]+|[0-9]+)', v) else '')")
ifeq ($(MODERN_TEXT_SHIFT_IS_NUM),)
  $(error MODERN_TEXT_SHIFT '$(MODERN_TEXT_SHIFT)' is not a valid number)
endif
MODERN_TEXT_SHIFT_IS_ALIGNED := $(shell printf '%s\n' '$(MODERN_TEXT_SHIFT)' | $(PYTHON) -c "import sys; v = sys.stdin.read().strip(); sys.stdout.write('ok' if int(v, 0) % 4 == 0 else '')")
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
# Preprocessed asset/data sources still contain deliberate declaration-order
# contracts. For example, difficulty-menu code copies Pal_DifficultyMenuObjs
# and the immediately following gMenuMainObjs_0 as one ten-palette span.
MODERN_DATA_LAYOUT_FLAGS := -fno-toplevel-reorder
# The battle overlay uses fixed cross-symbol offsets (for example
# gBanimOaml + 0x5800 and gBanimScrLeft + 0x2A00) as part of its runtime ABI.
MODERN_BANIM_OVERLAY_LAYOUT_FLAGS := -fno-toplevel-reorder
# Modern framework builds favor corrected behavior; the archival lane leaves
# BUGFIX undefined to preserve byte-identical original behavior.
MODERN_DEFINE_FLAGS := -DMODERN=1 -DNONMATCHING=1 -DBUGFIX=1

# Issue #10: the item ID cap is a single build input shared by the data
# generator (scripts/generated_data/idspace.py resolve_item_id_cap, via the
# FE8_ITEM_ID_CAP env var) and the compiled item consumer
# (include/id_space.h -> ITEM_ID_CONFIGURED_CAP, consumed by src/bmitem.c).
# Flow the same value into the compile so the generated (up to 207-record)
# gItemData[] table and bmitem.c's compile-time cap contract resolve one
# identical cap. Unset leaves id_space.h's built-in 0xCD default in force.
ifneq ($(FE8_ITEM_ID_CAP),)
MODERN_DEFINE_FLAGS += -DFE8_ITEM_ID_CAP=$(FE8_ITEM_ID_CAP)
endif

# Issue #10: opt-in runtime item-expansion probe (src/expansion_itemtest.c,
# include/expansion_itemtest.h). Explicitly separate from the debug/release
# preset and from FE8_EXPANSION_DEBUG, so the identical probe runs in a real
# debug ROM and a real release ROM; unset (the default) compiles that
# translation unit to an empty object and reaches no hook at all. The header
# itself #errors when it is enabled without an expanded FE8_ITEM_ID_CAP.
ifeq ($(FE8_EXPANSION_ITEMTEST),1)
MODERN_DEFINE_FLAGS += -DFE8_EXPANSION_ITEMTEST_ENABLED=1
endif
ifeq ($(VESLY_DEBUGGER),1)
MODERN_DEFINE_FLAGS += -DFE8_VESLY_DEBUGGER=1
endif
ifeq ($(DANGER_BONES),1)
MODERN_DEFINE_FLAGS += -DFE8_DANGER_BONES=1
endif
ifeq ($(NEW_ANIMS),1)
MODERN_DEFINE_FLAGS += -DFE8_NEW_ANIMS=1
endif
ifeq ($(PURCHASE_GENERICS),1)
MODERN_DEFINE_FLAGS += -DFE8_PURCHASE_GENERICS=1
endif
ifeq ($(MMB),1)
MODERN_DEFINE_FLAGS += -DFE8_MMB=1
endif
ifeq ($(EXTEND_DESC_BOX),1)
MODERN_DEFINE_FLAGS += -DFE8_EXTEND_DESC_BOX=1
endif
ifeq ($(OVERFLOW_SAFETY_CHECKS),0)
MODERN_DEFINE_FLAGS += -DFE8_OVERFLOW_SAFETY_CHECKS=0
endif
ifeq ($(DISPLAY_OBTAINABLE_ITEM),1)
MODERN_DEFINE_FLAGS += -DFE8_DISPLAY_OBTAINABLE_ITEM=1
endif
ifeq ($(DEBUFFS_EXIST),1)
MODERN_DEFINE_FLAGS += -DFE8_DEBUFFS_EXIST=1 -DDEBUFFS_EXIST=1
endif
ifeq ($(DEBUFFS_STACK),1)
MODERN_DEFINE_FLAGS += -DFE8_DEBUFFS_STACK=1 -DDEBUFFS_STACK=1
endif
ifeq ($(TEXT_CHAPTER_NAMES),1)
MODERN_DEFINE_FLAGS += -DFE8_TEXT_CHAPTER_NAMES=1
endif
ifeq ($(BATTLE_STATS_NO_ANIMS),1)
MODERN_DEFINE_FLAGS += -DFE8_BATTLE_STATS_NO_ANIMS=1
endif
ifeq ($(HP_BARS),1)
MODERN_DEFINE_FLAGS += -DFE8_HP_BARS=1
endif
ifeq ($(CREDITS),1)
MODERN_DEFINE_FLAGS += -DFE8_CREDITS=1
endif
ifeq ($(CUSTOM_CAMPAIGN),1)
MODERN_DEFINE_FLAGS += -DFE8_CUSTOM_CAMPAIGN=1
endif
ifeq ($(SKIP_OPENING),1)
MODERN_DEFINE_FLAGS += -DFE8_SKIP_OPENING=1
endif
MODERN_INCLUDE_FLAGS := -Iinclude -I.

# Issue #6 bundled content example: its ORIGINAL display text is authored in
# src/data/items_expansion.json and generated into a BUILD-LOCAL header
# (build/generated/data/items_expansion_content_text.h, see generated_data.mk)
# rather than added to the shared, Huffman-compressed message table, which
# would re-encode a DEFAULT build's text blob. Only the content profile puts
# that directory on the include path, so a default build cannot even see the
# header -- and its compile flags, and therefore its objects, are unchanged.
ifeq ($(EXPANSION_STARTER_CONTENT),1)
MODERN_INCLUDE_FLAGS += -I$(GENERATED_DATA_OUT_DIR)
endif
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

# Issue #10 (expansion-modern-idspace-active-check hermeticity): MODERN_CFLAGS
# bakes in whatever FE8_ITEM_ID_CAP happened to be resolved when *this*
# running instance of make parsed modern.mk (an ambient shell environment
# variable, or a `make FE8_ITEM_ID_CAP=... <goal>` command-line assignment
# for this very invocation) via MODERN_DEFINE_FLAGS above -- MODERN_CFLAGS
# itself is a plain `:=` snapshot, taken once, not re-evaluated per recipe
# line. expansion-modern-idspace-active-check needs to compile three
# DIFFERENT, explicit cap states (no cap define at all, -DFE8_ITEM_ID_CAP=0xCE,
# and "the 0xCE-record table with no cap define") in the course of ONE gate
# run, regardless of whatever ambient value the *caller* happened to invoke
# it under. Reusing $(MODERN_CFLAGS) as-is for any of those three compiles
# would silently fold the caller's ambient cap into all of them instead
# (e.g. an ambient/CLI FE8_ITEM_ID_CAP=0xCE would make the "no cap flag"
# steps compile with the flag anyway, turning the gate's own default and
# negative-mismatch assertions into false failures/false passes). Strip any
# existing -DFE8_ITEM_ID_CAP=... word so the gate can supply its own,
# explicit, per-step cap define (or none) on top of this instead.
MODERN_CFLAGS_NOCAP := $(filter-out -DFE8_ITEM_ID_CAP=%,$(MODERN_CFLAGS))

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
MODERN_ALL_C_SOURCES := $(filter-out src/VeslyDebugger.c src/vesly_debugger_data.c,$(MODERN_ALL_C_SOURCES))
ifeq ($(VESLY_DEBUGGER),1)
MODERN_ALL_C_SOURCES += src/VeslyDebugger.c src/vesly_debugger_data.c
endif

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

# --- Localization catalog availability/paths (issue #18 sprint 1) ----------
# Computed here (early, before MODERN_ALL_C_OBJECTS/MODERN_ALL_OBJECTS are
# finalized just below) purely from file existence -- never from a
# resolved config identity -- exactly like MODERN_EXPANSION_CONFIG_AVAILABLE
# further down, so a real checkout (which always has both files committed)
# always registers the generated catalog object, while a minimal synthetic
# modern.mk-only fixture tree (neither file present) safely no-ops instead
# of failing to find a rule for a target nothing added to
# MODERN_ALL_C_OBJECTS. The generated catalog/header/budget files
# themselves live under $(MODERN_BUILD_ROOT) (their content never depends
# on MODERN_CONFIG/MODERN_ABI/MODERN_ROM_SIZE -- only on
# texts/expansion/registry.json + the authored locale catalogs), so every
# MODERN_CONFIG/MODERN_ABI combination *within the same build root* shares
# one generated copy instead of needlessly regenerating an identical copy
# per $(MODERN_OUTPUT_DIR).
#
# Issue #18 sprint 5 root-cause fix: this used to be a single, hardcoded
# "build/expansion-localization" path shared by *every* build root,
# including expansion-modern-localization-runtime-multi-check's own
# recursive `+$(MAKE) expansion-modern-rom MODERN_BUILD_ROOT=build/
# expansion-modern-multi ...` sub-invocation (modern.mk's own
# "Localization runtime checks" section below). Content-wise this was
# always safe (the generator is a pure function of the registry/catalog,
# never of MODERN_BUILD_ROOT/MODERN_CONFIG/EXPANSION_ENABLED_LOCALES), but
# *process*-wise it meant the default single-locale build and the
# multi-locale build's own independent `make` process tree both read/wrote
# the exact same on-disk generated header/catalog/budget files -- a real
# recursive-make/shared-output hazard (see the "&:" grouped-target comment
# on the generation recipe below for the *intra*-process-tree version of
# this same class of hazard, which grouped targets already close) whenever
# two independent process trees raced this shared path (observed as a
# transient "missing generated header" clean-build failure specifically on
# the multi-locale build). Keying this path off $(MODERN_BUILD_ROOT)
# instead gives the default build and every recursively-invoked
# alternate-build-root sub-make (multi-locale today; any future one) its
# own private, non-shared copy -- eliminating the cross-process-tree race
# at its root instead of merely documenting a "never run this with -j"
# workaround. A useful side effect: expansion-modern-clean's `$(RM) -r
# $(MODERN_BUILD_ROOT)` now also cleans this build root's own generated
# localization output, instead of silently leaving it behind under a
# sibling path clean never touched.
MODERN_LOCALIZATION_CLI := scripts/localization/cli.py
MODERN_LOCALIZATION_REGISTRY := texts/expansion/registry.json
MODERN_LOCALIZATION_AVAILABLE := $(and $(wildcard $(MODERN_LOCALIZATION_CLI)),$(wildcard $(MODERN_LOCALIZATION_REGISTRY)))
MODERN_LOCALIZATION_ROOT := $(MODERN_BUILD_ROOT)/expansion-localization
MODERN_LOCALIZATION_GENERATED_DIR := $(MODERN_LOCALIZATION_ROOT)/generated
MODERN_LOCALIZATION_CATALOG_C := $(MODERN_LOCALIZATION_GENERATED_DIR)/expansion_locale_catalog.c
MODERN_LOCALIZATION_MSG_IDS_H := $(MODERN_LOCALIZATION_GENERATED_DIR)/expansion_msg_ids.h
MODERN_LOCALIZATION_BUDGET_JSON := $(MODERN_LOCALIZATION_GENERATED_DIR)/budget.json

# --- Full-game CJK catalog (issue #18 game-catalog slice) -------------------
# The validated production EXPANSION_ENABLED_LOCALES profile is the only
# source of truth for framework identity, full-game catalogs, and localized
# fonts. The generator receives the selected real CJK subset in stable locale
# order; English is emitted once as the bounded fallback whenever that subset
# is non-empty. English/qps-only profiles emit no full-game localization
# payload and keep the historical message buffer/decoder path.
MODERN_COMMA := ,
MODERN_ENABLED_LOCALE_WORDS := $(strip \
	$(subst $(MODERN_COMMA), ,$(EXPANSION_ENABLED_LOCALES)))
MODERN_GAME_LOCALIZATION_CATALOG_LOCALES :=
ifneq ($(filter ja,$(MODERN_ENABLED_LOCALE_WORDS)),)
MODERN_GAME_LOCALIZATION_CATALOG_LOCALES := ja
endif
ifneq ($(filter zh-Hans,$(MODERN_ENABLED_LOCALE_WORDS)),)
 ifeq ($(strip $(MODERN_GAME_LOCALIZATION_CATALOG_LOCALES)),)
MODERN_GAME_LOCALIZATION_CATALOG_LOCALES := zh-Hans
 else
MODERN_GAME_LOCALIZATION_CATALOG_LOCALES := $(MODERN_GAME_LOCALIZATION_CATALOG_LOCALES),zh-Hans
 endif
endif
MODERN_GAME_LOCALIZATION_AVAILABLE := $(and \
	$(wildcard scripts/localization/game_catalog/cli.py),\
	$(wildcard texts/locales/mapping/fe8u_target_map.json))
MODERN_GAME_LOCALIZATION_ROOT := $(MODERN_BUILD_ROOT)/game-localization
MODERN_GAME_LOCALIZATION_GENERATED_DIR := $(MODERN_GAME_LOCALIZATION_ROOT)/generated
MODERN_GAME_LOCALIZATION_CONFIG_H := $(MODERN_GAME_LOCALIZATION_GENERATED_DIR)/localized_game_text_data.h
MODERN_GAME_LOCALIZATION_HEADER := $(MODERN_GAME_LOCALIZATION_GENERATED_DIR)/game_localization_catalog.h
MODERN_GAME_LOCALIZATION_C := $(MODERN_GAME_LOCALIZATION_GENERATED_DIR)/game_localization_catalog.c
MODERN_GAME_LOCALIZATION_REPORT_JSON := $(MODERN_GAME_LOCALIZATION_GENERATED_DIR)/game_localization_report.json
MODERN_GAME_LOCALIZATION_BUDGET_JSON := $(MODERN_GAME_LOCALIZATION_GENERATED_DIR)/game_localization_budget.json

ifneq ($(strip $(MODERN_GAME_LOCALIZATION_CATALOG_LOCALES)),)
 ifeq ($(strip $(MODERN_GAME_LOCALIZATION_AVAILABLE)),)
  $(error Full-game localization inputs/generator are unavailable)
 endif
 MODERN_CFLAGS += -I$(MODERN_GAME_LOCALIZATION_GENERATED_DIR)
endif

# Lets a future sprint's C source #include "expansion_msg_ids.h" (the
# generated EXP_MSG_* numeric-id header) without a further modern.mk change;
# sprint 1 itself has no such consumer yet (src/expansion_locale.c only
# uses the `extern` data declarations already reachable via -Iinclude, see
# include/expansion_locale.h's own file comment for why). A safe no-op
# when MODERN_LOCALIZATION_AVAILABLE is empty.
ifneq ($(strip $(MODERN_LOCALIZATION_AVAILABLE)),)
MODERN_CFLAGS += -I$(MODERN_LOCALIZATION_GENERATED_DIR)
endif

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

# Issue #18 sprint 1: the generated locale catalog .c
# ($(MODERN_LOCALIZATION_CATALOG_C), under $(MODERN_BUILD_ROOT)/expansion-localization/
# generated/ -- never a committed source directory) has no "original hand
# path" to reuse (there is no hand-written predecessor; it is brand new
# this sprint, defining the `extern const` data
# include/expansion_locale.h declares). A synthetic path is registered
# instead, chosen to sort immediately before src/expansion_locale.o (the
# hand-written resolver, itself already picked up by the ordinary
# MODERN_ALL_C_SOURCES wildcard above -- "-" < "." so
# "expansion_locale-catalog.o" sorts ahead of "expansion_locale.o") purely
# for readability; unlike the Issue #5 slots above, there is no
# pre-existing legacy layout this needs to avoid shifting; since this
# object is entirely new content, some shift in later objects' addresses
# relative to a build that predates issue #18 is expected and harmless
# (this sprint does not yet link into any address-sensitive checkpoint
# fixture -- see this sprint's own DONE criteria). A safe no-op when
# MODERN_LOCALIZATION_AVAILABLE is empty (modern.mk included standalone,
# or a fixture tree missing scripts/localization or texts/expansion). An
# explicit (non-pattern) compile rule for this literal target path is
# defined further below, alongside the generation stamp.
ifneq ($(strip $(MODERN_LOCALIZATION_AVAILABLE)),)
MODERN_ALL_C_OBJECTS += $(MODERN_OUTPUT_DIR)/src/expansion_locale-catalog.o
endif

ifneq ($(strip $(MODERN_GAME_LOCALIZATION_CATALOG_LOCALES)),)
MODERN_ALL_C_OBJECTS += $(MODERN_OUTPUT_DIR)/src/localized_game_text-catalog.o
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
	expansion-modern-itemexpansion-check \
	expansion-modern-title-check \
	expansion-modern-debugtools-check \
	expansion-modern-debugtools-timer-check \
	expansion-modern-debugtools-map-check \
	expansion-modern-debugtools-tools-check \
	expansion-modern-debugtools-prep-check \
	expansion-modern-debugtools-ch4prep-check \
	expansion-modern-newgame-check \
	expansion-modern-combat-check \
	expansion-modern-saveload-check \
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

# Issue #6: in the content profile the bundled content module compiles the
# BUILD-LOCAL generated authored-text header, so make it an explicit
# prerequisite -- the generic -MM -MG header scan only learns about it after
# a first successful compile, and this must work on a clean tree too. Only
# declared when the flag is on: a default build neither generates nor
# consumes that header.
ifeq ($(EXPANSION_STARTER_CONTENT),1)
$(MODERN_OUTPUT_DIR)/src/expansion_starter_content.o: $(GENERATED_DATA_CONTENT_TEXT_HEADER)
endif

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

# IWRAM-placed symbols need per-symbol BSS sections. agb_sram.c additionally
# subtracts adjacent function addresses when copying routines into IWRAM.
$(MODERN_OUTPUT_DIR)/src/agb_sram.o: MODERN_CFLAGS += -fdata-sections -fno-toplevel-reorder -fno-reorder-functions
$(MODERN_OUTPUT_DIR)/src/m4a.o: MODERN_CFLAGS += -fdata-sections
$(MODERN_OUTPUT_DIR)/src/bmshop.o: MODERN_CFLAGS += -fdata-sections
$(MODERN_ALL_DATA_OBJECTS): MODERN_CFLAGS += $(MODERN_DATA_LAYOUT_FLAGS)
$(MODERN_OUTPUT_DIR)/src/banim-ekrbattle.o: MODERN_CFLAGS += $(MODERN_BANIM_OVERLAY_LAYOUT_FLAGS)

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
	@assets=$$("$(MODERN_SCANINC)" -I include -I "" "$<" | tr -d '\r') || { \
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

# Issue #18 sprint 3 clean-build fix: expansion_msg_ids.h is
# #include "expansion_msg_ids.h"'d bare (no directory) by several
# modern-only C sources (src/uiconfig.c, src/save_compat_menu.c,
# src/debugtools_registry.c, src/expansion_language_menu.c -- all gated
# `#ifdef MODERN`) and is only ever resolved through this Makefile's own
# -I$(MODERN_LOCALIZATION_GENERATED_DIR) (added above, guarded by
# MODERN_LOCALIZATION_AVAILABLE) -- never through a same-directory or
# repo-root-relative #include path the way json_data_rules.mk's
# src/data/chapter_settings.h is (see the MODERN_ALL_C_HEADER_DEPS comment
# above for why that legitimately-relative case works with plain "-MM
# -MG"). On a cold/clean build the header does not exist on disk yet, so
# GCC cannot resolve it through that extra -I search path at all: per
# GCC's documented -MG behavior, a header it cannot find is recorded using
# exactly the string written in the #include directive, with no directory
# prepended -- i.e. the bare "expansion_msg_ids.h", never this generated
# directory's real path. That bare name has no matching rule anywhere in
# this Makefile (only $(MODERN_LOCALIZATION_MSG_IDS_H)'s real path does),
# so once this recipe's output is `include`d below, GNU Make fails the
# *entire* clean parallel build with "No rule to make target
# 'expansion_msg_ids.h'" -- intermittently only, depending on whether some
# unrelated earlier target already caused the real header to exist on
# disk before this scan ran (e.g. a leftover build/ directory from a
# previous invocation), which is exactly why this surfaced as a flaky
# "passes if the cache happens to exist" clean-build regression rather
# than a deterministic failure.
#
# The fix is to strip just that one unresolvable bare token from this
# recipe's own freshly generated dependency file before it is ever
# `include`d -- not to weaken/relax any #include directive (none are
# touched) and not to commit the generated header. This loses no real
# dependency tracking: this header's build ordering is already
# independently and unconditionally guaranteed further below by
# `$(MODERN_ALL_C_OBJECTS) $(MODERN_ALL_DATA_OBJECTS):
# $(MODERN_LOCALIZATION_MSG_IDS_H)` (the header's real, rule-backed path),
# so every modern object -- not just the four direct consumers above --
# already waits for generation first; this just removes the duplicate,
# unresolvable alias GCC's -MG happens to also emit.
MODERN_LOCALIZATION_MSG_IDS_H_BASENAME := $(notdir $(MODERN_LOCALIZATION_MSG_IDS_H))
MODERN_LOCALIZATION_MSG_IDS_H_BASENAME_RE := $(subst .,\.,$(MODERN_LOCALIZATION_MSG_IDS_H_BASENAME))

# Portability note: this filter deliberately never uses `sed -i` (in-place
# editing). GNU sed's `-i` takes an *optional* backup-suffix argument (no
# argument at all means "no backup"), while BSD/macOS sed's `-i` takes a
# *mandatory* one (an explicit empty string, `-i ''`, is required for "no
# backup") -- the two are not command-line compatible, and macOS is a
# supported host (see this Makefile's own Darwin-conditional $(SED)
# definition). A bare `sed -E -i 's/.../' file` therefore either corrupts
# the very first regex group as the "suffix" on macOS (BSD sed would
# consume the script text as the backup suffix and then fail for a
# missing operand) or silently does the wrong thing depending on the host
# -- so this recipe instead redirects the filtered stream to a second,
# equally per-target-unique temp file and atomically renames it over the
# real target, exactly like the pre-scan step immediately above it. Plain
# `sed -E 's/.../' in > out` (no `-i` at all) is one of the few sed
# invocations that *is* command-line identical on GNU and BSD/macOS sed
# (both accept `-E` for extended regexes), so no $(SED)/uname branch is
# needed here at all. No backup file is ever created either way.
$(MODERN_ALL_C_HEADER_DEPS): $(MODERN_OUTPUT_DIR)/%.headers.d: %.c
	@mkdir -p "$(@D)"
	@"$(MODERN_CC)" $(MODERN_CFLAGS) -MM -MG -MT "$(MODERN_OUTPUT_DIR)/$*.o" "$<" > "$@.tmp" || { \
		rm -f "$@.tmp"; \
		printf '%s\n' "error: failed to pre-scan $< for generated header dependencies" >&2; \
		exit 1; \
	}
	@sed -E 's/(^|[[:space:]])$(MODERN_LOCALIZATION_MSG_IDS_H_BASENAME_RE)([[:space:]]|$$)/\1\2/g' "$@.tmp" > "$@.tmp2" || { \
		rm -f "$@.tmp" "$@.tmp2"; \
		printf '%s\n' "error: failed to filter generated header dependencies for $<" >&2; \
		exit 1; \
	}
	@rm -f "$@.tmp"
	@mv -f "$@.tmp2" "$@"

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
	expansion-modern-itemexpansion-check \
	expansion-modern-title-check \
	expansion-modern-debugtools-check \
	expansion-modern-debugtools-timer-check \
	expansion-modern-debugtools-map-check \
	expansion-modern-debugtools-tools-check \
	expansion-modern-debugtools-prep-check \
	expansion-modern-debugtools-ch4prep-check \
	expansion-modern-newgame-check \
	expansion-modern-combat-check \
	expansion-modern-saveload-check \
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
MODERN_ELF_LINK_PREP := $(MODERN_ELF_LINK_DIR)/prepare.stamp
MODERN_ELF := $(MODERN_OUTPUT_DIR)/fireemblem8.elf
MODERN_MAP := $(MODERN_OUTPUT_DIR)/fireemblem8.map
MODERN_ELF_BANIM_SYM := $(BANIM_OBJECT).sym.o

# Clean linker script (issue #4/#16) — replaces the transitional generator.
MODERN_CLEAN_LDSCRIPT := linker/expansion.ld
MODERN_CLEAN_IWRAM := linker/iwram.ld
$(MODERN_CLEAN_LDSCRIPT) $(MODERN_CLEAN_IWRAM): ;

# ROM size configuration: 16M (English/pseudo default) or 32M. Production
# profiles enabling ja or zh-Hans are validated below as 32M-only; the upper
# locale bank carries their full-game catalog and localized font data.
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
MODERN_EXPANSION_CONFIG_RUNNER := $(PYTHON) "$(MODERN_EXPANSION_CONFIG_TOOL)"

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
	@$(MODERN_EXPANSION_CONFIG_RUNNER) generate \
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
		--enabled-locales "$(EXPANSION_ENABLED_LOCALES)" \
		--default-locale "$(EXPANSION_DEFAULT_LOCALE)" \
		--pseudo-locale "$(EXPANSION_PSEUDO_LOCALE)" \
		--mechanics-hooks "$(EXPANSION_MECHANICS_HOOKS)" \
		--mechanics-sample "$(EXPANSION_MECHANICS_SAMPLE)" \
		--danger-overlay-menu "$(EXPANSION_DANGER_OVERLAY_MENU)" \
		--starter-content "$(EXPANSION_STARTER_CONTENT)" \
		--vesly-debugger "$(VESLY_DEBUGGER)" \
		--danger-bones "$(DANGER_BONES)" \
		--new-anims "$(NEW_ANIMS)" \
		--purchase-generics "$(PURCHASE_GENERICS)" \
		--mmb "$(MMB)" \
		--extend-desc-box "$(EXTEND_DESC_BOX)" \
		--overflow-safety-checks "$(OVERFLOW_SAFETY_CHECKS)" \
		--display-obtainable-item "$(DISPLAY_OBTAINABLE_ITEM)" \
		--text-chapter-names "$(TEXT_CHAPTER_NAMES)" \
		--battle-stats-no-anims "$(BATTLE_STATS_NO_ANIMS)" \
		--hp-bars "$(HP_BARS)" \
		--credits "$(CREDITS)" \
		--custom-campaign "$(CUSTOM_CAMPAIGN)" \
		--skip-opening "$(SKIP_OPENING)" \
		--item-id-cap "$(FE8_ITEM_ID_CAP)" \
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
  MODERN_EXPANSION_CONFIG_RESOLVE := $(shell $(MODERN_EXPANSION_CONFIG_RUNNER) resolve \
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
	--enabled-locales "$(EXPANSION_ENABLED_LOCALES)" \
	--default-locale "$(EXPANSION_DEFAULT_LOCALE)" \
	--pseudo-locale "$(EXPANSION_PSEUDO_LOCALE)" \
	--mechanics-hooks "$(EXPANSION_MECHANICS_HOOKS)" \
	--mechanics-sample "$(EXPANSION_MECHANICS_SAMPLE)" \
	--danger-overlay-menu "$(EXPANSION_DANGER_OVERLAY_MENU)" \
	--starter-content "$(EXPANSION_STARTER_CONTENT)" \
	--vesly-debugger "$(VESLY_DEBUGGER)" \
	--danger-bones "$(DANGER_BONES)" \
	--new-anims "$(NEW_ANIMS)" \
	--purchase-generics "$(PURCHASE_GENERICS)" \
	--mmb "$(MMB)" \
	--extend-desc-box "$(EXTEND_DESC_BOX)" \
	--overflow-safety-checks "$(OVERFLOW_SAFETY_CHECKS)" \
	--display-obtainable-item "$(DISPLAY_OBTAINABLE_ITEM)" \
	--text-chapter-names "$(TEXT_CHAPTER_NAMES)" \
	--battle-stats-no-anims "$(BATTLE_STATS_NO_ANIMS)" \
	--hp-bars "$(HP_BARS)" \
	--credits "$(CREDITS)" \
	--custom-campaign "$(CUSTOM_CAMPAIGN)" \
	--skip-opening "$(SKIP_OPENING)" \
	--item-id-cap "$(FE8_ITEM_ID_CAP)" \
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
  # Issue #18 sprint 1: locale identity tokens, resolved and validated the
  # exact same way (config.mk default, or a command-line/environment
  # MODERN_CONFIG_RESOLVE_GOALS override) as every other identity field
  # above -- see scripts/modernize/expansion_config.py's
  # validate_enabled_locales/validate_default_locale/validate_pseudo_locale
  # (an invalid or inconsistent combination already made
  # MODERN_EXPANSION_CONFIG_RESOLVE start with "error:" above, which the
  # $(error ...) a few lines up already caught).
  MODERN_EXPANSION_ENABLED_LOCALE_MASK := $(patsubst MODERN_EXPANSION_ENABLED_LOCALE_MASK=%,%,$(filter MODERN_EXPANSION_ENABLED_LOCALE_MASK=%,$(MODERN_EXPANSION_CONFIG_RESOLVE)))
  MODERN_EXPANSION_DEFAULT_LOCALE_ID := $(patsubst MODERN_EXPANSION_DEFAULT_LOCALE_ID=%,%,$(filter MODERN_EXPANSION_DEFAULT_LOCALE_ID=%,$(MODERN_EXPANSION_CONFIG_RESOLVE)))
  MODERN_EXPANSION_PSEUDO_LOCALE_ENABLED := $(patsubst MODERN_EXPANSION_PSEUDO_LOCALE_ENABLED=%,%,$(filter MODERN_EXPANSION_PSEUDO_LOCALE_ENABLED=%,$(MODERN_EXPANSION_CONFIG_RESOLVE)))
  ifeq ($(strip $(MODERN_BUILD_COMMIT)),)
    $(error modern.mk: failed to resolve MODERN_BUILD_COMMIT from '$(MODERN_EXPANSION_CONFIG_TOOL) resolve'; got: $(MODERN_EXPANSION_CONFIG_RESOLVE))
  endif
  ifeq ($(strip $(MODERN_SAVE_COMPAT_EPOCH)),)
    $(error modern.mk: failed to resolve MODERN_SAVE_COMPAT_EPOCH from '$(MODERN_EXPANSION_CONFIG_TOOL) resolve'; got: $(MODERN_EXPANSION_CONFIG_RESOLVE))
  endif
  ifeq ($(strip $(MODERN_EXPANSION_ENABLED_LOCALE_MASK)),)
    $(error modern.mk: failed to resolve MODERN_EXPANSION_ENABLED_LOCALE_MASK from '$(MODERN_EXPANSION_CONFIG_TOOL) resolve'; got: $(MODERN_EXPANSION_CONFIG_RESOLVE))
  endif

  MODERN_COMPILED_ENABLED_LOCALE_MASK := $(MODERN_EXPANSION_ENABLED_LOCALE_MASK)

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
	-DFE8_EXPANSION_SAVE_COMPAT_EPOCH=$(MODERN_SAVE_COMPAT_EPOCH) \
	-DFE8_EXPANSION_ENABLED_LOCALE_MASK=$(MODERN_COMPILED_ENABLED_LOCALE_MASK)u \
	-DFE8_EXPANSION_DEFAULT_LOCALE_ID=$(MODERN_EXPANSION_DEFAULT_LOCALE_ID) \
	-DFE8_EXPANSION_PSEUDO_LOCALE_ENABLED=$(MODERN_EXPANSION_PSEUDO_LOCALE_ENABLED) \
	-DFE8_EXPANSION_MECHANICS_HOOKS=$(EXPANSION_MECHANICS_HOOKS) \
	-DFE8_EXPANSION_MECHANICS_SAMPLE=$(EXPANSION_MECHANICS_SAMPLE) \
	-DFE8_EXPANSION_DANGER_OVERLAY_MENU=$(EXPANSION_DANGER_OVERLAY_MENU) \
	-DFE8_EXPANSION_STARTER_CONTENT=$(EXPANSION_STARTER_CONTENT) \
	-DFE8_VESLY_DEBUGGER=$(VESLY_DEBUGGER) \
	-DFE8_DANGER_BONES=$(DANGER_BONES) \
	-DFE8_NEW_ANIMS=$(NEW_ANIMS) \
	-DFE8_PURCHASE_GENERICS=$(PURCHASE_GENERICS) \
	-DFE8_MMB=$(MMB) \
	-DFE8_EXTEND_DESC_BOX=$(EXTEND_DESC_BOX) \
	-DFE8_OVERFLOW_SAFETY_CHECKS=$(OVERFLOW_SAFETY_CHECKS) \
	-DFE8_DISPLAY_OBTAINABLE_ITEM=$(DISPLAY_OBTAINABLE_ITEM) \
	-DFE8_DEBUFFS_EXIST=$(DEBUFFS_EXIST) \
	-DFE8_DEBUFFS_STACK=$(DEBUFFS_STACK) \
	-DFE8_TEXT_CHAPTER_NAMES=$(TEXT_CHAPTER_NAMES) \
	-DFE8_BATTLE_STATS_NO_ANIMS=$(BATTLE_STATS_NO_ANIMS) \
	-DFE8_HP_BARS=$(HP_BARS) \
	-DFE8_CREDITS=$(CREDITS)

  # Internal modern-build provenance discriminator (NOT a user feature flag,
  # NOT folded into MODERN_CONFIG_FINGERPRINT / save identity): defined for
  # every modern translation unit so always-linked negative-control state
  # (e.g. the issue #6 danger/range overlay probe in src/playerphase.c) stays
  # present in every modern build, while the legacy build keeps
  # include/expansion_config.h's 0 fallback and emits no orphan ewram_data.
  MODERN_CFLAGS += -DFE8_EXPANSION_MODERN_BUILD=1
 endif
endif

.PHONY: expansion-modern-game-localization-config-check
expansion-modern-game-localization-config-check: $(MODERN_BUILD_METADATA_JSON)
	@$(PYTHON) -c 'import json, pathlib, sys; from scripts.localization import schema; data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")); requested = set(sys.argv[4].split(",")); expected_locales = [name for name in schema.LOCALE_IDS if name in requested]; assert data["config_fingerprint"] == sys.argv[2], (data["config_fingerprint"], sys.argv[2]); assert data["enabled_locale_mask"] == int(sys.argv[3], 0), (data["enabled_locale_mask"], sys.argv[3]); assert data["enabled_locales"] == expected_locales, (data["enabled_locales"], expected_locales); print("game-localization identity: fingerprint={} mask={} locales={}".format(sys.argv[2], sys.argv[3], ",".join(expected_locales)))' \
		"$(MODERN_BUILD_METADATA_JSON)" "$(MODERN_CONFIG_FINGERPRINT)" \
		"$(MODERN_COMPILED_ENABLED_LOCALE_MASK)" "$(EXPANSION_ENABLED_LOCALES)"

# Named production CJK profiles. Each uses a private build root so callers can
# build/compare profiles without cleaning or cross-contaminating generated
# catalogs, metadata, fonts, or objects. MODERN_CONFIG remains caller-selectable
# (debug by default); all profiles keep English as the mandatory fallback.
MODERN_LOCALE_PROFILE_EN_JA_ROOT := $(MODERN_BUILD_ROOT)-locale-en-ja
MODERN_LOCALE_PROFILE_EN_ZH_HANS_ROOT := $(MODERN_BUILD_ROOT)-locale-en-zh-hans
MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_ROOT := $(MODERN_BUILD_ROOT)-locale-en-ja-zh-hans
MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_QPS_ROOT := \
	$(MODERN_BUILD_ROOT)-locale-en-ja-zh-hans-qps
MODERN_LOCALE_PROFILE_EN_JA_OUTPUT_DIR := \
	$(MODERN_LOCALE_PROFILE_EN_JA_ROOT)/$(MODERN_CONFIG)/$(MODERN_ABI)
MODERN_LOCALE_PROFILE_EN_ZH_HANS_OUTPUT_DIR := \
	$(MODERN_LOCALE_PROFILE_EN_ZH_HANS_ROOT)/$(MODERN_CONFIG)/$(MODERN_ABI)
MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_OUTPUT_DIR := \
	$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_ROOT)/$(MODERN_CONFIG)/$(MODERN_ABI)
MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_QPS_OUTPUT_DIR := \
	$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_QPS_ROOT)/$(MODERN_CONFIG)/$(MODERN_ABI)

expansion-modern-localization-profile-en-ja:
	+$(MAKE) expansion-modern-rom MODERN_CONFIG=$(MODERN_CONFIG) MODERN_ABI=$(MODERN_ABI) \
		MODERN_ROM_SIZE=32M MODERN_BUILD_ROOT=$(MODERN_LOCALE_PROFILE_EN_JA_ROOT) \
		EXPANSION_ENABLED_LOCALES=en,ja

expansion-modern-localization-profile-en-zh-hans:
	+$(MAKE) expansion-modern-rom MODERN_CONFIG=$(MODERN_CONFIG) MODERN_ABI=$(MODERN_ABI) \
		MODERN_ROM_SIZE=32M MODERN_BUILD_ROOT=$(MODERN_LOCALE_PROFILE_EN_ZH_HANS_ROOT) \
		EXPANSION_ENABLED_LOCALES=en,zh-Hans

expansion-modern-localization-profile-en-ja-zh-hans:
	+$(MAKE) expansion-modern-rom MODERN_CONFIG=$(MODERN_CONFIG) MODERN_ABI=$(MODERN_ABI) \
		MODERN_ROM_SIZE=32M MODERN_BUILD_ROOT=$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_ROOT) \
		EXPANSION_ENABLED_LOCALES=en,ja,zh-Hans

expansion-modern-localization-profile-en-ja-zh-hans-qps:
	+$(MAKE) expansion-modern-rom MODERN_CONFIG=$(MODERN_CONFIG) MODERN_ABI=$(MODERN_ABI) \
		MODERN_ROM_SIZE=32M \
		MODERN_BUILD_ROOT=$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_QPS_ROOT) \
		EXPANSION_ENABLED_LOCALES=en,ja,zh-Hans,qps-ploc \
		EXPANSION_PSEUDO_LOCALE=1

# Build the product profiles serially: every private modern build root still
# shares the generated battle-animation sidecar, so parallel recursive profile
# builds would race that one legacy asset. Each real linked map/ELF pair must
# agree on every non-empty allocatable output section's name, VMA, and size.
# They must also retain positive EWRAM headroom and the linker's minimum
# user-stack margin below __sp_usr; neither gate can be satisfied by a
# source-only aggregate budget or by physical IWRAM space reserved for stacks.
expansion-modern-localization-profile-headroom-check:
	+$(MAKE) expansion-modern-localization-profile-en-ja \
		MODERN_CONFIG=$(MODERN_CONFIG) MODERN_ABI=$(MODERN_ABI)
	READELF="$(MODERN_READELF)" "$(PYTHON)" scripts/linker_report/budget.py \
		--map "$(MODERN_LOCALE_PROFILE_EN_JA_OUTPUT_DIR)/fireemblem8.map" \
		--elf "$(MODERN_LOCALE_PROFILE_EN_JA_OUTPUT_DIR)/fireemblem8.elf" \
		--output "$(MODERN_LOCALE_PROFILE_EN_JA_OUTPUT_DIR)/linker-budget.json" \
		--validate-elf --require-positive-headroom ewram \
		--require-positive-headroom iwram
	+$(MAKE) expansion-modern-localization-profile-en-zh-hans \
		MODERN_CONFIG=$(MODERN_CONFIG) MODERN_ABI=$(MODERN_ABI)
	READELF="$(MODERN_READELF)" "$(PYTHON)" scripts/linker_report/budget.py \
		--map "$(MODERN_LOCALE_PROFILE_EN_ZH_HANS_OUTPUT_DIR)/fireemblem8.map" \
		--elf "$(MODERN_LOCALE_PROFILE_EN_ZH_HANS_OUTPUT_DIR)/fireemblem8.elf" \
		--output "$(MODERN_LOCALE_PROFILE_EN_ZH_HANS_OUTPUT_DIR)/linker-budget.json" \
		--validate-elf --require-positive-headroom ewram \
		--require-positive-headroom iwram
	+$(MAKE) expansion-modern-localization-profile-en-ja-zh-hans \
		MODERN_CONFIG=$(MODERN_CONFIG) MODERN_ABI=$(MODERN_ABI)
	READELF="$(MODERN_READELF)" "$(PYTHON)" scripts/linker_report/budget.py \
		--map "$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_OUTPUT_DIR)/fireemblem8.map" \
		--elf "$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_OUTPUT_DIR)/fireemblem8.elf" \
		--output "$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_OUTPUT_DIR)/linker-budget.json" \
		--validate-elf --require-positive-headroom ewram \
		--require-positive-headroom iwram
	+$(MAKE) expansion-modern-localization-profile-en-ja-zh-hans-qps \
		MODERN_CONFIG=$(MODERN_CONFIG) MODERN_ABI=$(MODERN_ABI)
	READELF="$(MODERN_READELF)" "$(PYTHON)" scripts/linker_report/budget.py \
		--map "$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_QPS_OUTPUT_DIR)/fireemblem8.map" \
		--elf "$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_QPS_OUTPUT_DIR)/fireemblem8.elf" \
		--output "$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_QPS_OUTPUT_DIR)/linker-budget.json" \
		--validate-elf --require-positive-headroom ewram \
		--require-positive-headroom iwram
	@printf 'Modern localization profile headroom checks passed (config=%s abi=%s)\n' \
		'$(MODERN_CONFIG)' '$(MODERN_ABI)'

.PHONY: \
	expansion-modern-localization-profile-en-ja \
	expansion-modern-localization-profile-en-zh-hans \
	expansion-modern-localization-profile-en-ja-zh-hans \
	expansion-modern-localization-profile-en-ja-zh-hans-qps \
	expansion-modern-localization-profile-headroom-check

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
# Content mirrors MODERN_EXPANSION_DEFINES_ACTIVE's resolved defines plus the
# layout flags whose semantics are part of the modern runtime contract. This
# makes a layout-flag change rebuild an existing real modern tree without a
# manual clean. Config-less fixtures still use the stable "unsupported"
# placeholder below.
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
		printf '%s\n' 'enabled_locale_mask=$(MODERN_COMPILED_ENABLED_LOCALE_MASK)'; \
		printf '%s\n' 'game_localization_catalog_locales=$(MODERN_GAME_LOCALIZATION_CATALOG_LOCALES)'; \
		printf '%s\n' 'default_locale_id=$(MODERN_EXPANSION_DEFAULT_LOCALE_ID)'; \
		printf '%s\n' 'pseudo_locale_enabled=$(MODERN_EXPANSION_PSEUDO_LOCALE_ENABLED)'; \
		printf '%s\n' 'mechanics_hooks=$(EXPANSION_MECHANICS_HOOKS)'; \
		printf '%s\n' 'mechanics_sample=$(EXPANSION_MECHANICS_SAMPLE)'; \
		printf '%s\n' 'danger_overlay_menu=$(EXPANSION_DANGER_OVERLAY_MENU)'; \
		printf '%s\n' 'starter_content=$(EXPANSION_STARTER_CONTENT)'; \
		printf '%s\n' 'vesly_debugger=$(VESLY_DEBUGGER)'; \
		printf '%s\n' 'danger_bones=$(DANGER_BONES)'; \
		printf '%s\n' 'new_anims=$(NEW_ANIMS)'; \
		printf '%s\n' 'purchase_generics=$(PURCHASE_GENERICS)'; \
		printf '%s\n' 'mmb=$(MMB)'; \
		printf '%s\n' 'extend_desc_box=$(EXTEND_DESC_BOX)'; \
		printf '%s\n' 'overflow_safety_checks=$(OVERFLOW_SAFETY_CHECKS)'; \
		printf '%s\n' 'display_obtainable_item=$(DISPLAY_OBTAINABLE_ITEM)'; \
		printf '%s\n' 'debuffs_exist=$(DEBUFFS_EXIST)'; \
		printf '%s\n' 'debuffs_stack=$(DEBUFFS_STACK)'; \
		printf '%s\n' 'text_chapter_names=$(TEXT_CHAPTER_NAMES)'; \
		printf '%s\n' 'battle_stats_no_anims=$(BATTLE_STATS_NO_ANIMS)'; \
		printf '%s\n' 'hp_bars=$(HP_BARS)'; \
		printf '%s\n' 'credits=$(CREDITS)'; \
		printf '%s\n' 'custom_campaign=$(CUSTOM_CAMPAIGN)'; \
		printf '%s\n' 'skip_opening=$(SKIP_OPENING)'; \
		printf '%s\n' 'modern_build=1'; \
		printf '%s\n' 'item_id_cap=$(FE8_ITEM_ID_CAP)'; \
		printf '%s\n' 'item_expansion_itemtest=$(FE8_EXPANSION_ITEMTEST)'; \
		printf '%s\n' 'layout_flags=$(MODERN_LAYOUT_FLAGS)'; \
		printf '%s\n' 'data_layout_flags=$(MODERN_DATA_LAYOUT_FLAGS)'; \
		printf '%s\n' 'banim_overlay_layout_flags=$(MODERN_BANIM_OVERLAY_LAYOUT_FLAGS)'; \
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

# --- Localization catalog generation (issue #18 sprint 1) -------------------
# Regenerates $(MODERN_BUILD_ROOT)/expansion-localization/generated/{expansion_locale_catalog.c,
# expansion_msg_ids.h,budget.json} from texts/expansion/registry.json +
# the authored locale catalogs via scripts/localization/generate.py (invoked through its
# CLI, scripts/localization/cli.py -- see also localization.mk's own
# standalone, toolchain-independent localization-* targets for the same
# generator run outside of any modern build). Uses the same FORCE +
# write-if-unchanged idiom as MODERN_BUILD_METADATA_JSON above (the
# generator itself only rewrites a file whose content actually changed),
# so an unrelated rebuild does not touch these files' mtimes and therefore
# does not spuriously invalidate $(MODERN_OUTPUT_DIR)/src/
# expansion_locale-catalog.o. This recipe is reachable only when something
# depends on $(MODERN_LOCALIZATION_CATALOG_C) -- which only happens when
# MODERN_LOCALIZATION_AVAILABLE gated that object into MODERN_ALL_C_OBJECTS
# above -- so no separate availability branch is needed here, unlike
# MODERN_BUILD_METADATA_JSON (which is unconditionally a $(MODERN_ROM)
# prerequisite and so needs its own placeholder fallback). Running
# scripts/localization/cli.py performs the full validation contract
# (duplicate/sparse/out-of-order/invalid/reused-tombstone ids, ASCII/
# width/byte-budget, placeholder/control-token parity, ...) before writing
# anything, so an invalid registry/catalog fails this recipe -- and
# therefore the modern build -- with an actionable message, exactly like
# an invalid config.mk value fails MODERN_BUILD_METADATA_JSON's own
# recipe.
#
# Parallel-build safety: this recipe's three outputs used to be a plain
# (non-grouped) multi-target rule, "$(A) $(B) $(C): FORCE_MODERN_LOCALIZATION
# \n\trecipe". Sprint 3 now has real, independent consumers of two
# *different* outputs of that same rule at once -- every ordinary modern
# object depends on $(MODERN_LOCALIZATION_MSG_IDS_H) (below), while the
# generated-catalog object depends on $(MODERN_LOCALIZATION_CATALOG_C) --
# so a real "-j>1" build now schedules both as independent goals in the
# same invocation. GNU Make treats each target of a plain multi-target
# rule as an independent goal with its *own copy* of the recipe (the same
# hazard already documented and fixed for FETSATOOL's feimg/fetsa pairs
# above, via a portable mkdir-lock wrapper because neither
# graphics_file_rules.mk nor grouped targets could be touched there);
# confirmed empirically here too (instrumented recipe run under "-j16":
# two distinct PIDs both entered the recipe body before either finished).
# Concurrent invocations both eventually write the exact same, correct
# content -- scripts/localization/cli.py's generation is deterministic --
# but scripts/localization/generate.py's own write-if-unchanged helper
# writes each output file in place (no atomic temp-file-plus-rename), so
# two concurrent writers really can interleave partial writes to the same
# file, and a third process (the compiler, reading the header mid-write)
# could observe a torn/partial file. Unlike the FETSATOOL case, this
# recipe and both files it lives in (modern.mk, scripts/localization/
# generate.py) are not off-limits, and this repository already requires
# GNU Make 4.3 (see the FETSATOOL comment above's own "isolated GNU Make
# 4.3 reproduction"), so grouped "&:" targets -- introduced in GNU Make
# 4.3 specifically to guarantee a multi-output recipe runs at most once
# per invocation regardless of how many of its outputs are needed -- are
# the correct, minimal fix here: no lock file, no wrapper script, no
# change to scripts/localization/generate.py's own write behavior needed.
.PHONY: FORCE_MODERN_LOCALIZATION
FORCE_MODERN_LOCALIZATION:

$(MODERN_LOCALIZATION_CATALOG_C) $(MODERN_LOCALIZATION_MSG_IDS_H) $(MODERN_LOCALIZATION_BUDGET_JSON) &: FORCE_MODERN_LOCALIZATION
	@mkdir -p "$(MODERN_LOCALIZATION_GENERATED_DIR)"
	@$(PYTHON) -m scripts.localization.cli generate --out-dir "$(MODERN_LOCALIZATION_GENERATED_DIR)"

# Issue #18 sprint 3: ordinary compiles are not otherwise made to wait for
# expansion_msg_ids.h -- only the synthetic expansion_locale-catalog.o
# object above has its own explicit prerequisite on the generated catalog
# .c. Sprint 3 adds several new `#ifdef MODERN` call sites (src/uiconfig.c,
# src/save_compat_menu.c, src/debugtools_registry.c,
# src/expansion_language_menu.c) that #include expansion_msg_ids.h
# directly, so every modern C object now needs this same generate-first
# guarantee, not just the catalog object -- otherwise a clean build can
# race a real compiler error ("expansion_msg_ids.h: No such file or
# directory") depending on unrelated build parallelism/ordering. Guarded
# by MODERN_LOCALIZATION_AVAILABLE exactly like every other localization
# prerequisite in this section (a no-op, unreachable line when modern.mk
# is included standalone without the localization toolchain present).
ifneq ($(strip $(MODERN_LOCALIZATION_AVAILABLE)),)
$(MODERN_ALL_C_OBJECTS) $(MODERN_ALL_DATA_OBJECTS): $(MODERN_LOCALIZATION_MSG_IDS_H)
endif

# Explicit (non-pattern) compile rule for the generated catalog's synthetic
# slot object (see the MODERN_ALL_C_OBJECTS += comment above for why this
# path is synthetic, not a reinstated "original" one). GNU Make always
# prefers this explicit rule over the generic `$(MODERN_OUTPUT_DIR)/%.o: %.c`
# pattern rule for the same target, so it always compiles the real
# generated .c -- there is no on-disk src/expansion_locale-catalog.c for it
# to ever fall back to. A safe no-op target when MODERN_LOCALIZATION_AVAILABLE
# is empty (modern.mk included standalone): the rule is simply never
# reachable, since nothing adds this path to MODERN_ALL_C_OBJECTS in that
# case.
$(MODERN_OUTPUT_DIR)/src/expansion_locale-catalog.o: $(MODERN_LOCALIZATION_CATALOG_C)
	@mkdir -p $(@D)
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"

# The full-game CJK catalog plus its single shared modern English bundle are
# generated and linked only when the production profile enables real CJK.
# Grouped outputs prevent parallel compiles from racing the deterministic
# writer when the runtime headers and generated source are requested together.
.PHONY: FORCE_MODERN_GAME_LOCALIZATION
FORCE_MODERN_GAME_LOCALIZATION:

$(MODERN_GAME_LOCALIZATION_CONFIG_H) $(MODERN_GAME_LOCALIZATION_HEADER) \
$(MODERN_GAME_LOCALIZATION_C) $(MODERN_GAME_LOCALIZATION_REPORT_JSON) \
$(MODERN_GAME_LOCALIZATION_BUDGET_JSON) &: FORCE_MODERN_GAME_LOCALIZATION
	@mkdir -p "$(MODERN_GAME_LOCALIZATION_GENERATED_DIR)"
	@$(PYTHON) -m scripts.localization.game_catalog generate \
		--out-dir "$(MODERN_GAME_LOCALIZATION_GENERATED_DIR)" \
		--enabled-locales "$(MODERN_GAME_LOCALIZATION_CATALOG_LOCALES)"

ifneq ($(strip $(MODERN_GAME_LOCALIZATION_CATALOG_LOCALES)),)
$(MODERN_ALL_C_OBJECTS) $(MODERN_ALL_DATA_OBJECTS): \
	$(MODERN_GAME_LOCALIZATION_CONFIG_H) $(MODERN_GAME_LOCALIZATION_HEADER)
game_localization_catalog.h: $(MODERN_GAME_LOCALIZATION_HEADER) ;
localized_game_text_data.h: $(MODERN_GAME_LOCALIZATION_CONFIG_H) ;
endif

$(MODERN_OUTPUT_DIR)/src/localized_game_text-catalog.o: $(MODERN_GAME_LOCALIZATION_C)
	@mkdir -p $(@D)
	"$(MODERN_CC)" $(MODERN_CFLAGS) -MMD -MP -MF "$(@:.o=.d)" -MQ "$@" -c "$<" -o "$@"


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
$(MODERN_ELF_LINK_PREP): $(MODERN_ELF_FE6SIO) \
		$(MODERN_ELF_OBJECTS_LST) $(BANIM_OBJECT) \
		$(MODERN_ELF_LEGACY_ASM) $(MODERN_ELF_LEGACY_MIDI) \
		$(MODERN_CLEAN_LDSCRIPT) $(MODERN_CLEAN_IWRAM)
	+$(MAKE) NODEP=0 $(MODERN_ELF_LEGACY_ASM) $(MODERN_ELF_LEGACY_MIDI)
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
	@touch "$@"

.PHONY: expansion-modern-link-prepare
expansion-modern-link-prepare: $(MODERN_ELF_LINK_PREP)

# Link the modern ELF with the clean, section-oriented expansion linker.
# Legacy objects and banim are owned by expansion-modern-link-prepare.
#
# $(MODERN_ALL_OBJECTS)/$(MODERN_COMPILE_SETTINGS) are listed here as
# EXPLICIT, real (non-phony) prerequisites, in addition to
# expansion-modern-link-prepare above (which already transitively pulls
# them in via $(MODERN_ELF_OBJECTS_LST)). Diagnosed while investigating a
# reported intermittent "gItemExpansionProbe not found" failure at
# expansion-modern-itemexpansion-check-debug when it runs, in the same
# build root, right after expansion-modern-linker-check (which compiles
# without FE8_EXPANSION_ITEMTEST/FE8_ITEM_ID_CAP=0xCE): every C/data
# object already depends on $(MODERN_COMPILE_SETTINGS) (which folds in
# both flags -- see that stamp's own comment), so a real, isolated,
# repeated `-j2`/`-j16` reproduction of that exact gate order never
# reproduced a stale link locally. But this rule's ONLY prior link to
# "objects must be current" was implicit: expansion-modern-link-prepare
# is `.PHONY`, so GNU Make always reruns it and therefore always reruns
# THIS rule's own recipe too (relying on that "phony prerequisite forces
# the whole chain" side effect, not on a real file-staleness comparison
# against the objects/compile-settings themselves). That made the "no
# stale object ever reaches the linker" guarantee for this specific rule
# real but non-obvious -- easy to silently break by a future change that
# converts expansion-modern-link-prepare's aggregation into anything less
# than an always-rerun phony (e.g. trimming it for build-speed). Listing
# the objects and the compile-settings stamp directly here turns "the
# link must observe the current cap/itemtest/compile flags" into an
# ordinary, explicit, self-enforcing Make dependency edge instead of a
# side effect of another rule's phoniness -- a pure hardening (no
# observable behavior change: the link already always reruns; see
# docs/upstream-porting.md and this sprint's diagnosis report,
# reports/itemexpansion_gate_order_race_diagnosis.md, for the full
# reproduction log and regression coverage added alongside this).
$(MODERN_ELF): $(MODERN_ELF_LINK_PREP) $(MODERN_ELF_LINK_SETTINGS) \
		$(MODERN_ALL_OBJECTS) $(MODERN_COMPILE_SETTINGS)
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
		--defsym=__end__=end \
		-T "$(MODERN_CLEAN_LDSCRIPT)" \
		-Map "$(MODERN_MAP)" \
		@"$(MODERN_ELF_OBJECTS_LST)" \
		-L "$$libgcc_dir" \
		-L "$$libc_dir" \
		-o "$@" \
		-lc -lsysbase -lc -lnosys -lgcc
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
ifeq ($(SKIP_OPENING),1)
MODERN_BOOT_FINGERPRINT := tools/gba-playtest/fingerprints/boot-skip-opening.json
endif
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

# Opt-in convenience target (not part of `all`/boot-check): copy the built
# modern ROM to a Windows-native path, for WSL setups where a GUI emulator
# on the Windows side reads over \\wsl.localhost\ -- copying to a native
# path avoids that bridge's file-locking/latency issues. Override
# WIN_SYNC_DIR to point elsewhere; default targets this machine's devkitPro
# install layout.
WIN_SYNC_DIR := /mnt/c/devkitPro/feex

.PHONY: sync-win
sync-win: expansion-modern-rom
	@mkdir -p "$(WIN_SYNC_DIR)"
	cp "$(MODERN_ROM)" "$(WIN_SYNC_DIR)/"
	@printf 'Copied %s -> %s/\n' "$(MODERN_ROM)" "$(WIN_SYNC_DIR)"

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

# Issue #11 closure: proves all five shipped bounded tools (Unit Inspect/Edit,
# Convoy Inspect/Edit, Flag/Chapter, RNG Inspect/Control, Save Compatibility/
# State Inspect) are driven LIVE from the real Chapter 2 map debug hub in a
# debug build -- each inspect samples semantic state, each mutating tool only
# mutates after its own explicit confirm submenu item (asserted via
# gDebugToolsProbe transaction counters and genuine convoy/flag/RNG pre/post
# deltas), the read-only Save inspector never writes, every submenu returns
# safely to the hub, and the map is still interactive after the hub closes
# (player cursor moves). The config-parametrized release scenario instead
# proves the identical input has zero effect (hub/tools compiled out,
# gDebugToolsProbe stays all-zero). Probe-only, so -- like
# expansion-modern-debugtools-map-check above -- it is not seeded with
# MODERN_DEBUGTOOLS_SRAM_FIXTURE. See docs/debugtools.md and
# reports/debugtools_issue11_closure.md.
MODERN_DEBUGTOOLS_TOOLS_SCENARIO := tools/gba-playtest/scenarios/debugtools-tools-modern-$(MODERN_CONFIG).json
MODERN_DEBUGTOOLS_TOOLS_FINGERPRINT := tools/gba-playtest/fingerprints/debugtools-tools-modern-$(MODERN_CONFIG).json

expansion-modern-debugtools-tools-check: expansion-modern-boot-preflight expansion-modern-rom
	@if [ ! -f "$(MODERN_DEBUGTOOLS_TOOLS_SCENARIO)" ] || \
		[ ! -f "$(MODERN_DEBUGTOOLS_TOOLS_FINGERPRINT)" ]; then \
		printf '%s\n' "error: missing debugtools tools scenario or fingerprint" >&2; \
		printf '  scenario:    %s\n' "$(MODERN_DEBUGTOOLS_TOOLS_SCENARIO)" >&2; \
		printf '  fingerprint: %s\n' "$(MODERN_DEBUGTOOLS_TOOLS_FINGERPRINT)" >&2; \
		exit 1; \
	fi
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_DEBUGTOOLS_TOOLS_SCENARIO)" \
		--expected "$(MODERN_DEBUGTOOLS_TOOLS_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM debugtools-tools-check passed (five bounded tools live+confirmed in debug, compiled-out all-zero in release): %s (config=%s abi=%s)\n' \
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
# Issue #11 closure: the live prep-screen-arrival scenario the debug branch
# below now actually runs (it was an explicit residual before). Boots the
# debug-only "Fast Boot: Ch4 Prep" launcher, traverses the Chapter 4 world
# map (L cursor-jump + A node-confirm), skips the beginning event/scripted
# battle to the real CALL(EventScr_CommonPrep) PREP opcode, rests
# gProcScr_SALLYCURSOR in PrepScreenProc_MapIdle, and fires the SELECT+B
# prep hotkey -- proving gDebugToolsProbe.prepScreenObservedCount 0->1, the
# hub opening, its idempotent reentrancy, and a safe return to the still-live
# prep. Debug-only: depends on the debug-only launcher (compiled out of a
# release build), which is why the release branch keeps the compiled-out
# mirror instead. Boots from blank SRAM (its own deterministic WipeSram path,
# verified reproducible), so unlike the ch4prep launcher check it needs no
# pre-seeded fixture. See reports/debugtools_issue11_closure.md.
MODERN_DEBUGTOOLS_PREP_POSITIVE_SCENARIO := tools/gba-playtest/scenarios/debugtools-ch4-prep-positive-modern-debug.json
MODERN_DEBUGTOOLS_PREP_POSITIVE_FINGERPRINT := tools/gba-playtest/fingerprints/debugtools-ch4-prep-positive-modern-debug.json

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
expansion-modern-debugtools-prep-check: expansion-modern-boot-preflight expansion-modern-rom
	@if [ ! -f "$(MODERN_DEBUGTOOLS_PREP_POSITIVE_SCENARIO)" ] || \
		[ ! -f "$(MODERN_DEBUGTOOLS_PREP_POSITIVE_FINGERPRINT)" ]; then \
		printf '%s\n' \
			"error: missing debugtools prep-positive scenario or fingerprint" >&2; \
		printf '  scenario:    %s\n' "$(MODERN_DEBUGTOOLS_PREP_POSITIVE_SCENARIO)" >&2; \
		printf '  fingerprint: %s\n' "$(MODERN_DEBUGTOOLS_PREP_POSITIVE_FINGERPRINT)" >&2; \
		exit 1; \
	fi
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_DEBUGTOOLS_PREP_POSITIVE_SCENARIO)" \
		--expected "$(MODERN_DEBUGTOOLS_PREP_POSITIVE_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM debugtools-prep-check passed (live prep MapIdle SELECT+B hotkey): %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'
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

# Issue #13 closure: deterministic clean-boot "New Game" creation. Shares
# savecompat-current.json's own title/save-menu cadence (frames 0..900,
# reaching the ordinary top-level Save Menu with no dialog) and then
# replays three ordinary A confirmations -- New Game, Easy, first empty
# save slot -- never a raw memory write or scripted cursor move (each
# confirmed item is already the menu's own default highlight). Requires
# the same deterministic pre-seeded CURRENT-format SRAM fixture as
# expansion-modern-debugtools-check above (a genuinely blank chip takes
# the WipeSram-driven boot path instead, with different frame timing) --
# reused as-is, not regenerated, since it is exactly "a deterministic
# CURRENT-format SRAM image", with no debug-tools-specific content. See
# tools/gba-playtest/scenarios/new-game.json and
# reports/gba_playtest_issue13_closure.md.
MODERN_NEWGAME_SCENARIO := tools/gba-playtest/scenarios/new-game.json
MODERN_NEWGAME_FINGERPRINT := tools/gba-playtest/fingerprints/new-game-modern-$(MODERN_CONFIG).json

expansion-modern-newgame-check: expansion-modern-boot-preflight expansion-modern-rom \
		$(MODERN_DEBUGTOOLS_SRAM_FIXTURE)
	@if [ ! -f "$(MODERN_NEWGAME_SCENARIO)" ] || \
		[ ! -f "$(MODERN_NEWGAME_FINGERPRINT)" ]; then \
		printf '%s\n' \
			"error: missing new-game scenario or fingerprint" >&2; \
		printf '  scenario:    %s\n' "$(MODERN_NEWGAME_SCENARIO)" >&2; \
		printf '  fingerprint: %s\n' "$(MODERN_NEWGAME_FINGERPRINT)" >&2; \
		exit 1; \
	fi
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_NEWGAME_SCENARIO)" \
		--sram-image "$(MODERN_DEBUGTOOLS_SRAM_FIXTURE)" \
		--expected "$(MODERN_NEWGAME_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM newgame-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'

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

# ---------------------------------------------------------------------------
# Issue #10: the ACTIVE id-space contract must be COMPILED, not just generated
# ---------------------------------------------------------------------------
# The generated item table (build/generated/data/data_items.c) includes the
# build-local ACTIVE header and compile-time asserts that the compiler cap
# (-DFE8_ITEM_ID_CAP / include/id_space.h default) and the generated record
# count are the same build input. This gate proves all three directions with
# the real modern toolchain:
#   * default    -> 0xCD / 206 records compiles;
#   * configured -> 0xCE / 207 records compiles with -DFE8_ITEM_ID_CAP=0xCE;
#   * mismatched -> the 0xCE table compiled WITHOUT the flag must fail, which
#     is exactly the silent 206-vs-207 divergence this contract exists to stop.
# Compile-only (no link/ROM), so it is fast and needs no emulator; it restores
# the default-cap generated table on the way out.
#
# Hermeticity (this gate must pass identically regardless of how the CALLER
# invoked it -- ambient shell environment unset, ambient FE8_ITEM_ID_CAP=0xCE,
# or a `make ... FE8_ITEM_ID_CAP=0xCE` command-line assignment on the gate
# itself): two independent leaks had to be closed, both stemming from the same
# root cause -- FE8_ITEM_ID_CAP is resolved ONCE per make process, not
# per-recipe-line, so a plain env-var prefix on a recipe command is not enough
# to force a particular state:
#   1. $(MODERN_CFLAGS) bakes in whatever FE8_ITEM_ID_CAP this gate's OWN
#      make process resolved at parse time (see MODERN_CFLAGS_NOCAP above).
#      Every compile below therefore uses $(MODERN_CFLAGS_NOCAP) plus its own
#      explicit -DFE8_ITEM_ID_CAP (or none), never the ambient $(MODERN_CFLAGS).
#   2. Each $(MAKE) recursion that regenerates $$C re-resolves FE8_ITEM_ID_CAP
#      for that CHILD process. A `FE8_ITEM_ID_CAP=... $(MAKE) ...` shell env
#      prefix is silently ignored by that child whenever the gate itself was
#      invoked with a `make ... FE8_ITEM_ID_CAP=...` command-line assignment,
#      because GNU Make auto-forwards command-line-origin variables to every
#      recursive $(MAKE) via MAKEFLAGS, and command-line origin outranks a
#      plain environment-variable prefix in the child too. The fix is GNU
#      Make's own documented escape hatch: pass FE8_ITEM_ID_CAP as an explicit
#      argument on the recursive make's OWN command line (`$(MAKE)
#      FE8_ITEM_ID_CAP=... $$C`, including the empty `FE8_ITEM_ID_CAP=` to
#      force the unset default) -- that always wins, in every ambient/CLI
#      combination, because it is that child's own command line.
.PHONY: expansion-modern-idspace-active-check
expansion-modern-idspace-active-check: expansion-modern-toolchain-check
	@set -e; \
	OUT="$(MODERN_OUTPUT_DIR)/idspace-active-check"; mkdir -p "$$OUT"; \
	C=$(GENERATED_DATA_OUT_DIR)/data_items.c; H=$(GENERATED_DATA_ACTIVE_HEADER); \
	echo "--- default cap: generated table and ACTIVE header must both say 0xCD / 206 ---"; \
	$(MAKE) --no-print-directory FE8_ITEM_ID_CAP= $$C >/dev/null; \
	grep -q "ITEM_ID_ACTIVE_CONFIGURED_CAP 0xCD" $$H || { echo "FAIL: ACTIVE header is not at the default cap" >&2; exit 1; }; \
	grep -q "ITEM_ID_ACTIVE_RECORD_COUNT 206" $$H || { echo "FAIL: ACTIVE header record count is not 206" >&2; exit 1; }; \
	"$(MODERN_CC)" $(MODERN_CFLAGS_NOCAP) -c "$$C" -o "$$OUT/items_default.o"; \
	echo "OK: default-cap generated table compiles against the ACTIVE contract (0xCD / 206)"; \
	echo "--- configured cap: FE8_ITEM_ID_CAP=0xCE must move both to 0xCE / 207 ---"; \
	$(MAKE) --no-print-directory FE8_ITEM_ID_CAP=0xCE $$C >/dev/null; \
	grep -q "ITEM_ID_ACTIVE_CONFIGURED_CAP 0xCE" $$H || { echo "FAIL: ACTIVE header did not follow the configured cap" >&2; exit 1; }; \
	grep -q "ITEM_ID_ACTIVE_RECORD_COUNT 207" $$H || { echo "FAIL: ACTIVE header record count is not 207" >&2; exit 1; }; \
	"$(MODERN_CC)" $(MODERN_CFLAGS_NOCAP) -DFE8_ITEM_ID_CAP=0xCE -c "$$C" -o "$$OUT/items_active.o"; \
	echo "OK: configured generated table compiles against the ACTIVE contract (0xCE / 207)"; \
	echo "--- negative: the 0xCE table compiled without the cap flag must FAIL ---"; \
	if "$(MODERN_CC)" $(MODERN_CFLAGS_NOCAP) -c "$$C" -o "$$OUT/items_mismatch.o" >/dev/null 2>&1; then \
		echo "FAIL: a 207-record table compiled at the 0xCD compiler cap -- the contract assert is dead" >&2; exit 1; \
	fi; \
	echo "OK: cap/count divergence is a hard compile error, not a silent truncation"; \
	echo "--- desync recovery: a stale ACTIVE header left by an out-of-band, differently-capped generated-data-check must self-heal on the FIRST plain default build, before this consumer compiles ---"; \
	$(MAKE) --no-print-directory FE8_ITEM_ID_CAP= $$C >/dev/null; \
	FE8_ITEM_ID_CAP=0xCE $(GENERATED_DATA_PY).idspace active-check --out-dir $(GENERATED_DATA_OUT_DIR) >/dev/null; \
	grep -q "ITEM_ID_ACTIVE_CONFIGURED_CAP 0xCE" $$H || { echo "FAIL: could not stage the stale-0xCE ACTIVE header desync" >&2; exit 1; }; \
	grep -q "item_id_cap=0xCD" $(GENERATED_DATA_OUT_DIR)/.item_id_cap.stamp || { echo "FAIL: desync setup expected the cap stamp to still record the default cap" >&2; exit 1; }; \
	$(MAKE) --no-print-directory FE8_ITEM_ID_CAP= $$C >/dev/null; \
	grep -q "ITEM_ID_ACTIVE_CONFIGURED_CAP 0xCD" $$H || { echo "FAIL: the stale 0xCE ACTIVE header did not self-heal to the default cap on the first plain build" >&2; exit 1; }; \
	grep -q "ITEM_ID_ACTIVE_RECORD_COUNT 206" $$H || { echo "FAIL: the self-healed ACTIVE header record count is not 206" >&2; exit 1; }; \
	"$(MODERN_CC)" $(MODERN_CFLAGS_NOCAP) -c "$$C" -o "$$OUT/items_healed.o"; \
	echo "OK: a single plain default build healed the out-of-band stale ACTIVE header and the generated table compiles clean -- no manual generated-data-check, no negative static assert"; \
	$(MAKE) --no-print-directory FE8_ITEM_ID_CAP= $$C >/dev/null; \
	grep -q "ITEM_ID_ACTIVE_RECORD_COUNT 206" $$H || { echo "FAIL: default-cap state was not restored" >&2; exit 1; }; \
	echo "PASS: expansion-modern-idspace-active-check"

expansion-modern-savefmt-check: expansion-modern-boot-preflight expansion-modern-rom
	"$(PYTHON)" "$(MODERN_SAVEFMT_CHECKS)" \
		--rom "$(MODERN_ROM)" \
		--config "$(MODERN_CONFIG)" \
		--fixture-dir "$(MODERN_SAVEFMT_FIXTURE_DIR)"
	@printf 'Modern ROM savefmt-check passed: %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'

# Combat runtime scenario (issue #13 closure). Boots the debug-only "Fast
# Boot: Ch4 Prep" launcher, traverses the Chapter 4 world map, and captures
# the chapter's own scripted FIGHT(CHARACTER_ARTUR, ...) (EventScr_Ch4_
# BeginningScene, src/events/ch4-eventscript.h) resolved by the real battle
# engine (Event3F_ScriptBattle): the target enemy gUnitArrayRed[0]'s curHP
# transitions 15->0 at the SCRIPT_BATTLE opcode (before the following KILL),
# then the unit is removed -- exact pre/post HP plus death, proven by fixed
# EWRAM unit probes, never framebuffer/timing. Debug-only: depends on the
# debug-only launcher (compiled out of release). Blank-SRAM boot, no fixture.
# See reports/gba_playtest_issue13_closure.md "Combat".
MODERN_COMBAT_SCENARIO := tools/gba-playtest/scenarios/combat.json
MODERN_COMBAT_FINGERPRINT := tools/gba-playtest/fingerprints/combat-modern-debug.json

ifeq ($(MODERN_CONFIG),debug)
expansion-modern-combat-check: expansion-modern-boot-preflight expansion-modern-rom
	@if [ ! -f "$(MODERN_COMBAT_SCENARIO)" ] || \
		[ ! -f "$(MODERN_COMBAT_FINGERPRINT)" ]; then \
		printf '%s\n' "error: missing combat scenario or fingerprint" >&2; \
		printf '  scenario:    %s\n' "$(MODERN_COMBAT_SCENARIO)" >&2; \
		printf '  fingerprint: %s\n' "$(MODERN_COMBAT_FINGERPRINT)" >&2; \
		exit 1; \
	fi
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_COMBAT_SCENARIO)" \
		--expected "$(MODERN_COMBAT_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM combat-check passed (Ch4 scripted FIGHT enemy HP 15->0 + death): %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'
else
expansion-modern-combat-check:
	@printf 'Modern ROM combat-check skipped: the Ch4 scripted-FIGHT combat scenario boots via the debug-only Fast Boot launcher (compiled out for config=%s); a debug-launcher scenario is legitimately debug-only, and the release runtime matrix does not include a separate combat scenario -- see reports/gba_playtest_issue13_closure.md\n' \
		'$(MODERN_CONFIG)'
endif

# Issue #6 starter-foundation runtime gate. The positive scenarios need a ROM
# built with the starter features ON, so this gate builds ONE dedicated
# starter-foundation profile ROM per (config, abi) -- all EXPANSION_MECHANICS_*
# and EXPANSION_DANGER_OVERLAY_MENU on -- into its OWN build root, so it never
# overwrites the default flags-off baseline ROM the linker/budget gates check.
# That single profile ROM is then reused by every positive scenario below,
# while each default-disabled negative control runs against the ordinary
# MODERN_ROM: same route, opposite semantic probe outcomes. Reuses the issue
# #13 gba-playtest harness (no new framework).
MODERN_STARTER_PROFILE_ROOT := build/expansion-modern-starter
MODERN_STARTER_PROFILE_ROM := $(MODERN_STARTER_PROFILE_ROOT)/$(MODERN_CONFIG)/$(MODERN_ABI)/fireemblem8.gba

# Mechanics-hook scenarios. The debug pair navigates Chapter 4 through the
# debug-only Fast Boot launcher (issue #13's proven combat route), so it is
# legitimately debug-only. The release pair instead uses the ORDINARY
# clean-boot Normal-difficulty route shared with the QoL scenarios: the
# Prologue's opening event contains a real scripted bout, so
# ComputeBattleUnitStats() genuinely runs with no launcher, no debug tools and
# no save fixture.
MODERN_STARTER_HOOK_SCENARIO := tools/gba-playtest/scenarios/starter-hook-modern-$(MODERN_CONFIG).json
MODERN_STARTER_HOOK_FINGERPRINT := tools/gba-playtest/fingerprints/starter-hook-modern-$(MODERN_CONFIG).json
MODERN_STARTER_HOOK_NEG_SCENARIO := tools/gba-playtest/scenarios/starter-hook-negative-modern-$(MODERN_CONFIG).json
MODERN_STARTER_HOOK_NEG_FINGERPRINT := tools/gba-playtest/fingerprints/starter-hook-negative-modern-$(MODERN_CONFIG).json
MODERN_STARTER_HOOK_CLEAN_SCENARIO := tools/gba-playtest/scenarios/starter-hook-clean-modern-$(MODERN_CONFIG).json
MODERN_STARTER_HOOK_CLEAN_FINGERPRINT := tools/gba-playtest/fingerprints/starter-hook-clean-modern-$(MODERN_CONFIG).json
MODERN_STARTER_HOOK_CLEAN_NEG_SCENARIO := tools/gba-playtest/scenarios/starter-hook-clean-negative-modern-$(MODERN_CONFIG).json
MODERN_STARTER_HOOK_CLEAN_NEG_FINGERPRINT := tools/gba-playtest/fingerprints/starter-hook-clean-negative-modern-$(MODERN_CONFIG).json

# Player QoL danger/range overlay scenarios. Both configs use the same
# ordinary clean-boot Normal-difficulty route to the real Prologue map.
MODERN_STARTER_QOL_SCENARIO := tools/gba-playtest/scenarios/starter-danger-overlay-modern-$(MODERN_CONFIG).json
MODERN_STARTER_QOL_FINGERPRINT := tools/gba-playtest/fingerprints/starter-danger-overlay-modern-$(MODERN_CONFIG).json
MODERN_STARTER_QOL_NEG_SCENARIO := tools/gba-playtest/scenarios/starter-danger-overlay-negative-modern-$(MODERN_CONFIG).json
MODERN_STARTER_QOL_NEG_FINGERPRINT := tools/gba-playtest/fingerprints/starter-danger-overlay-negative-modern-$(MODERN_CONFIG).json

expansion-modern-starter-profile-rom:
	$(MAKE) expansion-modern-rom \
		MODERN_CONFIG=$(MODERN_CONFIG) MODERN_ABI=$(MODERN_ABI) \
		MODERN_BUILD_ROOT=$(MODERN_STARTER_PROFILE_ROOT) \
		EXPANSION_MECHANICS_HOOKS=1 EXPANSION_MECHANICS_SAMPLE=1 \
		EXPANSION_DANGER_OVERLAY_MENU=1

MODERN_STARTER_PROFILE_ELF := $(MODERN_STARTER_PROFILE_ROOT)/$(MODERN_CONFIG)/$(MODERN_ABI)/fireemblem8.elf

# sizeof(struct ItemData) (include/bmitem.h). Used only to turn the linked
# gItemData symbol size into a record count for the negative below; a future
# struct-layout change fails that check loudly instead of silently.
MODERN_ITEM_DATA_RECORD_BYTES := 36

# Issue #6 content-DISABLED artifact negative, run against the SAME starter
# profile ROM/ELF the scenarios above already built (no extra ROM build, no
# second harness). The starter profile is the strongest possible negative:
# every other issue #6 flag is ON (hooks, sample, overlay) and the item cap is
# the vanilla default, so anything it still lacks is attributable to
# EXPANSION_STARTER_CONTENT=0 alone.
#
# It asserts three semantic facts a scenario cannot see:
#   1. the content mechanic's callback is not even compiled in, so it cannot
#      have been registered -- which is what the scenarios' registerOkCount=1
#      (sample only, versus 2 in the content profile) means at the artifact
#      level;
#   2. the content name accessor -- the only production seam that can read
#      authored content text -- is absent, so src/bmitem.c's GetItemName() is
#      the vanilla one; and
#   3. the authored display text itself appears NOWHERE in the ROM image, and
#      gItemData is still the 206-record vanilla table.
# The authored string is read from the authoring source of truth, so renaming
# the content item cannot make this negative vacuous.
define modern_starter_content_disabled_negative
	@set -eu; \
	elf='$(MODERN_STARTER_PROFILE_ELF)'; \
	rom='$(MODERN_STARTER_PROFILE_ROM)'; \
	for symbol in ExpansionStarterContentCharmEvade ExpansionStarterContentItemName; do \
		if "$(MODERN_NM)" "$$elf" | grep -q " $$symbol$$"; then \
			printf 'error: %s is linked into the content-DISABLED starter profile ROM\n' "$$symbol" >&2; \
			exit 1; \
		fi; \
	done; \
	name=$$("$(PYTHON)" -c "import json; print(json.load(open('src/data/items_expansion.json'))['items'][0]['authoringName'])"); \
	if LC_ALL=C grep -a -q -F "$$name" "$$rom"; then \
		printf 'error: authored content text "%s" is present in the content-DISABLED ROM\n' "$$name" >&2; \
		exit 1; \
	fi; \
	size=$$("$(MODERN_NM)" -S "$$elf" | awk '$$4 == "gItemData" { print $$2 }'); \
	if [ -z "$$size" ]; then \
		printf 'error: gItemData has no linked size in %s\n' "$$elf" >&2; \
		exit 1; \
	fi; \
	expected=$$("$(PYTHON)" -c "from scripts.generated_data.items import schema; print(len(schema.load_records('src/data/items.json', item_cap=0xCD)) * $(MODERN_ITEM_DATA_RECORD_BYTES))"); \
	if [ $$(( 0x$$size )) -ne "$$expected" ]; then \
		printf 'error: content-disabled gItemData is 0x%s bytes, expected %s (the vanilla-cap table)\n' "$$size" "$$expected" >&2; \
		exit 1; \
	fi; \
	printf 'Content-disabled artifact negative passed (no content callback/accessor symbol, no authored text in the ROM, vanilla-cap gItemData): config=%s abi=%s\n' \
		'$(MODERN_CONFIG)' '$(MODERN_ABI)'
endef

# Fail loudly rather than silently skipping when a scenario/fingerprint pair
# named by the matrix above is missing.
define modern_starter_require_pair
	@if [ ! -f "$(1)" ] || [ ! -f "$(2)" ]; then \
		printf '%s\n' "error: missing starter scenario or fingerprint" >&2; \
		printf '  scenario:    %s\n' "$(1)" >&2; \
		printf '  fingerprint: %s\n' "$(2)" >&2; \
		exit 1; \
	fi
endef

ifeq ($(MODERN_CONFIG),debug)
expansion-modern-starter-hook-check: expansion-modern-boot-preflight \
		expansion-modern-rom expansion-modern-starter-profile-rom
	$(call modern_starter_require_pair,$(MODERN_STARTER_HOOK_SCENARIO),$(MODERN_STARTER_HOOK_FINGERPRINT))
	$(call modern_starter_require_pair,$(MODERN_STARTER_HOOK_NEG_SCENARIO),$(MODERN_STARTER_HOOK_NEG_FINGERPRINT))
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_STARTER_PROFILE_ROM)" \
		--scenario "$(MODERN_STARTER_HOOK_SCENARIO)" \
		--expected "$(MODERN_STARTER_HOOK_FINGERPRINT)" \
		--policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_STARTER_HOOK_NEG_SCENARIO)" \
		--expected "$(MODERN_STARTER_HOOK_NEG_FINGERPRINT)" \
		--policy behavior
	$(modern_starter_content_disabled_negative)
	@printf 'Modern ROM starter-hook-check passed (positive registerOk=1/apply=2/sampleTrigger=2 on profile ROM; negative all-zero on default ROM; content-disabled artifact negative): config=%s abi=%s\n' \
		'$(MODERN_CONFIG)' '$(MODERN_ABI)'
else
expansion-modern-starter-hook-check: expansion-modern-boot-preflight \
		expansion-modern-rom expansion-modern-starter-profile-rom
	$(call modern_starter_require_pair,$(MODERN_STARTER_HOOK_CLEAN_SCENARIO),$(MODERN_STARTER_HOOK_CLEAN_FINGERPRINT))
	$(call modern_starter_require_pair,$(MODERN_STARTER_HOOK_CLEAN_NEG_SCENARIO),$(MODERN_STARTER_HOOK_CLEAN_NEG_FINGERPRINT))
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_STARTER_PROFILE_ROM)" \
		--scenario "$(MODERN_STARTER_HOOK_CLEAN_SCENARIO)" \
		--expected "$(MODERN_STARTER_HOOK_CLEAN_FINGERPRINT)" \
		--policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_STARTER_HOOK_CLEAN_NEG_SCENARIO)" \
		--expected "$(MODERN_STARTER_HOOK_CLEAN_NEG_FINGERPRINT)" \
		--policy behavior
	$(modern_starter_content_disabled_negative)
	@printf 'Modern ROM starter-hook-check passed (clean-boot Prologue bout: positive registerOk=1/apply=2/sampleTrigger=2/delta=+1 on profile ROM; negative all-zero on default ROM, same resolved battle; content-disabled artifact negative): config=%s abi=%s\n' \
		'$(MODERN_CONFIG)' '$(MODERN_ABI)'
endif

# Player QoL danger/range overlay runtime gate. Runs in BOTH configs against
# the same ordinary clean-boot route (no launcher, no debug tools, no save
# fixture): the positive proves menuSelect/dangerDisplay 0->1->2, an exact
# 39-tile danger range, rangeGraphicsActive toggling 1->0 and
# cancelReturnCount 0->1->2 on a real, interactive Prologue map; the negative
# proves the always-linked probe stays all-zero on the default flags-off ROM
# reached by the same route.
expansion-modern-starter-qol-check: expansion-modern-boot-preflight \
		expansion-modern-rom expansion-modern-starter-profile-rom
	$(call modern_starter_require_pair,$(MODERN_STARTER_QOL_SCENARIO),$(MODERN_STARTER_QOL_FINGERPRINT))
	$(call modern_starter_require_pair,$(MODERN_STARTER_QOL_NEG_SCENARIO),$(MODERN_STARTER_QOL_NEG_FINGERPRINT))
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_STARTER_PROFILE_ROM)" \
		--scenario "$(MODERN_STARTER_QOL_SCENARIO)" \
		--expected "$(MODERN_STARTER_QOL_FINGERPRINT)" \
		--policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_STARTER_QOL_NEG_SCENARIO)" \
		--expected "$(MODERN_STARTER_QOL_NEG_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM starter-qol-check passed (positive menuSelect/display 0->1->2, 39 danger tiles, cancel 0->1->2 on profile ROM; negative all-zero on default ROM): config=%s abi=%s\n' \
		'$(MODERN_CONFIG)' '$(MODERN_ABI)'

# One entry point for the whole issue #6 starter runtime matrix. Both member
# checks depend on the same expansion-modern-starter-profile-rom, so a single
# make invocation builds that profile ROM once and reuses it for every
# scenario.
expansion-modern-starter-runtime-check: expansion-modern-starter-hook-check \
		expansion-modern-starter-qol-check
	@printf 'Modern ROM starter runtime matrix passed (mechanics hook + player QoL overlay, positive and default-disabled negative): config=%s abi=%s\n' \
		'$(MODERN_CONFIG)' '$(MODERN_ABI)'

# Normal save/load runtime scenario (issue #13 closure). Reuses new-game.json's
# clean-boot SaveMenu New Game -> slot 0 write, then a real A+B+SELECT+START
# soft reset (RAM reinitialized), then the top-level SaveMenu RESTART item ->
# PostSaveMenuHandler -> ReadGameSave(0) (src/savemenu.c) -- a genuine normal
# game-save LOAD distinct from Suspend/ReadSuspendSave. Proven by the
# playthroughIdentifier/chapterModeIndex discriminants going 1 (created) -> 0
# (soft-reset cleared) -> 1 (loaded) plus before/after whole-SRAM hashes.
# Debug-only: its soft-reset input timing is debug-calibrated, exactly as
# savesuspend-resume-modern-debug.json is; release normal-save coverage is
# provided by expansion-modern-newgame-check (the WriteGameSave write path)
# and expansion-modern-savefmt-check (load classification). Needs the same
# deterministic pre-seeded CURRENT-format SRAM fixture as new-game.json.
MODERN_SAVELOAD_SCENARIO := tools/gba-playtest/scenarios/save-load.json
MODERN_SAVELOAD_FINGERPRINT := tools/gba-playtest/fingerprints/save-load-modern-debug.json

ifeq ($(MODERN_CONFIG),debug)
expansion-modern-saveload-check: expansion-modern-boot-preflight expansion-modern-rom \
		$(MODERN_DEBUGTOOLS_SRAM_FIXTURE)
	@if [ ! -f "$(MODERN_SAVELOAD_SCENARIO)" ] || \
		[ ! -f "$(MODERN_SAVELOAD_FINGERPRINT)" ]; then \
		printf '%s\n' "error: missing save-load scenario or fingerprint" >&2; \
		printf '  scenario:    %s\n' "$(MODERN_SAVELOAD_SCENARIO)" >&2; \
		printf '  fingerprint: %s\n' "$(MODERN_SAVELOAD_FINGERPRINT)" >&2; \
		exit 1; \
	fi
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify \
		--rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_SAVELOAD_SCENARIO)" \
		--sram-image "$(MODERN_DEBUGTOOLS_SRAM_FIXTURE)" \
		--expected "$(MODERN_SAVELOAD_FINGERPRINT)" \
		--policy behavior
	@printf 'Modern ROM saveload-check passed (SaveMenu RESTART -> ReadGameSave(0)): %s (config=%s abi=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)'
else
expansion-modern-saveload-check:
	@printf 'Modern ROM saveload-check skipped: the SaveMenu RESTART -> ReadGameSave(0) normal-load scenario uses a debug-calibrated soft-reset input sequence (as savesuspend-resume-modern-debug.json does) for config=%s; release normal-save coverage is provided by expansion-modern-newgame-check (write) and expansion-modern-savefmt-check (load classification) -- see reports/gba_playtest_issue13_closure.md\n' \
		'$(MODERN_CONFIG)'
endif

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
		--check --validate-elf \
		--require-positive-headroom ewram \
		--require-positive-headroom iwram

# Localization-specific runtime budget rollup (issue #18 sprint 4): combines
# the real per-region headroom already computed above (real floating_end ->
# next-pinned-region free_bytes from THIS build's own .map, never a hardcoded
# 2820/3508-style constant), the source-catalog budget (build-config-
# independent string/index/glyph counts from scripts/localization/generate
# .build_budget), and real `nm`-derived EWRAM/ROM symbol sizes for the
# concrete locale-resolver + language-menu-probe module symbols. See
# scripts/linker_report/localization_budget.py's module docstring for the
# exact provenance of every field. `--check` only fails on a real map-
# reported region overflow -- it asserts no magic byte thresholds.
MODERN_LOCALIZATION_BUDGET_REPORT ?= reports/linker-budget/modern-localization-$(MODERN_CONFIG).json
MODERN_LOCALIZATION_BUDGET_SCRIPT := scripts/linker_report/localization_budget.py

expansion-modern-localization-budget: expansion-modern-elf $(MODERN_LOCALIZATION_BUDGET_JSON)
	NM="$(MODERN_NM)" "$(PYTHON)" "$(MODERN_LOCALIZATION_BUDGET_SCRIPT)" \
		--map "$(MODERN_MAP)" \
		--elf "$(MODERN_ELF)" \
		--localization-budget "$(MODERN_LOCALIZATION_BUDGET_JSON)" \
		--output "$(MODERN_LOCALIZATION_BUDGET_REPORT)"

expansion-modern-localization-budget-check: expansion-modern-elf $(MODERN_LOCALIZATION_BUDGET_JSON)
	NM="$(MODERN_NM)" "$(PYTHON)" "$(MODERN_LOCALIZATION_BUDGET_SCRIPT)" \
		--map "$(MODERN_MAP)" \
		--elf "$(MODERN_ELF)" \
		--localization-budget "$(MODERN_LOCALIZATION_BUDGET_JSON)" \
		--output "$(MODERN_LOCALIZATION_BUDGET_REPORT)" \
		--check

MODERN_SHIFTCHECK_DIR := $(MODERN_OUTPUT_DIR)/shiftcheck
MODERN_RELOCS_ELF := $(MODERN_SHIFTCHECK_DIR)/fireemblem8.relocs.elf
MODERN_OVERLAY_REPORT := $(MODERN_SHIFTCHECK_DIR)/overlay-audit.json
MODERN_RELINK_SCRIPT := scripts/shiftcheck/modern_emit_relocs.sh
MODERN_OVERLAY_SCRIPT := scripts/linker_report/overlay_audit.py
MODERN_SHIFTED_SCRIPT := scripts/shiftcheck/modern_shifted_boot.sh
MODERN_SHIFT_AMOUNT ?= 0x40000
MODERN_SHIFTED_OUTDIR := $(MODERN_SHIFTCHECK_DIR)/shift-$(MODERN_SHIFT_AMOUNT)
# Sprint 6 (issue #18 gate-order race diagnosis): expansion-modern-shifted-check
# and expansion-modern-localization-runtime-shifted-check are undeclared-order
# SIBLING prerequisites of expansion-modern-linker-check (see that target's own
# prerequisite list below) -- under `make -jN` with N>1 (exactly what
# `python3 -m scripts.upstream_port verify --jobs N` passes through per gate),
# GNU Make is free to run sibling prerequisites concurrently. Both targets
# used to pass the SAME literal $(MODERN_SHIFTED_OUTDIR) as SHIFTCHECK_OUTDIR
# to scripts/shiftcheck/modern_shifted_boot.sh, which links straight to a
# fixed "$OUTDIR/shifted.elf" path with no temp-file-plus-rename step. Two
# concurrent invocations therefore raced two `arm-none-eabi-ld` processes
# writing the same shifted.elf, producing a torn ELF and an intermittent
# "nm failed ... file format not recognized" failure inside
# expansion-modern-linker-check (reproduced locally under -j16 while
# investigating the reported intermittent modern-itemexpansion-check-debug
# gItemExpansionProbe failure -- see
# reports/itemexpansion_gate_order_race_diagnosis.md). This is the exact
# same *class* of bug as commit 92ed1b6b (a shared, non-isolated output path
# torn by concurrent sibling recipes), just on a different pair of targets --
# so it is fixed the same way that precedent used elsewhere in this file:
# give each sibling its own, non-shared output directory, instead of trying
# to serialize two otherwise-independent checks via an artificial ordering
# edge (which would only re-hide the same class of bug behind a fragile,
# easy-to-lose dependency the next time either target is touched).
MODERN_SHIFTED_OUTDIR_BOOT := $(MODERN_SHIFTED_OUTDIR)/boot-check
MODERN_SHIFTED_OUTDIR_LOCALE := $(MODERN_SHIFTED_OUTDIR)/localization-runtime-check

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
	SHIFTCHECK_OUTDIR="$(MODERN_SHIFTED_OUTDIR_BOOT)" \
	SHIFTCHECK_OBJECTS_LST="$(MODERN_ELF_OBJECTS_LST)" \
	SHIFTCHECK_BANIM_SYM="$(MODERN_ELF_BANIM_SYM)" \
	SHIFTCHECK_LDSCRIPT="$(MODERN_CLEAN_LDSCRIPT)" \
	SHIFTCHECK_BASE_ELF="$(MODERN_ELF)" \
	SHIFTCHECK_ROM_SIZE_BYTES="$(MODERN_ROM_SIZE_BYTES)" \
	SHIFTCHECK_ROM_SIZE="$(MODERN_ROM_SIZE)" \
	SHIFTCHECK_PAD_TO="$(MODERN_PAD_TO)" \
	SHIFTCHECK_TITLE_EXPECTED="$(MODERN_TITLE_FINGERPRINT)" \
	"$(MODERN_SHIFTED_SCRIPT)" "$(MODERN_SHIFT_AMOUNT)"


# --- Issue #18 sprint 4: semantic locale runtime scenarios -----------------
# Real libmGBA captures proving locale-selection/persistence/settings/
# corrupt-prefs-safety milestones are actually reached at runtime -- never
# just host-structure or frame-replay self-assertions. Every scenario here
# was captured against a real built ROM + a byte-exact synthetic SRAM
# fixture (tools/gba-playtest/tests/locale_prefs_fixture.py /
# sram_fixture.py), verified via gba_playtest.py's own inline-expectation
# and fingerprint-equality checks (never hand-written fingerprint JSON).
MODERN_LOCALE_SCEN := tools/gba-playtest/scenarios
MODERN_LOCALE_FP := tools/gba-playtest/fingerprints
MODERN_LOCALE_FIXTURE_DIR := $(MODERN_OUTPUT_DIR)/locale-fixtures
MODERN_LOCALE_PREFS_FIXTURE_PY := tools/gba-playtest/tests/locale_prefs_fixture.py
MODERN_LOCALE_SRAM_FIXTURE_PY := tools/gba-playtest/tests/sram_fixture.py
MODERN_SAVE_FORMAT_TOOL_PY := scripts/modernize/save_format_tool.py
MODERN_EXPANSION_CONFIG_PY := scripts/modernize/expansion_config.py

# Issue #18 sprint 6 verifier-blocker fix: every fixture below is
# regenerated from config.mk (via save_format_tool.py's
# build_current_expansion_save_meta()/resolve_*() helpers) at *this*
# invocation's own live state, never a stale cached .sav left over from a
# previous config.mk/generator-script revision -- these real prerequisites
# (rather than none) are what make that true instead of merely asserted:
# without them, a change to config.mk or either generator script left an
# already-built build/ tree's *.sav byte-for-byte stale, silently
# reproducing whatever fixture the *previous* revision would have built.
# (The remaining source of non-determinism -- ExpansionSaveMeta.
# buildCommitShort's dependence on live `git rev-parse HEAD` -- is fixed
# directly in locale_prefs_fixture.py itself: see its own docstring and
# _freeze_diagnostic_build_commit().)
MODERN_LOCALE_FIXTURE_DEPS := \
	$(MODERN_LOCALE_PREFS_FIXTURE_PY) \
	$(MODERN_LOCALE_SRAM_FIXTURE_PY) \
	$(MODERN_SAVE_FORMAT_TOOL_PY) \
	$(MODERN_EXPANSION_CONFIG_PY) \
	config.mk

$(MODERN_LOCALE_FIXTURE_DIR)/blank.sav: $(MODERN_LOCALE_FIXTURE_DEPS)
	@mkdir -p "$(@D)"
	"$(PYTHON)" "$(MODERN_LOCALE_SRAM_FIXTURE_PY)" write-state SAVE_COMPAT_EMPTY "$@"

$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav: $(MODERN_LOCALE_FIXTURE_DEPS)
	@mkdir -p "$(@D)"
	"$(PYTHON)" "$(MODERN_LOCALE_PREFS_FIXTURE_PY)" EXPANSION_USER_PREFS_UNSET "$@"

$(MODERN_LOCALE_FIXTURE_DIR)/corrupt.sav: $(MODERN_LOCALE_FIXTURE_DEPS)
	@mkdir -p "$(@D)"
	"$(PYTHON)" "$(MODERN_LOCALE_PREFS_FIXTURE_PY)" EXPANSION_USER_PREFS_CORRUPT "$@"

$(MODERN_LOCALE_FIXTURE_DIR)/unknown.sav: $(MODERN_LOCALE_FIXTURE_DEPS)
	@mkdir -p "$(@D)"
	"$(PYTHON)" "$(MODERN_LOCALE_PREFS_FIXTURE_PY)" EXPANSION_USER_PREFS_UNKNOWN_LOCALE "$@"

$(MODERN_LOCALE_FIXTURE_DIR)/disabled_on_default.sav: $(MODERN_LOCALE_FIXTURE_DEPS)
	@mkdir -p "$(@D)"
	"$(PYTHON)" "$(MODERN_LOCALE_PREFS_FIXTURE_PY)" EXPANSION_USER_PREFS_DISABLED_LOCALE "$@" \
		--disabled-locale-id 7

# Issue #18 sprint 7: a second disabled-locale fixture for the multi-locale
# (en, qps-ploc) repair-matrix scenarios below. disabled_on_default.sav
# above uses localeId=7 (qps-ploc) because the *single*-locale default
# build only enables en, making qps-ploc the supported-but-not-enabled id
# for THAT build; the multi-locale build enables both en and qps-ploc, so
# qps-ploc is no longer disabled there -- this fixture instead uses
# localeId=1 (EXPANSION_LOCALE_JA, include/expansion_locale.h), a real,
# in-range, ExpansionLocale_IsSupported()-true id that is genuinely not
# enabled by EXPANSION_ENABLED_LOCALES=en,qps-ploc.
$(MODERN_LOCALE_FIXTURE_DIR)/disabled_on_multi.sav: $(MODERN_LOCALE_FIXTURE_DEPS)
	@mkdir -p "$(@D)"
	"$(PYTHON)" "$(MODERN_LOCALE_PREFS_FIXTURE_PY)" EXPANSION_USER_PREFS_DISABLED_LOCALE "$@" \
		--disabled-locale-id 1

# Issue #18 sprint 6 (runtime blocker fix): a real "already
# first-start-selected + persisted" fixture -- state VALID, locale en --
# needed by locale-settings-real-navigation-multi-modern-debug once blank
# SRAM on a multi-locale build correctly shows the first-start selector
# (see the blank-sram-selector-multi scenario above): that settings-
# submenu-reachability scenario's own real debugtools-hotkey boot recipe
# assumes it starts from an already-past-first-boot state (its point is
# Options -> Configuration -> Language row reachability, not first-start
# prompt reachability, which the blank-sram-selector-multi scenario
# already covers on its own), so it must no longer rely on blank SRAM's
# now-correctly-different (selector-shown) behavior to reach that state.
$(MODERN_LOCALE_FIXTURE_DIR)/valid_explicit_en.sav: $(MODERN_LOCALE_FIXTURE_DEPS)
	@mkdir -p "$(@D)"
	"$(PYTHON)" "$(MODERN_LOCALE_PREFS_FIXTURE_PY)" valid-explicit "$@" --locale-id 0

# 1. Blank SRAM + single-locale default build: auto-stamp path never shows
#    the selector; unset (never-saved) prefs on that same build auto-selects
#    the sole enabled locale with no visible selector either.
expansion-modern-localization-runtime-debug-check: expansion-modern-boot-preflight \
		expansion-modern-rom \
		$(MODERN_LOCALE_FIXTURE_DIR)/blank.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav
ifeq ($(MODERN_CONFIG),debug)
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-blank-sram-no-selector-default-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-blank-sram-no-selector-default-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/blank.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-auto-select-single-locale-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-auto-select-single-locale-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav" --policy behavior
	@printf 'Modern ROM localization-runtime debug-check passed (blank-sram + auto-select): %s\n' "$(MODERN_ROM)"
else
	@printf 'Modern ROM localization-runtime debug-check skipped for config=%s (debug-only boot-timing calibration)\n' '$(MODERN_CONFIG)'
endif

# 2. Same milestones, release build (different EWRAM probe-symbol layout,
#    same SKIP_HS boot-timing recipe -- both captured for real, separately).
expansion-modern-localization-runtime-release-check: expansion-modern-boot-preflight \
		expansion-modern-rom \
		$(MODERN_LOCALE_FIXTURE_DIR)/blank.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/valid_explicit_en.sav
ifeq ($(MODERN_CONFIG),release)
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-blank-sram-no-selector-default-modern-release.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-blank-sram-no-selector-default-modern-release.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/blank.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-auto-select-single-locale-modern-release.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-auto-select-single-locale-modern-release.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-settings-inline-single-modern-release.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-settings-inline-single-modern-release.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/valid_explicit_en.sav" --policy behavior
	@printf 'Modern ROM localization-runtime release-check passed (blank-sram + auto-select + inline settings): %s\n' "$(MODERN_ROM)"
else
	@printf 'Modern ROM localization-runtime release-check skipped for config=%s (release-only)\n' '$(MODERN_CONFIG)'
endif

# 3. Multi-locale (en + qps-ploc) build: issue #18 sprint 6 fixed a runtime
#    blocker where blank SRAM never showed the selector here (silently
#    auto-stamping a syntactically VALID ExpansionUserPrefs record via
#    BuildCurrentExpansionSaveMeta() regardless of enabled-locale count --
#    see src/bmsave-lib.c and locale-blank-sram-selector-multi-modern-
#    {debug,release}.json, which SUPERSEDE the pre-fix locale-blank-sram-
#    no-selector-multi-modern-{debug,release} pair that encoded that bug
#    as 'expected' and have been deleted); blank SRAM now correctly shows
#    the selector (active=1, needsPreferenceRepair=1) exactly like real
#    unset prefs does, and DOWN+A picks qps-ploc there -- proving the
#    EWRAM SetCurrent/GetCurrent round-trip fixed in an earlier sprint
#    actually works.
#    Uses its own build root + EXPANSION_ENABLED_LOCALES override so it
#    never disturbs the default single-locale $(MODERN_ROM) above.
#
#    Issue #18 sprint 5: derived from $(MODERN_BUILD_ROOT) (a "-multi"
#    sibling) rather than a hardcoded "build/expansion-modern-multi"
#    literal, so a caller that overrides MODERN_BUILD_ROOT (e.g. an
#    isolated/hermetic regression test -- see
#    scripts/modernize/tests/test_modern_localization_header_bootstrap.py's
#    ModernLocalizationMultiCheckColdCleanTests) gets its own equally
#    isolated multi-locale build root instead of always falling through to
#    the real repository-tracked default path regardless of the caller's
#    own override. The default value (MODERN_BUILD_ROOT's own default,
#    "build/expansion-modern") still resolves to exactly
#    "build/expansion-modern-multi" as before, so no real invocation's
#    on-disk output path actually changes.
MODERN_LOCALE_MULTI_BUILD_ROOT := $(MODERN_BUILD_ROOT)-multi
MODERN_LOCALE_MULTI_ROM := $(MODERN_LOCALE_MULTI_BUILD_ROOT)/$(MODERN_CONFIG)/$(MODERN_ABI)/fireemblem8.gba

expansion-modern-localization-runtime-multi-check: expansion-modern-boot-preflight \
		$(MODERN_LOCALE_FIXTURE_DIR)/blank.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/corrupt.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/unknown.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/disabled_on_multi.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/valid_explicit_en.sav
	+$(MAKE) expansion-modern-rom MODERN_CONFIG=$(MODERN_CONFIG) \
		MODERN_BUILD_ROOT=$(MODERN_LOCALE_MULTI_BUILD_ROOT) \
		EXPANSION_ENABLED_LOCALES=en,qps-ploc EXPANSION_PSEUDO_LOCALE=1
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_MULTI_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-blank-sram-selector-multi-modern-$(MODERN_CONFIG).json" \
		--expected "$(MODERN_LOCALE_FP)/locale-blank-sram-selector-multi-modern-$(MODERN_CONFIG).json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/blank.sav" --policy behavior
	# Issue #18 sprint 7: real multi-locale prompt/choose-default REPAIR
	# matrix (4 ExpansionUserPrefs sub-states that require a re-prompt x
	# both configs = 8 real scenarios, mandatory for every config -- never
	# gated to debug-only, unlike the single-locale AUTO_SELECT-collapsed
	# no-wipe checks in expansion-modern-localization-runtime-prefs-check
	# below, which this section does not replace/skip). Each scenario
	# shows the real blocking selector (never AUTO_SELECT -- this build
	# enables 2 locales), navigates it, explicitly confirms the English
	# row, proves the whole-SRAM-minus-prefs-record hash is unchanged, and
	# proves persistence + re-prompt suppression across a real
	# A+B+SELECT+START soft reset. See tools/gba-playtest/scenarios/
	# locale-repair-*-multi-modern-*.json and docs/localization.md.
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_MULTI_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-repair-unset-multi-modern-$(MODERN_CONFIG).json" \
		--expected "$(MODERN_LOCALE_FP)/locale-repair-unset-multi-modern-$(MODERN_CONFIG).json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_MULTI_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-repair-corrupt-multi-modern-$(MODERN_CONFIG).json" \
		--expected "$(MODERN_LOCALE_FP)/locale-repair-corrupt-multi-modern-$(MODERN_CONFIG).json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/corrupt.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_MULTI_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-repair-unknown-multi-modern-$(MODERN_CONFIG).json" \
		--expected "$(MODERN_LOCALE_FP)/locale-repair-unknown-multi-modern-$(MODERN_CONFIG).json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/unknown.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_MULTI_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-repair-disabled-multi-modern-$(MODERN_CONFIG).json" \
		--expected "$(MODERN_LOCALE_FP)/locale-repair-disabled-multi-modern-$(MODERN_CONFIG).json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/disabled_on_multi.sav" --policy behavior
ifeq ($(MODERN_CONFIG),debug)
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_MULTI_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-selector-multi-switch-qps-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-selector-multi-switch-qps-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_MULTI_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-settings-real-navigation-multi-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-settings-real-navigation-multi-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/valid_explicit_en.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_MULTI_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-softreset-persistence-multi-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-softreset-persistence-multi-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav" --policy behavior
endif
	@printf 'Modern ROM localization-runtime multi-check passed (config=%s): %s\n' '$(MODERN_CONFIG)' "$(MODERN_LOCALE_MULTI_ROM)"

# 4. Production CJK matrix: all four named profiles first pass the exact
#    product map/ELF headroom gate above. The trilingual profile then runs
#    captured first-start Japanese/Chinese choices, inline Config switching
#    across all three real locales, and Simplified Chinese persistence across
#    a real soft reset.
MODERN_LOCALE_CJK_ROM := \
	$(MODERN_LOCALE_PROFILE_EN_JA_ZH_HANS_ROOT)/$(MODERN_CONFIG)/$(MODERN_ABI)/fireemblem8.gba

expansion-modern-localization-runtime-cjk-check: expansion-modern-boot-preflight \
		expansion-modern-localization-profile-headroom-check \
		$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/valid_explicit_en.sav
ifeq ($(MODERN_CONFIG),debug)
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_CJK_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-cjk-first-start-ja-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-cjk-first-start-ja-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_CJK_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-cjk-first-start-zh-hans-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-cjk-first-start-zh-hans-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_CJK_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-cjk-settings-inline-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-cjk-settings-inline-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/valid_explicit_en.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_LOCALE_CJK_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-cjk-softreset-persistence-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-cjk-softreset-persistence-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav" --policy behavior
	@printf 'Modern ROM localization-runtime CJK check passed: %s\n' "$(MODERN_LOCALE_CJK_ROM)"
else
	@printf 'Modern ROM localization-runtime CJK check skipped for config=%s (debug fingerprints only)\n' '$(MODERN_CONFIG)'
endif

# 5. Corrupt/unknown-locale/disabled-locale ExpansionUserPrefs sub-states
#    all re-prompt (collapsing to AUTO_SELECT on this single-locale
#    default build, debug-only boot-timing calibration) and provably
#    never wipe SRAM outside (a) the 12-byte prefs record itself and (b)
#    the pre-existing, locale-unrelated vanilla SoundRoomSaveData struct
#    (include/bmsave.h) that ordinary boot-time bookkeeping legitimately
#    rewrites on every boot regardless of prefs state (see reports/
#    issue18_localization_closure.md). Issue #18 sprint 7: this single-
#    locale/AUTO_SELECT check is a real, honestly-named scenario in its
#    own right (a single-enabled-locale build genuinely collapses to
#    AUTO_SELECT -- that is not a gap), but it is NOT a substitute for the
#    real multi-locale PROMPT/choose-default repair matrix -- see the 8
#    locale-repair-*-multi-modern-{debug,release}.json scenarios wired
#    into expansion-modern-localization-runtime-multi-check above, which
#    close that previously-missing coverage for both configs.
expansion-modern-localization-runtime-prefs-check: expansion-modern-boot-preflight \
		expansion-modern-rom \
		$(MODERN_LOCALE_FIXTURE_DIR)/corrupt.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/unknown.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/disabled_on_default.sav
ifeq ($(MODERN_CONFIG),debug)
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-prefs-corrupt-no-wipe-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-prefs-corrupt-no-wipe-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/corrupt.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-prefs-unknown-locale-no-wipe-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-prefs-unknown-locale-no-wipe-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/unknown.sav" --policy behavior
	"$(PYTHON)" "$(MODERN_PLAYTEST)" verify --rom "$(MODERN_ROM)" \
		--scenario "$(MODERN_LOCALE_SCEN)/locale-prefs-disabled-locale-no-wipe-modern-debug.json" \
		--expected "$(MODERN_LOCALE_FP)/locale-prefs-disabled-locale-no-wipe-modern-debug.json" \
		--sram-image "$(MODERN_LOCALE_FIXTURE_DIR)/disabled_on_default.sav" --policy behavior
	@printf 'Modern ROM localization-runtime prefs-check passed (corrupt/unknown/disabled no-wipe): %s\n' "$(MODERN_ROM)"
else
	@printf 'Modern ROM localization-runtime prefs-check skipped for config=%s (debug-only boot-timing calibration)\n' '$(MODERN_CONFIG)'
endif

# 6. Locale prefs must not regress ordinary normal save/load and
#    suspend/resume behavior -- reruns the existing (unmodified) issue #13
#    save-path gates as-is; this is a regression check, not a new scenario.
expansion-modern-localization-runtime-save-check: expansion-modern-saveload-check \
		expansion-modern-savefmt-check
	@printf 'Modern ROM localization-runtime save-check passed (normal save/load + suspend/resume unaffected, config=%s)\n' '$(MODERN_CONFIG)'

# 7. Shifted ROM layout (P9-A __text_shift regression class): locale
#    resolver/selector probes must behave identically after the whole ROM
#    is relocated -- EWRAM probe addresses are unaffected by a ROM-only
#    text shift, so the exact same debug scenarios/fingerprints are reused
#    against the shifted ROM.
expansion-modern-localization-runtime-shifted-check: expansion-modern-boot-preflight \
		expansion-modern-rom \
		$(MODERN_LOCALE_FIXTURE_DIR)/blank.sav \
		$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav
ifeq ($(MODERN_CONFIG),debug)
	MODERN_CC="$(MODERN_CC)" MODERN_LD="$(MODERN_LD)" MODERN_OBJCOPY="$(MODERN_OBJCOPY)" \
	MODERN_NM="$(MODERN_NM)" MODERN_NEWLIB_LIB="$(MODERN_NEWLIB_LIB)" \
	SHIFTCHECK_OUTDIR="$(MODERN_SHIFTED_OUTDIR_LOCALE)" SHIFTCHECK_OBJECTS_LST="$(MODERN_ELF_OBJECTS_LST)" \
	SHIFTCHECK_BANIM_SYM="$(MODERN_ELF_BANIM_SYM)" SHIFTCHECK_LDSCRIPT="$(MODERN_CLEAN_LDSCRIPT)" \
	SHIFTCHECK_BASE_ELF="$(MODERN_ELF)" SHIFTCHECK_ROM_SIZE_BYTES="$(MODERN_ROM_SIZE_BYTES)" \
	SHIFTCHECK_ROM_SIZE="$(MODERN_ROM_SIZE)" SHIFTCHECK_PAD_TO="$(MODERN_PAD_TO)" \
	SHIFTCHECK_SRAM_IMAGE="$(MODERN_LOCALE_FIXTURE_DIR)/blank.sav" \
	SHIFTCHECK_SCENARIO="$(MODERN_LOCALE_SCEN)/locale-blank-sram-no-selector-default-modern-debug.json" \
	SHIFTCHECK_EXPECTED="$(MODERN_LOCALE_FP)/locale-blank-sram-no-selector-default-modern-debug.json" \
		"$(MODERN_SHIFTED_SCRIPT)" "$(MODERN_SHIFT_AMOUNT)"
	MODERN_CC="$(MODERN_CC)" MODERN_LD="$(MODERN_LD)" MODERN_OBJCOPY="$(MODERN_OBJCOPY)" \
	MODERN_NM="$(MODERN_NM)" MODERN_NEWLIB_LIB="$(MODERN_NEWLIB_LIB)" \
	SHIFTCHECK_OUTDIR="$(MODERN_SHIFTED_OUTDIR_LOCALE)" SHIFTCHECK_OBJECTS_LST="$(MODERN_ELF_OBJECTS_LST)" \
	SHIFTCHECK_BANIM_SYM="$(MODERN_ELF_BANIM_SYM)" SHIFTCHECK_LDSCRIPT="$(MODERN_CLEAN_LDSCRIPT)" \
	SHIFTCHECK_BASE_ELF="$(MODERN_ELF)" SHIFTCHECK_ROM_SIZE_BYTES="$(MODERN_ROM_SIZE_BYTES)" \
	SHIFTCHECK_ROM_SIZE="$(MODERN_ROM_SIZE)" SHIFTCHECK_PAD_TO="$(MODERN_PAD_TO)" \
	SHIFTCHECK_SRAM_IMAGE="$(MODERN_LOCALE_FIXTURE_DIR)/unset.sav" \
	SHIFTCHECK_SCENARIO="$(MODERN_LOCALE_SCEN)/locale-auto-select-single-locale-modern-debug.json" \
	SHIFTCHECK_EXPECTED="$(MODERN_LOCALE_FP)/locale-auto-select-single-locale-modern-debug.json" \
		"$(MODERN_SHIFTED_SCRIPT)" "$(MODERN_SHIFT_AMOUNT)"
	@printf 'Modern ROM localization-runtime shifted-check passed (locale resolver/selector probes unaffected by __text_shift), shifted output: %s\n' "$(MODERN_SHIFTED_OUTDIR_LOCALE)"
else
	@printf 'Modern ROM localization-runtime shifted-check skipped for config=%s (debug-only boot-timing calibration, matches expansion-modern-shifted-check)\n' '$(MODERN_CONFIG)'
endif

.PHONY: \
	expansion-modern-localization-budget \
	expansion-modern-localization-budget-check \
	expansion-modern-localization-runtime-debug-check \
	expansion-modern-localization-runtime-release-check \
	expansion-modern-localization-runtime-multi-check \
	expansion-modern-localization-runtime-cjk-check \
	expansion-modern-localization-runtime-prefs-check \
	expansion-modern-localization-runtime-save-check \
	expansion-modern-localization-runtime-shifted-check
# ---------------------------------------------------------------------------
# Issue #10: opt-in runtime item-ID-expansion probe
# ---------------------------------------------------------------------------
# Runs the real, booted expansion ROM and asserts what its own production
# paths recorded for the expanded item ID: the runtime GetItemData() record,
# the event engine's EV_CMD_GIVEITEM decoder placing it in a real unit
# inventory, the item menu/stat-screen draw, and the MultiArena/link, game
# save and suspend/resume roundtrips -- with the legacy 0xCD and empty
# (0x0000) item values unchanged next to it.
#
# Requires a probe build: FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1.
# The probe's EWRAM address is resolved from the linked ELF at check time,
# so this gate pins no ROM layout and needs no committed frame oracle.
#
# MODERN_CONFIG=release runs the boot-reachable stage set: a modern release
# ROM does not reach a battle map in this headless harness at all (a plain
# release ROM with no probe code, driven through the ordinary New Game route
# with full navigation input, stalls on the world map exactly the same way),
# so the map-dependent stages are proven against the debug configuration.
# See docs/id_space.md, "Runtime probe".
#
# Issue #6 (Sprint 2) rides this SAME gate and this SAME single ROM build
# rather than adding a second harness or a second ROM: when the caller also
# supplies the bundled-content profile (EXPANSION_STARTER_CONTENT=1, which
# itself requires EXPANSION_MECHANICS_HOOKS=1, plus EXPANSION_MECHANICS_SAMPLE=1
# so both the content mechanic and the pre-existing content-free sample are
# registered), the runner additionally asserts the authored content record's
# original name/description/uses/type/attributes/icon and the content
# mechanic's bounded, item-gated bonus. Requiring them here (instead of
# silently skipping) keeps the gate's contract explicit and its ROM one build.
MODERN_ITEMEXPANSION_SCRIPT := tools/gba-playtest/run_item_expansion_checks.py
MODERN_ITEMEXPANSION_DIR := $(MODERN_OUTPUT_DIR)/itemexpansion
MODERN_ITEMEXPANSION_STAGES := $(if $(filter release,$(MODERN_CONFIG)),boot,all)
MODERN_ITEMEXPANSION_ACTIVE_HEADER := $(GENERATED_DATA_ACTIVE_HEADER)

expansion-modern-itemexpansion-check: expansion-modern-rom
	@if [ "$(FE8_EXPANSION_ITEMTEST)" != "1" ] || [ -z "$(FE8_ITEM_ID_CAP)" ]; then \
		printf 'error: %s needs a probe build\n' 'expansion-modern-itemexpansion-check' >&2; \
		printf '  run: FE8_ITEM_ID_CAP=0xCE FE8_EXPANSION_ITEMTEST=1 make %s MODERN_CONFIG=%s MODERN_ABI=%s EXPANSION_STARTER_CONTENT=1 EXPANSION_MECHANICS_HOOKS=1 EXPANSION_MECHANICS_SAMPLE=1\n' \
			'expansion-modern-itemexpansion-check' '$(MODERN_CONFIG)' '$(MODERN_ABI)' >&2; \
		exit 1; \
	fi
	@if [ "$(EXPANSION_STARTER_CONTENT)" = "1" ] && \
		{ [ "$(EXPANSION_MECHANICS_HOOKS)" != "1" ] || [ "$(EXPANSION_MECHANICS_SAMPLE)" != "1" ]; }; then \
		printf 'error: %s with EXPANSION_STARTER_CONTENT=1 needs the full content profile\n' \
			'expansion-modern-itemexpansion-check' >&2; \
		printf '  add: EXPANSION_MECHANICS_HOOKS=1 EXPANSION_MECHANICS_SAMPLE=1\n' >&2; \
		exit 1; \
	fi
	NM="$(MODERN_NM)" "$(PYTHON)" "$(MODERN_ITEMEXPANSION_SCRIPT)" \
		--rom "$(MODERN_ROM)" \
		--elf "$(MODERN_ELF)" \
		--config "$(MODERN_CONFIG)" \
		--cap "$(FE8_ITEM_ID_CAP)" \
		--content "$(EXPANSION_STARTER_CONTENT)" \
		--active-header "$(MODERN_ITEMEXPANSION_ACTIVE_HEADER)" \
		--require-stages "$(MODERN_ITEMEXPANSION_STAGES)" \
		--out-dir "$(MODERN_ITEMEXPANSION_DIR)"
	@printf 'Modern ROM item-expansion runtime check passed: %s (config=%s abi=%s cap=%s stages=%s content=%s)\n' \
		"$(MODERN_ROM)" '$(MODERN_CONFIG)' '$(MODERN_ABI)' '$(FE8_ITEM_ID_CAP)' '$(MODERN_ITEMEXPANSION_STAGES)' '$(EXPANSION_STARTER_CONTENT)'

expansion-modern-linker-check: expansion-modern-budget-check \
		expansion-modern-overlay-audit \
		expansion-modern-starter-runtime-check \
		expansion-modern-boot-check \
		expansion-modern-title-check \
		expansion-modern-debugtools-check \
		expansion-modern-debugtools-timer-check \
		expansion-modern-debugtools-map-check \
		expansion-modern-debugtools-tools-check \
		expansion-modern-debugtools-prep-check \
		expansion-modern-debugtools-ch4prep-check \
		expansion-modern-newgame-check \
		expansion-modern-combat-check \
		expansion-modern-saveload-check \
		expansion-modern-savefmt-check \
		expansion-modern-shifted-check \
		expansion-modern-localization-budget-check \
		expansion-modern-localization-runtime-debug-check \
		expansion-modern-localization-runtime-release-check \
		expansion-modern-localization-runtime-multi-check \
		expansion-modern-localization-runtime-cjk-check \
		expansion-modern-localization-runtime-prefs-check \
		expansion-modern-localization-runtime-save-check \
		expansion-modern-localization-runtime-shifted-check
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
	expansion-modern-debugtools-tools-check \
	expansion-modern-debugtools-prep-check \
	expansion-modern-debugtools-ch4prep-check \
	expansion-modern-newgame-check \
	expansion-modern-combat-check \
	expansion-modern-saveload-check \
	expansion-modern-savefmt-check \
	expansion-modern-itemexpansion-check \
	expansion-modern-budget \
	expansion-modern-budget-check \
	expansion-modern-relocs \
	expansion-modern-overlay-audit \
	expansion-modern-shifted-check \
	expansion-modern-linker-check \
	expansion-modern-starter-profile-rom \
	expansion-modern-starter-hook-check \
	expansion-modern-starter-qol-check \
	expansion-modern-starter-runtime-check

-include $(wildcard $(sort $(MODERN_COHORT_DEPS) $(MODERN_ALL_DEPS) $(MODERN_FE6SIO_OBJ:.o=.d)))
