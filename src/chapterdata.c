#include "global.h"
#include "chapterdata.h"
#include "agb_sram.h"
#include "bmsave.h"

/* chapter_settings.h (generated below from src/data/chapter_settings.json)
 * spells its .mapBgmIds entries as SONG_* constants rather than raw numbers. */
#include "constants/songs.h"

#include "src/data/chapter_settings.h"

const struct ROMChapterData* GetROMChapterStruct(unsigned chIndex) {
    if (chIndex == 0x7F)
        return gExtraMapInfo->chapter_info;

    return gChapterDataTable + chIndex;
}

const void* GetChapterMapPointer(unsigned chIndex) {
    if (chIndex != 0x7F)
        return gChapterDataAssetTable[GetROMChapterStruct(chIndex)->map.mainLayerId];

    ReadSramFast(GetExtraMapMapReadAddr(), gGenericBuffer, GetExtraMapMapSize());
    return gGenericBuffer;
}

const void* GetChapterMapChangesPointer(unsigned chIndex) {
    if (chIndex != 0x7F)
        return gChapterDataAssetTable[GetROMChapterStruct(chIndex)->map.changeLayerId];

    return gExtraMapInfo->map_change_info;
}

const struct ChapterEventGroup* GetChapterEventDataPointer(unsigned chIndex) {
    if (chIndex != 0x7F)
        return gChapterDataAssetTable[GetROMChapterStruct(chIndex)->mapEventDataId];

    return gExtraMapInfo->event_info;
}

const char * GetChapterTitleName(unsigned chIndex)
{
    if (chIndex != 0x7F)
        return GetStringFromIndex(GetROMChapterStruct(chIndex)->chapTitleTextId);

    return gExtraMapInfo->chapter_title;
}

u8 IsDifficultMode(void) {
    u8 difficultState = gPlaySt.chapterStateBits & PLAY_FLAG_HARD;
    return difficultState ? TRUE : FALSE;
}
