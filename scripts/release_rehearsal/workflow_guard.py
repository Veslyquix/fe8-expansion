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
    # Bare invocation (`nc host port`, no flag at all) is exactly as
    # dangerous as a flagged one (`nc -e /bin/sh host port`) -- a fresh,
    # independent verifier reproduced the previous `nc\s+-`-only pattern
    # missing it. `\bnc\b` alone (any standalone "nc" token, flagged or
    # not) closes that gap; the `\b` word-boundary already prevents this
    # from matching as a mere substring inside an unrelated identifier
    # (e.g. "sync", "func", "async", "runc" all keep "nc" glued to a
    # preceding word character, so no boundary ever forms there).
    (r"\bnc\b", "'nc' (network command, bare or flagged invocation)"),
    (r"\bncat\b", "'ncat' (network command)"),
    (r"base64\s+(-d|--decode)", "base64 decode (common obfuscation/indirection pattern)"),
    (r"\bsh\s+-c\b", "'sh -c' (shell indirection)"),
    (r"\bbash\s+-c\b", "'bash -c' (shell indirection)"),
    (r"\beval\b", "'eval' (shell/command indirection)"),
    # Package/registry publish + registry-credential commands (issue #9
    # residual hardening): a fresh, independent verifier reproduced these
    # as unrejected -- symmetrical with the existing `gh release`/`git
    # push`/`git tag` ref-mutation and release-action heuristics above.
    (r"\bnpm\s+publish\b", "'npm publish' (package registry publish command)"),
    (r"\byarn\s+publish\b", "'yarn publish' (package registry publish command)"),
    (r"\bpnpm\s+publish\b", "'pnpm publish' (package registry publish command)"),
    (r"\bdocker(\s+image)?\s+push\b", "'docker push' (container image publish command)"),
    (r"\bdocker\s+login\b", "'docker login' (container registry credential command)"),
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


# --- Shell variable/fragment command assembly (issue #9 residual
# hardening) ------------------------------------------------------------
#
# A fresh, independent verifier reproduced a dangerous command name
# assembled at *runtime* from two or more concatenated shell variable
# expansions in command position -- e.g. `X=cur; Y=l; $X$Y
# https://example.invalid` actually executes `curl ...` even though the
# literal substring "curl" never appears anywhere in the workflow file,
# so no substring/regex rule in `FORBIDDEN_PATTERNS` above can ever
# match it. This is a narrow, deliberately conservative, command-
# position/assignment-aware heuristic -- not a shell parser -- covering
# exactly the high-confidence shapes issue #9 names: `$X$Y`, `${X}${Y}`
# (and any bare/braced mix, 2 or more fragments), concatenated with zero
# intervening whitespace; and a single shell variable invoked directly
# as a command after being locally assigned a literal value earlier in
# the very same script (`CMD=curl` ... `$CMD https://...` -- no
# assembly needed, just one layer of indirection).
#
# This must never flag this real workflow's own safe, ordinary
# `>> "$GITHUB_STEP_SUMMARY"` job-summary redirection, nor ordinary
# non-command data interpolation (e.g. `echo "$A$B"`): both sit *after*
# the actual command name, never *at* command position, which is
# exactly what "command position" (defined below) excludes.
_VAR_REF = r"\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*"
_STATEMENT_SEP = r"(?:;|&&|\|\||\|)"
# A YAML `run:` scalar's *inline* value start (e.g. `- run: CMD=curl; ...`,
# the whole script on one physical text line) -- the shell script here
# begins right after the `run:` key, not at column 0 of the raw YAML
# text, so a bare `^` alone would miss it. Block-scalar forms
# (`run: |`, `run: >-`, ...) are unaffected: their actual command text
# starts on the *next* line, which the plain `^` alternative already
# covers, and the literal characters right after "run:" there (`|`,
# `>`, a fold/chomp indicator) never satisfy the identifier/`$`
# patterns below anyway, so no separate carve-out is needed for them.
_RUN_SCALAR_PREFIX = r"\brun:[ \t]*"
# The start of a `run:` script line (any line -- real line-continuations
# are already collapsed by `_normalize_for_scanning` before this ever
# runs), the inline start of a `run:` scalar's value on the same text
# line, or, on the same line, immediately after a shell command
# separator (`;`, `&&`, `||`, or a pipe `|`). Deliberately line/
# separator-aware rather than a full parser -- see module docstring.
_COMMAND_POSITION_PREFIX = rf"(?:^|{_STATEMENT_SEP}|{_RUN_SCALAR_PREFIX})[ \t]*"
# A statement boundary: another separator, or a genuine end-of-line/
# end-of-text -- `\r` and `\n` are both matched directly (rather than
# relying solely on MULTILINE `$`, which sits *before* a bare `\n` and
# would otherwise miss a CRLF file's trailing `\r`).
_STATEMENT_END = rf"(?:{_STATEMENT_SEP}|[\r\n]|$)"
_BOUNDARY_AFTER = r"(?:[ \t\r\n]|$)"

