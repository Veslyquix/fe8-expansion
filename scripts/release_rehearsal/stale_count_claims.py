#!/usr/bin/env python3
"""Stale aggregate-test-count claim regression guard (issue #9 verifier
remediation).

Independent verification found that release closure evidence
(``docs/release_closure_candidate.md``) had accumulated brittle,
hardcoded aggregate test-count claims (e.g. "the full ... stdlib test
suite (860 tests)", "``Ran 860 tests ... FAILED``") that silently go
stale the moment a test is added, renamed, or removed -- exactly the
kind of frozen number a dynamic, re-runnable command should report
instead (see ``python3 -m unittest discover ...``'s own live output).

This module scans a fixed set of release-relevant docs/evidence for the
specific *shape* of an aggregate test-count claim -- "N test(s)" in
immediate numeric-adjacent position (`"(860 tests)"`, `"860 tests
pass"`, `"Ran 860 tests"`, `"all-860-passing"`) -- and flags it
unconditionally (there is no "correct" frozen aggregate count; the fix
is always to describe the *command* a reviewer can re-run, never a
specific number). This is deliberately narrower than "any digit near the
word test": a small, legitimate semantic constant or delta ("2 new
regression tests", "seven live structural findings", "epoch bumped from
1 to 2") is never adjacent to the word "test(s)" in the specific
countable-total shapes this module matches, so those are never flagged.

Deliberately dependency-free (Python stdlib only), matching this
repository's other release-rehearsal tooling.

Exit codes (CLI): 0 clean, 1 stale claim(s) found, 2 invocation/I/O error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

# The release-process-relevant surface this scan owns -- scoped
# deliberately (not every *.md in the repository) to stay within issue
# #9's own file domain, matching doc_links.py's/epoch_claims.py's own
# DEFAULT_* pattern.
DEFAULT_TARGETS: Tuple[str, ...] = (
    "docs/release_process.md",
    "docs/release_closure_candidate.md",
)

# Each pattern matches one specific *aggregate test-count claim* shape;
# every one requires the number to sit immediately adjacent to "test(s)"
# in a counting/total context -- never merely "a digit somewhere near
# the word test".
_AGGREGATE_COUNT_PATTERNS = (
    r"\bRan\s+\d+\s+tests?\b",
    r"\(\s*\d+\s+tests?\s*\)",
    r"\ball-\d+-passing\b",
    r"\b\d+\s+tests?\s+(?:pass|passing|passed|total|run)\b",
    r"\btest\s+suite\s*\(\s*\d+\s+tests?\s*\)",
)
AGGREGATE_COUNT_RE = re.compile("|".join(_AGGREGATE_COUNT_PATTERNS), re.IGNORECASE)


class StaleCountClaimError(ValueError):
    """An actionable invocation/I/O error -- distinct from a stale-claim finding."""


def find_stale_count_claims(repo_root: Path, target_relpaths: Tuple[str, ...] = DEFAULT_TARGETS) -> List[str]:
    """Returns a list of human-readable findings (empty means clean).
    Each finding names the exact file, line number, and matched text. A
    target file that does not exist is silently skipped."""
    repo_root = Path(repo_root)
    findings: List[str] = []
    for relpath in target_relpaths:
        path = repo_root / relpath
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in AGGREGATE_COUNT_RE.finditer(line):
                findings.append(
                    f"{relpath}:{lineno}: hardcoded aggregate test-count claim {match.group(0)!r} -- "
                    "report the exact command a reviewer can re-run instead of a frozen total "
                    f"(context: {line.strip()!r})"
                )
    return findings


def check(repo_root: Path, target_relpaths: Tuple[str, ...] = DEFAULT_TARGETS) -> dict:
    """Manifest-shaped report: `{"ok": bool, "errors": [...]}`."""
    findings = find_stale_count_claims(repo_root, target_relpaths)
    return {"ok": not findings, "errors": findings}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("targets", nargs="*", default=None, help="override the default target set")
    args = parser.parse_args(argv)

    try:
        targets = tuple(args.targets) if args.targets else DEFAULT_TARGETS
        findings = find_stale_count_claims(args.repo_root, targets)
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    for finding in findings:
        print(finding)
    if findings:
        print(f"stale_count_claims: {len(findings)} stale claim(s)", file=sys.stderr)
        return 1
    print("stale_count_claims: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
