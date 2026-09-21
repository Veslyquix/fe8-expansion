/* Build-local CONTENT text (issue #6 worked example).
 *
 * Hand-authored. Only compiled in the content profile
 * (EXPANSION_STARTER_CONTENT=1, see src/expansion_starter_content.c); a
 * default build never includes this header, so its ROM holds none of
 * these strings. The authored text lives directly in this table -- no
 * message is added to the shared, Huffman-compressed table in
 * texts/texts.txt.
 *
 * Only the item name is embedded/consumed at runtime (by
 * GetItemName() under FE8_EXPANSION_STARTER_CONTENT=1, see
 * src/expansion_starter_content.c). The item's help/description text is
 * not shown in game: the vanilla help/description UI is addressed by
 * message ID only, and this worked example adds/reuses none.
 */

#ifndef GUARD_ITEMS_EXPANSION_CONTENT_TEXT_H
#define GUARD_ITEMS_EXPANSION_CONTENT_TEXT_H

#include "id_space.h"
#include "constants/items_expansion.h"

/* Number of authored content records, and the longest authored name
 * (excluding the NUL). The consuming translation unit statically
 * asserts its own copy buffer against the capacity below. */
#define EXPANSION_CONTENT_TEXT_COUNT 1
#define EXPANSION_CONTENT_TEXT_NAME_CAPACITY 13

struct ExpansionContentItemText
{
    ItemId item;
    const char * name;
};

static const struct ExpansionContentItemText
    sExpansionContentItemText[EXPANSION_CONTENT_TEXT_COUNT] =
{
    { ITEM_EXPANSION_CE, "Sample Charm" },
};

#endif /* GUARD_ITEMS_EXPANSION_CONTENT_TEXT_H */
