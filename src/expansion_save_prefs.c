#include "global.h"
#include "expansion_save_prefs.h"

/*
 * Public store entry point (issue #18 sprint 2). Deliberately kept out of
 * src/bmsave-lib.c: unlike ExpansionUserPrefs_StoreRaw()/_Build()/
 * _ValidateRaw()/_Load()/_Normalize() (all pure struct/macro logic, no
 * expansion_locale.c symbol references, so they stay legacy-linkable),
 * this function must call the real ExpansionLocale_SetCurrent()
 * (src/expansion_locale.c) to keep the runtime resolver and its dependent
 * expansion/full-game caches coherent with whatever was just persisted --
 * and that symbol is only linked into the modern ROM
 * (see include/expansion_locale.h's file comment). This file is compiled
 * by both the legacy agbcc build and every modern build cell (so it must
 * stay strict C89-typecheckable) but -- exactly like
 * src/expansion_locale.c -- is only linked into the modern ROM: neither
 * file is named in ldscript.txt's explicit legacy object list, and
 * modern.mk's `wildcard src/*.c` picks up any new src/*.c automatically,
 * so no modern.mk source-list edit is required for this file either.
 */

bool8 ExpansionUserPrefs_Store(ExpansionLocaleId localeId, bool8 explicitSelection)
{
    if (!ExpansionLocale_IsSupported(localeId) || !ExpansionLocale_IsEnabled(localeId))
        return FALSE;

    if (!ExpansionUserPrefs_StoreRaw(localeId, explicitSelection))
        return FALSE;

    /*
     * ExpansionLocale_SetCurrent() already calls
     * ExpansionLocale_InvalidateCache() itself whenever the current locale
     * actually changes (src/expansion_locale.c), which clears both the
     * expansion catalog cache and the localized full-game message cache.
     * It cannot fail here: localeId was already proven
     * supported+enabled above.
     */
    return ExpansionLocale_SetCurrent(localeId);
}
