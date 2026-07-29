"""``ItemData`` schema: the full 206-record vanilla ``gItemData[]`` table.

Mirrors the hand-written C layout in ``include/bmitem.h`` (``struct
ItemData``) field-for-field so the round-trip checker (``parser.py``) can
compare generated output against ``src/data_items.c`` with no semantic
reinterpretation.

Unlike every other Chapter 2 vertical-slice table (``units``/``shops``/
``traps``/...), ``gItemData[]`` is not chapter-scoped: it is the single
global, index-designated table covering the *entire* vanilla ``ITEM_*``
enum (``ITEM_NONE``..``ITEM_UNK_CD``, 206 contiguous entries, 0..205),
authored as a flat list keyed by symbolic index (``[ITEM_X] = { ... }``)
rather than the grouped chapter-owned arrays the other tables use. Per
Issue #5 Batch 1 scope this is schema/generate/round-trip only --
``build/generated/data/data_items.c`` is never linked in place of the
hand-written ``src/data_items.c``.

``.number`` is never authored: it is always the item's own designator
value (``[ITEM_X] = { .number = ITEM_X, ... }`` in every one of the 206
vanilla records -- confirmed field-for-field against ``src/data_items.c``),
so the generator derives it directly from the JSON record's own ``item``
key instead of accepting it as input.

JSON source shape (see ``src/data/items.json``)::

    {
      "$schema": "fe8.items.v1",
      "items": [
        {
          "item": "ITEM_SWORD_IRON",
          "nameTextId": 852,
          "descTextId": 1028,
          "weaponType": "ITYPE_SWORD",
          "attributes": ["IA_WEAPON"],
          "maxUses": 46,
          "might": 5,
          "hit": 90,
          "weight": 5,
          "range": { "min": 1, "max": 1 },
          "costPerUse": 10,
          "requiredWexp": "WPN_EXP_E",
          "iconId": 0,
          "weaponExp": 1
        },
        ...
      ]
    }

``nameTextId``/``descTextId``/``useDescTextId`` accept either a plain
integer (the vanilla authoring form -- all 206 hand-ported records use it)
or a symbolic ``MSG_*`` name from ``include/constants/msg.h``, the header
``scripts/texttools/textprocess.py`` regenerates from ``texts/texts.txt``::

    "nameTextId": "MSG_SAVE_COMPAT_BACK"

The symbolic form binds a record to a message the text pipeline actually
emits, so removing or renaming that message fails the data build with an
actionable diagnostic instead of silently repointing the item at whatever
text later lands on that number. Both forms resolve to the same integer
before generation, so the generated C and the round-trip comparison are
identical either way.

POLICY: a framework-authored (expansion overlay) record must not author a
NEW message for itself. ``texts/texts.txt`` feeds one shared,
Huffman-compressed blob, so one added message re-encodes the text of every
build -- default, feature-free ones included. Such a record leaves its text
IDs unset (they stay ``0``) and authors its display text literally instead;
see ``authoringName`` below.

Optional ``ItemData`` fields default exactly like the hand-written
designated initializers that only set the fields they need:

* ``nameTextId``/``descTextId``/``useDescTextId`` -> ``0``
* ``attributes`` -> ``[]`` (``IA_NONE``)
* ``statBonuses``/``effectiveness`` -> ``null`` (``NULL`` pointer)
* ``maxUses``/``might``/``hit``/``weight``/``crit``/``costPerUse``/
  ``useEffect``/``weaponExp`` -> ``0``
* ``range`` -> ``{ "min": 0, "max": 0 }`` (``encodedRange = 0``)
* ``requiredWexp`` -> ``"WPN_EXP_0"`` -- this is the struct's
  ``.weaponRank`` field; despite its name it holds a ``WPN_EXP_*``
  *required weapon-exp threshold*, not a weapon rank letter (see
  ``GetItemRequiredExp`` in ``src/bmitem.c``, which reads ``.weaponRank``
  straight through with no further translation)
* ``weaponEffect`` -> ``"WPN_EFFECT_NONE"``

``weaponType`` and ``iconId`` are the only two fields the vanilla data
*always* sets explicitly (206/206 records, including an explicit
``iconId = 0x0`` for ``ITEM_NONE``) -- the generator always emits both,
even when ``iconId`` is ``0``, matching that convention exactly; every
other field is emitted only when non-default, mirroring the hand file's
own convention of omitting zero/empty/null fields from the designated
initializer (confirmed field-for-field against ``src/data_items.c``: no
vanilla record ever writes an explicit zero/``NONE``/``null`` for any of
the conditional fields above).

``useEffectId`` is authored as a bare ``u8`` (``useEffect`` in JSON): the
codebase defines no ``USE_EFFECT_*``-style enum for it (54 distinct small
integers, 1..54, appear in the vanilla data with no named header constants
to reference), so it is intentionally left unvalidated beyond its numeric
range instead of inventing enum names that do not exist in the codebase.
"""

