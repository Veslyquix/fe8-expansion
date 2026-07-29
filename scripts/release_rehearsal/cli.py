#!/usr/bin/env python3
"""Top-level release rehearsal CLI (issue #9).

Two subcommands, wired to `make release-check` / `make release-rehearse`:

  check     Build the full release manifest (scripts/release_rehearsal/manifest.py)
            and print it. By default, exit 0 for any well-formed report --
            the report's own "status" field says "mechanically eligible" or
            "blocked"; both are valid, expected, non-error outcomes of a
            correctly running checker. Exit 2 for an actionable input/
            schema error (a tooling defect, not an honestly-recorded
            unresolved fact).

  rehearse  Run the deterministic double-archive-build + hash-compare
            rehearsal and the clean-rebuild blocker check
            (scripts/release_rehearsal/archive_rehearsal.py), then fold in the
            manifest's provenance/source-guard findings so the exact
            unresolved license/assets/mgfembp inventory is always part of
            the printed report. Never uploads or retains any archive.

Both subcommands additionally accept a **machine-distinct status/exit
contract** (issue #9 verifier remediation) -- no consumer should ever have
to grep prose to learn the outcome:

  --require-eligible     Publication-eligibility gate. Exits
                          EXIT_NOT_ELIGIBLE (1) if the candidate status is
                          not exactly "mechanically eligible" (e.g. it is
                          "blocked", which is this repository's current,
                          expected, correct state); exits 0 only if it
                          truly is eligible.
  --expect-status STATUS Process-health/expected-status gate. STATUS must
                          be exactly "blocked" or "mechanically-eligible"
                          (hyphenated at the CLI layer; mapped internally
                          to the manifest's own "blocked"/"mechanically
                          eligible" strings). Exits 0 only if the actual
                          status matches exactly; exits EXIT_STATUS_
                          MISMATCH (3) on any mismatch. There is no
                          default/implicit value -- the caller must name
                          the exact status they expect, every time.

`--require-eligible` and `--expect-status` are mutually exclusive (each is
its own distinct gate; combining them would make the exit code ambiguous
about which gate failed). Canonical JSON always goes to stdout; every
human-readable diagnostic goes to stderr -- never the reverse -- so a
consumer can always `... | python3 -m json.tool` (or any stdlib
`json.load`) without ever parsing prose.

Exit code contract summary (both subcommands):

  0  the requested gate's own condition is satisfied (plain report mode:
     any well-formed report; --require-eligible: candidate IS eligible;
     --expect-status: actual status matches exactly).
  1  EXIT_NOT_ELIGIBLE -- only reachable via --require-eligible when the
     candidate is not eligible (a truthful, expected "blocked" result is
     not itself an error, but this flag exists precisely to make a
     publication pipeline fail loudly on it).
  2  EXIT_TOOLING_ERROR -- an actionable input/schema defect (checked
     first, before either gate is evaluated).
  3  EXIT_STATUS_MISMATCH -- only reachable via --expect-status when the
     actual status is not the exact one requested.

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
from scripts.release_rehearsal import workflow_guard as wg  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "scripts" / "modernize"))
import expansion_config as ec  # noqa: E402
from scripts.release_rehearsal import source_guard as sg  # noqa: E402

STATUS_BLOCKED = "blocked"
STATUS_MECHANICALLY_ELIGIBLE = "mechanically eligible"

# The CLI-facing --expect-status vocabulary is hyphenated/space-free (a
# friendlier shell token than the manifest's own "mechanically eligible",
# which contains a literal space); mapped 1:1 to the manifest's real
# status strings so there is exactly one source of truth for what the
# status values actually are.
EXPECT_STATUS_CHOICES = {"blocked": STATUS_BLOCKED, "mechanically-eligible": STATUS_MECHANICALLY_ELIGIBLE}

EXIT_OK = 0
EXIT_NOT_ELIGIBLE = 1
EXIT_TOOLING_ERROR = 2
EXIT_STATUS_MISMATCH = 3


def _apply_status_gates(report: dict, args, label: str) -> int:
    """Shared machine-distinct status/exit contract for both `check` and
    `rehearse`: applies whichever of --require-eligible/--expect-status
    (if either) was requested, against `report["status"]`. Returns the
    final process exit code. Never prints prose to stdout -- only to
    stderr -- and never invents a status value that is not already
    exactly what the manifest/rehearsal report computed."""
    status = report["status"]
    if args.expect_status is not None:
        expected = EXPECT_STATUS_CHOICES[args.expect_status]
        if status != expected:
            print(
                f"{label}: --expect-status {args.expect_status!r} requested but actual status is "
                f"{status!r} (expected {expected!r}) -- exit {EXIT_STATUS_MISMATCH}",
                file=sys.stderr,
            )
            return EXIT_STATUS_MISMATCH
        print(f"{label}: status matches expected {expected!r} -- exit {EXIT_OK}", file=sys.stderr)
        return EXIT_OK

    if args.require_eligible:
        if status != STATUS_MECHANICALLY_ELIGIBLE:
            print(
                f"{label}: --require-eligible requested but candidate status is {status!r}, "
                f"not {STATUS_MECHANICALLY_ELIGIBLE!r} -- exit {EXIT_NOT_ELIGIBLE}",
                file=sys.stderr,
            )
            return EXIT_NOT_ELIGIBLE
        print(f"{label}: candidate is {STATUS_MECHANICALLY_ELIGIBLE!r} -- exit {EXIT_OK}", file=sys.stderr)
        return EXIT_OK

    return EXIT_OK


# --- Dynamic $GITHUB_STEP_SUMMARY rendering (issue #9 verifier remediation) -
#
# Entirely data-driven from whatever "status"/"reasons"/sub-report fields
# are actually present in a build_manifest()/cmd_rehearse()-shaped report
# dict -- never a hardcoded "BLOCKED" string. If a future, separately-
# authorized change ever makes the candidate "mechanically eligible", this
# renders THAT truthfully, automatically, with no code change required
# here.

_SUB_REPORT_OK_RULES = {
    "changelog": lambda value: value.get("ok"),
    "migrations": lambda value: value.get("ok"),
    "allowlist": lambda value: value.get("ok"),
    "version_ledger": lambda value: value.get("ok"),
    "c_fallback_metadata": lambda value: value.get("ok"),
    "migration_reachability": lambda value: value.get("ok"),
    "doc_links": lambda value: value.get("ok"),
    "provenance": lambda value: value.get("status") == STATUS_MECHANICALLY_ELIGIBLE,
    "source_guard": lambda value: value.get("status") == "pass",
    "rebuild": lambda value: value.get("status") == "verified_success",
    "archive": lambda value: bool(value.get("match")),
}
# Rendered in this fixed order when present, for a byte-stable summary
# given the same input report.
_SUB_REPORT_ORDER = (
    "allowlist", "changelog", "version_ledger", "c_fallback_metadata",
    "migration_reachability", "doc_links", "migrations", "provenance", "source_guard",
    "archive", "rebuild",
)


def render_markdown_summary(report: dict) -> str:
    """Deterministically renders `report` (a build_manifest()-shaped dict,
    or scripts.release_rehearsal.cli's merged `rehearse` report) as
    GitHub Actions Job Summary Markdown. Every word describing the
    candidate's status is read from `report` itself -- nothing here is a
    fixed/hardcoded status string."""
    status = report.get("status", "unknown")
    lines = ["## Release Rehearsal", "", f"**Publication status:** `{status}`", ""]

    if status == STATUS_MECHANICALLY_ELIGIBLE:
        lines.append(
            "This candidate mechanically passed every automated check below. "
            "This is **not** by itself a publication approval -- a human "
            "maintainer must still separately authorize publication (see "
            "`docs/release_process.md`)."
        )
    else:
        lines.append(f"Candidate status is `{status}` for the following reason(s):")
        lines.append("")
        reasons = report.get("reasons") or ["(no reasons recorded)"]
        for reason in reasons:
            lines.append(f"- {reason}")
    lines.append("")

    rows = []
    for key in _SUB_REPORT_ORDER:
        if key not in report or not isinstance(report[key], dict):
            continue
        rule = _SUB_REPORT_OK_RULES.get(key)
        if rule is None:
            continue
        ok = rule(report[key])
        rows.append((key, ok))
    if rows:
        lines.append("| Check | Status |")
        lines.append("|---|---|")
        for key, ok in rows:
            mark = "✅" if ok else "❌"
            lines.append(f"| `{key}` | {mark} |")
        lines.append("")

    lines.append(
        "This workflow is read-only: no tag, release, asset, comment, or "
        "protected-environment mutation ever occurs here. See "
        "`docs/release_process.md` and `docs/release_data/provenance/*.json` "
        "for the exact unresolved inventory."
    )
    return "\n".join(lines) + "\n"


def cmd_summary(args) -> int:
    """Prints a dynamically-rendered Markdown job summary for the current
    candidate to stdout (intended for
    `... >> "$GITHUB_STEP_SUMMARY"` in CI). Exit-code contract matches
    `check`'s plain-report mode: 0 for a well-formed report of any status,
    2 for an actionable tooling/input defect."""
    try:
        manifest = rm.build_manifest(
            args.repo_root, args.config, args.abi, args.rom_size,
            target_sha_override=args.target_sha,
        )
    except (rm.ManifestError, ec.ConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_TOOLING_ERROR
    sys.stdout.write(render_markdown_summary(manifest))
    print(f"release-summary: rendered for status {manifest['status']!r}", file=sys.stderr)
    return EXIT_OK


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
        return EXIT_TOOLING_ERROR

    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"release-check status: {manifest['status']}", file=sys.stderr)
    if manifest["status"] == STATUS_BLOCKED:
        print("release-check: BLOCKED (this is the expected, truthful result -- see reasons above)", file=sys.stderr)
        for reason in manifest["reasons"]:
            print(f"  - {reason}", file=sys.stderr)

    return _apply_status_gates(manifest, args, "release-check")


def cmd_rehearse(args) -> int:
    map_hex_exceptions_path = args.repo_root / "docs" / "release_data" / "map_hex_exceptions.json"
    try:
        allowlist = sg.load_allowlist(args.repo_root / "docs" / "release_data" / "source_allowlist.json")
        map_hex_exceptions = (
            sg.load_map_hex_exceptions(map_hex_exceptions_path)
            if map_hex_exceptions_path.is_file() else frozenset()
        )
        archive_report = ar.rehearse_archive_twice(
            args.repo_root, allowlist, target_sha=args.target_sha, map_hex_exceptions=map_hex_exceptions,
        )
    except (sg.SourceGuardError, ar.ArchiveRehearsalError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_TOOLING_ERROR

    rebuild_report = ar.rebuild_rehearsal_blocker(args.repo_root)

    try:
        manifest = rm.build_manifest(
            args.repo_root, args.config, args.abi, args.rom_size,
            target_sha_override=args.target_sha,
        )
    except (rm.ManifestError, ec.ConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_TOOLING_ERROR

    report = {
        "archive": archive_report,
        "rebuild": rebuild_report,
        "provenance": manifest["provenance"],
        "source_guard": manifest["source_guard"],
        "allowlist": manifest["allowlist"],
        "version_ledger": manifest["version_ledger"],
        "status": manifest["status"],
        "reasons": manifest["reasons"],
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if not archive_report["match"]:
        print("error: two rehearsal archive builds produced different hashes", file=sys.stderr)
        return EXIT_TOOLING_ERROR

    print("release-rehearse: two independent archive builds are byte-identical (deterministic)", file=sys.stderr)
    print(f"release-rehearse: candidate publication status: {report['status']}", file=sys.stderr)
    if report["status"] == STATUS_BLOCKED:
        print("release-rehearse: BLOCKED (expected, truthful result):", file=sys.stderr)
        for reason in report["reasons"]:
            print(f"  - {reason}", file=sys.stderr)

    return _apply_status_gates(report, args, "release-rehearse")


def cmd_workflow_guard(args) -> int:
    try:
        text = args.workflow.read_text(encoding="utf-8")
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_TOOLING_ERROR
    violations = wg.validate_workflow_text(text)
    print(json.dumps({"workflow": str(args.workflow), "violations": violations}, indent=2, sort_keys=True))
    if violations:
        print(f"workflow-guard: {len(violations)} finding(s) -- exit 1", file=sys.stderr)
        return 1
    print("workflow-guard: ok -- exit 0", file=sys.stderr)
    return EXIT_OK


def _add_status_gate_arguments(subparser) -> None:
    group = subparser.add_mutually_exclusive_group()
    group.add_argument(
        "--require-eligible", action="store_true",
        help=f"exit {EXIT_NOT_ELIGIBLE} if status is not exactly {STATUS_MECHANICALLY_ELIGIBLE!r}",
    )
    group.add_argument(
        "--expect-status", choices=sorted(EXPECT_STATUS_CHOICES), default=None,
        help=f"exit {EXIT_OK} only if status matches exactly; exit {EXIT_STATUS_MISMATCH} otherwise",
    )


def _add_common_arguments(subparser) -> None:
    """Shared repo/build-identity options, added to *each subparser*
    (rather than only the top-level parser) so they may be given either
    before or after the subcommand name -- e.g. both
    `cli.py --target-sha X rehearse` and `cli.py rehearse --target-sha X`
    work identically. A parent-only option in a subparsers-based argparse
    CLI is otherwise silently unusable after the subcommand token, which
    is the natural place most users (and this module's own tests) expect
    to put it."""
    subparser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    subparser.add_argument("--config", default="release", choices=("debug", "release"))
    subparser.add_argument("--abi", default="aapcs", choices=("aapcs", "apcs-gnu"))
    subparser.add_argument("--rom-size", default="16M")
    subparser.add_argument("--target-sha", default=None)
    subparser.add_argument("--embedded-short-sha", default=None)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser("check")
    _add_common_arguments(check_p)
    _add_status_gate_arguments(check_p)

    rehearse_p = sub.add_parser("rehearse")
    _add_common_arguments(rehearse_p)
    _add_status_gate_arguments(rehearse_p)

    guard_p = sub.add_parser("workflow-guard", help="dynamic machine-JSON workflow permission/safety guard")
    guard_p.add_argument("workflow", type=Path)

    summary_p = sub.add_parser("summary", help="render a dynamic $GITHUB_STEP_SUMMARY-ready Markdown report")
    _add_common_arguments(summary_p)

    args = parser.parse_args(argv)

    if args.command == "check":
        return cmd_check(args)
    if args.command == "rehearse":
        return cmd_rehearse(args)
    if args.command == "summary":
        return cmd_summary(args)
    return cmd_workflow_guard(args)


if __name__ == "__main__":
    sys.exit(main())
