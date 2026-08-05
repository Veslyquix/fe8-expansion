"""Tests for the deterministic byte-preserving multilingual Huffman core."""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "texttools"))

from multilang_codec import (  # noqa: E402
    DecodeStatus,
    build_catalog,
    build_huffman_model,
    compress_symbols,
    decompress_bounded,
    pack_bytes,
    unpack_symbols,
)


CORPUS = (
    b"ASCII text\x00",
    "エフラムとエイリーク".encode("utf-8") + b"\x00",
    "火焰之纹章".encode("utf-8") + b"\x00",
    "four-byte: 😀 𠮷".encode("utf-8") + b"\x00",
    bytes((0x80, 0x01, 0x10, 0x02, 0x03, 0x23, 0x7F, 0xE9, 0x00)),
    b"ABCD\x00",
)


class BytePackingTests(unittest.TestCase):
    def test_adjacent_packing_is_lossless_for_corpus_and_zero_boundaries(self):
        samples = CORPUS + (
            b"",
            b"\x00",
            b"\x01\x02\x03",
            b"\x01\x00\x02\x00",
            b"\x00\x01\x00",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(unpack_symbols(pack_bytes(sample)), sample)

    def test_pairing_never_hides_zero_byte(self):
        self.assertEqual(pack_bytes(b"\x12\x34\x56"), (0x3412, 0x0056))
        self.assertEqual(pack_bytes(b"\x12\x00\x34\x00"), (0x0012, 0, 0x0034, 0))


class HuffmanModelTests(unittest.TestCase):
    def test_equal_frequency_ties_are_input_order_independent(self):
        forward = build_huffman_model((0, 1, 2, 3))
        reverse = build_huffman_model((3, 2, 1, 0))
        expected_nodes = (
            0xFFFF0000,
            0xFFFF0001,
            0x00010000,
            0xFFFF0002,
            0xFFFF0003,
            0x00040003,
            0x00050002,
        )

        self.assertEqual(forward.nodes, reverse.nodes)
        self.assertEqual(forward.codes, reverse.codes)
        self.assertEqual(forward.nodes, expected_nodes)
        self.assertEqual(forward.root_index, 6)

    def test_known_engine_node_format_and_lsb_first_stream(self):
        model = build_huffman_model((0, 0x41))
        codes = model.code_map()
        compressed, bit_length = compress_symbols((0x41, 0), codes)

        self.assertEqual(model.nodes, (0xFFFF0000, 0xFFFF0041, 0x00010000))
        self.assertEqual(compressed, b"\x01")
        self.assertEqual(bit_length, 2)

    def test_single_symbol_catalog_has_decodable_internal_root(self):
        catalog = build_catalog((b"\x00",))
        self.assertEqual(catalog.decode_entry(0), b"\x00")
        self.assertEqual(catalog.nodes, (0xFFFF0000, 0x00000000))
        self.assertEqual(catalog.root_index, 1)


class CatalogTests(unittest.TestCase):
    def test_multilingual_control_corpus_round_trips_byte_exact(self):
        messages = (CORPUS[0], None) + CORPUS[1:]
        catalog = build_catalog(messages, suffix_share=True)

        for index, expected in enumerate(messages):
            with self.subTest(index=index):
                self.assertEqual(catalog.decode_entry(index), expected)

        self.assertFalse(catalog.entries[1].present)
        self.assertIsNone(catalog.entries[1].pointer_offset)
        self.assertEqual(catalog.budget.pointer_bytes, len(messages) * 4)
        self.assertEqual(
            catalog.budget.max_decoded_bytes,
            max(len(message) for message in messages if message is not None),
        )
        self.assertEqual(
            catalog.budget.source_sha256,
            catalog.budget.round_trip_sha256,
        )
        self.assertGreater(catalog.budget.symbol_count, 0)
        self.assertEqual(catalog.budget.node_count, len(catalog.nodes))

    def test_immediate_predecessor_suffix_sharing_is_deterministic(self):
        longer = b"A" * 30 + b"\x00"
        shorter = b"A" * 14 + b"\x00"
        shared = build_catalog((longer, shorter), suffix_share=True)
        unshared = build_catalog((longer, shorter), suffix_share=False)

        self.assertEqual(shared.decode_entry(0), longer)
        self.assertEqual(shared.decode_entry(1), shorter)
        self.assertEqual(shared.entries[1].shared_from, 0)
        self.assertEqual(
            shared.entries[1].pointer_offset,
            shared.entries[0].pointer_offset + 1,
        )
        self.assertEqual(
            unshared.budget.compressed_bytes,
            shared.budget.compressed_bytes + shared.entries[1].compressed_size,
        )

    def test_absent_only_catalog_has_explicit_null_model(self):
        catalog = build_catalog((None, None))
        payload = catalog.to_dict()

        self.assertIsNone(payload["root_index"])
        self.assertEqual(payload["node_table"], [])
        self.assertEqual(payload["compressed_blob_hex"], "")
        self.assertEqual(payload["entries"][0]["present"], False)
        self.assertIsNone(payload["entries"][0]["pointer_offset"])
        self.assertEqual(catalog.budget.pointer_bytes, 8)

    def test_serialization_is_stable_and_hashes_match_payloads(self):
        catalog = build_catalog((CORPUS[0], None, CORPUS[1]))
        first = catalog.to_json()
        second = catalog.to_json()
        payload = json.loads(first)

        self.assertEqual(first, second)
        self.assertEqual(payload["schema"], "fe8-multilang-huffman-v1")
        self.assertEqual(
            payload["budget"]["hashes"]["compressed_blob_sha256"],
            hashlib.sha256(catalog.compressed_blob).hexdigest(),
        )

    def test_catalog_rejects_unreachable_bytes_after_nul(self):
        with self.assertRaisesRegex(ValueError, "end with NUL"):
            build_catalog((b"missing",))
        with self.assertRaisesRegex(ValueError, "interior NUL"):
            build_catalog((b"a\x00b\x00",))


class BoundedHostDecoderTests(unittest.TestCase):
    def test_malformed_child_index_is_explicit(self):
        result = decompress_bounded(
            (0x00020002, 0xFFFF0000), 2, 0, b"\x00", 1, 8
        )
        self.assertEqual(result.status, DecodeStatus.INVALID_NODE)
        self.assertEqual(result.data, b"")

    def test_truncated_input_while_inside_tree_is_explicit(self):
        nodes = (
            0x00090001,
            0x00090002,
            0x00090003,
            0x00090004,
            0x00090005,
            0x00090006,
            0x00090007,
            0x00090008,
            0x00090009,
            0xFFFF0000,
        )
        result = decompress_bounded(nodes, len(nodes), 0, b"\x00", 1, 8)
        self.assertEqual(result.status, DecodeStatus.TRUNCATED_INPUT)
        self.assertEqual(result.data, b"")

    def test_complete_symbols_without_terminator_are_explicit(self):
        nodes = (0xFFFF0041, 0xFFFF0000, 0x00010000)
        result = decompress_bounded(nodes, len(nodes), 2, b"\x00", 1, 8)
        self.assertEqual(result.status, DecodeStatus.MISSING_TERMINATOR)
        self.assertEqual(result.data, b"A" * 8)

    def test_output_overflow_stops_at_capacity(self):
        nodes = (0xFFFF0041, 0xFFFF0000, 0x00010000)
        result = decompress_bounded(nodes, len(nodes), 2, b"\x02", 1, 1)
        self.assertEqual(result.status, DecodeStatus.OUTPUT_OVERFLOW)
        self.assertEqual(result.data, b"A")
        self.assertEqual(result.decoded_length, 1)

    def test_paired_zero_symbol_is_rejected(self):
        nodes = (0xFFFF0100, 0xFFFF0000, 0x00010000)
        result = decompress_bounded(nodes, len(nodes), 2, b"\x00", 1, 8)
        self.assertEqual(result.status, DecodeStatus.INVALID_SYMBOL)
        self.assertEqual(result.data, b"")


if __name__ == "__main__":
    unittest.main()
