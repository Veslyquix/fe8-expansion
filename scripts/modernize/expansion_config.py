#!/usr/bin/env python3
"""Central expansion framework configuration/identity tool (issue #8).

Owns the validation and resolution logic for config.mk's semantic version
and GBA ROM identity fields, plus the two values config.mk cannot express
by itself: the deterministic build commit and the config identity
fingerprint. This is the single source of truth consumed by:

  * modern.mk (via the `resolve` and `generate` subcommands) to validate
    every modern build before any C/assembly compilation or linking, and to
    feed `-D` command-line defines for include/expansion_config.h.
  * scripts/modernize/finalize_rom_header.py, which patches a built ROM's
    header identity fields and regenerates the checksum from the same
    generated expansion_build_metadata.json.
  * scripts/modernize/verify_rom_header.py, which verifies both the header
    and the embedded ExpansionMetadata record (see
    include/expansion_metadata.h) against that same JSON.

Deliberately dependency-free (Python stdlib only), matching this
repository's existing scripts/modernize/*.py tools.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

# scripts/localization/schema.py is the single source of truth for the
# stable locale id list (issue #18 sprint 1); this tool only validates and
# encodes EXPANSION_ENABLED_LOCALES/EXPANSION_DEFAULT_LOCALE/
# EXPANSION_PSEUDO_LOCALE against that same list, never a private copy.
_REPO_ROOT_FOR_LOCALE_SCHEMA = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_FOR_LOCALE_SCHEMA) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_LOCALE_SCHEMA))
from scripts.localization import schema as locale_schema  # noqa: E402

# --- Field constraints (see docs/config_identity.md) -----------------------

ASCII_MIN = 0x20
ASCII_MAX = 0x7E

ROM_TITLE_MAX_LEN = 12
ROM_GAME_CODE_LEN = 4
ROM_MAKER_CODE_LEN = 2
ROM_REVISION_MIN = 0
ROM_REVISION_MAX = 255
VERSION_COMPONENT_MIN = 0
VERSION_COMPONENT_MAX = 255

# The save-compatibility epoch/key is stored as a u16 in
# include/save_format.h's ExpansionSaveMeta record.
SAVE_COMPAT_EPOCH_MIN = 0
SAVE_COMPAT_EPOCH_MAX = 0xFFFF

# Starter-feature opt-in flags (issue #6) are strict 0/1 build switches:
# any other value (-1, 2, text) is rejected with an actionable message.
FEATURE_FLAG_MIN = 0
FEATURE_FLAG_MAX = 1

# Item ID cap boundary the issue #6 starter *content* flag depends on.
# scripts/generated_data/idspace.py owns these numbers (ITEM domain
# `default_cap` / `ITEM_EXPANSION_FIRST`); they are restated here because
# this tool is deliberately import-free (it runs as a bare script from
# modern.mk, not as a package module). scripts/modernize/tests/
# test_expansion_config.py asserts the two definitions stay equal, so a
# future cap change cannot silently desynchronize them.
ITEM_ID_DEFAULT_CAP = 0xCD
ITEM_ID_EXPANSION_FIRST = 0xCE

# Named ROM sizes, matching modern.mk's MODERN_ROM_SIZE values.
NAMED_ROM_SIZES = {"16M": 16 * 1024 * 1024, "32M": 32 * 1024 * 1024}

SUPPORTED_PRESETS = ("debug", "release")
SUPPORTED_ABIS = ("aapcs", "apcs-gnu")

# A build id override must look like a git commit SHA (or short prefix):
# hex digits only. This rejects timestamps, branch names, and arbitrary
# strings, matching the "never a timestamp or branch name" requirement.
BUILD_ID_OVERRIDE_PATTERN = re.compile(r"^[0-9a-fA-F]{4,40}$")

# First N hex characters of a SHA-256 digest used as the config fingerprint.
FINGERPRINT_LEN = 16

# config.mk's fixed set of simple scalar assignments this tool understands.
CONFIG_MK_KEYS = (
    "EXPANSION_VERSION_MAJOR",
    "EXPANSION_VERSION_MINOR",
    "EXPANSION_VERSION_PATCH",
    "EXPANSION_ROM_TITLE",
    "EXPANSION_ROM_GAME_CODE",
    "EXPANSION_ROM_MAKER_CODE",
    "EXPANSION_ROM_REVISION",
    "EXPANSION_BUILD_ID",
    "EXPANSION_SAVE_COMPAT_EPOCH",
    "EXPANSION_ENABLED_LOCALES",
    "EXPANSION_DEFAULT_LOCALE",
    "EXPANSION_PSEUDO_LOCALE",
)

# Optional starter-feature flag keys (issue #6). Unlike CONFIG_MK_KEYS these
# are NOT required to be present: a config.mk (or a synthetic test fixture)
# that omits them is treated exactly as if each were 0, matching config.mk's
# own `?= 0` default. This keeps the blast radius of adding the flags to a
# single new source (config.mk) instead of every committed/synthetic fixture.
CONFIG_MK_FEATURE_KEYS = (
    "EXPANSION_MECHANICS_HOOKS",
    "EXPANSION_MECHANICS_SAMPLE",
    "EXPANSION_DANGER_OVERLAY_MENU",
    "EXPANSION_STARTER_CONTENT",
    "VESLY_DEBUGGER",
    "DANGER_BONES",
    "NEW_ANIMS",
    "NEW_TILESETS",
    "PURCHASE_GENERICS",
    "MMB",
    "DEBUFFS_EXIST",
    "DEBUFFS_STACK",
    "SELECT_VIEW_GROWTHS",
    "CUSTOM_CAMPAIGN",
    "SKIP_OPENING",
    "RAND_BGM",
    "CONTINUE_BGM_BATTLE",
)

_ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*[:?+]?=\s*(.*?)\s*$")


class ConfigError(ValueError):
    """A configuration value is invalid, or an incompatible combination was given."""


# --- Field validation --------------------------------------------------------


def _is_ascii_printable(text: str) -> bool:
    return all(ASCII_MIN <= ord(ch) <= ASCII_MAX for ch in text)


def validate_title(title: str) -> str:
    if not isinstance(title, str) or not title:
        raise ConfigError("EXPANSION_ROM_TITLE must be a non-empty string")
    if len(title) > ROM_TITLE_MAX_LEN:
        raise ConfigError(
            f"EXPANSION_ROM_TITLE {title!r} is {len(title)} bytes; the GBA "
            f"header title field holds at most {ROM_TITLE_MAX_LEN} bytes"
        )
    if not _is_ascii_printable(title):
        raise ConfigError(f"EXPANSION_ROM_TITLE {title!r} must be printable ASCII")
    return title


def validate_game_code(code: str) -> str:
    if not isinstance(code, str) or len(code) != ROM_GAME_CODE_LEN:
        raise ConfigError(
            f"EXPANSION_ROM_GAME_CODE {code!r} must be exactly "
            f"{ROM_GAME_CODE_LEN} ASCII bytes"
        )
    if not _is_ascii_printable(code):
        raise ConfigError(f"EXPANSION_ROM_GAME_CODE {code!r} must be printable ASCII")
    return code


def validate_maker_code(code: str) -> str:
    if not isinstance(code, str) or len(code) != ROM_MAKER_CODE_LEN:
        raise ConfigError(
            f"EXPANSION_ROM_MAKER_CODE {code!r} must be exactly "
            f"{ROM_MAKER_CODE_LEN} ASCII bytes"
        )
    if not _is_ascii_printable(code):
        raise ConfigError(f"EXPANSION_ROM_MAKER_CODE {code!r} must be printable ASCII")
    return code


def validate_revision(value) -> int:
    try:
        revision = int(str(value).strip(), 0)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"EXPANSION_ROM_REVISION {value!r} is not an integer") from error
    if not (ROM_REVISION_MIN <= revision <= ROM_REVISION_MAX):
        raise ConfigError(
            f"EXPANSION_ROM_REVISION {revision} out of range "
            f"[{ROM_REVISION_MIN}, {ROM_REVISION_MAX}]"
        )
    return revision


def validate_save_compat_epoch(value) -> int:
    """Validate EXPANSION_SAVE_COMPAT_EPOCH (see include/save_format.h's
    FE8_EXPANSION_SAVE_COMPAT_EPOCH and docs/save_format.md). Deliberately a
    separate, independent value from the framework semantic version and the
    config fingerprint -- see config.mk's comment for exactly when to bump
    it."""
    try:
        epoch = int(str(value).strip(), 0)
    except (TypeError, ValueError) as error:
        raise ConfigError(
            f"EXPANSION_SAVE_COMPAT_EPOCH {value!r} is not an integer"
        ) from error
    if not (SAVE_COMPAT_EPOCH_MIN <= epoch <= SAVE_COMPAT_EPOCH_MAX):
        raise ConfigError(
            f"EXPANSION_SAVE_COMPAT_EPOCH {epoch} out of range "
            f"[{SAVE_COMPAT_EPOCH_MIN}, {SAVE_COMPAT_EPOCH_MAX}]"
        )
    return epoch


def _normalize_locale_list(value) -> Tuple[str, ...]:
    """Splits a comma-separated EXPANSION_ENABLED_LOCALES string (or accepts
    an already-iterable value, for programmatic callers/tests) into a plain
    tuple of trimmed, non-empty tokens -- no dedup/order/membership
    validation yet, that is validate_enabled_locales's job."""
    if isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        text = str(value).strip()
        raw_items = [item.strip() for item in text.split(",")] if text else []
    return tuple(item for item in raw_items if item)


