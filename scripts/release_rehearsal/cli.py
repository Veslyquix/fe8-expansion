#!/usr/bin/env python3
"""Top-level release rehearsal CLI (issue #9).

Two subcommands, wired to `make release-check` / `make release-rehearse`:

  check     Build the full release manifest (scripts/release_rehearsal/manifest.py)
            and print it. Exit 0 for any well-formed report -- the report's
            own "status" field says "mechanically eligible" or "blocked";
            both are valid, expected, non-error outcomes of a correctly
            running checker. Exit 2 only for an actionable input/schema
            error (a tooling defect, not an honestly-recorded unresolved
            fact).

  rehearse  Run the deterministic double-archive-build + hash-compare
            rehearsal and the clean-rebuild blocker check
            (scripts/release_rehearsal/archive_rehearsal.py), then fold in the
            manifest's provenance/source-guard findings so the exact
            unresolved license/assets/mgfembp inventory is always part of
            the printed report. Never uploads or retains any archive.

Never claims "mechanically eligible" while any sub-check actually failed
closed -- see docs/release_process.md's "Exit code contract" section.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.release_rehearsal import archive_rehearsal as ar  # noqa: E402
from scripts.release_rehearsal import manifest as rm  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "scripts" / "modernize"))
import expansion_config as ec  # noqa: E402
from scripts.release_rehearsal import source_guard as sg  # noqa: E402


def cmd_check(args) -> int:
    try:
        manifest = rm.build_manifest(
            args.repo_root,
            args.config,
            args.abi,
            args.rom_size,
            target_sha_override=args.target_sha,
            embedded_short_sha=args.embedded_short_sha,
        )
    except (rm.ManifestError, ec.ConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"release-check status: {manifest['status']}", file=sys.stderr)
    if manifest["status"] == "blocked":
        print("release-check: BLOCKED (this is the expected, truthful result -- see reasons above)", file=sys.stderr)
        for reason in manifest["reasons"]:
            print(f"  - {reason}", file=sys.stderr)
    return 0


def cmd_rehearse(args) -> int:
    try:
        allowlist = sg.load_allowlist(args.repo_root / "docs" / "release_data" / "source_allowlist.json")
        archive_report = ar.rehearse_archive_twice(args.repo_root, allowlist)
    except (sg.SourceGuardError, ar.ArchiveRehearsalError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    rebuild_report = ar.rebuild_rehearsal_blocker(args.repo_root)

    try:
        manifest = rm.build_manifest(
            args.repo_root, args.config, args.abi, args.rom_size,
            target_sha_override=args.target_sha,
        )
    except (rm.ManifestError, ec.ConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    report = {
        "archive": archive_report,
        "rebuild": rebuild_report,
        "provenance": manifest["provenance"],
        "source_guard": manifest["source_guard"],
        "status": manifest["status"],
        "reasons": manifest["reasons"],
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if not archive_report["match"]:
        print("error: two rehearsal archive builds produced different hashes", file=sys.stderr)
        return 2

    print("release-rehearse: two independent archive builds are byte-identical (deterministic)", file=sys.stderr)
    print(f"release-rehearse: candidate publication status: {report['status']}", file=sys.stderr)
    if report["status"] == "blocked":
        print("release-rehearse: BLOCKED (expected, truthful result):", file=sys.stderr)
        for reason in report["reasons"]:
            print(f"  - {reason}", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--config", default="release", choices=("debug", "release"))
    parser.add_argument("--abi", default="aapcs", choices=("aapcs", "apcs-gnu"))
    parser.add_argument("--rom-size", default="16M")
    parser.add_argument("--target-sha", default=None)
    parser.add_argument("--embedded-short-sha", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("rehearse")
    args = parser.parse_args(argv)

    if args.command == "check":
        return cmd_check(args)
    return cmd_rehearse(args)


if __name__ == "__main__":
    sys.exit(main())
