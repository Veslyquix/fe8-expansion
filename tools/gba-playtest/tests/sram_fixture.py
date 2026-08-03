"""Synthetic 0x8000-byte SRAM image fixtures for gba-playtest save-gate
runtime scenarios (issue #2 slice 2, requirement 6).

All fixtures are generated at test/build time under caller-supplied,
ignored build/temp paths -- never committed as binaries. Byte layout is
derived from the Slice 1 format implementation/contracts in
scripts/modernize/save_format_tool.py (and its test helpers) rather than
duplicating magic numbers here: this module is a thin generator shell
around that existing, byte-exact source of truth.

Also exposes a small CLI (`write-deterministic-current`) used by
modern.mk's expansion-modern-debugtools-check to seed a debugtools-hub
scenario's starting SRAM with a fixed SAVE_COMPAT_CURRENT image -- see
build_deterministic_current_image()'s docstring and docs/debugtools.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODERNIZE_DIR = _REPO_ROOT / "scripts" / "modernize"
_MODERNIZE_TESTS_DIR = _MODERNIZE_DIR / "tests"
for _extra_path in (str(_MODERNIZE_DIR), str(_MODERNIZE_TESTS_DIR)):
    if _extra_path not in sys.path:
        sys.path.insert(0, _extra_path)

import save_format_tool as sft  # noqa: E402
from test_save_format_tool import make_header, make_image, make_meta  # noqa: E402


# Fixture state names, reusing the real classifier's own state constants
# (sft.SAVE_COMPAT_*) so a fixture name always matches the classification
# it is meant to produce.
STATE_CURRENT = sft.SAVE_COMPAT_CURRENT
STATE_VALID_LEGACY = sft.SAVE_COMPAT_VALID_LEGACY_OR_VANILLA
STATE_HEADER_CORRUPT = sft.SAVE_COMPAT_HEADER_CORRUPT
STATE_METADATA_CORRUPT = sft.SAVE_COMPAT_METADATA_CORRUPT
STATE_OLDER = sft.SAVE_COMPAT_MIGRATABLE_OLDER
STATE_NEWER = sft.SAVE_COMPAT_NEWER_UNSUPPORTED
STATE_CONFIG_INCOMPATIBLE = sft.SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE
STATE_EMPTY = sft.SAVE_COMPAT_EMPTY

ALL_FIXTURE_STATES = (
    STATE_CURRENT,
    STATE_VALID_LEGACY,
    STATE_HEADER_CORRUPT,
    STATE_METADATA_CORRUPT,
    STATE_OLDER,
    STATE_NEWER,
    STATE_CONFIG_INCOMPATIBLE,
    STATE_EMPTY,
)


def resolve_epoch(repo_root: Path = _REPO_ROOT) -> int:
    return sft.resolve_save_compat_epoch(repo_root)


def build_fixture_image(state: str, repo_root: Path = _REPO_ROOT) -> bytes:
    """Builds a byte-exact 0x8000 SRAM image classified as `state` by the
    real classify_image()/classify_save_compat_raw() mirror, using only
    the existing Slice 1 helpers (no duplicated magic numbers)."""
    epoch = resolve_epoch(repo_root)

    if state == STATE_EMPTY:
        image = bytes([0xFF] * sft.SRAM_SIZE)
    elif state == STATE_HEADER_CORRUPT:
        header = make_header(valid=False)
        meta = make_meta(present=False)
        image = bytes(make_image(header, meta))
    elif state == STATE_VALID_LEGACY:
        header = make_header(valid=True)
        meta = make_meta(present=False)  # no FSAV magic -> legacy/vanilla
        image = bytes(make_image(header, meta))
    elif state == STATE_METADATA_CORRUPT:
        header = make_header(valid=True)
        meta = make_meta(
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT,
            compat_epoch=epoch,
            corrupt_checksum=True,
        )
        image = bytes(make_image(header, meta))
    elif state == STATE_OLDER:
        header = make_header(valid=True)
        meta = make_meta(
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT - 1
            if sft.SAVE_FORMAT_VERSION_CURRENT > 0 else 0,
            compat_epoch=epoch,
        )
        image = bytes(make_image(header, meta))
    elif state == STATE_NEWER:
        header = make_header(valid=True)
        meta = make_meta(
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT + 1,
            compat_epoch=epoch,
        )
        image = bytes(make_image(header, meta))
    elif state == STATE_CONFIG_INCOMPATIBLE:
        header = make_header(valid=True)
        meta = make_meta(
            format_version=sft.SAVE_FORMAT_VERSION_CURRENT,
            compat_epoch=epoch + 1,
        )
        image = bytes(make_image(header, meta))
    elif state == STATE_CURRENT:
        header = make_header(valid=True)
        real_meta = sft.build_current_expansion_save_meta(repo_root)
        image = bytes(make_image(header, bytearray(real_meta.pack())))
    else:
        raise ValueError(f"unknown fixture state: {state!r}")

    actual_state = sft.classify_image(image, epoch)
    if actual_state != state:
        raise AssertionError(
            f"fixture generator bug: requested {state!r} but classify_image() "
            f"returned {actual_state!r}"
        )
    return image


def write_fixture(path: Path, state: str, repo_root: Path = _REPO_ROOT) -> Path:
    """Writes a generated fixture to `path` (expected to be under an
    ignored build/temp directory) and returns the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_fixture_image(state, repo_root))
    return path


