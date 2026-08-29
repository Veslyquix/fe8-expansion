# config.mk -- central, committed configuration surface for the expansion
# framework's semantic version and default GBA ROM identity (issue #8).
#
# This file intentionally does NOT redefine or duplicate MODERN_CONFIG
# (debug|release), MODERN_ABI (aapcs|apcs-gnu), MODERN_ROM_SIZE (16M|32M),
# or MODERN_TEXT_SHIFT: those presets remain owned and validated in
# modern.mk. config.mk only owns the values modern.mk did not previously
# have anywhere: the framework's semantic version and the GBA cartridge
# header identity fields.
#
# Every value below is validated by scripts/modernize/expansion_config.py
# before any modern C/assembly compilation or linking is attempted (see
# modern.mk's "Framework configuration and ROM identity" section), and is
# embedded into every modern ROM's expansion metadata record (see
# include/expansion_metadata.h and src/expansion_metadata.c). Overriding a
# value on the `make` command line (e.g. `make ... EXPANSION_ROM_TITLE=...`)
# changes the built ROM's identity; see docs/config_identity.md for the
# full settings reference, including which settings affect ABI, ROM
# data/layout, runtime behavior, or future save compatibility.

# --- Framework semantic version --------------------------------------------
# Each component must be an integer in [0, 255]. Bump these to mark a
# framework/config-identity change; the packed/string forms are derived
# automatically (see FE8_EXPANSION_VERSION_PACKED in
# include/expansion_config.h) and both are embedded in every modern ROM.
EXPANSION_VERSION_MAJOR ?= 0
EXPANSION_VERSION_MINOR ?= 1
EXPANSION_VERSION_PATCH ?= 0

# --- GBA cartridge header identity ------------------------------------------
# Defaults match the values hardcoded today in src/rom_header.s (the legacy
# build path, left untouched). The modern ROM recipe (modern.mk) patches a
# copy of the built ROM's header with these same fields and regenerates the
# header checksum accordingly -- see scripts/modernize/finalize_rom_header.py.
#   EXPANSION_ROM_TITLE      -- up to 12 printable-ASCII bytes (NUL-padded).
#   EXPANSION_ROM_GAME_CODE  -- exactly 4 printable-ASCII bytes.
#   EXPANSION_ROM_MAKER_CODE -- exactly 2 printable-ASCII bytes.
#   EXPANSION_ROM_REVISION   -- an integer in [0, 255] (the header's
#                               "software version" byte).
EXPANSION_ROM_TITLE      ?= FIREEMBLEM2E
EXPANSION_ROM_GAME_CODE  ?= BE8E
EXPANSION_ROM_MAKER_CODE ?= 01
EXPANSION_ROM_REVISION   ?= 0

# --- Deterministic build identity -------------------------------------------
# Explicit override for the embedded build id, e.g. for a CI-provided value
# on a reproducible source-archive build that has no .git directory. Empty
# by default: modern.mk then falls back to `git rev-parse HEAD` (works the
# same for a normal branch checkout or a detached HEAD) and finally to the
# fixed "unknown" sentinel when no git metadata is available at all. Never
# a timestamp, branch name, or host path -- see docs/config_identity.md.
EXPANSION_BUILD_ID ?=

