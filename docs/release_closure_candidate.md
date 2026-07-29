# Issue #9 closure-candidate report

**This report does not close issue #9 and is not a publication approval.**
It is the evidence bundle a maintainer reviews to decide what (if
anything) to do next. See [`docs/release_process.md`](release_process.md)
for the full system this report summarizes.

## Headline result

`make release-check` and `make release-rehearse` both currently, and
correctly, report:

```text
status: blocked
```

with the exact, current, honest inventory of unresolved items (every
tracked top-level path's provenance is `NOASSERTION`/
`redistribution_approved: false`/no reviewer -- see
[`docs/release_data/provenance/`](release_data/provenance/)). This is the
**expected, correct** result, not a defect. Publication remains
mechanically blocked pending explicit human license/provenance approval,
and separately requires a future, distinct authorization for any
write-capable publishing workflow (which does not exist in this
repository and which issue #9 explicitly forbids adding).

## What was implemented

* Public API / SemVer / branch-tag / support policy --
  [`docs/public_api_policy.md`](public_api_policy.md).
* Changelog fragments (`changelog_fragments/*.json`), schema/validator/
  renderer (`scripts/release_rehearsal/changelog.py`), and `CHANGELOG.md`
  with a deterministically-rendered `## [Unreleased]` section.
* Release manifest and identity checks
  (`scripts/release_rehearsal/manifest.py`): SemVer, embedded C metadata
  short/full SHA cross-check, candidate tag text validation (never a real
  tag), changelog, docs, save-format epoch + migrations, previous/next
  supported versions
  (`docs/release_data/version_ledger.json`).
* Migration registry/framework adjacent to
  `scripts/modernize/save_format_tool.py`
  (`scripts/modernize/migrations/`), reusing that tool via subprocess
  rather than duplicating its safety model --
  [`docs/migration_registry.md`](migration_registry.md).
* Source-release guard (`scripts/release_rehearsal/source_guard.py`) --
  separate from, and does not modify, `scripts/artifact_guard.py` -- plus
  provenance manifests
  (`scripts/release_rehearsal/provenance.py`,
  `docs/release_data/provenance/*.json`), seeded factually from the
  current tree, with `mgfembp` pinned to
  `c87e74dcd6c8878b809e013cd8ff0c52baa75332` and
  `redistribution_approved: false`.
* Deterministic archive + rebuild rehearsal
  (`scripts/release_rehearsal/archive_rehearsal.py`): two independent
  builds, SHA-256 hash compare, automatic cleanup, and an explicit,
  precise clean-rebuild blocker report (uninitialized `mgfembp` submodule
  + unresolved provenance), including the documented GitHub
  auto-generated-archive/submodule contradiction.
* `.github/workflows/release-rehearsal.yml` -- `pull_request`/
  `workflow_dispatch` only, top-level `permissions: contents: read`,
  `persist-credentials: false`, no secrets, no artifact upload, no tag/
  release/comment/environment mutation -- and its own permission/safety
  contract is itself checked by `scripts/release_rehearsal/workflow_guard.py`.
* `release.mk` Make targets: `release-test`, `release-migrations-check`,
  `release-rehearse`, `release-check`, `release-changelog-check`.
* 130 new stdlib tests under `scripts/release_rehearsal/tests/` + 17 under
  `scripts/modernize/migrations/tests/` (147 total), covering valid
  behavior and every required actionable-failure class (nested prohibited
  bytes/extensions, traversal/absolute archive members, symlinks/
  hardlinks/FIFOs, missing reviewer, `NOASSERTION`, unapproved
  redistribution, exact-SHA requirement, deterministic archive hashes, no
  retained temp output, workflow permission violations, and the current
  BLOCKED inventory).

## Evidence commands and results (run from this worktree)

```text
$ python3 -m unittest discover -s scripts/release_rehearsal/tests -v
Ran 130 tests in ~39s
OK

$ python3 -m unittest discover -s scripts/modernize/migrations/tests -v
Ran 17 tests in ~0.25s
OK

$ make release-migrations-check
migration registry: ok (1 entry)

$ make release-changelog-check
changelog: ok (3 rendered line(s), aggregate impact: none)

$ make release-check
... (full JSON manifest) ...
release-check status: blocked
release-check: BLOCKED (this is the expected, truthful result -- see reasons above)

$ make release-rehearse
"archive": {"match": true, "hash1": "...", "hash2": "..."}  # identical
"rebuild": {"status": "blocked", ...}  # precise mgfembp/provenance blocker
release-rehearse: two independent archive builds are byte-identical (deterministic)
release-rehearse: candidate publication status: blocked
```

## Existing gates re-verified unaffected

* `python3 scripts/artifact_guard.py --revision HEAD` -- exit 0, unchanged
  (this change never touches `scripts/artifact_guard.py`).
* `python3 -m unittest discover -s tests/upstream_port -v` -- 139/139
  pass.
* `make generated-data-check` -- clean, no drift (13 tables, 722
  records).
* `python3 -m unittest discover -s scripts/generated_data/tests -v` --
  511/511 pass.
* `python3 -m unittest discover -s tools/gba-playtest/tests -v` --
  256 tests, 11 skipped (pre-existing, environment-dependent skips), rest
  pass.
* `python3 -m unittest discover -s scripts/modernize/tests -v` -- 373
  tests; **19 failures + 3 errors are pre-existing and environment-caused,
  not introduced by this change**: every one of them traces to the same
  root cause this change's own rebuild-rehearsal explicitly documents --
  the `mgfembp` git submodule is not checked out in this worktree
  (`git submodule status` shows `-c87e74dcd6c8878b809e013cd8ff0c52baa75332
  mgfembp`), so any real (non-dry-run) modern build attempt fails with
  `make: *** No rule to make target 'mgfembp/data/message_tm_1.bin'`.
  Verified by re-running the identical suite with this change's own
  `Makefile` edit (the one-line `include release.mk`) reverted via
  `git stash -- Makefile`: **the exact same 19 failures/3 errors/3 skips**
  occur either way. `make expansion-modern-linker-check
  MODERN_CONFIG=debug MODERN_ABI=aapcs` was also attempted directly and
  fails with the identical, single root cause. This is a genuine external
  blocker (unresolved submodule provenance/content), not a fabricated
  success and not something this change's tooling papers over -- indeed
  it is exactly the blocker `scripts/release_rehearsal/archive_rehearsal.py`'s
  `rebuild_rehearsal_blocker()` is designed to report precisely instead of
  silently skipping.

## Repository state

* Worktree began at `agent/issue9-release-process` /
  `c717da36c51f94bc6051ec8954bed4ccec2b76fd` (verified: `git log -1`
  matched before any edit).
* Only `Makefile` was modified among previously-tracked files (a single
  `include release.mk` line); every other change is a new file.
* `git status` is clean of anything not intentionally added (build/.dep/
  __pycache__ output is removed and gitignored).

## What remains explicitly open (by design)

* Human license/provenance review and approval of every entry in
  `docs/release_data/provenance/*.json`.
* A future, separately-authorized, write-capable publishing workflow
  (does not exist; not added by this change).
* A real, initialized `mgfembp` checkout with its own reviewed provenance,
  needed before any "clean recursive rebuild" can be attempted for real.

Issue #9 is **not closed** by this report or by any command it describes.
