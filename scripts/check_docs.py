#!/usr/bin/env python3
"""Deterministic, stdlib-only Markdown documentation governance checker.

Single authoritative entry point for Issues #7/#17's documentation
governance closure. Verifies, over every tracked (and, in a dev worktree,
untracked-but-not-ignored) Markdown file in this repository:

  1. Internal relative links/images resolve to a real in-repo path, and
     ``file.md#anchor`` anchors resolve against a deterministic,
     GitHub-heading-slug-compatible stdlib algorithm (fenced code blocks
     are ignored so pseudo-links inside code samples are never checked).
     This covers both inline (``[text](target)``) and reference-style
     links/images (``[label]: target`` definitions plus ``[text][label]``,
     ``![alt][label]``, and collapsed ``[text][]`` usages): undefined
     labels and broken definition targets are hard findings, never
     silently skipped. Bare shortcut references (``[label]`` with no
     second bracket pair) are not resolved, but any occurrence whose text
     matches an actually-defined label is still reported as an explicit
     "unsupported" finding rather than passing silently.
  2. ``docs/documentation-inventory.md`` is a byte-exact, one-line-per-file
     registry of every Markdown path in the repo, each with an owner, a
     controlled status/category, and a short scope -- no drift allowed in
     either direction (missing or extra entries both fail).
  3. Every external (``http``/``https``) URL occurrence in every Markdown
     file -- including inside inline code spans, but not fenced code
     blocks -- is covered by a host/prefix rule in
     ``docs/external-link-registry.md`` with a controlled status. No
     network access is ever performed; this is registry/syntax coverage
     only.
  4. A small, explicit denylist of previously-real, now-stale phrasing
     (e.g. the pre-rewrite claim that the decomp tutorial lives in
     ``CONTRIBUTING.md``) does not reappear, and every ``make TARGET``
     invocation found in fenced/inline code across all Markdown resolves
     against a *statically parsed* (never executed) Makefile target
     database, so a renamed/removed target fails fast.

Exit codes: 0 clean, 1 findings, 2 invocation/environment error.

This script performs no network access and never executes a Makefile
recipe (targets are discovered by parsing ``Makefile``/its ``include``
graph as text, not by invoking ``make``). ``--check-examples`` additionally
spawns a small, hardcoded allowlist of zero-ROM/zero-network/zero-mutation
example commands (``--help`` invocations and this script's own
``--help``) to prove they still work; it never executes an arbitrary
command discovered in a doc file.
"""
import argparse
import os
import re
import subprocess
import sys
import urllib.parse
from collections import namedtuple

# ---------------------------------------------------------------------------
# Repository-relative constants
# ---------------------------------------------------------------------------

INVENTORY_PATH = "docs/documentation-inventory.md"
REGISTRY_PATH = "docs/external-link-registry.md"

INVENTORY_BEGIN = "<!-- DOCS-INVENTORY:BEGIN -->"
INVENTORY_END = "<!-- DOCS-INVENTORY:END -->"
REGISTRY_BEGIN = "<!-- EXTERNAL-LINK-REGISTRY:BEGIN -->"
REGISTRY_END = "<!-- EXTERNAL-LINK-REGISTRY:END -->"

# Controlled status/category enum for docs/documentation-inventory.md entries.
INVENTORY_STATUSES = {
    "current",            # authoritative, actively maintained, expected to match master
    "historical",         # archival / point-in-time; not re-verified against master
    "generated",          # machine-generated report/inventory; never hand-edit content
    "subsystem-reference", # deep reference scoped to one subsystem/tool
    "deprecated",         # superseded; kept only for compatibility/history
    "evidence",           # issue/closure candidate evidence report; not a closure claim
    "template",           # intentionally unfilled scaffolding
}

# Controlled status enum for docs/external-link-registry.md rules.
EXTERNAL_STATUSES = {
    "authoritative-self",     # this repository's own GitHub project surface
    "historical-upstream",    # the upstream fireemblem8u decomp project (wiki/tracker/etc)
    "downstream-reference",   # projects/sites that consume this repo, for credits/context
    "third-party-reference",  # external tools/docs/services this project merely links to
}

MATCH_TYPE_HOST = "host:"
MATCH_TYPE_PREFIX = "prefix:"

