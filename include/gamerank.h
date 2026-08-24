#ifndef GUARD_GAMERANK_H
#define GUARD_GAMERANK_H

#if FE8_GAME_RANK

/* Called once at the start of every chapter (src/bmio.c's InitChapter) --
 * resets this-chapter kill tracking. Player-unit deaths need no reset here;
 * see GameRank_GetChapterDeaths below. */
void GameRank_OnChapterInit(void);

/* Called once at the start of every new turn (src/bm.c's SwitchPhases,
 * the FACTION_GREEN -> FACTION_BLUE transition) -- resets the current
 * turn's kill counter so GameRank_GetChapterPowerScore/GetBestPowerScore
 * can track its high-water mark. */
void GameRank_OnTurnStart(void);

/* Called from UnitKill (src/bmunit.c) whenever a FACTION_RED unit dies. */
void GameRank_OnEnemyUnitKilled(void);

/* Player-unit deaths this chapter / this save slot. Backed directly by
 * vanilla's GetChapterDeathCount()/GetGameDeathCount() (src/gamerankings.c):
 * permadeath keeps a dead unit's US_DEAD state (and bwl->deathLoc, the
 * chapter it died in) set for the rest of the playthrough, so no separate
 * GameRank storage is needed for deaths. */
u16 GameRank_GetChapterDeaths(void);
u16 GameRank_GetGameDeaths(void);

/* Enemies defeated this chapter / this save slot. */
u16 GameRank_GetChapterKills(void);
u16 GameRank_GetTotalKills(void);

/* "Power score": most enemies defeated in a single turn, this chapter /
 * this save slot. */
u16 GameRank_GetChapterPowerScore(void);
u16 GameRank_GetBestPowerScore(void);

/* Event-script bridges (see EV_CMD_ASMC / EvtAsmCall, include/eventscript.h):
 * each writes its stat into gEventSlots[EVT_SLOT_1] (include/event.h) so a
 * chapter's event script can reference a prior chapter's or the running
 * save-slot's game rank, e.g.:
 *
 *   EvtAsmCall(GameRank_Evt_LoadTotalKills),
 *   ... (branch/substitute using event slot 1) ...
 */
struct EventEngineProc;
void GameRank_Evt_LoadChapterDeaths(struct EventEngineProc* proc);
void GameRank_Evt_LoadGameDeaths(struct EventEngineProc* proc);
void GameRank_Evt_LoadChapterKills(struct EventEngineProc* proc);
void GameRank_Evt_LoadTotalKills(struct EventEngineProc* proc);
void GameRank_Evt_LoadChapterPowerScore(struct EventEngineProc* proc);
void GameRank_Evt_LoadBestPowerScore(struct EventEngineProc* proc);

#endif // FE8_GAME_RANK

#endif // GUARD_GAMERANK_H
