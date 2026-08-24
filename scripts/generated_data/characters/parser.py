"""Round-trip checker: parse the hand-written ``gCharacterData[]`` (dense
1-based-designator, ``[SYMBOL - 1] = { ... }`` or ``[0xHEX - 1] = { ... }``,
``struct CharacterData[]``) array out of ``src/data_characters.c`` and
compare it, field for field, against the generated model built from the
JSON source.

Every field is resolved to the same symbol-blind canonical representation
:meth:`~.schema.CharacterRecord.as_tuple` produces (bitmask/enum fields
reduced to their live integer value; the ``baseRanks`` sparse map reduced
to a fixed-capacity tuple keyed by each weapon type's own index) -- this
is a *semantic* round trip: JSON authoring order of ``attributes``
flags/``baseRanks`` entries never causes a false mismatch. Only the
actual encoded bytes matter. ``supportData`` (a C symbol reference, not
a further-encoded scalar) is compared as a bare token string.

Unlike ``classes.parser`` (which matches hand entries purely by their own
``CLASS_*`` symbol), this table's records are keyed by *designator*
(1-based, symbolic or raw -- see ``schema.py``'s module docstring), since
that is the one collision-free identity space shared by both kinds of
record.
"""

from __future__ import annotations

import re

from ..cparse import (
    extract_designated_fields, find_matching_brace, line_of, strip_hand_conditionals, strip_outer_braces,
)
from ..diagnostics import GeneratedDataError, SourceLocation
from ..validators import extract_enum_constants
from .schema import (
    BMITEM_HEADER,
    BMUNIT_HEADER,
    CLASSES_HEADER,
    read_character_attributes,
    read_character_data_array_capacity,
    read_unit_affinities,
)

_DECL_RE = re.compile(r"CONST_DATA\s+struct\s+CharacterData\s+gCharacterData\s*\[\s*\]\s*=\s*", re.MULTILINE)
_DESIGNATOR_RE = re.compile(
    r"^\[\s*([A-Za-z_][A-Za-z0-9_]*|0[xX][0-9A-Fa-f]+)\s*-\s*1\s*\]\s*=\s*(.*)$", re.S
)
_ITYPE_DESIGNATOR_RE = re.compile(r"^\[\s*([A-Za-z_][A-Za-z0-9_]*)\s*\]\s*=\s*(.*)$", re.S)

_REQUIRED_FIELDS = (
    "number", "defaultClass",
    "baseHP", "basePow", "baseSkl", "baseSpd", "baseDef", "baseRes", "baseLck", "baseCon",
    "growthHP", "growthPow", "growthSkl", "growthSpd", "growthDef", "growthRes", "growthLck",
)


