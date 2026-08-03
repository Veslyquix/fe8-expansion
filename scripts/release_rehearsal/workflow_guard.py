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
from dataclasses import dataclass
from pathlib import Path
from typing import List

ALLOWED_TRIGGERS = {"pull_request", "workflow_dispatch"}
# issue #9 mandatory correction #1: there is no mutable-ref allowance any
# more (no version tag, branch, or short SHA of any external action is
# ever accepted -- see `check_uses_pins` below). `FULL_SHA_RE` is the one
# and only accepted shape for an external `uses:` reference's pin.
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
    # Shell process substitution (issue #9 final hardening): `<(...)` and
    # `>(...)` are real POSIX/bash command-position constructs -- their
    # body is executed as a command exactly like `$(...)` or a backtick
    # substitution is, so the same variable/fragment-assembly bypass
    # this module already closes for `$(...)`/backticks would apply
    # equally here. This real workflow has no legitimate use for either
    # spelling anywhere (confirmed: neither appears in
    # `.github/workflows/release-rehearsal.yml`), so -- following this
    # module's conservative, fail-closed design and the Musk-algorithm
    # instinct to delete rather than grow speculative complexity -- both
    # are rejected outright wherever they appear, rather than adding a
    # third parallel command-position-tracking implementation for a
    # construct the real workflow never needs.
    (r"<\(", "shell process substitution ('<(...)', unused by this real workflow; rejected fail-closed)"),
    (r">\(", "shell process substitution ('>(...)', unused by this real workflow; rejected fail-closed)"),
    (r"write-all", "GitHub Actions 'write-all' permissions shorthand"),
)
_COMPILED_FORBIDDEN_PATTERNS = [(re.compile(pattern, re.IGNORECASE), label) for pattern, label in FORBIDDEN_PATTERNS]

# `uses:` action-reference heuristics (issue #9 verifier remediation): a
# single generalized substring-in-the-action-name rule instead of an
# ever-growing enumeration of specific action names, so a "disguised"/
# unlisted-but-clearly-named upload/release/publish/deploy action is still
# caught. Deliberately case-insensitive.
_DANGEROUS_ACTION_NAME_SUBSTRINGS = ("upload", "release", "publish", "deploy")


# --- Canonical `uses:` occurrence extraction (fail-closed workflow/
# action-pin parsing hardening) ------------------------------------------
#
# The previous implementation here was a single line-anchored regex
# (`^\s*(?:-\s*)?uses:\s*(\S+)`, one match per *line*, MULTILINE): it only
# ever recognized a bare, unquoted `uses:` key sitting at the very start
# of a line (optionally after a single `-\s*` list-item marker). Two
# independent code-review findings showed that shape covers only the
# "happy path" YAML this repository's own real workflow happens to use,
# and is trivially bypassed by other, equally-valid YAML spellings of
# exactly the same key/value pair:
#
#   * a flow mapping step, e.g. `- {uses: actions/checkout@mutable}` or
#     `- {"uses": "actions/checkout@mutable"}` -- the key never sits at
#     column 0 (or right after a bare `-\s*`), so the old regex's `^`
#     anchor never matched it at all: a mutable ref hidden inside a flow
#     mapping silently passed every check below.
#   * a quoted key in block style, e.g. `"uses": ...` / `'uses': ...` --
#     the old regex only ever matched the bare word `uses`, never a
#     quoted spelling of it.
#   * a quoted *value*, e.g. `uses: "actions/checkout@mutable"` -- the
#     old regex's `(\S+)` captured the value *including* its
#     surrounding quote characters, which then never matched
#     `_USES_REF_SPLIT_RE` (a literal `"` is not part of any real action
#     name), so `check_uses_pins` silently treated it as a "no @ref at
#     all" case instead of validating the real, quoted pin underneath.
#
# This module deliberately still never depends on PyYAML (or any other
# new dependency) and never executes/evaluates any YAML or template --
# see the module docstring. Instead, `extract_uses_occurrences` below is
# a single, well-defined, structural *subset* scanner: a hand-written,
# character-by-character reader that understands exactly the YAML
# constructs a `uses:` key/value pair can legally appear in (block
# mapping, flow mapping, single/double-quoted keys and values, line
# comments, and enough indentation-/bracket-depth-aware nesting to tell
# one mapping scope apart from another for duplicate-key detection) --
# and explicitly, individually flags (rather than silently skipping)
# every construct it does not fully, unambiguously understand: a YAML
# anchor (`&name`) or an explicit tag (`!!str`, `!foo`) attached to the
# value, a YAML alias (`*name`) as the value, a GitHub Actions
# expression/template (`${{ ... }}`) anywhere in the value, an
# unterminated or multi-line quoted scalar, an unquoted `:` followed by
# whitespace inside a plain value (a strong sign of an unintended nested
# mapping key -- YAML's own plain-scalar grammar treats it exactly the
# same way), and a duplicate `uses` key repeated within the same
# enclosing mapping (block or flow). None of these ever "pass" -- every
# one of them produces a `problem`-tagged `UsesOccurrence` that
# `check_uses_pins` (below) always reports as a hard violation,
# regardless of what text happens to follow. This is the single,
# canonical extractor: `workflow_guard.check_uses_pins`,
# `check_checkout_pin`, `check_dangerous_uses_actions`, and
# `scripts/release_rehearsal/action_pins.py` (via
# `extract_uses_occurrences`) all share this one implementation -- there
# is exactly one definition, repository-wide, of what a `uses:`
# reference looks like and how to find every occurrence of one.
#
# Every physical `uses:` occurrence is yielded independently (never
# collapsed/deduplicated by action name) -- callers that need an
# action-name-keyed view (e.g. `action_pins.py`'s inventory cross-check)
# are responsible for grouping this module's occurrence list themselves,
# preserving every individual occurrence (see that module's own
# `workflow_external_occurrences`) -- this scanner itself never discards
# or overwrites one occurrence with another.
@dataclass(frozen=True)
class UsesOccurrence:
    """One `uses:` key/value pair found anywhere in a workflow's raw
    text (block or flow style, quoted or bare key). `line` is the
    1-based source line the *key* starts on. `key_repr` is the exact key
    spelling as found (`"uses"`, `'uses'`, or bare `uses`). `raw_value`
    is the unparsed value text exactly as it appeared (quotes, anchor/
    alias/tag prefix, and all -- for diagnostics). `action_ref` is the
    best-effort *decoded* value (quotes stripped/unescaped for a quoted
    scalar; the raw text, including any anchor/alias/tag prefix, for an
    unsupported shape) -- always a `str` (never `None`; an entirely
    empty `uses:` value decodes to `""`). `problem` is `None` for a
    clean, statically-resolvable value, or one of the short reason codes
    below (`"anchor"`, `"alias"`, `"tag"`, `"template-expression"`,
    `"unterminated-quote"`, `"ambiguous-colon-in-value"`,
    `"duplicate-key"`) otherwise. A caller must always treat any
    non-`None` `problem` as an unconditional, fail-closed rejection --
    never attempt to still parse/trust `action_ref` in that case."""

    line: int
    key_repr: str
    raw_value: str
    action_ref: str
    problem: "str | None"


