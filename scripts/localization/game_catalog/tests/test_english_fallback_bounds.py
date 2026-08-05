import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MSG_DATA = ROOT / "src" / "msg_data.c"
INPUT_LIMIT = 0x1000
OUTPUT_LIMIT = 0x1000
LEAF_MASK = 0xFFFF0000


class EnglishFallbackBoundsTests(unittest.TestCase):
    def test_committed_english_catalog_fits_bounded_fallback_decoder(self):
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
        self.assertIsNotNone(node_match)
        self.assertIsNotNone(root_match)
        self.assertIsNotNone(table_match)

        nodes = [
            int(value, 16)
            for value in re.findall(r"0x[0-9A-Fa-f]+", node_match.group(1))
        ]
        root_index = int(root_match.group(1), 16)
        arrays = {
            name: bytes(
                int(value, 16)
                for value in re.findall(r"0x[0-9A-Fa-f]+", body)
            )
            for name, body in re.findall(
                r"static const u8 (CompressedText_MSG_[0-9A-F]+)\[\] = "
                r"\{([^}]*)\};",
                text,
            )
        }
        table = re.findall(
            r"CompressedText_MSG_[0-9A-F]+", table_match.group(1)
        )

        self.assertEqual(root_index + 1, len(nodes))
        self.assertEqual(set(table), set(arrays))

        max_input = 0
        max_output = 0
        for name in table:
            data = arrays[name]
            current = root_index
            byte_index = 0
            bit_index = 8
            output_length = 0
            input_byte = 0
            terminated = False

            while not terminated:
                steps = 0
                while True:
                    self.assertLess(steps, len(nodes), name)
                    steps += 1
                    node = nodes[current]
                    self.assertNotEqual(node & LEAF_MASK, LEAF_MASK, name)

                    if bit_index == 8:
                        self.assertLess(byte_index, len(data), name)
                        input_byte = data[byte_index]
                        byte_index += 1
                        bit_index = 0

                    if (input_byte >> bit_index) & 1:
                        child_index = (node >> 16) & 0xFFFF
                    else:
                        child_index = node & 0xFFFF
                    bit_index += 1
                    self.assertLess(child_index, len(nodes), name)
                    current = child_index
                    node = nodes[current]
                    if (node & LEAF_MASK) == LEAF_MASK:
                        break

                symbol = node & 0xFFFF
                low = symbol & 0xFF
                high = (symbol >> 8) & 0xFF
                self.assertFalse(high and low == 0, name)
                output_length += 2 if high else 1
                if not high and low == 0:
                    terminated = True
                else:
                    current = root_index

            max_input = max(max_input, len(data))
            max_output = max(max_output, output_length)

        self.assertLessEqual(max_input, INPUT_LIMIT)
        self.assertLessEqual(max_output, OUTPUT_LIMIT)
        self.assertGreater(max_output, 0x555)


if __name__ == "__main__":
    unittest.main()
