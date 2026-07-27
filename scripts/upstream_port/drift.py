"""Read-only stale-state / drift detection.

Detects: the selected ref moving since the last recorded scan, recorded
state SHAs becoming unreachable/unresolvable in this clone, and any
outstanding unreviewed commits. Never fetches, never mutates state, never
executes upstream code.

Exit-code semantics (see cli.py): 0 = clean, 2 = drift found, 3 = state
integrity problem (unreachable/diverged SHA -- needs maintainer attention
before scan/report can be trusted).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import git_utils


@dataclass
class DriftReport:
    ref: str
    ref_sha: Optional[str]
    last_scanned_sha: str
    last_ported_sha: str
    last_scanned_reachable: bool
    last_ported_reachable: bool
    ref_moved_since_scan: bool
    histories_diverged: bool
    unreviewed_count: Optional[int]
    issues: List[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return bool(
            self.issues
            or self.ref_moved_since_scan
            or (self.unreviewed_count or 0) > 0
        )

    @property
    def integrity_problem(self) -> bool:
        return (
            not (self.last_scanned_reachable and self.last_ported_reachable)
            or self.ref_sha is None
            or self.histories_diverged
        )

    def exit_code(self) -> int:
        if self.integrity_problem:
            return 3
        if self.has_drift:
            return 2
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref": self.ref,
            "ref_sha": self.ref_sha,
            "last_scanned_sha": self.last_scanned_sha,
            "last_ported_sha": self.last_ported_sha,
            "last_scanned_reachable": self.last_scanned_reachable,
            "last_ported_reachable": self.last_ported_reachable,
            "ref_moved_since_scan": self.ref_moved_since_scan,
            "histories_diverged": self.histories_diverged,
            "unreviewed_count": self.unreviewed_count,
            "issues": self.issues,
            "has_drift": self.has_drift,
            "integrity_problem": self.integrity_problem,
            "exit_code": self.exit_code(),
        }


def compute_drift(cwd: str, ref: str, state: Dict[str, Any]) -> DriftReport:
    last_scanned_sha = state["last_scanned"]["sha"]
    last_ported_sha = state["last_ported"]["sha"]
    issues: List[str] = []

    last_scanned_reachable = git_utils.object_exists(last_scanned_sha, cwd)
    if not last_scanned_reachable:
        issues.append(f"last_scanned.sha {last_scanned_sha} is not a reachable local object")
    last_ported_reachable = git_utils.object_exists(last_ported_sha, cwd)
    if not last_ported_reachable:
        issues.append(f"last_ported.sha {last_ported_sha} is not a reachable local object")

    ref_sha: Optional[str]
    try:
        ref_sha = git_utils.resolve_commit_sha(ref, cwd)
    except Exception:  # noqa: BLE001 - any resolution failure is an integrity issue
        ref_sha = None
        issues.append(f"selected ref {ref!r} does not resolve to a local commit")

    ref_moved_since_scan = False
    histories_diverged = False
    unreviewed_count: Optional[int] = None

    if ref_sha is not None and last_scanned_reachable:
        if ref_sha != last_scanned_sha:
            ref_moved_since_scan = True

    if ref_sha is not None and last_ported_reachable:
        if last_ported_sha == ref_sha:
            unreviewed_count = 0
        elif git_utils.is_ancestor(last_ported_sha, ref_sha, cwd):
            unreviewed_count = len(git_utils.rev_list_range(last_ported_sha, ref_sha, cwd))
        else:
            histories_diverged = True
            issues.append(
                f"last_ported ({last_ported_sha}) is not an ancestor of ref "
                f"{ref!r} ({ref_sha}); histories have diverged"
            )

    return DriftReport(
        ref=ref,
        ref_sha=ref_sha,
        last_scanned_sha=last_scanned_sha,
        last_ported_sha=last_ported_sha,
        last_scanned_reachable=last_scanned_reachable,
        last_ported_reachable=last_ported_reachable,
        ref_moved_since_scan=ref_moved_since_scan,
        histories_diverged=histories_diverged,
        unreviewed_count=unreviewed_count,
        issues=issues,
    )