def validate_enabled_locales(value) -> Tuple[str, ...]:
    """Validate EXPANSION_ENABLED_LOCALES (see config.mk and
    scripts/localization/schema.py's LOCALE_IDS/CONFIGURABLE_LOCALES).

    Fails early (ConfigError) on: an empty list, any locale id outside the
    stable locale_schema.LOCALE_IDS set, a repeated locale id, a missing
    'en', or any locale not yet configurable. Japanese and Simplified Chinese
    are production-configurable; validate_locale_rom_size separately requires
    their builds to use the 32 MiB profile. On success, returns the enabled
    set normalized into the fixed stable-id order (locale_schema.LOCALE_IDS'
    order), independent of the input order, so two configs naming the same
    set in a different order are identical from here on (fingerprint
    included).
    """
    items = _normalize_locale_list(value)
    if not items:
        raise ConfigError("EXPANSION_ENABLED_LOCALES must not be empty")

    unknown = [item for item in items if item not in locale_schema.LOCALE_INDEX]
    if unknown:
        raise ConfigError(
            f"EXPANSION_ENABLED_LOCALES contains unknown locale id(s) {unknown!r}; "
            f"expected a subset of {locale_schema.LOCALE_IDS}"
        )

    seen = set()
    duplicates = []
    for item in items:
        if item in seen:
            duplicates.append(item)
        seen.add(item)
    if duplicates:
        raise ConfigError(
            f"EXPANSION_ENABLED_LOCALES contains duplicate locale id(s) {duplicates!r}"
        )

    if "en" not in seen:
        raise ConfigError("EXPANSION_ENABLED_LOCALES must include 'en'")

    unsupported = sorted(
        item for item in seen if item not in locale_schema.CONFIGURABLE_LOCALES
    )
    if unsupported:
        raise ConfigError(
            f"EXPANSION_ENABLED_LOCALES contains locale id(s) not yet configurable: "
            f"{unsupported!r}; expected a subset of "
            f"{locale_schema.CONFIGURABLE_LOCALES}. Other stable locale ids remain "
            f"reserved for future profiles"
        )

    return tuple(sorted(seen, key=lambda name: locale_schema.LOCALE_INDEX[name]))


def validate_default_locale(value, enabled_locales: Tuple[str, ...]) -> str:
    """Validate EXPANSION_DEFAULT_LOCALE: must be one of the stable locale
    ids, and must be a member of the already-validated `enabled_locales`
    set (a build can never default to a locale it does not enable)."""
    text = str(value).strip()
    if text not in locale_schema.LOCALE_INDEX:
        raise ConfigError(
            f"EXPANSION_DEFAULT_LOCALE {value!r} unknown; expected one of "
            f"{locale_schema.LOCALE_IDS}"
        )
    if text not in enabled_locales:
        raise ConfigError(
            f"EXPANSION_DEFAULT_LOCALE {text!r} must be included in "
            f"EXPANSION_ENABLED_LOCALES ({enabled_locales!r})"
        )
    return text


def validate_pseudo_locale(value, enabled_locales: Tuple[str, ...]) -> int:
    """Validate EXPANSION_PSEUDO_LOCALE: must be the literal string '0' or
    '1' (never a truthy-ish alternative like 'yes'/'true'/'2'), and must be
    exactly consistent with whether locale_schema.PSEUDO_LOCALE
    ('qps-ploc') is present in the already-validated `enabled_locales` set
    -- 1 requires qps-ploc enabled, 0 requires it not enabled. This keeps
    the flag from ever silently disagreeing with the enabled-locale set it
    describes."""
    text = str(value).strip()
    if text not in ("0", "1"):
        raise ConfigError(f"EXPANSION_PSEUDO_LOCALE {value!r} must be exactly '0' or '1'")
    flag = int(text)
    qps_enabled = locale_schema.PSEUDO_LOCALE in enabled_locales
    if flag == 1 and not qps_enabled:
        raise ConfigError(
            f"EXPANSION_PSEUDO_LOCALE=1 requires {locale_schema.PSEUDO_LOCALE!r} to be "
            f"present in EXPANSION_ENABLED_LOCALES ({enabled_locales!r})"
        )
    if flag == 0 and qps_enabled:
        raise ConfigError(
            f"EXPANSION_PSEUDO_LOCALE=0 but {locale_schema.PSEUDO_LOCALE!r} is present in "
            f"EXPANSION_ENABLED_LOCALES ({enabled_locales!r}); set EXPANSION_PSEUDO_LOCALE=1 "
            f"or remove it from EXPANSION_ENABLED_LOCALES"
        )
    return flag


def validate_locale_rom_size(
    enabled_locales: Tuple[str, ...], rom_size_bytes: int
) -> None:
    """Internal future-profile guard for the dedicated upper-ROM CJK bank."""
    cjk_locales = tuple(
        locale
        for locale in locale_schema.REAL_CJK_LOCALES
        if locale in enabled_locales
    )
    required_size = NAMED_ROM_SIZES["32M"]
    if cjk_locales and rom_size_bytes != required_size:
        raise ConfigError(
            f"EXPANSION_ENABLED_LOCALES enables real CJK locale(s) "
            f"{cjk_locales!r}, which require MODERN_ROM_SIZE=32M "
            f"({required_size} bytes); got {rom_size_bytes} bytes. "
            f"Use MODERN_ROM_SIZE=32M or remove {cjk_locales!r}"
        )


def validate_feature_flag(name: str, value) -> int:
    """Validate a starter-feature opt-in flag (issue #6): strictly 0 or 1.

    Any other value -- a negative number, 2, or non-numeric text -- is
    rejected with a specific, actionable message, matching the rest of this
    tool's fail-before-writing-anything contract.
    """
    try:
        flag = int(str(value).strip(), 0)
    except (TypeError, ValueError) as error:
        raise ConfigError(
            f"{name} {value!r} is not an integer; expected 0 or 1"
        ) from error
    if not (FEATURE_FLAG_MIN <= flag <= FEATURE_FLAG_MAX):
        raise ConfigError(
            f"{name} {flag} out of range [{FEATURE_FLAG_MIN}, {FEATURE_FLAG_MAX}]; "
            f"expected 0 (off) or 1 (on)"
        )
    return flag


