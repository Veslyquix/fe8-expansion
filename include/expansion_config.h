#ifndef GUARD_EXPANSION_CONFIG_H
#define GUARD_EXPANSION_CONFIG_H

/*
 * Central, committed C configuration contract for the expansion framework
 * (issue #8). This header is C89/agbcc-safe and is reachable through the
 * normal include architecture (see include/global.h).
 *
 * Every FE8_EXPANSION_* value below has a hardcoded fallback definition
 * guarded by #ifndef, matching config.mk's own defaults exactly (so the
 * legacy agbcc/old_agbcc build -- which never receives the modern -D
 * flags below -- keeps today's exact ROM identity and behavior). The
 * modern build (see modern.mk's "Framework configuration and ROM
 * identity" section) instead supplies every one of these as a `-D`
 * command-line define computed from config.mk plus MODERN_CONFIG/
 * MODERN_ABI/MODERN_ROM_SIZE and the resolved build commit/fingerprint,
 * so the #ifndef fallback below is never reached for a modern build.
 *
 * See docs/config_identity.md for the full settings reference.
 */

/* Unconditional: any translation unit that includes global.h can use this
 * to detect that it is part of the expansion framework. */
#define FE8_EXPANSION 1

/* --- Semantic version (see config.mk EXPANSION_VERSION_*) --------------- */

#ifndef FE8_EXPANSION_VERSION_MAJOR
#define FE8_EXPANSION_VERSION_MAJOR 0
#endif

#ifndef FE8_EXPANSION_VERSION_MINOR
#define FE8_EXPANSION_VERSION_MINOR 1
#endif

#ifndef FE8_EXPANSION_VERSION_PATCH
#define FE8_EXPANSION_VERSION_PATCH 0
#endif

#ifndef FE8_EXPANSION_VERSION_STRING
#define FE8_EXPANSION_VERSION_STRING "0.1.0"
#endif

/* Packed as (major << 16) | (minor << 8) | patch, matching
 * scripts/modernize/expansion_config.py's compute_version_packed(). */
#ifndef FE8_EXPANSION_VERSION_PACKED
#define FE8_EXPANSION_VERSION_PACKED \
    (((u32)(FE8_EXPANSION_VERSION_MAJOR) << 16) | \
     ((u32)(FE8_EXPANSION_VERSION_MINOR) << 8) | \
     (u32)(FE8_EXPANSION_VERSION_PATCH))
#endif

/* --- Deterministic build metadata (see modern.mk / expansion_config.py) - */

/* Full 40-hex-character git commit SHA the ROM was built from, or the
 * fixed sentinel "unknown" when no git metadata is available (a source
 * archive, or git missing). Never a timestamp or branch name. */
#ifndef FE8_EXPANSION_BUILD_COMMIT
#define FE8_EXPANSION_BUILD_COMMIT "unknown"
#endif

/* 16 lowercase hex characters: a SHA-256-derived fingerprint over every
 * compatibility-relevant setting (version, ABI, ROM size, text shift, ROM
 * identity, config preset). Two builds with the same fingerprint are
 * guaranteed to share those settings. */
#ifndef FE8_EXPANSION_CONFIG_FINGERPRINT
#define FE8_EXPANSION_CONFIG_FINGERPRINT "0000000000000000"
#endif

/* "debug" or "release" (see MODERN_CONFIG in modern.mk). */
#ifndef FE8_EXPANSION_CONFIG_PRESET
#define FE8_EXPANSION_CONFIG_PRESET "release"
#endif

/* "aapcs" or "apcs-gnu" (see MODERN_ABI in modern.mk). */
#ifndef FE8_EXPANSION_ABI
#define FE8_EXPANSION_ABI "aapcs"
#endif

/* --- ROM identity (see config.mk EXPANSION_ROM_*) ------------------------ */

#ifndef FE8_EXPANSION_ROM_TITLE
#define FE8_EXPANSION_ROM_TITLE "FIREEMBLEM2E"
#endif

#ifndef FE8_EXPANSION_ROM_GAME_CODE
#define FE8_EXPANSION_ROM_GAME_CODE "BE8E"
#endif

#ifndef FE8_EXPANSION_ROM_MAKER_CODE
#define FE8_EXPANSION_ROM_MAKER_CODE "01"
#endif

#ifndef FE8_EXPANSION_ROM_REVISION
#define FE8_EXPANSION_ROM_REVISION 0
#endif

/* Exact output ROM size in bytes (16 MiB or 32 MiB; see MODERN_ROM_SIZE). */
#ifndef FE8_EXPANSION_ROM_SIZE_BYTES
#define FE8_EXPANSION_ROM_SIZE_BYTES 0x1000000
#endif

/* --- Release-aware debug/assertion/logging switches ---------------------- */
/*
 * These follow the existing NDEBUG convention already used by
 * include/gba/isagbprint.h's AGB_ASSERT/AGB_WARNING macros: a debug preset
 * build compiles without NDEBUG, a release preset build compiles with it.
 * Subsystems added later can gate development-only code on
 * FE8_EXPANSION_DEBUG rather than re-deriving this from NDEBUG themselves.
 */
