#include "global.h"

#if FE8_GAME_RANK

#include "bmunit.h"
#include "event.h"
#include "gamerank.h"

void GameRank_OnChapterInit(void)
{
    gPlaySt.rankChapterKills = 0;
    gPlaySt.rankTurnKills = 0;
    gPlaySt.rankChapterPowerScore = 0;
}

void GameRank_OnTurnStart(void)
{
    gPlaySt.rankTurnKills = 0;
}

void GameRank_OnEnemyUnitKilled(void)
{
    gPlaySt.rankChapterKills++;
    gPlaySt.rankTotalKills++;

    gPlaySt.rankTurnKills++;

    if (gPlaySt.rankTurnKills > gPlaySt.rankChapterPowerScore)
        gPlaySt.rankChapterPowerScore = gPlaySt.rankTurnKills;

    if (gPlaySt.rankTurnKills > gPlaySt.rankBestPowerScore)
        gPlaySt.rankBestPowerScore = gPlaySt.rankTurnKills;
}

u16 GameRank_GetChapterDeaths(void)
{
    return GetChapterDeathCount();
}

u16 GameRank_GetGameDeaths(void)
{
    return GetGameDeathCount();
}

u16 GameRank_GetChapterKills(void)
{
    return gPlaySt.rankChapterKills;
}

u16 GameRank_GetTotalKills(void)
{
    return gPlaySt.rankTotalKills;
}

u16 GameRank_GetChapterPowerScore(void)
{
    return gPlaySt.rankChapterPowerScore;
}

u16 GameRank_GetBestPowerScore(void)
{
    return gPlaySt.rankBestPowerScore;
}

void GameRank_Evt_LoadChapterDeaths(struct EventEngineProc* proc)
{
    gEventSlots[EVT_SLOT_1] = GameRank_GetChapterDeaths();
}

void GameRank_Evt_LoadGameDeaths(struct EventEngineProc* proc)
{
    gEventSlots[EVT_SLOT_1] = GameRank_GetGameDeaths();
}

void GameRank_Evt_LoadChapterKills(struct EventEngineProc* proc)
{
    gEventSlots[EVT_SLOT_1] = GameRank_GetChapterKills();
}

void GameRank_Evt_LoadTotalKills(struct EventEngineProc* proc)
{
    gEventSlots[EVT_SLOT_1] = GameRank_GetTotalKills();
}

void GameRank_Evt_LoadChapterPowerScore(struct EventEngineProc* proc)
{
    gEventSlots[EVT_SLOT_1] = GameRank_GetChapterPowerScore();
}

void GameRank_Evt_LoadBestPowerScore(struct EventEngineProc* proc)
{
    gEventSlots[EVT_SLOT_1] = GameRank_GetBestPowerScore();
}

#endif // FE8_GAME_RANK
