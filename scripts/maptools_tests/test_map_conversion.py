"""Round-trip tests for scripts/tmx_to_map.py and scripts/mar_to_tmx.py
against scripts/mar_to_map.py's own, long-established .mar->.bin output --
mar_to_map.py itself is treated as ground truth (it's what every currently
shipping map already builds from).

Run: python3 -m unittest discover -s scripts/maptools_tests -p 'test_*.py'
"""
import glob
import importlib.util
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SCRIPTS_DIR)
MAP_LAYOUT_DIR = os.path.join(REPO_ROOT, "graphics", "map", "layout")
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS_DIR, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mar_to_map = _load("mar_to_map")
tmx_to_map = _load("tmx_to_map")
mar_to_tmx = _load("mar_to_tmx")


class TmxToMapKnownGoodPairTests(unittest.TestCase):
    """A fixed .mar/.tmx pair (scripts/maptools_tests/fixtures/), known by
    construction to represent identical map content -- NewPrologueMap.tmx
    is an actual Tiled export of the exact same map NewPrologueMap.mar
    encodes (independently authored, not derived from the .mar). Kept as
    a static fixture rather than reading the live graphics/map/layout/
    directory, since a real map is only ever committed in ONE of the two
    formats there. If this ever fails, the tile-value transform in
    tmx_to_map.py itself is wrong, not just a round-trip inconsistency."""

    def test_known_pair_produces_identical_bin(self):
        mar_path = os.path.join(FIXTURES_DIR, "NewPrologueMap.mar")
        tmx_path = os.path.join(FIXTURES_DIR, "NewPrologueMap.tmx")

        with tempfile.TemporaryDirectory() as tmp:
            from_mar = os.path.join(tmp, "from_mar.bin")
            mar_to_map.main(["mar_to_map.py", mar_path, from_mar])
            with open(from_mar, "rb") as f:
                mar_bytes = f.read()

            tmx_bytes = tmx_to_map.convert(tmx_path)
            self.assertEqual(mar_bytes, tmx_bytes)


class MarTmxRoundTripTests(unittest.TestCase):
    """Every committed vanilla .mar survives mar_to_tmx.py -> tmx_to_map.py
    and reproduces mar_to_map.py's own .bin byte-for-byte -- this is what
    makes converting an existing map to .tmx (mar_to_tmx.py) safe: the
    compiled map data cannot change."""

    @classmethod
    def setUpClass(cls):
        cls.mar_paths = sorted(glob.glob(os.path.join(MAP_LAYOUT_DIR, "*.mar")))
        if not cls.mar_paths:
            raise unittest.SkipTest(f"no .mar files found under {MAP_LAYOUT_DIR}")

    def test_all_committed_mar_maps_round_trip(self):
        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            for mar_path in self.mar_paths:
                name = os.path.splitext(os.path.basename(mar_path))[0]
                json_path = mar_path[:-4] + ".json"
                if not os.path.exists(json_path):
                    continue  # not a real map source (shouldn't happen, but don't crash the suite)

                original_bin = os.path.join(tmp, f"{name}.orig.bin")
                mar_to_map.main(["mar_to_map.py", mar_path, original_bin])

                tmx_path = os.path.join(tmp, f"{name}.tmx")
                try:
                    width, height, values = mar_to_tmx.load_mar(mar_path)
                    root = mar_to_tmx.build_tmx(width, height, values, name, None, 16, None)
                    ET.ElementTree(root).write(tmx_path, encoding="unicode", xml_declaration=False)
                except SystemExit as e:
                    failures.append(f"{name}: mar_to_tmx failed: {e}")
                    continue

                try:
                    roundtrip_bytes = tmx_to_map.convert(tmx_path)
                except SystemExit as e:
                    failures.append(f"{name}: tmx_to_map failed: {e}")
                    continue

                with open(original_bin, "rb") as f:
                    original_bytes = f.read()

                if roundtrip_bytes != original_bytes:
                    failures.append(f"{name}: round-trip mismatch "
                                     f"({len(original_bytes)} vs {len(roundtrip_bytes)} bytes)")

        self.assertEqual(failures, [], "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