from __future__ import annotations

import os
import re

from ..diagnostics import GeneratedDataError
from ..escape_hatch import CSymbolRefField
from ..json_loader import load_json_file
from ..schema import DependencyGraph, TableSchema
from .. import idspace
from ..validators import (
    extract_define_constant,
    extract_define_constants,
    extract_enum_constants,
    resolve_bitmask_flags,
    validate_range,
    validate_reference,
    validate_unique,
)

SCHEMA_NAME = "items"
SCHEMA_VERSION = 1
SCHEMA_ID = "fe8.items.v1"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ITEMS_HEADER = os.path.join(REPO_ROOT, "include", "constants", "items.h")
BMITEM_HEADER = os.path.join(REPO_ROOT, "include", "bmitem.h")
VARIABLES_HEADER = os.path.join(REPO_ROOT, "include", "variables.h")
MSG_HEADER = os.path.join(REPO_ROOT, "include", "constants", "msg.h")
ITEM_ICON_SOURCE = os.path.join(REPO_ROOT, "src", "data", "data_item_icon.c")
ITEMS_EXPANSION_HEADER = os.path.join(REPO_ROOT, "include", "constants", "items_expansion.h")
ITEMS_EXPANSION_SOURCE = os.path.join(REPO_ROOT, "src", "data", "items_expansion.json")

_U8_MIN, _U8_MAX = 0, 255
_U16_MIN, _U16_MAX = 0, 65535
_NIBBLE_MIN, _NIBBLE_MAX = 0, 15

WPN_EXP_DEFAULT = "WPN_EXP_0"
WPN_EFFECT_DEFAULT = "WPN_EFFECT_NONE"

_ITEM_ATTRIBUTES_BLOCK_RE = re.compile(r"//\s*Item attributes(.*?)//\s*Helpers", re.S)
_ITEM_ATTRIBUTE_ENTRY_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:\(\s*1\s*<<\s*(\d+)\s*\)|(-?\d+))\s*,"
)
_ITEM_ICON_ENTRY_RE = re.compile(r'u8\s+item_icon_\w+\[\]\s*=\s*INCBIN_U8\("[^"]+\.4bpp"\)\s*;')


