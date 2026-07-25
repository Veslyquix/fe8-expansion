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
python3 -m scripts.upstream_port scan --ref decomp/master --format json --output /tmp/scan.json
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
never dependent on wall-clock time.

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
suitable for CI (see the drift-scan workflow below).

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
- Output (`report.json`, `report.md`, and one `NNNN-<shortsha>.patch` per
  commit) is written only under the gitignored `build/upstream-port/` root
  (or another directory you point at, provided it is also confirmed
  gitignored via `git check-ignore` before anything is written).
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
`.github/workflows/build.yml` runs, in the same order, fail-fast:

1. `python3 scripts/artifact_guard.py --revision HEAD`
2. `python3 -m unittest discover -s scripts/modernize/tests -p test_build_default_lane.py -v`
   (issue #15: bare `make`/`make all` always resolves to the modern
   release AAPCS lane)
3. `python3 -m unittest discover -s scripts/modernize/tests -p test_quickstart.py -v`
   (issue #15: quickstart.sh only reaches the archival agbcc lane via
   explicit `make legacy`/`make fireemblem8.gba`)
4. `make generated-data-check`
5. `make expansion-modern-linker-check MODERN_CONFIG=debug MODERN_ABI=aapcs`
   (covers modern debug linker + boot + relocation/shift checks — see
   `modern.mk`'s `expansion-modern-linker-check` dependency chain)
6. `make expansion-modern-linker-check MODERN_CONFIG=release MODERN_ABI=aapcs`

None of these existing gates are weakened, reordered, or skipped.

### 7. Advance the ported boundary

```sh
python3 -m scripts.upstream_port update-state advance-ported --ref decomp/master
```

Only succeeds if every commit between the current `last_ported.sha` and the
new one is already `ported`, `skipped`, or `superseded` — it refuses to
silently skip review of any commit in the batch. Also only moves forward
(new SHA must be a descendant of, or equal to, the current one).

Separately, `update-state record-scan --ref decomp/master` lets you
explicitly advance `last_scanned` once you've reviewed a scan's output (also
forward-only).

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
- Never writes `report`/`patch` output anywhere except a confirmed-gitignored
  directory.
- Never generates a patch for a SHA that wasn't explicitly selected.
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
