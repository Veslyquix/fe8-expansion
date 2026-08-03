#!/usr/bin/env python3
"""Immutable Git-object content source (issue #9 verifier remediation).

A release-candidate archive must never be built from mutable worktree
bytes: a tracked file can be edited on disk (or staged) without being
committed, and a naive "read the file from the checkout" archive builder
would silently pick up those bytes even though they are not part of any
commit. This module is the fix: it reads a repository's tree structure
and blob *content* exclusively through Git's plumbing porcelain
(``git ls-tree``, ``git cat-file --batch``), keyed by an exact commit SHA,
so the resulting bytes are bound to that immutable commit object and are
provably independent of the current worktree/index state.

Deliberately dependency-free (Python stdlib ``subprocess`` only).

Git blob modes this module understands (``git ls-tree``'s first column):

* ``100644`` -- an ordinary regular file (not executable).
* ``100755`` -- an executable regular file.
* ``120000`` -- a symlink (the blob content is the link target text).
  Never safe to archive as regular file content -- see
  ``source_guard.py``'s existing symlink hard-deny policy, which this
  module's callers apply identically to git-sourced entries.
* ``160000`` -- a gitlink (submodule mountpoint); the "object id" is the
  pinned commit SHA of the submodule, not a blob -- there is no blob
  content to read at all, by design (see docs/release_process.md's
  submodule/provenance boundary).

Any other mode (e.g. a raw ``040000`` tree entry, which ``-r`` recursion
should never surface) is treated as unsafe/unrecognized and rejected by
the caller rather than silently skipped.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

MODE_REGULAR = "100644"
MODE_EXECUTABLE = "100755"
MODE_SYMLINK = "120000"
MODE_GITLINK = "160000"

SAFE_BLOB_MODES = (MODE_REGULAR, MODE_EXECUTABLE)


class GitSourceError(ValueError):
    """A git plumbing invocation failed or returned unparseable output --
    an actionable tooling/environment defect, never silently ignored."""


@dataclass(frozen=True)
class GitEntry:
    """One ``git ls-tree -r`` entry: an exact, immutable binding between a
    repo-relative path and a specific Git object at a specific mode."""

    path: str
    mode: str
    obj_type: str  # "blob" or "commit" (gitlink)
    object_id: str

    @property
    def is_gitlink(self) -> bool:
        return self.mode == MODE_GITLINK or self.obj_type == "commit"

    @property
    def is_symlink(self) -> bool:
        return self.mode == MODE_SYMLINK

    @property
    def is_safe_blob(self) -> bool:
        return self.mode in SAFE_BLOB_MODES and self.obj_type == "blob"


def _run_git(args: List[str], repo_root: Path, **kwargs) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(repo_root), capture_output=True, **kwargs
        )
    except OSError as error:
        raise GitSourceError(f"failed to invoke git {args!r}: {error}") from error


def is_git_repo(repo_root: Path) -> bool:
    return (Path(repo_root) / ".git").exists()


def resolve_sha(repo_root: Path, revision: str = "HEAD") -> str:
    """Resolves `revision` (default the current HEAD) to its exact,
    immutable 40-lowercase-hex commit object id -- never a symbolic ref
    name, branch, or "unknown" sentinel."""
    result = _run_git(["rev-parse", "--verify", f"{revision}^{{commit}}"], repo_root, text=True)
    sha = result.stdout.strip()
    if result.returncode != 0 or len(sha) != 40:
        raise GitSourceError(
            f"git rev-parse could not resolve {revision!r} to an exact commit SHA: "
            f"{result.stderr.strip()}"
        )
    return sha.lower()


def is_worktree_clean(repo_root: Path) -> bool:
    """True only if there is no difference at all between HEAD, the index,
    and the worktree (informational/diagnostic use only -- the archive
    itself never depends on this being true, since content is always read
    from immutable git objects rather than the worktree; see module
    docstring)."""
    result = _run_git(["status", "--porcelain=v1"], repo_root, text=True)
    if result.returncode != 0:
        raise GitSourceError(f"git status failed: {result.stderr.strip()}")
    return result.stdout.strip() == ""


def write_index_tree(repo_root: Path) -> str:
    """Serializes the *current index* (staged state -- ``git add``ed but
    not necessarily committed) into a real, addressable Git tree object
    via ``git write-tree`` and returns its SHA. This is a development-time
    convenience only -- it lets allowlist/manifest generation tooling see
    "what a commit right now would contain" before actually committing --
    never used by the archive-building/rehearsal path itself, which only
    ever binds to an actual, already-created commit SHA (``HEAD`` or an
    explicit ``--target-sha`` override)."""
    result = _run_git(["write-tree"], repo_root, text=True)
    sha = result.stdout.strip()
    if result.returncode != 0 or len(sha) != 40:
        raise GitSourceError(f"git write-tree failed: {result.stderr.strip()}")
    return sha.lower()


def object_kind(repo_root: Path, object_id: str) -> Optional[str]:
    """Returns the exact Git object type (``"commit"``/``"tree"``/
    ``"blob"``/``"tag"``) that `object_id` names in this repository's own
    object database, or ``None`` if it does not name any valid object at
    all (e.g. it was pruned by a `git gc`, or was never a real object in
    the first place). Deliberately never raises for a missing object --
    "this recorded id no longer exists at all" and "it exists but is the
    wrong kind of object" are two distinguishable, both-actionable
    outcomes a caller must be able to tell apart (see
    `check_generation_basis_is_commit` below)."""
    result = _run_git(["cat-file", "-t", object_id], repo_root, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def is_ancestor_commit(repo_root: Path, ancestor_sha: str, descendant: str = "HEAD") -> bool:
    """True if `ancestor_sha` *is* `descendant` itself, or is a genuine
    ancestor of it (``git merge-base --is-ancestor``) -- i.e. `ancestor_sha`
    is actually reachable today from a real, current ref/commit, not
    merely still physically present as some otherwise-unreferenced loose
    object sitting in the object database (which any future `git gc` may
    prune at any time without warning)."""
    result = _run_git(["merge-base", "--is-ancestor", ancestor_sha, descendant], repo_root, text=True)
    return result.returncode == 0


# --- Immutable annotated release-tag authority (issue #9 SemVer trust- ---
# boundary fix) -------------------------------------------------------------
#
# The version ledger's own `previous_supported_version` field
# (docs/release_data/version_ledger.json) is candidate-controlled and
# purely *descriptive* -- it must never itself be treated as the
# authoritative source of "what was actually released before this
# candidate". This section is that actual authority: it derives the true
# immediate SemVer predecessor exclusively from this repository's own
# real, immutable, **annotated** `refs/tags/expansion/MAJOR.MINOR.PATCH`
# release-tag history (never from the ledger, never from any other
# candidate-writable source) -- see consistency.py's
# `check_release_tag_authority`, which cross-checks the ledger's
# descriptive claim against this authority and fails closed on any
# disagreement.
#
# A **lightweight** tag under this reserved namespace is never accepted
# at all (it can be silently moved/recreated by anyone with push access,
# unlike an annotated tag object, which is itself an immutable,
# addressable Git object with its own SHA) -- nor is a malformed tag name
# (anything other than an exact `MAJOR.MINOR.PATCH` version under the
# namespace), nor an ambiguous duplicate-version alias (two refs whose
# names both parse to the same version but name different commits). Any
# of these is a release-tag *authority-integrity* defect -- raised as
# `ReleaseTagAuthorityError`, never silently skipped/ignored in favor of
# whatever tags *do* happen to be well-formed (that would let a single
# malformed/lightweight tag quietly make an otherwise-real predecessor
# invisible, or vice versa).
#
# Only a tag whose peeled commit is reachable from the candidate's own
# `target_sha` (is `target_sha` itself, or a genuine ancestor of it) is
# ever considered a real predecessor candidate -- a tag that exists but
# sits on an unrelated/divergent history (e.g. a different release
# branch, or history that has since been rewritten) is never silently
# treated as this candidate's predecessor merely because its version
# number is numerically lower.

RELEASE_TAG_NAMESPACE = "expansion"
RELEASE_TAG_REF_PREFIX = f"refs/tags/{RELEASE_TAG_NAMESPACE}/"
_RELEASE_TAG_NAME_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class ReleaseTagAuthorityError(GitSourceError):
    """A tag actually present under the reserved
    `refs/tags/expansion/` release-tag namespace is lightweight,
    malformed, does not peel to a real commit, or is an ambiguous
    duplicate-version alias -- an authority-integrity defect in the
    release-tag history itself, distinct from an ordinary, honest
    "no predecessor tag exists" fact (which is not an error at all --
    see `derive_release_predecessor`, which returns `None` for that)."""


@dataclass(frozen=True)
class ReleaseTag:
    """One validated, real, annotated `expansion/MAJOR.MINOR.PATCH`
    release tag: `ref` is its full `refs/tags/...` name, `version` its
    parsed `MAJOR.MINOR.PATCH` string, `version_tuple` the same as
    `(int, int, int)` for ordering, and `commit_sha` the exact commit its
    annotated tag object peels to (never the tag object's own SHA)."""

    ref: str
    version: str
    version_tuple: Tuple[int, int, int]
    commit_sha: str


def _list_release_tag_refs(repo_root: Path) -> List[str]:
    """Every ref name under `RELEASE_TAG_REF_PREFIX`, of *any* shape at
    all (annotated, lightweight, or malformed) -- `load_release_tags`
    below is what actually validates each one's shape; this is
    deliberately just an unfiltered listing via `git for-each-ref`."""
    result = _run_git(
        ["for-each-ref", "--format=%(refname)", RELEASE_TAG_REF_PREFIX], repo_root, text=True
    )
    if result.returncode != 0:
        raise GitSourceError(f"git for-each-ref failed: {result.stderr.strip()}")
    return sorted(line for line in result.stdout.splitlines() if line)


def load_release_tags(repo_root: Path) -> List[ReleaseTag]:
    """Fail-closed load of every real, reserved-namespace release tag in
    `repo_root` -- see the module section docstring above for exactly
    what is rejected (and why) versus accepted. Returns an empty list
    (never an error) when there are simply no tags under the namespace
    at all -- a genuine, truthful "no release has ever been tagged from
    this repository" fact, not a defect."""
    tags: Dict[str, ReleaseTag] = {}
    for ref in _list_release_tag_refs(repo_root):
        name = ref[len(RELEASE_TAG_REF_PREFIX):]
        match = _RELEASE_TAG_NAME_RE.fullmatch(name)
        if not match:
            raise ReleaseTagAuthorityError(
                f"{ref!r} is under the reserved release-tag namespace {RELEASE_TAG_REF_PREFIX!r} "
                "but its own name is not an exact 'MAJOR.MINOR.PATCH' version -- malformed "
                "release-tag name"
            )
        kind = object_kind(repo_root, ref)
        if kind != "tag":
            raise ReleaseTagAuthorityError(
                f"{ref!r} is a lightweight tag (its own Git object kind is {kind!r}, not 'tag') -- "
                f"every reserved {RELEASE_TAG_REF_PREFIX!r} release tag must be an annotated tag "
                "object; a lightweight tag can be silently moved/recreated by anyone with push "
                "access and is never accepted as release-history authority"
            )
        try:
            commit_sha = resolve_sha(repo_root, f"{ref}^{{commit}}")
        except GitSourceError as error:
            raise ReleaseTagAuthorityError(
                f"{ref!r} is an annotated tag object but does not peel to a real, existing commit: "
                f"{error}"
            ) from error
        version = name
        version_tuple = tuple(int(part) for part in match.groups())
        existing = tags.get(version)
        if existing is not None and existing.commit_sha != commit_sha:
            raise ReleaseTagAuthorityError(
                f"duplicate-version release tag alias: version {version!r} names both commit "
                f"{existing.commit_sha!r} (via {existing.ref!r}) and {commit_sha!r} (via {ref!r}) "
                "-- ambiguous, conflicting release-tag history"
            )
        tags[version] = ReleaseTag(ref=ref, version=version, version_tuple=version_tuple, commit_sha=commit_sha)
    return list(tags.values())


def find_release_tag_for_version(repo_root: Path, version: str) -> Optional[ReleaseTag]:
    """The single, real, validated release tag for exactly `version`, or
    `None` if no such tag exists at all -- used to detect "this candidate
    version has already been released/tagged" (see
    consistency.check_release_tag_authority), a fact wholly distinct
    from predecessor derivation below."""
    for tag in load_release_tags(repo_root):
        if tag.version == version:
            return tag
    return None


def derive_release_predecessor(repo_root: Path, target_sha: str, current_version: str) -> Optional[str]:
    """Derives the true immediate SemVer predecessor of `current_version`
    purely from this repository's own immutable, annotated
    `expansion/MAJOR.MINOR.PATCH` release-tag history -- never from any
    candidate-controlled ledger claim. Only a tag whose peeled commit is
    reachable from `target_sha` (is `target_sha` itself, or a genuine
    ancestor of it) and whose version is strictly less than
    `current_version` is ever a candidate; the highest such version is
    the true predecessor. Returns `None` if there is no such tag at all
    -- a truthful first-release/no-earlier-reachable-tag fact, never
    itself an error.

    Raises `ReleaseTagAuthorityError` if any tag actually present under
    the reserved namespace is lightweight, malformed, or an ambiguous
    duplicate-version alias (see `load_release_tags`) -- an authority-
    integrity defect must never be silently skipped in favor of whatever
    *other* tags happen to be well-formed."""
    current_tuple = tuple(int(part) for part in str(current_version).split("."))
    candidates: List[Tuple[Tuple[int, int, int], str]] = []
    for tag in load_release_tags(repo_root):
        if tag.version_tuple >= current_tuple:
            # A tag equal to (or newer than) the current candidate
            # version is never a predecessor candidate -- see
            # consistency.check_release_tag_authority's own separate,
            # explicit "already-tagged current version" finding, which
            # reports this case on its own terms rather than this
            # function silently coercing/ignoring it here.
            continue
        if not is_ancestor_commit(repo_root, tag.commit_sha, target_sha):
            continue
        candidates.append((tag.version_tuple, tag.version))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


_GENERATION_BASIS_SHA_RE_SOURCE = r"^[0-9a-f]{40}$"


def check_generation_basis_is_commit(repo_root: Path, document_path: Path) -> List[str]:
    """Issue #9 final-review remediation (false/ephemeral generation-
    basis claim): the single, canonical, shared truthfulness check for a
    generated evidence document's own `"generation_basis_sha"` field --
    used identically by `allowlist.py`'s `docs/release_data/
    source_allowlist.json` and `tree_coverage.py`'s `docs/release_data/
    export_exclusions.json`, since both documents' own `_comment` text
    makes the exact same promise: this field documents *which commit*
    the file was last regenerated against.

    In a real git repository, that promise must always actually hold:
    `generation_basis_sha` must resolve to a genuine, still-reachable
    *commit* object -- never a tree (e.g. from a locally-generated,
    pre-commit `git write-tree` "index" snapshot -- see
    `write_index_tree` above -- accidentally written into the checked-in
    file instead of only ever being used for local, uncommitted
    development-time preview/verification, exactly the defect a fresh,
    independent final review reproduced here), never any other non-
    commit object kind, and never a dangling/unreachable object a future
    `git gc` could silently prune out from under this "documentary"
    claim entirely (an ephemeral basis is exactly as false a provenance
    claim as a wrong-kind one).

    Returns a flat, human-readable error list (empty means the field is
    present, well-formed, and names a real, reachable commit). Never
    raises: a malformed/missing field, or a `document_path` that is not
    valid JSON at all, is reported as an ordinary string finding here,
    not an exception -- callers already treat this exactly like every
    other `check()`-style finding list. When `repo_root` is not a git
    repository at all (e.g. a genuinely extracted, non-git release
    candidate tree), there is no object database to check against, so
    this deliberately returns no findings -- exactly like every other
    git-only check in this module family."""
    try:
        data = json.loads(Path(document_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{document_path}: not valid JSON: {error}"]
    if "generation_basis_sha" not in data:
        # Absence is not itself a truthfulness defect this check exists
        # to catch: a document that makes no 'generation_basis_sha' claim
        # at all has nothing this check can validate or contradict (this
        # field is not otherwise schema-mandatory -- unlike, e.g.,
        # `load_allowlist_modes`'s own `schema_version`/`"modes"`
        # enforcement). Every *real* checked-in document in this
        # repository has always included it, though, so this branch is
        # exercised only by minimal ad hoc test fixtures exercising
        # unrelated concerns.
        return []
    basis = data.get("generation_basis_sha")
    if not isinstance(basis, str) or not re.fullmatch(_GENERATION_BASIS_SHA_RE_SOURCE, basis):
        return [f"{document_path}: 'generation_basis_sha' must be a 40-lowercase-hex object id, found {basis!r}"]
    if not is_git_repo(repo_root):
        return []
    kind = object_kind(repo_root, basis)
    if kind is None:
        return [
            f"{document_path}: 'generation_basis_sha' {basis!r} does not name any object in this "
            "repository's object database at all -- regenerate against a real, current commit "
            "(e.g. '--target-sha HEAD --write')"
        ]
    if kind != "commit":
        return [
            f"{document_path}: 'generation_basis_sha' {basis!r} is a Git {kind!r} object, not a "
            "commit -- this document's own schema/comment promises a commit; a tree (e.g. from a "
            "development-time '--target-sha index' preview) must never be written into the "
            "checked-in file -- regenerate against a real, current commit (e.g. '--target-sha HEAD "
            "--write')"
        ]
    if not is_ancestor_commit(repo_root, basis, "HEAD"):
        return [
            f"{document_path}: 'generation_basis_sha' {basis!r} is a real commit, but is not HEAD "
            "nor any ancestor of it in this repository -- it is an unreachable/dangling reference "
            "outside this branch's own history (a future 'git gc' could prune it at any time); "
            "regenerate against the actual current commit (e.g. '--target-sha HEAD --write')"
        ]
    return []


def list_tree(repo_root: Path, target_sha: str) -> List[GitEntry]:
    """Exact, recursive, immutable listing of every path in `target_sha`'s
    tree via ``git ls-tree -r -z --full-tree`` -- never a worktree walk.
    Returned in the order git itself produces (already tree-sorted); every
    entry's `object_id` is a blob (regular file/executable/symlink) or
    commit (gitlink) hash frozen at that exact commit, never re-read from
    disk afterwards."""
    result = _run_git(
        ["ls-tree", "-r", "-z", "--full-tree", target_sha], repo_root
    )
    if result.returncode != 0:
        raise GitSourceError(
            f"git ls-tree failed for {target_sha!r}: {result.stderr.decode(errors='replace').strip()}"
        )
    entries: List[GitEntry] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            header, path_bytes = raw.split(b"\t", 1)
            mode_bytes, obj_type_bytes, object_id_bytes = header.split(b" ")
        except ValueError as error:
            raise GitSourceError(f"unparseable git ls-tree line: {raw!r}") from error
        path = path_bytes.decode("utf-8", "surrogateescape")
        entries.append(
            GitEntry(
                path=path,
                mode=mode_bytes.decode("ascii"),
                obj_type=obj_type_bytes.decode("ascii"),
                object_id=object_id_bytes.decode("ascii"),
            )
        )
    return entries


class GitBatchBlobReader:
    """A single, persistent ``git cat-file --batch`` subprocess used to
    read many blobs' exact bytes efficiently (one process for an entire
    archive build, instead of re-spawning git per file). Strictly
    request/response: writes exactly one object id, then reads exactly
    that response, before writing the next -- never queues unread output,
    so this cannot deadlock regardless of blob size or count.

    Use as a context manager::

        with GitBatchBlobReader(repo_root) as reader:
            data = reader.read(object_id)
    """

    def __init__(self, repo_root: Path):
        self._repo_root = Path(repo_root)
        self._proc: Optional[subprocess.Popen] = None

    def __enter__(self) -> "GitBatchBlobReader":
        self._proc = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=str(self._repo_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._proc is None:
            return
        proc = self._proc
        self._proc = None
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
            proc.wait(timeout=30)
        finally:
            if proc.stdout and not proc.stdout.closed:
                proc.stdout.close()
            if proc.stderr and not proc.stderr.closed:
                proc.stderr.close()

    def read(self, object_id: str) -> bytes:
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise GitSourceError("GitBatchBlobReader used outside its context manager")
        self._proc.stdin.write((object_id + "\n").encode("ascii"))
        self._proc.stdin.flush()
        header = self._proc.stdout.readline()
        if not header:
            stderr = self._proc.stderr.read().decode(errors="replace") if self._proc.stderr else ""
            raise GitSourceError(
                f"git cat-file --batch produced no output for {object_id!r}: {stderr.strip()}"
            )
        header_text = header.decode("ascii", "replace").strip()
        parts = header_text.split()
        if len(parts) != 3 or parts[1] != "blob":
            raise GitSourceError(
                f"git cat-file --batch: unexpected header for {object_id!r}: {header_text!r} "
                "(missing object, or not a blob)"
            )
        size = int(parts[2])
        data = self._proc.stdout.read(size)
        trailing = self._proc.stdout.read(1)
        if trailing != b"\n":
            raise GitSourceError(
                f"git cat-file --batch: malformed trailing byte after {object_id!r}"
            )
        return data


def read_blobs(repo_root: Path, object_ids: Iterable[str]) -> Dict[str, bytes]:
    """Convenience one-shot helper (opens and closes its own batch reader)
    for callers that already have every needed object id in hand (e.g.
    tests); prefer `GitBatchBlobReader` directly for a full archive build
    to reuse one subprocess."""
    result: Dict[str, bytes] = {}
    with GitBatchBlobReader(repo_root) as reader:
        for object_id in object_ids:
            if object_id in result:
                continue
            result[object_id] = reader.read(object_id)
    return result