# Deliberately excludes "#": whether an unquoted "#" terminates a
# plain value as a trailing comment depends on context (it must be
# preceded by whitespace -- see the design-rationale comment on the
# main scan loop's own "#" handling above) rather than being an
# unconditional terminator, so it is handled explicitly inline
# in the plain-value scan below instead of living in this set.
_PLAIN_VALUE_TERMINATORS = frozenset(",}]\r\n")


def _scan_quoted_scalar(text: str, start: int, quote: str):
    """`start` indexes the opening quote character. Returns `(end,
    content, ok)`: `end` is the index just past the closing quote (or,
    if never properly closed, the index of the first raw `\r`/`\n`
    encountered, or `len(text)` if neither ever appears); `content` is
    the decoded scalar (double-quote backslash escapes resolved;
    single-quote `''` resolved to a literal `'`); `ok` is `False` if a
    raw newline was reached (or the text ran out) before the scalar was
    properly closed on the same logical line -- this scanner
    deliberately does not support a `uses:` value folded/continued
    across multiple physical lines (an obscure, never-needed-in-
    practice shape for a short action-reference string); an unterminated
    quote always fails closed rather than silently guessing where it
    should have ended."""
    n = len(text)
    i = start + 1
    parts: List[str] = []
    if quote == '"':
        escapes = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r", "0": "\0"}
        while i < n:
            c = text[i]
            if c == "\\" and i + 1 < n and text[i + 1] not in "\r\n":
                nxt = text[i + 1]
                parts.append(escapes.get(nxt, nxt))
                i += 2
                continue
            if c == '"':
                return i + 1, "".join(parts), True
            if c in "\r\n":
                return i, "".join(parts), False
            parts.append(c)
            i += 1
        return i, "".join(parts), False
    while i < n:
        c = text[i]
        if c == "'":
            if i + 1 < n and text[i + 1] == "'":
                parts.append("'")
                i += 2
                continue
            return i + 1, "".join(parts), True
        if c in "\r\n":
            return i, "".join(parts), False
        parts.append(c)
        i += 1
    return i, "".join(parts), False


