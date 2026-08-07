#ifndef GUARD_LOCALIZED_GAME_TEXT_RUNTIME_HOST_BMITEM_H
#define GUARD_LOCALIZED_GAME_TEXT_RUNTIME_HOST_BMITEM_H

struct ItemData
{
    int nameTextId;
};

int GetItemIndex(int item);
const struct ItemData *GetItemData(int item);

#endif
