"""``ClassData`` schema: the full 127-record vanilla ``gClassData[]`` table.

Mirrors the hand-written C layout in ``include/bmunit.h`` (``struct
ClassData``) field-for-field so the round-trip checker (``parser.py``)
can compare generated output against ``src/data_classes.c`` with no
semantic reinterpretation.

Like ``items`` (Issue #5 Batch 1's other global table), ``gClassData[]``
is not chapter-scoped: it is the single global, index-designated table
covering the *entire* vanilla ``CLASS_*`` enum, authored as a flat list
keyed by symbolic class rather than the grouped chapter-owned arrays the
Chapter 2 vertical-slice tables (``units``/``shops``/``traps``/...) use.
Per Issue #5 Batch 1 scope this is schema/generate/round-trip only --
``build/generated/data/data_classes.c`` is never linked in place of the
hand-written ``src/data_classes.c``.

``.number`` is never authored: it is always the class's own designator
value (``[CLASS_X - 1] = { .number = CLASS_X, ... }`` in every one of the
127 vanilla records -- confirmed field-for-field against
``src/data_classes.c``), so the generator derives it directly from the
JSON record's own ``class`` key instead of accepting it as input.

``CLASS_NONE`` (index 0, the sentinel "no class" value) and the
``CLASS_OBSTACLE`` alias (``#define``-like ``CLASS_OBSTACLE =
CLASS_EPHRAIM_LORD`` -- not its own enum value, so
``extract_enum_constants`` never returns it) are both excluded from the
required-coverage set: coverage is exactly the 127 contiguous values
``CLASS_EPHRAIM_LORD`` (1) .. ``CLASS_PUPIL_T1`` (127).

JSON source shape (see ``src/data/classes.json``)::

    {
      "$schema": "fe8.classes.v1",
      "classes": [
        {
          "class": "CLASS_EPHRAIM_LORD",
          "nameTextId": 703,
          "descTextId": 777,
          "promotion": "CLASS_EPHRAIM_MASTER_LORD",
          "smsId": 0,
          "defaultPortraitId": 139,
          "sortOrder": 1,
          "base": { "hp": 18, "pow": 6, "skl": 6, "spd": 7, "def": 6, "res": 0, "con": 8, "mov": 5 },
          "max": { "hp": 60, "pow": 20, "skl": 20, "spd": 20, "def": 20, "res": 20, "con": 20 },
          "classRelativePower": 3,
          "growth": { "hp": 90, "pow": 45, "skl": 40, "spd": 45, "def": 15, "res": 15, "lck": 40 },
          "attributes": ["CA_LORD", "CA_LOCK_5"],
          "baseRanks": { "ITYPE_LANCE": "WPN_EXP_D" },
          "battleAnim": "AnimConf_0",
          "movCostTable": [
            "TerrainTable_MovCost_CommonT2Normal",
            "TerrainTable_MovCost_CommonT2Rain",
            "TerrainTable_MovCost_CommonT2Snow"
          ],
          "terrainAvoid": "TerrainTable_Avo_Common",
          "terrainDefense": "TerrainTable_Def_Common",
          "terrainResistance": "TerrainTable_Res_Common"
        },
        ...
      ]
    }

Optional ``ClassData`` fields default exactly like the hand-written
designated initializers that only set the fields they need:

* ``nameTextId``/``descTextId`` -> ``0``
* ``promotion`` -> ``"CLASS_NONE"`` (no promotion; the field's own zero
  value -- 32/127 vanilla records omit it, meaning "this class doesn't
  promote")
* ``smsId`` -> ``0`` (though 127/127 vanilla records set it explicitly)
* ``slowWalking`` -> ``false`` (``UNIT_WALKSPEED_FAST``; ``true`` maps to
  ``UNIT_WALKSPEED_SLOW`` -- only 2 valid enum states, so this is
  authored as a JSON boolean rather than a bare enum-name string)
* ``defaultPortraitId``/``sortOrder``/``classRelativePower`` -> ``0``
* ``base``/``max``/``growth``/``promotionGain`` sub-objects -> all-zero
  when the whole object is omitted, or per-field ``0`` when the object is
  present but a particular stat key is omitted
* ``attributes`` -> ``[]`` (``CA_NONE``)
* ``baseRanks`` -> ``{}`` (``WPN_EXP_0`` for every weapon type -- 37/127
  vanilla records have no ``.baseRanks`` at all, meaning "this class
  cannot use any weapon type")
* ``battleAnim`` -> ``null`` (``NULL`` pointer -- 26/127 vanilla records,
  all non-combat obstacle/civilian/ballista-remnant classes, have no
  ``.pBattleAnimDef``)
* ``reservedTerrainTable`` -> ``null`` (``NULL`` -- the struct's
  ``._pU50`` escape hatch, see below)

``movCostTable``/``terrainAvoid``/``terrainDefense``/``terrainResistance``
are, like ``items``' ``weaponType``/``iconId``, always set explicitly by
every one of the 127 vanilla records (confirmed field-for-field), so they
are required JSON fields rather than defaulted/omittable ones.

``terrainAvoid``/``terrainDefense``/``terrainResistance`` are validated
against the Issue #5 Batch 1 ``terrainstats`` table (see
``dependency_tables()`` below) rather than the generic
``CSymbolRefField`` header-only check: each referenced symbol must be one
of the 6 ``TerrainTable_Avo_*``/``Def_*``/``Res_*`` arrays *authored in
terrainstats* with a matching ``field`` (``terrainAvoid``/
``terrainDefense``/``terrainResistance``) -- common or fly mobility are
both accepted, since ``ClassData`` itself has no separate "mobility"
concept; the referenced symbol alone (``_Common`` vs ``_Fly``) encodes
that. ``reservedTerrainTable`` is unaffected by this and remains a plain
``CSymbolRefField`` escape hatch (the unresearched ``_pU50`` field stays
out of scope).

``movCostTable`` is, since Issue #5 Batch 2, validated against the
``movecost`` table the same way: each non-null triplet entry must be one
of the 47 ``TerrainTable_MovCost_*``/``TerrainMoveCost_Ballista`` arrays
*authored in movecost*, and all non-null entries across the triplet must
resolve to the *same* movecost profile at their own matching
normal/rain/snow slot (see ``movecost/schema.py``'s
``build_slot_symbol_index()``) -- e.g. slot 0 (normal) must name that
profile's own ``normal`` array, not another profile's or another slot's.
Single-variant profiles (``DemonKing``/``Ballista``, which author only a
``normal`` array) resolve consistently no matter which of the 3 slots
their lone symbol is repeated in -- confirmed against ``CLASS_DEMON_KING``,
whose 127-record ``pMovCostTable`` entry is
``{ TerrainTable_MovCost_DemonKing, TerrainTable_MovCost_DemonKing,
TerrainTable_MovCost_DemonKing }`` (the same symbol in all 3 slots, not a
per-weather variant). An all-null triplet (the 9/127 fully-immobile
vanilla records, see ``MOV_COST_NULL_LITERAL`` above) is unaffected and
remains valid regardless of any movecost dependency.

``reservedTerrainTable`` models the struct's ``._pU50`` field (``const
void* _pU50``, an unresearched escape hatch -- see ``include/bmunit.h``).
11/127 vanilla records set it, always to ``&Unk_TerrainTable_N`` (N in
3..6); it is validated the same way as ``battleAnim``/``movCostTable``/
``terrainAvoid``/``terrainDefense``/``terrainResistance`` -- a
``CSymbolRefField`` reference into ``include/variables.h`` -- but unlike
those, the hand file always takes its address explicitly with ``&``
(because the field's C type is ``const void*``, not ``const s8*``, so a
bare array-decay wouldn't have the right type); ``generate.py`` emits the
matching ``&`` prefix and ``parser.py`` strips it back off before
comparing symbol names.

``defaultPortraitId`` is validated against the live count of numbered
entries in ``src/portrait_data.c`` (``portrait_data[]``, 172 entries,
0..171) -- the strongest deterministic *source-level* bound available,
since the real built asset table only exists after the graphics pipeline
runs. ``smsId`` is validated against the live count of numbered entries
in ``src/unit_icon_wait_data.c`` (``unit_icon_wait_table[]``, 107
entries, 0..106) for the same reason -- note this is a *stronger* bound
than the raw 7-bit mask ``GetInfo()`` applies at runtime
(``(id) & ((1<<7)-1)``, i.e. 0..127): entries 107..127 would read past
the end of the actual table, so validating against the real table length
(not the mask width) is the correct, provably-safe bound. Both bounds are
derived live from their source files rather than hardcoded, so they stay
honest if either table ever grows.
"""

