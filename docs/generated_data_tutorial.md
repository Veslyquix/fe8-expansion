# Generated-data authoring tutorial (Issue #5)

This is the **contributor-facing walkthrough** for the deterministic
generated-data platform. It shows, with runnable commands and real source
paths, how to add or modify every supported input type without ever
hand-editing generated C. For the full design/reference (per-field
semantics, every validation rule, linking mechanics), see
`docs/generated_data.md`; for the discoverable registry of every table and
its record count, see `reports/generated_data_manifest.md`.

Everything here is stdlib-only Python. There is no per-table dispatch: the
same three verbs drive every table.

## The core loop (applies to every table)

```sh
# 1. Edit the JSON source under src/data/ (see each section below).
# 2. Validate: reports every diagnostic with file:line:column, not just the first.
python3 -m scripts.generated_data validate --table <table>

# 3. Regenerate C89 output (build/generated/data/) + the committed inventory.
python3 -m scripts.generated_data generate --table <table>

# 4. Drift gate (CI-safe: writes nothing committed, non-zero exit on drift).
python3 -m scripts.generated_data check --table <table>
```

Whole-platform equivalents (all tables at once) are Make targets:

```sh
make generated-data-validate     # validate every registered table
make generated-data-generate     # regenerate every table's C + inventory + manifest
make generated-data-check        # CI drift gate: per-table + aggregate manifest
make generated-data-test         # the Python unittest suite
make generated-data-manifest     # (re)write reports/generated_data_manifest.md
```