# Known-stale phrasing that must never reappear once fixed. Each entry is
# (compiled regex, human message). Intentionally a small, explicit denylist
# -- not a general prose-quality linter.
STALE_PHRASE_RULES = [
    (
        re.compile(r"decomp tutorial in `CONTRIBUTING\.md`"),
        "stale pointer: the decomp tutorial now lives in docs/archival-decomp.md, "
        "not CONTRIBUTING.md (CONTRIBUTING.md's own decomp section links there)",
    ),
    (
        re.compile(r"CONTRIBUTING\.md[^.\n]{0,40}walks a full function end-to-end"),
        "stale pointer: the full-function decomp walkthrough now lives in "
        "docs/archival-decomp.md, not CONTRIBUTING.md",
    ),
    (
        re.compile(r"installs agbcc \+ builds the `tools/`"),
        "stale claim: scripts/quickstart.sh installs the modern toolchain "
        "(no agbcc) by default; agbcc is only installed with --legacy/--refresh-agbcc",
    ),
    # Issue #17 verifier finding: docs/quickstart.md hardcoded modern-object
    # counts (18/21/363/435/438) that drifted out of sync with modern.mk's
    # actual MODERN_COHORT_*/MODERN_ALL_* variables. The fix replaced every
    # such count with a qualitative description plus a `make print-<VAR>`
    # reproduction command; these phrases must never reappear verbatim.
    (
        re.compile(r"twenty-one `\.o` and twenty-one `\.d` files"),
        "stale claim: hardcoded cohort object/dep count -- describe "
        "qualitatively and point at `make print-MODERN_COHORT_C_OBJECTS`/"
        "`print-MODERN_COHORT_ASM_OBJECTS`/`print-MODERN_COHORT_OBJECTS` instead",
    ),
    (
        re.compile(r"all 435 authoritative C files"),
        "stale claim: hardcoded full-source C file count -- describe "
        "qualitatively and point at `make print-MODERN_ALL_C_OBJECTS`/"
        "`print-MODERN_ALL_DATA_OBJECTS` instead",
    ),
    (
        re.compile(r"363 normal `src/\*\.c`"),
        "stale claim: hardcoded normal-C-source count -- describe "
        "qualitatively and point at `make print-MODERN_ALL_C_OBJECTS` instead",
    ),
    (
        re.compile(r"\b18-file cohort\b"),
        "stale claim: hardcoded cohort file count -- describe qualitatively "
        "and point at `make print-MODERN_COHORT_C_OBJECTS` instead",
    ),
    (
        re.compile(r"363-file full C list"),
        "stale claim: hardcoded full C source list count -- describe "
        "qualitatively and point at `make print-MODERN_ALL_C_OBJECTS` instead",
    ),
    (
        re.compile(r"438 `\.o` and 438 primary `\.d` files"),
        "stale claim: hardcoded full-source object/dep count -- describe "
        "qualitatively and point at `make print-MODERN_ALL_OBJECTS` instead",
    ),
    (
        re.compile(r"all 438 modern objects"),
        "stale claim: hardcoded modern-ELF object count -- describe "
        "qualitatively and point at `make print-MODERN_ALL_OBJECTS` instead",
    ),
    # Acceptance-review finding (issues #7/#17 docs contract fixup):
    # docs/framework-support.md hardcoded MODERN_COHORT_OBJECTS/
    # MODERN_ALL_OBJECTS counts (21 C + 3 asm = 24; 450) that, unlike
    # quickstart.md's already-fixed wording above, still risked drifting
    # out of sync with modern.mk. Replaced with the same
    # `make print-<VAR>`-only pattern used for the phrases above; these
    # exact phrases must never reappear verbatim.
    (
        re.compile(re.escape(
            "21 `src/*.c` objects + 3 handwritten-assembly objects, 24 total"
        )),
        "stale claim: hardcoded cohort object count (21 C + 3 asm = 24 total) -- "
        "describe qualitatively and point at `make print-MODERN_COHORT_C_OBJECTS`/"
        "`print-MODERN_COHORT_ASM_OBJECTS`/`print-MODERN_COHORT_OBJECTS` instead",
    ),
    (
        re.compile(re.escape("handwritten asm: 450 objects as of this audit")),
        "stale claim: hardcoded full-source object count (450) -- describe "
        "qualitatively and point at `make print-MODERN_ALL_C_OBJECTS`/"
        "`print-MODERN_ALL_DATA_OBJECTS`/`print-MODERN_ALL_ASM_OBJECTS`/"
        "`print-MODERN_ALL_OBJECTS` instead",
    ),
    # Acceptance-review finding: docs/framework-support.md's
    # expansion-modern-elf row previously listed `MODERN_ABI=<aapcs|apcs-gnu>`
    # as if both ABIs were valid for a *linked* target. modern.mk's
    # MODERN_LINKED_GOALS guard fails fast on anything but aapcs for every
    # linked/ROM/runtime-gate target (expansion-modern-elf/-rom/
    # -boot-check/-linker-check/...); apcs-gnu is compile-only
    # (expansion-modern-cohort/-all layout comparison). This exact
    # ambiguous phrasing must never reappear.
    (
        re.compile(re.escape(
            r"expansion-modern-elf MODERN_CONFIG=<debug\|release> MODERN_ABI=<aapcs\|apcs-gnu>"
        )),
        "stale/incorrect claim: expansion-modern-elf (and every other linked modern "
        "output) does not accept MODERN_ABI=apcs-gnu -- modern.mk's linked-goal guard "
        "requires MODERN_ABI=aapcs and fails fast otherwise; apcs-gnu is compile-only "
        "(expansion-modern-cohort/-all layout comparison only)",
    ),
]

