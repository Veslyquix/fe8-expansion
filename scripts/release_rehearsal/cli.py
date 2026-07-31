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

from scripts.release_rehearsal import action_pins as ap  # noqa: E402
from scripts.release_rehearsal import allowlist as al  # noqa: E402
from scripts.release_rehearsal import archive_rehearsal as ar  # noqa: E402
from scripts.release_rehearsal import git_source as gs  # noqa: E402
from scripts.release_rehearsal import manifest as rm  # noqa: E402
from scripts.release_rehearsal import provenance as prov  # noqa: E402
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

# --- Single, uniform top-level exception boundary (issue #9 verifier -----
# remediation) for `check`, `summary`, and `rehearse` ----------------------
#
# Every one of these classes represents an *expected*, actionable tool/
# input/repository defect -- never a business "blocked" fact (which is
# always a well-formed report with a "status" field, not an exception),
# and never a programming bug this tooling should hide. A well-formed
# 40-lowercase-hex --target-sha that simply does not resolve to a real
# object (GitSourceError), an archive/source-guard hard-deny refusal
# (ArchiveRehearsalError/SourceGuardError), a malformed allowlist/
# provenance/manifest input (AllowlistError/ProvenanceError/
# ManifestError/ConfigError), or a subprocess/filesystem failure
# (OSError, which also covers FileNotFoundError e.g. a missing `git`
# binary) must never surface as an unhandled Python traceback -- doing so
# would exit 1, colliding with the unrelated, deliberate EXIT_NOT_ELIGIBLE
# meaning. Every one of these is instead converted here into a controlled
# EXIT_TOOLING_ERROR (2) with an actionable stderr message. Anything NOT
# in this tuple still raises/tracebacks, on purpose: this is deliberately
# not a blanket `except Exception`, so an actual bug in this tooling is
# never silently absorbed alongside a genuinely expected input error.
EXPECTED_TOOLING_ERRORS = (
    rm.ManifestError,
    ec.ConfigError,
    sg.SourceGuardError,
    ar.ArchiveRehearsalError,
    gs.GitSourceError,
    al.AllowlistError,
    prov.ProvenanceError,
    OSError,
)


def _run_guarded(label: str, func, args) -> int:
    """The single, shared top-level exception boundary `main()` routes
    `check`/`summary`/`rehearse` through. `func(args)` must itself return
    the correct process exit code for every *expected* outcome (including
    a well-formed "blocked" report, which is a normal return value, never
    an exception); this wrapper's only job is to guarantee that any of
    `EXPECTED_TOOLING_ERRORS` raised anywhere in that call graph -- no
    matter how deeply nested (manifest -> allowlist/provenance/
    source_guard/archive_rehearsal -> git_source) -- is converted into
    EXIT_TOOLING_ERROR with an actionable message instead of ever
    reaching the interpreter as a raw traceback."""
    try:
        return func(args)
    except EXPECTED_TOOLING_ERRORS as error:
        print(f"{label}: error: {error}", file=sys.stderr)
        return EXIT_TOOLING_ERROR


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
    "tree_coverage": lambda value: value.get("ok"),
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
    "allowlist", "tree_coverage", "changelog", "version_ledger", "c_fallback_metadata",
    "migration_reachability", "doc_links", "migrations", "provenance", "source_guard",
    "archive", "rebuild",
)

