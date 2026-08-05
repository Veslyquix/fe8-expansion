import json
import re
import unittest
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MSG_DATA = ROOT / "src" / "msg_data.c"
MAPPING = ROOT / "texts" / "locales" / "mapping" / "fe8u_target_map.json"
INPUT_LIMIT = 0x1000
OUTPUT_LIMIT = 0x1000
LEAF_MASK = 0xFFFF0000
LEGACY_REPLACEMENTS = {
    0x7F: b"-",
    0x93: b'"',
    0x94: b'"',
    0xE9: b"e",
}
LEGACY_SPACE = b"\x81\x40"
UTF8_SPACE = "\u3000".encode("utf-8")


def _decode(nodes, root_index, data):
    current = root_index
    byte_index = 0
    bit_index = 8
    output = bytearray()
    input_byte = 0

    while True:
        steps = 0
        while True:
            if steps >= len(nodes):
                return None
            steps += 1
            node = nodes[current]
            if node & LEAF_MASK == LEAF_MASK:
                return None

            if bit_index == 8:
                if byte_index >= len(data) or byte_index >= INPUT_LIMIT:
                    return None
                input_byte = data[byte_index]
                byte_index += 1
                bit_index = 0

            if (input_byte >> bit_index) & 1:
                child_index = (node >> 16) & 0xFFFF
            else:
                child_index = node & 0xFFFF
            bit_index += 1
            if child_index >= len(nodes):
                return None
            current = child_index
            node = nodes[current]
            if node & LEAF_MASK == LEAF_MASK:
                break

        symbol = node & 0xFFFF
        low = symbol & 0xFF
        high = (symbol >> 8) & 0xFF
        if high and low == 0:
            return None
        if len(output) + (2 if high else 1) > OUTPUT_LIMIT:
            return None

        output.append(low)
        if high:
            output.append(high)
        elif low == 0:
            return bytes(output)
        current = root_index


def _legacy_tokens(data):
    tokens = []
    index = 0
    while index < len(data):
        byte = data[index]
        if byte == 0:
            return tokens
        if byte < 0x20:
            length = 3 if byte == 0x10 else 1
            if index + length > len(data) - 1:
                raise AssertionError("truncated legacy control")
            index += length
            continue
        if byte == 0x80:
            if index + 2 > len(data) - 1:
                raise AssertionError("truncated extended control")
            index += 2
            continue
        if data[index : index + 2] == LEGACY_SPACE:
            tokens.append(LEGACY_SPACE)
            index += 2
            continue
        if byte >= 0x7F:
            tokens.append(bytes((byte,)))
        index += 1
    raise AssertionError("legacy stream has no terminator")


def _normalize_fallback(data):
    output = bytearray()
    state = "text"

    for byte in data:
        if state == "face-low":
            if byte == 0:
                return None
            output.append(byte)
            state = "face-high"
            continue
        if state in ("face-high", "extended"):
            if byte == 0:
                return None
            output.append(byte)
            state = "text"
            continue
        if state == "space":
            if byte != 0x40:
                return None
            output.extend(UTF8_SPACE)
            state = "text"
            continue

        if byte == 0:
            output.append(0)
            return bytes(output)
        if byte < 0x20:
            output.append(byte)
            if byte == 0x10:
                state = "face-low"
            continue
        if byte < 0x7F:
            output.append(byte)
            continue
        if byte in LEGACY_REPLACEMENTS:
            output.extend(LEGACY_REPLACEMENTS[byte])
            continue
        if byte == 0x80:
            output.append(byte)
            state = "extended"
            continue
        if byte == 0x81:
            state = "space"
            continue
        return None
    return None


def _is_renderer_valid(data):
    index = 0
    while index < len(data):
        first = data[index]
        if first == 0:
            return index == len(data) - 1
        if first < 0x20:
            length = 3 if first == 0x10 else 1
            if index + length > len(data) - 1:
                return False
            index += length
            continue
        if first < 0x7F:
            index += 1
            continue
        if first == 0x7F:
            return False
        if first == 0x80:
            if index + 2 > len(data) - 1 or data[index + 1] == 0:
                return False
            index += 2
            continue

        if 0xC2 <= first <= 0xDF:
            length = 2
        elif 0xE0 <= first <= 0xEF:
            length = 3
        elif 0xF0 <= first <= 0xF4:
            length = 4
        else:
            return False
        if index + length > len(data) - 1:
            return False
        continuation = data[index + 1 : index + length]
        if any(byte < 0x80 or byte > 0xBF for byte in continuation):
            return False
        second = continuation[0]
        if (
            (first == 0xE0 and second < 0xA0)
            or (first == 0xED and second >= 0xA0)
            or (first == 0xF0 and second < 0x90)
            or (first == 0xF4 and second >= 0x90)
        ):
            return False
        index += length
    return False


class EnglishFallbackBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = MSG_DATA.read_text(encoding="utf-8")
        node_match = re.search(
            r"const u32 gMsgHuffmanTable\[\] =\s*\{(.*?)\};\s*"
            r"const u32 \* const gMsgHuffmanTableRoot",
            text,
            re.DOTALL,
        )
        root_match = re.search(
            r"gMsgHuffmanTableRoot = gMsgHuffmanTable \+ (0x[0-9A-Fa-f]+)",
            text,
        )
        table_match = re.search(
            r"const u8 \* const gMsgTable\[\] =\s*\{(.*?)\};",
            text,
            re.DOTALL,
        )
        if node_match is None or root_match is None or table_match is None:
            raise AssertionError("could not parse committed English catalog")

        cls.nodes = [
            int(value, 16)
            for value in re.findall(r"0x[0-9A-Fa-f]+", node_match.group(1))
        ]
        cls.root_index = int(root_match.group(1), 16)
        cls.arrays = {
            name: bytes(
                int(value, 16)
                for value in re.findall(r"0x[0-9A-Fa-f]+", body)
            )
            for name, body in re.findall(
                r"static const u8 (CompressedText_MSG_[A-Z0-9_]+)\[\] = "
                r"\{([^}]*)\};",
                text,
            )
        }
        cls.table = re.findall(
            r"CompressedText_MSG_[A-Z0-9_]+", table_match.group(1)
        )
        rows = json.loads(MAPPING.read_text(encoding="utf-8"))["rows"]
        cls.explicit_fallback_ids = [
            int(row["target_id"], 16)
            for row in rows
            if row["source"]["kind"] == "english_fallback"
        ]

    def test_committed_english_catalog_fits_bounded_fallback_decoder(self):
        numeric_table = self.table[:0xD4C]
        numeric_arrays = {name: self.arrays[name] for name in numeric_table}

        self.assertEqual(self.root_index + 1, len(self.nodes))
        self.assertEqual(set(numeric_table), set(numeric_arrays))

        max_input = 0
        max_output = 0
        for name in numeric_table:
            data = numeric_arrays[name]
            decoded = _decode(self.nodes, self.root_index, data)
            self.assertIsNotNone(decoded, name)
            max_input = max(max_input, len(data))
            max_output = max(max_output, len(decoded))

        self.assertLessEqual(max_input, INPUT_LIMIT)
        self.assertLessEqual(max_output, OUTPUT_LIMIT)
        self.assertGreater(max_output, 0x555)

    def test_full_legacy_corpus_printable_encoding_inventory_is_complete(self):
        token_counts = Counter()
        token_ids = defaultdict(set)

        for msg_id, name in enumerate(self.table[:0xD4C]):
            decoded = _decode(self.nodes, self.root_index, self.arrays[name])
            self.assertIsNotNone(decoded, name)
            for token in _legacy_tokens(decoded):
                token_counts[token] += 1
                token_ids[token].add(msg_id)

        self.assertEqual(
            token_counts,
            Counter({b"\x7f": 34, b"\x93": 95, b"\x94": 95, b"\xe9": 1}),
        )
        self.assertEqual(token_ids[b"\xe9"], {0xD0E})
        self.assertNotIn(LEGACY_SPACE, token_counts)

    def test_every_explicit_fallback_normalizes_to_renderer_valid_input(self):
        self.assertEqual(len(self.explicit_fallback_ids), 1828)
        token_counts = Counter()
        token_ids = defaultdict(set)

        for msg_id in self.explicit_fallback_ids:
            compressed = b"".join(
                self.arrays[name] for name in self.table[msg_id:]
            )[:INPUT_LIMIT]
            decoded = _decode(self.nodes, self.root_index, compressed)
            self.assertIsNotNone(decoded, f"MSG_{msg_id:03X}")
            for token in _legacy_tokens(decoded):
                token_counts[token] += 1
                token_ids[token].add(msg_id)
            normalized = _normalize_fallback(decoded)
            self.assertIsNotNone(normalized, f"MSG_{msg_id:03X}")
            self.assertTrue(_is_renderer_valid(normalized), f"MSG_{msg_id:03X}")

        self.assertEqual(
            token_counts,
            Counter({b"\x7f": 28, b"\x93": 8, b"\x94": 8}),
        )
        self.assertEqual(
            token_ids[b"\x93"],
            {0x633, 0x809, 0xAF5, 0xAFB, 0xB88, 0xC10, 0xC12},
        )
        self.assertEqual(token_ids[b"\x93"], token_ids[b"\x94"])

    def test_msg_809_and_supported_spacing_normalize_without_missing_glyphs(self):
        decoded = _decode(
            self.nodes, self.root_index, self.arrays[self.table[0x809]]
        )
        self.assertIsNotNone(decoded)
        normalized = _normalize_fallback(decoded)
        self.assertIn(b'Rich "Merchant"', normalized)
        self.assertTrue(_is_renderer_valid(normalized))

        spacing = _normalize_fallback(b"A\x81\x40B\x00")
        self.assertEqual(spacing, b"A" + UTF8_SPACE + b"B\x00")
        self.assertTrue(_is_renderer_valid(spacing))


if __name__ == "__main__":
    unittest.main()