#ifndef FE8_EXPANSION_DEBUG
#ifdef NDEBUG
#define FE8_EXPANSION_DEBUG 0
#else
#define FE8_EXPANSION_DEBUG 1
#endif
#endif

#ifndef FE8_EXPANSION_ASSERTIONS_ENABLED
#define FE8_EXPANSION_ASSERTIONS_ENABLED FE8_EXPANSION_DEBUG
#endif

#ifndef FE8_EXPANSION_LOGGING_ENABLED
#define FE8_EXPANSION_LOGGING_ENABLED FE8_EXPANSION_DEBUG
#endif

/* --- Save-format compatibility (see config.mk EXPANSION_SAVE_COMPAT_EPOCH,
 * issue #2 slice 1) -------------------------------------------------------- */
/*
 * The explicit save-compatibility epoch/key gating include/save_format.h's
 * raw-byte classifier's SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE state. This is
 * deliberately independent of FE8_EXPANSION_VERSION_* and
 * FE8_EXPANSION_CONFIG_FINGERPRINT above: those are stored in the on-media
 * ExpansionSaveMeta record purely as diagnostics and must never gate save
 * compatibility by themselves (a build/title/debug/ROM-size-only change
 * must never make an existing current save look incompatible). Bump only
 * this value when a save-layout/serialization change requires it -- see
 * docs/save_format.md.
 *
 * Bumped 1 -> 2 for issue #18 sprint 2 alongside SAVE_FORMAT_VERSION_CURRENT
 * (include/save_format.h): struct ExpansionUserPrefs now occupies part of
 * ExpansionSaveMeta's `reserved` tail. This default is compiled in only
 * when config.mk does not itself define EXPANSION_SAVE_COMPAT_EPOCH (the
 * repository's config.mk does, and is bumped to the same value).
 */
#ifndef FE8_EXPANSION_SAVE_COMPAT_EPOCH
#define FE8_EXPANSION_SAVE_COMPAT_EPOCH 4
#endif


/* --- Locale identity (see config.mk EXPANSION_ENABLED_LOCALES/
 * EXPANSION_DEFAULT_LOCALE/EXPANSION_PSEUDO_LOCALE, issue #18 sprint 1) --- */
/*
 * FE8_EXPANSION_ENABLED_LOCALE_MASK is a bitmask over ExpansionLocaleId
 * values (include/expansion_locale.h): bit N set means locale id N
 * (EXPANSION_LOCALE_EN, EXPANSION_LOCALE_QPS_PLOC, ...) is enabled for
 * this build. FE8_EXPANSION_DEFAULT_LOCALE_ID is the ExpansionLocaleId
 * ExpansionLocale_GetDefault() returns; it is always one of the bits set
 * in the mask (scripts/modernize/expansion_config.py validates this
 * before any modern C/assembly compilation). FE8_EXPANSION_PSEUDO_LOCALE_
 * ENABLED mirrors whether EXPANSION_LOCALE_QPS_PLOC is enabled (bit 7 of
 * the mask) as a plain 0/1 flag, purely for callers that want to branch
 * on "is the ASCII pseudo-locale test harness active" without decoding
 * the mask themselves.
 *
 * The hardcoded fallback below (bit 0 only, i.e. English-only, default
 * English, pseudo disabled) matches config.mk's own EXPANSION_ENABLED_
 * LOCALES/EXPANSION_DEFAULT_LOCALE/EXPANSION_PSEUDO_LOCALE defaults
 * exactly, so the legacy agbcc build (which never receives the modern
 * -D locale flags -- and never links src/expansion_locale.c at all, see
 * that file's own header comment) still compiles consistently with
 * today's implicit English-only behavior.
 */
#ifndef FE8_EXPANSION_ENABLED_LOCALE_MASK
#define FE8_EXPANSION_ENABLED_LOCALE_MASK 0x1u
#endif

/*
 * Compile-time popcount of FE8_EXPANSION_ENABLED_LOCALE_MASK's low 8 bits
 * (EXPANSION_LOCALE_COUNT, include/expansion_locale.h, is fixed at 8) --
 * the single shared source of truth for "how many locales does this
 * build actually enable", used both by src/expansion_language_menu.c
 * (sizing its row table / deciding AUTO_SELECT vs. SHOW_MENU) and by
 * src/bmsave-lib.c's BuildCurrentExpansionSaveMeta() (issue #18 sprint 6:
 * deciding whether a brand-new save may auto-stamp a VALID default
 * ExpansionUserPrefs record, single-enabled-locale builds only, or must
 * leave that record at the canonical EXPANSION_USER_PREFS_UNSET all-zero
 * pattern so a genuinely multi-enabled-locale build's mandatory
 * first-start prompt is never silently skipped). Both call sites must
 * stay legacy-agbcc-compilable, so this is a plain preprocessor bit-sum,
 * never a call to ExpansionLocale_IsEnabled() (src/expansion_locale.c,
 * modern-linked only).
 */
