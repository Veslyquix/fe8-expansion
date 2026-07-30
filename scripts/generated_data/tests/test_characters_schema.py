import unittest

from scripts.generated_data.diagnostics import DiagnosticCollector, GeneratedDataError
from scripts.generated_data import character_refs
from scripts.generated_data.characters import schema as characters_schema
from scripts.generated_data.tests._util import fixture_path

_MINI_BMUNIT_HEADER = fixture_path("characters", "mini_bmunit.h")
_MINI_MSG_HEADER = fixture_path("characters", "mini_msg.h")
_MINI_PORTRAIT_SOURCE = fixture_path("characters", "mini_portrait_data.c")
_MINI_FACE_SOURCE = fixture_path("characters", "mini_face.c")


class _FakeClassRecord:
    """Minimal stand-in for ``classes.schema.ClassRecord`` -- only the
    ``class_name`` attribute characters' ``validate()`` reads."""

    def __init__(self, class_name):
        self.class_name = class_name


class _FakeSupportRecord:
    """Minimal stand-in for ``supports.schema.SupportRecord`` -- only the
    ``owner``/``symbol`` attributes characters' ``validate()`` reads."""

    def __init__(self, owner, symbol):
        self.owner = owner
        self.symbol = symbol


def _validate(fixture_name, dependency_records=None, **overrides):
    records = characters_schema.load_records(fixture_path("characters", fixture_name))
    diagnostics = DiagnosticCollector()
    characters_schema.validate(records, diagnostics, dependency_records=dependency_records, **overrides)
    return records, diagnostics


class CharactersSchemaValidTests(unittest.TestCase):
    def test_valid_fixture_has_no_diagnostics(self):
        records, diagnostics = _validate("valid.json")
        self.assertTrue(diagnostics.ok, msg=diagnostics.render())
        self.assertEqual(len(records), 3)

    def test_derived_number_matches_designator(self):
        records, _ = _validate("valid.json")
        by_key = {r.key_repr(): r for r in records}
        eirika = by_key["character=CHARACTER_EIRIKA"]
        self.assertEqual(eirika.designator(character_refs.read_character_designators()), 1)
        self.assertEqual(eirika.resolved_number(character_refs.read_character_designators()), 1)

    def test_padding_slot_number_derives_to_zero(self):
        records, _ = _validate("valid.json")
        by_key = {r.key_repr(): r for r in records}
        padding = by_key["characterId=256"]
        characters_enum = character_refs.read_character_designators()
        self.assertEqual(padding.designator(characters_enum), 256)
        self.assertEqual(padding.resolved_number(characters_enum), 0)

    def test_raw_record_is_raw_symbolic_is_not(self):
        records, _ = _validate("valid.json")
        by_key = {r.key_repr(): r for r in records}
        self.assertFalse(by_key["character=CHARACTER_EIRIKA"].is_raw())
        self.assertTrue(by_key["characterId=27"].is_raw())

    def test_encoded_base_ranks_resolved(self):
        records, _ = _validate("valid.json")
        by_key = {r.key_repr(): r for r in records}
        eirika = by_key["character=CHARACTER_EIRIKA"]
        self.assertEqual(
            eirika.encoded_base_ranks(
                {"ITYPE_SWORD": (0, None), "ITYPE_LANCE": (1, None)},
                {"WPN_EXP_0": (0, None), "WPN_EXP_E": (1, None)},
                8,
            ),
            (1, 0, 0, 0, 0, 0, 0, 0),
        )


class CharactersSchemaStructuralTests(unittest.TestCase):
    def test_missing_both_keys_raises(self):
        with self.assertRaises(GeneratedDataError):
            characters_schema.load_records(fixture_path("characters", "missing_key.json"))

    def test_both_keys_raises(self):
        with self.assertRaises(GeneratedDataError):
            characters_schema.load_records(fixture_path("characters", "both_keys.json"))


