#include "global.h"
#include <string.h>
#include "agb_sram.h"
#include "bmunit.h"
#include "bmitem.h"
#include "bmcontainer.h"
#include "bmreliance.h"
#include "bmsave.h"
#include "sram-layout.h"
#include "bmlib.h"
#include "eventinfo.h"
#include "bonusclaim.h"
#include "expansion_save_prefs.h"

// TODO: Should be in "bmsave.h", but doing so causes a non-match (implicit declaration?) in "bonusclaim.c"
bool LoadBonusContentData(void *buf);

EWRAM_DATA u8 gUnused_BmsaveLib_0[10] = { 0 };
EWRAM_DATA bool gBoolSramWorking = false;

static const char sSaveMarker[] = "AGB-FE9";
static const u8 sConvySavePackMask1[] = {
    0xC0,   /* 1100 0000 */
    0x81,   /* 1000 0001 */
    0x03,   /* 0000 0011 */
    0x07,   /* 0000 0111 */
    0x0F,   /* 0000 1111 */
    0x1F,   /* 0001 1111 */
    0x3F,   /* 0011 1111 */
    0x7F,   /* 0111 1111 */
};

static const u8 sConvySavePackMask2[] = {
    0x00,   /* 0000 0000 */
    0x00,   /* 0000 0000 */
    0x00,   /* 0000 0000 */
    0xF7,   /* 1111 0111 */
    0xFC,   /* 1111 1100 */
    0xF8,   /* 1111 1000 */
    0xF0,   /* 1111 0000 */
    0xE0,   /* 1110 0000 */
};

CONST_DATA struct SaveBlocks *gSram = CART_SRAM;

CONST_DATA int sSupportUnkLut[][2] = {
    { 0x0100, 0x0100 }, 
    { 0x0000, 0x0000 }
};

//! FE8U = 0x080A2C2C
u8 * BmSave_GetUnusedBuffer(void)
{
    gUnused_BmsaveLib_0[0] = 0;
    return gUnused_BmsaveLib_0;
}

void BmSave_NopStub(void)
{
    return;
}

#ifdef MODERN
EWRAM_DATA u8 gSramBootFlags;
#endif

void SramInit(void)
{
    u32 buf[2];
    buf[0] = 0x12345678;
    buf[1] = 0x87654321;

    SetSramFastFunc();
    REG_IE |= INTR_FLAG_GAMEPAK;
    WriteSramFast((u8 *)&buf[0], gSram->reserved, sizeof(gSram->reserved));
    ReadSramFast(gSram->reserved, &buf[1], sizeof(buf[1]));
    
    gBoolSramWorking = (buf[1] == buf[0])
                     ? true
                     : false;
}

bool IsSramWorking(void)
{
    return gBoolSramWorking;
}

void WipeSram(void)
{
    u32 buf[0x10];
    int i;

    for (i = 0; i < 0x10; i++)
        buf[i] = 0xFFFFFFFF;

    for (i = 0; i < 0x200; i++)
        WriteAndVerifySramFast(buf, (u8 *)gSram + i * 0x40, 0x40);
}

u16 Checksum16(void const * data, int size)
{
    u16 const * data_u16 = data;

    int i;

    u32 add_acc = 0;
    u32 xor_acc = 0;

    for (i = 0; i < size/2; ++i)
    {
        add_acc += data_u16[i];
        xor_acc ^= data_u16[i];
    }

    return add_acc + xor_acc;
}

/*
 * Copies at most (destCapacity - 1) bytes from a NUL-terminated src into
 * dest, then always NUL-terminates dest. Unlike CopyString() (bmlib.c),
 * this never writes past destCapacity bytes, which matters here because
 * FE8_EXPANSION_BUILD_COMMIT/FE8_EXPANSION_CONFIG_FINGERPRINT are wider
 * than the fixed diagnostic fields they are copied into below.
 */
static void CopyStringBounded(char *dest, const char *src, int destCapacity)
{
    int i;

    for (i = 0; i < destCapacity - 1 && '\0' != src[i]; ++i)
        dest[i] = src[i];

    dest[i] = '\0';
}

/* Byte-for-byte compare of a fixed-size, not-necessarily-NUL-terminated
 * region (used for the metadata magic, which is not a C string). */
static bool BytesEqual(void const *a, void const *b, int size)
{
    u8 const *pa = a;
    u8 const *pb = b;
    int i;

    for (i = 0; i < size; ++i)
    {
        if (pa[i] != pb[i])
            return false;
    }

    return true;
}

/* True if every byte of the region is 0xFF, matching WipeSram()'s
 * 0xFFFFFFFF fill pattern. */
static bool IsRegionBlank(void const *data, int size)
{
    u8 const *bytes = data;
    int i;

    for (i = 0; i < size; ++i)
    {
        if (bytes[i] != 0xFF)
            return false;
    }

    return true;
}

/* True if every byte of the region is 0x00 -- the deterministic "never
 * written" pattern every pre-issue-#18-sprint-2 build left in struct
 * ExpansionSaveMeta's `reserved` tail (see BuildCurrentExpansionSaveMeta()
 * below, which memset()s the whole struct before setting any named
 * field). Also used by modern live-SRAM EMPTY detection and by
 * ExpansionUserPrefs_ValidateRaw()'s callers, where either legacy "unset"
 * pattern (all-zero or all-0xFF) is never treated as CORRUPT. */
static bool IsRegionAllZero(void const *data, int size)
{
    u8 const *bytes = data;
    int i;

    for (i = 0; i < size; ++i)
    {
        if (bytes[i] != 0x00)
            return false;
    }

    return true;
}

#ifdef MODERN
/*
 * SramInit() overwrites gSram->reserved as its four-byte hardware probe
 * before compatibility classification. Every other byte must retain one
 * consistent erased fill value before EMPTY is safe to report.
 */
static bool IsSramErasedWithValue(u8 value)
{
    u32 probeOffset;
    u32 probeEnd;

    probeOffset = (u8 *)gSram->reserved - (u8 *)gSram;
    probeEnd = probeOffset + sizeof(gSram->reserved);

    return VerifySramValueFast(gSram, value, probeOffset) == 0
        && VerifySramValueFast(
            (u8 *)gSram + probeEnd,
            value,
            CART_SRAM_SIZE - probeEnd) == 0;
}
#endif

