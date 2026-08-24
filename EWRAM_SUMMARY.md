# EWRAM Usage Summary

GBA EWRAM is 256 KiB (0x02000000-0x0203FFFF). This repo's linker script
(`linker/expansion.ld`) splits it into two kinds of region:

- **Persistent (`EWRAM_DATA`)** — a fixed, always-resident address for the
  life of the program. Symbols recovered directly from the linked ELF
  (`arm-none-eabi-nm -S`, filtered to addresses in `0x02000000-0x0203FFFF`)
  — this is more reliable than checking section names on individual `.o`
  files, since a few symbols (e.g. `debug_font_4bpp`) are typed as data
  pre-link but get routed into ROM by the linker script (this repo's
  `SHOULD_BE_CONST`/"data that should be const but was `.data` in the
  original binary" convention) — checking only the object file wrongly
  counts those against EWRAM.
- **Overlaid (`EWRAM_OVERLAY(group)`)** — every symbol tagged with the same
  group name starts at the *same* address (`__ewram_start`, see
  `linker/expansion.ld` lines ~33-151), so mutually-exclusive screens/systems
  share physical memory instead of each reserving their own. Only the
  **largest** group's size actually costs real EWRAM
  (`__ewram_overlay_peak_size = MAX(...)` across every group); persistent
  `ewram_data` starts right after that peak. Regenerate the numbers below
  with:
  ```bash
  arm-none-eabi-nm build/expansion-modern/debug/aapcs/fireemblem8.elf \
      | grep '__ewram_overlay_.*_size\|__ewram_overlay_peak_size'
  arm-none-eabi-nm -S --size-sort build/expansion-modern/debug/aapcs/fireemblem8.elf \
      | awk '{ addr = strtonum("0x" $1); if (addr >= 0x02000000 && addr < 0x02040000) print }'
  ```

## Overlay groups (share memory — only the largest one actually costs EWRAM)

| Group | Size | Contents / when active |
| --- | --- | --- |
| `banim` | **131,468 B (~128.4 KB) — current peak** | Battle animation engine state: `gBanimOaml`/`gBanimOamr2` (22 KB each, OAM), `gTmB_Banim`/`gTmA_Banim`, `gBuf_Banim`, `gBanimScrLeft`/`gBanimScrRight`, `gEkrKakudaiSomeBufLeft`/`Right`, `gEkrTsaBuffer`, `gUnk_Banim_Ekrbattle_0`, etc. (`src/banim-ekr*.c`, `src/banim-efx*.c`). Live only while a full battle animation is actually playing. |
| `gamestart` | 130,392 B (~127.3 KB) | New-game/intro sequence scratch state. Only live while starting a new game. |
| `0` (unlabeled) | 127,486 B (~124.5 KB) | Shared by most menu/prep screens: `prepscreen.c`, `bonusclaim.c`, `bmdifficulty.c`, `minimap.c`, `statscreen.c`, `savedraw.c`, `difficultymenu.c`, `bmtrade.c`, `convoymenu.c`, `bmmenu.c`, `bksel.c`, `bmio.c`, and — notably — **`mu.c`'s `gMUGfxBuffer`** (see below). Live only while the corresponding screen is open. |
| `worldmap` | 118,228 B (~115.5 KB) | World-map screen's own scratch region (legacy hardcoded offsets, mostly still-undecompiled `gUnk_*` symbols). Live only on the world map. |
| `gamestartsave` | 32,768 B (32 KB) | New-game save-slot setup scratch (`sGameStartSaveBuf`). |
| `gameending` | 10,296 B (~10.1 KB) | Ending sequence (`ending_details.c`). |
| `sio` | 4,492 B (~4.4 KB) | A *second*, smaller link-cable scratch region, distinct from the persistent `sio_core.c` buffers below — legacy hardcoded offsets (`gUnk_Sio_*`). |
| `bmstart` | 2,048 B (2 KB) | Battle-map start sequence (`bmmap.c`). |

Since these all alias the same space, the real EWRAM cost of this whole
overlay mechanism is just the peak, currently **`banim` at 131,468 bytes**
— roughly half the entire 256 KB chip. That's expensive-looking but not
wasteful: without overlaying, all 8 groups would need to be resident
simultaneously (~577 KB total), more than double the whole chip. If
`banim` ever needs to shrink, `gBanimOaml`/`gBanimOamr2` (22.5 KB each) are
the two biggest single pieces in it.

## "MMS" — MU vs SMS (two different, easily-confused sprite-graphics buffers)

- **`gMUGfxBuffer`** (`src/mu.c`) — **34,816 bytes (0x8800), the single
  largest buffer in the whole EWRAM map.** Tagged `EWRAM_OVERLAY(0)`, so it
  shares memory with the menu/prep-screen group above, **not** with
  `banim` directly — but since `banim` is currently the bigger peak, this
  buffer effectively rides for free inside that same reserved space. MU
  ("Map Unit") is the system that animates a unit sprite actively *moving*
  across the map (walking during a move action, an AI unit's turn, etc.) —
  live only while that's happening.
- **`gSMSGfxBuffer`** + **`gSMSHandleArray`** (`src/bmudisp.c`) — 24,576 +
  1,200 bytes, plain `EWRAM_DATA` (**not** overlaid — genuinely persistent
  the whole time you're on the map). SMS is the system that draws units
  *standing still* on the map. Because it's persistent rather than
  overlaid, this one really is "always resident" in the strict sense, for
  as long as any unit sprite is visible.

So: `gMUGfxBuffer` (moving-unit graphics) overlaps with menu screens, not
battle animations directly; `gSMSGfxBuffer`/`gSMSHandleArray`
(standing-unit graphics) don't overlap with anything — they're always on.
If you meant something else by "MMS", let me know and I'll dig further.

## Debug font — correction from the last version of this doc

`debug_font_4bpp` (`src/fontgrp.c`) is **not** in EWRAM at all — its final
linked address (`0x089c3168`) is in ROM. The earlier version of this
summary miscounted it based on its pre-link object-file section type; the
methodology note above explains why that check is unreliable. No EWRAM
cost here, so nothing to reclaim.

## Sound Room

`src/soundroom.c` / `src/soundroom_data.c` declare no `EWRAM_DATA` or
`EWRAM_OVERLAY` symbols at all — it's pure ROM (the song list table) plus
code. It has no EWRAM footprint of its own to report.

## Persistent (`EWRAM_DATA`) — always resident, not shared with anything

Every row below was individually confirmed as `EWRAM_DATA` (not
`EWRAM_OVERLAY`) at its declaration site — this ranking is worth less trust
than the Overlay groups table above unless double-checked this way, since
several large-looking symbols at nearby addresses (`gUisupport_1`,
`gPrepUnitPool`, `gBufPrep`, `gBuf_Banim`, `gSpellAnimBgfx`,
`gBanimOaml`/`gBanimOamr2`, `gTmB_Banim`, `gMUGfxBuffer`) turned out to
actually be `EWRAM_OVERLAY` members once checked, despite showing up
in the raw address dump looking identical to persistent ones.

| Symbol | Size | What / when |
| --- | --- | --- |
| `sGameStartSaveBuf` | 32,768 B | New-game save-slot scratch — technically persistent storage but only meaningfully written during new-game setup |
| `gSMSGfxBuffer` | 24,576 B | Standing-unit sprite graphics (`bmudisp.c`) — live whenever a unit is visible on the map |
| `sTilesetConfig` | 9,216 B | Map tileset config (`bmmap.c`) — resident whenever a map is loaded |
| `gFontgrp_0` | 8,212 B | The main font's glyph bitmap cache (`fontgrp.c`) — used for all text rendering |
| `gSioStInstance` | 7,040 B | Persistent link-cable session state (`sio_core.c`) — separate from the smaller `EWRAM_OVERLAY(sio)` group above |
| `sProcArray` | 6,912 B | The Proc scheduler's process table (`proc.c`) — the entire engine runs on this |
| `gUnitArrayBlue` | 4,712 B | Player unit roster (62 slots) |
| `gSioIncoming` | 4,096 B | Persistent link-cable receive buffer (`sio_core.c`) |
| `gUnitArrayRed` | 3,800 B | Enemy unit roster (50 slots) |
| `gSMSHandleArray` | 1,200 B | Standing-unit sprite handle bookkeeping (`bmudisp.c`) |
| `gUnitArrayGreen` | 1,520 B | NPC unit roster (20 slots) |
| `gUnitArrayPurple` | 380 B | Purple-faction unit roster (5 slots) |

The Overlay groups table above is the more accurate way to reason about
*total* EWRAM cost; this table is only the genuinely always-on subset.


