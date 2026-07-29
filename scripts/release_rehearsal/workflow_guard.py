#!/usr/bin/env python3
"""Read-only-publishing workflow permission/safety checker (issue #9).

A small, targeted text-based checker (deliberately not a general YAML
parser -- stdlib-only, no PyYAML dependency) for exactly the constraints
`.github/workflows/release-rehearsal.yml` must satisfy: read-only
top-level/job-level/nested permissions, no credential persistence, no
secrets/token interpolation, no tag/release/asset/comment/environment
mutation, no artifact upload, no network publish/upload/download
commands, and a pinned/accepted `actions/checkout` reference.

Conservative and fail-closed by construction: every check here is a
structured/line-aware substring or regex match, never a full YAML/shell
parse, so an ambiguous or unusual construct this module cannot fully
understand is far more likely to trip a rule (a false positive an author
must then justify/rephrase) than to silently slip through (a false
negative). See docs/release_process.md.

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

# Forbidden regardless of case/whitespace (each compiled with re.IGNORECASE
# below); every pattern here is a *substring or simple regex*, deliberately
# conservative rather than a full shell-semantics parse -- see module
# docstring. Line-continuation backslashes are collapsed before matching
# (see `_normalize_for_scanning`) so a naive "split the dangerous command
# across two lines" evasion does not work.
FORBIDDEN_PATTERNS = (
    (r"upload-artifact", "artifact upload action"),
    (r"actions/create-release", "release-creation action"),
    (r"softprops/action-gh-release", "release-creation action"),
    (r"\bgh\s+release\b", "'gh release' (mutating GitHub CLI subcommand)"),
    (r"gh\s+api\b[^\n]*(-x|--method)\s+(post|put|patch|delete)", "mutating 'gh api' call"),
    (r"\bgit\s+tag\b", "'git tag' (ref mutation)"),
    (r"\bgit\s+push\b", "'git push' (ref mutation)"),
    (r"environment\s*:", "GitHub Actions (protected-)environment usage"),
    (r"secrets\.", "'secrets.*' interpolation"),
    (r"github\.token\b", "'github.token' credential interpolation"),
    (r"\bgithub_token\b", "GITHUB_TOKEN credential reference"),
    (r"\bgh_token\b", "GH_TOKEN credential reference"),
    (r"\bcurl\b", "'curl' (network command)"),
    (r"\bwget\b", "'wget' (network command)"),
    (r"\bnc\s+-", "'nc' (network command)"),
    (r"\bncat\b", "'ncat' (network command)"),
    (r"base64\s+(-d|--decode)", "base64 decode (common obfuscation/indirection pattern)"),
    (r"\bsh\s+-c\b", "'sh -c' (shell indirection)"),
    (r"\bbash\s+-c\b", "'bash -c' (shell indirection)"),
    (r"\beval\b", "'eval' (shell/command indirection)"),
    (r"write-all", "GitHub Actions 'write-all' permissions shorthand"),
)
_COMPILED_FORBIDDEN_PATTERNS = [(re.compile(pattern, re.IGNORECASE), label) for pattern, label in FORBIDDEN_PATTERNS]

# `uses:` action-reference heuristics (issue #9 verifier remediation): a
# single generalized substring-in-the-action-name rule instead of an
# ever-growing enumeration of specific action names, so a "disguised"/
# unlisted-but-clearly-named upload/release/publish/deploy action is still
# caught. Deliberately case-insensitive.
_USES_LINE_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
_DANGEROUS_ACTION_NAME_SUBSTRINGS = ("upload", "release", "publish", "deploy")


def _normalize_for_scanning(text: str) -> str:
    """Collapses a POSIX shell line-continuation (a trailing backslash at
    end-of-line) into a single logical line before any pattern match runs,
    exactly like a real shell would when it actually executes a `run:`
    script -- the backslash and the newline are removed entirely (never
    replaced with a space), so a dangerous command split across two YAML
    lines, at *any* point including mid-token (a simple, common evasion
    of a naive single-line substring/regex check), cannot slip past
    `FORBIDDEN_PATTERNS`/checkout-pin checks. This is intentionally still
    just conservative text normalization, not a shell parser."""
    return re.sub(r"\\[ \t]*\n", "", text)


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
        violations.append(f"top-level permissions block does not declare 'contents: read': {block.strip()!r}")
    if re.search(r"\bwrite\b", block, re.IGNORECASE):
        violations.append(f"top-level permissions block grants a 'write' scope: {block.strip()!r}")
    return violations


def check_no_write_anywhere(text: str) -> List[str]:
    """Detects `contents: write` (job-level or nested, any indentation,
    any amount/kind of whitespace around the colon, optionally
    single/double-quoted) anywhere outside the validated top-level
    `permissions:` block -- i.e. everywhere, since this function scans the
    *entire* text; `check_top_level_permissions` above separately allows
    (indeed requires) `contents: read` there. Also flags a bare
    `permissions: write-all`/`write` shorthand scalar wherever it occurs."""
    violations = []
    for match in re.finditer(r"contents\s*:\s*['\"]?write\b", text, re.IGNORECASE):
        violations.append(f"found 'contents: write' outside the top-level permissions block: {match.group(0)!r}")
    for match in re.finditer(r"permissions\s*:\s*['\"]?write(-all)?\b", text, re.IGNORECASE):
        violations.append(f"found a 'permissions: write...' shorthand grant: {match.group(0)!r}")
    return violations


def check_checkout_pin(text: str) -> List[str]:
    violations = []
    refs = re.findall(r"uses:\s*actions/checkout@([^\s]+)", text, re.IGNORECASE)
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


def check_forbidden_patterns(text: str) -> List[str]:
    violations = []
    for pattern, label in _COMPILED_FORBIDDEN_PATTERNS:
        match = pattern.search(text)
        if match:
            violations.append(f"forbidden pattern found ({label}): {match.group(0)!r}")
    return violations


def check_dangerous_uses_actions(text: str) -> List[str]:
    """Generalized, case-insensitive `uses:` action-name heuristic: any
    referenced action whose name contains "upload", "release", "publish",
    or "deploy" is rejected, regardless of exact action identity/case --
    this deliberately catches a disguised/unlisted-but-clearly-named
    action (e.g. a fork, a differently-cased reference, or an action this
    module's authors have never heard of) instead of only matching a
    fixed enumeration that must be kept manually up to date forever."""
    violations = []
    for match in _USES_LINE_RE.finditer(text):
        action_ref = match.group(1)
        lowered = action_ref.lower()
        for needle in _DANGEROUS_ACTION_NAME_SUBSTRINGS:
            if needle in lowered:
                violations.append(f"'uses:' references a dangerous-sounding action: {action_ref!r} (contains {needle!r})")
                break
    return violations


def validate_workflow_text(text: str) -> List[str]:
    normalized = _normalize_for_scanning(text)
    violations: List[str] = []
    violations.extend(check_triggers(normalized))
    violations.extend(check_top_level_permissions(normalized))
    violations.extend(check_no_write_anywhere(normalized))
    violations.extend(check_checkout_pin(normalized))
    violations.extend(check_forbidden_patterns(normalized))
    violations.extend(check_dangerous_uses_actions(normalized))
    return sorted(set(violations))


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
