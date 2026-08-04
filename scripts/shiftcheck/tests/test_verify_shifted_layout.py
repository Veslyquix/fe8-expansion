"""Tests for exact modern shifted-layout verification."""

from __future__ import annotations

import unittest

from scripts.shiftcheck.verify_shifted_layout import (
    BANIM_OVERLAY_SPANS,
    PINNED_SYMBOL_ADDRESSES,
    SAVE_PALETTE_SPANS,
    verify_layout,
)


class VerifyShiftedLayoutTests(unittest.TestCase):
    def symbols(self):
        symbols = {
            "Init": 0x08000000,
            "__shift_start": 0x08000A20,
            "__shift_end": 0x08000A20,
            "ReadSramFast_Core": 0x08000A20,
            "__floating_end": 0x08B26F0C,
            **PINNED_SYMBOL_ADDRESSES,
        }
        cursor = 0x02000088
        for start, end, size in BANIM_OVERLAY_SPANS:
            symbols.setdefault(start, cursor)
            symbols[end] = symbols[start] + size
            cursor = symbols[end]
        cursor = 0x08600000
        for start, end, size in SAVE_PALETTE_SPANS:
            symbols.setdefault(start, cursor)
            symbols[end] = symbols[start] + size
            cursor = symbols[end]
        return symbols

    def test_exact_shift_passes(self):
        shift = 0x40000
        base = self.symbols()
        shifted = dict(base)
        shifted["__shift_end"] += shift
        shifted["ReadSramFast_Core"] += shift
        shifted["__floating_end"] += shift
        self.assertEqual(verify_layout(base, shifted, shift), [])

    def test_moved_pin_fails(self):
        shift = 0x40000
        base = self.symbols()
        shifted = dict(base)
        shifted["Init"] += shift
        shifted["__shift_end"] += shift
        shifted["ReadSramFast_Core"] += shift
        shifted["__floating_end"] += shift
        errors = verify_layout(base, shifted, shift)
        self.assertTrue(any("pinned symbol Init moved" in error for error in errors))

    def test_pre_shifted_base_fails(self):
        shift = 0x40000
        base = self.symbols()
        base["__shift_end"] += 0x100
        shifted = dict(base)
        shifted["__shift_end"] += shift
        shifted["ReadSramFast_Core"] += shift
        shifted["__floating_end"] += shift
        errors = verify_layout(base, shifted, shift)
        self.assertTrue(any("base ELF is already shifted" in error for error in errors))

    def test_wrong_battle_table_pin_fails(self):
        shift = 0x40000
        base = self.symbols()
        base["banim_data"] -= 0x1000
        shifted = dict(base)
        shifted["__shift_end"] += shift
        shifted["ReadSramFast_Core"] += shift
        shifted["__floating_end"] += shift
        errors = verify_layout(base, shifted, shift)
        self.assertTrue(
            any(
                "base pinned symbol banim_data" in error
                and "expected 0x08c00008" in error
                for error in errors
            )
        )

    def test_reordered_battle_overlay_fails(self):
        shift = 0x40000
        base = self.symbols()
        base["gBanimOamr2"] = base["gBanimOaml"] - 0x5800
        shifted = dict(base)
        shifted["__shift_end"] += shift
        shifted["ReadSramFast_Core"] += shift
        shifted["__floating_end"] += shift
        errors = verify_layout(base, shifted, shift)
        self.assertTrue(
            any(
                "base relative span gBanimOaml->gBanimOamr2" in error
                for error in errors
            )
        )

    def test_padded_save_palette_span_fails(self):
        shift = 0x40000
        base = self.symbols()
        base["gPal_SaveSlotHardSelectedBlendA"] += 2
        shifted = dict(base)
        shifted["__shift_end"] += shift
        shifted["ReadSramFast_Core"] += shift
        shifted["__floating_end"] += shift
        errors = verify_layout(base, shifted, shift)
        self.assertTrue(
            any(
                "base relative span "
                "Pal_ChapterTitleAlt->gPal_SaveSlotHardSelectedBlendA"
                in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