def extract_uses_occurrences(text: str) -> List[UsesOccurrence]:
    """The single, canonical `uses:` key/value-pair scanner (see the
    design-rationale comment block above this function). Fails closed by
    construction: a `uses:` value shape this scanner does not fully,
    unambiguously understand is always yielded with a non-`None`
    `problem` (never silently skipped/ignored), and a `uses` key
    repeated within the same enclosing mapping (block or flow) is always
    flagged `"duplicate-key"` for every repeat after the first."""
    occurrences: List[UsesOccurrence] = []
    n = len(text)
    i = 0
    line = 1
    # `flow_stack`: one frame per currently-open `{`/`[`; only a `{`
    # (mapping) frame's `seen` set matters for duplicate-key detection --
    # a `[` (sequence) frame carries no key semantics of its own but
    # still needs a stack slot so its matching `]` pops the right frame.
    flow_stack: List[dict] = []
    # `block_stack[0]` is a permanent root/document-level scope (never
    # popped) so even a stray top-level `uses:` (outside any list item)
    # still has a defined enclosing scope to check for a duplicate
    # sibling. Every subsequent frame corresponds to one open block
    # list-item (`- ...`) mapping, keyed by that item's own `-` column
    # (`indent`) so a dedent (a new line whose indentation is at or
    # below an open item's own column) correctly closes it -- and every
    # deeper-nested item -- before any new key on that line is scanned.
    block_stack: List[dict] = [{"indent": -1, "seen": set()}]

    def current_scope() -> dict:
        for frame in reversed(flow_stack):
            if frame["kind"] == "{":
                return frame
        return block_stack[-1]

    at_line_start = True
    while i < n:
        if at_line_start:
            j = i
            while j < n and text[j] in " \t":
                j += 1
            if j < n and text[j] not in "\r\n":
                indent = j - i
                if not flow_stack:
                    while len(block_stack) > 1 and block_stack[-1]["indent"] >= indent:
                        block_stack.pop()
                    if text[j] == "-" and (j + 1 >= n or text[j + 1] in " \t\r\n"):
                        block_stack.append({"indent": indent, "seen": set()})
            at_line_start = False

        ch = text[i]

        if ch == "\n":
            line += 1
            at_line_start = True
            i += 1
            continue
        if ch == "\r":
            i += 1
            continue
        # YAML's comment indicator ("#") only ever starts a comment
        # when it is the first character on the (logical) line or is
        # immediately preceded by whitespace (a space or tab) -- see
        # YAML spec 6.2.4 / 7.3.3 ("Plain scalars must not contain the
        # '#' character preceded by whitespace [that is not itself part
        # of the scalar]"; conversely, a '#' with *no* preceding
        # whitespace is simply an ordinary character embedded in
        # whatever token precedes it, e.g. the plain scalar `setup#`).
        # A fresh, independent final review reproduced a fail-open
        # bypass here: `- {name: setup#, uses: evilcorp/...@main}` has
        # its `#` glued directly onto `setup` with no preceding
        # whitespace, so it is *not* a comment at all -- the previous,
        # unconditional "any '#' starts a comment" rule nonetheless
        # consumed the rest of that physical line (silently discarding
        # the very real `uses:` key that followed), so the dangerous,
        # mutable-ref `uses:` occurrence was never even yielded, let
        # alone rejected. When the preceding-whitespace/start-of-line
        # condition does not hold, '#' is simply an ordinary character:
        # fall through to the normal key/quote/plain-value handling
        # below (which, for a bare '#' matching none of those, just
        # advances one character at the bottom of this loop) instead of
        # ever silently truncating the rest of the line.
        if ch == "#" and (i == 0 or text[i - 1] in " \t\r\n"):
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        if ch in "{[":
            flow_stack.append({"kind": ch, "seen": set()})
            i += 1
            continue
        if ch in "}]":
            if flow_stack:
                flow_stack.pop()
            i += 1
            continue

        # A `uses` key -- quoted (`"uses":`/`'uses':`) or bare (`uses:`)
        # -- attempted *before* any generic quote handling below, so a
        # quoted key is recognized as a key instead of merely being
        # consumed as an unrelated quoted scalar.
        key_repr = None
        key_end = None
        quote = ch if ch in ('"', "'") else None
        if quote is not None:
            if text[i + 1:i + 5] == "uses" and i + 5 < n and text[i + 5] == quote:
                k = i + 6
                while k < n and text[k] in " \t":
                    k += 1
                if k < n and text[k] == ":" and (k + 1 >= n or text[k + 1] != ":"):
                    key_repr = f"{quote}uses{quote}"
                    key_end = k + 1
        elif ch == "u" and text[i:i + 4] == "uses":
            word_boundary_before = i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")
            if word_boundary_before:
                k = i + 4
                while k < n and text[k] in " \t":
                    k += 1
                if k < n and text[k] == ":" and (k + 1 >= n or text[k + 1] != ":"):
                    key_repr = "uses"
                    key_end = k + 1

        if key_repr is None:
            if quote is not None:
                end, _content, _ok = _scan_quoted_scalar(text, i, quote)
                i = end
            else:
                i += 1
            continue

        k = key_end
        while k < n and text[k] in " \t":
            k += 1

        problem = None
        ws_before_value = k > key_end
        raw_start = k
        if k >= n or text[k] in "\r\n":
            value = ""
        elif text[k] == "#" and ws_before_value:
            # Same YAML comment-indicator rule as the main scan loop:
            # only a "#" preceded by whitespace (here, at least one
            # space/tab consumed right after the "uses:" colon) is a
            # comment. A bare "uses:#..." (no separating whitespace at
            # all) falls through to the plain-value branch below
            # instead, where it is treated as literal value content.
            value = ""
        elif text[k] in "&*!":
            prefix = text[k]
            end_of_line = k
            while end_of_line < n and text[end_of_line] not in "\r\n":
                end_of_line += 1
            value = text[k:end_of_line].strip()
            problem = {"&": "anchor", "*": "alias", "!": "tag"}[prefix]
            k = end_of_line
        elif text[k] in ('"', "'"):
            q = text[k]
            end, content, ok = _scan_quoted_scalar(text, k, q)
            value = content
            if not ok:
                problem = "unterminated-quote"
            elif "${{" in content:
                problem = "template-expression"
            k = end
        else:
            start = k
            ambiguous_colon = False
            while k < n and text[k] not in _PLAIN_VALUE_TERMINATORS:
                # A "#" only terminates a plain value as a trailing
                # comment when it is preceded by whitespace (a space or
                # tab) -- exactly the same YAML comment-indicator rule
                # as the main scan loop above. A final review reproduced
                # a fail-open bypass here: an unquoted plain value such
                # as `setup#` (no whitespace before the "#") previously
                # had this "#" mis-treated as an unconditional
                # terminator by `_PLAIN_VALUE_TERMINATORS`, truncating
                # the value and -- worse, in the main scan loop's own
                # matching bug -- discarding whatever real YAML followed
                # it on the same line (e.g. a sibling `uses:` key).
                # `k > start` guards the very first character of this
                # value: a "#" glued directly onto the preceding ":" (no
                # separating whitespace at all) is never treated as a
                # comment either, and instead becomes literal value
                # content, consistent with the "must be preceded by
                # whitespace" rule (there is no whitespace to precede it
                # here at all).
                if text[k] == "#" and k > start and text[k - 1] in " \t":
                    break
                if text[k] == ":" and (k + 1 >= n or text[k + 1] in " \t\r\n"):
                    ambiguous_colon = True
                    break
                k += 1
            value = text[start:k].strip()
            if ambiguous_colon:
                problem = "ambiguous-colon-in-value"
            elif "${{" in value:
                problem = "template-expression"

        scope = current_scope()
        if "uses" in scope["seen"]:
            problem = problem or "duplicate-key"
        else:
            scope["seen"].add("uses")

        occurrences.append(
            UsesOccurrence(
                line=line,
                key_repr=key_repr,
                raw_value=text[raw_start:k],
                action_ref=value,
                problem=problem,
            )
        )
        i = k

    return occurrences


