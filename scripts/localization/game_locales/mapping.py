"""Sparse FE8U-target mapping schema and authority-aware validation."""

from __future__ import annotations

import ast
import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from .parsers import FE8J_MAX_INDEXED_ID

MAPPING_SCHEMA_VERSION = 2
MAPPING_KIND = "fe8u-locale-mapping"
AUTHORITY_CANDIDATE = "candidate"
AUTHORITY_VERIFIED = "verified"
ROW_CANDIDATE = "candidate"
ROW_VERIFIED = "verified"
SOURCE_KINDS = ("indexed", "raw", "authored", "english_fallback")
LOCALE_IDS = ("ja", "zh-Hans")
VERIFICATION_CONFIDENCE = ("high", "manual", "explicit")

_ID_RE = re.compile(r"0x([0-9A-F]{4})")
_RAW_IMPORT_ID_RE = re.compile(r"fe8cn\.raw\.import-[0-9]{4}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_LITERAL_SOURCE_KEY_RE = re.compile(r"message_id=0x([0-9A-F]{4})")
_C_STRING_ENTRY_RE = re.compile(
    r'^\s*"((?:\\.|[^"\\])*)"\s*,\s*(0[xX][0-9A-Fa-f]+|[0-9]+)\b',
    re.DOTALL,
)
_COMMITTED_SOURCE_SUFFIXES = (".c", ".h")


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


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _scan_balanced_source(text: str, opening: int, field: str) -> Tuple[str, int]:
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
    raise MappingError(f"{field} references an unterminated source initializer")


def _top_level_source_entries(body: str, field: str) -> List[str]:
    entries = []
    index = 0
    while index < len(body):
        if body[index] == "{":
            entry, index = _scan_balanced_source(body, index, field)
            entries.append(entry)
        else:
            index += 1
    return entries


def _decode_c_string(value: str, field: str) -> str:
    if "\\" not in value:
        return value
    try:
        decoded = ast.literal_eval(f'"{value}"')
    except (SyntaxError, ValueError) as error:
        raise MappingError(f"{field} contains an unsupported C string escape") from error
    if not isinstance(decoded, str):
        raise MappingError(f"{field} did not decode to a string")
    return decoded


def _resolve_committed_source(
    source_path: str,
    *,
    field: str,
    repo_root: Optional[Path],
) -> Path:
    relative = PurePosixPath(source_path)
    if relative.is_absolute() or ".." in relative.parts or str(relative) != source_path:
        raise MappingError(f"{field}.source_path must be a canonical repository-relative path")
    if relative.suffix not in _COMMITTED_SOURCE_SUFFIXES:
        raise MappingError(
            f"{field}.source_path must reference committed C source/header content"
        )
    root = Path(repo_root) if repo_root is not None else _default_repo_root()
    root = root.resolve()
    path = (root / source_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise MappingError(f"{field}.source_path escapes the repository") from error
    if not path.is_file():
        raise MappingError(f"{field}.source_path does not exist: {source_path}")
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", source_path],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if tracked.returncode != 0:
        raise MappingError(f"{field}.source_path is not committed: {source_path}")
    return path


def literal_context_hashes(
    *,
    text: str,
    provenance: Dict[str, Any],
    field: str,
    repo_root: Optional[Path] = None,
) -> Tuple[int, Tuple[str, ...]]:
    source_path = _require_nonempty_string(
        provenance.get("source_path"), f"{field}.source_path"
    )
    source_symbol = _require_nonempty_string(
        provenance.get("source_symbol"), f"{field}.source_symbol"
    )
    if not _IDENTIFIER_RE.fullmatch(source_symbol):
        raise MappingError(f"{field}.source_symbol must be a C identifier")
    source_key = _require_nonempty_string(
        provenance.get("source_key"), f"{field}.source_key"
    )
    key_match = _LITERAL_SOURCE_KEY_RE.fullmatch(source_key)
    if not key_match:
        raise MappingError(f"{field}.source_key must use message_id=0xNNNN form")
    source_key_id = int(key_match.group(1), 16)

    path = _resolve_committed_source(
        source_path,
        field=field,
        repo_root=repo_root,
    )
    source = path.read_text(encoding="utf-8")
    definition = re.search(
        rf"\b{re.escape(source_symbol)}\s*\[[^\]]*\][^=;]*=\s*\{{",
        source,
    )
    if not definition:
        raise MappingError(
            f"{field}.source_symbol is absent from {source_path}: {source_symbol}"
        )
    opening = source.find("{", definition.start())
    body, _ = _scan_balanced_source(source, opening, field)
    keyed_entries = []
    literal_entries = []
    for entry in _top_level_source_entries(body, field):
        match = _C_STRING_ENTRY_RE.match(entry)
        if not match or int(match.group(2), 0) != source_key_id:
            continue
        keyed_entries.append(entry)
        if _decode_c_string(match.group(1), field) == text:
            literal_entries.append(entry)
    if not keyed_entries:
        raise MappingError(
            f"{field}.source_key is absent from {source_symbol}: {source_key}"
        )
    if not literal_entries:
        raise MappingError(
            f"{field} literal does not match {source_symbol} {source_key}"
        )
    return source_key_id, tuple(
        hashlib.sha256(entry.strip().encode("utf-8")).hexdigest()
        for entry in literal_entries
    )


def validate_source_provider(
    source: Dict[str, Any],
    field: str,
    *,
    target_id: Optional[int] = None,
    repo_root: Optional[Path] = None,
) -> str:
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
        import_id = source.get("import_id")
        if not isinstance(import_id, str) or not _RAW_IMPORT_ID_RE.fullmatch(import_id):
            raise MappingError(
                f"{field}.import_id must use stable fe8cn.raw.import-NNNN form"
            )
        if "key" in source or "address" in source:
            raise MappingError(
                f"{field} must not use address-derived identity or embed provenance"
            )
        alternate_import_ids = source.get("alternate_import_ids", [])
        if not isinstance(alternate_import_ids, list) or any(
            not isinstance(value, str) or not _RAW_IMPORT_ID_RE.fullmatch(value)
            for value in alternate_import_ids
        ):
            raise MappingError(
                f"{field}.alternate_import_ids must contain stable import IDs"
            )
        if len(set(alternate_import_ids)) != len(alternate_import_ids):
            raise MappingError(f"{field}.alternate_import_ids must be unique")
        regional_sources = source.get("regional_sources")
        if regional_sources is not None:
            regional_sources = _require_dict(
                regional_sources, f"{field}.regional_sources"
            )
            ja_source = _require_dict(
                regional_sources.get("ja"), f"{field}.regional_sources.ja"
            )
            ja_kind = ja_source.get("kind")
            if ja_kind not in ("symbol", "literal"):
                raise MappingError(
                    f"{field}.regional_sources.ja.kind must be 'symbol' or 'literal'"
                )
            if ja_kind == "symbol":
                _require_nonempty_string(
                    ja_source.get("symbol"), f"{field}.regional_sources.ja.symbol"
                )
            else:
                literal_text = _require_nonempty_string(
                    ja_source.get("text"), f"{field}.regional_sources.ja.text"
                )
                provenance = _require_dict(
                    ja_source.get("provenance"),
                    f"{field}.regional_sources.ja.provenance",
                )
                provenance_field = f"{field}.regional_sources.ja.provenance"
                source_key_id, context_hashes = literal_context_hashes(
                    text=literal_text,
                    provenance=provenance,
                    field=provenance_field,
                    repo_root=repo_root,
                )
                if target_id is not None and source_key_id != target_id:
                    raise MappingError(
                        f"{provenance_field}.source_key must match target "
                        f"{format_message_id(target_id)}"
                    )
                context_sha256 = provenance.get("context_sha256")
                if not isinstance(context_sha256, str) or not _SHA256_RE.fullmatch(
                    context_sha256
                ):
                    raise MappingError(
                        f"{provenance_field}.context_sha256 must be 64 lowercase hex digits"
                    )
                if context_sha256 not in context_hashes:
                    raise MappingError(
                        f"{provenance_field}.context_sha256 does not match committed source context"
                    )
            cn_source = _require_dict(
                regional_sources.get("zh-Hans"),
                f"{field}.regional_sources.zh-Hans",
            )
            if cn_source.get("kind") != "import":
                raise MappingError(
                    f"{field}.regional_sources.zh-Hans.kind must be 'import'"
                )
            if cn_source.get("import_id") != import_id:
                raise MappingError(
                    f"{field}.regional_sources.zh-Hans.import_id must match import_id"
                )
    elif kind == "authored":
        _require_nonempty_string(source.get("translation_key"), f"{field}.translation_key")
    elif kind == "english_fallback":
        _require_nonempty_string(source.get("reason"), f"{field}.reason")
    return kind


def validate_mapping_document(
    data: Any,
    *,
    target_count: Optional[int] = None,
    repo_root: Optional[Path] = None,
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
        _require_nonempty_string(
            provenance.get("committed_snapshot"),
            "mapping.provenance.committed_snapshot",
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
        source_kind = validate_source_provider(
            source,
            f"{field}.source",
            target_id=target_id,
            repo_root=repo_root,
        )

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
            for verification_field in (
                "evidence_kind",
                "source_table",
                "source_symbol",
                "source_key",
                "subsystem",
                "rationale",
            ):
                _require_nonempty_string(
                    verified.get(verification_field),
                    f"{field}.verification.{verification_field}",
                )
            if verified.get("confidence") not in VERIFICATION_CONFIDENCE:
                raise MappingError(
                    f"{field}.verification.confidence must be one of "
                    f"{VERIFICATION_CONFIDENCE}"
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
