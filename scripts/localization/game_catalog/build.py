"""Deterministic builder for full-game localized catalogs."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from scripts.localization.game_locales.controls import (
    ControlSyntaxError,
    expand_canonical_text,
)
from scripts.localization.game_locales.coverage import load_fe8u_target_ids
from scripts.localization.game_locales.mapping import (
    MappingError,
    format_message_id,
    validate_mapping_document,
)
from scripts.localization.game_locales.parsers import LocaleSourceError, parse_hash_indexed
from scripts.texttools.multilang_codec import build_catalog
from scripts.texttools.multilang_codec.codec import SCHEMA as CODEC_SCHEMA

from .c_emitter import render_config_header, render_header, render_source
from .constants import (
    BUDGET_KIND,
    BUDGET_SCHEMA_VERSION,
    ENTRY_STRUCT_SIZE_BYTES,
    FALLBACK_KIND_EXPLICIT_ENGLISH,
    FALLBACK_KIND_NONE,
    FALLBACK_KIND_PROVIDER_UNAVAILABLE,
    LOCALE_CATALOG_STRUCT_SIZE_BYTES,
    LOCALE_IDS,
    LOCALE_POINTER_ARRAY_BYTES,
    OUTPUT_BUDGET_NAME,
    OUTPUT_CONFIG_HEADER_NAME,
    OUTPUT_HEADER_NAME,
    OUTPUT_REPORT_NAME,
    OUTPUT_SOURCE_NAME,
    PRESENT_PROVIDER_KINDS,
    REPORT_KIND,
    REPORT_SCHEMA_VERSION,
    SOURCE_KINDS,
    TARGET_STORAGE_BYTES,
)
from .english_source import load_english_source_entries
from .model import (
    EnglishCatalogBundle,
    EntryPayloadMeta,
    GameCatalogBuild,
    GameCatalogError,
    LocaleCatalogBundle,
)

DEFAULT_ENGLISH_TEXTS_PATH = Path("texts/texts.txt")
DEFAULT_ENGLISH_DEFINITIONS_PATH = Path("texts/textdefs.txt")
DEFAULT_JA_INDEXED_PATH = Path("texts/locales/ja/indexed.txt")
DEFAULT_ZH_INDEXED_PATH = Path("texts/locales/zh-Hans/indexed.txt")
DEFAULT_ZH_RAW_PATH = Path("texts/locales/zh-Hans/raw.json")
DEFAULT_MAPPING_PATH = Path("texts/locales/mapping/fe8u_target_map.json")
DEFAULT_TARGET_HEADER_PATH = Path("include/constants/msg.h")

_AUTHORED_KIND = "fe8u-game-authored-catalog"


def canonical_json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strict_utf8_text(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise GameCatalogError(f"{path}: file is not strict UTF-8") from error


def _load_json(path: Path) -> Any:
    try:
        return json.loads(_strict_utf8_text(path))
    except json.JSONDecodeError as error:
        raise GameCatalogError(f"{path}: invalid JSON: {error}") from error


def _load_indexed(path: Path) -> Dict[int, str]:
    text = _strict_utf8_text(path)
    matches = list(re.finditer(r"^#0x([0-9A-Fa-f]{4})$", text, re.MULTILINE))
    if not matches:
        raise GameCatalogError(f"{path}: no indexed markers found")
    expected_last_id = int(matches[-1].group(1), 16)
    try:
        messages = parse_hash_indexed(
            text,
            expected_last_id=expected_last_id,
            source_name=str(path),
        )
    except LocaleSourceError as error:
        raise GameCatalogError(str(error)) from error
    return {message.id: message.text for message in messages}


def _load_raw_records(path: Path) -> Dict[str, str]:
    data = _load_json(path)
    if not isinstance(data, dict):
        raise GameCatalogError(f"{path}: raw record root must be an object")
    if data.get("schema_version") != 2:
        raise GameCatalogError(f"{path}: raw records schema_version must be 2")
    if data.get("locale_id") != "zh-Hans":
        raise GameCatalogError(f"{path}: raw records locale_id must be \"zh-Hans\"")
    if data.get("source_layout") != "FE8CN-raw-address":
        raise GameCatalogError(
            f"{path}: raw records source_layout must be FE8CN-raw-address"
        )
    records = data.get("records")
    if not isinstance(records, list):
        raise GameCatalogError(f"{path}: raw records list is missing")
    unique_import_count = data.get("unique_import_count")
    if unique_import_count is not None and unique_import_count != len(records):
        raise GameCatalogError(
            f"{path}: unique_import_count does not match records length"
        )
    if data.get("record_count") is None:
        raise GameCatalogError(f"{path}: record_count is missing")
    result: Dict[str, str] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise GameCatalogError(f"{path}: records[{index}] must be an object")
        import_id = record.get("import_id")
        text = record.get("text")
        provenance = record.get("provenance")
        if not isinstance(import_id, str) or not import_id:
            raise GameCatalogError(
                f"{path}: records[{index}].import_id must be a non-empty string"
            )
        if not isinstance(text, str):
            raise GameCatalogError(f"{path}: records[{index}].text must be a string")
        if not isinstance(provenance, dict):
            raise GameCatalogError(
                f"{path}: records[{index}].provenance must be an object"
            )
        if import_id in result:
            raise GameCatalogError(f"{path}: duplicate raw import_id {import_id!r}")
        result[import_id] = text
    return result


def _load_authored_catalogs(paths: Optional[Mapping[str, Path]]) -> Dict[str, Dict[str, str]]:
    if not paths:
        return {}
    catalogs: Dict[str, Dict[str, str]] = {}
    for locale, path in sorted(paths.items()):
        if locale not in LOCALE_IDS:
            raise GameCatalogError(f"unsupported authored locale {locale!r}")
        data = _load_json(path)
        if not isinstance(data, dict):
            raise GameCatalogError(f"{path}: authored catalog root must be an object")
        if data.get("kind") not in (None, _AUTHORED_KIND):
            raise GameCatalogError(
                f"{path}: authored catalog kind must be {_AUTHORED_KIND!r} when present"
            )
        file_locale = data.get("locale", locale)
        if file_locale != locale:
            raise GameCatalogError(
                f"{path}: authored catalog locale {file_locale!r} does not match {locale!r}"
            )
        strings = data.get("strings")
        if not isinstance(strings, dict):
            raise GameCatalogError(f"{path}: authored catalog strings must be an object")
        normalized: Dict[str, str] = {}
        for key, value in sorted(strings.items()):
            if not isinstance(key, str) or not key:
                raise GameCatalogError(
                    f"{path}: authored translation keys must be non-empty strings"
                )
            if not isinstance(value, str):
                raise GameCatalogError(f"{path}: authored string {key!r} must be a string")
            normalized[key] = value
        catalogs[locale] = normalized
    return catalogs


def _load_mapping(path: Path, *, target_count: int):
    data = _load_json(path)
    try:
        mapping = validate_mapping_document(data, target_count=target_count)
    except MappingError as error:
        raise GameCatalogError(str(error)) from error
    if not mapping.coverage_eligible:
        raise GameCatalogError(f"{path}: mapping must be authoritative and verified")
    expected_locales = tuple(LOCALE_IDS)
    if tuple(mapping.locale_ids) != expected_locales:
        raise GameCatalogError(
            f"{path}: mapping locale_ids must be {expected_locales}, got {mapping.locale_ids}"
        )
    if len(mapping.rows) != target_count:
        raise GameCatalogError(
            f"{path}: mapping row count {len(mapping.rows)} does not match "
            f"target count {target_count}"
        )
    return mapping


def _encode_control_unit(value: int) -> bytes:
    low = value & 0xFF
    high = (value >> 8) & 0xFF
    chunk = bytes((low,))
    if high:
        chunk += bytes((high,))
    if b"\x00" in chunk:
        raise GameCatalogError(
            f"control unit 0x{value:04X} encodes an embedded NUL byte and cannot be stored"
        )
    return chunk


def encode_canonical_text(text: str) -> bytes:
    try:
        units = expand_canonical_text(text)
    except ControlSyntaxError as error:
        raise GameCatalogError(str(error)) from error
    payload = bytearray()
    for unit in units:
        if isinstance(unit, str):
            encoded = unit.encode("utf-8")
            if b"\x00" in encoded:
                raise GameCatalogError("literal UTF-8 payload contains an embedded NUL byte")
            payload.extend(encoded)
        else:
            payload.extend(_encode_control_unit(unit))
    if b"\x00" in payload:
        raise GameCatalogError("encoded payload contains an embedded NUL byte")
    payload.append(0)
    return bytes(payload)


def _mapping_source_counts(mapping) -> Dict[str, int]:
    counts = Counter(row.source_kind for row in mapping.rows)
    return {kind: counts.get(kind, 0) for kind in SOURCE_KINDS}


def _normalize_enabled_locales(enabled_locales: Sequence[str]) -> Tuple[str, ...]:
    if isinstance(enabled_locales, str):
        requested = tuple(
            item.strip() for item in enabled_locales.split(",") if item.strip()
        )
    else:
        requested = tuple(enabled_locales)

    if not requested:
        raise GameCatalogError("enabled locales must not be empty")

    unsupported = sorted(set(requested) - set(LOCALE_IDS))
    if unsupported:
        raise GameCatalogError(
            f"unsupported enabled game-catalog locale(s) {unsupported!r}; "
            f"expected a subset of {LOCALE_IDS!r}"
        )

    if len(set(requested)) != len(requested):
        raise GameCatalogError("enabled game-catalog locales must not repeat")

    return tuple(locale for locale in LOCALE_IDS if locale in requested)


def _entry_for_locale(
    *,
    locale: str,
    row,
    indexed_sources: Mapping[str, Mapping[int, str]],
    raw_records: Mapping[str, str],
    authored_records: Mapping[str, Mapping[str, str]],
) -> EntryPayloadMeta:
    source = dict(row.source)
    if row.source_kind == "english_fallback":
        return EntryPayloadMeta(
            target_id=row.target_id,
            mapping_source_kind=row.source_kind,
            mapping_source=source,
            locale_provider_kind=None,
            source_text=None,
            encoded_bytes=None,
            fallback_kind=FALLBACK_KIND_EXPLICIT_ENGLISH,
            fallback_reason=source["reason"],
            note=None,
        )

    if row.source_kind == "indexed":
        source_id = int(source["id"], 16)
        if source_id not in indexed_sources[locale]:
            raise GameCatalogError(
                f"{locale}: missing indexed source {source['id']} for target "
                f"{format_message_id(row.target_id)}"
            )
        source_text = indexed_sources[locale][source_id]
        return EntryPayloadMeta(
            target_id=row.target_id,
            mapping_source_kind=row.source_kind,
            mapping_source=source,
            locale_provider_kind="indexed",
            source_text=source_text,
            encoded_bytes=encode_canonical_text(source_text),
            fallback_kind=FALLBACK_KIND_NONE,
            fallback_reason=None,
            note=None,
        )

    if row.source_kind == "raw":
        if locale == "zh-Hans":
            import_id = source["import_id"]
            if import_id not in raw_records:
                raise GameCatalogError(
                    f"{locale}: missing raw import {import_id!r} for target "
                    f"{format_message_id(row.target_id)}"
                )
            source_text = raw_records[import_id]
            return EntryPayloadMeta(
                target_id=row.target_id,
                mapping_source_kind=row.source_kind,
                mapping_source=source,
                locale_provider_kind="raw",
                source_text=source_text,
                encoded_bytes=encode_canonical_text(source_text),
                fallback_kind=FALLBACK_KIND_NONE,
                fallback_reason=None,
                note=None,
            )
        regional_sources = source.get("regional_sources", {})
        ja_source = regional_sources.get("ja", {}) if isinstance(regional_sources, dict) else {}
        ja_kind = ja_source.get("kind") if isinstance(ja_source, dict) else None
        if ja_kind == "literal":
            source_text = ja_source["text"]
            return EntryPayloadMeta(
                target_id=row.target_id,
                mapping_source_kind=row.source_kind,
                mapping_source=source,
                locale_provider_kind="raw",
                source_text=source_text,
                encoded_bytes=encode_canonical_text(source_text),
                fallback_kind=FALLBACK_KIND_NONE,
                fallback_reason=None,
                note=None,
            )
        symbol = ja_source.get("symbol") if ja_kind == "symbol" else None
        note = "verified raw mapping has no committed canonical ja payload source"
        if symbol:
            note += f"; evidence symbol={symbol}"
        return EntryPayloadMeta(
            target_id=row.target_id,
            mapping_source_kind=row.source_kind,
            mapping_source=source,
            locale_provider_kind=None,
            source_text=None,
            encoded_bytes=None,
            fallback_kind=FALLBACK_KIND_PROVIDER_UNAVAILABLE,
            fallback_reason="locale-provider-unavailable",
            note=note,
        )

    if row.source_kind == "authored":
        translation_key = source["translation_key"]
        locale_catalog = authored_records.get(locale)
        if locale_catalog is None or translation_key not in locale_catalog:
            raise GameCatalogError(
                f"{locale}: missing authored translation {translation_key!r} for target "
                f"{format_message_id(row.target_id)}"
            )
        source_text = locale_catalog[translation_key]
        return EntryPayloadMeta(
            target_id=row.target_id,
            mapping_source_kind=row.source_kind,
            mapping_source=source,
            locale_provider_kind="authored",
            source_text=source_text,
            encoded_bytes=encode_canonical_text(source_text),
            fallback_kind=FALLBACK_KIND_NONE,
            fallback_reason=None,
            note=None,
        )

    raise GameCatalogError(f"unsupported mapping source kind {row.source_kind!r}")


def _build_locale_bundle(
    *,
    locale: str,
    mapping,
    indexed_sources: Mapping[str, Mapping[int, str]],
    raw_records: Mapping[str, str],
    authored_records: Mapping[str, Mapping[str, str]],
    suffix_share: bool,
) -> LocaleCatalogBundle:
    entries = tuple(
        _entry_for_locale(
            locale=locale,
            row=row,
            indexed_sources=indexed_sources,
            raw_records=raw_records,
            authored_records=authored_records,
        )
        for row in mapping.rows
    )
    messages = tuple(entry.encoded_bytes for entry in entries)
    catalog = build_catalog(messages, suffix_share=suffix_share)
    return LocaleCatalogBundle(locale=locale, entries=entries, catalog=catalog)


def _entry_report(meta: EntryPayloadMeta, entry) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "target_id": format_message_id(meta.target_id),
        "present": meta.present,
        "mapping_source_kind": meta.mapping_source_kind,
        "mapping_source": meta.mapping_source,
        "provider_kind": meta.locale_provider_kind,
        "fallback_to_english": not meta.present,
        "fallback_kind": meta.fallback_kind,
        "fallback_reason": meta.fallback_reason,
        "pointer_offset": entry.pointer_offset,
        "compressed_size": entry.compressed_size,
        "bit_length": entry.bit_length,
        "max_decoded_bytes": entry.decoded_size,
        "shared_from": entry.shared_from,
        "decoded_sha256": entry.decoded_sha256,
    }
    if meta.note is not None:
        payload["note"] = meta.note
    return payload


def _entry_table_hash(entries: Sequence[Dict[str, Any]]) -> str:
    return _sha256_bytes(
        json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def _locale_report(bundle: LocaleCatalogBundle, *, suffix_share: bool) -> Dict[str, Any]:
    entry_reports = [
        _entry_report(meta, entry)
        for meta, entry in zip(bundle.entries, bundle.catalog.entries)
    ]
    provider_counts = Counter(
        meta.locale_provider_kind
        for meta in bundle.entries
        if meta.locale_provider_kind is not None
    )
    explicit_fallback_count = sum(
        1 for meta in bundle.entries if meta.fallback_kind == FALLBACK_KIND_EXPLICIT_ENGLISH
    )
    provider_unavailable_count = sum(
        1 for meta in bundle.entries if meta.fallback_kind == FALLBACK_KIND_PROVIDER_UNAVAILABLE
    )
    requirement_bytes = bundle.catalog.budget.max_decoded_bytes
    return {
        "codec_schema": CODEC_SCHEMA,
        "entry_count": len(bundle.entries),
        "present_count": sum(1 for meta in bundle.entries if meta.present),
        "absent_count": sum(1 for meta in bundle.entries if not meta.present),
        "explicit_fallback_count": explicit_fallback_count,
        "provider_unavailable_count": provider_unavailable_count,
        "provider_counts": {kind: provider_counts.get(kind, 0) for kind in PRESENT_PROVIDER_KINDS},
        "storage": {
            "target_bytes": TARGET_STORAGE_BYTES,
            "required_bytes": requirement_bytes,
            "assertion_bytes": max(TARGET_STORAGE_BYTES, requirement_bytes),
            "target_fits": requirement_bytes <= TARGET_STORAGE_BYTES,
        },
        "hashes": {
            "source_framed_sha256": bundle.catalog.budget.source_sha256,
            "round_trip_framed_sha256": bundle.catalog.budget.round_trip_sha256,
            "compressed_blob_sha256": bundle.catalog.budget.compressed_sha256,
            "node_table_sha256": bundle.catalog.budget.node_table_sha256,
            "entry_table_sha256": _entry_table_hash(entry_reports),
        },
        "huffman": {
            "root_index": bundle.catalog.root_index,
            "node_count": len(bundle.catalog.nodes),
            "nodes": list(bundle.catalog.nodes),
            "compressed_blob_hex": bundle.catalog.compressed_blob.hex(),
            "compressed_bytes": len(bundle.catalog.compressed_blob),
            "suffix_share": suffix_share,
        },
        "budget": bundle.catalog.budget.to_dict(),
        "entries": entry_reports,
    }


def _english_report(
    bundle: EnglishCatalogBundle, *, suffix_share: bool
) -> Dict[str, Any]:
    entry_reports = []
    for meta, entry in zip(bundle.entries, bundle.catalog.entries):
        entry_reports.append(
            {
                "target_id": format_message_id(meta.target_id),
                "definition": meta.definition,
                "present": True,
                "pointer_offset": entry.pointer_offset,
                "compressed_size": entry.compressed_size,
                "bit_length": entry.bit_length,
                "max_decoded_bytes": entry.decoded_size,
                "shared_from": entry.shared_from,
                "decoded_sha256": entry.decoded_sha256,
            }
        )
    requirement_bytes = bundle.catalog.budget.max_decoded_bytes
    return {
        "codec_schema": CODEC_SCHEMA,
        "entry_count": len(bundle.entries),
        "present_count": len(bundle.entries),
        "absent_count": 0,
        "storage": {
            "target_bytes": TARGET_STORAGE_BYTES,
            "required_bytes": requirement_bytes,
            "assertion_bytes": max(TARGET_STORAGE_BYTES, requirement_bytes),
            "target_fits": requirement_bytes <= TARGET_STORAGE_BYTES,
        },
        "hashes": {
            "source_framed_sha256": bundle.catalog.budget.source_sha256,
            "round_trip_framed_sha256": bundle.catalog.budget.round_trip_sha256,
            "compressed_blob_sha256": bundle.catalog.budget.compressed_sha256,
            "node_table_sha256": bundle.catalog.budget.node_table_sha256,
            "entry_table_sha256": _entry_table_hash(entry_reports),
        },
        "huffman": {
            "root_index": bundle.catalog.root_index,
            "node_count": len(bundle.catalog.nodes),
            "nodes": list(bundle.catalog.nodes),
            "compressed_blob_hex": bundle.catalog.compressed_blob.hex(),
            "compressed_bytes": len(bundle.catalog.compressed_blob),
            "suffix_share": suffix_share,
        },
        "budget": bundle.catalog.budget.to_dict(),
        "entries": entry_reports,
    }


def _build_report(
    *,
    english_report,
    mapping_source_counts,
    target_count,
    mapping,
    locale_reports,
    suffix_share: bool,
) -> Dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "kind": REPORT_KIND,
        "codec_schema": CODEC_SCHEMA,
        "suffix_share": suffix_share,
        "target_count": target_count,
        "mapping_authority": mapping.authority,
        "mapping_authoritative": mapping.authoritative,
        "mapping_source_counts": {
            **{kind: mapping_source_counts.get(kind, 0) for kind in SOURCE_KINDS},
            "unresolved": 0,
        },
        "storage_target_bytes": TARGET_STORAGE_BYTES,
        "enabled_locales": list(locale_reports),
        "compiled_locales": ["en", *locale_reports],
        "shared_english": english_report,
        "locales": locale_reports,
    }


def _build_budget(
    *,
    mapping_source_counts,
    english_bundle: EnglishCatalogBundle,
    locale_bundles: Sequence[LocaleCatalogBundle],
) -> Dict[str, Any]:
    locale_budget = {}
    english_node_bytes = len(english_bundle.catalog.nodes) * 4
    english_compressed_bytes = len(english_bundle.catalog.compressed_blob)
    english_entry_bytes = len(english_bundle.entries) * ENTRY_STRUCT_SIZE_BYTES
    english_estimated_bytes = (
        english_node_bytes
        + english_compressed_bytes
        + english_entry_bytes
        + LOCALE_CATALOG_STRUCT_SIZE_BYTES
    )
    total_node_bytes = english_node_bytes
    total_compressed_bytes = english_compressed_bytes
    total_entry_bytes = english_entry_bytes
    total_present = len(english_bundle.entries)
    total_absent = 0
    for bundle in locale_bundles:
        explicit_fallback_count = sum(
            1 for meta in bundle.entries if meta.fallback_kind == FALLBACK_KIND_EXPLICIT_ENGLISH
        )
        provider_unavailable_count = sum(
            1 for meta in bundle.entries if meta.fallback_kind == FALLBACK_KIND_PROVIDER_UNAVAILABLE
        )
        present_count = sum(1 for meta in bundle.entries if meta.present)
        absent_count = len(bundle.entries) - present_count
        node_bytes = len(bundle.catalog.nodes) * 4
        compressed_bytes = len(bundle.catalog.compressed_blob)
        entry_bytes = len(bundle.entries) * ENTRY_STRUCT_SIZE_BYTES
        estimated_bytes = (
            node_bytes
            + compressed_bytes
            + entry_bytes
            + LOCALE_CATALOG_STRUCT_SIZE_BYTES
        )
        requirement_bytes = bundle.catalog.budget.max_decoded_bytes
        total_node_bytes += node_bytes
        total_compressed_bytes += compressed_bytes
        total_entry_bytes += entry_bytes
        total_present += present_count
        total_absent += absent_count
        locale_budget[bundle.locale] = {
            "present_count": present_count,
            "absent_count": absent_count,
            "explicit_fallback_count": explicit_fallback_count,
            "provider_unavailable_count": provider_unavailable_count,
            "provider_counts": {
                kind: sum(1 for meta in bundle.entries if meta.locale_provider_kind == kind)
                for kind in PRESENT_PROVIDER_KINDS
            },
            "max_decoded_bytes": requirement_bytes,
            "storage_target_bytes": TARGET_STORAGE_BYTES,
            "storage_assertion_bytes": max(TARGET_STORAGE_BYTES, requirement_bytes),
            "storage_target_fits": requirement_bytes <= TARGET_STORAGE_BYTES,
            "node_bytes": node_bytes,
            "compressed_bytes": compressed_bytes,
            "entry_bytes": entry_bytes,
            "locale_catalog_struct_bytes": LOCALE_CATALOG_STRUCT_SIZE_BYTES,
            "estimated_total_c_bytes": estimated_bytes,
            "codec_budget": bundle.catalog.budget.to_dict(),
        }
    return {
        "schema_version": BUDGET_SCHEMA_VERSION,
        "kind": BUDGET_KIND,
        "storage_target_bytes": TARGET_STORAGE_BYTES,
        "enabled_locales": [bundle.locale for bundle in locale_bundles],
        "compiled_locales": ["en", *[bundle.locale for bundle in locale_bundles]],
        "mapping_source_counts": {
            **{kind: mapping_source_counts.get(kind, 0) for kind in SOURCE_KINDS},
            "unresolved": 0,
        },
        "shared_english": {
            "present_count": len(english_bundle.entries),
            "absent_count": 0,
            "max_decoded_bytes": english_bundle.catalog.budget.max_decoded_bytes,
            "storage_target_bytes": TARGET_STORAGE_BYTES,
            "storage_assertion_bytes": max(
                TARGET_STORAGE_BYTES,
                english_bundle.catalog.budget.max_decoded_bytes,
            ),
            "storage_target_fits": (
                english_bundle.catalog.budget.max_decoded_bytes
                <= TARGET_STORAGE_BYTES
            ),
            "node_bytes": english_node_bytes,
            "compressed_bytes": english_compressed_bytes,
            "entry_bytes": english_entry_bytes,
            "catalog_struct_bytes": LOCALE_CATALOG_STRUCT_SIZE_BYTES,
            "estimated_total_c_bytes": english_estimated_bytes,
            "codec_budget": english_bundle.catalog.budget.to_dict(),
        },
        "locales": locale_budget,
        "totals": {
            "present_count": total_present,
            "absent_count": total_absent,
            "node_bytes": total_node_bytes,
            "compressed_bytes": total_compressed_bytes,
            "entry_bytes": total_entry_bytes,
            "locale_catalog_struct_bytes": len(locale_bundles) * LOCALE_CATALOG_STRUCT_SIZE_BYTES,
            "shared_english_catalog_struct_bytes": LOCALE_CATALOG_STRUCT_SIZE_BYTES,
            "locale_pointer_array_bytes": LOCALE_POINTER_ARRAY_BYTES,
            "shared_english_bytes": english_estimated_bytes,
            "estimated_total_c_bytes": (
                total_node_bytes
                + total_compressed_bytes
                + total_entry_bytes
                + (len(locale_bundles) + 1) * LOCALE_CATALOG_STRUCT_SIZE_BYTES
                + LOCALE_POINTER_ARRAY_BYTES
            ),
        },
    }


def build_game_catalog(
    *,
    english_texts_path: Path = DEFAULT_ENGLISH_TEXTS_PATH,
    english_definitions_path: Path = DEFAULT_ENGLISH_DEFINITIONS_PATH,
    ja_indexed_path: Path = DEFAULT_JA_INDEXED_PATH,
    zh_indexed_path: Path = DEFAULT_ZH_INDEXED_PATH,
    zh_raw_path: Path = DEFAULT_ZH_RAW_PATH,
    mapping_path: Path = DEFAULT_MAPPING_PATH,
    target_header_path: Path = DEFAULT_TARGET_HEADER_PATH,
    authored_paths: Optional[Mapping[str, Path]] = None,
    enabled_locales: Sequence[str] = LOCALE_IDS,
    suffix_share: bool = True,
) -> GameCatalogBuild:
    enabled_locales = _normalize_enabled_locales(enabled_locales)
    target_count = len(load_fe8u_target_ids(target_header_path))
    english_entries = load_english_source_entries(
        english_texts_path,
        english_definitions_path,
        target_count=target_count,
    )
    english_bundle = EnglishCatalogBundle(
        locale="en",
        entries=english_entries,
        catalog=build_catalog(
            tuple(entry.encoded_bytes for entry in english_entries),
            suffix_share=suffix_share,
        ),
    )
    mapping = _load_mapping(mapping_path, target_count=target_count)
    indexed_sources = {}
    if "ja" in enabled_locales:
        indexed_sources["ja"] = _load_indexed(ja_indexed_path)
    if "zh-Hans" in enabled_locales:
        indexed_sources["zh-Hans"] = _load_indexed(zh_indexed_path)
    raw_records = (
        _load_raw_records(zh_raw_path) if "zh-Hans" in enabled_locales else {}
    )
    authored_records = _load_authored_catalogs(authored_paths)
    mapping_source_counts = _mapping_source_counts(mapping)
    locale_bundles = tuple(
        _build_locale_bundle(
            locale=locale,
            mapping=mapping,
            indexed_sources=indexed_sources,
            raw_records=raw_records,
            authored_records=authored_records,
            suffix_share=suffix_share,
        )
        for locale in enabled_locales
    )
    locale_reports = {
        bundle.locale: _locale_report(bundle, suffix_share=suffix_share)
        for bundle in locale_bundles
    }
    english_report = _english_report(english_bundle, suffix_share=suffix_share)
    report = _build_report(
        english_report=english_report,
        mapping_source_counts=mapping_source_counts,
        target_count=target_count,
        mapping=mapping,
        locale_reports=locale_reports,
        suffix_share=suffix_share,
    )
    budget = _build_budget(
        mapping_source_counts=mapping_source_counts,
        english_bundle=english_bundle,
        locale_bundles=locale_bundles,
    )
    return GameCatalogBuild(
        target_count=target_count,
        mapping=mapping,
        mapping_source_counts=mapping_source_counts,
        english=english_bundle,
        locales=locale_bundles,
        report=report,
        budget=budget,
        suffix_share=suffix_share,
    )


def _write_text_if_changed(path: Path, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def _write_bytes_if_changed(path: Path, content: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == content:
        return False
    path.write_bytes(content)
    return True


def write_build(build: GameCatalogBuild, *, output_dir: Path) -> Dict[str, Path]:
    output_dir = Path(output_dir)
    config_header_path = output_dir / OUTPUT_CONFIG_HEADER_NAME
    header_path = output_dir / OUTPUT_HEADER_NAME
    source_path = output_dir / OUTPUT_SOURCE_NAME
    report_path = output_dir / OUTPUT_REPORT_NAME
    budget_path = output_dir / OUTPUT_BUDGET_NAME

    _write_text_if_changed(config_header_path, render_config_header(build))
    _write_text_if_changed(header_path, render_header(build))
    _write_text_if_changed(source_path, render_source(build))
    _write_bytes_if_changed(report_path, canonical_json_bytes(build.report))
    _write_bytes_if_changed(budget_path, canonical_json_bytes(build.budget))
    return {
        "config_header": config_header_path,
        "header": header_path,
        "source": source_path,
        "report_json": report_path,
        "budget_json": budget_path,
    }


def generate(
    *,
    output_dir: Path,
    english_texts_path: Path = DEFAULT_ENGLISH_TEXTS_PATH,
    english_definitions_path: Path = DEFAULT_ENGLISH_DEFINITIONS_PATH,
    ja_indexed_path: Path = DEFAULT_JA_INDEXED_PATH,
    zh_indexed_path: Path = DEFAULT_ZH_INDEXED_PATH,
    zh_raw_path: Path = DEFAULT_ZH_RAW_PATH,
    mapping_path: Path = DEFAULT_MAPPING_PATH,
    target_header_path: Path = DEFAULT_TARGET_HEADER_PATH,
    authored_paths: Optional[Mapping[str, Path]] = None,
    enabled_locales: Sequence[str] = LOCALE_IDS,
    suffix_share: bool = True,
) -> Dict[str, Path]:
    build = build_game_catalog(
        english_texts_path=english_texts_path,
        english_definitions_path=english_definitions_path,
        ja_indexed_path=ja_indexed_path,
        zh_indexed_path=zh_indexed_path,
        zh_raw_path=zh_raw_path,
        mapping_path=mapping_path,
        target_header_path=target_header_path,
        authored_paths=authored_paths,
        enabled_locales=enabled_locales,
        suffix_share=suffix_share,
    )
    return write_build(build, output_dir=output_dir)
