#!/usr/bin/env python3
"""Save-format migration registry (issue #9).

Declares every known save-compatibility transition and whether it is
mechanically automatable or requires manual human steps. Every mechanical
step is executed by shelling out to
``scripts/modernize/save_format_tool.py``'s existing ``validate``/
``migrate`` subcommands -- this module never re-implements or weakens that
tool's classification or atomic-publish safety model (see its own
docstring and docs/save_format.md). All transformations are strictly
out-of-place (a distinct destination path is always required) and this
module never touches a real user save; tests use synthetic in-memory
fixtures only, matching scripts/modernize/tests/test_save_format_tool.py's
existing guardrail.

Issue #9 residual-hardening, formatVersion/compatEpoch pair modeling: a
declared transition's source and target are each an *exact*
``(format_version, compat_epoch)`` pair, never a single conflated number
and never a broad classifier bucket alone. A checksum-valid source whose
raw ``format_version`` matches a step's declared ``epoch_from`` is not, on
its own, proof the source actually belongs to that step -- its raw
``compat_epoch`` must independently match too (``classify_save_compat_
raw()`` itself never inspects ``compat_epoch`` at all once ``format_
version`` has already resolved the state to ``SAVE_COMPAT_MIGRATABLE_
OLDER``, so a forged/corrupt source can carry a genuinely wrong
``compat_epoch`` while still checksum-validating and classifying
identically to a genuine one). Both ``dry_run()`` and ``run()`` verify the
full exact source pair before ever invoking ``save_format_tool.py``, and
``run()`` independently re-verifies the full exact *target* pair against
the actually-published destination afterwards -- see
``_exact_source_state_mismatch()`` and ``run()`` below. The historic
``None`` ``epoch_from``/``compat_epoch_from`` legacy/absent case ("no
on-media ExpansionSaveMeta record at all") is preserved unchanged as its
own explicit, unambiguous sentinel state, never guessed at or conflated
with a real numbered pair (not even ``(0, 0)``).

See docs/migration_registry.md for the human-readable registry contract.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
SAVE_FORMAT_TOOL = REPO_ROOT / "scripts" / "modernize" / "save_format_tool.py"

# Issue #9 residual-hardening: run() independently re-reads/re-verifies a
# produced destination against the *exact* declared step.epoch_to by
# reusing save_format_tool.py's own struct layout (ExpansionSaveMeta),
# never re-implementing it -- this is strictly a defense-in-depth belt
# for run()'s own contract ("produce and verify exactly epoch_to"), on
# top of (not instead of) save_format_tool.py's own pre-publish
# verification. Same sys.path idiom scripts/modernize/migrations/tests/
# test_registry.py already uses to import the tool as a plain module.
sys.path.insert(0, str(REPO_ROOT / "scripts" / "modernize"))
import save_format_tool as _sft  # noqa: E402

MECHANICAL = "mechanical"
MANUAL = "manual"

# Sentinel distinguishing "caller did not specify compat_epoch_from/
# compat_epoch_to at all" from an explicit, real None (the legacy/absent
# source state) -- see MigrationStep.__post_init__ and its docstring.
_UNSET = object()


@dataclass(frozen=True)
class MigrationStep:
    """A single declared save-compatibility transition.

    Models the *exact* source and target ``(format_version, compat_epoch)``
    pairs independently -- issue #9 residual-hardening, pair-modeling slice:
    a checksum-valid source whose raw formatVersion matches this step's
    declared ``epoch_from`` is *not* sufficient on its own (a forged/corrupt
    source can carry a genuinely different, wrong compatEpoch, e.g.
    formatVersion 1 with compatEpoch 999, and still checksum-validate); every
    declared transition must match its own exact source (format_version,
    compat_epoch) pair, never a formatVersion-only match. Likewise the
    target is never assumed to stamp the same numeric value into both
    fields just because today's two registered transitions happen to.

    ``epoch_from``/``epoch_to`` (format_version) are kept as the historic,
    externally-relied-upon attribute names -- scripts/release_rehearsal/
    consistency.py's check_migration_epoch_reachability() already walks a
    registry's steps by these two names to prove config.mk's live
    EXPANSION_SAVE_COMPAT_EPOCH is reachable, and that file is outside this
    module's own edit domain; nothing here may rename or repurpose them.
    ``compat_epoch_from``/``compat_epoch_to`` are the new, independent
    compat_epoch source/target fields this hardening adds alongside them.

    ``epoch_from is None`` is this registry's explicit, named legacy/absent
    source representation -- "no on-media ExpansionSaveMeta record at all"
    (SAVE_COMPAT_VALID_LEGACY_OR_VANILLA) -- never guessed from, or
    conflated with, any real numbered epoch (not even 0, which this tool
    has never itself produced but which *is* a real, distinct, numbered
    formatVersion a forged source could carry -- see
    ExactSourceEpochEnforcementTests in this module's own tests).
    ``compat_epoch_from`` must be the very same explicit ``None`` exactly
    when ``epoch_from`` is ``None`` (enforced below) -- the legacy/absent
    state is one unambiguous state, never a source pair independently
    guessed field-by-field.
    """

    epoch_from: Optional[int]  # format_version source; None = explicit legacy/absent sentinel (v0)
    epoch_to: int  # format_version target
    kind: str  # MECHANICAL | MANUAL
    description: str
    # compat_epoch_from/compat_epoch_to default to the _UNSET sentinel, never
    # to a guessed numeric value: __post_init__ resolves an _UNSET
    # compat_epoch_from/compat_epoch_to by mirroring epoch_from/epoch_to
    # *only* as a construction-time convenience for call-sites this module's
    # own edit domain cannot reach (scripts/release_rehearsal/tests/
    # test_consistency.py constructs bare MigrationStep(epoch_from=...,
    # epoch_to=..., kind=..., description=...) instances of its own to
    # exercise check_migration_epoch_reachability(), which never reads
    # compat_epoch_from/compat_epoch_to at all). Every REGISTRY entry this
    # module itself declares below always passes both compat_epoch fields
    # explicitly and never relies on this default -- the "no assuming
    # format_version == compat_epoch without an explicit transition
    # contract" rule applies to this registry's own real, live transitions,
    # not to this backward-compatibility constructor convenience.
    compat_epoch_from: Optional[int] = _UNSET  # compat_epoch source; None iff epoch_from is None
    compat_epoch_to: Optional[int] = _UNSET  # compat_epoch target
    manual_steps: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.compat_epoch_from is _UNSET:
            object.__setattr__(self, "compat_epoch_from", self.epoch_from)
        if self.compat_epoch_to is _UNSET:
            object.__setattr__(self, "compat_epoch_to", self.epoch_to)
        if self.kind not in (MECHANICAL, MANUAL):
            raise ValueError(f"kind must be {MECHANICAL!r} or {MANUAL!r}, got {self.kind!r}")
        if self.kind == MANUAL and not self.manual_steps:
            raise ValueError("a manual migration step must declare at least one manual step")
        if self.kind == MECHANICAL and self.manual_steps:
            raise ValueError("a mechanical migration step must not declare manual steps")
        if (self.epoch_from is None) != (self.compat_epoch_from is None):
            raise ValueError(
                "epoch_from and compat_epoch_from must both be the explicit legacy/absent "
                "sentinel (None) together, or both be given as real, numbered values -- "
                "the exact source state is one unambiguous pair, never guessed field-by-field "
                f"(got epoch_from={self.epoch_from!r}, compat_epoch_from={self.compat_epoch_from!r})"
            )
        if self.compat_epoch_to <= (self.compat_epoch_from if self.compat_epoch_from is not None else -1):
            raise ValueError(
                "compat_epoch_to must be greater than compat_epoch_from "
                f"(got compat_epoch_from={self.compat_epoch_from!r}, compat_epoch_to={self.compat_epoch_to!r})"
            )


# Two mechanical transitions scripts/modernize/save_format_tool.py's
# migrate command implements today (both via the same 'migrate'
# subcommand -- it always targets whatever config.mk's real, live
# EXPANSION_SAVE_COMPAT_EPOCH/SAVE_FORMAT_VERSION_CURRENT currently are,
# never a value parameterized by this registry's own epoch_to): "v0" (no
# ExpansionSaveMeta record at all, i.e. SAVE_COMPAT_VALID_LEGACY_OR_
# VANILLA) -> epoch 1, and epoch 1 (SAVE_COMPAT_MIGRATABLE_OLDER once a
# newer epoch is current) -> epoch 2, added for the origin/master merge
# (issue #9 release-branch integration) that brought in issue #18 sprint
# 2's real EXPANSION_SAVE_COMPAT_EPOCH/SAVE_FORMAT_VERSION_CURRENT 1 -> 2
# bump (struct ExpansionUserPrefs, include/expansion_save_prefs.h, now
# occupies part of ExpansionSaveMeta's reserved tail -- see
# docs/save_format.md). Any future EXPANSION_SAVE_COMPAT_EPOCH bump needs
# its own registry entry, added deliberately -- this registry never
# infers a mechanical path that save_format_tool.py does not actually
# implement.
REGISTRY: Tuple[MigrationStep, ...] = (
    MigrationStep(
        epoch_from=None,
        epoch_to=1,
        compat_epoch_from=None,
        compat_epoch_to=1,
        kind=MECHANICAL,
        description=(
            "No on-media ExpansionSaveMeta record (legacy/vanilla save) -> "
            "formatVersion 1/compatEpoch 1. Implemented by "
            "scripts/modernize/save_format_tool.py's 'migrate' subcommand."
        ),
    ),
    MigrationStep(
        epoch_from=1,
        epoch_to=2,
        compat_epoch_from=1,
        compat_epoch_to=2,
        kind=MECHANICAL,
        description=(
            "formatVersion 1/compatEpoch 1 -> formatVersion 2/compatEpoch 2 "
            "(current): struct ExpansionUserPrefs (include/expansion_save_prefs.h) "
            "now occupies part of ExpansionSaveMeta's reserved tail (issue #18 "
            "sprint 2). Classifies SAVE_COMPAT_MIGRATABLE_OLDER (formatVersion "
            "< current) and is implemented by the same "
            "scripts/modernize/save_format_tool.py 'migrate' subcommand, which "
            "now accepts SAVE_COMPAT_MIGRATABLE_OLDER as a migratable source "
            "state and carries forward any bytes already in `reserved` "
            "verbatim rather than overwriting them with a fresh default. Both "
            "formatVersion and compatEpoch happen to be numerically equal on "
            "both ends of this particular declared transition -- an incidental "
            "fact of this transition's own history, never assumed true for any "
            "other/future transition."
        ),
    ),
)


def registry() -> Tuple[MigrationStep, ...]:
    return REGISTRY


def find_step(epoch_from: Optional[int], epoch_to: int) -> Optional[MigrationStep]:
    for step in REGISTRY:
        if step.epoch_from == epoch_from and step.epoch_to == epoch_to:
            return step
    return None


def check_registry() -> List[str]:
    """Deterministic, side-effect-free consistency check of the registry
    itself (no file I/O beyond checking that save_format_tool.py exists for
    every declared mechanical step)."""
    errors: List[str] = []
    seen = set()
    for step in REGISTRY:
        key = (step.epoch_from, step.epoch_to)
        if key in seen:
            errors.append(f"duplicate registry entry for {key}")
        seen.add(key)
        if step.epoch_to <= (step.epoch_from or -1):
            errors.append(f"registry entry {key}: epoch_to must be greater than epoch_from")
        # Defense in depth: independently re-checked here even though
        # MigrationStep.__post_init__ already enforces both of these at
        # construction time -- this function's own contract is a
        # side-effect-free re-audit of whatever REGISTRY actually holds,
        # not merely trusting that every entry was necessarily built
        # through the normal constructor.
        if (step.epoch_from is None) != (step.compat_epoch_from is None):
            errors.append(
                f"registry entry {key}: epoch_from and compat_epoch_from must both be "
                "the explicit legacy/absent sentinel (None) together, or both be given "
                "as real, numbered values"
            )
        elif step.compat_epoch_to <= (step.compat_epoch_from if step.compat_epoch_from is not None else -1):
            errors.append(
                f"registry entry {key}: compat_epoch_to must be greater than compat_epoch_from "
                f"(compat_epoch_from={step.compat_epoch_from!r}, compat_epoch_to={step.compat_epoch_to!r})"
            )
        if step.kind == MECHANICAL and not SAVE_FORMAT_TOOL.is_file():
            errors.append(
                f"registry entry {key} declares a mechanical step but "
                f"{SAVE_FORMAT_TOOL} is missing"
            )
        if step.kind == MANUAL and not step.manual_steps:
            errors.append(f"registry entry {key} is manual but declares no manual_steps")
    return errors


def _expected_pre_migration_state(step: MigrationStep) -> str:
    """The save_format_tool.py classification a source must already have
    *before* `step` runs, mirroring classify_save_compat_raw()'s own
    precedence (magic -> formatVersion -> compatEpoch) rather than
    guessing: `epoch_from is None` means no on-media ExpansionSaveMeta
    record at all (SAVE_COMPAT_VALID_LEGACY_OR_VANILLA -- no magic).
    Any real, numbered `epoch_from` means a valid record whose
    formatVersion is older than SAVE_FORMAT_VERSION_CURRENT (
    SAVE_COMPAT_MIGRATABLE_OLDER) -- classify_save_compat_raw() resolves
    that from formatVersion alone, strictly before it ever looks at
    compatEpoch, so this holds for *any* numbered epoch_from, not only
    the one immediately below today's live current epoch (see
    docs/save_format.md's "Raw-byte compatibility classifier" and its
    epoch-1-vs-2 worked example). A previous version of this helper
    hardcoded 'SAVE_COMPAT_CURRENT' for every non-None epoch_from -- that
    was only ever exercised while the registry had exactly one, `None`-
    sourced entry; it was never correct for a real numbered epoch_from,
    and is fixed here alongside this registry's first such entry
    (`epoch_from=1, epoch_to=2`, issue #9 release-branch/origin-master
    merge)."""
    if step.epoch_from is None:
        return "SAVE_COMPAT_VALID_LEGACY_OR_VANILLA"
    return "SAVE_COMPAT_MIGRATABLE_OLDER"


# States for which save_format_tool.py's own classifier has already
# verified the on-media ExpansionSaveMeta record's checksum -- i.e. its
# raw `format_version` field is genuinely trustworthy, not merely
# present. `SAVE_COMPAT_EMPTY`/`HEADER_CORRUPT`/`METADATA_CORRUPT`/
# `VALID_LEGACY_OR_VANILLA` are deliberately excluded: none of them has a
# checksum-verified format_version to read at all (see
# `classify_save_compat_raw`'s own precedence), so `_exact_source_epoch_
# mismatch` below always falls through to the ordinary `--expect`
# classification check for those, unchanged.
_TRUSTWORTHY_FORMAT_VERSION_STATES = frozenset((
    _sft.SAVE_COMPAT_MIGRATABLE_OLDER,
    _sft.SAVE_COMPAT_CURRENT,
    _sft.SAVE_COMPAT_NEWER_UNSUPPORTED,
    _sft.SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE,
))


def _exact_source_state_mismatch(step: MigrationStep, source: Path) -> "str | None":
    """Issue #9 residual-hardening (fresh-verifier reproduction, finding
    C, extended to the full (format_version, compat_epoch) pair): closes
    a real gap this registry's own `--expect SAVE_COMPAT_MIGRATABLE_OLDER`
    precondition (see `_expected_pre_migration_state` above) left open
    for every step with a real, numbered `epoch_from`. `SAVE_COMPAT_
    MIGRATABLE_OLDER` is a *broad* classification -- "raw formatVersion is
    less than today's live `SAVE_FORMAT_VERSION_CURRENT`" -- which can
    span more than one real, distinct formatVersion at once (today, with
    `SAVE_FORMAT_VERSION_CURRENT == 2`: both formatVersion 1, a real prior
    save, *and* formatVersion 0, which this tool has never itself
    produced and which this registry has no declared `epoch_from=0` step
    for at all, both classify identically as `SAVE_COMPAT_MIGRATABLE_
    OLDER`) -- and, independently, `classify_save_compat_raw()` never even
    inspects `compat_epoch` at all once `format_version` has already
    resolved the state to `SAVE_COMPAT_MIGRATABLE_OLDER` (it only ever
    compares `compat_epoch` in the separate `format_version == current`
    branch) -- so a checksum-valid source whose raw `format_version`
    genuinely matches this step's declared `epoch_from` can still carry
    an arbitrary, wrong raw `compat_epoch` (e.g. `format_version=1`,
    `compat_epoch=999`) and classify identically to a genuine, honest
    epoch-1 save. Reproduced (two independent bypass shapes, both closed
    here):

    * a forged/crafted source whose on-media, checksum-valid
      ExpansionSaveMeta record declares `format_version=0` was silently
      accepted and migrated forward by the declared `epoch_from=1` step
      (`--expect SAVE_COMPAT_MIGRATABLE_OLDER` alone cannot tell 0 and 1
      apart);
    * a forged/crafted source whose `format_version` genuinely is 1 (this
      step's own declared `epoch_from`) but whose `compat_epoch` is an
      arbitrary wrong value (e.g. 999, not this step's declared
      `compat_epoch_from`) was, before this hardening, *also* silently
      accepted -- the registry's own exact-epoch check only ever compared
      `format_version`, never `compat_epoch`, and the classifier itself
      never gates on `compat_epoch` in the `MIGRATABLE_OLDER` branch
      either -- so neither layer alone caught it.

    This independently re-reads `source`'s own raw, on-media
    `format_version` *and* `compat_epoch` fields (never re-derived from,
    or trusting, the classifier's own collapsed bucket alone) and
    confirms *both* are *exactly* `step.epoch_from`/`step.compat_epoch_
    from` before any subprocess is ever invoked -- so an exact-pair
    mismatch on either field is rejected before any mutation, exactly
    like every other precondition this module enforces. Neither field is
    ever mutated/destination-written on a mismatch: this function itself
    performs no I/O beyond a read-only re-read of `source`.

    Only ever applies when `step.epoch_from` is a real, numbered epoch:
    the `None` epoch_from case (`SAVE_COMPAT_VALID_LEGACY_OR_VANILLA`,
    "no on-media record at all") is already its own exact, unambiguous
    state with no numbered pair left to further narrow -- there is
    nothing for this function to add there, so it always returns `None`
    (no mismatch) immediately for that case, deferring entirely to the
    ordinary `--expect` classification check.

    Returns `None` (no mismatch found -- or not independently
    determinable at all, e.g. an unreadable/wrong-size source, or a
    source classifying into one of the four states with no trustworthy
    format_version/compat_epoch to read in the first place) so the caller
    always falls through to its own existing, unchanged subprocess-based
    `--expect` check in every one of those cases; returns a human-
    readable mismatch message (never raises) the moment the raw,
    checksum-verified `format_version` or `compat_epoch` genuinely
    disagrees with this step's declared exact source pair. `format_
    version` is checked first (existing, unchanged message shape) so any
    pre-existing caller depending on that specific wording is unaffected;
    `compat_epoch` is checked second, only once `format_version` already
    matches."""
    if step.epoch_from is None:
        return None
    try:
        image = _sft.read_image(Path(source))
        save_compat_epoch = _sft.resolve_save_compat_epoch(REPO_ROOT)
    except (_sft.SaveFormatError, _sft.ec.ConfigError):
        return None
    header_bytes = image[_sft.HEADER_OFFSET:_sft.HEADER_OFFSET + _sft.HEADER_SIZE]
    meta_bytes = image[_sft.META_OFFSET:_sft.META_OFFSET + _sft.META_SIZE]
    state = _sft.classify_save_compat_raw(header_bytes, meta_bytes, save_compat_epoch)
    if state not in _TRUSTWORTHY_FORMAT_VERSION_STATES:
        return None
    raw_meta = _sft.ExpansionSaveMeta.unpack(meta_bytes)
    raw_epoch = raw_meta.format_version
    if raw_epoch != step.epoch_from:
        return (
            f"{source}'s own raw, checksum-verified on-media formatVersion is exactly "
            f"{raw_epoch}, not this step's declared epoch_from {step.epoch_from} -- "
            f"classifying it broadly as {state!r} is not enough on its own (that bucket "
            "can span more than one real epoch); every declared transition must match "
            "its own exact source epoch, never merely 'some migratable-older source'"
        )
    raw_compat_epoch = raw_meta.compat_epoch
    if raw_compat_epoch != step.compat_epoch_from:
        return (
            f"{source}'s own raw, checksum-verified on-media compatEpoch is exactly "
            f"{raw_compat_epoch}, not this step's declared compat_epoch_from "
            f"{step.compat_epoch_from} -- a matching formatVersion alone is not enough "
            f"on its own (classify_save_compat_raw() never even inspects compatEpoch "
            f"once formatVersion has already resolved the state to {state!r}); every "
            "declared transition must match its own exact source (formatVersion, "
            "compatEpoch) pair, never merely a matching formatVersion"
        )
    return None


def dry_run(step: MigrationStep, source: Path) -> Tuple[int, str]:
    """Deterministic, read-only eligibility check: classifies `source`
    (via save_format_tool.py's 'validate') without writing anything,
    reporting whether a subsequent 'run' would be expected to succeed.
    Never invokes 'migrate' itself."""
    if step.kind == MANUAL:
        steps = "; ".join(step.manual_steps)
        return 4, f"manual migration required, no mechanical dry-run possible: {steps}"

    state_mismatch = _exact_source_state_mismatch(step, source)
    if state_mismatch is not None:
        return 3, f"dry-run: {source} is NOT eligible: {state_mismatch}"

    expect = _expected_pre_migration_state(step)
    result = subprocess.run(
        [sys.executable, str(SAVE_FORMAT_TOOL), "validate", str(source), "--expect", expect],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return 0, f"dry-run: {source} is eligible for {step.description}"
    return 3, f"dry-run: {source} is NOT eligible: {result.stderr.strip() or result.stdout.strip()}"


def run(step: MigrationStep, source: Path, dest: Path, force: bool = False) -> Tuple[int, str]:
    """Executes a mechanical migration strictly out-of-place by shelling
    out to save_format_tool.py's own 'migrate' subcommand (never
    reimplemented here). Refuses (without shelling out) for a manual
    step.

    Issue #9 residual-hardening: a fresh, independent verifier reproduced
    every registry entry's own declared `epoch_from`/`epoch_to` as
    non-executable -- `migrate` was invoked with no way to tell it which
    transition was being asked for, so it always fell back to whatever
    formatVersion/EXPANSION_SAVE_COMPAT_EPOCH config.mk's live values
    happened to be (today, epoch 2) *and* accepted any of the tool's own
    generic MIGRATABLE_SOURCE_STATES regardless of this step's specific
    `epoch_from`. Both gaps are closed here:

    * `--expect <exact source state for this step>` is always passed, so
      a source that is not *this step's* declared `epoch_from`/
      `compat_epoch_from` precondition is rejected before any mutation --
      not merely "some migratable state", which could silently accept a
      source belonging to a different, unrelated transition (the exact
      pair itself is independently re-verified first, before this
      subprocess is even invoked -- see `_exact_source_state_mismatch()`
      above).
    * `--to-format-version step.epoch_to --to-compat-epoch
      step.compat_epoch_to` are always passed *independently* (never the
      conflating `--to-epoch` shorthand), so the produced destination is
      stamped with exactly this step's declared target formatVersion
      *and* compatEpoch pair -- never assumed equal to one another, and
      never whatever the live config happens to be.

    After a successful subprocess invocation (which already re-verifies
    its own output before publish -- see save_format_tool.py's
    cmd_migrate), this function independently re-reads the *published*
    destination once more and re-checks both its raw formatVersion *and*
    compatEpoch fields against `step.epoch_to`/`step.compat_epoch_to`
    themselves, as a second, independent proof that this specific
    declared transition's full (format_version, compat_epoch) contract
    was met -- not merely trusting the subprocess's own self-reported
    exit code, and not merely one of the two fields (a forged/regressed
    tool could get one field right and the other wrong).
    """
    if step.kind == MANUAL:
        steps = "; ".join(step.manual_steps)
        return 4, f"manual migration required, cannot run mechanically: {steps}"
    if Path(source).resolve() == Path(dest).resolve():
        return 6, "source and destination must differ (out-of-place only)"

    state_mismatch = _exact_source_state_mismatch(step, source)
    if state_mismatch is not None:
        return 4, f"{source} rejected before any mutation: {state_mismatch}"

    expected_source_state = _expected_pre_migration_state(step)
    args = [
        sys.executable, str(SAVE_FORMAT_TOOL), "migrate", str(source), str(dest),
        "--to-format-version", str(step.epoch_to),
        "--to-compat-epoch", str(step.compat_epoch_to),
        "--expect", expected_source_state,
    ]
    if force:
        args.append("--force")
    result = subprocess.run(args, capture_output=True, text=True)
    message = result.stdout.strip() or result.stderr.strip()
    if result.returncode != 0:
        return result.returncode, message

    try:
        published = Path(dest).read_bytes()
        produced_meta = _sft.ExpansionSaveMeta.unpack(
            published[_sft.META_OFFSET:_sft.META_OFFSET + _sft.META_SIZE]
        )
    except OSError as error:
        return 1, f"migration reported success but destination could not be re-read for verification: {error}"

    if produced_meta.format_version != step.epoch_to:
        return (
            5,
            f"migration reported success but the published destination's own formatVersion "
            f"is {produced_meta.format_version}, not the declared epoch_to {step.epoch_to} "
            f"(registry entry {step.epoch_from} -> {step.epoch_to})",
        )

    if produced_meta.compat_epoch != step.compat_epoch_to:
        return (
            5,
            f"migration reported success but the published destination's own compatEpoch "
            f"is {produced_meta.compat_epoch}, not the declared compat_epoch_to "
            f"{step.compat_epoch_to} (registry entry compat_epoch {step.compat_epoch_from} -> "
            f"{step.compat_epoch_to}) -- a correct formatVersion alone is not sufficient proof "
            "this declared transition's full target pair was actually produced",
        )

    return 0, message


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="print the registry deterministically")
    sub.add_parser("check", help="validate registry consistency; no file I/O")

    dry_p = sub.add_parser("dry-run", help="read-only eligibility check")
    dry_p.add_argument("--from-epoch", type=int, default=None)
    dry_p.add_argument("--to-epoch", type=int, required=True)
    dry_p.add_argument("--source", type=Path, required=True)

    run_p = sub.add_parser("run", help="execute a mechanical migration out-of-place")
    run_p.add_argument("--from-epoch", type=int, default=None)
    run_p.add_argument("--to-epoch", type=int, required=True)
    run_p.add_argument("--source", type=Path, required=True)
    run_p.add_argument("--dest", type=Path, required=True)
    run_p.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "list":
        for step in REGISTRY:
            print(f"{step.epoch_from} -> {step.epoch_to} [{step.kind}]: {step.description}")
        return 0

    if args.command == "check":
        errors = check_registry()
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if errors:
            return 2
        print(f"migration registry: ok ({len(REGISTRY)} entr{'y' if len(REGISTRY) == 1 else 'ies'})")
        return 0

    step = find_step(args.from_epoch, args.to_epoch)
    if step is None:
        print(
            f"error: no registered migration from {args.from_epoch} to {args.to_epoch}",
            file=sys.stderr,
        )
        return 2

    if args.command == "dry-run":
        code, message = dry_run(step, args.source)
        print(message)
        return code

    code, message = run(step, args.source, args.dest, force=args.force)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