from __future__ import annotations

import os
import re

from ..cparse import strip_hand_conditionals
from ..diagnostics import GeneratedDataError
from ..escape_hatch import CSymbolRefField
from ..json_loader import load_json_file
from ..schema import DependencyGraph, TableSchema
from ..validators import (
    extract_enum_constants,
    resolve_bitmask_flags,
    validate_range,
    validate_reference,
    validate_unique,
)

SCHEMA_NAME = "classes"
SCHEMA_VERSION = 1
SCHEMA_ID = "fe8.classes.v1"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CLASSES_HEADER = os.path.join(REPO_ROOT, "include", "constants", "classes.h")
BMUNIT_HEADER = os.path.join(REPO_ROOT, "include", "bmunit.h")
BMITEM_HEADER = os.path.join(REPO_ROOT, "include", "bmitem.h")
EKRBATTLE_HEADER = os.path.join(REPO_ROOT, "include", "ekrbattle.h")
VARIABLES_HEADER = os.path.join(REPO_ROOT, "include", "variables.h")
MSG_HEADER = os.path.join(REPO_ROOT, "include", "constants", "msg.h")
PORTRAIT_DATA_SOURCE = os.path.join(REPO_ROOT, "src", "portrait_data.c")
SMS_DATA_SOURCE = os.path.join(REPO_ROOT, "src", "unit_icon_wait_data.c")

_S8_MIN, _S8_MAX = -128, 127
_U8_MIN, _U8_MAX = 0, 255

WPN_EXP_DEFAULT = "WPN_EXP_0"
CLASS_NONE_DEFAULT = "CLASS_NONE"