def read_item_attributes(header=BMITEM_HEADER):
    """Read the individual ``IA_*`` bit-flag constants (the block starting
    at ``IA_NONE = 0`` and ending right before the ``// Helpers`` combos
    like ``IA_REQUIRES_WEXP``/``IA_LOCK_ANY``) live from
    ``include/bmitem.h``.

    Only real single-bit flags (plus the ``IA_NONE = 0`` sentinel) are
    returned. The ``// Helpers`` combination constants are deliberately
    excluded: no vanilla record references them directly (they exist only
    for C code readability), so they are not accepted as ``attributes``
    list entries either.
    """
    with open(header, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = _ITEM_ATTRIBUTES_BLOCK_RE.search(text)
    if not match:
        raise GeneratedDataError("could not find the IA_* item-attributes enum in {}".format(header))
    flags = {}
    for entry_match in _ITEM_ATTRIBUTE_ENTRY_RE.finditer(match.group(1)):
        name = entry_match.group(1)
        if entry_match.group(2) is not None:
            value = 1 << int(entry_match.group(2))
        else:
            value = int(entry_match.group(3))
        flags[name] = value
    return flags


def read_msg_count(header=MSG_HEADER):
    """Read the live ``MSG_COUNT`` upper bound for text IDs."""
    value, _ = extract_define_constant(header, "MSG_COUNT")
    return value


def read_msg_constants(header=MSG_HEADER):
    """Read the live ``MSG_*`` text-ID constant family from
    ``include/constants/msg.h`` (the header the text pipeline
    ``scripts/texttools/textprocess.py`` regenerates from
    ``texts/texts.txt``).

    Returned as ``{name: (value, line_number)}``, i.e. the same shape
    :func:`~scripts.generated_data.validators.extract_enum_constants`
    produces, so a symbolic text ID can be validated and resolved with the
    ordinary reference machinery.

    ``MSG_COUNT`` is deliberately excluded: it is the table's *bound*, not
    a message, and authoring it as a text ID would always be a bug.
    """
    constants = extract_define_constants(header, name_prefix="MSG_")
    constants.pop("MSG_COUNT", None)
    return constants


# Cache keyed by header path: the MSG_* family is ~3.4k entries and every
# record in a table load would otherwise re-read the whole header.
_MSG_CONSTANTS_CACHE = {}


def _msg_constants(header=MSG_HEADER):
    cached = _MSG_CONSTANTS_CACHE.get(header)
    if cached is None:
        cached = read_msg_constants(header)
        _MSG_CONSTANTS_CACHE[header] = cached
    return cached


def read_item_icon_count(source=ITEM_ICON_SOURCE):
    """Derive the number of item-icon graphics tiles from
    ``src/data/data_item_icon.c`` by counting ``u8 item_icon_*[] =
    INCBIN_U8(".../*.4bpp")`` declarations.

    This is the strongest deterministic *source-level* bound available:
    the actual built asset table only exists after ``gbagfx`` decompresses
    these tiles during the build, so counting the declarations that drive
    that step avoids depending on any generated/binary build state. The
    one non-tile line in that file (``item_icon_palette[]``, a
    ``.agbpal`` palette, not a ``.4bpp`` tile) and the ``item_icon_tiles``
    alias (an ``extern`` alias of the first tile symbol, not its own
    ``INCBIN_U8`` declaration) are both excluded by construction -- the
    regex only matches ``.4bpp`` ``INCBIN_U8`` calls.
    """
    with open(source, "r", encoding="utf-8") as handle:
        text = handle.read()
    return len(_ITEM_ICON_ENTRY_RE.findall(text))


def _optional_int(node, default=0):
    if node is None:
        return default, None
    return node.as_int(), node.loc


def _optional_text_id(node, msg_header=MSG_HEADER):
    """``nameTextId``/``descTextId``/``useDescTextId``.

    Accepts either the vanilla authoring form -- a plain integer, which the
    206 hand-ported records all use -- or a symbolic ``MSG_*`` name from
    ``include/constants/msg.h``. The symbolic form is what
    framework-authored (non-vanilla) records should use: it binds the record
    to a message the text pipeline actually emits, so deleting/renaming that
    message fails the data build with an actionable diagnostic instead of
    silently pointing the item at whatever text later lands on that number.

    Always returns a resolved ``(int, loc)`` pair, so everything downstream
    (generation, round-trip comparison, range validation) is unchanged.
    """
    if node is None:
        return 0, None
    if node.is_scalar() and isinstance(node.value, str):
        symbol = node.as_str()
        constants = _msg_constants(msg_header)
        if symbol not in constants:
            raise GeneratedDataError(
                "unknown text ID '{}': no '#define {} ...' in {} (author it in "
                "texts/texts.txt and regenerate with `make src/msg_data.c`)".format(
                    symbol, symbol, os.path.relpath(msg_header, REPO_ROOT)),
                node.loc,
                SCHEMA_NAME,
            )
        return constants[symbol][0], node.loc
    return node.as_int(), node.loc


def _optional_str(node, default):
    if node is None:
        return default, None
    return node.as_str(), node.loc


def _nullable_str(node):
    """``statBonuses``/``effectiveness``: absent or explicit JSON ``null``
    both mean "no pointer" (``NULL``); otherwise a plain string symbol."""
    if node is None:
        return None, None
    if node.is_scalar() and node.value is None:
        return None, node.loc
    return node.as_str(), node.loc


class ItemRecord:
    """One ``gItemData[]`` entry, with per-field source locations."""

    def __init__(self, item, item_loc, name_text_id, name_text_loc, desc_text_id, desc_text_loc,
                 use_desc_text_id, use_desc_text_loc, weapon_type, weapon_type_loc,
                 attributes, attributes_loc, stat_bonuses, stat_bonuses_loc,
                 effectiveness, effectiveness_loc, max_uses, max_uses_loc,
                 might, might_loc, hit, hit_loc, weight, weight_loc, crit, crit_loc,
                 range_min, range_min_loc, range_max, range_max_loc,
                 cost_per_use, cost_per_use_loc, required_wexp, required_wexp_loc,
                 icon_id, icon_id_loc, use_effect_id, use_effect_id_loc,
                 weapon_effect, weapon_effect_loc, weapon_exp, weapon_exp_loc, loc):
        self.item = item
        self.item_loc = item_loc
        self.name_text_id = name_text_id
        self.name_text_loc = name_text_loc
        self.desc_text_id = desc_text_id
        self.desc_text_loc = desc_text_loc
        self.use_desc_text_id = use_desc_text_id
        self.use_desc_text_loc = use_desc_text_loc
        self.weapon_type = weapon_type
        self.weapon_type_loc = weapon_type_loc
        self.attributes = attributes
        self.attributes_loc = attributes_loc
        self.stat_bonuses = stat_bonuses
        self.stat_bonuses_loc = stat_bonuses_loc
        self.effectiveness = effectiveness
        self.effectiveness_loc = effectiveness_loc
        self.max_uses = max_uses
        self.max_uses_loc = max_uses_loc
        self.might = might
        self.might_loc = might_loc
        self.hit = hit
        self.hit_loc = hit_loc
        self.weight = weight
        self.weight_loc = weight_loc
        self.crit = crit
        self.crit_loc = crit_loc
        self.range_min = range_min
        self.range_min_loc = range_min_loc
        self.range_max = range_max
        self.range_max_loc = range_max_loc
        self.cost_per_use = cost_per_use
        self.cost_per_use_loc = cost_per_use_loc
        self.required_wexp = required_wexp
        self.required_wexp_loc = required_wexp_loc
        self.icon_id = icon_id
        self.icon_id_loc = icon_id_loc
        self.use_effect_id = use_effect_id
        self.use_effect_id_loc = use_effect_id_loc
        self.weapon_effect = weapon_effect
        self.weapon_effect_loc = weapon_effect_loc
        self.weapon_exp = weapon_exp
        self.weapon_exp_loc = weapon_exp_loc
        self.loc = loc

    @property
    def encoded_range(self):
        """``.encodedRange``: high nibble = min range, low nibble = max
        range (see ``GetItemMinRange``/``GetItemMaxRange`` in
        ``src/bmitem.c``)."""
        return ((self.range_min & 0xF) << 4) | (self.range_max & 0xF)

    def as_tuple(self, weapon_types, attribute_flags, wexp_thresholds, weapon_effects):
        """A fully-resolved, symbol-blind tuple for exact round-trip
        comparison against the hand-parsed record (see ``parser.py``).
        Every enum/bitmask-valued field (``weaponType`` included) is
        resolved to its live integer value so authoring order and which
        of two equal-valued symbolic constants either side happens to use
        never cause a false mismatch -- only the actual encoded bytes
        matter."""
        weapon_type_value = weapon_types.get(self.weapon_type, (None, None))[0]
        attributes_value, _ = resolve_bitmask_flags(self.attributes, attribute_flags, self.loc, "")
        required_wexp_value = wexp_thresholds.get(self.required_wexp, (None, None))[0]
        weapon_effect_value = weapon_effects.get(self.weapon_effect, (None, None))[0]
        return (
            self.name_text_id, self.desc_text_id, self.use_desc_text_id,
            weapon_type_value, attributes_value, self.stat_bonuses, self.effectiveness,
            self.max_uses, self.might, self.hit, self.weight, self.crit,
            self.encoded_range, self.cost_per_use, required_wexp_value,
            self.icon_id, self.use_effect_id, weapon_effect_value, self.weapon_exp,
        )


class ItemRecordList(list):
    """A plain list of :class:`ItemRecord` that also remembers the
    ``items`` JSON array's own source location, for diagnostics (e.g.
    missing coverage) that describe the document as a whole rather than
    any single record."""

    def __init__(self, records, loc):
        super().__init__(records)
        self.loc = loc


def _load_records_file(source_path):
    root = load_json_file(source_path)
    schema_node = root.require("$schema")
    if schema_node.as_str() != SCHEMA_ID:
        raise GeneratedDataError(
            "unexpected $schema '{}', expected '{}'".format(schema_node.as_str(), SCHEMA_ID),
            schema_node.loc,
        )
    items_node = root.require("items")
    records = []
    for item_node in items_node.as_list():
        item_name_node = item_node.require("item")
        weapon_type_node = item_node.require("weaponType")

        name_text_id, name_text_loc = _optional_text_id(item_node.get("nameTextId"))
        desc_text_id, desc_text_loc = _optional_text_id(item_node.get("descTextId"))
        use_desc_text_id, use_desc_text_loc = _optional_text_id(item_node.get("useDescTextId"))

        attributes_node = item_node.get("attributes")
        attributes = [n.as_str() for n in attributes_node.as_list()] if attributes_node is not None else []
        attributes_loc = attributes_node.loc if attributes_node is not None else item_node.loc

        stat_bonuses, stat_bonuses_loc = _nullable_str(item_node.get("statBonuses"))
        effectiveness, effectiveness_loc = _nullable_str(item_node.get("effectiveness"))

        max_uses, max_uses_loc = _optional_int(item_node.get("maxUses"))
        might, might_loc = _optional_int(item_node.get("might"))
        hit, hit_loc = _optional_int(item_node.get("hit"))
        weight, weight_loc = _optional_int(item_node.get("weight"))
        crit, crit_loc = _optional_int(item_node.get("crit"))

        range_node = item_node.get("range")
        if range_node is not None:
            min_node = range_node.require("min")
            max_node = range_node.require("max")
            range_min, range_min_loc = min_node.as_int(), min_node.loc
            range_max, range_max_loc = max_node.as_int(), max_node.loc
        else:
            range_min, range_min_loc = 0, item_node.loc
            range_max, range_max_loc = 0, item_node.loc

        cost_per_use, cost_per_use_loc = _optional_int(item_node.get("costPerUse"))
        required_wexp, required_wexp_loc = _optional_str(item_node.get("requiredWexp"), WPN_EXP_DEFAULT)
        icon_id, icon_id_loc = _optional_int(item_node.get("iconId"))
        use_effect_id, use_effect_id_loc = _optional_int(item_node.get("useEffect"))
        weapon_effect, weapon_effect_loc = _optional_str(item_node.get("weaponEffect"), WPN_EFFECT_DEFAULT)
        weapon_exp, weapon_exp_loc = _optional_int(item_node.get("weaponExp"))

        records.append(
            ItemRecord(
                item=item_name_node.as_str(), item_loc=item_name_node.loc,
                name_text_id=name_text_id, name_text_loc=name_text_loc,
                desc_text_id=desc_text_id, desc_text_loc=desc_text_loc,
                use_desc_text_id=use_desc_text_id, use_desc_text_loc=use_desc_text_loc,
                weapon_type=weapon_type_node.as_str(), weapon_type_loc=weapon_type_node.loc,
                attributes=attributes, attributes_loc=attributes_loc,
                stat_bonuses=stat_bonuses, stat_bonuses_loc=stat_bonuses_loc,
                effectiveness=effectiveness, effectiveness_loc=effectiveness_loc,
                max_uses=max_uses, max_uses_loc=max_uses_loc,
                might=might, might_loc=might_loc,
                hit=hit, hit_loc=hit_loc,
                weight=weight, weight_loc=weight_loc,
                crit=crit, crit_loc=crit_loc,
                range_min=range_min, range_min_loc=range_min_loc,
                range_max=range_max, range_max_loc=range_max_loc,
                cost_per_use=cost_per_use, cost_per_use_loc=cost_per_use_loc,
                required_wexp=required_wexp, required_wexp_loc=required_wexp_loc,
                icon_id=icon_id, icon_id_loc=icon_id_loc,
                use_effect_id=use_effect_id, use_effect_id_loc=use_effect_id_loc,
                weapon_effect=weapon_effect, weapon_effect_loc=weapon_effect_loc,
                weapon_exp=weapon_exp, weapon_exp_loc=weapon_exp_loc,
                loc=item_node.loc,
            )
        )
    return ItemRecordList(records, items_node.loc)


def load_records(source_path, item_cap=None, overlay_source=None):
    """Load ItemData records, merging the opt-in expansion overlay only
    when the resolved item ID cap has been raised to include those IDs.
    Default (cap 0xCD) is byte-identical to the vanilla single-file load."""
    records = _load_records_file(source_path)
    cap = item_cap if item_cap is not None else idspace.resolve_item_id_cap()
    if cap >= idspace.ITEM_EXPANSION_FIRST:
        overlay_source = overlay_source or ITEMS_EXPANSION_SOURCE
        if os.path.exists(overlay_source):
            overlay = _load_records_file(overlay_source)
            return ItemRecordList(list(records) + list(overlay), records.loc)
    return records


def validate(records, diagnostics, items_header=ITEMS_HEADER, bmitem_header=BMITEM_HEADER,
             variables_header=VARIABLES_HEADER, msg_header=MSG_HEADER,
             icon_source=ITEM_ICON_SOURCE, msg_count=None, icon_count=None,
             item_cap=None, expansion_header=None):
    """Run all ``ItemData`` validations, appending errors to ``diagnostics``.

    Checks: unique + full contiguous ``ITEM_*`` coverage (0..max enum
    value, no gaps/strays), ``weaponType``/``requiredWexp``/
    ``weaponEffect`` enum references, ``attributes`` as a validated
    ``IA_*`` bitmask list, nullable ``statBonuses``/``effectiveness`` C
    symbol references, all numeric widths/ranges (including the
    ``range.min``/``range.max`` nibble bounds), text IDs against the live
    ``MSG_COUNT``, and ``iconId`` against the live item-icon-graphics
    count.
    """
    if msg_count is None:
        msg_count = read_msg_count(msg_header)
    if icon_count is None:
        icon_count = read_item_icon_count(icon_source)

    items_enum = extract_enum_constants(items_header, name_prefix="ITEM_")
    cap = item_cap if item_cap is not None else idspace.resolve_item_id_cap()
    # Always make expansion IDs *known* so an un-opted expansion record is
    # rejected with the actionable cap diagnostic (raise FE8_ITEM_ID_CAP)
    # rather than a generic undefined-reference error.
    if expansion_header and os.path.exists(expansion_header):
        items_enum = dict(items_enum)
        items_enum.update(extract_enum_constants(expansion_header, name_prefix="ITEM_"))
    weapon_types = extract_enum_constants(bmitem_header, name_prefix="ITYPE_")
    wexp_thresholds = extract_enum_constants(bmitem_header, name_prefix="WPN_EXP_")
    weapon_effects = extract_enum_constants(bmitem_header, name_prefix="WPN_EFFECT_")
    attribute_flags = read_item_attributes(bmitem_header)
    stat_bonuses_field = CSymbolRefField(bmitem_header, description="item stat-bonuses table")
    effectiveness_field = CSymbolRefField(variables_header, description="item effectiveness table")

    diagnostics.extend(
        validate_unique(
            ((r.item, r.item_loc) for r in records),
            "duplicate item entry '{key}' (first defined at {first_loc})",
            "items[item={key}]",
        )
    )

    covered_values = {}
    for record in records:
        ref = "items[item={}]".format(record.item)

        diagnostics.extend(validate_reference(record.item, items_enum, record.item_loc, ref, kind="item"))
        if record.item in items_enum:
            covered_values[items_enum[record.item][0]] = record.item

        diagnostics.extend(
            validate_reference(record.weapon_type, weapon_types, record.weapon_type_loc,
                                "{}.weaponType".format(ref), kind="weapon type")
        )

        _, attribute_errors = resolve_bitmask_flags(
            record.attributes, attribute_flags, record.attributes_loc,
            "{}.attributes".format(ref), kind="item attribute",
        )
        diagnostics.extend(attribute_errors)

        for field_name, value, loc in (
            ("nameTextId", record.name_text_id, record.name_text_loc),
            ("descTextId", record.desc_text_id, record.desc_text_loc),
            ("useDescTextId", record.use_desc_text_id, record.use_desc_text_loc),
        ):
            diagnostics.extend(
                validate_range(value, 0, msg_count - 1, loc or record.loc,
                                "{}.{}".format(ref, field_name), field_name=field_name)
            )

        for field_name, value, loc in (
            ("maxUses", record.max_uses, record.max_uses_loc),
            ("might", record.might, record.might_loc),
            ("hit", record.hit, record.hit_loc),
            ("weight", record.weight, record.weight_loc),
            ("crit", record.crit, record.crit_loc),
            ("useEffect", record.use_effect_id, record.use_effect_id_loc),
            ("weaponExp", record.weapon_exp, record.weapon_exp_loc),
        ):
            diagnostics.extend(
                validate_range(value, _U8_MIN, _U8_MAX, loc or record.loc,
                                "{}.{}".format(ref, field_name), field_name=field_name)
            )

        diagnostics.extend(
            validate_range(record.range_min, _NIBBLE_MIN, _NIBBLE_MAX, record.range_min_loc or record.loc,
                            "{}.range.min".format(ref), field_name="range.min")
        )
        diagnostics.extend(
            validate_range(record.range_max, _NIBBLE_MIN, _NIBBLE_MAX, record.range_max_loc or record.loc,
                            "{}.range.max".format(ref), field_name="range.max")
        )
        diagnostics.extend(
            validate_range(record.cost_per_use, _U16_MIN, _U16_MAX, record.cost_per_use_loc or record.loc,
                            "{}.costPerUse".format(ref), field_name="costPerUse")
        )
        diagnostics.extend(
            validate_reference(record.required_wexp, wexp_thresholds, record.required_wexp_loc or record.loc,
                                "{}.requiredWexp".format(ref), kind="weapon-exp threshold")
        )
        diagnostics.extend(
            validate_reference(record.weapon_effect, weapon_effects, record.weapon_effect_loc or record.loc,
                                "{}.weaponEffect".format(ref), kind="weapon effect")
        )
        diagnostics.extend(
            validate_range(record.icon_id, 0, icon_count - 1, record.icon_id_loc or record.loc,
                            "{}.iconId".format(ref), field_name="iconId")
        )

        if record.stat_bonuses is not None:
            diagnostics.extend(
                stat_bonuses_field.validate(record.stat_bonuses, record.stat_bonuses_loc,
                                             "{}.statBonuses".format(ref))
            )
        if record.effectiveness is not None:
            diagnostics.extend(
                effectiveness_field.validate(record.effectiveness, record.effectiveness_loc,
                                              "{}.effectiveness".format(ref))
            )

    if items_enum:
        enum_max = max(value for value, _ in items_enum.values())
        required_max = min(cap, enum_max)
        for _rec in records:
            _v = items_enum.get(_rec.item, (None, None))[0]
            if _v is not None and _v > cap:
                diagnostics.add(GeneratedDataError(
                    "item {} (index {}) is beyond the configured item cap "
                    "0x{:X}; raise FE8_ITEM_ID_CAP to opt this ID in".format(
                        _rec.item, _v, cap),
                    _rec.item_loc, "items"))
        missing = sorted(set(range(0, required_max + 1)) - set(covered_values))
        if missing:
            value_to_name = {value: name for name, (value, _) in items_enum.items()}
            doc_loc = getattr(records, "loc", None)
            for value in missing:
                name = value_to_name.get(value, "0x{:02X}".format(value))
                diagnostics.add(
                    GeneratedDataError(
                        "missing item coverage for '{}' (index {}): no authored record".format(name, value),
                        doc_loc,
                        "items",
                    )
                )


class ItemsTableSchema(TableSchema):
    name = SCHEMA_NAME
    version = SCHEMA_VERSION

    default_source = "src/data/items.json"
    default_hand_source = "src/data_items.c"
    default_output_name = "data_items.c"
    default_inventory_path = "reports/generated_data_items_inventory.md"

    def dependencies(self):
        return (
            "constants.items.ITEM", "bmitem.ITYPE", "bmitem.WPN_EXP", "bmitem.WPN_EFFECT",
            "bmitem.IA", "bmitem.ItemBonus", "variables.ItemEffectiveness",
            "constants.msg.MSG_COUNT", "data.data_item_icon",
        )

    def load_records(self, source_path):
        return load_records(source_path, overlay_source=ITEMS_EXPANSION_SOURCE)

    def validate(self, records, diagnostics):
        validate(records, diagnostics, expansion_header=ITEMS_EXPANSION_HEADER)

    def generate_c(self, records, source_path):
        from . import generate as items_generate
        return items_generate.generate_c_source(records, source_path)

    def build_inventory(self, records):
        from . import inventory as items_inventory
        return items_inventory.build_inventory(records)

    def manifest_record_count(self, records):
        # Archival/default manifest count: exclude opt-in ITEM_EXPANSION_*
        # overlay records so the committed manifest stays byte-identical
        # between the default (0xCD) and opt-in (>=0xCE) builds. Expansion
        # records are audited in reports/id_space_audit.md and generated into
        # the ROM table under build/.
        items_enum = extract_enum_constants(ITEMS_HEADER, name_prefix="ITEM_")
        return sum(1 for r in records if r.item in items_enum)

    def round_trip_errors(self, records, hand_source):
        if not hand_source or not os.path.exists(hand_source):
            return []
        from . import parser as items_roundtrip
        # Opt-in expansion IDs (ITEM_EXPANSION_*, authored in the overlay
        # src/data/items_expansion.json) never appear in the vanilla hand
        # table src/data_items.c; they are validated separately (schema cap
        # check + generated-source compile). The vanilla hand table must
        # still round-trip 100%, so compare only the hand-backed records
        # here. This is a scoped exclusion, never a global --no-roundtrip:
        # every record that exists in the hand source is still compared
        # field-for-field.
        expansion_names = set()
        if os.path.exists(ITEMS_EXPANSION_HEADER):
            expansion_names = set(
                extract_enum_constants(ITEMS_EXPANSION_HEADER, name_prefix="ITEM_"))
        hand_backed = [r for r in records if r.item not in expansion_names]
        item_names = [r.item for r in hand_backed]
        hand_records = items_roundtrip.parse_hand_written(hand_source, item_names)
        return items_roundtrip.compare_records(
            hand_backed, hand_records, hand_path=hand_source)


def dependency_graph():
    graph = DependencyGraph()
    for dep in ItemsTableSchema().dependencies():
        graph.add_dependency(SCHEMA_NAME, dep)
    return graph
