import unittest

from scripts.generated_data.diagnostics import DiagnosticCollector, GeneratedDataError
from scripts.generated_data.supports import schema as supports_schema
from scripts.generated_data.tests._util import fixture_path


def _validate(fixture_name):
    records = supports_schema.load_records(fixture_path("supports", fixture_name))
    diagnostics = DiagnosticCollector()
    supports_schema.validate(records, diagnostics)
    return records, diagnostics


class SupportsSchemaValidTests(unittest.TestCase):
    def test_valid_fixture_has_no_diagnostics(self):
        records, diagnostics = _validate("valid.json")
        self.assertTrue(diagnostics.ok, msg=diagnostics.render())
        self.assertEqual(len(records), 3)


class SupportsSchemaDuplicateTests(unittest.TestCase):
    def test_duplicate_owner_detected(self):
        _, diagnostics = _validate("duplicate_owner.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("duplicate owner 'CHARACTER_EIRIKA'" in m for m in messages), messages)

    def test_duplicate_partner_detected(self):
        _, diagnostics = _validate("duplicate_partner.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("duplicate partner 'CHARACTER_SETH'" in m for m in messages), messages)


class SupportsSchemaReferenceTests(unittest.TestCase):
    def test_missing_character_reference_detected(self):
        _, diagnostics = _validate("missing_ref.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("undefined character reference 'CHARACTER_NOT_A_REAL_CHARACTER'" in m for m in messages),
            messages,
        )

    def test_self_reference_detected(self):
        _, diagnostics = _validate("self_reference.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("lists its own owner" in m for m in messages), messages)

    def test_event_autoload_slot_sentinels_rejected_as_partner(self):
        """CHARACTER_EVT_LEADER/ACTIVE/SLOTB/SLOT2 belong to the separate
        ``event_autoload_pid_idx`` enum (active-unit-slot indices, two of
        them negative) -- they share the ``CHARACTER_`` textual prefix
        with real designators but must never be accepted as a support
        partner."""
        _, diagnostics = _validate("char_evt_sentinels.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        for sentinel in (
            "CHARACTER_EVT_LEADER", "CHARACTER_EVT_ACTIVE", "CHARACTER_EVT_SLOTB", "CHARACTER_EVT_SLOT2",
        ):
            self.assertTrue(
                any("undefined character reference '{}'".format(sentinel) in m for m in messages),
                (sentinel, messages),
            )

    def test_synthetic_sibling_enum_collision_excluded(self):
        """Wiring-level proof (not just the shared reader in isolation):
        a support record whose owner is a synthetic-header primary-block
        member but whose partner is the sibling enum's
        ``CHARACTER_SIBLING_FAKE`` must be rejected."""
        records = supports_schema.load_records(fixture_path("supports", "valid.json"))
        records[0].characters = ["CHARACTER_SIBLING_FAKE"]
        records[0].owner = "CHARACTER_ALPHA"
        diagnostics = DiagnosticCollector()
        supports_schema.validate(
            records, diagnostics,
            characters_header=fixture_path("character_refs", "mini_characters_sibling_enum.h"),
        )
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("undefined character reference 'CHARACTER_SIBLING_FAKE'" in m for m in messages), messages
        )


class SupportsSchemaRangeTests(unittest.TestCase):
    def test_out_of_range_value_detected(self):
        _, diagnostics = _validate("out_of_range.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("supportExpBase 300 out of range [0, 255]" in m for m in messages), messages)


class SupportsSchemaCountTests(unittest.TestCase):
    def test_count_mismatch_detected(self):
        _, diagnostics = _validate("bad_count.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("does not match 2 partner entries" in m for m in messages), messages)

    def test_capacity_exceeded_detected(self):
        _, diagnostics = _validate("capacity_exceeded.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("support partners count 8 exceeds fixed capacity 7" in m for m in messages), messages
        )


class SupportsSchemaParallelLengthTests(unittest.TestCase):
    def test_mismatched_parallel_lengths_report_cleanly_without_crashing(self):
        """A short supportExpBase/Growth array must yield an actionable
        parallel-array diagnostic, never an uncaught IndexError in the
        reciprocal cross-check (regression: crash-to-diagnostic)."""
        _, diagnostics = _validate("mismatched_parallel_lengths.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("parallel arrays have mismatched lengths" in m for m in messages), messages
        )


class SupportsSchemaReciprocalTests(unittest.TestCase):
    def test_reciprocal_mismatch_detected(self):
        _, diagnostics = _validate("reciprocal_mismatch.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("reciprocal mismatch" in m for m in messages), messages)

    def test_reciprocal_missing_detected(self):
        _, diagnostics = _validate("reciprocal_missing.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("does not list 'CHARACTER_EIRIKA' back" in m for m in messages), messages
        )


class SupportsSchemaSourceLocationTests(unittest.TestCase):
    def test_diagnostics_reference_the_fixture_path(self):
        _, diagnostics = _validate("out_of_range.json")
        self.assertFalse(diagnostics.ok)
        for error in diagnostics.errors:
            self.assertIsNotNone(error.location)
            self.assertIn("out_of_range.json", str(error.location.path))
            self.assertGreaterEqual(error.location.line, 1)
            self.assertGreaterEqual(error.location.column, 1)


class UnitSupportMaxCountTests(unittest.TestCase):
    def test_reads_seven_from_types_header(self):
        self.assertEqual(supports_schema.read_unit_support_max_count(), 7)


if __name__ == "__main__":
    unittest.main()
