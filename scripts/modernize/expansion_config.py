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


def validate_feature_flags(mechanics_hooks, mechanics_sample, danger_overlay_menu):
    """Validate the three starter-feature flags plus their one dependency.

    The sample mechanic can only be registered through the mechanics hook
    registry, so EXPANSION_MECHANICS_SAMPLE=1 with EXPANSION_MECHANICS_HOOKS=0
    is a contradiction and is rejected here (an actionable error), rather than
    silently linking a sample with no registry to register it into.
    """
    hooks = validate_feature_flag("EXPANSION_MECHANICS_HOOKS", mechanics_hooks)
    sample = validate_feature_flag("EXPANSION_MECHANICS_SAMPLE", mechanics_sample)
    danger = validate_feature_flag("EXPANSION_DANGER_OVERLAY_MENU", danger_overlay_menu)
    if sample and not hooks:
        raise ConfigError(
            "EXPANSION_MECHANICS_SAMPLE=1 requires EXPANSION_MECHANICS_HOOKS=1: "
            "the sample mechanic is registered through the mechanics hook "
            "registry, which is not linked when EXPANSION_MECHANICS_HOOKS=0"
        )
    return hooks, sample, danger


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
    tag/PR merge commit). If no git metadata is available at all (a source
    archive with no .git directory, or git itself missing), fall back to
    the fixed deterministic sentinel "unknown" -- never a timestamp,
    branch name, or host path.
    """
    if override:
        return override
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
    mechanics_hooks: int = 0
    mechanics_sample: int = 0
    danger_overlay_menu: int = 0
    config_fingerprint: str = field(default="")

    @property
    def version_string(self) -> str:
        return format_version_string(self.version_major, self.version_minor, self.version_patch)

    @property
    def version_packed(self) -> int:
        return compute_version_packed(self.version_major, self.version_minor, self.version_patch)

    def fingerprint_fields(self) -> dict:
        """Compatibility-relevant settings folded into the config fingerprint:
        semantic version, ABI, ROM size, link-time text shift, ROM identity,
        the debug/release preset, and the issue #6 starter-feature opt-in
        flags (so toggling any feature flag changes the fingerprint, while the
        independent save-compatibility epoch/key is deliberately NOT folded in
        here). See docs/config_identity.md and docs/starter_features.md."""
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
            "features": {
                "mechanics_hooks": self.mechanics_hooks,
                "mechanics_sample": self.mechanics_sample,
                "danger_overlay_menu": self.danger_overlay_menu,
            },
        }

    def to_dict(self) -> dict:
        data = asdict(self)
        data["version_string"] = self.version_string
        data["version_packed"] = self.version_packed
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
    mechanics_hooks=None,
    mechanics_sample=None,
    danger_overlay_menu=None,
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
    resolved_hooks, resolved_sample, resolved_danger = validate_feature_flags(
        mechanics_hooks
        if mechanics_hooks not in (None, "")
        else cfg.get("EXPANSION_MECHANICS_HOOKS", "0"),
        mechanics_sample
        if mechanics_sample not in (None, "")
        else cfg.get("EXPANSION_MECHANICS_SAMPLE", "0"),
        danger_overlay_menu
        if danger_overlay_menu not in (None, "")
        else cfg.get("EXPANSION_DANGER_OVERLAY_MENU", "0"),
    )
    resolved_rom_size = validate_rom_size(rom_size)
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
        mechanics_hooks=resolved_hooks,
        mechanics_sample=resolved_sample,
        danger_overlay_menu=resolved_danger,
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


def _resolve_tokens(identity: ExpansionIdentity) -> str:
    return (
        f"MODERN_BUILD_COMMIT={identity.build_commit} "
        f"MODERN_CONFIG_FINGERPRINT={identity.config_fingerprint} "
        f"MODERN_VERSION_PACKED={identity.version_packed} "
        f"MODERN_VERSION_STRING={identity.version_string} "
        f"MODERN_SAVE_COMPAT_EPOCH={identity.save_compat_epoch}"
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
            mechanics_hooks=args.mechanics_hooks,
            mechanics_sample=args.mechanics_sample,
            danger_overlay_menu=args.danger_overlay_menu,
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