class CharactersSchemaDuplicateTests(unittest.TestCase):
    def test_duplicate_symbolic_designator_detected(self):
        _, diagnostics = _validate("duplicate_symbolic.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("duplicate character designator 1" in m for m in messages), messages)

    def test_duplicate_raw_designator_detected(self):
        _, diagnostics = _validate("duplicate_raw.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("duplicate character designator 27" in m for m in messages), messages)

    def test_duplicate_cross_symbolic_and_raw_designator_detected(self):
        _, diagnostics = _validate("duplicate_cross.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("duplicate character designator 2" in m for m in messages), messages)


class CharactersSchemaCoverageTests(unittest.TestCase):
    def test_gap_in_full_coverage_detected(self):
        _, diagnostics = _validate("gap.json", designator_min=1, designator_max=3)
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("missing character coverage for designator 2" in m for m in messages), messages
        )

    def test_full_coverage_ok_has_no_gap_diagnostics(self):
        _, diagnostics = _validate("full_coverage_ok.json", designator_min=1, designator_max=3)
        self.assertTrue(diagnostics.ok, msg=diagnostics.render())

    def test_partial_source_without_full_coverage_flag_is_not_flagged_incomplete(self):
        # "valid.json" only authors 3 of the full 256 designators and leaves
        # fullCoverage at its default (false) -- confirms Batch 2a fixtures
        # are never penalized for incompleteness.
        _, diagnostics = _validate("valid.json")
        messages = [str(e) for e in diagnostics.errors]
        self.assertFalse(any("missing character coverage" in m for m in messages), messages)


class CharactersSchemaReferenceTests(unittest.TestCase):
    def test_character_none_rejected_as_designator(self):
        _, diagnostics = _validate("character_none.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("CHARACTER_NONE (0) cannot be used" in m for m in messages), messages)

    def test_bad_character_reference_detected(self):
        _, diagnostics = _validate("bad_character_ref.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("undefined character reference 'CHARACTER_NOT_A_REAL_CHARACTER'" in m for m in messages), messages
        )

    def test_event_autoload_slot_sentinels_rejected_as_designators(self):
        """CHARACTER_EVT_LEADER/ACTIVE/SLOTB/SLOT2 belong to the separate
        ``event_autoload_pid_idx`` enum (active-unit-slot indices, two of
        them negative) -- they share the ``CHARACTER_`` textual prefix
        with real designators but must never be accepted as one."""
        _, diagnostics = _validate("character_evt_sentinels.json")
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
        a record's own ``character`` designator from the synthetic
        sibling enum (``CHARACTER_SIBLING_FAKE``) must be rejected when
        ``characters_header`` is overridden to the mini fixture, while a
        real primary-block member of that same mini header
        (``CHARACTER_ALPHA``) is accepted."""
        _, diagnostics = _validate(
            "synthetic_sibling_enum.json",
            characters_header=fixture_path("character_refs", "mini_characters_sibling_enum.h"),
        )
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("undefined character reference 'CHARACTER_SIBLING_FAKE'" in m for m in messages), messages
        )

    def test_synthetic_primary_block_member_accepted(self):
        records = characters_schema.load_records(fixture_path("characters", "synthetic_sibling_enum.json"))
        records[0].character = "CHARACTER_ALPHA"
        diagnostics = DiagnosticCollector()
        characters_schema.validate(
            records, diagnostics,
            characters_header=fixture_path("character_refs", "mini_characters_sibling_enum.h"),
        )
        messages = [str(e) for e in diagnostics.errors]
        self.assertFalse(
            any("undefined character reference 'CHARACTER_ALPHA'" in m for m in messages), messages
        )
        _, diagnostics = _validate("bad_class_ref.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("undefined class reference 'CLASS_NOT_A_REAL_CLASS'" in m for m in messages), messages)

    def test_characterid_out_of_range_low_detected(self):
        _, diagnostics = _validate("characterid_out_of_range_low.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("characterId 0 out of range [1, 256]" in m for m in messages), messages)

    def test_characterid_out_of_range_high_detected(self):
        _, diagnostics = _validate("characterid_out_of_range_high.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("characterId 257 out of range [1, 256]" in m for m in messages), messages)

    def test_bad_affinity_reference_detected(self):
        _, diagnostics = _validate("bad_affinity.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("undefined affinity reference 'UNIT_AFFIN_NOT_REAL'" in m for m in messages), messages)

    def test_bad_attribute_detected(self):
        _, diagnostics = _validate("bad_attribute.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("undefined character attribute reference 'CA_NOT_A_REAL_FLAG'" in m for m in messages), messages
        )

    def test_duplicate_attribute_detected(self):
        _, diagnostics = _validate("duplicate_attribute.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("duplicate character attribute 'CA_LORD'" in m for m in messages), messages)

    def test_bad_base_ranks_itype_reference_detected(self):
        _, diagnostics = _validate("bad_base_ranks_itype_ref.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("undefined weapon type reference 'ITYPE_NOT_A_REAL_TYPE'" in m for m in messages), messages
        )

    def test_bad_base_ranks_wexp_reference_detected(self):
        _, diagnostics = _validate("bad_base_ranks_wexp_ref.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("undefined weapon-exp threshold reference 'WPN_EXP_NOT_REAL'" in m for m in messages), messages
        )


class CharactersSchemaRangeTests(unittest.TestCase):
    def test_bad_text_id_detected(self):
        # The upper bound is MSG_COUNT - 1, read live from
        # include/constants/msg.h -- never a copied literal, which would go
        # stale (and silently stop asserting the real bound) the moment the
        # text pipeline emits another message.
        from scripts.generated_data.items.schema import read_msg_count

        upper = read_msg_count() - 1
        _, diagnostics = _validate("bad_text_id.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        expected = "nameTextId 999999 out of range [0, {}]".format(upper)
        self.assertTrue(any(expected in m for m in messages), messages)

    def test_bad_portrait_detected(self):
        _, diagnostics = _validate("bad_portrait.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("portrait 99999 out of range [0, 171]" in m for m in messages), messages)

    def test_bad_mini_portrait_detected(self):
        _, diagnostics = _validate("bad_mini_portrait.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("miniPortrait 99 out of range [0, 7]" in m for m in messages), messages)

    def test_bad_base_stat_range_detected(self):
        _, diagnostics = _validate("bad_base_stat_range.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("hp 999 out of range [-128, 127]" in m for m in messages), messages)

    def test_bad_growth_range_detected(self):
        _, diagnostics = _validate("bad_growth_range.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("hp -5 out of range [0, 255]" in m for m in messages), messages)

    def test_bad_visit_group_detected(self):
        _, diagnostics = _validate("bad_visit_group.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("visitGroup 300 out of range [0, 255]" in m for m in messages), messages)

    def test_bad_base_level_detected(self):
        _, diagnostics = _validate("bad_base_level.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(any("baseLevel -1 out of range [0, 255]" in m for m in messages), messages)


class CharactersSchemaReservedFieldTests(unittest.TestCase):
    def test_reserved_field_rejected(self):
        _, diagnostics = _validate("reserved_field.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("field '_u23' is reserved" in m and "must not be authored" in m for m in messages), messages
        )


class CharactersSchemaSupportDataTests(unittest.TestCase):
    def test_raw_record_with_support_data_rejected(self):
        _, diagnostics = _validate("raw_record_with_support_data.json")
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("raw/generic-template character records must not reference supportData" in m for m in messages),
            messages,
        )

    def test_support_data_skipped_when_supports_table_not_loaded(self):
        # No dependency_records at all -- the supportData cross-reference
        # check must be skipped gracefully, not raise/report a false error.
        _, diagnostics = _validate("valid.json")
        messages = [str(e) for e in diagnostics.errors]
        self.assertFalse(any("supportData" in m for m in messages), messages)

    def test_support_data_missing_reference_detected(self):
        dependency_records = {"supports": [_FakeSupportRecord("CHARACTER_EIRIKA", "SupportData_Eirika")]}
        _, diagnostics = _validate("support_data_missing_ref.json", dependency_records=dependency_records)
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any("undefined supportData reference 'SupportData_NotReal'" in m for m in messages), messages
        )

    def test_support_data_owner_mismatch_detected(self):
        dependency_records = {"supports": [_FakeSupportRecord("CHARACTER_EIRIKA", "SupportData_Eirika")]}
        _, diagnostics = _validate("support_data_owner_mismatch.json", dependency_records=dependency_records)
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any(
                "supportData 'SupportData_Eirika' belongs to owner 'CHARACTER_EIRIKA', not 'CHARACTER_SETH'" in m
                for m in messages
            ),
            messages,
        )

    def test_support_data_reciprocal_reference_passes(self):
        dependency_records = {"supports": [_FakeSupportRecord("CHARACTER_EIRIKA", "SupportData_Eirika")]}
        _, diagnostics = _validate("valid.json", dependency_records=dependency_records)
        messages = [str(e) for e in diagnostics.errors]
        self.assertFalse(any("supportData" in m for m in messages), messages)


class CharactersSchemaClassDependencyTests(unittest.TestCase):
    def test_class_missing_from_loaded_classes_table_detected(self):
        dependency_records = {"classes": [_FakeClassRecord("CLASS_MYRMIDON")]}
        _, diagnostics = _validate("class_missing_from_table.json", dependency_records=dependency_records)
        self.assertFalse(diagnostics.ok)
        messages = [str(e) for e in diagnostics.errors]
        self.assertTrue(
            any(
                "defaultClass 'CLASS_GENERAL' is a valid CLASS_* constant but has no ClassData record" in m
                for m in messages
            ),
            messages,
        )

    def test_class_present_in_loaded_classes_table_passes(self):
        dependency_records = {"classes": [_FakeClassRecord("CLASS_GENERAL")]}
        _, diagnostics = _validate("class_missing_from_table.json", dependency_records=dependency_records)
        self.assertTrue(diagnostics.ok, msg=diagnostics.render())

    def test_class_check_skipped_when_classes_table_not_loaded(self):
        _, diagnostics = _validate("class_missing_from_table.json")
        self.assertTrue(diagnostics.ok, msg=diagnostics.render())


class CharactersSchemaDiagnosticLocationTests(unittest.TestCase):
    def test_diagnostic_renders_file_line_column(self):
        _, diagnostics = _validate("bad_class_ref.json")
        self.assertFalse(diagnostics.ok)
        rendered = diagnostics.render()
        self.assertRegex(rendered, r"bad_class_ref\.json:\d+:\d+: ")


class CharactersHeaderConstantsTests(unittest.TestCase):
    def test_reads_character_data_array_capacity(self):
        self.assertEqual(
            characters_schema.read_character_data_array_capacity("baseRanks", _MINI_BMUNIT_HEADER), 8
        )

    def test_reads_character_attributes_without_helper_combos(self):
        flags = characters_schema.read_character_attributes(_MINI_BMUNIT_HEADER)
        self.assertIn("CA_LORD", flags)
        self.assertIn("CA_FEMALE", flags)
        self.assertNotIn("CA_MOUNTEDAID", flags)

    def test_reads_live_msg_count(self):
        self.assertEqual(characters_schema.read_msg_count(_MINI_MSG_HEADER), 10)

    def test_reads_live_portrait_count(self):
        self.assertEqual(characters_schema.read_portrait_count(_MINI_PORTRAIT_SOURCE), 3)

    def test_reads_live_mini_portrait_capacity(self):
        self.assertEqual(characters_schema.read_mini_portrait_capacity(_MINI_FACE_SOURCE), 3)

    def test_reads_unit_affinities_with_implicit_increment(self):
        values = characters_schema.read_unit_affinities(_MINI_BMUNIT_HEADER)
        self.assertEqual(values["UNIT_AFFIN_FIRE"], 1)
        self.assertEqual(values["UNIT_AFFIN_THUNDER"], 2)
        self.assertEqual(values["UNIT_AFFIN_ANIMA"], 7)


if __name__ == "__main__":
    unittest.main()
