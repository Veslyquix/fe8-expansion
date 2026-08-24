# localization.mk -- fast, toolchain-independent developer/CI targets for
# the expansion localization catalog (issue #18 sprint 1).
#
# These targets only require Python (the stdlib-only scripts/localization
# package) -- never the modern GCC toolchain or legacy agbcc -- and never
# write anything outside build/ (see scripts/localization/generate.py's
# write-if-unchanged output and this repository's .gitignore). They are
# independent of (but consistent with) modern.mk's own "Localization
# catalog" section, which invokes the exact same generator as part of a
# real modern linked build; use these targets for a fast local/CI check
# without building the whole ROM.
#
# Included directly by the top-level Makefile, mirroring generated_data.mk's
# own standalone-fast-target convention (see that file/docs/generated_data.md).

LOCALIZATION_OUT_DIR := build/expansion-localization/generated

.PHONY: localization-validate localization-generate localization-check \
	localization-test localization-budget

# validate -- load + fully validate texts/expansion/registry.json +
# catalog.en.json (duplicate/sparse/out-of-order/invalid/reused-tombstone
# ids, ASCII/width/byte-budget, placeholder/control-token parity, ...);
# silent on success, fails with an actionable message otherwise. Never
# writes any file.
localization-validate:
	$(PYTHON) -m scripts.localization.cli validate

# generate -- validate, then write the generated header/C/budget report
# under $(LOCALIZATION_OUT_DIR) (write-if-unchanged).
localization-generate:
	@mkdir -p $(LOCALIZATION_OUT_DIR)
	$(PYTHON) -m scripts.localization.cli generate --out-dir $(LOCALIZATION_OUT_DIR)

# check -- the CI-suitable gate: validate + generate, self-healing the
# generated files under $(LOCALIZATION_OUT_DIR) -- never touches anything
# committed. An alias for generate today; kept as its own target so CI
# workflows can name the gate independently of the local dev target.
localization-check: localization-generate

# test -- the full scripts/localization/tests/ suite: schema/pseudo/
# catalog/generate/CLI/determinism unit tests plus the host-native
# resolver-behavior and vanilla-isolation source-audit tests (skipped
# automatically if no host `cc` is available).
localization-test:
	$(PYTHON) -m unittest discover -s scripts/localization/tests -p "test_*.py"

# budget -- validate + generate, then print the budget report JSON
# (catalog/index/string/scratch byte usage, ASCII codepoint/glyph counts,
# and their configured limits) to stdout.
localization-budget:
	@mkdir -p $(LOCALIZATION_OUT_DIR)
	$(PYTHON) -m scripts.localization.cli budget --out-dir $(LOCALIZATION_OUT_DIR)
