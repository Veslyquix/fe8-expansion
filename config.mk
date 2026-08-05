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
EXPANSION_SAVE_COMPAT_EPOCH ?= 2

# --- Localization (issue #18) -----------------------------------------------
# EXPANSION_ENABLED_LOCALES -- comma-separated stable locale ids (see
#   scripts/localization/schema.py's LOCALE_IDS) enabled for this build; must
#   include "en" and must not repeat an id. Legal profile ids are "en", "ja",
#   "zh-Hans", and "qps-ploc" (an ASCII pseudo-locale test harness, never a
#   real translation -- see scripts/localization/pseudo.py). Enabling "ja" or
#   "zh-Hans" requires MODERN_ROM_SIZE=32M for the dedicated upper-ROM locale
#   bank; this is configuration/layout foundation only, not a claim that CJK
#   catalogs, fonts, codecs, or runtime rendering are complete.
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
