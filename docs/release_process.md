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
   [`docs/release_data/provenance/*.json`](release/provenance/) (currently every
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
| Release manifest | `scripts/release_rehearsal/manifest.py` | Ties together `config.mk` SemVer, embedded C metadata, a candidate tag string, changelog, docs, save format/migrations, and previous/next supported versions into one report. |
| Migration registry | `scripts/modernize/migrations/registry.py` | Declares mechanical vs. manual save-format epoch transitions; see [`docs/migration_registry.md`](migration_registry.md). |
| Provenance manifests | `scripts/release_rehearsal/provenance.py`, `docs/release_data/provenance/*.json` | Factual, hand-seeded code/asset/submodule provenance records. |
| Source-release guard | `scripts/release_rehearsal/source_guard.py`, `docs/release_data/source_allowlist.json` | Exact top-level allowlist + recursive hard-deny rules for a release candidate tree/archive. Separate from, and does not modify, `scripts/artifact_guard.py`. |
| Archive/rebuild rehearsal | `scripts/release_rehearsal/archive_rehearsal.py` | Deterministic double-build archive hash comparison; clean-rebuild blocker reporting. |
| Workflow guard | `scripts/release_rehearsal/workflow_guard.py` | Validates `.github/workflows/release-rehearsal.yml`'s own permission/safety contract. |
| CLI / Make targets | `scripts/release_rehearsal/cli.py`, `release.mk` | `make release-check`, `make release-rehearse`, `make release-migrations-check`. |
| CI | `.github/workflows/release-rehearsal.yml` | Runs all of the above read-only, on `pull_request`/`workflow_dispatch` only. |

## Exit code contract

This is the "documented, mechanically tested blocked/eligible contract"
referenced by issue #9's acceptance criteria:

* **Exit `0`** -- the tool ran correctly and produced a well-formed report.
  The report's own `"status"` field says either `"mechanically eligible"`
  or `"blocked"`. **Both are valid, expected, successful outcomes of a
  correctly-functioning checker** -- correctly detecting and reporting an
  unresolved legal/provenance fact is the checker doing its job, not the
  checker failing. A `"blocked"` report is never printed as, or
  confusable with, a publication success: every CLI additionally echoes
  `status: blocked` plus the exact reasons to stderr, and CI's job summary
  states the publication status in plain English.
* **Exit `2`** (`1` for the standalone guard scripts' own hard-deny
  findings) -- an **actionable defect**: a malformed changelog fragment, a
  changelog/version-impact mismatch, an invalid candidate tag, a missing
  required doc, a malformed provenance/allowlist JSON file, a migration
  registry inconsistency, a source-release guard hard-deny hit (symlink,
  device, traversal path, prohibited nested magic/extension), or an
  archive-rehearsal hash mismatch. These represent tooling/input defects
  to fix, distinct from an honestly-recorded unresolved business fact.

`make release-check` and `make release-rehearse` both exit `0` on the
current tree (a well-formed `"blocked"` report) and exit non-zero only if
a genuine defect is introduced (e.g. a stale changelog, a broken
migration registry, a hard-deny content violation, or a workflow
permission regression) -- this is intentional so this rehearsal can run in
CI as an ordinary, informative, always-green (until something is actually
broken) job without ever being misread as "ready to publish".

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
  `"unknown"`;
* a **short-form derivation** (`target_sha[:8]`) matching
  `scripts/modernize/save_format_tool.py`'s own
  `ExpansionSaveMeta.buildCommitShort` derivation
  (`build_commit[:8]`), so an embedded short-form value can be verified
  against the full target SHA while the manifest/evidence always retains
  the full 40-character SHA;
* changelog validity + aggregate declared SemVer impact;
* required-docs presence;
* save-format compatibility epoch + migration-registry consistency;
* previous/next supported versions
  (`docs/release_data/version_ledger.json`);
* provenance status (`scripts/release_rehearsal/provenance.py`);
* source-release guard status (`scripts/release_rehearsal/source_guard.py`).

The manifest's overall `"status"` is `"mechanically eligible"` only if
**every** one of those sub-checks passes; otherwise it is `"blocked"`,
with every contributing reason listed verbatim in `"reasons"`.

## Legal and provenance boundary

`docs/release_data/provenance/{code,assets,submodules}.json` record, for every
entry in `docs/release_data/source_allowlist.json`, an honestly-unresolved
`author`/`rightsholder`/`license` of `"NOASSERTION"`,
`"redistribution_approved": false`, and `"reviewer": null`. **This
repository's tooling never invents an author, rightsholder, license, or
reviewer, and never selects or adds a root `LICENSE` file** -- doing so
would be a legal claim this repository has no authority to make on its
own. The `mgfembp` git submodule is separately pinned in
`docs/release_data/provenance/submodules.json` to the exact commit
`c87e74dcd6c8878b809e013cd8ff0c52baa75332` (matching this worktree's
gitlink) and is, and remains, `redistribution_approved: false`.

`scripts/release_rehearsal/provenance.py evaluate()` is `"blocked"` whenever any
entry has `NOASSERTION`, `redistribution_approved: false`, or no
`reviewer` -- which is every entry, today. Resolving this is a human legal
decision; no amount of running this tooling changes that.

## Source-release guard

`scripts/release_rehearsal/source_guard.py` is intentionally **separate from, and
does not modify or weaken**, `scripts/artifact_guard.py` (which continues
to review ordinary tracked-Git content per
[`docs/issue-resolution-policy.md`](issue-resolution-policy.md)). It
instead governs an actual *release candidate tree or archive*:

* an **exact top-level allowlist**
  (`docs/release_data/source_allowlist.json`), seeded from this worktree's
  tracked top-level entries plus the new entries issue #9 itself
  introduces (`CHANGELOG.md`, `changelog_fragments/`, `release.mk`);
* recursive hard-deny rules for prohibited nested files/magic bytes
  (mirroring, independently, `scripts/artifact_guard.py`'s prohibited
  extension/magic/path-segment classes), absolute or `..`-traversal
  paths, unsafe archive member names (NUL bytes, backslashes, empty
  components), symlinks, hardlinks (`st_nlink > 1`), and devices/FIFOs/
  sockets -- for both a real filesystem tree (`scan_tree`) and a tar
  archive's members without ever extracting them to disk
  (`scan_archive_members`, using `TarFile.extractfile()` for read-only
  content access only, never `TarFile.extractall()`).

`scan_source_release_candidate()` is what `manifest.py`'s source_guard
check (and therefore `make release-check`/`make release-rehearse`)
actually calls. It picks the right check for what `root` *is*: a genuine
extracted archive/other non-git candidate tree (the tree *is* the
release candidate) still gets the full fail-closed `scan_tree(...,
closed_world=True)` check above -- every top-level entry must equal the
allowlist, everything is walked. A **live git development worktree** is
not that: it routinely accumulates gitignored/untracked build byproducts
(`.dep/` dependency output, a built ROM/ELF, host tool binaries, stale
`build/` output, etc.) that were never going to ship. For a worktree,
`scan_source_release_candidate()` instead evaluates exactly the
git-tracked-intersect-allowlist candidate set
(`git_tracked_allowlisted_files()`) that
`scripts/release_rehearsal/archive_rehearsal.py` itself would archive,
running every hard-deny rule above against that exact set -- so the
report is deterministic and independent of what happens to be lying
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
  exception -- nothing is ever left on disk, nothing is ever uploaded;
* separately attempts a **clean recursive rebuild** rehearsal
  (`rebuild_rehearsal_blocker()`): checks `git submodule status` for
  `mgfembp` and reports the **precise** blocker (uninitialized submodule
  content it deliberately does not fetch, plus the still-unresolved
  provenance approval) rather than silently skipping or fetching
  unreviewed content over the network;
* explicitly documents, in both the report JSON and this document, the
  **GitHub auto-generated source archive contradiction**: GitHub's
  "Source code (zip/tar.gz)" archives are generated from the tree alone
  and never include submodule contents, so that archive can never be this
  repository's supported, complete source artifact while `mgfembp` is a
  submodule.

## Workflow and Make integration

`.github/workflows/release-rehearsal.yml` triggers on `pull_request` and
`workflow_dispatch` only, declares top-level `permissions: contents:
read`, checks out with `persist-credentials: false`, uses no secrets, and
never uploads an artifact or mutates a tag/release/comment/protected
environment (only a job summary, which is explicitly allowed). Its own
permission/safety contract is itself mechanically checked by
`scripts/release_rehearsal/workflow_guard.py`, run as a step inside the workflow.

Make targets (`release.mk`, included from the top-level `Makefile`):

* `make release-test` -- runs the stdlib test suites for
  `scripts/release_rehearsal/` and `scripts/modernize/migrations/`.
* `make release-migrations-check` -- runs the migration registry's
  `check` (always expected to pass on a well-formed registry).
* `make release-rehearse` -- the deterministic double-archive-build +
  rebuild-blocker rehearsal, folding in the current provenance/
  source-guard findings.
* `make release-check` -- the full release-manifest eligibility check.

None of these targets are wired into `all`, `expansion-modern-*`, or any
existing host/build/generated/upstream/default/runtime gate; they are
fully standalone, exactly like `generated-data-check`
(`generated_data.mk`) and the upstream-port tooling before them.

## Closure-candidate report

See [`docs/release_closure_candidate.md`](release_closure_candidate.md)
for the evidence bundle a maintainer reviews before deciding what (if
anything) to do next with issue #9. That report is explicit that it is
**not** a closure of issue #9 and does not claim publication readiness.
