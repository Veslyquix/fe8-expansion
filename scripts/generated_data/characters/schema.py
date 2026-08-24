"""``CharacterData`` schema: Issue #5 Batch 2b full 256-record authoring,
C89 generation, and hand-source round trip for ``gCharacterData[]`` (see
``include/bmunit.h``, ``struct CharacterData``).

Batch 2a (schema/dependency-validation foundation only) provided the
record model, loader, and validator so a JSON source can be checked with
``python3 -m scripts.generated_data validate --table characters --source
<path>``. Batch 2b extends that foundation with ``generate.py``
(C89 emission), ``parser.py`` (semantic round trip against the
hand-written ``src/data_characters.c``), ``inventory.py`` (committed
summary report), a real, complete ``fullCoverage: true`` source at
``src/data/characters.json``, and registration in ``generated_data.mk``'s
``GENERATED_DATA_TABLES``/CI drift loop -- see ``docs/generated_data.md``
for full status.

Unlike every other global table (``items``, 206 contiguous ``ITEM_*``
records; ``classes``, 127 contiguous ``CLASS_*`` records excluding the
sentinel/alias), ``gCharacterData[]`` has a unique **256-slot** model
confirmed field-for-field against ``src/data_characters.c``:

* 1-based **designator** values ``1..256`` select the array slot
  ``[designator - 1]`` (mirroring the hand file's own ``[CHARACTER_X - 1]``
  / ``[0x1B - 1]`` indexing) -- so the full dense domain this schema
  validates coverage against is designators ``1..256`` (256 slots total),
  *not* zero-based array indices ``0..255``.
* A **symbolic** record (JSON key ``"character"``) designates its slot
  with a named ``CHARACTER_*`` constant (excluding ``CHARACTER_NONE`` == 0,
  which can never be a table entry -- its implied index would be ``-1``).
  ~96 of the 256 designators have a named constant in
  ``include/constants/characters.h``.
  those are what the issue calls the "94 symbolic ... records" (Batch 2a
  validates this dynamically against the live header rather than
  hardcoding a count, so the exact number is intentionally not pinned
  here).
* A **raw/generic-template** record (JSON key ``"characterId"``) uses a
  bare integer designator instead, for the ~160 slots that have no named
  constant (unnamed enemy/filler templates the hand file indexes with a
  raw hex literal, e.g. ``[0x1B - 1]``).
* Designator ``256`` (``0x100``) is the single **unreachable padding
  slot**: confirmed against the hand file's last entry
  (``[0x100 - 1] = { ..., .number = 0, ... }``) -- no real ``u8`` character
  byte can ever equal ``256``, so this slot can never be reached by
  ``GetCharacterData()`` at runtime. It is still a real, authored array
  entry (the array has exactly 256 elements), so it is included in the
  dense coverage domain like every other slot; only ``characterId`` (not
  ``character``) can designate it, since no ``CHARACTER_*`` constant is
  (or could be) ``256``.

``.number`` is never authored (derived only): it is always the record's
own designator value, truncated to ``u8`` (``designator & 0xFF``) -- for
designators ``1..255`` that's just the designator itself (matching every
non-padding vanilla record's ``.number = CHARACTER_X`` /
``.number = 0x1B``); for the padding slot (designator ``256``) the u8
truncation naturally yields ``0``, matching the hand file's explicit
``.number = 0`` for that one entry exactly (so authoring it explicitly
there was always equivalent to deriving it -- there is no special case in
this schema's derivation rule).

JSON source shape (``fe8.characters.v1``)::

    {
      "$schema": "fe8.characters.v1",
      "fullCoverage": false,
      "characters": [
        {
          "character": "CHARACTER_EIRIKA",
          "nameTextId": 530,
          "descTextId": 622,
          "defaultClass": "CLASS_EIRIKA_LORD",
          "portrait": 2,
          "affinity": "UNIT_AFFIN_LIGHT",
          "sortOrder": 1,
          "visitGroup": 7,
          "baseLevel": 1,
          "base": { "lck": 5 },
          "baseRanks": { "ITYPE_SWORD": "WPN_EXP_E" },
          "growth": { "hp": 70, "pow": 40, "skl": 60, "spd": 60, "def": 30, "res": 30, "lck": 60 },
          "attributes": ["CA_FEMALE"],
          "supportData": "SupportData_Eirika"
        },
        {
          "characterId": 256,
          "defaultClass": "CLASS_BRIGAND",
          "nameTextId": 37,
          "descTextId": 37,
          "miniPortrait": 2,
          "baseLevel": 1,
          "baseRanks": { "ITYPE_SWORD": "WPN_EXP_D" },
          "growth": { "hp": 60, "pow": 20, "skl": 30, "spd": 35, "def": 15, "res": 15, "lck": 25 }
        }
      ]
    }

``fullCoverage`` (top-level, optional, default ``false``) toggles the
dense ``1..256`` coverage check (see :func:`validate`). Batch 2b commits
the real, complete ``src/data/characters.json`` with ``fullCoverage:
true`` (all 256 designators authored); unit-test fixtures still mostly
leave it ``false`` so partial fixtures can be validated purely for
uniqueness/reference/range correctness without also having to satisfy
full coverage.

Optional ``CharacterData`` fields default exactly like the hand-written
designated initializers that only set the fields they need (mirroring
``classes/schema.py``'s own optional-field defaulting):

* ``nameTextId``/``descTextId`` -> ``0``
* ``portrait`` -> ``0`` (``.portraitId``)
* ``miniPortrait`` -> ``0`` (``0`` means "no mini portrait" -- see
  ``read_mini_portrait_capacity``)
* ``affinity`` -> absent means ``0``/none (``UNIT_AFFIN_*`` has no
  explicit zero-valued member -- ``0`` is the implicit "no affinity"
  sentinel, exactly like 93/256 vanilla records that omit ``.affinity``)
* ``sortOrder`` -> ``0`` (``.sort_order`` -- omitted on the ~210/256
  vanilla records that don't set it explicitly)
* ``visitGroup`` -> ``0``
* ``baseLevel`` -> ``0``
* ``base``/``growth`` sub-objects -> all-zero when the whole object is
  omitted, or per-field ``0`` when the object is present but a particular
  stat key is omitted
* ``baseRanks`` -> ``{}`` (``WPN_EXP_0`` for every weapon type)
* ``attributes`` -> ``[]`` (``CA_NONE``)
* ``supportData`` -> absent/``null`` (``NULL`` -- most records, and *all*
  raw/generic-template records, have no ``SupportData`` -- see
  :func:`validate`)

The struct's ``_u23``/``_u24``/``_u25``/``_u27`` reserved bytes (fixed
zero in every vanilla record -- ``_u25`` is even documented in
``include/bmunit.h`` as "Unique animation IDs in FE7", i.e. dead weight
carried over from the previous game, never read anywhere in this
codebase) are **not modeled as authorable fields at all**: this schema
rejects any record JSON that includes one of those four keys outright
(see :func:`validate`), rather than silently accepting and ignoring them.
"""