#define FE8_EXPANSION_ENABLED_LOCALE_COUNT \
    (((FE8_EXPANSION_ENABLED_LOCALE_MASK >> 0) & 1) + \
     ((FE8_EXPANSION_ENABLED_LOCALE_MASK >> 1) & 1) + \
     ((FE8_EXPANSION_ENABLED_LOCALE_MASK >> 2) & 1) + \
     ((FE8_EXPANSION_ENABLED_LOCALE_MASK >> 3) & 1) + \
     ((FE8_EXPANSION_ENABLED_LOCALE_MASK >> 4) & 1) + \
     ((FE8_EXPANSION_ENABLED_LOCALE_MASK >> 5) & 1) + \
     ((FE8_EXPANSION_ENABLED_LOCALE_MASK >> 6) & 1) + \
     ((FE8_EXPANSION_ENABLED_LOCALE_MASK >> 7) & 1))

#ifndef FE8_EXPANSION_DEFAULT_LOCALE_ID
#define FE8_EXPANSION_DEFAULT_LOCALE_ID 0
#endif

#ifndef FE8_EXPANSION_PSEUDO_LOCALE_ENABLED
#define FE8_EXPANSION_PSEUDO_LOCALE_ENABLED 0
#endif

/* --- Internal modern-build discriminator (see modern.mk) ---------------- */
/*
 * Build-provenance flag, NOT a user-facing feature flag: the modern build
 * (modern.mk) supplies -DFE8_EXPANSION_MODERN_BUILD=1 for every one of its
 * translation units, while the legacy agbcc/old_agbcc build (which never
 * receives the modern -D flags) keeps the 0 fallback below. It is
 * deliberately NOT folded into FE8_EXPANSION_CONFIG_FINGERPRINT and never
 * touches save-compatibility or ROM identity -- it only lets always-linked
 * modern-only negative-control scaffolding (e.g. the issue #6 danger/range
 * overlay semantic probe in src/playerphase.c) stay present and zero in
 * every modern build without emitting an unreferenced legacy ewram_data
 * object -- a silent orphan under ldscript.txt's per-object ewram_data
 * enumeration, which does not list src/playerphase.o. Do not gate feature
 * behaviour on this; gate always-linked provenance/negative-control state
 * only (feature writes stay gated on the feature flags below).
 */
#ifndef FE8_EXPANSION_MODERN_BUILD
#define FE8_EXPANSION_MODERN_BUILD 0
#endif

#if (FE8_EXPANSION_MODERN_BUILD != 0) && (FE8_EXPANSION_MODERN_BUILD != 1)
#error "FE8_EXPANSION_MODERN_BUILD must be 0 or 1"
#endif

/* --- Starter-feature opt-in switches (issue #6) ------------------------- */
/* See config.mk EXPANSION_MECHANICS_HOOKS, EXPANSION_MECHANICS_SAMPLE,
 * EXPANSION_DANGER_OVERLAY_MENU, and EXPANSION_STARTER_CONTENT. */
/*
 * Independent 0/1 build flags for the issue #6 starter features. Each
 * defaults to 0, so the legacy agbcc build (which never receives the modern
 * -D flags) and any default modern build link none of these features and
 * stay behaviour-identical to today's ROM. The modern build supplies each as
 * a -D define computed from config.mk's matching EXPANSION_* value (see
 * modern.mk), after scripts/modernize/expansion_config.py has validated it
 * (only 0 or 1) and folded every one of them into the config-identity
 * fingerprint. See docs/starter_features.md.
 */

/* Link the public battle-stat mechanics hook registry
 * (include/expansion_mechanics.h, src/expansion_mechanics.c). */
#ifndef FE8_EXPANSION_MECHANICS_HOOKS
#define FE8_EXPANSION_MECHANICS_HOOKS 0
#endif

/* Register the bundled sample mechanic through that registry. Requires
 * FE8_EXPANSION_MECHANICS_HOOKS (enforced below and in expansion_config.py). */
#ifndef FE8_EXPANSION_MECHANICS_SAMPLE
#define FE8_EXPANSION_MECHANICS_SAMPLE 0
#endif

/* Expose the player-facing danger/range overlay map-menu surface, reusing
 * the existing danger-zone range path (src/playerphase.c). */
#ifndef FE8_EXPANSION_DANGER_OVERLAY_MENU
#define FE8_EXPANSION_DANGER_OVERLAY_MENU 0
#endif

/* Link the bundled generated-data content example: the framework-authored
 * item ITEM_EXPANSION_CE (src/data/items_expansion.json) and the mechanic
 * that reads it, registered through the public hook registry
 * (include/expansion_starter_content.h, src/expansion_starter_content.c).
 *
 * This flag gates CONTENT BEHAVIOUR only. The item RECORD itself is owned by
 * the issue #10 ID-space platform and is generated purely from the active
 * item ID cap (FE8_ITEM_ID_CAP >= ITEM_ID_EXPANSION_FIRST), so the platform
 * stays independently testable at any cap with this flag off. */