_PROBLEM_DESCRIPTIONS = {
    "anchor": "a YAML anchor ('&name') attached to the value -- this scanner never resolves anchors",
    "alias": "a YAML alias ('*name') -- this scanner never resolves aliases, so the actual pinned value cannot be statically verified",
    "tag": "an explicit YAML tag (e.g. '!!str'/'!foo') attached to the value",
    "template-expression": "a GitHub Actions expression ('${{ ... }}') or other template/variable substitution -- the actual pinned value is not statically knowable and can change at runtime",
    "unterminated-quote": "an unterminated or multi-line quoted string -- only a single-line quoted scalar is a supported 'uses:' value shape",
    "ambiguous-colon-in-value": "an unquoted ':' followed by whitespace inside the value -- this looks like an unintended nested mapping key, not a real action reference",
    "duplicate-key": "a duplicate 'uses' key repeated within the same enclosing mapping -- a YAML mapping must not repeat a key, and this scanner refuses to guess which repeated value would actually win",
}


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
# The opening of a POSIX command-substitution subshell: either the
# modern `$(` spelling, or the legacy backtick (`` ` ``) spelling --
# both are real POSIX command-substitution syntax, and a fresh,
# independent final review confirmed the previous `$(`-only recognition
# let a variable/fragment-assembled command hide inside a backtick pair
# instead (e.g. a backtick-wrapped `$X$Y https://example.invalid`, or a
# backtick-wrapped `$CMD ...` where `CMD` was locally assigned/exported/
# `read` elsewhere) and go completely unrejected -- exactly the same
# "command name assembled/indirected at runtime, so no literal
# substring ever appears" evasion `$(` closes below, just spelled with
# backticks instead of `$(...)`. This module still never treats an
# *ordinary* backtick pair as dangerous by itself: a literal,
# non-assembled backtick command substitution, and -- critically --
# backticks used only as prose/markdown formatting punctuation (this
# very file's own header comments, and this real workflow's own
# top-of-file comments, both use backtick-wrapped words this way) are
# never flagged, because neither ever sits at a recognized command
# position (start of a `run:` line/scalar, right after a `;`/`&&`/
# `||`/`|` separator, or immediately inside an already-opened `$(`/
# backtick) in the first place -- only a variable/fragment-assembled or
# previously-tracked-variable command actually invoked *there* still
# triggers the same narrow rules as everywhere else.
#
# Issue #9 residual hardening (previous round): a fresh, independent
# verifier reproduced a dangerous command executed *inside* `$( ... )`
# -- `echo $($X$Y https://example.invalid)`, `echo $(${X}${Y} ...)`,
# and a direct `echo $($CMD ...)` where `CMD` was locally assigned
# elsewhere -- as unrejected, since the text immediately following `$(`
# is exactly as much "command position" as the start of a `run:` script
# line or the text right after a `;`/`&&`/`||`/`|` separator, yet none
# of those already-recognized command-position starts include it.
# Adding `$(` (and now the backtick) here is the single, minimal change
# that lets the *existing* concatenated-fragment and locally-assigned-
# single-variable checks below cover a command executed inside either
# subshell spelling for free, with no separate detection logic
# duplicated. This never turns an *ordinary*, safe `$(...)` (e.g. a
# literal `$(date)`, or one whose result is merely assigned/
# interpolated as data) into a violation by itself -- only a variable/
# fragment-assembled command actually invoked at that position still
# triggers the same narrow rules as everywhere else.
_COMMAND_SUBSTITUTION_OPEN = r"(?:\$\(|`)"
# The start of a `run:` script line (any line -- real line-continuations
# are already collapsed by `_normalize_for_scanning` before this ever
# runs), the inline start of a `run:` scalar's value on the same text
# line, immediately after a shell command separator (`;`, `&&`, `||`, or
# a pipe `|`), or immediately inside an opened `$( ... )` command
# substitution *or* an opened legacy backtick command substitution.
# Deliberately line/separator/subshell-aware rather than a full parser
# -- see module docstring.
_COMMAND_POSITION_PREFIX = (
    rf"(?:^|{_STATEMENT_SEP}|{_RUN_SCALAR_PREFIX}|{_COMMAND_SUBSTITUTION_OPEN})[ \t]*"
)
# A statement boundary: another separator, or a genuine end-of-line/
# end-of-text -- `\r` and `\n` are both matched directly (rather than
# relying solely on MULTILINE `$`, which sits *before* a bare `\n` and
# would otherwise miss a CRLF file's trailing `\r`).
_STATEMENT_END = rf"(?:{_STATEMENT_SEP}|[\r\n]|$)"
# A command-position token's trailing boundary: ordinary whitespace/
# end-of-line/end-of-text, a closing `)` -- added for issue #9's `$(...)`
# command-substitution coverage above, so a variable invoked directly as
# the *entire* body of a subshell with no trailing argument (`$($CMD)`,
# no space before the closing paren) still has a real boundary to match
# against -- or a closing backtick, for the same reason applied to the
# legacy backtick command-substitution spelling (a backtick-wrapped
# `$CMD` with no trailing argument and no space before the closing
# backtick).
_BOUNDARY_AFTER = r"(?:[ \t\r\n)`]|$)"