def compute_locale_mask(enabled_locales: Tuple[str, ...]) -> int:
    """Bitmask over locale_schema.LOCALE_INDEX -- bit N set iff
    locale_schema.LOCALE_IDS[N] is enabled. Matches
    ExpansionLocale_IsEnabled()'s `FE8_EXPANSION_ENABLED_LOCALE_MASK &
    (1u << locale)` check in src/expansion_locale.c exactly."""
    mask = 0
    for name in enabled_locales:
        mask |= 1 << locale_schema.LOCALE_INDEX[name]
    return mask
def validate_item_id_cap(value) -> int:
    """Resolve the active item ID cap (modern.mk's FE8_ITEM_ID_CAP).

    An empty/None value means "not overridden", i.e. the committed default
    cap in include/id_space.h. Anything else must be an integer in
    [0, 0xFF] (the item ID storage width, see
    scripts/generated_data/idspace.py's item domain).
    """
    if value in (None, ""):
        return ITEM_ID_DEFAULT_CAP
    try:
        cap = int(str(value).strip(), 0)
    except (TypeError, ValueError) as error:
        raise ConfigError(
            f"FE8_ITEM_ID_CAP {value!r} is not an integer"
        ) from error
    if not (0 <= cap <= 0xFF):
        raise ConfigError(
            f"FE8_ITEM_ID_CAP 0x{cap:X} out of range [0x00, 0xFF]; the item ID "
            f"storage width is 8 bits (see scripts/generated_data/idspace.py)"
        )
    return cap


def validate_feature_flags(mechanics_hooks, mechanics_sample, danger_overlay_menu,
                           starter_content=0, vesly_debugger=0, danger_bones=0,
                           new_anims=0, new_tilesets=0,
                           purchase_generics=0, mmb=0, extend_desc_box=0,
                           extend_dialogue_box=0,
                           overflow_safety_checks=1, display_obtainable_item=0,
                           debuffs_exist=0, debuffs_stack=0,
                           select_view_growths=0,
                           text_chapter_names=0, battle_stats_no_anims=0,
                           draw_map_anims=0, hp_bars=0, group_ai=0, alpha_sprite_arrow=0, turn_autosave=0,
                           fort_units_start_greyed_out=0, promote_command=0, fix_bugs=0, credits=0,
                           custom_campaign=0, skip_opening=0, game_rank=0, co_powers=0,
                           febuilder_pointers=0, aw2_assets=0, anims_fast_forward=0,
                           nimap2=0,
                           rand_bgm=0, continue_bgm_battle=0,
                           item_id_cap=None):
    """Validate the three starter-feature flags plus their one dependency.

    The sample mechanic can only be registered through the mechanics hook
    registry, so EXPANSION_MECHANICS_SAMPLE=1 with EXPANSION_MECHANICS_HOOKS=0
    is a contradiction and is rejected here (an actionable error), rather than
    silently linking a sample with no registry to register it into.
    """
    hooks = validate_feature_flag("EXPANSION_MECHANICS_HOOKS", mechanics_hooks)
    sample = validate_feature_flag("EXPANSION_MECHANICS_SAMPLE", mechanics_sample)
    danger = validate_feature_flag("EXPANSION_DANGER_OVERLAY_MENU", danger_overlay_menu)
    content = validate_feature_flag("EXPANSION_STARTER_CONTENT", starter_content)
    debugger = validate_feature_flag("VESLY_DEBUGGER", vesly_debugger)
    bones = validate_feature_flag("DANGER_BONES", danger_bones)
    anims = validate_feature_flag("NEW_ANIMS", new_anims)
    tilesets = validate_feature_flag("NEW_TILESETS", new_tilesets)
    generics = validate_feature_flag("PURCHASE_GENERICS", purchase_generics)
    mmb_flag = validate_feature_flag("MMB", mmb)
    desc_box = validate_feature_flag("EXTEND_DESC_BOX", extend_desc_box)
    dialogue_box = validate_feature_flag("EXTEND_DIALOGUE_BOX", extend_dialogue_box)
    overflow_checks = validate_feature_flag("OVERFLOW_SAFETY_CHECKS", overflow_safety_checks)
    obtainable_item = validate_feature_flag("DISPLAY_OBTAINABLE_ITEM", display_obtainable_item)
    debuffs = validate_feature_flag("DEBUFFS_EXIST", debuffs_exist)
    debuffs_stack_flag = validate_feature_flag("DEBUFFS_STACK", debuffs_stack)
    select_growths = validate_feature_flag("SELECT_VIEW_GROWTHS", select_view_growths)
    ch_names = validate_feature_flag("TEXT_CHAPTER_NAMES", text_chapter_names)
    battle_stats = validate_feature_flag("BATTLE_STATS_NO_ANIMS", battle_stats_no_anims)
    draw_map = validate_feature_flag("DRAW_MAP_ANIMS", draw_map_anims)
    bars = validate_feature_flag("HP_BARS", hp_bars)
    group_ai_flag = validate_feature_flag("GROUP_AI", group_ai)
    alpha_sprite_arrow_flag = validate_feature_flag("ALPHA_SPRITE_ARROW", alpha_sprite_arrow)
    autosave_flag = validate_feature_flag("TURN_AUTOSAVE", turn_autosave)
    fort_greyed_flag = validate_feature_flag("FORT_UNITS_START_GREYED_OUT", fort_units_start_greyed_out)
    promote_command_flag = validate_feature_flag("PROMOTE_COMMAND", promote_command)
    fix_bugs_flag = validate_feature_flag("FIX_BUGS", fix_bugs)
    credits_flag = validate_feature_flag("CREDITS", credits)
    campaign = validate_feature_flag("CUSTOM_CAMPAIGN", custom_campaign)
    skip_opening_flag = validate_feature_flag("SKIP_OPENING", skip_opening)
    game_rank_flag = validate_feature_flag("GAME_RANK", game_rank)
    co_powers_flag = validate_feature_flag("CO_POWERS", co_powers)
    febuilder_pointers_flag = validate_feature_flag("FEBUILDER_POINTERS", febuilder_pointers)
    aw2_assets_flag = validate_feature_flag("AW2_ASSETS", aw2_assets)
    anims_fast_forward_flag = validate_feature_flag("ANIMS_FAST_FORWARD", anims_fast_forward)
    nimap2_flag = validate_feature_flag("NIMAP2", nimap2)
    rand_bgm_flag = validate_feature_flag("RAND_BGM", rand_bgm)
    continue_bgm_battle_flag = validate_feature_flag("CONTINUE_BGM_BATTLE", continue_bgm_battle)
    cap = validate_item_id_cap(item_id_cap)
    if sample and not hooks:
        raise ConfigError(
            "EXPANSION_MECHANICS_SAMPLE=1 requires EXPANSION_MECHANICS_HOOKS=1: "
            "the sample mechanic is registered through the mechanics hook "
            "registry, which is not linked when EXPANSION_MECHANICS_HOOKS=0"
        )
    if content and not hooks:
        raise ConfigError(
            "EXPANSION_STARTER_CONTENT=1 requires EXPANSION_MECHANICS_HOOKS=1: "
            "the bundled content item's mechanic is registered through the "
            "mechanics hook registry, which is not linked when "
            "EXPANSION_MECHANICS_HOOKS=0"
        )
    if content and cap < ITEM_ID_EXPANSION_FIRST:
        raise ConfigError(
            f"EXPANSION_STARTER_CONTENT=1 requires an expanded item ID cap: the "
            f"bundled content item is ITEM_EXPANSION_CE "
            f"(0x{ITEM_ID_EXPANSION_FIRST:02X}) and the active cap is "
            f"0x{cap:02X}; build with FE8_ITEM_ID_CAP=0x"
            f"{ITEM_ID_EXPANSION_FIRST:02X} (or higher)"
        )
    if debuffs_stack_flag and not debuffs:
        raise ConfigError(
            "DEBUFFS_STACK=1 requires DEBUFFS_EXIST=1: repeated debuff "
            "applications require the per-unit debuff storage to be linked"
        )
    if bars and not obtainable_item:
        raise ConfigError(
            "HP_BARS=1 requires DISPLAY_OBTAINABLE_ITEM=1: the HP-bar and "
            "warning-icon tiles it draws live in the icon sheet that flag "
            "loads"
        )
    return (hooks, sample, danger, content, debugger, bones, anims, tilesets, generics, mmb_flag, desc_box,
            overflow_checks, obtainable_item, debuffs, debuffs_stack_flag,
            select_growths, ch_names, battle_stats, draw_map, bars, group_ai_flag, alpha_sprite_arrow_flag,
            autosave_flag, fort_greyed_flag, promote_command_flag, fix_bugs_flag, credits_flag, campaign, skip_opening_flag,
            game_rank_flag, co_powers_flag, febuilder_pointers_flag, aw2_assets_flag,
            anims_fast_forward_flag, nimap2_flag, rand_bgm_flag, continue_bgm_battle_flag,
            dialogue_box)


