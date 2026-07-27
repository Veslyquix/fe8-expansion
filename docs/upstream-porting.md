# Canonical upstream porting (Issue #12)

This document describes the read-only-by-default tooling under
`scripts/upstream_port/` that helps a human maintainer track drift against
the canonical upstream decomp repository, classify unreviewed commits, and
explicitly select, review, and manually apply upstream patches.

**Nothing in this tool automatically cherry-picks, applies, merges, commits,
branches, or pushes anything. It never fetches unless you explicitly ask it
to. It never executes upstream code.** Every mutating action is a distinct,
explicit subcommand documented below.

## Canonical upstream

- Canonical URL (pinned, hardcoded): `https://github.com/laqieer/fireemblem8u.git`
- Reusable remote name (default, matches existing maintainer clones): `decomp`
- The tool refuses to fetch through any remote whose configured URL does not
  match the pinned canonical URL exactly.

## State/manifest

Persistent, committed state lives in `config/upstream-port-state.json`
(schema-versioned JSON, sorted keys, stable formatting so diffs are
reviewable). It records:

- `canonical_upstream_url`, `remote_name`
- `last_scanned` — `{ref, sha}` of the last human-reviewed scan boundary
- `last_ported` — `{ref, sha}` of the last fully-accounted-for integration
  boundary (every commit up to this SHA is `ported`/`skipped`/`superseded`)
- `commits` — map of full 40-hex SHA → `{status, author_name, author_email,
  subject, rationale, validation_evidence, updated_at}`

Status values: `pending`, `ported`, `skipped`, `superseded`, `conflict`.

**Strict commit-record schema (enforced at `load_state` time, before any
dependent command produces output, scans git, or writes a file):** every
`commits[sha]` record must have *exactly* the seven fields above — no
missing, no extra (a record must not, for instance, carry its own redundant
`sha` field; the map key already is the SHA) — all seven typed as strings,
`status` one of the five legal values, and `author_name`/`author_email`/
`subject`/`updated_at` non-empty (author_email must look like an email;
`updated_at` must match `YYYY-MM-DDTHH:MM:SSZ`). `ported`/`skipped`/
`superseded`/`conflict` additionally require non-empty `rationale` and
`validation_evidence`; `pending` still requires every field to be present
and correctly typed, but `rationale`/`validation_evidence` may be empty
strings. A malformed record anywhere in `commits` fails the whole
`load_state` call — see `state._validate_commit_record` — so a forged or
hand-edited "evidence" gap is caught before it can be mistaken for a real
review decision.

Only the explicit `update-state` subcommand ever writes this file. `scan`,
`drift`, and `report` are read-only and never touch it.

## Workflow

### 0. (Optional, explicit) Fetch the canonical remote

```sh
python3 -m scripts.upstream_port fetch --remote decomp
```

Refuses to run unless `git remote get-url decomp` equals the pinned
canonical URL. Only updates remote-tracking refs/objects — never touches
local branches, the working tree, or history. If you already have a fresh
local `decomp/*` ref (e.g. from a prior maintainer fetch), you can skip this
and go straight to `scan`.

### 1. Review: scan for unreviewed commits (read-only)

```sh
python3 -m scripts.upstream_port scan --ref decomp/master --format text
python3 -m scripts.upstream_port scan --ref decomp/master --format json \
  --output build/upstream-port/scan.json
```

Lists every commit strictly after `last_ported.sha` up to the caller-selected
local ref (`decomp/master`, `decomp/remove_tools`, a raw SHA, etc.), with:
original full SHA, author identity, subject, changed paths, a path
classification (`code`/`data`/`symbol`/`docs`/`tools`/`build`/`linker`/
`config`/`other`), and risk flags (`modern-build-divergence-risk`,
`linker-conflict-risk`, `symbol-table-conflict-risk`,
`known-fork-divergence-hotspot`) for commits touching known fork/build
hotspots (`Makefile`, `modern.mk`, `ldscript.txt`, `scripts/shiftcheck/*`,
etc.). Output is deterministically ordered (oldest-first, topological) —
never dependent on wall-clock time. A merge commit in range is classified
using the deterministic, sorted **union** of changed paths across all of
its parents (never a silently empty path list, which is what plain `git
diff-tree` would give you for a merge commit by default).

