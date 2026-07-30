# Issue #5 closure evidence -- "Phase 3: schema-driven generated data authoring"

Status: final closure-evidence status as of 2026-07-25. **GitHub issue
#5 is CLOSED; the completion commit
`ac0ee5d7f17eb8e70175576cb46d9f320d8013cd` is in the merged master
history. This report does not itself claim any CI run URL.** It maps
every item of the issue's own scope checklist and acceptance criteria
to concrete code, tests, docs, and explicit non-goals so a reviewer can
verify closure claim-by-claim.

Run the evidence locally:

```sh
make generated-data-check    # per-table validation/round-trip/inventory drift + aggregate manifest/budget gate
make generated-data-test     # full stdlib unittest suite
```

## Scope checklist

### [x] Generalize the existing JSON pipeline into deterministic schemas/generators
- Code: `scripts/generated_data/schema.py` (`TableSchema`, `SchemaRegistry`,
  `DependencyGraph`), `registry.py` (one line per table, no CLI dispatch),
  `cli.py` (`validate`/`generate`/`check`/`manifest`), `cgen.py`
  (`write_if_changed`, mtime-preserving).
- Determinism: sorted iteration, stable digests, write-if-changed.
- Tests: `tests/test_schema.py`, `tests/test_cli.py`,
  `tests/test_cli_new_tables.py`.

### [x] Support characters, classes, items, chapters, units, shops, supports, events, and mechanics data
- Global: `characters` (256), `classes` (127), `items` (206),
  `supports` (33).
- Chapter 2 slice: `units` (7, `UnitDefinition`/`REDA`), `shops` (1),
  `traps` (2), `eventscripts` (43), `eventlists` (9, list + 30-entry
  tutorial list + `Ch2Events` manifest), `chapterbundle` (1, whole-bundle
  coherence).
- Mechanics: `terrainstats` (8), `movecost` (17), `weapontriangle` (12).
- 13 registered tables; see `reports/generated_data_manifest.md`.
- Non-goal (explicit): additional/other chapters and other data domains
  beyond this vertical slice + the global tables (see
  `docs/generated_data.md`, "Issue #5 completion boundary and status").

### [x] Generate typed C, symbolic constants, counts, registries, and dependencies
- Typed C: `build/generated/data/data_*.c` (one per non-metadata table),
  linked with zero ROM/ELF address shift (Make link-check targets).
- Counts/registry (NEW): `scripts/generated_data/manifest.py` +
  `manifest` CLI verb ->
  - committed `reports/generated_data_manifest.md` (every table, record
    count, capacity, output symbol, cross-table dependency topo order +
    aggregate sha256 digest);
  - generated `build/generated/data/generated_data_manifest.h`
    (`GENERATED_DATA_TABLE_COUNT`, per-table
    `GENERATED_DATA_<TABLE>_RECORD_COUNT`/`_VERSION`/`_CAPACITY`), so
    downstream C tooling discovers tables + counts at compile time.
- Dependencies: `DependencyGraph.topo_order()`/`digest()` per table and
  aggregate; committed per-table inventories carry the digest.
- Tests: `tests/test_manifest.py`, `tests/test_schema.py`.

### [x] Validate duplicate IDs, missing references, ranges, assets/text, and memory budgets
- Code: `scripts/generated_data/validators.py` -- `validate_unique`
  (duplicate IDs), `validate_reference`/`resolve_bitmask_flags` (missing
  references), `validate_range` (ranges), `validate_fixed_capacity` +
  `validate_parallel_arrays` (capacity/shape).
- Assets/text: `items` text IDs range-checked against the live
  `MSG_COUNT` (`validators.extract_define_constant`); unit/shop/trap/item
  symbol references resolved.
- Memory/record budgets (NEW): `manifest.budget_diagnostics` -- any
  schema declaring `record_budget` (e.g. `characters` = 256-slot
  `gCharacterData[]`) fails the manifest gate if a source overflows the
  fixed array. Reported as an actionable `manifest.<table>` error.