_CONCATENATED_VAR_REFS_RE = re.compile(
    rf"{_COMMAND_POSITION_PREFIX}(?:{_VAR_REF}){{2,}}", re.MULTILINE
)
_COMMAND_POSITION_SINGLE_VAR_RE = re.compile(
    rf"{_COMMAND_POSITION_PREFIX}({_VAR_REF})(?={_BOUNDARY_AFTER})", re.MULTILINE
)
# A "pure" local shell-variable assignment statement: exactly
# `NAME=value` (optionally `export NAME=value` -- issue #9 residual
# hardening: a fresh, independent verifier reproduced `export NAME=...`
# followed by a later direct `$NAME`/`${NAME}` command-position
# invocation as unrejected, since the plain `NAME=value` shape below
# never matched the `export` keyword prefix) occupying an entire command
# position by itself (no attached command afterward on the same
# statement -- so the common, legitimate `FOO=bar some-command args`
# inline-env-var-prefix idiom is deliberately *not* matched/recorded
# here, `export` prefix or not). Never tries to resolve/interpret
# `value` itself (no shell parser); merely recording *that* `NAME` was
# locally assigned anything at all is enough to make a later bare
# `$NAME`/`${NAME}` command-position invocation of it suspicious.
_PURE_ASSIGNMENT_RE = re.compile(
    rf"{_COMMAND_POSITION_PREFIX}(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)=[^\s;&|]*[ \t]*(?={_STATEMENT_END})",
    re.MULTILINE,
)
# `read`/`read -r`/`read -r -s ...` (any number of simple single-token
# `-x` flags with no attached argument -- e.g. `-r`, `-s`, `-e`; a real
# shell's `read -p prompt NAME` etc., where a flag itself consumes a
# separate argument token, is out of scope, matching this module's
# narrow, high-confidence design) populating one **or more** shell
# variables from runtime input rather than a literal RHS value --
# issue #9 residual hardening: a fresh, independent verifier reproduced
# `read NAME` followed by a later direct `$NAME`/`${NAME}` command-
# position invocation as unrejected, since `_PURE_ASSIGNMENT_RE` above
# only ever recognizes the `NAME=value` shape, never `read NAME`.
#
# Final-round hardening: a fresh, independent verifier further confirmed
# only the *first* named variable was tracked, so a multi-variable
# `read A B` left `B` (and any further name) completely untracked -- a
# later direct `$B`/`${B}` command-position invocation of it went
# unrejected even though `A` would have been caught. Every
# whitespace-separated identifier-shaped name after `read` and its
# leading flags is now captured in a single group and split out below,
# so `read A B C` tracks `A`, `B`, *and* `C` alike.
_READ_ASSIGNMENT_RE = re.compile(
    rf"{_COMMAND_POSITION_PREFIX}read\b(?:[ \t]+-[A-Za-z]+)*((?:[ \t]+[A-Za-z_][A-Za-z0-9_]*)+)",
    re.MULTILINE,
)
# Splits a `_READ_ASSIGNMENT_RE` match's captured name-list group (e.g.
# `" A B C"`) into its individual identifier-shaped variable names
# (`["A", "B", "C"]`).
_READ_NAME_LIST_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SINGLE_VAR_NAME_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")