void BuildCurrentExpansionSaveMeta(struct ExpansionSaveMeta *meta)
{
    int i;

    /*
     * Issue #2 slice 1 (review fix): zero the entire struct first,
     * deterministically, before setting any named field. Without this,
     * the STRUCT_PAD() alignment bytes at 0x05, 0x09-0x0B, 0x21-0x23, and
     * 0x2D (all inside EXPANSION_SAVE_META_SIZE_FOR_CHECKSUM's checksum
     * domain) were left holding whatever garbage was already on the
     * stack/in the caller's buffer, making the checksummed bytes -- and
     * therefore this metadata record -- non-deterministic across builds
     * and potentially leaking uninitialized memory into SRAM.
     */
    memset(meta, 0, sizeof(*meta));

    for (i = 0; i < EXPANSION_SAVE_META_MAGIC_SIZE; i++)
        meta->magic[i] = EXPANSION_SAVE_META_MAGIC[i];

    meta->formatVersion = SAVE_FORMAT_VERSION_CURRENT;
    meta->compatEpoch = FE8_EXPANSION_SAVE_COMPAT_EPOCH;
    meta->abiId = StringCompare(FE8_EXPANSION_ABI, "aapcs") ? SAVE_ABI_ID_AAPCS : SAVE_ABI_ID_APCS_GNU;
    meta->frameworkVersionPacked = FE8_EXPANSION_VERSION_PACKED;

    CopyStringBounded(meta->configFingerprint, FE8_EXPANSION_CONFIG_FINGERPRINT, sizeof(meta->configFingerprint));
    CopyStringBounded(meta->buildCommitShort, FE8_EXPANSION_BUILD_COMMIT, sizeof(meta->buildCommitShort));

    /*
     * Issue #18 sprint 6 (runtime blocker fix): a brand-new save (the
     * only real caller of this function -- InitGlobalSaveInfodata(), on
     * genuinely blank SRAM only) may only auto-stamp a fully-built,
     * VALID-classifying ExpansionUserPrefs record into the front of
     * `reserved` (EXPANSION_USER_PREFS_META_OFFSET) when this build
     * enables exactly one locale (FE8_EXPANSION_ENABLED_LOCALE_COUNT <= 1,
     * include/expansion_config.h) -- the same enabledLocaleCount <= 1
     * collapse ExpansionLanguageMenu_DecideStartupAction() itself uses to
     * pick EXPANSION_LANGUAGE_STARTUP_AUTO_SELECT over ...SHOW_MENU
     * (src/expansion_language_menu.c). In that single-enabled-locale
     * case there is no real choice for the player to make, so stamping
     * the build's configured default now is exactly equivalent to (and
     * strictly cheaper than) letting the runtime auto-select path do the
     * identical write on this save's own first real boot.
     *
     * A multi-enabled-locale build must NOT take this shortcut: prior to
     * this fix, ExpansionUserPrefs_Build() was called unconditionally
     * here, so every brand-new save -- regardless of how many locales
     * this build enabled -- was stamped with a syntactically VALID
     * record (magic/checksum set, ExpansionUserPrefs_ValidateRaw() has
     * no way to distinguish "player chose this" from "auto-stamped
     * default") and `requiresPrompt` was FALSE from the very first boot,
     * silently skipping the mandatory first-start locale prompt that
     * build was supposed to show. Leaving `reserved` at the
     * already-memset()'d canonical all-zero EXPANSION_USER_PREFS_UNSET
     * pattern instead (the implicit `else` below -- no code needed, the
     * memset() above already did it) makes ExpansionUserPrefs_Load()
     * classify this save's first real read as genuinely UNSET, so
     * ExpansionUserPrefs_Normalize()/DecideStartupAction() correctly
     * require -- and, for a multi-enabled-locale build, actually show --
     * the first-start prompt. Every remaining byte of `reserved` past
     * this record stays zeroed by the memset() above either way
     * (EXPANSION_SAVE_META_RESERVED_HEADROOM_BYTES of future headroom,
     * include/expansion_save_prefs.h).
     */
    if (FE8_EXPANSION_ENABLED_LOCALE_COUNT <= 1)
    {
        struct ExpansionUserPrefs prefs;

        /* explicitSelection=FALSE: this is this build's configured
         * default, not something the player chose. */
        ExpansionUserPrefs_Build(&prefs, (ExpansionLocaleId)FE8_EXPANSION_DEFAULT_LOCALE_ID, FALSE);
        memcpy(&meta->reserved[EXPANSION_USER_PREFS_META_OFFSET], &prefs, sizeof(prefs));
    }

    meta->checksum = ExpansionSaveMetaChecksum(meta);
}


u16 ExpansionSaveMetaChecksum(struct ExpansionSaveMeta const *meta)
{
    return Checksum16(meta, EXPANSION_SAVE_META_SIZE_FOR_CHECKSUM);
}

enum SaveCompatState ClassifySaveCompatRaw(
    struct GlobalSaveInfo const *header,
    bool headerRegionBlank,
    struct ExpansionSaveMeta const *meta,
    bool metaRegionBlank)
{
    bool headerValid;

    if (headerRegionBlank && metaRegionBlank)
        return SAVE_COMPAT_EMPTY;

    headerValid = (0 != StringCompare(header->name, sSaveMarker)
                && SAVEMAGIC32 == header->magic32
                && SAVEMAGIC16 == header->magic16
                && header->checksum == Checksum16(header, GLOBALSIZEINFO_SIZE_FOR_CHECKSUM));

    if (!headerValid)
        return SAVE_COMPAT_HEADER_CORRUPT;

    if (!BytesEqual(meta->magic, EXPANSION_SAVE_META_MAGIC, EXPANSION_SAVE_META_MAGIC_SIZE))
        return SAVE_COMPAT_VALID_LEGACY_OR_VANILLA;

    if (meta->checksum != ExpansionSaveMetaChecksum(meta))
        return SAVE_COMPAT_METADATA_CORRUPT;

    if (meta->formatVersion > SAVE_FORMAT_VERSION_CURRENT)
        return SAVE_COMPAT_NEWER_UNSUPPORTED;

    if (meta->formatVersion < SAVE_FORMAT_VERSION_CURRENT)
        return SAVE_COMPAT_MIGRATABLE_OLDER;

    if (meta->compatEpoch != FE8_EXPANSION_SAVE_COMPAT_EPOCH)
        return SAVE_COMPAT_SAVE_CONFIG_INCOMPATIBLE;

    return SAVE_COMPAT_CURRENT;
}

enum SaveCompatState ClassifySramSaveCompat(void)
{
    struct GlobalSaveInfo header;
    struct ExpansionSaveMeta meta;
#ifdef MODERN
    bool sramErased;
#endif

    /* SRAM hardware not confirmed working: never treat as blank, since
     * that would risk an automatic wipe of a cart we cannot actually
     * read back reliably. */
    if (!IsSramWorking())
        return SAVE_COMPAT_HEADER_CORRUPT;

    ReadSramFast(&gSram->globalSaveInfo, &header, sizeof(header));
    ReadSramFast(&gSram->expansionSaveMeta, &meta, sizeof(meta));

#ifdef MODERN
    /*
     * Hardware erase uses 0xFF, while deterministic emulator/movie resets
     * commonly expose never-written SRAM as 0x00. Require one consistent
     * fill across the entire chip (apart from SramInit's probe bytes);
     * erased-looking header/metadata must never hide surviving save blocks.
     */
    sramErased =
        (IsRegionBlank(&header, sizeof(header))
            && IsRegionBlank(&meta, sizeof(meta))
            && IsSramErasedWithValue(0xFF))
        || (IsRegionAllZero(&header, sizeof(header))
            && IsRegionAllZero(&meta, sizeof(meta))
            && IsSramErasedWithValue(0x00));

