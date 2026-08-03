# Standalone targets for scripts/release_rehearsal + scripts/modernize/migrations
# (issue #9 -- read-only release/publication rehearsal).
#
# None of these targets are wired into `all`, `expansion-modern-*`, or any
# existing host/build/generated/upstream/default/runtime gate; they are
# fully standalone, exactly like generated-data-check (generated_data.mk).
# See docs/release_process.md for the full contract, including the exit
# code contract the underlying CLI itself defines (0/1/2/3 -- see
# scripts/release_rehearsal/cli.py's own module docstring for the exact
# meaning of each code).
#
# IMPORTANT -- Make does not preserve/forward that granular exit code.
# That 0/1/2/3 contract belongs to a *direct* CLI invocation (e.g.
# `python3 -m scripts.release_rehearsal.cli check --require-eligible`).
# GNU Make itself, when any recipe in a target exits non-zero, always
# reports the *target*'s own exit status as exit code 2 (a fixed "Error
# N" message is printed naming the recipe's real code, but `make`'s own
# process exit status to its caller is 2 regardless of whether the
# recipe actually exited 1, 2, 3, or any other non-zero value --
# reproduce with e.g. `printf 't:\n\texit 1\n' | make -f - t; echo $?`,
# which prints `2`, never `1`). So every comment below that says a target
# "exits N" while invoked via `make <target>` means the *underlying CLI*
# exits N; `make <target>` itself only ever distinguishes exit 0 (the
# recipe succeeded) from exit 2 (the recipe failed for *some* reason --
# the granular 1-vs-2-vs-3 distinction is not visible at the `make`
# process-exit-status layer, only in the recipe's own stdout/stderr/JSON
# report). Invoke the CLI directly (never through `make`) when the exact
# 1-vs-3 distinction itself must be observed as a process exit code.
#
# release-test                    : stdlib unittest suites for
#                                    scripts/release_rehearsal and
#                                    scripts/modernize/migrations.
# release-migrations-check        : migration registry internal-
#                                    consistency gate
#                                    (scripts/modernize/migrations/registry.py check).
# release-changelog-check         : changelog-fragment/CHANGELOG.md
#                                    freshness gate.
# release-rehearse                : deterministic double-archive-build +
#                                    hash compare + clean-rebuild blocker
#                                    report. Never uploads or retains an
#                                    archive. ALWAYS exits 0 for a
#                                    well-formed report (the report's own
#                                    "status" may say "blocked" -- expected
#                                    -- or "mechanically eligible").
# release-check                   : full release-manifest eligibility
#                                    check. Same always-exit-0-for-a-
#                                    well-formed-report contract as
#                                    release-rehearse above.
#
# The two targets below are the machine-distinct status/exit-code gates
# (issue #9 verifier remediation) -- unlike the two targets above, THESE
# ARE INTENDED TO, AND CURRENTLY DO, FAIL (non-zero exit) while this
# repository's candidate is BLOCKED (its current, correct, expected
# state): they exist so a stricter pipeline stage (or a human) can demand
# "prove this is actually eligible" and get a real failure, instead of
# reading prose.
#
# release-check-require-eligible  : `cli check --require-eligible`.
#                                    The CLI itself exits 1 while
#                                    BLOCKED; `make` itself reports this
#                                    (like any failed recipe) as exit 2,
#                                    not 1 -- see the IMPORTANT note above.
# release-rehearse-require-eligible : `cli rehearse --require-eligible`.
#                                    Same CLI-exits-1/make-itself-exits-2
#                                    contract as the target above.
#
# The two targets below are the complementary "expected-blocked health
# check" targets: the underlying CLI exits 0 ONLY if the candidate's
# status is exactly "blocked" (today's real, expected state) and exits 3
# the moment it ever stops being exactly that -- e.g. useful in CI to
# mechanically assert "still blocked, as expected" without ever papering
# over a status this repository has not been told (via a real, reviewed
# change to this Makefile/workflow) to expect instead. Through `make`,
# the healthy (still-blocked) case is exit 0 exactly as the CLI reports;
# the moment that ever stops being true, `make` itself reports exit 2
# (not 3) for the same reason as `*-require-eligible` above.
#
# release-check-expect-blocked    : `cli check --expect-status blocked`.
# release-rehearse-expect-blocked : `cli rehearse --expect-status blocked`.
#
# release-workflow-guard          : dynamic machine-JSON check of
#                                    .github/workflows/release-rehearsal.yml's
#                                    own permission/safety contract
#                                    (`cli workflow-guard`) -- this now also
#                                    includes the action-pin inventory
#                                    cross-check below (folded into the same
#                                    JSON report/exit contract).
# release-action-pins-check       : standalone direct invocation of
#                                    scripts/release_rehearsal/action_pins.py
#                                    (issue #9 mandatory correction #1) --
#                                    every external `uses:` reference in
#                                    .github/workflows/release-rehearsal.yml
#                                    must be pinned to an exact 40-lowercase-
#                                    hex commit SHA, and that pin must
#                                    exactly match docs/release_data/
#                                    action_pins.json's committed inventory.
#                                    This is documentation/evidence only --
#                                    never itself a publication authorization.
# release-tree-coverage-check     : standalone direct invocation of
#                                    scripts/release_rehearsal/tree_coverage.py
#                                    (issue #9 mandatory correction #2) --
#                                    the included allowlist and the export
#                                    exclusions must be an exact, disjoint
#                                    partition of the complete immutable
#                                    HEAD tree.
# release-submodule-binding-check : standalone direct invocation of
#                                    scripts/release_rehearsal/submodule_binding.py
#                                    (issue #9 mandatory correction #4) --
#                                    the mgfembp submodule's .gitmodules
#                                    section, HEAD tree gitlink, export
#                                    exclusion, and provenance record must
#                                    all agree exactly. Never fetches/
#                                    initializes the submodule.
# release-epoch-claims-check      : standalone direct invocation of
#                                    scripts/release_rehearsal/epoch_claims.py
#                                    (issue #9 verifier remediation) --
#                                    scans release docs/headers for a
#                                    stale current-state
#                                    EXPANSION_SAVE_COMPAT_EPOCH claim
#                                    (e.g. "epoch stays 1" after a later
#                                    commit actually bumped it). Already
#                                    folded into every `release-check`/
#                                    `release-rehearse` report too (see
#                                    manifest.py's "epoch_claims" sub-
#                                    report) -- this target exists for a
#                                    fast, standalone, non-JSON check.
# release-stale-count-claims-check: standalone direct invocation of
#                                    scripts/release_rehearsal/stale_count_claims.py
#                                    (issue #9 verifier remediation) --
#                                    scans release closure evidence/docs
#                                    for a hardcoded aggregate test-count
#                                    claim (e.g. "(860 tests)"). Already
#                                    folded into every `release-check`/
#                                    `release-rehearse` report too (see
#                                    manifest.py's "stale_count_claims"
#                                    sub-report).

