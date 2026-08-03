# `id_space_active.h` cap-DAG closure (Issue #18 branch-local report)

## Reported symptom

`generated-data-check` (verify's own `generated-data-check` gate, always
run at the default, unset-`FE8_ITEM_ID_CAP` cap) was reported to leave
`build/generated/data/id_space_active.h` at the default cap (0xCD/206
records), after which a *subsequent* `FE8_ITEM_ID_CAP=0xCE` item gate
would "reuse the existing target by mtime and compile/read [the] stale
header" -- the compiled `gItemData[]` table expecting 207 records while
the header (and therefore the compile-time static assert against it)
still claimed 206. The reported root cause: "cap is missing from Make
DAG/state".

## What this investigation found

**Not reproduced.** The literal, real, full 11-gate
`python3 -m scripts.upstream_port verify --jobs 2` sequence was run, once,
start to finish, in THIS repository's own artifact-rich `build/` tree --
no `clean`, no isolated/temp build root, the exact same shared
`build/generated/data/` and `build/expansion-modern/{debug,release}`
paths every gate and every developer invocation already reuses -- and
every gate passed:

```
[PASS] gba-playtest-host-suite
[PASS] upstream-port-tests
[PASS] localization-host-suite
[PASS] artifact-guard
[PASS] default-lane-check
[PASS] quickstart-legacy-check
[PASS] generated-data-check
[PASS] modern-linker-check-debug
[PASS] modern-linker-check-release
[PASS] modern-itemexpansion-check-debug
[PASS] modern-itemexpansion-check-release
```

The `id_space_active.h`/`.json`/`.md` surfaces and the compiled
`data_items.o` objects were independently re-checked at every named
transition (default -> 0xCE debug -> 0xCE release -> a manual reverse
default `generated-data-check`) and always agreed with each other; a
same-cap warm rerun never advanced any surface's mtime.

**Real, but narrower, structural gap identified and closed.** The
`generated-data-check` gate's own recipe (`generated_data.mk`) never
referenced `$(GENERATED_DATA_ITEM_CAP_STAMP)` -- the one real,
Make-tracked file every other cap-aware rule (the grouped
`$(GENERATED_DATA_ACTIVE_OUTPUTS)` rule, every linked table's `.c` rule)
keys its own staleness on. The gate instead heals the ACTIVE surfaces
(and the `items` table) via *direct* python calls
(`idspace active-check`, `check --table items`) inside its own recipe,
which are correct on their own terms -- both resolve THIS invocation's
own env cap and rewrite write-if-changed, independent of the stamp's
prior mtime -- but this is a genuine asymmetry between "what the gate's
recipe actually (already correctly) does" and "what the Make dependency
graph believes happened". That asymmetry is exactly the literal "cap
missing from Make DAG/state" the report named, even though the
independent `active-heal` self-heal (invoked, unconditionally, from the
stamp's own FORCE recipe on every *other* cap-aware build) already
prevented it from producing an observable stale-header defect in every
sequence actually exercised here.

This is the same investigative shape as the prior
`reports/itemexpansion_gate_order_race_diagnosis.md` finding: the exact
reported symptom did not reproduce, but a real, related structural risk
in the same area was found and hardened anyway, rather than leaving a
known asymmetry unfixed on the theory that today's independent self-heal
happens to mask it.

## Fix applied

`generated_data.mk`: `generated-data-check` now declares
`$(GENERATED_DATA_ITEM_CAP_STAMP)` as an ordinary prerequisite (a second
prerequisite line, appended after the stamp variable/rule is defined
further down the file; GNU Make accumulates a target's prerequisites
across multiple appearances, so no reordering of the file was needed).
This closes the gap for good: the gate now always reconciles the SAME
stamp every other cap-aware rule relies on, so the graph and the on-disk
cap state can never observably diverge, at the cost of one extra
(idempotent, sub-second, write-if-changed) stamp-recipe invocation per
`generated-data-check` run. No gate's observable output changed --
confirmed by re-running `make generated-data-check` at the default cap,
at `FE8_ITEM_ID_CAP=0xCE`, and back, both before and after the edit, with
byte-identical resulting surfaces and unchanged pass/fail behavior.

## Regression coverage added

`scripts/modernize/tests/test_generated_data_check_cap_dag.py`:

* `GeneratedDataCheckStampPrerequisiteTests` -- fast (~1 s),
  toolchain-independent structural pins: the new prerequisite edge
  itself, that the stamp's own inline self-heal calls are untouched, and
  a `make -n` dry-run proving the stamp recipe is actually reached.
* `GeneratedDataCheckArtifactRichCapDagSequenceTests` -- a real (not
  `-n`) integration test, against THIS repository's actual, shared
  `build/generated/data/` (no temp copy, no `clean`), driving the
  gate-relevant default -> 0xCE -> 0xCE (warm) -> default (reverse)
  sequence and asserting the C header / JSON / Markdown surfaces agree
  at every transition and that same-cap warm reruns never advance any
  surface's mtime.
* `ExpandedCapConsumerObjectAgreementTests` (toolchain-gated, no
  libmGBA/ROM-boot needed) -- compiles the real `data_items.o` for both
  the `debug` and `release` modern configs at the expanded cap and
  proves the compiled object's own record count -- derived
  proportionally from its data-section size, never a hardcoded byte
  count -- agrees with the header's `ITEM_ID_ACTIVE_RECORD_COUNT`: the
  actual "gItem expansion expects 207 but sees 206" consumer-side risk
  this issue names, pinned without paying for a full ROM link/boot.

## Verification

* `make generated-data-check` (default cap): `[PASS]`, restores
  0xCD/206.
* `FE8_ITEM_ID_CAP=0xCE make generated-data-check`: `[PASS]`, moves to
  0xCE/207; a warm rerun at the same cap leaves every ACTIVE surface's
  mtime untouched.
* A subsequent plain `make generated-data-check` restores 0xCD/206
  again, with a warm rerun again leaving mtimes untouched.
* The new regression module: 6/6 tests pass (fast tier ~1.5 s,
  artifact-rich sequence tier ~253 s, toolchain-gated consumer-object
  tier ~88 s).
* Full `python3 -m scripts.upstream_port verify --jobs 2`: 11/11 gates
  `[PASS]`, run against this same artifact-rich worktree (no `clean`).
