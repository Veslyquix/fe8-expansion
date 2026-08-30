# Map BGM randomization (`RAND_BGM`, `CONTINUE_BGM_BATTLE`)

Two independent, default-off config flags in [`config.mk`](../config.mk),
ported from the SRR FE randomizer project's BGM-randomization logic (see
[`CREDITS.md`](../CREDITS.md)) and adapted to this codebase's own decompiled
map-BGM path.

Both are modern-lane only, exactly like every other feature flag: the
archival legacy lane (`make legacy`) always builds vanilla's fixed BGM
selection, so it stays byte-matching regardless of how these are set.

---

## `RandBgm` (`FE8_RAND_BGM`)

When enabled, map BGM selection becomes seeded-random instead of vanilla's
fixed per-chapter table lookup.

### What changes

`src/bm.c` gains `GetBGMTrack(void)`, next to the existing
`GetCurrentMapMusicIndex(void)`:

* `FE8_RAND_BGM=0` (default): `GetBGMTrack()` just calls
  `GetCurrentMapMusicIndex()` -- vanilla behavior, unchanged.
* `FE8_RAND_BGM=1`: `GetBGMTrack()` picks a random song sharing the vanilla
  pick's music-player/priority pair (`gSongTable[].ms`/`.me` -- `1, 1` is the
  pair every vanilla map-BGM entry uses, e.g.
  `song004_agbfe3_bgm_wmap_01, 1, 1` in `sound/song_table.s`), instead of
  returning the vanilla chapter-table entry.

`GetCurrentMapMusicIndex()` itself is untouched and remains the fallback/
vanilla path -- it still owns the skirmish/victory-song threshold checks
(`SONG_GRASP_AT_VICTORY`), and `GetBGMTrack()` always defers to it verbatim
when that victory jingle would play, since that is a scripted cue rather
than generic wandering-around music.

Every call site that asks "what should be playing right now" now goes
through `GetBGMTrack()` instead of `GetCurrentMapMusicIndex()` directly:

* `StartMapSongBgm` (`src/bm.c`) -- starts map BGM (chapter load, phase
  starts).
* `PhaseIntroInitText` (`src/phasechangefx.c`) -- decides whether to fade
  out the current track at phase-change.
* `RestoreMapSongBgm` (`src/bmmind.c`) -- see `ContinueBgmBattle` below.

`src/VeslyDebugger.c`'s `VeslyDebugger_GetBgmOverride()` still wins over
either path in all three call sites (unchanged precedence): when a debug
override is active, `RandBgm` never overrides it.

### How the pick is seeded