# A real "blocked" report on this repository today carries 200+ individual
# per-category provenance reasons (one honestly-unresolved NOASSERTION
# fact per tracked category); rendering all of them verbatim into a CI
# job summary is technically dynamic/accurate but unreadable. Cap the
# rendered list and point at the full JSON for the rest -- purely a
# presentation choice, never a truncation of the underlying report data
# (the full "reasons" list is always in the JSON printed by `check`/
# `rehearse`, never only in this Markdown rendering).
_MAX_RENDERED_REASONS = 25


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
        for reason in reasons[:_MAX_RENDERED_REASONS]:
            lines.append(f"- {reason}")
        if len(reasons) > _MAX_RENDERED_REASONS:
            lines.append(
                f"- ... and {len(reasons) - _MAX_RENDERED_REASONS} more reason(s) "
                "(see the full JSON report, e.g. `make release-check`, for all of them)"
            )
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
    2 for an actionable tooling/input defect -- any of
    `EXPECTED_TOOLING_ERRORS` raised while building the manifest (e.g. a
    well-formed but nonexistent --target-sha, or a non-git repo-root
    missing its required --target-sha override) is caught by `main()`'s
    shared `_run_guarded` boundary, never left to traceback here."""
    manifest = rm.build_manifest(
        args.repo_root, args.config, args.abi, args.rom_size,
        target_sha_override=args.target_sha,
    )
    sys.stdout.write(render_markdown_summary(manifest))
    print(f"release-summary: rendered for status {manifest['status']!r}", file=sys.stderr)
    return EXIT_OK


def cmd_check(args) -> int:
    """Builds and prints the full release manifest. Any of
    `EXPECTED_TOOLING_ERRORS` (a well-formed but nonexistent
    --target-sha, a non-git repo-root missing its required --target-sha
    override, a malformed allowlist/provenance/changelog input, etc.) is
    caught by `main()`'s shared `_run_guarded` boundary -- never left to
    traceback here, and never confusable with EXIT_NOT_ELIGIBLE (1)."""
    manifest = rm.build_manifest(
        args.repo_root,
        args.config,
        args.abi,
        args.rom_size,
        target_sha_override=args.target_sha,
        embedded_short_sha=args.embedded_short_sha,
    )

    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"release-check status: {manifest['status']}", file=sys.stderr)
    if manifest["status"] == STATUS_BLOCKED:
        print("release-check: BLOCKED (this is the expected, truthful result -- see reasons above)", file=sys.stderr)
        for reason in manifest["reasons"]:
            print(f"  - {reason}", file=sys.stderr)

    return _apply_status_gates(manifest, args, "release-check")


def cmd_rehearse(args) -> int:
    """Runs the deterministic double-archive-build + rebuild-blocker
    rehearsal, then folds in the manifest's provenance/source-guard/
    allowlist/version-ledger findings. Any of `EXPECTED_TOOLING_ERRORS`
    is caught by `main()`'s shared `_run_guarded` boundary -- never left
    to traceback here.

    `target_sha` is resolved and format-/existence-validated **once, up
    front** (`rm.resolve_target_sha` -- the exact same single source of
    truth `build_manifest()` itself uses), *before* attempting either the
    archive build or the rebuild-eligibility check: this is what makes
    the documented non-git/extracted candidate path's required exact
    40-lowercase-hex --target-sha override actually enforced before any
    other work (never silently proceeding with an unbound/omitted
    identity for a non-git tree, the way the archive step alone would if
    it resolved this independently), and it is exactly the identity bound
    into both the archive report and the manifest below -- never two
    independently-resolved values that could theoretically disagree."""
    target_sha = rm.resolve_target_sha(args.repo_root, args.target_sha)

    map_hex_exceptions_path = args.repo_root / "docs" / "release_data" / "map_hex_exceptions.json"
    allowlist = sg.load_allowlist(args.repo_root / "docs" / "release_data" / "source_allowlist.json")
    map_hex_exceptions = (
        sg.load_map_hex_exceptions(map_hex_exceptions_path)
        if map_hex_exceptions_path.is_file() else frozenset()
    )
    archive_report = ar.rehearse_archive_twice(
        args.repo_root, allowlist, target_sha=target_sha, map_hex_exceptions=map_hex_exceptions,
    )

    rebuild_report = ar.rebuild_rehearsal_blocker(args.repo_root)

    manifest = rm.build_manifest(
        args.repo_root, args.config, args.abi, args.rom_size,
        target_sha_override=target_sha,
    )

    report = {
        "archive": archive_report,
        "rebuild": rebuild_report,
        "provenance": manifest["provenance"],
        "source_guard": manifest["source_guard"],
        "allowlist": manifest["allowlist"],
        "tree_coverage": manifest["tree_coverage"],
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
    """Validates `args.workflow`'s own permission/network/safety contract
    (`workflow_guard.validate_workflow_text`, which now includes the
    generalized `check_uses_pins` exact-40-hex-SHA pin requirement for
    every external action) **and** the separate, committed action-pin
    inventory cross-check (`action_pins.check` -- issue #9 mandatory
    correction #1: the workflow's pins and
    `docs/release_data/action_pins.json` must agree exactly, in both
    directions). Both are folded into one JSON report and one shared
    0/1/2 exit contract, since both are the same underlying "is this
    workflow's own safety/pin contract intact" question `make
    release-workflow-guard` answers -- see docs/release_process.md's
    "Workflow guard is advisory, not authorization" section: a clean
    result here is necessary, never sufficient, for eligibility."""
    try:
        text = args.workflow.read_text(encoding="utf-8")
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_TOOLING_ERROR
    violations = list(wg.validate_workflow_text(text))
    action_pin_inventory_path = REPO_ROOT / ap.DEFAULT_INVENTORY_PATH
    try:
        action_pin_violations = ap.check(
            args.workflow, action_pin_inventory_path, workflow_key=args.workflow.as_posix(),
        )
    except ap.ActionPinError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_TOOLING_ERROR
    violations = sorted(set(violations) | set(action_pin_violations))
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

    # `check`/`rehearse`/`summary` all run through the single, shared
    # top-level exception boundary (`_run_guarded` / `EXPECTED_TOOLING_
    # ERRORS` above); `workflow-guard` only ever reads a single workflow
    # file and already handles its own OSError inline (a distinct,
    # simpler exit-code contract -- 0/1, not 0/1/2/3 -- documented in its
    # own module docstring), so it is deliberately left as-is here.
    if args.command == "check":
        return _run_guarded("release-check", cmd_check, args)
    if args.command == "rehearse":
        return _run_guarded("release-rehearse", cmd_rehearse, args)
    if args.command == "summary":
        return _run_guarded("release-summary", cmd_summary, args)
    return cmd_workflow_guard(args)


if __name__ == "__main__":
    sys.exit(main())
