#include "localized_game_text.h"
#include "types.h"

typedef char cjk_profile_enabled[
    (FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED == 1) ? 1 : -1];
typedef char cjk_floor_storage[
    (sizeof(struct MsgBuffer) == 0x1600u) ? 1 : -1];
typedef char cjk_legacy_offsets_preserved[
    (sizeof(((struct MsgBuffer *)0)->storage.legacy) == 0x1000u) ? 1 : -1];
typedef char cjk_primary_offset_preserved[
    (sizeof(((struct MsgBuffer *)0)->storage.legacy.buffer1) == 0x555u) ? 1 : -1];

int main(void)
{
    return 0;
}