def migrate_fixture(source: Path, dest: Path, repo_root: Path = _REPO_ROOT) -> Path:
    """Invokes the existing, unmodified save_format_tool.py CLI (as a
    subprocess, exactly as a human operator would run it) to migrate
    `source` (must classify as SAVE_COMPAT_VALID_LEGACY_OR_VANILLA or
    SAVE_COMPAT_CURRENT) into `dest`, which must classify as
    SAVE_COMPAT_CURRENT afterward. Raises RuntimeError with the CLI's own
    stderr on any failure."""
    import subprocess

    dest.parent.mkdir(parents=True, exist_ok=True)
    tool = _MODERNIZE_DIR / "save_format_tool.py"
    result = subprocess.run(
        [
            sys.executable, str(tool),
            "--repo-root", str(repo_root),
            "migrate", str(source), str(dest), "--force",
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"save_format_tool.py migrate failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    epoch = resolve_epoch(repo_root)
    migrated_state = sft.classify_image(dest.read_bytes(), epoch)
    if migrated_state != STATE_CURRENT:
        raise AssertionError(
            f"migrated fixture {dest} classified as {migrated_state!r}, expected "
            f"{STATE_CURRENT!r}"
        )
    return dest


# --- Deterministic (commit-invariant) SAVE_COMPAT_CURRENT fixture ----------
#
# build_fixture_image(STATE_CURRENT) above (via
# sft.build_current_expansion_save_meta()) intentionally stamps the *live*
# build commit into ExpansionSaveMeta.buildCommitShort, mirroring
# BuildCurrentExpansionSaveMeta() (src/bmsave-lib.c) exactly -- correct for
# the savecompat-* scenarios, which explicitly normalize that field out via
# `sram_hash_exclude_ranges` (see tools/gba-playtest/scenarios/
# savecompat-current.json).
#
# The debugtools-hub scenarios instead assert an EXACT, zero-exclusion-range
# whole-SRAM hash (`fnv1a64-sram`), so they must never boot from genuinely
# blank SRAM: doing so drives ClassifySramSaveCompat() to SAVE_COMPAT_EMPTY,
# which makes EnsureGlobalSaveInfoLoaded() call InitGlobalSaveInfodata() ->
# BuildCurrentExpansionSaveMeta(), stamping that commit's
# FE8_EXPANSION_BUILD_COMMIT into SRAM and changing the exact hash on every
# commit. Seeding SRAM instead with the fixed-diagnostics image below keeps
# SRAM already SAVE_COMPAT_CURRENT, so that wipe/stamp path is never taken.
DETERMINISTIC_BUILD_COMMIT_SHORT = b"00000000\x00"


def build_deterministic_current_image(repo_root: Path = _REPO_ROOT) -> bytes:
    """Builds a byte-exact 0x8000 SRAM image classified SAVE_COMPAT_CURRENT
    whose diagnostic-only ExpansionSaveMeta.buildCommitShort field is a
    fixed sentinel (DETERMINISTIC_BUILD_COMMIT_SHORT) instead of the live,
    per-commit `git rev-parse HEAD`-derived value that
    sft.build_current_expansion_save_meta()/build_fixture_image(STATE_CURRENT)
    embed. Every compatibility-gating field (magic, formatVersion,
    compatEpoch) and every other diagnostic field (abiId,
    frameworkVersionPacked, configFingerprint) is left exactly as the real
    running ROM would produce it -- only the commit-derived field is frozen,
    so this fixture classifies identically to a genuine CURRENT save and its
    whole-SRAM hash stays invariant across commits."""
    epoch = resolve_epoch(repo_root)
    meta = sft.build_current_expansion_save_meta(repo_root)
    meta.build_commit_short = DETERMINISTIC_BUILD_COMMIT_SHORT
    meta.checksum = 0
    meta.checksum = meta.computed_checksum()

    header = make_header(valid=True)
    image = bytes(make_image(header, bytearray(meta.pack())))

    actual_state = sft.classify_image(image, epoch)
    if actual_state != STATE_CURRENT:
        raise AssertionError(
            f"deterministic-current fixture generator bug: expected "
            f"{STATE_CURRENT!r} but classify_image() returned {actual_state!r}"
        )
    return image


def write_deterministic_current_fixture(path: Path, repo_root: Path = _REPO_ROOT) -> Path:
    """Writes build_deterministic_current_image()'s output to `path`
    (expected to be under an ignored build/temp directory) and returns the
    path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_deterministic_current_image(repo_root))
    return path


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write synthetic SRAM fixtures for gba-playtest runtime scenarios."
        ),
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    deterministic_current = subparsers.add_parser(
        "write-deterministic-current",
        help=(
            "Write a commit-invariant SAVE_COMPAT_CURRENT 0x8000 SRAM image "
            "(fixed diagnostic buildCommitShort) to the given path."
        ),
    )
    deterministic_current.add_argument("output", type=Path)
    deterministic_current.add_argument(
        "--repo-root", type=Path, default=_REPO_ROOT,
        help="Repository root used to resolve config.mk (default: %(default)s)",
    )

    write_state = subparsers.add_parser(
        "write-state",
        help=(
            "Write a byte-exact SRAM image classified as the given "
            "ClassifySramSaveCompat() state (build_fixture_image) -- e.g. "
            "'write-state EXPANSION_USER_PREFS_EMPTY' style genuinely-blank "
            "(all-0xFF) SRAM for issue #18 sprint 4's locale-blank-sram "
            "scenarios. See ALL_FIXTURE_STATES for the full list."
        ),
    )
    write_state.add_argument("state", choices=list(ALL_FIXTURE_STATES))
    write_state.add_argument("output", type=Path)
    write_state.add_argument(
        "--repo-root", type=Path, default=_REPO_ROOT,
        help="Repository root used to resolve config.mk (default: %(default)s)",
    )

    args = parser.parse_args(argv)

    if args.mode == "write-state":
        image = build_fixture_image(args.state, args.repo_root)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(image)
        print(f"wrote {args.state} SRAM fixture: {args.output} ({len(image)} bytes)")
        return 0

    if args.mode == "write-deterministic-current":
        path = write_deterministic_current_fixture(args.output, args.repo_root)
        print(
            f"wrote deterministic SAVE_COMPAT_CURRENT SRAM fixture: {path} "
            f"({path.stat().st_size} bytes, "
            f"buildCommitShort={DETERMINISTIC_BUILD_COMMIT_SHORT!r})"
        )
        return 0

    parser.error(f"unknown mode: {args.mode!r}")
    return 2  # pragma: no cover -- parser.error() always raises SystemExit


if __name__ == "__main__":
    raise SystemExit(_main())
