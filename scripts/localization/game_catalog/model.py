"""Data models for deterministic full-game locale catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from scripts.localization.game_locales.mapping import MappingDocument
from scripts.texttools.multilang_codec import Catalog


class GameCatalogError(ValueError):
    """Raised when full-game locale inputs or generated outputs are invalid."""


@dataclass(frozen=True)
class EntryPayloadMeta:
    target_id: int
    mapping_source_kind: str
    mapping_source: Dict[str, Any]
    locale_provider_kind: Optional[str]
    source_text: Optional[str]
    encoded_bytes: Optional[bytes]
    fallback_kind: str
    fallback_reason: Optional[str]
    note: Optional[str]

    @property
    def present(self) -> bool:
        return self.encoded_bytes is not None


@dataclass(frozen=True)
class EnglishSourceEntry:
    target_id: int
    definition: Optional[str]
    source_text: str
    encoded_bytes: bytes


@dataclass(frozen=True)
class EnglishCatalogBundle:
    locale: str
    entries: Tuple[EnglishSourceEntry, ...]
    catalog: Catalog


@dataclass(frozen=True)
class LocaleCatalogBundle:
    locale: str
    entries: Tuple[EntryPayloadMeta, ...]
    catalog: Catalog


@dataclass(frozen=True)
class GameCatalogBuild:
    target_count: int
    mapping: MappingDocument
    mapping_source_counts: Mapping[str, int]
    english: EnglishCatalogBundle
    locales: Tuple[LocaleCatalogBundle, ...]
    report: Dict[str, Any]
    budget: Dict[str, Any]
    suffix_share: bool

    @property
    def enabled_locales(self) -> Tuple[str, ...]:
        return tuple(bundle.locale for bundle in self.locales)

    def locale_bundle(self, locale: str) -> LocaleCatalogBundle:
        for bundle in self.locales:
            if bundle.locale == locale:
                return bundle
        raise KeyError(locale)
