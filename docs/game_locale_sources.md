# Full-game locale source imports

`texts/locales/` contains deterministic, UTF-8 source imports for future
full-game Japanese (`ja`) and Simplified Chinese (`zh-Hans`) localization.
These files are data inputs only; they are not integrated with the runtime
locale catalog.

## Layout and provenance

- `source/fe8j/jp_texts.txt`, `source/fe8j/jp_textdefs.txt`,
  `source/fe8j/msg_map.tsv`, and `source/fe8cn/FE8CN.txt`: byte-exact,
  hash-pinned authorized input snapshots. These committed raw files are the
  independent regeneration source.
- `ja/indexed.txt`: 3,339 FE8J-layout messages (`0x0000` through `0x0D0A`).
- `ja/control_defs.txt`: FE8J source aliases mapped to canonical controls. It is
  an alias table, not normalized locale payload.
- `zh-Hans/indexed.txt`: 3,339 FE8CN messages using the FE8J indexed layout.
- `zh-Hans/raw.json`: 152 raw-address occurrences deduplicated to 143 stable
  `fe8cn.raw.import-NNNN` IDs. IDs are assigned by pinned source import order,
  not ROM address. Address, source lines, and duplicate occurrences exist only
  under each record's `provenance` field.
- `mapping/fe8j_to_fe8u.candidates.json`: a sparse import of the supplied
  `msg_map.tsv`. It is explicitly `candidate`, `authoritative: false`, and
  unverified.
- `manifest.json`: pinned input SHA-256 hashes, artifact hashes, exact counts,
  locale IDs, codepoint counts, and maximum UTF-8 payload lengths.

FE8J source IDs are not FE8U target IDs. The FE8U target universe has 3,414
IDs, while the indexed FE8J layout has 3,339. Candidate rows must therefore
remain unresolved until semantic verification produces an authoritative
mapping.

## Canonical controls

Normalized payload has one accepted control spelling:

```text
[CTRL:HHHH]
```

`HHHH` is exactly four uppercase hexadecimal digits representing one u16
control unit. The importer converts FE8J `[$HHHH]`, FE8CN `[0xHHH]` /
`[0xHHHH]`, and pinned named aliases to that form. Unknown, malformed, mixed,
or bare marker-like tokens such as `[0001]` are rejected rather than retained
as text. `scripts.localization.game_locales` exports APIs to expand a
canonical token to its exact u16 value and little-endian bytes.

## Regeneration and check

Regenerate only when intentionally refreshing normalized outputs:

```bash
python3 -m scripts.localization.game_locales regenerate
```

The required source-of-truth gate regenerates every artifact and the manifest
from the committed raw snapshots in memory, then compares committed output
byte-for-byte:

```bash
python3 -m scripts.localization.game_locales check
```

This check does not trust artifact hashes recorded by the committed manifest,
so changing an artifact and its manifest entry together still fails. The four
raw snapshots must also match the independent SHA-256 pins in
`scripts/localization/game_locales/importer.py`.

The explicit `import` command remains available for checking prospective
external replacements, but it accepts only inputs matching those pins.

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
