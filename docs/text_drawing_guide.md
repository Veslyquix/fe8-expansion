# Text-drawing guide

`PutDrawText` generally causes graphical glitches when a neighboring text
handle doesn't have a fixed width in VRAM. Using something like
`(GetStringTextLen(str) + 8) / 8` to size a `struct Text` handle is
problematic, because that computed width changes depending on what string
happens to be current, which shifts where neighboring handles' VRAM ranges
start and corrupts them. (This doesn't matter if the screen is faded to
black when it happens.)

When adding text, follow this schema:

1. In `texts/texts.txt`, add a new text entry at the end and write the
   text with a definition.

2. Refer to this text only through `char *GetStringFromIndex(int index);`,
   never raw strings. `GetStringFromIndexInBuffer` can be used to join
   multiple strings together when necessary (e.g. with `Text_DrawNumber`).

3. **Init**
   - `void InitSystemTextFont(void);` — for everything that isn't a
     dialogue event.
   - `void ResetText(void);` — resets to the default font and
     initializes the text VRAM location.
   - `void ResetTextFont(void);` — resets the VRAM location for the
     *active* font. Use this instead of `ResetText` if you aren't using
     `gDefaultFont` but need to update all text (e.g. after
     `InitTextFont`).
   - Skip this step if text is being drawn immediately after menu text
     was just drawn.

4. **Width**
   - `void InitText(struct Text *a, int tileWidth);` — sets the width
     for a text handle; also does `ClearText`.
   - `void InitTextDb(struct Text *text, int tileWidth);` — same, but
     double-buffered: it reserves `tileWidth * 2` tiles and flips
     `db_id` between the two halves on every redraw, so the new string
     renders into the half that *isn't* currently on screen. Use this
     instead of `InitText` when the text redraws every frame (live
     counters, values that scroll/update while visible).
   - `tileWidth` should default to 10 for things that are 1-3 words, or
     20 for full lines of text.

5. **Clear VRAM**
   - `void ClearText(struct Text *text);` — if you're redrawing text and
     skipping steps 3-4, start here. Unnecessary if steps 3-4 were done
     (`InitText` already calls it).

6. **Optional parameters**
   - `void Text_SetParams(struct Text* th, int x, int colorId);` —
     offsets the x position and/or sets a color. Default to `x = 0` and
     `TEXT_COLOR_SYSTEM_WHITE`, except for titles, which use
     `TEXT_COLOR_SYSTEM_GOLD` or `TEXT_COLOR_SYSTEM_BLUE`.

7. **Draw into VRAM**
   - `void Text_DrawString(struct Text *text, const char *str);` — draws
     the text into VRAM. Only use `Text_DrawNumber` if a variable number
     is needed in the middle of a text string.

8. **Erase the destination**
   - `void TileMap_FillRect(u16 *dest, int width, int height, int fillValue);`
     — erase the BG tilemap area where the text will land, before
     placing it. Each line of text is always height 2. `fillValue` is
     generally 0, except for sprite text with a box background, which is
     `0x4444` (see `SpriteText_DrawBackground`).

9. **Place it on the screen**
   - `void PutText(struct Text *th, u16 *dest);`

## Numbers — call `PreallocateCommonGlyphs` after `ResetText`

`PutNumber`/`PutSpecialChar` allocate each `(color, id)` digit/special-char
glyph into VRAM lazily, the first time that exact combination is drawn
(`GetSpecialCharChr`/`AddSpecialChar`, `src/fontgrp.c`). `sSpecialCharStList`
is an append-only cache for the current font generation, so which glyphs
are already resident — and therefore where the *next* one lands — depends
on the history of what's been drawn. If a redraw needs fewer distinct
digits than a previous one, whatever gets `InitText`'d afterward can land
at a different VRAM offset than last time and visibly jump/glitch — the
same root cause as the fixed-`tileWidth` rule above, just for numbers
instead of strings.

Whenever a screen uses `PutNumber` (or any of its variants), call
`void PreallocateCommonGlyphs(int color);` (`src/fontgrp.c` /
`include/fontgrp.h`, `#if FE8_PURCHASE_GENERICS`) **once**, immediately
after step 3 (`ResetText`/`ResetTextFont`) and before any `PutNumber`
calls for that screen — do **not** call it again per color used on the
same screen; one call is sufficient regardless of how many text colors
that screen draws numbers in. It front-loads every digit 0-9 (both
`TEXT_SPECIAL_BIGNUM_*` and `TEXT_SPECIAL_SMALLNUM_*`), `TEXT_SPECIAL_DASH`,
`TEXT_SPECIAL_PLUS`, and `TEXT_SPECIAL_SLASH` into the cache via the same
`GetSpecialCharChr` that `PutSpecialChar` uses internally — it never
writes to a tilemap/OAM destination, so nothing is placed on screen, but
every subsequent number redraw on that screen allocates from an
already-fully-populated, fixed set instead of growing the cache
unpredictably.

## Multi-line strings — how vanilla actually does it

`Text_DrawString`/`Text_DrawStringASCII` (`src/fontgrp.c`) stop at the
first `[LF]` they hit, and `PutText` only ever places a single row — so a
multi-line string still needs one `struct Text` handle per line. But the
*source* is still just ONE `texts.txt` entry with `[LF]` separating its
lines (not one entry per line). Vanilla reconciles this with
`PrintStringToTexts(struct Text** texts, const char* str, u16* tm, int unk)`
(`src/scene.c`, declared in `include/scene.h`) — the same helper the
dialogue box uses. It walks the single source string character by
character, and on each `[LF]` it `PutText`s whatever accumulated in the
*current* line's handle to `tm + line*0x40` (`0x40` = 2 tilemap rows,
matching "each line is height 2"), then advances to the next handle in
the array and keeps drawing.

So for a multi-line block:

1. Write ONE `texts.txt` entry with `[LF]` between lines (step 1).
2. `InitText` + `Text_SetParams` an array of `struct Text` handles — one
   per line, sized to the max line count you'll ever show (steps 4/6).
3. `TileMap_FillRect` the whole block's destination area up front (step 8).
4. Call `PrintStringToTexts(texts, GetStringFromIndex(msgId), tm, lineCount)`
   once — it does step 7 (`Text_DrawString`-equivalent, via
   `Text_DrawCharacter`) and step 9 (`PutText`) together, per line,
   internally.

Applied in `src/power.c`'s `CoScreen_PutMultilineText`.

## Why this matters

Raw strings and ad-hoc width guesses (e.g. `(GetStringTextLen(str)+8)/8`)
cause VRAM glyph-shift glitches when a neighboring text handle's actual
width doesn't match its allocated `tileWidth`. This schema fixes that by
routing every string through `texts.txt` + `GetStringFromIndex` and always
giving `InitText`/`InitTextDb` an explicit, fixed width.

Follow this schema step-by-step any time new text-drawing code is written
in this repo (menus, screens, HUD elements, etc.) — not just as a
reference to consult. See `src/power.c`'s CO screen (`CoScreen_PutText`,
`CoScreen_PutMultilineText`) and `src/purchase_generics.c` for worked
examples.