def check_variable_command_assembly(text: str) -> List[str]:
    """Rejects (1) two or more shell variable expansions concatenated
    with zero intervening whitespace in command position (`$X$Y`,
    `${X}${Y}`, and any bare/braced mix), including inside a `$( ... )`
    command substitution or a legacy backtick command substitution
    (e.g. `$($X$Y ...)`, `$(${X}${Y} ...)`, or the same shapes wrapped
    in backticks instead) -- a command name assembled at runtime from
    separately-innocuous fragments -- and (2) a single shell variable,
    previously assigned a value elsewhere in the very same script via a
    plain `NAME=value` assignment, an `export NAME=value` assignment, or
    a `read`/`read -r` statement (every variable name `read` populates
    is tracked, not only the first), later invoked directly in command
    position, including directly inside a `$( ... )` *or* backtick
    command substitution (e.g. `CMD=curl` ... `$CMD https://...`, or
    `... $($CMD ...)`, or the backtick-wrapped equivalent). All of these
    are high-confidence, command-position-aware evasions of every
    literal-command-name check in `FORBIDDEN_PATTERNS` above; none of
    them ever fire against ordinary tail-position interpolation (e.g.
    this repository's own real `>> "$GITHUB_STEP_SUMMARY"`), plain data
    interpolation, or an *ordinary*, non-assembled `$(...)`/backtick
    command substitution (e.g. `$(date)`), since none of those ever sit
    at a recognized command position."""
    violations: List[str] = []
    for match in _CONCATENATED_VAR_REFS_RE.finditer(text):
        shown = re.sub(r"^[ \t;&|(`]+", "", match.group(0))
        violations.append(
            "command position invokes a name assembled by concatenating 2+ shell variable "
            f"expansions with no separator (evades literal-command-name detection): {shown!r}"
        )
    assigned_by_value = {match.group(1) for match in _PURE_ASSIGNMENT_RE.finditer(text)}
    assigned_by_read = {
        name
        for match in _READ_ASSIGNMENT_RE.finditer(text)
        for name in _READ_NAME_LIST_RE.findall(match.group(1))
    }
    assigned_names = assigned_by_value | assigned_by_read
    if assigned_names:
        for match in _COMMAND_POSITION_SINGLE_VAR_RE.finditer(text):
            name_match = _SINGLE_VAR_NAME_RE.fullmatch(match.group(1))
            if not name_match:
                continue
            name = name_match.group(1)
            shown = re.sub(r"^[ \t;&|(`]+", "", match.group(0))
            if name in assigned_by_value:
                violations.append(
                    "command position directly invokes shell variable "
                    f"{name!r}, which was locally assigned a literal value earlier "
                    f"in this same script (evades literal-command-name detection): {shown!r}"
                )
            elif name in assigned_by_read:
                violations.append(
                    "command position directly invokes shell variable "
                    f"{name!r}, which was populated by a 'read' statement earlier in this "
                    f"same script (evades literal-command-name detection): {shown!r}"
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
    """`actions/checkout` itself must be present at least once, and every
    checkout step must disable credential persistence. The *pin format*
    for `actions/checkout` (and every other external action) is validated
    generically by `check_uses_pins` below -- this function is
    deliberately narrow now (checkout-specific presence/credential
    hygiene only), so there is exactly one place (`check_uses_pins`) that
    knows what an acceptable action pin looks like. Uses the same
    canonical `extract_uses_occurrences` scanner as every other `uses:`
    check in this module (see that function's own design-rationale
    comment) -- a checkout step hidden inside a flow mapping or behind a
    quoted key is found exactly the same way a plain block-style one
    is."""
    violations = []
    found_checkout = any(
        occ.problem is None and occ.action_ref.lower().startswith("actions/checkout@")
        for occ in extract_uses_occurrences(text)
    )
    if not found_checkout:
        violations.append("no 'actions/checkout' step found")
    if "persist-credentials: false" not in text:
        violations.append("no checkout step sets 'persist-credentials: false'")
    return violations


# `owner/repo[/subpath]@ref`: captures the action reference up to (but
# excluding) the final `@ref` segment, and the ref itself, in one shot --
# reused by both `check_uses_pins` (pin-format enforcement) and
# `scripts/release_rehearsal/action_pins.py` (the separate committed
# inventory cross-check), so there is exactly one definition of "what an
# external `uses:` action reference looks like".
_USES_REF_SPLIT_RE = re.compile(r"^(?P<action>[^@\s]+)@(?P<ref>[^\s]+)$")


def is_local_action_reference(action_ref: str) -> bool:
    """The single, explicit, narrow "safe local action" rule (issue #9
    mandatory correction #1): a reference to an action *inside this same
    repository* (`./path/to/action` or `../path/to/action`) is implicitly
    pinned to the exact same immutable commit as the workflow file that
    references it -- there is no separate external SHA to pin, and no
    separate upstream source to independently validate. Nothing else is
    ever exempted: any `owner/repo[/subpath]@ref` reference (a real
    external action, on GitHub or any other host) and a Docker
    `docker://...` reference (never used by this repository's real
    workflow, so deliberately not carved out at all -- see module
    docstring's fail-closed design) are always treated as external and
    must be pinned to an exact 40-lowercase-hex commit SHA."""
    return action_ref.startswith("./") or action_ref.startswith("../")


def check_uses_pins(text: str) -> List[str]:
    """Every external `uses:` reference (i.e. every reference that is not
    a local action -- see `is_local_action_reference`) must be pinned to
    an exact, immutable, 40-lowercase-hex commit SHA. A mutable version
    tag (`v7`, `v7.0.1`, `main`, any other branch name), a short SHA, a
    malformed reference, or a wrong-case (uppercase/mixed-case) SHA are
    all rejected alike -- there is no accepted-tag allowlist any more.
    A reference with no `@ref` segment at all (an entirely unpinned
    `owner/repo` -- implicitly whatever the default branch currently
    is) is exactly as rejected as a mutable tag.

    Every occurrence `extract_uses_occurrences` finds is visited here --
    block style, flow style, quoted or bare keys, all alike -- and any
    occurrence that scanner could not fully, unambiguously parse (an
    anchor/alias/tag, a template expression, an unterminated quote, an
    ambiguous embedded colon, or a duplicate key within the same
    mapping) is *always* reported as a hard violation, regardless of
    whatever text happens to follow: this module never guesses a
    meaning for a construct it does not fully understand, and never
    lets an unrecognized `uses:` shape silently pass through
    unchecked."""
    violations = []
    for occ in extract_uses_occurrences(text):
        if occ.problem is not None:
            description = _PROBLEM_DESCRIPTIONS.get(occ.problem, occ.problem)
            violations.append(
                f"line {occ.line}: 'uses:' value {occ.raw_value!r} is not a recognized/supported "
                f"static action reference ({description}) -- rejected fail-closed"
            )
            continue
        action_ref = occ.action_ref
        if is_local_action_reference(action_ref):
            continue
        split = _USES_REF_SPLIT_RE.match(action_ref)
        if split is None:
            violations.append(
                f"line {occ.line}: 'uses: {action_ref}' has no '@ref' pin at all -- every external "
                "action must be pinned to an exact 40-lowercase-hex commit SHA"
            )
            continue
        ref = split.group("ref")
        if not FULL_SHA_RE.fullmatch(ref):
            violations.append(
                f"line {occ.line}: 'uses: {action_ref}' is not pinned to an immutable "
                f"40-lowercase-hex commit SHA (found {ref!r} -- a version tag, branch name, short "
                "SHA, or wrong-case SHA is never accepted; see docs/release_data/action_pins.json "
                "for the exact pinned SHA and its documented upstream source/version)"
            )
    return violations


def check_forbidden_patterns(text: str) -> List[str]:
    violations = []
    for pattern, label in _COMPILED_FORBIDDEN_PATTERNS:
        match = pattern.search(text)
        if match:
            violations.append(f"forbidden pattern found ({label}): {match.group(0)!r}")
    return violations


# issue #9 verifier remediation: the normal release workflow's
# publication-eligibility steps (`make release-check`/`make release-
# rehearse`, and their `-require-eligible`/`-expect-blocked` siblings --
# see release.mk) must bind the exact, immutable checked-out commit
# (`${{ github.sha }}`) as this candidate's target SHA -- never silently
# leave it to whatever `git rev-parse HEAD` happens to resolve to inside
# the runner (correct in practice, but not itself an auditable, explicit
# binding a reviewer can see without also trusting the checkout step's
# own exact behavior). release.mk's own `RELEASE_TARGET_SHA ?= $(shell
# git rev-parse HEAD)` accepts an environment-variable override with
# exactly this name, so a single job-level (or step-level) `env:`
# mapping is sufficient -- never required on every individual `run:`
# line.
RELEASE_ELIGIBILITY_TARGET_RE = re.compile(r"\bmake\s+release-(check|rehearse)(-require-eligible|-expect-blocked)?\b")
GITHUB_SHA_BINDING_RE = re.compile(r"RELEASE_TARGET_SHA\s*:\s*\$\{\{\s*github\.sha\s*\}\}")


def check_release_target_sha_binding(text: str) -> List[str]:
    """Fails closed if this workflow ever invokes a release publication-
    eligibility target (`make release-check`/`make release-rehearse` or
    a `-require-eligible`/`-expect-blocked` sibling) without also
    declaring an explicit `RELEASE_TARGET_SHA: ${{ github.sha }}` `env:`
    binding somewhere in the same file -- this is what makes "bound to
    the exact checked-out commit" an auditable fact in the workflow
    file itself, not merely an assumption about `git rev-parse HEAD`'s
    behavior inside the runner.

    Deliberately NOT folded into `validate_workflow_text()`'s shared
    aggregator (called directly by `cli.py`'s `cmd_workflow_guard`
    instead, alongside `validate_workflow_text()`) -- that aggregator is
    reused by ~170 other unit tests exercising small, isolated workflow-
    text snippets for unrelated checks (permissions, pins, forbidden
    patterns, variable-assembly) that were never meant to also carry a
    full `RELEASE_TARGET_SHA` binding; keeping this issue-#9-specific
    check separate avoids a false-positive blast radius across every
    one of those unrelated fixtures."""
    invokes_eligibility_target = bool(RELEASE_ELIGIBILITY_TARGET_RE.search(text))
    if not invokes_eligibility_target:
        return []
    if not GITHUB_SHA_BINDING_RE.search(text):
        return [
            "invokes a release publication-eligibility target (make release-check/"
            "release-rehearse or a -require-eligible/-expect-blocked sibling) without an "
            "explicit 'RELEASE_TARGET_SHA: ${{ github.sha }}' env binding anywhere in this "
            "workflow -- the exact checked-out commit must be bound explicitly, never left "
            "implicit"
        ]
    return []


def check_dangerous_uses_actions(text: str) -> List[str]:
    """Generalized, case-insensitive `uses:` action-name heuristic: any
    referenced action whose name contains "upload", "release", "publish",
    or "deploy" is rejected, regardless of exact action identity/case --
    this deliberately catches a disguised/unlisted-but-clearly-named
    action (e.g. a fork, a differently-cased reference, or an action this
    module's authors have never heard of) instead of only matching a
    fixed enumeration that must be kept manually up to date forever.
    Scans every occurrence `extract_uses_occurrences` finds (block,
    flow, quoted, or bare key alike), not only a bare block-style
    `uses:` at column 0."""
    violations = []
    for occ in extract_uses_occurrences(text):
        action_ref = occ.action_ref
        if not action_ref:
            continue
        lowered = action_ref.lower()
        for needle in _DANGEROUS_ACTION_NAME_SUBSTRINGS:
            if needle in lowered:
                violations.append(
                    f"line {occ.line}: 'uses:' references a dangerous-sounding action: "
                    f"{action_ref!r} (contains {needle!r})"
                )
                break
    return violations


def validate_workflow_text(text: str) -> List[str]:
    normalized = _normalize_for_scanning(text)
    violations: List[str] = []
    violations.extend(check_triggers(normalized))
    violations.extend(check_top_level_permissions(normalized))
    violations.extend(check_no_write_anywhere(normalized))
    violations.extend(check_checkout_pin(normalized))
    violations.extend(check_uses_pins(normalized))
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
