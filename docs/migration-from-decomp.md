# Migrating from the decomp-base/agbcc workflow to the modern framework

This is a practical guide for contributors used to the original
decomp-base/agbcc workflow (`make fireemblem8.gba`, byte-matching against
`asm/`) who now want to work on the **supported modern GCC/AAPCS
framework** instead. It does not replace
[`docs/quickstart.md`](quickstart.md) or
[`docs/archival-decomp.md`](archival-decomp.md) — it is the bridge between
them.

## Why this exists

Historically, this repository's default build, tooling, and contribution
guide were all decomp-matching-first (agbcc, byte-identical output). That
is now the **archival, explicitly-unsupported side lane**. The
default/supported path is a modern `arm-none-eabi` GCC/AAPCS release build
that does not need to be byte-identical to the original ROM. See
[`docs/architecture.md`](architecture.md) for why, and
[`docs/issue-resolution-policy.md`](issue-resolution-policy.md#supported-modern-path-vs-archival-decomp-path)
for the governance framing.

## Step-by-step migration

1. **Stop assuming `make`/`make all` builds the agbcc ROM.** It now
   unconditionally builds and boot-verifies the modern release ROM
   (`build/expansion-modern/release/aapcs/fireemblem8.gba`). To reach the
   archival ROM you now must name it explicitly:
   ```bash
   make legacy -j$(nproc)      # identical output to the old `make fireemblem8.gba`
   ```
2. **Re-run quickstart without `--legacy`.**
   ```bash
   ./scripts/quickstart.sh
   ```
   This installs the modern toolchain + libmGBA (no agbcc), builds, and
   boot-verifies the modern release ROM. See
   [`docs/quickstart.md`](quickstart.md) for the full flag/troubleshooting
   reference, and only pass `--legacy`/`--refresh-agbcc` when you actually
   need decomp-matching work.
3. **Retarget content authoring at generated data, not raw C tables.**
   Characters, classes, items, supports, and the Chapter 2 slice are
   authored as validated JSON under `src/data/` and compiled to typed
   C89 — see [`docs/generated_data_tutorial.md`](generated_data_tutorial.md).
   Hand-editing `build/generated/data/*.c` is never the supported path in
   either build lane.
4. **Retarget verification at compile/link/boot success, not byte-diff.**
   Modern-lane correctness is judged by
   `expansion-modern-boot-check`/`expansion-modern-linker-check`
   (deterministic runtime fingerprints at frames 0/60/120, budget/shift/
   overlay gates), not equality with the vanilla ROM. `asmdiff.sh` and
   byte-matching remain meaningful only for the archival lane.
5. **Know the config/data differences.**
   - The modern lane has an explicit, versioned config-identity fingerprint
     (`config.mk` + `modern.mk` presets) embedded in every ROM — see
     [`docs/config_identity.md`](config_identity.md). The archival lane has
     none of this; it keeps its own hardcoded identity
     (`src/rom_header.s`), entirely unaffected by `config.mk`.
   - Save-format compatibility is currently format/epoch 2 because the
     checksummed locale-prefs subrecord gives part of the reserved tail a
     defined meaning. Classification checks format before epoch, and host
     migration is out-of-place — see [`docs/save_format.md`](save_format.md).
   - The four issue #6 starter switches default off and carry dependency
     checks; expansion-localized strings use stable IDs/catalogs independent
     of vanilla `MSG_*`. See [`starter_features.md`](starter_features.md) and
     [`localization.md`](localization.md).
6. **Retarget authoring and tests together.** Run `make generated-data-check`
   after data edits and `make localization-test` after catalog/locale edits.
   For runtime changes, run both debug and release modern linker checks; do
   not substitute archival byte comparison for modern behavior evidence.
7. **Pick the right issue/PR evidence template.** State which lane
   (modern/archival) your change targets and run the commands in
   [`CONTRIBUTING.md`](../CONTRIBUTING.md)'s fast-checks/full-gates
   sections for that lane.

## What does not change

- The archival agbcc lane (`make legacy`) remains available, unbroken, and
  unchanged for decomp-matching work — it was not deleted.
- Decompiling individual `asm/` functions to `src/*.c` is still exactly the
  workflow in [`docs/archival-decomp.md`](archival-decomp.md) when that is
  your goal.
- Generated-data inventories and manifests (`reports/generated_data_*`) are
  produced by the same platform regardless of which ROM you ultimately
  build.

## Rollback boundary

If a modern-lane change causes a regression you can't immediately resolve,
you can always fall back to `make legacy`/`make fireemblem8.gba` for
decomp-matching work — the archival lane's build path, linker script
(`ldscript.txt`), and header (`src/rom_header.s`) are untouched by anything
in the modern lane. There is no migration step that removes or requires
removing the archival lane; the two build paths are independent by design
(see [`docs/framework-support.md`](framework-support.md)).
