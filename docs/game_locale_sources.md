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
- `mapping/fe8u_structural_evidence.json`: hash-pinned evidence harvested from
  matching named FE8U/FE8J structures. Each slot records its subsystem,
  evidence kind, table/symbol/key, confidence, source paths, and rationale.
- `mapping/fe8u_target_map.json`: the authoritative 3,414-row FE8U target
  decision ledger generated from the committed evidence. Every row is indexed,
  raw, authored, or an explicit English fallback.
- `mapping/fe8u_target_map.coverage.json`: deterministic source-kind and
  subsystem counts plus every fallback target ID and reason.
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

## Structural mapping methodology

Mappings are promoted only by an independent semantic key shared by the FE8U
and FE8J references. Current evidence families are:

- character, class, and item row keys plus the corresponding name,
  description, and use-text fields;
- chapter `internalName` plus title/objective/goal fields;
- support `(character A, character B, rank)` slots;
- matching named event/world-map scripts plus text ordinal, including reviewed
  raw event opcodes;
- menu table symbol plus override ID/row, with direct regional strings keyed by
  stable `fe8cn.raw.import-NNNN` IDs;
- terrain enum index;
- battle/defeat table keys decoded from the named ROM structures.

The candidate seed is consulted only to record whether an independently proven
decision agrees with it. `interp`, `extrap`, shifted, or identity candidates
cannot create a release mapping. Split/merge cases remain explicit evidence
gaps; for example the two Chapter 14B scenes are not ordinal-mapped. The shared
Duessel/Knoll support key proves FE8U `0x0D49`-`0x0D4B` maps to FE8J
`0x0D08`-`0x0D0A`.

Maintainers may refresh the evidence from the authorized reference trees:

```bash
python3 -m scripts.localization.game_locales harvest-crosswalk \
  --fe8u-root /path/to/fireemblem8u \
  --fe8j-root /path/to/fireemblem8j
```

Normal validation does not require those trees. It rebuilds only from committed
evidence and compares the release artifacts byte-for-byte:

```bash
python3 -m scripts.localization.game_locales build-crosswalk
python3 -m scripts.localization.game_locales check-crosswalk
```

The committed report currently contains 3,414 decisions and zero unresolved:

- 1,472 verified indexed mappings;
- 114 verified raw mappings;
- 0 authored translations;
- 1,828 explicit English fallbacks.

Translation coverage is therefore 1,586 targets (46.46%). Explicit fallback
coverage is 1,828 targets (53.54%); fallback content is not translated content.
The largest reported gap is 1,816 `not-yet-verified` targets, chiefly dialogue
outside the proven named structures. Other fallback reasons are `dummy` (1),
`region-only` (1), and `expansion-only` (10).

## Mapping validation and coverage

```bash
python3 -m scripts.localization.game_locales validate-mapping \
  --mapping texts/locales/mapping/fe8u_target_map.json

python3 -m scripts.localization.game_locales coverage \
  --locale ja \
  --mapping texts/locales/mapping/fe8u_target_map.json
```

Coverage classifications are `indexed_source`, `raw_source`,
`authored_translation`, `explicit_english_fallback`, and `unresolved`.
The release report further groups them by structural subsystem. Candidate rows
remain unresolved when validating the candidate file itself; only a
schema-valid verified mapping backed by committed evidence contributes release
coverage.
