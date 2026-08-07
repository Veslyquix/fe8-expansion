"""Coverage classification for future verified FE8U locale mappings."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable

from .mapping import MappingDocument, MappingError, format_message_id

CATEGORY_BY_SOURCE_KIND = {
    "indexed": "indexed_source",
    "raw": "raw_source",
    "authored": "authored_translation",
    "english_fallback": "explicit_english_fallback",
}
CATEGORIES = tuple(CATEGORY_BY_SOURCE_KIND.values()) + ("unresolved",)

_MSG_COUNT_RE = re.compile(r"#define\s+MSG_COUNT\s+0x([0-9A-Fa-f]+)")


def load_fe8u_target_ids(header_path: Path) -> range:
    text = Path(header_path).read_text(encoding="utf-8")
    matches = _MSG_COUNT_RE.findall(text)
    if len(matches) != 1:
        raise MappingError(f"{header_path}: expected exactly one hexadecimal MSG_COUNT")
    count = int(matches[0], 16)
    if count <= 0 or count > 0xFFFF:
        raise MappingError(f"{header_path}: MSG_COUNT {count} is outside the supported range")
    return range(count)


def build_coverage_report(
    mapping: MappingDocument,
    target_ids: Iterable[int],
    *,
    locale: str,
) -> Dict[str, Any]:
    if locale not in mapping.locale_ids:
        raise MappingError(
            f"mapping does not apply to locale {locale!r}; expected one of {mapping.locale_ids}"
        )

    target_list = list(target_ids)
    target_set = set(target_list)
    rows_by_target = {row.target_id: row for row in mapping.rows}
    unknown_targets = sorted(set(rows_by_target) - target_set)
    if unknown_targets:
        raise MappingError(
            "mapping contains targets outside the requested universe: "
            + ", ".join(format_message_id(value) for value in unknown_targets[:8])
        )

    counts = {category: 0 for category in CATEGORIES}
    report_rows = []
    for target_id in target_list:
        mapping_row = rows_by_target.get(target_id)
        candidate_present = bool(mapping_row and not mapping.coverage_eligible)
        if mapping_row is not None and mapping.coverage_eligible:
            category = CATEGORY_BY_SOURCE_KIND[mapping_row.source_kind]
        else:
            category = "unresolved"
        counts[category] += 1
        report_row: Dict[str, Any] = {
            "target_id": format_message_id(target_id),
            "classification": category,
        }
        if candidate_present:
            report_row["candidate_present"] = True
        if mapping_row is not None and mapping.coverage_eligible:
            report_row["source"] = mapping_row.source
        report_rows.append(report_row)

    return {
        "schema_version": 1,
        "locale": locale,
        "mapping_authority": mapping.authority,
        "mapping_authoritative": mapping.authoritative,
        "target_count": len(target_list),
        "candidate_rows_ignored": len(mapping.rows) if not mapping.coverage_eligible else 0,
        "summary": counts,
        "rows": report_rows,
    }
