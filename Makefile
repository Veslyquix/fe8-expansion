#### Tools ####

ifeq ($(OS),Windows_NT)
  EXE := .exe
else
  EXE :=
endif

UNAME := $(shell uname)

TOOLCHAIN ?= $(DEVKITARM)
PREFIX ?= arm-none-eabi-

export PATH := $(TOOLCHAIN)/bin:$(PATH)

ifeq ($(UNAME),Darwin)
	SHELL := env PATH=$(PATH) /bin/bash
endif

CPP ?= $(PREFIX)cpp$(EXE)
AS := $(PREFIX)as$(EXE)
LD := $(PREFIX)ld$(EXE)
OBJCOPY := $(PREFIX)objcopy$(EXE)
STRIP := $(PREFIX)strip$(EXE)

CC1     := tools/agbcc/bin/agbcc$(EXE)
CC1_OLD := tools/agbcc/bin/old_agbcc$(EXE)

BIN2C      := tools/bin2c/bin2c$(EXE)
GBAGFX     := tools/gbagfx/gbagfx$(EXE)
SCANINC    := tools/scaninc/scaninc$(EXE)
AIF2PCM    := tools/aif2pcm/aif2pcm$(EXE)
MID2AGB    := tools/mid2agb/mid2agb$(EXE)
TEXTENCODE := tools/textencode/textencode$(EXE)
JSONPROC   := tools/jsonproc/jsonproc$(EXE)
PREPROC    := tools/preproc/preproc$(EXE)
ifeq ($(OS),Windows_NT)
PYTHON    ?= C:/Python312/python.exe
else
PYTHON    ?= python3
endif
FETSATOOL  := $(PYTHON) scripts/gfxtools/tsa_generator.py
TMAP2TSA   := $(PYTHON) scripts/tmap2tsa.py
MARTOMAP   := $(PYTHON) scripts/mar_to_map.py
PAL2GBAPAL := $(GBAGFX)

ifeq ($(UNAME),Darwin)
	SED := sed -i ''
else
	SED := sed -i
endif

CC1FLAGS := -mthumb-interwork -Wimplicit -Wparentheses -Werror -O2 -fhex-asm -ffix-debug-line -g
CPPFLAGS := -I tools/agbcc/include -iquote include -iquote . -nostdinc -undef
ASFLAGS  := -mcpu=arm7tdmi -mthumb-interwork -I include

# Issue #5 generated-data platform: standalone targets, never wired into
# `all` on their own (see generated_data.mk / docs/generated_data.md for
# full scope/status). Included this early -- before the Files section
# below and before `include modern.mk` further down -- because Batch
# 2c-1's GENERATED_DATA_LINKED_HAND_SOURCES/GENERATED_DATA_LINKED_C
# single-source-of-truth list (generated_data.mk) must already be defined
# before CFILES/ALL_OBJECTS (below) and MODERN_ALL_C_SOURCES (modern.mk)
# are computed, so a linked table's hand source can be filtered out of
# both lists and its generated equivalent added, exactly once, in its
# place.
#
# GNU Make's implicit default goal is the target of the *first* rule in
# the *first* makefile read (ignoring special/suffix targets) -- normally
# `all:` below, since it's the first real target this Makefile itself
# defines. Including generated_data.mk here, before `all:` is reached,
# means *its* first target (generated-data-validate) would otherwise
# silently become the default goal instead, so a bare `make` would
# validate generated-data JSON instead of building the ROM. Pin the
# default goal explicitly, before the include, so this include-order
# requirement can never regress bare `make`'s behavior regardless of
# what any included makefile defines first.
.DEFAULT_GOAL := all

include generated_data.mk

# Issue #18 sprint 1: fast, Python-only localization catalog targets
# (validate/generate/check/test/budget); see localization.mk for details.
include localization.mk

# Issue #18 full-game catalog slice: opt-in Python-only generator targets.
# The fragment does not add prerequisites to `all`; bare/default builds stay
# English-only and never generate or link CJK game-message payloads.
include game_localization.mk

#### Files ####

C_SUBDIR = src
ASM_SUBDIR = asm
DATA_SUBDIR = data
DATA_SRC_SUBDIR = src/data
SAMPLE_SUBDIR = sound/direct_sound_samples
MID_SUBDIR = sound/songs/midi
MAP_LAYOUT_SUBDIR = graphics/map/layout