`scan`/`drift` print to **stdout by default**. `--output PATH` is only ever
honored if `PATH` passes the same write-safety contract described in
Step 3 below (repo-contained, no symlink anywhere on the path, confirmed
gitignored) — a tracked file (e.g. `README.md`), a path outside the repo
(e.g. `/tmp/scan.json`), or a symlinked path is rejected with a clear error
*before anything is opened*, and nothing is mutated.

If `last_ported` is not an ancestor of the selected ref (histories
diverged — e.g. you selected a side-topic branch that was never rebased
onto the tip you last ported from), `scan` refuses to guess and tells you to
run `drift` first.

### 2. Check for drift / stale state (read-only)

```sh
python3 -m scripts.upstream_port drift --ref decomp/master --format json
```

Reports whether the selected ref moved since the last recorded scan, whether
the state's recorded SHAs are still reachable/consistent in this clone, and
how many commits remain unreviewed. Exit codes: `0` clean, `2` drift found
(ref moved and/or unreviewed commits exist), `3` integrity problem (a
recorded SHA is unreachable, or histories have diverged) — always read-only,
suitable for CI (see the drift-scan workflow below). Same `--output`
write-safety contract as `scan` above.

### 3. Select commits and generate a review report + patches

```sh
python3 -m scripts.upstream_port report \
  --ref decomp/master \
  --sha <full-sha-1> --sha <full-sha-2> \
  --out-dir build/upstream-port/my-batch
```

- Only the **explicitly listed** SHAs get anything generated — nothing is
  auto-selected.
- Each SHA must be a full 40-hex commit SHA that already exists locally and
  is reachable from the selected ref or from any `refs/remotes/<remote>/*`
  ref; anything else is rejected with a clear error.
- **A merge commit SHA is always rejected outright** — before any output
  directory is created or any file is written. Plain `git format-patch -1
  --stdout <merge-sha>` does not honestly patch a merge commit at all: it
  silently walks past it and formats a *different*, non-merge ancestor
  commit instead (or produces nothing), which would be a dangerously
  misleading result to hand a reviewer. There is no single deterministic,
  safely hand-appliable patch this tool can produce for a merge that also
  preserves provenance, so it refuses rather than fabricate one. Select the
  merge's individual non-merge constituent commits instead, or review it
  manually (`git show <merge-sha>`, `git log --graph`) outside this tool.
  A mixed selection containing even one merge SHA is rejected wholesale —
  no partial output is ever written for the valid SHAs in the same batch.
- Output (`report.json`, `report.md`, and one `NNNN-<shortsha>.patch` per
  commit) is written only under the gitignored `build/upstream-port/` root
  (or another directory you point at), and only after that directory passes
  the full write-safety contract: it must resolve inside the repository
  root, contain no symlink anywhere on its path (an ignored directory that
  is itself a symlink — whether pointing outside the repo or to another
  location inside it — is rejected, not silently followed), and be
  confirmed ignored via `git check-ignore`. All checks run, and must pass,
  before anything is created or written.
- Patches are produced by `git format-patch --stdout` reading local objects
  only — never applied, cherry-picked, or merged — and preserve the original
  author name/email/date/subject and commit SHA in standard patch headers.

### 4. Manually review and apply

Read `report.md`, inspect each `.patch` file, and manually apply the ones you
accept (e.g. `git apply <patch>` or hand-editing) **outside this tool**. This
tool does not do this step for you.

### 5. Explicitly record your review decisions

```sh
python3 -m scripts.upstream_port update-state mark \
  --sha <full-sha> --status ported \
  --rationale "why this was ported" \
  --evidence "how you validated it (tests run, diff reviewed, etc.)"
```

Legal statuses: `pending`, `ported`, `skipped`, `superseded`, `conflict`.
`ported`/`skipped`/`superseded`/`conflict` all require non-empty `rationale`
and `evidence`. Illegal transitions (e.g. leaving a `superseded` commit
without `--force`) are rejected.

### 6. Verify the manually-applied batch

```sh
python3 -m scripts.upstream_port verify
python3 -m scripts.upstream_port verify --dry-run   # list the gate commands without running them
```

