#ifndef GUARD_EXPANSION_STARTER_CONTENT_H
#define GUARD_EXPANSION_STARTER_CONTENT_H

/*
 * Bundled generated-data CONTENT example (issue #6, Sprint 2).
 *
 * This is the framework's one shipped demonstration that the three public
 * seams -- compile-time config, generated data, and the runtime hook API --
 * compose without any of them being special-cased:
 *
 *   config : FE8_EXPANSION_STARTER_CONTENT (config.mk
 *            EXPANSION_STARTER_CONTENT), a strict 0/1 flag defaulting to 0.
 *   data   : the framework-authored item record ITEM_EXPANSION_CE, authored
 *            in src/data/items_expansion.json and emitted into
 *            gItemData[ITEM_EXPANSION_CE] by the ordinary generated-data
 *            pipeline. Its ORIGINAL display name is authored literally in
 *            that same record ("authoringName") and emitted by the same
 *            pipeline into a BUILD-LOCAL text table that only this profile
 *            generates and links -- the record binds no message ID, because
 *            texts/texts.txt is one shared Huffman-compressed blob whose
 *            re-encode would move a DEFAULT build's ROM. No vanilla message,
 *            name or icon art is reused as a shortcut and no new graphics
 *            asset is added (the record points at the neutral, purely
 *            geometric unused placeholder icon slot).
 *   hook   : one mechanic registered through the PUBLIC
 *            ExpansionMechanicsRegister() API (include/expansion_mechanics.h).
 *            src/bmbattle.c is not touched, no stat is special-cased, and no
 *            second router/registry is introduced.
 *
 * Dependencies (each a hard error, in all three of Python/Make and C):
 *   * FE8_EXPANSION_MECHANICS_HOOKS=1 -- checked in
 *     include/expansion_config.h and scripts/modernize/expansion_config.py.
 *   * an active item ID cap that actually reaches ITEM_EXPANSION_CE --
 *     checked below and in scripts/modernize/expansion_config.py.
 *
 * The dependency is deliberately one-way: the issue #10 ID-space platform
 * never depends on this flag, so an expanded-cap build with the content flag
 * off is still a valid, independently testable platform build.
 *
 * Save format: untouched by this feature. It introduces no new save field
 * and requires no epoch bump of its own -- EXPANSION_SAVE_COMPAT_EPOCH's
 * live current value (config.mk; currently 2, independently bumped 1 -> 2
 * for issue #18 sprint 2) is unaffected by this feature either way. The
 * item ID travels in the existing 14-bit item fields the vanilla
 * save/suspend/link records already use.
 *
 * C89/agbcc-safe, and (like the rest of the expansion headers) expects
 * global.h to have been included first.
 */

#include "expansion_config.h"
#include "id_space.h"

#if FE8_EXPANSION_STARTER_CONTENT
#if ITEM_ID_CONFIGURED_CAP < ITEM_ID_EXPANSION_FIRST
#error "FE8_EXPANSION_STARTER_CONTENT=1 requires an expanded item cap (build with FE8_ITEM_ID_CAP=0xCE or higher)"
#endif
#endif

struct Unit;

/*
 * The bundled mechanic, "Content Sample Evade": while the subject carries
 * the bundled content item, it gains a fixed, strictly clamped avoid bonus.
 *
 * The registry label below deliberately does NOT restate the item's authored
 * display name: that name has exactly one source of truth (the authored
 * record + the generated content text table), and a hand-copy here would be
 * a second one, free to drift.
 *
 * It is deliberately a DIFFERENT stat from the content-free sample mechanic
 * in include/expansion_mechanics.h ("Full-HP Guard", +1 battleDefense), so
 * the two are independently observable in one apply and the pre-existing
 * sample keeps exactly its previous standalone semantics.
 *
 * Inventory membership is read with the production accessor
 * GetUnitItemSlot(); the item is named symbolically (ITEM_EXPANSION_CE) and
 * held in a typed ItemId. No raw numeric item ID appears anywhere.
 */
#define EXPANSION_STARTER_CONTENT_KEY "content.sample_charm"
#define EXPANSION_STARTER_CONTENT_LABEL "Content Sample Evade +5"
#define EXPANSION_STARTER_CONTENT_AVOID_BONUS 5
#define EXPANSION_STARTER_CONTENT_AVOID_CAP 120

/*
 * Register the bundled content mechanic through the public registry API.
 * Called once from ExpansionMechanicsInstallBuiltins() -- the framework's
 * single built-in install point -- so there is exactly one install path.
 * A no-op when the content flag is 0. Idempotent (the registry rejects a
 * duplicate key without changing anything).
 */
void ExpansionStarterContentInstallMechanics(void);

/*
 * The bundled content item's typed ID, or ITEM_ID_SENTINEL when the content
 * flag is 0. Lets a caller (e.g. the issue #10 runtime probe) assert the
 * exact typed identity without restating a numeric literal.
 */
ItemId ExpansionStarterContentItemId(void);

#if FE8_EXPANSION_STARTER_CONTENT

/*
 * Capacity of the module's own name buffer. The generated content text
 * table (build/generated/data/items_expansion_content_text.h) publishes its
 * longest authored name as EXPANSION_CONTENT_TEXT_NAME_CAPACITY, and
 * src/expansion_starter_content.c statically asserts that it fits here, so
 * over-long authoring text fails the build instead of truncating on screen.
 * Sized to hold any schema-legal authored name (bounded at 20 characters by
 * scripts/generated_data/items/schema.py) plus the article/prefix room
 * GetItemNameWithArticle() may insert in place.
 */
#define EXPANSION_STARTER_CONTENT_NAME_BUFFER 32

/*
 * The narrow, typed production seam for authored content text.
 *
 * Returns a writable copy of the item's ORIGINAL authored name -- the exact
 * string the generated content text table holds -- or NULL when `item` is
 * not an authored content record, in which case the caller must fall through
 * to the ordinary message-table path. Writable because the vanilla name path
 * (GetItemNameWithArticle -> InsertPrefix) edits the string it is handed.
 *
 * Declared and compiled ONLY under FE8_EXPANSION_STARTER_CONTENT, so a
 * default build has no declaration, no definition, no data and no call site:
 * src/bmitem.c's GetItemName() is preprocessed back to its vanilla body.
 */
char * ExpansionStarterContentItemName(ItemId item);

#endif /* FE8_EXPANSION_STARTER_CONTENT */

/* 1 when the content flag is on, else 0. */
int ExpansionStarterContentIsEnabled(void);

#endif /* GUARD_EXPANSION_STARTER_CONTENT_H */
