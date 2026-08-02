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
  exception list in `docs/release_data/map_hex_exceptions.json`).
  **Every candidate file/member -- filesystem closed-world scan
  (`scan_tree`), archive members (`scan_archive_members`), and the
  non-git/extracted-archive-candidate and archive-build fallback paths
  (`archive_rehearsal._filesystem_allowlisted_files`) alike -- is now
  matched against the exact allowlist; a directory is walked through only
  as a structural parent and never itself authorizes anything nested
  under it** (a fresh, independent review found a residual top-level/
  directory-prefix membership check in these paths; `src/unlisted.c` now
  fails even when `src/known.c` is allowlisted, in both filesystem and
  archive-member modes).
  Provenance manifests
  (`scripts/release_rehearsal/provenance.py`,
  `docs/release_data/provenance/*.json`) are, likewise, now **one exact
  record per exact allowlisted path** (never a directory-prefix/category-
  level grant): a small, human-curated `PROVENANCE_ROOT_SEED` plus
  `generate_exact_entries()` mechanically fan every already-recorded fact
  out to its own exact record per file, but runtime validation
  (`evaluate_coverage`) only ever reads the exact records actually
  committed to disk -- a new allowlisted file with no dedicated exact
  provenance entry fails, exactly like an unlisted tracked file fails
  allowlist completeness. **Update (mandatory-correction round, see below):**
  `mgfembp` no longer sits *inside* the included allowlist at all -- it is now
  its own explicit export-exclusion record
  (`docs/release_data/export_exclusions.json`,
  `scripts/release_rehearsal/tree_coverage.py`); its provenance record keeps
  its exact path, its `c87e74dcd6c8878b809e013cd8ff0c52baa75332` pin (cross-
  checked against the real gitlink object id via `check_gitlink_pins()`), a
  `url` matching `.gitmodules` (`submodule_binding.py`'s three-way binding),
  and `redistribution_approved: false`.
* Immutable, Git-blob-bound archive/rebuild rehearsal
  (`scripts/release_rehearsal/git_source.py`,
  `scripts/release_rehearsal/archive_rehearsal.py`): archive content is
  read exclusively through `git ls-tree`/`git cat-file --batch` keyed to
  an exact resolved commit SHA, never the mutable worktree/index (proven
  by dedicated mutation tests); two independent builds, SHA-256 hash
  compare, automatic cleanup; a truthful, four-state
  (`not_run`/`blocked`/`failed`/`verified_success`) rebuild rehearsal with
  a real, executable eligible-path double-compile-and-compare mechanism
  (`run_build_twice_from_immutable_source()`, wired into
  `rebuild_rehearsal_blocker()`), exercised end-to-end -- via
  `RebuildRehearsalBlockerEndToEndBuildTests`, which calls
  `rebuild_rehearsal_blocker()` **itself** -- against a hermetic
  synthetic fixture, for every one of `verified_success`/a mismatch/a
  build failure/a missing declared output/a shared-directory refusal/an
  input-source mutation (guardian-correction remediation D1: an
  independent review found the *previous* version of this bullet, and a
  same-named test's own docstring, described a *different*, legacy,
  copy-based `run_build_twice()` helper as if it drove
  `rebuild_rehearsal_blocker()` end-to-end -- it never did, and that
  legacy helper has since been deleted outright rather than left as a
  standing misattribution risk); and the documented GitHub
  auto-generated-archive/submodule contradiction. The documented
  non-git/extracted candidate path (a
  genuine extracted archive, with a required exact 40-lowercase-hex
  `--target-sha` override) is now fully working end-to-end: a fresh,
  independent review reproduced it (and a well-formed-but-nonexistent
  `--target-sha` against a real git repository) tracebacking as an
  unhandled exception instead of the documented `EXIT_TOOLING_ERROR`
  (`2`) -- `check`/`summary`/`rehearse` now route through one single,
  shared top-level exception boundary (`cli.py`'s `_run_guarded`/
  `EXPECTED_TOOLING_ERRORS`), `evaluate_rebuild_eligibility()` never
  invokes `git submodule status` (or any other git command) against a
  non-git `repo_root`, and a declared allowlist member with no on-disk
  representation at all (e.g. an absent `mgfembp` gitlink mountpoint) is
  a controlled `rehearse`-time refusal rather than a silent omission --
  see `docs/release_process.md`'s "The documented non-git/extracted
  candidate path" and `scripts/release_rehearsal/tests/test_cli.py`'s
  `ExtractedNonGitTreeEndToEndTests`/`MalformedExtractedTreeTests`/
  `Issue9LiteralReproductionCommandsTests`.
* Release-doc relative-link validator
  (`scripts/release_rehearsal/doc_links.py`) -- the three broken
  `docs/release/...` links the independent verifier found (they should
  have pointed at `docs/release_data/...`) are fixed and mechanically
  regression-guarded.
* Hardened, dynamic-JSON workflow guard
  (`scripts/release_rehearsal/workflow_guard.py`): **any** permission
  scope (`contents`, `id-token`, `packages`, `pull-requests`, `issues`,
  `actions`, `checks`, `deployments`, `statuses`, or any scope this
  module's authors have never heard of) granted `write`, at top level,
  job level, deeply nested, or inside an inline/flow mapping (any
  quoting/whitespace/indentation/case), shorthand `permissions:
  write-all`, `github.token`/`secrets.*`/`GITHUB_TOKEN` interpolation,
  network tools (`curl`/`wget`), a generalized upload/release/publish/
  deploy `uses:` action-name heuristic, ref mutation (`git tag`/`git
  push`), and common shell-indirection evasions (line continuations,
  `eval`, `base64 -d`, `sh -c`/`bash -c`). A fresh, independent review
  found the previous check only ever matched the literal scope name
  `contents`; every other scope (and any future, unknown one) is now
  rejected identically, and the real, legitimate
  `.github/workflows/release-rehearsal.yml` still passes with zero
  findings.
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

# The machine-distinct publication-eligibility gate. The underlying CLI
# itself is EXPECTED to exit non-zero (1, EXIT_NOT_ELIGIBLE) while the
# candidate is blocked -- this is not a failure of this change, it is the
# gate doing its job. Run *through* `make` as below, GNU Make reports any
# failed recipe as exit 2 (never the recipe's own code -- this is
# standard, unconfigurable `make` behavior, not specific to this
# repository), so the command below currently and correctly prints
# "exit=2", not "exit=1"; invoke
# `python3 -m scripts.release_rehearsal.cli check --require-eligible`
# directly (never through `make`) to observe the CLI's own literal `1`.
make release-check-require-eligible; echo "exit=$?"

# The expected-status health check: exits 0 only while truly blocked.
make release-check-expect-blocked

# Deterministic archive + rebuild rehearsal (always exits 0 for a
# well-formed report; "rebuild".status is truthfully "blocked" today).
make release-rehearse

# The documented non-git/extracted candidate path, reproduced directly
# against a real extraction of this repository's own current HEAD (never
# a hand-authored fake) -- requires the exact 40-lowercase-hex
# --target-sha override; genuinely works end-to-end (no traceback, a
# truthful "blocked" JSON report, exit 0):
HEAD_SHA="$(git rev-parse HEAD)"
EXTRACTED="$(mktemp -d)"
git archive "$HEAD_SHA" | tar -x -C "$EXTRACTED"
python3 -m scripts.release_rehearsal.cli check --repo-root "$EXTRACTED" --target-sha "$HEAD_SHA"
python3 -m scripts.release_rehearsal.cli rehearse --repo-root "$EXTRACTED" --target-sha "$HEAD_SHA"
rm -rf "$EXTRACTED"

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

## Mandatory-correction round (policy guardian, post-verifier)

A subsequent policy-guardian review required additional corrections
beyond the independent-verifier round documented above, all implemented
in the `agent/issue9-release-process` branch on top of it -- **the
candidate remains mechanically BLOCKED; this section is evidence, not a
closure claim**:

1. **Immutable Actions pins** -- every external `uses:` reference in
   `.github/workflows/release-rehearsal.yml` is now pinned to an exact,
   independently-verified 40-lowercase-hex commit SHA (no mutable tag,
   not even a major-version tag); `docs/release_data/action_pins.json` +
   `scripts/release_rehearsal/action_pins.py` record and cross-check the
   upstream source/version/verification/update procedure.
2. **Exact immutable HEAD tree coverage** -- `scripts/release_rehearsal/
   tree_coverage.py` + `docs/release_data/export_exclusions.json` prove
   the included allowlist and the explicit export exclusions (the
   `mgfembp` gitlink, with its exact mode/OID and a factual reason) are
   an exact, disjoint partition of the complete tree; wired into the
   archive build itself (refuses to build on any mismatch) and into a
   non-git closed-world missing/extra/unsafe check.
3. **Per-blob provenance identity** -- every included `"code"`/`"asset"`
   provenance record now also carries the exact Git blob `oid` and a
   deterministic SHA-256 `sha256`, cross-checked against the live
   tree/blob content (`check_blob_identity`); a changed/new blob
   invalidates its old record instead of silently passing on path match.
4. **mgfembp three-way binding** -- `scripts/release_rehearsal/
   submodule_binding.py` (+ the new minimal `.gitmodules` parser,
   `gitmodules.py`) cross-checks `.gitmodules`, the HEAD tree gitlink,
   the export-exclusion record, and the provenance record all agree
   exactly (path, URL, pinned OID); rejects a non-`https://` submodule
   URL scheme and any allowlist/exclusion contradiction. Never
   fetches/initializes the submodule.
5. **External attestation outside candidate control** --
   `manifest.py check_external_attestation()` is a zero-argument
   function that always reports substatus `"missing"`, folded into the
   overall status unconditionally -- proven (even with *every other*
   sub-check mocked to a fully-passing synthetic shape) that the overall
   candidate still cannot become `"mechanically eligible"` from inside
   this repository. Only a future, separate, out-of-repo human/harness
   gate may combine a real external attestation with this candidate's
   evidence.
6. **Guard remains advisory** -- documented explicitly (`docs/
   release_process.md`'s "Workflow guard is advisory, never
   authorization" and "External attestation is outside candidate
   control" sections) that a clean workflow-guard/action-pins/tree-
   coverage/submodule-binding result is necessary, never sufficient, for
   authorization or publication.
7. **Independent immutable rebuild materialization** --
   `run_build_twice_from_immutable_source()` replaces the copy-of-the-
   live-worktree double-build as what actually produces
   `"verified_success"`: each run materializes its own source tree
   independently via `git archive <target_sha>` (never the live
   worktree), verifies its own input files are unchanged after the
   build, and the two runs can never share a directory. A real
   regression this same round introduced (a missing `is_git_repo` guard
   in the new `.gitmodules`/submodule-binding code, which could have let
   git's own upward-directory-discovery adopt an unrelated enclosing
   repository for a non-git candidate tree) was caught by re-running
   this worktree's own existing regression-test pattern and fixed in the
   same branch.

Every item above is additionally covered by dedicated, adversarial
stdlib-unittest coverage (`scripts/release_rehearsal/tests/
test_action_pins.py`, `test_tree_coverage.py`, `test_gitmodules.py`,
`test_submodule_binding.py`, plus extensions to `test_provenance.py`,
`test_manifest.py`, `test_archive_rehearsal.py`, and
`test_workflow_guard.py`), and the full `scripts/release_rehearsal` +
`scripts/modernize/migrations` stdlib test suites were reverified green
after every commit in this round. `make release-check`'s live status
remains, correctly and exactly, `"blocked"`.
## Guardian-correction remediation round (fresh independent review, D1-D5)

An independent review of `2b376912..130713de` found three blocking
defects (D1-D3) plus several adjacent high-confidence exactness gaps,
all remediated in the `agent/issue9-release-process` branch on top of
the mandatory-correction round above -- **the candidate remains
mechanically BLOCKED; this section is evidence, not a closure claim**:

1. **D1 -- real end-to-end verified-success test, legacy fake path
   removed.** The evidence/docs previously claimed a test named
   `test_hermetic_eligible_rebuild_runs_twice_and_verifies_success`
   drove `rebuild_rehearsal_blocker()` end-to-end to `verified_success`;
   it actually only ever called the legacy, copy-based
   `run_build_twice()` helper (never wired into the release status at
   all) and asserted nothing about the manifest-facing status.
   `run_build_twice()` is now deleted outright.
   `RebuildRehearsalBlockerEndToEndBuildTests` (`test_archive_
   rehearsal.py`) is the real replacement: it drives
   `rebuild_rehearsal_blocker()` itself, through a synthetic
   approved+pinned+initialized submodule fixture, to
   `REBUILD_STATUS_VERIFIED_SUCCESS` -- executing a real hermetic build
   command twice from two independently materialized immutable inputs
   and directly asserting the status, the two runs' distinct
   materialization roots, unchanged/unmutated inputs, and matching
   declared outputs (a real, hand-computed hash built from both the
   superproject's own tracked content and the pinned-commit-bound
   submodule content). The same class adds blocker-level tests for a
   mismatch, a build failure, a missing declared output, a shared-
   directory refusal, and a source (input-tree) mutation --
   `RebuildRehearsalBlockerTests`'s pre-existing "not_run"/"eligible"
   tests were also corrected to actually call `rebuild_rehearsal_
   blocker()` with matching `submodule_path`/`provenance_dir` (they
   previously fell back to this repository's own unrelated `mgfembp`
   defaults, so they never really exercised the wrapper's eligible path
   at all). `docs/release_process.md`'s "Rebuild rehearsal" section and
   this document's own "What is implemented" bullet are corrected to
   name the actual wired function/test and only the claims it proves.

2. **D2 -- provenance blob-identity exemption narrowed to the one
   genuinely self-referential file, structurally.** `check_blob_
   identity()` previously exempted all three provenance-manifest files
   (`code.json`, `assets.json`, `submodules.json`) from live-content
   cross-checking, even though only `code.json`'s own self-record (a
   record about `code.json`'s content, stored *inside* `code.json`) is
   a genuine "hash quine" -- `assets.json`/`submodules.json`'s own
   records live inside `code.json`, a *different* file, so cross-
   checking them has no cycle at all, and exempting them let committed
   tampering of either file silently evade identity validation. Fixed
   structurally, not by merely narrowing the exemption list: `docs/
   release_data/provenance/code.json` is now an exact, explicit,
   minimal export exclusion (`tree_coverage.
   KIND_SELF_REFERENTIAL_EVIDENCE`, `SELF_REFERENTIAL_EVIDENCE_PATHS`)
   -- it is no longer an *included* allowlist member at all, so it
   never requires (and, after regeneration, no longer has) its own
   provenance record; its own export-exclusion entry (kind, mode, OID,
   and a documented reason) is its complete, sufficient, externally-
   owned evidence. `check_blob_identity()`'s old `SELF_REFERENTIAL_
   PROVENANCE_PATHS` exemption is deleted entirely -- there is nothing
   left to exempt. `tree_coverage.py`'s exact-coverage machinery
   (`check_partition`/`check_non_git_tree`/`check_archive_membership_
   exact`) is generalized to a second exclusion kind so included ∪
   excluded remains the complete, disjoint immutable HEAD tree;
   `allowlist.py`/`provenance.py` exclude `code.json`'s path from their
   own generated/required sets the same way a gitlink already was.
   Committed tamper probes cover `assets.json`, `submodules.json`, a
   changed same-path blob, and the excluded self-referential-evidence
   path itself (a stray leftover self-record is now reported as a
   provenance "ghost" entry, never silently accepted). `make
   release-check`'s live status remains BLOCKED (provenance is,
   correctly, still unresolved) throughout.

3. **D3 -- immutable submodule bytes, never a dirty worktree copy.**
   `evaluate_rebuild_eligibility()` now additionally requires (4) a
   genuinely clean submodule worktree/index (`git status --porcelain`
   run *inside* the submodule itself is empty -- modified, staged, and
   untracked content are all rejected), (5) the submodule's own
   configured `remote.origin.url` to agree with `.gitmodules`'s
   declared URL, and (6) the provenance-pinned commit to be a real,
   locally-accessible object inside the submodule's own object database
   -- on top of the pre-existing (1)-(3) initialized/pinned-identity/
   approved checks. Independently (defense-in-depth), the extra-
   materialize callback `rebuild_rehearsal_blocker()` passes into the
   double-build (`_materialize_verified_submodule_content()`, replacing
   `_copy_verified_submodule_content()`) no longer `shutil.copytree`s
   the submodule's live worktree directory at all -- it materializes the
   submodule's content via `git archive <pinned_commit>` run *inside*
   the submodule's own repository, exactly mirroring how the
   superproject's own content is materialized, so even a hypothetical
   future eligibility bug could not let dirty/tampered submodule bytes
   flow into a build. `SubmoduleDirtyWorktreeReproducerTests` reproduces
   the reviewer's literal dirty/staged/untracked scenarios (all
   correctly ineligible) and directly proves the materializer itself
   extracts the pinned commit's own content, never the dirty worktree
   bytes, even when called directly against a dirty submodule.

4. **D4 -- included Git modes bound and validated.**
   `docs/release_data/source_allowlist.json` (schema_version 4) now
   additionally records a `"modes"` map (exact path -> Git mode) for
   every included path; `allowlist.py check()` cross-checks this
   bijection and, for a real git repository, each declared mode against
   the live tree (`check_mode_identity`) -- a committed executable-bit
   (or other mode) change now makes this canonical data stale/fail
   until regenerated. The archive itself continues to canonicalize
   every written tar member's mode to a fixed `0o644` regardless of the
   source Git mode (a deliberate, now-documented and now-tested
   determinism policy, not an accidental omission -- see "Archive
   member mode policy" in `docs/release_process.md`); mode-binding is a
   drift-detection/provenance-identity concern here, not an archive-
   fidelity promise. Tests cover a `100644<->100755` change, an
   unsupported mode value, and the archive's own fixed output mode. The
   allowlist file's own mode is recorded like any other path -- no new
   self-reference cycle is introduced (a mode is a small, independently
   verifiable fact, unlike a live-content hash of the file that would
   have to embed it).

5. **D5 -- closed-world symlinks, and evidence honesty.**
   `tree_coverage.py`'s and `allowlist.py`'s non-git closed-world
   enumeration (`_present_paths`, replacing `_present_regular_files`) no
   longer `continue`s straight past a symlink it finds -- a stray,
   unlisted symlink (or any other non-regular node) at any path is now
   reported as an unaccounted-for "extra"/"missing from allowlist"
   finding instead of being silently invisible; only a genuine,
   non-symlink directory is still ever walked through rather than
   reported. `build_deterministic_archive`'s own wired archive-member-
   exact refusal (not merely `tree_coverage.check_archive_membership_
   exact` tested in isolation) now has a dedicated regression test
   forcing an "extra members" report through the real call site.
   `docs/release_process.md`'s "External attestation is outside
   candidate control" section is tightened to explicitly note that
   Git-blob immutability binds *which bytes* a given commit contains,
   never protects against what a candidate author chooses to commit in
   the first place, and that no candidate-controlled config/data/flag/
   env input of any kind (including a JSON provenance/allowlist/
   exclusions record a PR author can freely edit) can ever satisfy the
   external attestation requirement; external protected human review
   remains the sole owner of that decision. `provenance.py`'s generator
   docs are corrected: a changed or brand-new blob resets any
   previously-recorded approval/reviewer/legal fact (there is nothing
   this generator ever "preserves" -- every field it controls is always
   freshly recomputed on every run), and a submodule's `pinned_commit`/
   `url` are always re-read from the immutable target tree/
   `.gitmodules`, never carried over from an existing on-disk record.

### Verification (this round)

* Full `scripts/release_rehearsal` + `scripts/modernize/migrations`
  stdlib test suites re-verified green after this round's changes (see
  the evidence commands above; the pass count itself is deliberately
  not hardcoded here, for the same "do not trust a fixed number" reason
  the rest of this document already explains).
* `make release-check`'s live status remains, correctly and exactly,
  `"blocked"`: external attestation is still, and can only ever be,
  `"missing"`; the `mgfembp` submodule remains uninitialized/
  unapproved/excluded; every provenance record remains honestly
  unresolved.
* `python3 scripts/artifact_guard.py --revision HEAD` -- unaffected;
  this round never touches `scripts/artifact_guard.py`.
* No tag/release/asset/comment/environment/protected ref was created,
  moved, or deleted; no `contents: write` permission was added anywhere;
  the `mgfembp` submodule was never fetched/initialized; no license was
  selected; no author/rightsholder/license/reviewer/approval was
  invented.

Issue #9 remains **not closed** by this report, this round, or any
command either describes.

## R1-R5 remediation round (independent re-review at `28972b24`)

A further independent re-review of `28972b24` (the exact tip of the
guardian-correction remediation round above) reproduced five additional
defects (R1-R5), all remediated in the `agent/issue9-release-process`
branch on top of every round above -- **the candidate remains
mechanically BLOCKED; this section is evidence, not a closure claim**:

1. **R1 -- self-referential-evidence exclusion is now a validator
   invariant, never a generator convention.** Previously, *any* tracked
   path could be claimed under `tree_coverage.
   KIND_SELF_REFERENTIAL_EVIDENCE` with a fabricated `oid`, and tree
   coverage stayed clean -- silently moving an arbitrary blob out of the
   archive+provenance-required set with no actual review, even though
   D2 (above) had already narrowed this kind's *legitimate* use to
   exactly one curated path. `tree_coverage.py` now checks this kind's
   `path` against a small, hard-coded, human-curated policy set
   (`SELF_REFERENTIAL_EVIDENCE_PATHS`, today exactly
   `{"docs/release_data/provenance/code.json"}`) in *both*
   `load_exclusions()` (the JSON-file-loading gate) and independently
   again inside `check_partition()` itself, so even a directly-
   constructed exclusion entry that never went through
   `load_exclusions()` at all is still caught -- no prefix, no
   wildcard, no second/extra row of this kind for any other path. A
   claim against any other path, or an uncurated extra row, now fails
   the partition outright (a new, dedicated
   `invalid_self_referential_evidence` bucket on `PartitionResult`, kept
   separate from the pre-existing `missing_included`/`missing_excluded`/
   `mismatched_excluded` buckets so each failure mode is independently
   reported and independently tested). Dropping the one legitimate
   curated exclusion without replacing it is unaffected and still
   separately, correctly caught by the pre-existing `missing_included`
   accounting once the real path resurfaces as neither included nor
   excluded -- so neither dropping the curated row nor adding an
   uncurated one can ever pass.
2. **R2 -- no false OID semantics for self-referential evidence.**
   This kind's exclusion record previously carried an `oid` that was, in
   truth, never cross-checked against anything at all (silently
   "documentary/best-effort" only, while nearby prose read as if it were
   an immutable, verified fact), and the real, checked-in document's own
   recorded value had already drifted stale relative to the live blob
   well before this fix, precisely because nothing ever caught that
   drift. There is no such thing as a truthful, immutable `oid` for this
   kind in the first place: a file cannot record an exact hash of its
   own not-yet-finalized content without exactly the "hash quine" cycle
   D2 (above) already describes and rejects. The schema now requires
   this kind's `oid` to be absent or JSON `null`; `load_exclusions()`
   hard-rejects any supplied/stale/fake value (a real 40-hex OID, an
   empty string, anything but `null`/absent), and
   `generate_exclusions_document()` always writes `null` for it, never a
   live tree OID -- `docs/release_data/export_exclusions.json` is
   regenerated accordingly. Nothing about this kind's OID is ever
   claimed, recorded, or cross-checked as a content-identity fact; a
   content change to the curated path is instead caught purely by the
   ordinary tree-membership contract, which remains fully live (it is
   still a live, correctly-kinded, correctly-moded blob either way).
   `docs/release_process.md` and this document now say explicitly:
   `code.json` is a curated path-only-plus-mode exclusion and
   **external rehearsal evidence about this repository's own tooling --
   never source archive content, and never itself a redistribution/
   legal authorization of any kind.** Every *included* blob (every
   ordinary allowlist member, `assets.json`, and `submodules.json`
   alike) remains exactly OID/SHA256-bound with no exemption at all; a
   `"gitlink"` exclusion (`mgfembp`) is unaffected and still requires
   and strictly cross-checks its own exact, immutable OID exactly as
   before -- only the one, single, curated, self-referential path's OID
   semantics changed. `test_tree_coverage.py`'s
   `ArbitraryPathSelfReferentialEvidenceExclusionRejectionTests` covers, at
   both the `load_exclusions` JSON-schema-gate layer and the
   `check_partition` validator-invariant layer: injecting an arbitrary
   second blob under this kind -- using two different real tracked paths as
   the example across the two layers (`src/main.c` and the repository's own
   top-level `Makefile`) to show the rejection is path-agnostic, not a
   special case keyed to one hard-coded name -- a bogus/stale/non-null `oid`
   on the legitimate curated entry, an extra uncurated row alongside the
   legitimate one, a missing curated exclusion (the path silently
   resurfacing as neither included nor excluded), and an actual content
   change to `code.json`'s own live blob that a stale `oid` could otherwise
   have masked.
3. **R3 -- submodule future rebuild-eligibility fails closed on origin
   URL and command failure, not just on the checks it already
   performed.** `evaluate_rebuild_eligibility()`'s prior URL check only
   ever compared `remote.origin.url` against `.gitmodules`'s declared
   URL *when both sides already happened to be known* -- a genuinely
   missing origin (the ordinary state of an uninitialized-then-partly-
   configured submodule) left the check vacuously unexercised rather
   than failing. Eligibility now requires a live, non-empty configured
   origin that agrees *exactly* with **both** independent immutable
   declared sources this repository records for it -- `.gitmodules`'s
   own declared `url`, and the separate `docs/release_data/provenance/
   submodules.json` record's own `url` field -- defaulting to
   non-eligible and only becoming eligible once all three agree; a
   missing declaration in *either* immutable source, or a mismatch
   against *either* of them, is its own actionable, non-eligible
   finding. `git cat-file -e <sha>^{commit}` already correctly enforced
   both existence and type for the pinned commit object before this
   round (a blob/tree SHA, or any other unresolvable value, was already
   rejected) -- this round adds explicit regression coverage for that
   existing behavior rather than changing it. Every underlying `git
   status`/`git config`/`git cat-file` command is now itself required
   to actually *succeed*: a genuine tooling failure (as opposed to the
   command's own ordinary not-clean/no-origin-set/object-absent
   outcome) is caught and reported as its own actionable, non-eligible
   finding, never silently swallowed into a false pass -- `git config
   --get remote.origin.url`'s exit code `1` ("key not found", the
   ordinary no-origin-configured case) is distinguished from any other
   nonzero exit (a genuine config/tooling error). New tests cover: a
   clean positive control, a missing origin, a URL mismatch against
   `.gitmodules`, a URL mismatch against provenance, a missing
   `.gitmodules` URL, a missing provenance URL, a wrong-type pinned
   object, a nonexistent pinned object SHA, a `git status` command
   failure, and a `git config` command failure.
4. **R4 -- source comment now names a real test class.** A comment in
   `archive_rehearsal.py` referenced
   `RebuildRehearsalBlockerEndToEndVerifiedSuccessTests`, a test class
   that has never existed under that name; the real, existing class
   exercising that exact end-to-end path is
   `RebuildRehearsalBlockerEndToEndBuildTests` (see D1 above). The
   comment is corrected to name it. A new mechanical check,
   `SourceCommentTestClassReferenceTests`
   (`test_archive_rehearsal.py`), scans every
   `scripts/release_rehearsal/*.py` source file for any backtick-quoted
   `` `SomeNameTests` `` reference and cross-checks each one against the
   real `class SomeNameTests(...)` definitions actually present under
   `scripts/release_rehearsal/tests/`, failing on any reference that
   does not resolve -- verified, by a temporary negative control, to
   actually fail when a referenced class is renamed away, then restored.
5. **R5 -- mode-binding schema cannot be silently switched off.** D4
   (above) added the allowlist's `"modes"` map and its cross-checks, but
   `load_allowlist_modes()` treated `"modes"` as effectively optional at
   load time (returning `None` with no error at all when the key was
   simply absent) and nothing anywhere checked `schema_version` itself
   -- so deleting the `"modes"` key, or rolling `schema_version` back to
   an older value, silently disabled every one of D4's mode checks with
   no actionable failure, while every other allowlist check kept
   passing. `load_allowlist_modes()` now hard-requires `schema_version`
   to be *exactly* the current, single supported value (`4`); a
   missing, downgraded, upgraded-but-unknown, or wrong-type
   `schema_version` is an actionable `AllowlistError`, raised *before*
   any mode checking is even attempted. Once `schema_version` passes,
   `"modes"` itself becomes unconditionally mandatory (a missing key is
   now the same class of hard error, never a silent `None`), and its
   bijection/identity checks always run. New tests cover: deleting
   `"modes"` entirely, an unsupported/downgraded/missing/wrong-type
   `schema_version`, adding an extra mode entry with no corresponding
   path, and dropping a mode entry for an existing path. The committed
   `chmod` of an allowlisted file coverage
   (`test_committed_executable_bit_change_makes_mode_data_stale`) is
   **not** new to this round -- a further independent re-review found
   this section previously mislabeled it as one of the "new tests"; it
   was already added in the guardian-correction remediation round's D4
   fix (`a2f9d442`), and is only re-verified, unchanged in substance,
   end-to-end here (its fixture was adjusted to also declare
   `schema_version`/`"modes"`, per this round's own new requirement) to
   confirm the schema fix did not regress the pre-existing check it
   protects.

Every item above is additionally covered by dedicated, adversarial
stdlib-unittest coverage (extensions to `test_tree_coverage.py`,
`test_archive_rehearsal.py`, and `test_allowlist.py`), and the full
`scripts/release_rehearsal` stdlib test suite was reverified green after
this round's changes. `make release-check`'s live status remains,
correctly and exactly, `"blocked"` throughout -- this round changes no
workflow, legal, or `artifact_guard.py` file, adds no approval/fetch/
publication/ref/merge action of any kind, and closes no issue.

### Verification (this round)

* Full `scripts/release_rehearsal` stdlib test suite re-verified green
  after this round's changes (see the evidence commands above; the pass
  count itself is deliberately not hardcoded here, for the same "do not
  trust a fixed number" reason the rest of this document already
  explains).
* `make release-check`'s live status remains, correctly and exactly,
  `"blocked"`: external attestation is still, and can only ever be,
  `"missing"`; the `mgfembp` submodule remains uninitialized/
  unapproved/excluded; every provenance record remains honestly
  unresolved.
* `python3 scripts/artifact_guard.py --revision HEAD` -- unaffected;
  this round never touches `scripts/artifact_guard.py`.
* No tag/release/asset/comment/environment/protected ref was created,
  moved, or deleted; no `contents: write` permission was added anywhere;
  the `mgfembp` submodule was never fetched/initialized; no license was
  selected; no author/rightsholder/license/reviewer/approval was
  invented.

Issue #9 remains **not closed** by this report, this round, or any
command either describes.


## Closing round (independent review at `4ea66356`)

A further independent re-review of `4ea66356` (the exact tip of the
R1-R5 remediation round above) found four additional, precise defects,
all remediated in the `agent/issue9-release-process` branch on top of
every round above -- **the candidate remains mechanically BLOCKED; this
section is evidence, not a closure claim**:

1. **Truthful, kind-specific generated export-exclusions comment.**
   `tree_coverage.generate_exclusions_document()`'s generated
   `docs/release_data/export_exclusions.json` `"_comment"` field
   previously claimed every entry has "immutable mode/OID (as recorded
   by 'git ls-tree')" -- true for a `"gitlink"` entry, but false for a
   `"self_referential_evidence"` entry, whose `oid` has always been (R2)
   exactly JSON `null` and is never itself cross-checked as a
   content-identity fact. The generated comment is now kind-specific and
   explicit about each kind's genuinely distinct semantics: `"gitlink"`
   carries a mandatory, strictly cross-checked 40-lowercase-hex `oid`;
   `"self_referential_evidence"` carries exact path/mode/reason only,
   with `oid` always `null` and never claimed or cross-checked.
2. **Manifest comment no longer claims a stale OID for self-evidence.**
   `manifest.py`'s `check_provenance()` had a source comment describing
   the self-referential-evidence exclusion record as carrying
   "kind/mode/oid/reason" as its "complete, sufficient" evidence -- true
   before R2, stale after it (this kind's `oid` was already fixed to
   always be `null`, never a claimed fact). The comment now says
   "kind/mode/reason" and explicitly notes `oid` is always `null` here.
3. **R5's closure-report wording no longer mislabels a pre-existing
   test as new.** The R1-R5 remediation round's own R5 write-up (above)
   listed a real, committed `chmod` of an allowlisted file among "New
   tests cover" -- but
   `test_committed_executable_bit_change_makes_mode_data_stale` was
   already added in the guardian-correction remediation round's D4 fix
   (`a2f9d442`), well before R5; R5 only re-verified it end-to-end
   (adjusting its fixture to also declare `schema_version`/`"modes"`)
   to confirm the schema fix did not regress it. The R5 write-up now
   says so explicitly instead of implying it was newly authored.
4. **Allowlist's non-gitlink exclusion reader no longer more permissive
   than tree_coverage's own validator.**
   `allowlist._load_non_gitlink_exclusion_paths()` used to be its own,
   separate, minimal JSON reader that treated *any* exclusion entry
   whose `kind` merely was not the literal string `"gitlink"` as a valid
   non-gitlink exclusion -- no curated-path check against
   `tree_coverage.SELF_REFERENTIAL_EVIDENCE_PATHS`, no `oid`-shape check
   at all. That meant `allowlist.check()`'s own sub-report (exercised by
   `manifest.check_allowlist_exact()` / `make release-check`) could stay
   perfectly clean for an arbitrary, uncurated self-evidence exclusion,
   or one carrying a fabricated/stale `oid`, even though
   `tree_coverage.check_partition()` -- reading the *exact same file* --
   already, correctly rejected it (R1/R2's own validator invariants).
   This reader now delegates entirely to
   `tree_coverage.load_exclusion_paths()`, restricted to
   `tree_coverage.KIND_SELF_REFERENTIAL_EVIDENCE` (the only
   non-`"gitlink"` kind `tree_coverage.VALID_EXCLUSION_KINDS` permits at
   all, so this restriction is exactly equivalent in scope to the old
   "kind != gitlink" filter) -- so both consumers now share one,
   single, strictly-validated implementation instead of two
   independently-maintained readers that could (and did) silently drift
   apart in permissiveness. Literal reviewer-reproducer tests
   (`NonGitlinkExclusionReaderDelegatesToTreeCoverageTests` in
   `test_allowlist.py`) cover: an arbitrary, non-curated path with a
   fabricated `oid` (both at the reader layer and wired fully
   end-to-end through `al.check()`), the curated path itself with a
   fabricated `oid`, and confirm the pre-existing "exclusions file
   genuinely absent" behavior is unchanged.

Additionally, per this round's own request, the generated allowlist and
export-exclusions documents' `"generated_from_sha"` field -- which was
never actually read, compared, or cross-checked by any check in this
repository (every check has always independently re-derived its own
live `target_sha`) -- is renamed to `"generation_basis_sha"`, and both
generators' own `"_comment"` text now says explicitly that this field is
a documentary record only, never a validated commit binding.

Every item above is additionally covered by dedicated, adversarial
stdlib-unittest coverage (extensions to `test_tree_coverage.py` and
`test_allowlist.py`), and the full `scripts/release_rehearsal` stdlib
test suite was reverified green after this round's changes. `make
release-check`'s live status remains, correctly and exactly, `"blocked"`
throughout -- this round changes no workflow, legal, or
`artifact_guard.py` file, adds no approval/fetch/publication/ref/merge
action of any kind, and closes no issue.

### Verification (closing round)

* Full `scripts/release_rehearsal` stdlib test suite re-verified green
  after this round's changes.
* `make release-check`'s live status remains, correctly and exactly,
  `"blocked"`.
* `python3 scripts/artifact_guard.py --revision HEAD` -- unaffected;
  this round never touches `scripts/artifact_guard.py`.
* No tag/release/asset/comment/environment/protected ref was created,
  moved, or deleted; no `contents: write` permission was added anywhere;
  the `mgfembp` submodule was never fetched/initialized; no license was
  selected; no author/rightsholder/license/reviewer/approval was
  invented.

## Integration-evidence disclosure round (independent integration review)

A further independent **integration** review (distinct from the code-level
reviews above) recommended `candidate_pass` but found four factual
disclosure gaps in this report and its underlying data that had to be
corrected first. None of them changes any check's pass/fail behavior;
all four are corrections to what this report says about the branch's own
history, hash semantics, mode semantics, and one provenance note's
accuracy -- **the candidate remains mechanically BLOCKED; this section is
evidence, not a closure claim.**

1. **History is never rewritten -- several intermediate commits on this
   integration branch are not individually green, and that is expected,
   not concealed.** `agent/issue9-release-process` merges
   `origin/master` (issue #6 and issue #18's completed work) via commit
   `44ff6558`. A merge commit mechanically combines two trees before any
   semantic reconciliation between them has happened; checking out and
   running `python3 -m scripts.release_rehearsal.provenance check` (and,
   equivalently, the full `scripts/release_rehearsal` stdlib test suite)
   in isolation, at each commit in turn, reproduces a genuinely non-green
   state at every one of the following four commits (each checked out
   via a separate, detached `git worktree add --detach <dir> <sha>` --
   never amended, rebased, cherry-picked, or otherwise rewritten; each
   remains exactly as it was originally committed):
   * `44ff6558` (the merge itself): the full suite reports
     `FAILED (failures=4)` -- two `MigrationEpochReachabilityTests`/
     `test_manifest_includes_migration_reachability_report` failures
     (origin/master's own save-format epoch advanced past what this
     branch's migration registry knew about before the merge), plus a
     `check_blob_identity` self-reference staleness (below) on exactly
     one file, `docs/release_data/provenance/assets.json` (its content
     changed -- issue #18's newly-authored `texts/expansion` entries
     were merged in -- but `code.json`'s own record of its oid was not
     yet regenerated to match).
   * `40940817` ("register the epoch 1->2 migration the merge exposed"):
     the migration-reachability failures above are fixed; the
     `check_blob_identity` staleness set *grows* to four files
     (`docs/release_data/provenance/assets.json`,
     `docs/migration_registry.md`,
     `scripts/modernize/migrations/registry.py`,
     `scripts/modernize/migrations/tests/test_registry.py` -- this
     commit's own new/changed migration-registry files, again not yet
     re-synced into `code.json`).
   * `f57f2b6e` ("correct stale `EXPANSION_SAVE_COMPAT_EPOCH` claims"):
     the staleness set grows to five files (adds
     `docs/starter_features.md`, the file this commit itself edits).
   * `accb56ea` ("add changelog fragments for #6/#10/#18's public-API
     surfaces"): the staleness set grows to six files (adds
     `CHANGELOG.md`, changed by this commit's own new fragments).

   Every one of these four commits is individually non-green for the
   *same* reason, compounding: each edits a file already tracked with
   an exact provenance record, but -- unlike the disciplined
   `exclusions -> allowlist -> provenance` regeneration order this
   repository documents elsewhere -- does not, in the same commit,
   also re-run `provenance.py generate --write` to resync `code.json`'s
   own record of that file's new oid. Commit `f0e7a7fa` ("resync
   provenance's self-referential oid records") is exactly that
   regeneration, in one pass, for all six accumulated files; its own
   commit message (written before this disclosure round) named three of
   the four affected commits (`44ff6558`/`f57f2b6e`/`accb56ea`) by its
   author's own account of which commits it was aware of at the time --
   this round's fresh, independent re-verification additionally found
   `40940817` carries the same defect (it was never called out by name
   before now), so the complete, exact set disclosed here is four
   commits, not three. `python3 -m scripts.release_rehearsal.provenance
   check` reports zero `check_blob_identity` findings at `f0e7a7fa`, and
   the full `scripts/release_rehearsal` stdlib test suite (860 tests)
   passes cleanly there (see "Verification" below); it does **not**
   continue to pass "after every change in this disclosure round" the
   way an earlier draft of this report claimed -- some of that suite's
   own tests (`test_tree_coverage.py`/`test_provenance.py`'s
   `RepositoryStateTests`) run `tree_coverage check`/`allowlist
   check`/`check_blob_identity` directly against this repository's own
   live tree, not only disposable fixtures, so the suite's own result is
   exactly as red as the live checks whenever the live tree drifts. This
   disclosure round's own commit, `18f63d4c` ("close integration-
   evidence disclosure gaps"), repeated the identical undisciplined-
   regeneration defect against itself: it edited five already-tracked
   files without, in that same commit, also re-running the `exclusions
   -> allowlist -> provenance` regeneration sequence against its own new
   tree, leaving `code.json` stale for four of those five files
   (`CHANGELOG.md`, `docs/release_closure_candidate.md`, `docs/
   release_data/provenance/assets.json`, `scripts/release_rehearsal/
   provenance.py`) and leaving its own new changelog fragment
   (`changelog_fragments/0009-release-rehearsal-integration-disclosure-
   corrections.json`) entirely absent from both
   `docs/release_data/source_allowlist.json` and every provenance
   manifest -- seven live, structural findings in total (2 from
   `tree_coverage check`, 1 from `allowlist check`, 4
   `check_blob_identity` findings from `provenance check`), which
   `RepositoryStateTests` surfaces as seven live test failures at
   `18f63d4c` (`Ran 860 tests ... FAILED (failures=7)`), reproduced
   directly against that commit (see "Verification" below). This
   report's own live, immutable tip is the final resync that closes that
   transient drift, run the same disciplined way `f0e7a7fa` closed the
   four earlier ones: correct this disclosure's own wording first, stage
   every text/data change, regenerate exclusions/allowlist/provenance
   against the staged index, and verify zero structural findings (and a
   clean, all-860-passing suite run) before committing.

   **This repository's branch/tag/support policy has never required,
   and this round does not newly require, every ancestor commit on a
   long-lived integration branch to be individually green** -- only the
   branch's current tip is ever the unit this report, `make
   release-check`, or the CI workflow evaluates. Nothing in `git log` is
   amended, rebased, squashed, or force-pushed by this disclosure; the
   four commits above remain exactly as committed, named here only as
   truthful, reproducible evidence a reviewer can verify with `git
   worktree add --detach <dir> <sha>` and `python3 -m
   scripts.release_rehearsal.provenance check`, run from each detached
   checkout in turn.

2. **The immutable Git-blob archive and a genuine git-archive-extracted
   non-git tree are two distinct hash domains that must never be
   compared as the same artifact.** `build_deterministic_archive()`
   reads every included byte exclusively through `git cat-file --batch`
   when `root` is a real Git working tree (see
   `scripts/release_rehearsal/git_source.py`) -- this is the *committed
   blob* content, never worktree/checkout bytes. The documented non-git/
   extracted-candidate path (see "The documented non-git/extracted
   candidate path" in `docs/release_process.md`) instead reads whatever
   bytes are physically present on disk in an already-extracted tree
   (`path.read_bytes()` in `_filesystem_allowlisted_files`'s callers) --
   for a tree produced by `git archive <sha> | tar -x` (the real,
   documented reproduction command this repository's own tests use),
   those bytes have already passed through any `.gitattributes`
   checkout-time text/EOL conversion. This repository's `.gitattributes`
   declares `*.pal text eol=crlf`: every one of the exactly 510 tracked
   `.pal` palette files is stored as an LF-only blob (verified: `git
   cat-file blob HEAD:<path> | grep -c $'\r'` is `0` for all 510) but
   materializes with CRLF line endings on any checkout or `git archive`
   extraction (verified directly against this repository's own HEAD:
   `git cat-file blob HEAD:<path>` and a fresh `git archive HEAD | tar -x`
   extraction of the same path differ byte-for-byte). Consequently:
   * the git-blob-mode archive (built from a real `.git` `root`) and the
     non-git/extracted-tree-mode archive (built from the *same* commit's
     `git archive`-extracted tree) are **two independently deterministic,
     but never mutually hash-equal, artifacts** -- each mode's own
     `rehearse_archive_twice()` double-build-and-compare (see
     `docs/release_process.md`'s "Archive/rebuild rehearsal") only ever
     proves determinism *within* its own mode, never equality *across*
     modes, and no code, test, or prior version of this report ever
     claimed otherwise;
   * this is a direct, mechanical consequence of a `.gitattributes`
     export/checkout transform declared for exactly one tracked file
     extension, not a defect in `git_source.py`, `archive_rehearsal.py`,
     or the non-git/extracted-tree contract -- both modes remain exactly
     as reliable and reproducible as documented elsewhere in this report,
     each *on its own terms*;
   * no command, doc, or check in this repository compares a git-blob-
     mode archive hash against a non-git/extracted-tree-mode archive
     hash as if they were the same artifact, and none ever should;
     publication remains blocked regardless of which mode is rehearsed.
   A reviewer can reproduce this directly:
   ```sh
   git ls-tree -r HEAD --name-only | grep -c '\.pal$'   # 510
   f=$(git ls-tree -r HEAD --name-only | grep '\.pal$' | head -1)
   git cat-file blob "HEAD:$f" | sha256sum                # blob-mode bytes
   tmp=$(mktemp -d); git archive HEAD | tar -x -C "$tmp"
   sha256sum "$tmp/$f"                                    # extracted-mode bytes -- differs
   rm -rf "$tmp"
   ```

3. **Archive member mode wording, precisely: every written tar member is
   `0o644`, never `0o755` -- `CANONICAL_DIR_MODE` is a defined-but-unused
   constant.** `archive_rehearsal.py` defines both
   `CANONICAL_FILE_MODE = 0o644` and `CANONICAL_DIR_MODE = 0o755`, but
   `build_deterministic_archive()` only ever adds `tarfile.REGTYPE`
   (regular-file) members -- it never adds a directory member of any
   kind -- and unconditionally stamps every one of those regular-file
   members' `info.mode` with `CANONICAL_FILE_MODE`. `CANONICAL_DIR_MODE`
   is therefore never read or applied anywhere in this module or its
   callers -- scoped to code only, a plain `git grep -n
   CANONICAL_DIR_MODE -- '*.py'` finds only its own definition; a
   `docs/`-inclusive text grep additionally matches this very report's
   own prose discussing the constant by name (including this sentence),
   which is expected commentary, never a second *code* reference, so
   this disclosure's own evidence is scoped to the one code definition,
   not to a mixed scripts+docs text match. Reading "modes 0644/0755" as
   describing two
   different kinds of archive output member would be wrong: the archive
   itself only ever produces `0o644` members, full stop.
   `docs/release_process.md`'s "Archive member mode policy" section
   already correctly describes the schema's own `100644`/`100755`/
   `120000` **Git**-mode bijection (a drift-detection/provenance-identity
   concern, tracked in `source_allowlist.json`, never an archive-fidelity
   promise) as distinct from the archive's own fixed `0o644` **tar**
   output mode; this disclosure additionally, explicitly records that
   `CANONICAL_DIR_MODE`'s existence must never be read as evidence that
   any archived member other than `0o644` is ever produced.

4. **`texts/expansion`'s provenance note no longer inherits an
   inaccurate original-game-asset claim.** `PROVENANCE_ROOT_SEED`
   previously seeded a single `"texts"` prefix root covering every path
   under `texts/` (both the original-game `texts/textdefs.txt` /
   `texts/texts.txt` dumps *and* issue #18's newly-authored
   `texts/expansion/registry.json` / `texts/expansion/catalog.en.json`
   localization-framework catalog/source) with one shared note asserting
   "extracted/derived original-game asset... Original Fire Emblem: The
   Sacred Stones copyright/trademark ownership is Nintendo/Intelligent
   Systems" -- true for the two original-game text dumps, **never true**
   for `texts/expansion`'s own repository-authored framework message
   keys and locale strings. `PROVENANCE_ROOT_SEED` now seeds three
   disjoint, non-overlapping roots instead of one prefix root --
   `"texts/textdefs.txt"` and `"texts/texts.txt"` (each an exact, single-
   path root, keeping the original-game-asset note exactly where it is
   accurate) and `"texts/expansion"` (a new, neutral note stating this
   path is a tracked, repository-authored localization catalog/source,
   never derived from the original game, with author/rightsholder/
   license/redistribution-approval left exactly as unresolved as every
   other tracked path -- nothing is invented). `docs/release_data/
   provenance/assets.json` is regenerated
   (`python3 -m scripts.release_rehearsal.provenance generate
   --target-sha HEAD --write`); only the two `texts/expansion/*` entries'
   `notes` field changed -- every `author`/`rightsholder`/`license`
   remains `NOASSERTION`, `redistribution_approved` remains `false`, and
   `reviewer` remains `null`, exactly as before and exactly as every
   other still-unreviewed tracked path.

### Verification (integration-evidence disclosure round)

* Full `scripts/release_rehearsal` stdlib test suite (860 tests)
  re-verified green at this report's own live tip -- item 1 above
  discloses that this claim was **not** true at this round's prior tip,
  `18f63d4c` (`Ran 860 tests ... FAILED (failures=7)`, all seven
  failures inside `RepositoryStateTests`, which probes the live tree
  directly rather than only disposable fixtures).
* `18f63d4c` re-verified as live-red, exactly as item 1 above
  describes: `python3 -m scripts.release_rehearsal.tree_coverage check
  --target-sha 18f63d4c` (2 findings), `python3 -m
  scripts.release_rehearsal.allowlist check --target-sha 18f63d4c` (1
  finding), and `check_blob_identity` inside `python3 -m
  scripts.release_rehearsal.provenance check` against a detached
  checkout of `18f63d4c` (4 findings) -- the same seven live, structural
  findings the test suite's own `RepositoryStateTests` failures surface,
  all corrected by this report's own live tip (zero remaining at `HEAD`
  after this resync; legal-provenance/`NOASSERTION` findings are
  unaffected and pre-existing).
* `44ff6558`/`40940817`/`f57f2b6e`/`accb56ea` re-verified individually
  red via `python3 -m scripts.release_rehearsal.provenance check` (in
  isolated, detached `git worktree` checkouts, never the live
  worktree), exactly as described in item 1 above -- including the
  cumulative, growing stale-file count (1/4/5/6) and the fact that
  `40940817` is disclosed here despite not being named in `f0e7a7fa`'s
  own commit message; a transient `test_no_temporary_files_retained_
  after_rehearsal` failure observed once during this review's own
  parallel multi-commit full-suite runs was reproduced as a
  parallel-execution/`/tmp` artifact, not a real regression, by
  re-running that one test alone at the same commit.
* `git cat-file`/`git archive` reproduction in item 2 above re-run
  directly against this repository's own current HEAD; the byte
  difference and the exact `.pal` count (510) are both reproducible,
  not asserted.
* `git grep -n CANONICAL_DIR_MODE -- '*.py'` -- exactly one match (its
  own definition in `archive_rehearsal.py`), confirming item 3, scoped to
  code only. (A `docs/`-inclusive text grep additionally matches this
  report's own prose discussing the constant by name; that is expected
  commentary, not further code usage, so item 3's evidence is
  deliberately scoped to the one code definition, never a mixed
  scripts+docs text match.)
* `make release-check`'s live status remains, correctly and exactly,
  `"blocked"`.
* `python3 scripts/artifact_guard.py --revision HEAD` -- unaffected;
  this round never touches `scripts/artifact_guard.py`, any workflow
  file, or any legal/migration-behavior file.
* No tag/release/asset/comment/environment/protected ref was created,
  moved, or deleted; no `contents: write` permission was added anywhere;
  the `mgfembp` submodule was never fetched/initialized; no history was
  rewritten/amended/rebased/force-pushed; no author/rightsholder/
  license/reviewer/approval was invented anywhere, including for
  `texts/expansion`.

Issue #9 remains **not closed** by this report, this round, or any
command either describes.
