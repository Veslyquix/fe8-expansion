#include "localized_game_text.h"
#include "types.h"

typedef char english_msg_buffer_size[
    (sizeof(struct MsgBuffer) == 0x1000u) ? 1 : -1];
typedef char english_primary_bytes[
    (sizeof(((struct MsgBuffer *)0)->buffer1) == 0x555u) ? 1 : -1];
typedef char english_secondary_bytes[
    (sizeof(((struct MsgBuffer *)0)->buffer2) == 0x555u) ? 1 : -1];
typedef char english_insert_bytes[
    (sizeof(((struct MsgBuffer *)0)->buffer3) == 0x356u) ? 1 : -1];
typedef char english_cjk_disabled[
    (FE8_LOCALIZED_GAME_TEXT_CJK_PROFILE_ENABLED == 0) ? 1 : -1];

int main(void)
{
    return 0;
}
