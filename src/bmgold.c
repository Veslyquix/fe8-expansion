#include "global.h"

#include "bmitem.h"
#include "bmunit.h"

#if FE8_PURCHASE_GENERICS
enum
{
    CHAPTER_GOLD_MAX = 999999,
    CHAPTER_GOLD_FACTION_COUNT = 3,
};

EWRAM_DATA static u32 sChapterGoldAmount[CHAPTER_GOLD_FACTION_COUNT] = {};
#endif

u32 GetPartyGoldAmount(void) {
    s8 id = gPlaySt.chapterIndex;
    if (id == 5) {
        return 0;
    }
    else {
        return gPlaySt.partyGoldAmount;
    }
}

void SetPartyGoldAmount(s32 amt) {
    gPlaySt.partyGoldAmount = amt;
    if (amt > 999999) {
        gPlaySt.partyGoldAmount = 999999;
    }
}

// addToPartyGold
void AddPartyGoldAmount(u32 amt) {
    s32 new_amt = gPlaySt.partyGoldAmount + amt;
    gPlaySt.partyGoldAmount = new_amt;
    if (new_amt > 999999) {
        gPlaySt.partyGoldAmount = 999999;
    }
}

#if FE8_PURCHASE_GENERICS
u32 GetChapterGoldAmount(void)
{
    return GetFactionChapterGoldAmount(FACTION_ID_BLUE);
}

void SetChapterGoldAmount(s32 amt)
{
    SetFactionChapterGoldAmount(FACTION_ID_BLUE, amt);
}

void AddChapterGoldAmount(u32 amt)
{
    AddFactionChapterGoldAmount(FACTION_ID_BLUE, amt);
}

void SubChapterGoldAmount(u32 amt)
{
    SubFactionChapterGoldAmount(FACTION_ID_BLUE, amt);
}

void ResetChapterGoldAmount(void)
{
    int i;

    for (i = 0; i < CHAPTER_GOLD_FACTION_COUNT; ++i)
        sChapterGoldAmount[i] = 0;
}

u32 GetFactionChapterGoldAmount(int factionId)
{
    if (factionId < 0 || factionId >= CHAPTER_GOLD_FACTION_COUNT)
        return 0;

    return sChapterGoldAmount[factionId];
}

void SetFactionChapterGoldAmount(int factionId, s32 amt)
{
    if (factionId < 0 || factionId >= CHAPTER_GOLD_FACTION_COUNT)
        return;

    if (amt < 0) {
        sChapterGoldAmount[factionId] = 0;
    } else if (amt > CHAPTER_GOLD_MAX) {
        sChapterGoldAmount[factionId] = CHAPTER_GOLD_MAX;
    } else {
        sChapterGoldAmount[factionId] = amt;
    }
}

void AddFactionChapterGoldAmount(int factionId, u32 amt)
{
    if (factionId < 0 || factionId >= CHAPTER_GOLD_FACTION_COUNT)
        return;

    if (amt > CHAPTER_GOLD_MAX || sChapterGoldAmount[factionId] > CHAPTER_GOLD_MAX - amt) {
        sChapterGoldAmount[factionId] = CHAPTER_GOLD_MAX;
    } else {
        sChapterGoldAmount[factionId] += amt;
    }
}

void SubFactionChapterGoldAmount(int factionId, u32 amt)
{
    if (factionId < 0 || factionId >= CHAPTER_GOLD_FACTION_COUNT)
        return;

    if (amt > sChapterGoldAmount[factionId]) {
        sChapterGoldAmount[factionId] = 0;
    } else {
        sChapterGoldAmount[factionId] -= amt;
    }
}
#endif
