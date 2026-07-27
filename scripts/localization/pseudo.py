"""Deterministic ASCII pseudo-locale transform (issue #18 sprint 1).

Generates the qps-ploc ("Pseudo (Test)") catalog from the English catalog
at generate time -- never hand-authored, never a real translation of any
language. The transform is intentionally decorative and obviously
synthetic (bracket-wrapped, alternating-case, vowel-doubled ASCII) so it
can never be mistaken for actual localized content; it exists purely as a
deterministic, snapshot-testable exercise of the runtime resolver/UI width
budget for a locale whose rendered text differs from English.

Placeholder tokens (``{0}``, ``{1}``, ...) and the single supported
control token (``\\n``) are always copied through verbatim -- transforming
either would break format-string/formatting parity between English and
the pseudo locale (see validate.py's placeholder/control-token parity
check).
"""

from __future__ import annotations

import re

_PLACEHOLDER_RE = re.compile(r"\{[0-9]+\}")
_VOWELS = set("aeiouAEIOU")

PSEUDO_PREFIX = "[["
PSEUDO_SUFFIX = "]]"


def _transform_span(text: str, start_index: int) -> str:
    """Transforms one non-placeholder span: alternates letter case by a
    running alpha-character index (deterministic, position-based -- not
    random), and doubles vowels for a mild, deterministic length
    expansion (real pseudo-localization tooling expands string length to
    exercise width/wrapping budgets). Newlines and all other non-alpha
    characters (spaces, punctuation, digits) pass through unchanged."""
    out = []
    alpha_index = start_index
    for ch in text:
        if ch.isalpha():
            out.append(ch.upper() if alpha_index % 2 == 0 else ch.lower())
            if ch in _VOWELS:
                out.append(out[-1])
            alpha_index += 1
        else:
            out.append(ch)
    return "".join(out), alpha_index


def pseudoize(text: str) -> str:
    """Deterministically transforms one English catalog string into its
    ASCII pseudo-locale form, preserving every ``{N}`` placeholder and
    ``\\n`` control token exactly (both are matched by _PLACEHOLDER_RE /
    passed through untouched by _transform_span respectively)."""
    pieces = []
    alpha_index = 0
    last_end = 0
    for match in _PLACEHOLDER_RE.finditer(text):
        span_text, alpha_index = _transform_span(text[last_end:match.start()], alpha_index)
        pieces.append(span_text)
        pieces.append(match.group(0))
        last_end = match.end()
    span_text, alpha_index = _transform_span(text[last_end:], alpha_index)
    pieces.append(span_text)
    return f"{PSEUDO_PREFIX}{''.join(pieces)}{PSEUDO_SUFFIX}"


def pseudoize_catalog(catalog: dict) -> dict:
    """Applies pseudoize() to every value of an English key->text catalog
    dict, preserving key order (Python 3.7+ dicts are ordered) for
    deterministic downstream iteration."""
    return {key: pseudoize(text) for key, text in catalog.items()}
