"""Registry/catalog loading and validation for expansion-framework text.

Loads the stable numeric-ID registry plus a mapping of authored UTF-8
catalogs, validates each catalog independently, derives qps-ploc from
English, and exposes one locale-indexed ``LoadedCatalog`` consumed by the
generator and CLI.

Every check here is a build-time validation gate, not a runtime one --
see src/expansion_locale.c for the separate, much smaller set of runtime
defensive checks (bounded scratch, missing-marker fallback) that must
hold even if this validation is somehow bypassed.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from . import schema
from .pseudo import pseudoize

_PLACEHOLDER_RE = re.compile(r"\{[0-9]+\}")

DEFAULT_REGISTRY_PATH = Path("texts/expansion/registry.json")
DEFAULT_CATALOG_PATHS = {
    locale: Path(f"texts/expansion/catalog.{locale}.json")
    for locale in schema.AUTHORED_CATALOG_LOCALES
}


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
    locale_strings: Dict[str, Dict[str, Optional[str]]]
    authored_locales: Tuple[str, ...]
    generated_locales: Tuple[str, ...]

    def active_by_key(self) -> Dict[str, RegistryEntry]:
        return {entry.key: entry for entry in self.active_entries}

    @property
    def en_strings(self) -> Dict[str, str]:
        return {
            key: text
            for key, text in self.locale_strings["en"].items()
            if text is not None
        }

    @property
    def pseudo_strings(self) -> Dict[str, str]:
        return {
            key: text
            for key, text in self.locale_strings[schema.PSEUDO_LOCALE].items()
            if text is not None
        }

    def strings_for(self, locale: str) -> Dict[str, Optional[str]]:
        return self.locale_strings[locale]

    def missing_keys(self, locale: str) -> Tuple[str, ...]:
        strings = self.locale_strings[locale]
        return tuple(entry.key for entry in self.active_entries if strings[entry.key] is None)


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


def _check_utf8_text(text: str, key: str, locale: str) -> None:
    try:
        text.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise schema.SchemaError(
            f"message {key!r} locale {locale!r} is not valid Unicode scalar text: {error}"
        ) from error

    for index, ch in enumerate(text):
        code = ord(ch)
        if ch in schema.ALLOWED_CONTROL_TOKENS:
            continue
        if ch.isspace() and ch != " ":
            raise schema.SchemaError(
                f"message {key!r} locale {locale!r} contains unsupported whitespace "
                f"U+{code:04X} at scalar {index}; only ASCII space and "
                f"{schema.ALLOWED_CONTROL_TOKENS!r} are allowed"
            )
        category = unicodedata.category(ch)
        if category.startswith("C"):
            raise schema.SchemaError(
                f"message {key!r} locale {locale!r} contains unsupported control/"
                f"format/private/unassigned scalar U+{code:04X} at scalar {index}"
            )


def _surface_width(text: str) -> int:
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def _check_width_and_bytes(text: str, key: str, entry: RegistryEntry, locale: str) -> None:
    for line in text.split("\n"):
        width = _surface_width(line)
        if width > entry.max_width:
            raise schema.SchemaError(
                f"message {key!r} locale {locale!r} line {line!r} has surface width "
                f"{width}; exceeds max_width {entry.max_width}"
            )
    encoded_len = len(text.encode("utf-8")) + 1
    if encoded_len > entry.max_decoded_bytes:
        raise schema.SchemaError(
            f"message {key!r} locale {locale!r} decodes to {encoded_len} bytes "
            f"(including NUL); exceeds max_decoded_bytes {entry.max_decoded_bytes}"
        )


def _placeholder_tokens(text: str) -> List[str]:
    return _PLACEHOLDER_RE.findall(text)


def _check_placeholder_syntax(text: str, key: str, locale: str) -> None:
    remainder = _PLACEHOLDER_RE.sub("", text)
    if "{" in remainder or "}" in remainder:
        raise schema.SchemaError(
            f"message {key!r} locale {locale!r} contains malformed placeholder braces; "
            "only {0}, {1}, ... tokens are allowed"
        )


def _check_parity(text: str, en_text: str, key: str, locale: str) -> None:
    en_tokens = _placeholder_tokens(en_text)
    locale_tokens = _placeholder_tokens(text)
    if en_tokens != locale_tokens:
        raise schema.SchemaError(
            f"message {key!r} placeholder tokens differ between en {en_tokens!r} "
            f"and {locale!r} {locale_tokens!r}"
        )
    en_newlines = en_text.count("\n")
    locale_newlines = text.count("\n")
    if en_newlines != locale_newlines:
        raise schema.SchemaError(
            f"message {key!r} control-token (\\n) count differs between en "
            f"({en_newlines}) and {locale!r} ({locale_newlines})"
        )


def _read_json(path: Path, label: str) -> dict:
    try:
        source = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise schema.SchemaError(f"{label} is not strict UTF-8: {path}: {error}") from error
    try:
        data = json.loads(source)
    except json.JSONDecodeError as error:
        raise schema.SchemaError(f"{label} is not valid JSON: {path}: {error}") from error
    if not isinstance(data, dict):
        raise schema.SchemaError(f"{label} must be a JSON object: {path}")
    return data


def _ordered_catalog_paths(
    catalog_paths: Optional[Mapping[str, Path]],
) -> Tuple[Tuple[str, Path], ...]:
    raw_paths = DEFAULT_CATALOG_PATHS if catalog_paths is None else catalog_paths
    paths = {locale: Path(path) for locale, path in raw_paths.items()}
    if "en" not in paths:
        raise schema.SchemaError("catalog mapping must include the English fallback locale 'en'")
    for locale in paths:
        if locale not in schema.LOCALE_INDEX:
            raise schema.SchemaError(f"catalog mapping contains unknown stable locale {locale!r}")
        if locale == schema.PSEUDO_LOCALE:
            raise schema.SchemaError(
                f"{schema.PSEUDO_LOCALE!r} is derived from English and cannot be authored"
            )
    return tuple((locale, paths[locale]) for locale in schema.LOCALE_IDS if locale in paths)


def load_catalog(
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    catalog_paths: Optional[Mapping[str, Path]] = None,
) -> LoadedCatalog:
    registry_path = Path(registry_path)
    ordered_catalog_paths = _ordered_catalog_paths(catalog_paths)

    if not registry_path.is_file():
        raise schema.SchemaError(f"registry not found: {registry_path}")
    for locale, path in ordered_catalog_paths:
        if not path.is_file():
            raise schema.SchemaError(f"catalog for locale {locale!r} not found: {path}")

    registry_data = _read_json(registry_path, "registry")
    entries = parse_registry(registry_data)
    active_entries = tuple(e for e in entries if e.is_active)
    tombstone_entries = tuple(e for e in entries if not e.is_active)
    active_keys = {e.key for e in active_entries}

    locale_strings: Dict[str, Dict[str, Optional[str]]] = {}
    authored_locales = tuple(locale for locale, _path in ordered_catalog_paths)
    for locale, path in ordered_catalog_paths:
        catalog_data = _read_json(path, f"catalog for locale {locale!r}")
        if "strings" not in catalog_data:
            raise schema.SchemaError(f"{path} must contain a 'strings' map")
        if catalog_data.get("locale") != locale:
            raise schema.SchemaError(f"{path} 'locale' field must be {locale!r}")
        strings_raw = catalog_data["strings"]
        if not isinstance(strings_raw, dict):
            raise schema.SchemaError(f"{path} 'strings' must be an object")

        catalog_keys = set(strings_raw.keys())
        if locale == "en":
            missing = sorted(active_keys - catalog_keys)
            if missing:
                raise schema.SchemaError(
                    f"English catalog is missing required active message(s): {missing}"
                )
        extra = sorted(catalog_keys - active_keys)
        if extra:
            raise schema.SchemaError(
                f"catalog {locale!r} has extra message(s) not in the active registry: {extra}"
            )

        strings: Dict[str, Optional[str]] = {}
        for entry in active_entries:
            if entry.key not in strings_raw:
                strings[entry.key] = None
                continue
            text = strings_raw[entry.key]
            if not isinstance(text, str) or not text:
                raise schema.SchemaError(
                    f"text for {entry.key!r} locale {locale!r} must be a non-empty string"
                )
            _check_utf8_text(text, entry.key, locale)
            _check_placeholder_syntax(text, entry.key, locale)
            _check_width_and_bytes(text, entry.key, entry, locale)
            if locale != "en":
                en_text = locale_strings["en"][entry.key]
                if en_text is None:
                    raise schema.SchemaError(
                        f"English fallback text for {entry.key!r} is unexpectedly missing"
                    )
                _check_parity(text, en_text, entry.key, locale)
            strings[entry.key] = text
        locale_strings[locale] = strings

    en_strings = {
        key: text for key, text in locale_strings["en"].items() if text is not None
    }
    pseudo_strings = pseudoize_and_validate(en_strings, {e.key: e for e in active_entries})
    locale_strings[schema.PSEUDO_LOCALE] = dict(pseudo_strings)
    generated_locales = tuple(
        locale
        for locale in schema.LOCALE_IDS
        if locale in locale_strings
    )

    return LoadedCatalog(
        entries=entries,
        active_entries=active_entries,
        tombstone_entries=tombstone_entries,
        locale_strings=locale_strings,
        authored_locales=authored_locales,
        generated_locales=generated_locales,
    )


def pseudoize_and_validate(
    en_strings: Dict[str, str], active_by_key: Dict[str, RegistryEntry]
) -> Dict[str, str]:
    """Derives the pseudo-locale catalog and validates it against the same
    UTF-8/width/byte-budget/placeholder-parity contract as English -- the
    "one-step English fallback contract" only ever needs to reason about
    checked populated descriptors, never an unchecked derived one."""
    pseudo_strings: Dict[str, str] = {}
    for key, en_text in en_strings.items():
        entry = active_by_key[key]
        pseudo_text = pseudoize(en_text)
        _check_utf8_text(pseudo_text, key, schema.PSEUDO_LOCALE)
        _check_placeholder_syntax(pseudo_text, key, schema.PSEUDO_LOCALE)
        _check_width_and_bytes(pseudo_text, key, entry, schema.PSEUDO_LOCALE)
        _check_parity(pseudo_text, en_text, key, schema.PSEUDO_LOCALE)
        pseudo_strings[key] = pseudo_text
    return pseudo_strings