    return ClassifySaveCompatRaw(
        &header, sramErased,
        &meta, sramErased);
#else
    return ClassifySaveCompatRaw(
        &header, IsRegionBlank(&header, sizeof(header)),
        &meta, IsRegionBlank(&meta, sizeof(meta)));
#endif
}

/* --- ExpansionUserPrefs (issue #18 sprint 2) --------------------------- */

void ExpansionUserPrefs_Build(struct ExpansionUserPrefs *prefs, ExpansionLocaleId localeId, bool8 explicitSelection)
{
    memset(prefs, 0, sizeof(*prefs));

    prefs->magic = EXPANSION_USER_PREFS_MAGIC;
    prefs->version = EXPANSION_USER_PREFS_VERSION_CURRENT;
    prefs->localeId = (u8)localeId;
    prefs->flags = explicitSelection ? EXPANSION_USER_PREFS_FLAG_LOCALE_EXPLICIT : 0;

    /* prefs->reserved is already zeroed by the memset() above. */

    prefs->checksum = ExpansionUserPrefsChecksum(prefs);
}

u16 ExpansionUserPrefsChecksum(struct ExpansionUserPrefs const *prefs)
{
    return Checksum16(prefs, EXPANSION_USER_PREFS_SIZE_FOR_CHECKSUM);
}

enum ExpansionUserPrefsState ExpansionUserPrefs_ValidateRaw(struct ExpansionUserPrefs const *prefs, bool8 regionUnset)
{
    /*
     * Deliberately checks EXPANSION_LOCALE_COUNT/FE8_EXPANSION_ENABLED_LOCALE_MASK
     * directly (compile-time macros/constants, include/expansion_locale.h
     * and include/expansion_config.h) rather than calling
     * ExpansionLocale_IsSupported()/ExpansionLocale_IsEnabled()
     * (src/expansion_locale.c): those real functions are only linked
     * into the modern ROM (see include/expansion_locale.h's file
     * comment), while this function -- like ClassifySaveCompatRaw() --
     * must stay callable from the legacy-linked src/bmsave-lib.c. Both
     * call sites derive the same answer from the same single-source-of-
     * truth macros, so there is no duplicated business logic to drift.
     */
    if (regionUnset)
        return EXPANSION_USER_PREFS_UNSET;

    if (prefs->magic != EXPANSION_USER_PREFS_MAGIC)
        return EXPANSION_USER_PREFS_CORRUPT;

    if (prefs->checksum != ExpansionUserPrefsChecksum(prefs))
        return EXPANSION_USER_PREFS_CORRUPT;

    if (prefs->version > EXPANSION_USER_PREFS_VERSION_CURRENT)
        return EXPANSION_USER_PREFS_CORRUPT;

    if (prefs->localeId >= EXPANSION_LOCALE_COUNT)
        return EXPANSION_USER_PREFS_UNKNOWN_LOCALE;

    if (!(FE8_EXPANSION_ENABLED_LOCALE_MASK & ((u32)1 << prefs->localeId)))
        return EXPANSION_USER_PREFS_DISABLED_LOCALE;

    if (prefs->version < EXPANSION_USER_PREFS_VERSION_CURRENT)
        return EXPANSION_USER_PREFS_MIGRATED;

    return EXPANSION_USER_PREFS_VALID;
}

enum ExpansionUserPrefsState ExpansionUserPrefs_Load(struct ExpansionUserPrefs *out)
{
    struct ExpansionUserPrefs local;
    bool regionUnset;

    if (!IsSramWorking())
    {
        if (out != NULL)
            memset(out, 0, sizeof(*out));
        return EXPANSION_USER_PREFS_CORRUPT;
    }

    ReadSramFast(&gSram->expansionSaveMeta.reserved[EXPANSION_USER_PREFS_META_OFFSET], &local, sizeof(local));

    regionUnset = IsRegionBlank(&local, sizeof(local)) || IsRegionAllZero(&local, sizeof(local));

    if (out != NULL)
        *out = local;

    return ExpansionUserPrefs_ValidateRaw(&local, regionUnset);
}

enum ExpansionUserPrefsState ExpansionUserPrefs_Normalize(
    struct ExpansionUserPrefs const *prefs,
    enum ExpansionUserPrefsState state,
    ExpansionLocaleId *outLocaleId,
    bool8 *outRequiresPrompt)
{
    if (state == EXPANSION_USER_PREFS_VALID || state == EXPANSION_USER_PREFS_MIGRATED)
    {
        if (outLocaleId != NULL)
            *outLocaleId = (ExpansionLocaleId)prefs->localeId;
        if (outRequiresPrompt != NULL)
            *outRequiresPrompt = FALSE;
    }
    else
    {
        if (outLocaleId != NULL)
            *outLocaleId = (ExpansionLocaleId)FE8_EXPANSION_DEFAULT_LOCALE_ID;
        if (outRequiresPrompt != NULL)
            *outRequiresPrompt = TRUE;
    }

    return state;
}

bool8 ExpansionUserPrefs_StoreRaw(ExpansionLocaleId localeId, bool8 explicitSelection)
{
    struct ExpansionUserPrefs prefs;
    u32 errorAddr;

    if (localeId >= EXPANSION_LOCALE_COUNT)
        return FALSE;

    if (!(FE8_EXPANSION_ENABLED_LOCALE_MASK & ((u32)1 << localeId)))
        return FALSE;

    if (!IsSramWorking())
        return FALSE;

#ifdef MODERN
    if (!(gSramBootFlags & SRAM_BOOT_FLAG_WRITES_ALLOWED))
        return FALSE;
#endif

    /*
     * Issue #18 sprint 2 write-interruption contract: build the whole
     * record (magic/version/localeId/flags/checksum) in a local, non-SRAM
     * temporary first, then perform exactly one bounded
     * WriteAndVerifySramFast() call covering only this record's own
     * fixed window inside gSram->expansionSaveMeta.reserved -- never
     * WipeSram(), never any wider write. `prefs` (stack-local) and the
     * SRAM destination never overlap. If interrupted/failed partway, at
     * worst this record's own checksum stops matching on the next read
     * (classified EXPANSION_USER_PREFS_CORRUPT -- safe fallback + a
     * requires-prompt signal, never SRAM corruption elsewhere).
     */
    ExpansionUserPrefs_Build(&prefs, localeId, explicitSelection);

    errorAddr = WriteAndVerifySramFast(
        &prefs, &gSram->expansionSaveMeta.reserved[EXPANSION_USER_PREFS_META_OFFSET], sizeof(prefs));

    return (bool8)(errorAddr == 0);
}

