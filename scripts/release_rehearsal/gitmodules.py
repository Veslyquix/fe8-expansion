#!/usr/bin/env python3
"""Minimal, dependency-free ``.gitmodules`` blob parser (issue #9
mandatory correction #4).

Git's ``.gitmodules`` file uses a small subset of the ``git-config`` INI
dialect: ``[submodule "name"]`` section headers, followed by indented
``key = value`` lines. This module parses that dialect directly from an
immutable Git blob's *content string* (never a worktree path, and never
by shelling out to ``git config -f <path>``, which requires a real file
on disk) -- callers read the blob's bytes via
``scripts/release_rehearsal/git_source.py`` first (see
``load_gitmodules_sections`` below).

Deliberately narrow and fail-closed: a duplicate section name, a
duplicate key within one section, or any non-blank/non-comment line
found outside of (before) any section header is an actionable
``GitmodulesError`` -- this never silently ignores a malformed
``.gitmodules`` file the way a more permissive parser might.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

from scripts.release_rehearsal import git_source as gs

_SECTION_RE = re.compile(r'^\[submodule\s+"(?P<name>[^"]*)"\]\s*$')
_KV_RE = re.compile(r'^[ \t]+(?P<key>[A-Za-z][A-Za-z0-9_-]*)[ \t]*=[ \t]*(?P<value>.*?)[ \t]*$')
_COMMENT_PREFIXES = ("#", ";")


class GitmodulesError(ValueError):
    """A malformed ``.gitmodules`` file, or a git plumbing failure while
    reading it -- an actionable tooling defect, distinct from a normal
    "binding mismatch" finding (reported as a string in a list
    elsewhere, never raised)."""


def parse_gitmodules(content: str) -> Dict[str, Dict[str, str]]:
    """Parses `content` into ``{section_name: {key: value}}``. Every
    line must be blank, a comment (``#``/``;`` prefix, ignoring leading
    whitespace), a ``[submodule "name"]`` section header, or an indented
    ``key = value`` line belonging to the most recently opened section --
    anything else (including any non-blank content before the first
    section header) is an actionable `GitmodulesError`. A duplicate
    section name, or a duplicate key within one section, is likewise
    rejected rather than silently overwritten (the last-one-wins
    behavior a more permissive INI parser might apply would hide a real
    authoring mistake)."""
    sections: Dict[str, Dict[str, str]] = {}
    current: str | None = None
    for lineno, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.rstrip("\r")
        stripped = line.strip()
        if not stripped or stripped.startswith(_COMMENT_PREFIXES):
            continue
        section_match = _SECTION_RE.match(line)
        if section_match:
            name = section_match.group("name")
            if name in sections:
                raise GitmodulesError(f".gitmodules: duplicate section [submodule \"{name}\"] (line {lineno})")
            sections[name] = {}
            current = name
            continue
        if current is None:
            raise GitmodulesError(
                f".gitmodules: line {lineno} ({line!r}) appears before any "
                "'[submodule \"name\"]' section header"
            )
        kv_match = _KV_RE.match(line)
        if not kv_match:
            raise GitmodulesError(f".gitmodules: unparseable line {lineno} in section {current!r}: {line!r}")
        key = kv_match.group("key").lower()
        value = kv_match.group("value")
        if key in sections[current]:
            raise GitmodulesError(f".gitmodules: duplicate key {key!r} in section {current!r} (line {lineno})")
        sections[current][key] = value
    return sections


def load_gitmodules_sections(repo_root: Path, target_sha: str = "HEAD") -> Dict[str, Dict[str, str]]:
    """Reads ``.gitmodules``'s exact content at the immutable `target_sha`
    (via ``git_source.list_tree``/``read_blobs`` -- never the worktree
    path) and parses it. Raises `GitmodulesError` if ``.gitmodules`` is
    not a tracked safe blob at `target_sha` at all, or if its content is
    malformed.

    Deliberately, explicitly refuses to invoke any git plumbing at all
    when `repo_root` has no `.git` of its own (a genuine extracted
    archive/non-git candidate tree) -- see `git_source.is_git_repo`.
    Invoking `git` with such a directory as `cwd` anyway would let
    git's own upward-directory-discovery silently find an unrelated
    *enclosing* repository (if `repo_root` happens to sit inside one)
    and read `target_sha`'s tree from *that* repository's object
    database instead -- exactly the "pretend the override proves Git
    content identity" failure this module must never reproduce (see
    `scripts/release_rehearsal/tests/test_gitmodules.py`'s
    `NeverInvokesGitForNonGitRepoRootTests`)."""
    if not gs.is_git_repo(repo_root):
        raise GitmodulesError(
            f"{repo_root} has no .git metadata (a genuine extracted archive/non-git candidate "
            "tree); .gitmodules cannot be read via git plumbing from it -- this never invokes git "
            "against such a tree at all"
        )
    try:
        tree = {entry.path: entry for entry in gs.list_tree(repo_root, target_sha)}
    except gs.GitSourceError as error:
        raise GitmodulesError(f"could not read the tree at {target_sha!r}: {error}") from error
    entry = tree.get(".gitmodules")
    if entry is None or not entry.is_safe_blob:
        raise GitmodulesError(f".gitmodules is not a tracked regular file at {target_sha!r}")
    try:
        data = gs.read_blobs(repo_root, [entry.object_id])[entry.object_id]
    except gs.GitSourceError as error:
        raise GitmodulesError(f"could not read .gitmodules blob content at {target_sha!r}: {error}") from error
    return parse_gitmodules(data.decode("utf-8", "surrogateescape"))