**⚠️ This builds and checks the CURRENT TRUSTED WORKTREE (your repo, after
you manually applied whatever you accepted) — it never builds, checks out,
or executes the upstream ref/tree.** It orchestrates the same gates
`.github/workflows/build.yml` runs, in the same order, fail-fast. The
workflow splits them across two jobs — a fast, host-only `host-tests` job
(textually first: no arm-none-eabi toolchain, no ROM/linker build) and the
`build` job (full modern ROM/ELF/linker) — and `verify` mirrors that exact
argv-and-order sequence across both jobs:

1. `python3 -m unittest discover -s tools/gba-playtest/tests -v`
   (issue #13: the full host-only tools/gba-playtest suite — host job,
   never rebuilds the ROM)
2. `python3 -m unittest discover -s tests/upstream_port -v`
   (issue #12/#15: the 139 pure-stdlib upstream-port review tooling tests,
   including this `verify.gates()` <-> `build.yml` mirror — host job, links
   no C and never rebuilds the ROM)
3. `python3 scripts/artifact_guard.py --revision HEAD`
4. `python3 -m unittest discover -s scripts/modernize/tests -p test_build_default_lane.py -v`
   (issue #15: bare `make`/`make all` always resolves to the modern
   release AAPCS lane)
5. `python3 -m unittest discover -s scripts/modernize/tests -p test_quickstart.py -v`
   (issue #15: quickstart.sh only reaches the archival agbcc lane via
   explicit `make legacy`/`make fireemblem8.gba`)