from __future__ import annotations

import os
import re

from ..cparse import strip_hand_conditionals
from ..diagnostics import GeneratedDataError
from ..json_loader import load_json_file
from ..schema import DependencyGraph, TableSchema
from .. import character_refs
from ..validators import (
    extract_define_constant,
    extract_enum_constants,
    resolve_bitmask_flags,
    validate_range,
    validate_reference,
    validate_unique,
)

SCHEMA_NAME = "characters"
SCHEMA_VERSION = 1
SCHEMA_ID = "fe8.characters.v1"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CHARACTERS_HEADER = character_refs.CHARACTERS_HEADER
CLASSES_HEADER = os.path.join(REPO_ROOT, "include", "constants", "classes.h")
BMUNIT_HEADER = os.path.join(REPO_ROOT, "include", "bmunit.h")
BMITEM_HEADER = os.path.join(REPO_ROOT, "include", "bmitem.h")
MSG_HEADER = os.path.join(REPO_ROOT, "include", "constants", "msg.h")
PORTRAIT_DATA_SOURCE = os.path.join(REPO_ROOT, "src", "portrait_data.c")
FACE_SOURCE = os.path.join(REPO_ROOT, "src", "face.c")

_S8_MIN, _S8_MAX = -128, 127
_U8_MIN, _U8_MAX = 0, 255

# The full dense designator domain: 1-based slots 1..256 (array indices
# 0..255), independent of how many named CHARACTER_* constants exist --
# see the module docstring. Not derived from the live header, unlike
# items'/classes' coverage bounds, because raw/generic-template records
# fill every designator no symbol names.
DESIGNATOR_MIN = 1
DESIGNATOR_MAX = 256

_RESERVED_FIELDS = ("_u23", "_u24", "_u25", "_u27")

_CHARACTER_ATTRIBUTES_BLOCK_RE = re.compile(r"//\s*Character/Class attributes(.*?)//\s*Helpers", re.S)
_ATTRIBUTE_ENTRY_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:\(\s*1\s*<<\s*(\d+)\s*\)|(-?\d+))\s*,"
)
_STRUCT_BODY_RE_CACHE = {}
_NUMBERED_ARRAY_ENTRY_RE = re.compile(r"^\s*\{[^{}]*\},?\s*//\s*\d+\s*$", re.MULTILINE)
_GENERIC_CHIBI_LUT_RE = re.compile(r"sGenericChibiImgLut\[\]\s*=\s*\{(.*?)\}\s*;", re.S)
_UNIT_AFFIN_ENUM_RE = re.compile(r"enum\s+unit_affinity_index\s*\{(.*?)\}", re.S)

