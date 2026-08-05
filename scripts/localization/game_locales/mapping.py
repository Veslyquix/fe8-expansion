"""Sparse FE8U-target mapping schema and authority-aware validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .parsers import FE8J_MAX_INDEXED_ID

MAPPING_SCHEMA_VERSION = 1
MAPPING_KIND = "fe8u-locale-mapping"
AUTHORITY_CANDIDATE = "candidate"
AUTHORITY_VERIFIED = "verified"
ROW_CANDIDATE = "candidate"
ROW_VERIFIED = "verified"
SOURCE_KINDS = ("indexed", "raw", "authored", "english_fallback")
LOCALE_IDS = ("ja", "zh-Hans")

_ID_RE = re.compile(r"0x([0-9A-F]{4})")
_ADDRESS_RE = re.compile(r"0x([0-9A-F]{8})")
_RAW_KEY_RE = re.compile(r"fe8cn\.raw\.[0-9A-F]{8}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class MappingError(ValueError):
    """Raised when a sparse mapping document violates its authority contract."""


@dataclass(frozen=True)
class MappingRow:
    target_id: int
    state: str
    source_kind: str
    source: Dict[str, Any]
    candidate_provenance: Optional[Dict[str, Any]]
    verification: Optional[Dict[str, Any]]


@dataclass(frozen=True)
class MappingDocument:
    authority: str
    authoritative: bool
    locale_ids: Tuple[str, ...]
    rows: Tuple[MappingRow, ...]
    note: str

    @property
    def coverage_eligible(self) -> bool:
        return self.authority == AUTHORITY_VERIFIED and self.authoritative


def format_message_id(value: int) -> str:
    return f"0x{value:04X}"


def _require_dict(value: Any, field: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise MappingError(f"{field} must be an object")
    return value


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise MappingError(f"{field} must be a non-empty string")
    return value


def _parse_id(value: Any, field: str) -> int:
    if not isinstance(value, str) or not (match := _ID_RE.fullmatch(value)):
        raise MappingError(f"{field} must use canonical 0xNNNN form")
    return int(match.group(1), 16)


def _validate_source(source: Dict[str, Any], field: str) -> str:
    kind = source.get("kind")
    if kind not in SOURCE_KINDS:
        raise MappingError(f"{field}.kind must be one of {SOURCE_KINDS}")
    if kind == "indexed":
        if source.get("layout") != "FE8J":
            raise MappingError(f"{field}.layout must be 'FE8J' for indexed sources")
        source_id = _parse_id(source.get("id"), f"{field}.id")
        if source_id > FE8J_MAX_INDEXED_ID:
            raise MappingError(
                f"{field}.id exceeds the FE8J indexed maximum 0x{FE8J_MAX_INDEXED_ID:04X}"
            )
    elif kind == "raw":
        key = source.get("key")
        address = source.get("address")
        if not isinstance(key, str) or not _RAW_KEY_RE.fullmatch(key):
            raise MappingError(f"{field}.key must be a stable fe8cn.raw.ADDRESS key")
        if not isinstance(address, str) or not _ADDRESS_RE.fullmatch(address):
            raise MappingError(f"{field}.address must use canonical 0xNNNNNNNN form")
        if key.rsplit(".", 1)[1] != address[2:]:
            raise MappingError(f"{field}.key and address must name the same record")
    elif kind == "authored":
        _require_nonempty_string(source.get("translation_key"), f"{field}.translation_key")
    elif kind == "english_fallback":
        _require_nonempty_string(source.get("reason"), f"{field}.reason")
    return kind


def validate_mapping_document(
    data: Any,
    *,
    target_count: Optional[int] = None,
) -> MappingDocument:
    document = _require_dict(data, "mapping")
    if document.get("schema_version") != MAPPING_SCHEMA_VERSION:
        raise MappingError(
            f"mapping.schema_version must be {MAPPING_SCHEMA_VERSION}"
        )
    if document.get("kind") != MAPPING_KIND:
        raise MappingError(f"mapping.kind must be {MAPPING_KIND!r}")

    authority = document.get("authority")
    if authority not in (AUTHORITY_CANDIDATE, AUTHORITY_VERIFIED):
        raise MappingError("mapping.authority must be 'candidate' or 'verified'")
    authoritative = document.get("authoritative")
    if not isinstance(authoritative, bool):
        raise MappingError("mapping.authoritative must be a boolean")
    if authoritative != (authority == AUTHORITY_VERIFIED):
        raise MappingError(
            "mapping.authoritative must be false for candidates and true for verified mappings"
        )

    raw_locale_ids = document.get("locale_ids")
    if not isinstance(raw_locale_ids, list) or not raw_locale_ids:
        raise MappingError("mapping.locale_ids must be a non-empty array")
    if any(locale not in LOCALE_IDS for locale in raw_locale_ids):
        raise MappingError(f"mapping.locale_ids must contain only {LOCALE_IDS}")
    if len(set(raw_locale_ids)) != len(raw_locale_ids):
        raise MappingError("mapping.locale_ids must not contain duplicates")
    if authority == AUTHORITY_VERIFIED and len(raw_locale_ids) != 1:
        raise MappingError("verified mappings must cover exactly one locale")

    note = _require_nonempty_string(document.get("note"), "mapping.note")
    if authority == AUTHORITY_CANDIDATE:
        if document.get("source_layout") != "FE8J":
            raise MappingError("candidate mapping.source_layout must be 'FE8J'")
        provenance = _require_dict(document.get("provenance"), "mapping.provenance")
        _require_nonempty_string(
            provenance.get("input_id"),
            "mapping.provenance.input_id",
        )
        _require_nonempty_string(
            provenance.get("logical_path"),
            "mapping.provenance.logical_path",
        )
        sha256 = provenance.get("sha256")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            raise MappingError("mapping.provenance.sha256 must be 64 lowercase hex digits")
    raw_rows = document.get("rows")
    if not isinstance(raw_rows, list):
        raise MappingError("mapping.rows must be an array")

    rows = []
    seen_targets = set()
    previous_target: Optional[int] = None
    for index, raw_row in enumerate(raw_rows):
        field = f"mapping.rows[{index}]"
        row = _require_dict(raw_row, field)
        target_id = _parse_id(row.get("target_id"), f"{field}.target_id")
        if target_count is not None and target_id >= target_count:
            raise MappingError(
                f"{field}.target_id {format_message_id(target_id)} is outside "
                f"FE8U target count {target_count}"
            )
        if target_id in seen_targets:
            raise MappingError(
                f"{field}.target_id duplicates {format_message_id(target_id)}"
            )
        if previous_target is not None and target_id <= previous_target:
            raise MappingError("mapping rows must be sorted by ascending target_id")
        seen_targets.add(target_id)
        previous_target = target_id

        state = row.get("state")
        expected_state = ROW_VERIFIED if authority == AUTHORITY_VERIFIED else ROW_CANDIDATE
        if state != expected_state:
            raise MappingError(
                f"{field}.state must be {expected_state!r} for a {authority} document"
            )
        source = _require_dict(row.get("source"), f"{field}.source")
        source_kind = _validate_source(source, f"{field}.source")

        candidate_provenance = row.get("candidate_provenance")
        verification = row.get("verification")
        if authority == AUTHORITY_CANDIDATE:
            provenance = _require_dict(
                candidate_provenance,
                f"{field}.candidate_provenance",
            )
            _require_nonempty_string(
                provenance.get("seed_tag"),
                f"{field}.candidate_provenance.seed_tag",
            )
            source_line = provenance.get("source_line")
            if isinstance(source_line, bool) or not isinstance(source_line, int) or source_line < 1:
                raise MappingError(
                    f"{field}.candidate_provenance.source_line must be a positive integer"
                )
            if verification is not None:
                raise MappingError(f"{field}.verification is forbidden on candidate rows")
        else:
            if candidate_provenance is not None:
                raise MappingError(
                    f"{field}.candidate_provenance is forbidden on verified rows"
                )
            verified = _require_dict(verification, f"{field}.verification")
            _require_nonempty_string(
                verified.get("method"),
                f"{field}.verification.method",
            )
            _require_nonempty_string(
                verified.get("evidence"),
                f"{field}.verification.evidence",
            )

        rows.append(
            MappingRow(
                target_id=target_id,
                state=state,
                source_kind=source_kind,
                source=source,
                candidate_provenance=candidate_provenance,
                verification=verification,
            )
        )

    return MappingDocument(
        authority=authority,
        authoritative=authoritative,
        locale_ids=tuple(raw_locale_ids),
        rows=tuple(rows),
        note=note,
    )