FENCE_RE = re.compile(r"^(```+|~~~+)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
LINK_RE = re.compile(r'!?\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
INLINE_CODE_RE = re.compile(r"(?<!`)`([^`]+)`(?!`)")
URL_RE = re.compile(r"https?://[^\s)>\]\"'`]+")
MAKE_CMD_RE = re.compile(r"^\s*make(?=[\s;&|#]|$)([^\n;&|#]*)")

# Reference-style link/image support (CommonMark "reference link" family):
#
#   [label]: /url "title"        <- definition line (anywhere in the doc)
#   [text][label]                 <- full reference (link)
#   ![alt][label]                 <- full reference (image)
#   [text][]                      <- collapsed reference (label := text)
#
# are fully parsed and resolved the same way an inline ``[text](target)``
# link is: undefined labels, and internal-path/anchor-broken definition
# targets, are hard findings (never silently 0-findings). External
# (``http``/``https``) definition targets are covered for free by
# ``check_external_urls`` -- the raw URL text on the definition line is
# already scanned by ``extract_external_urls`` regardless of the
# surrounding link syntax.
#
# Shortcut references (``[label]`` with no second bracket pair at all) are
# intentionally NOT resolved -- disambiguating a bare ``[word]`` occurrence
# in prose from an actual shortcut-reference-link use would require much
# more Markdown-inline-parsing machinery than this stdlib-only checker
# implements. Per this checker's fail-closed policy, any such occurrence
# whose bracketed text matches an *actually-defined* label in the same
# document is reported as an explicit "unsupported" finding rather than
# being silently skipped -- see ``check_reference_style_links`` below.
REF_DEF_LINE_RE = re.compile(r'^[ ]{0,3}\[([^\]\n]+)\]:\s*(.*)$')
REF_USE_RE = re.compile(r'!?\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\[([^\]]*)\]')
SHORTCUT_BRACKET_RE = re.compile(r'!?\[([^\[\]]+)\]')

Finding = namedtuple("Finding", "file line message")


class DocsCheckError(Exception):
    pass


# ---------------------------------------------------------------------------
# Repository / Git plumbing
# ---------------------------------------------------------------------------

def get_repo_root(start=None):
    start = start or os.getcwd()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start, capture_output=True, check=True, text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise DocsCheckError("not inside a Git repository: %s" % exc)
    return out.stdout.strip()


def discover_markdown_files(root):
    """Tracked + untracked-but-not-ignored Markdown paths, repo-relative.

    In CI (a fresh checkout of a commit) everything present is tracked, so
    this is exactly the tracked set. In a dev worktree it also picks up
    new, not-yet-committed Markdown files, without picking up anything
    .gitignore excludes (build/, tool submodule content, etc.).
    """
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md"],
        cwd=root, capture_output=True, check=True,
    )
    names = [n for n in out.stdout.decode("utf-8").split("\0") if n]
    return sorted(set(names))


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Markdown structure helpers (stdlib only -- no third-party parser)
# ---------------------------------------------------------------------------

def strip_fenced_blocks(text):
    """Blank out the contents (and fence lines) of fenced code blocks.

    Preserves line count/line numbers. Only triple-or-more backtick/tilde
    fences are recognized (GitHub-flavored); indented-only code blocks are
    intentionally not treated as fences (this repo does not use them for
    link-bearing prose).
    """
    lines = text.split("\n")
    out = []
    in_fence = False
    fence_char = None
    fence_len = 0
    for line in lines:
        stripped = line.strip()
        m = FENCE_RE.match(stripped)
        if not in_fence and m:
            in_fence = True
            fence_char = m.group(1)[0]
            fence_len = len(m.group(1))
            out.append("")
            continue
        if in_fence:
            closing = re.match(r"^(" + re.escape(fence_char) + r"{%d,})\s*$" % fence_len, stripped)
            if closing:
                in_fence = False
            out.append("")
            continue
        out.append(line)
    return "\n".join(out)


def iter_fenced_block_bodies(text):
    """Yield the raw text content of every fenced code block (for command
    extraction only -- never for link/URL scanning)."""
    lines = text.split("\n")
    in_fence = False
    fence_char = None
    fence_len = 0
    body = []
    for line in lines:
        stripped = line.strip()
        m = FENCE_RE.match(stripped)
        if not in_fence and m:
            in_fence = True
            fence_char = m.group(1)[0]
            fence_len = len(m.group(1))
            body = []
            continue
        if in_fence:
            closing = re.match(r"^(" + re.escape(fence_char) + r"{%d,})\s*$" % fence_len, stripped)
            if closing:
                in_fence = False
                yield "\n".join(body)
            else:
                body.append(line)
            continue
    # Unterminated fence (shouldn't happen; balance is a lint concern, not
    # this function's job) -- yield whatever was collected.
    if in_fence and body:
        yield "\n".join(body)


def github_heading_slug(text):
    """Deterministic approximation of GitHub's heading-anchor slug rule.

    Strips markdown link syntax down to link text, strips inline code
    backticks and emphasis markers, lowercases, drops every character that
    is not a Unicode word character, whitespace, or ASCII hyphen, then
    replaces each individual whitespace character with a single hyphen
    (runs of whitespace are NOT collapsed -- this matches GitHub's actual
    behavior for e.g. em-dash-separated headings, which produce a double
    hyphen).
    """
    t = text.strip()
    t = re.sub(r"#+\s*$", "", t).strip()
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = t.replace("`", "")
    t = re.sub(r"[*_]{1,3}", "", t)
    t = t.lower()
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    t = t.replace(" ", "-")
    return t


def compute_heading_slugs(stripped_text):
    """Return the ordered list of anchor slugs for every heading in a
    fence-stripped document, applying GitHub's duplicate-heading suffix
    rule (-1, -2, ... in order of appearance)."""
    seen = {}
    slugs = []
    for line in stripped_text.split("\n"):
        m = HEADING_RE.match(line)
        if not m:
            continue
        base = github_heading_slug(m.group(2))
        if base in seen:
            seen[base] += 1
            slugs.append("%s-%d" % (base, seen[base]))
        else:
            seen[base] = 0
            slugs.append(base)
    return slugs


def extract_internal_link_targets(stripped_text):
    """Yield (line_no, target) for every markdown link/image target in a
    fence-stripped document (1-indexed line numbers)."""
    for lineno, line in enumerate(stripped_text.split("\n"), start=1):
        for target in LINK_RE.findall(line):
            yield lineno, target


def extract_external_urls(stripped_text):
    """Yield (line_no, url) for every bare or wrapped external URL
    occurrence in a fence-stripped document (fenced code already blanked;
    inline single-backtick code spans are intentionally still scanned)."""
    for lineno, line in enumerate(stripped_text.split("\n"), start=1):
        for m in URL_RE.finditer(line):
            url = m.group(0)
            while url and url[-1] in ").,;:'\">]":
                url = url[:-1]
            if url:
                yield lineno, url


# ---------------------------------------------------------------------------
# Internal link resolution
# ---------------------------------------------------------------------------

def _is_external(target):
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", target)) or target.startswith("mailto:")


def resolve_internal_link(root, source_rel_path, target, heading_slug_cache):
    """Resolve one non-external link target found in ``source_rel_path``.

    Returns (ok: bool, message: str-or-None). ``heading_slug_cache`` maps a
    repo-relative Markdown path to its ordered slug list (lazily filled in
    by the caller) so cross-file anchor checks don't re-parse a file for
    every incoming link.
    """
    if target.startswith("#"):
        path_part, anchor = "", target[1:]
        target_path = source_rel_path
    else:
        if "#" in target:
            path_part, anchor = target.split("#", 1)
        else:
            path_part, anchor = target, None
        path_part = urllib.parse.unquote(path_part)
        source_dir = os.path.dirname(source_rel_path)
        target_path = os.path.normpath(os.path.join(source_dir, path_part))

    # Path-escape guard: never allow a resolved link to leave the repo root.
    abs_root = os.path.abspath(root)
    abs_target = os.path.abspath(os.path.join(root, target_path))
    if os.path.commonpath([abs_root, abs_target]) != abs_root:
        return False, "link target escapes the repository root: %s" % target

    if not os.path.exists(abs_target):
        return False, "internal link target does not exist: %s" % target

    if anchor and target_path.endswith(".md"):
        if target_path not in heading_slug_cache:
            heading_slug_cache[target_path] = compute_heading_slugs(
                strip_fenced_blocks(read_text(abs_target))
            )
        if anchor not in heading_slug_cache[target_path]:
            return False, "anchor #%s not found in %s (no matching heading slug)" % (anchor, target_path)

    return True, None


# ---------------------------------------------------------------------------
# Reference-style link/image support
# ---------------------------------------------------------------------------

def normalize_reference_label(label):
    """CommonMark reference-label normalization: strip, collapse internal
    whitespace runs to a single space, and case-fold for comparison."""
    return re.sub(r"\s+", " ", label.strip()).casefold()


def parse_reference_definition_destination(rest):
    """Parse the part of a ``[label]: <rest>`` definition line after the
    colon. Returns ``(target_or_None, error_or_None)``. ``target`` is
    ``None`` only when no destination could be found at all; a malformed
    *title* still returns the (valid) destination alongside an error
    message, since the destination is the only part actually resolved."""
    s = rest.strip()
    if not s:
        return None, "missing destination"
    if s[0] == "<":
        end = s.find(">")
        if end == -1:
            return None, "unterminated <destination>"
        target = s[1:end]
        remainder = s[end + 1:].strip()
    else:
        m = re.match(r"^(\S+)(.*)$", s)
        target = m.group(1)
        remainder = m.group(2).strip()
    if remainder:
        first, last = remainder[0], remainder[-1]
        pair_ok = (
            len(remainder) >= 2
            and ((first == '"' and last == '"') or (first == "'" and last == "'")
                 or (first == "(" and last == ")"))
        )
        if not pair_ok:
            return target, "unexpected trailing content after destination: %r" % remainder
    return target, None


def blank_inline_code_spans(line):
    """Blank the contents of single-backtick inline code spans on one
    line (length-preserving), so reference-style link/definition
    scanning never mistakes code-only bracket syntax (e.g. a shell regex
    character class like ``[0-9A-Fa-f]`` inside a `` `grep -E '...'` ``
    inline code span) for real Markdown link syntax. This mirrors every
    real Markdown renderer's own precedence rule: a code span's contents
    are never re-parsed as link/emphasis syntax. (External-URL scanning
    deliberately still looks inside inline code -- a bare URL written in
    code font is still a real, checkable URL -- so this helper is used
    only for reference-style link/definition scanning, not URL scanning.)
    """
    return INLINE_CODE_RE.sub(lambda m: "`" + (" " * len(m.group(1))) + "`", line)


def extract_reference_definitions(lines):
    """Scan every line of a fence-stripped document for reference-style
    link definitions (``[label]: target "title"``).

    Returns ``(definitions, issues, def_line_numbers)`` where:
      - ``definitions`` maps a normalized label to
        ``(target, line_no, raw_label)`` for its *first* definition
        (CommonMark: the first definition of a duplicated label wins, but
        the duplicate itself is still a reported issue here -- this
        checker treats it as a findable authoring mistake, not silent
        shadowing).
      - ``issues`` is a list of ``(line_no, message)`` for malformed or
        duplicate definitions.
      - ``def_line_numbers`` is the set of 1-indexed line numbers that
        are themselves definition lines (so usage/shortcut scanning can
        skip a definition's own ``[label]:`` bracket).
    """
    definitions = {}
    issues = []
    def_line_numbers = set()
    for lineno, line in enumerate(lines, start=1):
        m = REF_DEF_LINE_RE.match(line)
        if not m:
            continue
        def_line_numbers.add(lineno)
        raw_label, rest = m.group(1), m.group(2)
        target, error = parse_reference_definition_destination(rest)
        if target is None:
            issues.append((
                lineno,
                "malformed reference-style link definition for label '%s': %s" % (raw_label, error),
            ))
            continue
        if error:
            issues.append((
                lineno,
                "malformed reference-style link definition title for label '%s': %s" % (raw_label, error),
            ))
        norm = normalize_reference_label(raw_label)
        if norm in definitions:
            issues.append((
                lineno,
                "duplicate reference-style link definition for label '%s' (first defined at line %d)"
                % (raw_label, definitions[norm][1]),
            ))
            continue
        definitions[norm] = (target, lineno, raw_label)
    return definitions, issues, def_line_numbers


def check_reference_style_links(markdown_files, root):
    """Fail-closed check for the entire reference-style link/image family
    (see the module-level comment above ``REF_DEF_LINE_RE``):

      - malformed/duplicate ``[label]: target`` definitions,
      - undefined labels used via ``[text][label]``/``![alt][label]``/
        ``[text][]``,
      - a defined label's own definition target being an internal path/
        anchor that does not resolve (external targets are covered for
        free by ``check_external_urls``, since the raw URL text on the
        definition line is scanned regardless of link syntax),
      - a bracketed occurrence that is ambiguous with a shortcut
        reference (``[label]`` alone, no second bracket pair) but whose
        text matches an *actually-defined* label in the same document --
        reported as an explicit "unsupported, verify manually" finding
        rather than silently passing.
    """
    findings = []
    heading_slug_cache = {}
    for path in markdown_files:
        text = read_text(os.path.join(root, path))
        stripped = strip_fenced_blocks(text)
        lines = stripped.split("\n")

        scan_lines = [blank_inline_code_spans(line) for line in lines]

        definitions, def_issues, def_line_numbers = extract_reference_definitions(scan_lines)
        for lineno, message in def_issues:
            findings.append(Finding(path, lineno, message))

        for target, lineno, raw_label in definitions.values():
            if _is_external(target):
                continue
            ok, message = resolve_internal_link(root, path, target, heading_slug_cache)
            if not ok:
                findings.append(Finding(
                    path, lineno,
                    "reference-style link definition '%s' target broken: %s" % (raw_label, message),
                ))

        consumed_spans = {}
        for lineno, line in enumerate(scan_lines, start=1):
            if lineno in def_line_numbers:
                continue
            for m in REF_USE_RE.finditer(line):
                consumed_spans.setdefault(lineno, []).append(m.span())
                text_part, label_part = m.group(1), m.group(2)
                label = label_part if label_part.strip() else text_part
                if not label.strip():
                    findings.append(Finding(
                        path, lineno,
                        "malformed reference-style link/image: empty label and empty link text",
                    ))
                    continue
                norm = normalize_reference_label(label)
                if norm not in definitions:
                    findings.append(Finding(
                        path, lineno,
                        "undefined reference-style link label '%s' (used as [%s][%s])"
                        % (label.strip(), text_part, label_part),
                    ))
                    continue
                target, _def_lineno, raw_label = definitions[norm]
                if _is_external(target):
                    continue
                ok, message = resolve_internal_link(root, path, target, heading_slug_cache)
                if not ok:
                    findings.append(Finding(
                        path, lineno,
                        "reference-style link label '%s' resolves to broken target: %s"
                        % (label.strip(), message),
                    ))

        for lineno, line in enumerate(scan_lines, start=1):
            if lineno in def_line_numbers:
                continue
            existing_spans = consumed_spans.get(lineno, [])
            for m in SHORTCUT_BRACKET_RE.finditer(line):
                s, e = m.span()
                if any(s < ce and e > cs for cs, ce in existing_spans):
                    continue  # already handled as a full/collapsed reference above
                if e < len(line) and line[e] == "(":
                    continue  # inline [text](url) link, handled by check_internal_links
                candidate_text = m.group(1)
                if candidate_text.startswith("^"):
                    continue  # footnote-style reference, not a link label
                if candidate_text.strip().lower() in ("", "x"):
                    continue  # GFM task-list checkbox: "[ ]"/"[x]"/"[X]"
                norm = normalize_reference_label(candidate_text)
                if norm in definitions:
                    findings.append(Finding(
                        path, lineno,
                        "unsupported: possible shortcut reference-style link '[%s]' matches "
                        "a defined label in this document, but this checker does not resolve "
                        "shortcut references ([label] with no second bracket pair) -- convert "
                        "to an explicit [text](target) or [text][label] form, or confirm this "
                        "is plain text, not a link" % candidate_text,
                    ))
    return findings


# ---------------------------------------------------------------------------
# docs/documentation-inventory.md parsing
# ---------------------------------------------------------------------------

InventoryEntry = namedtuple("InventoryEntry", "path owner status scope line")


def _extract_delimited_block(text, begin_marker, end_marker):
    if begin_marker not in text:
        raise DocsCheckError("missing %r marker" % begin_marker)
    if end_marker not in text:
        raise DocsCheckError("missing %r marker" % end_marker)
    start = text.index(begin_marker) + len(begin_marker)
    end = text.index(end_marker, start)
    if end < start:
        raise DocsCheckError("%r appears before %r" % (end_marker, begin_marker))
    # Preserve absolute line numbers of the sliced region for diagnostics.
    prefix_lines = text[:start].count("\n")
    return text[start:end], prefix_lines


def parse_inventory(root):
    """Parse docs/documentation-inventory.md.

    Returns (entries: dict[path -> InventoryEntry], errors: list[str]).
    """
    inv_path = os.path.join(root, INVENTORY_PATH)
    errors = []
    entries = {}
    if not os.path.isfile(inv_path):
        return entries, ["%s does not exist" % INVENTORY_PATH]
    text = read_text(inv_path)
    try:
        block, prefix_lines = _extract_delimited_block(text, INVENTORY_BEGIN, INVENTORY_END)
    except DocsCheckError as exc:
        return entries, [str(exc)]
    for offset, raw_line in enumerate(block.split("\n")):
        line_no = prefix_lines + offset + 1
        line = raw_line.strip()
        if not line or not line.startswith("-"):
            continue
        body = line[1:].strip()
        fields = [f.strip() for f in body.split("|")]
        if len(fields) != 4:
            errors.append("%s:%d: expected 4 `|`-delimited fields (path | owner | status | scope), got %d"
                           % (INVENTORY_PATH, line_no, len(fields)))
            continue
        path, owner, status, scope = fields
        if not path:
            errors.append("%s:%d: empty path field" % (INVENTORY_PATH, line_no))
            continue
        if path in entries:
            errors.append("%s:%d: duplicate inventory entry for %s (first seen line %d)"
                           % (INVENTORY_PATH, line_no, path, entries[path].line))
            continue
        if not owner:
            errors.append("%s:%d: %s has an empty owner field" % (INVENTORY_PATH, line_no, path))
        if status not in INVENTORY_STATUSES:
            errors.append("%s:%d: %s has invalid status %r (must be one of: %s)"
                           % (INVENTORY_PATH, line_no, path, status, ", ".join(sorted(INVENTORY_STATUSES))))
        if not scope:
            errors.append("%s:%d: %s has an empty scope field" % (INVENTORY_PATH, line_no, path))
        entries[path] = InventoryEntry(path, owner, status, scope, line_no)
    return entries, errors


def check_inventory_coverage(root, markdown_files, entries):
    findings = []
    doc_set = set(markdown_files)
    inv_set = set(entries)
    for missing in sorted(doc_set - inv_set):
        findings.append(Finding(INVENTORY_PATH, 0, "missing inventory entry for tracked Markdown file: %s" % missing))
    for extra in sorted(inv_set - doc_set):
        findings.append(Finding(INVENTORY_PATH, entries[extra].line,
                                 "inventory entry references a Markdown file that does not exist/is not tracked: %s" % extra))
    return findings


# ---------------------------------------------------------------------------
# docs/external-link-registry.md parsing
# ---------------------------------------------------------------------------

RegistryRule = namedtuple("RegistryRule", "match_type pattern owner status notes line")


def parse_registry(root):
    reg_path = os.path.join(root, REGISTRY_PATH)
    errors = []
    rules = []
    if not os.path.isfile(reg_path):
        return rules, ["%s does not exist" % REGISTRY_PATH]
    text = read_text(reg_path)
    try:
        block, prefix_lines = _extract_delimited_block(text, REGISTRY_BEGIN, REGISTRY_END)
    except DocsCheckError as exc:
        return rules, [str(exc)]
    for offset, raw_line in enumerate(block.split("\n")):
        line_no = prefix_lines + offset + 1
        line = raw_line.strip()
        if not line or not line.startswith("-"):
            continue
        body = line[1:].strip()
        fields = [f.strip() for f in body.split("|")]
        if len(fields) != 4:
            errors.append("%s:%d: expected 4 `|`-delimited fields (pattern | owner | status | notes), got %d"
                           % (REGISTRY_PATH, line_no, len(fields)))
            continue
        pattern_field, owner, status, notes = fields
        if pattern_field.startswith(MATCH_TYPE_HOST):
            match_type, pattern = "host", pattern_field[len(MATCH_TYPE_HOST):].strip()
        elif pattern_field.startswith(MATCH_TYPE_PREFIX):
            match_type, pattern = "prefix", pattern_field[len(MATCH_TYPE_PREFIX):].strip()
        else:
            errors.append("%s:%d: pattern field must start with %r or %r, got %r"
                           % (REGISTRY_PATH, line_no, MATCH_TYPE_HOST, MATCH_TYPE_PREFIX, pattern_field))
            continue
        if not pattern:
            errors.append("%s:%d: empty pattern value" % (REGISTRY_PATH, line_no))
            continue
        if not owner:
            errors.append("%s:%d: empty owner field for pattern %r" % (REGISTRY_PATH, line_no, pattern))
        if status not in EXTERNAL_STATUSES:
            errors.append("%s:%d: pattern %r has invalid status %r (must be one of: %s)"
                           % (REGISTRY_PATH, line_no, pattern, status, ", ".join(sorted(EXTERNAL_STATUSES))))
        rules.append(RegistryRule(match_type, pattern, owner, status, notes, line_no))
    return rules, errors


def match_registry(url, rules):
    """Return the first registry rule that covers ``url``, or None."""
    parsed = urllib.parse.urlsplit(url)
    for rule in rules:
        if rule.match_type == "host" and parsed.netloc == rule.pattern:
            return rule
        if rule.match_type == "prefix" and url.startswith(rule.pattern):
            return rule
    return None


FIREEMBLEM8U_URL_RE = re.compile(r"^https?://(github\.com/laqieer/fireemblem8u|decomp\.dev/laqieer/fireemblem8u)")


def check_external_urls(markdown_files, root, rules):
    findings = []
    for path in markdown_files:
        text = read_text(os.path.join(root, path))
        stripped = strip_fenced_blocks(text)
        for lineno, url in extract_external_urls(stripped):
            if not re.match(r"^https?://[^\s/]+", url):
                findings.append(Finding(path, lineno, "malformed external URL: %r" % url))
                continue
            rule = match_registry(url, rules)
            if rule is None:
                findings.append(Finding(path, lineno,
                                         "external URL not covered by any %s rule: %s" % (REGISTRY_PATH, url)))
                continue
            if FIREEMBLEM8U_URL_RE.match(url) and rule.status != "historical-upstream":
                findings.append(Finding(path, lineno,
                                         "fireemblem8u upstream URL matched a registry rule with status %r, "
                                         "must be 'historical-upstream': %s" % (rule.status, url)))
    return findings


# ---------------------------------------------------------------------------
# Static (never-executed) Makefile target database
# ---------------------------------------------------------------------------

MAKE_ROOT_FILE = "Makefile"
MAKE_TARGET_LINE_RE = re.compile(r"^([^:\t#][^:#]*):(?!=)")
MAKE_INCLUDE_RE = re.compile(r"^(-?include)\s+(.+)$")


def _split_make_line_tokens(lhs):
    """Split a Makefile rule's left-hand side into individual target
    tokens, dropping special targets and anything containing an
    unresolved Make variable/wildcard (those are handled by the
    caller via pattern-rule matching, or are simply not a target name
    a doc could reference literally)."""
    tokens = []
    for tok in lhs.split():
        if tok.startswith("."):
            continue
        if "$" in tok:
            continue
        tokens.append(tok)
    return tokens


def parse_make_targets(root):
    """Statically parse Makefile + its (non-variable) ``include``s for
    target names, WITHOUT ever invoking ``make`` (so no recipe -- and
    hence no compiler/network/ROM-build command -- is ever executed).

    Returns (literal_targets: set[str], pattern_targets: set[str]) where
    pattern_targets contains raw ``%``-containing target tokens (e.g.
    ``%.gba``) to be matched via ``make_target_exists``.
    """
    literal = set()
    patterns = set()
    seen_files = set()

    def parse_file(rel_path):
        abs_path = os.path.normpath(os.path.join(root, rel_path))
        if abs_path in seen_files or not os.path.isfile(abs_path):
            return
        seen_files.add(abs_path)
        lines = read_text(abs_path).split("\n")
        cont_buf = None
        for line in lines:
            if cont_buf is not None:
                piece = line.rstrip()
                more = piece.endswith("\\")
                if more:
                    piece = piece[:-1]
                cont_buf += " " + piece.strip()
                if more:
                    continue
                process_line(cont_buf, os.path.dirname(rel_path))
                cont_buf = None
                continue
            if line.startswith("\t"):
                continue  # recipe line, never parsed/executed
            stripped_line = line.rstrip()
            if stripped_line.endswith("\\") and not stripped_line.strip().startswith("#"):
                cont_buf = stripped_line[:-1]
                continue
            process_line(line, os.path.dirname(rel_path))

    def process_line(line, containing_dir):
        s = line.strip()
        if not s or s.startswith("#"):
            return
        m = MAKE_INCLUDE_RE.match(s)
        if m:
            for inc in m.group(2).split():
                if "$" in inc or "*" in inc:
                    continue  # can't resolve a computed/wildcard include path statically
                parse_file(os.path.normpath(os.path.join(containing_dir, inc)))
            return
        m = MAKE_TARGET_LINE_RE.match(s)
        if not m:
            return
        for tok in _split_make_line_tokens(m.group(1)):
            if "%" in tok:
                patterns.add(tok)
            else:
                literal.add(tok)

    parse_file(MAKE_ROOT_FILE)
    return literal, patterns


def make_target_exists(name, literal_targets, pattern_targets):
    if name in literal_targets:
        return True
    for pat in pattern_targets:
        if "%" not in pat:
            continue
        regex = "^" + "".join(
            ".+" if part == "%" else re.escape(part)
            for part in re.split(r"(%)", pat)
        ) + "$"
        if re.match(regex, name):
            return True
    return False


PLACEHOLDER_CHARS = set("<>*{}")
DIR_REDIRECT_FLAGS = {"-C", "--directory"}


def _make_invocation_lines(markdown_text):
    """Yield individual candidate command lines: every line of every
    fenced code block, plus every whole inline-code-span (never plain
    prose -- this is what keeps "to make target X" in a quoted error
    message, or "make sure", from ever being considered a command)."""
    for block in iter_fenced_block_bodies(markdown_text):
        for line in block.split("\n"):
            yield line
    for line in markdown_text.split("\n"):
        for span in INLINE_CODE_RE.findall(line):
            yield span


def extract_make_invocations(markdown_text):
    """Yield every distinct (is_bare, target) pair for a ``make`` command
    that is the first token of its own fenced-code line or inline code
    span (never matched mid-sentence in prose, e.g. "to make target X" in
    a quoted error message). ``is_bare`` is True for a target-less
    ``make``/``make -jN`` invocation (the documented default-build case).
    A candidate whose only token is a placeholder (``<target>``, ``%``,
    etc.) or that redirects to a different Makefile via ``-C``/
    ``--directory`` is intentionally not yielded at all (nothing to
    validate against this repository's own Makefile database).
    """
    seen = set()
    for line in _make_invocation_lines(markdown_text):
        m = MAKE_CMD_RE.match(line)
        if not m:
            continue
        tokens = m.group(1).strip().split()
        target = None
        skip_invocation = False
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in DIR_REDIRECT_FLAGS or re.match(r"^--directory=", tok):
                skip_invocation = True  # targets a different Makefile entirely
                break
            if tok.startswith("-"):
                i += 1
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):
                i += 1
                continue  # VAR=value override, not a target name
            if any(c in PLACEHOLDER_CHARS for c in tok):
                skip_invocation = True  # illustrative placeholder, not a real target
                break
            if not any(c.isalnum() for c in tok):
                skip_invocation = True  # e.g. an ellipsis "..." standing in for elided args
                break
            if tok.isalpha() and tok.isupper() and len(tok) > 1:
                skip_invocation = True  # e.g. generic ALL-CAPS "TARGET"/"N" placeholder prose
                break
            target = tok
            break
        if skip_invocation:
            continue
        key = (True, None) if target is None else (False, target)
        if key in seen:
            continue
        seen.add(key)
        yield key