`--table <name>` accepts any registered table. Discover the full set (and
each table's live record count / capacity / dependency order) from
`reports/generated_data_manifest.md`, or at compile time from the
generated `build/generated/data/generated_data_manifest.h`
(`GENERATED_DATA_<TABLE>_RECORD_COUNT`, `GENERATED_DATA_TABLE_COUNT`).

Diagnostics are actionable. A duplicate/invalid/out-of-range/dangling
reference is reported as `src/data/<file>.json:LINE:COL: <message> (at
<breadcrumb>)`, and a run reports *every* problem it finds, so you fix a
batch per iteration instead of one-at-a-time.

---

## Global tables

### Add or modify a **character** (`--table characters`)

Source: `src/data/characters.json` (the `characters` array, one record per
`CHARACTER_*`). Modify a field in place, e.g. bump Eirika's luck growth:

```json
{
  "character": "CHARACTER_EIRIKA",
  "defaultClass": "CLASS_EIRIKA_LORD",
  "growth": { "hp": 70, "pow": 40, "skl": 60, "spd": 60, "def": 30, "res": 30, "lck": 65 },
  "supportData": "SupportData_Eirika"
}
```

`characters` is a hard **256-slot** array (`gCharacterData[]`). The manifest
reports usage as `256/256` and the `manifest` command *fails* if a source
ever authors more than 256 records (record-budget diagnostic). Cross-table
validation checks `defaultClass` against `classes` and `supportData`
against `supports`, so an edit that dangles either is rejected with a
`file:line:column` diagnostic.

```sh
python3 -m scripts.generated_data validate --table characters
python3 -m scripts.generated_data generate --table characters   # -> build/generated/data/data_characters.c
```

### Add or modify a **class** (`--table classes`)

Source: `src/data/classes.json` (the `classes` array, one record per
`CLASS_*`). Records carry `base`/`max`/`growth`/`promotionGain` stat
blocks plus terrain-lookup fields cross-validated against the
`terrainstats` and `movecost` tables. Same validate/generate/check loop
(output: `data_classes.c`).

### Add or modify an **item** (`--table items`)

Source: `src/data/items.json` (the `items` array, one record per
`ITEM_*`). Example: raise the Iron Sword's might:

```json
{
  "item": "ITEM_SWORD_IRON",
  "weaponType": "ITYPE_SWORD",
  "attributes": ["IA_WEAPON"],
  "might": 6,
  "range": { "min": 1, "max": 1 }
}
```

`nameTextId`/`descTextId`/`useDescTextId` are range-checked against the
live `MSG_COUNT` bound; `attributes`/`requiredWexp`/`weaponType` are
resolved symbolically. Output: `data_items.c`.

Text IDs may also be authored **symbolically** as `MSG_*` names resolved
against `include/constants/msg.h`:

```json
{ "item": "ITEM_SWORD_STEEL", "nameTextId": "MSG_SAVE_COMPAT_BACK" }
```

(any `MSG_*` constant the live header defines; the one above is only a
spelling example). An unknown symbol fails the data build with an actionable
diagnostic instead of silently repointing the item at whatever text later
lands on that number.
The 206 vanilla records keep the plain-integer form and still round-trip
byte-for-byte.

**Framework-authored (expansion) records must not add a message at all.**
`texts/texts.txt` feeds one shared, Huffman-compressed blob, so appending a
message re-encodes the text of every build, default ones included. Leave the
text IDs unset on such a record and author its display text through the
config-gated content path instead -- see `docs/starter_features.md` for the
bundled worked example.

### Add or modify a **support** (`--table supports`)

Source: `src/data/supports.json`. A record is one owner and its parallel
`characters[]`/`supportExpBase[]`/`supportExpGrowth[]` arrays (all must be
the same length, `<= UNIT_SUPPORT_MAX_COUNT`, and `supportCount` must
match). Add a partner to Eirika:

```json
{
  "owner": "CHARACTER_EIRIKA",
  "symbol": "SupportData_Eirika",
  "characters": ["CHARACTER_EPHRAIM", "CHARACTER_SETH"],
  "supportExpBase": [30, 25],
  "supportExpGrowth": [4, 3],
  "supportCount": 2
}
```

Supports are **reciprocal**: if Eirika lists Ephraim with a given
`(base, growth)`, Ephraim's record must list Eirika back with the same
pair -- edit both directions together. Mismatched parallel-array
lengths, an out-of-capacity `supportCount`, a duplicate owner, a
one-directional/asymmetric support, or an unknown `CHARACTER_*` are
each reported with a `file:line:column` location. Output:
`data_supports.c`.

---

## Chapter 2 vertical slice

### Add or modify a **unit group** (`--table units`)

Source: `src/data/ch2_units.json` (the `groups` array; each `symbol` is a
`UnitDef_*` list of placed units with `charIndex`/`classIndex`/
`allegiance`/position/`items[]`/`redas[]` reinforcement records). Every
`charIndex`/`classIndex`/`items` entry resolves symbolically; item lists
and `redas` are capacity-checked. Output: `data_ch2_units.c`.

### Add or modify a **shop** (`--table shops`)

Source: `src/data/ch2_shops.json` (the `shops` array; each `symbol` is a
`ShopList_*` with an `items[]` list). Add a stock item:

```json
{
  "symbol": "ShopList_Event_Ch2Armory",
  "items": ["ITEM_SWORD_SLIM", "ITEM_SWORD_IRON", "ITEM_LANCE_IRON"]
}
```

Output: `data_ch2_shops.c`.

### Add or modify a **trap** (`--table traps`)

Source: `src/data/ch2_traps.json` (the `traps` array; each `symbol` is a
`TrapData_*` with an `entries[]` list, capacity-checked against
`TRAP_MAX_COUNT`). Output: `data_ch2_traps.c`.

### Add or modify an **event symbol** (`--table eventscripts`)

Source: `src/data/ch2_eventscripts.json` (the `scripts` array). This is a
metadata-only table (no generated C): it declares each hand-written
`EventScr_*`/`EventListScr_*` symbol, its `owner` category
(`turn_based`, `character_based`, `location_based`, `misc_based`,
`tutorial`, ...), `kind`, and the header that declares it. Adding an entry
here is what lets an `eventlists` list reference that symbol.

### Add or modify an **event-list** (`--table eventlists`)

Source: `src/data/ch2_eventlists.json` (the `lists` array + the 30-entry
`tutorial` list + the `Ch2Events` manifest). Each list entry is a
`{ "macro": ..., "args": [...] }` event macro call. String args that name
a symbol (e.g. `"EventScr_Ch2_Turn1Player"`) are resolved against the
`eventscripts` table; unknown symbols, an out-of-range tutorial list, or a
missing manifest field are each reported with a location. Output:
`data_ch2_eventlists.c`.

`eventlists` declares `dependency_tables()` (`units`, `shops`, `traps`,
`eventscripts`), so `validate` loads those tables automatically to resolve
cross-references. Override a dependency's source for local iteration with
`--dep-source NAME=PATH`.

### Compose the whole chapter: the **chapter bundle** (`--table chapterbundle`)

Source: `src/data/ch2_bundle.json`. This is the coherence layer: it names
the chapter (`CHAPTER_L_2`, its `chapterSettingsIndex`, etc.), the
`Ch2Events` manifest, and every `units`/`shops`/`traps`/`eventscripts`
symbol the chapter uses, and cross-checks that the whole slice is
internally consistent as one bundle (every referenced symbol exists and is
reachable, support owners are reciprocal, referenced character/class/item
IDs exist). It is metadata-only (no generated C) -- its job is the
whole-bundle drift gate `make generated-data-ch2-check`.

---

## Custom C symbols / callbacks (escape hatch)

When a field must reference existing hand-written C (a callback pointer, a
shared constant/table) rather than a value the generator invents, the
schema declares it as a `CSymbolRefField` bound to a specific header. The
validator rejects malformed identifiers and any symbol not *declared* in
that header (an allowlist by construction), and the generator emits the
name as a bare C token (unquoted) so it compiles as a real reference. This
is how you point generated data at hand-owned code without editing any
generated output. See `scripts/generated_data/escape_hatch.py` and its
tests for the end-to-end contract.

---

## What "done" looks like

```sh
make generated-data-check   # per-table drift + aggregate manifest/budget gate, all OK
make generated-data-test    # full unittest suite green
```

CI runs `make generated-data-check` on every push (`.github/workflows/build.yml`),
so a stale inventory, a broken reference, a capacity/budget overflow, or a
manifest drift fails fast with an actionable diagnostic before the slower
ROM linker gate runs.
