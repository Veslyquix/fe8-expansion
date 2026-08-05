"""Strict parsers for the authorized FE8J and FE8CN locale sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

FE8J_MAX_INDEXED_ID = 0x0D0A
FE8J_INDEXED_COUNT = FE8J_MAX_INDEXED_ID + 1

_HASH_MARKER_RE = re.compile(r"#0x([0-9A-Fa-f]{4})")
_CN_INDEXED_MARKER_RE = re.compile(r"\[([0-9A-Fa-f]{2}|[0-9A-Fa-f]{4})\]")
_CN_RAW_MARKER_RE = re.compile(r"\[([0-9A-Fa-f]{8})\]")
_CONTROL_RE = re.compile(r"\[([^\]\r\n]+)\]\s*=\s*(.+)")
_HEX4_RE = re.compile(r"[0-9A-Fa-f]{4}")


class LocaleSourceError(ValueError):
    """Raised when an imported locale source violates its pinned grammar."""


@dataclass(frozen=True)
class IndexedMessage:
    id: int
    text: str
    marker_line: int


@dataclass(frozen=True)
class ControlDefinition:
    name: str
    values: Tuple[int, ...]
    source_line: int


@dataclass(frozen=True)
class RawOccurrence:
    record_index: int
    address: int
    text: str
    marker_line: int
    payload_start_line: int


@dataclass(frozen=True)
class RawString:
    key: str
    address: int
    text: str
    occurrences: Tuple[RawOccurrence, ...]


@dataclass(frozen=True)
class ChineseSource:
    indexed: Tuple[IndexedMessage, ...]
    raw_occurrences: Tuple[RawOccurrence, ...]
    raw_strings: Tuple[RawString, ...]


@dataclass(frozen=True)
class MappingSeedRow:
    target_id: int
    source_id: int
    provenance_tag: str
    source_line: int


def _lines(text: str) -> List[str]:
    return text.lstrip("\ufeff").splitlines()


def _finish_indexed(
    messages: List[IndexedMessage],
    current_id: Optional[int],
    marker_line: Optional[int],
    payload: List[str],
) -> None:
    if current_id is None or marker_line is None:
        return
    messages.append(IndexedMessage(current_id, "\n".join(payload), marker_line))


def parse_hash_indexed(
    text: str,
    *,
    expected_last_id: int = FE8J_MAX_INDEXED_ID,
    source_name: str = "indexed source",
) -> Tuple[IndexedMessage, ...]:
    """Parse sequential ``#0xNNNN`` messages.

    Comments and blank lines are accepted only before the first marker.
    Once records start, every marker-like line must be well formed and must
    equal the next sequential identifier.
    """

    messages: List[IndexedMessage] = []
    payload: List[str] = []
    current_id: Optional[int] = None
    marker_line: Optional[int] = None
    expected = 0

    for line_number, line in enumerate(_lines(text), 1):
        match = _HASH_MARKER_RE.fullmatch(line)
        if match:
            value = int(match.group(1), 16)
            if value != expected:
                raise LocaleSourceError(
                    f"{source_name}:{line_number}: expected marker #0x{expected:04X}, "
                    f"got #0x{value:04X}"
                )
            _finish_indexed(messages, current_id, marker_line, payload)
            current_id = value
            marker_line = line_number
            payload = []
            expected += 1
            continue

        if line.startswith("#0x"):
            raise LocaleSourceError(
                f"{source_name}:{line_number}: malformed indexed marker {line!r}"
            )
        if current_id is None:
            if line and not line.startswith(("#", "//")):
                raise LocaleSourceError(
                    f"{source_name}:{line_number}: content before first indexed marker"
                )
            continue
        payload.append(line)

    _finish_indexed(messages, current_id, marker_line, payload)
    expected_count = expected_last_id + 1
    if len(messages) != expected_count:
        raise LocaleSourceError(
            f"{source_name}: expected {expected_count} indexed messages through "
            f"0x{expected_last_id:04X}, got {len(messages)}"
        )
    return tuple(messages)


def _is_canonical_cn_indexed_marker(token: str, value: int) -> bool:
    return len(token) == (2 if value < 0x100 else 4)


def parse_fe8cn(
    text: str,
    *,
    expected_last_id: int = FE8J_MAX_INDEXED_ID,
    source_name: str = "FE8CN source",
) -> ChineseSource:
    """Parse FE8CN indexed messages followed by raw-address records.

    A bracketed hex token is an indexed marker only when it has canonical
    width and equals the next sequential identifier. One-character controls
    such as ``[A]`` therefore remain message payload.
    """

    indexed: List[IndexedMessage] = []
    raw_occurrences: List[RawOccurrence] = []
    indexed_payload: List[str] = []
    raw_payload: List[str] = []
    current_indexed_id: Optional[int] = None
    indexed_marker_line: Optional[int] = None
    current_raw_address: Optional[int] = None
    raw_marker_line: Optional[int] = None
    expected = 0
    in_raw = False

    def finish_raw() -> None:
        if current_raw_address is None or raw_marker_line is None:
            return
        raw_occurrences.append(
            RawOccurrence(
                record_index=len(raw_occurrences),
                address=current_raw_address,
                text="\n".join(raw_payload),
                marker_line=raw_marker_line,
                payload_start_line=raw_marker_line + 1,
            )
        )

    for line_number, line in enumerate(_lines(text), 1):
        raw_match = _CN_RAW_MARKER_RE.fullmatch(line)
        if raw_match:
            if expected != expected_last_id + 1:
                raise LocaleSourceError(
                    f"{source_name}:{line_number}: raw-address records started before "
                    f"indexed marker [{expected_last_id:04X}]"
                )
            if not in_raw:
                _finish_indexed(
                    indexed,
                    current_indexed_id,
                    indexed_marker_line,
                    indexed_payload,
                )
                in_raw = True
            else:
                finish_raw()
            current_raw_address = int(raw_match.group(1), 16)
            raw_marker_line = line_number
            raw_payload = []
            continue

        indexed_match = _CN_INDEXED_MARKER_RE.fullmatch(line)
        if indexed_match:
            token = indexed_match.group(1)
            value = int(token, 16)
            if _is_canonical_cn_indexed_marker(token, value):
                if in_raw:
                    raise LocaleSourceError(
                        f"{source_name}:{line_number}: indexed marker appears after raw records"
                    )
                if value != expected:
                    raise LocaleSourceError(
                        f"{source_name}:{line_number}: expected indexed marker "
                        f"[{expected:02X}]" if expected < 0x100 else
                        f"{source_name}:{line_number}: expected indexed marker "
                        f"[{expected:04X}]"
                    )
                _finish_indexed(
                    indexed,
                    current_indexed_id,
                    indexed_marker_line,
                    indexed_payload,
                )
                current_indexed_id = value
                indexed_marker_line = line_number
                indexed_payload = []
                expected += 1
                continue

        if in_raw:
            if current_raw_address is None:
                raise LocaleSourceError(
                    f"{source_name}:{line_number}: raw payload before an address marker"
                )
            raw_payload.append(line)
        else:
            if current_indexed_id is None:
                raise LocaleSourceError(
                    f"{source_name}:{line_number}: content before first indexed marker"
                )
            indexed_payload.append(line)

    if in_raw:
        finish_raw()
    else:
        _finish_indexed(
            indexed,
            current_indexed_id,
            indexed_marker_line,
            indexed_payload,
        )

    expected_count = expected_last_id + 1
    if len(indexed) != expected_count:
        raise LocaleSourceError(
            f"{source_name}: expected {expected_count} indexed messages through "
            f"0x{expected_last_id:04X}, got {len(indexed)}"
        )
    if not raw_occurrences:
        raise LocaleSourceError(f"{source_name}: no raw-address records found")

    occurrences_by_address: Dict[int, List[RawOccurrence]] = {}
    address_order: List[int] = []
    for occurrence in raw_occurrences:
        if occurrence.address not in occurrences_by_address:
            occurrences_by_address[occurrence.address] = []
            address_order.append(occurrence.address)
        occurrences_by_address[occurrence.address].append(occurrence)

    raw_strings: List[RawString] = []
    for address in address_order:
        occurrences = occurrences_by_address[address]
        texts = {occurrence.text for occurrence in occurrences}
        if len(texts) != 1:
            lines = ", ".join(str(item.marker_line) for item in occurrences)
            raise LocaleSourceError(
                f"{source_name}: duplicate address 0x{address:08X} has conflicting "
                f"payloads at marker lines {lines}"
            )
        raw_strings.append(
            RawString(
                key=f"fe8cn.raw.{address:08X}",
                address=address,
                text=occurrences[0].text,
                occurrences=tuple(occurrences),
            )
        )

    return ChineseSource(tuple(indexed), tuple(raw_occurrences), tuple(raw_strings))


def parse_control_definitions(
    text: str,
    *,
    source_name: str = "control definitions",
) -> Tuple[ControlDefinition, ...]:
    definitions: List[ControlDefinition] = []
    seen = set()
    for line_number, line in enumerate(_lines(text), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _CONTROL_RE.fullmatch(stripped)
        if not match:
            raise LocaleSourceError(
                f"{source_name}:{line_number}: malformed control definition {line!r}"
            )
        name = match.group(1)
        if name in seen:
            raise LocaleSourceError(
                f"{source_name}:{line_number}: duplicate control token [{name}]"
            )
        raw_values = [item for item in re.split(r"[\s,]+", match.group(2).strip()) if item]
        try:
            values = tuple(int(item, 0) for item in raw_values)
        except ValueError as error:
            raise LocaleSourceError(
                f"{source_name}:{line_number}: invalid control value"
            ) from error
        if not values or any(value < 0 or value > 0xFFFF for value in values):
            raise LocaleSourceError(
                f"{source_name}:{line_number}: control values must be u16 integers"
            )
        seen.add(name)
        definitions.append(ControlDefinition(name, values, line_number))
    if not definitions:
        raise LocaleSourceError(f"{source_name}: no control definitions found")
    return tuple(definitions)


def parse_mapping_seed_tsv(
    text: str,
    *,
    source_name: str = "mapping seed",
) -> Tuple[MappingSeedRow, ...]:
    rows: List[MappingSeedRow] = []
    previous_target: Optional[int] = None
    seen_targets = set()

    for line_number, line in enumerate(_lines(text), 1):
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 3:
            raise LocaleSourceError(
                f"{source_name}:{line_number}: expected three tab-separated fields"
            )
        target_token, source_token, tag = fields
        if not _HEX4_RE.fullmatch(target_token) or not _HEX4_RE.fullmatch(source_token):
            raise LocaleSourceError(
                f"{source_name}:{line_number}: ids must be four hexadecimal digits"
            )
        if not tag:
            raise LocaleSourceError(
                f"{source_name}:{line_number}: provenance tag must not be empty"
            )
        target_id = int(target_token, 16)
        source_id = int(source_token, 16)
        if source_id > FE8J_MAX_INDEXED_ID:
            raise LocaleSourceError(
                f"{source_name}:{line_number}: FE8J source id 0x{source_id:04X} "
                f"exceeds 0x{FE8J_MAX_INDEXED_ID:04X}"
            )
        if target_id in seen_targets:
            raise LocaleSourceError(
                f"{source_name}:{line_number}: duplicate FE8U target 0x{target_id:04X}"
            )
        if previous_target is not None and target_id <= previous_target:
            raise LocaleSourceError(
                f"{source_name}:{line_number}: FE8U targets must be strictly ascending"
            )
        seen_targets.add(target_id)
        previous_target = target_id
        rows.append(MappingSeedRow(target_id, source_id, tag, line_number))

    if not rows:
        raise LocaleSourceError(f"{source_name}: no mapping rows found")
    return tuple(rows)