.PHONY: release-test release-migrations-check release-rehearse release-check \
        release-changelog-check release-check-require-eligible \
        release-rehearse-require-eligible release-check-expect-blocked \
        release-rehearse-expect-blocked release-workflow-guard \
        release-action-pins-check release-tree-coverage-check \
        release-submodule-binding-check release-epoch-claims-check \
        release-stale-count-claims-check

# RELEASE_TARGET_SHA -- issue #9 mandatory correction (exact target-SHA
# binding): every publication-eligibility/rehearsal target below passes
# this explicitly as `--target-sha`, rather than letting
# scripts/release_rehearsal/manifest.py's own `resolve_target_sha`
# implicitly fall back to a bare `git rev-parse HEAD` call. Locally, this
# still resolves to the exact current HEAD by default (identical
# behavior to before) -- but it is now an explicit, auditable value any
# caller can see/override, and CI (.github/workflows/release-rehearsal.yml)
# overrides it via a job-level `env: RELEASE_TARGET_SHA: ${{ github.sha }}`
# so the *exact, immutable checked-out commit* is what every eligibility
# check actually binds to, never an independently-resolved value that
# could theoretically disagree with the checkout step.
RELEASE_TARGET_SHA ?= $(shell git rev-parse HEAD)

release-test:
	$(PYTHON) -m unittest discover -s scripts/release_rehearsal/tests -v
	$(PYTHON) -m unittest discover -s scripts/modernize/migrations/tests -v

release-migrations-check:
	$(PYTHON) -m scripts.modernize.migrations.cli check

release-changelog-check:
	$(PYTHON) -m scripts.release_rehearsal.changelog check

release-rehearse:
	$(PYTHON) -m scripts.release_rehearsal.cli rehearse --target-sha $(RELEASE_TARGET_SHA)

release-check:
	$(PYTHON) -m scripts.release_rehearsal.cli check --target-sha $(RELEASE_TARGET_SHA)

release-check-require-eligible:
	$(PYTHON) -m scripts.release_rehearsal.cli check --target-sha $(RELEASE_TARGET_SHA) --require-eligible

release-rehearse-require-eligible:
	$(PYTHON) -m scripts.release_rehearsal.cli rehearse --target-sha $(RELEASE_TARGET_SHA) --require-eligible

release-check-expect-blocked:
	$(PYTHON) -m scripts.release_rehearsal.cli check --target-sha $(RELEASE_TARGET_SHA) --expect-status blocked

release-rehearse-expect-blocked:
	$(PYTHON) -m scripts.release_rehearsal.cli rehearse --target-sha $(RELEASE_TARGET_SHA) --expect-status blocked

release-workflow-guard:
	$(PYTHON) -m scripts.release_rehearsal.cli workflow-guard .github/workflows/release-rehearsal.yml

release-action-pins-check:
	$(PYTHON) -m scripts.release_rehearsal.action_pins .github/workflows/release-rehearsal.yml

release-tree-coverage-check:
	$(PYTHON) -m scripts.release_rehearsal.tree_coverage check

release-submodule-binding-check:
	$(PYTHON) -m scripts.release_rehearsal.submodule_binding

release-epoch-claims-check:
	$(PYTHON) -m scripts.release_rehearsal.epoch_claims

release-stale-count-claims-check:
	$(PYTHON) -m scripts.release_rehearsal.stale_count_claims
