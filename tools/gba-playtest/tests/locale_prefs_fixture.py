"""Synthetic 0x8000-byte SRAM image fixtures for issue #18 sprint 4's
localization-prefs runtime scenarios: unset/unknown/disabled/corrupt
`struct ExpansionUserPrefs` sub-records embedded inside an otherwise
byte-exact SAVE_COMPAT_CURRENT `struct ExpansionSaveMeta`.

Distinct from tools/gba-playtest/tests/sram_fixture.py's STATE_EMPTY
(genuinely blank/all-0xFF SRAM chip): on THIS build's real runtime (see
src/bmsave-lib.c's BuildCurrentExpansionSaveMeta(), issue #18 sprint 2),
genuinely blank SRAM is auto-stamped with a fully VALID default
ExpansionUserPrefs record the moment EraseSramDataIfInvalid() runs
(before the language selector's own RuntimeInit ever executes) -- so a
literal blank cartridge can never exercise
EXPANSION_LANGUAGE_STARTUP_SHOW_MENU/AUTO_SELECT's "requires prompt"
branch. This module instead builds a save whose OUTER ExpansionSaveMeta
already classifies SAVE_COMPAT_CURRENT (so EraseSramDataIfInvalid() never
re-stamps it -- ClassifySramSaveCompat() != SAVE_COMPAT_EMPTY) but whose
INNER ExpansionUserPrefs sub-record is deliberately unset/unknown/
disabled/corrupt -- a real, reachable runtime state (e.g. a save carried
forward from a build predating issue #18 sprint 2's stamp, or a save
whose stored locale became unsupported/disabled by a later build), never
a fabricated impossible byte pattern: every field is built via the same
save_format_tool.py primitives the real ExpansionUserPrefs_Build()/
ExpansionSaveMeta machinery mirrors byte-for-byte.

All fixtures are generated at test/capture time under caller-supplied,
ignored build/temp paths -- never committed as binaries, exactly like
sram_fixture.py's own contract.

Verifier-blocker fix (issue #18 sprint 6): sft.build_current_expansion_
save_meta() stamps ExpansionSaveMeta.buildCommitShort from this host's
*live* `git rev-parse HEAD` (scripts/modernize/expansion_config.py's
resolve_build_commit()) -- correct for a real ROM's own runtime-stamped
SRAM, but these no-wipe fixtures' outer ExpansionSaveMeta is never
re-stamped by the runtime (that is the whole point of "no-wipe"), so its
bytes are never actually build-variable at boot; only this *host-side
generator* made them look that way, by re-resolving the checked-out
commit every time the fixture is (re)built. That silently invalidated
every committed fingerprint asserting the magic/checksum probes at this
region on the very next commit -- reproducible in the default build root
just as much as any isolated one, since both resolve the same live git
HEAD.

Fixed the same already-reviewed way sram_fixture.py's own
build_deterministic_current_image() freezes this exact field for the
debugtools-hub scenarios: after building the real meta, overwrite
buildCommitShort with sram_fixture.DETERMINISTIC_BUILD_COMMIT_SHORT (a
fixed, honestly-labeled sentinel -- never a hand-picked hash) and
recompute the checksum. Every compatibility-gating field (magic,
formatVersion, compatEpoch) and the real config-derived reserved-tail
prefs bytes are untouched; only the diagnostic, never-compared
buildCommitShort (and its dependent checksum) become commit- and
build-root-invariant, matching docs/save_format.md's own "why every
other field stays covered" contract for configFingerprint.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[2]
_MODERNIZE_DIR = _REPO_ROOT / "scripts" / "modernize"
_MODERNIZE_TESTS_DIR = _MODERNIZE_DIR / "tests"
for _extra_path in (str(_THIS_DIR), str(_MODERNIZE_DIR), str(_MODERNIZE_TESTS_DIR)):
    if _extra_path not in sys.path:
        sys.path.insert(0, _extra_path)

import save_format_tool as sft  # noqa: E402
import sram_fixture  # noqa: E402
from test_save_format_tool import make_header, make_image  # noqa: E402


def _freeze_diagnostic_build_commit(meta: sft.ExpansionSaveMeta) -> sft.ExpansionSaveMeta:
    """Overwrites `meta.build_commit_short` with sram_fixture.py's own
    DETERMINISTIC_BUILD_COMMIT_SHORT sentinel and recomputes the
    checksum -- the same, already-reviewed technique
    build_deterministic_current_image() uses to make a host-crafted
    SAVE_COMPAT_CURRENT fixture's diagnostic bytes commit-invariant (see
    this module's own docstring). Mutates and returns `meta` for
    convenient chaining; every other field (including the real
    config-derived `reserved` tail) is left untouched."""
    meta.build_commit_short = sram_fixture.DETERMINISTIC_BUILD_COMMIT_SHORT
    meta.checksum = 0
    meta.checksum = meta.computed_checksum()
    return meta


# Fixture state names -- reuse the real classifier's own
# EXPANSION_USER_PREFS_* state constants so a fixture name always matches
# the ExpansionUserPrefs sub-state it is built to produce.
PREFS_STATE_UNSET = sft.EXPANSION_USER_PREFS_UNSET
PREFS_STATE_CORRUPT = sft.EXPANSION_USER_PREFS_CORRUPT
PREFS_STATE_UNKNOWN_LOCALE = sft.EXPANSION_USER_PREFS_UNKNOWN_LOCALE
PREFS_STATE_DISABLED_LOCALE = sft.EXPANSION_USER_PREFS_DISABLED_LOCALE

ALL_PREFS_FIXTURE_STATES = (
    PREFS_STATE_UNSET,
    PREFS_STATE_CORRUPT,
    PREFS_STATE_UNKNOWN_LOCALE,
    PREFS_STATE_DISABLED_LOCALE,
)

# Deliberately >= EXPANSION_LOCALE_COUNT (8) for every build this repo can
# configure (include/expansion_locale.h's stable ExpansionLocaleId slot
# list is fixed at 8 entries) -- see docs/localization.md's catalog table.
_UNKNOWN_LOCALE_ID = 200


def _reserved_tail(prefs_bytes: bytes) -> bytes:
    padding_len = sft.EXPANSION_SAVE_META_RESERVED_SIZE - len(prefs_bytes)
    assert padding_len >= 0
    return prefs_bytes + b"\x00" * padding_len


def build_prefs_reserved_bytes(state: str, disabled_locale_id: int = 0) -> bytes:
    """Builds the `reserved`-tail bytes (EXPANSION_SAVE_META_RESERVED_SIZE,
    0x2C) for the given ExpansionUserPrefs sub-state. `disabled_locale_id`
    is only used for PREFS_STATE_DISABLED_LOCALE and must be a
    supported-but-not-enabled ExpansionLocaleId for the *specific* build
    the resulting image will be captured against (never resolved from
    config.mk here -- see this module's docstring: the caller must know
    the real compiled-in enabled mask of that build)."""
    if state == PREFS_STATE_UNSET:
        # Every byte 0x00 -- ExpansionUserPrefs_Load()'s own
        # IsRegionAllZero() branch (distinct from, but equally
        # "unset", as the all-0xFF blank-chip pattern).
        return b"\x00" * sft.EXPANSION_SAVE_META_RESERVED_SIZE

    if state == PREFS_STATE_UNKNOWN_LOCALE:
        prefs = sft.build_default_user_prefs(_UNKNOWN_LOCALE_ID, explicit_selection=False)
        return _reserved_tail(prefs.pack())

    if state == PREFS_STATE_DISABLED_LOCALE:
        prefs = sft.build_default_user_prefs(disabled_locale_id, explicit_selection=False)
        return _reserved_tail(prefs.pack())

    if state == PREFS_STATE_CORRUPT:
        prefs = sft.build_default_user_prefs(0, explicit_selection=False)
        prefs.checksum ^= 0xFFFF  # magic/version/localeId all otherwise valid
        return _reserved_tail(prefs.pack())

    raise ValueError(f"unknown ExpansionUserPrefs fixture state: {state!r}")


def build_prefs_fixture_image(
    repo_root: Path,
    state: str,
    disabled_locale_id: int = 0,
) -> bytes:
    """Builds a byte-exact 0x8000-byte SRAM image whose outer
    ExpansionSaveMeta classifies SAVE_COMPAT_CURRENT and whose inner
    ExpansionUserPrefs sub-record classifies `state` -- real captures
    read this back via the live GBA binary's own
    ExpansionUserPrefs_Load()/_ValidateRaw(), never a duplicated Python
    classifier standing in for it."""
    reserved = build_prefs_reserved_bytes(state, disabled_locale_id=disabled_locale_id)
    meta = _freeze_diagnostic_build_commit(
        sft.build_current_expansion_save_meta(repo_root, reserved=reserved)
    )
    header = make_header(valid=True)
    return bytes(make_image(header, meta.pack()))


def build_valid_explicit_prefs_reserved_bytes(locale_id: int) -> bytes:
    """Builds the `reserved`-tail bytes for an already-VALID, already-
    explicit ExpansionUserPrefs record selecting `locale_id` -- simulates
    a save that already went through the first-start selector on a
    previous boot (contrast with the UNSET/CORRUPT/UNKNOWN_LOCALE/
    DISABLED_LOCALE "requires re-prompt" states above). Used by the
    persistence-across-reboot scenario: this is the *post-selection*
    state a real save would be in, so booting from it must never show
    the selector again."""
    prefs = sft.build_default_user_prefs(locale_id, explicit_selection=True)
    return _reserved_tail(prefs.pack())


def build_valid_explicit_prefs_fixture_image(repo_root: Path, locale_id: int) -> bytes:
    """Byte-exact 0x8000 SRAM image: outer ExpansionSaveMeta CURRENT,
    inner ExpansionUserPrefs VALID/explicit for `locale_id`."""
    reserved = build_valid_explicit_prefs_reserved_bytes(locale_id)
    meta = _freeze_diagnostic_build_commit(
        sft.build_current_expansion_save_meta(repo_root, reserved=reserved)
    )
    header = make_header(valid=True)
    return bytes(make_image(header, meta.pack()))


def _main(argv: list | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Write synthetic ExpansionUserPrefs SRAM fixtures for "
            "issue #18 sprint 4 localization runtime scenarios."
        ),
    )
    parser.add_argument(
        "state",
        choices=list(ALL_PREFS_FIXTURE_STATES) + ["valid-explicit"],
        help=(
            "ExpansionUserPrefs sub-state to build ('valid-explicit' takes "
            "--locale-id as the already-selected, persisted locale)."
        ),
    )
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--repo-root", type=Path, default=_REPO_ROOT,
        help="Repository root used to resolve config.mk (default: %(default)s)",
    )
    parser.add_argument(
        "--disabled-locale-id", type=int, default=0,
        help="Supported-but-disabled ExpansionLocaleId for this target build "
             "(only used by the disabled-locale state).",
    )
    parser.add_argument(
        "--locale-id", type=int, default=0,
        help="Already-selected ExpansionLocaleId (only used by 'valid-explicit').",
    )
    args = parser.parse_args(argv)

    if args.state == "valid-explicit":
        image = build_valid_explicit_prefs_fixture_image(args.repo_root, args.locale_id)
    else:
        image = build_prefs_fixture_image(
            args.repo_root, args.state, disabled_locale_id=args.disabled_locale_id,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    print(f"wrote {args.state} ExpansionUserPrefs SRAM fixture: {args.output} "
          f"({len(image)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
