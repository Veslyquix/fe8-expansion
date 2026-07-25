"""Persistent state/manifest handling for the upstream porting tool.

The state file is the *only* artifact this package commits to the tree by
default (and only via the explicit `update-state` subcommand -- `scan` and
`report` never touch it). It is plain, sorted, stable JSON so a diff of it is
meaningful in code review.
"""

from __future__ import annotations

import json
import os
import re
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


# Exact, allowed field set for a `commits[sha]` record. This is intentionally
# a closed set (no additional/optional fields) -- provenance/evidence gaps
# must fail loudly at load time, not be silently tolerated by a permissive
# schema. Note `sha` is deliberately NOT one of these fields: the commit's
# full SHA is the dict *key* (validated separately below); a redundant `sha`
# field inside the record would be an unexpected extra field and is rejected
# by the "extra field" check the same as any other unknown key.
_COMMIT_RECORD_FIELDS = (
    "status",
    "author_name",
    "author_email",
    "subject",
    "rationale",
    "validation_evidence",
    "updated_at",
)

# Fields (beyond `status`, which is checked against constants.STATUSES) that
# must be non-empty strings for *every* status, including `pending` -- a
# commit record is only ever created from real `git` metadata (see
# upsert_commit_status/cli.py), so a blank one of these always indicates a
# hand-edited or otherwise forged/corrupted record, never a legitimate one.
_COMMIT_RECORD_ALWAYS_NON_EMPTY_FIELDS = ("author_name", "author_email", "subject", "updated_at")

# `updated_at` must match the exact UTC timestamp format this package itself
# always generates (see cli._now_iso): YYYY-MM-DDTHH:MM:SSZ.
_UPDATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _validate_commit_record(sha: str, record: Any, path: str) -> None:
    """Strictly validate one `commits[sha]` record: exact field set, exact
    types, a legal status, and non-empty commit-provenance/evidence fields.

    Raises StateError -- and never returns a "fixed up" record -- for any of:
    a non-object record; a missing or unexpected/extra field; a
    wrong-typed field; an illegal `status`; an empty `author_name`/
    `author_email`/`subject`/`updated_at`; a malformed `updated_at`; or a
    non-pending status with empty `rationale`/`validation_evidence`.
    """
    if not isinstance(record, dict):
        raise StateError(f"state file {path!r}: commit {sha} record must be an object")

    actual_fields = set(record.keys())
    expected_fields = set(_COMMIT_RECORD_FIELDS)
    missing = expected_fields - actual_fields
    if missing:
        raise StateError(
            f"state file {path!r}: commit {sha} record missing required "
            f"field(s): {', '.join(sorted(missing))}"
        )
    extra = actual_fields - expected_fields
    if extra:
        raise StateError(
            f"state file {path!r}: commit {sha} record has unexpected extra "
            f"field(s) (exact schema only): {', '.join(sorted(extra))}"
        )

    for field in _COMMIT_RECORD_FIELDS:
        value = record[field]
        if not isinstance(value, str):
            raise StateError(
                f"state file {path!r}: commit {sha} field {field!r} must be "
                f"a string, got {type(value).__name__}"
            )

    status = record["status"]
    if status not in constants.STATUSES:
        raise StateError(
            f"state file {path!r}: commit {sha} has illegal status {status!r} "
            f"(must be one of {constants.STATUSES})"
        )

    for field in _COMMIT_RECORD_ALWAYS_NON_EMPTY_FIELDS:
        if not record[field].strip():
            raise StateError(
                f"state file {path!r}: commit {sha} field {field!r} must be "
                "a non-empty string"
            )

    author_email = record["author_email"]
    if "@" not in author_email or author_email != author_email.strip():
        raise StateError(
            f"state file {path!r}: commit {sha} author_email {author_email!r} "
            "is not a plausible email address"
        )

    updated_at = record["updated_at"]
    if not _UPDATED_AT_RE.match(updated_at):
        raise StateError(
            f"state file {path!r}: commit {sha} updated_at {updated_at!r} "
            "does not match the required UTC timestamp format "
            "YYYY-MM-DDTHH:MM:SSZ"
        )

    if status in constants.STATUSES_REQUIRING_EVIDENCE:
        if not record["rationale"].strip():
            raise StateError(
                f"state file {path!r}: commit {sha} status {status!r} "
                "requires a non-empty rationale"
            )
        if not record["validation_evidence"].strip():
            raise StateError(
                f"state file {path!r}: commit {sha} status {status!r} "
                "requires non-empty validation_evidence"
            )
    # `pending` records still require every field above to be *present and
    # correctly typed* (already enforced) -- rationale/validation_evidence
    # are simply allowed to be empty strings for `pending`.


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
        _validate_commit_record(sha, record, path)


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


def _require_local_object(sha: str, cwd: str, label: str) -> None:
    """Fail with an actionable StateError (never a raw GitError) when `sha`
    is not a commit object this local clone actually has -- e.g. a SHA that
    only exists upstream but was never fetched, or a typo'd/forged value.
    Callers must call this BEFORE any `git merge-base`/ancestry plumbing so
    a missing object produces a clear message instead of a `git` fatal
    error surfacing from deeper inside the ancestry check."""
    if not git_utils.object_exists(sha, cwd):
        raise StateError(
            f"refusing to use {label} {sha}: not a locally-resolvable commit "
            "object in this clone (fetch it first if it is genuinely "
            "upstream, or double check the value)"
        )