_BASE_STATS = ("hp", "pow", "skl", "spd", "def", "res", "lck", "con")
_GROWTH_STATS = ("hp", "pow", "skl", "spd", "def", "res", "lck")


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


def read_character_data_array_capacity(field_name, header=BMUNIT_HEADER):
    """Read a ``struct CharacterData`` fixed-array field's declared
    capacity (e.g. ``baseRanks[8]`` -> 8) live from ``include/bmunit.h``,
    instead of hardcoding the numeral (mirrors
    ``classes.read_class_data_array_capacity``)."""
    body = _read_struct_body(header, "CharacterData")
    match = re.search(r"\b{}\s*\[\s*(\d+)\s*\]".format(re.escape(field_name)), body)
    if not match:
        raise GeneratedDataError(
            "could not find 'CharacterData::{}[N]' in {}".format(field_name, header)
        )
    return int(match.group(1))


def read_character_attributes(header=BMUNIT_HEADER):
    """Read the individual ``CA_*`` bit-flag constants (shared with
    ``ClassData.attributes`` -- see ``UNIT_CATTRIBUTES()`` in
    ``include/bmunit.h``, which ORs both tables' ``attributes`` fields
    together at runtime) live from ``include/bmunit.h``. Duplicates
    ``classes.read_class_attributes`` deliberately: each table package
    owns its own live-source readers rather than importing across
    sibling table packages (see other tables' schema.py modules)."""
    with open(header, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = _CHARACTER_ATTRIBUTES_BLOCK_RE.search(text)
    if not match:
        raise GeneratedDataError("could not find the CA_* attributes enum in {}".format(header))
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
    ``items``/``classes`` schemas, which read the same constant)."""
    value, _ = extract_define_constant(header, "MSG_COUNT")
    return value


def _count_numbered_array_entries(source):
    with open(source, "r", encoding="utf-8") as handle:
        text = handle.read()
    text = strip_hand_conditionals(text)
    return len(_NUMBERED_ARRAY_ENTRY_RE.findall(text))


def read_portrait_count(source=PORTRAIT_DATA_SOURCE):
    """Derive the number of playable portrait slots from the live,
    numbered ``portrait_data[]`` array in ``src/portrait_data.c`` (mirrors
    ``classes.read_portrait_count``, which validates ``defaultPortraitId``
    against the same live table)."""
    return _count_numbered_array_entries(source)


def read_mini_portrait_capacity(source=FACE_SOURCE):
    """Derive ``miniPortrait``'s strongest provable bound from the live
    ``sGenericChibiImgLut[]`` array literal inside ``GetGenericChibiImg``
    (``src/face.c``).

    ``GetUnitMiniPortraitId()`` (``src/bmunit.c``) returns
    ``FID_FACTION_CHIBI + miniPortrait`` (``FID_FACTION_CHIBI == 0x7F00``,
    ``include/constants/faces.h``) whenever ``miniPortrait`` is nonzero;
    ``GetGenericChibiImg()`` then computes ``fid - FID_FACTION_CHIBI``
    (i.e. exactly ``miniPortrait`` again) and indexes
    ``sGenericChibiImgLut[]`` with it directly -- so this array's own
    entry count is a real, live, provably-safe upper bound for
    ``miniPortrait``, one entry stronger than the raw ``u8`` width
    (0..255): every vanilla record only ever sets ``miniPortrait`` to
    ``0`` (omitted -- "no mini portrait", a distinct code path that never
    reaches this array) or ``1..7`` (confirmed field-for-field against
    ``src/data_characters.c``), both within ``0..capacity-1``.
    """
    with open(source, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = _GENERIC_CHIBI_LUT_RE.search(text)
    if not match:
        raise GeneratedDataError("could not find 'sGenericChibiImgLut[]' in {}".format(source))
    entries = [e.strip() for e in match.group(1).split(",") if e.strip()]
    return len(entries)


def read_unit_affinities(header=BMUNIT_HEADER):
    """Read the ``UNIT_AFFIN_*`` member names from ``enum
    unit_affinity_index`` live from ``include/bmunit.h``.

    Unlike :func:`~..validators.extract_enum_constants` (which only reads
    lines with an explicit ``NAME = value,``), this enum only assigns its
    *first* member explicitly (``UNIT_AFFIN_FIRE = 1``) and lets every
    other member auto-increment implicitly -- so this reader walks the
    enum body itself, tracking the running value the same way the C
    compiler would. ``0`` (no explicit member) is the implicit "no
    affinity" sentinel -- see the module docstring -- so it is
    deliberately not included in the returned mapping.
    """
    with open(header, "r", encoding="utf-8") as handle:
        text = handle.read()
    match = _UNIT_AFFIN_ENUM_RE.search(text)
    if not match:
        raise GeneratedDataError("could not find 'enum unit_affinity_index' in {}".format(header))
    values = {}
    next_value = 0
    for entry in match.group(1).split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" in entry:
            name, raw_value = (part.strip() for part in entry.split("=", 1))
            next_value = int(raw_value, 0)
        else:
            name = entry
        values[name] = next_value
        next_value += 1
    return values


def _optional_int(node, default=0):
    if node is None:
        return default, None
    return node.as_int(), node.loc


def _optional_str(node, default=None):
    if node is None:
        return default, None
    return node.as_str(), node.loc


def _load_stat_group(node, keys, container_loc):
    """Parse an optional ``{ "hp": N, ... }`` stat sub-object -- every key
    defaults to ``0`` (with no location) when the whole group, or an
    individual key, is omitted (mirrors ``classes._load_stat_group``)."""
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


class CharacterRecord:
    """One ``gCharacterData[]`` entry, with per-field source locations.

    Exactly one of ``character``/``character_id`` is non-``None`` (see
    :func:`load_records`, which raises immediately -- a structural
    problem, like every other table's required-key checks -- if a record
    JSON object has both or neither key).
    """

    def __init__(self, character, character_loc, character_id, character_id_loc,
                 name_text_id, name_text_loc, desc_text_id, desc_text_loc,
                 default_class, default_class_loc,
                 portrait, portrait_loc, mini_portrait, mini_portrait_loc,
                 affinity, affinity_loc, sort_order, sort_order_loc,
                 visit_group, visit_group_loc,
                 base_level, base_level_loc,
                 base, base_locs, growth, growth_locs,
                 base_ranks, base_ranks_locs, base_ranks_container_loc,
                 attributes, attributes_loc,
                 support_data, support_data_loc,
                 reserved_fields, loc):
        self.character = character
        self.character_loc = character_loc
        self.character_id = character_id
        self.character_id_loc = character_id_loc
        self.name_text_id = name_text_id
        self.name_text_loc = name_text_loc
        self.desc_text_id = desc_text_id
        self.desc_text_loc = desc_text_loc
        self.default_class = default_class
        self.default_class_loc = default_class_loc
        self.portrait = portrait
        self.portrait_loc = portrait_loc
        self.mini_portrait = mini_portrait
        self.mini_portrait_loc = mini_portrait_loc
        self.affinity = affinity
        self.affinity_loc = affinity_loc
        self.sort_order = sort_order
        self.sort_order_loc = sort_order_loc
        self.visit_group = visit_group
        self.visit_group_loc = visit_group_loc
        self.base_level = base_level
        self.base_level_loc = base_level_loc
        self.base = base
        self.base_locs = base_locs
        self.growth = growth
        self.growth_locs = growth_locs
        self.base_ranks = base_ranks
        self.base_ranks_locs = base_ranks_locs
        self.base_ranks_container_loc = base_ranks_container_loc
        self.attributes = attributes
        self.attributes_loc = attributes_loc
        self.support_data = support_data
        self.support_data_loc = support_data_loc
        self.reserved_fields = reserved_fields
        self.loc = loc

    def is_raw(self):
        """``True`` for a raw/generic-template record (``characterId``
        key); ``False`` for a symbolic (``character`` key) record."""
        return self.character is None

    def key_repr(self):
        if self.character is not None:
            return "character={}".format(self.character)
        return "characterId={}".format(self.character_id)

    def designator(self, characters_enum):
        """Resolve this record's 1-based designator (see the module
        docstring), or ``None`` if it's a symbolic record whose
        ``character`` isn't a defined ``CHARACTER_*`` constant (already
        reported separately by :func:`validate`'s reference check)."""
        if self.character is not None:
            if self.character not in characters_enum:
                return None
            return characters_enum[self.character][0]
        return self.character_id

    def resolved_number(self, characters_enum):
        """The derived (never-authored) ``.number`` field: the
        designator truncated to ``u8`` -- see the module docstring for
        why this naturally yields ``0`` for the designator-256 padding
        slot with no special case needed."""
        designator = self.designator(characters_enum)
        if designator is None:
            return None
        return designator & 0xFF

    def encoded_base_ranks(self, weapon_types, wexp_thresholds, capacity):
        """Resolve ``baseRanks`` to a fixed ``capacity``-length tuple of
        ``WPN_EXP_*`` integer values, indexed by each weapon type's own
        enum value (unset slots default to ``WPN_EXP_0`` = 0). Mirrors
        ``classes.ClassRecord.encoded_base_ranks``."""
        slots = [0] * capacity
        for itype_name, wexp_name in self.base_ranks.items():
            if itype_name not in weapon_types or wexp_name not in wexp_thresholds:
                continue
            index = weapon_types[itype_name][0]
            if 0 <= index < capacity:
                slots[index] = wexp_thresholds[wexp_name][0]
        return tuple(slots)

    def as_tuple(self, classes_enum, attribute_flags, weapon_types, wexp_thresholds,
                 base_ranks_capacity, affinity_values):
        """A fully-resolved, symbol-blind tuple for exact round-trip
        comparison against the hand-parsed record (see ``parser.py``).
        Mirrors ``classes.ClassRecord.as_tuple``: enum/bitmask-valued
        fields are resolved to their live integer value; the derived
        ``.number`` field is intentionally excluded here (the parser
        checks it separately against the record's own designator, since
        it is never authored -- see the module docstring)."""
        default_class_value = classes_enum.get(self.default_class, (0, None))[0]
        affinity_value = affinity_values.get(self.affinity, 0) if self.affinity is not None else 0
        attributes_value, _ = resolve_bitmask_flags(self.attributes, attribute_flags, self.loc, "")
        base_ranks_tuple = self.encoded_base_ranks(weapon_types, wexp_thresholds, base_ranks_capacity)
        return (
            self.name_text_id, self.desc_text_id, default_class_value,
            self.portrait, self.mini_portrait, affinity_value, self.sort_order,
            self.base_level,
            tuple(self.base[k] for k in _BASE_STATS),
            base_ranks_tuple,
            tuple(self.growth[k] for k in _GROWTH_STATS),
            attributes_value,
            self.support_data,
            self.visit_group,
        )


