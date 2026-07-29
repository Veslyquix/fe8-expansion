"""Reusable validation helpers shared across generated-data tables.

Each helper returns/raises :class:`GeneratedDataError` diagnostics carrying
a :class:`SourceLocation` and a ``reference_path`` breadcrumb, so callers
can keep collecting errors with a :class:`DiagnosticCollector` instead of
stopping at the first problem.
"""

from __future__ import annotations

import re

from .diagnostics import GeneratedDataError

_ENUM_ENTRY_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?0[xX][0-9A-Fa-f]+|-?\d+)\s*,?\s*(//.*)?$"
)

_DEFINE_ENTRY_RE = re.compile(
    r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\s+(-?0[xX][0-9A-Fa-f]+|-?\d+)\s*(?:/\*.*?\*/|//.*)?\s*$"
)


def extract_enum_constants(header_path, name_prefix=None):
    """Scan a C header for ``NAME = <value>,`` enum entries.

    Returns an ordered ``dict`` of ``name -> (value, line_number)``. This
    is intentionally simple (regex, not a real C parser) -- sufficient for
    this project's enum-style constant headers, which always assign an
    explicit numeric value per entry.

    ``name_prefix``, if given, filters to symbols starting with it (e.g.
    ``"CHARACTER_"``), letting the same header be reused for multiple
    constant families without cross-contamination.
    """
    constants = {}
    with open(header_path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            match = _ENUM_ENTRY_RE.match(line)
            if not match:
                continue
            name = match.group(1)
            if name_prefix is not None and not name.startswith(name_prefix):
                continue
            value_text = match.group(2)
            value = int(value_text, 16) if value_text.lower().startswith(("0x", "-0x")) else int(value_text)
            constants[name] = (value, line_number)
    return constants


def extract_define_constant(header_path, name):
    """Scan a C header for a single ``#define NAME VALUE`` object-like macro.

    Unlike :func:`extract_enum_constants` (which reads ``NAME = value,``
    enum entries), this reads plain preprocessor object-macro constants
    such as ``#define MSG_COUNT 0x0D56`` -- the live upper bound for text
    IDs (``items`` table's ``nameTextId``/``descTextId``/``useDescTextId``
    fields validate against this instead of a hardcoded number so the
    bound stays honest if the message table ever grows).

    Returns ``(value, line_number)``. Raises :class:`GeneratedDataError`
    if ``name`` is not defined as a plain integer literal anywhere in the
    header.
    """
    with open(header_path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            match = _DEFINE_ENTRY_RE.match(line)
            if not match or match.group(1) != name:
                continue
            value_text = match.group(2)
            value = int(value_text, 16) if value_text.lower().startswith(("0x", "-0x")) else int(value_text)
            return value, line_number
    raise GeneratedDataError("could not find '#define {} ...' in {}".format(name, header_path))


def extract_define_constants(header_path, name_prefix=None):
    """Scan a C header for every ``#define NAME VALUE`` object-like macro.

    The plural companion of :func:`extract_define_constant`: it returns an
    ordered ``dict`` of ``name -> (value, line_number)`` for a whole
    constant family instead of one named macro, mirroring
    :func:`extract_enum_constants`' shape so both can feed
    :func:`validate_reference` unchanged.

    ``name_prefix``, if given, filters to symbols starting with it (e.g.
    ``"MSG_"`` for ``include/constants/msg.h``), so a header that also
    defines unrelated macros (``MSG_COUNT``'s neighbours, include guards)
    does not contaminate the family.
    """
    constants = {}
    with open(header_path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            match = _DEFINE_ENTRY_RE.match(line)
            if not match:
                continue
            name = match.group(1)
            if name_prefix is not None and not name.startswith(name_prefix):
                continue
            value_text = match.group(2)
            value = int(value_text, 16) if value_text.lower().startswith(("0x", "-0x")) else int(value_text)
            constants[name] = (value, line_number)
    return constants


def resolve_bitmask_flags(names, flag_values, loc, reference_path, kind="flag"):
    """Validate and resolve a list of symbolic bitmask flag names (e.g.
    ``["IA_WEAPON", "IA_UNSELLABLE"]``) against a ``{name: int_value}``
    mapping (typically built by a table-specific header reader, since
    project bitmask enums are usually written as ``NAME = (1 << N)``
    expressions that :func:`extract_enum_constants` does not parse).

    Returns ``(value, errors)`` where ``value`` is the bitwise-OR of every
    *valid* name's resolved value (unknown/duplicate names contribute
    nothing to it, since the caller should treat a value accompanied by
    errors as unreliable) and ``errors`` is a list of
    :class:`GeneratedDataError` covering unknown names and names repeated
    within the same list.
    """
    errors = []
    seen = set()
    value = 0
    for name in names:
        if name in seen:
            errors.append(
                GeneratedDataError(
                    "duplicate {} '{}' in the same list".format(kind, name),
                    loc,
                    reference_path,
                )
            )
            continue
        seen.add(name)
        if name not in flag_values:
            errors.append(
                GeneratedDataError(
                    "undefined {} reference '{}'".format(kind, name),
                    loc,
                    reference_path,
                )
            )
            continue
        value |= flag_values[name]
    return value, errors


def validate_unique(entries, message_fmt, reference_path_fmt):
    """Detect duplicate keys among ``entries``.

    ``entries`` is an iterable of ``(key, location)`` pairs (in the order
    encountered). Returns a list of :class:`GeneratedDataError`, one per
    duplicate occurrence, referencing the first definition's location.
    """
    errors = []
    seen = {}
    for key, loc in entries:
        if key in seen:
            errors.append(
                GeneratedDataError(
                    message_fmt.format(key=key, first_loc=seen[key]),
                    loc,
                    reference_path_fmt.format(key=key),
                )
            )
        else:
            seen[key] = loc
    return errors


def validate_reference(symbol, allowed, loc, reference_path, kind="symbol"):
    """Check ``symbol`` is a member of the ``allowed`` set/dict.

    Returns a single-element error list if invalid, else ``[]``.
    """
    if symbol not in allowed:
        return [
            GeneratedDataError(
                "undefined {} reference '{}'".format(kind, symbol),
                loc,
                reference_path,
            )
        ]
    return []


def validate_range(value, minimum, maximum, loc, reference_path, field_name="value"):
    """Check ``minimum <= value <= maximum``."""
    if not (minimum <= value <= maximum):
        return [
            GeneratedDataError(
                "{} {} out of range [{}, {}]".format(field_name, value, minimum, maximum),
                loc,
                reference_path,
            )
        ]
    return []


def validate_fixed_capacity(count, capacity, loc, reference_path, what="entries"):
    """Check ``0 <= count <= capacity`` (a fixed-size C array bound)."""
    if not (0 <= count <= capacity):
        return [
            GeneratedDataError(
                "{} count {} exceeds fixed capacity {}".format(what, count, capacity),
                loc,
                reference_path,
            )
        ]
    return []


def validate_parallel_arrays(lengths, loc, reference_path, names):
    """Check that all parallel arrays (e.g. characters[]/expBase[]/...) agree in length."""
    errors = []
    if len(set(lengths)) > 1:
        detail = ", ".join("{}={}".format(name, length) for name, length in zip(names, lengths))
        errors.append(
            GeneratedDataError(
                "parallel arrays have mismatched lengths: {}".format(detail),
                loc,
                reference_path,
            )
        )
    return errors
