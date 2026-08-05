"""Stable constants for generated full-game locale catalogs."""

LOCALE_IDS = ("ja", "zh-Hans")
SOURCE_KINDS = ("indexed", "raw", "authored", "english_fallback")
PRESENT_PROVIDER_KINDS = ("indexed", "raw", "authored")

FALLBACK_KIND_NONE = "none"
FALLBACK_KIND_EXPLICIT_ENGLISH = "explicit_english_fallback"
FALLBACK_KIND_PROVIDER_UNAVAILABLE = "provider_unavailable"

TARGET_STORAGE_BYTES = 0x1600
NULL_OFFSET = 0xFFFFFFFF
NULL_ROOT_INDEX = 0xFFFFFFFF

REPORT_SCHEMA_VERSION = 1
BUDGET_SCHEMA_VERSION = 1
REPORT_KIND = "fe8u-game-localization-report"
BUDGET_KIND = "fe8u-game-localization-budget"

OUTPUT_HEADER_NAME = "game_localization_catalog.h"
OUTPUT_CONFIG_HEADER_NAME = "localized_game_text_data.h"
OUTPUT_SOURCE_NAME = "game_localization_catalog.c"
OUTPUT_REPORT_NAME = "game_localization_report.json"
OUTPUT_BUDGET_NAME = "game_localization_budget.json"

ENTRY_STRUCT_SIZE_BYTES = 20
LOCALE_CATALOG_STRUCT_SIZE_BYTES = 44
LOCALE_POINTER_ARRAY_BYTES = len(LOCALE_IDS) * 4

PROVIDER_KIND_VALUES = {
    None: 0,
    "indexed": 1,
    "raw": 2,
    "authored": 3,
}
FALLBACK_KIND_VALUES = {
    FALLBACK_KIND_NONE: 0,
    FALLBACK_KIND_EXPLICIT_ENGLISH: 1,
    FALLBACK_KIND_PROVIDER_UNAVAILABLE: 2,
}