def validate_rom_size(value) -> int:
    text = str(value).strip()
    named = NAMED_ROM_SIZES.get(text.upper())
    if named is not None:
        return named
    try:
        size = int(text, 0)
    except ValueError as error:
        allowed = ", ".join(sorted(NAMED_ROM_SIZES))
        raise ConfigError(
            f"MODERN_ROM_SIZE {value!r} invalid; expected one of "
            f"[{allowed}] or an exact byte count"
        ) from error
    if size not in NAMED_ROM_SIZES.values():
        allowed = ", ".join(sorted(NAMED_ROM_SIZES))
        raise ConfigError(
            f"MODERN_ROM_SIZE {value!r} ({size} bytes) is not a supported "
            f"size; expected one of [{allowed}]"
        )
    return size


def _validate_version_component(name: str, value) -> int:
    try:
        component = int(str(value).strip(), 0)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{name} {value!r} is not an integer") from error
    if not (VERSION_COMPONENT_MIN <= component <= VERSION_COMPONENT_MAX):
        raise ConfigError(
            f"{name} {component} out of range "
            f"[{VERSION_COMPONENT_MIN}, {VERSION_COMPONENT_MAX}]"
        )
    return component


def validate_version(major, minor, patch) -> Tuple[int, int, int]:
    return (
        _validate_version_component("EXPANSION_VERSION_MAJOR", major),
        _validate_version_component("EXPANSION_VERSION_MINOR", minor),
        _validate_version_component("EXPANSION_VERSION_PATCH", patch),
    )


def validate_preset(preset: str) -> str:
    if preset not in SUPPORTED_PRESETS:
        raise ConfigError(
            f"MODERN_CONFIG {preset!r} unsupported; expected one of {SUPPORTED_PRESETS}"
        )
    return preset


def validate_abi(abi: str) -> str:
    if abi not in SUPPORTED_ABIS:
        raise ConfigError(f"MODERN_ABI {abi!r} unsupported; expected one of {SUPPORTED_ABIS}")
    return abi


def validate_text_shift(value) -> int:
    text = str(value).strip()
    try:
        shift = int(text, 0)
    except ValueError as error:
        raise ConfigError(f"MODERN_TEXT_SHIFT {value!r} is not a valid number") from error
    if shift % 4 != 0:
        raise ConfigError(f"MODERN_TEXT_SHIFT {value!r} must be 4-byte aligned")
    return shift


def validate_build_id_override(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    if not BUILD_ID_OVERRIDE_PATTERN.fullmatch(value):
        raise ConfigError(
            f"EXPANSION_BUILD_ID {value!r} must be 4-40 hex characters (a git "
            f"commit SHA or SHA prefix); timestamps and branch names are not allowed"
        )
    return value.lower()


# --- config.mk parsing -------------------------------------------------------


def parse_config_mk(path: Path) -> Dict[str, str]:
    """Parse config.mk's simple `KEY := VALUE` / `KEY ?= VALUE` assignments.

    Only the fixed, documented set of scalar identity/version keys is
    recognized (CONFIG_MK_KEYS); config.mk must keep these as simple literal
    assignments with no Make function calls or variable references, so this
    tiny parser -- deliberately not a full Make evaluator -- stays correct.
    Comments (#...) and blank lines are ignored.
    """
    if not path.is_file():
        raise ConfigError(f"config.mk not found: {path}")
    values: Dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = _ASSIGNMENT_RE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2)
        if key in CONFIG_MK_KEYS or key in CONFIG_MK_FEATURE_KEYS:
            values[key] = value
    missing = [key for key in CONFIG_MK_KEYS if key not in values]
    if missing:
        raise ConfigError(f"{path} is missing required assignment(s): {', '.join(missing)}")
    return values


# --- Build commit / fingerprint resolution -----------------------------------


def resolve_build_commit(override: Optional[str], repo_root: Path) -> str:
    """Resolve the embedded build commit id.

    Precedence: an explicit override always wins (validate with
    validate_build_id_override first). Otherwise, fall back to `git
    rev-parse HEAD` run from repo_root, which resolves identically for a
    normal branch checkout or a detached HEAD (e.g. a CI checkout of a
    tag/PR merge commit) -- but *only* when `repo_root` is itself bound to
    its own `.git` metadata (a real repository root). `git rev-parse` is
    never invoked otherwise: git's own upward directory discovery would
    silently walk up to and adopt an unrelated *outer* repository's HEAD
    as this candidate's build identity when `repo_root` is a non-git tree
    (e.g. an extracted release archive) nested inside someone else's
    checkout -- a latent identity-confusion bug (issue #9 remediation).
    If no git metadata is bound to `repo_root` at all (a source archive
    with no .git entry of its own, or git itself missing/failing), fall
    back to the fixed deterministic sentinel "unknown" -- never a
    timestamp, branch name, host path, or an outer/ancestor repository's
    identity.
    """
    if override:
        return override
    repo_root = Path(repo_root)
    if not (repo_root / ".git").exists():
        return "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    sha = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        return "unknown"
    return sha.lower()


def compute_version_packed(major: int, minor: int, patch: int) -> int:
    return ((major & 0xFF) << 16) | ((minor & 0xFF) << 8) | (patch & 0xFF)


def format_version_string(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor}.{patch}"


def compute_fingerprint(fields: dict) -> str:
    """Deterministic config identity fingerprint over compatibility-relevant
    settings (see docs/config_identity.md for exactly which settings are
    considered compatibility-relevant, and why). Returns the first
    FINGERPRINT_LEN hex characters of a SHA-256 digest over a canonical
    (sorted-key, fixed-separator) JSON encoding of `fields`, so identical
    inputs always produce the same fingerprint on any host.
    """
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:FINGERPRINT_LEN]


# --- Resolved identity --------------------------------------------------------