# ``pMovCostTable`` entries are normally ``CSymbolRefField`` references into
# a ``TerrainTable_MovCost_*`` symbol, but 9/127 vanilla records (fully
# immobile classes: gorgon egg forms, spent/empty ballistae, CLASS_UNK77)
# use this literal null-pointer cast for every slot instead of a named
# table -- confirmed field-for-field against ``src/data_classes.c``.
# Modeled as JSON ``null`` in ``movCostTable`` (see ``_nullable_str``);
# ``generate.py`` emits the literal back verbatim and ``parser.py``
# recognizes it as the same "no table" sentinel rather than a symbol.
MOV_COST_NULL_LITERAL = "(void *)0x00000000"

_CLASS_ATTRIBUTES_BLOCK_RE = re.compile(r"//\s*Character/Class attributes(.*?)//\s*Helpers", re.S)
_ATTRIBUTE_ENTRY_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:\(\s*1\s*<<\s*(\d+)\s*\)|(-?\d+))\s*,"
)
_STRUCT_BODY_RE_CACHE = {}
_NUMBERED_ARRAY_ENTRY_RE = re.compile(r"^\s*\{[^{}]*\},?\s*//\s*\d+\s*$", re.MULTILINE)

_BASE_STATS = ("hp", "pow", "skl", "spd", "def", "res", "con", "mov")
_MAX_STATS = ("hp", "pow", "skl", "spd", "def", "res", "con")
_GROWTH_STATS = ("hp", "pow", "skl", "spd", "def", "res", "lck")
_PROMOTION_STATS = ("hp", "pow", "skl", "spd", "def", "res")

_MOVCOST_SLOTS = ("normal", "rain", "snow")


def _read_struct_body(header, struct_name):
    key = (header, struct_name)
    if key in _STRUCT_BODY_RE_CACHE:
        return _STRUCT_BODY_RE_CACHE[key]
    with open(header, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"struct\s+{}\s*\{{(.*?)\n\}};".format(re.escape(struct_name)), text, re.S)
    if not match:
        raise GeneratedDataError("could not find 'struct {}' in {}".format(struct_name, header))
    body = match.group(1)
    _STRUCT_BODY_RE_CACHE[key] = body
    return body


def read_class_data_array_capacity(field_name, header=BMUNIT_HEADER):
    """Read a ``struct ClassData`` fixed-array field's declared capacity
    (e.g. ``baseRanks[8]`` -> 8, ``pMovCostTable[3]`` -> 3) live from
    ``include/bmunit.h``, instead of hardcoding the numeral."""
    body = _read_struct_body(header, "ClassData")
    match = re.search(r"\b{}\s*\[\s*(\d+)\s*\]".format(re.escape(field_name)), body)
    if not match:
        raise GeneratedDataError(
            "could not find 'ClassData::{}[N]' in {}".format(field_name, header)
        )
    return int(match.group(1))