def record_scan(state: Dict[str, Any], ref: str, explicit_sha: Optional[str], cwd: str) -> Dict[str, Any]:
    """Explicitly advance the last_scanned boundary after a human-reviewed scan.

    `explicit_sha` binds tightly to `ref`'s own resolved local tip:
    - If `explicit_sha` is given (a caller-supplied `--sha`), it must be a
      full 40-hex SHA and must be EXACTLY EQUAL to
      `git_utils.resolve_commit_sha(ref, cwd)` -- the current local tip of
      `ref`. Any other value (an expansion-side SHA, an unrelated/diverged
      commit, or a real-but-stale/older SHA on the same branch that is no
      longer `ref`'s tip) is rejected before the state dict is touched.
    - If `explicit_sha` is None (the CLI's implicit/no-`--sha` path), the
      resolved tip of `ref` is used directly -- there is no separate,
      looser "implicit" code path to bypass the same binding.

    All of the above happens before `state["last_scanned"]` is mutated, so a
    rejected call leaves `state` (and, in turn, the on-disk file the caller
    saves it to) byte-for-byte unchanged.
    """
    resolved_sha = git_utils.resolve_commit_sha(ref, cwd)
    if explicit_sha is not None:
        if not git_utils.is_full_sha(explicit_sha):
            raise StateError(f"refusing to record last_scanned with non-full SHA: {explicit_sha!r}")
        if explicit_sha != resolved_sha:
            raise StateError(
                f"refusing to record last_scanned: --sha {explicit_sha} does not "
                f"exactly match the resolved local tip {resolved_sha} of ref "
                f"{ref!r}; record-scan only ever records a ref's own current "
                "tip, never an arbitrary/unrelated/stale SHA"
            )
        sha = explicit_sha
    else:
        sha = resolved_sha

    old_sha = state["last_scanned"]["sha"]
    _require_local_object(old_sha, cwd, "current last_scanned.sha")
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
    explicit_sha: Optional[str],
    cwd: str,
) -> Dict[str, Any]:
    """Explicitly advance the last_ported boundary after manual application+verify.

    The candidate boundary (whether given explicitly via `--sha` or implied
    by omitting it) must sit inside the ancestry corridor bounded by the
    CURRENT `last_ported.sha` on one end and the selected `ref`'s own
    resolved local tip on the other -- both ends of the corridor are
    validated, not just the old-boundary side:

    - descendant-of-or-equal-to the current `last_ported.sha` (existing
      forward-only/no-op policy, unchanged); AND
    - ancestor-of-or-equal-to `git_utils.resolve_commit_sha(ref, cwd)` (the
      NEW check this closes) -- an expansion-side commit, an unrelated
      commit, a commit that only exists past/after `ref`'s tip, or a commit
      on a diverged/forked branch is rejected here even though it might
      otherwise look like "a descendant of the old boundary".

    A candidate strictly between the two ends (an "intermediate" upstream
    commit, not necessarily `ref`'s exact tip) is accepted as long as every
    commit up to it is already ported/skipped/superseded -- advancing to a
    partial batch boundary is a legitimate, intentional workflow, unlike
    accepting an out-of-corridor commit.

    Refuses to advance unless every commit strictly between the old and new
    boundary has already been given a terminal-ish disposition (ported,
    skipped, or superseded) -- this is the "validate legitimate transition"
    guard that stops a maintainer from silently skipping review of commits
    in the batch.

    All checks (including the unaccounted-commits scan) happen before
    `state["last_ported"]` is mutated, so a rejected call leaves `state`
    byte-for-byte unchanged.
    """
    resolved_ref_sha = git_utils.resolve_commit_sha(ref, cwd)
    if explicit_sha is not None:
        if not git_utils.is_full_sha(explicit_sha):
            raise StateError(f"refusing to record last_ported with non-full SHA: {explicit_sha!r}")
        sha = explicit_sha
    else:
        sha = resolved_ref_sha
    _require_local_object(sha, cwd, "candidate last_ported sha")

    old_sha = state["last_ported"]["sha"]
    _require_local_object(old_sha, cwd, "current last_ported.sha")
    if old_sha != sha and not git_utils.is_ancestor(old_sha, sha, cwd):
        raise StateError(
            f"refusing to move last_ported backward/sideways: current "
            f"{old_sha} is not an ancestor of {sha}"
        )
    if sha != resolved_ref_sha and not git_utils.is_ancestor(sha, resolved_ref_sha, cwd):
        raise StateError(
            f"refusing to advance last_ported to {sha}: it is not an "
            f"ancestor of (or equal to) ref {ref!r}'s resolved tip "
            f"{resolved_ref_sha}; the candidate must lie within the "
            f"current last_ported ({old_sha}) .. ref-tip ({resolved_ref_sha}) "
            "ancestry corridor -- an expansion-side, unrelated, "
            "past-the-tip, or diverged/forked commit is rejected"
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