bool ReadGlobalSaveInfo(struct GlobalSaveInfo *buf)
{
    struct GlobalSaveInfo local_info;

    if (!IsSramWorking())
        return false;

    if (NULL == buf)
        buf = &local_info;

    ReadSramFast(&gSram->globalSaveInfo, buf, sizeof(struct GlobalSaveInfo));

    if (0 != StringCompare(buf->name, sSaveMarker)
        && SAVEMAGIC32 == buf->magic32
        && SAVEMAGIC16 == buf->magic16
        && buf->checksum == Checksum16(buf, GLOBALSIZEINFO_SIZE_FOR_CHECKSUM))
        return true;

    return false;
}

void WriteGlobalSaveInfo(struct GlobalSaveInfo *header)
{
    header->checksum = Checksum16(header, GLOBALSIZEINFO_SIZE_FOR_CHECKSUM);
    WriteAndVerifySramFast(header, &gSram->globalSaveInfo, sizeof(struct GlobalSaveInfo));
}

void WriteGlobalSaveInfoNoChecksum(struct GlobalSaveInfo *header)
{
    WriteAndVerifySramFast(header, &gSram->globalSaveInfo, sizeof(struct GlobalSaveInfo));
}

void InitGlobalSaveInfodata(void)
{
    struct GlobalSaveInfo info;
    int i;

    WipeSram();
    CopyString(info.name, sSaveMarker);

    info.magic32 = SAVEMAGIC32;
    info.magic16 = SAVEMAGIC16;

    info.completed  = 0;
    info.flag0E_1 = 0;
    info.Eirk_mode_easy = 0;
    info.Eirk_mode_norm = 0;
    info.Eirk_mode_hard = 0;
    info.Ephy_mode_easy = 0;
    info.Ephy_mode_norm = 0;
    info.Ephy_mode_hard = 0;

    info.game_end = 0;
    info.unk0F_1 = 0;

    info.unk10 = 0;
    info.unk12 = 0;

    info.last_suspend_slot = 0;
    info.last_game_save_id = 0;

    for (i = 0; i < 0xC; i++)
        info.cleared_playthroughs[i] = 0;

    for (i = 0; i < 0x20; i++)
        info.SuppordRecord[i] = 0;

    for (i = 0; i < 0x20; i++)
        info.charKnownFlags[i] = 0;

    WriteGlobalSaveInfo(&info);

    /* Genuinely-blank SRAM is being initialized -- also stamp the current
     * expansion save metadata record (issue #2 slice 1) so this save is
     * classified SAVE_COMPAT_CURRENT from now on. */
    {
        struct ExpansionSaveMeta meta;

        BuildCurrentExpansionSaveMeta(&meta);
        WriteAndVerifySramFast(&meta, &gSram->expansionSaveMeta, sizeof(meta));
    }
#ifdef MODERN
    gSramBootFlags |= SRAM_BOOT_FLAG_WRITES_ALLOWED;
#endif
}

bool EnsureGlobalSaveInfoLoaded(struct GlobalSaveInfo *buf)
{
    /*
     * Issue #2 slice 1 (review fix): shared safe-init helper for every
     * gameplay call site that used to do:
     *
     *     if (!ReadGlobalSaveInfo(&info)) {
     *         InitGlobalSaveInfodata();
     *         ReadGlobalSaveInfo(&info);
     *     }
     *
     * That pattern silently equated "ReadGlobalSaveInfo() failed" with
     * "SRAM is blank", so it also wiped/reinitialized on top of corrupt,
     * newer, older, or save-config-incompatible expansion data. Only a
     * raw classification of SAVE_COMPAT_EMPTY may trigger the wipe done
     * by InitGlobalSaveInfodata(); every other non-current state must be
     * left byte-for-byte untouched and must not be reinterpreted as a
     * writable struct. Returns false (with *buf left unmodified) when the
     * caller must not proceed to read/write the global save info block.
     */
    if (ReadGlobalSaveInfo(buf))
        return true;

    if (SAVE_COMPAT_EMPTY != ClassifySramSaveCompat())
        return false;

    InitGlobalSaveInfodata();
    return ReadGlobalSaveInfo(buf);
}

void EraseBonusContentData(void)
{
    u8 *buf = gGenericBuffer;
    CPU_FILL(0, buf, 0x144, 16);
    SaveBonusContentData(buf);
}

void * SramOffsetToAddr(u16 off)
{
    return (u8 *)gSram + off;
}

u16 SramAddrToOffset(void * addr)
{
    return ((u8 *)addr) - (u8 *)gSram;
}

bool ReadSaveBlockInfo(struct SaveBlockInfo *chunk, int index)
{
    struct SaveBlockInfo tmp;
    u32 magic;

    if (NULL == chunk)
        chunk = &tmp;

    ReadSramFast(&gSram->saveBlockInfo[index], chunk, sizeof(struct SaveBlockInfo));

    if (SAVEMAGIC16 != chunk->magic16)
        return false;

    switch (index) {
    case SAVE_ID_GAME0:
    case SAVE_ID_GAME1:
    case SAVE_ID_GAME2:
        magic = SAVEMAGIC32;
        break;

    case SAVE_ID_SUSPEND:    
    case SAVE_ID_SUSPEND_ALT:
        magic = SAVEMAGIC32;
        break;

    case SAVE_ID_ARENA:
        magic = SAVEMAGIC32_ARENA;
        break;

    case SAVE_ID_XMAP:
        magic = SAVEMAGIC32_XMAP;
        break;
    
    default:
        return false;
        break;
    } /* switch */

    if (chunk->magic32 != magic)
        return false;

    return VerifySaveBlockChecksum(chunk);
}

void WriteSaveBlockInfo(struct SaveBlockInfo *chunk, int index)
{

    chunk->magic16 = SAVEMAGIC16;
#if BUGFIX
    chuck->offset = SramAddrToOffset(GetSaveWriteAddr(index));
#else
    chunk->offset = (uintptr_t)GetSaveWriteAddr(index);
#endif

    if (index >= SAVE_ID_MAX)
        return;

    switch (chunk->kind) {
    case SAVEBLOCK_KIND_GAME:
        chunk->size = sizeof(struct GameSaveBlock);
        break;

    case SAVEBLOCK_KIND_SUSPEND:
        chunk->size = SRAM_SIZE_SUSPEND;
        break;

    case SAVEBLOCK_KIND_ARENA:
        chunk->size = SRAM_SIZE_MARENA;
        break;

    case SAVEBLOCK_KIND_XMAP:
        chunk->size = SRAM_SIZE_XMAP;
        break;

    case (u8)SAVEBLOCK_KIND_INVALID:
        chunk->size = 0;
        chunk->offset = 0;
        chunk->magic16 = 0;
        break;

    default:
        return;
    }

    PopulateSaveBlockChecksum(chunk);
    WriteAndVerifySramFast(chunk, &gSram->saveBlockInfo[index], sizeof(struct SaveBlockInfo));
}

