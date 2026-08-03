import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.localization.generate import generate


class DeterminismTests(unittest.TestCase):
    def test_two_independent_generate_runs_are_byte_identical(self):
        """Generating twice into two different directories from the same
        committed registry/catalog input must be byte-for-byte identical
        -- the exact property a nondeterministic generator (dict ordering,
        timestamps, set iteration) would violate."""
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            written_a = generate(output_dir=Path(tmp_a))
            written_b = generate(output_dir=Path(tmp_b))
            for name in written_a:
                content_a = written_a[name].read_text(encoding="utf-8")
                content_b = written_b[name].read_text(encoding="utf-8")
                self.assertEqual(content_a, content_b, f"{name} differs between runs")


if __name__ == "__main__":
    unittest.main()
