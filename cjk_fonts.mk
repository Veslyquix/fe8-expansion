PYTHON ?= python3
FEBUILDER_CLI ?= FEBuilderGBA.CLI
CJK_BUILD_DIR ?= build/cjk-fonts
CJK_PACKAGE_DIR := $(CJK_BUILD_DIR)/package
CJK_MANIFEST := fonts/cjk/febuilder-manifest.json
CJK_GENERATION_REPORT := fonts/cjk/reports/febuilder-generation-report.json
CJK_PACKAGE_ARCHIVE := fonts/cjk/packages/febuilder-schema-v1.zip

.NOTPARALLEL:

.PHONY: cjk-fonts-check cjk-fonts-test cjk-fonts-generate-inventory
.PHONY: cjk-fonts-febuilder-dry-run cjk-fonts-febuilder-generate
.PHONY: cjk-fonts-febuilder-validate cjk-fonts-febuilder-roundtrip
.PHONY: cjk-fonts-import cjk-fonts-febuilder-all

cjk-fonts-check:
	$(PYTHON) -m scripts.fonttools.cjk check

cjk-fonts-test:
	$(PYTHON) -m unittest discover -s scripts/fonttools/cjk/tests -p 'test_*.py' -v

cjk-fonts-generate-inventory:
	$(PYTHON) -m scripts.fonttools.cjk generate-inventory

cjk-fonts-febuilder-dry-run: cjk-fonts-generate-inventory
	rm -rf $(CJK_BUILD_DIR)/dry-run-package $(CJK_BUILD_DIR)/dry-run-report.json
	mkdir -p $(CJK_BUILD_DIR)
	$(FEBUILDER_CLI) --build-font-library --manifest=$(CJK_MANIFEST) \
		--out=$(CJK_BUILD_DIR)/dry-run-package --mode=dry-run \
		--report=$(CJK_BUILD_DIR)/dry-run-report.json

cjk-fonts-febuilder-generate: cjk-fonts-febuilder-dry-run
	rm -rf $(CJK_PACKAGE_DIR) $(CJK_GENERATION_REPORT)
	mkdir -p $(CJK_BUILD_DIR) fonts/cjk/reports
	$(FEBUILDER_CLI) --build-font-library --manifest=$(CJK_MANIFEST) \
		--out=$(CJK_PACKAGE_DIR) --mode=generate \
		--report=$(CJK_GENERATION_REPORT)

cjk-fonts-febuilder-validate: cjk-fonts-febuilder-generate
	$(FEBUILDER_CLI) --build-font-library --manifest=$(CJK_MANIFEST) \
		--out=$(CJK_PACKAGE_DIR) --mode=validate \
		--report=$(CJK_GENERATION_REPORT)

cjk-fonts-febuilder-roundtrip: cjk-fonts-febuilder-validate
	$(FEBUILDER_CLI) --build-font-library --manifest=$(CJK_MANIFEST) \
		--out=$(CJK_PACKAGE_DIR) --mode=roundtrip \
		--report=$(CJK_GENERATION_REPORT)

cjk-fonts-import: cjk-fonts-febuilder-roundtrip
	$(PYTHON) -m scripts.fonttools.cjk archive-package \
		--package-dir $(CJK_PACKAGE_DIR) --output $(CJK_PACKAGE_ARCHIVE)
	$(PYTHON) -m scripts.fonttools.cjk import-package \
		--package $(CJK_PACKAGE_ARCHIVE) --report $(CJK_GENERATION_REPORT)

cjk-fonts-febuilder-all: cjk-fonts-import
	$(PYTHON) -m scripts.fonttools.cjk check
	$(PYTHON) -m unittest discover -s scripts/fonttools/cjk/tests -p 'test_*.py' -v
