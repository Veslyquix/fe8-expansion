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

| From epoch | To epoch | Kind | Mechanism |
|---|---|---|---|
| *(none -- no `ExpansionSaveMeta` record at all, i.e. legacy/vanilla save)* | `1` | mechanical | `scripts/modernize/save_format_tool.py migrate SOURCE DEST` |

No `EXPANSION_SAVE_COMPAT_EPOCH` bump beyond `1` has ever shipped from this
repository (see `config.mk` and
[`docs/release_data/version_ledger.json`](release/version_ledger.json)), so no
further transition is registered yet. Any future epoch bump **must** add
its own registry entry before that bump lands -- `make release-check`
fails actionably (via `scripts.release_rehearsal.manifest`'s `migrations` field) if
the registry and `config.mk`'s current epoch disagree in a way the
registry cannot explain.

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
```

`make release-migrations-check` runs `check` (the registry consistency
gate); it is expected to always pass on a well-formed registry, unlike
`make release-check`/`make release-rehearse`, which today truthfully
report the overall candidate as `blocked` for unrelated (provenance/
license) reasons.
