import os
import unittest
from unittest import mock

from scripts.generated_data.classes import parser as classes_parser
from scripts.generated_data.classes.schema import load_records
from scripts.generated_data.tests._util import fixture_path

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
REAL_SOURCE = os.path.join(REPO_ROOT, "src", "data", "classes.json")
REAL_HAND_FILE = os.path.join(REPO_ROOT, "src", "data_classes.c")

FIXTURE_CLASS_NAMES = ["CLASS_FIXTURE_A", "CLASS_FIXTURE_B"]

_MINI_CLASSES_HEADER = fixture_path("classes", "mini_classes.h")
_MINI_BMUNIT_HEADER = fixture_path("classes", "mini_bmunit.h")
_MINI_BMITEM_HEADER = fixture_path("classes", "mini_bmitem.h")


def _mock_fixture_headers():
    return mock.patch.multiple(
        classes_parser,
        CLASSES_HEADER=_MINI_CLASSES_HEADER,
        BMUNIT_HEADER=_MINI_BMUNIT_HEADER,
        BMITEM_HEADER=_MINI_BMITEM_HEADER,
    )


class HandWrittenParserTests(unittest.TestCase):
    def test_parses_fixture_classes(self):
        with _mock_fixture_headers():
            records = classes_parser.parse_hand_written(
                fixture_path("classes", "valid_hand.c"), FIXTURE_CLASS_NAMES
            )
        self.assertEqual(set(records), set(FIXTURE_CLASS_NAMES))

    def test_missing_class_symbol_raises(self):
        with _mock_fixture_headers():
            with self.assertRaises(Exception):
                classes_parser.parse_hand_written(
                    fixture_path("classes", "valid_hand.c"), ["CLASS_TOTALLY_MADE_UP"]
                )


class FullRoundTripTests(unittest.TestCase):
    """Every one of the 129 gClassData[] records (127 vanilla + CLASS_CAMP /
    CLASS_TENT_STRUCTURE from the Camp/Tent structures feature) must
    round-trip semantically against src/data_classes.c -- not just examples
    (Issue #5 Batch 1 DONE)."""

    def test_generated_model_matches_every_hand_written_class(self):
        generated_records = load_records(REAL_SOURCE)
        self.assertEqual(len(generated_records), 129)

        class_names = [r.class_name for r in generated_records]
        hand_records = classes_parser.parse_hand_written(REAL_HAND_FILE, class_names)
        errors = classes_parser.compare_records(generated_records, hand_records, hand_path=REAL_HAND_FILE)
        self.assertEqual(errors, [], msg="\n".join(str(e) for e in errors))


class FixtureRoundTripTests(unittest.TestCase):
    def test_matching_fixture_passes(self):
        generated_records = load_records(fixture_path("classes", "valid.json"))
        with _mock_fixture_headers():
            hand_records = classes_parser.parse_hand_written(
                fixture_path("classes", "valid_hand.c"), FIXTURE_CLASS_NAMES
            )
            errors = classes_parser.compare_records(
                generated_records, hand_records, hand_path=fixture_path("classes", "valid_hand.c")
            )
        self.assertEqual(errors, [], msg="\n".join(str(e) for e in errors))

    def test_mismatched_fixture_detected(self):
        generated_records = load_records(fixture_path("classes", "valid.json"))
        with _mock_fixture_headers():
            hand_records = classes_parser.parse_hand_written(
                fixture_path("classes", "mismatched_hand.c"), FIXTURE_CLASS_NAMES
            )
            errors = classes_parser.compare_records(
                generated_records, hand_records, hand_path=fixture_path("classes", "mismatched_hand.c")
            )
        messages = [str(e) for e in errors]
        self.assertTrue(any("fields mismatch for CLASS_FIXTURE_A" in m for m in messages), messages)


class RoundTripMismatchDetectionTests(unittest.TestCase):
    def test_detects_missing_hand_class(self):
        generated_records = load_records(fixture_path("classes", "valid.json"))
        with _mock_fixture_headers():
            hand_records = classes_parser.parse_hand_written(
                fixture_path("classes", "valid_hand.c"), FIXTURE_CLASS_NAMES
            )
        del hand_records["CLASS_FIXTURE_B"]

        errors = classes_parser.compare_records(
            generated_records, hand_records, hand_path=fixture_path("classes", "valid_hand.c")
        )
        messages = [str(e) for e in errors]
        self.assertTrue(any("CLASS_FIXTURE_B" in m for m in messages), messages)

    def test_detects_extra_hand_class(self):
        generated_records = [
            r for r in load_records(fixture_path("classes", "valid.json")) if r.class_name != "CLASS_FIXTURE_B"
        ]
        with _mock_fixture_headers():
            hand_records = classes_parser.parse_hand_written(
                fixture_path("classes", "valid_hand.c"), FIXTURE_CLASS_NAMES
            )

        errors = classes_parser.compare_records(
            generated_records, hand_records, hand_path=fixture_path("classes", "valid_hand.c")
        )
        messages = [str(e) for e in errors]
        self.assertTrue(
            any("hand-written class 'CLASS_FIXTURE_B' has no counterpart" in m for m in messages), messages
        )


if __name__ == "__main__":
    unittest.main()
