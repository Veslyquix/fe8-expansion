# Public API and SemVer policy (issue #9)

This document defines what counts as this project's **public API** for
SemVer purposes, and the branch/tag conventions used to track it. It does
not, by itself, authorize publishing anything -- see
[`docs/release_process.md`](release_process.md)'s "Legal and provenance
boundary" for why publication remains mechanically blocked today.

## What "public API" means here

This is a ROM-hacking/decompilation expansion framework, not a library, so
"public API" is scoped to the **externally observable contracts** a
downstream consumer (a save file, a CI pipeline, a fork, or a tool reading
a built ROM) can depend on:

* **The embedded ROM identity/metadata contract**: `config.mk`'s
  `EXPANSION_VERSION_*`/`EXPANSION_ROM_*`/`EXPANSION_SAVE_COMPAT_EPOCH`
  fields, `include/expansion_config.h`'s `FE8_EXPANSION_*` macros, and
  `include/expansion_metadata.h`'s `struct ExpansionMetadata` binary layout
  (see [`docs/config_identity.md`](config_identity.md)).
* **The on-media save format**: `include/save_format.h`'s
  `struct ExpansionSaveMeta` layout and `enum SaveCompatState` semantics
  (see [`docs/save_format.md`](save_format.md)).
* **The supported build entry points**: `make`/`make legacy`/
  `make expansion-modern-*` target names and their documented command-line
  overrides (see [`docs/quickstart.md`](quickstart.md)).
* **The host-side tooling CLIs** under `scripts/modernize/*.py` and
  `scripts/release_rehearsal/*.py`: subcommand names, argument names, and exit-code
  contracts.

Internal implementation details (object layout inside a translation unit,
private helper functions, generated intermediate files under `build/`,
non-committed reports) are **not** public API and may change in a patch
release.

## Pre-1.0 rules (current: see `config.mk`)

While `EXPANSION_VERSION_MAJOR == 0`:

* `MINOR` bumps may include breaking changes to any public-API surface
  above. This mirrors SemVer 2.0.0's own pre-1.0 carve-out (spec item 4).
* `PATCH` bumps are reserved for backward-compatible fixes only: no public
  API contract listed above may change observable behavior for an existing
  consumer.
* `EXPANSION_SAVE_COMPAT_EPOCH` is bumped independently of
  `EXPANSION_VERSION_*` -- see `config.mk`'s own comment and
  [`docs/save_format.md`](save_format.md). A save-format-breaking change
  MUST bump the epoch (regardless of which version component changes) and
  MUST have a registry entry in [`docs/migration_registry.md`](migration_registry.md).
* Every change that touches a public-API surface above MUST add a
  `changelog_fragments/*.json` fragment declaring an honest `semver_impact` (see
  [`changelog_fragments/README.md`](../changelog_fragments/README.md)) -- `make
  release-check` fails actionably if the fragment's impact and the actual
  `config.mk` version delta disagree.

## Post-1.0 rules

Once `EXPANSION_VERSION_MAJOR >= 1`:

* `MAJOR` -- any breaking change to a public-API surface above.
* `MINOR` -- backward-compatible additions (a new build target, a new
  optional `config.mk` field with a safe default, a new save-format field
  that does not change classification for an existing valid save).
* `PATCH` -- backward-compatible fixes only, exactly as pre-1.0.
* The same `EXPANSION_SAVE_COMPAT_EPOCH` and changelog-fragment
  requirements above continue to apply unchanged.

## Branch and tag conventions

This repository does not create any of the refs described below as part of
issue #9 -- these are the conventions a human maintainer follows when they
later decide to cut a release; `scripts/release_rehearsal/manifest.py` only
*validates candidate tag text* (see below), it never creates a tag.

* **`master`** -- the trunk. Every merged pull request lands here. CI
  (`.github/workflows/build.yml`) and this rehearsal
  (`.github/workflows/release-rehearsal.yml`) both gate it.
* **`upcoming`** (optional, maintainer-created when needed) -- an
  integration branch for changes staged ahead of a release that are not
  yet ready to land on `master`. Not created by any tooling in this
  repository.
* **`expansion`** (optional) -- a long-lived branch for larger expansion
  framework work landing in slices, mirroring the `agent/issueN-*` working
  branches already used in this repository's development process. Not a
  release branch by itself.
* **`vX.Y.Z` tags** -- the candidate tag text format is exactly
  `v<major>.<minor>.<patch>` (e.g. `v0.1.0`), matching
  `config.mk`'s resolved `EXPANSION_VERSION_*`. This is the exact text
  `scripts/release_rehearsal/manifest.py`'s `candidate_tag` field validates
  (`CANDIDATE_TAG_RE`) -- validation only, this repository's tooling never
  runs `git tag` on this text. A human maintainer creates the real tag by
  hand, after independently confirming the manifest reports
  `"status": "mechanically eligible"` **and** obtaining the separate human
  legal/provenance/publish authorization described in
  [`docs/release_process.md`](release_process.md).
* **`X.Y.Z` (no `master`/`upcoming`/`expansion` prefix, bare version)** --
  reserved for a future maintenance branch cut from a tag, e.g. `0.1.x`,
  if a fix needs to be urgently backported after `master` has moved on.
  Not created by any tooling in this repository.

## Support, EOL, and urgent-fix policy

* **Supported version(s)**: recorded factually in
  [`docs/release_data/version_ledger.json`](release/version_ledger.json)
  (`current_version`, `previous_supported_version`,
  `next_supported_version`, and the `supported` list with each entry's
  `status`/`eol`). No release has ever been tagged from this repository,
  so `previous_supported_version`/`next_supported_version` are explicitly
  `null` today -- this file is meant to be updated by hand alongside a
  real `config.mk` version bump, never inferred or fabricated by tooling.
* **EOL**: a supported version's `eol` field in the ledger becomes a date
  (ISO 8601) when a maintainer decides to end support for it; until then
  it stays `null`. This repository's tooling never sets this field
  automatically.
* **Urgent fixes**: a fix that must ship outside the normal `master` flow
  (e.g. a save-corruption regression) is cut from the affected maintenance
  branch (see `X.Y.Z` above), gets its own `changelog_fragments/*.json` fragment
  with `"category": "fixed"`, and bumps `PATCH` only -- never `MINOR`/
  `MAJOR` -- regardless of how urgent it is, since an urgent fix must, by
  definition, stay backward-compatible for it to be safely urgent.

## Relationship to Wave 0 (`docs/issue-resolution-policy.md`)

Wave 0 deliberately made **no** decision about SemVer scope, release
branch/tag conventions, or a source-release allowlist, and explicitly
deferred all of it to this issue (see that document's "No source-release
allowlist in Wave 0" section). This document is that deferred decision for
the public-API/SemVer/branch/tag/support half of issue #9; see
[`docs/release_process.md`](release_process.md) for the rest (changelog,
release manifest, migrations, provenance, source guard, and archive/
rebuild rehearsal).
