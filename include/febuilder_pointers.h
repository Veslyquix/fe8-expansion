#ifndef GUARD_FEBUILDER_POINTERS_H
#define GUARD_FEBUILDER_POINTERS_H

#if FE8_FEBUILDER_POINTERS

/* One entry per line of tools/febuilder_pointers/field_order.txt, same
 * order -- see scripts/gen_custom_pointer_txt.py, which zips the two
 * together to produce fireemblem8.custom_pointer.txt. */
extern CONST_DATA u32 gFebuilderPointers[];

#endif

#endif // GUARD_FEBUILDER_POINTERS_H
