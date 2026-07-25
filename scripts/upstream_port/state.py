"""Persistent state/manifest handling for the upstream porting tool.

The state file is the *only* artifact this package commits to the tree by
default (and only via the explicit `update-state` subcommand -- `scan` and
`report` never touch it). It is plain, sorted, stable JSON so a diff of it is
meaningful in code review.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List, Optional

from . import constants, git_utils


class StateError(RuntimeError):
    """Raised for malformed state files or illegal state transitions."""


def default_state(
    canonical_url: str,
    remote_name: str,
    ref: str,
    sha: str,
) -> Dict[str, Any]:
    """Build an initial state dict from a real, locally-resolved ref/SHA.

    Callers must pass a `sha` obtained via git_utils.resolve_commit_sha on a
    real local ref -- this function never fabricates or guesses a SHA.
    """
    if not git_utils.is_full_sha(sha):
        raise StateError(f"refusing to seed state with a non-full SHA: {sha!r}")
    return {
        "schema_version": constants.STATE_SCHEMA_VERSION,
        "canonical_upstream_url": canonical_url,
        "remote_name": remote_name,
        "last_scanned": {"ref": ref, "sha": sha},
        "last_ported": {"ref": ref, "sha": sha},
        "commits": {},
    }


def load_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise StateError(
            f"state file not found: {path!r}. Run `init-state` first "
            "(see docs/upstream-porting.md)."
        )
    with open(path, "r", encoding="utf-8") as fh:
        try:
            state = json.load(fh)
        except json.JSONDecodeError as exc:
            raise StateError(f"state file {path!r} is not valid JSON: {exc}") from exc
    _validate_schema(state, path)
    return state


def _validate_schema(state: Dict[str, Any], path: str) -> None:
    if not isinstance(state, dict):
        raise StateError(f"state file {path!r}: top level must be an object")
    if state.get("schema_version") != constants.STATE_SCHEMA_VERSION:
        raise StateError(
            f"state file {path!r}: unsupported schema_version "
            f"{state.get('schema_version')!r} (expected "
            f"{constants.STATE_SCHEMA_VERSION!r})"
        )
    for key in ("canonical_upstream_url", "remote_name", "last_scanned", "last_ported", "commits"):
        if key not in state:
            raise StateError(f"state file {path!r}: missing required key {key!r}")
    if state["canonical_upstream_url"] != constants.CANONICAL_UPSTREAM_URL:
        raise StateError(
            f"state file {path!r}: canonical_upstream_url does not match the "
            f"pinned canonical URL {constants.CANONICAL_UPSTREAM_URL!r}"
        )
    for boundary_key in ("last_scanned", "last_ported"):
        boundary = state[boundary_key]
        if not isinstance(boundary, dict) or "ref" not in boundary or "sha" not in boundary:
            raise StateError(f"state file {path!r}: {boundary_key!r} must have ref+sha")
        if not git_utils.is_full_sha(boundary["sha"]):
            raise StateError(
                f"state file {path!r}: {boundary_key}.sha is not a full 40-hex SHA"
            )
    if not isinstance(state["commits"], dict):
        raise StateError(f"state file {path!r}: commits must be an object")
    for sha, record in state["commits"].items():
        if not git_utils.is_full_sha(sha):
            raise StateError(f"state file {path!r}: commit key {sha!r} is not a full SHA")
        if record.get("status") not in constants.STATUSES:
            raise StateError(
                f"state file {path!r}: commit {sha} has illegal status "
                f"{record.get('status')!r}"
            )


def save_state(path: str, state: Dict[str, Any]) -> None:
    _validate_schema(state, path)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".upstream-port-state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def get_commit_record(state: Dict[str, Any], sha: str) -> Dict[str, Any]:
    return state["commits"].get(sha, {"status": "pending"})


def upsert_commit_status(
    state: Dict[str, Any],
    sha: str,
    *,
    new_status: str,
    author_name: str,
    author_email: str,
    subject: str,
    rationale: str,
    validation_evidence: str,
    updated_at: str,
    force: bool = False,
) -> Dict[str, Any]:
    """Validate and apply a single commit's status transition in-place.

    Raises StateError on an illegal transition, missing rationale/evidence,
    or a non-full SHA. Never touches Git refs, source, or history -- this
    only mutates the in-memory state dict (caller persists it via
    save_state).
    """
    if not git_utils.is_full_sha(sha):
        raise StateError(f"refusing to record status for non-full SHA: {sha!r}")
    if new_status not in constants.STATUSES:
        raise StateError(f"illegal status {new_status!r}; must be one of {constants.STATUSES}")

    current = state["commits"].get(sha)
    current_status = current["status"] if current else None
    allowed = constants.ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed and not force:
        raise StateError(
            f"illegal transition for {sha}: {current_status!r} -> {new_status!r} "
            f"(allowed: {sorted(allowed) or 'none'}; pass force=True to override)"
        )

    if new_status in constants.STATUSES_REQUIRING_EVIDENCE:
        if not rationale.strip():
            raise StateError(f"status {new_status!r} requires a non-empty rationale")
        if not validation_evidence.strip():
            raise StateError(
                f"status {new_status!r} requires non-empty validation_evidence"
            )

    record = dict(current) if current else {}
    record.update(
        {
            "status": new_status,
            "author_name": author_name,
            "author_email": author_email,
            "subject": subject,
            "rationale": rationale,
            "validation_evidence": validation_evidence,
            "updated_at": updated_at,
        }
    )
    state["commits"][sha] = record
    return state


def record_scan(state: Dict[str, Any], ref: str, sha: str, cwd: str) -> Dict[str, Any]:
    """Explicitly advance the last_scanned boundary after a human-reviewed scan."""
    if not git_utils.is_full_sha(sha):
        raise StateError(f"refusing to record last_scanned with non-full SHA: {sha!r}")
    old_sha = state["last_scanned"]["sha"]
    if old_sha != sha and not git_utils.is_ancestor(old_sha, sha, cwd):
        raise StateError(
            f"refusing to move last_scanned backward/sideways: current "
            f"{old_sha} is not an ancestor of {sha}"
        )
    state["last_scanned"] = {"ref": ref, "sha": sha}
    return state


def advance_last_ported(
    state: Dict[str, Any],
    ref: str,
    sha: str,
    cwd: str,
) -> Dict[str, Any]:
    """Explicitly advance the last_ported boundary after manual application+verify.

    Refuses to advance unless every commit strictly between the old and new
    boundary has already been given a terminal-ish disposition (ported,
    skipped, or superseded) -- this is the "validate legitimate transition"
    guard that stops a maintainer from silently skipping review of commits
    in the batch.
    """
    old_sha = state["last_ported"]["sha"]
    if not git_utils.is_full_sha(sha):
        raise StateError(f"refusing to record last_ported with non-full SHA: {sha!r}")
    if old_sha != sha and not git_utils.is_ancestor(old_sha, sha, cwd):
        raise StateError(
            f"refusing to move last_ported backward/sideways: current "
            f"{old_sha} is not an ancestor of {sha}"
        )
    unaccounted: List[str] = []
    for commit_sha in git_utils.rev_list_range(old_sha, sha, cwd):
        record = state["commits"].get(commit_sha)
        status = record["status"] if record else "pending"
        if status not in ("ported", "skipped", "superseded"):
            unaccounted.append(f"{commit_sha} (status={status})")
    if unaccounted:
        raise StateError(
            "refusing to advance last_ported: the following commits are not "
            "yet ported/skipped/superseded: " + ", ".join(unaccounted)
        )
    state["last_ported"] = {"ref": ref, "sha": sha}
    return state