#ifndef FE8_EXPANSION_STARTER_CONTENT
#define FE8_EXPANSION_STARTER_CONTENT 0
#endif

/* Experimental modern-build port of src/VeslyDebugger.c. */
#ifndef FE8_VESLY_DEBUGGER
#define FE8_VESLY_DEBUGGER 0
#endif

/* Modern-build port of src/DangerBones.c. */
#ifndef FE8_DANGER_BONES
#define FE8_DANGER_BONES 0
#endif

/* Custom community-sourced battle animation sets for select classes,
 * swapped in for the vanilla animation via each class's pBattleAnimDef
 * (see src/data_classes.c / src/data_banimconf.c). Purely cosmetic; no
 * gameplay/save-format effect. See CREDITS.md for the per-class attribution. */
#ifndef FE8_NEW_ANIMS
#define FE8_NEW_ANIMS 0
#endif

/* Custom community-sourced map tilesets for select chapters, swapped in for
 * the vanilla tileset via gChapterDataAssetTable (see src/data/data_8B363C.c).
 * Purely cosmetic; no gameplay/save-format effect. See CREDITS.md. */
#ifndef FE8_NEW_TILESETS
#define FE8_NEW_TILESETS 0
#endif

/* Purchasable generic-unit bases and temporary chapter gold economy. */
#ifndef FE8_PURCHASE_GENERICS
#define FE8_PURCHASE_GENERICS 0
#endif

/* Single static 256-color (8bpp) title screen background, replacing the
 * vanilla tiled 16-color background/dragon overlay. Skips the vanilla
 * dragon-flash/demon-king/logo-zoom intro sequence -- see
 * TitleScreenTryJumpIntroAnim, src/titlescreen.c. Purely cosmetic. */
#ifndef FE8_TITLE_256_COLORS
#define FE8_TITLE_256_COLORS 0
#endif

/* 224/256-colour (8bpp) conversation-background images, alongside the
 * vanilla 16-colour ones. See LoadMultipaletteConvoBg, src/eventscr2.c. */
#ifndef FE8_MULTIPALETTE_BG
#define FE8_MULTIPALETTE_BG 0
#endif

/* Procedurally generated chapter maps: a base tent per allegiance in opposite
 * quadrants, joined by a road. Overwrites the authored map terrain for any
 * chapter it accepts (see MapGen_IsEnabledForChapter). Requires
 * FE8_PURCHASE_GENERICS for the Camp/Tent trap kinds. See src/mapgen.c. */
#ifndef FE8_MAPGEN
#define FE8_MAPGEN 0
#endif

/* Mini Mug Box side window plus the C Gorgon Egg hatch phase display. */
#ifndef FE8_MMB
#define FE8_MMB 0
#endif

/* Modern-build port of ExtendWeaponDescBox (extends the item/weapon help box
 * from 3 to 5 lines). */
#ifndef FE8_EXTEND_DESC_BOX
#define FE8_EXTEND_DESC_BOX 0
#endif

/* Dynamic (1-4 line) event/conversation dialogue box sizing (src/scene.c),
 * instead of the vanilla fixed 2 lines. */
#ifndef FE8_EXTEND_DIALOGUE_BOX
#define FE8_EXTEND_DIALOGUE_BOX 0
#endif

/* PutSprite/PutSpriteExt (src/ctc.c) sprite-pool overflow bounds check. */
#ifndef FE8_OVERFLOW_SAFETY_CHECKS
#define FE8_OVERFLOW_SAFETY_CHECKS 1
#endif

/* Modern-build port of src/DisplayObtainableItem.c (icon over enemy units
 * carrying a droppable/stealable item). */
#ifndef FE8_DISPLAY_OBTAINABLE_ITEM
#define FE8_DISPLAY_OBTAINABLE_ITEM 0
#endif

/* Chapter titles drawn as text instead of a pre-rendered graphic banner
 * (see src/chapter_title.c's PutChapterTitleGfx). */
/* Per-unit temporary stat buffs/debuffs (see include/debuffs.h). */
#ifndef FE8_DEBUFFS_EXIST
#define FE8_DEBUFFS_EXIST 0
#endif

/* Repeated debuff applications continue worsening stats toward -31. */
#ifndef FE8_DEBUFFS_STACK
#define FE8_DEBUFFS_STACK 0
#endif

#if FE8_DEBUFFS_EXIST && !defined(DEBUFFS_EXIST)
#define DEBUFFS_EXIST 1
#endif

#if FE8_DEBUFFS_STACK && !defined(DEBUFFS_STACK)
#define DEBUFFS_STACK 1
#endif

/* Select toggles the first stat-screen page between stats and growths. */
#ifndef FE8_SELECT_VIEW_GROWTHS
#define FE8_SELECT_VIEW_GROWTHS 0
#endif

