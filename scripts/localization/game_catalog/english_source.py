"""Parser and encoder for the committed FE8U English message sources."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .model import EnglishSourceEntry, GameCatalogError


_DEFINITION_RE = re.compile(r"^\[([^\]]+)\]\s*=\s*(.+?)\s*$")
_EXPLICIT_ID_RE = re.compile(r"^#([0-9A-Fa-fx]+)\s*$")
_MACRO_RE = re.compile(r"^##\s*(\w+)\s*$")
_INCLUDE_RE = re.compile(r'^#include\s+"([^"]+)"\s*$')
_TOKEN_RE = re.compile(r"\[([^\[\]\r\n]+)\]")

_PRINTABLE_REPLACEMENTS = {
    "DashedLine": b"-",
    "TAB": "\u3000".encode("utf-8"),
    "LQuote": b'"',
    "RQuote": b'"',
    "AccentedE": b"e",
}


def _strict_utf8_text(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise GameCatalogError(f"{path}: file is not strict UTF-8") from error


def _strip_comments(text: str, *, source_name: str) -> str:
    output: List[str] = []
    index = 0
    while index < len(text):
        if text.startswith("//", index):
            newline = text.find("\n", index + 2)
            if newline < 0:
                break
            output.append("\n")
            index = newline + 1
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise GameCatalogError(f"{source_name}: unterminated block comment")
            output.extend("\n" for char in text[index:end + 2] if char == "\n")
            index = end + 2
            continue
        output.append(text[index])
        index += 1
    return "".join(output)


def load_english_definitions(path: Path) -> Dict[str, Tuple[int, ...]]:
    text = _strip_comments(_strict_utf8_text(path), source_name=str(path))
    definitions: Dict[str, Tuple[int, ...]] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        match = _DEFINITION_RE.match(line.strip())
        if match is None:
            continue
        name = match.group(1)
        if name in definitions:
            raise GameCatalogError(
                f"{path}:{line_number}: duplicate text definition {name!r}"
            )
        try:
            values = tuple(
                int(value.strip(), 0) for value in match.group(2).split(",")
            )
        except ValueError as error:
            raise GameCatalogError(
                f"{path}:{line_number}: invalid byte list for {name!r}"
            ) from error
        if not values or any(value < 0 or value > 0xFF for value in values):
            raise GameCatalogError(
                f"{path}:{line_number}: {name!r} must define one or more bytes"
            )
        definitions[name] = values

    if definitions.get("X") != (0,):
        raise GameCatalogError(f"{path}: [X] must be the standalone NUL byte")
    return definitions


def _encode_named_token(
    name: str,
    definitions: Mapping[str, Tuple[int, ...]],
    *,
    source_name: str,
) -> bytes:
    replacement = _PRINTABLE_REPLACEMENTS.get(name)
    if replacement is not None:
        return replacement
    if name not in definitions:
        raise GameCatalogError(f"{source_name}: unknown text token [{name}]")

    values = definitions[name]
    if any(value >= 0x7F for value in values):
        is_control = values[0] == 0x80
        is_face_payload = name.startswith("FID_")
        if not is_control and not is_face_payload:
            raise GameCatalogError(
                f"{source_name}: non-UTF-8 printable token [{name}] has no "
                "modern replacement"
            )
    return bytes(values)


def encode_english_source_text(
    text: str,
    definitions: Mapping[str, Tuple[int, ...]],
    *,
    source_name: str,
) -> bytes:
    text = _strip_comments(text, source_name=source_name)
    text = text.replace("\r", "").replace("\n", "")
    payload = bytearray()
    position = 0
    for match in _TOKEN_RE.finditer(text):
        literal = text[position:match.start()]
        if "[" in literal or "]" in literal:
            raise GameCatalogError(f"{source_name}: malformed text token")
        payload.extend(literal.encode("utf-8"))
        payload.extend(
            _encode_named_token(
                match.group(1), definitions, source_name=source_name
            )
        )
        position = match.end()

    literal = text[position:]
    if "[" in literal or "]" in literal:
        raise GameCatalogError(f"{source_name}: malformed text token")
    payload.extend(literal.encode("utf-8"))

    data = bytes(payload)
    if not data.endswith(b"\x00"):
        raise GameCatalogError(f"{source_name}: message must end with [X]")
    if b"\x00" in data[:-1]:
        raise GameCatalogError(f"{source_name}: message contains an interior NUL")
    return data


def _parse_source_file(
    path: Path,
    definitions: Mapping[str, Tuple[int, ...]],
    entries: List[EnglishSourceEntry],
    current_id: int,
    include_stack: Sequence[Path],
) -> int:
    path = path.resolve()
    if path in include_stack:
        chain = " -> ".join(str(item) for item in (*include_stack, path))
        raise GameCatalogError(f"English text include cycle: {chain}")

    lines = _strict_utf8_text(path).splitlines()
    stack = (*include_stack, path)
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        include_match = _INCLUDE_RE.match(stripped)
        explicit_match = _EXPLICIT_ID_RE.match(stripped)
        macro_match = _MACRO_RE.match(stripped)

        if include_match is not None:
            include_path = path.parent / include_match.group(1)
            if not include_path.is_file():
                raise GameCatalogError(
                    f"{path}:{index + 1}: included file does not exist: "
                    f"{include_match.group(1)!r}"
                )
            current_id = _parse_source_file(
                include_path, definitions, entries, current_id, stack
            )
            index += 1
            continue

        definition: Optional[str]
        if explicit_match is not None:
            current_id = int(explicit_match.group(1), 16)
            definition = None
        elif macro_match is not None:
            definition = macro_match.group(1)
        else:
            if stripped.startswith("#"):
                raise GameCatalogError(
                    f"{path}:{index + 1}: unknown text directive {stripped!r}"
                )
            index += 1
            continue

        directive_line = index + 1
        index += 1
        body: List[str] = []
        while index < len(lines) and not lines[index].startswith("#"):
            body.append(lines[index])
            index += 1

        source_name = f"{path}:{directive_line}: message 0x{current_id:04X}"
        source_text = "\n".join(body)
        encoded = encode_english_source_text(
            source_text, definitions, source_name=source_name
        )
        entries.append(
            EnglishSourceEntry(
                target_id=current_id,
                definition=definition,
                source_text=source_text,
                encoded_bytes=encoded,
            )
        )
        current_id += 1

    return current_id


def load_english_source_entries(
    texts_path: Path,
    definitions_path: Path,
    *,
    target_count: int,
) -> Tuple[EnglishSourceEntry, ...]:
    definitions = load_english_definitions(definitions_path)
    parsed: List[EnglishSourceEntry] = []
    _parse_source_file(texts_path, definitions, parsed, 0, ())

    by_id: Dict[int, EnglishSourceEntry] = {}
    definitions_seen = set()
    for entry in parsed:
        if entry.target_id in by_id:
            raise GameCatalogError(
                f"{texts_path}: duplicate English message ID 0x{entry.target_id:04X}"
            )
        if entry.definition is not None:
            if entry.definition in definitions_seen:
                raise GameCatalogError(
                    f"{texts_path}: duplicate English macro {entry.definition!r}"
                )
            definitions_seen.add(entry.definition)
        by_id[entry.target_id] = entry

    expected = set(range(target_count))
    actual = set(by_id)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        detail = []
        if missing:
            detail.append(
                "missing " + ", ".join(f"0x{value:04X}" for value in missing[:8])
            )
        if extra:
            detail.append(
                "extra " + ", ".join(f"0x{value:04X}" for value in extra[:8])
            )
        raise GameCatalogError(
            f"{texts_path}: English source IDs do not match target range: "
            + "; ".join(detail)
        )

    return tuple(by_id[target_id] for target_id in range(target_count))
