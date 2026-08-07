#include "localized_game_text.h"
#include "types.h"

typedef char cjk_growth_storage[
    (sizeof(struct MsgBuffer) == 0x1601u) ? 1 : -1];
typedef char cjk_growth_bound[
    (sizeof(struct MsgBuffer) >= FE8_GAME_LOCALIZATION_MAX_DECODED_BYTES) ? 1 : -1];

int main(void)
{
    return 0;
}
