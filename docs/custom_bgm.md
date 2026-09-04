# Custom BGM (`NIMAP2`)

Adds community custom music support: a General-MIDI-shaped instrument map, a
percussion "drumfix", and custom songs appended past vanilla's song table.
All of it is gated on the `NIMAP2` flag in [`config.mk`](../config.mk).

Everything here lives in the repository. Nothing at build time reads the
upstream BGM pack, a vanilla ROM, or anything else outside the checkout.

---

## What the flag turns on

| Piece | Files | Effect |
| --- | --- | --- |
| **NIMAP2 instrument map** | `sound/voicegroups/voicegroup000_nimap2.s` | Replaces `voicegroup000` with a 128-slot General MIDI instrument map. Vanilla fills only 23 of those slots; the rest are dummy square waves. |
| **Drumfix** | `sound/voicegroups/voicegroup0{79,80,81,83,84}_nimap2.s` | Fills 44 empty percussion slots so GM drum-track note numbers hit real percussion samples. |
| **Custom songs** | `sound/songs/bgm/*.s` | Song bodies, appended to `gSongTable` after vanilla's 1000 entries. |
| **Song IDs** | `include/constants/songs.h` | `SONG_BGM_*` constants for the appended entries. |

Custom songs point their `_grp` at `voicegroup000`, which is why the map has to
live there rather than at a spare index.

### Vanilla impact — read this before enabling

The **drumfix is vanilla-neutral**. All 44 entries it writes land on slots that
held dummy square waves, so every percussion voice vanilla actually plays is
untouched.

The **`voicegroup000` replacement is not**. `song001_agbfe3_bgm_opening` — the
title theme — is the one vanilla song that plays out of `voicegroup000`, and
NIMAP2 changes all 11 voice slots it uses. Most are subtle (one strings or
brass sample swapped for another), but slot 126 changes from a percussion
keysplit (`voicegroup083`) to a pitched sample, which is audible.

If you want vanilla's opening intact, either set `NIMAP2 = 0`, or give the
custom songs their own voicegroup: copy `voicegroup000_nimap2.s` to a free
index, drop `voicegroup000` from `MODERN_NIMAP2_VOICEGROUPS` in
[`modern.mk`](../modern.mk), and repoint each song's `_grp` in
`sound/songs/bgm/*.s`.

### Lane behavior

`NIMAP2` is **modern-lane only**, exactly like every other feature flag. The
archival legacy lane (`make legacy`) always builds vanilla's voicegroups and
the vanilla 1000-entry song table, so it stays byte-matching regardless of how
`NIMAP2` is set.

That works because:

* `SOUND_S_FILES` in [`Makefile`](../Makefile) globs
  `voicegroup[0-9][0-9][0-9].s`, not `*.s`, so the `_nimap2` variants are never
  assembled into the shared object list, and `sound/songs/bgm/` is not globbed
  at all.
* `sound/song_table.s` wraps its custom entries in `.if FE8_NIMAP2` and
  self-defaults that symbol to `0` when nothing defines it. Only the modern
  assembler is handed `--defsym FE8_NIMAP2=1` (see `MODERN_ASFLAGS`).

Each `voicegroupNNN_nimap2.s` defines the **same symbol** as its vanilla
counterpart — only the filename differs — so exactly one of each pair may be
linked. `modern.mk` drops the vanilla objects via `MODERN_ELF_NIMAP2_DROPPED`.

---

## Adding a song

1. Import the Sappy `.s` export:

   ```bash
   python3 scripts/sound/import_bgm.py /path/to/pack/s/Series/YourSong.s
   ```

2. Add a `gSongTable` entry inside the `.if FE8_NIMAP2` block at the end of
   [`sound/song_table.s`](../sound/song_table.s):

   ```
   	song YourSong, 1, 1
   ```

   `1, 1` is the music-player/priority pair vanilla map BGM uses.

3. Add the matching `SONG_BGM_*` constant to
   [`include/constants/songs.h`](../include/constants/songs.h), continuing the
   IDs past `0x3E7`.

4. Credit the arranger in [`CREDITS.md`](../CREDITS.md).

The build picks the new file up automatically — `modern.mk` globs
`sound/songs/bgm/*.s`.

### Why an importer is needed

The pack's `.s` files are ordinary GBA m4a track data and assemble against
`include/MPlayDef.s` unchanged, except for two exporter quirks GNU `as`
rejects (present in 42 of the pack's 171 songs):

* space-separated `.byte` operands (`.byte MODT 0`), and
* a `,byte` typo for `.byte`.

Upstream assembles through Event Assembler, whose `BYTE a b` *is*
space-separated, so both are purely syntactic. `import_bgm.py` rewrites them
and refuses to proceed if a rewrite would change the operand token sequence.

`verify_bgm.py` proves the result is byte-identical to upstream's own Event
Assembler output — it decodes the pack's `.event` file independently and diffs
it against the assembled object, comparing pointer words structurally (the two
representations place tracks at different absolute addresses):

```bash
python3 scripts/sound/verify_bgm.py /path/to/pack/s/Series/YourSong.event
```

---

## Regenerating the instrument maps

`scripts/sound/gen_nimap2.py` derives the committed voicegroup sources from
the upstream Event Assembler patch. It is **not** wired into the build; the
generated `.s` files are committed and are what the build consumes.

```bash
python3 scripts/sound/gen_nimap2.py --upstream /path/to/pack
```

Upstream ships this data as raw bytes written to hardcoded vanilla ROM offsets,
with sample pointers as absolute vanilla addresses. Neither survives into a
relocated build, so the generator:

* resolves every sample pointer back to its `DirectSoundData_*` symbol using
  [`reference/fe8u_symbols.txt`](../reference/fe8u_symbols.txt), letting the
  linker place samples wherever it likes; and
* translates the drumfix's absolute `ORG` offsets into
  `(voicegroup, entry index)` pairs, applying them to the committed vanilla
  voicegroup sources.

It errors out rather than guessing on any voice type
[`asm/macros/music_voice.inc`](../asm/macros/music_voice.inc) does not cover.

One case that macro genuinely cannot express is pan byte `0x80` ("forced pan,
value 0") — `_voice_directsound` re-derives the byte as
`pan ? (0x80 | pan) : 0`. The generator detects any entry whose pan byte would
not round-trip and emits explicit `.byte`/`.4byte` for it instead of silently
altering the panning. Three entries in the drumfix hit this.
