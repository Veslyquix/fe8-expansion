# Full-game localization catalog

The full-game catalog is an opt-in modern-build input for FE8U message IDs.
It is separate from the expansion-framework catalog documented in
`localization.md`.

## Generate and validate

```bash
make game-localization-validate
make game-localization-generate
make game-localization-check
make game-localization-test
make game-localization-budget
```

These targets generate both CJK bundles by default. Every generated CJK
profile also emits exactly one shared modern English bundle covering all 3,414
FE8U message IDs. To inspect one build profile in isolation, set
`GAME_LOCALIZATION_ENABLED_LOCALES=ja` or
`GAME_LOCALIZATION_ENABLED_LOCALES=zh-Hans`. A single-locale profile emits no
nodes, compressed blob, entries, or catalog descriptor for the disabled CJK
locale; its fixed `gGameLocalizationCatalogs[]` slot is null, while the shared
English bundle remains present once.

The generator reads committed `texts/texts.txt` plus `texts/textdefs.txt` for
English, and the canonical `texts/locales/` sources plus verified
`texts/locales/mapping/fe8u_target_map.json` decisions for CJK. The English
parser handles explicit `#` IDs, `##` macro IDs, relative includes, named
controls/FIDs, and source comments deterministically. It encodes literal text
as UTF-8 while preserving engine control payload bytes. Legacy printable
tokens are normalized during generation: `DashedLine` to `-`, `TAB` to UTF-8
U+3000, `LQuote`/`RQuote` to `"`, and `AccentedE` to `e`. An unknown high-byte
printable token is rejected rather than emitted as invalid UTF-8.

The CJK mapping never infers a positional match. Explicit English fallback
decisions produce absent CJK entries. Evidence-backed regional raw mappings
may commit an authorized FE8J literal as the Japanese provider while retaining
the FE8CN import as the Chinese provider, but only when a tracked C source
table's symbol, message-ID key, exact literal, and bounded context hash all
verify. Unprovable Japanese text remains an explicit English fallback.

Outputs are generated under `build/game-localization/generated/`:

- `localized_game_text_data.h`: target count and maximum decoded bytes;
- `game_localization_catalog.h`: catalog and entry descriptors;
- `game_localization_catalog.c`: Huffman nodes, blobs, metadata, and entries
  in `.locale_data`;
- `game_localization_report.json`: entry-level provenance and hashes;
- `game_localization_budget.json`: coverage, storage, shared-English, and
  profile-specific ROM estimates.

Every present message is strict UTF-8 plus canonical engine control bytes and
one trailing NUL. Each descriptor records both compressed byte length and
exact meaningful bit length; the standalone NUL is the final Huffman symbol at
that bit boundary. Generation rejects unknown controls, embedded NUL bytes,
unresolved mapping decisions, and codec round-trip mismatches.

## Runtime and build gating

English-only modern and archival builds do not generate or link this catalog.
They retain the historical 4 KiB `MsgBuffer`, English `gMsgTable`, and ARM
decoder path with zero modern English/CJK payload.

Production CJK assets are selected directly from the validated locale profile:

```bash
make expansion-modern-localization-profile-en-ja
make expansion-modern-localization-profile-en-zh-hans
make expansion-modern-localization-profile-en-ja-zh-hans
```

Equivalent direct builds use `EXPANSION_ENABLED_LOCALES=en,ja`,
`en,zh-Hans`, or `en,ja,zh-Hans` with `MODERN_ROM_SIZE=32M`. The same
effective profile drives identity metadata/fingerprint/mask, the selected CJK
catalog bundle(s), and localized font compilation. There is no synthetic
identity or separate CJK mask. Every CJK profile emits one shared English
bundle and only its selected CJK bundle(s); adding `qps-ploc` changes the
framework profile but does not duplicate full-game English data.

CJK profiles use one explicit message-storage overlay. The historical helper
scratch fields keep their offsets inside the overlay; total capacity is at
least `0x1600` bytes and grows if the generated maximum (including NUL)
requires more. Decode overflow or corrupt input returns a visible marker and
an explicit `LocalizedGameTextStatus`. Message indexes are checked before
localized or English lookup. In every CJK-enabled build, English and qps-ploc
decode the modern English descriptor directly; absent/unpopulated Japanese or
Simplified Chinese entries select that same descriptor. No active CJK path
reads `gMsgTable`, guesses a 4 KiB compressed-input bound, or depends on
adjacent compressed arrays. Bounded InBuffer lookup remains
cache-independent, so it cannot invalidate or overwrite a pointer returned by
an earlier `GetStringFromIndex` call.

The exhaustive audit independently decodes all 3,414 English entries, checks
source equality, renderer-valid UTF-8/control structure, and exact NUL bit
boundaries. It separately guards `0xD4D`, `0xD4E`, `0xD4F`, `0xD50`, and
`0xD54`, and compares all 1,809 explicit CJK fallbacks byte-for-byte with the
corresponding shared English descriptor.

The 143-record raw closure is a separate call-site audit:

```bash
python3 -m scripts.localization.game_locales check-raw-closure
```

See `docs/game_locale_sources.md` for its 134 game-ID, 2 semantic-key, 4
exclusion, and 3 explicit English-fallback decisions.

`StringInsertSpecialPrefixByCtrl`, `StrInsertTact`, and other renderer-side
walkers remain byte-oriented. They must not process long UTF-8 overlay content
until the renderer integration sprint replaces their legacy `0x80` parsing.