@dataclass
class ExpansionIdentity:
    version_major: int
    version_minor: int
    version_patch: int
    rom_title: str
    rom_game_code: str
    rom_maker_code: str
    rom_revision: int
    rom_size_bytes: int
    config_preset: str
    abi: str
    text_shift: int
    build_commit: str
    save_compat_epoch: int
    enabled_locales: Tuple[str, ...] = ()
    default_locale: str = locale_schema.DEFAULT_LOCALE
    pseudo_locale_enabled: int = 0
    mechanics_hooks: int = 0
    mechanics_sample: int = 0
    danger_overlay_menu: int = 0
    starter_content: int = 0
    vesly_debugger: int = 0
    danger_bones: int = 0
    new_anims: int = 0
    new_tilesets: int = 0
    purchase_generics: int = 0
    mmb: int = 0
    extend_desc_box: int = 0
    extend_dialogue_box: int = 0
    overflow_safety_checks: int = 1
    display_obtainable_item: int = 0
    debuffs_exist: int = 0
    debuffs_stack: int = 0
    select_view_growths: int = 0
    text_chapter_names: int = 0
    battle_stats_no_anims: int = 0
    draw_map_anims: int = 0
    hp_bars: int = 0
    group_ai: int = 0
    alpha_sprite_arrow: int = 0
    turn_autosave: int = 0
    fort_units_start_greyed_out: int = 0
    promote_command: int = 0
    fix_bugs: int = 0
    credits: int = 0
    custom_campaign: int = 0
    skip_opening: int = 0
    game_rank: int = 0
    co_powers: int = 0
    febuilder_pointers: int = 0
    aw2_assets: int = 0
    anims_fast_forward: int = 0
    nimap2: int = 0
    rand_bgm: int = 0
    continue_bgm_battle: int = 0
    config_fingerprint: str = field(default="")

    @property
    def version_string(self) -> str:
        return format_version_string(self.version_major, self.version_minor, self.version_patch)

    @property
    def version_packed(self) -> int:
        return compute_version_packed(self.version_major, self.version_minor, self.version_patch)

    @property
    def enabled_locale_mask(self) -> int:
        return compute_locale_mask(self.enabled_locales)

    @property
    def default_locale_id(self) -> int:
        return locale_schema.LOCALE_INDEX[self.default_locale]

    def fingerprint_fields(self) -> dict:
        """Compatibility-relevant settings folded into the config fingerprint:
        semantic version, ABI, ROM size, link-time text shift, ROM identity,
        the debug/release preset, (issue #18 sprint 1) the normalized
        enabled-locale set/default locale/pseudo-locale flag, and (issue #6)
        the starter-feature opt-in flags (so toggling any feature flag or
        locale setting changes the fingerprint). Deliberately does NOT
        include save_compat_epoch: that field has its own independent,
        narrower bump policy (see config.mk) and must never change merely
        because a locale or feature-flag setting changed -- proven by
        scripts/modernize/tests/test_expansion_config.py. See
        docs/config_identity.md and docs/starter_features.md."""
        return {
            "version": [self.version_major, self.version_minor, self.version_patch],
            "abi": self.abi,
            "config_preset": self.config_preset,
            "rom_size_bytes": self.rom_size_bytes,
            "text_shift": self.text_shift,
            "rom_title": self.rom_title,
            "rom_game_code": self.rom_game_code,
            "rom_maker_code": self.rom_maker_code,
            "rom_revision": self.rom_revision,
            "enabled_locales": list(self.enabled_locales),
            "default_locale": self.default_locale,
            "pseudo_locale_enabled": self.pseudo_locale_enabled,
            "features": {
                "mechanics_hooks": self.mechanics_hooks,
                "mechanics_sample": self.mechanics_sample,
                "danger_overlay_menu": self.danger_overlay_menu,
                "starter_content": self.starter_content,
                "vesly_debugger": self.vesly_debugger,
                "danger_bones": self.danger_bones,
                "new_anims": self.new_anims,
                "new_tilesets": self.new_tilesets,
                "purchase_generics": self.purchase_generics,
                "mmb": self.mmb,
                "extend_desc_box": self.extend_desc_box,
                "extend_dialogue_box": self.extend_dialogue_box,
                "overflow_safety_checks": self.overflow_safety_checks,
                "display_obtainable_item": self.display_obtainable_item,
                "debuffs_exist": self.debuffs_exist,
                "debuffs_stack": self.debuffs_stack,
                "select_view_growths": self.select_view_growths,
                "text_chapter_names": self.text_chapter_names,
                "battle_stats_no_anims": self.battle_stats_no_anims,
                "draw_map_anims": self.draw_map_anims,
                "hp_bars": self.hp_bars,
                "group_ai": self.group_ai,
                "alpha_sprite_arrow": self.alpha_sprite_arrow,
                "turn_autosave": self.turn_autosave,
                "fort_units_start_greyed_out": self.fort_units_start_greyed_out,
                "promote_command": self.promote_command,
                "fix_bugs": self.fix_bugs,
                "credits": self.credits,
                "custom_campaign": self.custom_campaign,
                "skip_opening": self.skip_opening,
                "game_rank": self.game_rank,
                "co_powers": self.co_powers,
                "febuilder_pointers": self.febuilder_pointers,
                "aw2_assets": self.aw2_assets,
                "anims_fast_forward": self.anims_fast_forward,
                "nimap2": self.nimap2,
                "rand_bgm": self.rand_bgm,
                "continue_bgm_battle": self.continue_bgm_battle,
            },
        }

    def to_dict(self) -> dict:
        data = asdict(self)
        data["enabled_locales"] = list(self.enabled_locales)
        data["version_string"] = self.version_string
        data["version_packed"] = self.version_packed
        data["enabled_locale_mask"] = self.enabled_locale_mask
        data["default_locale_id"] = self.default_locale_id
        return data


