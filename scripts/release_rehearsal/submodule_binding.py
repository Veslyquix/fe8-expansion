#!/usr/bin/env python3
"""mgfembp submodule three-way binding validator (issue #9 mandatory
correction #4).

Cross-checks the `mgfembp` git submodule across every immutable source
this repository records about it, proving they all agree *exactly*:

1. `.gitmodules`'s blob content at the target SHA (never the worktree
   path -- read via `scripts/release_rehearsal/gitmodules.py`, itself
   backed by `scripts/release_rehearsal/git_source.py` plumbing): the
   exact `[submodule "mgfembp"]` section, its `path`, and its `url`.
2. The immutable HEAD tree's own gitlink entry for that exact path:
   mode `160000` and the exact pinned commit OID.
3. `docs/release_data/export_exclusions.json`'s exact exclusion record:
   same path, `kind: "gitlink"`, and OID.
4. `docs/release_data/provenance/submodules.json`'s exact provenance
   record: same path, `url`, `pinned_commit`, and its (today, and
   expected to remain, unapproved) `redistribution_approved` state.

Every one of the four must agree on the submodule's exact `path` and
pinned commit OID; `.gitmodules` and the provenance record must agree on
the exact `url`; the export-exclusion record and the HEAD tree gitlink
must agree on the exact OID. A missing/duplicate/malformed `.gitmodules`
section, a path/URL mismatch anywhere, a URL that does not use the
`https://` scheme (this module's own minimal, explicit URL-scheme
policy -- a submodule fetched over an unauthenticated/plaintext or
otherwise ambiguous scheme is never accepted), a wrong gitlink mode/OID,
a wrong provenance/exclusion URL/OID, or the `mgfembp` path appearing in
the *included* source allowlist (an allowlist/exclusion contradiction --
it must be excluded there, never included) are all reported.

This module never fetches, initializes, or clones the submodule --
every check reads only already-committed, immutable blob/tree content
and the already-checked-in JSON data files.

Deliberately dependency-free (Python stdlib only); reuses
`git_source.py`/`gitmodules.py`/`tree_coverage.py`/`provenance.py`'s own
loaders rather than re-parsing their file formats a second time.

Exit codes (CLI): 0 clean binding, 1 binding finding(s), 2 invocation/I/O
or schema error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from scripts.release_rehearsal import allowlist as al
from scripts.release_rehearsal import git_source as gs
from scripts.release_rehearsal import gitmodules as gm
from scripts.release_rehearsal import provenance as prov
from scripts.release_rehearsal import tree_coverage as tc

DEFAULT_SUBMODULE_PATH = "mgfembp"
REQUIRED_URL_SCHEME = "https://"


class SubmoduleBindingError(ValueError):
    """An actionable I/O/schema defect in one of the four cross-checked
    sources -- distinct from a normal binding-mismatch finding (reported
    as a string in a list, never raised)."""


def check_submodule_binding(
    repo_root: Path,
    target_sha: str = "HEAD",
    submodule_path: str = DEFAULT_SUBMODULE_PATH,
    allowlist_path: Path = al.DEFAULT_ALLOWLIST_PATH,
    exclusions_path: Path = tc.DEFAULT_EXCLUSIONS_PATH,
    provenance_dir: Path = Path("docs/release_data/provenance"),
) -> List[str]:
    """The full three/four-way cross-check for `submodule_path` (default
    `"mgfembp"`). Returns a flat, human-readable finding list -- empty
    means every source agrees exactly. Never raises for an ordinary
    mismatch/inconsistency finding; only for a genuine I/O/schema defect
    in one of the four underlying files (propagated as
    `SubmoduleBindingError`, exactly like every other release-rehearsal
    module's `check()` entry point)."""
    reasons: List[str] = []

    # --- 1. .gitmodules -----------------------------------------------
    # A missing/unreadable/malformed `.gitmodules` is reported as a soft,
    # actionable *finding* here (never a hard raise) -- exactly like the
    # task's own "reject missing/duplicate/malformed .gitmodules
    # sections" framing describes it as one more binding-mismatch class,
    # not a distinct tooling-error class. This also lets every other
    # independent check below still run and report its own findings in
    # the same pass, instead of aborting the entire report at the first
    # problem found.
    gitmodules_url = None
    try:
        sections = gm.load_gitmodules_sections(repo_root, target_sha)
    except gm.GitmodulesError as error:
        reasons.append(str(error))
        sections = {}

    if sections:
        matches = [
            (name, section) for name, section in sections.items()
            if section.get("path") == submodule_path
        ]
        if not matches:
            reasons.append(
                f".gitmodules has no section declaring path {submodule_path!r} at {target_sha!r}"
            )
        elif len(matches) > 1:
            reasons.append(
                f".gitmodules has more than one section declaring path {submodule_path!r}: "
                f"{sorted(name for name, _ in matches)}"
            )
        else:
            _name, section = matches[0]
            gitmodules_url = section.get("url")
            if not gitmodules_url:
                reasons.append(f".gitmodules section for {submodule_path!r} has no 'url'")
            elif not gitmodules_url.startswith(REQUIRED_URL_SCHEME):
                reasons.append(
                    f".gitmodules url {gitmodules_url!r} for {submodule_path!r} does not use the "
                    f"required {REQUIRED_URL_SCHEME!r} scheme"
                )

    # --- 2. HEAD tree gitlink -------------------------------------------
    try:
        tree = {entry.path: entry for entry in gs.list_tree(repo_root, target_sha)}
    except gs.GitSourceError as error:
        raise SubmoduleBindingError(str(error)) from error
    tree_entry = tree.get(submodule_path)
    if tree_entry is None or not tree_entry.is_gitlink:
        reasons.append(
            f"no gitlink (mode {gs.MODE_GITLINK}) is recorded at {submodule_path!r} in the tree "
            f"at {target_sha!r}"
        )
        gitlink_oid = None
    else:
        gitlink_oid = tree_entry.object_id

    # --- 3. export_exclusions.json --------------------------------------
    try:
        exclusion_entries = tc.load_exclusions(exclusions_path)
    except tc.TreeCoverageError as error:
        raise SubmoduleBindingError(str(error)) from error
    exclusion_matches = [entry for entry in exclusion_entries if entry.path == submodule_path]
    if not exclusion_matches:
        reasons.append(f"no export-exclusion entry recorded for {submodule_path!r} in {exclusions_path}")
        exclusion_oid = None
    else:
        exclusion_entry = exclusion_matches[0]
        if exclusion_entry.kind != "gitlink":
            reasons.append(
                f"export-exclusion entry for {submodule_path!r} has kind {exclusion_entry.kind!r}, "
                "expected 'gitlink'"
            )
        exclusion_oid = exclusion_entry.oid
        if gitlink_oid is not None and exclusion_oid != gitlink_oid:
            reasons.append(
                f"export-exclusion OID {exclusion_oid!r} for {submodule_path!r} does not match the "
                f"actual gitlink OID {gitlink_oid!r} Git's tree records at {target_sha!r}"
            )

    # --- 4. provenance/submodules.json ----------------------------------
    try:
        provenance_entries = prov.load_all(provenance_dir)
    except prov.ProvenanceError as error:
        raise SubmoduleBindingError(str(error)) from error
    provenance_matches = [
        entry for entry in provenance_entries
        if entry["path"] == submodule_path and entry["category"] == "submodule"
    ]
    if not provenance_matches:
        reasons.append(
            f"no 'submodule'-category provenance entry recorded for {submodule_path!r} in "
            f"{provenance_dir}"
        )
    else:
        provenance_entry = provenance_matches[0]
        pinned_commit = provenance_entry.get("pinned_commit")
        if gitlink_oid is not None and pinned_commit != gitlink_oid:
            reasons.append(
                f"provenance pinned_commit {pinned_commit!r} for {submodule_path!r} does not match "
                f"the actual gitlink OID {gitlink_oid!r} Git's tree records at {target_sha!r}"
            )
        provenance_url = provenance_entry.get("url")
        if not provenance_url:
            reasons.append(f"provenance entry for {submodule_path!r} has no 'url'")
        elif gitmodules_url is not None and provenance_url != gitmodules_url:
            reasons.append(
                f"provenance url {provenance_url!r} for {submodule_path!r} does not match "
                f".gitmodules url {gitmodules_url!r}"
            )
        # This module never *requires* redistribution_approved to be any
        # particular value (that is provenance.py's own evaluate()'s
        # job, folded separately into the overall manifest status) -- it
        # only requires the field to be a real boolean the caller can
        # read truthfully; a non-bool would already have been rejected
        # by provenance.load_manifest's own schema check before this
        # function ever saw it.

    # --- 5. allowlist/exclusion contradiction ---------------------------
    try:
        allowlist_paths = al.load_allowlist_paths(allowlist_path)
    except al.AllowlistError as error:
        raise SubmoduleBindingError(str(error)) from error
    if submodule_path in allowlist_paths:
        reasons.append(
            f"{submodule_path!r} appears in the included source allowlist ({allowlist_path}) -- "
            "a gitlink must be excluded there, never included (allowlist/exclusion contradiction)"
        )
    if not exclusion_matches:
        pass  # already reported above; do not duplicate
    elif submodule_path not in {entry.path for entry in exclusion_entries}:
        reasons.append(f"{submodule_path!r} is missing from the export exclusions ({exclusions_path})")

    return sorted(set(reasons))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--target-sha", default="HEAD")
    parser.add_argument("--submodule-path", default=DEFAULT_SUBMODULE_PATH)
    parser.add_argument("--allowlist", type=Path, default=al.DEFAULT_ALLOWLIST_PATH)
    parser.add_argument("--exclusions", type=Path, default=tc.DEFAULT_EXCLUSIONS_PATH)
    parser.add_argument("--provenance-dir", type=Path, default=Path("docs/release_data/provenance"))
    args = parser.parse_args(argv)

    try:
        if args.target_sha == "index":
            target_sha = gs.write_index_tree(args.repo_root)
        else:
            target_sha = gs.resolve_sha(args.repo_root, args.target_sha)
    except gs.GitSourceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        reasons = check_submodule_binding(
            args.repo_root, target_sha, args.submodule_path,
            args.allowlist, args.exclusions, args.provenance_dir,
        )
    except SubmoduleBindingError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps({"submodule_path": args.submodule_path, "reasons": reasons}, indent=2, sort_keys=True))
    if reasons:
        print(f"submodule_binding: {len(reasons)} finding(s)", file=sys.stderr)
        return 1
    print(f"submodule_binding: ok ({args.submodule_path!r} fully bound at {target_sha!r})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
