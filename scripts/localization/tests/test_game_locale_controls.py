import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization.game_locales.controls import (
    FE8CN_NAMED_CONTROL_ALIASES,
    SOURCE_DIALECT_CHINESE,
    SOURCE_DIALECT_JAPANESE,
    ControlSyntaxError,
    canonical_control_token,
    expand_canonical_control,
    expand_canonical_control_bytes,
    expand_canonical_controls,
    expand_canonical_controls_bytes,
    expand_canonical_text,
    normalize_source_controls,
    validate_canonical_text,
)


class GameLocaleControlTests(unittest.TestCase):
    ALIASES = {
        "LF": (0x0001,),
        "Pair": (0x0080, 0x0020),
    }

    def test_source_spellings_and_named_aliases_share_one_canonical_grammar(self):
        self.assertEqual(
            normalize_source_controls(
                "日[$1234][LF][Pair]",
                dialect=SOURCE_DIALECT_JAPANESE,
                aliases=self.ALIASES,
            ),
            "日[CTRL:1234][CTRL:0001][CTRL:0080][CTRL:0020]",
        )
        self.assertEqual(
            normalize_source_controls(
                "中[0x007][0x1234][LF]",
                dialect=SOURCE_DIALECT_CHINESE,
                aliases=self.ALIASES,
            ),
            "中[CTRL:0007][CTRL:1234][CTRL:0001]",
        )
        self.assertEqual(
            normalize_source_controls(
                "[Clear][Buy/Sell][Tact]",
                dialect=SOURCE_DIALECT_CHINESE,
                aliases=FE8CN_NAMED_CONTROL_ALIASES,
            ),
            "[CTRL:0002][CTRL:001A][CTRL:0080][CTRL:0020]",
        )

    def test_canonical_tokens_expand_to_exact_u16_and_little_endian_bytes(self):
        self.assertEqual(canonical_control_token(0x1234), "[CTRL:1234]")
        self.assertEqual(expand_canonical_control("[CTRL:1234]"), 0x1234)
        self.assertEqual(
            expand_canonical_control_bytes("[CTRL:1234]"),
            b"\x34\x12",
        )
        self.assertEqual(
            expand_canonical_text("A[CTRL:0001][CTRL:1234]B"),
            ("A", 0x0001, 0x1234, "B"),
        )
        self.assertEqual(
            expand_canonical_controls("[CTRL:0080][CTRL:0020]"),
            (0x0080, 0x0020),
        )
        self.assertEqual(
            expand_canonical_controls_bytes("[CTRL:0080][CTRL:0020]"),
            b"\x80\x00\x20\x00",
        )
        with self.assertRaisesRegex(ControlSyntaxError, "must not contain payload"):
            expand_canonical_controls("text[CTRL:0001]")

    def test_unknown_and_malformed_marker_like_tokens_are_rejected(self):
        for token in (
            "[Unknown]",
            "[0001]",
            "[CTRL:001]",
            "[CTRL:000g]",
            "[0x01]",
            "[$001]",
            "[CTRL:0001",
            "CTRL:0001]",
        ):
            with self.subTest(token=token):
                with self.assertRaises(ControlSyntaxError):
                    normalize_source_controls(
                        token,
                        dialect=SOURCE_DIALECT_CHINESE,
                        aliases=self.ALIASES,
                    )

    def test_canonical_validator_rejects_all_legacy_or_unknown_spellings(self):
        validate_canonical_text("text[CTRL:0001]")
        for text in ("[LF]", "[$0001]", "[0x001]", "[0001]"):
            with self.subTest(text=text):
                with self.assertRaises(ControlSyntaxError):
                    validate_canonical_text(text)


if __name__ == "__main__":
    unittest.main()