# --- Save-format compatibility (issue #2 slice 1) ---------------------------
# An integer in [0, 65535] identifying the on-media SRAM save format's
# compatibility generation. This is INDEPENDENT of EXPANSION_VERSION_* above:
# the framework version can change (new features, unrelated fixes) without
# the save format changing, and vice versa. Bump this value only when a
# change would make an existing on-media save (include/save_format.h's
# `struct ExpansionSaveMeta`, or any current save-block struct it gates) no
# longer safely interpretable by the new build -- e.g. reordering/resizing a
# current save-block struct, changing the metadata checksum domain, or
# changing what a field means. Do NOT bump it for diagnostic-only changes
# (build commit, config fingerprint, ABI, title, ROM size, debug/release) --
# see docs/save_format.md for the full compatibility-vs-diagnostic field
# list and docs/config_identity.md for how this fits the rest of the
# identity surface.
#
# Bumped 1 -> 2 for issue #18 sprint 2: struct ExpansionUserPrefs
# (include/expansion_save_prefs.h) now occupies part of ExpansionSaveMeta's
# `reserved` tail.
#
# Bumped 2 -> 3 for the Camp/Tent structures feature: when
# FE8_PURCHASE_GENERICS is enabled, struct GameSavePackedUnit's `jid` field
# moves out of its packed bitfield into a standalone byte (widening the class
# ID save field from 7 to 8 bits so classes up to 0xFF survive a normal save;
# see docs/id_space.md's "class" domain and include/bmsave.h). This changes
# what the game-save unit bytes mean, so it must invalidate old saves via the
# existing save-compat gate rather than silently misreading them.
#
# Bumped 3 -> 4 for the debuffs feature: struct SuspendSavePackedUnit gained a
# conditional `debuffs[UNIT_DEBUFF_STAT_COUNT]` field and
# SUSPEND_SAVE_BLOCK_COUNT became conditional (1 vs 2) rather than a hardcoded
# 2, both changing struct SaveBlocks' layout from suspendSaveBlocks onward.
#
# Bumped 4 -> 5 for FE8_MAPGEN's per-save generation seed: struct PlaySt
# (include/types.h) gains a `#if FE8_MAPGEN u32 mapGenSeed;` field appended at
# its own end. This grows every struct that embeds struct PlaySt
# (GameSaveBlock, SuspendSaveBlock) and therefore shifts every subsequent
# offset in struct SaveBlocks, same class of change as the jid-widening bump
# above -- flag-gated (only FE8_MAPGEN=1 builds are affected), but real saves
# from a pre-bump build must not be silently misread post-bump.
# Bumped 5 -> 6 for the GameRank feature: struct PlaySt (include/types.h)
# gains a `#if FE8_GAME_RANK` block of five u16 kill-tracking fields appended
# at its own end (same class of change as FE8_MAPGEN's mapGenSeed bump
# above) -- flag-gated, but grows GameSaveBlock/SuspendSaveBlock and shifts
# every subsequent struct SaveBlocks offset when FE8_GAME_RANK=1.
#
# Bumped 6 -> 7 for the CO screen feature: struct PlaySt gains a
# `#if FE8_CO_POWERS` u8 commanderId[4] field appended at its own end (same
# class of change again) -- flag-gated, but grows GameSaveBlock/
# SuspendSaveBlock and shifts every subsequent struct SaveBlocks offset when
# FE8_CO_POWERS=1.
#
# Bumped 7 -> 8 for the CO gauge feature: struct PlaySt gains a
# `#if FE8_CO_POWERS` s16 coGauge[4] field appended right after
# commanderId (same class of change again).
EXPANSION_SAVE_COMPAT_EPOCH ?= 8

# --- Localization (issue #18) -----------------------------------------------
# EXPANSION_ENABLED_LOCALES -- comma-separated stable locale ids (see
#   scripts/localization/schema.py's LOCALE_IDS) enabled for this build; must
#   include "en" and must not repeat an id. The production allowlist is
#   "en", "ja", "zh-Hans", plus "qps-ploc" (an ASCII pseudo-locale test
#   harness, never a real translation -- see scripts/localization/pseudo.py).
#   Enabling "ja" or "zh-Hans" requires MODERN_ROM_SIZE=32M so their full-game
#   catalogs and CJK fonts live in the dedicated upper-ROM locale bank.
#   Normalized into the fixed stable-id order regardless of the order given
#   here (see scripts/modernize/expansion_config.py's validate_enabled_locales).
EXPANSION_ENABLED_LOCALES ?= en

# EXPANSION_DEFAULT_LOCALE -- the locale the runtime resolver
# (src/expansion_locale.c) starts in; must be one of EXPANSION_ENABLED_LOCALES.
EXPANSION_DEFAULT_LOCALE ?= en

# EXPANSION_PSEUDO_LOCALE -- exactly "0" or "1"; must be "1" if and only if
# "qps-ploc" is present in EXPANSION_ENABLED_LOCALES above (this is checked,
# not just documented -- an inconsistent combination fails the build before
# any compilation). This setting (like EXPANSION_ENABLED_LOCALES/
# EXPANSION_DEFAULT_LOCALE above) folds into the config identity fingerprint
# but never changes EXPANSION_SAVE_COMPAT_EPOCH: locale configuration is
# diagnostic/UI-facing, never a save-format compatibility concern.
EXPANSION_PSEUDO_LOCALE ?= 0