#if FE8_SELECT_VIEW_GROWTHS && !defined(SELECT_VIEW_GROWTHS)
#define SELECT_VIEW_GROWTHS 1
#endif

#ifndef FE8_TEXT_CHAPTER_NAMES
#define FE8_TEXT_CHAPTER_NAMES 0
#endif

/* Hit/Damage/Crit/AS numbers shown alongside the map battle info boxes
 * when battle animations are off (see ShowBattleStatsNoAnims in
 * src/mapanim_infobox.c). */
#ifndef FE8_BATTLE_STATS_NO_ANIMS
#define FE8_BATTLE_STATS_NO_ANIMS 0
#endif

/* Draw weapon-type map battle impact animations and floating damage numbers
 * during the default no-battle-animation round proc. */
#ifndef FE8_DRAW_MAP_ANIMS
#define FE8_DRAW_MAP_ANIMS 0
#endif

/* Floating battle-animation damage/heal numbers. */
#ifndef FE8_BATTLE_ANIMATION_NUMBERS
#define FE8_BATTLE_ANIMATION_NUMBERS 0
#endif

/* Per-unit HP bar and effectiveness/crit/talk warning icons on the map
 * (see src/HpBars.c). Requires FE8_DISPLAY_OBTAINABLE_ITEM=1 -- validated
 * below and in src/HpBars.c's own #error. */
#ifndef FE8_HP_BARS
#define FE8_HP_BARS 0
#endif

/* Modern-build port of the "Danger Radius" fog-of-war-aware enemy attack
 * range overlay (original hack by Huichelaar; see src/dangerradius.c).
 * Requires FE8_DISPLAY_OBTAINABLE_ITEM=1 -- shares its icon sheet
 * (validated below). */
#ifndef FE8_DANGER_RADIUS
#define FE8_DANGER_RADIUS 0
#endif

/* Group AI (ported from Pokemblem's GroupAI patch): attacking (or being
 * attacked by) a group-tagged enemy wakes the rest of its group to Charge
 * and queues them to act again this enemy phase (see src/group_ai.c). */
#ifndef FE8_GROUP_AI
#define FE8_GROUP_AI 0
#endif

/* Replaces the player-phase movement-path arrow with a pathfound move
 * straight to the cursor plus a translucent unit "ghost" at the cursor tip
 * (see src/alpha_sprite_arrow.c). */
#ifndef FE8_ALPHA_SPRITE_ARROW
#define FE8_ALPHA_SPRITE_ARROW 0
#endif

/* Weapon attack range computed from each carried weapon's own min/max
 * range (GetUnitItemEffectiveMinRange/MaxRange, src/bmitem.c) instead of
 * the vanilla-profile-only reach-bits switch in
 * GenerateUnitCompleteAttackRange (src/bmidoten.c), so a non-vanilla
 * range (e.g. 2-4) actually works. Also lets a CO's class-affinity
 * rangeBon (struct CoClassAffinity, src/power.c) shift max range for
 * real, not just display it. */
#ifndef FE8_RANGE_REWORK
#define FE8_RANGE_REWORK 0
#endif

/* Consolidates every vanilla per-action suspend-save write down to one,
 * conditional write at the start of Player Phase (see src/turn_autosave.c). */
#ifndef FE8_TURN_AUTOSAVE
#define FE8_TURN_AUTOSAVE 0
#endif

/* Generic units purchased from a Fort-terrain base spawn directly on the
 * fort tile itself (instead of an adjacent free tile) and start the turn
 * already marked as having acted. Gate/House/Throne/Village/Camp/Tent
 * purchase bases are unaffected (see src/purchase_generics.c). */
#ifndef FE8_FORT_UNITS_START_GREYED_OUT
#define FE8_FORT_UNITS_START_GREYED_OUT 0
#endif

/* Adds a "Promote" entry to the unit map action menu for level-20+ units
 * whose class has a promotion target, letting them promote without a
 * promotion item (see src/promote_command.c). */
#ifndef FE8_PROMOTE_COMMAND
#define FE8_PROMOTE_COMMAND 0
#endif

/* Clamps a unit's base stats to a sane minimum (HP >= 1, others >= 0)
 * right after character base + class base is summed, instead of leaving a
 * negative (or, for HP, exactly-0) result when that sum doesn't recover
 * (see src/bmunit.c). */
#ifndef FE8_FIX_BUGS
#define FE8_FIX_BUGS 0
#endif

/* Tracks per-chapter and per-save-slot player-unit deaths, plus enemies
 * defeated (a per-turn "power score" high-water mark and a per-chapter
 * total), so later chapters/events can reference them as a running game
 * rank (see src/gamerank.c). */
#ifndef FE8_GAME_RANK
#define FE8_GAME_RANK 0
#endif

/* Advance Wars reference: adds a "CO Powers" entry to the chapter (map)
 * menu that pans the camera onto every one of the player's units in turn,
 * parking the cursor on each for 5 frames (see src/power.c). */
