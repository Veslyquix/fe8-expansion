"""Registry/catalog loading and validation (issue #18 sprint 1).

Loads texts/expansion/registry.json (the stable numeric-ID message
registry) and texts/expansion/catalog.en.json (the UTF-8/ASCII English
catalog), validates both against schema.py's contract, derives the
qps-ploc pseudo-locale catalog deterministically (pseudo.py), and exposes
a single ``LoadedCatalog`` the generator (generate.py) and CLI (cli.py)
both consume.

Every check here is a build-time validation gate, not a runtime one --
see src/expansion_locale.c for the separate, much smaller set of runtime
defensive checks (bounded scratch, missing-marker fallback) that must
hold even if this validation is somehow bypassed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import schema
from .pseudo import pseudoize

_PLACEHOLDER_RE = re.compile(r"\{[0-9]+\}")

DEFAULT_REGISTRY_PATH = Path("texts/expansion/registry.json")
DEFAULT_CATALOG_EN_PATH = Path("texts/expansion/catalog.en.json")


@dataclass(frozen=True)
class RegistryEntry:
    id: int
    key: str
    status: str
    surface: Optional[str] = None
    max_width: Optional[int] = None
    max_decoded_bytes: Optional[int] = None
    notes: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.status == schema.STATUS_ACTIVE


@dataclass(frozen=True)
class LoadedCatalog:
    entries: Tuple[RegistryEntry, ...]
    active_entries: Tuple[RegistryEntry, ...]
    tombstone_entries: Tuple[RegistryEntry, ...]
    en_strings: Dict[str, str]
    pseudo_strings: Dict[str, str]

    def active_by_key(self) -> Dict[str, RegistryEntry]:
        return {entry.key: entry for entry in self.active_entries}


def _require_int(value, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise schema.SchemaError(f"{field} must be an integer, got {value!r}")
    return value


def _require_str(value, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise schema.SchemaError(f"{field} must be a non-empty string, got {value!r}")
    return value


def parse_registry(data: dict) -> Tuple[RegistryEntry, ...]:
    if not isinstance(data, dict) or "messages" not in data:
        raise schema.SchemaError("registry JSON must be an object with a 'messages' array")
    raw_messages = data["messages"]
    if not isinstance(raw_messages, list) or not raw_messages:
        raise schema.SchemaError("registry 'messages' must be a non-empty array")

    entries: List[RegistryEntry] = []
    seen_ids = set()
    seen_keys = set()
    previous_id: Optional[int] = None

    for raw in raw_messages:
        entry_id = _require_int(raw.get("id"), "message id")
        key = _require_str(raw.get("key"), "message key")
        status = raw.get("status")
        if status not in schema.STATUSES:
            raise schema.SchemaError(
                f"message {key!r} (id {entry_id}) has invalid status {status!r}; "
                f"expected one of {schema.STATUSES}"
            )
        if entry_id < schema.MSG_ID_MIN or entry_id > schema.MSG_ID_MAX:
            raise schema.SchemaError(
                f"message {key!r} has id {entry_id} outside the assignable "
                f"ExpansionMsgId range [{schema.MSG_ID_MIN}, {schema.MSG_ID_MAX}]; "
                f"{schema.MSG_ID_INVALID} (0x{schema.MSG_ID_INVALID:04X}) is the "
                f"reserved EXPANSION_MSG_ID_INVALID sentinel and can never be "
                f"assigned to a real message"
            )
        if entry_id in seen_ids:
            raise schema.SchemaError(f"duplicate message id {entry_id} (key {key!r})")
        if previous_id is not None and entry_id <= previous_id:
            raise schema.SchemaError(
                f"registry ids must be strictly ascending and sorted in the file; "
                f"id {entry_id} (key {key!r}) is not greater than the previous id "
                f"{previous_id}"
            )
        if key in seen_keys:
            raise schema.SchemaError(f"duplicate message key {key!r} (id {entry_id})")
        seen_ids.add(entry_id)
        seen_keys.add(key)
        previous_id = entry_id

        if status == schema.STATUS_TOMBSTONE:
            entries.append(
                RegistryEntry(
                    id=entry_id,
                    key=key,
                    status=status,
                    notes=raw.get("notes"),
                )
            )
            continue

        surface = raw.get("surface")
        if surface not in schema.SURFACES:
            raise schema.SchemaError(
                f"message {key!r} (id {entry_id}) has invalid surface {surface!r}; "
                f"expected one of {schema.SURFACES}"
            )
        max_width = _require_int(raw.get("max_width"), f"{key} max_width")
        if not (schema.MAX_WIDTH_MIN <= max_width <= schema.MAX_WIDTH_MAX):
            raise schema.SchemaError(
                f"message {key!r} max_width {max_width} out of range "
                f"[{schema.MAX_WIDTH_MIN}, {schema.MAX_WIDTH_MAX}]"
            )
        max_decoded_bytes = _require_int(raw.get("max_decoded_bytes"), f"{key} max_decoded_bytes")
        if not (schema.MAX_DECODED_BYTES_MIN <= max_decoded_bytes <= schema.MAX_DECODED_BYTES_MAX):
            raise schema.SchemaError(
                f"message {key!r} max_decoded_bytes {max_decoded_bytes} out of range "
                f"[{schema.MAX_DECODED_BYTES_MIN}, {schema.MAX_DECODED_BYTES_MAX}]"
            )
        entries.append(
            RegistryEntry(
                id=entry_id,
                key=key,
                status=status,
                surface=surface,
                max_width=max_width,
                max_decoded_bytes=max_decoded_bytes,
                notes=raw.get("notes"),
            )
        )

    return tuple(entries)


def _check_ascii_text(text: str, key: str) -> None:
    for token in schema.ALLOWED_CONTROL_TOKENS:
        text = text.replace(token, "")
    for ch in text:
        code = ord(ch)
        if not (schema.ASCII_MIN <= code <= schema.ASCII_MAX):
            raise schema.SchemaError(
                f"message {key!r} contains a non-ASCII/non-printable character "
                f"U+{code:04X}; only printable ASCII (0x20-0x7E) plus "
                f"{schema.ALLOWED_CONTROL_TOKENS!r} are allowed in sprint 1"
            )


def _check_width_and_bytes(text: str, key: str, entry: RegistryEntry, locale: str) -> None:
    for line in text.split("\n"):
        if len(line) > entry.max_width:
            raise schema.SchemaError(
                f"message {key!r} locale {locale!r} line {line!r} is {len(line)} "
                f"columns wide; exceeds max_width {entry.max_width}"
            )
    encoded_len = len(text.encode("ascii")) + 1  # +1 for the NUL terminator
    if encoded_len > entry.max_decoded_bytes:
        raise schema.SchemaError(
            f"message {key!r} locale {locale!r} decodes to {encoded_len} bytes "
            f"(including NUL); exceeds max_decoded_bytes {entry.max_decoded_bytes}"
        )


def _placeholder_tokens(text: str) -> List[str]:
    return _PLACEHOLDER_RE.findall(text)


def load_catalog(
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    catalog_en_path: Path = DEFAULT_CATALOG_EN_PATH,
) -> LoadedCatalog:
    registry_path = Path(registry_path)
    catalog_en_path = Path(catalog_en_path)

    if not registry_path.is_file():
        raise schema.SchemaError(f"registry not found: {registry_path}")
    if not catalog_en_path.is_file():
        raise schema.SchemaError(f"English catalog not found: {catalog_en_path}")

    registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = parse_registry(registry_data)
    active_entries = tuple(e for e in entries if e.is_active)
    tombstone_entries = tuple(e for e in entries if not e.is_active)

    catalog_data = json.loads(catalog_en_path.read_text(encoding="utf-8"))
    if not isinstance(catalog_data, dict) or "strings" not in catalog_data:
        raise schema.SchemaError(
            f"{catalog_en_path} must be an object with a 'strings' map"
        )
    if catalog_data.get("locale") != "en":
        raise schema.SchemaError(f"{catalog_en_path} 'locale' field must be 'en'")
    en_strings_raw = catalog_data["strings"]
    if not isinstance(en_strings_raw, dict):
        raise schema.SchemaError(f"{catalog_en_path} 'strings' must be an object")

    active_keys = {e.key for e in active_entries}
    catalog_keys = set(en_strings_raw.keys())

    missing = sorted(active_keys - catalog_keys)
    if missing:
        raise schema.SchemaError(
            f"English catalog is missing required active message(s): {missing}"
        )
    extra = sorted(catalog_keys - active_keys)
    if extra:
        raise schema.SchemaError(
            f"English catalog has extra message(s) not in the active registry: {extra}"
        )

    en_strings: Dict[str, str] = {}
    for entry in active_entries:
        text = en_strings_raw[entry.key]
        if not isinstance(text, str) or not text:
            raise schema.SchemaError(f"English text for {entry.key!r} must be a non-empty string")
        _check_ascii_text(text, entry.key)
        _check_width_and_bytes(text, entry.key, entry, "en")
        en_strings[entry.key] = text

    pseudo_strings = pseudoize_and_validate(en_strings, {e.key: e for e in active_entries})

    return LoadedCatalog(
        entries=entries,
        active_entries=active_entries,
        tombstone_entries=tombstone_entries,
        en_strings=en_strings,
        pseudo_strings=pseudo_strings,
    )


def pseudoize_and_validate(
    en_strings: Dict[str, str], active_by_key: Dict[str, RegistryEntry]
) -> Dict[str, str]:
    """Derives the pseudo-locale catalog and validates it against the same
    ASCII/width/byte-budget/placeholder-parity contract as English -- the
    "one-step English fallback contract" only ever needs to reason about
    two known-good catalogs, never a partially-checked derived one."""
    pseudo_strings: Dict[str, str] = {}
    for key, en_text in en_strings.items():
        entry = active_by_key[key]
        pseudo_text = pseudoize(en_text)
        _check_ascii_text(pseudo_text, key)
        _check_width_and_bytes(pseudo_text, key, entry, schema.PSEUDO_LOCALE)

        en_tokens = _placeholder_tokens(en_text)
        pseudo_tokens = _placeholder_tokens(pseudo_text)
        if en_tokens != pseudo_tokens:
            raise schema.SchemaError(
                f"message {key!r} placeholder tokens differ between en {en_tokens!r} "
                f"and {schema.PSEUDO_LOCALE!r} {pseudo_tokens!r}"
            )
        en_newlines = en_text.count("\n")
        pseudo_newlines = pseudo_text.count("\n")
        if en_newlines != pseudo_newlines:
            raise schema.SchemaError(
                f"message {key!r} control-token (\\n) count differs between en "
                f"({en_newlines}) and {schema.PSEUDO_LOCALE!r} ({pseudo_newlines})"
            )
        pseudo_strings[key] = pseudo_text
    return pseudo_strings