void EraseSaveBlockInfo(int index)
{
    struct SaveBlockInfo chunk;

    if (index < SAVE_ID_MAX) {
        CpuFill16(0xFFFF, &chunk, sizeof(struct SaveBlockInfo));
        WriteAndVerifySramFast(
            &chunk,
            &gSram->saveBlockInfo[index],
            sizeof(struct SaveBlockInfo));
    }
}

void *GetSaveWriteAddr(int index)
{
    switch (index) {
        case SAVE_ID_GAME0:
            return &gSram->gameSaveBlocks[0];
            break;

        case SAVE_ID_GAME1:
            return &gSram->gameSaveBlocks[1];
            break;

        case SAVE_ID_GAME2:
            return &gSram->gameSaveBlocks[2];
            break;

        case SAVE_ID_SUSPEND:
            return &gSram->suspendSaveBlocks[0];
            break;

        case SAVE_ID_SUSPEND_ALT:
            return &gSram->suspendSaveBlocks[1];
            break;

        case SAVE_ID_ARENA:
            return &gSram->multiArenaBlock;
            break;

        case SAVE_ID_XMAP:
            return CART_SRAM + SRAM_OFFSET_XMAP;
            break;

        default:
            return NULL;
            break;
    }
}

void *GetSaveReadAddr(int index)
{
    struct SaveBlockInfo chunk;
    ReadSaveBlockInfo(&chunk, index);
    return SramOffsetToAddr(chunk.offset);
}

void WriteChapterFlags(void *sram_dest)
{
    WriteAndVerifySramFast(
        GetChapterFlagBits(),
        sram_dest,
        GetChapterFlagBitsSize());
}

void WritePermanentFlags(void *sram_dest)
{
    WriteAndVerifySramFast(
        GetPermanentFlagBits(),
        sram_dest,
        GetPermanentFlagBitsSize());
}

void ReadChapterFlags(void *ewram_dest)
{
    ReadSramFast(
        ewram_dest,
        GetChapterFlagBits(),
        GetChapterFlagBitsSize());
}

void ReadPermanentFlags(void *ewram_dest)
{
    ReadSramFast(
        ewram_dest,
        GetPermanentFlagBits(),
        GetPermanentFlagBitsSize());
}

void ReadPermanentFlags_ret(const void *sram_src, void *ewram_dest)
{
    ReadSramFast(
        sram_src,
        ewram_dest,
        GetPermanentFlagBitsSize());
}

void WriteSupplyItems(void *sram_dest)
{
    const unsigned short *items = GetConvoyItemArray();
    unsigned char *cur;
    int i, item_use, var0, var1;
    unsigned char buf[176];
    cur = &buf[100];
    var1 = 0;

    for (i = 0; i < CONVOY_ITEM_COUNT; i++) {
        buf[i] = items[0];
        item_use = ITEM_USES(items[0]) & 0x3F;
        var0 = var1 & 0x7;
        *cur = 
            (*cur & sConvySavePackMask1[var0]) |
            (item_use << var0);

        if (var0 > 1) {
            cur++;
            if (var0 > 2) {
                *cur =
                    (*cur & sConvySavePackMask2[var0]) |
                    (item_use >> (8 - var0));
            }
        }
        var1 += 6;
        ++items;
    }

    WriteAndVerifySramFast(buf, sram_dest, GAMESAVE_SIZE_SUPPLY);
}

void ReadSupplyItems(const void *sram_src)
{
    unsigned char buf[GAMESAVE_SIZE_SUPPLY];
    unsigned short *items;
    unsigned char *cur, item_use;
    int i, var0, var1;

    ReadSramFast(sram_src, buf, sizeof(buf));
    items = GetConvoyItemArray();
    cur = &buf[100];
    var1 = 0;

    for (i = 0; i < CONVOY_ITEM_COUNT; i++) {
        items[0] = buf[i];
        var0 = var1 & 0x7;
        item_use = (*cur & ~sConvySavePackMask1[var0]) >> var0;

        if (var0 > 1) {
            cur++;

            if (var0 > 2) {
                item_use |= (*cur & ~sConvySavePackMask2[var0]) << (8 - var0);
            }
        }

        items[0] |= item_use << 8;
        var1 += 6;
        items++;
    }

}

bool null_true(void)
{
    return true;
}

bool IsExtraLinkArenaEnabled(int index __attribute__((unused)))
{
    int i;

    if (!IsSramWorking())
        return 0;

    for (i = 0; i < 3; i++)
        if (IsGameSaveNotFirstChapter(i))
            return 1;

    return IsMultiArenaSaveReady();
}

bool IsExtraSoundRoomEnabled(void)
{
    return 1;
}

bool IsExtraSupportViewerEnabled(void)
{
    int tmp0 = GGM_IsAnyCharacterKnown(NULL);
    int tmp1 = IsGamePlayedThrough();
    return tmp1 & tmp0;
}

u32 GetRankDataValidBitMap(void)
{
    struct GameRankSaveDataPacks buf;
    u32 attr = 0;
    u8 ret = IsGamePlayedThrough();
    if (!ret)
        return 0;

    if (LoadAndVerfyRankData(&buf)) {
        if (buf.pack[0].valid)
            attr  = 1 << 0x0;
    
        if (buf.pack[1].valid)
            attr |= 1 << 0x1;
    
        if (buf.pack[2].valid)
            attr |= 1 << 0x2;
    
        if (buf.pack[3].valid)
            attr |= 1 << 0x3;
    
        if (buf.pack[4].valid)
            attr |= 1 << 0x4;
    
        if (buf.pack[5].valid)
            attr |= 1 << 0x5;
    }
    return attr;
}

bool IsValidExtraMapAvilable(void)
{
    struct GlobalSaveInfo buf;

    if (!ReadGlobalSaveInfo(&buf))
        return false;

    if (!IsExtraMapAvailable())
        return false;
    else
        return true;
}

bool IsExtraFreeMapEnabled(void)
{
    int i;

    if (!IsSramWorking())
        return 0;

    for (i = 0; i < 3; i++)
        if (IsGameSaveComplete(i))
            return true;

    return false;
}

bool IsExtraBonusClaimEnabled(void)
{
    struct PlaySt playSt __attribute__((unused));
    struct BonusClaimEnt * buf1;
    int i, ret;

    if (LoadBonusContentData((void *)gGenericBuffer)) {

        ret = 0;
        buf1 = (void*)gGenericBuffer;
    
        for (i = 0; i < 0x10; i++) {
            if (!buf1[i].unseen)
                continue;
    
            if (BONUSKIND_ITEM0 == buf1[i].kind)
                ret = true;

            if (BONUSKIND_MONEY == buf1[i].kind)
                ret = true;
        }

        if (0 == ret)
            return false;
        else
            return true;
    }
    return 0;
}