def check_make_targets(markdown_files, root, literal_targets, pattern_targets):
    findings = []
    for path in markdown_files:
        text = read_text(os.path.join(root, path))
        for is_bare, target in extract_make_invocations(text):
            if is_bare or target is None:
                continue
            if not make_target_exists(target, literal_targets, pattern_targets):
                findings.append(Finding(path, 0, "documented `make %s` does not resolve to any known Makefile target"
                                        % target))
    return findings


# ---------------------------------------------------------------------------
# Stale-phrase denylist
# ---------------------------------------------------------------------------

def check_stale_phrases(markdown_files, root):
    findings = []
    for path in markdown_files:
        text = read_text(os.path.join(root, path))
        stripped = strip_fenced_blocks(text)
        for lineno, line in enumerate(stripped.split("\n"), start=1):
            for regex, message in STALE_PHRASE_RULES:
                if regex.search(line):
                    findings.append(Finding(path, lineno, message))
    return findings


# ---------------------------------------------------------------------------
# Internal-link orchestration
# ---------------------------------------------------------------------------

def check_internal_links(markdown_files, root):
    findings = []
    heading_slug_cache = {}
    for path in markdown_files:
        text = read_text(os.path.join(root, path))
        stripped = strip_fenced_blocks(text)
        for lineno, target in extract_internal_link_targets(stripped):
            if _is_external(target):
                continue
            ok, message = resolve_internal_link(root, path, target, heading_slug_cache)
            if not ok:
                findings.append(Finding(path, lineno, message))
    return findings


