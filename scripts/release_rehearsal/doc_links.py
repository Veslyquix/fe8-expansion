#!/usr/bin/env python3
"""Release-doc relative-link validator (issue #9 verifier remediation).

The independent verifier found three broken relative Markdown links in
this issue's own documentation (each pointed at a "release/..." path that
was never actually created; the real directory is
``docs/release_data/...``). This module is the regression guard: it scans
a fixed set of release-process-related Markdown documents for Markdown-
style relative links (``[text](path)``) and verifies every non-HTTP(S),
non-fragment-only link target resolves to an existing file relative to
the linking document.

Deliberately dependency-free (Python stdlib only, a regex scan -- not a
full Markdown parser, matching this repository's other release-rehearsal
tooling).

Exit codes (CLI): 0 clean, 1 broken link(s) found, 2 invocation/I/O error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

LINK_RE = re.compile(r"\]\(([^)]+)\)")

# The release-process documentation set this issue introduced/touches;
# scoped deliberately (not every *.md in the repository) to stay within
# issue #9's own file domain and avoid flagging pre-existing, unrelated
# documentation this issue does not own.
DEFAULT_DOCS: Tuple[str, ...] = (
    "docs/release_process.md",
    "docs/public_api_policy.md",
    "docs/migration_registry.md",
    "docs/save_format.md",
    "docs/release_closure_candidate.md",
    "CHANGELOG.md",
)


def find_broken_links(repo_root: Path, doc_relpaths: Sequence[str] = DEFAULT_DOCS) -> List[Tuple[str, str]]:
    """Returns a list of (doc_relpath, broken_target) pairs; empty means
    every scanned link resolves. A missing doc itself is reported as one
    finding with the sentinel target ``"<doc-missing>"``."""
    repo_root = Path(repo_root)
    broken: List[Tuple[str, str]] = []
    for relpath in doc_relpaths:
        path = repo_root / relpath
        if not path.is_file():
            broken.append((relpath, "<doc-missing>"))
            continue
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("#"):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved = path.parent / path_part
            if not resolved.exists():
                broken.append((relpath, target))
    return broken


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("docs", nargs="*", default=None, help="override the default doc set")
    args = parser.parse_args(argv)

    try:
        doc_relpaths = tuple(args.docs) if args.docs else DEFAULT_DOCS
        broken = find_broken_links(args.repo_root, doc_relpaths)
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    for relpath, target in broken:
        print(f"{relpath}: broken link -> {target}")
    if broken:
        print(f"doc_links: {len(broken)} broken link(s)", file=sys.stderr)
        return 1
    print("doc_links: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
