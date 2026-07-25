"""Deterministic synthetic-Git-repo builder for upstream_port tests.

Builds two local, filesystem-only repositories (no network involved
anywhere): an `upstream` repo standing in for the canonical decomp remote,
and a `fork` repo standing in for this project, with a `decomp` remote
pointing at the upstream repo's local path. All commits use fixed,
explicit author/committer identities and dates (never wall-clock `now()`)
so SHAs and ordering are fully reproducible from run to run given the same
sequence of calls.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

FIXED_AUTHOR_NAME = "Synthetic Upstream Author"
FIXED_AUTHOR_EMAIL = "synthetic-upstream@example.invalid"
FIXED_FORK_AUTHOR_NAME = "Synthetic Fork Maintainer"
FIXED_FORK_AUTHOR_EMAIL = "synthetic-fork@example.invalid"

# Fixed, deterministic ISO8601 dates (never datetime.now()) -- increasing so
# rev-list ordering is unambiguous without depending on the wall clock the
# test happened to run at.
_BASE_DATE = "2024-01-01T00:00:00+00:00"


def _iso(offset_seconds: int) -> str:
    # Simple deterministic offsetting without touching the real clock.
    import datetime

    base = datetime.datetime.fromisoformat(_BASE_DATE)
    return (base + datetime.timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def run_git(args: List[str], cwd: str, env: Optional[Dict[str, str]] = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout


def init_repo(path: str, branch: str = "master") -> None:
    os.makedirs(path, exist_ok=True)
    run_git(["init", "-q", "-b", branch], path)
    run_git(["config", "user.name", "placeholder"], path)
    run_git(["config", "user.email", "placeholder@example.invalid"], path)


def write_files(repo_dir: str, files: Dict[str, str]) -> None:
    for relpath, content in files.items():
        full = os.path.join(repo_dir, relpath)
        os.makedirs(os.path.dirname(full) or repo_dir, exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)


def commit(
    repo_dir: str,
    files: Dict[str, str],
    message: str,
    *,
    author_name: str = FIXED_AUTHOR_NAME,
    author_email: str = FIXED_AUTHOR_EMAIL,
    seconds_offset: int = 0,
    delete: Optional[List[str]] = None,
) -> str:
    write_files(repo_dir, files)
    for relpath in delete or []:
        full = os.path.join(repo_dir, relpath)
        if os.path.exists(full):
            os.remove(full)
    run_git(["add", "-A"], repo_dir)
    date = _iso(seconds_offset)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
            "GIT_COMMITTER_DATE": date,
        }
    )
    run_git(["commit", "-q", "-m", message], repo_dir, env=env)
    return rev_parse(repo_dir, "HEAD")


def rev_parse(repo_dir: str, ref: str = "HEAD") -> str:
    return run_git(["rev-parse", "--verify", ref], repo_dir).strip()


def create_branch(repo_dir: str, branch: str, start_point: str = "HEAD") -> None:
    run_git(["branch", branch, start_point], repo_dir)


def checkout(repo_dir: str, ref: str) -> None:
    run_git(["checkout", "-q", ref], repo_dir)


@dataclass
class SyntheticFixture:
    tmp_dir: str
    upstream_dir: str
    fork_dir: str
    base_sha: str
    remote_name: str = "decomp"


def build_fixture(tmp_dir: str, remote_name: str = "decomp") -> SyntheticFixture:
    """Create upstream + fork repos sharing a base commit, fork has a
    `remote_name` remote pointing at the upstream repo's local path, and a
    fetched remote-tracking ref `remote_name/master` matching the current
    upstream tip (simulating "the maintainer already fetched once")."""
    upstream_dir = os.path.join(tmp_dir, "upstream")
    fork_dir = os.path.join(tmp_dir, "fork")

    init_repo(upstream_dir, branch="master")
    base_sha = commit(
        upstream_dir,
        {"src/main.c": "int main(void) { return 0; }\n"},
        "base: initial upstream commit",
        seconds_offset=0,
    )

    init_repo(fork_dir, branch="master")
    run_git(["fetch", "-q", upstream_dir, "master"], fork_dir)
    run_git(["reset", "-q", "--hard", "FETCH_HEAD"], fork_dir)
    run_git(["remote", "add", remote_name, upstream_dir], fork_dir)
    run_git(["fetch", "-q", remote_name], fork_dir)

    return SyntheticFixture(
        tmp_dir=tmp_dir,
        upstream_dir=upstream_dir,
        fork_dir=fork_dir,
        base_sha=base_sha,
        remote_name=remote_name,
    )


def refetch(fixture: SyntheticFixture) -> None:
    """Re-run the (offline, filesystem-only) fetch so new upstream commits
    become locally resolvable in the fork repo -- simulating a maintainer
    having explicitly run the `fetch` subcommand already."""
    run_git(["fetch", "-q", fixture.remote_name], fixture.fork_dir)