# ---------------------------------------------------------------------------
# Safe, explicitly allowlisted example-command execution
# ---------------------------------------------------------------------------

UNSAFE_TOKEN_RE = re.compile(
    r"^(curl|wget|scp|ssh|nc|ncat|pip|pip3|npm|npx|yarn|go)$", re.IGNORECASE
)
UNSAFE_SUBCOMMANDS = {"fetch", "verify", "clone", "push", "pull"}
ROM_BUILD_TOKENS = {"all", "legacy", "fireemblem8.gba"}


def is_command_safe(argv):
    """Defense-in-depth guard: reject anything that looks like it could
    touch the network, mutate source, or build/link a ROM. Used both to
    sanity-check this script's own hardcoded example allowlist and as the
    general-purpose rejection logic exercised by tests -- this script
    never executes an arbitrary command discovered inside a doc file."""
    if not argv:
        return False
    tokens = [os.path.basename(str(t)) for t in argv]
    for tok in tokens:
        if UNSAFE_TOKEN_RE.match(tok):
            return False
    joined = " ".join(str(t) for t in argv)
    for bad in UNSAFE_SUBCOMMANDS:
        if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(bad), joined):
            return False
    if tokens and (tokens[0] == "make" or tokens[0].endswith(("quickstart.sh",))):
        if "--help" not in argv and "-h" not in argv:
            # A quickstart/make invocation without --help would actually
            # attempt a real build -- only --help forms are ever "safe".
            if tokens[0] == "make":
                return False
    for tok in argv:
        if tok in ROM_BUILD_TOKENS:
            return False
    return True


