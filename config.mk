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
EXPANSION_SAVE_COMPAT_EPOCH ?= 4

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

# --- Optional Vesly debugger -------------------------------------------------
# Press B on a unit to edit them. 
VESLY_DEBUGGER ?= 1

# --- Optional DangerBones ----------------------------------------------------
# Highlight enemies that can attack the tile currently selected by the path
# arrow, using the fourth unit palette and map-sprite shake.
DANGER_BONES ?= 1

# --- Optional custom battle animations ---------------------------------------
# Swaps in community-sourced custom battle animation sets for select classes
# (see CREDITS.md), in place of the vanilla animation. Purely cosmetic.
NEW_ANIMS ?= 1

# --- Optional gameplay features ---------------------------------------------
# Adds chapter-scoped temporary gold and purchasable generic-unit bases on
# eligible fort / empty-village terrain.
PURCHASE_GENERICS ?= 1

# --- Optional MMB / Gorgon Egg -----------------------------------------------
# Enables the minimug side window and C Gorgon Egg hatch phase display. This
# mirrors the Catball1-style MMB setup by default; build with MMB=0 to fall
# back to the burst unit display for unitDisplayType=0.
MMB ?= 1

# --- Optional ExtendWeaponDescBox --------------------------------------------
# Modern-build port of ExtendWeaponDescBox: extends the item/weapon
# description help box from 3 to 5 lines (extra VRAM text-tile rows/handles),
# and the associated shop/prep/supply/trade VRAM-bank and layout fixes it
# depends on.
EXTEND_DESC_BOX ?= 1

# --- Optional DisplayObtainableItem ------------------------------------------
# Draws a small icon over enemy units carrying a droppable or stealable
# item, so the player can tell at a glance which enemies are worth
# attacking/stealing without opening each unit's inventory. The icon
# graphics themselves are not yet wired up -- see src/DisplayObtainableItem.c.
DISPLAY_OBTAINABLE_ITEM ?= 1

# --- Optional Debuffs ---------------------------------------------------------
# Enables per-unit temporary stat modifiers. DEBUFFS_STACK controls whether
# repeat applications of the same debuff keep worsening a stat toward -31.
DEBUFFS_EXIST ?= 1
DEBUFFS_STACK ?= 0

# --- Optional TextChNames -----------------------------------------------------
# Draws the actual chapter title text instead of a pre-rendered graphic
# banner, so any chapter name reads correctly without needing a hand-drawn
# banner per chapter. The original patch's save-select-screen per-slot
# chapter name preview (reads chapter id out of raw SRAM save data) is not
# ported -- see src/chapter_title.c.
TEXT_CHAPTER_NAMES ?= 0

# --- Optional BattleStatsNoAnims ---------------------------------------------
# Shows the attack forecast's Hit/Damage/Crit/AS numbers alongside the unit
# name/HP boxes when battle animations are off, instead of that information
# only being visible during the (skipped) battle animation. The original
# patch's weapon-icon-at-bottom sub-feature is not ported -- see
# ShowBattleStatsNoAnims in src/mapanim_infobox.c.
BATTLE_STATS_NO_ANIMS ?= 1

# --- Optional HpBars ----------------------------------------------------------
# Draws a partial-fill HP bar over each visible unit, plus a small icon
# over enemies the selected unit could hit for bonus effectiveness, land a
# high crit on, or start a support/talk event with. Requires
# DISPLAY_OBTAINABLE_ITEM=1 -- shares its icon sheet (validated: HP_BARS=1
# with DISPLAY_OBTAINABLE_ITEM=0 is a hard compile error). The in-game
# options-menu toggle from the original patch is not ported: this is a
# build-time flag instead, which already serves the same purpose. See
# src/HpBars.c for two further narrow simplifications.
HP_BARS ?= 1

# --- Optional CustomCampaign --------------------------------------------------
# Swaps in graphics/map/layout/NewPrologueMap.mar for the prologue chapter's
# map (see gChapterDataAssetTable in src/data/data_8B363C.c), and replaces
# the prologue's scripted beginning-of-chapter events with a version that
# still loads Eirika and Seth the same way but skips the Renais-throne-room
# cutscene and dialogue (see src/events/prologue-eventscript.h).
CUSTOM_CAMPAIGN ?= 1

# --- Optional SkipOpening -------------------------------------------------------
# Boots straight to the title screen: no health & safety screen, no
# Nintendo/Intelligent Systems logos, and no attract-mode opening demo. On
# New Game, also skips the world-map "continent of Magvel" narration and the
# "In an age long past..." opening text crawl. Does not affect continue/load.
SKIP_OPENING ?= 1

# --- Optional Credits ----------------------------------------------------------
# Scrolling end-credits sequence (big-font headers via the existing class-
# name-intro-letter font, sprite-text body lines, per-screen background/CG
# crossfades). Exposes StartCreditsProc(ProcPtr parent) for an event script
# or other game-flow point to call -- not wired to any specific trigger,
# since the original patch didn't have a real one either (only a build-
# time-disabled test hook). See src/Credits.c for two further narrow
# simplifications.
CREDITS ?= 0

# --- Optional bugfixes --------------------------------------------------------
# PutSprite/PutSpriteExt (src/ctc.c) bounds-check the secondary sprite-object
# pool before writing to it, instead of silently overflowing sSpritePool into
# sSpriteLayers when more than 0x80 sprites are queued in one frame. On by
# default: this is a pure bugfix with no behavioural change short of avoiding
# the overflow.
OVERFLOW_SAFETY_CHECKS ?= 1

