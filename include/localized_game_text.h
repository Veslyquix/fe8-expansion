#ifndef GUARD_LOCALIZED_GAME_TEXT_H
#define GUARD_LOCALIZED_GAME_TEXT_H

#include "gba/types.h"
#include "expansion_config.h"
#include "expansion_locale.h"

/* Optional generated contract. English/default and legacy builds do not
 * require this header and therefore retain their exact historical message
 * storage and code paths. FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES includes
 * the terminating NUL, matching LocalizedTextCodec_Decode. */
#if defined(__has_include)
#if __has_include("localized_game_text_data.h")
#include "localized_game_text_data.h"
#endif
#endif

#ifndef FE8_GAME_LOCALIZATION_DATA_PRESENT
#define FE8_GAME_LOCALIZATION_DATA_PRESENT 0
#endif

#ifndef FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES
#define FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES 0u
#endif

#ifndef FE8_GAME_LOCALIZATION_TARGET_COUNT
#define FE8_GAME_LOCALIZATION_TARGET_COUNT 0u
#endif

#define FE8_LOCALIZED_GAME_TEXT_TARGET_CAPACITY 0x1600u

#define FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER1_BYTES 0x555u
#define FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER2_BYTES 0x555u
#define FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER3_BYTES 0x356u
#define FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER4_BYTES 0x100u
#define FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER5_BYTES 0x100u

#if defined(MODERN) && ((FE8_EXPANSION_ENABLED_LOCALE_MASK & 0x06u) != 0)
#define FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED 1
#else
#define FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED 0
#endif

#define FE8_LOCALIZED_GAME_TEXT_REQUIRED_STORAGE_BYTES \
    ((FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES) \
        > FE8_LOCALIZED_GAME_TEXT_TARGET_CAPACITY \
        ? (FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES) \
        : FE8_LOCALIZED_GAME_TEXT_TARGET_CAPACITY)

#define FE8_LOCALIZED_GAME_TEXT_LEGACY_MSG_BUFFER_BYTES \
    (FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER1_BYTES \
        + FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER2_BYTES \
        + FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER3_BYTES \
        + FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER4_BYTES \
        + FE8_LOCALIZED_GAME_TEXT_LEGACY_BUFFER5_BYTES)

#define FE8_LOCALIZED_GAME_TEXT_MSG_BUFFER_BYTES \
    (FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED \
        ? FE8_LOCALIZED_GAME_TEXT_REQUIRED_STORAGE_BYTES \
        : FE8_LOCALIZED_GAME_TEXT_LEGACY_MSG_BUFFER_BYTES)

#define LOCALIZED_GAME_TEXT_STATIC_ASSERT(cond, tag) \
    typedef char localized_game_text_static_assert_##tag[(cond) ? 1 : -1]

LOCALIZED_GAME_TEXT_STATIC_ASSERT(
    FE8_LOCALIZED_GAME_TEXT_LEGACY_MSG_BUFFER_BYTES == 0x1000u,
    legacy_msg_buffer_is_exact_4k);
LOCALIZED_GAME_TEXT_STATIC_ASSERT(
    FE8_LOCALIZED_GAME_TEXT_REQUIRED_STORAGE_BYTES
        >= FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES,
    generated_max_fits_storage);

#define LOCALIZED_GAME_TEXT_MARKER_OVERFLOW "<!LOC_OVF!>"
#define LOCALIZED_GAME_TEXT_MARKER_CORRUPT  "<!LOC_BAD!>"
#define LOCALIZED_GAME_TEXT_MARKER_INVALID  "<!LOC_INV!>"

/* Explicit resolution status for renderer/integration work:
 * - ENGLISH_DEFAULT: the modern English bundle decoded for English/qps.
 * - ENGLISH_FALLBACK_*: a CJK request decoded the shared English bundle.
 * - DECODE_*: a generated entry was attempted and wrote a visible marker
 *   instead of silently succeeding. */
enum LocalizedGameTextStatus
{
    LOCALIZED_GAME_TEXT_STATUS_ENGLISH_DEFAULT = 0,
    LOCALIZED_GAME_TEXT_STATUS_OK = 1,
    LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_ABSENT = 2,
    LOCALIZED_GAME_TEXT_STATUS_ENGLISH_FALLBACK_UNPOPULATED = 3,
    LOCALIZED_GAME_TEXT_STATUS_DECODE_OVERFLOW = 4,
    LOCALIZED_GAME_TEXT_STATUS_DECODE_CORRUPT = 5,
    LOCALIZED_GAME_TEXT_STATUS_DECODE_INVALID = 6
};

enum LocalizedGameTextStatus LocalizedGameText_ResolveCurrentToBuffer(
    int msgIndex,
    char *buffer,
    u32 bufferCapacity,
    u32 *outDecodedLength);
enum LocalizedGameTextStatus LocalizedGameText_ResolveCurrentToUnboundedBuffer(
    int msgIndex,
    char *buffer,
    u32 *outDecodedLength);

void LocalizedGameText_InvalidateCache(void);
enum LocalizedGameTextStatus LocalizedGameText_GetLastStatus(void);

#endif /* GUARD_LOCALIZED_GAME_TEXT_H */
