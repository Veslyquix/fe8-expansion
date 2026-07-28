"""Stable locale/message identifier contract (issue #18 sprint 1).

This module is the single Python-side source of truth for the stable
locale ID list; include/expansion_locale.h's ExpansionLocale_* #define
values are hand-kept in sync with LOCALE_IDS below (both are locked by
tests: scripts/localization/tests/test_schema.py on the Python side, the
host-compiled C driver tests on the C side). Never renumber an existing
locale; append-only, and a retired locale's slot must never be reused.

Deliberately independent of vanilla GetLang()/SetLang()/gLanguageMode and
of any FE8J/EU/CN language pack: these are brand-new expansion-framework
identifiers with no relation to those vanilla values.
"""

from __future__ import annotations

from typing import Dict, Tuple

# Stable, append-only, test-locked ordering. Index == the numeric
# ExpansionLocaleId value embedded in ROMs and generated tables -- do not
# reorder existing entries.
LOCALE_IDS: Tuple[str, ...] = (
    "en",
    "ja",
    "zh-Hans",
    "fr",
    "de",
    "es",
    "it",
    "qps-ploc",
)

LOCALE_INDEX: Dict[str, int] = {name: index for index, name in enumerate(LOCALE_IDS)}
LOCALE_COUNT = len(LOCALE_IDS)
LOCALE_INVALID = 0xFF

# qps-ploc is the ASCII pseudo-locale test harness (see pseudo.py):
# deterministically derived from the English catalog at generate time, and
# explicitly documented everywhere as a test tool, never a real
# translation, so it can never be mistaken for actual localized content.
PSEUDO_LOCALE = "qps-ploc"

# Sprint 1 only ships real content for English, plus the derived pseudo
# locale. Every other stable locale ID above is reserved (a stable slot
# future sprints can populate) but is never a legal value for
# EXPANSION_ENABLED_LOCALES / EXPANSION_DEFAULT_LOCALE today.
INITIALLY_SUPPORTED_LOCALES: Tuple[str, ...] = ("en", PSEUDO_LOCALE)

DEFAULT_LOCALE = "en"

# --- Message id contract -----------------------------------------------

# Mirrors include/expansion_locale.h's `typedef u16 ExpansionMsgId;` +
# `#define EXPANSION_MSG_ID_INVALID 0xFFFFu` exactly (kept in sync
# explicitly, not imported from C -- there is no Python/C shared build
# step here -- and cross-checked by scripts/localization/tests/
# test_schema.py). 0xFFFF is the one reserved "no such message" sentinel
# value every resolver caller must be able to represent; it can therefore
# never be assigned to a real registry entry (active or tombstone) by any
# path that produces a build -- see catalog.parse_registry (source-of-
# truth validation) and generate.py's defensive re-check (belt-and-braces
# against any future caller that builds a registry/catalog in-process,
# bypassing parse_registry).
MSG_ID_INVALID = 0xFFFF
MSG_ID_MIN = 0
MSG_ID_MAX = MSG_ID_INVALID - 1  # 0xFFFE -- highest assignable id

# --- Message registry field contract ----------------------------------------

STATUS_ACTIVE = "active"
STATUS_TOMBSTONE = "tombstone"
STATUSES = (STATUS_ACTIVE, STATUS_TOMBSTONE)

# Message "surface" -- which framework UI/diagnostic surface a message is
# rendered on -- purely descriptive metadata used for width-budget
# validation; not itself a rendering feature in this sprint.
SURFACES = (
    "framework_generic",
    "locale_name",
    "debug_overlay",
    "diagnostic",
)

# ASCII-only glyph allowlist for sprint 1 (see docs/config_identity.md-style
# reasoning: expansion framework strings ship as plain printable ASCII, plus
# the single control token \n). Matches vanilla's own initial glyph set
# intentionally kept narrow: broadening this later requires an explicit,
# reviewed glyph-budget change, not a silent expansion.
ASCII_MIN = 0x20
ASCII_MAX = 0x7E
ALLOWED_CONTROL_TOKENS = ("\n",)

MAX_WIDTH_MIN = 1
MAX_WIDTH_MAX = 240
MAX_DECODED_BYTES_MIN = 1
# Matches EXPANSION_LOCALE_SCRATCH_SLOT_BYTES in include/expansion_locale.h;
# kept in sync explicitly (not imported from C) and cross-checked by
# scripts/localization/tests/test_generate.py.
MAX_DECODED_BYTES_MAX = 96


class SchemaError(ValueError):
    """A registry/catalog value violates the sprint 1 schema contract."""