6. `make generated-data-check`
7. `make expansion-modern-linker-check MODERN_CONFIG=debug MODERN_ABI=aapcs`
   (aggregates the full modern debug ROM/runtime + linker suite off one
   reused object/ELF build — boot/title/new-game/debugtools-hub/timer/map/
   tools/prep/ch4-prep/combat/save-load/suspend/save-format-migration,
   budget, shift/offset, raw-pointer, relocation and cross-overlay — so the
   runtime scenarios are covered here, not re-run individually; see
   `modern.mk`'s `expansion-modern-linker-check` dependency chain)
8. `make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs`
   (release-config counterpart, incl. the release debugtools-disabled
   negative scenarios)

None of these existing gates are weakened, reordered, or skipped; the two
host-lane gates were added by the issues #11/#13 <-> #12/#15 integration and
run before the ROM build so a host-tooling regression fails in well under a
minute.

**There is no gate subset/selection flag, on the CLI or in the internal
`verify.run_gates` API.** `verify` (with or without `--dry-run`) always
runs/lists the *full*, fixed, ordered gate set above — never an
unknown-gate, partial, or zero-gate result. This is intentional: closure
evidence for a manually-applied port batch is only ever meaningful as a
full-gate outcome, so the ability to select a subset was removed rather
than merely restricted (an `--gate` flag would let a caller manufacture a
"verified" result that skipped some gates entirely). `verify --dry-run`
lists every gate command in the exact order above without running any of
them — never a filtered preview.

### 7. Advance the ported boundary

```sh
python3 -m scripts.upstream_port update-state advance-ported --ref decomp/master
```

Only succeeds if every commit between the current `last_ported.sha` and the
new one is already `ported`, `skipped`, or `superseded` — it refuses to
silently skip review of any commit in the batch. Also only moves forward
(new SHA must be a descendant of, or equal to, the current one).

**Ref-tip binding (both the explicit `--sha` and the implicit no-`--sha`
path are validated identically):**

- `record-scan --ref X [--sha Y]` — `Y` (if given) must be a full 40-hex
  SHA and must be **exactly equal** to `X`'s own resolved local tip, i.e.
  `resolve_commit_sha(X)` right now. An expansion-side commit, an
  unrelated/diverged commit, or a real-but-stale SHA that used to be `X`'s
  tip but no longer is are all rejected — `record-scan` only ever records a
  ref's *current* tip, never an arbitrary point on or off its history.
  Omitting `--sha` uses that same resolved tip directly (there is no
  looser implicit path).
- `advance-ported --ref X [--sha Y]` — the candidate (`Y`, or the resolved
  tip of `X` if omitted) must lie inside the ancestry corridor bounded by
  the **current** `last_ported.sha` on one end and `X`'s resolved tip on
  the other: a descendant-of-or-equal-to the current boundary, **and** an
  ancestor-of-or-equal-to the resolved ref tip. Both ends are checked —
  not just old-boundary ancestry, which is what let an expansion-side
  commit (itself a genuine descendant of the old boundary, since it shares
  that ancestor) slip through before this fix. A commit only reachable via
  a diverged/forked branch, or one that comes *after* the resolved ref tip,
  is rejected the same way. A legitimate **intermediate** upstream commit
  (not necessarily `X`'s exact tip) is still accepted as a valid partial
  batch boundary, provided every commit up to it is already accounted for.

All of the above validation happens — including missing/unreachable local
objects being reported as an actionable error — **before** `state.json` is
ever written, so a rejected call leaves the file byte-for-byte unchanged.

Separately, `update-state record-scan --ref decomp/master` lets you
explicitly advance `last_scanned` once you've reviewed a scan's output (also
forward-only, and ref-tip-bound as described above).

## Path classification categories

`code`, `data`, `symbol`, `docs`, `tools`, `build`, `linker`, `config`,
`other` — see `scripts/upstream_port/classify.py` for the exact, ordered
pattern rules (first match wins, purely a function of the path string, no
git calls).

## Safety boundaries (what this tool will never do)

- Never fetches by default; `fetch` is the only network-touching subcommand
  and it validates the remote URL first.
- Never applies, cherry-picks, merges, commits, branches, or pushes.
- Never executes, imports, builds, or tests upstream source.
- Never writes `report`/`patch` output, or a `scan`/`drift --output` file,
  anywhere that fails the shared write-safety contract
  (`output_safety.validate_output_target`, used by every write path in this
  package): the resolved target must be contained inside the repository
  root, must not pass through a symlink anywhere on its path (regardless of
  whether that symlink points inside or outside the repo), and must be
  confirmed ignored via `git check-ignore`. A tracked file (e.g.
  `README.md`) is always rejected, unchanged, before anything is opened.
- Never generates a patch for a SHA that wasn't explicitly selected, and
  never generates one for a merge commit SHA even if explicitly selected —
  see Step 3 above for why.
- For a merge commit, `scan`/classification always report the
  deterministic, sorted **union** of changed paths across all of its
  parents — never a silently empty path list.
- Never mutates `config/upstream-port-state.json` except via `update-state`.
- `verify` never builds the upstream ref/tree — only the current worktree.

## Scheduled drift check (CI)

`.github/workflows/upstream-port-drift.yml` runs on a schedule and on
`workflow_dispatch`, with `permissions: contents: read` only, no secrets, and
`persist-credentials: false`. Each run:

1. Configures/verifies the `decomp` remote points at the pinned canonical URL
   (`https://github.com/laqieer/fireemblem8u.git`) — a local `.git/config`
   edit only, never a fetch/checkout by itself.
2. Explicitly, anonymously fetches that remote's objects/refs by calling the
   same `python3 -m scripts.upstream_port fetch --remote decomp` subcommand a
   maintainer runs locally (see Step 0 above), which re-verifies the pinned
   URL itself before running a plain `git fetch`. This **only** updates local
   remote-tracking refs/objects (e.g. `refs/remotes/decomp/master`) — it never
   checks out, builds, imports, or executes anything from the fetched tree.
3. Runs the read-only `drift` (and, best-effort, `scan`) subcommands against
   that freshly-fetched local ref — not against the recorded `last_ported`
   SHA itself — so it can genuinely detect new commits that have landed on
   the live canonical branch since the last recorded scan/port boundary.
4. Writes the textual drift/scan report to the job summary and uploads it as
   an artifact, whether or not drift was found, before deciding the job's
   pass/fail status.
5. Fails the job (as a visibility signal only, never a state change) when the
   `drift` subcommand's exit code is non-zero — real upstream drift found
   (`2`) or an integrity problem/tool error (`3`/other).

It never commits, branches, opens a PR, merges, cherry-picks, or pushes
anything, and it never calls `update-state` — detecting drift never
auto-updates `config/upstream-port-state.json`, the source tree, or `HEAD`.
`workflow_dispatch` takes no inputs, so there is no caller-controlled value
that could inject an alternate remote/ref/URL into any step.

## Tests

```sh
python3 -m unittest discover -s tests/upstream_port -p "test_*.py" -v
```

Uses deterministic, offline, synthetic Git repositories (fixed author
identities/dates via `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`, never
`datetime.now()`) built with plain local `git` subprocess calls — no
network access, and upstream "commits" in the fixtures are never executed,
only read.
