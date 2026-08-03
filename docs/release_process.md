# Release process (issue #9)

This document is the single authoritative description of this
repository's **release rehearsal** system: a fail-closed, read-only,
mechanically-checked process that can only ever report a candidate as
`"mechanically eligible"` or `"blocked"` -- it never publishes anything,
and it never grants publication authority. See
[`docs/public_api_policy.md`](public_api_policy.md) for the SemVer/branch/
tag/support policy this process validates against, and
[`docs/issue-resolution-policy.md`](issue-resolution-policy.md) for why
Wave 0 deliberately deferred all of this to issue #9.

## The headline fact

**Public publication of this repository remains mechanically BLOCKED**,
today and until a human maintainer:

1. resolves the legal/provenance status recorded in
   [`docs/release_data/provenance/*.json`](release_data/provenance/) (currently every
   entry is honestly `NOASSERTION`/`redistribution_approved: false`/no
   reviewer -- see "Legal and provenance boundary" below), **and**
2. separately authorizes (in a future, distinct change) any write-capable
   publishing workflow -- **no such workflow exists in this repository**,
   and issue #9 explicitly forbids adding one
   (`.github/workflows/release-publish.yml` or any `contents: write`
   workflow/job).

Nothing in this document, or any command it describes, changes that. This
document does **not** close issue #9.

## Components