def load_identity(
    config_mk_path: Path,
    config_preset: str,
    abi: str,
    rom_size,
    text_shift=0,
    build_id_override: Optional[str] = None,
    repo_root: Optional[Path] = None,
    version_major=None,
    version_minor=None,
    version_patch=None,
    rom_title: Optional[str] = None,
    rom_game_code: Optional[str] = None,
    rom_maker_code: Optional[str] = None,
    rom_revision=None,
    save_compat_epoch=None,
    enabled_locales=None,
    default_locale=None,
    pseudo_locale=None,
    mechanics_hooks=None,
    mechanics_sample=None,
    danger_overlay_menu=None,
    starter_content=None,
    vesly_debugger=None,
    danger_bones=None,
    new_anims=None,
    new_tilesets=None,
    purchase_generics=None,
    mmb=None,
    extend_desc_box=None,
    extend_dialogue_box=None,
    overflow_safety_checks=None,
    display_obtainable_item=None,
    debuffs_exist=None,
    debuffs_stack=None,
    select_view_growths=None,
    text_chapter_names=None,
    battle_stats_no_anims=None,
    draw_map_anims=None,
    hp_bars=None,
    group_ai=None,
    alpha_sprite_arrow=None,
    turn_autosave=None,
    fort_units_start_greyed_out=None,
    promote_command=None,
    fix_bugs=None,
    credits=None,
    custom_campaign=None,
    skip_opening=None,
    game_rank=None,
    co_powers=None,
    febuilder_pointers=None,
    aw2_assets=None,
    anims_fast_forward=None,
    nimap2=None,
    rand_bgm=None,
    continue_bgm_battle=None,
    item_id_cap=None,
) -> ExpansionIdentity:
    """Parse, validate, and resolve a complete ExpansionIdentity.

    config.mk supplies the defaults for the version/ROM-identity/save-compat
    fields. Any of version_major/version_minor/version_patch/rom_title/
    rom_game_code/rom_maker_code/rom_revision/save_compat_epoch passed as
    not-None override the corresponding config.mk value -- this is how a
    `make ... EXPANSION_ROM_TITLE=...` command-line override (or any other
    Make-level override of a config.mk `?=` default) is threaded through to
    this tool, so the generated metadata JSON/embedded ExpansionMetadata
    record and the `-D` defines compiled into the ROM always agree: there is
    exactly one resolved value per field, never two competing sources of
    truth.

    Raises ConfigError (with a specific, actionable message) for any
    malformed title, game code, maker code, revision, ROM size, semantic
    version, build id, or unsupported preset/ABI -- before any file is
    written.
    """
    config_mk_path = Path(config_mk_path)
    repo_root = Path(repo_root) if repo_root is not None else config_mk_path.resolve().parent

    cfg = parse_config_mk(config_mk_path)

    major, minor, patch = validate_version(
        version_major if version_major not in (None, "") else cfg["EXPANSION_VERSION_MAJOR"],
        version_minor if version_minor not in (None, "") else cfg["EXPANSION_VERSION_MINOR"],
        version_patch if version_patch not in (None, "") else cfg["EXPANSION_VERSION_PATCH"],
    )
    rom_title = validate_title(rom_title if rom_title not in (None, "") else cfg["EXPANSION_ROM_TITLE"])
    rom_game_code = validate_game_code(
        rom_game_code if rom_game_code not in (None, "") else cfg["EXPANSION_ROM_GAME_CODE"]
    )
    rom_maker_code = validate_maker_code(
        rom_maker_code if rom_maker_code not in (None, "") else cfg["EXPANSION_ROM_MAKER_CODE"]
    )
    rom_revision = validate_revision(
        rom_revision if rom_revision not in (None, "") else cfg["EXPANSION_ROM_REVISION"]
    )
    resolved_save_compat_epoch = validate_save_compat_epoch(
        save_compat_epoch
        if save_compat_epoch not in (None, "")
        else cfg["EXPANSION_SAVE_COMPAT_EPOCH"]
    )
    resolved_enabled_locales = validate_enabled_locales(
        enabled_locales if enabled_locales not in (None, "") else cfg["EXPANSION_ENABLED_LOCALES"]
    )
    resolved_default_locale = validate_default_locale(
        default_locale if default_locale not in (None, "") else cfg["EXPANSION_DEFAULT_LOCALE"],
        resolved_enabled_locales,
    )
    resolved_pseudo_locale = validate_pseudo_locale(
        pseudo_locale if pseudo_locale not in (None, "") else cfg["EXPANSION_PSEUDO_LOCALE"],
        resolved_enabled_locales,
    )
    (resolved_hooks, resolved_sample, resolved_danger, resolved_content, resolved_debugger,
     resolved_bones, resolved_anims, resolved_tilesets, resolved_generics, resolved_mmb, resolved_desc_box, resolved_overflow_checks,
     resolved_obtainable_item, resolved_debuffs, resolved_debuffs_stack,
     resolved_select_growths, resolved_ch_names, resolved_battle_stats, resolved_draw_map_anims,
     resolved_hp_bars, resolved_group_ai, resolved_alpha_sprite_arrow, resolved_autosave,
     resolved_fort_units_start_greyed_out, resolved_promote_command, resolved_fix_bugs, resolved_credits,
     resolved_custom_campaign, resolved_skip_opening, resolved_game_rank, resolved_co_powers,
     resolved_febuilder_pointers, resolved_aw2_assets, resolved_anims_fast_forward,
     resolved_nimap2, resolved_rand_bgm, resolved_continue_bgm_battle,
     resolved_dialogue_box) = validate_feature_flags(
        mechanics_hooks
        if mechanics_hooks not in (None, "")
        else cfg.get("EXPANSION_MECHANICS_HOOKS", "0"),
        mechanics_sample
        if mechanics_sample not in (None, "")
        else cfg.get("EXPANSION_MECHANICS_SAMPLE", "0"),
        danger_overlay_menu
        if danger_overlay_menu not in (None, "")
        else cfg.get("EXPANSION_DANGER_OVERLAY_MENU", "0"),
        starter_content
        if starter_content not in (None, "")
        else cfg.get("EXPANSION_STARTER_CONTENT", "0"),
        vesly_debugger
        if vesly_debugger not in (None, "")
        else cfg.get("VESLY_DEBUGGER", "0"),
        danger_bones
        if danger_bones not in (None, "")
        else cfg.get("DANGER_BONES", "0"),
        new_anims
        if new_anims not in (None, "")
        else cfg.get("NEW_ANIMS", "0"),
        new_tilesets
        if new_tilesets not in (None, "")
        else cfg.get("NEW_TILESETS", "0"),
        purchase_generics
        if purchase_generics not in (None, "")
        else cfg.get("PURCHASE_GENERICS", "0"),
        mmb
        if mmb not in (None, "")
        else cfg.get("MMB", "0"),
        extend_desc_box
        if extend_desc_box not in (None, "")
        else cfg.get("EXTEND_DESC_BOX", "0"),
        extend_dialogue_box
        if extend_dialogue_box not in (None, "")
        else cfg.get("EXTEND_DIALOGUE_BOX", "0"),
        overflow_safety_checks
        if overflow_safety_checks not in (None, "")
        else cfg.get("OVERFLOW_SAFETY_CHECKS", "1"),
        display_obtainable_item
        if display_obtainable_item not in (None, "")
        else cfg.get("DISPLAY_OBTAINABLE_ITEM", "0"),
        debuffs_exist
        if debuffs_exist not in (None, "")
        else cfg.get("DEBUFFS_EXIST", "0"),
        debuffs_stack
        if debuffs_stack not in (None, "")
        else cfg.get("DEBUFFS_STACK", "0"),
        select_view_growths
        if select_view_growths not in (None, "")
        else cfg.get("SELECT_VIEW_GROWTHS", "0"),
        text_chapter_names
        if text_chapter_names not in (None, "")
        else cfg.get("TEXT_CHAPTER_NAMES", "0"),
        battle_stats_no_anims
        if battle_stats_no_anims not in (None, "")
        else cfg.get("BATTLE_STATS_NO_ANIMS", "0"),
        draw_map_anims
        if draw_map_anims not in (None, "")
        else cfg.get("DRAW_MAP_ANIMS", "0"),
        hp_bars
        if hp_bars not in (None, "")
        else cfg.get("HP_BARS", "0"),
        group_ai
        if group_ai not in (None, "")
        else cfg.get("GROUP_AI", "0"),
        alpha_sprite_arrow
        if alpha_sprite_arrow not in (None, "")
        else cfg.get("ALPHA_SPRITE_ARROW", "0"),
        turn_autosave
        if turn_autosave not in (None, "")
        else cfg.get("TURN_AUTOSAVE", "0"),
        fort_units_start_greyed_out
        if fort_units_start_greyed_out not in (None, "")
        else cfg.get("FORT_UNITS_START_GREYED_OUT", "0"),
        promote_command
        if promote_command not in (None, "")
        else cfg.get("PROMOTE_COMMAND", "0"),
        fix_bugs
        if fix_bugs not in (None, "")
        else cfg.get("FIX_BUGS", "0"),
        credits
        if credits not in (None, "")
        else cfg.get("CREDITS", "0"),
        custom_campaign
        if custom_campaign not in (None, "")
        else cfg.get("CUSTOM_CAMPAIGN", "0"),
        skip_opening
        if skip_opening not in (None, "")
        else cfg.get("SKIP_OPENING", "0"),
        game_rank
        if game_rank not in (None, "")
        else cfg.get("GAME_RANK", "0"),
        co_powers
        if co_powers not in (None, "")
        else cfg.get("CO_POWERS", "0"),
        febuilder_pointers
        if febuilder_pointers not in (None, "")
        else cfg.get("FEBUILDER_POINTERS", "0"),
        aw2_assets
        if aw2_assets not in (None, "")
        else cfg.get("AW2_ASSETS", "0"),
        anims_fast_forward
        if anims_fast_forward not in (None, "")
        else cfg.get("ANIMS_FAST_FORWARD", "0"),
        nimap2
        if nimap2 not in (None, "")
        else cfg.get("NIMAP2", "0"),
        rand_bgm
        if rand_bgm not in (None, "")
        else cfg.get("RAND_BGM", "0"),
        continue_bgm_battle
        if continue_bgm_battle not in (None, "")
        else cfg.get("CONTINUE_BGM_BATTLE", "0"),
        item_id_cap,
    )
    resolved_rom_size = validate_rom_size(rom_size)
    validate_locale_rom_size(resolved_enabled_locales, resolved_rom_size)
    resolved_preset = validate_preset(config_preset)
    resolved_abi = validate_abi(abi)
    resolved_text_shift = validate_text_shift(text_shift)

    override = build_id_override if build_id_override else (cfg.get("EXPANSION_BUILD_ID") or None)
    override = validate_build_id_override(override)
    build_commit = resolve_build_commit(override, repo_root)

    identity = ExpansionIdentity(
        version_major=major,
        version_minor=minor,
        version_patch=patch,
        rom_title=rom_title,
        rom_game_code=rom_game_code,
        rom_maker_code=rom_maker_code,
        rom_revision=rom_revision,
        rom_size_bytes=resolved_rom_size,
        config_preset=resolved_preset,
        abi=resolved_abi,
        text_shift=resolved_text_shift,
        build_commit=build_commit,
        save_compat_epoch=resolved_save_compat_epoch,
        enabled_locales=resolved_enabled_locales,
        default_locale=resolved_default_locale,
        pseudo_locale_enabled=resolved_pseudo_locale,
        mechanics_hooks=resolved_hooks,
        mechanics_sample=resolved_sample,
        danger_overlay_menu=resolved_danger,
        starter_content=resolved_content,
        vesly_debugger=resolved_debugger,
        danger_bones=resolved_bones,
        new_anims=resolved_anims,
        new_tilesets=resolved_tilesets,
        purchase_generics=resolved_generics,
        mmb=resolved_mmb,
        extend_desc_box=resolved_desc_box,
        extend_dialogue_box=resolved_dialogue_box,
        overflow_safety_checks=resolved_overflow_checks,
        display_obtainable_item=resolved_obtainable_item,
        debuffs_exist=resolved_debuffs,
        debuffs_stack=resolved_debuffs_stack,
        select_view_growths=resolved_select_growths,
        text_chapter_names=resolved_ch_names,
        battle_stats_no_anims=resolved_battle_stats,
        draw_map_anims=resolved_draw_map_anims,
        hp_bars=resolved_hp_bars,
        group_ai=resolved_group_ai,
        alpha_sprite_arrow=resolved_alpha_sprite_arrow,
        turn_autosave=resolved_autosave,
        fort_units_start_greyed_out=resolved_fort_units_start_greyed_out,
        promote_command=resolved_promote_command,
        fix_bugs=resolved_fix_bugs,
        credits=resolved_credits,
        custom_campaign=resolved_custom_campaign,
        skip_opening=resolved_skip_opening,
        game_rank=resolved_game_rank,
        co_powers=resolved_co_powers,
        febuilder_pointers=resolved_febuilder_pointers,
        aw2_assets=resolved_aw2_assets,
        anims_fast_forward=resolved_anims_fast_forward,
        nimap2=resolved_nimap2,
        rand_bgm=resolved_rand_bgm,
        continue_bgm_battle=resolved_continue_bgm_battle,
    )
    identity.config_fingerprint = compute_fingerprint(identity.fingerprint_fields())
    return identity