def _split_entries_with_offsets(body, body_start):
    """Like :func:`~..cparse.split_top_level_entries`, but keeps each
    entry's absolute character offset in the original text (needed for
    accurate ``line:column`` diagnostics per entry -- ``gCharacterData``
    is one large array, so a single offset for the whole block would be
    far too coarse). Mirrors ``classes.parser._split_entries_with_offsets``.
    """
    entries = []
    depth = 0
    current_start = 0
    length = len(body)
    i = 0
    while i < length:
        ch = body[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "," and depth == 0:
            entries.append((body[current_start:i], body_start + current_start))
            current_start = i + 1
        i += 1
    tail = body[current_start:]
    if tail.strip():
        entries.append((tail, body_start + current_start))
    return entries


def _parse_int_token(raw):
    raw = raw.strip()
    if raw.lower().startswith("0x") or raw.lower().startswith("-0x"):
        return int(raw, 16)
    return int(raw, 10)


def _parse_s8_token(raw):
    """Like :func:`_parse_int_token`, but normalizes a bare
    unsigned-looking literal (128..255) into its signed ``s8``
    equivalent -- the hand file sometimes spells a negative ``s8`` field
    as its unsigned decimal literal (e.g. ``.baseSkl = 255`` means
    ``-1``, since the compiler truncates any wider integer literal into
    the field's own ``s8`` type; the byte written to the ROM is
    identical either way, so this is a legitimate spelling, not an
    out-of-range value)."""
    value = _parse_int_token(raw)
    if value > 127:
        return value - 256
    return value


def _resolve_ca_flags(raw, attribute_flags):
    value = 0
    for name in (t.strip() for t in raw.split("|")):
        if name not in attribute_flags:
            raise GeneratedDataError("unknown CA_* flag '{}' in hand-written attributes".format(name))
        value |= attribute_flags[name]
    return value


def _resolve_pointer(raw):
    raw = raw.strip()
    if raw.startswith("&"):
        return raw[1:].strip()
    return raw


def _parse_base_ranks(raw, weapon_types, wexp_thresholds, capacity):
    slots = [0] * capacity
    body = strip_outer_braces(raw.strip())
    for entry in _split_entries_with_offsets(body, 0):
        entry_text = entry[0].strip()
        if not entry_text:
            continue
        match = _ITYPE_DESIGNATOR_RE.match(entry_text)
        if not match:
            raise GeneratedDataError("malformed baseRanks entry '{}'".format(entry_text))
        itype_name = match.group(1)
        wexp_name = match.group(2).strip()
        if itype_name not in weapon_types:
            raise GeneratedDataError("unknown ITYPE_* '{}' in hand-written baseRanks".format(itype_name))
        if wexp_name not in wexp_thresholds:
            raise GeneratedDataError("unknown WPN_EXP_* '{}' in hand-written baseRanks".format(wexp_name))
        index = weapon_types[itype_name][0]
        if 0 <= index < capacity:
            slots[index] = wexp_thresholds[wexp_name][0]
    return tuple(slots)


def parse_hand_written(path, characters_enum, wanted_designators):
    """Parse only the ``wanted_designators`` (a set of resolved 1-based
    designator ints -- see ``schema.py``'s module docstring) entries out
    of the ``gCharacterData[]`` array in ``path``.

    Returns ``{designator: {"tuple": (...), "line": N}}`` -- ``tuple`` is
    the same canonical, symbol-blind representation
    :meth:`~.schema.CharacterRecord.as_tuple` produces, so callers can
    compare the two directly with ``==``.
    """
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    text = strip_hand_conditionals(text)

    decl_match = _DECL_RE.search(text)
    if not decl_match:
        raise GeneratedDataError(
            "could not find 'CONST_DATA struct CharacterData gCharacterData[] = { ... };' in {}".format(path)
        )
    outer_brace_start = text.index("{", decl_match.end())
    outer_brace_end = find_matching_brace(text, outer_brace_start)
    body_start = outer_brace_start + 1
    body = text[body_start:outer_brace_end]

    classes_enum = extract_enum_constants(CLASSES_HEADER, name_prefix="CLASS_")
    attribute_flags = read_character_attributes(BMUNIT_HEADER)
    affinity_values = read_unit_affinities(BMUNIT_HEADER)
    weapon_types = extract_enum_constants(BMITEM_HEADER, name_prefix="ITYPE_")
    wexp_thresholds = extract_enum_constants(BMITEM_HEADER, name_prefix="WPN_EXP_")
    base_ranks_capacity = read_character_data_array_capacity("baseRanks", BMUNIT_HEADER)

    wanted = set(wanted_designators)
    records = {}
    for raw_entry, entry_offset in _split_entries_with_offsets(body, body_start):
        stripped = raw_entry.strip()
        if not stripped:
            continue
        leading_ws = len(raw_entry) - len(raw_entry.lstrip())
        entry_abs_start = entry_offset + leading_ws
        line = line_of(text, entry_abs_start)

        designator_match = _DESIGNATOR_RE.match(stripped)
        if not designator_match:
            raise GeneratedDataError(
                "gCharacterData entry is not a '[SYMBOL - 1] = { ... }'/'[0xHEX - 1] = { ... }' "
                "designated initializer",
                SourceLocation(path, line, 1),
            )
        token = designator_match.group(1)
        if token in characters_enum:
            designator = characters_enum[token][0]
        else:
            designator = _parse_int_token(token)

        if designator not in wanted:
            continue

        struct_body = strip_outer_braces(designator_match.group(2).strip())
        fields = extract_designated_fields(struct_body)

        for required_field in _REQUIRED_FIELDS:
            if required_field not in fields:
                raise GeneratedDataError(
                    "gCharacterData[{}] has no .{} (a required field)".format(token, required_field),
                    SourceLocation(path, line, 1),
                )

        expected_number = designator & 0xFF
        number_raw = fields["number"].strip()
        if token in characters_enum:
            if number_raw != token:
                raise GeneratedDataError(
                    "gCharacterData['{}'].number is '{}', expected the designator's own symbol".format(
                        token, number_raw
                    ),
                    SourceLocation(path, line, 1),
                )
        else:
            number_value = _parse_int_token(number_raw)
            if number_value != expected_number:
                raise GeneratedDataError(
                    "gCharacterData[{}].number is {}, expected {} (the designator truncated to u8)".format(
                        token, number_value, expected_number
                    ),
                    SourceLocation(path, line, 1),
                )

        portrait = _parse_int_token(fields["portraitId"]) if "portraitId" in fields else 0
        mini_portrait = _parse_int_token(fields["miniPortrait"]) if "miniPortrait" in fields else 0
        affinity_value = affinity_values.get(fields["affinity"].strip(), 0) if "affinity" in fields else 0
        sort_order = _parse_int_token(fields["sort_order"]) if "sort_order" in fields else 0
        base_level = _parse_s8_token(fields["baseLevel"]) if "baseLevel" in fields else 0
        attributes_value = _resolve_ca_flags(fields["attributes"], attribute_flags) if "attributes" in fields else 0
        base_ranks_tuple = (
            _parse_base_ranks(fields["baseRanks"], weapon_types, wexp_thresholds, base_ranks_capacity)
            if "baseRanks" in fields else tuple([0] * base_ranks_capacity)
        )
        support_data = _resolve_pointer(fields["pSupportData"]) if "pSupportData" in fields else None
        visit_group = _parse_int_token(fields["visit_group"]) if "visit_group" in fields else 0

        record_tuple = (
            _parse_int_token(fields["nameTextId"]) if "nameTextId" in fields else 0,
            _parse_int_token(fields["descTextId"]) if "descTextId" in fields else 0,
            classes_enum[fields["defaultClass"].strip()][0],
            portrait, mini_portrait, affinity_value, sort_order,
            base_level,
            tuple(_parse_s8_token(fields[f]) for f in
                  ("baseHP", "basePow", "baseSkl", "baseSpd", "baseDef", "baseRes", "baseLck", "baseCon")),
            base_ranks_tuple,
            tuple(_parse_int_token(fields[f]) for f in
                  ("growthHP", "growthPow", "growthSkl", "growthSpd", "growthDef", "growthRes", "growthLck")),
            attributes_value,
            support_data,
            visit_group,
        )
        records[designator] = {"tuple": record_tuple, "line": line, "token": token}

    missing = wanted - set(records)
    if missing:
        raise GeneratedDataError(
            "expected character designator(s) {} not found in gCharacterData[] in {}".format(
                sorted(missing), path
            ),
            SourceLocation(path, 1, 1),
        )
    return records


def compare_records(generated_records, hand_records, hand_path):
    """Compare generated :class:`~.schema.CharacterRecord` objects against
    parsed hand records (keyed by resolved designator). Returns a list of
    :class:`GeneratedDataError`."""
    from .. import character_refs

    characters_enum = character_refs.read_character_designators()
    classes_enum = extract_enum_constants(CLASSES_HEADER, name_prefix="CLASS_")
    attribute_flags = read_character_attributes(BMUNIT_HEADER)
    affinity_values = read_unit_affinities(BMUNIT_HEADER)
    weapon_types = extract_enum_constants(BMITEM_HEADER, name_prefix="ITYPE_")
    wexp_thresholds = extract_enum_constants(BMITEM_HEADER, name_prefix="WPN_EXP_")
    base_ranks_capacity = read_character_data_array_capacity("baseRanks", BMUNIT_HEADER)

    errors = []
    gen_by_designator = {}
    for record in generated_records:
        designator = record.designator(characters_enum)
        if designator is not None:
            gen_by_designator[designator] = record

    for designator in sorted(set(gen_by_designator) - set(hand_records)):
        record = gen_by_designator[designator]
        errors.append(
            GeneratedDataError(
                "generated character '{}' has no counterpart in {}".format(record.key_repr(), hand_path),
                record.loc,
            )
        )
    for designator in sorted(set(hand_records) - set(gen_by_designator)):
        hand = hand_records[designator]
        errors.append(
            GeneratedDataError(
                "hand-written character '{}' has no counterpart in generated source".format(hand["token"]),
                SourceLocation(hand_path, hand["line"], 1),
            )
        )
    for designator in sorted(set(gen_by_designator) & set(hand_records)):
        gen = gen_by_designator[designator]
        hand = hand_records[designator]
        loc = SourceLocation(hand_path, hand["line"], 1)
        gen_tuple = gen.as_tuple(
            classes_enum, attribute_flags, weapon_types, wexp_thresholds, base_ranks_capacity, affinity_values
        )
        hand_tuple = hand["tuple"]
        if gen_tuple != hand_tuple:
            errors.append(
                GeneratedDataError(
                    "fields mismatch for {}: generated={!r} hand-written={!r}".format(
                        gen.key_repr(), gen_tuple, hand_tuple
                    ),
                    loc, gen.key_repr(),
                )
            )

    return errors
