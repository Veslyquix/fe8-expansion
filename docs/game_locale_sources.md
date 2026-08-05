# Full-game locale source imports

`texts/locales/` contains deterministic, UTF-8 source imports for future
full-game Japanese (`ja`) and Simplified Chinese (`zh-Hans`) localization.
These files are data inputs only; they are not integrated with the runtime
locale catalog.

## Layout and provenance

- `ja/indexed.txt`: 3,339 FE8J-layout messages (`0x0000` through `0x0D0A`).
- `ja/control_defs.txt`: normalized FE8J message control definitions.
- `zh-Hans/indexed.txt`: 3,339 FE8CN messages using the FE8J indexed layout.
- `zh-Hans/raw.json`: 152 raw-address records deduplicated to 143 stable
  `fe8cn.raw.ADDRESS` keys. Every occurrence retains its input record index
  and source line.
- `mapping/fe8j_to_fe8u.candidates.json`: a sparse import of the supplied
  `msg_map.tsv`. It is explicitly `candidate`, `authoritative: false`, and
  unverified.
- `manifest.json`: pinned input SHA-256 hashes, artifact hashes, exact counts,
  locale IDs, codepoint counts, and maximum UTF-8 payload lengths.

FE8J source IDs are not FE8U target IDs. The FE8U target universe has 3,414
IDs, while the indexed FE8J layout has 3,339. Candidate rows must therefore
remain unresolved until semantic verification produces an authoritative
mapping.

## Import

Run the importer only when intentionally refreshing the vendored sources:

```bash
python3 -m scripts.localization.game_locales import \
  --jp-text /path/to/fireemblem8j/texts/jp_texts.txt \
  --jp-controls /path/to/fireemblem8j/texts/jp_textdefs.txt \
  --cn-text /path/to/FE8CN.txt \
  --mapping-seed /path/to/fireemblem8j/layout/msg_map.tsv \
  --out-dir texts/locales
```

The four inputs must match the SHA-256 pins in
`scripts/localization/game_locales/importer.py`. The normal build consumes no
external or parent-directory paths.

## Mapping validation and coverage

```bash
python3 -m scripts.localization.game_locales validate-mapping \
  --mapping texts/locales/mapping/fe8j_to_fe8u.candidates.json

python3 -m scripts.localization.game_locales coverage \
  --locale ja \
  --mapping texts/locales/mapping/fe8j_to_fe8u.candidates.json
```

Coverage classifications are `indexed_source`, `raw_source`,
`authored_translation`, `explicit_english_fallback`, and `unresolved`.
Candidate rows are reported as present but remain `unresolved`; only a
schema-valid verified mapping can contribute coverage.
