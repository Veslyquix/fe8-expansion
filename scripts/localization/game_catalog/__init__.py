"""Deterministic full-game localized catalog generator."""

from .build import (
    DEFAULT_ENGLISH_DEFINITIONS_PATH,
    DEFAULT_ENGLISH_TEXTS_PATH,
    DEFAULT_JA_INDEXED_PATH,
    DEFAULT_MAPPING_PATH,
    DEFAULT_TARGET_HEADER_PATH,
    DEFAULT_ZH_INDEXED_PATH,
    DEFAULT_ZH_RAW_PATH,
    GameCatalogError,
    build_game_catalog,
    encode_canonical_text,
    generate,
    write_build,
)

__all__ = [
    "DEFAULT_ENGLISH_DEFINITIONS_PATH",
    "DEFAULT_ENGLISH_TEXTS_PATH",
    "DEFAULT_JA_INDEXED_PATH",
    "DEFAULT_MAPPING_PATH",
    "DEFAULT_TARGET_HEADER_PATH",
    "DEFAULT_ZH_INDEXED_PATH",
    "DEFAULT_ZH_RAW_PATH",
    "GameCatalogError",
    "build_game_catalog",
    "encode_canonical_text",
    "generate",
    "write_build",
]