def _safe_examples(root):
    return [
        ("quickstart-help", [os.path.join(root, "scripts", "quickstart.sh"), "--help"]),
        ("upstream-port-help", [sys.executable, "-m", "scripts.upstream_port", "--help"]),
        ("check-docs-help", [sys.executable, os.path.join(root, "scripts", "check_docs.py"), "--help"]),
    ]


def run_safe_example(name, argv, root, timeout=30):
    if not is_command_safe(argv):
        return False, "refused: %s is not on the safe (zero-ROM/zero-network) allowlist" % name
    try:
        result = subprocess.run(
            argv, cwd=root, capture_output=True, timeout=timeout, text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "%s failed to execute: %s" % (name, exc)
    if result.returncode != 0:
        return False, "%s exited %d: %s" % (name, result.returncode, result.stderr.strip()[:400])
    return True, "%s: ok" % name


def run_all_safe_examples(root):
    results = []
    for name, argv in _safe_examples(root):
        ok, message = run_safe_example(name, argv, root)
        results.append((name, ok, message))
    return results


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def run_checks(root, check_examples=False):
    findings = []
    markdown_files = discover_markdown_files(root)

    entries, inv_errors = parse_inventory(root)
    findings.extend(Finding(INVENTORY_PATH, 0, e) for e in inv_errors)
    findings.extend(check_inventory_coverage(root, markdown_files, entries))

    rules, reg_errors = parse_registry(root)
    findings.extend(Finding(REGISTRY_PATH, 0, e) for e in reg_errors)
    findings.extend(check_external_urls(markdown_files, root, rules))

    findings.extend(check_internal_links(markdown_files, root))
    findings.extend(check_reference_style_links(markdown_files, root))
    findings.extend(check_stale_phrases(markdown_files, root))

    literal_targets, pattern_targets = parse_make_targets(root)
    findings.extend(check_make_targets(markdown_files, root, literal_targets, pattern_targets))

    example_results = []
    if check_examples:
        example_results = run_all_safe_examples(root)
        for name, ok, message in example_results:
            if not ok:
                findings.append(Finding("(safe-example)", 0, message))

    findings.sort(key=lambda f: (f.file, f.line, f.message))
    return findings, markdown_files, example_results


def format_findings(findings):
    lines = []
    for f in findings:
        loc = "%s:%d" % (f.file, f.line) if f.line else f.file
        lines.append("%s: %s" % (loc, f.message))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Stdlib-only Markdown documentation governance checker (Issues #7/#17).",
    )
    parser.add_argument(
        "--check", action="store_true", default=True,
        help="Run the full static check suite (default action).",
    )
    parser.add_argument(
        "--check-examples", action="store_true",
        help="Additionally execute the hardcoded, zero-ROM/zero-network safe example "
             "commands (quickstart/upstream-port/check-docs --help) and require they succeed.",
    )
    parser.add_argument(
        "--root", default=None,
        help="Repository root (default: auto-detect via `git rev-parse --show-toplevel`).",
    )
    args = parser.parse_args(argv)

    try:
        root = args.root or get_repo_root()
    except DocsCheckError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    try:
        findings, markdown_files, example_results = run_checks(root, check_examples=args.check_examples)
    except DocsCheckError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if findings:
        print(format_findings(findings))
        print("\n%d finding(s) across %d Markdown file(s) checked." % (len(findings), len(markdown_files)))
        return 1

    print("check_docs: OK -- %d Markdown file(s) checked, 0 findings." % len(markdown_files))
    if args.check_examples:
        for name, ok, message in example_results:
            print("  example[%s]: %s" % (name, message))
    return 0


if __name__ == "__main__":
    sys.exit(main())
