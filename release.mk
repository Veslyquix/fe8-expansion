# Standalone targets for scripts/release_rehearsal + scripts/modernize/migrations
# (issue #9 -- read-only release/publication rehearsal).
#
# None of these targets are wired into `all`, `expansion-modern-*`, or any
# existing host/build/generated/upstream/default/runtime gate; they are
# fully standalone, exactly like generated-data-check (generated_data.mk).
# See docs/release_process.md for the full contract, including the exit
# code contract these targets rely on (0/1/2/3 -- see
# scripts/release_rehearsal/cli.py's own module docstring for the exact
# meaning of each code).
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
#                                    Exits 1 (not 0) while BLOCKED.
# release-rehearse-require-eligible : `cli rehearse --require-eligible`.
#                                    Exits 1 (not 0) while BLOCKED.
#
# The two targets below are the complementary "expected-blocked health
# check" targets: they exit 0 ONLY if the candidate's status is exactly
# "blocked" (today's real, expected state) and exit 3 the moment it ever
# stops being exactly that -- e.g. useful in CI to mechanically assert
# "still blocked, as expected" without ever papering over a status this
# repository has not been told (via a real, reviewed change to this
# Makefile/workflow) to expect instead.
#
# release-check-expect-blocked    : `cli check --expect-status blocked`.
# release-rehearse-expect-blocked : `cli rehearse --expect-status blocked`.
#
# release-workflow-guard          : dynamic machine-JSON check of
#                                    .github/workflows/release-rehearsal.yml's
#                                    own permission/safety contract
#                                    (`cli workflow-guard`).

.PHONY: release-test release-migrations-check release-rehearse release-check \
        release-changelog-check release-check-require-eligible \
        release-rehearse-require-eligible release-check-expect-blocked \
        release-rehearse-expect-blocked release-workflow-guard

release-test:
	$(PYTHON) -m unittest discover -s scripts/release_rehearsal/tests -v
	$(PYTHON) -m unittest discover -s scripts/modernize/migrations/tests -v

release-migrations-check:
	$(PYTHON) -m scripts.modernize.migrations.cli check

release-changelog-check:
	$(PYTHON) -m scripts.release_rehearsal.changelog check

release-rehearse:
	$(PYTHON) -m scripts.release_rehearsal.cli rehearse

release-check:
	$(PYTHON) -m scripts.release_rehearsal.cli check

release-check-require-eligible:
	$(PYTHON) -m scripts.release_rehearsal.cli check --require-eligible

release-rehearse-require-eligible:
	$(PYTHON) -m scripts.release_rehearsal.cli rehearse --require-eligible

release-check-expect-blocked:
	$(PYTHON) -m scripts.release_rehearsal.cli check --expect-status blocked

release-rehearse-expect-blocked:
	$(PYTHON) -m scripts.release_rehearsal.cli rehearse --expect-status blocked

release-workflow-guard:
	$(PYTHON) -m scripts.release_rehearsal.cli workflow-guard .github/workflows/release-rehearsal.yml