# --- Starter-feature opt-in build flags (issue #6) --------------------------
# Independent 0/1 switches for the issue #6 starter-feature foundation. Each
# flag defaults to 0, so a default build links none of them and stays
# byte/behaviour-identical to today's ROM (see docs/starter_features.md).
# Overriding a flag on the `make` command line (e.g.
# `make ... EXPANSION_MECHANICS_HOOKS=1`) opts that one feature in.
# scripts/modernize/expansion_config.py validates every value (only 0 or 1
# is accepted; -1/2/text fail with an actionable message) and folds every
# one of them into the config-identity fingerprint and embedded metadata JSON --
# they are diagnostic identity only and never change the save format (see
# EXPANSION_SAVE_COMPAT_EPOCH above, which stays independent).
#
#   EXPANSION_MECHANICS_HOOKS     -- link the public battle-stat mechanics
#                                    hook registry (include/expansion_mechanics.h).
#   EXPANSION_MECHANICS_SAMPLE    -- register the bundled sample mechanic
#                                    through that registry. Requires
#                                    EXPANSION_MECHANICS_HOOKS=1 (validated:
#                                    sample=1 with hooks=0 is a hard error).
#   EXPANSION_DANGER_OVERLAY_MENU -- expose the player-facing danger/range
#                                    overlay map-menu surface (reuses the
#                                    existing danger-zone range path).
#   EXPANSION_STARTER_CONTENT     -- link the bundled generated-data content
#                                    example: the framework-authored item
#                                    ITEM_EXPANSION_CE ("Sample Charm",
#                                    src/data/items_expansion.json) and its
#                                    mechanic, registered through the public
#                                    hook registry. Requires
#                                    EXPANSION_MECHANICS_HOOKS=1 AND an
#                                    expanded item ID cap
#                                    (FE8_ITEM_ID_CAP=0xCE or higher) --
#                                    both validated, both hard errors.
EXPANSION_MECHANICS_HOOKS     ?= 0
EXPANSION_MECHANICS_SAMPLE    ?= 0
EXPANSION_DANGER_OVERLAY_MENU ?= 0
EXPANSION_STARTER_CONTENT     ?= 0



    ## Campaign specific things 
# --- Optional CustomCampaign --------------------------------------------------
# Vesly's custom game. 
CUSTOM_CAMPAIGN ?= 1

# --- Optional gameplay features ---------------------------------------------
# Buy generic units on forts/camps. 
PURCHASE_GENERICS ?= 1

# --- Optional FortUnitsStartGreyedOut --------------------------------------------
# Units spawned from forts cannot immediately act. 
FORT_UNITS_START_GREYED_OUT ?= 1


# --- Optional procedural maps ------------------------------------------------
# Randomizes maps with premade map chunks. Requires
# PURCHASE_GENERICS (Camp/Tent trap kinds).
MAPGEN ?= 1

# --- Optional custom battle animations ---------------------------------------
# Swaps in community-sourced custom battle animation sets for select classes
# (see CREDITS.md), in place of the vanilla animation. Purely cosmetic.
NEW_ANIMS ?= 1

# --- Optional custom map tilesets --------------------------------------------
# Swaps in community-sourced map tilesets (see CREDITS.md) for the chapters
# that use them. Purely cosmetic: graphics, palette and tile config only.
NEW_TILESETS ?= 1

# --- Optional 256-color title screen -----------------------------------------
# Replaces the vanilla title screen's tiled 16-color background/dragon overlay
# with a single static 256-color (8bpp) background image. 
TITLE_256_COLORS ?= 1

# --- Optional TextChNames -----------------------------------------------------
# Draws the actual chapter title text instead of a pre-rendered graphic
# banner, so any chapter name reads correctly without needing a hand-drawn
# banner per chapter. 
# Note: vanilla text names for chapters are like this: TXT00 L00
TEXT_CHAPTER_NAMES ?= 1

# --- Optional Credits ----------------------------------------------------------
# Scrolling end-credits sequence using text instead of images. 
CREDITS ?= 0





    ## Bug fixes 
# --- Optional FixBugs -------------------------------------------------------------
# Prevents negative stats when loading a character with negative bases. 
FIX_BUGS ?= 1

# --- Optional bugfixes --------------------------------------------------------
# PutSprite/PutSpriteExt (src/ctc.c) bounds-check the secondary sprite-object
# pool before writing to it, instead of silently overflowing sSpritePool into
# sSpriteLayers when more than 0x80 sprites are queued in one frame. On by
# default: this is a pure bugfix with no behavioural change short of avoiding
# the overflow.
OVERFLOW_SAFETY_CHECKS ?= 1




    # For testing purposes 
