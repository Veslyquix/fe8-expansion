# Issue #9 closure-candidate report

**This report does not close issue #9 and is not a publication approval.**
It is the evidence bundle a maintainer reviews to decide what (if
anything) to do next. See [`docs/release_process.md`](release_process.md)
for the full system this report summarizes.

This report deliberately does **not** hardcode test counts, timings, or
other numbers that drift the moment a test is added, renamed, or the host
running them changes speed. Every claim below is either a command a
reviewer can re-run to see the current, live number, or a structural fact
(e.g. "every entry is `NOASSERTION`") that is independent of any count.

## Headline result

`python3 -m scripts.release_rehearsal.cli check` currently, and correctly,
reports:

```text
status: blocked
```

with the exact, current, honest inventory of unresolved items -- see
[`docs/release_data/provenance/`](release_data/provenance/) (every entry's
`author`/`rightsholder`/`license` is `NOASSERTION`,
`redistribution_approved` is `false`, and `reviewer` is `null`) and the
`mgfembp` submodule's uninitialized state (`git submodule status`). This is
the **expected, correct** result, not a defect. Publication remains
mechanically blocked pending explicit human license/provenance approval,
and separately requires a future, distinct authorization for any
write-capable publishing workflow (which does not exist in this
repository and which issue #9 explicitly forbids adding).

`python3 -m scripts.release_rehearsal.cli check --require-eligible`
mechanically demonstrates this is not merely descriptive prose: it exits
non-zero (see "Evidence commands" below) precisely because the candidate
is not `"mechanically eligible"`.

## What is implemented

* Public API / SemVer / branch-tag / support policy --
  [`docs/public_api_policy.md`](public_api_policy.md).
* Changelog fragments (`changelog_fragments/*.json`), schema/validator/
  renderer (`scripts/release_rehearsal/changelog.py`), and `CHANGELOG.md`
  with a deterministically-rendered `## [Unreleased]` section.
* Release manifest and identity checks
  (`scripts/release_rehearsal/manifest.py`): SemVer, embedded C metadata
  short/full SHA cross-check (mandatory, format-validated), candidate tag
  text validation (never a real tag), changelog, docs, save-format epoch +
  migration-registry consistency *and reachability*, version-ledger
  topology/candidate agreement, C-fallback-metadata-vs-`config.mk`
  consistency, release-doc link validity, and the rebuild rehearsal's own
  status.
* Manifest consistency validators
  (`scripts/release_rehearsal/consistency.py`): version-ledger topology,
  changelog-declared-impact-vs-actual-version-delta (pre-/post-1.0 aware),
  `include/expansion_config.h` C-fallback cross-check, migration-epoch
  reachability -- each with dedicated invalid-fixture tests covering every
  contradiction class.
* Exact, deterministic, generated per-member source allowlist
  (`scripts/release_rehearsal/allowlist.py`,
  `docs/release_data/source_allowlist.json`) -- replaces the previous
  top-level-directory allowlist; a new/unlisted tracked file, or a stale
  entry, is an actionable `make release-check` failure.
* Migration registry/framework adjacent to
  `scripts/modernize/save_format_tool.py`
  (`scripts/modernize/migrations/`), reusing that tool via subprocess
  rather than duplicating its safety model --
  [`docs/migration_registry.md`](migration_registry.md).
* Source-release guard (`scripts/release_rehearsal/source_guard.py`) --
  separate from, and does not modify, `scripts/artifact_guard.py` -- with
  expanded hard-deny coverage (object/library/executable/debug artifacts,
  generic archive/compression containers including Java/JVM variants,
  content-based magic detection for nested archives/executables under any
  extension, default-deny `.map`/`.hex` with an exact, factual, file-level
  exception list in `docs/release_data/map_hex_exceptions.json`) plus
  provenance manifests
  (`scripts/release_rehearsal/provenance.py`,
  `docs/release_data/provenance/*.json`), seeded factually from the
  current tree with exact-or-directory-prefix coverage of the allowlist
  (no gap, no ghost entry, no ambiguous/duplicate coverage), with
  `mgfembp` pinned to `c87e74dcd6c8878b809e013cd8ff0c52baa75332` and
  `redistribution_approved: false`.
* Immutable, Git-blob-bound archive/rebuild rehearsal
  (`scripts/release_rehearsal/git_source.py`,
  `scripts/release_rehearsal/archive_rehearsal.py`): archive content is
  read exclusively through `git ls-tree`/`git cat-file --batch` keyed to
  an exact resolved commit SHA, never the mutable worktree/index (proven
  by dedicated mutation tests); two independent builds, SHA-256 hash
  compare, automatic cleanup; a truthful, four-state
  (`not_run`/`blocked`/`failed`/`verified_success`) rebuild rehearsal with
  a real, executable eligible-path double-compile-and-compare mechanism
  (`run_build_twice`), exercised end-to-end against a hermetic synthetic
  fixture; and the documented GitHub auto-generated-archive/submodule
  contradiction.
* Release-doc relative-link validator
  (`scripts/release_rehearsal/doc_links.py`) -- the three broken
  `docs/release/...` links the independent verifier found (they should
  have pointed at `docs/release_data/...`) are fixed and mechanically
  regression-guarded.
* Hardened, dynamic-JSON workflow guard
  (`scripts/release_rehearsal/workflow_guard.py`): job-level/nested
  `contents: write` (any quoting/whitespace/indentation), shorthand
  `permissions: write-all`, `github.token`/`secrets.*`/`GITHUB_TOKEN`
  interpolation, network tools (`curl`/`wget`), a generalized
  upload/release/publish/deploy `uses:` action-name heuristic, ref
  mutation (`git tag`/`git push`), and common shell-indirection evasions
  (line continuations, `eval`, `base64 -d`, `sh -c`/`bash -c`).
* `.github/workflows/release-rehearsal.yml` -- `pull_request`/
  `workflow_dispatch` only, top-level `permissions: contents: read`,
  `persist-credentials: false`, no secrets, no artifact upload, no tag/
  release/comment/environment mutation -- mechanically asserts the
  expected `blocked` status (`make release-check-expect-blocked`) rather
  than relying on prose, and renders `$GITHUB_STEP_SUMMARY` **dynamically**
  from the tool's own canonical JSON (`cli summary`), never a hardcoded
  status string.
* `release.mk` Make targets: `release-test`, `release-migrations-check`,
  `release-changelog-check`, `release-rehearse`, `release-check`, plus the
  machine-distinct `release-check-require-eligible`/
  `release-rehearse-require-eligible` (intentionally exit non-zero while
  blocked) and `release-check-expect-blocked`/
  `release-rehearse-expect-blocked` (expected-status health checks) gate
  targets, and `release-workflow-guard`.
* A public stdlib `unittest` suite for every module above, including
  dedicated adversarial coverage (misleading extensions/nested paths/
  magic-only detection/path-traversal-shape probes, exact map/hex
  exceptions, git-blob immutability mutation tests, hermetic rebuild
  double-build tests, exact exit-code-per-gate tests, and workflow-guard
  evasion probes for every escalation class listed above).

## Evidence commands (run these; do not trust a fixed number)

```sh
# Full release rehearsal stdlib test suites (current pass/fail count is
# whatever running this actually reports -- see "Verification" below for
# a snapshot from this change's own verification pass).
python3 -m unittest discover -s scripts/release_rehearsal/tests -v
python3 -m unittest discover -s scripts/modernize/migrations/tests -v

# Migration registry / changelog fixture gates.
make release-migrations-check
make release-changelog-check

# Full manifest report (always exits 0 for a well-formed report).
make release-check

# The machine-distinct publication-eligibility gate: EXPECTED to exit
# non-zero (1) while the candidate is blocked -- this is not a failure of
# this change, it is the gate doing its job.
make release-check-require-eligible; echo "exit=$?"

# The expected-status health check: exits 0 only while truly blocked.
make release-check-expect-blocked

# Deterministic archive + rebuild rehearsal (always exits 0 for a
# well-formed report; "rebuild".status is truthfully "blocked" today).
make release-rehearse

# Dynamic workflow guard (machine JSON).
make release-workflow-guard

# Release-doc link validator + exact allowlist completeness (folded into
# `make release-check` above; standalone invocations for direct evidence):
python3 -m scripts.release_rehearsal.doc_links
python3 -m scripts.release_rehearsal.allowlist check

# artifact_guard.py is asserted byte-for-byte unchanged by this change
# (see "Existing gates re-verified unaffected" below).
python3 scripts/artifact_guard.py --revision HEAD
```

## Existing gates re-verified unaffected

* `python3 scripts/artifact_guard.py --revision HEAD` -- exit 0, unchanged
  (this change never touches `scripts/artifact_guard.py`; verified by
  `git diff <starting-HEAD> HEAD -- scripts/artifact_guard.py` producing
  no output).
* `python3 -m unittest discover -s tests/upstream_port -v` -- run this to
  see the current pass count; unaffected by this change (no file under
  `tests/upstream_port` or the modules it exercises was touched).
* `make generated-data-check` -- unaffected; no generated-data table or
  rule was touched.
* `python3 -m unittest discover -s scripts/generated_data/tests -v` --
  unaffected; run for the current count.
* `python3 -m unittest discover -s tools/gba-playtest/tests -v` --
  unaffected; some environment-dependent skips are pre-existing (real
  hardware/emulator-dependent tests), independent of this change.
* `python3 -m unittest discover -s scripts/modernize/tests -v` -- **some
  pre-existing failures/errors are expected here, and every one of them
  traces to the same single root cause this change's own
  `rebuild_rehearsal_blocker()` is designed to report precisely**: the
  `mgfembp` git submodule is not checked out in this worktree (`git
  submodule status` shows a `-`-prefixed line for it), so any real
  (non-dry-run) modern build attempt that needs it fails with `make: ***
  No rule to make target 'mgfembp/...'`. Reproduce and confirm the exact
  attribution with:

  ```sh
  git submodule status                      # confirm "-" (uninitialized)
  python3 -m unittest discover -s scripts/modernize/tests -v 2>&1 \
    | grep -B2 "mgfembp" | head -60         # every modernize failure/
                                             # error mentions mgfembp
  ```

  This is a genuine external blocker (unresolved submodule provenance/
  content), not a fabricated success and not something this change's
  tooling papers over -- it is exactly the blocker
  `scripts/release_rehearsal/archive_rehearsal.py`'s
  `rebuild_rehearsal_blocker()` reports precisely instead of silently
  skipping or fetching unreviewed content.
* Generated-data, upstream, and host/default/runtime/public build gates
  remain feasible to run **without** fetching unapproved `mgfembp`
  wherever they do not themselves require it; wherever a gate's own
  target genuinely requires `mgfembp` content (e.g. a modern ROM link
  step), that is reproduced and attributed above, never fetched or
  fabricated green.

## Repository state

* Worktree began at `agent/issue9-release-process` /
  `45fb67e41134faffe9b58bedc70ddea11d5a5bb2` (this change's own starting
  point; verified by `git log -1` before any edit).
* `scripts/artifact_guard.py` is untouched (see above).
* No tag, release, asset, comment, environment, protected ref, or other
  branch was created, moved, or deleted; no `contents: write` permission
  was added anywhere.
* No root `LICENSE` was added; no author/rightsholder/license/reviewer was
  invented; `redistribution_approved` was never set to `true` anywhere
  live.

## What remains explicitly open (by design)

* Human license/provenance review and approval of every entry in
  `docs/release_data/provenance/*.json`.
* A future, separately-authorized, write-capable publishing workflow
  (does not exist; not added by this change).
* A real, initialized `mgfembp` checkout with its own reviewed provenance
  and identity verification, needed before any "clean recursive rebuild"
  can be attempted for real (the eligible code path exists and is tested
  end-to-end against a hermetic synthetic fixture, but is not, and must
  not be, exercised against the real, still-unapproved `mgfembp`).

Issue #9 is **not closed** by this report or by any command it describes.
