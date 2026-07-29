#!/usr/bin/env python3
"""Read-only-publishing workflow permission/safety checker (issue #9).

A small, targeted text-based checker (deliberately not a general YAML
parser -- stdlib-only, no PyYAML dependency) for exactly the constraints
`.github/workflows/release-rehearsal.yml` must satisfy: read-only
top-level permissions, no credential persistence, no secrets, no tag/
release/asset/comment/environment mutation, no artifact upload, and a
pinned/accepted `actions/checkout` reference. See docs/release_process.md.

Exit codes (CLI): 0 clean, 1 violation(s) found, 2 invocation/I/O error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List

ALLOWED_TRIGGERS = {"pull_request", "workflow_dispatch"}
ALLOWED_CHECKOUT_REFS = {"v7"}
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

FORBIDDEN_SUBSTRINGS = (
    "upload-artifact",
    "actions/create-release",
    "softprops/action-gh-release",
    "gh release",
    "gh api -X POST",
    "gh api -X PATCH",
    "gh api -X PUT",
    "gh api -X DELETE",
    "git tag",
    "git push --tags",
    "environment:",
    "secrets.",
)


def _extract_block(text: str, key: str) -> str:
    """Extracts a fixed-indentation top-level `key:` mapping block's raw
    text (from the `key:` line up to, but excluding, the next line at
    indentation 0). Deliberately simple/line-based since this checks a
    single, repository-authored workflow file with a known fixed shape."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.rstrip() == f"{key}:" or line.startswith(f"{key}:"):
            start = index
            break
    if start is None:
        return ""
    block = [lines[start]]
    for line in lines[start + 1:]:
        if line.strip() == "":
            block.append(line)
            continue
        if not line.startswith((" ", "\t")):
            break
        block.append(line)
    return "\n".join(block)


def check_triggers(text: str) -> List[str]:
    violations = []
    block = _extract_block(text, "on")
    if not block:
        return ["no top-level 'on:' trigger block found"]
    found = set(re.findall(r"^\s{2}([a-zA-Z_]+):", block, flags=re.MULTILINE))
    disallowed = found - ALLOWED_TRIGGERS
    if disallowed:
        violations.append(f"disallowed trigger(s): {sorted(disallowed)} (only {sorted(ALLOWED_TRIGGERS)} allowed)")
    if not found:
        violations.append("'on:' block declares no recognizable trigger keys")
    return violations


def check_top_level_permissions(text: str) -> List[str]:
    violations = []
    lines = text.splitlines()
    top_level_perm_idx = None
    for index, line in enumerate(lines):
        if line.rstrip() == "permissions:":
            top_level_perm_idx = index
            break
        if line.startswith("jobs:"):
            break
    if top_level_perm_idx is None:
        violations.append("no top-level 'permissions:' block found before 'jobs:'")
        return violations
    block = _extract_block(text, "permissions")
    if "contents: read" not in block:
        violations.append("top-level permissions block does not declare 'contents: read'")
    if re.search(r"\bwrite\b", block):
        violations.append(f"top-level permissions block grants a 'write' scope: {block.strip()!r}")
    return violations


def check_no_write_anywhere(text: str) -> List[str]:
    violations = []
    for match in re.finditer(r"contents:\s*write", text):
        violations.append("found 'contents: write' outside the top-level permissions block")
    return violations


def check_checkout_pin(text: str) -> List[str]:
    violations = []
    refs = re.findall(r"uses:\s*actions/checkout@([^\s]+)", text)
    if not refs:
        violations.append("no 'actions/checkout' step found")
    for ref in refs:
        if ref not in ALLOWED_CHECKOUT_REFS and not FULL_SHA_RE.fullmatch(ref):
            violations.append(
                f"actions/checkout@{ref} is not an accepted version tag "
                f"({sorted(ALLOWED_CHECKOUT_REFS)}) or an immutable 40-hex commit SHA"
            )
    if "persist-credentials: false" not in text:
        violations.append("no checkout step sets 'persist-credentials: false'")
    return violations


def check_forbidden_substrings(text: str) -> List[str]:
    return [f"forbidden pattern found: {needle!r}" for needle in FORBIDDEN_SUBSTRINGS if needle in text]


def validate_workflow_text(text: str) -> List[str]:
    violations: List[str] = []
    violations.extend(check_triggers(text))
    violations.extend(check_top_level_permissions(text))
    violations.extend(check_no_write_anywhere(text))
    violations.extend(check_checkout_pin(text))
    violations.extend(check_forbidden_substrings(text))
    return violations


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", type=Path)
    args = parser.parse_args(argv)

    try:
        text = args.workflow.read_text(encoding="utf-8")
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    violations = validate_workflow_text(text)
    for violation in violations:
        print(violation)
    if violations:
        print(f"workflow_guard: {len(violations)} finding(s)", file=sys.stderr)
        return 1
    print(f"workflow_guard: {args.workflow} ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