# --- Generated build metadata -------------------------------------------------


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def generate_metadata_files(output_dir: Path, identity: ExpansionIdentity) -> Dict[str, Path]:
    """Write the deterministic per-build metadata files under output_dir.

    output_dir is expected to be build/expansion-modern/<config>/<abi>/generated
    -- never a committed source directory. Files are only rewritten when
    their content actually changes, so an unrelated rebuild does not touch
    their mtimes.
    """
    output_dir = Path(output_dir)
    data = identity.to_dict()

    json_path = output_dir / "expansion_build_metadata.json"
    _write_if_changed(json_path, json.dumps(data, indent=2, sort_keys=True) + "\n")

    mk_path = output_dir / "expansion_build_metadata.mk"
    mk_lines = [
        "# Generated by scripts/modernize/expansion_config.py -- do not edit.",
        "# Deterministic per-build expansion metadata (issue #8), regenerated",
        "# from config.mk plus MODERN_CONFIG/MODERN_ABI/MODERN_ROM_SIZE/",
        "# MODERN_TEXT_SHIFT/EXPANSION_BUILD_ID on every relevant build.",
        f"MODERN_BUILD_COMMIT := {identity.build_commit}",
        f"MODERN_CONFIG_FINGERPRINT := {identity.config_fingerprint}",
        f"MODERN_VERSION_PACKED := {identity.version_packed}",
        f"MODERN_VERSION_STRING := {identity.version_string}",
        f"MODERN_SAVE_COMPAT_EPOCH := {identity.save_compat_epoch}",
        f"MODERN_EXPANSION_ENABLED_LOCALE_MASK := {identity.enabled_locale_mask}",
        f"MODERN_EXPANSION_DEFAULT_LOCALE_ID := {identity.default_locale_id}",
        f"MODERN_EXPANSION_PSEUDO_LOCALE_ENABLED := {identity.pseudo_locale_enabled}",
        "",
    ]
    _write_if_changed(mk_path, "\n".join(mk_lines))

    return {"json": json_path, "mk": mk_path}