int GetUnitsAverageSupportValue(const int unitA, const int unitB)
{
    int i;


    for (i = 0; 0 != sSupportUnkLut[i][0]; i++) {
        if (sSupportUnkLut[i][0] == unitA)
            if (sSupportUnkLut[i][1] != unitB)
                return 2;

        if (sSupportUnkLut[i][0] == unitB)
            if (sSupportUnkLut[i][1] != unitA)
                return 2;
            
        if (sSupportUnkLut[i][1] == unitA)
            if (sSupportUnkLut[i][0] != unitB)
                return 2;

        if (sSupportUnkLut[i][1] == unitB)
            if (sSupportUnkLut[i][0] != unitA)
                return 2;
    }

    return 3;
}

int GetTotalAverageSupportValue(void)
{
    int ret = 0;
    struct SupportTalkEnt *buf = GetSupportTalkList();

    for (; 0xFFFF != buf->unitA; buf++)
        ret += GetUnitsAverageSupportValue(buf->unitA, buf->unitB);

    return ret;
}

int GetTotalGlobalSupportValue(struct GlobalSaveInfo * buf)
{
    int i, j, tmp1, tmp2, ret = 0;
    unsigned char *SuppordRecord __attribute__((unused));
    struct GlobalSaveInfo tmp_header;

    if (0 == buf) {
        buf = &tmp_header;
        ReadGlobalSaveInfo(buf);
    }

    for (i = 0; i < 0x20; i++) {
        for (j = 0; j < 4; j++) {
            tmp1 = 1 + i;
            tmp2 = buf->SuppordRecord[tmp1 - 1];
            ret += (tmp2 >> (j << 1)) & 3;
        }
    }

    return ret;
}

int GetTotalSupportCollection(void)
{
    int tmp0 = GetTotalGlobalSupportValue(0);
    int tmp1 = GetTotalAverageSupportValue();

    if ((tmp0 > 0) && (0 == ((tmp0 * 100) / tmp1)))
            tmp0 = 1;
    else
        tmp0 = (tmp0 * 100) / tmp1;

    if (tmp0 > 100)
        tmp0 = 100;
    
    return tmp0;
}

int GetGlobalBestSupport(int unitA, int unitB, struct GlobalSaveInfo *info)
{
    struct GlobalSaveInfo local_info;
    int i = 0;
    int ret = 0;
    int tmp0, tmp1, tmp2 __attribute__((unused)), tmp3 __attribute__((unused));
    unsigned char *SuppordRecord __attribute__((unused));
    struct SupportTalkEnt *cur = GetSupportTalkList();

    if (info == NULL) {
        info = &local_info;
        ReadGlobalSaveInfo(info);
    }

    for (; cur->unitA != 0xFFFF; i++, cur++) {
        
        if (cur->unitA == unitA && cur->unitB == unitB)
            break;
    
        if (cur->unitA == unitB && cur->unitB == unitA)
            break;
    }

    tmp0 =  i >> 2;
    tmp1 = (3 & i) << 1;
    ret = 3 & info->SuppordRecord[tmp0] >> tmp1;
    return ret;
}

void GetGlobalSupportListFromSave(int unitId, u8* data, struct GlobalSaveInfo* info)
{
    struct GlobalSaveInfo local_info;
    struct SupportTalkEnt* ptr;
    int i;
    int j;

    if (gCharacterData[unitId-1].pSupportData == 0) {
        for (i = 0; i < UNIT_SUPPORT_MAX_COUNT; data++, i++)
            *data = 0;

        return;
    }

    j = 0;
    ptr = GetSupportTalkList();

    if (info == NULL) {
        info = &local_info;
        ReadGlobalSaveInfo(info);
    }

    for (; ; j++, ptr++) {
        int tmp1, tmp2;

        if (ptr->unitA == 0xFFFF)
            break;

        if ((ptr->unitA != unitId) && (ptr->unitB != unitId))
            continue;

        tmp1 = j >> 2;
        tmp2 = (j & 3) << 1;

        for (i = 0; i < gCharacterData[unitId-1].pSupportData->supportCount; i++) {

            if ((ptr->unitA != gCharacterData[unitId-1].pSupportData->characters[i]) &&
                (ptr->unitB != gCharacterData[unitId-1].pSupportData->characters[i])) {
                continue;
            }

            data[i] = (info->SuppordRecord[tmp1] >> (tmp2)) & 3;

            break;
        }
    }

    for (i = gCharacterData[unitId-1].pSupportData->supportCount; i < UNIT_SUPPORT_MAX_COUNT; i++) {
        data[i] = 0;
    }

    return;
}

bool UpdateBestGlobalSupportValue(int unitA, int unitB, int supportRank) {
    int convo;
    int var0;
    int var1;
    struct GlobalSaveInfo info;
    struct SupportTalkEnt* ptr;

    supportRank = supportRank & 3;

    if (!ReadGlobalSaveInfo(&info)) {
        return 0;
    }

    convo = 0;

    for (ptr = GetSupportTalkList(); ; ptr++) {

        if (ptr->unitA == 0xFFFF)
            break;

        if ((ptr->unitA == unitA) && (ptr->unitB == unitB))
            break;

        if ((ptr->unitA == unitB) && (ptr->unitB == unitA))
            break;

        convo++;
    }

    var0 = convo >> 2;
    var1 = (convo & 3) << 1;

    if (((info.SuppordRecord[var0] >> var1) & 3) >= (supportRank))
        return false;

    info.SuppordRecord[var0] &= ~(3 << var1);
    info.SuppordRecord[var0] += (supportRank << var1);

    WriteGlobalSaveInfo(&info);

    return true;
}

void SGM_SetCharacterKnown(s32 charId, struct GlobalSaveInfo* buf)
{
  s32 boolLoadedSecureHeader = 0;
  struct GlobalSaveInfo tmp_header;
  
  if (charId > 256) {
    return;
  }
  if (buf == NULL) {
    buf = &tmp_header;
    ReadGlobalSaveInfo(buf);
    boolLoadedSecureHeader = 1;
  }
  
  buf->charKnownFlags[charId >> 3] |= 1 << (charId & 7);
  
  if (boolLoadedSecureHeader) {
    WriteGlobalSaveInfo(buf);
  }
}

bool GGM_IsCharacterKnown(int index, struct GlobalSaveInfo *buf)
{
    struct GlobalSaveInfo tmp_header;
    u32 _index = index;

    if (index > 0x100)
        return 0;

    if (0 == buf) {
        buf = &tmp_header;
        ReadGlobalSaveInfo(&tmp_header);
    }

    if (1 & buf->charKnownFlags[index >> 3] >> (_index % 8))
        return 1;
    else
        return 0;
}

