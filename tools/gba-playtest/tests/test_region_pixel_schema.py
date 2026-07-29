"""Host-only coverage for the region-hash/pixel-probe backend feature
added for issue #18 sprint 5 WHAT #5 (real, targeted visible-marker
proof): a checkpoint's `regions` (named rectangular sub-regions of the
240x160 framebuffer, each hashed independently via backend.c's new
hash_region()) and `pixel_probes` (single (x, y) coordinates read back as
an exact 24-bit R,G,B value via backend.c's new read_pixel()) fields.

Root motivation recap: a whole-frame `framebuffer_hash` can prove "some
pixel somewhere changed" but can never prove *which* on-screen area
changed, or that a specific pixel took on a specific real color -- so it
cannot, by itself, distinguish "the qps-ploc pseudo-locale decoration
marker is visibly present at its own screen location" from "literally
anything else on screen differs". `regions`/`pixel_probes` close that gap
with real, per-area/per-pixel evidence, additive to (never a replacement
for) the existing whole-frame hash.

None of these tests require libmGBA or a built ROM: schema parsing/
fingerprint validation/backend-output parsing are exercised directly
against gba_playtest.py's real, unmodified production functions
(`parse_scenario_data`, `_write_plan`, `_parse_backend_output`,
`compare_inline_expectations`, `validate_fingerprint`), and the pure hash/
pixel-extraction math is exercised via region_hash_mirror.py, a byte-exact
host mirror of backend.c's hash_region()/read_pixel() (same pattern as
sram_hash_mirror.py for hash_sram()).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PLAYTEST_DIR = Path(__file__).resolve().parents[1]
for _extra_path in (str(PLAYTEST_DIR), str(PLAYTEST_DIR / "tests")):
    if _extra_path not in sys.path:
        sys.path.insert(0, _extra_path)

import gba_playtest  # noqa: E402
from region_hash_mirror import (  # noqa: E402
    compute_region_hash,
    compute_whole_frame_hash,
    read_pixel_rgb,
)

GBA_SCREEN_WIDTH = 240
GBA_SCREEN_HEIGHT = 160


def valid_scenario_with_region_and_pixel():
    return {
        "schema_version": 1,
        "name": "region-pixel-unit-test",
        "frames": [{"start": 2, "end": 3, "keys": ["A"]}],
        "checkpoints": [
            {
                "name": "checkpoint",
                "frame": 5,
                "framebuffer": True,
                "probes": [],
                "regions": [
                    {"name": "marker-region", "x": 10, "y": 20, "width": 16, "height": 8},
                ],
                "pixel_probes": [
                    {"x": 12, "y": 22},
                ],
            }
        ],
    }


def _synthetic_backend_stdout(scenario, region_hash_hex="a" * 16, pixel_hex="ff00ff"):
    """Builds the exact tab-separated backend.c stdout text
    _parse_backend_output() expects, for a scenario whose sole checkpoint
    has framebuffer=True, no probes, exactly one region, and exactly one
    pixel probe -- reused across several tests below to exercise
    _parse_backend_output() itself without needing libmGBA."""
    checkpoint = scenario.checkpoints[0]
    lines = [
        f"CHECKPOINT\t0\t{checkpoint.frame}\t{'0' * 16}",
        f"REGIONHASH\t0\t0\t{region_hash_hex}",
        f"PIXEL\t0\t0\t{pixel_hex}",
    ]
    return "\n".join(lines) + "\n"


class RegionScenarioParsingTests(unittest.TestCase):
    def test_parses_region_and_pixel_probe(self):
        scenario = gba_playtest.parse_scenario_data(valid_scenario_with_region_and_pixel())
        checkpoint = scenario.checkpoints[0]
        self.assertEqual(len(checkpoint.regions), 1)
        region = checkpoint.regions[0]
        self.assertEqual((region.name, region.x, region.y, region.width, region.height),
                         ("marker-region", 10, 20, 16, 8))
        self.assertEqual(len(checkpoint.pixel_probes), 1)
        pixel = checkpoint.pixel_probes[0]
        self.assertEqual((pixel.x, pixel.y), (12, 22))

    def test_region_requires_framebuffer_true(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["framebuffer"] = False
        # sram_hash/probes empty + framebuffer False would otherwise fail
        # the "must capture something" check first; give it an sram_hash
        # so the framebuffer-requirement check for `regions` is what fires.
        data["checkpoints"][0]["sram_hash"] = True
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "requires the checkpoint's framebuffer"):
            gba_playtest.parse_scenario_data(data)

    def test_pixel_probe_requires_framebuffer_true(self):
        data = valid_scenario_with_region_and_pixel()
        del data["checkpoints"][0]["regions"]
        data["checkpoints"][0]["framebuffer"] = False
        data["checkpoints"][0]["sram_hash"] = True
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "requires the checkpoint's framebuffer"):
            gba_playtest.parse_scenario_data(data)

    def test_rejects_region_out_of_bounds(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["regions"][0]["width"] = 240
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "width must be an integer"):
            gba_playtest.parse_scenario_data(data)

    def test_rejects_region_negative_or_overlarge_coordinate(self):
        for field, value in (("x", -1), ("y", 999)):
            with self.subTest(field=field):
                data = valid_scenario_with_region_and_pixel()
                data["checkpoints"][0]["regions"][0][field] = value
                with self.assertRaises(gba_playtest.PlaytestError):
                    gba_playtest.parse_scenario_data(data)

    def test_rejects_duplicate_region_name(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["regions"].append(dict(data["checkpoints"][0]["regions"][0]))
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "duplicates"):
            gba_playtest.parse_scenario_data(data)

    def test_rejects_duplicate_pixel_coordinate(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["pixel_probes"].append(
            dict(data["checkpoints"][0]["pixel_probes"][0])
        )
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "duplicates coordinate"):
            gba_playtest.parse_scenario_data(data)

    def test_rejects_pixel_coordinate_out_of_bounds(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["pixel_probes"][0]["x"] = GBA_SCREEN_WIDTH
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "must be an integer"):
            gba_playtest.parse_scenario_data(data)

    def test_rejects_too_many_regions(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["regions"] = [
            {"name": f"r{i}", "x": 0, "y": 0, "width": 1, "height": 1}
            for i in range(gba_playtest.MAX_REGIONS_PER_CHECKPOINT + 1)
        ]
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "region limit"):
            gba_playtest.parse_scenario_data(data)

    def test_rejects_malformed_expected_hash(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["regions"][0]["expected_hash"] = "not-a-hash"
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "expected_hash must look like"):
            gba_playtest.parse_scenario_data(data)

    def test_rejects_malformed_expected_pixel(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["pixel_probes"][0]["expected"] = "0xnotahex"
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "expected must be lowercase"):
            gba_playtest.parse_scenario_data(data)

    def test_accepts_valid_expected_hash_and_pixel(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["regions"][0]["expected_hash"] = "fnv1a64-region:" + "0" * 16
        data["checkpoints"][0]["pixel_probes"][0]["expected"] = "0x112233"
        scenario = gba_playtest.parse_scenario_data(data)
        self.assertEqual(
            scenario.checkpoints[0].regions[0].expected_hash, "fnv1a64-region:" + "0" * 16
        )
        self.assertEqual(scenario.checkpoints[0].pixel_probes[0].expected, "0x112233")


class PlanRoundTripTests(unittest.TestCase):
    def test_write_plan_bumps_version_and_encodes_regions(self, tmp_path=None):
        import tempfile

        scenario = gba_playtest.parse_scenario_data(valid_scenario_with_region_and_pixel())
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "plan.txt"
            gba_playtest._write_plan(plan_path, scenario)
            text = plan_path.read_text(encoding="ascii")
        self.assertTrue(text.startswith("GBA_PLAYTEST_PLAN 3\n"))
        # Checkpoint header line: frame probe_count sram_hash_flag
        # exclude_range_count region_count pixel_probe_count.
        self.assertIn("5 0 0 0 1 1\n", text)
        # Region record: x y width height.
        self.assertIn("10 20 16 8\n", text)
        # Pixel-probe record: x y.
        self.assertIn("12 22\n", text)


class BackendOutputParsingTests(unittest.TestCase):
    def test_parses_region_hash_and_pixel_lines(self):
        scenario = gba_playtest.parse_scenario_data(valid_scenario_with_region_and_pixel())
        stdout = _synthetic_backend_stdout(scenario, region_hash_hex="deadbeefcafebabe", pixel_hex="112233")
        fingerprint = gba_playtest._parse_backend_output(stdout, scenario)
        checkpoint = fingerprint["checkpoints"][0]
        self.assertEqual(checkpoint["regions"], [
            {
                "name": "marker-region",
                "x": 10,
                "y": 20,
                "width": 16,
                "height": 8,
                "hash": "fnv1a64-region:deadbeefcafebabe",
            }
        ])
        self.assertEqual(checkpoint["pixel_probes"], [
            {"x": 12, "y": 22, "value": "0x112233"}
        ])

    def test_rejects_missing_region_hash(self):
        scenario = gba_playtest.parse_scenario_data(valid_scenario_with_region_and_pixel())
        checkpoint = scenario.checkpoints[0]
        stdout = (
            f"CHECKPOINT\t0\t{checkpoint.frame}\t{'0' * 16}\n"
            f"PIXEL\t0\t0\t112233\n"
        )
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "region hash"):
            gba_playtest._parse_backend_output(stdout, scenario)

    def test_rejects_missing_pixel_value(self):
        scenario = gba_playtest.parse_scenario_data(valid_scenario_with_region_and_pixel())
        checkpoint = scenario.checkpoints[0]
        stdout = (
            f"CHECKPOINT\t0\t{checkpoint.frame}\t{'0' * 16}\n"
            f"REGIONHASH\t0\t0\t{'a' * 16}\n"
        )
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "pixel probes"):
            gba_playtest._parse_backend_output(stdout, scenario)

    def test_rejects_malformed_region_hash_hex(self):
        scenario = gba_playtest.parse_scenario_data(valid_scenario_with_region_and_pixel())
        checkpoint = scenario.checkpoints[0]
        stdout = (
            f"CHECKPOINT\t0\t{checkpoint.frame}\t{'0' * 16}\n"
            f"REGIONHASH\t0\t0\tNOTHEX\n"
            f"PIXEL\t0\t0\t112233\n"
        )
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "malformed region hash"):
            gba_playtest._parse_backend_output(stdout, scenario)


class InlineExpectationTests(unittest.TestCase):
    def test_region_and_pixel_inline_expectation_mismatch_reported(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["regions"][0]["expected_hash"] = "fnv1a64-region:" + "1" * 16
        data["checkpoints"][0]["pixel_probes"][0]["expected"] = "0xabcdef"
        scenario = gba_playtest.parse_scenario_data(data)
        stdout = _synthetic_backend_stdout(scenario, region_hash_hex="2" * 16, pixel_hex="000000")
        fingerprint = gba_playtest._parse_backend_output(stdout, scenario)
        differences = gba_playtest.compare_inline_expectations(scenario, fingerprint)
        self.assertEqual(len(differences), 2)
        self.assertTrue(any("region 'marker-region'" in diff for diff in differences))
        self.assertTrue(any("pixel (12, 22)" in diff for diff in differences))

    def test_region_and_pixel_inline_expectation_match_passes(self):
        data = valid_scenario_with_region_and_pixel()
        data["checkpoints"][0]["regions"][0]["expected_hash"] = "fnv1a64-region:" + "2" * 16
        data["checkpoints"][0]["pixel_probes"][0]["expected"] = "0x000000"
        scenario = gba_playtest.parse_scenario_data(data)
        stdout = _synthetic_backend_stdout(scenario, region_hash_hex="2" * 16, pixel_hex="000000")
        fingerprint = gba_playtest._parse_backend_output(stdout, scenario)
        differences = gba_playtest.compare_inline_expectations(scenario, fingerprint)
        self.assertEqual(differences, [])


class FingerprintValidationTests(unittest.TestCase):
    def _base_fingerprint(self):
        return {
            "format_version": gba_playtest.FINGERPRINT_FORMAT_VERSION,
            "scenario": "region-pixel-unit-test",
            "rom": {
                "sha1": "0" * 40,
                "size": 16777216,
                "title": "FIREEMBLEM2E",
                "game_code": "BE8E",
            },
            "checkpoints": [
                {
                    "frame": 5,
                    "name": "checkpoint",
                    "probes": [],
                    "regions": [
                        {
                            "name": "marker-region",
                            "x": 10,
                            "y": 20,
                            "width": 16,
                            "height": 8,
                            "hash": "fnv1a64-region:" + "a" * 16,
                        }
                    ],
                    "pixel_probes": [{"x": 12, "y": 22, "value": "0x112233"}],
                }
            ],
        }

    def test_accepts_valid_regions_and_pixel_probes(self):
        gba_playtest.validate_fingerprint(self._base_fingerprint(), "<test>")

    def test_rejects_malformed_region_hash(self):
        data = self._base_fingerprint()
        data["checkpoints"][0]["regions"][0]["hash"] = "not-a-hash"
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "hash is malformed"):
            gba_playtest.validate_fingerprint(data, "<test>")

    def test_rejects_region_exceeding_framebuffer_bounds(self):
        data = self._base_fingerprint()
        data["checkpoints"][0]["regions"][0]["width"] = 240
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "exceeds the framebuffer width"):
            gba_playtest.validate_fingerprint(data, "<test>")

    def test_rejects_malformed_pixel_value(self):
        data = self._base_fingerprint()
        data["checkpoints"][0]["pixel_probes"][0]["value"] = "0xzz"
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "value is malformed"):
            gba_playtest.validate_fingerprint(data, "<test>")

    def test_rejects_empty_regions_array(self):
        data = self._base_fingerprint()
        data["checkpoints"][0]["regions"] = []
        with self.assertRaisesRegex(gba_playtest.PlaytestError, "non-empty array"):
            gba_playtest.validate_fingerprint(data, "<test>")


class RegionHashMirrorTests(unittest.TestCase):
    def _synthetic_framebuffer(self):
        # Deterministic, non-trivial 240x160 buffer: pixel color encodes
        # its own (x, y) so a region hash provably differs by position.
        buffer = [0] * (GBA_SCREEN_WIDTH * GBA_SCREEN_HEIGHT)
        for y in range(GBA_SCREEN_HEIGHT):
            for x in range(GBA_SCREEN_WIDTH):
                buffer[y * GBA_SCREEN_WIDTH + x] = (x & 0xFF) | ((y & 0xFF) << 8) | (0xAB << 24)
        return buffer

    def test_region_hash_is_deterministic(self):
        buffer = self._synthetic_framebuffer()
        first = compute_region_hash(buffer, 10, 20, 16, 8)
        second = compute_region_hash(buffer, 10, 20, 16, 8)
        self.assertEqual(first, second)
        self.assertRegex(first, r"^fnv1a64-region:[0-9a-f]{16}$")

    def test_region_hash_differs_for_different_region(self):
        buffer = self._synthetic_framebuffer()
        self.assertNotEqual(
            compute_region_hash(buffer, 0, 0, 8, 8),
            compute_region_hash(buffer, 100, 100, 8, 8),
        )

    def test_region_hash_is_not_whole_frame_hash(self):
        buffer = self._synthetic_framebuffer()
        region = compute_region_hash(buffer, 0, 0, 16, 16)
        whole = compute_whole_frame_hash(buffer)
        self.assertNotEqual(region, whole)

    def test_region_hash_insensitive_to_padding_byte(self):
        buffer = self._synthetic_framebuffer()
        # Flip only the ignored 4th (padding/alpha) byte everywhere in the
        # region -- the hash must be unaffected, exactly matching
        # backend.c's hash_region() only ever shifting 0/8/16.
        mutated = list(buffer)
        for y in range(20, 28):
            for x in range(10, 26):
                mutated[y * GBA_SCREEN_WIDTH + x] ^= 0x7F000000
        self.assertEqual(
            compute_region_hash(buffer, 10, 20, 16, 8),
            compute_region_hash(mutated, 10, 20, 16, 8),
        )

    def test_read_pixel_extracts_canonical_rgb(self):
        buffer = self._synthetic_framebuffer()
        # (x=12, y=22): R=12 (0x0c), G=22 (0x16), B=0 -> 0xRRGGBB = 0x0c1600.
        self.assertEqual(read_pixel_rgb(buffer, 12, 22), "0x0c1600")

    def test_read_pixel_ignores_padding_byte(self):
        buffer = self._synthetic_framebuffer()
        mutated = list(buffer)
        mutated[22 * GBA_SCREEN_WIDTH + 12] ^= 0x55000000
        self.assertEqual(read_pixel_rgb(buffer, 12, 22), read_pixel_rgb(mutated, 12, 22))

    def test_rejects_out_of_bounds_region(self):
        buffer = self._synthetic_framebuffer()
        with self.assertRaises(ValueError):
            compute_region_hash(buffer, 230, 0, 16, 1)

    def test_rejects_out_of_bounds_pixel(self):
        buffer = self._synthetic_framebuffer()
        with self.assertRaises(ValueError):
            read_pixel_rgb(buffer, 240, 0)


if __name__ == "__main__":
    unittest.main()