| Component | Module | Purpose |
|---|---|---|
| Changelog fragments | `scripts/release_rehearsal/changelog.py`, `changelog_fragments/*.json`, `CHANGELOG.md` | Categorized, schema-validated, deterministically-rendered change notes with declared SemVer impact. |
| Release manifest | `scripts/release_rehearsal/manifest.py` | Ties together `config.mk` SemVer, embedded C metadata, a candidate tag string, changelog, docs, save format/migrations, previous/next supported versions, the exact allowlist, version-ledger topology, C-fallback-metadata consistency, migration-epoch reachability, doc-link validity, and the rebuild rehearsal into one report. |
| Manifest consistency validators | `scripts/release_rehearsal/consistency.py` | Version-ledger topology/candidate-agreement, changelog-declared-SemVer-impact-vs-actual-delta (pre-/post-1.0 aware), `include/expansion_config.h` C-fallback-vs-`config.mk` cross-check, and save-format migration-registry epoch reachability. |
| Migration registry | `scripts/modernize/migrations/registry.py` | Declares mechanical vs. manual save-format epoch transitions; see [`docs/migration_registry.md`](migration_registry.md). |
| Provenance manifests | `scripts/release_rehearsal/provenance.py`, `docs/release_data/provenance/*.json` | Factual, generated code/asset/submodule provenance records: one exact record per exact allowlisted path (never directory-prefix/category credit), bound to the exact allowlist by a literal exact-path bijection (no gap, no ghost entry, no duplicate/leftover-category-style entry), plus a submodule gitlink-pin cross-check. |
| Exact source allowlist | `scripts/release_rehearsal/allowlist.py`, `docs/release_data/source_allowlist.json` | Exact, deterministic, generated **per-member** (every tracked blob -- regular file, executable, or symlink) allowlist, with a bound-and-cross-checked exact Git mode per member (`"modes"`, schema_version 4) -- no directory-level/prefix grant, and neither a gitlink nor a self-referential-evidence blob (see Tree coverage below) is ever a member here. `check_allowlist_completeness()`/`check_mode_identity()` fail actionably the moment a tracked blob, its mode, or the checked-in allowlist ever disagree in any direction. |
| Exact tree coverage / export exclusions | `scripts/release_rehearsal/tree_coverage.py`, `docs/release_data/export_exclusions.json` | Proves the included allowlist and an explicit, factual export-exclusions file (every excluded member's exact path, kind -- `"gitlink"` or `"self_referential_evidence"` -- immutable mode, and reason) are an exact, disjoint partition of the *complete* immutable HEAD tree -- a new tracked path (of any kind) absent from both fails coverage outright; a changed/stale pin, or a kind mismatch, is reported, never silently trusted. issue #9 R1/R2 fix: a `"gitlink"` exclusion additionally carries and strictly cross-checks an exact, immutable OID; a `"self_referential_evidence"` exclusion never carries an OID at all (schema requires it absent/`null`; a supplied/stale/fake value is a hard validator rejection, never merely "unchecked"), and this kind's own path is itself validated -- as a validator invariant, not a generator convention -- against a small, hard-coded, curated policy set (today exactly `docs/release_data/provenance/code.json`); an arbitrary tracked path claimed under this kind, or an extra/uncurated row of this kind, fails coverage outright even when constructed directly, bypassing the generator entirely. Also proves the actually-built archive's members equal the included set exactly (with a dedicated regression test against the real, wired archive-building call site), and closed-world-validates a genuine non-git extracted candidate tree's missing/extra/unsafe paths (of any filesystem entry kind, never skipping a stray symlink) against this same contract. |
| `.gitmodules` parser | `scripts/release_rehearsal/gitmodules.py` | Minimal, dependency-free parser for Git's `[submodule "name"]` INI dialect, reading the blob's exact content at an immutable target SHA (never the worktree path). |
| mgfembp submodule three-way binding | `scripts/release_rehearsal/submodule_binding.py` | Cross-checks `.gitmodules`'s exact section/path/URL, the immutable HEAD tree gitlink's exact mode/OID, the export-exclusion record, and the submodule provenance record all agree exactly -- a missing/duplicate/malformed `.gitmodules` section, a path/URL mismatch, a non-`https://` URL scheme, a wrong gitlink mode/OID, a wrong provenance/exclusion URL/OID, or the submodule path appearing in the *included* allowlist (an allowlist/exclusion contradiction) are all reported. Never fetches/initializes the submodule. |
| Source-release guard | `scripts/release_rehearsal/source_guard.py`, `docs/release_data/map_hex_exceptions.json` | Recursive hard-deny rules (path/extension **and** file-magic) for a release candidate tree/archive, including default-deny `.map`/`.hex` with an exact, factual, file-level exception list. Separate from, and does not modify, `scripts/artifact_guard.py`. |
| Immutable Git-object source | `scripts/release_rehearsal/git_source.py` | `git ls-tree`/`git cat-file --batch` plumbing wrappers so archive content is always read from an immutable commit object, never the mutable worktree/index. |
| Archive/rebuild rehearsal | `scripts/release_rehearsal/archive_rehearsal.py` | Deterministic double-build archive hash comparison (git-blob-bound); rebuild-eligibility evaluation plus (when eligible) an actually-executed double-compile-and-compare, with four machine-distinct states (`not_run`/`blocked`/`failed`/`verified_success`). issue #9 R3 fix: eligibility requires a live, non-empty configured submodule origin URL that agrees exactly with *both* independent immutable declared sources (`.gitmodules` and the provenance record) -- missing or mismatched against either is non-eligible, never a vacuous pass -- and every underlying `git status`/`git config`/`git cat-file` command is itself required to actually succeed, a genuine tooling failure being its own actionable, non-eligible finding rather than a silent false pass. |
| Release-doc link validator | `scripts/release_rehearsal/doc_links.py` | Verifies every relative Markdown link in the release-process doc set resolves to a real file. |
| Workflow guard | `scripts/release_rehearsal/workflow_guard.py` | Validates `.github/workflows/release-rehearsal.yml`'s own permission/safety contract: **any** permission scope (`contents`, `id-token`, `packages`, `pull-requests`, `issues`, `actions`, `checks`, `deployments`, `statuses`, or any future scope) granted `write`, at top level/job level/nested/inline-mapping, any quoting/case/spacing, shorthand `write-all` permissions, token/secrets interpolation, network/upload/publish/deploy/release commands and actions, ref mutation, and common shell-indirection evasions (line continuations, `eval`, `base64 -d`, `sh -c`/`bash -c`, command-position shell-variable/fragment assembly -- including inside a `$( ... )` command substitution *or* a legacy backtick command substitution, and including every variable tracked from a prior `export NAME=value` or `read`/`read -r NAME` statement (every name a multi-variable `read A B` populates, not only the first), not only a plain `NAME=value` assignment -- plus outright rejection of shell process substitution (`<(...)`/`>(...)`, unused by the real workflow)). |
| Action pin inventory | `scripts/release_rehearsal/action_pins.py`, `docs/release_data/action_pins.json` | `workflow_guard.py`'s `check_uses_pins` rejects any external `uses:` reference not pinned to an exact 40-lowercase-hex commit SHA (no version tag -- not even a major-version tag like `v7` -- branch, or short/malformed/wrong-case SHA is ever accepted; a local `./`-prefixed action is the one explicit exemption). `action_pins.py` separately cross-checks that pin against a committed, machine-readable inventory recording the action repository, the pinned SHA, its human-readable upstream version, the official source URL/reference used to establish that correspondence, and the update procedure -- evidence/documentation only, never itself an authorization. |
| CLI / Make targets | `scripts/release_rehearsal/cli.py`, `release.mk` | `make release-check`, `make release-rehearse`, `make release-migrations-check`, plus the machine-distinct `*-require-eligible`/`*-expect-blocked` gate targets, `release-workflow-guard` (now folding in the action-pin inventory cross-check), `release-action-pins-check`, `release-tree-coverage-check`, `release-submodule-binding-check`, and dynamic `cli summary`. |
| CI | `.github/workflows/release-rehearsal.yml` | Runs all of the above read-only, on `pull_request`/`workflow_dispatch` only, and renders `$GITHUB_STEP_SUMMARY` dynamically from the tool's own canonical JSON. |

## Exit code contract

This is the "documented, mechanically tested blocked/eligible contract"
referenced by issue #9's acceptance criteria. `scripts/release_rehearsal/cli.py`'s
own module docstring is the normative source; summarized here. **This
0/1/2/3 contract describes a *direct* CLI invocation** (e.g. `python3 -m
scripts.release_rehearsal.cli check --require-eligible`) -- see the
"Workflow and Make integration" section below for what actually happens
to these codes when the same commands are run through `make <target>`
instead (GNU Make does not preserve/forward a recipe's specific
non-zero exit code; it always reports the target itself as exit `2`
regardless of whether the recipe exited `1`, `2`, `3`, or any other
non-zero value).

* **Exit `0`** -- either (a) plain report mode: the tool ran correctly and
  produced a well-formed report (the report's own `"status"` field says
  either `"mechanically eligible"` or `"blocked"` -- **both are valid,
  expected, successful outcomes of a correctly-functioning checker**), or
  (b) a requested machine-distinct status gate's own condition was
  satisfied (see below). A `"blocked"` report is never printed as, or
  confusable with, a publication success: every CLI additionally echoes
  `status: blocked` plus the exact reasons to stderr (never stdout, which
  is canonical JSON only), and CI's job summary is rendered dynamically
  from that same JSON (see "Workflow and Make integration" below).
* **Exit `1`** (`EXIT_NOT_ELIGIBLE`) -- **only** reachable via
  `--require-eligible`: the candidate's status is not exactly
  `"mechanically eligible"`. This is the publication-eligibility gate a
  stricter pipeline stage uses to fail loudly instead of reading prose;
  today, and expected for the foreseeable future, this always fires,
  because the candidate is genuinely `"blocked"`.
* **Exit `2`** (`EXIT_TOOLING_ERROR`; `1` for the standalone guard
  scripts' own hard-deny findings) -- an **actionable defect**: a
  malformed changelog fragment, a changelog/version-impact mismatch, an
  invalid candidate tag, a missing required doc, a malformed provenance/
  allowlist/map-hex-exceptions JSON file, a stale or incomplete exact
  allowlist, a version-ledger topology/candidate contradiction, a
  `include/expansion_config.h` C-fallback-vs-`config.mk` mismatch, an
  unreachable migration-registry epoch, a broken release-doc link, a
  migration registry inconsistency, a source-release guard hard-deny hit
  (symlink, device, traversal path, prohibited nested magic/extension),
  an archive-rehearsal hash mismatch, a well-formed (40-lowercase-hex)
  `--target-sha` that simply does not resolve to a real object in an
  actual git repository, or a non-git `--repo-root` (a genuine extracted
  archive/non-git candidate tree) whose declared allowlist member(s) have
  no on-disk representation at all. These represent tooling/input
  defects to fix, distinct from an honestly-recorded unresolved business
  fact. Checked **before** either status gate below, since a gate cannot
  be meaningfully evaluated against a broken report.

  All three subcommands (`check`, `summary`, `rehearse`) route through
  one **single, shared top-level exception boundary**
  (`cli.py`'s `_run_guarded`/`EXPECTED_TOOLING_ERRORS`): every expected
  tool/input/repository exception class raised anywhere in the call
  graph below them --
  `git_source.GitSourceError`, `archive_rehearsal.ArchiveRehearsalError`,
  `source_guard.SourceGuardError`, `allowlist.AllowlistError`,
  `provenance.ProvenanceError`, `manifest.ManifestError`,
  `expansion_config.ConfigError`, or `OSError` -- is always converted
  here into exit `2` with an actionable message, **never** an unhandled
  Python traceback. This matters specifically because an *unhandled*
  exception's own process exit code is `1`, which would otherwise be
  silently indistinguishable from the deliberate, documented
  `EXIT_NOT_ELIGIBLE` (a fresh, independent review reproduced exactly
  this collision: a well-formed but nonexistent `--target-sha`, and the
  documented non-git/extracted-tree path, both used to traceback as exit
  `1` instead of failing actionably as exit `2` -- see "The documented
  non-git/extracted candidate path" below). Anything *not* in that
  exception tuple still tracebacks, on purpose -- this is deliberately
  not a blanket `except Exception`, so a genuine programming bug in this
  tooling is never silently absorbed alongside an expected input error.
* **Exit `3`** (`EXIT_STATUS_MISMATCH`) -- **only** reachable via
  `--expect-status {blocked,mechanically-eligible}`: the actual status is
  not exactly the one the caller named. There is no default/implicit
  expected value -- the caller must say which status they expect, every
  time.

`--require-eligible` and `--expect-status` are mutually exclusive (each is
its own distinct gate). `make release-check` and `make release-rehearse`
(plain, no flags) both exit `0` on the current tree (a well-formed
`"blocked"` report) and exit non-zero only if a genuine tooling defect is
introduced -- this is intentional so this rehearsal can run in CI as an
ordinary, informative, always-green (until something is actually broken)
job without ever being misread as "ready to publish". The **separate**
`make release-check-require-eligible` / `make release-rehearse-require-
eligible` targets wrap a CLI invocation that is **intentionally** expected
to fail (the underlying CLI itself exits `1`) while the candidate is
`"blocked"`; `make release-check-expect-blocked` / `make release-rehearse-
expect-blocked` wrap the complementary health-check CLI invocation that
exits `0` only while truly `"blocked"` and exits `3` the moment that ever
silently stops being true. **Observed through `make` itself** (rather than
the CLI directly), only the exit-`0`-vs-non-zero distinction survives:
GNU Make reports *any* failed recipe -- whether the underlying CLI exited
`1`, `2`, or `3` -- as the target's own exit code `2`, never the recipe's
original code (this is standard, unconfigurable GNU Make behavior, not
specific to this repository's tooling). See "Workflow and Make
integration" below for the exact, per-target breakdown of what `make
<target>` itself reports.

## Release manifest and identity checks

`scripts/release_rehearsal/manifest.py build_manifest()` resolves (via
`scripts/modernize/expansion_config.py`, never re-derived):

* the framework SemVer (`version_string`/`version_packed`) and config
  fingerprint from `config.mk`;
* a **candidate tag string** (`vMAJOR.MINOR.PATCH`) -- **validated as text
  only**; this tooling never runs `git tag`;
* a **target SHA**: from `git rev-parse HEAD` when `.git` metadata is
  present, or an **explicit, exact 40-lowercase-hex `--target-sha`
  override** when it is not (an archive/non-git tree) -- a missing
  override in that case is an actionable error, never silently
  `"unknown"`. **Normal, non-archive usage (issue #9 mandatory
  correction) never leaves this implicit either:** `release.mk`'s
  `RELEASE_TARGET_SHA ?= $(shell git rev-parse HEAD)` is passed
  explicitly as `--target-sha` by every `release-check`/`release-
  rehearse` target (and their `-require-eligible`/`-expect-blocked`
  siblings), and `.github/workflows/release-rehearsal.yml` overrides it
  via a job-level `env: RELEASE_TARGET_SHA: ${{ github.sha }}` -- so CI
  always binds to the *exact, immutable checked-out commit*, never an
  independently-resolved value that could theoretically disagree with
  the checkout step. `scripts/release_rehearsal/workflow_guard.py`'s
  `check_release_target_sha_binding()` fails closed if a release
  publication-eligibility step is ever added without this binding;
* a **short-form derivation** (`target_sha[:8]`) matching
  `scripts/modernize/save_format_tool.py`'s own
  `ExpansionSaveMeta.buildCommitShort` derivation
  (`build_commit[:8]`), so an embedded short-form value can be verified
  against the full target SHA while the manifest/evidence always retains
  the full 40-character SHA;
* a **mandatory embedded build-identity binding** (issue #9 mandatory
  correction #2, `check_embedded_identity_binding()`): a *missing*
  `embedded_short_sha` (nobody supplied/verified one at all) is folded
  into `"reasons"` as its own always-present, never-mockable-away
  finding -- exactly symmetric to the external-attestation gate below --
  so a candidate can never be reported `"mechanically eligible"` while
  its build-identity binding to `target_sha` was never actually verified
  against a real embedded artifact. This is never conditional/optional
  on any `check`/`rehearse`/`summary` invocation. A *supplied-but-wrong*
  value is a stronger, distinct failure mode: `verify_short_sha()` raises
  an actionable `ManifestError` before `build_manifest()` even reaches
  its reasons/status computation, rather than being folded in as a soft
  "blocked" reason. `cli.py`'s `cmd_rehearse` never requires a caller to
  manually supply this -- it threads through the real, verified short SHA
  automatically extracted from the rebuild it just executed (see
  "Rebuild rehearsal" below) whenever that rebuild reaches
  `"verified_success"`;
* a **stale current-epoch-claim regression check**
  (`check_epoch_claims()` -- `scripts/release_rehearsal/epoch_claims.py`)
  over release docs/headers, catching the known "epoch stays 1"
  falsehood shape without ever rejecting a legitimate historical
  migration statement ("bumped 1 -> 2");
* a **stale aggregate-test-count-claim regression check**
  (`check_stale_count_claims()` --
  `scripts/release_rehearsal/stale_count_claims.py`) over release
  closure evidence/docs, catching a hardcoded frozen total in the shape
  `(N tests)`/`Ran N tests` (N being any digit sequence) without ever
  rejecting a legitimate small semantic constant or migration delta
  ("2 new regression tests", "epoch 1 -> 2");
* changelog validity + aggregate declared SemVer impact;
* required-docs presence;
* save-format compatibility epoch + migration-registry consistency, **and**
  registry epoch *reachability* (`scripts/release_rehearsal/consistency.py`'s
  `check_migration_epoch_reachability` -- a future epoch bump with no
  connecting registry entry is an actionable contradiction, not silently
  ignored);
* the version ledger's own topology (unique versions, exactly one
  `status: "current"` entry that never itself carries a non-null EOL
  date, previous/current/next ordering, valid EOL dates) **and** its
  agreement with `config.mk`'s actual candidate version
  (`docs/release_data/version_ledger.json`,
  `check_version_ledger`);
* the changelog's declared aggregate SemVer impact versus the *actual*
  version delta from the ledger's previous version, honoring this
  project's pre-1.0 carve-out (`check_changelog_semver_delta`);
* `include/expansion_config.h`'s `#ifndef`-guarded C fallback literals
  (version/ROM-identity/save-epoch, plus the config-fingerprint
  placeholder's shape) against `config.mk`'s own resolved values
  (`check_c_fallback_metadata`);
* the exact per-member source allowlist's completeness against the
  actual tracked-file/gitlink set at the target SHA
  (`scripts/release_rehearsal/allowlist.py`'s `check_allowlist_completeness`
  -- a new/unlisted tracked file, or a stale entry for something no
  longer tracked, is an actionable failure, never a silent omission);
* previous/next supported versions -- when non-null, each must
  actually exist as a unique entry in the ledger's own `supported[]`
  array, sit on the correct side of the current version, and carry a
  status-compatible entry (`docs/release_data/version_ledger.json`,
  `check_version_ledger`);
* provenance status **and its exact coverage of the allowlist**
  (`scripts/release_rehearsal/provenance.py`);
* source-release guard status (`scripts/release_rehearsal/source_guard.py`);
* every relative link in the release-process doc set actually resolves
  (`scripts/release_rehearsal/doc_links.py`);
* the rebuild rehearsal's own status (`scripts/release_rehearsal/
  archive_rehearsal.py`'s `rebuild_rehearsal_blocker` -- see "Deterministic
  archive and rebuild rehearsal" below): anything other than
  `verified_success` (i.e. `blocked`, `not_run`, or `failed`) is folded
  into `"reasons"` exactly like every other sub-check.

The manifest's overall `"status"` is `"mechanically eligible"` only if
**every** one of those sub-checks passes -- **including** the rebuild
rehearsal actually having been executed and verified successful twice, not
merely "not attempted" -- otherwise it is `"blocked"`, with every
contributing reason listed verbatim in `"reasons"`.

## Legal and provenance boundary

`docs/release_data/provenance/{code,assets,submodules}.json` record, for
every entry in `docs/release_data/source_allowlist.json` (the included
set) plus the `mgfembp` gitlink exclusion, an honestly-unresolved
`author`/`rightsholder`/`license` of `"NOASSERTION"`,
`"redistribution_approved": false`, and `"reviewer": null`. **This
repository's tooling never invents an author, rightsholder, license, or
reviewer, and never selects or adds a root `LICENSE` file** -- doing so
would be a legal claim this repository has no authority to make on its
own. The `mgfembp` git submodule is separately pinned in
`docs/release_data/provenance/submodules.json` to the exact commit
`c87e74dcd6c8878b809e013cd8ff0c52baa75332` (matching this worktree's
gitlink) and is, and remains, `redistribution_approved: false`. The
one, sole exception to "every included/gitlink-excluded path has its own
record" is `docs/release_data/provenance/code.json` itself (guardian-
correction remediation, D2): it is neither an included allowlist member
nor a gitlink -- it is its own explicit, minimal, self-referential-
evidence export exclusion (see "Exact immutable HEAD tree coverage and
explicit export exclusions" below) and, structurally, never has (or
needs) its own provenance-manifest entry at all.

`scripts/release_rehearsal/provenance.py evaluate()` is `"blocked"` whenever any
entry has `NOASSERTION`, `redistribution_approved: false`, or no
`reviewer` -- which is every entry, today. Resolving this is a human legal
decision; no amount of running this tooling changes that.

## External attestation is outside candidate control

Issue #9 mandatory correction #5. Everything above -- provenance
records, the exact allowlist/tree-coverage partition, the submodule
binding, the workflow guard, the rebuild rehearsal -- is a *mechanical*
check this in-repo tooling can run and truthfully report on its own.
Real-world publication additionally requires a **protected external
human attestation**: an accountable human reviewer's legal/provenance
approval decision, made *outside* this repository's own tooling. That
attestation is deliberately, structurally **outside this candidate's
control**:

* `scripts/release_rehearsal/manifest.py`'s `check_external_attestation()`
  takes **no arguments at all** and always returns the same fixed
  substatus (`"missing"`) -- there is no in-repo attestation file,
  secret, public key, environment variable, CLI flag, or any other
  candidate-writable path anywhere in this repository that could ever
  change it to `"present"`.
* No in-repo reviewer string recorded in
  `docs/release_data/provenance/*.json`, no `redistribution_approved`
  boolean there, no clean `workflow_guard`/`action_pins`/
  `tree_coverage`/`submodule_binding` result, no CI job output, and no
  `--require-eligible`/`--expect-status` CLI argument is ever *sufficient*
  to produce an overall `"mechanically eligible"` status -- this
  substatus is unconditionally folded into the overall candidate status
  in `build_manifest()`, exactly like every other sub-check, and it can
  never itself report anything other than `"missing"`.
  `scripts/release_rehearsal/tests/test_manifest.py`'s
  `ExternalAttestationCannotBeSatisfiedByInRepoDataTests` proves this
  directly: even with **every other** sub-check mocked to a fully-
  passing, synthetic shape, the overall candidate status still comes
  back `"blocked"`, solely because of this one substatus.
* **Guardian-correction remediation (D5): immutability is not
  authorship protection.** Every "immutable"/"Git-blob-bound" claim
  elsewhere in this document (the archive rehearsal, the rebuild
  materialization, the per-blob provenance identity) means exactly one
  thing: bytes committed under a specific commit SHA cannot be silently
  swapped out *after* that commit exists, without changing the SHA. It
  is never a claim that this repository's source code, or any of its
  JSON config/allowlist/provenance/exclusions data, is somehow immutable
  *from its own candidate author* -- a PR author fully, trivially
  controls what they commit in the first place (including editing a
  `redistribution_approved` boolean, a reviewer name, or any other
  config/data field this tooling reads). No candidate-controlled input
  of *any* kind -- a config/data field in a committed JSON file, a CLI
  flag, an environment variable, or anything else this repository's own
  tooling reads -- can ever satisfy the external attestation requirement,
  precisely because all of it is candidate-controlled; only a human
  reviewer acting *outside* this repository's own tooling and this
  candidate's own commits can ever supply it.
* The **only** entity permitted to combine a genuine external protected
  human attestation with this candidate's own mechanical evidence is a
  **future, separate, out-of-repo human/harness gate** -- one that does
  not exist in this repository and is not any part of this workflow.
  Adding such a gate (an in-repo attestation file/secret/public key, a
  bypass flag, or any candidate-writable path that could flip
  eligibility) is explicitly out of scope for this change and remains
  forbidden.

This is the same "necessary, never sufficient" pattern the workflow
guard already uses (see "Workflow guard is advisory, never
authorization" under "Workflow and Make integration" below) -- applied
one level up, to the *entire* in-repo mechanical result, not just its
permission/safety contract.

## Exact per-member source allowlist and provenance coverage

`docs/release_data/source_allowlist.json` is **not** a top-level-directory
grant any more. It is an exact, deterministic, generated list of every
single tracked *blob* path (regular file, executable, or symlink) --
generated and validated by `scripts/release_rehearsal/allowlist.py`
directly from Git's own tree listing (`git ls-tree -r`), never
hand-maintained. Neither a gitlink (e.g. the `mgfembp` submodule
mountpoint) nor a self-referential-evidence blob (e.g.
`docs/release_data/provenance/code.json`) is ever a member here -- each
is instead its own explicit, factual export-exclusion record (see
"Exact immutable HEAD tree coverage and explicit export exclusions"
below). A brand-new tracked file with no corresponding entry is an
actionable `make release-check` failure (`check_allowlist_completeness`'s
"missing" list), not a silent gap; a stale entry for a file that no
longer exists is equally reported ("stale" list) so the allowlist can
never quietly drift out of sync with reality in either direction.
Regenerate it with:

```sh
python3 -m scripts.release_rehearsal.allowlist generate --target-sha HEAD --write
```

**issue #9 final-review remediation -- 'generation_basis_sha' must be a
real, reachable commit, never a dangling tree.** Both
`docs/release_data/source_allowlist.json` and `docs/release_data/
export_exclusions.json` record a `"generation_basis_sha"` field whose
own schema/comment text promises it documents *which commit* the file
was last regenerated against. `--target-sha index` (a development-time
convenience that serializes the *current staged index* into a real Git
tree object via `git write-tree` -- see `git_source.write_index_tree`)
is useful for previewing/verifying an in-progress, not-yet-committed
change, but its resulting object is a **tree**, never a commit, and (if
never actually committed) is never reachable from any ref either -- a
future `git gc` can prune it at any time. Writing that value into the
actual checked-in file would make the schema's own "which commit"
promise false and ephemeral. Both CLIs therefore **refuse** `--write`
combined with `--target-sha index` outright (`generate --write` /
`generate-exclusions --write` exit 2, actionably, without touching the
checked-in file) -- `--target-sha index` remains available without
`--write` for a local, uncommitted stdout preview only. `allowlist.py
check()` and `manifest.check_tree_coverage()` additionally both call
the single, shared `git_source.check_generation_basis_is_commit()`
check on every `make release-check`, which fails closed if either
checked-in document's own `"generation_basis_sha"` is not itself a
real, still-reachable commit object -- so this exact defect (a
dangling/tree basis silently committed into checked-in evidence) can
never regress unnoticed.

### Archive member mode policy (guardian-correction remediation, D4)

`docs/release_data/source_allowlist.json` (schema_version 4) additionally
records a `"modes"` map: every included path's exact Git mode
(`100644`/`100755`/`120000`). `allowlist.py check()` cross-checks this
map is an exact bijection with `"paths"` (no gap, no orphan) and, for a
real git repository, that every declared mode still matches the live
tree's actual mode for that path (`check_mode_identity`) -- a committed
executable-bit (or other mode) change now makes this canonical data
stale/fail until `allowlist generate --write` is re-run, exactly like a
content or path change already does.

**issue #9 R5 fix -- mode binding cannot be silently switched off.** An
earlier version of this schema treated `"modes"` as effectively
optional at load time: `load_allowlist_modes()` returned `None` with no
error at all when the key was simply absent, and nothing anywhere
checked `schema_version` itself -- so deleting the `"modes"` key (or
rolling `schema_version` back to an older value) silently disabled
every mode check above with no actionable failure, while every other
allowlist check kept passing. `load_allowlist_modes()` now hard-requires
`schema_version` to be *exactly* the current, single supported value
(`4`; every real checked-in document has always been schema_version 4,
so there is no legitimate older-schema fallback to preserve) -- a
missing, downgraded, upgraded-but-unknown, or wrong-type
`schema_version` is an actionable `AllowlistError`, raised *before* any
mode checking is even attempted. Once `schema_version` passes, `"modes"`
itself becomes unconditionally mandatory (a missing key is now the same
class of hard error, never a silent `None`), and its bijection/identity
checks always run -- there is no code path left that skips them.

This mode binding is a **drift-detection/provenance-identity** concern
only -- it is deliberately **not** an archive-fidelity promise.
`archive_rehearsal.py`'s `build_deterministic_archive` continues to
canonicalize *every* written tar member's mode to a fixed
`CANONICAL_FILE_MODE = 0o644`, regardless of the source path's actual
Git mode (a `100755` executable script and a `100644` ordinary file both
land in the archive with the identical `0o644` tar mode) -- this is a
deliberate, tested determinism policy (byte-identical archives from
byte-identical trees, independent of a host's own umask/tar-implementation
quirks), not an oversight. A tracked symlink (`120000`) is never archived
at all (`source_guard.py`'s pre-existing hard-deny), so the only modes
that ever reach the archive-writing step in practice are `100644`/
`100755`, both mapped to the same fixed output mode. If archive-fidelity
mode preservation is ever needed for `120000`-adjacent tooling, that
would be a distinct, explicitly-reviewed policy change -- this document
and the allowlist's own `"modes"` map exist so that decision is at least
made with full, exact, live information about what modes are actually in
play, never guessed at.

**Provenance coverage is now a literal, exact, one-record-per-member
bijection -- never directory-prefix/category credit.** A fresh,
independent review found the previous design let a single category-level
provenance entry (e.g. `"src"`) "cover" every allowlisted path nested
under it by directory prefix, which meant a brand-new tracked file, once
added to the allowlist, could silently inherit an ancestor directory's
provenance record with no dedicated review decision of its own. That is
fixed: `docs/release_data/provenance/{code,assets,submodules}.json` now
contain one exact provenance record **per exact allowlisted path** (as
many records as there are allowlist entries -- currently in the
thousands, one for every tracked file plus the single `mgfembp` gitlink),
and `scripts/release_rehearsal/provenance.py`'s coverage functions
(`coverage_gaps`, `find_ghost_entries`, `find_duplicate_entry_paths`,
`evaluate_coverage`) are now pure **exact-path set operations**: an
entry's `path` covers *only* that literal path, never a descendant. A new
allowlisted file with no exact same-path provenance entry is an actionable
`missing provenance entry for ...` finding, exactly like a brand-new
tracked file with no allowlist entry is an actionable allowlist finding --
there is no auto-granting at validation time in either case.
`find_ambiguous_entries()` is kept as a defense-in-depth hygiene guard
(it can never legitimately fire against a genuine one-record-per-tracked-
file data set, since no real Git blob path can be a directory-prefix
ancestor of another) that catches a leftover category/directory-style
entry mixed in with exact ones.

Hand-authoring thousands of otherwise-identical `NOASSERTION` records by
hand would itself be an unreviewable maintenance hazard, so
`scripts/release_rehearsal/provenance.py` also provides a small,
deterministic **generator**: `PROVENANCE_ROOT_SEED` is the single,
human-curated input (one entry per reviewable top-level root -- the same
roots this repository already reviewed at category granularity before
this fix), and `generate_exact_entries()` mechanically fans each root's
`category`/`notes` out to every exact allowlisted (or, for a
`"submodule"`-category root, explicitly excluded) path nested under (or
equal to) it. **Guardian-correction remediation (D5): this generator
never "preserves" a previously-recorded fact across a changed or
brand-new blob -- there is nothing to preserve.** Every run always,
unconditionally, freshly proposes the exact same honest starting point
for `author`/`rightsholder`/`license`/`redistribution_approved`/
`reviewer` (`"NOASSERTION"`/`"NOASSERTION"`/`"NOASSERTION"`/`false`/
`null`) for every path, however it was assigned a root -- it never
invents a *different* fact, but it equally never carries a human's
*already-recorded* `redistribution_approved: true`/named `reviewer`
forward either: regenerating after a human has actually resolved an
entry would silently discard that resolution back to the unresolved
starting point (this is precisely why `check`/`evaluate_coverage`'s
runtime validation path -- see below -- never invokes this generator
itself; it only ever reads whatever a human has actually committed).
A `"submodule"`-category entry's `pinned_commit` and `url` are always
read fresh from the immutable target tree/`.gitmodules` at generation
time, never hardcoded or carried over from any existing on-disk
record -- so a re-pinned submodule commit or a changed `.gitmodules` URL
is reflected immediately, honestly, the next time this generator is run,
never silently stale. This directory-prefix fan-out is **exclusively a
generator-time convenience**; it plays no role in, and is never invoked
by, the runtime `check`/`evaluate_coverage` validation path, which only
ever reads whatever exact records are actually committed to disk.
Regenerate (after adding a new root to `PROVENANCE_ROOT_SEED` for a
genuinely new top-level location, or whenever the allowlist changes)
with:

```sh
python3 -m scripts.release_rehearsal.provenance generate --write
```

`scripts/release_rehearsal/provenance.py`'s `check_gitlink_pins()` is an
additional cross-check specific to the `"submodule"`-category entry: it
compares the provenance record's declared `pinned_commit` against the
actual gitlink object id Git's own tree records for that exact path (via
`git ls-tree`), independent of whether the submodule is actually
initialized/checked out locally -- a provenance record that merely
*claims* a pin is exactly as much an honesty gap as an unresolved
NOASSERTION fact if the superproject's own tree does not actually record
that commit.

## Exact immutable HEAD tree coverage and explicit export exclusions

Issue #9 mandatory correction #2 closes a residual gap the exact
per-member allowlist above, on its own, still left open: the `mgfembp`
submodule **gitlink** used to sit *inside* that same allowlist file as an
ordinary-looking entry (`archive_rehearsal.py` has always silently
skipped it via `not entry.is_gitlink` when building archive bytes, since
a gitlink has no blob content at all -- but nothing forced that skip to
be an explicit, separately reviewed, checked-in decision).

`scripts/release_rehearsal/tree_coverage.py` defines two canonical sets
directly from an immutable `git ls-tree -r <target_sha>`:

* **included** -- `docs/release_data/source_allowlist.json`'s exact
  per-blob paths (regular file, executable, or symlink -- never a
  gitlink any more; `allowlist.py`'s generator schema_version bumped to
  `3`, then to `4` for the added `"modes"` mode-binding map -- see
  "Archive member mode policy" below -- to reflect this);
* **excluded** -- `docs/release_data/export_exclusions.json`'s exact,
  factual records: for every currently-excluded member, its exact path,
  `kind`, immutable `mode`, and a factual `reason`. Two kinds are
  modeled today (a brand-new, third kind is deliberately rejected
  fail-closed rather than silently accepted), and -- issue #9 R1/R2 fix
  -- each kind now has genuinely distinct, kind-specific OID/path
  semantics that the *validator itself* enforces (never merely a
  convention the generator happens to follow -- see below):
  * `"gitlink"` -- a real Git gitlink with no blob content in this
    repository's own tree at all. Today this is exactly one entry:
    `mgfembp`, excluded because no approved submodule content is
    present (see "Legal and provenance boundary" above); a gitlink
    exclusion still requires its own separate, dedicated provenance-
    manifest legal-review record elsewhere (`docs/release_data/
    provenance/submodules.json`). It carries and strictly requires an
    exact, immutable 40-lowercase-hex `oid`, cross-checked against the
    live tree exactly like before -- a changed/stale pin is reported,
    never silently trusted.
  * `"self_referential_evidence"` (guardian-correction remediation, D2;
    issue #9 R1/R2 fix below) -- an ordinary tracked *blob* (never a
    gitlink) that is structurally excluded because it cannot record a
    live-content-bound identity fact about itself without an unsolvable
    circular dependency. Today this is exactly one entry:
    `docs/release_data/provenance/code.json` itself -- `provenance.py`'s
    own generated "code"-category manifest, which is what *every other*
    included blob's own oid/sha256 provenance record (including the
    records describing `assets.json` and `submodules.json` themselves)
    actually lives inside. A record describing `code.json` *inside*
    `code.json` would need to embed a hash of its own not-yet-finalized
    content (a "hash quine"); there is no ordinary regeneration process
    that reaches a fixed point for that. Unlike a gitlink exclusion,
    this kind's own `reason` field *is* its complete, sufficient,
    externally-owned evidence record -- it never requires (and never
    receives) a *second*, separate provenance-manifest entry (see "Exact
    per-file provenance identity" below for why exempting a path from
    live cross-checking inside `check_blob_identity()` is the wrong fix,
    and excluding it from the archive/required-coverage set entirely is
    the right one).

    **issue #9 R1/R2 fix -- curated path-only-plus-mode exclusion, no
    OID semantics at all.** Two independent defects an earlier version
    of this fix left open, both closed as *validator* invariants (in
    `tree_coverage.check_partition()`/`load_exclusions()` themselves,
    independent of whichever code happens to construct an exclusion
    entry -- so neither gap can be reopened merely by bypassing the
    generator):

    * **R1 (arbitrary self-evidence exclusion injection).** Previously,
      *any* tracked path could be claimed under
      `kind: "self_referential_evidence"` with a fabricated `oid`, and
      tree coverage stayed clean -- silently moving an arbitrary blob
      out of the archive+provenance-required set with no actual review.
      This kind's `path` is now checked against a small, hard-coded,
      human-curated policy set (`SELF_REFERENTIAL_EVIDENCE_PATHS`,
      today exactly `{"docs/release_data/provenance/code.json"}`) in
      *both* `load_exclusions()` (the JSON-file-loading gate) and
      independently again inside `check_partition()` itself (so even a
      directly-constructed exclusion entry that never went through
      `load_exclusions()` at all is still caught) -- no prefix, no
      wildcard, no second/extra row of this kind for any other path. A
      claim against any other path, or an uncurated extra row, fails
      the partition outright (`invalid_self_referential_evidence`).
      Dropping the one legitimate curated exclusion is unaffected and
      still separately caught by the pre-existing `missing_included`
      accounting once the real path resurfaces as neither included nor
      excluded.
    * **R2 (stale, unenforced, falsely-immutable-sounding OID).** This
      kind's exclusion record used to carry an `oid` that was, in
      truth, never cross-checked against anything at all (silently
      "documentary/best-effort" only, while nearby prose read as if it
      were an immutable, verified fact) -- and the real, checked-in
      document's own recorded value had already drifted stale relative
      to the live blob well before this fix, precisely because nothing
      ever caught that drift. There is no such thing as a truthful,
      immutable oid for this kind in the first place: a file cannot
      record an exact hash of its own not-yet-finalized content without
      exactly the "hash quine" cycle described above. The schema now
      requires this kind's `oid` to be absent or JSON `null` --
      `load_exclusions()` hard-rejects any supplied/stale/fake value
      (a real 40-hex OID, an empty string, anything but `null`/absent)
      -- and `generate_exclusions_document()` always writes `null` for
      it, never a live tree OID. **Nothing about this kind's OID is
      ever claimed, recorded, or cross-checked as a content-identity
      fact**; a content change to the curated path is instead caught
      purely by the ordinary tree-membership contract (it remains a
      live, correctly-kinded, correctly-moded blob either way, so
      neither a stale nor a "correct" OID was ever doing any real work).
      This is a structural path-only-plus-mode exclusion and **external
      rehearsal evidence about this repository's own tooling -- never
      source archive content, and never itself a redistribution/legal
      authorization of any kind.** Every *included* blob (every
      ordinary allowlist member, `assets.json`, and `submodules.json`
      alike) remains exactly OID/SHA256-bound with no exemption at all;
      only this one, single, curated, self-referential path is excluded
      this way.

`check_partition()` proves these two checked-in sets, **together**,
account for *every* tracked path in the complete tree **exactly once**:
a brand-new tracked path of any kind (blob or gitlink) that is not
already in one of these two sets fails coverage outright -- it is never
silently absorbed into either side, and it never merely disappears from
the archive. It also rejects any overlap (a path listed in both), any
stale entry (an included/excluded record that no longer matches a real
tracked path of the expected kind -- including a kind mismatch, e.g. a
`"gitlink"`-kind exclusion whose path is now an ordinary blob, or vice
versa), and any export-exclusion path that is a directory-prefix
ancestor of another tracked path (broad-prefix directory exclusions are
forbidden -- every exclusion must be an exact leaf, exactly like every
allowlist entry already is).

Two further checks close the loop end-to-end:

* **Archive-member exact equality** (`check_archive_membership_exact`) --
  wired directly into `archive_rehearsal.py`'s own archive-building path
  (not merely a separate, possibly-skipped report): the actually-built
  archive's members must equal the included set exactly, or the archive
  build itself refuses (`ArchiveRehearsalError`) rather than silently
  producing a subset/superset. Guardian-correction remediation (D5):
  `scripts/release_rehearsal/tests/test_archive_rehearsal.py`'s
  `test_wired_membership_exact_check_refuses_on_extra_members` forces
  this exact, wired call site (not merely the standalone `tree_
  coverage.check_archive_membership_exact` helper) to refuse, proving
  the wiring itself, not only the underlying helper's own logic.
* **Non-git closed-world coverage** (`check_non_git_tree`) -- for a
  genuine already-extracted candidate tree (no `.git` at all), reports
  three independent, actionable buckets: `missing` (an included path
  with no on-disk file, or a gitlink-kind excluded path with no on-disk
  directory), `extra` (a present filesystem entry of *any* kind --
  regular file, symlink, hardlink, device, FIFO, socket -- accounted for
  by neither set), and `unsafe` (a path present with the wrong *shape*
  -- e.g. an included path materialized as a symlink, a gitlink-kind
  excluded path materialized as a plain file instead of a directory, or
  a self-referential-evidence-kind excluded path present *at all*, in
  any shape -- it was never part of the archive to begin with, so
  nothing should ever be there). Never invokes any git command.
  Guardian-correction remediation (D5): a fresh, independent review
  found the previous enumeration (`_present_regular_files`) `continue`d
  straight past any symlink it found, making a stray, unlisted symlink
  at any path completely invisible to both `extra` and `missing`
  accounting; the replacement (`_present_paths`) never skips a
  filesystem entry by kind -- only a genuine, non-symlink directory is
  still ever walked through rather than reported.

`scripts/release_rehearsal/manifest.py`'s `check_tree_coverage()` folds
this into the overall candidate report (`"tree_coverage"`) exactly like
every other sub-check -- any finding here forces the overall status to
`"blocked"`. Provenance coverage (below) now spans **both** the included
allowlist **and** the export exclusions (`tree_coverage.
combined_required_paths`), so `mgfembp`'s own provenance/exclusion record
is neither a false "ghost" nor a false "gap".

Regenerate with:

```sh
python3 -m scripts.release_rehearsal.tree_coverage generate-exclusions --target-sha HEAD --write
```

## mgfembp submodule three-way binding

Issue #9 mandatory correction #4: `scripts/release_rehearsal/
submodule_binding.py` proves the `mgfembp` submodule is consistently
described across every immutable source this repository records about
it -- never merely "the JSON files happen to look similar":

1. `.gitmodules`'s blob content at the target SHA (parsed by the new,
   minimal, dependency-free `scripts/release_rehearsal/gitmodules.py` --
   never the worktree path): the exact `[submodule "mgfembp"]` section's
   `path` and `url`. A missing section, more than one section declaring
   the same path, a path mismatch, a missing/empty `url`, or a `url` not
   using the `https://` scheme (this module's explicit, minimal URL-
   scheme policy) are all reported.
2. The immutable HEAD tree's own gitlink entry for that exact path
   (mode `160000`, an exact pinned commit OID).
3. `docs/release_data/export_exclusions.json`'s exact exclusion record
   (same path, `kind: "gitlink"`, and OID -- cross-checked against the
   live gitlink OID, exactly like `tree_coverage.py`'s own check).
4. `docs/release_data/provenance/submodules.json`'s exact provenance
   record (same path, `url`, `pinned_commit`) -- `provenance.py`'s
   schema now requires every `"submodule"`-category entry to also
   record a non-empty `url`, cross-checked against `.gitmodules`'s own
   URL; the deterministic generator (`generate_exact_entries`) reads
   this URL fresh from `.gitmodules` every run, never hardcoding it.

A `mgfembp` path present in the *included* source allowlist (rather than
only the export exclusions) is reported as an explicit allowlist/
exclusion contradiction. This module never fetches, initializes, or
clones the submodule -- every check reads only already-committed,
immutable blob/tree content and the already-checked-in JSON data files.
Folded into the overall candidate status
(`scripts/release_rehearsal/manifest.py`'s `check_submodule_binding`,
`"submodule_binding"`) exactly like every other sub-check -- any finding
here forces `"blocked"`. Also directly runnable standalone via
`make release-submodule-binding-check`.

## Source-release guard

`scripts/release_rehearsal/source_guard.py` is intentionally **separate from, and
does not modify or weaken**, `scripts/artifact_guard.py` (which continues
to review ordinary tracked-Git content per
[`docs/issue-resolution-policy.md`](issue-resolution-policy.md)). It
instead governs an actual *release candidate tree or archive*:

* the **exact per-member allowlist** above;
* recursive hard-deny rules for prohibited nested files/magic bytes
  (mirroring, independently, `scripts/artifact_guard.py`'s prohibited
  extension/magic/path-segment classes): object/library/executable/debug
  artifacts (`.o .obj .a .lib .so`, including versioned shared-object
  suffixes like `.so.1.2.3`, `.dll .dylib .exe .pdb`, `.dSYM` bundles),
  generic archive/compression containers including Java/JVM variants
  (`.zip .jar .war .ear .tar .tgz .gz .bz2 .xz .7z .rar`), the pre-existing
  GBA ROM/save-state/patch formats, and arbitrary build `.map`/`.hex`
  output (default-denied; see below); content-based magic detection (ZIP,
  Unix `ar`, gzip, bzip2, xz, 7z, rar, zstd, `ustar` tar, PE/Mach-O/Java
  executables, plus the pre-existing ROM/patch magics) that catches a
  nested archive/executable regardless of its extension or nesting depth;
  absolute or `..`-traversal paths, `a//b` double slashes, `a/./b`
  literal-dot components, leading/trailing slashes, NUL/control bytes,
  backslashes, symlinks, hardlinks (`st_nlink > 1`), and devices/FIFOs/
  sockets -- for a real filesystem tree (`scan_tree`), a tar archive's
  members without ever extracting them to disk (`scan_archive_members`,
  using `TarFile.extractfile()` for read-only content access only, never
  `TarFile.extractall()`), and immutable Git blobs (see "Immutable archive
  inputs" below).
* **`.map`/`.hex` are default-denied**, exactly like every other build
  artifact extension -- there is no broad carve-out. The *only* exception
  mechanism is `docs/release_data/map_hex_exceptions.json`: an exact,
  file-level allowlist where every entry records a factual rationale.
  Every one of the 12 tracked `.map`/`.hex` paths at the time of this
  audit is a synthetic/hand-authored test fixture under a `tests/
  fixtures/` directory (verified individually; see that file's own
  `_comment`/entries) -- a real build-generated map (e.g.
  `fireemblem8.map`) is gitignored and was never one of the 12, so it
  remains hard-denied with no exception.

`scan_source_release_candidate()` is what `manifest.py`'s source_guard
check (and therefore `make release-check`/`make release-rehearse`)
actually calls. It picks the right check for what `root` *is*: a genuine
extracted archive/other non-git candidate tree (the tree *is* the
release candidate) still gets the full fail-closed `scan_tree(...,
closed_world=True)` check above -- every top-level entry must be covered
by the allowlist, everything is walked. A **live git development
worktree** is not that: it routinely accumulates gitignored/untracked
build byproducts (`.dep/` dependency output, a built ROM/ELF, host tool
binaries, stale `build/` output, etc.) that were never going to ship. For
a worktree, `scan_source_release_candidate()` instead evaluates exactly
the git-tracked-intersect-allowlist candidate set
(`git_tracked_allowlisted_files()`, now an **exact**, not top-level-prefix,
match) that `scripts/release_rehearsal/archive_rehearsal.py` itself would
archive, running every hard-deny rule above against that exact set -- so
the report is deterministic and independent of what happens to be lying
around on disk, while any *tracked* malicious/unsafe content (including a
tracked symlink) is still denied exactly as before.

## Deterministic archive and rebuild rehearsal

`scripts/release_rehearsal/archive_rehearsal.py`:

* builds a canonical, deterministic, **uncompressed** tar (fixed member
  order, `mtime=0`, `uid=gid=0`, empty `uname`/`gname`, fixed
  `0o644`/`0o755` modes, regular files only) **twice**, into two
  independent `tempfile.TemporaryDirectory()`s, hashes both with SHA-256,
  and asserts they match;
* both temporary directories (and therefore both archives) are removed by
  their `with` context managers on **any** exit path, success or
  exception -- nothing is ever left on disk, nothing is ever uploaded.

### Immutable archive inputs

When `root` is a real Git working tree, every byte the archive contains
is read **exclusively** through Git plumbing
(`scripts/release_rehearsal/git_source.py`'s `git ls-tree`/`git cat-file
--batch` wrappers), keyed to an exact, resolved commit SHA -- **never** by
opening the tracked file's path in the worktree. A tracked file edited on
disk, or even `git add`ed, without being committed therefore cannot
change a single byte of the archive: the archive is bound to the commit
object, not the checkout or the index. `rehearse_archive_twice()` resolves
that commit SHA **once**, before either of the two builds runs, so both
builds target the exact same immutable commit.
`scripts/release_rehearsal/tests/test_archive_rehearsal.py`'s
`GitBackedArchiveTests` mutate a tracked file directly on disk (unstaged),
then stage it (`git add`, still uncommitted), and prove the archive
hash is unaffected either way -- and that an actual commit *does* change
it, and that an unsafe Git mode (a tracked symlink) or a gitlink (no blob
content at all) are handled correctly even though fully committed.

### The documented non-git/extracted candidate path

Only for a genuine already-extracted archive/non-git candidate tree (no
`.git` at all -- the tree *is* the candidate, e.g. a downloaded and
extracted GitHub source archive) does the above fall back to a raw
filesystem walk of exactly the allowlisted entries. This path is fully
end-to-end tested (`scripts/release_rehearsal/tests/test_cli.py`'s
`ExtractedNonGitTreeEndToEndTests`, against a real `git archive HEAD |
tar -x` extraction of this repository's own current HEAD) and:

* **requires** an explicit, exact 40-lowercase-hex `--target-sha`
  override (`resolve_target_sha` in
  `scripts/release_rehearsal/manifest.py`, shared by `check`, `summary`,
  and `rehearse` alike) -- a missing override is an actionable exit `2`,
  never a silent `"unknown"` identity and never a traceback;
* **never invokes any git command** against the extracted tree -- not
  `git ls-tree` (`scripts/release_rehearsal/allowlist.py`'s
  `check_allowlist_completeness_non_git`), not `git submodule status`
  (`scripts/release_rehearsal/archive_rehearsal.py`'s
  `evaluate_rebuild_eligibility`, unconditionally `"blocked"` for a
  non-git `repo_root` -- see "Rebuild rehearsal" below), and not `git
  rev-parse HEAD` (`scripts/modernize/expansion_config.py`'s
  `resolve_build_commit`, which now only ever runs when `repo_root` is
  itself bound to its own `.git` metadata, never as an upward-discovery
  fallback). This is not merely a style preference: git's own upward
  directory discovery could otherwise silently find an unrelated
  *enclosing* repository (if the extracted tree happens to sit inside
  one) and report *that* repository's tracked files/submodule
  state/HEAD as if they belonged to the extracted tree -- exactly the
  "pretend the override proves Git content identity" failure this
  remediation forbids (a fresh-review regression covering this exact
  nested-inside-an-outer-repository scenario lives in
  `NestedOuterRepositoryZeroGitCallsTests` in
  `scripts/release_rehearsal/tests/test_cli.py`);
* **binds** the supplied `--target-sha` into both the manifest and the
  archive report as an **externally-asserted identity** -- recorded
  verbatim, never independently verified (there is no git metadata in a
  non-git tree to verify it against);
* **closed-world-validates exact membership**: a file physically present
  in the tree with no allowlist entry is reported (`check`'s
  `allowlist.errors`, folded into `"reasons"` -- a normal, well-formed
  `"blocked"` business fact, not an error) exactly like
  `source_guard`'s existing `"not-allowlisted"` finding; an allowlist
  member with **no on-disk representation at all** (neither a file nor a
  directory -- e.g. a missing `"mgfembp"` gitlink mountpoint, which a
  real extracted GitHub archive always materializes as an empty
  directory) is instead a `rehearse`-time refusal
  (`ArchiveRehearsalError`, actionable exit `2`): you cannot build
  trustworthy archive bytes when declared content is simply absent.
  `check` (report-only; never attempts to build archive bytes) still
  reports the same gap as a `"blocked"` reason rather than a crash.
* still returns a well-formed, current, honest `"blocked"` result (never
  a fabricated `"mechanically eligible"`) for a structurally sound
  extraction -- `--expect-status blocked` on it exits `0`, exactly like
  the live git worktree.

A fresh, independent review reproduced the previous defect exactly: a
well-formed but nonexistent `--target-sha` in an actual git repository,
and this documented non-git/extracted path (both with and without the
required override), all tracebacked as an unhandled Python exception
(process exit `1`) instead of failing actionably as `EXIT_TOOLING_ERROR`
(`2`) -- see "Exit code contract" above for the fix (a single, shared
top-level exception boundary in `cli.py`) and
`scripts/release_rehearsal/tests/test_cli.py`'s
`NonexistentTargetShaExitContractTests`,
`ExtractedNonGitTreeEndToEndTests`, `MalformedExtractedTreeTests`, and
`Issue9LiteralReproductionCommandsTests` for the regression coverage.

### Rebuild rehearsal

Never describes a rebuild as proved/clean when it was not actually
executed. `rebuild_rehearsal_blocker()` reports exactly one of four
machine-distinct states:

* **`"blocked"`** -- not even eligible to attempt: `mgfembp` is
  uninitialized and/or its provenance is `redistribution_approved: false`
  and/or its checked-out commit does not match the pinned/reviewed
  commit and/or (guardian-correction remediation, D3) its own worktree/
  index is not genuinely clean (`git status --porcelain`, run *inside*
  the submodule itself, is non-empty -- a modified, staged, or untracked
  path in an otherwise commit-matching checkout is exactly as
  disqualifying as a wrong commit) and/or its pinned commit is not
  actually a locally-accessible object of the correct type inside its
  own object database (`git cat-file -e <sha>^{commit}`; a blob/tree
  SHA, a shallow clone missing the object, or any other unresolvable
  value are all "not accessible", never merely "unverified"). **issue #9
  R3 fix:** a *missing* configured `remote.origin.url` used to leave the
  URL check vacuously passing (every branch of the old condition
  required both sides to already be known before comparing them at
  all) -- eligibility now requires a live, non-empty configured origin
  that agrees *exactly* with **both** of the two independent immutable
  declared sources this repository records for it (`.gitmodules`'s own
  declared `url`, and the separate `docs/release_data/provenance/
  submodules.json` record's own `url`) -- a missing declaration in
  *either* immutable source, or a mismatch against *either* of them, is
  equally non-eligible, never only checked "when known". Every
  underlying `git status`/`git config`/`git cat-file` command is itself
  required to actually *succeed*, beyond its own pass/fail semantics
  above -- a genuine command/tooling failure (as opposed to an ordinary
  not-clean/no-origin-set/object-absent outcome) is caught and reported
  as its own actionable, non-eligible finding, never silently swallowed
  into a false pass. This never fetches, initializes, or approves
  anything -- `evaluate_rebuild_eligibility()` only ever *reads* `git
  submodule status`, `docs/release_data/provenance/submodules.json`,
  and (once initialized) the submodule's own `git status`/`git config`/
  `git cat-file`. **This is this repository's real, current, expected
  state.** A non-git `repo_root` (a genuine extracted archive/non-git
  candidate tree, see above) is unconditionally `"blocked"` too, for a
  distinct, precisely reported reason -- `evaluate_rebuild_eligibility()`
  never invokes `git submodule status` (or any other git command)
  against such a tree at all.
* **`"not_run"`** -- eligible, but no actual build was attempted (the
  caller passed `attempt_build=False`, or omitted an explicit
  `--build-command`/`--output-paths` for the real pinned rebuild). Kept
  strictly distinct from `"blocked"` so a report can never conflate "we
  refused to even try" with "we tried and it worked".
* **`"failed"`** -- a build was actually attempted
  (`run_build_twice_from_immutable_source()`) and either run exited
  non-zero, a declared output was missing, the two runs' output hashes
  disagreed, or either run's own independent input materialization was
  mutated during the build.
* **`"verified_success"`** -- both runs actually executed -- each from
  its own independent, immutable-`target_sha`-bound materialization, in
  its own separate temp/build directory, with neither run's input tree
  mutated during the build -- both exited `0`, and every declared output
  was present and byte-identical.

**Independent immutable rebuild materialization (issue #9 mandatory
correction #7).** `run_build_twice_from_immutable_source()` is what
actually produces `"verified_success"` now -- never a build copied twice
from the same, potentially-mutable live worktree. For each of the two
runs, it:

1. materializes a completely separate, fresh source tree via `git
   archive <target_sha> | tar -x` (`materialize_immutable_source_tree()`)
   -- an independent extraction bound to the exact same immutable commit,
   never a copy of the live worktree (which could have been edited after
   `target_sha` was resolved, and is never read for this purpose at all);
2. places any already-eligibility-verified submodule content `git
   archive` itself never includes into that same independent
   materialization (`_materialize_verified_submodule_content()` -- the
   one, narrow, explicitly-gated exception; see the "GitHub
   auto-generated source archive contradiction" below). **Guardian-
   correction remediation (D3):** this materializes the submodule's own
   content via a *second*, independent `git archive <pinned_commit>`
   extraction -- run *inside the submodule's own repository* -- never a
   `shutil.copytree` of the submodule's live worktree directory. The
   previous version of this function (`_copy_verified_submodule_
   content()`) did copy that live directory; since `evaluate_rebuild_
   eligibility()`'s pinned-commit match only proves the submodule's HEAD
   *commit* agrees with the pin, not that its *worktree bytes* are
   unmodified, a dirty-but-commit-matching submodule checkout could have
   had its locally-modified/staged/untracked bytes copied straight into
   both "independent" runs. `evaluate_rebuild_eligibility()` now also
   requires the submodule's own worktree/index to be genuinely clean
   before eligibility is ever granted (see above) -- but this
   materializer is independent, defense-in-depth: it never reads the
   submodule's worktree at all, so a future eligibility-gate bug alone
   could not resurrect this defect;
3. snapshots every file in that materialization (`_hash_tree_snapshot()`)
   *before* running `build_command` in it, via `subprocess.run` with a
   small, explicit, controlled environment (`_controlled_build_environment()`
   -- fixed `LANG`/`LC_ALL`/`TZ`/private `HOME`, never a blind passthrough
   of this process's own full ambient environment);
4. verifies every one of those originally-materialized files is still
   present and byte-identical *after* the build runs
   (`_verify_input_tree_unchanged()`) -- a build script that mutates or
   deletes any of its own declared input files (instead of only ever
   writing new, genuinely separate output paths) is reported as a
   failure, never silently `"match": True`;
5. hashes every declared output path, and (issue #9 mandatory
   correction #2) attempts to locate and parse an embedded
   `ExpansionMetadata` record (`scripts/modernize/verify_rom_header.py`)
   in each declared output; whenever one is actually present, its
   `build_commit` field is verified against this exact `target_sha` --
   **for both independent runs**. This is strictly stronger than "the
   two runs' hashes matched each other": a build script that ignores its
   own build-identity input and hardcodes a stale value would still
   produce two byte-identical (and therefore superficially "matching")
   runs, but would never be correctly bound to `target_sha` -- exactly
   the gap this closes. An output with no embedded record at all (e.g.
   a synthetic test fixture's own plain-bytes output, or a non-ROM
   artifact) is never itself treated as a failure; only a *present but
   wrong* record is, and it demotes the overall result from
   `"verified_success"` to `"failed"` with an explicit, actionable
   `"embedded_metadata_mismatches"` reason (never silently absorbed into
   a generic hash-mismatch message).

**Mandatory `EXPANSION_BUILD_ID` binding (issue #9 mandatory correction).**
Every one of the two runs' materializations is a fresh `git archive
<target_sha> | tar -x` extraction -- which, by construction, never
carries `.git` metadata. `scripts/modernize/expansion_config.py`'s own
`resolve_build_commit()` falls back to the fixed sentinel `"unknown"` for
exactly this shape of tree unless an explicit override is supplied.
`_controlled_build_environment()` therefore *always* sets
`EXPANSION_BUILD_ID=<target_sha>` (the full 40-lowercase-hex commit) in
both runs' build environment -- passed as a real environment variable to
a `subprocess.run(..., shell=False)` argv list, never interpolated into
a shell string -- so a real build's own embedded identity is correctly
bound instead of silently degrading to `"unknown"`.

**Output-path safety (issue #9 verifier remediation).** Every declared
output path is validated (`_validate_output_relpath()`) both before and
immediately after the build executes (the build script itself is
untrusted and could plant a symlink among its own declared outputs that
did not exist before it ran): an absolute path, a `..` traversal
component, or a path that -- once any symlink components are resolved
(`os.path.realpath`) -- would resolve outside that run's own
materialization root is refused outright with an actionable
`ArchiveRehearsalError`, before that path is ever read. The two runs'
resolved real output paths are additionally cross-checked against one
another so an output can never be aliased/shared/reused across the two
independent runs.

**The committed, locked, public rebuild profile (issue #9 mandatory
correction #3).** `DEFAULT_REBUILD_BUILD_COMMAND`/`DEFAULT_REBUILD_
OUTPUT_RELPATHS` (and the parameterized `build_default_rebuild_
profile(config, abi, rom_size)`, which mirrors the exact same shape
using `cli.py`'s own already-existing `--config`/`--abi`/`--rom-size`
knobs) are the one, safe, public, documented, deterministic interface a
future eligible candidate's rebuild rehearsal actually executes
through -- a plain argv list (`["make", "-j1", "MODERN_CONFIG=...",
"MODERN_ABI=...", "MODERN_ROM_SIZE=...", "expansion-modern-rom"]`,
`shell=False`, never a shell string) naming this repository's own real,
already-existing `make`/`modern.mk` targets, and a plain relative output
path list (`fireemblem8.elf`/`fireemblem8.gba` under `build/expansion-
modern/<config>/<abi>/`). `cli.py`'s `cmd_rehearse` wires this in and
executes it **exactly once** (never a second, redundant real build --
see `precomputed_rebuild_report` below); `rebuild_rehearsal_blocker()`
itself still short-circuits to `"blocked"` before ever reading a single
byte of this profile whenever `mgfembp`'s provenance remains unapproved
(today, and until a human resolves it), so wiring this in cannot itself
cause any fetch/build of `mgfembp` while this repository remains
BLOCKED.

**Single source of truth for the rehearsal's own rebuild result.** A
fresh review found that `cli.py`'s `cmd_rehearse` previously computed
its own, separate `rebuild_rehearsal_blocker()` call (with no
`build_command` at all -- always reporting the eligibility-only result)
for the JSON it printed, while `build_manifest()` *internally* computed
a second, independent, always-`attempt_build=False` rebuild check for
its own `"status"`/`"reasons"` computation -- so even a real, executed,
successful double build would never have been able to flip the overall
candidate status, because the status computation was never looking at
its result at all. `build_manifest()` now accepts an optional
`precomputed_rebuild_report` -- when given, it is used as-is (never
re-invoking `rebuild_rehearsal_blocker()` a second time). `cmd_rehearse`
computes the real rebuild result **once**, extracts its own verified
`embedded_short_sha` from it (see "Mandatory embedded short-SHA binding"
below), and threads both into the same `build_manifest()` call -- so the
printed `"rebuild"` report and the overall `"status"`/`"reasons"` are
always the exact same computation, never two independently-resolved
values that could theoretically disagree.

The two runs can never share a source or build directory: each is rooted
at its own `tempfile.mkdtemp()` path, and an explicit guard rejects the
(otherwise-impossible) case of both runs resolving to the same directory
rather than silently trusting that they never could.
`scripts/release_rehearsal/tests/test_archive_rehearsal.py`'s
`RunBuildTwiceFromImmutableSourceTests` exercises the lower-level
mechanism directly (deterministic match, nondeterministic mismatch, a
failing build, a missing declared output, a build that mutates or
deletes its own input reported as a failure, live-worktree edits after
SHA resolution never affecting the build, and -- via dependency
injection -- the shared-directory guard actually firing).

**Guardian-correction remediation (D1): the real, wired end-to-end
proof is `RebuildRehearsalBlockerEndToEndBuildTests`.** A fresh,
independent review found this document, and the closure-candidate
report, previously claimed that a test named `test_hermetic_eligible_
rebuild_runs_twice_and_verifies_success` drove `rebuild_rehearsal_
blocker()` itself, end-to-end, to `"verified_success"` -- that claim was
false: the named test only ever called the legacy, copy-based
`run_build_twice()` helper directly (never `rebuild_rehearsal_blocker()`
at all), and asserted nothing about the manifest-facing `"status"`
value. `run_build_twice()` was never wired into `rebuild_rehearsal_
blocker()`/the release manifest's status computation in the first place
(only `run_build_twice_from_immutable_source()` ever was) -- so this was
purely a documentation/evidence defect, not a live status defect -- but
it is corrected here and the misleading legacy function has been deleted
outright (see below) so it can never be misattributed again.
`RebuildRehearsalBlockerEndToEndBuildTests` (`scripts/release_rehearsal/
tests/test_archive_rehearsal.py`) is the real, corrected replacement: it
constructs a fully synthetic, fully eligible (initialized/approved/
identity-matched/clean-submodule-worktree/URL-matched/pinned-object-
accessible -- see "Submodule dirty-worktree/URL/accessible-object
guards" below) submodule fixture and calls `rebuild_rehearsal_blocker()`
**itself** (never a lower-level function in isolation) with a real,
hermetic `build_command`, directly asserting:

* `"status"` is exactly `REBUILD_STATUS_VERIFIED_SUCCESS` for the
  matching-output case, and exactly `REBUILD_STATUS_FAILED` for a
  nondeterministic-output mismatch, a non-zero exit, a missing declared
  output, and a build that mutates its own declared input (the literal
  "source mutation" case);
* the two runs' own independent materialization roots
  (`build_result["materialization_root1"/"materialization_root2"]`) are
  directly observed to be distinct, never merely assumed;
* both runs' input-tree mutation-problem lists are empty for the
  success case (`input_tree_mutation_problems1`/`2`);
* the declared output's hash matches a hand-computed expectation built
  from both the superproject's own tracked content *and* the pinned-
  commit-bound submodule content, proving real bytes from both
  independent immutable sources actually flowed into the build; and
* the shared-directory refusal (`ArchiveRehearsalError`) fires through
  `rebuild_rehearsal_blocker()` itself, not only the lower-level
  function.

**The legacy, copy-based `run_build_twice()` has been deleted outright**
(not merely deprecated) -- it was never wired into `rebuild_rehearsal_
blocker()`/the release manifest's status computation, and keeping a
copy-of-a-mutable-directory helper around risked exactly the same
misattribution a future doc/test change could reintroduce. No test or
document may name it as, or use it to demonstrate, the eligible/
`"verified_success"` path any more -- there is no such function left to
call. The manifest's overall `"status"` is never `"mechanically
eligible"` while this reports anything other than `"verified_success"`
(see "Release manifest and identity checks" above).

Also explicitly documents, in both the report JSON and this document, the
**GitHub auto-generated source archive contradiction**: GitHub's
"Source code (zip/tar.gz)" archives are generated from the tree alone
and never include submodule contents, so that archive can never be this
repository's supported, complete source artifact while `mgfembp` is a
submodule.

## Immutable Actions pin inventory

Every external `uses:` reference in `.github/workflows/release-rehearsal.yml`
is pinned to an exact, immutable **40-lowercase-hex commit SHA** -- never a
version tag (not even a major-version tag like `v7`), a branch name, or a
short/malformed/wrong-case SHA. `scripts/release_rehearsal/workflow_guard.py`'s
`check_uses_pins()` mechanically enforces this for **every** external
action the workflow references, not merely `actions/checkout` -- a single,
explicit, narrow exemption (`is_local_action_reference()`) allows a
`./`-prefixed (or `../`-prefixed) local, in-repository action, which is
implicitly pinned to the workflow file's own commit and has no separate
external SHA to record.

A pin's mere *shape* being a well-formed 40-hex string says nothing about
*which* upstream release it actually corresponds to. That fact is
recorded separately, as committed, machine-readable evidence, in
`docs/release_data/action_pins.json`: for every external action pinned in
the workflow, the exact action repository, the pinned commit SHA, the
human-readable upstream version (e.g. `v7.0.1`) that SHA corresponds to,
the official source URL/reference, the exact read-only verification
method used to establish the correspondence (a `git ls-remote --tags`
lookup against the official action repository, cross-checked against that
repository's own published release metadata -- never a `git fetch`/
`clone` of the upstream action repository, never an authenticated/
mutating GitHub API call), the date verified, and the update procedure a
future maintainer follows to move the pin forward.
`scripts/release_rehearsal/action_pins.py`'s `check()` cross-checks the
real workflow file against this inventory in both directions: a workflow
pin with no matching inventory row, an inventory row whose `pinned_sha`
disagrees with what the workflow actually pins, and a stale inventory row
left behind for an action no longer referenced are all reported.

**This inventory is documentation/evidence only -- it is never itself an
authorization.** `make release-workflow-guard` (via
`scripts/release_rehearsal/cli.py`'s `workflow-guard` subcommand) folds
both the generalized pin-format check and the inventory cross-check into
one JSON report and exit-code contract; `make release-action-pins-check`
additionally runs `scripts/release_rehearsal/action_pins.py` standalone,
directly against the real workflow and inventory. Passing either is
necessary, but never sufficient, for eligibility -- exactly like every
other guard in this system (see "Workflow guard is advisory, never
authorization" below).

## Workflow and Make integration

`.github/workflows/release-rehearsal.yml` triggers on `pull_request` and
`workflow_dispatch` only, declares top-level `permissions: contents:
read`, checks out with `persist-credentials: false`, uses no secrets, and
never uploads an artifact or mutates a tag/release/comment/protected
environment (only a job summary, which is explicitly allowed). Its own
permission/safety contract is itself mechanically checked by
`scripts/release_rehearsal/workflow_guard.py` (via `make
release-workflow-guard`, using the CLI's dynamic-JSON `workflow-guard`
subcommand -- not a bare script invocation), run as a step inside the
workflow. A dedicated step additionally runs `make
release-check-expect-blocked` to **mechanically assert** the current
expected status is `blocked`, rather than relying on `make
release-check`'s always-exit-`0` prose. Two further standalone
regression-guard steps run `make release-epoch-claims-check` (stale
current-epoch claims) and `make release-stale-count-claims-check` (stale
aggregate test-count claims) -- both are already folded into every
`release-check`/`release-rehearse` report too (`"epoch_claims"`/
`"stale_count_claims"`), so these steps are redundant-but-fast standalone
confirmations, not the only place either is checked. Every publication-
eligibility step in this job runs under a job-level `env:
RELEASE_TARGET_SHA: ${{ github.sha }}` (see "Release manifest and
identity checks" above), mechanically cross-checked by
`workflow_guard.check_release_target_sha_binding()`. The job summary
(`$GITHUB_STEP_SUMMARY`) is rendered **dynamically** from
`scripts.release_rehearsal.cli summary`'s own canonical JSON (stdlib
`json`, no prose parsing) -- see `render_markdown_summary()` and
`scripts/release_rehearsal/tests/test_cli.py`'s
`RenderMarkdownSummaryTests`, which prove this with a **synthetic**
`"mechanically eligible"` report dict (this real repository's own status
alone could never prove the eligible branch is not secretly hardcoded).
If a future, separately-authorized change ever makes the candidate
`"mechanically eligible"`, the summary renders that truthfully with no
workflow edit required.

### Workflow guard is advisory, never authorization

`workflow_guard.py`/`action_pins.py` (together, "the workflow guard")
mechanically prove this workflow's own permission/network/safety
contract is intact, and that its Action pins are exact and documented.
That is **necessary, but never sufficient**, for anything: passing the
workflow guard is a self-check *of the CI workflow file itself* -- it
says nothing about license/provenance approval, submodule redistribution
approval, rebuild verification, or (see "External attestation is outside
candidate control" above) the separate, protected external human
attestation real publication additionally requires. A clean
`workflow-guard`/`action_pins` result is exactly one advisory,
defense-in-depth signal among many in this system, never itself an
authorization to publish, and never folded into the overall
`"mechanically eligible"`/`"blocked"` candidate status computed by
`manifest.py` (it is deliberately a separate, standalone check --
`make release-workflow-guard`/`make release-action-pins-check` --
reported on its own 0/1/2 exit contract, not inside `make release-check`).
Protected external review -- not this repository's own tooling -- owns
approval and final publication status.

Make targets (`release.mk`, included from the top-level `Makefile`):

* `make release-test` -- runs the stdlib test suites for
  `scripts/release_rehearsal/` and `scripts/modernize/migrations/`.
* `make release-migrations-check` -- runs the migration registry's
  `check` (always expected to pass on a well-formed registry).
* `make release-rehearse` -- the deterministic double-archive-build +
  rebuild-blocker rehearsal, folding in the current provenance/
  source-guard/allowlist/version-ledger findings. Always exits `0` for a
  well-formed report (see "Exit code contract" above).
* `make release-check` -- the full release-manifest eligibility check.
  Always exits `0` for a well-formed report.
* `make release-check-require-eligible` / `make
  release-rehearse-require-eligible` -- the machine-distinct
  publication-eligibility gates (`cli ... --require-eligible`).
  **The underlying CLI is intentionally expected to, and currently does,
  exit non-zero (`1`, `EXIT_NOT_ELIGIBLE`) while the candidate is
  `blocked`. `make` itself, however, reports *any* failed recipe as exit
  `2` -- not the recipe's own code -- so running these specific targets
  through `make` (rather than invoking
  `python3 -m scripts.release_rehearsal.cli check --require-eligible`
  directly) currently and correctly exits `2`, never `1`; this is GNU
  Make's own universal recipe-failure convention, not a defect in this
  Makefile.**
* `make release-check-expect-blocked` / `make
  release-rehearse-expect-blocked` -- the complementary expected-status
  health-check targets (`cli ... --expect-status blocked`); the
  underlying CLI exits `0` only while truly `blocked`, and exits `3`
  (`EXIT_STATUS_MISMATCH`) the moment that ever stops being true. Through
  `make`, the healthy (still-`blocked`) case is exit `0` exactly as the
  CLI reports; the moment that ever stops being true, `make` itself
  reports exit `2` (never `3`), for the identical GNU-Make-recipe-failure
  reason as the paragraph above.
* `make release-workflow-guard` -- the dynamic machine-JSON workflow
  guard invocation.

None of these targets are wired into `all`, `expansion-modern-*`, or any
existing host/build/generated/upstream/default/runtime gate; they are
fully standalone, exactly like `generated-data-check`
(`generated_data.mk`) and the upstream-port tooling before them.

## Closure-candidate report

See [`docs/release_closure_candidate.md`](release_closure_candidate.md)
for the evidence bundle a maintainer reviews before deciding what (if
anything) to do next with issue #9. That report is explicit that it is
**not** a closure of issue #9 and does not claim publication readiness.
