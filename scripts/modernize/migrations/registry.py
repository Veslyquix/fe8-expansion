#!/usr/bin/env python3
"""Save-format migration registry (issue #9).

Declares every known save-compatibility-epoch transition and whether it is
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

MECHANICAL = "mechanical"
MANUAL = "manual"


@dataclass(frozen=True)
class MigrationStep:
    epoch_from: Optional[int]  # None means "no metadata record at all" (v0)
    epoch_to: int
    kind: str  # MECHANICAL | MANUAL
    description: str
    manual_steps: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.kind not in (MECHANICAL, MANUAL):
            raise ValueError(f"kind must be {MECHANICAL!r} or {MANUAL!r}, got {self.kind!r}")
        if self.kind == MANUAL and not self.manual_steps:
            raise ValueError("a manual migration step must declare at least one manual step")
        if self.kind == MECHANICAL and self.manual_steps:
            raise ValueError("a mechanical migration step must not declare manual steps")


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
        kind=MECHANICAL,
        description=(
            "No on-media ExpansionSaveMeta record (legacy/vanilla save) -> "
            "epoch 1. Implemented by "
            "scripts/modernize/save_format_tool.py's 'migrate' subcommand."
        ),
    ),
    MigrationStep(
        epoch_from=1,
        epoch_to=2,
        kind=MECHANICAL,
        description=(
            "formatVersion 1 (epoch 1) -> formatVersion 2 (epoch 2, current): "
            "struct ExpansionUserPrefs (include/expansion_save_prefs.h) now "
            "occupies part of ExpansionSaveMeta's reserved tail (issue #18 "
            "sprint 2). Classifies SAVE_COMPAT_MIGRATABLE_OLDER (formatVersion "
            "< current) and is implemented by the same "
            "scripts/modernize/save_format_tool.py 'migrate' subcommand, which "
            "now accepts SAVE_COMPAT_MIGRATABLE_OLDER as a migratable source "
            "state and carries forward any bytes already in `reserved` "
            "verbatim rather than overwriting them with a fresh default."
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


def dry_run(step: MigrationStep, source: Path) -> Tuple[int, str]:
    """Deterministic, read-only eligibility check: classifies `source`
    (via save_format_tool.py's 'validate') without writing anything,
    reporting whether a subsequent 'run' would be expected to succeed.
    Never invokes 'migrate' itself."""
    if step.kind == MANUAL:
        steps = "; ".join(step.manual_steps)
        return 4, f"manual migration required, no mechanical dry-run possible: {steps}"

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
    step."""
    if step.kind == MANUAL:
        steps = "; ".join(step.manual_steps)
        return 4, f"manual migration required, cannot run mechanically: {steps}"
    if Path(source).resolve() == Path(dest).resolve():
        return 6, "source and destination must differ (out-of-place only)"
    args = [sys.executable, str(SAVE_FORMAT_TOOL), "migrate", str(source), str(dest)]
    if force:
        args.append("--force")
    result = subprocess.run(args, capture_output=True, text=True)
    message = result.stdout.strip() or result.stderr.strip()
    return result.returncode, message


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
