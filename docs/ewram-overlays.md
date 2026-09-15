# EWRAM overlay budget

`linker/expansion.ld` defines a set of mutually-exclusive `EWRAM_OVERLAY(tag)`
regions that all start at `__ewram_start`. The linker sizes the whole overlay
block to `__ewram_overlay_peak_size`, the `MAX()` of every tag's own size —
so any tag can grow for free as long as it stays under whatever the largest
tag currently is. Only bytes past that peak cost real, additional EWRAM.

As of this writing, `ewram_overlay_banim` (battle-animation runtime buffers)
is the peak tag at **131,468 bytes (0x2018C)** — this is understood to be
essentially unavoidable (it matches vanilla's own decomp within 4 bytes).
Every other tag's "free" headroom is measured against that ceiling:

| tag | contents | current size | headroom before it becomes the new peak |
|---|---|---:|---:|
| `ewram_overlay_banim` | battle-animation runtime buffers (peak) | 131,468 | — |
| `ewram_overlay_gamestart` | game-start flow | 130,392 | 1,076 |
| `ewram_overlay_0` | sound room, unit-list, bksel forecast, weather/gradient effects, trade menu, item-select, convoy, bonus claim, difficulty menu | 127,486 | 3,982 |
| `ewram_overlay_worldmap` | world map | 118,740 | 12,728 |
| `ewram_overlay_coselect` | CO Select carousel (FE8_CO_POWERS) | 83,596 | 47,872 |
| `ewram_overlay_gamestartsave` | game-start save flow | 32,768 | 98,700 |
| `ewram_overlay_debugconsole` | `gFontgrp_0` debug-console scrollback (VeslyDebugger / debug tools only) | 8,212 | 123,256 |
| `ewram_overlay_gameending` | game-ending flow | 10,296 | 121,172 |
| `ewram_overlay_sio` | link-cable | 4,492 | 126,976 |
| `ewram_overlay_bmstart` | battle-map start flow | 2,048 | 129,420 |
| `ewram_overlay_modeselect` | Mode Select carousel (FE8_MODE_SELECT) | 0 (flag off in this build) | 131,468 |

To regenerate this table after changing overlay contents, build with
`make sync-win` and read the sizes back out of the linked ELF:

```bash
arm-none-eabi-nm build/expansion-modern/debug/aapcs/AdvanfeWarblem.elf \
  | grep -E "__ewram_overlay_.*_size$|__ewram_overlay_peak_size$"
```

## Rules for adding to a tag, or adding a new tag

- A tag only needs to be temporally disjoint from *every other tag*, not
  just the current peak (`banim`) — all tags alias the same address range,
  so anything placed in one tag is corrupted the instant another tag's
  owner writes to that memory concurrently. Verify the feature genuinely
  never runs alongside anything else that already lives in any tag before
  adding to it (see `reference_ewram_overlays_alias.md` in project memory,
  and the historical `EWRAM_OVERLAY(gameending)` corruption bug documented
  in `src/modeselect.c`'s own comment for a concrete cautionary example).
- Adding a new tag follows the pattern of the existing ones in
  `linker/expansion.ld`: a `ewram_overlay_<tag> __ewram_start (NOLOAD)`
  section block, a `__ewram_overlay_<tag>_size` symbol, folding that size
  into the `__ewram_overlay_peak_size` `MAX()` nest, and an
  `ASSERT(SIZEOF(ewram_overlay_<tag>) <= 256K, ...)` line at the bottom.
- Persistent EWRAM (`EWRAM_DATA`) is separate and additive — it is never
  reused, so moving something from `EWRAM_DATA` into an existing
  under-peak overlay tag is free EWRAM, while adding a brand new
  `EWRAM_DATA` global always costs its full size.
