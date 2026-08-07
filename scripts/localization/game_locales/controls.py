"""Canonical control-token grammar for imported game locale text."""

from __future__ import annotations

import re
from typing import Iterator, Mapping, Sequence, Tuple, Union

CANONICAL_CONTROL_GRAMMAR = "[CTRL:HHHH]"
SOURCE_DIALECT_JAPANESE = "ja"
SOURCE_DIALECT_CHINESE = "zh-Hans"

_CANONICAL_RE = re.compile(r"\[CTRL:([0-9A-F]{4})\]")
_JAPANESE_RE = re.compile(r"\[\$([0-9A-F]{4})\]")
_CHINESE_RE = re.compile(r"\[0x([0-9A-F]{3,4})\]")

CanonicalTextUnit = Union[str, int]

FE8CN_NAMED_CONTROL_ALIASES = {
    "Buy/Sell": (0x001A,),
    "Clear": (0x0002,),
    "LoadOverworldFaces": (0x0080, 0x0004),
    "G": (0x0080, 0x0005),
    "MoveFarLeft": (0x0080, 0x000A),
    "MoveMidLeft": (0x0080, 0x000B),
    "MoveLeft": (0x0080, 0x000C),
    "MoveRight": (0x0080, 0x000D),
    "MoveMidRight": (0x0080, 0x000E),
    "MoveFarRight": (0x0080, 0x000F),
    "MoveFarFarLeft": (0x0080, 0x0010),
    "MoveFarFarRight": (0x0080, 0x0011),
    "OpenEyes": (0x0080, 0x001C),
    "CloseEyes": (0x0080, 0x001D),
    "HalfCloseEyes": (0x0080, 0x001E),
    "Tact": (0x0080, 0x0020),
    "ToggleRed": (0x0080, 0x0021),
    "Item": (0x0080, 0x0022),
    "SetName": (0x0080, 0x0023),
    "ToggleColorInvert": (0x0080, 0x0025),
}


class ControlSyntaxError(ValueError):
    """Raised when locale text does not use an accepted control grammar."""


def canonical_control_token(value: int) -> str:
    """Return the sole canonical spelling for one u16 control value."""

    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFF:
        raise ControlSyntaxError("control value must be a u16 integer")
    return f"[CTRL:{value:04X}]"


def expand_canonical_control(token: str) -> int:
    """Expand one canonical token to its exact u16 value."""

    if not isinstance(token, str) or not (match := _CANONICAL_RE.fullmatch(token)):
        raise ControlSyntaxError(
            f"control token must use canonical {CANONICAL_CONTROL_GRAMMAR} form"
        )
    return int(match.group(1), 16)


def expand_canonical_control_bytes(token: str) -> bytes:
    """Expand one canonical token to its exact little-endian GBA u16 bytes."""

    return expand_canonical_control(token).to_bytes(2, "little")


def _scan_bracket_tokens(text: str) -> Iterator[Tuple[int, int, str]]:
    cursor = 0
    while cursor < len(text):
        open_index = text.find("[", cursor)
        close_index = text.find("]", cursor)
        if close_index != -1 and (open_index == -1 or close_index < open_index):
            raise ControlSyntaxError(f"stray closing bracket at character {close_index}")
        if open_index == -1:
            return
        end_index = text.find("]", open_index + 1)
        if end_index == -1 or "\n" in text[open_index:end_index]:
            raise ControlSyntaxError(
                f"unterminated control-like token at character {open_index}"
            )
        yield open_index, end_index + 1, text[open_index : end_index + 1]
        cursor = end_index + 1


def _alias_tokens(
    token: str,
    aliases: Mapping[str, Sequence[int]],
) -> str:
    name = token[1:-1]
    if name not in aliases:
        raise ControlSyntaxError(f"unknown or malformed control-like token {token!r}")
    values = aliases[name]
    if not values:
        raise ControlSyntaxError(f"control alias {token!r} has no values")
    return "".join(canonical_control_token(value) for value in values)


def normalize_source_controls(
    text: str,
    *,
    dialect: str,
    aliases: Mapping[str, Sequence[int]],
) -> str:
    """Normalize authorized source controls into the canonical grammar.

    Japanese numeric controls must use ``[$HHHH]``. FE8CN numeric controls
    use the authorized legacy ``[0xHHH]`` or ``[0xHHHH]`` forms. Named aliases
    must be present in the pinned FE8J control-definition snapshot.
    """

    if dialect not in (SOURCE_DIALECT_JAPANESE, SOURCE_DIALECT_CHINESE):
        raise ControlSyntaxError(f"unsupported source control dialect {dialect!r}")

    output = []
    cursor = 0
    for start, end, token in _scan_bracket_tokens(text):
        output.append(text[cursor:start])
        numeric_match = (
            _JAPANESE_RE.fullmatch(token)
            if dialect == SOURCE_DIALECT_JAPANESE
            else _CHINESE_RE.fullmatch(token)
        )
        if numeric_match:
            output.append(canonical_control_token(int(numeric_match.group(1), 16)))
        else:
            output.append(_alias_tokens(token, aliases))
        cursor = end
    output.append(text[cursor:])
    return "".join(output)


def validate_canonical_text(text: str) -> None:
    """Reject every bracketed spelling except the canonical control grammar."""

    for _, _, token in _scan_bracket_tokens(text):
        expand_canonical_control(token)


def expand_canonical_text(text: str) -> Tuple[CanonicalTextUnit, ...]:
    """Split canonical text into literal strings and exact u16 control values."""

    validate_canonical_text(text)
    units = []
    cursor = 0
    for match in _CANONICAL_RE.finditer(text):
        if match.start() > cursor:
            units.append(text[cursor : match.start()])
        units.append(int(match.group(1), 16))
        cursor = match.end()
    if cursor < len(text):
        units.append(text[cursor:])
    return tuple(units)


def expand_canonical_controls(text: str) -> Tuple[int, ...]:
    """Expand a canonical control-only sequence to exact u16 values."""

    units = expand_canonical_text(text)
    if any(isinstance(unit, str) for unit in units):
        raise ControlSyntaxError("control sequence must not contain payload text")
    return tuple(unit for unit in units if isinstance(unit, int))


def expand_canonical_controls_bytes(text: str) -> bytes:
    """Expand a canonical control-only sequence to little-endian u16 bytes."""

    return b"".join(
        value.to_bytes(2, "little") for value in expand_canonical_controls(text)
    )
