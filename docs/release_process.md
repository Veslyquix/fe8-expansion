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
| Exact source allowlist | `scripts/release_rehearsal/allowlist.py`, `docs/release_data/source_allowlist.json` | Exact, deterministic, generated **per-member** (per tracked file, plus the single `mgfembp` gitlink) allowlist -- no directory-level/prefix grant. `check_allowlist_completeness()` fails actionably the moment a tracked file and the checked-in allowlist ever disagree in either direction. |
| Source-release guard | `scripts/release_rehearsal/source_guard.py`, `docs/release_data/map_hex_exceptions.json` | Recursive hard-deny rules (path/extension **and** file-magic) for a release candidate tree/archive, including default-deny `.map`/`.hex` with an exact, factual, file-level exception list. Separate from, and does not modify, `scripts/artifact_guard.py`. |
| Immutable Git-object source | `scripts/release_rehearsal/git_source.py` | `git ls-tree`/`git cat-file --batch` plumbing wrappers so archive content is always read from an immutable commit object, never the mutable worktree/index. |
| Archive/rebuild rehearsal | `scripts/release_rehearsal/archive_rehearsal.py` | Deterministic double-build archive hash comparison (git-blob-bound); rebuild-eligibility evaluation plus (when eligible) an actually-executed double-compile-and-compare, with four machine-distinct states (`not_run`/`blocked`/`failed`/`verified_success`). |
| Release-doc link validator | `scripts/release_rehearsal/doc_links.py` | Verifies every relative Markdown link in the release-process doc set resolves to a real file. |
| Workflow guard | `scripts/release_rehearsal/workflow_guard.py` | Validates `.github/workflows/release-rehearsal.yml`'s own permission/safety contract: **any** permission scope (`contents`, `id-token`, `packages`, `pull-requests`, `issues`, `actions`, `checks`, `deployments`, `statuses`, or any future scope) granted `write`, at top level/job level/nested/inline-mapping, any quoting/case/spacing, shorthand `write-all` permissions, token/secrets interpolation, network/upload/publish/deploy/release commands and actions, ref mutation, and common shell-indirection evasions (line continuations, `eval`, `base64 -d`, `sh -c`/`bash -c`, command-position shell-variable/fragment assembly -- including inside a `$( ... )` command substitution *or* a legacy backtick command substitution, and including every variable tracked from a prior `export NAME=value` or `read`/`read -r NAME` statement (every name a multi-variable `read A B` populates, not only the first), not only a plain `NAME=value` assignment -- plus outright rejection of shell process substitution (`<(...)`/`>(...)`, unused by the real workflow)). |
| CLI / Make targets | `scripts/release_rehearsal/cli.py`, `release.mk` | `make release-check`, `make release-rehearse`, `make release-migrations-check`, plus the machine-distinct `*-require-eligible`/`*-expect-blocked` gate targets and `release-workflow-guard`/dynamic `cli summary`. |
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
  `"unknown"`;
* a **short-form derivation** (`target_sha[:8]`) matching
  `scripts/modernize/save_format_tool.py`'s own
  `ExpansionSaveMeta.buildCommitShort` derivation
  (`build_commit[:8]`), so an embedded short-form value can be verified
  against the full target SHA while the manifest/evidence always retains
  the full 40-character SHA;
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

## Exact per-member source allowlist and provenance coverage

`docs/release_data/source_allowlist.json` is **not** a top-level-directory
grant any more. It is an exact, deterministic, generated list of every
single tracked file's repo-relative path, plus the single `mgfembp`
gitlink path -- generated and validated by
`scripts/release_rehearsal/allowlist.py` directly from Git's own tree
listing (`git ls-tree -r`), never hand-maintained. A brand-new tracked
file with no corresponding entry is an actionable `make release-check`
failure (`check_allowlist_completeness`'s "missing" list), not a silent
gap; a stale entry for a file that no longer exists is equally reported
("stale" list) so the allowlist can never quietly drift out of sync with
reality in either direction. Regenerate it with:

```sh
python3 -m scripts.release_rehearsal.allowlist generate --target-sha HEAD --write
```

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
`category`/`notes` out to every exact allowlisted path nested under (or
equal to) it, preserving every already-recorded fact
(`author`/`rightsholder`/`license` stay `"NOASSERTION"`,
`redistribution_approved` stays `false`, `reviewer` stays absent/`null`;
`mgfembp`'s exact path and its
`c87e74dcd6c8878b809e013cd8ff0c52baa75332` pin are unchanged) -- it never
invents a new fact for any path, however it was assigned a root. This
directory-prefix fan-out is **exclusively a generator-time convenience**;
it plays no role in, and is never invoked by, the runtime `check`/
`evaluate_coverage` validation path, which only ever reads whatever exact
records are actually committed to disk. Regenerate (after adding a new
root to `PROVENANCE_ROOT_SEED` for a genuinely new top-level location, or
whenever the allowlist changes) with:

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
  commit. This never fetches, initializes, or approves anything --
  `evaluate_rebuild_eligibility()` only ever *reads* `git submodule
  status` and `docs/release_data/provenance/submodules.json`. **This is
  this repository's real, current, expected state.** A non-git
  `repo_root` (a genuine extracted archive/non-git candidate tree, see
  above) is unconditionally `"blocked"` too, for a distinct, precisely
  reported reason -- `evaluate_rebuild_eligibility()` never invokes `git
  submodule status` (or any other git command) against such a tree at
  all.
* **`"not_run"`** -- eligible, but no actual build was attempted (the
  caller passed `attempt_build=False`, or omitted an explicit
  `--build-command`/`--output-paths` for the real pinned rebuild). Kept
  strictly distinct from `"blocked"` so a report can never conflate "we
  refused to even try" with "we tried and it worked".
* **`"failed"`** -- a build was actually attempted
  (`run_build_twice()`) and either run exited non-zero, a declared output
  was missing, or the two runs' output hashes disagreed.
* **`"verified_success"`** -- both runs actually executed, both exited
  `0`, and every declared output was present and byte-identical.

`run_build_twice()` is the actual, executable "run a build command twice
and hash its outputs" mechanism -- never a mocked boolean: each run copies
the source into its own fresh temporary directory and invokes the given
command via `subprocess.run`.
`scripts/release_rehearsal/tests/test_archive_rehearsal.py`'s
`RunBuildTwiceTests` exercise this directly with real (trivial,
hermetic, synthetic) build commands, proving both the match and the
mismatch/failure paths genuinely execute; `RebuildRehearsalBlockerTests`
additionally construct a fully synthetic eligible (initialized/approved/
identity-matched) submodule fixture and run the pinned double-build path
against it end-to-end. The manifest's overall `"status"` is never
`"mechanically eligible"` while this reports anything other than
`"verified_success"` (see "Release manifest and identity checks" above).

Also explicitly documents, in both the report JSON and this document, the
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
`scripts/release_rehearsal/workflow_guard.py` (via `make
release-workflow-guard`, using the CLI's dynamic-JSON `workflow-guard`
subcommand -- not a bare script invocation), run as a step inside the
workflow. A dedicated step additionally runs `make
release-check-expect-blocked` to **mechanically assert** the current
expected status is `blocked`, rather than relying on `make
release-check`'s always-exit-`0` prose. The job summary
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
