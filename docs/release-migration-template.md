# Release migration template

> **This is a template, not a current release's migration guide.** No
> tagged version-to-version migration exists yet in this repository as of
> commit `68871ed5b6ef3c47b301e26824ca7725383ab606`. Copy this file's
> structure into a real, dated migration doc (for example
> `docs/migration-v0.1-to-v0.2.md`) when a future framework version
> actually ships a breaking or notable change, and fill in every bracketed
> placeholder with real facts verified against that release's source and
> commands. Do not fill in this file itself with invented specifics.

## Migration: `[FROM_VERSION]` → `[TO_VERSION]`

- **From**: `[FROM_VERSION]` (`config.mk` `EXPANSION_VERSION_MAJOR.MINOR.PATCH`, commit `[FROM_SHA]`)
- **To**: `[TO_VERSION]` (commit `[TO_SHA]`)
- **Config-identity fingerprint change**: `[FROM_FINGERPRINT]` → `[TO_FINGERPRINT]`
  (see [`docs/config_identity.md`](config_identity.md) for how this is computed
  and why it changed, if it did)

## Breaking changes

List every change that is not purely additive/backward-compatible. For
each: what changed, why, and which lane(s) (modern/archival) it affects.

- `[CHANGE_1]` — `[modern | archival | both]` — `[reason]`

## Config identity / save format

- Did `EXPANSION_VERSION_MAJOR`/`MINOR`/`PATCH` change? `[yes/no + values]`
- Did any other fingerprinted setting change (ABI, ROM size, text shift,
  ROM identity)? See [`docs/config_identity.md`](config_identity.md)'s
  fingerprint-fields table. `[list]`
- Did `EXPANSION_SAVE_COMPAT_EPOCH` change? If so, per
  [`docs/save_format.md`](save_format.md), explain exactly what on-media
  layout change forced the bump and what compatibility classification
  older saves now receive. `[explanation]`

## Data migration

- Which `src/data/*.json` tables changed schema (not just content)? Link
  the relevant [`docs/generated_data.md`](generated_data.md) section.
  `[list]`
- Is a one-time data-migration script needed for existing content authors'
  JSON, or is the change purely additive? `[explanation]`
- Did the committed inventories/manifest (`reports/generated_data_*`)
  regenerate cleanly via `make generated-data-check`? `[pass/fail + link]`

## API / interface changes

- Public headers changed: `[list `include/*.h` files and the specific
  symbols added/removed/changed]`
- If this migration involves issue **#10** (extensible ID contracts),
  **#11** (debug-tools extension surface), or **#13** (regression/host
  matrix policy) reaching a final merged interface for the first time,
  say so explicitly here and update
  [`docs/architecture.md`](architecture.md#public-extension-boundaries--later-integration-slots)
  in the same change — do not leave that document's "later integration
  slot" language stale once an interface actually ships.

## Debug and test surface changes

- Debug-tools config gate/hotkeys changed: `[list, link `docs/debugtools.md`]`
- New/changed `tools/gba-playtest` scenarios or fingerprints: `[list]`
  Remember these are reviewed oracles per
  [`docs/issue-resolution-policy.md`](issue-resolution-policy.md#baseline-and-fingerprint-review) —
  explain why each fingerprint changed.

## Validation

List every command actually run for this migration and its result (paste
output or link a CI run — do not summarize as "tests pass"), per
[`docs/issue-resolution-policy.md`](issue-resolution-policy.md#issue-closure-evidence):

```
[command 1]
[command 2]
```

## Provenance

- PR(s): `[links]`
- Issue(s): `[links]`
- Reviewer(s) for any baseline/fingerprint path touched: `[names, per CODEOWNERS]`

## Rollback

- Is the previous version's ROM/save still loadable after this migration?
  `[yes/no + explanation]`
- Exact steps to revert (git ref, `make` target) if this migration needs
  to be rolled back: `[steps]`
