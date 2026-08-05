# game_localization.mk -- focused developer/CI targets for the
# deterministic full-game localized catalog generator. Every selected CJK
# profile also emits one shared modern English source bundle.
#
# Included by the top-level Makefile, but standalone on purpose: none of these
# targets is a prerequisite of `all`, so default English builds never generate
# full-game locale payloads unless a caller opts in explicitly.

GAME_LOCALIZATION_OUT_DIR ?= build/game-localization/generated
GAME_LOCALIZATION_ENABLED_LOCALES ?= ja,zh-Hans
PYTHON3 ?= python3
PYTEST_ENV := PYTHONDONTWRITEBYTECODE=1

.PHONY: game-localization-validate game-localization-generate \
	game-localization-check game-localization-test game-localization-budget

game-localization-validate:
	$(PYTEST_ENV) $(PYTHON3) -m scripts.localization.game_catalog validate \
		--enabled-locales "$(GAME_LOCALIZATION_ENABLED_LOCALES)"

game-localization-generate:
	@mkdir -p $(GAME_LOCALIZATION_OUT_DIR)
	$(PYTEST_ENV) $(PYTHON3) -m scripts.localization.game_catalog generate \
		--out-dir $(GAME_LOCALIZATION_OUT_DIR) \
		--enabled-locales "$(GAME_LOCALIZATION_ENABLED_LOCALES)"

game-localization-check: game-localization-generate

game-localization-test:
	$(PYTEST_ENV) $(PYTHON3) -m unittest discover \
		-s scripts/localization/game_catalog/tests -p 'test_*.py' -v

game-localization-budget:
	@mkdir -p $(GAME_LOCALIZATION_OUT_DIR)
	$(PYTEST_ENV) $(PYTHON3) -m scripts.localization.game_catalog budget \
		--out-dir $(GAME_LOCALIZATION_OUT_DIR) \
		--enabled-locales "$(GAME_LOCALIZATION_ENABLED_LOCALES)"
