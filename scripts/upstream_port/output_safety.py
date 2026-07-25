"""Single shared "is it safe to write here?" primitive.

Every code path in this package that ever opens a file for writing (the
`report` subcommand's report/patch files, and `scan`/`drift`'s optional
`--output` file) must call `validate_output_target` first and use the
resolved path it returns. Centralizing this here means there is exactly one
place to get the safety contract right, instead of one lexical-gitignore
check per caller that can silently drift out of sync.

Safety contract (fail-closed; all three must hold, checked in this order so
the error message a caller sees always names the *first* problem found):

  1. No symlink anywhere on the path. `os.path.realpath()` only resolves
     symlinks for path components that already exist on disk and leaves any
     not-yet-existing tail untouched; comparing that against the plain
     `os.path.abspath()`/`os.path.normpath()` form of the same path is
     therefore a precise test for "does any *existing* component resolve
     somewhere other than its literal name" -- which catches both a
     symlinked ancestor directory and the target itself already being a
     symlink (regardless of whether the symlink's destination is inside or
     outside the repository).
  2. Containment: the fully-resolved path must be the repo root itself or a
     strict descendant of it -- never outside, never via `..` traversal.
  3. Confirmed ignored via `git check-ignore` -- a tracked/unignored path
     (e.g. `README.md`) is always rejected, even if it happens to be inside
     the repo and symlink-free.

Nothing is opened, created, or written before all three checks pass.
"""

from __future__ import annotations

import os

from . import git_utils


class OutputSafetyError(RuntimeError):
    """Raised when a requested output location fails the write-safety contract."""


def validate_output_target(cwd: str, target_path: str, *, is_dir: bool) -> str:
    """Validate `target_path` as a write destination rooted at `cwd`.

    `cwd` is assumed to already be the repository top-level (as returned by
    `git rev-parse --show-toplevel`) -- every caller in this package obtains
    it that way.

    `is_dir` selects how the ignore check is performed: for a directory
    target (e.g. a `report` `--out-dir`) a synthetic probe filename is
    appended before calling `git check-ignore`, so directory-level ignore
    rules (e.g. `/build/upstream-port/`) resolve correctly even before the
    directory exists on disk; for a file target (e.g. `scan`/`drift`
    `--output`) the path itself is checked directly.

    Returns the resolved absolute path to write to. Raises
    `OutputSafetyError` with a specific, actionable message if any part of
    the safety contract fails.
    """
    repo_root_real = os.path.realpath(cwd)
    # Relative paths are anchored to the already-resolved repo root (not the
    # raw `cwd` string) so that an incidental symlink somewhere in `cwd`'s
    # own ancestry (e.g. a `/tmp` alias on some platforms) can never produce
    # a false-positive "symlink detected" rejection for a target that is
    # not itself symlinked.
    target_abs = os.path.normpath(
        target_path if os.path.isabs(target_path) else os.path.join(repo_root_real, target_path)
    )
    target_real = os.path.realpath(target_abs)

    if target_real != target_abs:
        raise OutputSafetyError(
            f"refusing to write to {target_path!r}: it resolves through a "
            f"symlink ({target_abs!r} -> {target_real!r}). Symlinked output "
            "locations are never allowed, whether the symlink points inside "
            "or outside the repository -- use a plain, non-symlinked, "
            "gitignored path instead."
        )

    if target_real != repo_root_real and not target_real.startswith(repo_root_real + os.sep):
        raise OutputSafetyError(
            f"refusing to write to {target_path!r}: it resolves to "
            f"{target_real!r}, which is outside the repository root "
            f"{repo_root_real!r}."
        )

    rel = os.path.relpath(target_real, repo_root_real)
    probe = os.path.join(rel, ".upstream-port-ignore-probe") if is_dir else rel
    if not git_utils.check_ignore(probe, cwd):
        raise OutputSafetyError(
            f"refusing to write to {target_path!r}: it is not covered by "
            ".gitignore. Use the default output root (or another directory "
            "already covered by an ignore rule) before generating output."
        )

    return target_real