# --- CLI ----------------------------------------------------------------------


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config-mk", type=Path, default=Path("config.mk"))
    parser.add_argument("--config", required=True, choices=SUPPORTED_PRESETS)
    parser.add_argument("--abi", required=True, choices=SUPPORTED_ABIS)
    parser.add_argument("--rom-size", required=True)
    parser.add_argument("--text-shift", default="0")
    parser.add_argument("--build-id", default="")
    parser.add_argument("--repo-root", type=Path, default=None)
    # Optional overrides for the version/ROM-identity fields config.mk
    # otherwise supplies. These exist so a Make-level override (e.g. `make
    # ... EXPANSION_ROM_TITLE=...`) can be threaded through to this tool --
    # the caller (modern.mk) always passes the current Make variable value
    # (default or overridden) here, so there is exactly one resolved value
    # per field instead of the Make-compiled `-D` defines and this tool's
    # generated metadata silently disagreeing.
    parser.add_argument("--version-major", default=None)
    parser.add_argument("--version-minor", default=None)
    parser.add_argument("--version-patch", default=None)
    parser.add_argument("--title", default=None, help="override EXPANSION_ROM_TITLE")
    parser.add_argument("--game-code", default=None, help="override EXPANSION_ROM_GAME_CODE")
    parser.add_argument("--maker-code", default=None, help="override EXPANSION_ROM_MAKER_CODE")
    parser.add_argument("--revision", default=None, help="override EXPANSION_ROM_REVISION")
    parser.add_argument(
        "--save-compat-epoch", default=None, help="override EXPANSION_SAVE_COMPAT_EPOCH"
    )
    parser.add_argument(
        "--enabled-locales", default=None, help="override EXPANSION_ENABLED_LOCALES"
    )
    parser.add_argument(
        "--default-locale", default=None, help="override EXPANSION_DEFAULT_LOCALE"
    )
    parser.add_argument(
        "--pseudo-locale", default=None, help="override EXPANSION_PSEUDO_LOCALE"
    )
    parser.add_argument(
        "--mechanics-hooks",
        default=None,
        help="override EXPANSION_MECHANICS_HOOKS (0 or 1)",
    )
    parser.add_argument(
        "--mechanics-sample",
        default=None,
        help="override EXPANSION_MECHANICS_SAMPLE (0 or 1)",
    )
    parser.add_argument(
        "--danger-overlay-menu",
        default=None,
        help="override EXPANSION_DANGER_OVERLAY_MENU (0 or 1)",
    )
    parser.add_argument(
        "--starter-content",
        default=None,
        help="override EXPANSION_STARTER_CONTENT (0 or 1)",
    )
    parser.add_argument(
        "--vesly-debugger",
        default=None,
        help="override VESLY_DEBUGGER (0 or 1)",
    )
    parser.add_argument(
        "--danger-bones",
        default=None,
        help="override DANGER_BONES (0 or 1)",
    )
    parser.add_argument(
        "--new-anims",
        default=None,
        help="override NEW_ANIMS (0 or 1)",
    )
    parser.add_argument(
        "--new-tilesets",
        default=None,
        help="override NEW_TILESETS (0 or 1)",
    )
    parser.add_argument(
        "--purchase-generics",
        default=None,
        help="override PURCHASE_GENERICS (0 or 1)",
    )
    parser.add_argument(
        "--mmb",
        default=None,
        help="override MMB (0 or 1)",
    )
    parser.add_argument(
        "--extend-desc-box",
        default=None,
        help="override EXTEND_DESC_BOX (0 or 1)",
    )
    parser.add_argument(
        "--extend-dialogue-box",
        default=None,
        help="override EXTEND_DIALOGUE_BOX (0 or 1)",
    )
    parser.add_argument(
        "--overflow-safety-checks",
        default=None,
        help="override OVERFLOW_SAFETY_CHECKS (0 or 1)",
    )
    parser.add_argument(
        "--display-obtainable-item",
        default=None,
        help="override DISPLAY_OBTAINABLE_ITEM (0 or 1)",
    )
    parser.add_argument(
        "--debuffs-exist",
        default=None,
        help="override DEBUFFS_EXIST (0 or 1)",
    )
    parser.add_argument(
        "--debuffs-stack",
        default=None,
        help="override DEBUFFS_STACK (0 or 1)",
    )
    parser.add_argument(
        "--select-view-growths",
        default=None,
        help="override SELECT_VIEW_GROWTHS (0 or 1)",
    )
    parser.add_argument(
        "--text-chapter-names",
        default=None,
        help="override TEXT_CHAPTER_NAMES (0 or 1)",
    )
    parser.add_argument(
        "--battle-stats-no-anims",
        default=None,
        help="override BATTLE_STATS_NO_ANIMS (0 or 1)",
    )
    parser.add_argument(
        "--draw-map-anims",
        default=None,
        help="override DRAW_MAP_ANIMS (0 or 1)",
    )
    parser.add_argument(
        "--hp-bars",
        default=None,
        help="override HP_BARS (0 or 1)",
    )
    parser.add_argument(
        "--group-ai",
        default=None,
        help="override GROUP_AI (0 or 1)",
    )
    parser.add_argument(
        "--alpha-sprite-arrow",
        default=None,
        help="override ALPHA_SPRITE_ARROW (0 or 1)",
    )
    parser.add_argument(
        "--turn-autosave",
        default=None,
        help="override TURN_AUTOSAVE (0 or 1)",
    )
    parser.add_argument(
        "--game-rank",
        default=None,
        help="override GAME_RANK (0 or 1)",
    )
    parser.add_argument(
        "--co-powers",
        default=None,
        help="override CO_POWERS (0 or 1)",
    )
    parser.add_argument(
        "--febuilder-pointers",
        default=None,
        help="override FEBUILDER_POINTERS (0 or 1)",
    )
    parser.add_argument(
        "--aw2-assets",
        default=None,
        help="override AW2_ASSETS (0 or 1)",
    )
    parser.add_argument(
        "--anims-fast-forward",
        default=None,
        help="override ANIMS_FAST_FORWARD (0 or 1)",
    )
    parser.add_argument(
        "--nimap2",
        default=None,
        help="override NIMAP2 (0 or 1)",
    )
    parser.add_argument(
        "--rand-bgm",
        default=None,
        help="override RAND_BGM (0 or 1)",
    )
    parser.add_argument(
        "--continue-bgm-battle",
        default=None,
        help="override CONTINUE_BGM_BATTLE (0 or 1)",
    )
    parser.add_argument(
        "--fort-units-start-greyed-out",
        default=None,
        help="override FORT_UNITS_START_GREYED_OUT (0 or 1)",
    )
    parser.add_argument(
        "--promote-command",
        default=None,
        help="override PROMOTE_COMMAND (0 or 1)",
    )
    parser.add_argument(
        "--fix-bugs",
        default=None,
        help="override FIX_BUGS (0 or 1)",
    )
    parser.add_argument(
        "--credits",
        default=None,
        help="override CREDITS (0 or 1)",
    )
    parser.add_argument(
        "--custom-campaign",
        default=None,
        help="override CUSTOM_CAMPAIGN (0 or 1)",
    )
    parser.add_argument(
        "--skip-opening",
        default=None,
        help="override SKIP_OPENING (0 or 1)",
    )
    parser.add_argument(
        "--item-id-cap",
        default=None,
        help=(
            "the build's active FE8_ITEM_ID_CAP (empty = the committed default "
            "cap); EXPANSION_STARTER_CONTENT=1 requires it to reach "
            "ITEM_EXPANSION_CE"
        ),
    )


def _resolve_tokens(identity: ExpansionIdentity) -> str:
    return (
        f"MODERN_BUILD_COMMIT={identity.build_commit} "
        f"MODERN_CONFIG_FINGERPRINT={identity.config_fingerprint} "
        f"MODERN_VERSION_PACKED={identity.version_packed} "
        f"MODERN_VERSION_STRING={identity.version_string} "
        f"MODERN_SAVE_COMPAT_EPOCH={identity.save_compat_epoch} "
        f"MODERN_EXPANSION_ENABLED_LOCALE_MASK={identity.enabled_locale_mask} "
        f"MODERN_EXPANSION_DEFAULT_LOCALE_ID={identity.default_locale_id} "
        f"MODERN_EXPANSION_PSEUDO_LOCALE_ENABLED={identity.pseudo_locale_enabled}"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate_p = sub.add_parser(
        "validate", help="validate config.mk plus the given build settings; silent on success"
    )
    _add_common_args(validate_p)

    resolve_p = sub.add_parser(
        "resolve", help="validate, then print resolved MODERN_* KEY=VALUE tokens"
    )
    _add_common_args(resolve_p)

    generate_p = sub.add_parser(
        "generate", help="validate, resolve, and write generated metadata files"
    )
    _add_common_args(generate_p)
    generate_p.add_argument("--output-dir", type=Path, required=True)

    args = parser.parse_args(argv)

    try:
        identity = load_identity(
            config_mk_path=args.config_mk,
            config_preset=args.config,
            abi=args.abi,
            rom_size=args.rom_size,
            text_shift=args.text_shift,
            build_id_override=args.build_id or None,
            repo_root=args.repo_root,
            version_major=args.version_major,
            version_minor=args.version_minor,
            version_patch=args.version_patch,
            rom_title=args.title,
            rom_game_code=args.game_code,
            rom_maker_code=args.maker_code,
            rom_revision=args.revision,
            save_compat_epoch=args.save_compat_epoch,
            enabled_locales=args.enabled_locales,
            default_locale=args.default_locale,
            pseudo_locale=args.pseudo_locale,
            mechanics_hooks=args.mechanics_hooks,
            mechanics_sample=args.mechanics_sample,
            danger_overlay_menu=args.danger_overlay_menu,
            starter_content=args.starter_content,
            vesly_debugger=args.vesly_debugger,
            danger_bones=args.danger_bones,
            new_anims=args.new_anims,
            new_tilesets=args.new_tilesets,
            purchase_generics=args.purchase_generics,
            mmb=args.mmb,
            extend_desc_box=args.extend_desc_box,
            extend_dialogue_box=args.extend_dialogue_box,
            overflow_safety_checks=args.overflow_safety_checks,
            display_obtainable_item=args.display_obtainable_item,
            debuffs_exist=args.debuffs_exist,
            debuffs_stack=args.debuffs_stack,
            select_view_growths=args.select_view_growths,
            text_chapter_names=args.text_chapter_names,
            battle_stats_no_anims=args.battle_stats_no_anims,
            draw_map_anims=args.draw_map_anims,
            hp_bars=args.hp_bars,
            group_ai=args.group_ai,
            alpha_sprite_arrow=args.alpha_sprite_arrow,
            turn_autosave=args.turn_autosave,
            fort_units_start_greyed_out=args.fort_units_start_greyed_out,
            promote_command=args.promote_command,
            fix_bugs=args.fix_bugs,
            credits=args.credits,
            custom_campaign=args.custom_campaign,
            skip_opening=args.skip_opening,
            game_rank=args.game_rank,
            co_powers=args.co_powers,
            febuilder_pointers=args.febuilder_pointers,
            aw2_assets=args.aw2_assets,
            anims_fast_forward=args.anims_fast_forward,
            nimap2=args.nimap2,
            rand_bgm=args.rand_bgm,
            continue_bgm_battle=args.continue_bgm_battle,
            item_id_cap=args.item_id_cap,
        )
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.command == "validate":
        return 0

    if args.command == "generate":
        generate_metadata_files(args.output_dir, identity)

    print(_resolve_tokens(identity))
    return 0


if __name__ == "__main__":
    sys.exit(main())