_CONCATENATED_VAR_REFS_RE = re.compile(
    rf"{_COMMAND_POSITION_PREFIX}(?:{_VAR_REF}){{2,}}", re.MULTILINE
)
_COMMAND_POSITION_SINGLE_VAR_RE = re.compile(
    rf"{_COMMAND_POSITION_PREFIX}({_VAR_REF})(?={_BOUNDARY_AFTER})", re.MULTILINE
)
# A "pure" local shell-variable assignment statement: exactly
# `NAME=value` occupying an entire command position by itself (no
# attached command afterward on the same statement -- so the common,
# legitimate `FOO=bar some-command args` inline-env-var-prefix idiom is
# deliberately *not* matched/recorded here). Never tries to resolve/
# interpret `value` itself (no shell parser); merely recording *that*
# `NAME` was locally assigned anything at all is enough to make a later
# bare `$NAME`/`${NAME}` command-position invocation of it suspicious.
_PURE_ASSIGNMENT_RE = re.compile(
    rf"{_COMMAND_POSITION_PREFIX}([A-Za-z_][A-Za-z0-9_]*)=[^\s;&|]*[ \t]*(?={_STATEMENT_END})",
    re.MULTILINE,
)
_SINGLE_VAR_NAME_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")


def check_variable_command_assembly(text: str) -> List[str]:
    """Rejects (1) two or more shell variable expansions concatenated
    with zero intervening whitespace in command position (`$X$Y`,
    `${X}${Y}`, and any bare/braced mix) -- a command name assembled at
    runtime from separately-innocuous fragments -- and (2) a single
    shell variable, previously assigned a literal value elsewhere in the
    very same script, later invoked directly in command position (e.g.
    `CMD=curl` ... `$CMD https://...`). Both are high-confidence,
    command-position-aware evasions of every literal-command-name check
    in `FORBIDDEN_PATTERNS` above; neither ever fires against ordinary
    tail-position interpolation (e.g. this repository's own real
    `>> "$GITHUB_STEP_SUMMARY"`) or plain data interpolation, since
    those never sit in command position."""
    violations: List[str] = []
    for match in _CONCATENATED_VAR_REFS_RE.finditer(text):
        shown = re.sub(r"^[ \t;&|]+", "", match.group(0))
        violations.append(
            "command position invokes a name assembled by concatenating 2+ shell variable "
            f"expansions with no separator (evades literal-command-name detection): {shown!r}"
        )
    assigned_names = {match.group(1) for match in _PURE_ASSIGNMENT_RE.finditer(text)}
    if assigned_names:
        for match in _COMMAND_POSITION_SINGLE_VAR_RE.finditer(text):
            name_match = _SINGLE_VAR_NAME_RE.fullmatch(match.group(1))
            if name_match and name_match.group(1) in assigned_names:
                shown = re.sub(r"^[ \t;&|]+", "", match.group(0))
                violations.append(
                    "command position directly invokes shell variable "
                    f"{match.group(1)!r}, which was locally assigned a literal value earlier "
                    f"in this same script (evades literal-command-name detection): {shown!r}"
                )
    return violations