#ifndef FE8_CO_POWERS
#define FE8_CO_POWERS 0
#endif

/* Emits src/febuilder_pointers.c's gFebuilderPointers[] array (this build's
 * real addresses for the tables FEBuilderGBA's ROMFE8U.cs hardcodes vanilla
 * addresses for) -- consumed by scripts/gen_custom_pointer_txt.py to
 * produce fireemblem8.custom_pointer.txt. No gameplay/save impact. */
#ifndef FE8_FEBUILDER_POINTERS
#define FE8_FEBUILDER_POINTERS 0
#endif

/* Advance Wars 2 VRAM-dump UI asset import (star/rank icons, POWER/SUPER
 * labels, debug font) as LZ77-compressed OBJ tile graphics -- see
 * src/aw2_gfx.c. No gameplay or save-format impact. */
#ifndef FE8_AW2_ASSETS
#define FE8_AW2_ASSETS 0
#endif

/* Held-button battle animation controls, ported from a standalone Lyn-hooked
 * ASM patch (asm/AnimsFastForward on disk): L+B+A skips the main loop's
 * normal VBlankIntrWait pacing so the current battle animation plays as
 * fast as the hardware allows; L+R reverses whatever the current battle
 * animation setting would have shown for just that fight. See
 * src/anims_fast_forward.c. No save-format impact. */
#ifndef FE8_ANIMS_FAST_FORWARD
#define FE8_ANIMS_FAST_FORWARD 0
#endif

/* Custom BGM support: the NIMAP2 General-MIDI instrument map (voicegroup000)
 * plus the percussion "drumfix" (voicegroups 079/080/081/083/084), and the
 * custom songs in sound/songs/bgm/ appended to gSongTable past vanilla's 1000
 * entries. Pure sound data -- no C code is compiled in or out by this flag,
 * beyond the custom song IDs in include/constants/songs.h; it is defined so
 * the config fingerprint and the generated build metadata record it like
 * every other feature flag. Note the voicegroup000 swap also changes how
 * vanilla's title theme (song001) sounds -- see config.mk's NIMAP2 block and
 * docs/custom_bgm.md. */
#ifndef FE8_NIMAP2
#define FE8_NIMAP2 0
#endif

/* Swaps in graphics/map/layout/NewPrologueMap.mar for the prologue chapter's
 * map, and replaces the prologue's scripted beginning-of-chapter events with
 * a version that still loads Eirika and Seth the same way but skips the
 * Renais-throne-room cutscene and dialogue (see src/data/data_8B363C.c and
 * src/events/prologue-eventscript.h). */
#ifndef FE8_CUSTOM_CAMPAIGN
#define FE8_CUSTOM_CAMPAIGN 0
#endif

/* Boots directly to the title screen (skips the health & safety screen,
 * Nintendo/Intelligent Systems logos, and attract-mode opening demo), and
 * on New Game skips the world-map "continent of Magvel" narration and the
 * "In an age long past..." opening text crawl (see src/gamecontrol.c and
 * src/worldmap_main.c). Does not affect continue/load. */
#ifndef FE8_SKIP_OPENING
#define FE8_SKIP_OPENING 0
#endif

/* Scrolling end-credits sequence (see src/Credits.c). */
#ifndef FE8_CREDITS
#define FE8_CREDITS 0
#endif

/* Map BGM selection becomes seeded-random instead of vanilla's fixed
 * per-chapter table lookup: GetBGMTrack() (src/bm.c, next to
 * GetCurrentMapMusicIndex(), which it wraps and falls back to when this
 * flag is off) picks a random song matching the current pick's vanilla
 * music-player/priority pair (gSongTable[].ms/.me), deterministically from
 * gPlaySt.playthroughIdentifier (an existing per-save byte -- no new save
 * data) plus the current chapter/turn/phase. Uses a private, stateless hash
 * chain, never NextRN()/gRNSeeds (the live combat RNG stream) and never the
 * shared cosmetic-FX gLCGRNValue LCG, so map BGM selection can never
 * perturb, or be perturbed by, combat rolls or weather/face/sparkle FX. See
 * docs/random_bgm.md. */
#ifndef FE8_RAND_BGM
#define FE8_RAND_BGM 0
#endif

/* Entering a battle animation no longer swaps to a distinct battle theme --
 * the current map BGM keeps playing through combat. In this codebase's own
 * decompiled FE8 sources, ordinary combat does not already trigger a BGM
 * swap (unlike the FE6/7-oriented source this was ported from); the one
 * spot that COULD force a restart is src/bmmind.c's RestoreMapSongBgm(),
 * which currently has no callers anywhere in src/. This flag makes that
 * function an explicit no-op, so map BGM is guaranteed to keep playing
 * through combat even if/when RestoreMapSongBgm() gains a caller. See
 * docs/random_bgm.md. */