class CharacterRecordList(list):
    """A plain list of :class:`CharacterRecord` that also remembers the
    ``characters`` JSON array's own source location (for document-level
    diagnostics like missing coverage) and the top-level ``fullCoverage``
    flag (see the module docstring)."""

    def __init__(self, records, loc, full_coverage):
        super().__init__(records)
        self.loc = loc
        self.full_coverage = full_coverage


def load_records(source_path):
    """Parse the JSON source into a :class:`CharacterRecordList`.

    Raises :class:`GeneratedDataError` immediately for structural problems
    (wrong top-level shape, missing required fields, both/neither of
    ``character``/``characterId``, wrong types) -- exactly like every
    other table's loader (see ``classes.load_records``/
    ``supports.load_records``). Content-level problems (duplicates, bad
    references, out-of-range values) are left to :func:`validate` so every
    one of them is reported in a single pass.
    """
    root = load_json_file(source_path)
    schema_node = root.require("$schema")
    if schema_node.as_str() != SCHEMA_ID:
        raise GeneratedDataError(
            "unexpected $schema '{}', expected '{}'".format(schema_node.as_str(), SCHEMA_ID),
            schema_node.loc,
        )
    full_coverage_node = root.get("fullCoverage")
    if full_coverage_node is None or full_coverage_node.value is None:
        # Absent or explicit JSON ``null`` both mean "false" -- Batch 2a
        # never commits a real full-coverage source (see the module
        # docstring), so this must not require every fixture to spell out
        # ``"fullCoverage": false`` explicitly.
        full_coverage = False
    else:
        full_coverage = full_coverage_node.value
        if not isinstance(full_coverage, bool):
            raise GeneratedDataError(
                "'fullCoverage' must be a boolean, found {}".format(type(full_coverage).__name__),
                full_coverage_node.loc,
            )

    characters_node = root.require("characters")
    records = []
    for char_node in characters_node.as_list():
        character_node = char_node.get("character")
        character_id_node = char_node.get("characterId")
        if character_node is not None and character_id_node is not None:
            raise GeneratedDataError(
                "record has both 'character' and 'characterId'; exactly one is required",
                char_node.loc,
            )
        if character_node is None and character_id_node is None:
            raise GeneratedDataError(
                "record is missing both 'character' and 'characterId'; exactly one is required",
                char_node.loc,
            )
        character = character_node.as_str() if character_node is not None else None
        character_loc = character_node.loc if character_node is not None else None
        character_id = character_id_node.as_int() if character_id_node is not None else None
        character_id_loc = character_id_node.loc if character_id_node is not None else None

        default_class_node = char_node.require("defaultClass")

        name_text_id, name_text_loc = _optional_int(char_node.get("nameTextId"))
        desc_text_id, desc_text_loc = _optional_int(char_node.get("descTextId"))
        portrait, portrait_loc = _optional_int(char_node.get("portrait"))
        mini_portrait, mini_portrait_loc = _optional_int(char_node.get("miniPortrait"))
        affinity, affinity_loc = _optional_str(char_node.get("affinity"), None)
        sort_order, sort_order_loc = _optional_int(char_node.get("sortOrder"))
        visit_group, visit_group_loc = _optional_int(char_node.get("visitGroup"))
        base_level, base_level_loc = _optional_int(char_node.get("baseLevel"))

        base_node = char_node.get("base")
        base, base_locs = _load_stat_group(base_node, _BASE_STATS, char_node.loc)
        growth_node = char_node.get("growth")
        growth, growth_locs = _load_stat_group(growth_node, _GROWTH_STATS, char_node.loc)

        base_ranks_node = char_node.get("baseRanks")
        base_ranks = {}
        base_ranks_locs = {}
        base_ranks_container_loc = base_ranks_node.loc if base_ranks_node is not None else char_node.loc
        if base_ranks_node is not None:
            for itype_key in base_ranks_node.keys():
                value_node = base_ranks_node.require(itype_key)
                base_ranks[itype_key] = value_node.as_str()
                base_ranks_locs[itype_key] = value_node.loc

        attributes_node = char_node.get("attributes")
        attributes = [n.as_str() for n in attributes_node.as_list()] if attributes_node is not None else []
        attributes_loc = attributes_node.loc if attributes_node is not None else char_node.loc

        support_data, support_data_loc = _optional_str(char_node.get("supportData"), None)

        reserved_fields = [
            (name, char_node.key_locations.get(name))
            for name in _RESERVED_FIELDS
            if name in char_node.value
        ]

        records.append(
            CharacterRecord(
                character=character, character_loc=character_loc,
                character_id=character_id, character_id_loc=character_id_loc,
                name_text_id=name_text_id, name_text_loc=name_text_loc,
                desc_text_id=desc_text_id, desc_text_loc=desc_text_loc,
                default_class=default_class_node.as_str(), default_class_loc=default_class_node.loc,
                portrait=portrait, portrait_loc=portrait_loc,
                mini_portrait=mini_portrait, mini_portrait_loc=mini_portrait_loc,
                affinity=affinity, affinity_loc=affinity_loc,
                sort_order=sort_order, sort_order_loc=sort_order_loc,
                visit_group=visit_group, visit_group_loc=visit_group_loc,
                base_level=base_level, base_level_loc=base_level_loc,
                base=base, base_locs=base_locs,
                growth=growth, growth_locs=growth_locs,
                base_ranks=base_ranks, base_ranks_locs=base_ranks_locs,
                base_ranks_container_loc=base_ranks_container_loc,
                attributes=attributes, attributes_loc=attributes_loc,
                support_data=support_data, support_data_loc=support_data_loc,
                reserved_fields=reserved_fields,
                loc=char_node.loc,
            )
        )
    return CharacterRecordList(records, characters_node.loc, full_coverage)