int GGM_IsAnyCharacterKnown(struct GlobalSaveInfo *buf)
{
    int i;
    struct GlobalSaveInfo tmp_header;

    if (NULL == buf) {
        buf = &tmp_header;
        ReadGlobalSaveInfo(&tmp_header);
    }

    for (i = 0; i < 0x20; i++) {
        if (0 != buf->charKnownFlags[i])
            return 1;
    }
    return 0;
}

void BmSave_NopStub2(void) {}

void __malloc_unlock_3(void) {}

int IsGamePlayedThrough(void)
{
    struct GlobalSaveInfo tmp_header;

    if (!ReadGlobalSaveInfo(&tmp_header))
        return 0;

    if (0 == tmp_header.completed )
        return 0;
    else
        return 1;
}

bool LoadAndVerfyRankData(void *buf)
{
    struct GameRankSaveDataPacks *_buf = buf;

    if (!IsSramWorking())
        return 0;

    if (NULL == _buf)
        _buf = (void*)gGenericBuffer;

    ReadSramFast(
        &gSram->gameRankSave,
        (void*)_buf,
        sizeof(struct GameRankSaveDataPacks)
    );

    if (_buf->magic0 != Checksum16((void*)_buf, 0x90))
        return 0;
    else
        return 1;
}

bool LoadBonusContentData(void * buf)
{
    struct BonusClaimSaveData * _buf = buf;
    
    if (!IsSramWorking())
        return 0;

    if (0 == _buf)
        _buf = (void*)gGenericBuffer;

    ReadSramFast(
        &gSram->bonusClaim,
        (void *)_buf,
        sizeof(gSram->bonusClaim)
    );

    if (_buf->cksum16 != Checksum16(_buf, sizeof(_buf->bonus)))
        return 0;
    else
        return 1;
}

void SaveBonusContentData(void * buf)
{
    struct BonusClaimSaveData * _buf = buf;
    _buf->cksum16 = Checksum16(_buf, sizeof(_buf->bonus));
    WriteAndVerifySramFast(buf, &gSram->bonusClaim, sizeof(gSram->bonusClaim));
}

void SaveRankings(void * buf)
{
    struct GameRankSaveDataPacks *_buf = buf;

    _buf->magic0 = Checksum16(buf, 0x90);

    WriteAndVerifySramFast(
        buf,
        &gSram->gameRankSave,
        sizeof(struct GameRankSaveDataPacks)
    );
}

void EraseSaveRankData(void)
{
    u16 _buf[sizeof(struct GameRankSaveDataPacks) / 2];

    CpuFill16(0, _buf, sizeof(struct GameRankSaveDataPacks));
    SaveRankings(_buf);
}

int GetNextChapterMode(void)
{
    return gPlaySt.chapterModeIndex - 1;
}

int GetSavedRankData(void *buf, int chapter_mode, int difficulty)
{
    struct GameRankSaveDataPacks _buf;
    struct GameRankSaveData *src;
    struct GameRankSaveData *dest = buf;

    CpuFill16(0, buf, 0x18);
    CpuFill16(0, &_buf, sizeof(_buf));

    if (0 != LoadAndVerfyRankData(&_buf)) {
        src = &_buf.pack[(chapter_mode + difficulty * 3)];
        *dest = *src;
        return 1;
    }
    
    return 0;
}

void SaveNewRankData(void *buf, int chapter_mode, int difficulty)
{
    struct GameRankSaveDataPacks _buf;
    struct GameRankSaveData *src = buf;

    if (0 != LoadAndVerfyRankData(&_buf)) {
        _buf.pack[chapter_mode + difficulty * 3] = *src;
        SaveRankings(&_buf);
    }
}

u8 JudgeGameRankSaveData(struct GameRankSaveData *old, struct GameRankSaveData *new)
{
    int newtime, oldtime;
    
    if (0 == old->valid)
        return 1;

    if (new->unk00_01 > old->unk00_01)
        return 1;
    else if (new->unk00_01 != old->unk00_01)
        return 0;

    if (new->luckydog != 0 && new->luckydog != old->luckydog)
        return 1;

    if (new->unk00_17 > old->unk00_17)
        return 1;

    if (new->gold > old->gold)
        return 1;
    else if (new->gold != old->gold)
        return 0;

    newtime = new->hours * 3600
         + new->minutes * 60
         + new->seconds;

    oldtime = old->hours * 3600
         + old->minutes * 60
         + old->seconds;

    if (newtime >= oldtime)
        return 0;

    return 1;
}

void GenerateGameRankSaveData(struct GameRankSaveData *buf, int chapter_mode, int difficulty)
{
    int i, j;
    int best = 0;
    u16 hours, minutes, seconds;

    CpuFill16(0, buf, sizeof(struct GameRankSaveData));

    buf->valid = 1;
    buf->chapter_mode = chapter_mode;
    buf->chapter_stat = difficulty;

    buf->gold = GetPartyTotalGoldValue();
    
    buf->unk00_16 = gPlaySt.unk_2B_00;
    buf->unk00_17 = gPlaySt.unk_2C_04;

    FormatTime(GetGameTotalTime(), &hours, &minutes, &seconds);
    buf->hours = hours;
    buf->minutes = minutes;
    buf->seconds = seconds;

    buf->cuteguy = 0;
    buf->luckydog = 0;

    for (i = 1; i < FACTION_GREEN; i++) {
        struct Unit *unit = GetUnit(i);

        if (!UNIT_IS_VALID(unit))
            continue;

        if (US_GROWTH_BOOST & unit->state) {
            if (US_DEAD & unit->state)
                break;
            
            buf->luckydog = unit->pCharacterData->number;
            break;
        }
    }

    for (j = 1; j < FACTION_GREEN; j++) {
        struct Unit *unit = GetUnit(j);

        if (0 == UNIT_IS_VALID(unit))
            continue;

        if (0 != ((CA_LOCK_1 | CA_STEAL) & unit->state))
            continue;

        if (PidStatsGetFavval(unit->pCharacterData->number) <= best)
            continue;

        best = PidStatsGetFavval(unit->pCharacterData->number);
        buf->cuteguy = unit->pCharacterData->number;
    }

    buf->tacticsRank = GetGameTacticsRank();
    buf->fundsRank = GetGameFundsRank();
    buf->survivalRank = GetGameSurvivalRank();
    buf->expRank = GetGameExpRank();
    buf->combatRank = GetGameCombatRank();

    buf->unk00_01 = GetOverallRank(buf->tacticsRank, buf->survivalRank, buf->fundsRank, buf->expRank, buf->combatRank);
    buf->unk08_15 = GetCurCompleteChapters();
    strcpy((void*)&buf->tactician_name, GetTacticianName());
}

void SaveEndgameRankings(void)
{
    struct GameRankSaveData old, new;

    int chapter_mode = GetNextChapterMode();
    int difficult = 1 & gPlaySt.chapterStateBits >> 6;

    GenerateGameRankSaveData(&new, chapter_mode, difficult);
    GetSavedRankData(&old, chapter_mode, difficult);

    if (0 != JudgeGameRankSaveData(&old, &new))
        SaveNewRankData(&new, chapter_mode, difficult);
}

