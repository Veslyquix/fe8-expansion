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

These targets generate both CJK bundles by default. To inspect one build
profile in isolation, set `GAME_LOCALIZATION_ENABLED_LOCALES=ja` or
`GAME_LOCALIZATION_ENABLED_LOCALES=zh-Hans`. A single-locale profile emits no
nodes, compressed blob, entries, or catalog descriptor for the disabled
locale; its fixed `gGameLocalizationCatalogs[]` slot is null.

The generator reads the canonical `texts/locales/` sources and the verified
`texts/locales/mapping/fe8u_target_map.json` decisions. It never infers a
positional mapping. Explicit English fallback decisions produce absent
entries; a verified provider without a committed payload is also absent and
reported separately as `provider_unavailable`.

Outputs are generated under `build/game-localization/generated/`:

- `localized_game_text_data.h`: target count and maximum decoded bytes;
- `game_localization_catalog.h`: catalog and entry descriptors;
- `game_localization_catalog.c`: Huffman nodes, blobs, metadata, and entries
  in `.locale_data`;
- `game_localization_report.json`: entry-level provenance and hashes;
- `game_localization_budget.json`: coverage, storage, and ROM estimates.

Every present message is strict UTF-8 plus canonical engine control bytes and
one trailing NUL. Generation rejects unknown controls, embedded NUL bytes,
unresolved mapping decisions, and codec round-trip mismatches.

## Runtime and build gating

English/default and archival builds do not generate or link this catalog.
They retain the historical 4 KiB `MsgBuffer`, English `gMsgTable`, and ARM
decoder path.

Until production Japanese/Chinese configuration is enabled by a later sprint,
an internal link test can exercise this slice:

```bash
make expansion-modern-rom \
  MODERN_ROM_SIZE=32M \
  MODERN_GAME_LOCALIZATION_CJK_MASK=0x06 \
  MODERN_BUILD_ROOT=build/gamecat-modern
```

The synthetic mask accepts `0x02` (Japanese), `0x04` (Simplified Chinese), or
`0x06` (both). Each mask generates and links only its selected game-catalog
bundle(s). The effective synthetic locale list is resolved through the normal
expansion identity pipeline before metadata and fingerprint generation, while
`config.mk` and production locale validation remain unchanged.

CJK profiles use one explicit message-storage overlay. The historical helper
scratch fields keep their offsets inside the overlay; total capacity is at
least `0x1600` bytes and grows if the generated maximum (including NUL)
requires more. Decode overflow or corrupt input returns a visible marker and
an explicit `LocalizedGameTextStatus`. Message indexes are checked before
localized or English fallback lookup. Bounded English fallback uses a
cache-independent C decoder with explicit input, output, node, and caller
capacity checks; it never stages through the active `MsgBuffer` overlay, so an
InBuffer lookup cannot invalidate or overwrite a pointer returned by an
earlier `GetStringFromIndex` call.

`StringInsertSpecialPrefixByCtrl`, `StrInsertTact`, and other renderer-side
walkers remain byte-oriented. They must not process long UTF-8 overlay content
until the renderer integration sprint replaces their legacy `0x80` parsing.
