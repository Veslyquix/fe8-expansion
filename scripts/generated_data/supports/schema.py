"""``SupportData`` schema: fields, loading, and validation.

Mirrors the hand-written C layout in ``include/bmreliance.h``
(``struct SupportData``) field-for-field so the round-trip checker
(``parser.py``) can compare generated output against
``src/data_supports.c`` with no semantic reinterpretation:

    characters[UNIT_SUPPORT_MAX_COUNT]        -- CHARACTER_* symbols
    supportExpBase[UNIT_SUPPORT_MAX_COUNT]    -- u8
    supportExpGrowth[UNIT_SUPPORT_MAX_COUNT]  -- u8
    supportCount                              -- u8, <= UNIT_SUPPORT_MAX_COUNT

JSON source shape (see ``src/data/supports.json``)::

    {
      "$schema": "fe8.supports.v1",
      "records": [
        {
          "owner": "CHARACTER_EIRIKA",
          "symbol": "SupportData_Eirika",
          "characters": ["CHARACTER_EPHRAIM", ...],
          "supportExpBase": [30, ...],
          "supportExpGrowth": [4, ...],
          "supportCount": 7
        },
        ...
      ]
    }
"""

from __future__ import annotations

import os
import re

from ..diagnostics import GeneratedDataError
from ..json_loader import load_json_file
from ..schema import DependencyGraph, TableSchema
from .. import character_refs
from ..validators import (
    extract_enum_constants,
    validate_fixed_capacity,
    validate_parallel_arrays,
    validate_range,
    validate_reference,
    validate_unique,
)

SCHEMA_NAME = "supports"
SCHEMA_VERSION = 1
SCHEMA_ID = "fe8.supports.v1"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CHARACTERS_HEADER = character_refs.CHARACTERS_HEADER
TYPES_HEADER = os.path.join(REPO_ROOT, "include", "types.h")

_U8_MIN, _U8_MAX = 0, 255

_UNIT_SUPPORT_MAX_COUNT_RE = re.compile(r"UNIT_SUPPORT_MAX_COUNT\s*=\s*(\d+)")