# --- Optional Vesly debugger -------------------------------------------------
# Press B on a unit to edit them. 
VESLY_DEBUGGER ?= 1

# --- Optional SkipOpening -------------------------------------------------------
# Boots straight to the title screen: no health & safety screen, no
# Nintendo/Intelligent Systems logos, and no attract-mode opening demo. On
# New Game, also skips the world-map "continent of Magvel" narration and the
# "In an age long past..." opening text crawl. 
SKIP_OPENING ?= 1




    # Quality of Life 
# --- Optional DangerBones ----------------------------------------------------
# Highlight enemies that can attack the tile currently selected by the path
# arrow, using the fourth unit palette and map-sprite shake.
DANGER_BONES ?= 1

# --- Optional SelectViewGrowths ---------------------------------------------
# Press Select on the first stat-screen page to alternate between current
# stats and character growth rates.
SELECT_VIEW_GROWTHS ?= 1

# --- Optional BattleStatsNoAnims ---------------------------------------------
# Shows the attack forecast's Hit/Damage/Crit/AS numbers alongside the unit
# name/HP boxes when battle animations are off, instead of that information
# only being visible during the (skipped) battle animation. The original
# patch's weapon-icon-at-bottom sub-feature is not ported -- see
# ShowBattleStatsNoAnims in src/mapanim_infobox.c.
BATTLE_STATS_NO_ANIMS ?= 1

# --- Optional DrawMapAnims ----------------------------------------------------
# Draws weapon-type hit animations and floating damage numbers during map
# battle rounds when full battle animations are disabled. Purely cosmetic.
DRAW_MAP_ANIMS ?= 1

# --- Optional BattleAnimationNumbers ----------------------------------------
# Shows floating damage/heal numbers over battle-animation sprites. This is
# the full battle-animation counterpart to DRAW_MAP_ANIMS. Event flag 0xEE
# disables the numbers at runtime, matching the original SkillSystem hack.
BATTLE_ANIMATION_NUMBERS ?= 1

# --- Optional multipalette conversation backgrounds --------------------------
# Adds 224/256-colour (8bpp) conversation-background images alongside the
# vanilla 16-colour ones in gConvoBackgroundData. A 224-colour image leaves
# two palette banks (32 colours) free for text/chatbubble UI.
MULTIPALETTE_BG ?= 1

# --- Optional MMB / Gorgon Egg -----------------------------------------------
# Enables the minimug side window and C Gorgon Egg hatch phase display. This
# mirrors the Catball1-style MMB setup by default.
MMB ?= 1

# --- Optional ExtendWeaponDescBox --------------------------------------------
# Modern-build port of ExtendWeaponDescBox: extends the item/weapon
# description help box from 3 to 5 lines (extra VRAM text-tile rows/handles),
# and the associated shop/prep/supply/trade VRAM-bank and layout fixes it
# depends on.
EXTEND_DESC_BOX ?= 1

# --- Optional DisplayObtainableItem ------------------------------------------
# Draws a small icon over enemy units carrying a droppable or stealable.
DISPLAY_OBTAINABLE_ITEM ?= 1

# --- Optional HpBars ----------------------------------------------------------
# Draws a partial-fill HP bar over each visible unit, plus a small icon
# over enemies the selected unit could hit for bonus effectiveness, land a
# high crit on, or start a support/talk event with. Requires
# DISPLAY_OBTAINABLE_ITEM=1 -- shares its icon sheet 
HP_BARS ?= 1

# --- Optional AlphaSpriteArrow ---------------------------------------------------
# Displays a ghost of the unit at the tip of the blue arrow when selecting 
# where to move the unit to. 
ALPHA_SPRITE_ARROW ?= 1




    ## Gameplay related 
# --- Optional Debuffs ---------------------------------------------------------
# Enables per-unit temporary stat modifiers. DEBUFFS_STACK controls whether
# repeat applications of the same debuff keep worsening a stat toward -31.
DEBUFFS_EXIST ?= 1
DEBUFFS_STACK ?= 0


# --- Optional GroupAI ----------------------------------------------------------
# Attack one member of a tagged group and the rest immediately aggro. 
GROUP_AI ?= 1


