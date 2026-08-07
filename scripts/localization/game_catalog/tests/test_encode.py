import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from scripts.localization.game_catalog.build import encode_canonical_text
from scripts.localization.game_catalog.model import GameCatalogError


class EncodeCanonicalTextTests(unittest.TestCase):
    def test_literal_utf8_and_canonical_controls_use_engine_byte_stream(self):
        self.assertEqual(
            encode_canonical_text("A[CTRL:0080][CTRL:0020]中[CTRL:0165]"),
            b"A\x80\x20" + "中".encode("utf-8") + b"\x65\x01\x00",
        )

    def test_unknown_and_malformed_controls_are_rejected(self):
        for text in ("[LF]", "[CTRL:001]", "[CTRL:ZZZZ]", "[CTRL:0001"):
            with self.subTest(text=text):
                with self.assertRaises(GameCatalogError):
                    encode_canonical_text(text)

    def test_embedded_nul_literal_and_zero_emitting_controls_are_rejected(self):
        with self.assertRaisesRegex(GameCatalogError, "embedded NUL"):
            encode_canonical_text("bad\x00text")
        with self.assertRaisesRegex(GameCatalogError, "embedded NUL"):
            encode_canonical_text("[CTRL:0000]")
        with self.assertRaisesRegex(GameCatalogError, "embedded NUL"):
            encode_canonical_text("[CTRL:0100]")


if __name__ == "__main__":
    unittest.main()
