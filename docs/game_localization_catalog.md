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
`0x06` (both). It does not change `config.mk` or production locale validation.

CJK profiles use one explicit message-storage overlay. The historical helper
scratch fields keep their offsets inside the overlay; total capacity is at
least `0x1600` bytes and grows if the generated maximum (including NUL)
requires more. Decode overflow or corrupt input returns a visible marker and
an explicit `LocalizedGameTextStatus`. Message indexes are checked before
localized or English fallback lookup, and bounded English fallback is staged
through the historical primary scratch capacity before copying to the caller.

`StringInsertSpecialPrefixByCtrl`, `StrInsertTact`, and other renderer-side
walkers remain byte-oriented. They must not process long UTF-8 overlay content
until the renderer integration sprint replaces their legacy `0x80` parsing.