def read_class_attributes(header=BMUNIT_HEADER):
    """Read the individual ``CA_*`` bit-flag constants (the block starting
    at ``CA_NONE = 0`` and ending right before the ``// Helpers`` combos
    like ``CA_REFRESHER``/``CA_FLYER``/``CA_TRIANGLEATTACK_ANY``) live
    from ``include/bmunit.h``.

    Only real single-bit flags (plus the ``CA_NONE = 0`` sentinel) are
    returned -- the combo helpers are deliberately excluded: no vanilla
    record references them directly, so they are not accepted as
    ``attributes`` list entries either.
    """
    with open(header, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = _CLASS_ATTRIBUTES_BLOCK_RE.search(text)
    if not match:
        raise GeneratedDataError("could not find the CA_* class-attributes enum in {}".format(header))
    flags = {}
    for entry_match in _ATTRIBUTE_ENTRY_RE.finditer(match.group(1)):
        name = entry_match.group(1)
        if entry_match.group(2) is not None:
            value = 1 << int(entry_match.group(2))
        else:
            value = int(entry_match.group(3))
        flags[name] = value
    return flags


def read_msg_count(header=MSG_HEADER):
    """Read the live ``MSG_COUNT`` upper bound for text IDs (see
    ``items/schema.py``, which reads the same constant)."""
    from ..validators import extract_define_constant
    value, _ = extract_define_constant(header, "MSG_COUNT")
    return value


def _count_numbered_array_entries(source):
    with open(source, "r", encoding="utf-8") as handle:
        text = handle.read()
    text = strip_hand_conditionals(text)
    return len(_NUMBERED_ARRAY_ENTRY_RE.findall(text))


def read_portrait_count(source=PORTRAIT_DATA_SOURCE):
    """Derive the number of playable portrait slots from the live,
    numbered ``portrait_data[]`` array in ``src/portrait_data.c`` (each
    entry carries its own index as a trailing ``// N`` comment)."""
    return _count_numbered_array_entries(source)


def read_sms_count(source=SMS_DATA_SOURCE):
    """Derive the number of map-sprite-set (SMS) slots from the live,
    numbered ``unit_icon_wait_table[]`` array in
    ``src/unit_icon_wait_data.c``.

    This is a stronger bound than the raw 7-bit mask ``GetInfo()`` applies
    at runtime (``(id) & ((1<<7)-1)``, i.e. 0..127): the real table only
    has 107 entries (0..106), so any ``smsId`` in 107..127 would read past
    its end. See the module docstring for the full rationale.
    """
    return _count_numbered_array_entries(source)


def _optional_int(node, default=0):
    if node is None:
        return default, None
    return node.as_int(), node.loc


def _optional_str(node, default):
    if node is None:
        return default, None
    return node.as_str(), node.loc


def _optional_bool(node, default=False):
    if node is None:
        return default, None
    if not (node.is_scalar() and isinstance(node.value, bool)):
        raise GeneratedDataError("expected a boolean, found {}".format(node._type_name()), node.loc)
    return node.value, node.loc


def _nullable_str(node):
    """``battleAnim``/``reservedTerrainTable``: absent or explicit JSON
    ``null`` both mean "no pointer" (``NULL``); otherwise a plain string
    symbol."""
    if node is None:
        return None, None
    if node.is_scalar() and node.value is None:
        return None, node.loc
    return node.as_str(), node.loc


def _load_stat_group(node, keys, container_loc):
    """Parse an optional ``{ "hp": N, ... }`` stat sub-object. Returns
    ``(values_dict, locs_dict)`` -- every key defaults to ``0`` (with no
    location) when the whole group, or an individual key, is omitted."""
    values = {k: 0 for k in keys}
    locs = {k: None for k in keys}
    if node is None:
        return values, locs
    for key in keys:
        key_node = node.get(key)
        if key_node is not None:
            values[key] = key_node.as_int()
            locs[key] = key_node.loc
    return values, locs


class ClassRecord:
    """One ``gClassData[]`` entry, with per-field source locations."""

    def __init__(self, class_name, class_loc, name_text_id, name_text_loc,
                 desc_text_id, desc_text_loc, promotion, promotion_loc,
                 sms_id, sms_id_loc, slow_walking, slow_walking_loc,
                 default_portrait_id, default_portrait_id_loc,
                 sort_order, sort_order_loc,
                 base, base_locs, max_stats, max_locs,
                 class_relative_power, class_relative_power_loc,
                 growth, growth_locs, promotion_gain, promotion_gain_locs,
                 attributes, attributes_loc,
                 base_ranks, base_ranks_locs, base_ranks_container_loc,
                 battle_anim, battle_anim_loc,
                 mov_cost_table, mov_cost_table_locs,
                 terrain_avoid, terrain_avoid_loc,
                 terrain_defense, terrain_defense_loc,
                 terrain_resistance, terrain_resistance_loc,
                 reserved_terrain_table, reserved_terrain_table_loc, loc):
        self.class_name = class_name
        self.class_loc = class_loc
        self.name_text_id = name_text_id
        self.name_text_loc = name_text_loc
        self.desc_text_id = desc_text_id
        self.desc_text_loc = desc_text_loc
        self.promotion = promotion
        self.promotion_loc = promotion_loc
        self.sms_id = sms_id
        self.sms_id_loc = sms_id_loc
        self.slow_walking = slow_walking
        self.slow_walking_loc = slow_walking_loc
        self.default_portrait_id = default_portrait_id
        self.default_portrait_id_loc = default_portrait_id_loc
        self.sort_order = sort_order
        self.sort_order_loc = sort_order_loc
        self.base = base
        self.base_locs = base_locs
        self.max_stats = max_stats
        self.max_locs = max_locs
        self.class_relative_power = class_relative_power
        self.class_relative_power_loc = class_relative_power_loc
        self.growth = growth
        self.growth_locs = growth_locs
        self.promotion_gain = promotion_gain
        self.promotion_gain_locs = promotion_gain_locs
        self.attributes = attributes
        self.attributes_loc = attributes_loc
        self.base_ranks = base_ranks
        self.base_ranks_locs = base_ranks_locs
        self.base_ranks_container_loc = base_ranks_container_loc
        self.battle_anim = battle_anim
        self.battle_anim_loc = battle_anim_loc
        self.mov_cost_table = mov_cost_table
        self.mov_cost_table_locs = mov_cost_table_locs
        self.terrain_avoid = terrain_avoid
        self.terrain_avoid_loc = terrain_avoid_loc
        self.terrain_defense = terrain_defense
        self.terrain_defense_loc = terrain_defense_loc
        self.terrain_resistance = terrain_resistance
        self.terrain_resistance_loc = terrain_resistance_loc
        self.reserved_terrain_table = reserved_terrain_table
        self.reserved_terrain_table_loc = reserved_terrain_table_loc
        self.loc = loc

    def encoded_base_ranks(self, weapon_types, wexp_thresholds, capacity):
        """Resolve ``baseRanks`` to a fixed ``capacity``-length tuple of
        ``WPN_EXP_*`` integer values, indexed by each weapon type's own
        enum value (unset slots default to ``WPN_EXP_0`` = 0)."""
        slots = [0] * capacity
        for itype_name, wexp_name in self.base_ranks.items():
            if itype_name not in weapon_types or wexp_name not in wexp_thresholds:
                continue
            index = weapon_types[itype_name][0]
            if 0 <= index < capacity:
                slots[index] = wexp_thresholds[wexp_name][0]
        return tuple(slots)

    def as_tuple(self, classes_enum, attribute_flags, weapon_types, wexp_thresholds, base_ranks_capacity):
        """A fully-resolved, symbol-blind tuple for exact round-trip
        comparison against the hand-parsed record (see ``parser.py``).
        Enum/bitmask-valued fields are resolved to their live integer
        value; C-symbol-reference fields (``battleAnim``/
        ``movCostTable``/terrain lookups/``reservedTerrainTable``) are
        compared as bare token strings, since they have no further
        numeric encoding to resolve."""
        promotion_value = classes_enum.get(self.promotion, (0, None))[0]
        attributes_value, _ = resolve_bitmask_flags(self.attributes, attribute_flags, self.loc, "")
        base_ranks_tuple = self.encoded_base_ranks(weapon_types, wexp_thresholds, base_ranks_capacity)
        return (
            self.name_text_id, self.desc_text_id, promotion_value,
            self.sms_id, 1 if self.slow_walking else 0,
            self.default_portrait_id, self.sort_order,
            tuple(self.base[k] for k in _BASE_STATS),
            tuple(self.max_stats[k] for k in _MAX_STATS),
            self.class_relative_power,
            tuple(self.growth[k] for k in _GROWTH_STATS),
            tuple(self.promotion_gain[k] for k in _PROMOTION_STATS),
            attributes_value,
            base_ranks_tuple,
            self.battle_anim,
            tuple(self.mov_cost_table),
            self.terrain_avoid, self.terrain_defense, self.terrain_resistance,
            self.reserved_terrain_table,
        )


class ClassRecordList(list):
    """A plain list of :class:`ClassRecord` that also remembers the
    ``classes`` JSON array's own source location, for diagnostics (e.g.
    missing coverage) that describe the document as a whole rather than
    any single record."""

    def __init__(self, records, loc):
        super().__init__(records)
        self.loc = loc


def load_records(source_path):
    root = load_json_file(source_path)
    schema_node = root.require("$schema")
    if schema_node.as_str() != SCHEMA_ID:
        raise GeneratedDataError(
            "unexpected $schema '{}', expected '{}'".format(schema_node.as_str(), SCHEMA_ID),
            schema_node.loc,
        )
    classes_node = root.require("classes")
    records = []
    for class_node in classes_node.as_list():
        class_name_node = class_node.require("class")

        name_text_id, name_text_loc = _optional_int(class_node.get("nameTextId"))
        desc_text_id, desc_text_loc = _optional_int(class_node.get("descTextId"))
        promotion, promotion_loc = _optional_str(class_node.get("promotion"), CLASS_NONE_DEFAULT)
        sms_id, sms_id_loc = _optional_int(class_node.get("smsId"))
        slow_walking, slow_walking_loc = _optional_bool(class_node.get("slowWalking"))
        default_portrait_id, default_portrait_id_loc = _optional_int(class_node.get("defaultPortraitId"))
        sort_order, sort_order_loc = _optional_int(class_node.get("sortOrder"))

        base_node = class_node.get("base")
        base, base_locs = _load_stat_group(base_node, _BASE_STATS, class_node.loc)
        max_node = class_node.get("max")
        max_stats, max_locs = _load_stat_group(max_node, _MAX_STATS, class_node.loc)
        class_relative_power, class_relative_power_loc = _optional_int(class_node.get("classRelativePower"))
        growth_node = class_node.get("growth")
        growth, growth_locs = _load_stat_group(growth_node, _GROWTH_STATS, class_node.loc)
        promotion_gain_node = class_node.get("promotionGain")
        promotion_gain, promotion_gain_locs = _load_stat_group(promotion_gain_node, _PROMOTION_STATS, class_node.loc)

        attributes_node = class_node.get("attributes")
        attributes = [n.as_str() for n in attributes_node.as_list()] if attributes_node is not None else []
        attributes_loc = attributes_node.loc if attributes_node is not None else class_node.loc

        base_ranks_node = class_node.get("baseRanks")
        base_ranks = {}
        base_ranks_locs = {}
        base_ranks_container_loc = base_ranks_node.loc if base_ranks_node is not None else class_node.loc
        if base_ranks_node is not None:
            for itype_key in base_ranks_node.keys():
                value_node = base_ranks_node.require(itype_key)
                base_ranks[itype_key] = value_node.as_str()
                base_ranks_locs[itype_key] = value_node.loc

        battle_anim, battle_anim_loc = _nullable_str(class_node.get("battleAnim"))

        mov_cost_node = class_node.require("movCostTable")
        mov_cost_items = mov_cost_node.as_list()
        mov_cost_table = []
        mov_cost_table_locs = []
        for item_node in mov_cost_items:
            if item_node.is_scalar() and item_node.value is None:
                mov_cost_table.append(None)
            else:
                mov_cost_table.append(item_node.as_str())
            mov_cost_table_locs.append(item_node.loc)

        terrain_avoid_node = class_node.require("terrainAvoid")
        terrain_defense_node = class_node.require("terrainDefense")
        terrain_resistance_node = class_node.require("terrainResistance")

        reserved_terrain_table, reserved_terrain_table_loc = _nullable_str(class_node.get("reservedTerrainTable"))

        records.append(
            ClassRecord(
                class_name=class_name_node.as_str(), class_loc=class_name_node.loc,
                name_text_id=name_text_id, name_text_loc=name_text_loc,
                desc_text_id=desc_text_id, desc_text_loc=desc_text_loc,
                promotion=promotion, promotion_loc=promotion_loc,
                sms_id=sms_id, sms_id_loc=sms_id_loc,
                slow_walking=slow_walking, slow_walking_loc=slow_walking_loc,
                default_portrait_id=default_portrait_id, default_portrait_id_loc=default_portrait_id_loc,
                sort_order=sort_order, sort_order_loc=sort_order_loc,
                base=base, base_locs=base_locs,
                max_stats=max_stats, max_locs=max_locs,
                class_relative_power=class_relative_power, class_relative_power_loc=class_relative_power_loc,
                growth=growth, growth_locs=growth_locs,
                promotion_gain=promotion_gain, promotion_gain_locs=promotion_gain_locs,
                attributes=attributes, attributes_loc=attributes_loc,
                base_ranks=base_ranks, base_ranks_locs=base_ranks_locs,
                base_ranks_container_loc=base_ranks_container_loc,
                battle_anim=battle_anim, battle_anim_loc=battle_anim_loc,
                mov_cost_table=mov_cost_table, mov_cost_table_locs=mov_cost_table_locs,
                terrain_avoid=terrain_avoid_node.as_str(), terrain_avoid_loc=terrain_avoid_node.loc,
                terrain_defense=terrain_defense_node.as_str(), terrain_defense_loc=terrain_defense_node.loc,
                terrain_resistance=terrain_resistance_node.as_str(), terrain_resistance_loc=terrain_resistance_node.loc,
                reserved_terrain_table=reserved_terrain_table, reserved_terrain_table_loc=reserved_terrain_table_loc,
                loc=class_node.loc,
            )
        )
    return ClassRecordList(records, classes_node.loc)


def validate(records, diagnostics, dependency_records=None, classes_header=CLASSES_HEADER,
             bmunit_header=BMUNIT_HEADER,
             bmitem_header=BMITEM_HEADER, ekrbattle_header=EKRBATTLE_HEADER,
             variables_header=VARIABLES_HEADER, msg_header=MSG_HEADER,
             portrait_source=PORTRAIT_DATA_SOURCE, sms_source=SMS_DATA_SOURCE,
             msg_count=None, portrait_count=None, sms_count=None,
             base_ranks_capacity=None, mov_cost_table_capacity=None):
    """Run all ``ClassData`` validations, appending errors to ``diagnostics``.

    Checks: unique + full contiguous ``CLASS_*`` coverage (1..127,
    excluding ``CLASS_NONE`` and the ``CLASS_OBSTACLE`` alias),
    ``promotion`` self-reference, ``attributes`` as a validated ``CA_*``
    bitmask list, ``baseRanks`` as validated ``ITYPE_*`` (bounded to the
    array's own capacity) -> ``WPN_EXP_*`` entries, all numeric widths/
    ranges (base/max/growth/promotion-gain stats at their actual C type
    widths, text IDs against ``MSG_COUNT``, ``defaultPortraitId``/
    ``smsId`` against their live source-derived bounds), the exact
    ``movCostTable`` triplet capacity, and every C-symbol-reference field
    (``battleAnim``, ``reservedTerrainTable``).
    ``terrainAvoid``/``terrainDefense``/``terrainResistance`` are instead
    resolved against ``dependency_records["terrainstats"]`` (see
    ``dependency_tables()``) -- each referenced symbol must be one of the
    authored terrainstats arrays with a matching ``field``; when no
    terrainstats dependency records are supplied, falls back to the
    generic ``CSymbolRefField`` header check (standalone/unit-test use).
    ``movCostTable`` entries are similarly resolved against
    ``dependency_records["movecost"]`` -- each non-null entry must be one
    of the authored movecost arrays, and all non-null entries in a
    triplet must resolve to the same movecost profile at their own
    matching slot; when no movecost dependency records are supplied,
    falls back to the generic ``CSymbolRefField`` header check.
    """
    dependency_records = dependency_records or {}
    terrainstats_field_by_symbol = {
        r.symbol: r.field for r in dependency_records.get("terrainstats", ())
    }
    movecost_records = dependency_records.get("movecost")
    movecost_slot_index = None
    if movecost_records:
        from ..movecost.schema import build_slot_symbol_index
        movecost_slot_index = build_slot_symbol_index(movecost_records)

    if msg_count is None:
        msg_count = read_msg_count(msg_header)
    if portrait_count is None:
        portrait_count = read_portrait_count(portrait_source)
    if sms_count is None:
        sms_count = read_sms_count(sms_source)
    if base_ranks_capacity is None:
        base_ranks_capacity = read_class_data_array_capacity("baseRanks", bmunit_header)
    if mov_cost_table_capacity is None:
        mov_cost_table_capacity = read_class_data_array_capacity("pMovCostTable", bmunit_header)

    classes_enum = extract_enum_constants(classes_header, name_prefix="CLASS_")
    weapon_types = extract_enum_constants(bmitem_header, name_prefix="ITYPE_")
    wexp_thresholds = extract_enum_constants(bmitem_header, name_prefix="WPN_EXP_")
    attribute_flags = read_class_attributes(bmunit_header)
    battle_anim_field = CSymbolRefField(ekrbattle_header, description="battle animation table")
    terrain_field = CSymbolRefField(variables_header, description="terrain/movement table")

    diagnostics.extend(
        validate_unique(
            ((r.class_name, r.class_loc) for r in records),
            "duplicate class entry '{key}' (first defined at {first_loc})",
            "classes[class={key}]",
        )
    )

    covered_values = {}
    for record in records:
        ref = "classes[class={}]".format(record.class_name)

        diagnostics.extend(validate_reference(record.class_name, classes_enum, record.class_loc, ref, kind="class"))
        if record.class_name in classes_enum:
            covered_values[classes_enum[record.class_name][0]] = record.class_name

        diagnostics.extend(
            validate_reference(record.promotion, classes_enum, record.promotion_loc or record.loc,
                                "{}.promotion".format(ref), kind="class")
        )

        for field_name, value, loc in (
            ("nameTextId", record.name_text_id, record.name_text_loc),
            ("descTextId", record.desc_text_id, record.desc_text_loc),
        ):
            diagnostics.extend(
                validate_range(value, 0, msg_count - 1, loc or record.loc,
                                "{}.{}".format(ref, field_name), field_name=field_name)
            )

        diagnostics.extend(
            validate_range(record.sms_id, 0, sms_count - 1, record.sms_id_loc or record.loc,
                            "{}.smsId".format(ref), field_name="smsId")
        )
        diagnostics.extend(
            validate_range(record.default_portrait_id, 0, portrait_count - 1,
                            record.default_portrait_id_loc or record.loc,
                            "{}.defaultPortraitId".format(ref), field_name="defaultPortraitId")
        )
        diagnostics.extend(
            validate_range(record.sort_order, _U8_MIN, _U8_MAX, record.sort_order_loc or record.loc,
                            "{}.sortOrder".format(ref), field_name="sortOrder")
        )

        for group_name, values, locs in (
            ("base", record.base, record.base_locs),
            ("max", record.max_stats, record.max_locs),
            ("growth", record.growth, record.growth_locs),
        ):
            for stat_key, value in values.items():
                diagnostics.extend(
                    validate_range(value, _S8_MIN, _S8_MAX, locs[stat_key] or record.loc,
                                    "{}.{}.{}".format(ref, group_name, stat_key), field_name=stat_key)
                )
        diagnostics.extend(
            validate_range(record.class_relative_power, _S8_MIN, _S8_MAX,
                            record.class_relative_power_loc or record.loc,
                            "{}.classRelativePower".format(ref), field_name="classRelativePower")
        )
        for stat_key, value in record.promotion_gain.items():
            diagnostics.extend(
                validate_range(value, _U8_MIN, _U8_MAX, record.promotion_gain_locs[stat_key] or record.loc,
                                "{}.promotionGain.{}".format(ref, stat_key), field_name=stat_key)
            )

        _, attribute_errors = resolve_bitmask_flags(
            record.attributes, attribute_flags, record.attributes_loc,
            "{}.attributes".format(ref), kind="class attribute",
        )
        diagnostics.extend(attribute_errors)

        for itype_name, wexp_name in record.base_ranks.items():
            entry_loc = record.base_ranks_locs.get(itype_name) or record.base_ranks_container_loc
            entry_ref = "{}.baseRanks[{}]".format(ref, itype_name)
            type_errors = validate_reference(itype_name, weapon_types, entry_loc, entry_ref, kind="weapon type")
            diagnostics.extend(type_errors)
            if not type_errors:
                index = weapon_types[itype_name][0]
                if not (0 <= index < base_ranks_capacity):
                    diagnostics.add(
                        GeneratedDataError(
                            "weapon type '{}' (index {}) exceeds baseRanks capacity {}".format(
                                itype_name, index, base_ranks_capacity
                            ),
                            entry_loc, entry_ref,
                        )
                    )
            diagnostics.extend(
                validate_reference(wexp_name, wexp_thresholds, entry_loc, entry_ref, kind="weapon-exp threshold")
            )

        if record.battle_anim is not None:
            diagnostics.extend(
                battle_anim_field.validate(record.battle_anim, record.battle_anim_loc, "{}.battleAnim".format(ref))
            )

        if len(record.mov_cost_table) != mov_cost_table_capacity:
            diagnostics.add(
                GeneratedDataError(
                    "movCostTable has {} entries, expected exactly {} ({})".format(
                        len(record.mov_cost_table), mov_cost_table_capacity, "/".join(_MOVCOST_SLOTS)
                    ),
                    record.loc, "{}.movCostTable".format(ref),
                )
            )
        resolved_profiles = {}
        for slot_index, symbol in enumerate(record.mov_cost_table):
            if symbol is None:
                continue
            loc = record.mov_cost_table_locs[slot_index] if slot_index < len(record.mov_cost_table_locs) else record.loc
            entry_ref = "{}.movCostTable[{}]".format(ref, slot_index)
            if movecost_slot_index is not None:
                slot_name = _MOVCOST_SLOTS[slot_index] if slot_index < len(_MOVCOST_SLOTS) else None
                slot_map = movecost_slot_index.get(slot_name, {}) if slot_name else {}
                profile = slot_map.get(symbol)
                if profile is None:
                    diagnostics.add(
                        GeneratedDataError(
                            "movCostTable[{}] '{}' is not one of the arrays authored in movecost "
                            "for the '{}' slot".format(slot_index, symbol, slot_name),
                            loc, entry_ref,
                        )
                    )
                else:
                    resolved_profiles.setdefault(profile, []).append(slot_index)
            else:
                diagnostics.extend(terrain_field.validate(symbol, loc, entry_ref))

        if movecost_slot_index is not None and len(resolved_profiles) > 1:
            diagnostics.add(
                GeneratedDataError(
                    "movCostTable mixes symbols from different movecost profiles: {}".format(
                        ", ".join(
                            "{} (slot(s) {})".format(profile, ", ".join(map(str, slots)))
                            for profile, slots in sorted(resolved_profiles.items())
                        )
                    ),
                    record.loc, "{}.movCostTable".format(ref),
                )
            )

        for field_name, symbol, loc in (
            ("terrainAvoid", record.terrain_avoid, record.terrain_avoid_loc),
            ("terrainDefense", record.terrain_defense, record.terrain_defense_loc),
            ("terrainResistance", record.terrain_resistance, record.terrain_resistance_loc),
        ):
            field_loc = loc or record.loc
            field_ref = "{}.{}".format(ref, field_name)
            if terrainstats_field_by_symbol:
                actual_field = terrainstats_field_by_symbol.get(symbol)
                if actual_field is None:
                    diagnostics.add(
                        GeneratedDataError(
                            "{} '{}' is not one of the arrays authored in terrainstats".format(
                                field_name, symbol
                            ),
                            field_loc, field_ref,
                        )
                    )
                elif actual_field != field_name:
                    diagnostics.add(
                        GeneratedDataError(
                            "{} '{}' is authored in terrainstats with field '{}', expected '{}'".format(
                                field_name, symbol, actual_field, field_name
                            ),
                            field_loc, field_ref,
                        )
                    )
            else:
                diagnostics.extend(terrain_field.validate(symbol, field_loc, field_ref))

        if record.reserved_terrain_table is not None:
            diagnostics.extend(
                terrain_field.validate(
                    record.reserved_terrain_table, record.reserved_terrain_table_loc,
                    "{}.reservedTerrainTable".format(ref),
                )
            )

    if classes_enum:
        max_value = max(value for value, _ in classes_enum.values())
        missing = sorted(set(range(1, max_value + 1)) - set(covered_values))
        if missing:
            value_to_name = {value: name for name, (value, _) in classes_enum.items()}
            doc_loc = getattr(records, "loc", None)
            for value in missing:
                name = value_to_name.get(value, "0x{:02X}".format(value))
                diagnostics.add(
                    GeneratedDataError(
                        "missing class coverage for '{}' (index {}): no authored record".format(name, value),
                        doc_loc, "classes",
                    )
                )


class ClassesTableSchema(TableSchema):
    name = SCHEMA_NAME
    version = SCHEMA_VERSION

    default_source = "src/data/classes.json"
    default_hand_source = "src/data_classes.c"
    default_output_name = "data_classes.c"
    default_inventory_path = "reports/generated_data_classes_inventory.md"

    def dependencies(self):
        return (
            "constants.classes.CLASS", "bmitem.ITYPE", "bmitem.WPN_EXP", "bmunit.CA",
            "ekrbattle.AnimConf", "variables.TerrainTable", "constants.msg.MSG_COUNT",
            "data.portrait_data", "data.unit_icon_wait_data", "terrainstats", "movecost",
        )

    def dependency_tables(self):
        # Loaded via terrainstats'/movecost's own registered schemas and
        # `default_source` (overridable with `--dep-source
        # terrainstats=PATH`/`--dep-source movecost=PATH`) -- see
        # `cli.py`'s `_load_dependency_records()`. Used to validate
        # terrainAvoid/terrainDefense/terrainResistance against real
        # authored terrainstats records and movCostTable against real
        # authored movecost records, instead of a generic
        # header-presence check; reservedTerrainTable remains a
        # CSymbolRefField escape hatch, unaffected by either dependency.
        return ("terrainstats", "movecost")

    def load_records(self, source_path):
        return load_records(source_path)

    def validate(self, records, diagnostics, dependency_records=None):
        validate(records, diagnostics, dependency_records)

    def generate_c(self, records, source_path):
        from . import generate as classes_generate
        return classes_generate.generate_c_source(records, source_path)

    def build_inventory(self, records):
        from . import inventory as classes_inventory
        return classes_inventory.build_inventory(records)

    def round_trip_errors(self, records, hand_source):
        if not hand_source or not os.path.exists(hand_source):
            return []
        from . import parser as classes_roundtrip
        class_names = [r.class_name for r in records]
        hand_records = classes_roundtrip.parse_hand_written(hand_source, class_names)
        return classes_roundtrip.compare_records(records, hand_records, hand_path=hand_source)


def dependency_graph():
    graph = DependencyGraph()
    for dep in ClassesTableSchema().dependencies():
        graph.add_dependency(SCHEMA_NAME, dep)
    return graph
