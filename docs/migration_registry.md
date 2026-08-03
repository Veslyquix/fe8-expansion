# Save-format migration registry (issue #9)

`scripts/modernize/migrations/registry.py` declares every known
`EXPANSION_SAVE_COMPAT_EPOCH` transition and whether it is mechanically
automatable or requires manual human steps. It lives next to, and reuses
(never re-implements or weakens),
[`scripts/modernize/save_format_tool.py`](../scripts/modernize/save_format_tool.py) --
see that tool's own docstring and [`docs/save_format.md`](save_format.md)
for the classification/publish safety model this registry shells out to
rather than duplicating.

## Current registry

Issue #9 residual-hardening: every declared transition's source and
target are each an **exact `(format_version, compat_epoch)` pair**, never
a single conflated "epoch" number. The two fields happen to be
numerically equal on both ends of both transitions registered today --
that is an incidental fact of these two transitions' own history, never
assumed true for any other/future transition (`MigrationStep` models
`compat_epoch_from`/`compat_epoch_to` completely independently of
`epoch_from`/`epoch_to`; see `scripts/modernize/migrations/registry.py`'s
own docstrings for the exact enforcement).

| From formatVersion | From compatEpoch | To formatVersion | To compatEpoch | Kind | Mechanism |
|---|---|---|---|---|---|
| *(none -- no `ExpansionSaveMeta` record at all, i.e. legacy/vanilla save)* | *(none)* | `1` | `1` | mechanical | `scripts/modernize/save_format_tool.py migrate SOURCE DEST` |
| `1` | `1` | `2` | `2` | mechanical | `scripts/modernize/save_format_tool.py migrate SOURCE DEST` |

