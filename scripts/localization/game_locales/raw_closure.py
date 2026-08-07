"""Machine-checked closure ledger for FE8CN raw localized string records."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .mapping import MappingError, validate_mapping_document

CLOSURE_SCHEMA_VERSION = 1
DECISIONS_KIND = "fe8cn-raw-surface-decisions"
CLOSURE_KIND = "fe8cn-raw-surface-closure"
DECISION_CLASSES = (
    "game_message",
    "expansion_message",
    "non_user_facing_exclusion",
    "diagnostic_exclusion",
    "english_fallback",
)
_IMPORT_ID_RE = re.compile(r"fe8cn\.raw\.import-[0-9]{4}")
_TARGET_ID_RE = re.compile(r"0x[0-9A-F]{4}")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class RawClosureError(MappingError):
    """Raised when a raw import lacks a durable closure decision."""


def canonical_json_bytes(data: Any) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _require_dict(value: Any, field: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise RawClosureError(f"{field} must be an object")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RawClosureError(f"{field} must be a non-empty string")
    return value


def _load_raw_records(data: Any) -> Dict[str, Dict[str, Any]]:
    document = _require_dict(data, "raw")
    if document.get("schema_version") != 2:
        raise RawClosureError("raw.schema_version must be 2")
    records = document.get("records")
    if not isinstance(records, list):
        raise RawClosureError("raw.records must be an array")
    result: Dict[str, Dict[str, Any]] = {}
    for index, record in enumerate(records):
        field = f"raw.records[{index}]"
        record = _require_dict(record, field)
        import_id = _require_string(record.get("import_id"), f"{field}.import_id")
        if not _IMPORT_ID_RE.fullmatch(import_id):
            raise RawClosureError(f"{field}.import_id is not canonical")
        _require_string(record.get("text"), f"{field}.text")
        provenance = _require_dict(record.get("provenance"), f"{field}.provenance")
        _require_string(provenance.get("address"), f"{field}.provenance.address")
        if import_id in result:
            raise RawClosureError(f"duplicate raw import {import_id}")
        result[import_id] = record
    return result


def _validate_call_sites(
    call_sites: Any,
    *,
    field: str,
    repo_root: Path,
) -> List[Dict[str, Any]]:
    if not isinstance(call_sites, list) or not call_sites:
        raise RawClosureError(f"{field} must be a non-empty array")
    normalized = []
    for index, raw_site in enumerate(call_sites):
        site_field = f"{field}[{index}]"
        site = _require_dict(raw_site, site_field)
        relative_path = _require_string(site.get("path"), f"{site_field}.path")
        anchors = site.get("anchors")
        if not isinstance(anchors, list) or not anchors:
            raise RawClosureError(f"{site_field}.anchors must be a non-empty array")
        if any(not isinstance(anchor, str) or not anchor for anchor in anchors):
            raise RawClosureError(
                f"{site_field}.anchors must contain non-empty strings"
            )
        path = repo_root / relative_path
        if not path.is_file():
            raise RawClosureError(f"{site_field}.path disappeared: {relative_path}")
        source = path.read_text(encoding="utf-8")
        if not any(anchor in source for anchor in anchors):
            raise RawClosureError(
                f"{site_field} has no surviving anchor in {relative_path}: {anchors}"
            )
        normalized.append({"anchors": list(anchors), "path": relative_path})
    return normalized


def _validate_decisions(
    data: Any,
    *,
    raw_records: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> Dict[str, Dict[str, Any]]:
    document = _require_dict(data, "decisions")
    if document.get("schema_version") != CLOSURE_SCHEMA_VERSION:
        raise RawClosureError(
            f"decisions.schema_version must be {CLOSURE_SCHEMA_VERSION}"
        )
    if document.get("kind") != DECISIONS_KIND:
        raise RawClosureError(f"decisions.kind must be {DECISIONS_KIND!r}")
    rows = document.get("decisions")
    if not isinstance(rows, list):
        raise RawClosureError("decisions.decisions must be an array")
    if document.get("deferred_record_count") != len(rows):
        raise RawClosureError("decisions.deferred_record_count does not match rows")

    result: Dict[str, Dict[str, Any]] = {}
    for index, raw_decision in enumerate(rows):
        field = f"decisions.decisions[{index}]"
        decision = _require_dict(raw_decision, field)
        import_id = _require_string(decision.get("import_id"), f"{field}.import_id")
        if import_id not in raw_records:
            raise RawClosureError(f"{field}.import_id is absent from raw source")
        if import_id in result:
            raise RawClosureError(f"duplicate deferred decision {import_id}")
        classification = decision.get("classification")
        if classification not in DECISION_CLASSES:
            raise RawClosureError(
                f"{field}.classification must be one of {DECISION_CLASSES}"
            )
        user_facing = decision.get("user_facing")
        if not isinstance(user_facing, bool):
            raise RawClosureError(f"{field}.user_facing must be a boolean")
        if classification.endswith("_exclusion") and user_facing:
            raise RawClosureError(f"{field} exclusions cannot be user-facing")
        if classification in ("game_message", "expansion_message") and not user_facing:
            raise RawClosureError(f"{field} localized decisions must be user-facing")
        _require_string(decision.get("rationale"), f"{field}.rationale")
        normalized = dict(decision)
        normalized["call_sites"] = _validate_call_sites(
            decision.get("call_sites"),
            field=f"{field}.call_sites",
            repo_root=repo_root,
        )
        if classification == "game_message":
            target_id = decision.get("target_id")
            if not isinstance(target_id, str) or not _TARGET_ID_RE.fullmatch(target_id):
                raise RawClosureError(
                    f"{field}.target_id must use canonical 0xNNNN form"
                )
        elif classification == "expansion_message":
            _require_string(decision.get("expansion_key"), f"{field}.expansion_key")
        elif classification == "english_fallback":
            _require_string(decision.get("fallback_reason"), f"{field}.fallback_reason")
        result[import_id] = normalized
    return result


def _mapped_imports(
    mapping_data: Any,
    *,
    repo_root: Path,
) -> Dict[str, Dict[str, Any]]:
    try:
        mapping = validate_mapping_document(mapping_data, repo_root=repo_root)
    except MappingError as error:
        raise RawClosureError(f"mapping literal evidence failed: {error}") from error
    result: Dict[str, Dict[str, Any]] = {}
    for row in mapping.rows:
        if row.source_kind != "raw":
            continue
        for import_id in (
            row.source["import_id"],
            *row.source.get("alternate_import_ids", []),
        ):
            if import_id in result:
                raise RawClosureError(f"{import_id} maps to more than one FE8U target")
            result[import_id] = {
                "row": row,
                "target_id": f"0x{row.target_id:04X}",
            }
    return result


def _derived_call_sites(row: Any, repo_root: Path) -> List[Dict[str, Any]]:
    verification = row.verification or {}
    source_paths = verification.get("source_paths", {})
    relative_path = source_paths.get("fe8u")
    if not relative_path:
        raise RawClosureError(
            f"0x{row.target_id:04X} raw mapping lacks an FE8U call-site path"
        )
    source_key = verification.get("source_key", "")
    anchors = [verification.get("source_symbol", ""), source_key]
    anchors.extend(_IDENTIFIER_RE.findall(source_key))
    anchors = list(dict.fromkeys(anchor for anchor in anchors if anchor))
    return _validate_call_sites(
        [{"path": relative_path, "anchors": anchors}],
        field=f"mapping.0x{row.target_id:04X}.call_sites",
        repo_root=repo_root,
    )


def _active_registry_keys(registry_data: Any) -> set[str]:
    registry = _require_dict(registry_data, "registry")
    messages = registry.get("messages")
    if not isinstance(messages, list):
        raise RawClosureError("registry.messages must be an array")
    return {
        row["key"]
        for row in messages
        if isinstance(row, dict) and row.get("status") == "active"
    }


def _catalog_strings(data: Any, locale: str) -> Dict[str, str]:
    catalog = _require_dict(data, f"catalog.{locale}")
    if catalog.get("locale") != locale:
        raise RawClosureError(f"catalog.{locale}.locale must be {locale!r}")
    strings = catalog.get("strings")
    if not isinstance(strings, dict):
        raise RawClosureError(f"catalog.{locale}.strings must be an object")
    return strings


def build_raw_surface_closure(
    *,
    raw_data: Any,
    mapping_data: Any,
    decisions_data: Any,
    registry_data: Any,
    catalog_data: Mapping[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    repo_root = Path(repo_root)
    raw_records = _load_raw_records(raw_data)
    decisions = _validate_decisions(
        decisions_data,
        raw_records=raw_records,
        repo_root=repo_root,
    )
    mapped = _mapped_imports(mapping_data, repo_root=repo_root)
    active_keys = _active_registry_keys(registry_data)
    catalogs = {
        locale: _catalog_strings(catalog_data[locale], locale)
        for locale in ("en", "ja", "zh-Hans")
    }

    rows = []
    for import_id, raw_record in sorted(raw_records.items()):
        source_hash = hashlib.sha256(
            raw_record["text"].encode("utf-8")
        ).hexdigest()
        decision = decisions.get(import_id)
        if decision is None:
            mapped_entry = mapped.get(import_id)
            if mapped_entry is None:
                raise RawClosureError(f"{import_id} has no closure decision")
            row = mapped_entry["row"]
            closure_row = {
                "call_sites": _derived_call_sites(row, repo_root),
                "classification": "game_message",
                "decision_origin": "verified-game-map",
                "import_id": import_id,
                "rationale": row.verification["rationale"],
                "source_text_sha256": source_hash,
                "target_id": mapped_entry["target_id"],
                "user_facing": True,
            }
        else:
            classification = decision["classification"]
            closure_row = {
                "call_sites": decision["call_sites"],
                "classification": classification,
                "decision_origin": "deferred-surface-audit",
                "import_id": import_id,
                "rationale": decision["rationale"],
                "source_text_sha256": source_hash,
                "user_facing": decision["user_facing"],
            }
            if classification == "game_message":
                mapped_entry = mapped.get(import_id)
                if mapped_entry is None:
                    raise RawClosureError(
                        f"{import_id} game-message decision is absent from verified mapping"
                    )
                if mapped_entry["target_id"] != decision["target_id"]:
                    raise RawClosureError(
                        f"{import_id} target mismatch: {decision['target_id']} vs "
                        f"{mapped_entry['target_id']}"
                    )
                ja_source = mapped_entry["row"].source.get(
                    "regional_sources", {}
                ).get("ja", {})
                if ja_source.get("kind") != "literal":
                    raise RawClosureError(
                        f"{import_id} deferred game-message decision lacks canonical ja text"
                    )
                closure_row["target_id"] = decision["target_id"]
            elif classification == "expansion_message":
                key = decision["expansion_key"]
                if key not in active_keys:
                    raise RawClosureError(
                        f"{import_id} expansion key {key!r} is not active"
                    )
                for locale, strings in catalogs.items():
                    if not isinstance(strings.get(key), str) or not strings[key]:
                        raise RawClosureError(
                            f"{import_id} expansion key {key!r} is missing in {locale}"
                        )
                if catalogs["zh-Hans"][key] != raw_record["text"]:
                    raise RawClosureError(
                        f"{import_id} zh-Hans expansion text must equal imported raw payload"
                    )
                closure_row["expansion_key"] = key
            elif classification == "english_fallback":
                closure_row["fallback_reason"] = decision["fallback_reason"]
        closure_row["provenance"] = {
            "address": raw_record["provenance"]["address"],
        }
        rows.append(closure_row)

    counts = {
        classification: sum(
            1 for row in rows if row["classification"] == classification
        )
        for classification in DECISION_CLASSES
    }
    unresolved = len(raw_records) - len(rows)
    summary = {
        "baseline_game_message_count": sum(
            1 for row in rows if row["decision_origin"] == "verified-game-map"
        ),
        "deferred_decision_count": len(decisions),
        "diagnostic_exclusion_count": counts["diagnostic_exclusion"],
        "english_fallback_count": counts["english_fallback"],
        "expansion_message_count": counts["expansion_message"],
        "game_message_count": counts["game_message"],
        "non_user_facing_exclusion_count": counts["non_user_facing_exclusion"],
        "total_count": len(raw_records),
        "unresolved_count": unresolved,
        "user_facing_deferred_localized_count": sum(
            1
            for row in rows
            if row["decision_origin"] == "deferred-surface-audit"
            and row["user_facing"]
            and row["classification"] in ("game_message", "expansion_message")
        ),
    }
    if unresolved:
        raise RawClosureError(f"raw closure has {unresolved} unresolved records")
    return {
        "kind": CLOSURE_KIND,
        "rows": rows,
        "schema_version": CLOSURE_SCHEMA_VERSION,
        "summary": summary,
    }