def validate(records, diagnostics, dependency_records=None,
             characters_header=CHARACTERS_HEADER, classes_header=CLASSES_HEADER,
             bmunit_header=BMUNIT_HEADER, bmitem_header=BMITEM_HEADER, msg_header=MSG_HEADER,
             portrait_source=PORTRAIT_DATA_SOURCE, face_source=FACE_SOURCE,
             msg_count=None, portrait_count=None, mini_portrait_capacity=None,
             base_ranks_capacity=None, designator_min=DESIGNATOR_MIN, designator_max=DESIGNATOR_MAX):
    """Run all ``CharacterData`` validations, appending errors to
    ``diagnostics``.

    Checks: exactly-one-key already enforced structurally by
    :func:`load_records`; unique normalized designators (symbolic and raw
    records share one collision domain); ``CHARACTER_NONE``/out-of-range
    designator rejection; full dense ``1..256`` coverage when
    ``records.full_coverage`` is set; ``defaultClass`` both as a valid
    ``CLASS_*`` reference *and* (when the ``classes`` dependency table is
    loaded) present in it; ``supportData`` as a validated cross-reference
    into the loaded ``supports`` dependency table (owner reciprocity) --
    rejected outright on raw/generic-template records; numeric
    ranges/bounds (text IDs against ``MSG_COUNT``, ``portrait`` against
    the live portrait table, ``miniPortrait`` against the live
    ``sGenericChibiImgLut`` bound, signed base stats, unsigned growths);
    ``baseRanks`` as validated ``ITYPE_*`` (bounded to the array's own
    capacity) -> ``WPN_EXP_*`` entries; ``attributes`` as a validated
    ``CA_*`` bitmask list; ``affinity`` as an optional ``UNIT_AFFIN_*``
    reference; and outright rejection of the reserved, non-authorable
    ``_u23``/``_u24``/``_u25``/``_u27`` struct fields.

    ``dependency_records``, when given, is the ``{"classes": [...],
    "supports": [...]}`` dict the CLI's ``dependency_tables()`` machinery
    loads (see ``cli.py``); either or both keys may be absent (module-level
    direct tests may call this with ``dependency_records=None`` entirely
    to exercise header-only checks in isolation), in which case the
    corresponding cross-table check is skipped (the header-level reference
    check still runs regardless).
    """
    if msg_count is None:
        msg_count = read_msg_count(msg_header)
    if portrait_count is None:
        portrait_count = read_portrait_count(portrait_source)
    if mini_portrait_capacity is None:
        mini_portrait_capacity = read_mini_portrait_capacity(face_source)
    if base_ranks_capacity is None:
        base_ranks_capacity = read_character_data_array_capacity("baseRanks", bmunit_header)

    dependency_records = dependency_records or {}
    classes_records = dependency_records.get("classes")
    known_class_names = {r.class_name for r in classes_records} if classes_records is not None else None
    supports_records = dependency_records.get("supports")
    supports_by_symbol = {r.symbol: r for r in supports_records} if supports_records is not None else None

    characters_enum = character_refs.read_character_designators(characters_header)
    classes_enum = extract_enum_constants(classes_header, name_prefix="CLASS_")
    weapon_types = extract_enum_constants(bmitem_header, name_prefix="ITYPE_")
    wexp_thresholds = extract_enum_constants(bmitem_header, name_prefix="WPN_EXP_")
    attribute_flags = read_character_attributes(bmunit_header)
    affinity_values = read_unit_affinities(bmunit_header)

    designator_entries = []  # (designator, loc) for unique/coverage checks

    for record in records:
        ref = "characters[{}]".format(record.key_repr())

        if record.character is not None:
            diagnostics.extend(
                validate_reference(record.character, characters_enum, record.character_loc, ref, kind="character")
            )
            if record.character in characters_enum:
                if record.character == character_refs.CHARACTER_NONE_NAME:
                    value = characters_enum[record.character][0]
                    diagnostics.add(
                        GeneratedDataError(
                            "CHARACTER_NONE ({}) cannot be used as a character record's designator "
                            "(its implied array index -1 is not a valid table entry)".format(value),
                            record.character_loc, ref,
                        )
                    )
                else:
                    value = characters_enum[record.character][0]
                    designator_entries.append((value, record.character_loc))
        else:
            diagnostics.extend(
                validate_range(record.character_id, designator_min, designator_max, record.character_id_loc,
                                "{}.characterId".format(ref), field_name="characterId")
            )
            if designator_min <= record.character_id <= designator_max:
                designator_entries.append((record.character_id, record.character_id_loc))

        diagnostics.extend(
            validate_reference(record.default_class, classes_enum, record.default_class_loc,
                                "{}.defaultClass".format(ref), kind="class")
        )
        if record.default_class in classes_enum and known_class_names is not None:
            if record.default_class not in known_class_names:
                diagnostics.add(
                    GeneratedDataError(
                        "defaultClass '{}' is a valid CLASS_* constant but has no ClassData record "
                        "in the loaded classes table (see --dep-source classes=PATH)".format(record.default_class),
                        record.default_class_loc, "{}.defaultClass".format(ref),
                    )
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
            validate_range(record.portrait, 0, portrait_count - 1, record.portrait_loc or record.loc,
                            "{}.portrait".format(ref), field_name="portrait")
        )
        diagnostics.extend(
            validate_range(record.mini_portrait, 0, mini_portrait_capacity - 1,
                            record.mini_portrait_loc or record.loc,
                            "{}.miniPortrait".format(ref), field_name="miniPortrait")
        )
        diagnostics.extend(
            validate_range(record.sort_order, _U8_MIN, _U8_MAX, record.sort_order_loc or record.loc,
                            "{}.sortOrder".format(ref), field_name="sortOrder")
        )
        diagnostics.extend(
            validate_range(record.visit_group, _U8_MIN, _U8_MAX, record.visit_group_loc or record.loc,
                            "{}.visitGroup".format(ref), field_name="visitGroup")
        )
        diagnostics.extend(
            validate_range(record.base_level, _U8_MIN, _U8_MAX, record.base_level_loc or record.loc,
                            "{}.baseLevel".format(ref), field_name="baseLevel")
        )

        if record.affinity is not None:
            diagnostics.extend(
                validate_reference(record.affinity, affinity_values, record.affinity_loc or record.loc,
                                    "{}.affinity".format(ref), kind="affinity")
            )

        for stat_key, value in record.base.items():
            diagnostics.extend(
                validate_range(value, _S8_MIN, _S8_MAX, record.base_locs[stat_key] or record.loc,
                                "{}.base.{}".format(ref, stat_key), field_name=stat_key)
            )
        for stat_key, value in record.growth.items():
            diagnostics.extend(
                validate_range(value, _U8_MIN, _U8_MAX, record.growth_locs[stat_key] or record.loc,
                                "{}.growth.{}".format(ref, stat_key), field_name=stat_key)
            )

        _, attribute_errors = resolve_bitmask_flags(
            record.attributes, attribute_flags, record.attributes_loc,
            "{}.attributes".format(ref), kind="character attribute",
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

        for name, loc in record.reserved_fields:
            diagnostics.add(
                GeneratedDataError(
                    "field '{}' is reserved (fixed zero in every record) and must not be authored".format(name),
                    loc or record.loc, "{}.{}".format(ref, name),
                )
            )

        if record.support_data is not None:
            if record.is_raw():
                diagnostics.add(
                    GeneratedDataError(
                        "raw/generic-template character records must not reference supportData "
                        "(no proven generic-template record has SupportData)",
                        record.support_data_loc, "{}.supportData".format(ref),
                    )
                )
            elif supports_by_symbol is not None:
                partner_record = supports_by_symbol.get(record.support_data)
                if partner_record is None:
                    diagnostics.add(
                        GeneratedDataError(
                            "undefined supportData reference '{}' (not found in the loaded supports table)".format(
                                record.support_data
                            ),
                            record.support_data_loc, "{}.supportData".format(ref),
                        )
                    )
                elif partner_record.owner != record.character:
                    diagnostics.add(
                        GeneratedDataError(
                            "supportData '{}' belongs to owner '{}', not '{}'".format(
                                record.support_data, partner_record.owner, record.character
                            ),
                            record.support_data_loc, "{}.supportData".format(ref),
                        )
                    )

    diagnostics.extend(
        validate_unique(
            designator_entries,
            "duplicate character designator {key} (first defined at {first_loc})",
            "characters[id={key}]",
        )
    )

    if getattr(records, "full_coverage", False):
        covered = {value for value, _ in designator_entries}
        missing = sorted(set(range(designator_min, designator_max + 1)) - covered)
        if missing:
            doc_loc = getattr(records, "loc", None)
            for value in missing:
                diagnostics.add(
                    GeneratedDataError(
                        "missing character coverage for designator {}: no authored record".format(value),
                        doc_loc, "characters",
                    )
                )


class CharactersTableSchema(TableSchema):
    """Batch 2b: full 256-record authoring, C89 generation, and
    hand-source semantic round trip (extends Batch 2a's schema/
    dependency-validation foundation -- see the module docstring).
    """

    name = SCHEMA_NAME
    version = SCHEMA_VERSION

    default_source = "src/data/characters.json"
    default_hand_source = "src/data_characters.c"
    default_output_name = "data_characters.c"
    default_inventory_path = "reports/generated_data_characters_inventory.md"

    # gCharacterData[] is a hard 256-element array (1-based designators
    # 1..256, see DESIGNATOR_MAX and the module docstring): the u8 unit
    # .number selector can never exceed 256, so authoring more than 256
    # records would overflow the array. Reported/gated by manifest.py.
    record_budget = DESIGNATOR_MAX
    record_budget_reason = "gCharacterData[] fixed 256-slot array (1-based designators 1..256)"

    def dependencies(self):
        return (
            "constants.characters.CHARACTER", "constants.classes.CLASS",
            "bmunit.CA", "bmunit.UNIT_AFFIN", "bmitem.ITYPE", "bmitem.WPN_EXP",
            "constants.msg.MSG_COUNT", "data.portrait_data", "data.face.sGenericChibiImgLut",
            "classes", "supports",
        )

    def dependency_tables(self):
        return ("classes", "supports")

    def load_records(self, source_path):
        return load_records(source_path)

    def validate(self, records, diagnostics, dependency_records=None):
        validate(records, diagnostics, dependency_records)

    def generate_c(self, records, source_path):
        from . import generate as characters_generate
        return characters_generate.generate_c_source(records, source_path)

    def build_inventory(self, records):
        from . import inventory as characters_inventory
        return characters_inventory.build_inventory(records)

    def round_trip_errors(self, records, hand_source):
        if not hand_source or not os.path.exists(hand_source):
            return []
        from . import parser as characters_roundtrip
        characters_enum = character_refs.read_character_designators()
        designators = {
            d for d in (r.designator(characters_enum) for r in records) if d is not None
        }
        hand_records = characters_roundtrip.parse_hand_written(hand_source, characters_enum, designators)
        return characters_roundtrip.compare_records(records, hand_records, hand_path=hand_source)


def dependency_graph():
    graph = DependencyGraph()
    for dep in CharactersTableSchema().dependencies():
        graph.add_dependency(SCHEMA_NAME, dep)
    return graph
