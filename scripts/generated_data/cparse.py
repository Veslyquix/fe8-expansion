"""Small brace-depth-aware C source parsing helpers shared by the
hand-written round-trip parsers.

Regexes with non-greedy ``.*?`` capture groups (as used by
``supports/parser.py``) work fine for a struct with no nested array
initializers, but ``UnitDefinition``/``TrapData``-style tables need genuine
brace-matching: a top-level array of struct literals, where each struct
literal itself contains nested ``{ ... }`` initializers (``items``, ``ai``).
This module is still not a general C parser -- it only understands plain
``{``/``}`` nesting (no string/char literals containing braces, which none
of this project's designated-initializer data files use).
"""

from __future__ import annotations

import re

from .diagnostics import GeneratedDataError, SourceLocation


def find_matching_brace(text, open_index):
    """Given the index of an opening ``{`` in ``text``, return the index of
    its matching closing ``}`` (brace-depth aware)."""
    assert text[open_index] == "{"
    depth = 0
    for i in range(open_index, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    raise GeneratedDataError("unbalanced braces starting at index {}".format(open_index))


def find_c_array_blocks(text, decl_pattern):
    """Find every ``<decl_pattern> <NAME>[] = { ... };`` block in ``text``.

    ``decl_pattern`` is a regex fragment matching the declaration prefix up
    to (not including) the array name, e.g. ``r"CONST_DATA\\s+struct\\s+REDA"``.

    Returns a list of ``(name, body, start_index)`` tuples, where ``body``
    is the raw text strictly between the outermost ``{`` and ``}``
    (exclusive), and ``start_index`` is the character offset of the ``NAME``
    token (for line-number diagnostics).
    """
    header_re = re.compile(decl_pattern + r"\s+([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*\]\s*=\s*", re.MULTILINE)
    blocks = []
    for match in header_re.finditer(text):
        name = match.group(1)
        name_index = match.start(1)
        brace_start = text.index("{", match.end())
        brace_end = find_matching_brace(text, brace_start)
        body = text[brace_start + 1:brace_end]
        blocks.append((name, body, name_index))
    return blocks


def split_top_level_entries(body):
    """Split an array-literal body into its top-level comma-separated
    entries, respecting brace nesting (so commas inside a nested ``{ ... }``
    don't split the entry).

    Whitespace-only/empty entries (e.g. a trailing comma) are dropped.
    """
    entries = []
    depth = 0
    current_start = 0
    i = 0
    length = len(body)
    while i < length:
        ch = body[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "," and depth == 0:
            entries.append(body[current_start:i])
            current_start = i + 1
        i += 1
    entries.append(body[current_start:])
    return [e.strip() for e in entries if e.strip()]


def strip_outer_braces(entry):
    """Strip one layer of enclosing ``{ ... }`` from a trimmed entry string."""
    entry = entry.strip()
    if entry.startswith("{") and entry.endswith("}"):
        return entry[1:-1].strip()
    return entry


_FIELD_RE_CACHE = {}


def extract_designated_fields(struct_body):
    """Parse ``.field = value`` pairs out of a struct literal body (already
    brace-stripped), respecting nested-brace values for array fields.

    Returns an ordered ``dict`` of ``field_name -> raw_value_text`` (value
    text is NOT further parsed -- callers interpret it, since some fields
    are scalars and others are nested ``{ ... }`` array literals).
    """
    fields = {}
    for entry in split_top_level_entries(struct_body):
        m = re.match(r"^\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", entry, re.S)
        if not m:
            continue
        fields[m.group(1)] = m.group(2).strip()
    return fields


_IF_RE = re.compile(r"^[ \t]*#if\b")
_ELSE_RE = re.compile(r"^[ \t]*#else\b")
_ENDIF_RE = re.compile(r"^[ \t]*#endif\b")


def strip_hand_conditionals(text):
    """Reduce every top-level ``#if X ... #else ... #endif`` block (as
    used e.g. by ``#if FE8_CUSTOM_CAMPAIGN`` overrides in the generated-data
    linked hand sources) down to just its ``#else`` branch, blanking
    everything else -- the ``#if`` line, the ``#if`` branch's own lines,
    and the ``#else``/``#endif`` directive lines themselves -- to blank
    lines. A block with no ``#else`` is blanked out entirely.

    This is deliberately narrow, not a general preprocessor: round-trip
    parsing exists to catch drift between the JSON source of truth and a
    hand file that is meant to mirror it exactly, and JSON has no notion
    of a build flag. A conditional branch is, by definition, a build-time
    -only override with nothing in JSON to compare against, so the
    ``#else`` fallback -- conventionally the unmodified/vanilla value --
    is what round-trip parsing should see. Blanking (rather than
    deleting) every non-``#else`` line keeps line numbers stable for
    diagnostics. Only one level of nesting is handled -- none of this
    project's hand-linked tables currently nest ``#if`` blocks.
    """
    lines = text.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _IF_RE.match(line):
            out.append("")
            i += 1
            while i < n and not _ELSE_RE.match(lines[i]) and not _ENDIF_RE.match(lines[i]):
                out.append("")
                i += 1
            if i < n and _ELSE_RE.match(lines[i]):
                out.append("")
                i += 1
                while i < n and not _ENDIF_RE.match(lines[i]):
                    out.append(lines[i])
                    i += 1
            if i < n and _ENDIF_RE.match(lines[i]):
                out.append("")
                i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def loc_at(path, text, index, column=1):
    return SourceLocation(path, line_of(text, index), column)
