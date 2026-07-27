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
 */
#ifndef FE8_EXPANSION_SAVE_COMPAT_EPOCH
#define FE8_EXPANSION_SAVE_COMPAT_EPOCH 1
#endif

/* --- Starter-feature opt-in switches (issue #6) ------------------------- */
/* See config.mk EXPANSION_MECHANICS_HOOKS, EXPANSION_MECHANICS_SAMPLE, and
 * EXPANSION_DANGER_OVERLAY_MENU. */
/*
 * Independent 0/1 build flags for the issue #6 starter-feature foundation.
 * Each defaults to 0, so the legacy agbcc build (which never receives the
 * modern -D flags) and any default modern build link none of these features
 * and stay byte/behaviour identical to today's ROM. The modern build
 * supplies each as a -D define computed from config.mk's matching
 * EXPANSION_* value (see modern.mk), after
 * scripts/modernize/expansion_config.py has validated it (only 0 or 1) and
 * folded all three into the config-identity fingerprint. See
 * docs/starter_features.md.
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

/* Defence in depth: the same relationship expansion_config.py rejects at
 * configure time is a hard compile error here, so a hand-passed -D (or a
 * future include-only consumer) can never build a sample with no registry. */
#if FE8_EXPANSION_MECHANICS_SAMPLE && !FE8_EXPANSION_MECHANICS_HOOKS
#error "FE8_EXPANSION_MECHANICS_SAMPLE=1 requires FE8_EXPANSION_MECHANICS_HOOKS=1"
#endif

#endif /* GUARD_EXPANSION_CONFIG_H */