def _normalize_for_scanning(text: str) -> str:
    """Collapses a POSIX shell line-continuation (a trailing backslash at
    end-of-line) into a single logical line before any pattern match runs,
    exactly like a real shell would when it actually executes a `run:`
    script -- the backslash and the newline are removed entirely (never
    replaced with a space), so a dangerous command split across two YAML
    lines, at *any* point including mid-token (a simple, common evasion
    of a naive single-line substring/regex check), cannot slip past
    `FORBIDDEN_PATTERNS`/checkout-pin checks.

    This also consumes (discards) any leading indentation -- spaces or
    tabs -- at the start of the continuation line itself. That mirrors
    the two layers of real semantics that actually apply to a `run: |`
    step: (1) a YAML block-scalar strips every line's *common* leading
    indentation before the shell ever sees the script text, so an
    equally-indented continuation line (the realistic, common-looking
    shape an author -- or an adversary -- actually writes) reaches the
    shell with *no* leading whitespace of its own, and (2) POSIX shell
    backslash-newline splicing then joins the (now-dedented) lines with
    no separator inserted. Skipping the indentation-consumption step
    would leave the continuation line's raw *YAML source* indentation
    sitting literally inside the joined line -- e.g. `gh rel\\` followed
    by an indented `ease create ...` would normalize to `gh rel
    ease create ...` (still two separate whitespace-separated words, so
    `\\bgh\\s+release\\b` never matches) instead of the actual executed
    `gh release create ...` (a single, dangerous `gh release`
    invocation). Handles CRLF line endings the same way. This is
    intentionally still just conservative text normalization, not a
    shell parser."""
    return re.sub(r"\\[ \t]*\r?\n[ \t]*", "", text)


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


# Any GitHub Actions permission *scope* name (`contents`, `id-token`,
# `packages`, `pull-requests`, `issues`, `actions`, `checks`,
# `deployments`, `statuses`, `pages`, `security-events`, `discussions`,
# `attestations`, `models`, and any future scope GitHub ever adds) is a
# lowercase-with-hyphens identifier. Rather than enumerate a fixed,
# ever-growing list of "known" scope names (issue #9 verifier
# remediation: the independent reviewer found the previous check only
# ever matched the literal word `contents`), this matches *any*
# identifier-shaped mapping key -- quoted or not, any case, any amount of
# surrounding whitespace, whether it appears at top level, job level,
# deeply nested, or inside a `{ "flow", "mapping" }` -- immediately
# followed by a `write`/`write-all` value. A single, general rule instead
# of a fixed enumeration is exactly the same "generalized heuristic over
# an ever-growing specific list" design `_DANGEROUS_ACTION_NAME_SUBSTRINGS`
# already uses for `uses:` action names below.
_ANY_SCOPE_WRITE_RE = re.compile(
    r"""['"]?(?P<scope>[a-zA-Z][a-zA-Z0-9_-]*)['"]?\s*:\s*['"]?(?P<value>write(?:-all)?)['"]?\b""",
    re.IGNORECASE,
)


def check_no_write_anywhere(text: str) -> List[str]:
    """Detects **any** `<scope>: write` permission grant -- `contents`,
    `id-token`, `packages`, `pull-requests`, `issues`, `actions`,
    `checks`, `deployments`, `statuses`, or any scope this module's
    authors have never heard of -- job-level or nested, any indentation,
    any amount/kind of whitespace around the colon, any case, optionally
    single/double-quoted (key and/or value), and whether it sits in
    block style or an inline/flow mapping (e.g.
    `permissions: {contents: read, id-token: write}`) -- anywhere outside
    the validated top-level `permissions:` block -- i.e. everywhere,
    since this function scans the *entire* text; `check_top_level_
    permissions` above separately allows (indeed requires) `contents:
    read` there, and never itself grants any scope `write`. Also flags a
    bare `permissions: write-all`/`write` shorthand scalar wherever it
    occurs, and a bare, ambiguous `write`/`write-all` shorthand for any
    other scope-shaped key."""
    violations = []
    for match in _ANY_SCOPE_WRITE_RE.finditer(text):
        scope, value = match.group("scope"), match.group("value")
        # The message always includes the *canonical*, whitespace/quote-
        # normalized "scope: value" rendering (reconstructed from the
        # named groups, e.g. always exactly "contents: write" -- never
        # "contents:      write" or "'contents': write" verbatim) so a
        # consumer/test can match on it regardless of the original
        # formatting quirk that was actually used, plus the raw matched
        # text for full transparency.
        violations.append(
            f"found permission scope grant {scope}: {value} (raw: {match.group(0)!r})"
        )
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
    violations.extend(check_variable_command_assembly(normalized))
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
