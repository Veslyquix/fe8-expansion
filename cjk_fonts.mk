PYTHON ?= python3
FEBUILDER_CLI ?= FEBuilderGBA.CLI
CJK_BUILD_DIR ?= build/tmp/cjk-fonts
CJK_PACKAGE_DIR := $(CJK_BUILD_DIR)/package
CJK_MANIFEST := fonts/cjk/febuilder-manifest.json
CJK_DRY_RUN_REPORT := $(CJK_BUILD_DIR)/dry-run-report.json
CJK_TEMP_GENERATION_REPORT := $(CJK_BUILD_DIR)/generation-report.json
CJK_GENERATION_REPORT := fonts/cjk/reports/febuilder-generation-report.json
CJK_GATE_REPORT := fonts/cjk/reports/febuilder-gates.json
CJK_PACKAGE_ARCHIVE := $(CJK_BUILD_DIR)/febuilder-schema-v1.zip
FEBUILDER_COMMIT ?= c1700532b27c579511585ca63e2d63222b9ea646
FEBUILDER_DOTNET_SDK ?= 10.0.302
FEBUILDER_REPOSITORY ?= https://github.com/laqieer/FEBuilderGBA
FEBUILDER_EVIDENCE_COMMAND ?= FEBuilderGBA.CLI --build-font-library

.NOTPARALLEL:

.PHONY: cjk-fonts-check cjk-fonts-test cjk-fonts-generate-inventory
.PHONY: cjk-fonts-febuilder-dry-run cjk-fonts-febuilder-generate
.PHONY: cjk-fonts-febuilder-validate cjk-fonts-febuilder-roundtrip
.PHONY: cjk-fonts-record-gates cjk-fonts-import cjk-fonts-febuilder-all

cjk-fonts-check:
	$(PYTHON) -m scripts.fonttools.cjk check

cjk-fonts-test:
	$(PYTHON) -m unittest discover -s scripts/fonttools/cjk/tests -p 'test_*.py' -v

cjk-fonts-generate-inventory:
	$(PYTHON) -m scripts.fonttools.cjk generate-inventory

cjk-fonts-febuilder-dry-run: cjk-fonts-generate-inventory
	rm -rf $(CJK_BUILD_DIR)/dry-run-package $(CJK_DRY_RUN_REPORT)
	mkdir -p $(CJK_BUILD_DIR)
	$(FEBUILDER_CLI) --build-font-library --manifest=$(CJK_MANIFEST) \
		--out=$(CJK_BUILD_DIR)/dry-run-package --mode=dry-run \
		--report=$(CJK_DRY_RUN_REPORT)

cjk-fonts-febuilder-generate: cjk-fonts-febuilder-dry-run
	rm -rf $(CJK_PACKAGE_DIR) $(CJK_TEMP_GENERATION_REPORT)
	mkdir -p $(CJK_BUILD_DIR)
	$(FEBUILDER_CLI) --build-font-library --manifest=$(CJK_MANIFEST) \
		--out=$(CJK_PACKAGE_DIR) --mode=generate \
		--report=$(CJK_TEMP_GENERATION_REPORT)

cjk-fonts-febuilder-validate: cjk-fonts-febuilder-generate
	$(FEBUILDER_CLI) --build-font-library --manifest=$(CJK_MANIFEST) \
		--out=$(CJK_PACKAGE_DIR) --mode=validate \
		--report=$(CJK_TEMP_GENERATION_REPORT)

cjk-fonts-febuilder-roundtrip: cjk-fonts-febuilder-validate
	$(FEBUILDER_CLI) --build-font-library --manifest=$(CJK_MANIFEST) \
		--out=$(CJK_PACKAGE_DIR) --mode=roundtrip \
		--report=$(CJK_TEMP_GENERATION_REPORT)

cjk-fonts-record-gates: cjk-fonts-febuilder-roundtrip
	$(PYTHON) -m scripts.fonttools.cjk record-gates \
		--dry-run-report $(CJK_DRY_RUN_REPORT) \
		--generation-report $(CJK_TEMP_GENERATION_REPORT) \
		--output-report $(CJK_GENERATION_REPORT) \
		--gate-report $(CJK_GATE_REPORT) \
		--cli-command "$(FEBUILDER_EVIDENCE_COMMAND)" \
		--commit $(FEBUILDER_COMMIT) \
		--dotnet-sdk $(FEBUILDER_DOTNET_SDK) \
		--repository $(FEBUILDER_REPOSITORY)

cjk-fonts-import: cjk-fonts-record-gates
	$(PYTHON) -m scripts.fonttools.cjk archive-package \
		--package-dir $(CJK_PACKAGE_DIR) --output $(CJK_PACKAGE_ARCHIVE)
	$(PYTHON) -m scripts.fonttools.cjk import-package \
		--package $(CJK_PACKAGE_ARCHIVE) --report $(CJK_TEMP_GENERATION_REPORT)

cjk-fonts-febuilder-all: cjk-fonts-import
	$(PYTHON) -m scripts.fonttools.cjk check
	$(PYTHON) -m unittest discover -s scripts/fonttools/cjk/tests -p 'test_*.py' -v