The pick must be reproducible within a playthrough (so walking back onto a
tile doesn't change the song under your feet) but must not touch the live
combat RNG, and must not add any new save data. `GetBGMTrack()` uses:

* **Seed**: `gPlaySt.playthroughIdentifier`, an **existing** per-save byte
  assigned once at new-game start (see `src/bmsave.c`). No new save field is
  introduced -- this reuses a value that already round-trips through every
  save/suspend format, so `MODERN_SAVE_COMPAT_EPOCH` is untouched.
* **Mixed in**: the current `gPlaySt.chapterIndex`, `chapterTurnNumber`, and
  `faction` (phase), so the pick varies across chapters/turns/phases even
  within one playthrough.
* **Hash**: a private, stateless function (`RandBgmAdvanceHash`) using the
  *exact same recurrence* as `rng.c`'s `AdvanceGetLCGRNValue()`
  (`value = (v*4+2) * (v*4+3) >> 2`), but applied to a caller-local value
  instead of the shared `gLCGRNValue` global.

**Why not reuse `AdvanceGetLCGRNValue()`/`SetLCGRNValue()` directly**:
`gLCGRNValue` is continuously advanced every frame by cosmetic FX elsewhere
in the engine -- weather particles (`src/bmio.c`), face animation
(`src/face.c`), sparkle trails (`src/emitstarfx.c`), and more. Reseeding or
advancing that shared global from `GetBGMTrack()` would perturb those
effects every time a song is picked. Using the same math as a private,
parameterized function sidesteps that while still matching this repo's real
LCG constants (per the porting brief) instead of importing a different
generator from the upstream source.

**Why not `NextRN()`/`gRNSeeds`**: that is the live combat RNG stream.
Touching it here would mean walking around the map (which re-evaluates map
BGM at phase starts) could shift or be shifted by actual combat rolls --
exactly the coupling this port is required to avoid.

### Song eligibility and NIMAP2

Eligibility is determined purely by scanning `gSongTable[].ms`/`.me` for the
vanilla map-BGM pair (`1, 1`) across vanilla's first 1000 entries
(`gSongTable` IDs `0x000`-`0x3E7`; see `include/constants/songs.h`). This
naturally excludes the table's dummy/empty slots, which are all `ms=0,
me=0` -- no separate exceptions table or hardcoded address list is needed.

This codebase revision does not have the `NIMAP2` custom-BGM append (a
later revision's `config.mk` flag that appends extra songs past vanilla's
1000 entries with the same `1, 1` priority pair). If/when that flag is
present, widen `RANDBGM_SONG_COUNT` in `src/bm.c` under its own `#if
FE8_NIMAP2` the same way that flag's own doc documents appending song IDs,
so randomized picks can reach the appended songs too.

### Deliberately out of scope

The SRR source this was ported from also has a *separate*,
deliberately-non-deterministic `RandomizeBattleMusic` feature that
randomizes what plays *during* combat using the live combat RNG stream.
That is **not** what `RandBgm` does here -- `RandBgm` is scoped to map BGM
only (chapter/phase/turn granularity), matching the source's own
`GetBGMTrack()` doc comment ("fe7/fe8 only?"). Randomizing in-combat music
specifically was not requested and is not wired up; if that turns out to be
wanted, it should be a distinct flag so it can be reasoned about (and
turned off) independently of `RandBgm`.

---

## `ContinueBgmBattle` (`FE8_CONTINUE_BGM_BATTLE`)

When enabled, entering a battle animation keeps the current map BGM playing
instead of switching to a distinct battle theme.

### Correction: vanilla FE8 does switch BGM during combat

An earlier draft of this doc claimed `src/bmbattle.c` had no BGM code and
concluded vanilla FE8 never interrupts map BGM for ordinary combat. That was
wrong -- the real vanilla hook is `EkrPlayMainBGM()` / `EkrRestoreBGM()` in
`src/banim-efxsound.c`, called from the *Ekr* battle-animation controller in
`src/banim-ekrbattle.c` (`NewEkrBattle()` calls `EkrPlayMainBGM()` on combat
start; `ekrBattle_PostDragonStatusEffect()` calls `EkrRestoreBGM()` at
combat end), not `src/bmbattle.c` (which only holds combat *math*, not the
animation/BGM controller). This matches the original SRR installer's own ROM
hook (`ORG $726E2` into `EkrPlayMainBGM`, per the `.event` patch this feature
was ported from).

`EkrPlayMainBGM()` picks `SONG_ATTACK`/`SONG_DEFENSE` as a baseline, then
overrides it further for special cases (colosseum/link arena, promotion
scenes, boss themes via `gBanimBossBGMs[]`, dancer/healer themes) through
`EfxOverrideBgm()`, and sets `gEkrMainBgmPlaying = 1`. `EkrRestoreBGM()`
checks `gEkrMainBgmPlaying`: if it was never set (e.g. the vanilla
formation/hensei/`BM_FLAG_5` bail-out already in the function), it calls
`MakeBgmOverridePersist()` (a no-op-equivalent bookkeeping call) instead of
actually restoring anything.

### What the flag actually gates

`ContinueBgmBattle` short-circuits `EkrPlayMainBGM()` at its very top:

```c
void EkrPlayMainBGM(void)
{
#if FE8_CONTINUE_BGM_BATTLE
    gEkrMainBgmPlaying = 0;
    return;
#else
    ... (unmodified vanilla body) ...
#endif
}
```

This reuses vanilla's own "no override happened" state -- it's the exact
same `gEkrMainBgmPlaying = 0` the BM_FLAG_5 bail-out already produces a few
lines further down. No boss-theme, colosseum, or promotion-scene logic is
touched or duplicated; it's simply never reached when the flag is on.

`EkrRestoreBGM()` *does* also need a guard, though -- its vanilla
`gEkrMainBgmPlaying == false` path calls `MakeBgmOverridePersist()`
(`src/soundwrapper.c`), which unconditionally sets
`gSoundSt.songId = gSoundSt.unk2`. On the vanilla path `unk2` was populated
by `OverrideBgm()`'s own bookkeeping earlier; on the `ContinueBgmBattle`
path `OverrideBgm()` is never called at all, so `unk2` is stale/zero and
this zeroes `gSoundSt.songId` even though the map BGM is still playing
correctly. A later "is the right song playing?" check
(`GetCurrentBgmSong() != ...`) then sees a false mismatch and restarts the
track -- the exact "song restarts after battle" bug this was fixed for.
`EkrRestoreBGM()` is therefore also gated to a plain no-op under
`FE8_CONTINUE_BGM_BATTLE`, leaving `gSoundSt` untouched entirely.

`src/bmmind.c`'s `RestoreMapSongBgm()` (FE8U `0x080328B0`) is an unrelated
function -- a different vanilla address with genuinely zero callers anywhere
in this codebase's `src/` (checked against the three remaining
un-decompiled `asm/*.s` files too, no reference found). It still carries a
defensive `#if FE8_CONTINUE_BGM_BATTLE` no-op guard from this feature's
first draft; that's harmless (dead code either way) and left in place in
case it ever gains a caller, but it is **not** what makes `ContinueBgmBattle`
work -- `EkrPlayMainBGM()`/`EkrRestoreBGM()` above is the real mechanism.

---

## Build verification note

Both flags default to `0`. With both off, `GetBGMTrack()` and
`EkrPlayMainBGM()` compile to their vanilla-equivalent bodies -- a release
build with both flags at their default should be unaffected by this change.
