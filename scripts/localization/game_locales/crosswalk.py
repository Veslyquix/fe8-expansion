"""Evidence-first FE8U-target to FE8J-layout crosswalk generation."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from .mapping import (
    MappingError,
    format_message_id,
    validate_mapping_document,
    validate_source_provider,
)
from .parsers import FE8J_MAX_INDEXED_ID

EVIDENCE_SCHEMA_VERSION = 1
EVIDENCE_KIND = "fe8u-fe8j-structural-evidence"
RELEASE_MAP_NOTE = (
    "Authoritative FE8U-target decisions generated only from committed structural "
    "evidence. Candidate/interpolated rows never create a mapping."
)
CONFIDENCE_LEVELS = ("high", "manual")
FALLBACK_REASONS = (
    "dummy",
    "expansion-only",
    "not-yet-verified",
    "region-only",
    "unreferenced",
)

_HEX_OR_DEC_RE = re.compile(r"^(?:0[xX][0-9A-Fa-f]+|[0-9]+)$")
_SCRIPT_DEF_RE = re.compile(
    r"\b(?:EventListScr|EventScr)\s+([A-Za-z_][A-Za-z0-9_]*)"
    r"\s*(?:\[[^\]]*\])?\s*(?:__attribute__\([^=;]*\)\s*)?=\s*\{"
)
_MESSAGE_MACRO_RE = re.compile(
    r"\b(?:TEXTSHOW|Text|BROWNBOXTEXT)\s*\(\s*"
    r"(0[xX][0-9A-Fa-f]+|[0-9]+)"
)
_TEXT_BG_RE = re.compile(
    r"\bText_BG\s*\(\s*[^,]+,\s*(0[xX][0-9A-Fa-f]+|[0-9]+)"
)
_SLOT3_BG_RE = re.compile(
    r"SVAL\s*\(\s*EVT_SLOT_3\s*,\s*(0[xX][0-9A-Fa-f]+|[0-9]+)\s*\)"
    r"(?:(?!SVAL).){0,240}?CALL\s*\([^\n]*Event_TextWithBG[^\n]*\)",
    re.DOTALL,
)
_WM_MESSAGE_RE = re.compile(
    r"\b(?:TEXTSHOW|WM_TEXT)\s*\(\s*(0[xX][0-9A-Fa-f]+|[0-9]+)"
)


class CrosswalkError(MappingError):
    """Raised when structural evidence cannot produce an honest release map."""


@dataclass(frozen=True)
class EvidenceRecord:
    target_id: int
    source: Dict[str, Any]
    subsystem: str
    evidence_kind: str
    source_table: str
    source_symbol: str
    source_key: str
    confidence: str
    source_paths: Dict[str, str]
    rationale: str

    def to_json(self) -> Dict[str, Any]:
        return {
            "confidence": self.confidence,
            "evidence_kind": self.evidence_kind,
            "rationale": self.rationale,
            "source": self.source,
            "source_key": self.source_key,
            "source_paths": self.source_paths,
            "source_symbol": self.source_symbol,
            "source_table": self.source_table,
            "subsystem": self.subsystem,
            "target_id": format_message_id(self.target_id),
        }


def canonical_json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _parse_int(value: str) -> int:
    value = value.strip()
    if not _HEX_OR_DEC_RE.fullmatch(value):
        raise CrosswalkError(f"expected integer literal, got {value!r}")
    return int(value, 0)


def _scan_balanced(text: str, opening: int) -> Tuple[str, int]:
    if text[opening] != "{":
        raise CrosswalkError("balanced scan must start at an opening brace")
    depth = 0
    quote: Optional[str] = None
    escaped = False
    in_line_comment = False
    in_block_comment = False
    index = opening
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char == "/" and next_char == "/":
            in_line_comment = True
            index += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue
        if char in ('"', "'"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : index], index + 1
        index += 1
    raise CrosswalkError("unterminated brace-delimited source block")


def _find_named_array_body(text: str, symbol: str) -> str:
    match = re.search(rf"\b{re.escape(symbol)}\s*\[[^\]]*\][^=;]*=\s*\{{", text)
    if not match:
        raise CrosswalkError(f"could not find array definition {symbol}")
    opening = text.find("{", match.start())
    return _scan_balanced(text, opening)[0]


def _top_level_entries(body: str) -> List[str]:
    entries: List[str] = []
    index = 0
    while index < len(body):
        if body[index] == "{":
            entry, index = _scan_balanced(body, index)
            entries.append(entry)
        else:
            index += 1
    return entries


def _split_c_fields(body: str) -> List[str]:
    fields: List[str] = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0}
    closers = {")": "(", "]": "[", "}": "{"}
    quote: Optional[str] = None
    escaped = False
    for index, char in enumerate(body):
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
        elif char in depths:
            depths[char] += 1
        elif char in closers:
            depths[closers[char]] -= 1
        elif char == "," and all(depth == 0 for depth in depths.values()):
            fields.append(body[start:index].strip())
            start = index + 1
    tail = body[start:].strip()
    if tail:
        fields.append(tail)
    return fields


def _field_value(body: str, field: str) -> Optional[int]:
    match = re.search(
        rf"\.{re.escape(field)}\s*=\s*(0[xX][0-9A-Fa-f]+|[0-9]+)", body
    )
    return _parse_int(match.group(1)) if match else None


def _parse_designated_table(
    path: Path, key_prefix: str, fields: Sequence[str]
) -> Dict[str, Dict[str, int]]:
    text = path.read_text(encoding="utf-8")
    result: Dict[str, Dict[str, int]] = {}
    pattern = re.compile(
        rf"\[\s*({re.escape(key_prefix)}[A-Za-z0-9_]+)(?:\s*-\s*1)?\s*\]\s*=\s*\{{"
    )
    for match in pattern.finditer(text):
        opening = text.find("{", match.start())
        body, _ = _scan_balanced(text, opening)
        values = {
            field: value
            for field in fields
            if (value := _field_value(body, field)) is not None
        }
        result[match.group(1)] = values
    if not result:
        raise CrosswalkError(f"{path}: no {key_prefix} designated rows found")
    return result


def _indexed_source(source_id: int) -> Dict[str, Any]:
    if source_id < 0 or source_id > FE8J_MAX_INDEXED_ID:
        raise CrosswalkError(
            f"FE8J indexed source {format_message_id(source_id)} is outside range"
        )
    return {"id": format_message_id(source_id), "kind": "indexed", "layout": "FE8J"}


def _raw_source(
    import_id: str,
    *,
    ja_symbol: str,
    alternate_import_ids: Sequence[str] = (),
) -> Dict[str, Any]:
    source: Dict[str, Any] = {
        "import_id": import_id,
        "kind": "raw",
        "regional_sources": {
            "ja": {"kind": "symbol", "symbol": ja_symbol},
            "zh-Hans": {"import_id": import_id, "kind": "import"},
        },
    }
    if alternate_import_ids:
        source["alternate_import_ids"] = list(alternate_import_ids)
    return source


def _record(
    target_id: int,
    source: Dict[str, Any],
    *,
    subsystem: str,
    evidence_kind: str,
    source_table: str,
    source_symbol: str,
    source_key: str,
    source_paths: Mapping[str, str],
    rationale: str,
    confidence: str = "high",
) -> EvidenceRecord:
    return EvidenceRecord(
        target_id=target_id,
        source=source,
        subsystem=subsystem,
        evidence_kind=evidence_kind,
        source_table=source_table,
        source_symbol=source_symbol,
        source_key=source_key,
        confidence=confidence,
        source_paths=dict(source_paths),
        rationale=rationale,
    )


def _logical_paths(fe8u_path: Path, fe8j_path: Path) -> Dict[str, str]:
    return {"fe8j": str(fe8j_path), "fe8u": str(fe8u_path)}


def _harvest_keyed_entities(
    fe8u_root: Path, fe8j_root: Path
) -> Tuple[List[EvidenceRecord], List[Path]]:
    records: List[EvidenceRecord] = []
    files: List[Path] = []
    families = (
        (
            "characters",
            "CHARACTER_",
            "gCharacterData",
            ("nameTextId", "descTextId"),
            fe8u_root / "src/data_characters.c",
            fe8j_root / "src/data/data_characters.c",
        ),
        (
            "classes",
            "CLASS_",
            "gClassData",
            ("nameTextId", "descTextId"),
            fe8u_root / "src/data_classes.c",
            fe8j_root / "src/data/data_classes.c",
        ),
        (
            "items",
            "ITEM_",
            "gItemData",
            ("nameTextId", "descTextId", "useDescTextId"),
            fe8u_root / "src/data_items.c",
            fe8j_root / "src/data/data_items.c",
        ),
    )
    for subsystem, prefix, table, fields, fe8u_path, fe8j_path in families:
        files.extend((fe8u_path, fe8j_path))
        fe8u_rows = _parse_designated_table(fe8u_path, prefix, fields)
        fe8j_rows = _parse_designated_table(fe8j_path, prefix, fields)
        for key in sorted(set(fe8u_rows) & set(fe8j_rows)):
            for field in fields:
                target_id = fe8u_rows[key].get(field, 0)
                source_id = fe8j_rows[key].get(field, 0)
                if not target_id or not source_id:
                    continue
                records.append(
                    _record(
                        target_id,
                        _indexed_source(source_id),
                        subsystem=subsystem,
                        evidence_kind="shared-keyed-table",
                        source_table=table,
                        source_symbol=table,
                        source_key=f"{key}.{field}",
                        source_paths=_logical_paths(
                            Path(fe8u_path.relative_to(fe8u_root)),
                            Path(fe8j_path.relative_to(fe8j_root)),
                        ),
                        rationale="The same named row and field identify the semantic slot.",
                    )
                )
    return records, files


def _parse_chapter_rows(path: Path) -> Dict[str, Dict[str, int]]:
    text = path.read_text(encoding="utf-8")
    body = _find_named_array_body(text, "gChapterDataTable")
    result: Dict[str, Dict[str, int]] = {}
    for entry in _top_level_entries(body):
        name_match = re.search(r'\.internalName\s*=\s*"([^"]+)"', entry)
        if not name_match:
            continue
        result[name_match.group(1)] = {
            field: value
            for field in ("chapTitleTextId", "statusObjectiveTextId", "goalWindowTextId")
            if (value := _field_value(entry, field)) is not None
        }
    return result


def _harvest_chapters(
    fe8u_root: Path, fe8j_root: Path
) -> Tuple[List[EvidenceRecord], List[Path]]:
    fe8u_path = fe8u_root / "src/data/chapter_settings.json"
    fe8j_path = fe8j_root / "src/data/chapter_settings.h"
    fe8u_data = json.loads(fe8u_path.read_text(encoding="utf-8"))
    fe8u_rows = {
        row["internalName"]: {
            "chapTitleTextId": row.get("chapTitleTextId", 0),
            "statusObjectiveTextId": row.get("goal", {}).get(
                "statusObjectiveTextId", 0
            ),
            "goalWindowTextId": row.get("goal", {}).get("windowTextId", 0),
        }
        for row in fe8u_data["chapters"]
    }
    fe8j_rows = _parse_chapter_rows(fe8j_path)
    records: List[EvidenceRecord] = []
    paths = _logical_paths(
        Path(fe8u_path.relative_to(fe8u_root)),
        Path(fe8j_path.relative_to(fe8j_root)),
    )
    for key in sorted(set(fe8u_rows) & set(fe8j_rows)):
        for field in ("chapTitleTextId", "statusObjectiveTextId", "goalWindowTextId"):
            target_id = fe8u_rows[key].get(field, 0)
            source_id = fe8j_rows[key].get(field, 0)
            if not target_id or not source_id:
                continue
            records.append(
                _record(
                    target_id,
                    _indexed_source(source_id),
                    subsystem="chapters",
                    evidence_kind="shared-keyed-table",
                    source_table="gChapterDataTable",
                    source_symbol="gChapterDataTable",
                    source_key=f"{key}.{field}",
                    source_paths=paths,
                    rationale="The shared internalName and field identify the chapter slot.",
                )
            )
    return records, [fe8u_path, fe8j_path]


def _parse_support_rows(path: Path) -> Dict[Tuple[str, str], Tuple[int, int, int]]:
    body = _find_named_array_body(path.read_text(encoding="utf-8"), "gSupportTalkList")
    result: Dict[Tuple[str, str], Tuple[int, int, int]] = {}
    pattern = re.compile(
        r"\{\s*(CHARACTER_[A-Za-z0-9_]+)\s*,\s*"
        r"(CHARACTER_[A-Za-z0-9_]+)\s*,\s*"
        r"(0[xX][0-9A-Fa-f]+)\s*,\s*(0[xX][0-9A-Fa-f]+)\s*,\s*"
        r"(0[xX][0-9A-Fa-f]+)"
    )
    for match in pattern.finditer(body):
        pair = tuple(sorted((match.group(1), match.group(2))))
        result[pair] = tuple(_parse_int(match.group(index)) for index in (3, 4, 5))
    return result


def _harvest_supports(
    fe8u_root: Path, fe8j_root: Path
) -> Tuple[List[EvidenceRecord], List[Path]]:
    fe8u_path = fe8u_root / "src/data_event_trigger.c"
    fe8j_path = (
        fe8j_root / "src/data/gSupportTalkList_ref/dat_gSupportTalkList_ref.c"
    )
    fe8u_rows = _parse_support_rows(fe8u_path)
    fe8j_rows = _parse_support_rows(fe8j_path)
    records: List[EvidenceRecord] = []
    paths = _logical_paths(
        Path(fe8u_path.relative_to(fe8u_root)),
        Path(fe8j_path.relative_to(fe8j_root)),
    )
    for pair in sorted(set(fe8u_rows) & set(fe8j_rows)):
        for rank, target_id, source_id in zip(
            ("C", "B", "A"), fe8u_rows[pair], fe8j_rows[pair]
        ):
            records.append(
                _record(
                    target_id,
                    _indexed_source(source_id),
                    subsystem="supports",
                    evidence_kind="shared-keyed-table",
                    source_table="gSupportTalkList",
                    source_symbol="gSupportTalkList",
                    source_key=f"{pair[0]}+{pair[1]}.{rank}",
                    source_paths=paths,
                    rationale="The shared character pair and support rank identify the dialogue.",
                )
            )
    return records, [fe8u_path, fe8j_path]


def _parse_script_definitions(paths: Iterable[Path]) -> Dict[str, Tuple[str, Path]]:
    definitions: Dict[str, Tuple[str, Path]] = {}
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        for match in _SCRIPT_DEF_RE.finditer(text):
            opening = text.find("{", match.start())
            body, _ = _scan_balanced(text, opening)
            definitions[match.group(1)] = (body, path)
    return definitions


def _macro_message_ids(body: str) -> List[int]:
    matches: List[Tuple[int, int]] = []
    for match in _MESSAGE_MACRO_RE.finditer(body):
        value = _parse_int(match.group(1))
        if value != 0xFFFF:
            matches.append((match.start(), value))
    for match in _TEXT_BG_RE.finditer(body):
        value = _parse_int(match.group(1))
        if value != 0xFFFF:
            matches.append((match.start(), value))
    for match in _SLOT3_BG_RE.finditer(body):
        value = _parse_int(match.group(1))
        if value != 0xFFFF:
            matches.append((match.start(), value))
    return [value for _, value in sorted(matches)]


def _harvest_event_scripts(
    fe8u_root: Path, fe8j_root: Path
) -> Tuple[List[EvidenceRecord], List[Dict[str, Any]], List[Path]]:
    fe8u_paths = [
        path
        for path in (fe8u_root / "src/events").rglob("*")
        if path.suffix in (".c", ".h")
    ]
    fe8j_paths = list((fe8j_root / "src/data").glob("EventScr_*_ref/*.c"))
    fe8u_defs = _parse_script_definitions(fe8u_paths)
    fe8j_defs = _parse_script_definitions(fe8j_paths)
    records: List[EvidenceRecord] = []
    gaps: List[Dict[str, Any]] = []
    manual_script_ids = {
        "EventScr_Ch1Tut_EirikaVisitHouseInit": [0x08EE, 0x08FE],
        "EventScr_Ch1Tut_OnBeginning": [0x0903, 0x08EF],
        "EventScr_Prologue_OneEnemyLeft": [0x08D3],
    }
    manual_ordinals = {
        ("EventScr_Ch1Tut_EirikaVisitHouseInit", 2),
        ("EventScr_Ch1Tut_OnBeginning", 2),
        ("EventScr_Prologue_OneEnemyLeft", 1),
    }
    for symbol in sorted(set(fe8u_defs) & set(fe8j_defs)):
        fe8u_body, fe8u_path = fe8u_defs[symbol]
        fe8j_body, fe8j_path = fe8j_defs[symbol]
        fe8u_ids = _macro_message_ids(fe8u_body)
        fe8j_ids = manual_script_ids.get(symbol, _macro_message_ids(fe8j_body))
        if not fe8u_ids and not fe8j_ids:
            continue
        if len(fe8u_ids) != len(fe8j_ids):
            gaps.append(
                {
                    "fe8j_slot_count": len(fe8j_ids),
                    "fe8u_slot_count": len(fe8u_ids),
                    "reason": "split-merge-manual-review",
                    "source_key": symbol,
                    "subsystem": "events",
                }
            )
            continue
        paths = _logical_paths(
            Path(fe8u_path.relative_to(fe8u_root)),
            Path(fe8j_path.relative_to(fe8j_root)),
        )
        for ordinal, (target_id, source_id) in enumerate(
            zip(fe8u_ids, fe8j_ids), start=1
        ):
            manual = (symbol, ordinal) in manual_ordinals
            records.append(
                _record(
                    target_id,
                    _indexed_source(source_id),
                    subsystem="events",
                    evidence_kind=(
                        "manual-raw-opcode-review" if manual else "shared-script-slot"
                    ),
                    source_table="event-script",
                    source_symbol=symbol,
                    source_key=f"{symbol}.text[{ordinal}]",
                    source_paths=paths,
                    rationale=(
                        "The raw EVENT_WORD_SYM address resolves to this TEXTSHOW ID."
                        if manual
                        else "The same named event script and text ordinal identify the slot."
                    ),
                    confidence="manual" if manual else "high",
                )
            )
    return records, gaps, fe8u_paths + fe8j_paths


def _wm_raw_message_ids(body: str) -> List[int]:
    words = [_parse_int(value) for value in re.findall(r"0[xX][0-9A-Fa-f]+", body)]
    result: List[int] = []
    for index, word in enumerate(words):
        if word & 0xFFFF == 0x1B20:
            result.append((word >> 16) & 0xFFFF)
        elif word == 0x0000C640 and index + 1 < len(words):
            result.append(words[index + 1] & 0xFFFF)
    return result


def _harvest_world_map(
    fe8u_root: Path, fe8j_root: Path
) -> Tuple[List[EvidenceRecord], List[Dict[str, Any]], List[Path]]:
    fe8u_paths = list((fe8u_root / "src/events").glob("*-wm.h"))
    messed = fe8u_root / "src/events/messed-eventscr-wm.h"
    if messed.exists():
        fe8u_paths.append(messed)
    fe8j_path = fe8j_root / "src/events_wm.c"
    fe8u_defs = _parse_script_definitions(fe8u_paths)
    fe8j_defs = _parse_script_definitions([fe8j_path])
    records: List[EvidenceRecord] = []
    gaps: List[Dict[str, Any]] = []
    for symbol in sorted(set(fe8u_defs) & set(fe8j_defs)):
        if not symbol.startswith("EventScrWM_"):
            continue
        fe8u_body, fe8u_path = fe8u_defs[symbol]
        fe8j_body, _ = fe8j_defs[symbol]
        fe8u_ids = [_parse_int(match.group(1)) for match in _WM_MESSAGE_RE.finditer(fe8u_body)]
        fe8j_ids = _wm_raw_message_ids(fe8j_body)
        if not fe8u_ids and not fe8j_ids:
            continue
        if len(fe8u_ids) != len(fe8j_ids):
            gaps.append(
                {
                    "fe8j_slot_count": len(fe8j_ids),
                    "fe8u_slot_count": len(fe8u_ids),
                    "reason": "raw-opcode-slot-count-mismatch",
                    "source_key": symbol,
                    "subsystem": "world-map",
                }
            )
            continue
        paths = _logical_paths(
            Path(fe8u_path.relative_to(fe8u_root)),
            Path(fe8j_path.relative_to(fe8j_root)),
        )
        for ordinal, (target_id, source_id) in enumerate(
            zip(fe8u_ids, fe8j_ids), start=1
        ):
            records.append(
                _record(
                    target_id,
                    _indexed_source(source_id),
                    subsystem="world-map",
                    evidence_kind="shared-script-slot",
                    source_table="world-map-event-script",
                    source_symbol=symbol,
                    source_key=f"{symbol}.text[{ordinal}]",
                    source_paths=paths,
                    rationale="The same named world-map script and decoded text ordinal match.",
                )
            )
    return records, gaps, fe8u_paths + [fe8j_path]


def _parse_positional_menu(path: Path, symbol: str) -> List[Tuple[int, int, int]]:
    body = _find_named_array_body(path.read_text(encoding="utf-8"), symbol)
    rows: List[Tuple[int, int, int]] = []
    for entry in _top_level_entries(body):
        fields = _split_c_fields(entry)
        if len(fields) < 5:
            continue
        try:
            rows.append(
                (_parse_int(fields[1]), _parse_int(fields[2]), _parse_int(fields[4]))
            )
        except CrosswalkError:
            continue
    return rows


def _parse_designated_menu(path: Path, symbol: str) -> List[Tuple[int, int, int]]:
    body = _find_named_array_body(path.read_text(encoding="utf-8"), symbol)
    rows: List[Tuple[int, int, int]] = []
    for entry in _top_level_entries(body):
        name_id = _field_value(entry, "nameMsgId")
        help_id = _field_value(entry, "helpMsgId")
        override_id = _field_value(entry, "overrideId")
        if name_id is None or help_id is None or override_id is None:
            continue
        rows.append((name_id, help_id, override_id))
    return rows


def _parse_raw_menu_words(path: Path, symbol: str, count: int) -> List[Tuple[int, int]]:
    body = _find_named_array_body(path.read_text(encoding="utf-8"), symbol)
    values = [line.strip().rstrip(",") for line in body.splitlines() if line.strip()]
    rows: List[Tuple[int, int]] = []
    for index in range(count):
        packed = _parse_int(values[index * 9 + 1])
        rows.append((packed & 0xFFFF, packed >> 16))
    return rows


def _parse_asm_menu_words(path: Path, count: int) -> List[Tuple[int, int]]:
    values = [
        match.group(1)
        for match in re.finditer(
            r"^\s*\.4byte\s+([^\s,]+)",
            path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    ]
    rows: List[Tuple[int, int]] = []
    for index in range(count):
        packed = _parse_int(values[index * 9 + 1])
        rows.append((packed & 0xFFFF, packed >> 16))
    return rows


def _load_raw_records(path: Path) -> Dict[str, Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    records = {row["import_id"]: row for row in data["records"]}
    if len(records) != data["unique_import_count"]:
        raise CrosswalkError(f"{path}: raw import IDs are not unique")
    return records


def _harvest_menus(
    fe8u_root: Path, fe8j_root: Path, raw_path: Path
) -> Tuple[List[EvidenceRecord], List[Dict[str, Any]], List[Path]]:
    fe8u_menu = fe8u_root / "src/menu_def.c"
    fe8j_menu = fe8j_root / "src/menu_def.c"
    fe8u_world = fe8u_root / "src/worldmap_path.c"
    fe8j_item = (
        fe8j_root / "src/data/frontier_df4_uistuff/frontier_df4_uistuff.c"
    )
    fe8j_wm_general = (
        fe8j_root
        / "src/data/MenuItemDef_WMGeneralMenu_ref/dat_MenuItemDef_WMGeneralMenu_ref.s"
    )
    fe8j_wm_node = (
        fe8j_root
        / "src/data/MenuItemDef_WMNodeMenu_ref/dat_MenuItemDef_WMNodeMenu_ref.s"
    )
    raw_records = _load_raw_records(raw_path)
    records: List[EvidenceRecord] = []
    gaps: List[Dict[str, Any]] = []

    table_specs = (
        (
            "gYesNoSelectionMenuItems",
            _parse_positional_menu(fe8u_menu, "gYesNoSelectionMenuItems"),
            _parse_positional_menu(fe8j_menu, "gYesNoSelectionMenuItems"),
            17,
            "gMenuStr_12C/gMenuStr_124",
            fe8u_menu,
            fe8j_menu,
        ),
        (
            "gItemSubMenuItems",
            _parse_positional_menu(fe8u_menu, "gItemSubMenuItems"),
            [
                (name, help_id, 0x34 + index)
                for index, (name, help_id) in enumerate(
                    _parse_raw_menu_words(
                        fe8j_item, "frontier_df4_uistuff_029_5C4A94", 4
                    )
                )
            ],
            19,
            "gMenuStr_14C..gMenuStr_134",
            fe8u_menu,
            fe8j_item,
        ),
        (
            "gUnitActionMenuItems",
            _parse_positional_menu(fe8u_menu, "gUnitActionMenuItems"),
            _parse_positional_menu(fe8j_menu, "gUnitActionMenuItems"),
            23,
            "gMenuStr_25C..gMenuStr_154",
            fe8u_menu,
            fe8j_menu,
        ),
    )
    raw_by_target: MutableMapping[int, Tuple[str, str]] = {}
    for table, fe8u_rows, fe8j_rows, raw_base, ja_symbol, fe8u_path, fe8j_path in table_specs:
        if len(fe8u_rows) != len(fe8j_rows):
            raise CrosswalkError(f"{table}: FE8U/FE8J row counts differ")
        paths = _logical_paths(
            Path(fe8u_path.relative_to(fe8u_root)),
            Path(fe8j_path.relative_to(fe8j_root)),
        )
        for ordinal, (fe8u_row, fe8j_row) in enumerate(
            zip(fe8u_rows, fe8j_rows)
        ):
            target_name, target_help, override_id = fe8u_row
            source_name, source_help, source_override = fe8j_row
            if override_id != source_override:
                raise CrosswalkError(
                    f"{table}[{ordinal}]: override IDs differ "
                    f"{override_id:#x}/{source_override:#x}"
                )
            import_id = f"fe8cn.raw.import-{raw_base + ordinal:04d}"
            raw_text = raw_records[import_id]["text"]
            if target_name:
                previous = raw_by_target.get(target_name)
                if previous and previous[1] != raw_text:
                    gaps.append(
                        {
                            "reason": "region-only-split-merge",
                            "source_key": format_message_id(target_name),
                            "subsystem": "menus",
                            "targets": [previous[0], import_id],
                        }
                    )
                elif not previous:
                    raw_by_target[target_name] = (import_id, raw_text)
                    records.append(
                        _record(
                            target_name,
                            _raw_source(import_id, ja_symbol=ja_symbol),
                            subsystem="menus",
                            evidence_kind="regional-raw-table",
                            source_table=table,
                            source_symbol=table,
                            source_key=f"{table}.override[{override_id:#x}].name",
                            source_paths=paths,
                            rationale=(
                                "The shared menu row selects a direct regional string; "
                                "the stable import ID is runtime identity."
                            ),
                        )
                    )
            if target_help and source_help:
                records.append(
                    _record(
                        target_help,
                        _indexed_source(source_help),
                        subsystem="menus",
                        evidence_kind="shared-keyed-table",
                        source_table=table,
                        source_symbol=table,
                        source_key=f"{table}.override[{override_id:#x}].help",
                        source_paths=paths,
                        rationale="The shared menu override ID identifies the help slot.",
                    )
                )

    map_rows = _parse_positional_menu(fe8u_menu, "gMapMenuItems")
    for ordinal, (target_name, _, override_id) in enumerate(map_rows):
        import_id = f"fe8cn.raw.import-{52 + ordinal:04d}"
        records.append(
            _record(
                target_name,
                _raw_source(import_id, ja_symbol=f"gMapMenuItems[{ordinal}].name"),
                subsystem="menus",
                evidence_kind="regional-raw-table",
                source_table="gMapMenuItems",
                source_symbol="gMapMenuItems",
                source_key=f"gMapMenuItems.override[{override_id:#x}].name",
                source_paths={"fe8j": "src/menu_def.c raw string pool", "fe8u": "src/menu_def.c"},
                rationale="The stable FE8CN raw import order mirrors the named map menu rows.",
            )
        )

    wm_specs = (
        (
            "MenuItemDef_WMGeneralMenu",
            5,
            65,
            fe8j_wm_general,
        ),
        ("MenuItemDef_WMNodeMenu", 4, 70, fe8j_wm_node),
    )
    for table, count, raw_base, fe8j_path in wm_specs:
        fe8u_rows = _parse_designated_menu(fe8u_world, table)
        fe8j_rows = _parse_asm_menu_words(fe8j_path, count)
        if len(fe8u_rows) != count:
            raise CrosswalkError(f"{table}: expected {count} FE8U rows")
        paths = _logical_paths(
            Path(fe8u_world.relative_to(fe8u_root)),
            Path(fe8j_path.relative_to(fe8j_root)),
        )
        for ordinal, ((target_name, target_help, override_id), (_, source_help)) in enumerate(
            zip(fe8u_rows, fe8j_rows)
        ):
            import_id = f"fe8cn.raw.import-{raw_base + ordinal:04d}"
            records.append(
                _record(
                    target_name,
                    _raw_source(
                        import_id, ja_symbol=f"sGmapRouteMenuText:{table}[{ordinal}]"
                    ),
                    subsystem="menus",
                    evidence_kind="regional-raw-table",
                    source_table=table,
                    source_symbol=table,
                    source_key=f"{table}.override[{override_id:#x}].name",
                    source_paths=paths,
                    rationale="The shared world-map menu row selects the direct regional string.",
                )
            )
            records.append(
                _record(
                    target_help,
                    _indexed_source(source_help),
                    subsystem="menus",
                    evidence_kind="shared-keyed-table",
                    source_table=table,
                    source_symbol=table,
                    source_key=f"{table}.override[{override_id:#x}].help",
                    source_paths=paths,
                    rationale="The shared world-map menu override identifies the help slot.",
                )
            )
    return records, gaps, [
        fe8u_menu,
        fe8j_menu,
        fe8u_world,
        fe8j_item,
        fe8j_wm_general,
        fe8j_wm_node,
        raw_path,
    ]


def _harvest_terrain(
    fe8u_root: Path, fe8j_root: Path, raw_path: Path
) -> Tuple[List[EvidenceRecord], List[Path]]:
    fe8u_path = fe8u_root / "src/data_terrains.c"
    fe8j_path = fe8j_root / "src/data/data_088617C8/data_088617C8.s"
    raw_records = _load_raw_records(raw_path)
    body = _find_named_array_body(fe8u_path.read_text(encoding="utf-8"), "gTerrains_0")
    rows = [
        (match.group(1), _parse_int(match.group(2)))
        for match in re.finditer(
            r"\[\s*(TERRAIN_[A-Za-z0-9_]+)\s*\]\s*=\s*"
            r"(0[xX][0-9A-Fa-f]+|[0-9]+)",
            body,
        )
    ]
    if len(rows) != 65:
        raise CrosswalkError(f"gTerrains_0: expected 65 rows, found {len(rows)}")
    records: List[EvidenceRecord] = []
    paths = _logical_paths(
        Path(fe8u_path.relative_to(fe8u_root)),
        Path(fe8j_path.relative_to(fe8j_root)),
    )
    for terrain_id, (terrain_key, target_id) in enumerate(rows):
        import_id = f"fe8cn.raw.import-{74 + terrain_id:04d}"
        if import_id not in raw_records:
            raise CrosswalkError(f"missing terrain raw import {import_id}")
        records.append(
            _record(
                target_id,
                _raw_source(
                    import_id, ja_symbol=f"gTerrainNames[{terrain_key}]"
                ),
                subsystem="terrain",
                evidence_kind="regional-raw-table",
                source_table="gTerrains_0/gTerrainNames",
                source_symbol="gTerrainNames",
                source_key=terrain_key,
                source_paths=paths,
                rationale="The shared terrain enum index selects a direct regional string.",
            )
        )
    return records, [fe8u_path, fe8j_path, raw_path]


def _elf_symbols(path: Path, names: Sequence[str]) -> Dict[str, int]:
    errors = []
    for tool in ("arm-none-eabi-nm", "nm"):
        try:
            result = subprocess.run(
                [tool, "-n", str(path)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as error:
            errors.append(str(error))
            continue
        if result.returncode != 0:
            errors.append(result.stderr.strip())
            continue
        symbols = {}
        wanted = set(names)
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 3 and fields[-1] in wanted:
                symbols[fields[-1]] = int(fields[0], 16)
        if set(symbols) == wanted:
            return symbols
    raise CrosswalkError(
        f"{path}: could not resolve symbols {', '.join(names)}: {'; '.join(errors)}"
    )


def _tsv_symbol(path: Path, name: str) -> int:
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if fields and fields[0] == name:
            return int(fields[1], 16)
    raise CrosswalkError(f"{path}: missing symbol {name}")


def _rom_offset(address: int) -> int:
    if address < 0x08000000:
        raise CrosswalkError(f"ROM address 0x{address:08X} is below cartridge space")
    return address - 0x08000000


def _battle_rows(rom: bytes, address: int) -> List[Tuple[Tuple[int, ...], int]]:
    rows: List[Tuple[Tuple[int, ...], int]] = []
    offset = _rom_offset(address)
    for index in range(1024):
        pid_a, pid_b, chapter, flag, msg, _event = struct.unpack_from(
            "<HHHHH2xI", rom, offset + index * 16
        )
        if pid_a == 0xFFFF:
            return rows
        rows.append(((pid_a, pid_b, chapter, flag), msg))
    raise CrosswalkError("battle talk table terminator was not found")


def _defeat_rows(rom: bytes, address: int) -> List[Tuple[Tuple[int, ...], int]]:
    rows: List[Tuple[Tuple[int, ...], int]] = []
    offset = _rom_offset(address)
    for index in range(1024):
        pid, route, chapter, flag, msg, _event = struct.unpack_from(
            "<HBBHHI", rom, offset + index * 12
        )
        if pid == 0xFFFF:
            return rows
        rows.append(((pid, route, chapter, flag), msg))
    raise CrosswalkError("defeat talk table terminator was not found")


def _harvest_battle_defeat(
    fe8u_root: Path, fe8j_root: Path
) -> Tuple[List[EvidenceRecord], List[Path]]:
    fe8u_rom = fe8u_root / "fireemblem8.gba"
    fe8u_elf = fe8u_root / "fireemblem8.elf"
    fe8j_rom = fe8j_root / "baserom.gba"
    fe8j_symbols = (
        fe8j_root / "layout/baseline_syms.d/code_8086934-cfe2cbce.tsv"
    )
    fe8u_addresses = _elf_symbols(
        fe8u_elf, ("gBattleTalkList", "gDefeatTalkList")
    )
    fe8j_addresses = {
        name: _tsv_symbol(fe8j_symbols, name)
        for name in ("gBattleTalkList", "gDefeatTalkList")
    }
    fe8u_bytes = fe8u_rom.read_bytes()
    fe8j_bytes = fe8j_rom.read_bytes()
    records: List[EvidenceRecord] = []
    specs = (
        (
            "battle-quotes",
            "gBattleTalkList",
            _battle_rows,
            ("pidA", "pidB", "chapter", "flag"),
        ),
        (
            "defeat-quotes",
            "gDefeatTalkList",
            _defeat_rows,
            ("pid", "route", "chapter", "flag"),
        ),
    )
    paths = _logical_paths(
        Path(fe8u_rom.relative_to(fe8u_root)),
        Path(fe8j_rom.relative_to(fe8j_root)),
    )
    for subsystem, symbol, parser, key_names in specs:
        fe8u_rows = parser(fe8u_bytes, fe8u_addresses[symbol])
        fe8j_rows = parser(fe8j_bytes, fe8j_addresses[symbol])
        if len(fe8u_rows) != len(fe8j_rows):
            raise CrosswalkError(
                f"{symbol}: FE8U/FE8J row counts differ "
                f"{len(fe8u_rows)}/{len(fe8j_rows)}"
            )
        for ordinal, ((fe8u_key, target_id), (fe8j_key, source_id)) in enumerate(
            zip(fe8u_rows, fe8j_rows)
        ):
            if fe8u_key != fe8j_key:
                raise CrosswalkError(
                    f"{symbol}[{ordinal}]: semantic keys differ "
                    f"{fe8u_key!r}/{fe8j_key!r}"
                )
            if not target_id or not source_id:
                continue
            key = ",".join(
                f"{name}=0x{value:X}" for name, value in zip(key_names, fe8u_key)
            )
            records.append(
                _record(
                    target_id,
                    _indexed_source(source_id),
                    subsystem=subsystem,
                    evidence_kind="shared-rom-table-key",
                    source_table=symbol,
                    source_symbol=symbol,
                    source_key=key,
                    source_paths=paths,
                    rationale=(
                        "The named ROM tables have identical non-message key fields "
                        "for this row."
                    ),
                )
            )
    return records, [fe8u_rom, fe8u_elf, fe8j_rom, fe8j_symbols]


def _file_manifest(paths: Iterable[Path], roots: Mapping[str, Path]) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    for path in sorted(set(path.resolve() for path in paths)):
        logical_path = str(path)
        for label, root in roots.items():
            try:
                logical_path = f"{label}:{path.relative_to(root.resolve())}"
                break
            except ValueError:
                continue
        result.append(
            {
                "logical_path": logical_path,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return result


def harvest_structural_evidence(
    *,
    fe8u_root: Path,
    fe8j_root: Path,
    raw_path: Path,
    target_count: int,
) -> Dict[str, Any]:
    fe8u_root = Path(fe8u_root)
    fe8j_root = Path(fe8j_root)
    raw_path = Path(raw_path)
    records: List[EvidenceRecord] = []
    gaps: List[Dict[str, Any]] = []
    files: List[Path] = []
    for harvest in (
        lambda: _harvest_keyed_entities(fe8u_root, fe8j_root),
        lambda: _harvest_chapters(fe8u_root, fe8j_root),
        lambda: _harvest_supports(fe8u_root, fe8j_root),
    ):
        new_records, new_files = harvest()
        records.extend(new_records)
        files.extend(new_files)
    event_records, event_gaps, event_files = _harvest_event_scripts(
        fe8u_root, fe8j_root
    )
    records.extend(event_records)
    gaps.extend(event_gaps)
    files.extend(event_files)
    wm_records, wm_gaps, wm_files = _harvest_world_map(fe8u_root, fe8j_root)
    records.extend(wm_records)
    gaps.extend(wm_gaps)
    files.extend(wm_files)
    menu_records, menu_gaps, menu_files = _harvest_menus(
        fe8u_root, fe8j_root, raw_path
    )
    records.extend(menu_records)
    gaps.extend(menu_gaps)
    files.extend(menu_files)
    terrain_records, terrain_files = _harvest_terrain(
        fe8u_root, fe8j_root, raw_path
    )
    records.extend(terrain_records)
    files.extend(terrain_files)
    battle_records, battle_files = _harvest_battle_defeat(fe8u_root, fe8j_root)
    records.extend(battle_records)
    files.extend(battle_files)

    for record in records:
        if record.target_id < 0 or record.target_id >= target_count:
            raise CrosswalkError(
                f"evidence target {format_message_id(record.target_id)} is outside target universe"
            )
    return {
        "fallback_overrides": [
            {
                "reason": "region-only",
                "rationale": (
                    "Two distinct regional raw menu strings share FE8U target 0x0693; "
                    "a single target provider cannot preserve both contexts."
                ),
                "subsystem": "menus",
                "target_id": "0x0693",
            }
        ],
        "gaps": sorted(gaps, key=lambda row: (row["subsystem"], row["source_key"])),
        "kind": EVIDENCE_KIND,
        "records": [
            record.to_json()
            for record in sorted(
                records,
                key=lambda row: (
                    row.target_id,
                    row.source["kind"],
                    row.source_key,
                ),
            )
        ],
        "reference_files": _file_manifest(
            files,
            {
                "fe8j": fe8j_root,
                "fe8u": fe8u_root,
                "repository": raw_path.parents[3],
            },
        ),
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "target_count": target_count,
    }


def _validated_fallback_overrides(
    data: Any,
    *,
    target_count: int,
) -> Dict[int, Dict[str, Any]]:
    raw_overrides = data.get("fallback_overrides")
    if not isinstance(raw_overrides, list):
        raise CrosswalkError("evidence.fallback_overrides must be an array")
    result = {}
    for index, raw in enumerate(raw_overrides):
        field = f"evidence.fallback_overrides[{index}]"
        if not isinstance(raw, dict):
            raise CrosswalkError(f"{field} must be an object")
        target = raw.get("target_id")
        if not isinstance(target, str) or not re.fullmatch(r"0x[0-9A-F]{4}", target):
            raise CrosswalkError(f"{field}.target_id must use canonical 0xNNNN form")
        target_id = int(target, 16)
        if target_id < 0 or target_id >= target_count:
            raise CrosswalkError(f"{field}.target_id is outside target universe")
        if target_id in result:
            raise CrosswalkError(f"{field}.target_id is duplicated")
        if raw.get("reason") not in FALLBACK_REASONS:
            raise CrosswalkError(
                f"{field}.reason must be one of {FALLBACK_REASONS}"
            )
        for name in ("subsystem", "rationale"):
            if not isinstance(raw.get(name), str) or not raw[name]:
                raise CrosswalkError(f"{field}.{name} must be a non-empty string")
        result[target_id] = raw
    return result


def validate_evidence_document(
    data: Any,
    *,
    target_count: int,
    repo_root: Optional[Path] = None,
) -> List[EvidenceRecord]:
    if not isinstance(data, dict):
        raise CrosswalkError("evidence must be an object")
    if data.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise CrosswalkError(
            f"evidence.schema_version must be {EVIDENCE_SCHEMA_VERSION}"
        )
    if data.get("kind") != EVIDENCE_KIND:
        raise CrosswalkError(f"evidence.kind must be {EVIDENCE_KIND!r}")
    if data.get("target_count") != target_count:
        raise CrosswalkError(f"evidence.target_count must be {target_count}")
    _validated_fallback_overrides(data, target_count=target_count)
    raw_records = data.get("records")
    if not isinstance(raw_records, list):
        raise CrosswalkError("evidence.records must be an array")
    records: List[EvidenceRecord] = []
    for index, raw in enumerate(raw_records):
        field = f"evidence.records[{index}]"
        if not isinstance(raw, dict):
            raise CrosswalkError(f"{field} must be an object")
        try:
            target_id = int(raw["target_id"], 16)
            source = dict(raw["source"])
            subsystem = raw["subsystem"]
            evidence_kind = raw["evidence_kind"]
            source_table = raw["source_table"]
            source_symbol = raw["source_symbol"]
            source_key = raw["source_key"]
            confidence = raw["confidence"]
            source_paths = dict(raw["source_paths"])
            rationale = raw["rationale"]
        except (KeyError, TypeError, ValueError) as error:
            raise CrosswalkError(f"{field} is incomplete: {error}") from error
        try:
            validate_source_provider(
                source,
                f"{field}.source",
                target_id=target_id,
                repo_root=repo_root,
            )
        except MappingError as error:
            raise CrosswalkError(str(error)) from error
        for name, value in (
            ("subsystem", subsystem),
            ("evidence_kind", evidence_kind),
            ("source_table", source_table),
            ("source_symbol", source_symbol),
            ("source_key", source_key),
            ("rationale", rationale),
        ):
            if not isinstance(value, str) or not value:
                raise CrosswalkError(f"{field}.{name} must be a non-empty string")
        if not source_paths or any(
            not isinstance(name, str)
            or not name
            or not isinstance(path, str)
            or not path
            for name, path in source_paths.items()
        ):
            raise CrosswalkError(
                f"{field}.source_paths must contain non-empty string paths"
            )
        if confidence not in CONFIDENCE_LEVELS:
            raise CrosswalkError(
                f"{field}.confidence must be one of {CONFIDENCE_LEVELS}"
            )
        if target_id < 0 or target_id >= target_count:
            raise CrosswalkError(f"{field}.target_id is outside target universe")
        records.append(
            EvidenceRecord(
                target_id,
                source,
                subsystem,
                evidence_kind,
                source_table,
                source_symbol,
                source_key,
                confidence,
                source_paths,
                rationale,
            )
        )
    return records


def _provider_key(source: Mapping[str, Any]) -> str:
    return json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _candidate_rows(
    candidate_data: Optional[Any],
    target_count: int,
    *,
    repo_root: Optional[Path],
) -> Dict[int, Any]:
    if candidate_data is None:
        return {}
    candidate = validate_mapping_document(
        candidate_data,
        target_count=target_count,
        repo_root=repo_root,
    )
    if candidate.coverage_eligible:
        raise CrosswalkError("candidate input must not be authoritative")
    return {row.target_id: row for row in candidate.rows}


def build_release_mapping(
    evidence_data: Any,
    *,
    target_count: int,
    candidate_data: Optional[Any] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    records = validate_evidence_document(
        evidence_data,
        target_count=target_count,
        repo_root=repo_root,
    )
    candidates = _candidate_rows(
        candidate_data,
        target_count,
        repo_root=repo_root,
    )
    grouped: Dict[int, List[EvidenceRecord]] = {}
    for record in records:
        grouped.setdefault(record.target_id, []).append(record)

    fallback_overrides = _validated_fallback_overrides(
        evidence_data,
        target_count=target_count,
    )
    rows: List[Dict[str, Any]] = []
    for target_id in range(target_count):
        evidence = grouped.get(target_id, [])
        override = fallback_overrides.get(target_id)
        if override is not None:
            source = {"kind": "english_fallback", "reason": override["reason"]}
            verification = {
                "confidence": "explicit",
                "evidence": override["rationale"],
                "evidence_kind": "fallback-classification",
                "method": "explicit-fallback",
                "rationale": override["rationale"],
                "source_key": format_message_id(target_id),
                "source_symbol": "gMsgTable",
                "source_table": "FE8U target universe",
                "subsystem": override["subsystem"],
            }
        elif evidence:
            raw_records = [record for record in evidence if record.source["kind"] == "raw"]
            chosen = raw_records or evidence
            providers = {_provider_key(record.source) for record in chosen}
            if len(providers) != 1:
                raise CrosswalkError(
                    f"{format_message_id(target_id)} has conflicting structural providers"
                )
            source = chosen[0].source
            primary = sorted(
                chosen,
                key=lambda record: (
                    record.confidence != "high",
                    record.subsystem,
                    record.source_key,
                ),
            )[0]
            candidate = candidates.get(target_id)
            verification = {
                "confidence": primary.confidence,
                "evidence": (
                    f"{primary.evidence_kind}: {primary.source_symbol} "
                    f"{primary.source_key}"
                ),
                "evidence_kind": primary.evidence_kind,
                "method": "structural-crosswalk",
                "rationale": primary.rationale,
                "source_key": primary.source_key,
                "source_paths": primary.source_paths,
                "source_symbol": primary.source_symbol,
                "source_table": primary.source_table,
                "subsystem": primary.subsystem,
            }
            if len(chosen) > 1:
                verification["additional_evidence"] = [
                    {
                        "evidence_kind": record.evidence_kind,
                        "source_key": record.source_key,
                        "source_symbol": record.source_symbol,
                        "source_table": record.source_table,
                        "subsystem": record.subsystem,
                    }
                    for record in sorted(chosen, key=lambda item: item.source_key)
                    if record != primary
                ]
            if candidate is not None:
                verification["candidate_seed"] = {
                    "matched": _provider_key(candidate.source) == _provider_key(source),
                    "seed_tag": candidate.candidate_provenance["seed_tag"],
                    "source_line": candidate.candidate_provenance["source_line"],
                }
        else:
            if target_id == 0:
                reason = "dummy"
                subsystem = "system"
            elif target_id > FE8J_MAX_INDEXED_ID:
                reason = "expansion-only"
                subsystem = "expansion"
            else:
                reason = "not-yet-verified"
                subsystem = "unclassified"
            source = {"kind": "english_fallback", "reason": reason}
            candidate = candidates.get(target_id)
            evidence_text = "No accepted structural evidence identifies this semantic slot."
            if candidate is not None:
                evidence_text += " A candidate seed exists but was not allowed to self-promote."
            verification = {
                "confidence": "explicit",
                "evidence": evidence_text,
                "evidence_kind": "fallback-classification",
                "method": "explicit-fallback",
                "rationale": reason,
                "source_key": format_message_id(target_id),
                "source_symbol": "gMsgTable",
                "source_table": "FE8U target universe",
                "subsystem": subsystem,
            }
            if candidate is not None:
                verification["candidate_seed"] = {
                    "ignored": True,
                    "seed_tag": candidate.candidate_provenance["seed_tag"],
                    "source_line": candidate.candidate_provenance["source_line"],
                }
        rows.append(
            {
                "source": source,
                "state": "verified",
                "target_id": format_message_id(target_id),
                "verification": verification,
            }
        )

    mapping = {
        "authoritative": True,
        "authority": "verified",
        "kind": "fe8u-locale-mapping",
        "locale_ids": ["ja", "zh-Hans"],
        "note": RELEASE_MAP_NOTE,
        "rows": rows,
        "schema_version": 2,
    }
    validate_mapping_document(
        mapping,
        target_count=target_count,
        repo_root=repo_root,
    )
    return mapping


def build_crosswalk_coverage_report(
    mapping_data: Any,
    *,
    target_count: int,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    mapping = validate_mapping_document(
        mapping_data,
        target_count=target_count,
        repo_root=repo_root,
    )
    if not mapping.coverage_eligible:
        raise CrosswalkError("coverage requires an authoritative mapping")
    if len(mapping.rows) != target_count:
        raise CrosswalkError(
            f"release mapping must contain {target_count} rows, found {len(mapping.rows)}"
        )
    source_counts = {
        "authored_translation": 0,
        "explicit_english_fallback": 0,
        "indexed_source": 0,
        "raw_source": 0,
    }
    by_subsystem: Dict[str, Dict[str, int]] = {}
    fallback_ids: List[Dict[str, str]] = []
    fallback_reasons: Dict[str, int] = {}
    source_category = {
        "authored": "authored_translation",
        "english_fallback": "explicit_english_fallback",
        "indexed": "indexed_source",
        "raw": "raw_source",
    }
    for row in mapping.rows:
        category = source_category[row.source_kind]
        source_counts[category] += 1
        subsystem = row.verification["subsystem"]
        subsystem_counts = by_subsystem.setdefault(
            subsystem,
            {
                "authored_translation": 0,
                "explicit_english_fallback": 0,
                "indexed_source": 0,
                "raw_source": 0,
                "total": 0,
            },
        )
        subsystem_counts[category] += 1
        subsystem_counts["total"] += 1
        if row.source_kind == "english_fallback":
            reason = row.source["reason"]
            fallback_reasons[reason] = fallback_reasons.get(reason, 0) + 1
            fallback_ids.append(
                {
                    "reason": reason,
                    "subsystem": subsystem,
                    "target_id": format_message_id(row.target_id),
                }
            )
    translation_count = (
        source_counts["indexed_source"]
        + source_counts["raw_source"]
        + source_counts["authored_translation"]
    )
    return {
        "by_subsystem": dict(sorted(by_subsystem.items())),
        "explicit_fallback_coverage": {
            "count": source_counts["explicit_english_fallback"],
            "percent": round(
                100 * source_counts["explicit_english_fallback"] / target_count, 2
            ),
        },
        "fallback_ids": fallback_ids,
        "fallback_reasons": dict(sorted(fallback_reasons.items())),
        "mapping_authoritative": True,
        "schema_version": 1,
        "source_kind_counts": source_counts,
        "target_count": target_count,
        "translation_coverage": {
            "count": translation_count,
            "percent": round(100 * translation_count / target_count, 2),
        },
        "unresolved_count": 0,
    }
