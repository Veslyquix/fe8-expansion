"""Explicit-table Huffman primitives for future multilingual catalogs.

This layer treats message content as opaque bytes. It deliberately performs no
UTF-8 or FE control-code validation; importers and renderers own those semantic
checks. Present catalog entries must contain exactly one trailing NUL because
the runtime decoder uses that byte as its only termination condition. Each
entry carries its exact meaningful compressed bit length so byte padding is
never decoded as message data.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

LEAF_MASK = 0xFFFF0000
MAX_NODE_COUNT = 0x10000
POINTER_SIZE = 4
SCHEMA = "fe8-multilang-huffman-v1"


class DecodeStatus(IntEnum):
    """Statuses shared numerically with ``localized_text_codec.h``."""

    OK = 0
    INVALID_ARGUMENT = 1
    INVALID_ROOT = 2
    INVALID_NODE = 3
    INVALID_SYMBOL = 4
    TRUNCATED_INPUT = 5
    MISSING_TERMINATOR = 6
    OUTPUT_OVERFLOW = 7
    TRAILING_DATA = 8


@dataclass(frozen=True)
class DecodeResult:
    status: DecodeStatus
    data: bytes
    decoded_length: int
    consumed_bytes: int


@dataclass(frozen=True)
class HuffmanCode:
    symbol: int
    bits: Tuple[int, ...]

    @property
    def bit_length(self) -> int:
        return len(self.bits)

    @property
    def packed_lsb_value(self) -> int:
        value = 0
        for index, bit in enumerate(self.bits):
            value |= bit << index
        return value

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "path_bits": "".join(str(bit) for bit in self.bits),
            "bit_length": self.bit_length,
            "packed_lsb_value": self.packed_lsb_value,
        }


@dataclass(frozen=True)
class HuffmanModel:
    frequencies: Tuple[Tuple[int, int], ...]
    nodes: Tuple[int, ...]
    root_index: int
    codes: Tuple[HuffmanCode, ...]

    def code_map(self) -> Dict[int, Tuple[int, ...]]:
        return {code.symbol: code.bits for code in self.codes}


@dataclass(frozen=True)
class CatalogEntry:
    present: bool
    pointer_offset: Optional[int]
    compressed_size: int
    bit_length: int
    decoded_size: int
    shared_from: Optional[int]
    decoded_sha256: Optional[str]

    @classmethod
    def absent(cls) -> "CatalogEntry":
        return cls(
            present=False,
            pointer_offset=None,
            compressed_size=0,
            bit_length=0,
            decoded_size=0,
            shared_from=None,
            decoded_sha256=None,
        )

    def to_dict(self) -> dict:
        return {
            "present": self.present,
            "pointer_offset": self.pointer_offset,
            "compressed_size": self.compressed_size,
            "bit_length": self.bit_length,
            "decoded_size": self.decoded_size,
            "shared_from": self.shared_from,
            "decoded_sha256": self.decoded_sha256,
        }


@dataclass(frozen=True)
class CatalogBudget:
    symbol_count: int
    node_count: int
    node_bytes: int
    compressed_bytes: int
    pointer_bytes: int
    max_decoded_bytes: int
    source_sha256: str
    round_trip_sha256: str
    compressed_sha256: str
    node_table_sha256: str

    def to_dict(self) -> dict:
        return {
            "symbol_count": self.symbol_count,
            "node_count": self.node_count,
            "node_bytes": self.node_bytes,
            "compressed_bytes": self.compressed_bytes,
            "pointer_bytes": self.pointer_bytes,
            "max_decoded_bytes": self.max_decoded_bytes,
            "hashes": {
                "source_framed_sha256": self.source_sha256,
                "round_trip_framed_sha256": self.round_trip_sha256,
                "compressed_blob_sha256": self.compressed_sha256,
                "node_table_sha256": self.node_table_sha256,
            },
        }


@dataclass(frozen=True)
class Catalog:
    """Serialized-catalog-ready model with blob-relative pointer metadata."""

    entries: Tuple[CatalogEntry, ...]
    compressed_blob: bytes
    model: Optional[HuffmanModel]
    budget: CatalogBudget

    @property
    def nodes(self) -> Tuple[int, ...]:
        return () if self.model is None else self.model.nodes

    @property
    def root_index(self) -> Optional[int]:
        return None if self.model is None else self.model.root_index

    def decode_entry(self, index: int) -> Optional[bytes]:
        entry = self.entries[index]
        if not entry.present:
            return None

        if self.model is None or entry.pointer_offset is None:
            raise ValueError("present entry has no Huffman model or pointer")

        start = entry.pointer_offset
        encoded = self.compressed_blob[start:start + entry.compressed_size]
        result = decompress_bounded(
            self.model.nodes,
            len(self.model.nodes),
            self.model.root_index,
            encoded,
            len(encoded),
            entry.bit_length,
            entry.decoded_size,
        )
        if result.status != DecodeStatus.OK:
            raise ValueError("catalog entry failed to decode: {}".format(result.status.name))
        return result.data

    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "entry_count": len(self.entries),
            "pointer_size": POINTER_SIZE,
            "root_index": self.root_index,
            "node_table": list(self.nodes),
            "code_table": (
                [] if self.model is None
                else [code.to_dict() for code in self.model.codes]
            ),
            "compressed_blob_hex": self.compressed_blob.hex(),
            "entries": [entry.to_dict() for entry in self.entries],
            "budget": self.budget.to_dict(),
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(
            self.to_dict(),
            indent=indent,
            sort_keys=True,
            separators=(",", ":") if indent is None else None,
        )


class _TreeNode:
    __slots__ = ("symbol", "frequency", "minimum_symbol", "serial", "left", "right")

    def __init__(
        self,
        symbol: Optional[int],
        frequency: int,
        minimum_symbol: int,
        serial: int,
        left: Optional["_TreeNode"] = None,
        right: Optional["_TreeNode"] = None,
    ):
        self.symbol = symbol
        self.frequency = frequency
        self.minimum_symbol = minimum_symbol
        self.serial = serial
        self.left = left
        self.right = right

    @property
    def is_leaf(self) -> bool:
        return self.symbol is not None


def pack_bytes(data: bytes) -> Tuple[int, ...]:
    """Pack adjacent nonzero bytes as little-endian u16 Huffman symbols.

    A zero byte is always a single-byte symbol. A nonzero byte immediately
    before a zero is also emitted alone, so unpacking never loses the zero or
    turns a terminator into the high byte of another leaf.
    """

    symbols: List[int] = []
    index = 0
    while index < len(data):
        low = data[index]
        if low == 0 or index + 1 == len(data) or data[index + 1] == 0:
            symbols.append(low)
            index += 1
        else:
            symbols.append(low | (data[index + 1] << 8))
            index += 2
    return tuple(symbols)


def unpack_symbols(symbols: Iterable[int]) -> bytes:
    """Invert :func:`pack_bytes` for arbitrary valid u16 symbols."""

    output = bytearray()
    for symbol in symbols:
        if symbol < 0 or symbol > 0xFFFF:
            raise ValueError("symbol out of u16 range: {!r}".format(symbol))
        output.append(symbol & 0xFF)
        if symbol & 0xFF00:
            output.append((symbol >> 8) & 0xFF)
    return bytes(output)


def build_frequency_table(symbols: Iterable[int]) -> Tuple[Tuple[int, int], ...]:
    """Return a symbol-sorted immutable frequency table."""

    counts: Dict[int, int] = {}
    for symbol in symbols:
        if symbol < 0 or symbol > 0xFFFF:
            raise ValueError("symbol out of u16 range: {!r}".format(symbol))
        counts[symbol] = counts.get(symbol, 0) + 1
    return tuple(sorted(counts.items()))


def _build_tree(
    frequencies: Sequence[Tuple[int, int]]
) -> Tuple[_TreeNode, bool]:
    heap: List[Tuple[int, int, int, _TreeNode]] = []
    serial = 0

    for symbol, frequency in frequencies:
        node = _TreeNode(symbol, frequency, symbol, serial)
        heapq.heappush(heap, (frequency, symbol, serial, node))
        serial += 1

    if not heap:
        raise ValueError("cannot build a Huffman tree without symbols")

    if len(heap) == 1:
        return heap[0][3], True

    while len(heap) > 1:
        _, _, _, left = heapq.heappop(heap)
        _, _, _, right = heapq.heappop(heap)
        node = _TreeNode(
            None,
            left.frequency + right.frequency,
            min(left.minimum_symbol, right.minimum_symbol),
            serial,
            left,
            right,
        )
        heapq.heappush(
            heap,
            (node.frequency, node.minimum_symbol, node.serial, node),
        )
        serial += 1

    return heap[0][3], False


def _build_codes(root: _TreeNode, single_symbol: bool) -> Tuple[HuffmanCode, ...]:
    if single_symbol:
        if root.symbol is None:
            raise AssertionError("single-symbol Huffman root is not a leaf")
        return (HuffmanCode(root.symbol, (0,)),)

    codes: Dict[int, Tuple[int, ...]] = {}

    def visit(node: _TreeNode, path: Tuple[int, ...]) -> None:
        if node.is_leaf:
            if node.symbol is None:
                raise AssertionError("leaf is missing its symbol")
            codes[node.symbol] = path
            return
        if node.left is None or node.right is None:
            raise AssertionError("internal node is missing a child")
        visit(node.left, path + (0,))
        visit(node.right, path + (1,))

    visit(root, ())
    return tuple(HuffmanCode(symbol, codes[symbol]) for symbol in sorted(codes))


def _serialize_tree(root: _TreeNode, single_symbol: bool) -> Tuple[Tuple[int, ...], int]:
    if single_symbol:
        if root.symbol is None:
            raise AssertionError("single-symbol Huffman root is not a leaf")
        nodes = (LEAF_MASK | root.symbol, 0)
        return nodes, 1

    nodes: List[int] = []

    def visit(node: _TreeNode) -> int:
        if node.is_leaf:
            if node.symbol is None:
                raise AssertionError("leaf is missing its symbol")
            index = len(nodes)
            nodes.append(LEAF_MASK | node.symbol)
            return index

        if node.left is None or node.right is None:
            raise AssertionError("internal node is missing a child")
        left_index = visit(node.left)
        right_index = visit(node.right)
        index = len(nodes)
        nodes.append((right_index << 16) | left_index)
        return index

    root_index = visit(root)
    if len(nodes) > MAX_NODE_COUNT:
        raise ValueError("Huffman node table exceeds 16-bit child indices")
    return tuple(nodes), root_index


def build_huffman_model(symbols: Iterable[int]) -> HuffmanModel:
    frequencies = build_frequency_table(symbols)
    root, single_symbol = _build_tree(frequencies)
    nodes, root_index = _serialize_tree(root, single_symbol)
    codes = _build_codes(root, single_symbol)
    return HuffmanModel(frequencies, nodes, root_index, codes)


def compress_symbols(
    symbols: Iterable[int],
    code_table: Mapping[int, Sequence[int]],
) -> Tuple[bytes, int]:
    """Compress one message, restarting at bit zero for byte alignment."""

    output = bytearray()
    current_byte = 0
    used_bits = 0
    total_bits = 0

    for symbol in symbols:
        if symbol not in code_table:
            raise ValueError("symbol 0x{:04X} is absent from the code table".format(symbol))
        bits = code_table[symbol]
        if not bits:
            raise ValueError("empty Huffman code is not encodable")
        for bit in bits:
            if bit not in (0, 1):
                raise ValueError("Huffman code bits must be zero or one")
            current_byte |= bit << used_bits
            used_bits += 1
            total_bits += 1
            if used_bits == 8:
                output.append(current_byte)
                current_byte = 0
                used_bits = 0

    if used_bits:
        output.append(current_byte)
    return bytes(output), total_bits


def _decode_result(
    status: DecodeStatus,
    output: bytearray,
    byte_index: int,
    bit_index: int,
) -> DecodeResult:
    consumed = byte_index + (1 if bit_index else 0)
    return DecodeResult(status, bytes(output), len(output), consumed)


def decompress_bounded(
    nodes: Sequence[int],
    node_count: int,
    root_index: int,
    compressed: bytes,
    input_length: int,
    input_bit_length: int,
    output_capacity: int,
) -> DecodeResult:
    """Decode exactly the declared meaningful bits with explicit bounds."""

    output = bytearray()
    byte_index = 0
    bit_index = 0

    if (
        node_count <= 0
        or node_count > MAX_NODE_COUNT
        or node_count > len(nodes)
        or input_length < 0
        or input_length > len(compressed)
        or input_bit_length < 0
        or input_bit_length > input_length * 8
        or output_capacity < 0
    ):
        return _decode_result(
            DecodeStatus.INVALID_ARGUMENT, output, byte_index, bit_index
        )
    if root_index < 0 or root_index >= node_count:
        return _decode_result(DecodeStatus.INVALID_ROOT, output, byte_index, bit_index)
    if nodes[root_index] & LEAF_MASK == LEAF_MASK:
        return _decode_result(DecodeStatus.INVALID_ROOT, output, byte_index, bit_index)

    current_index = root_index
    while True:
        if byte_index * 8 + bit_index >= input_bit_length:
            status = (
                DecodeStatus.MISSING_TERMINATOR
                if current_index == root_index
                else DecodeStatus.TRUNCATED_INPUT
            )
            return _decode_result(status, output, byte_index, bit_index)

        word = nodes[current_index]
        if word & LEAF_MASK == LEAF_MASK:
            return _decode_result(
                DecodeStatus.INVALID_NODE, output, byte_index, bit_index
            )

        bit = (compressed[byte_index] >> bit_index) & 1
        bit_index += 1
        if bit_index == 8:
            bit_index = 0
            byte_index += 1

        child_index = (word >> 16) & 0xFFFF if bit else word & 0xFFFF
        if child_index >= node_count:
            return _decode_result(
                DecodeStatus.INVALID_NODE, output, byte_index, bit_index
            )

        current_index = child_index
        word = nodes[current_index]
        if word & LEAF_MASK != LEAF_MASK:
            continue

        symbol = word & 0xFFFF
        low = symbol & 0xFF
        high = (symbol >> 8) & 0xFF
        needed = 2 if high else 1

        if high and low == 0:
            return _decode_result(
                DecodeStatus.INVALID_SYMBOL, output, byte_index, bit_index
            )
        if output_capacity - len(output) < needed:
            return _decode_result(
                DecodeStatus.OUTPUT_OVERFLOW, output, byte_index, bit_index
            )

        output.append(low)
        if high:
            output.append(high)
        elif low == 0:
            status = (
                DecodeStatus.OK
                if byte_index * 8 + bit_index == input_bit_length
                else DecodeStatus.TRAILING_DATA
            )
            return _decode_result(status, output, byte_index, bit_index)

        current_index = root_index


def _validate_message(message: bytes) -> None:
    if not message or message[-1] != 0:
        raise ValueError("present catalog messages must end with NUL")
    if b"\x00" in message[:-1]:
        raise ValueError("present catalog messages cannot contain an interior NUL")


def _framed_hash(messages: Sequence[Optional[bytes]]) -> str:
    digest = hashlib.sha256()
    for message in messages:
        if message is None:
            digest.update(b"\x00")
        else:
            digest.update(b"\x01")
            digest.update(struct.pack("<I", len(message)))
            digest.update(message)
    return digest.hexdigest()


def _node_table_hash(nodes: Sequence[int]) -> str:
    digest = hashlib.sha256()
    for node in nodes:
        digest.update(struct.pack("<I", node))
    return digest.hexdigest()


def build_catalog(
    messages: Sequence[Optional[bytes]],
    suffix_share: bool = False,
) -> Catalog:
    """Build one deterministic catalog.

    ``None`` is a null pointer/absent entry. If suffix sharing is enabled, a
    compressed message may point into the immediately preceding present
    message only when it is a strictly shorter byte suffix.
    """

    normalized: List[Optional[bytes]] = []
    all_symbols: List[int] = []
    packed_messages: List[Optional[Tuple[int, ...]]] = []

    for message in messages:
        if message is None:
            normalized.append(None)
            packed_messages.append(None)
            continue
        if not isinstance(message, bytes):
            raise TypeError("catalog messages must be bytes or None")
        _validate_message(message)
        symbols = pack_bytes(message)
        if unpack_symbols(symbols) != message:
            raise AssertionError("byte packing failed to round-trip")
        normalized.append(message)
        packed_messages.append(symbols)
        all_symbols.extend(symbols)

    if not all_symbols:
        empty_hash = _framed_hash(normalized)
        budget = CatalogBudget(
            symbol_count=0,
            node_count=0,
            node_bytes=0,
            compressed_bytes=0,
            pointer_bytes=len(messages) * POINTER_SIZE,
            max_decoded_bytes=0,
            source_sha256=empty_hash,
            round_trip_sha256=empty_hash,
            compressed_sha256=hashlib.sha256(b"").hexdigest(),
            node_table_sha256=hashlib.sha256(b"").hexdigest(),
        )
        return Catalog(
            tuple(CatalogEntry.absent() for _ in messages),
            b"",
            None,
            budget,
        )

    model = build_huffman_model(all_symbols)
    code_map = model.code_map()
    compressed_messages: List[Optional[bytes]] = []
    bit_lengths: List[int] = []

    for symbols in packed_messages:
        if symbols is None:
            compressed_messages.append(None)
            bit_lengths.append(0)
        else:
            compressed, bit_length = compress_symbols(symbols, code_map)
            compressed_messages.append(compressed)
            bit_lengths.append(bit_length)

    blob = bytearray()
    entries: List[CatalogEntry] = []
    previous_compressed: Optional[bytes] = None
    previous_entry: Optional[CatalogEntry] = None
    previous_index: Optional[int] = None

    for index, message in enumerate(normalized):
        compressed = compressed_messages[index]
        if message is None or compressed is None:
            entries.append(CatalogEntry.absent())
            previous_compressed = None
            previous_entry = None
            previous_index = None
            continue

        shared_from = None
        if (
            suffix_share
            and previous_compressed is not None
            and previous_entry is not None
            and previous_entry.pointer_offset is not None
            and len(compressed) < len(previous_compressed)
            and previous_compressed.endswith(compressed)
        ):
            pointer_offset = (
                previous_entry.pointer_offset
                + len(previous_compressed)
                - len(compressed)
            )
            shared_from = previous_index
        else:
            pointer_offset = len(blob)
            blob.extend(compressed)

        entries.append(
            CatalogEntry(
                present=True,
                pointer_offset=pointer_offset,
                compressed_size=len(compressed),
                bit_length=bit_lengths[index],
                decoded_size=len(message),
                shared_from=shared_from,
                decoded_sha256=hashlib.sha256(message).hexdigest(),
            )
        )
        previous_compressed = compressed
        previous_entry = entries[-1]
        previous_index = index

    round_trip: List[Optional[bytes]] = []
    for index, message in enumerate(normalized):
        entry = entries[index]
        if message is None:
            round_trip.append(None)
            continue
        if entry.pointer_offset is None:
            raise AssertionError("present entry is missing its pointer")
        encoded = bytes(
            blob[entry.pointer_offset:entry.pointer_offset + entry.compressed_size]
        )
        result = decompress_bounded(
            model.nodes,
            len(model.nodes),
            model.root_index,
            encoded,
            len(encoded),
            entry.bit_length,
            len(message),
        )
        if result.status != DecodeStatus.OK or result.data != message:
            raise AssertionError(
                "catalog message {} failed round-trip: {}".format(
                    index, result.status.name
                )
            )
        round_trip.append(result.data)

    source_hash = _framed_hash(normalized)
    round_trip_hash = _framed_hash(round_trip)
    if source_hash != round_trip_hash:
        raise AssertionError("catalog round-trip hash mismatch")

    budget = CatalogBudget(
        symbol_count=len(model.frequencies),
        node_count=len(model.nodes),
        node_bytes=len(model.nodes) * 4,
        compressed_bytes=len(blob),
        pointer_bytes=len(messages) * POINTER_SIZE,
        max_decoded_bytes=max(len(message) for message in normalized if message is not None),
        source_sha256=source_hash,
        round_trip_sha256=round_trip_hash,
        compressed_sha256=hashlib.sha256(blob).hexdigest(),
        node_table_sha256=_node_table_hash(model.nodes),
    )
    return Catalog(tuple(entries), bytes(blob), model, budget)
