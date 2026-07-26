"""Thin, explicit subprocess wrappers around the local `git` binary.

Every function here operates on local repository state only. The single
network-touching operation (`fetch`) is isolated in its own function and is
never called by scan/report/drift/verify code paths -- only by the explicit
`fetch` CLI subcommand, and only after `verify_remote_url` confirms the
configured remote points at the pinned canonical URL.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List, Optional, Sequence

_SHA_HEX_LEN = 40


class GitError(RuntimeError):
    """Raised when a git subprocess invocation fails or returns unusable output."""


@dataclass(frozen=True)
class CommitMeta:
    sha: str
    author_name: str
    author_email: str
    subject: str
    author_date_iso: str


def _run(args: Sequence[str], cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and proc.returncode != 0:
        raise GitError(
            "git {} failed (exit {}): {}".format(
                " ".join(args), proc.returncode, proc.stderr.strip()
            )
        )
    return proc


def is_full_sha(value: str) -> bool:
    if len(value) != _SHA_HEX_LEN:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def resolve_commit_sha(ref: str, cwd: str) -> str:
    """Resolve `ref` to a full 40-hex commit SHA using only local refs/objects.

    Never triggers a fetch. Raises GitError if the ref does not resolve to a
    commit object that already exists locally.
    """
    proc = _run(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd, check=False)
    sha = proc.stdout.strip()
    if proc.returncode != 0 or not is_full_sha(sha):
        raise GitError(f"ref {ref!r} does not resolve to a local commit object")
    return sha


def object_exists(sha: str, cwd: str) -> bool:
    proc = _run(["cat-file", "-e", f"{sha}^{{commit}}"], cwd, check=False)
    return proc.returncode == 0


def is_ancestor(ancestor_sha: str, descendant_sha: str, cwd: str) -> bool:
    proc = _run(["merge-base", "--is-ancestor", ancestor_sha, descendant_sha], cwd, check=False)
    if proc.returncode not in (0, 1):
        raise GitError(
            f"git merge-base --is-ancestor {ancestor_sha} {descendant_sha} "
            f"errored: {proc.stderr.strip()}"
        )
    return proc.returncode == 0


def merge_base(a: str, b: str, cwd: str) -> Optional[str]:
    proc = _run(["merge-base", a, b], cwd, check=False)
    if proc.returncode != 0:
        return None
    sha = proc.stdout.strip()
    return sha if is_full_sha(sha) else None


def rev_list_range(baseline_sha: str, tip_sha: str, cwd: str) -> List[str]:
    """Commits in (baseline_sha, tip_sha], oldest first, deterministic.

    Uses --reverse so ordering only depends on the fixed commit graph, never
    on wall-clock time the command happens to run at.
    """
    proc = _run(
        ["rev-list", "--reverse", "--topo-order", f"{baseline_sha}..{tip_sha}"],
        cwd,
    )
    return [line for line in proc.stdout.splitlines() if line]


_META_SEP = "\x1f"  # unit separator, extremely unlikely to appear in subjects


def commit_meta(sha: str, cwd: str) -> CommitMeta:
    fmt = _META_SEP.join(["%H", "%an", "%ae", "%s", "%aI"])
    proc = _run(["show", "-s", f"--format={fmt}", sha], cwd)
    parts = proc.stdout.strip("\n").split(_META_SEP)
    if len(parts) != 5:
        raise GitError(f"unexpected `git show` metadata output for {sha}")
    full_sha, author_name, author_email, subject, author_date_iso = parts
    return CommitMeta(
        sha=full_sha,
        author_name=author_name,
        author_email=author_email,
        subject=subject,
        author_date_iso=author_date_iso,
    )


def commit_parents(sha: str, cwd: str) -> List[str]:
    """Full 40-hex parent SHAs of `sha`, in `git`'s own parent order.

    Empty list for a root commit (no parents). A single-element list is the
    overwhelmingly common case (an ordinary, non-merge commit). Two or more
    elements means `sha` is a merge commit -- callers must not treat it like
    an ordinary commit for diff/patch purposes (see `changed_paths` and
    `format_patch_text` below).
    """
    proc = _run(["show", "-s", "--format=%P", sha], cwd)
    line = proc.stdout.strip("\n")
    return line.split() if line else []


def is_merge_commit(sha: str, cwd: str) -> bool:
    return len(commit_parents(sha, cwd)) > 1


def changed_paths(sha: str, cwd: str) -> List[str]:
    """Deterministic, sorted, de-duplicated list of paths changed by `sha`.

    Plain `git diff-tree --name-only` has two sharp edges this function
    exists to close:

    - Root commit (no parents): without `--root`, `diff-tree` silently
      returns nothing at all for a root commit (there is no parent to diff
      against by default). Diffed against the empty tree via `--root`
      instead, so a root commit's real files are never silently dropped.
    - Merge commit (2+ parents): without `-m`/`-c`, `diff-tree` also
      silently returns nothing for a merge commit (its default "combined
      diff" is empty whenever the merge introduced no conflict hunks
      against either parent, which is the common case). That silent-empty
      result is exactly the kind of ambiguous, easy-to-miss gap this tool
      must never produce. Instead, this computes the diff against *each*
      parent individually and returns the UNION of every changed path,
      de-duplicated and sorted -- i.e. every path the merge commit's tree
      actually differs on from at least one parent -- so scan/classify
      output for a merge commit is honest and deterministic.

    An ordinary (single-parent) commit is diffed against that one parent,
    exactly as before.
    """
    parents = commit_parents(sha, cwd)
    if not parents:
        proc = _run(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha],
            cwd,
        )
        return sorted({line for line in proc.stdout.splitlines() if line})
    if len(parents) == 1:
        proc = _run(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", sha],
            cwd,
        )
        return sorted({line for line in proc.stdout.splitlines() if line})
    paths = set()
    for parent in parents:
        proc = _run(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", parent, sha],
            cwd,
        )
        paths.update(line for line in proc.stdout.splitlines() if line)
    return sorted(paths)


def format_patch_text(sha: str, cwd: str) -> str:
    """Render a single, non-merge commit as a patch, reading local git
    objects only.

    This never applies, cherry-picks, or merges anything -- it is a pure
    read (`git format-patch --stdout`) that preserves the original author
    identity, date, and subject in standard mbox patch headers.

    Refuses (raises `GitError`) for a merge commit: `git format-patch -1
    --stdout <merge-sha>` does not honestly patch the merge commit at all
    -- by default it silently walks past merges and emits a patch for a
    different, non-merge ancestor commit instead (or nothing), which would
    be a dangerously misleading result to write to a review output file.
    Callers must reject merge commits before calling this (see
    `report.validate_selection`); this is a defense-in-depth guard for any
    other caller.
    """
    if is_merge_commit(sha, cwd):
        raise GitError(
            f"refusing to format-patch merge commit {sha}: `git format-patch` "
            "does not produce a single deterministic, honest diff for a "
            "merge commit (it silently skips or retargets it). Select its "
            "individual non-merge commits instead, or review it manually."
        )
    proc = _run(
        ["format-patch", "-1", "--stdout", "--no-signature", sha],
        cwd,
    )
    return proc.stdout


def remote_url(remote_name: str, cwd: str) -> Optional[str]:
    proc = _run(["remote", "get-url", remote_name], cwd, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def remote_refs(remote_name: str, cwd: str) -> List[str]:
    """List local remote-tracking refs for `remote_name` (no network)."""
    proc = _run(["for-each-ref", f"refs/remotes/{remote_name}/", "--format=%(refname)"], cwd)
    return [line for line in proc.stdout.splitlines() if line]


def fetch_remote(remote_name: str, cwd: str) -> str:
    """Perform an explicit `git fetch` of `remote_name`.

    Caller MUST have already validated the remote URL against the pinned
    canonical URL (see cli.verify_remote_or_raise). This only updates
    remote-tracking refs/objects; it never touches local branches, the
    working tree, or history.
    """
    proc = _run(["fetch", "--quiet", remote_name], cwd)
    return proc.stdout


def check_ignore(path: str, cwd: str) -> bool:
    proc = _run(["check-ignore", "-q", path], cwd, check=False)
    return proc.returncode == 0


def status_short(cwd: str) -> str:
    proc = _run(["status", "--short"], cwd)
    return proc.stdout


def head_sha(cwd: str) -> str:
    return resolve_commit_sha("HEAD", cwd)
