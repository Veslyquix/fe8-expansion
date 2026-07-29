# Standalone targets for scripts/release_rehearsal + scripts/modernize/migrations
# (issue #9 -- read-only release/publication rehearsal).
#
# None of these targets are wired into `all`, `expansion-modern-*`, or any
# existing host/build/generated/upstream/default/runtime gate; they are
# fully standalone, exactly like generated-data-check (generated_data.mk).
# See docs/release_process.md for the full contract, including the exit
# code contract these targets rely on: exit 0 means "the checker ran and
# produced a well-formed report" (the report's own status may say
# "mechanically eligible" or "blocked" -- both are valid), exit non-zero
# means an actionable tooling/input defect was found.
#
# release-test              : stdlib unittest suites for scripts/release
#                              and scripts/modernize/migrations.
# release-migrations-check  : migration registry internal-consistency gate
#                              (scripts/modernize/migrations/registry.py check).
# release-rehearse          : deterministic double-archive-build + hash
#                              compare + clean-rebuild blocker report.
#                              Never uploads or retains an archive.
# release-check             : full release-manifest eligibility check.

.PHONY: release-test release-migrations-check release-rehearse release-check \
        release-changelog-check

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
