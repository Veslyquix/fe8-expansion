"""C89 generation for the gItemData[] (index-designated struct ItemData[]) table."""

from __future__ import annotations

import os

from ..cgen import render_banner
from ..validators import extract_enum_constants
from .schema import BMITEM_HEADER, ITEMS_HEADER, ITEMS_EXPANSION_HEADER, read_item_attributes


def _sorted_attributes(attributes, attribute_flags):
    """Emit flags in ascending bit-value order -- matches the vanilla hand
    file convention field-for-field (every .attributes combo in
    src/data_items.c lists its IA_* flags in ascending bit-position order)."""
    return sorted(attributes, key=lambda name: attribute_flags.get(name, 0))


def generate_c_source(records, source_path):
    items_enum = extract_enum_constants(ITEMS_HEADER, name_prefix="ITEM_")
    if os.path.exists(ITEMS_EXPANSION_HEADER):
        expansion_enum = extract_enum_constants(ITEMS_EXPANSION_HEADER, name_prefix="ITEM_")
    else:
        expansion_enum = {}
    order_enum = dict(items_enum)
    order_enum.update(expansion_enum)
    attribute_flags = read_item_attributes(BMITEM_HEADER)

    ordered = sorted(
        records,
        key=lambda r: order_enum[r.item][0] if r.item in order_enum else 1 << 30,
    )

    uses_expansion = any(r.item in expansion_enum for r in records)

    parts = [render_banner(source=source_path, table="items")]
    parts.append("#include \"global.h\"\n")
    parts.append("#include \"bmitem.h\"\n")
    parts.append("#include \"constants/items.h\"\n")
    if uses_expansion:
        parts.append("#include \"constants/items_expansion.h\"\n")
    # Issue #10: this generated table is the one real consumer that can prove
    # the *generated* record count and the *compiled* cap are the same build
    # input. id_space.h is the committed DEFAULT contract (ITEM_ID_CONFIGURED_CAP,
    # overridable through -DFE8_ITEM_ID_CAP); id_space_active.h is the
    # build-local ACTIVE contract this generator just resolved and sits in this
    # same generated directory, so the quoted include resolves with no extra
    # -I flag in either the modern or the archival lane.
    parts.append("#include \"id_space.h\"\n")
    parts.append("#include \"id_space_active.h\"\n")
    parts.append("\n")
    parts.append("CONST_DATA struct ItemData gItemData[] = {\n")

    for record in ordered:
        parts.append("\t[{}] = {{\n".format(record.item))

        if record.name_text_id:
            parts.append("\t\t.nameTextId = {},\n".format(record.name_text_id))
        if record.desc_text_id:
            parts.append("\t\t.descTextId = {},\n".format(record.desc_text_id))
        if record.use_desc_text_id:
            parts.append("\t\t.useDescTextId = {},\n".format(record.use_desc_text_id))

        parts.append("\t\t.number = {},\n".format(record.item))
        parts.append("\t\t.weaponType = {},\n".format(record.weapon_type))

        if record.attributes:
            flags = _sorted_attributes(record.attributes, attribute_flags)
            parts.append("\t\t.attributes = {},\n".format(" | ".join(flags)))

        if record.stat_bonuses is not None:
            parts.append("\t\t.pStatBonuses = &{},\n".format(record.stat_bonuses))
        if record.effectiveness is not None:
            parts.append("\t\t.pEffectiveness = {},\n".format(record.effectiveness))

        if record.max_uses:
            parts.append("\t\t.maxUses = {},\n".format(record.max_uses))
        if record.might:
            parts.append("\t\t.might = {},\n".format(record.might))
        if record.hit:
            parts.append("\t\t.hit = {},\n".format(record.hit))
        if record.weight:
            parts.append("\t\t.weight = {},\n".format(record.weight))
        if record.crit:
            parts.append("\t\t.crit = {},\n".format(record.crit))

        if record.encoded_range:
            parts.append("\t\t.encodedRange = {},\n".format(record.encoded_range))

        if record.cost_per_use:
            parts.append("\t\t.costPerUse = {},\n".format(record.cost_per_use))
        if record.required_wexp != "WPN_EXP_0":
            parts.append("\t\t.weaponRank = {},\n".format(record.required_wexp))

        parts.append("\t\t.iconId = {},\n".format(record.icon_id))

        if record.use_effect_id:
            parts.append("\t\t.useEffectId = {},\n".format(record.use_effect_id))
        if record.weapon_effect != "WPN_EFFECT_NONE":
            parts.append("\t\t.weaponEffectId = {},\n".format(record.weapon_effect))
        if record.weapon_exp:
            parts.append("\t\t.weaponExp = {},\n".format(record.weapon_exp))

        parts.append("\t},\n")

    parts.append("};\n")

    # Compile-time proof, in the translation unit that owns the table:
    #   1. the compiler cap (-DFE8_ITEM_ID_CAP / id_space.h default) is exactly
    #      the cap this generator resolved, and
    #   2. the emitted, index-designated gItemData[] really holds the active
    #      record count (207 at cap 0xCE, 206 at the vanilla 0xCD).
    # A stale generated table, a stale active header, or a build that flows a
    # different -DFE8_ITEM_ID_CAP than the generator saw all fail to compile
    # here instead of silently linking a truncated table.
    parts.append("\n")
    parts.append("/* Issue #10 active-contract proof (see scripts/generated_data/idspace.py). */\n")
    parts.append("ID_SPACE_STATIC_ASSERT(ITEM_ID_CONFIGURED_CAP == ITEM_ID_ACTIVE_CONFIGURED_CAP,\n")
    parts.append("    generated_items_cap_matches_active_contract);\n")
    parts.append("ID_SPACE_STATIC_ASSERT(\n")
    parts.append("    sizeof(gItemData) / sizeof(gItemData[0]) == ITEM_ID_ACTIVE_RECORD_COUNT,\n")
    parts.append("    generated_items_record_count_matches_active_contract);\n")
    return "".join(parts)
