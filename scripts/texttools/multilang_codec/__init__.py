"""Deterministic byte-preserving Huffman codec for localized FE8 text."""

from .codec import (
    Catalog,
    CatalogBudget,
    CatalogEntry,
    DecodeResult,
    DecodeStatus,
    HuffmanCode,
    HuffmanModel,
    build_catalog,
    build_frequency_table,
    build_huffman_model,
    compress_symbols,
    decompress_bounded,
    pack_bytes,
    unpack_symbols,
)

__all__ = [
    "Catalog",
    "CatalogBudget",
    "CatalogEntry",
    "DecodeResult",
    "DecodeStatus",
    "HuffmanCode",
    "HuffmanModel",
    "build_catalog",
    "build_frequency_table",
    "build_huffman_model",
    "compress_symbols",
    "decompress_bounded",
    "pack_bytes",
    "unpack_symbols",
]