- Robustness fix (NEW): a mismatched-length parallel array in `supports`
  previously crashed the reciprocity cross-check with an uncaught
  `IndexError`; it now degrades to the clean `parallel arrays have
  mismatched lengths` `file:line:column` diagnostic.
- Tests: `tests/test_validators.py`, `tests/test_manifest.py`
  (`BudgetDiagnosticsTests`), `tests/test_supports_schema.py`
  (`SupportsSchemaParallelLengthTests`).

### [x] Keep generated build artifacts out of source directories where possible
- Bulky generated C and the symbolic manifest header live under
  `build/generated/data/` (never committed); only small, reviewable
  inventories + the manifest markdown are committed under `reports/`.
- `.gitignore` keeps `build/` out of source.

### [x] Provide custom C record/callback escape hatches without editing generated files
- Code: `scripts/generated_data/escape_hatch.py` (`CSymbolRefField`):
  validates a field value against symbols *declared* in a specific header
  (allowlist by construction) and emits the symbol unquoted as a real C
  token (function pointer / shared constant), not a string literal.
- Consumed in-tree by `classes` (`reservedTerrainTable`) and exercised
  end-to-end by `tests/test_escape_hatch.py`.

### [x] Migrate one complete vanilla vertical slice, then remaining tables in reviewable batches
- Chapter 2 is the complete migrated + linked vertical slice (units,
  shops, traps, event-list composition, chapter bundle) plus the global
  and mechanics tables, each linked with zero ROM/ELF address shift,
  delivered in the documented batches (`docs/generated_data.md`).
- Non-goals (explicit): additional chapters; the 7 unknown
  `Unk_TerrainTable_*` escape-hatch arrays; `data_terrains.c` graphics
  lookup tables; procedural hit/crit/damage/growth/AI formulas;
  hand-written event-script bytecode bodies. All documented as out of
  scope, not silently dropped.

## Acceptance criteria

### A contributor can add a documented character, class, item, chapter, unit group, shop, support, and event through supported inputs
- Doc: `docs/generated_data_tutorial.md` -- concrete, command-driven
  walkthrough for every input type + the escape hatch, using real source
  paths and field names.
- Proof: `tests/test_tutorial.py` -- doc-rot guard (every referenced
  table registered, every referenced source path exists, every input
  type covered) + an end-to-end CLI proof of a good modify (passes) and a
  bad edit (fails with an actionable diagnostic, no traceback).

### Invalid data fails with actionable source locations
- Code: `diagnostics.py` (`SourceLocation`, `GeneratedDataError`,
  `DiagnosticCollector` reports *every* problem, not just the first).
- Every validator carries `file:line:column` + a reference-path
  breadcrumb. Verified across the per-table `*_schema.py` tests.

### Generation is deterministic and CI checks committed public outputs for drift
- `check`/`manifest --check` compare committed inventories + manifest
  against freshly generated content and exit non-zero on drift, writing
  nothing committed.
- CI: `.github/workflows/build.yml` runs `make generated-data-check`
  (now including the aggregate manifest/budget gate) before the ROM
  linker gate.

### Vanilla data round-trips before semantic expansion
- Each table with a hand-written counterpart implements
  `round_trip_errors` and is proven byte/semantics-identical (e.g.
  `characters` 256/256 vs `src/data_characters.c`).
- Tests: `tests/test_*_roundtrip.py`.

## What this closure explicitly does NOT claim
- This report does not itself perform issue-state changes; #5 was
  closed after this merged completion evidence (commit
  `ac0ee5d7f17eb8e70175576cb46d9f320d8013cd`, closed 2026-07-25).
- Does not assert any CI run URL, green pipeline badge, or merged PR.
- Does not migrate chapters beyond Chapter 2, model procedural
  combat/growth/AI formulas, the 7 unknown terrain arrays, graphics
  lookup tables, or replace hand-written event bytecode bodies -- all are
  documented non-goals.