ROM          := fireemblem8.gba
ELF          := $(ROM:.gba=.elf)
MAP          := $(ROM:.gba=.map)
LDSCRIPT     := ldscript.txt
SYM_FILES    := sym_iwram.txt
CFILES_GENERATED := $(C_SUBDIR)/msg_data.c
CFILES       := $(wildcard $(C_SUBDIR)/*.c)
ifeq (,$(findstring $(CFILES_GENERATED),$(CFILES)))
CFILES       += $(CFILES_GENERATED)
endif
# Issue #5 Batch 2c-1: hand C tables superseded by a linked generated-data
# equivalent are excluded from the legacy build here (their objects are
# re-added to ALL_OBJECTS below, from build/generated/data/ instead) -- see
# GENERATED_DATA_LINKED_HAND_SOURCES in generated_data.mk. The hand source
# itself stays on disk untouched; it is simply not compiled/linked.
CFILES       := $(filter-out $(GENERATED_DATA_LINKED_HAND_SOURCES),$(CFILES))
ASM_S_FILES  := $(wildcard $(ASM_SUBDIR)/*.s)
SRC_S_FILES  := src/rom_header.s src/crt0.s src/m4a_1.s src/libagbsyscall.s
DATA_S_FILES := $(wildcard $(DATA_SUBDIR)/*.s)
DATA_SRC_C_FILES := $(wildcard $(DATA_SRC_SUBDIR)/*.c $(DATA_SRC_SUBDIR)/mapanim/*.c $(DATA_SRC_SUBDIR)/menu/*.c $(DATA_SRC_SUBDIR)/ending/*.c $(DATA_SRC_SUBDIR)/worldmap/*.c $(DATA_SRC_SUBDIR)/ui/*.c)
DATA_SRC_C_OBJECTS := $(DATA_SRC_C_FILES:.c=.o)
DATA_SRC_SFILES_COMPILED := $(DATA_SRC_C_FILES:.c=.s)
# Hand-written (extracted, descriptively-named) data assembled directly. Kept in
# src/data/ subdirs (not the top-level src/data/*.s wildcard, which holds
# compiler intermediates of the typed .c data).
DATA_SRC_S_FILES := $(filter-out $(DATA_SRC_SFILES_COMPILED),$(wildcard $(DATA_SRC_SUBDIR)/map/*.s $(DATA_SRC_SUBDIR)/unit_icon/*.s $(DATA_SRC_SUBDIR)/banim/*.s $(DATA_SRC_SUBDIR)/mapanim/*.s $(DATA_SRC_SUBDIR)/menu/*.s $(DATA_SRC_SUBDIR)/ending/*.s $(DATA_SRC_SUBDIR)/worldmap/*.s $(DATA_SRC_SUBDIR)/ui/*.s))
SOUND_S_FILES := $(wildcard sound/*.s sound/songs/*.s sound/songs/mml/*.s sound/voicegroups/*.s)
SFILES       := $(ASM_S_FILES) $(SRC_S_FILES) $(DATA_S_FILES) $(DATA_SRC_S_FILES) $(SOUND_S_FILES)
SFILES_COMPILED := $(CFILES:.c=.s)
C_OBJECTS    := $(CFILES:.c=.o)
ASM_OBJECTS  := $(SFILES:.s=.o)
BANIM_OBJECT := banim/data_banim.o
MID_FILES    := $(wildcard $(MID_SUBDIR)/*.mid)
MID_OBJECTS  := $(MID_FILES:.mid=.o)
# Issue #5 Batch 3a: unlike GENERATED_DATA_LINKED_OBJECTS (whole-file
# swaps), $(GENERATED_DATA_CH2_UNITS_OBJECT) (generated_data.mk) is
# additive -- src/events_udefs.c/.o stays in CFILES/C_OBJECTS untouched
# (it still defines every other chapter's units), guarded internally to
# exclude just its Chapter 2 prefix slice. See generated_data.mk's
# "Linking a Chapter-2-owned partial-file table" section.
# Issue #5 Batch 3b: $(GENERATED_DATA_CH2_TRAPS_OBJECT) is the same kind
# of additive object -- src/events_trapdata.c/.o stays in CFILES/
# C_OBJECTS untouched (it still defines every other chapter's traps),
# guarded internally (twice, for its two non-adjacent Ch2 blocks) to
# exclude only TrapData_Event_Ch2/TrapData_Event_Ch2Hard. See
# generated_data.mk's "Linking a Chapter-2-owned partial-file table"
# section, traps subsection.
# Issue #5 Batch 3c: $(GENERATED_DATA_CH2_SHOPS_OBJECT) is the same kind
# of additive object -- src/events_shoplist.c/.o stays in CFILES/
# C_OBJECTS untouched (it still defines every other shop list), guarded
# internally to exclude only ShopList_Event_Ch2Armory. See
# generated_data.mk's "Linking a Chapter-2-owned partial-file table"
# section, shops subsection.
# Issue #5 Batch 3d: $(GENERATED_DATA_CH2_EVENTLISTS_OBJECT) is the same
# kind of additive object -- src/events_info.c/.o stays in CFILES/
# C_OBJECTS untouched (it still defines every other chapter's event-list
# composition), guarded internally to exclude only its (whole-header)
# "events/ch2-eventinfo.h" include. See generated_data.mk's "Linking a
# Chapter-2-owned partial-file table" section, eventlists subsection.
# Issue #5 Batch 1 (mechanics): $(GENERATED_DATA_TERRAINSTATS_OBJECT) is
# the same kind of additive object -- src/data_terrains.c/.o stays in
# CFILES/C_OBJECTS untouched (it still defines every movement-cost table,
# escape-hatch Unk_TerrainTable_N array, and banim graphics table), guarded
# internally (twice, for its two non-adjacent groups of arrays) to
# exclude only the 6 TerrainTable_Avo_*/Def_*/Res_* arrays and
# TerrainTable_HealAmount/TerrainTable_HealsStatus. See generated_data.mk's
# "Linking a partial-file table with two non-adjacent hand blocks, neither
# Chapter-2-owned" section, terrainstats subsection.
# Issue #5 Batch 2 (mechanics): $(GENERATED_DATA_MOVECOST_OBJECT) is the
# same kind of additive object, sharing src/data_terrains.c/.o with
# terrainstats above -- guarded internally (twice, for its two
# non-adjacent groups of arrays) to exclude only the 47 movement-cost
# arrays (15 named mobility profiles' Normal/Rain/Snow triplets,
# TerrainTable_MovCost_DemonKing, TerrainMoveCost_Ballista); it is
# canonically linked as the *first* `.data` prefix, ahead of
# terrainstats. See generated_data.mk's "Chapter-2-owned (Issue #5 Batch
# 2: mechanics movecost)" section.
# Issue #5 Batch 3 (mechanics): $(GENERATED_DATA_WEAPONTRIANGLE_OBJECT) is
# the same kind of additive object -- src/bmbattle.c/.o stays in CFILES/
# C_OBJECTS untouched (it still defines BattleApplyWeaponTriangleEffect/
# BattleApplyReaverEffect and every other battle-engine symbol), guarded
# internally (once) to exclude only the 12-rule sWeaponTriangleRules[]
# table; it is canonically linked as the literal first `.data` prefix of
# src/bmbattle.o, with everything else that file defines redirected into
# src/bmbattle.o(.data.bmbattletail). See generated_data.mk's "Linking a
# partial-file table" section, weapontriangle subsection.
ALL_OBJECTS  := $(C_OBJECTS) $(DATA_SRC_C_OBJECTS) $(ASM_OBJECTS) $(BANIM_OBJECT) $(MID_OBJECTS) $(GENERATED_DATA_LINKED_OBJECTS) $(GENERATED_DATA_CH2_UNITS_OBJECT) $(GENERATED_DATA_CH2_TRAPS_OBJECT) $(GENERATED_DATA_CH2_SHOPS_OBJECT) $(GENERATED_DATA_CH2_EVENTLISTS_OBJECT) $(GENERATED_DATA_TERRAINSTATS_OBJECT) $(GENERATED_DATA_MOVECOST_OBJECT) $(GENERATED_DATA_WEAPONTRIANGLE_OBJECT)
OBJECTS_LST  := objects.lst
DEPS_DIR     := .dep

AUTO_GEN_TARGETS :=

# Use the older compiler to build library code
src/agb_sram.o: CC1FLAGS := -mthumb-interwork -Wimplicit -Wparentheses -Werror -O1 -ffix-debug-line -g
src/m4a.o: CC1 := $(CC1_OLD)

# TODO: find a more elegant solution to the inlining issue
src/bmitem.o: CC1FLAGS += -Wno-error
src/menu_def.o: CC1FLAGS += -Wno-error

#### Main Targets ####

# Issue #15: this expansion ships ONE supported release lane -- modern GCC
# with the AAPCS ABI. A bare `make`/`make all` therefore unconditionally
# builds and real-emulator boot-verifies the modern release ROM end-to-end
# (`expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs`),
# and never requires, builds, or resolves to a tools/agbcc executable or
# library. This is a structural guarantee, not a configurable convention:
# `all:` takes no lane-selection variable of any kind, so no environment
# variable and no `make VAR=value` command-line override (regardless of
# name) can redirect it to the archival lane -- see
# scripts/modernize/tests/test_build_default_lane.py's negative-regression
# coverage for both of those ambient-pollution shapes. The recursive
# $(MAKE) call below hardcodes MODERN_CONFIG/MODERN_ABI as command-line
# assignments (highest make precedence), so the default lane is also
# deterministic against any ambient override of *those* two variables.
#
# The archival agbcc/decomp-matching lane is a deliberate, explicit,
# unsupported side door -- not deleted -- reachable *only* by naming it:
# `make legacy` (below) or the pre-existing `make fireemblem8.gba`; see
# CONTRIBUTING.md and docs/quickstart.md for when to use it.
#
# scripts/quickstart.sh --legacy invokes `make legacy` by name directly
# (never a bare `make`/`make all` plus a lane-selection variable), so
# there is nothing for quickstart -- or anyone else -- to set to reach the
# archival lane except this target's name.
ifeq ($(OS),Windows_NT)
all:
	+$(MAKE) expansion-modern-rom MODERN_CONFIG=release MODERN_ABI=aapcs
else
all:
	+$(MAKE) expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs
endif

# Explicit, clearly-named archival alias (issue #15): builds the exact same
# agbcc-based $(ROM) as `make fireemblem8.gba`. Kept as its own target so
# scripts/docs can name the archival lane directly.
legacy: $(ROM)
	@echo "Archival legacy build complete (agbcc, unsupported release lane): $(ROM)" >&2
	@echo "See CONTRIBUTING.md for the decomp-matching workflow this lane exists for." >&2

# Prevent the catch-all %.s rule from turning the removed comparison command
# into an unrelated native executable through make's built-in implicit rules.
compare:
	@echo "The legacy comparison target has been removed; build fireemblem8.gba instead." >&2
	@false

.PHONY: all legacy compare

#### Shiftability harness (scripts/shiftcheck/) ####
# Detects hardcoded pointers (raw absolute addresses that bypass the symbol system)
# which would break if the ROM layout shifted. See scripts/shiftcheck/README.md.
RELOCS_ELF  := fireemblem8_relocs.elf
SHIFTDIR    := build/shiftcheck
SHIFT       ?= 0x40000
SHIFT2      ?= 0x80000
SHIFTCHECK  := scripts/shiftcheck

# Layer 0: audit hardcoded addresses in the build system (Makefile/ldscripts).
shiftcheck-build:
	$(PYTHON) $(SHIFTCHECK)/scan_build_addrs.py --makefile Makefile \
	    --ldscript $(LDSCRIPT) --banim-ldscript linker_script_banim.txt

# Layer 1: relink with --emit-relocs, then flag ROM-pointer words with no relocation.
$(RELOCS_ELF): $(ALL_OBJECTS) $(OBJECTS_LST) $(LDSCRIPT)
	LD='$(LD)' OBJECTS_LST='$(OBJECTS_LST)' BANIM_OBJECT='$(BANIM_OBJECT)' \
	    $(SHIFTCHECK)/emit_relocs_link.sh $@ $(LDSCRIPT) -q

shiftcheck-static: $(RELOCS_ELF) $(ROM) $(MAP)
	$(PYTHON) $(SHIFTCHECK)/scan_relocs.py --elf $(RELOCS_ELF) --gba $(ROM) \
	    --map $(MAP) --ref-elf $(ELF) --prefix $(PREFIX) \
	    --allowlist $(SHIFTCHECK)/allowlist.txt

# Layer 1b: flag relocations against the WRONG base symbol -- a stored pointer written
# "ResourceA + hardcoded offset" that lands in a different resource B (breaks if A is resized).
shiftcheck-offsets: $(RELOCS_ELF) $(ROM) $(MAP)
	$(PYTHON) $(SHIFTCHECK)/scan_offsets.py --elf $(RELOCS_ELF) --gba $(ROM) \
	    --map $(MAP) --ref-elf $(ELF) --prefix $(PREFIX)

# Layer 2: differential two-shift build; an independent (reloc-table-free) confirm.
shiftcheck-diff: $(ROM) $(MAP) $(OBJECTS_LST)
	LD='$(LD)' OBJCOPY='$(OBJCOPY)' OBJECTS_LST='$(OBJECTS_LST)' \
	    BANIM_OBJECT='$(BANIM_OBJECT)' \
	    $(PYTHON) $(SHIFTCHECK)/diff_shift.py --base-gba $(ROM) --ldscript $(LDSCRIPT) \
	    --map $(MAP) --ref-elf $(ELF) --prefix $(PREFIX) --shifts $(SHIFT),$(SHIFT2) \
	    --outdir $(SHIFTDIR) --allowlist $(SHIFTCHECK)/allowlist.txt

# Layer 3: runtime smoke test (needs mGBA python bindings; non-blocking if absent).
shiftcheck-run: $(ROM) $(MAP) $(OBJECTS_LST)
	LD='$(LD)' OBJCOPY='$(OBJCOPY)' OBJECTS_LST='$(OBJECTS_LST)' \
	    BANIM_OBJECT='$(BANIM_OBJECT)' \
	    $(PYTHON) $(SHIFTCHECK)/run_dynamic.py --base-gba $(ROM) --shift $(SHIFT) \
	    --ldscript $(LDSCRIPT) --map $(MAP) --outdir $(SHIFTDIR) --prefix $(PREFIX)

# Static layers (the CI gate): build-system audit + reloc scan + cross-resource offsets + differential.
shiftcheck: shiftcheck-build shiftcheck-static shiftcheck-offsets shiftcheck-diff

.PHONY: shiftcheck shiftcheck-build shiftcheck-static shiftcheck-offsets shiftcheck-diff shiftcheck-run

# --- Issue #10 archival item-cap guard: parse-time known-goal fast-fail -----
# The dependency-graph attachment below is the backstop for *unknown /
# indirect / future* archival entries. But for a KNOWN, explicitly-named
# public archival goal we must fail EARLIER than the graph can: at Make
# parse/plan time, before any recipe, sub-make ($(MAKE) -C mgfembp ...), or
# agbcc / arm-none-eabi compile is planned or run. That is what the reviewer's
# 'fail early' requirement means -- a real `make legacy` / `make
# fireemblem8.gba` at an expanded cap must NOT first churn mgfembp's sub-build
# and hundreds of agbcc objects (all *regular* prerequisites of $(ROM),
# updated before the order-only guard) only to abort at the final link. An
# order-only prerequisite is updated AFTER the target's normal prerequisites,
# so the graph guard alone cannot pre-empt that upfront compile churn.
#
# ARCHIVAL_KNOWN_GOALS is every public goal that reaches the agbcc archival
# lane (verified against the Makefile / `make -p` DB, not guessed): the
# `legacy` alias, the direct $(ROM)/$(ELF)/$(MAP) products, $(RELOCS_ELF),
# $(OBJECTS_LST), and the whole shiftcheck aggregate + sub-targets that pull
# in $(ROM)/$(MAP)/$(RELOCS_ELF)/$(OBJECTS_LST). (shiftcheck-build is omitted:
# it only scans build-system addresses and reaches no archival product.)
# Anything not listed still trips the graph backstop. Both gates share the
# same actionable diagnostic ($(GENERATED_DATA_ARCHIVAL_ITEM_CAP_DIAG), defined
# once in generated_data.mk) so they can never drift.
ARCHIVAL_KNOWN_GOALS := legacy $(ROM) $(ELF) $(MAP) $(RELOCS_ELF) $(OBJECTS_LST) \
    shiftcheck shiftcheck-static shiftcheck-offsets shiftcheck-diff shiftcheck-run
ifneq (,$(GENERATED_DATA_ITEM_CAP_EXPANDED))
ifneq (,$(filter $(ARCHIVAL_KNOWN_GOALS),$(MAKECMDGOALS)))
$(error $(GENERATED_DATA_ARCHIVAL_ITEM_CAP_DIAG))
endif
endif

# --- Issue #10 archival item-cap guard: dependency-graph attachment ----------
# Bind generated_data.mk's archival item-cap guard (a .PHONY target whose
# recipe fires a make $(error) at a non-vanilla item cap) to the archival
# link/list/artifact boundary as an order-only prerequisite. Any target that
# reaches the agbcc archival lane -- the direct $(ROM)/$(ELF)/$(MAP) products,
# the `legacy` alias, $(RELOCS_ELF), the whole shiftcheck family (via
# $(ROM)/$(MAP)/$(RELOCS_ELF)/$(OBJECTS_LST)), $(OBJECTS_LST) itself, and any
# future target that depends on these -- therefore inherits an early,
# `make -n`-visible, parse/plan-time failure at an expanded cap, with no
# fragile MAKECMDGOALS whitelist to maintain. The
# guard is bound to the archival LINK/LIST/ARTIFACT boundary, not to the
# individual $(ALL_OBJECTS): several src/data/*.o data objects are *shared* --
# the modern lane's expansion-modern-boot-check builds them through its own
# `make NODEP=0 <objects>` sub-make -- so guarding objects would wrongly block
# the modern lane at an expanded cap. $(OBJECTS_LST)/$(ELF)/$(ROM)/$(MAP)/
# $(RELOCS_ELF), by contrast, are produced *only* by the agbcc archival lane
# (the modern lane emits its own separate MODERN_* products, and the
# generated-data checks build only generated objects), and every archival
# artifact -- incl. the whole shiftcheck family -- funnels through at least one
# of them. That is exactly the point where the generator's cap-sized table
# meets the cap-baked agbcc engine code, so it is the correct divergence gate.
# Order-only ('|') so the always-out-of-date .PHONY guard never forces an
# archival relink at the vanilla cap; the guard is a no-op (`:`) there.
ARCHIVAL_ITEM_CAP_GUARDED_TARGETS := $(OBJECTS_LST) $(ELF) $(ROM) $(MAP) $(RELOCS_ELF)
$(ARCHIVAL_ITEM_CAP_GUARDED_TARGETS): | generated-data-archival-item-cap-guard

CLEAN_FILES := $(ROM) $(ELF) $(MAP) $(OBJECTS_LST) $(SFILES_COMPILED) $(DATA_SRC_SFILES_COMPILED) graphics/*.h $(CFILES_GENERATED) $(RELOCS_ELF) $(RELOCS_ELF:.elf=.map)
# $(GENERATED_DATA_OUT_DIR) (build/generated/data) holds every linked
# table's stamp/.c/.s/.o (Issue #5 Batch 2c-1, generated_data.mk) -- added
# directly to this line (rather than generated_data.mk appending to
# CLEAN_DIRS) because generated_data.mk is included before this
# assignment and `:=` here would clobber any earlier append anyway.
CLEAN_DIRS := $(DEPS_DIR) $(SHIFTDIR) $(GENERATED_DATA_OUT_DIR)
CLEAN_BINS := graphics/statscreen/*.bin $(SAMPLE_SUBDIR)/*.bin $(MAP_LAYOUT_SUBDIR)/*.bin graphics/map/*TileConfiguration*.bin $(AUTO_GEN_TARGETS)
CLEAN_SONGS := $(MID_SUBDIR)/*.s

# Isolated, opt-in modern GCC object rules (no modern ELF/ROM target).
include modern.mk

# Shared clean routine
clean_common:
	$(RM) $(CLEAN_FILES) $(CLEAN_BINS) $(CLEAN_SONGS)
	$(RM) -rf $(CLEAN_DIRS)

clean_fast: clean_common
	$(RM) $(C_OBJECTS) $(ASM_OBJECTS) $(MID_OBJECTS)
	@find . \( -iname '*.o' -o -iname '*.obj' -o -iname '*.feimg*.bin'  -o -iname '*.fetsa*.bin' -o -iname '*.1bpp' -o -iname '*.4bpp' -o -iname '*.8bpp' -o -iname '*.gbapal' -o -iname '*.lz' -o -iname '*.fk' -o -iname '*.latfont' -o -iname '*.hwjpnfont' -o -iname '*.fwjpnfont' \) -not -path './banim/*' -not -path './graphics/banim/banim_new*' -exec rm {} +

.PHONY: clean_fast clean_common

# FE8_NEW_ANIMS custom battle-animation assets (see scripts/banim_event_to_source.py
# and CREDITS.md): banim_new*_{oam,modes,script}* live under banim/, already
# excluded above, but their sheet/palette siblings (banim_new*_sheet_N.4bpp.lz,
# banim_new*.agbpal.lz) live under graphics/banim/, which was NOT excluded --
# clean_fast/clean's generic find swept them by extension like any other build
# byproduct. Unlike vanilla graphics/banim/*.lz (regenerated from a checked-in
# .png via graphics_file_rules.mk), these have no Makefile-visible source: they
# are extracted once from an AA.exe .event export that exists only on the
# original Windows machine, so deleting them is NOT recoverable by `make` --
# only by re-running the converter against that export. Protect them in both
# targets; only `clean_all` (git clean -dfx, already documented as maximally
# destructive) may remove them.
clean: clean_common
	$(RM) $(ALL_OBJECTS)
	# Remove battle animation binaries
	$(RM) -f banim/*.bin banim/*.o banim/*.lz banim/*.bak
	@find . \( -iname '*.o' -o -iname '*.obj' -o -iname '*.feimg*.bin'  -o -iname '*.fetsa*.bin' -o -iname '*.1bpp' -o -iname '*.4bpp' -o -iname '*.8bpp' -o -iname '*.gbapal' -o -iname '*.lz' -o -iname '*.fk' -o -iname '*.latfont' -o -iname '*.hwjpnfont' -o -iname '*.fwjpnfont' \) -not -path './graphics/banim/banim_new*' -exec rm {} +

.PHONY: clean

# Hard clean: remove every untracked and ignored file in the working tree,
# preserving only baserom.gba (and embedded git repos like .deps/agbcc).
# After this you must rebuild the tools (and reinstall agbcc into tools/agbcc
# via .deps/agbcc/install.sh) before `make` will work again.
clean_all:
	git clean -dfx -e baserom.gba

.PHONY: clean_all

tag:
	gtags
	ctags -R
	cscope -Rbkq

.PHONY: tag

#### Recipes ####

# Comprssed Texts Recipes

# =========
# = Texts =
# =========
TEXT_DIR := texts
TEXT_TOOLS := scripts/texttools

TEXT_DECODER := $(PYTHON)  $(TEXT_TOOLS)/textdecoder.py
TEXT_DPARSER := $(PYTHON) $(TEXT_TOOLS)/textdeparser.py
TEXT_PROCESS := $(PYTHON) $(TEXT_TOOLS)/textprocess.py

TEXT_MAIN := $(TEXT_DIR)/texts.txt
TEXT_DEFS := $(TEXT_DIR)/textdefs.txt
TEXT_SRC  := $(TEXT_MAIN) $(shell find $(TEXT_DIR) -type f -name "*.txt")

TEXT_HEADER := include/constants/msg.h
MSG_LIST    := src/msg_data.c

src/msg_data.c: $(TEXT_SRC) $(TEXT_DEFS)
	@$(TEXT_PROCESS) $(TEXT_MAIN) $(TEXT_DEFS) $@ $(TEXT_HEADER) utf8

# Graphics Recipes

include graphics_file_rules.mk
include graphics/banim/assets/img/banim_img_rules.mk
include songs.mk
include json_data_rules.mk

# release.mk (issue #9): standalone release/publication rehearsal
# targets (release-check, release-rehearse, release-migrations-check,
# release-test). Not wired into `all` or any existing gate; see
# docs/release_process.md.
include release.mk

# generated_data.mk is included earlier now (right after the Tools section,
# before the Files section) -- see the comment there. Its
# generated-data-* targets are standalone, not part of `all`;
# `generated-data-check` itself *is* wired into
# .github/workflows/build.yml as a CI gate (Batch C). See generated_data.mk
# and docs/generated_data.md.

%.s: ;
%.png: ;
%.pal: ;
%.aif: ;

%.1bpp: %.png  ; $(GBAGFX) $< $@
%.4bpp: %.png  ; $(GBAGFX) $< $@
%.8bpp: %.png  ; $(GBAGFX) $< $@
%.gbapal: %.pal ; $(PAL2GBAPAL) $< $@
%.gbapal: %.png ; $(GBAGFX) $< $@
%.lz: % ; $(GBAGFX) $< $@ $(LZ_FLAGS)
# These DemonLight sprite images were compressed in the original ROM with a
# minimum LZ match distance of 3 (gbagfx defaults to 2). Reproduce byte-identically.
graphics/banim/dragonfx/Img_DemonLightSprites_087A5BA4.4bpp.lz: LZ_FLAGS := -mindist 3
graphics/banim/dragonfx/Img_DemonLightSprites_087A5E9C.4bpp.lz: LZ_FLAGS := -mindist 3
# Class-reel (gOpinfo) glyph font: 64 per-glyph 4bpp images, min LZ match distance 2.
graphics/misc/opinfo_letter/%.4bpp.lz: LZ_FLAGS := -mindist 2
# Orphaned LZ77 TSA tilemap (was hidden after Pal_080E1164), min LZ match distance 1.
graphics/banim/misc/Tsa_080E1184.tsa.lz: LZ_FLAGS := -mindist 1
# Orphaned PlayerRankFog fog image (was hidden after Pal_PlayerRankFog), min match distance 2.
graphics/misc/Img_PlayerRankFog.4bpp.lz: LZ_FLAGS := -mindist 2
# FE6 SIO multiboot image, built from source via the mgfembp submodule
# (StanHash/mgfembp) instead of a committed blob, then LZ-compressed (the original
# ROM used minimum match distance 1) for the incbin in asm/fe6sio.s. mgfembp
# needs its own agbcc variant (010110-ThumbPatch, fetched by its installer) and
# CPP=cpp because arm-none-eabi-cpp may be absent.
mgfembp/tools/agbcc/bin/agbcc:
	cd mgfembp && bash tools/install_agbcc.sh

mgfembp/mgfembp.bin: mgfembp/tools/agbcc/bin/agbcc FORCE
	$(MAKE) -C mgfembp CPP=cpp PREFIX="$(PREFIX)" tools
	$(MAKE) -C mgfembp CPP=cpp PREFIX="$(PREFIX)" mgfembp.bin

fe6sio_payload.bin.lz: mgfembp/mgfembp.bin
	$(GBAGFX) $< $@ -mindist 1

FORCE:
.PHONY: FORCE
# Titlescreen dragon-foreground TSA was compressed with minimum LZ match distance 1.
graphics/titlescreen/title_dragon_foreground.map.bin.lz: LZ_FLAGS := -mindist 1
%.rl: % ; $(GBAGFX) $< $@
%.fk: % ; ./scripts/compressor.py $< fk
%.bin: %.mar  ; $(MARTOMAP)  $< $@
sound/%.bin: sound/%.aif ; $(AIF2PCM) $< $@

%.4bpp.h: %.4bpp
	$(BIN2C) $< $(subst .,_,$(notdir $<)) | sed 's/^const //' > $@

%.feimg1.bin %.fetsa1.bin: %.png
	$(FETSATOOL) $< $*.feimg1.bin $*.fetsa1.bin

%.feimg2.bin %.fetsa2.bin: %.png
	$(FETSATOOL) $< $*.feimg2.bin $*.fetsa2.bin

%.feimg3.bin %.fetsa3.bin: %.png
	$(FETSATOOL) $< $*.feimg3.bin $*.fetsa3.bin

%.feimg4.bin %.fetsa4.bin: %.png
	$(FETSATOOL) $< $*.feimg4.bin $*.fetsa4.bin

# Battle Animation Recipes

$(BANIM_OBJECT): $(shell ./scripts/arm_compressing_linker.py -t linker_script_banim.txt -m)
	./scripts/arm_compressing_linker.py -o $@ -t linker_script_banim.txt -b 0x8c02000 -l $(LD) --objcopy $(OBJCOPY) -c ./scripts/compressor.py

%_modes.bin: %_motion.o
	$(OBJCOPY) -O binary -j .data.modes $< $@

%_oam_l.bin: %_motion.o
	$(OBJCOPY) -O binary -j .data.oam_l $< $@

%_oam_r.bin: %_motion.o
	$(OBJCOPY) -O binary -j .data.oam_r $< $@

# Map tileset configuration: assemble .S (metatile/terrain macros) to a flat
# binary, which the %.lz rule then compresses for incbin.
graphics/map/%.bin: graphics/map/%.S graphics/map/tile_config.inc
	$(AS) $(ASFLAGS) -g $< -o $(@:.bin=.o)
	$(OBJCOPY) -O binary $(@:.bin=.o) $@


# Automatic dependency generation

MAKEDEP = mkdir -p $(DEPS_DIR)/$(dir $*) && $(CPP) $(CPPFLAGS) $< -MM -MG -MT $*.o > $(DEPS_DIR)/$*.d

MAKECMDGOALS_NODEP := clean tag $(MODERN_GOALS) \
	game-localization-validate game-localization-generate \
	game-localization-check game-localization-test game-localization-budget

ifeq (,$(filter $(MAKECMDGOALS),$(MAKECMDGOALS_NODEP)))
-include $(addprefix $(DEPS_DIR)/,$(CFILES:.c=.d))
endif

$(DEPS_DIR)/%.d: %.c
	@$(MAKEDEP)

# FORCE (not just $(ALL_OBJECTS)) makes this rule's recipe *always* run,
# even when every object file in $(ALL_OBJECTS) already exists and is
# older than a stale $(OBJECTS_LST) left over from a prior invocation
# where $(ALL_OBJECTS) resolved to a different list (e.g. a hand object
# such as src/data_characters.o that a generated-data link swap has
# since filtered out, or a switched branch/stash) -- ordinary
# file-mtime prerequisite tracking can never catch that case, since
# make only re-runs a recipe when a *prerequisite file's* mtime is
# newer than the target's, and none of the individual object files
# changed. Regenerating into a temp file and only replacing $@ via `cmp
# -s || mv` when the content actually differs keeps $@'s own mtime (and
# therefore every downstream user -- $(ELF), shiftcheck-diff/-run)
# untouched on a content-identical regenerate, so an unrelated touch
# elsewhere can never trigger an unnecessary relink.
$(OBJECTS_LST): $(ALL_OBJECTS) FORCE
	@echo $(ALL_OBJECTS) > $@.tmp
	@cmp -s $@.tmp $@ 2>/dev/null && rm -f $@.tmp || mv -f $@.tmp $@

$(ELF): $(ALL_OBJECTS) $(OBJECTS_LST) $(LDSCRIPT) $(SYM_FILES)
	$(LD) -T $(LDSCRIPT) -Map $(MAP) @$(OBJECTS_LST) -L tools/agbcc/lib -o $@ -lc -lgcc
	$(STRIP) -N .gcc2_compiled. $@

%.gba: %.elf
	$(OBJCOPY) --strip-debug -O binary --pad-to 0x9000000 --gap-fill=0xff $< $@

$(C_OBJECTS): %.o: %.c $(DEPS_DIR)/%.d
	@$(MAKEDEP)
	$(CPP) $(CPPFLAGS) $< | iconv -f UTF-8 -t CP932 | $(CC1) $(CC1FLAGS) -o $*.s
	echo '.ALIGN 2, 0' >> $*.s
ifeq ($(UNAME),Darwin)
	$(SED) -f scripts/align_2_before_debug_section_for_osx.sed $*.s
else
	$(SED) '/.section	.debug_line/i\.align 2, 0' $*.s
endif
	$(AS) $(ASFLAGS) $*.s -o $@

src/chapterdata.o: $(DATA_SRC_SUBDIR)/chapter_settings.h
src/fontgrp.o: graphics/debug_font.4bpp.h

ifeq ($(NODEP),1)
asm/%.o:      data_dep :=
else
asm/%.o:      data_dep = $(shell $(SCANINC) -I include -I "" $*.s)
endif

ifeq ($(NODEP),1)
src/%.o:      data_dep :=
else
src/%.o:      data_dep = $(shell $(SCANINC) -I include -I "" $*.s)
endif

ifeq ($(NODEP),1)
src/data/%.o: data_dep :=
else
src/data/%.o: data_dep = $(shell $(SCANINC) -I include -I "" $(if $(wildcard $*.c),$*.c,$*.s))
endif

ifeq ($(NODEP),1)
data/%.o:     data_dep :=
else
data/%.o:     data_dep = $(shell $(SCANINC) -I include -I "" $*.s)
endif

ifeq ($(NODEP),1)
banim/%.o:    data_dep :=
else
banim/%.o:    data_dep = $(shell $(SCANINC) -I include -I "" $*.s)
endif

ifeq ($(NODEP),1)
sound/%.o:    data_dep :=
else
sound/%.o:    data_dep = $(shell $(SCANINC) -I include -I "" $*.s)
endif

.SECONDEXPANSION:
$(ASM_OBJECTS): %.o: %.s $$(data_dep)
	$(AS) $(ASFLAGS) -g $< -o $@

# Build the host preproc via its own Makefile (plain g++). build_tools.sh already
# does this through make_tools.mk's tools/* wildcard; this explicit rule shadows
# make's built-in %:%.cpp rule, which would otherwise inherit the project's
# -nostdinc CPPFLAGS and fail (<cstdio> not found) if preproc.cpp is newer than
# the binary -- e.g. after a `git pull` followed by `make` without rebuilding tools.
$(PREPROC): tools/preproc/preproc.cpp tools/preproc/Makefile
	$(MAKE) -C tools/preproc

$(DATA_SRC_C_OBJECTS): %.o: %.c $(PREPROC) $$(data_dep)
	$(PREPROC) $< | $(CPP) $(CPPFLAGS) - | iconv -f UTF-8 -t CP932 | $(CC1) $(CC1FLAGS) -o $*.s
	echo '.ALIGN 2, 0' >> $*.s
ifeq ($(UNAME),Darwin)
	$(SED) -f scripts/align_2_before_debug_section_for_osx.sed $*.s
else
	$(SED) '/.section	.debug_line/i\.align 2, 0' $*.s
endif
	$(AS) $(ASFLAGS) $*.s -o $@
%.lz:$(MAP_LAYOUT_SUBDIR)/%.bin ; $(GBAGFX) $< $@

# Don't delete intermediate files
.SECONDARY:

# debug print, to use, call "make print-(your label here)"
print-% : ; $(info $* is a $(flavor $*) variable set to [$($*)]) @true