void EraseSoundRoomSaveData(void)
{
    struct SoundRoomSaveData buf;
    
    CpuFill16(0, &buf, sizeof(buf));
    WriteSoundRoomSaveData(&buf);
}

bool LoadAndVerifySoundRoomData(struct SoundRoomSaveData * buf)
{
    struct SoundRoomSaveData tmp;

    if (!IsSramWorking())
        return false;

    if (NULL == buf)
        buf = &tmp;

    ReadSramFast(&gSram->soundRoomSave, buf, sizeof(struct SoundRoomSaveData));

    if (buf->magic1 != Checksum16(buf, sizeof(struct SoundRoomSaveData) - 4))
        return false;
    else
        return true;
}

void WriteSoundRoomSaveData(struct SoundRoomSaveData * buf)
{
#ifdef MODERN
    if (!(gSramBootFlags & SRAM_BOOT_FLAG_WRITES_ALLOWED))
        return;
#endif

    buf->magic1 = Checksum16(buf, sizeof(struct SoundRoomSaveData) - 4);
    WriteAndVerifySramFast(buf, &gSram->soundRoomSave, sizeof(struct SoundRoomSaveData));
}

bool IsSoundRoomSongUnlocked(struct SoundRoomSaveData * buf, int val)
{
    struct SoundRoomSaveData tmp;
    u32 _val = val;

    if (buf == NULL) {
        buf = &tmp;
        LoadAndVerifySoundRoomData(&tmp);
    }

    if ((buf->flags[val >> 5] >> (_val % 0x20)) & 1)
        return true;

    return false;
}

void UnlockSoundRoomSong(struct SoundRoomSaveData * buf, int val)
{
    struct SoundRoomSaveData tmp;
    u32 _val = val;
    
    if (buf == NULL) {
        buf = &tmp;
        if (!LoadAndVerifySoundRoomData(&tmp))
            return;
    }

    if (buf->flags[val >> 5] & (1 << (_val % 0x20)))
        return;

    buf->flags[val >> 5] |= 1 << (_val % 0x20);

    if (0x43 == val)
        buf->flags[0] |= 4;
    else if (2 == val)
        buf->flags[2] |= 8;

    if (0x54 == val)
        buf->flags[1] |= 1 << 0x10;
    else if (0x30 == val)
        buf->flags[2] |= 1 << 0x14;

    WriteSoundRoomSaveData(buf);
}

void EraseLinkArenaStruct2(void)
{
    struct bmsave_unkstruct2 buf;
    
    CpuFill16(0, (void*)&buf, sizeof(buf));
    WriteLinkArenaStruct2(&buf);
}

bool LoadAndVerfyLinkArenaStruct2(void * buf)
{
    struct bmsave_unkstruct2 tmp, * _buf = buf;

    if (!IsSramWorking())
        return 0;

    if (0 == _buf)
        _buf = &tmp;

    ReadSramFast(&gSram->unkstruct2, (void*)_buf, sizeof(struct bmsave_unkstruct2));

    if (_buf->magic1 != Checksum16((u16*)_buf, sizeof(struct bmsave_unkstruct2) - 4))
        return 0;
    else
        return 1;
}

void WriteLinkArenaStruct2(struct bmsave_unkstruct2 * buf)
{
    buf->magic1 = Checksum16((u16 *)buf, sizeof(struct bmsave_unkstruct2) - 4);

    WriteAndVerifySramFast((void*)buf,
                           &gSram->unkstruct2,
                           sizeof(struct bmsave_unkstruct2));
}

int ModifySaveLinkArenaStruct2A(void * buf, int val)
{
    struct bmsave_unkstruct2 tmp;
    struct bmsave_unkstruct2 * _buf;
    u32 _val = val;

    if (0 == buf) {
        buf = &tmp;
        LoadAndVerfyLinkArenaStruct2(&tmp);
    }

    _buf = buf;
    if (1 & (_buf->unk[val >> 5] >> (_val % 0x20)))
        return 1;
    else
        return 0;
}

void ModifySaveLinkArenaStruct2B(struct bmsave_unkstruct2 * buf, int val)
{
    struct bmsave_unkstruct2 tmp;
    u32 _val = val;
    
    if (NULL == buf) {
        buf = &tmp;
        
        if (!LoadAndVerfyLinkArenaStruct2(&tmp))
            return;
    }

    if (buf->unk[val >> 5] & (1 << (_val % 0x20)))
        return;

    buf->unk[val >> 5] |= (1 << (_val % 0x20));
    WriteLinkArenaStruct2(buf);
}

void EraseSramDataIfInvalid(void)
{
#ifdef MODERN
    enum SaveCompatState state;

    gSramBootFlags = 0;

    /*
     * Issue #2 slice 1: only a uniformly erased SRAM state (hardware
     * 0xFF or deterministic emulator/movie 0x00) may trigger the full-SRAM
     * wipe done by InitGlobalSaveInfodata().
     * Previously this checked `!ReadGlobalSaveInfo(NULL)`, which is also
     * true for corrupt, newer, older, or save-config-incompatible data --
     * silently destroying all 32 KiB of valid-but-unrecognized SRAM before
     * any UI/tooling ever gets a chance to classify it. Valid legacy/
     * vanilla saves, corrupt saves, and every other non-blank state must
     * be left byte-for-byte untouched here; see docs/save_format.md.
     */
    state = ClassifySramSaveCompat();

    if (state == SAVE_COMPAT_EMPTY)
    {
        InitGlobalSaveInfodata();
        gSramBootFlags |= SRAM_BOOT_FLAG_DATA_INITIALIZED;
    }
    else if (state == SAVE_COMPAT_CURRENT)
    {
        gSramBootFlags |= SRAM_BOOT_FLAG_WRITES_ALLOWED;
    }

    /*
     * Every remaining verifier can repair its own bounded auxiliary
     * record. That is safe only after EMPTY became CURRENT, or when the
     * input was already CURRENT. Non-current saves stay untouched for the
     * compatibility dialog/host tooling.
     */
    if (state != SAVE_COMPAT_EMPTY && state != SAVE_COMPAT_CURRENT)
        return;
#else
    if (SAVE_COMPAT_EMPTY == ClassifySramSaveCompat())
        InitGlobalSaveInfodata();
#endif

    if (!LoadBonusContentData(NULL))
        EraseBonusContentData();
    
    if (!LoadAndVerfyRankData(NULL))
        EraseSaveRankData();
    
    if (!LoadAndVerifySoundRoomData(NULL))
        EraseSoundRoomSaveData();
    
    if (!LoadAndVerfyLinkArenaStruct2(NULL))
        EraseLinkArenaStruct2();
    
    LoadAndVerfySuspendSave();
}