`EXPANSION_SAVE_COMPAT_EPOCH` has been bumped once, from `1` to `2`
(`config.mk`; issue #18 sprint 2 -- `struct ExpansionUserPrefs`,
[`include/expansion_save_prefs.h`](../include/expansion_save_prefs.h), now
occupies part of `struct ExpansionSaveMeta`'s `reserved` tail; see
[`docs/save_format.md`](save_format.md)). This registry entry was added
during the issue #9 release-branch/origin-master merge that first brought
that bump into this branch (origin/master's own issue #18 work never had
this registry module to update, since it did not exist on that branch);
the underlying mechanical capability itself (accepting a
`SAVE_COMPAT_MIGRATABLE_OLDER` source, preserving any bytes already
present in `reserved`) was already implemented and documented directly on
`scripts/modernize/save_format_tool.py`/`docs/save_format.md` before this
registry entry was added -- this is a registry-bookkeeping addition, not a
new migration mechanism. No `EXPANSION_SAVE_COMPAT_EPOCH` bump beyond `2`
has ever shipped from this repository (see `config.mk` and
[`docs/release_data/version_ledger.json`](release_data/version_ledger.json)), so no
further transition is registered yet. Any future epoch bump **must** add
its own registry entry (its own exact `(format_version, compat_epoch)`
source/target pair, not merely a bumped `epoch_to`) before that bump
lands -- `make release-check` fails actionably (via
`scripts.release_rehearsal.manifest`'s `migrations` field) if the registry
and `config.mk`'s current epoch disagree in a way the registry cannot
explain, and `registry.py check`/`MigrationStep.__post_init__` both
independently refuse a step whose `compat_epoch_from`/`compat_epoch_to`
disagree in shape with `epoch_from`/`epoch_to` (e.g. one is the explicit
legacy/absent `None` sentinel while the other is a real number) or whose
`compat_epoch_to` does not strictly exceed `compat_epoch_from`.

A checksum-valid source whose raw `formatVersion` matches a step's
declared `epoch_from` is **not**, on its own, sufficient proof it belongs
to that step: `classify_save_compat_raw()` never even inspects
`compatEpoch` once `formatVersion` alone has already resolved the state to
`SAVE_COMPAT_MIGRATABLE_OLDER`, so a forged/corrupt source could carry a
genuinely wrong `compatEpoch` (e.g. `formatVersion` `1` with `compatEpoch`
`999`) while still checksum-validating and classifying identically to a
genuine epoch-1 save. Both `dry_run()` and `run()` independently re-read
and verify the source's full, exact `(format_version, compat_epoch)` pair
against the step's declared `epoch_from`/`compat_epoch_from` before ever
invoking `save_format_tool.py` (`_exact_source_state_mismatch()`), and
`run()` separately re-verifies the full exact **target** pair against the
actually-published destination afterwards -- a correct `formatVersion`
alone is never accepted as sufficient proof the declared `compat_epoch_to`
was also produced.

## Contract

* **Out-of-place only.** Every mechanical step requires a distinct
  `--dest`/destination path; `scripts/modernize/save_format_tool.py`
  itself refuses source==destination (by resolved path *and* by
  device+inode identity), regardless of `--force`.
* **Deterministic `--check`-equivalent (`registry.py check` /
  `make release-migrations-check`)**: validates the registry's internal
  consistency (no duplicate transitions, `epoch_to > epoch_from`, every
  mechanical entry has an underlying tool to shell out to, every manual
  entry declares at least one concrete step) with **no file I/O beyond
  checking that `save_format_tool.py` exists**. Always deterministic,
  never touches a save.
* **Deterministic `--dry-run`**: classifies a given source image (via
  `save_format_tool.py validate --expect ...`) to report whether a
  mechanical migration *would* succeed, without writing anything. Refuses
  outright (without even reading the source) for a manual step.
* **`run`**: executes a mechanical step by shelling out to
  `save_format_tool.py migrate`; refuses outright for a manual step,
  printing its declared `manual_steps`.
* **Synthetic fixtures only.** Every test in
  `scripts/modernize/migrations/tests/` builds its SRAM images in memory
  (mirroring `scripts/modernize/tests/test_save_format_tool.py`'s existing
  guardrail) -- this repository never commits or migrates a real user
  save.

## Manual-step declarations

A future `EXPANSION_SAVE_COMPAT_EPOCH` bump whose migration cannot be
expressed as a byte-level classify/rewrite transform (e.g. one that needs
game-logic-aware reinterpretation of a field, not just a layout change)
must be registered with `kind="manual"` and a non-empty `manual_steps`
tuple describing exactly what a human must do; `registry.py`'s
`MigrationStep.__post_init__` enforces that a manual entry cannot omit
steps and a mechanical entry cannot declare any (those are mutually
exclusive by construction, not just by convention).

## CLI

```sh
python3 -m scripts.modernize.migrations.cli list
python3 -m scripts.modernize.migrations.cli check
python3 -m scripts.modernize.migrations.cli dry-run --to-epoch 1 --source SRAM.bin
python3 -m scripts.modernize.migrations.cli run --to-epoch 1 --source SRAM.bin --dest OUT.bin
python3 -m scripts.modernize.migrations.cli dry-run --from-epoch 1 --to-epoch 2 --source SRAM.bin
python3 -m scripts.modernize.migrations.cli run --from-epoch 1 --to-epoch 2 --source SRAM.bin --dest OUT.bin
```

`registry.py`'s own public CLI keys a declared step's *lookup* by
`--from-epoch`/`--to-epoch` (`format_version` only -- unchanged, existing
shape); each `REGISTRY` entry it resolves also carries its own,
independently-declared `compat_epoch_from`/`compat_epoch_to`, which
`dry_run()`/`run()` thread through internally without any further flag
from this CLI's own caller.

`make release-migrations-check` runs `check` (the registry consistency
gate); it is expected to always pass on a well-formed registry, unlike
`make release-check`/`make release-rehearse`, which today truthfully
report the overall candidate as `blocked` for unrelated (provenance/
license) reasons.

## Underlying `save_format_tool.py migrate` target semantics

`registry.py run()` never shells out to `save_format_tool.py migrate` with
the conflating `--to-epoch` shorthand. It always passes the precise,
independent pair:

```sh
python3 -m scripts.modernize.save_format_tool migrate SOURCE DEST \
    --expect SAVE_COMPAT_MIGRATABLE_OLDER \
    --to-format-version FV --to-compat-epoch CE
```

* **`--to-format-version FV --to-compat-epoch CE`** -- the precise,
  independent target pair this registry always uses: `FV` stamps the
  produced destination's raw `formatVersion` and `CE` independently stamps
  its raw `compatEpoch`, never assumed equal to one another. Both must be
  given together (`save_format_tool.py` itself refuses one without the
  other) and are mutually exclusive with `--to-epoch`.
* **`--to-epoch N`** -- a backward-compatible shorthand available directly
  on `save_format_tool.py`'s own CLI for a human/ad-hoc invocation outside
  this registry (truthfully documented there as stamping the *same*
  numeric value `N` into both `formatVersion` and `compatEpoch`); mutually
  exclusive with `--to-format-version`/`--to-compat-epoch` -- never
  silently combined or reinterpreted. `registry.py` itself never emits
  this shorthand internally, precisely because a step's two target fields
  are never assumed equal for any future transition.

After a successful `migrate` invocation, `registry.py run()` independently
re-reads the *published* destination and re-checks **both** its raw
`formatVersion` and `compatEpoch` fields against the step's declared
`epoch_to`/`compat_epoch_to` -- a correct `formatVersion` alone is never
accepted as proof the declared `compat_epoch_to` was also actually
produced (see `scripts/modernize/migrations/registry.py`'s `run()`
docstring).
