"""Command-line entry point.

Subcommand safety summary (see docs/upstream-porting.md for the full
workflow):

  init-state     writes the state file once, seeded from a real local SHA.
  scan           READ-ONLY. Never fetches, never writes state.
  drift          READ-ONLY. Never fetches, never writes state.
  report         READ-ONLY w.r.t. Git refs/history. Writes report+patch files
                 only into a confirmed-gitignored output directory, only for
                 explicitly selected commit SHAs.
  update-state   The only subcommand that mutates the committed state file.
                 Requires explicit, individually-justified arguments.
  fetch          The only subcommand that touches the network. Refuses to
                 run unless the target remote's URL matches the pinned
                 canonical upstream URL exactly.
  verify         Builds/checks the CURRENT TRUSTED WORKTREE using existing
                 gates. Never builds the upstream ref/tree.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from typing import List, Optional, Sequence

from . import constants, drift as drift_mod, git_utils, report as report_mod
from . import scan as scan_mod
from . import state as state_mod
from . import verify as verify_mod


def _repo_root(explicit: Optional[str]) -> str:
    if explicit:
        return os.path.abspath(explicit)
    proc_cwd = os.getcwd()
    try:
        import subprocess

        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=proc_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except OSError:
        pass
    return proc_cwd


def _state_path(repo_root: str, explicit: Optional[str]) -> str:
    path = explicit or constants.DEFAULT_STATE_PATH
    if not os.path.isabs(path):
        path = os.path.join(repo_root, path)
    return path


def _now_iso(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def verify_remote_or_raise(repo_root: str, remote_name: str) -> str:
    url = git_utils.remote_url(remote_name, repo_root)
    if url != constants.CANONICAL_UPSTREAM_URL:
        raise git_utils.GitError(
            f"refusing to fetch: remote {remote_name!r} URL is {url!r}, "
            f"expected pinned canonical URL {constants.CANONICAL_UPSTREAM_URL!r}"
        )
    return url


def _print(obj_or_text, as_json: bool, out_path: Optional[str]) -> None:
    if as_json:
        text = json.dumps(obj_or_text, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    else:
        text = obj_or_text if isinstance(obj_or_text, str) else str(obj_or_text)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="upstream_port",
        description="Read-only-by-default canonical upstream port tooling (Issue #12).",
    )
    parser.add_argument("--repo", default=None, help="Repo root (default: auto-detect via git)")
    parser.add_argument("--state", default=None, help="State file path (default: %s)" % constants.DEFAULT_STATE_PATH)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-state", help="Create the state file, seeded from a real local ref.")
    p_init.add_argument("--ref", default=f"{constants.DEFAULT_REMOTE_NAME}/master")
    p_init.add_argument("--remote", default=constants.DEFAULT_REMOTE_NAME)
    p_init.add_argument("--force", action="store_true", help="Overwrite an existing state file.")

    p_scan = sub.add_parser("scan", help="READ-ONLY: list unreviewed commits up to --ref.")
    p_scan.add_argument("--ref", required=True)
    p_scan.add_argument("--format", choices=("json", "text"), default="text")
    p_scan.add_argument("--output", default=None)

    p_drift = sub.add_parser("drift", help="READ-ONLY: detect stale state / drift for --ref.")
    p_drift.add_argument("--ref", required=True)
    p_drift.add_argument("--format", choices=("json", "text"), default="text")
    p_drift.add_argument("--output", default=None)

    p_report = sub.add_parser(
        "report", help="Generate a review report + patches for EXPLICITLY selected SHAs."
    )
    p_report.add_argument("--ref", required=True)
    p_report.add_argument("--remote", default=None)
    p_report.add_argument("--sha", action="append", required=True, dest="shas")
    p_report.add_argument("--out-dir", default=None)

    p_update = sub.add_parser("update-state", help="The only state-mutating subcommand.")
    update_sub = p_update.add_subparsers(dest="update_command", required=True)

    p_mark = update_sub.add_parser("mark", help="Record a reviewed status for one commit SHA.")
    p_mark.add_argument("--sha", required=True)
    p_mark.add_argument("--status", required=True, choices=constants.STATUSES)
    p_mark.add_argument("--rationale", default="")
    p_mark.add_argument("--evidence", default="")
    p_mark.add_argument("--now", default=None, help="ISO8601 timestamp override (tests only)")
    p_mark.add_argument("--force", action="store_true")

    p_scanrec = update_sub.add_parser("record-scan", help="Advance last_scanned after a reviewed scan.")
    p_scanrec.add_argument("--ref", required=True)
    p_scanrec.add_argument("--sha", default=None, help="Defaults to resolving --ref locally")

    p_advance = update_sub.add_parser("advance-ported", help="Advance last_ported after manual apply+verify.")
    p_advance.add_argument("--ref", required=True)
    p_advance.add_argument("--sha", default=None, help="Defaults to resolving --ref locally")

    p_fetch = sub.add_parser("fetch", help="EXPLICIT, network-touching: git fetch the canonical remote.")
    p_fetch.add_argument("--remote", default=constants.DEFAULT_REMOTE_NAME)

    p_verify = sub.add_parser(
        "verify", help="Build/check the CURRENT TRUSTED WORKTREE with existing gates (never the upstream tree)."
    )
    p_verify.add_argument("--jobs", type=int, default=2)
    p_verify.add_argument("--dry-run", action="store_true")
    p_verify.add_argument("--gate", action="append", default=[], dest="gates")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = _repo_root(args.repo)
    state_path = _state_path(repo_root, args.state)

    try:
        if args.command == "init-state":
            if os.path.exists(state_path) and not args.force:
                print(f"error: state file already exists: {state_path}", file=sys.stderr)
                return 1
            sha = git_utils.resolve_commit_sha(args.ref, repo_root)
            state = state_mod.default_state(
                constants.CANONICAL_UPSTREAM_URL, args.remote, args.ref, sha
            )
            state_mod.save_state(state_path, state)
            print(f"initialized {state_path} at {args.ref} @ {sha}")
            return 0

        if args.command == "scan":
            state = state_mod.load_state(state_path)
            try:
                result = scan_mod.scan(repo_root, args.ref, state)
            except scan_mod.ScanBoundaryError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 3
            if args.format == "json":
                _print(result.to_dict(), True, args.output)
            else:
                _print(scan_mod.render_text(result), False, args.output)
            return 0

        if args.command == "drift":
            state = state_mod.load_state(state_path)
            result = drift_mod.compute_drift(repo_root, args.ref, state)
            if args.format == "json":
                _print(result.to_dict(), True, args.output)
            else:
                text = json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"
                _print(text, False, args.output)
            return result.exit_code()

        if args.command == "report":
            state = state_mod.load_state(state_path)
            remote_name = args.remote or state["remote_name"]
            out_dir = args.out_dir or os.path.join(
                repo_root, constants.DEFAULT_OUTPUT_ROOT, _batch_name(args.shas)
            )
            try:
                report = report_mod.generate(
                    repo_root, remote_name, args.ref, args.shas, out_dir,
                    canonical_upstream_url=state["canonical_upstream_url"],
                )
            except (report_mod.SelectionError, report_mod.OutputSafetyError) as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            print(f"wrote report + {report['selected_count']} patch(es) to {out_dir}")
            return 0

        if args.command == "update-state":
            return _handle_update_state(args, repo_root, state_path)

        if args.command == "fetch":
            verify_remote_or_raise(repo_root, args.remote)
            output = git_utils.fetch_remote(args.remote, repo_root)
            print(f"fetched {args.remote} ({constants.CANONICAL_UPSTREAM_URL})")
            if output.strip():
                print(output)
            return 0

        if args.command == "verify":
            results = verify_mod.run_gates(
                repo_root, jobs=args.jobs, dry_run=args.dry_run, selected=args.gates
            )
            ok = True
            for r in results:
                status = "SKIPPED(dry-run)" if not r.ran else ("PASS" if r.passed else "FAIL")
                print(f"[{status}] {r.gate.name}: {' '.join(r.gate.command)}")
                if r.ran and not r.passed:
                    print(r.stdout)
                    print(r.stderr, file=sys.stderr)
                    ok = False
            return 0 if ok else 1

    except (state_mod.StateError, git_utils.GitError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error("unhandled command")
    return 2


def _batch_name(shas: Sequence[str]) -> str:
    if len(shas) == 1:
        return shas[0][:12]
    return "batch-" + shas[0][:8] + f"-plus{len(shas) - 1}"


def _handle_update_state(args, repo_root: str, state_path: str) -> int:
    state = state_mod.load_state(state_path)

    if args.update_command == "mark":
        sha = args.sha
        if not git_utils.is_full_sha(sha) or not git_utils.object_exists(sha, repo_root):
            print(f"error: {sha!r} is not a locally-resolvable full commit SHA", file=sys.stderr)
            return 1
        meta = git_utils.commit_meta(sha, repo_root)
        try:
            state_mod.upsert_commit_status(
                state,
                sha,
                new_status=args.status,
                author_name=meta.author_name,
                author_email=meta.author_email,
                subject=meta.subject,
                rationale=args.rationale,
                validation_evidence=args.evidence,
                updated_at=_now_iso(args.now),
                force=args.force,
            )
        except state_mod.StateError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        state_mod.save_state(state_path, state)
        print(f"marked {sha} as {args.status}")
        return 0

    if args.update_command == "record-scan":
        sha = args.sha or git_utils.resolve_commit_sha(args.ref, repo_root)
        try:
            state_mod.record_scan(state, args.ref, sha, repo_root)
        except state_mod.StateError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        state_mod.save_state(state_path, state)
        print(f"recorded last_scanned = {args.ref} @ {sha}")
        return 0

    if args.update_command == "advance-ported":
        sha = args.sha or git_utils.resolve_commit_sha(args.ref, repo_root)
        try:
            state_mod.advance_last_ported(state, args.ref, sha, repo_root)
        except state_mod.StateError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        state_mod.save_state(state_path, state)
        print(f"advanced last_ported = {args.ref} @ {sha}")
        return 0

    print("error: unknown update-state subcommand", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