# --- Optional PromoteCommand ------------------------------------------------------
# Adds a "Promote" command to the unit menu for units at level 20+ who
# can promote. 
PROMOTE_COMMAND ?= 1

# --- Optional Autosave ----------------------------------------------------------
# BmMain_SuspendBeforePhase only writes while
# transitioning into Player Phase, and only if the number of alive,
# deployed player units hasn't dropped since the last write 
TURN_AUTOSAVE ?= 1

# --- Optional GameRank ----------------------------------------------------------
# Tracks per-chapter and per-save-slot player-unit deaths, plus enemies
# defeated (both a per-turn "power score" high-water mark and a per-chapter
# total), so later chapters/events can reference them as a running game
# rank. See include/gamerank.h.
GAME_RANK ?= 1

# --- Optional CoPowers ----------------------------------------------------------
# Advance Wars reference: adds a "CO Powers" entry to the chapter (map) menu
# that pans the camera onto every one of the player's units in turn, parking
# the cursor on each for 5 frames. See src/power.c.
CO_POWERS ?= 1

# --- Optional FEBuilderGBA custom-pointer export ----------------------------
# Emits a small const array (src/febuilder_pointers.c) of this build's real
# addresses for the game-data tables FEBuilderGBA's ROMFE8U.cs hardcodes
# vanilla addresses for, and `make sync-win` uses it to regenerate
# fireemblem8.custom_pointer.txt (FEBuilderGBA's per-ROM pointer-override
# file) so FEBuilderGBA can be pointed at this ROM. Purely additive/opt-in
# tooling support -- no gameplay or save-format impact.
FEBUILDER_POINTERS ?= 1

# --- Optional Advance Wars 2 UI asset import --------------------------------
# Loads 5 PNGs dumped from Advance Wars 2's VRAM (no$gba) -- a star/rank icon
# strip, a taller "big stars" variant, and "POWER"/"SUPER" label graphics,
# plus a debug font -- as LZ77-compressed OBJ tile graphics. See src/aw2_gfx.c.
AW2_ASSETS ?= 1
# NOTE that AW2_COMINI_PAL_ID will need to be changed later, as it uses bg pal 15 (which fog also uses)

# --- Optional battle animation fast-forward ---------------------------------
# Ported from a standalone Lyn-hooked ASM patch (asm/AnimsFastForward on
# disk): holding L+B+A during a battle skips the main loop's normal
# VBlankIntrWait pacing so the animation plays as fast as the hardware
# allows (not during a promotion animation); holding L+R instead reverses
# whatever the current battle animation setting would have shown (full anims
# force off, off/map-anims forces full) for just that fight. See
# src/anims_fast_forward.c.
ANIMS_FAST_FORWARD ?= 1

# --- Optional custom BGM (NIMAP2) -------------------------------------------
# Swaps in the community "native instrument map, revision 2" so custom music
# written against General MIDI instrument numbers plays with the intended
# timbres, and appends custom songs to the end of gSongTable:
#
#   * voicegroup000 -- vanilla fills only 23 of its 128 slots (the other 105
#     are dummy square waves); NIMAP2 replaces the whole group with a
#     GM-shaped instrument map. Every custom song's _grp points here.
#   * voicegroups 079/080/081/083/084 -- the "drumfix". Purely additive: all
#     44 entries it writes land on slots that were dummy square waves in
#     vanilla, so GM drum-track note numbers hit real percussion samples
#     while every percussion voice vanilla actually plays is left untouched.
#   * sound/songs/bgm/*.s -- the custom songs themselves, appended to
#     gSongTable after vanilla's 1000 entries (see include/constants/songs.h).
#
# Modern lane only: the archival legacy lane keeps vanilla's voicegroups and
# song table so it stays byte-matching, exactly as every other feature flag
# leaves it alone. See docs/custom_bgm.md and scripts/sound/.
#
# TRADEOFF: replacing voicegroup000 is NOT vanilla-neutral. song001
# (agbfe3_bgm_opening, the title theme) is the one vanilla song that uses
# voicegroup000, and NIMAP2 changes every one of the 11 voice slots it plays
# -- mostly swapped strings/brass samples, but slot 126 goes from a
# percussion keysplit (voicegroup083) to a pitched sample, which is audible.
# Set NIMAP2=0 to keep vanilla's opening intact, or give the custom songs
# their own voicegroup instead (see docs/custom_bgm.md).
NIMAP2 ?= 1






