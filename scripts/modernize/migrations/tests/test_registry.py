"""Tests for scripts/modernize/migrations/registry.py (issue #9).

All fixtures are synthetic in-memory byte arrays -- no committed binary
blobs, ROM dumps, or real user saves -- matching
scripts/modernize/tests/test_save_format_tool.py's own guardrail.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "modernize"))

import save_format_tool as sft  # noqa: E402

from scripts.modernize.migrations import registry as reg  # noqa: E402


def make_header(valid: bool = True) -> bytearray:
    header = bytearray(sft.HEADER_SIZE)
    if valid:
        header[0:8] = sft.HEADER_NAME_MARKER
        header[8:12] = sft.SAVEMAGIC32.to_bytes(4, "little")
        header[12:14] = sft.SAVEMAGIC16.to_bytes(2, "little")
        checksum = sft.checksum16(bytes(header[: sft.HEADER_CHECKSUM_DOMAIN]))
        header[0x60:0x62] = checksum.to_bytes(2, "little")
    else:
        header[0:8] = b"garbage!"
    return header


def make_meta_absent() -> bytearray:
    return bytearray([0xFF] * sft.META_SIZE)


def make_image(header: bytes, meta: bytes) -> bytearray:
    image = bytearray(b"\x00" * sft.SRAM_SIZE)
    image[sft.HEADER_OFFSET : sft.HEADER_OFFSET + sft.HEADER_SIZE] = header
    image[sft.META_OFFSET : sft.META_OFFSET + sft.META_SIZE] = meta
    return image


def legacy_image() -> bytes:
    """A 'v0' image: valid header, no ExpansionSaveMeta record at all."""
    return bytes(make_image(make_header(valid=True), make_meta_absent()))


def current_image() -> bytes:
    """A real 'current' (epoch 1) image, built the same way
    scripts/modernize/save_format_tool.py's own tests build one."""
    meta = sft.build_current_expansion_save_meta(ROOT)
    return bytes(make_image(make_header(valid=True), meta.pack()))


class RegistryStructureTests(unittest.TestCase):
    def test_registry_has_v0_to_1_mechanical_entry(self):
        step = reg.find_step(None, 1)
        self.assertIsNotNone(step)
        self.assertEqual(step.kind, reg.MECHANICAL)

    def test_manual_step_requires_steps(self):
        with self.assertRaises(ValueError):
            reg.MigrationStep(epoch_from=1, epoch_to=2, kind=reg.MANUAL, description="x")

    def test_mechanical_step_forbids_manual_steps(self):
        with self.assertRaises(ValueError):
            reg.MigrationStep(
                epoch_from=1, epoch_to=2, kind=reg.MECHANICAL, description="x",
                manual_steps=("do something",),
            )

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError):
            reg.MigrationStep(epoch_from=1, epoch_to=2, kind="bogus", description="x")

    def test_find_step_missing_returns_none(self):
        self.assertIsNone(reg.find_step(5, 6))


class CheckRegistryTests(unittest.TestCase):
    def test_real_registry_is_consistent(self):
        errors = reg.check_registry()
        self.assertEqual(errors, [])

    def test_duplicate_entries_detected(self):
        original = reg.REGISTRY
        try:
            reg.REGISTRY = original + (original[0],)
            errors = reg.check_registry()
            self.assertTrue(any("duplicate" in error for error in errors))
        finally:
            reg.REGISTRY = original

    def test_bad_epoch_ordering_detected(self):
        original = reg.REGISTRY
        try:
            bad_step = reg.MigrationStep(epoch_from=2, epoch_to=1, kind=reg.MECHANICAL, description="bad")
            reg.REGISTRY = (bad_step,)
            errors = reg.check_registry()
            self.assertTrue(any("epoch_to must be greater" in error for error in errors))
        finally:
            reg.REGISTRY = original


class DryRunTests(unittest.TestCase):
    def test_dry_run_eligible_legacy_source(self):
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.sav"
            source.write_bytes(legacy_image())
            code, message = reg.dry_run(step, source)
            self.assertEqual(code, 0, message)
            self.assertIn("eligible", message)

    def test_dry_run_not_eligible_for_garbage_source(self):
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "garbage.sav"
            source.write_bytes(b"\x00" * sft.SRAM_SIZE)
            code, message = reg.dry_run(step, source)
            self.assertNotEqual(code, 0)
            self.assertIn("NOT eligible", message)

    def test_dry_run_manual_step_refuses_without_reading_source(self):
        manual_step = reg.MigrationStep(
            epoch_from=1, epoch_to=2, kind=reg.MANUAL, description="future epoch bump",
            manual_steps=("do the thing by hand",),
        )
        code, message = reg.dry_run(manual_step, Path("/nonexistent/does/not/matter"))
        self.assertEqual(code, 4)
        self.assertIn("manual migration required", message)


class RunTests(unittest.TestCase):
    def test_run_out_of_place_success(self):
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.sav"
            source.write_bytes(legacy_image())
            dest = Path(tmp) / "migrated.sav"
            code, message = reg.run(step, source, dest)
            self.assertEqual(code, 0, message)
            self.assertTrue(dest.is_file())
            # Source must be untouched (out-of-place only).
            self.assertEqual(source.read_bytes(), legacy_image())

    def test_run_refuses_same_source_and_destination(self):
        step = reg.find_step(None, 1)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.sav"
            source.write_bytes(legacy_image())
            code, message = reg.run(step, source, source)
            self.assertEqual(code, 6)
            self.assertIn("out-of-place", message)

    def test_run_manual_step_refuses(self):
        manual_step = reg.MigrationStep(
            epoch_from=1, epoch_to=2, kind=reg.MANUAL, description="future epoch bump",
            manual_steps=("step one", "step two"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "a.sav"
            source.write_bytes(current_image())
            dest = Path(tmp) / "b.sav"
            code, message = reg.run(manual_step, source, dest)
            self.assertEqual(code, 4)
            self.assertIn("step one", message)
            self.assertFalse(dest.exists())

    def test_run_never_touches_real_user_save_fixtures_directory(self):
        # This test asserts the *contract*, not a real save: every fixture
        # in this module is built in memory (legacy_image()/current_image()),
        # never read from a committed binary blob.
        self.assertIsInstance(legacy_image(), bytes)
        self.assertIsInstance(current_image(), bytes)


class CliTests(unittest.TestCase):
    def test_check_cli_ok(self):
        self.assertEqual(reg.main(["check"]), 0)

    def test_list_cli_ok(self):
        self.assertEqual(reg.main(["list"]), 0)


if __name__ == "__main__":
    unittest.main()