#ifndef FE8_CONTINUE_BGM_BATTLE
#define FE8_CONTINUE_BGM_BATTLE 0
#endif

/* Defence in depth: the same relationships expansion_config.py rejects at
 * configure time are hard compile errors here, so a hand-passed -D (or a
 * future include-only consumer) can never build a sample with no registry,
 * or the bundled content with no registry to register it into. The content
 * flag's OTHER dependency -- an item cap that actually reaches
 * ITEM_EXPANSION_CE -- needs include/id_space.h and is therefore asserted in
 * include/expansion_starter_content.h, which owns that include. */
#if FE8_EXPANSION_MECHANICS_SAMPLE && !FE8_EXPANSION_MECHANICS_HOOKS
#error "FE8_EXPANSION_MECHANICS_SAMPLE=1 requires FE8_EXPANSION_MECHANICS_HOOKS=1"
#endif

#if FE8_EXPANSION_STARTER_CONTENT && !FE8_EXPANSION_MECHANICS_HOOKS
#error "FE8_EXPANSION_STARTER_CONTENT=1 requires FE8_EXPANSION_MECHANICS_HOOKS=1"
#endif

#if (FE8_VESLY_DEBUGGER != 0) && (FE8_VESLY_DEBUGGER != 1)
#error "FE8_VESLY_DEBUGGER must be 0 or 1"
#endif

#if (FE8_DANGER_BONES != 0) && (FE8_DANGER_BONES != 1)
#error "FE8_DANGER_BONES must be 0 or 1"
#endif

#if (FE8_NEW_ANIMS != 0) && (FE8_NEW_ANIMS != 1)
#error "FE8_NEW_ANIMS must be 0 or 1"
#endif

#if (FE8_NEW_TILESETS != 0) && (FE8_NEW_TILESETS != 1)
#error "FE8_NEW_TILESETS must be 0 or 1"
#endif

#if (FE8_PURCHASE_GENERICS != 0) && (FE8_PURCHASE_GENERICS != 1)
#error "FE8_PURCHASE_GENERICS must be 0 or 1"
#endif

#if (FE8_TITLE_256_COLORS != 0) && (FE8_TITLE_256_COLORS != 1)
#error "FE8_TITLE_256_COLORS must be 0 or 1"
#endif

#if (FE8_MULTIPALETTE_BG != 0) && (FE8_MULTIPALETTE_BG != 1)
#error "FE8_MULTIPALETTE_BG must be 0 or 1"
#endif

#if (FE8_MAPGEN != 0) && (FE8_MAPGEN != 1)
#error "FE8_MAPGEN must be 0 or 1"
#endif

#if FE8_MAPGEN && !FE8_PURCHASE_GENERICS
#error "FE8_MAPGEN requires FE8_PURCHASE_GENERICS (Camp/Tent trap kinds)"
#endif

#if (FE8_MMB != 0) && (FE8_MMB != 1)
#error "FE8_MMB must be 0 or 1"
#endif

#if (FE8_EXTEND_DESC_BOX != 0) && (FE8_EXTEND_DESC_BOX != 1)
#error "FE8_EXTEND_DESC_BOX must be 0 or 1"
#endif

#if (FE8_EXTEND_DIALOGUE_BOX != 0) && (FE8_EXTEND_DIALOGUE_BOX != 1)
#error "FE8_EXTEND_DIALOGUE_BOX must be 0 or 1"
#endif

#if (FE8_OVERFLOW_SAFETY_CHECKS != 0) && (FE8_OVERFLOW_SAFETY_CHECKS != 1)
#error "FE8_OVERFLOW_SAFETY_CHECKS must be 0 or 1"
#endif

#if (FE8_DISPLAY_OBTAINABLE_ITEM != 0) && (FE8_DISPLAY_OBTAINABLE_ITEM != 1)
#error "FE8_DISPLAY_OBTAINABLE_ITEM must be 0 or 1"
#endif

#if (FE8_DEBUFFS_EXIST != 0) && (FE8_DEBUFFS_EXIST != 1)
#error "FE8_DEBUFFS_EXIST must be 0 or 1"
#endif

#if (FE8_DEBUFFS_STACK != 0) && (FE8_DEBUFFS_STACK != 1)
#error "FE8_DEBUFFS_STACK must be 0 or 1"
#endif

#if FE8_DEBUFFS_STACK && !FE8_DEBUFFS_EXIST
#error "FE8_DEBUFFS_STACK=1 requires FE8_DEBUFFS_EXIST=1"
#endif

#if (FE8_SELECT_VIEW_GROWTHS != 0) && (FE8_SELECT_VIEW_GROWTHS != 1)
#error "FE8_SELECT_VIEW_GROWTHS must be 0 or 1"
#endif

#if (FE8_TEXT_CHAPTER_NAMES != 0) && (FE8_TEXT_CHAPTER_NAMES != 1)
#error "FE8_TEXT_CHAPTER_NAMES must be 0 or 1"
#endif

