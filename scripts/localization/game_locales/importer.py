"""Pinned, deterministic importer for full-game locale source artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Tuple

from .controls import (
    CANONICAL_CONTROL_GRAMMAR,
    FE8CN_NAMED_CONTROL_ALIASES,
    SOURCE_DIALECT_CHINESE,
    SOURCE_DIALECT_JAPANESE,
    ControlSyntaxError,
    canonical_control_token,
    normalize_source_controls,
    validate_canonical_text,
)
from .mapping import MAPPING_KIND, MAPPING_SCHEMA_VERSION, validate_mapping_document
from .parsers import (
    FE8J_INDEXED_COUNT,
    FE8J_MAX_INDEXED_ID,
    ChineseSource,
    ControlDefinition,
    IndexedMessage,
    LocaleSourceError,
    MappingSeedRow,
    RawOccurrence,
    RawString,
    parse_control_definitions,
    parse_fe8cn,
    parse_hash_indexed,
    parse_mapping_seed_tsv,
)

JP_SOURCE_ID = "fe8j_indexed"
JP_CONTROLS_SOURCE_ID = "fe8j_controls"
CN_SOURCE_ID = "fe8cn_source"
MAPPING_SOURCE_ID = "fe8j_mapping_seed"

PINNED_SOURCE_SHA256 = {
    JP_SOURCE_ID: "511ce51cadd2ac94ec3f5219a81205f6aa52de3c3c659c9efd1f0f75f9079a8a",
    JP_CONTROLS_SOURCE_ID: "93186c5645192ef46484b34f0d6dc4237cf21b61ffac317077ac5892067cc0b5",
    CN_SOURCE_ID: "bef561dd5a45f81658d4f06b0b9f58bdc6fde2ed4b4c57034d17b88cb595f517",
    MAPPING_SOURCE_ID: "9acb014c27148366cec70ce7bf2c64e021bf10bfc4e55df7cfe99d12ad40c751",
}

SOURCE_LOGICAL_PATHS = {
    JP_SOURCE_ID: "fireemblem8j/texts/jp_texts.txt",
    JP_CONTROLS_SOURCE_ID: "fireemblem8j/texts/jp_textdefs.txt",
    CN_SOURCE_ID: "FE8CN.txt",
    MAPPING_SOURCE_ID: "fireemblem8j/layout/msg_map.tsv",
}

VENDORED_SOURCE_PATHS = {
    JP_SOURCE_ID: Path("fe8j/jp_texts.txt"),
    JP_CONTROLS_SOURCE_ID: Path("fe8j/jp_textdefs.txt"),
    CN_SOURCE_ID: Path("fe8cn/FE8CN.txt"),
    MAPPING_SOURCE_ID: Path("fe8j/msg_map.tsv"),
}

EXPECTED_JP_COUNT = 3339
EXPECTED_CN_INDEXED_COUNT = 3339
EXPECTED_CN_RAW_RECORD_COUNT = 152
EXPECTED_CN_RAW_UNIQUE_COUNT = 143
EXPECTED_MAPPING_SEED_ROWS = 2770
FE8U_TARGET_COUNT = 0x0D56

_ARTIFACT_PATHS = (
    "ja/indexed.txt",
    "ja/control_defs.txt",
    "zh-Hans/indexed.txt",
    "zh-Hans/raw.json",
    "mapping/fe8j_to_fe8u.candidates.json",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def verify_source_hash(path: Path, source_id: str, expected_sha256: str) -> bytes:
    data = Path(path).read_bytes()
    actual = sha256_bytes(data)
    if actual != expected_sha256:
        raise LocaleSourceError(
            f"{source_id}: SHA-256 mismatch for {path}; expected {expected_sha256}, got {actual}"
        )
    return data


def _load_sources(
    paths: Mapping[str, Path],
    expected_hashes: Mapping[str, str],
) -> Tuple[Dict[str, str], Dict[str, Dict[str, Any]]]:
    texts: Dict[str, str] = {}
    metadata: Dict[str, Dict[str, Any]] = {}
    for source_id in (
        JP_SOURCE_ID,
        JP_CONTROLS_SOURCE_ID,
        CN_SOURCE_ID,
        MAPPING_SOURCE_ID,
    ):
        if source_id not in expected_hashes:
            raise LocaleSourceError(f"missing pinned SHA-256 for {source_id}")
        path = Path(paths[source_id])
        data = verify_source_hash(path, source_id, expected_hashes[source_id])
        try:
            texts[source_id] = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise LocaleSourceError(f"{source_id}: input must be valid UTF-8") from error
        metadata[source_id] = {
            "logical_path": SOURCE_LOGICAL_PATHS[source_id],
            "committed_snapshot": (
                "texts/locales/source/" + VENDORED_SOURCE_PATHS[source_id].as_posix()
            ),
            "sha256": sha256_bytes(data),
            "byte_count": len(data),
        }
    return texts, metadata


def vendored_source_paths(source_dir: Path) -> Dict[str, Path]:
    source_dir = Path(source_dir)
    return {
        source_id: source_dir / relative_path
        for source_id, relative_path in VENDORED_SOURCE_PATHS.items()
    }


def _normalize_payload(
    text: str,
    *,
    dialect: str,
    aliases: Mapping[str, Tuple[int, ...]],
    source_name: str,
    source_line: int,
) -> str:
    try:
        normalized = normalize_source_controls(
            text,
            dialect=dialect,
            aliases=aliases,
        )
        validate_canonical_text(normalized)
        return normalized
    except ControlSyntaxError as error:
        raise LocaleSourceError(f"{source_name}:{source_line}: {error}") from error


def _normalize_indexed_messages(
    messages: Iterable[IndexedMessage],
    *,
    dialect: str,
    aliases: Mapping[str, Tuple[int, ...]],
    source_name: str,
) -> Tuple[IndexedMessage, ...]:
    return tuple(
        IndexedMessage(
            message.id,
            _normalize_payload(
                message.text,
                dialect=dialect,
                aliases=aliases,
                source_name=source_name,
                source_line=message.marker_line + 1,
            ),
            message.marker_line,
        )
        for message in messages
    )


def _normalize_chinese_source(
    source: ChineseSource,
    *,
    aliases: Mapping[str, Tuple[int, ...]],
    source_name: str,
) -> ChineseSource:
    indexed = _normalize_indexed_messages(
        source.indexed,
        dialect=SOURCE_DIALECT_CHINESE,
        aliases=aliases,
        source_name=source_name,
    )
    occurrences = tuple(
        RawOccurrence(
            occurrence.record_index,
            occurrence.address,
            _normalize_payload(
                occurrence.text,
                dialect=SOURCE_DIALECT_CHINESE,
                aliases=aliases,
                source_name=source_name,
                source_line=occurrence.payload_start_line,
            ),
            occurrence.marker_line,
            occurrence.payload_start_line,
        )
        for occurrence in source.raw_occurrences
    )
    occurrence_by_index = {
        occurrence.record_index: occurrence for occurrence in occurrences
    }
    raw_strings = tuple(
        RawString(
            raw_string.import_id,
            raw_string.address,
            occurrence_by_index[raw_string.occurrences[0].record_index].text,
            tuple(
                occurrence_by_index[occurrence.record_index]
                for occurrence in raw_string.occurrences
            ),
        )
        for raw_string in source.raw_strings
    )
    return ChineseSource(indexed, occurrences, raw_strings)


def _write_indexed(
    locale: str,
    messages: Iterable[IndexedMessage],
    source_sha256: str,
) -> bytes:
    lines = [
        "# Normalized UTF-8 indexed locale source.",
        f"# Locale ID: {locale}",
        "# Source layout: FE8J; these identifiers are not FE8U target identifiers.",
        f"# Input SHA-256: {source_sha256}",
        "",
    ]
    for message in messages:
        lines.append(f"#0x{message.id:04X}")
        lines.extend(message.text.split("\n"))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write_controls(
    definitions: Iterable[ControlDefinition],
    source_sha256: str,
) -> bytes:
    lines = [
        "# FE8J source aliases mapped to the canonical control grammar.",
        "# This is an alias table, not normalized locale payload.",
        f"# Canonical grammar: {CANONICAL_CONTROL_GRAMMAR}",
        f"# Input SHA-256: {source_sha256}",
        "",
    ]
    for definition in definitions:
        values = "".join(canonical_control_token(value) for value in definition.values)
        lines.append(f"{definition.name} = {values}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _raw_document(raw_strings: Iterable[RawString]) -> Dict[str, Any]:
    records = []
    record_count = 0
    for raw_string in sorted(raw_strings, key=lambda item: item.import_id):
        occurrences = []
        for occurrence in raw_string.occurrences:
            record_count += 1
            occurrences.append(
                {
                    "record_index": occurrence.record_index,
                    "marker_line": occurrence.marker_line,
                    "payload_start_line": occurrence.payload_start_line,
                }
            )
        records.append(
            {
                "import_id": raw_string.import_id,
                "text": raw_string.text,
                "provenance": {
                    "address": f"0x{raw_string.address:08X}",
                    "occurrences": occurrences,
                },
            }
        )
    return {
        "schema_version": 2,
        "locale_id": "zh-Hans",
        "source_layout": "FE8CN-raw-address",
        "record_count": record_count,
        "unique_import_count": len(records),
        "unique_address_count": len(records),
        "records": records,
    }


def _candidate_mapping_document(
    rows: Iterable[MappingSeedRow],
    source_metadata: Mapping[str, Any],
) -> Dict[str, Any]:
    document = {
        "schema_version": MAPPING_SCHEMA_VERSION,
        "kind": MAPPING_KIND,
        "locale_ids": ["ja", "zh-Hans"],
        "authority": "candidate",
        "authoritative": False,
        "source_layout": "FE8J",
        "note": (
            "UNVERIFIED candidate seed only. Numeric FE8J positions and provenance "
            "tags do not establish semantic correctness for FE8U targets."
        ),
        "provenance": {
            "input_id": MAPPING_SOURCE_ID,
            "logical_path": source_metadata["logical_path"],
            "committed_snapshot": source_metadata["committed_snapshot"],
            "sha256": source_metadata["sha256"],
        },
        "rows": [
            {
                "target_id": f"0x{row.target_id:04X}",
                "state": "candidate",
                "source": {
                    "kind": "indexed",
                    "layout": "FE8J",
                    "id": f"0x{row.source_id:04X}",
                },
                "candidate_provenance": {
                    "seed_tag": row.provenance_tag,
                    "source_line": row.source_line,
                },
            }
            for row in rows
        ],
    }
    validate_mapping_document(document, target_count=FE8U_TARGET_COUNT)
    return document


def _payload_statistics(messages: Iterable[IndexedMessage]) -> Dict[str, Any]:
    message_list = list(messages)
    all_text = "".join(message.text for message in message_list)
    max_message = max(
        message_list,
        key=lambda message: (len(message.text.encode("utf-8")), -message.id),
    )
    return {
        "message_count": len(message_list),
        "max_id": f"0x{message_list[-1].id:04X}",
        "payload_codepoint_count": sum(len(message.text) for message in message_list),
        "unique_payload_codepoint_count": len(set(all_text)),
        "max_utf8_payload_bytes": len(max_message.text.encode("utf-8")),
        "max_utf8_payload_message_id": f"0x{max_message.id:04X}",
    }


def _raw_statistics(raw_strings: Iterable[RawString]) -> Dict[str, Any]:
    unique = list(raw_strings)
    occurrences = [
        occurrence
        for raw_string in unique
        for occurrence in raw_string.occurrences
    ]
    all_unique_text = "".join(raw_string.text for raw_string in unique)
    max_raw = max(
        unique,
        key=lambda raw_string: (
            len(raw_string.text.encode("utf-8")),
            raw_string.import_id,
        ),
    )
    return {
        "record_count": len(occurrences),
        "unique_import_count": len(unique),
        "unique_address_count": len(unique),
        "duplicate_record_count": len(occurrences) - len(unique),
        "duplicate_address_count": sum(
            1 for raw_string in unique if len(raw_string.occurrences) > 1
        ),
        "payload_codepoint_count_all_records": sum(
            len(occurrence.text) for occurrence in occurrences
        ),
        "payload_codepoint_count_unique_records": sum(
            len(raw_string.text) for raw_string in unique
        ),
        "unique_payload_codepoint_count": len(set(all_unique_text)),
        "max_utf8_payload_bytes": len(max_raw.text.encode("utf-8")),
        "max_utf8_payload_import_id": max_raw.import_id,
    }


def _artifact_metadata(artifacts: Mapping[str, bytes]) -> Dict[str, Dict[str, Any]]:
    return {
        name: {
            "sha256": sha256_bytes(content),
            "byte_count": len(content),
        }
        for name, content in sorted(artifacts.items())
    }


def build_locale_artifacts(
    *,
    jp_text_path: Path,
    jp_controls_path: Path,
    cn_text_path: Path,
    mapping_seed_path: Path,
    expected_hashes: Mapping[str, str] = PINNED_SOURCE_SHA256,
) -> Dict[str, bytes]:
    paths = {
        JP_SOURCE_ID: Path(jp_text_path),
        JP_CONTROLS_SOURCE_ID: Path(jp_controls_path),
        CN_SOURCE_ID: Path(cn_text_path),
        MAPPING_SOURCE_ID: Path(mapping_seed_path),
    }
    source_texts, source_metadata = _load_sources(paths, expected_hashes)

    japanese_source = parse_hash_indexed(
        source_texts[JP_SOURCE_ID],
        source_name=SOURCE_LOGICAL_PATHS[JP_SOURCE_ID],
    )
    controls = parse_control_definitions(
        source_texts[JP_CONTROLS_SOURCE_ID],
        source_name=SOURCE_LOGICAL_PATHS[JP_CONTROLS_SOURCE_ID],
    )
    aliases = {definition.name: definition.values for definition in controls}
    japanese = _normalize_indexed_messages(
        japanese_source,
        dialect=SOURCE_DIALECT_JAPANESE,
        aliases=aliases,
        source_name=SOURCE_LOGICAL_PATHS[JP_SOURCE_ID],
    )
    chinese_aliases = dict(aliases)
    chinese_aliases.update(FE8CN_NAMED_CONTROL_ALIASES)
    chinese = _normalize_chinese_source(
        parse_fe8cn(
            source_texts[CN_SOURCE_ID],
            source_name=SOURCE_LOGICAL_PATHS[CN_SOURCE_ID],
        ),
        aliases=chinese_aliases,
        source_name=SOURCE_LOGICAL_PATHS[CN_SOURCE_ID],
    )
    mapping_rows = parse_mapping_seed_tsv(
        source_texts[MAPPING_SOURCE_ID],
        source_name=SOURCE_LOGICAL_PATHS[MAPPING_SOURCE_ID],
    )

    if len(japanese) != EXPECTED_JP_COUNT or len(japanese) != FE8J_INDEXED_COUNT:
        raise LocaleSourceError(f"expected {EXPECTED_JP_COUNT} Japanese indexed messages")
    if len(chinese.indexed) != EXPECTED_CN_INDEXED_COUNT:
        raise LocaleSourceError(
            f"expected {EXPECTED_CN_INDEXED_COUNT} Chinese indexed messages"
        )
    if len(chinese.raw_occurrences) != EXPECTED_CN_RAW_RECORD_COUNT:
        raise LocaleSourceError(
            f"expected {EXPECTED_CN_RAW_RECORD_COUNT} Chinese raw records"
        )
    if len(chinese.raw_strings) != EXPECTED_CN_RAW_UNIQUE_COUNT:
        raise LocaleSourceError(
            f"expected {EXPECTED_CN_RAW_UNIQUE_COUNT} unique Chinese raw addresses"
        )
    if len(mapping_rows) != EXPECTED_MAPPING_SEED_ROWS:
        raise LocaleSourceError(
            f"expected {EXPECTED_MAPPING_SEED_ROWS} mapping seed rows"
        )
    if japanese[-1].id != FE8J_MAX_INDEXED_ID:
        raise LocaleSourceError("Japanese indexed source has an unexpected maximum id")
    if chinese.indexed[-1].id != FE8J_MAX_INDEXED_ID:
        raise LocaleSourceError("Chinese indexed source has an unexpected maximum id")

    artifacts = {
        "ja/indexed.txt": _write_indexed(
            "ja",
            japanese,
            source_metadata[JP_SOURCE_ID]["sha256"],
        ),
        "ja/control_defs.txt": _write_controls(
            controls,
            source_metadata[JP_CONTROLS_SOURCE_ID]["sha256"],
        ),
        "zh-Hans/indexed.txt": _write_indexed(
            "zh-Hans",
            chinese.indexed,
            source_metadata[CN_SOURCE_ID]["sha256"],
        ),
        "zh-Hans/raw.json": _json_bytes(_raw_document(chinese.raw_strings)),
        "mapping/fe8j_to_fe8u.candidates.json": _json_bytes(
            _candidate_mapping_document(
                mapping_rows,
                source_metadata[MAPPING_SOURCE_ID],
            )
        ),
    }
    if tuple(sorted(artifacts)) != tuple(sorted(_ARTIFACT_PATHS)):
        raise AssertionError("artifact set drifted from the importer contract")

    manifest = {
        "schema_version": 2,
        "locale_ids": ["ja", "zh-Hans"],
        "control_grammar": {
            "canonical_token": CANONICAL_CONTROL_GRAMMAR,
            "control_unit": "u16",
            "byte_order": "little",
            "source_alias_count": len(controls),
            "fe8cn_additional_alias_count": len(FE8CN_NAMED_CONTROL_ALIASES),
        },
        "source_layout": {
            "indexed": "FE8J",
            "fe8j_indexed_count": FE8J_INDEXED_COUNT,
            "fe8j_max_id": f"0x{FE8J_MAX_INDEXED_ID:04X}",
            "fe8u_target_count": FE8U_TARGET_COUNT,
            "warning": (
                "FE8J indexed identifiers are source positions, not FE8U target "
                "identifiers. A verified sparse mapping is required."
            ),
        },
        "inputs": source_metadata,
        "locales": {
            "ja": {
                "indexed": _payload_statistics(japanese),
                "control_definition_count": len(controls),
            },
            "zh-Hans": {
                "indexed": _payload_statistics(chinese.indexed),
                "raw": _raw_statistics(chinese.raw_strings),
            },
        },
        "mapping_seed": {
            "row_count": len(mapping_rows),
            "authority": "candidate",
            "authoritative": False,
            "verified_row_count": 0,
            "provenance_tag_counts": dict(
                sorted(Counter(row.provenance_tag for row in mapping_rows).items())
            ),
        },
        "artifacts": _artifact_metadata(artifacts),
    }
    artifacts["manifest.json"] = _json_bytes(manifest)
    return artifacts


def write_locale_artifacts(
    artifacts: Mapping[str, bytes],
    output_dir: Path,
) -> Dict[str, Path]:
    output_dir = Path(output_dir)
    written = {}
    for relative_path, content in sorted(artifacts.items()):
        destination = output_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or destination.read_bytes() != content:
            destination.write_bytes(content)
        written[relative_path] = destination
    return written


def import_locale_sources(
    *,
    jp_text_path: Path,
    jp_controls_path: Path,
    cn_text_path: Path,
    mapping_seed_path: Path,
    output_dir: Path,
    expected_hashes: Mapping[str, str] = PINNED_SOURCE_SHA256,
) -> Dict[str, Path]:
    artifacts = build_locale_artifacts(
        jp_text_path=jp_text_path,
        jp_controls_path=jp_controls_path,
        cn_text_path=cn_text_path,
        mapping_seed_path=mapping_seed_path,
        expected_hashes=expected_hashes,
    )
    return write_locale_artifacts(artifacts, output_dir)


def regenerate_vendored_locale_sources(
    *,
    source_dir: Path,
    output_dir: Path,
) -> Dict[str, Path]:
    paths = vendored_source_paths(source_dir)
    return import_locale_sources(
        jp_text_path=paths[JP_SOURCE_ID],
        jp_controls_path=paths[JP_CONTROLS_SOURCE_ID],
        cn_text_path=paths[CN_SOURCE_ID],
        mapping_seed_path=paths[MAPPING_SOURCE_ID],
        output_dir=output_dir,
    )


def check_vendored_locale_sources(
    *,
    source_dir: Path,
    output_dir: Path,
) -> Dict[str, bytes]:
    paths = vendored_source_paths(source_dir)
    expected = build_locale_artifacts(
        jp_text_path=paths[JP_SOURCE_ID],
        jp_controls_path=paths[JP_CONTROLS_SOURCE_ID],
        cn_text_path=paths[CN_SOURCE_ID],
        mapping_seed_path=paths[MAPPING_SOURCE_ID],
    )
    mismatches = []
    output_dir = Path(output_dir)
    for relative_path, expected_bytes in sorted(expected.items()):
        destination = output_dir / relative_path
        if not destination.is_file():
            mismatches.append(f"missing {relative_path}")
        elif destination.read_bytes() != expected_bytes:
            mismatches.append(f"differs {relative_path}")
    if mismatches:
        raise LocaleSourceError(
            "committed locale artifacts do not match vendored raw snapshots: "
            + ", ".join(mismatches)
        )
    return expected
