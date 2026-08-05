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
decisions produce absent CJK entries; a verified provider without a committed
payload is also absent and reported separately as `provider_unavailable`.

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

Until production Japanese/Chinese configuration is enabled by a later sprint,
an internal link test can exercise this slice:

```bash
make expansion-modern-rom \
  MODERN_ROM_SIZE=32M \
  MODERN_GAME_LOCALIZATION_CJK_MASK=0x06 \
  MODERN_BUILD_ROOT=build/gamecat-modern
```

The synthetic mask accepts `0x02` (Japanese), `0x04` (Simplified Chinese), or
`0x06` (both). Each mask generates one shared English bundle and only its
selected CJK bundle(s). The effective synthetic locale list is resolved
through the normal expansion identity pipeline before metadata and fingerprint
generation, while `config.mk` and production locale validation remain
unchanged.

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
`0xD54`, and compares all 1,828 explicit CJK fallbacks byte-for-byte with the
corresponding shared English descriptor.

`StringInsertSpecialPrefixByCtrl`, `StrInsertTact`, and other renderer-side
walkers remain byte-oriented. They must not process long UTF-8 overlay content
until the renderer integration sprint replaces their legacy `0x80` parsing.
