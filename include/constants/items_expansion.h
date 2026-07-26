#ifndef GUARD_CONSTANTS_ITEMS_EXPANSION_H
#define GUARD_CONSTANTS_ITEMS_EXPANSION_H

/* Opt-in item ID expansion slots (Issue #10 pilot).
 *
 * Vanilla / default builds never include this header, so the vanilla
 * include/constants/items.h enum still stops at ITEM_UNK_CD (0xCD) and any
 * stray reference to an expansion item fails to compile early. Expansion
 * builds (item cap raised via FE8_ITEM_ID_CAP >= 0xCE, see
 * scripts/generated_data/idspace.py) include this alongside items.h to make
 * the first practical expansion item ID resolvable.
 *
 * The item save fields are already 14-bit (0x3FFF) and the runtime index is
 * masked to 8 bits (ITEM_INDEX), so 0xCE costs 0 RAM / 0 save-layout bytes;
 * see reports/id_space_audit.md, item domain.
 */
enum {
    ITEM_EXPANSION_CE = 0xCE,
};

#endif /* GUARD_CONSTANTS_ITEMS_EXPANSION_H */