def read_unit_support_max_count(types_header=TYPES_HEADER):
    """Read the ``UNIT_SUPPORT_MAX_COUNT`` fixed-capacity constant from types.h.

    Reading it from the header (instead of hardcoding ``7`` here) keeps the
    validator's fixed-capacity check honest if the struct's array size ever
    changes.
    """
    with open(types_header, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = _UNIT_SUPPORT_MAX_COUNT_RE.search(text)
    if not match:
        raise GeneratedDataError(
            "could not find UNIT_SUPPORT_MAX_COUNT in {}".format(types_header)
        )
    return int(match.group(1))


class SupportRecord:
    """One owner's ``SupportData`` record, with per-field source locations."""

    def __init__(self, owner, owner_loc, symbol, symbol_loc, characters, char_locs,
                 support_exp_base, base_locs, support_exp_growth, growth_locs,
                 support_count, count_loc, record_loc):
        self.owner = owner
        self.owner_loc = owner_loc
        self.symbol = symbol
        self.symbol_loc = symbol_loc
        self.characters = characters
        self.char_locs = char_locs
        self.support_exp_base = support_exp_base
        self.base_locs = base_locs
        self.support_exp_growth = support_exp_growth
        self.growth_locs = growth_locs
        self.support_count = support_count
        self.count_loc = count_loc
        self.record_loc = record_loc

    def partners(self):
        """Yield ``(character, expBase, expGrowth, index)`` tuples."""
        return zip(self.characters, self.support_exp_base, self.support_exp_growth, range(len(self.characters)))


def load_records(source_path):
    """Parse the JSON source into a list of :class:`SupportRecord`.

    Raises :class:`GeneratedDataError` immediately for structural problems
    (wrong top-level shape, missing required fields, wrong types) since
    those make the record impossible to validate further. Content-level
    problems (duplicates, bad references, out-of-range values) are left to
    :func:`validate` so every one of them is reported in a single pass.
    """
    root = load_json_file(source_path)
    schema_node = root.require("$schema")
    if schema_node.as_str() != SCHEMA_ID:
        raise GeneratedDataError(
            "unexpected $schema '{}', expected '{}'".format(schema_node.as_str(), SCHEMA_ID),
            schema_node.loc,
        )
    records_node = root.require("records")
    records = []
    for record_node in records_node.as_list():
        owner_node = record_node.require("owner")
        symbol_node = record_node.require("symbol")
        characters_node = record_node.require("characters")
        base_node = record_node.require("supportExpBase")
        growth_node = record_node.require("supportExpGrowth")
        count_node = record_node.require("supportCount")

        char_nodes = characters_node.as_list()
        base_nodes = base_node.as_list()
        growth_nodes = growth_node.as_list()

        records.append(
            SupportRecord(
                owner=owner_node.as_str(),
                owner_loc=owner_node.loc,
                symbol=symbol_node.as_str(),
                symbol_loc=symbol_node.loc,
                characters=[n.as_str() for n in char_nodes],
                char_locs=[n.loc for n in char_nodes],
                support_exp_base=[n.as_int() for n in base_nodes],
                base_locs=[n.loc for n in base_nodes],
                support_exp_growth=[n.as_int() for n in growth_nodes],
                growth_locs=[n.loc for n in growth_nodes],
                support_count=count_node.as_int(),
                count_loc=count_node.loc,
                record_loc=record_node.loc,
            )
        )
    return records


def validate(records, diagnostics, characters_header=CHARACTERS_HEADER, capacity=None):
    """Run all SupportData validations, appending errors to ``diagnostics``.

    Checks: unique owner IDs, unique symbols, unique partners per owner,
    defined character references (owner + partners), parallel-array/count
    consistency, fixed capacity (<= UNIT_SUPPORT_MAX_COUNT), u8 value
    ranges, and reciprocal support pairs (every partner listed back with
    matching exp base/growth -- required by every vanilla record).
    """
    if capacity is None:
        capacity = read_unit_support_max_count()

    characters = character_refs.read_character_designators(characters_header)

    diagnostics.extend(
        validate_unique(
            ((r.owner, r.owner_loc) for r in records),
            "duplicate owner '{key}' (first defined at {first_loc})",
            "records[owner={key}]",
        )
    )
    diagnostics.extend(
        validate_unique(
            ((r.symbol, r.symbol_loc) for r in records),
            "duplicate symbol '{key}' (first defined at {first_loc})",
            "records[symbol={key}]",
        )
    )

    records_by_owner = {}
    for record in records:
        records_by_owner.setdefault(record.owner, record)

    for record in records:
        ref_prefix = "records[owner={}]".format(record.owner)

        diagnostics.extend(
            validate_reference(
                record.owner, characters, record.owner_loc,
                "{}.owner".format(ref_prefix), kind="character",
            )
        )

        diagnostics.extend(
            validate_parallel_arrays(
                [len(record.characters), len(record.support_exp_base), len(record.support_exp_growth)],
                record.record_loc,
                ref_prefix,
                ["characters", "supportExpBase", "supportExpGrowth"],
            )
        )
        if len(record.characters) != record.support_count:
            diagnostics.add(
                GeneratedDataError(
                    "supportCount {} does not match {} partner entries".format(
                        record.support_count, len(record.characters)
                    ),
                    record.count_loc,
                    "{}.supportCount".format(ref_prefix),
                )
            )

        diagnostics.extend(
            validate_fixed_capacity(
                record.support_count, capacity, record.count_loc,
                "{}.supportCount".format(ref_prefix), what="support partners",
            )
        )

        diagnostics.extend(
            validate_unique(
                (
                    (partner, record.char_locs[i])
                    for partner, i in zip(record.characters, range(len(record.characters)))
                ),
                "duplicate partner '{key}' in " + ref_prefix + " (first at {first_loc})",
                ref_prefix + ".characters[{key}]",
            )
        )

        for partner, base, growth, index in record.partners():
            ref_path = "{}.characters[{}]={}".format(ref_prefix, index, partner)
            diagnostics.extend(
                validate_reference(partner, characters, record.char_locs[index], ref_path, kind="character")
            )
            diagnostics.extend(
                validate_range(base, _U8_MIN, _U8_MAX, record.base_locs[index],
                                ref_path + ".supportExpBase", field_name="supportExpBase")
            )
            diagnostics.extend(
                validate_range(growth, _U8_MIN, _U8_MAX, record.growth_locs[index],
                                ref_path + ".supportExpGrowth", field_name="supportExpGrowth")
            )

            if partner == record.owner:
                diagnostics.add(
                    GeneratedDataError(
                        "record lists its own owner '{}' as a support partner".format(partner),
                        record.char_locs[index], ref_path,
                    )
                )
                continue

            partner_record = records_by_owner.get(partner)
            if partner_record is None:
                # Already reported by validate_reference / missing owner above
                # only if partner isn't even a valid character; if it *is* a
                # valid character but has no SupportData record at all, that's
                # a reciprocity failure specific to this table.
                if partner in characters:
                    diagnostics.add(
                        GeneratedDataError(
                            "partner '{}' has no SupportData record (reciprocal support required)".format(partner),
                            record.char_locs[index], ref_path,
                        )
                    )
                continue

            if record.owner not in partner_record.characters:
                diagnostics.add(
                    GeneratedDataError(
                        "'{}' lists '{}' as a partner, but '{}' does not list '{}' back".format(
                            record.owner, partner, partner, record.owner
                        ),
                        record.char_locs[index], ref_path,
                    )
                )
                continue

            back_index = partner_record.characters.index(record.owner)
            # The partner's own parallel-array length mismatch (if any) is
            # already reported above via validate_parallel_arrays; guard the
            # reciprocal value cross-check so a short partner base/growth
            # array degrades to that clean diagnostic instead of crashing.
            if (back_index >= len(partner_record.support_exp_base)
                    or back_index >= len(partner_record.support_exp_growth)):
                continue
            back_base = partner_record.support_exp_base[back_index]
            back_growth = partner_record.support_exp_growth[back_index]
            if back_base != base or back_growth != growth:
                diagnostics.add(
                    GeneratedDataError(
                        "reciprocal mismatch: {} lists {} with (base={}, growth={}), "
                        "but {} lists {} back with (base={}, growth={})".format(
                            record.owner, partner, base, growth,
                            partner, record.owner, back_base, back_growth,
                        ),
                        record.char_locs[index], ref_path,
                    )
                )


class SupportsTableSchema(TableSchema):
    name = SCHEMA_NAME
    version = SCHEMA_VERSION

    default_source = "src/data/supports.json"
    default_hand_source = "src/data_supports.c"
    default_output_name = "data_supports.c"
    default_inventory_path = "reports/generated_data_supports_inventory.md"

    def dependencies(self):
        return ("constants.characters", "types.UNIT_SUPPORT_MAX_COUNT")

    def load_records(self, source_path):
        return load_records(source_path)

    def validate(self, records, diagnostics):
        validate(records, diagnostics)

    def generate_c(self, records, source_path):
        from . import generate as supports_generate
        return supports_generate.generate_c_source(records, source_path)

    def build_inventory(self, records):
        from . import inventory as supports_inventory
        return supports_inventory.build_inventory(records)

    def round_trip_errors(self, records, hand_source):
        if not hand_source or not os.path.exists(hand_source):
            return []
        from . import parser as supports_roundtrip
        hand_records = supports_roundtrip.parse_hand_written(hand_source)
        return supports_roundtrip.compare_records(records, hand_records, hand_path=hand_source)


def dependency_graph():
    graph = DependencyGraph()
    graph.add_dependency(SCHEMA_NAME, "constants.characters")
    graph.add_dependency(SCHEMA_NAME, "types.UNIT_SUPPORT_MAX_COUNT")
    return graph