#if (FE8_BATTLE_STATS_NO_ANIMS != 0) && (FE8_BATTLE_STATS_NO_ANIMS != 1)
#error "FE8_BATTLE_STATS_NO_ANIMS must be 0 or 1"
#endif

#if (FE8_DRAW_MAP_ANIMS != 0) && (FE8_DRAW_MAP_ANIMS != 1)
#error "FE8_DRAW_MAP_ANIMS must be 0 or 1"
#endif

#if (FE8_BATTLE_ANIMATION_NUMBERS != 0) && (FE8_BATTLE_ANIMATION_NUMBERS != 1)
#error "FE8_BATTLE_ANIMATION_NUMBERS must be 0 or 1"
#endif

#if (FE8_HP_BARS != 0) && (FE8_HP_BARS != 1)
#error "FE8_HP_BARS must be 0 or 1"
#endif

#if FE8_HP_BARS && !FE8_DISPLAY_OBTAINABLE_ITEM
#error "FE8_HP_BARS=1 requires FE8_DISPLAY_OBTAINABLE_ITEM=1"
#endif

#if (FE8_DANGER_RADIUS != 0) && (FE8_DANGER_RADIUS != 1)
#error "FE8_DANGER_RADIUS must be 0 or 1"
#endif

#if FE8_DANGER_RADIUS && !FE8_DISPLAY_OBTAINABLE_ITEM
#error "FE8_DANGER_RADIUS=1 requires FE8_DISPLAY_OBTAINABLE_ITEM=1"
#endif

#if (FE8_GROUP_AI != 0) && (FE8_GROUP_AI != 1)
#error "FE8_GROUP_AI must be 0 or 1"
#endif

#if (FE8_ALPHA_SPRITE_ARROW != 0) && (FE8_ALPHA_SPRITE_ARROW != 1)
#error "FE8_ALPHA_SPRITE_ARROW must be 0 or 1"
#endif

#if (FE8_RANGE_REWORK != 0) && (FE8_RANGE_REWORK != 1)
#error "FE8_RANGE_REWORK must be 0 or 1"
#endif

#if (FE8_FORT_UNITS_START_GREYED_OUT != 0) && (FE8_FORT_UNITS_START_GREYED_OUT != 1)
#error "FE8_FORT_UNITS_START_GREYED_OUT must be 0 or 1"
#endif

#if (FE8_PROMOTE_COMMAND != 0) && (FE8_PROMOTE_COMMAND != 1)
#error "FE8_PROMOTE_COMMAND must be 0 or 1"
#endif

#if (FE8_FIX_BUGS != 0) && (FE8_FIX_BUGS != 1)
#error "FE8_FIX_BUGS must be 0 or 1"
#endif

#if (FE8_TURN_AUTOSAVE != 0) && (FE8_TURN_AUTOSAVE != 1)
#error "FE8_TURN_AUTOSAVE must be 0 or 1"
#endif

#if (FE8_GAME_RANK != 0) && (FE8_GAME_RANK != 1)
#error "FE8_GAME_RANK must be 0 or 1"
#endif

#if (FE8_CO_POWERS != 0) && (FE8_CO_POWERS != 1)
#error "FE8_CO_POWERS must be 0 or 1"
#endif

#if (FE8_FEBUILDER_POINTERS != 0) && (FE8_FEBUILDER_POINTERS != 1)
#error "FE8_FEBUILDER_POINTERS must be 0 or 1"
#endif

#if (FE8_AW2_ASSETS != 0) && (FE8_AW2_ASSETS != 1)
#error "FE8_AW2_ASSETS must be 0 or 1"
#endif

#if (FE8_ANIMS_FAST_FORWARD != 0) && (FE8_ANIMS_FAST_FORWARD != 1)
#error "FE8_ANIMS_FAST_FORWARD must be 0 or 1"
#endif

#if (FE8_NIMAP2 != 0) && (FE8_NIMAP2 != 1)
#error "FE8_NIMAP2 must be 0 or 1"
#endif

#if (FE8_CUSTOM_CAMPAIGN != 0) && (FE8_CUSTOM_CAMPAIGN != 1)
#error "FE8_CUSTOM_CAMPAIGN must be 0 or 1"
#endif

#if (FE8_SKIP_OPENING != 0) && (FE8_SKIP_OPENING != 1)
#error "FE8_SKIP_OPENING must be 0 or 1"
#endif

#if (FE8_CREDITS != 0) && (FE8_CREDITS != 1)
#error "FE8_CREDITS must be 0 or 1"
#endif

#if (FE8_RAND_BGM != 0) && (FE8_RAND_BGM != 1)
#error "FE8_RAND_BGM must be 0 or 1"
#endif

#if (FE8_CONTINUE_BGM_BATTLE != 0) && (FE8_CONTINUE_BGM_BATTLE != 1)
#error "FE8_CONTINUE_BGM_BATTLE must be 0 or 1"
#endif

#endif /* GUARD_EXPANSION_CONFIG_H */
