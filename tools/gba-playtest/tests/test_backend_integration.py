import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gba_playtest
from homebrew_fixture import build_homebrew_rom


def fixture_scenario():
    return gba_playtest.parse_scenario_data(
        {
            "schema_version": 1,
            "name": "homebrew-integration",
            "description": "A changes a pixel and a semantic KEYINPUT mirror.",
            "frames": [{"start": 2, "end": 2, "keys": ["A"]}],
            "checkpoints": [
                {
                    "name": "released",
                    "frame": 1,
                    "framebuffer": True,
                    "probes": [{"address": "0x02000000", "size": 4}],
                },
                {
                    "name": "a-held",
                    "frame": 2,
                    "framebuffer": True,
                    "probes": [{"address": "0x02000000", "size": 4}],
                },
                {
                    "name": "released-again",
                    "frame": 3,
                    "framebuffer": True,
                    "probes": [{"address": "0x02000000", "size": 4}],
                },
            ],
        }
    )


class BackendIntegrationTests(unittest.TestCase):
    def _capture_or_skip(self, rom, scenario):
        try:
            return gba_playtest.capture(rom, scenario)
        except gba_playtest.PlaytestError as exc:
            unavailable_markers = (
                "C compiler ",
                "mgba/core/core.h: No such file",
                "'mgba/core/core.h' file not found",
                "cannot find -lmgba",
                "library not found for -lmgba",
            )
            if any(marker in str(exc) for marker in unavailable_markers):
                raise unittest.SkipTest(
                    f"libmGBA integration skipped explicitly: {exc}"
                ) from exc
            raise

    def test_generated_homebrew_full_lifecycle_and_policies(self):
        with tempfile.TemporaryDirectory(prefix="gba-playtest-test-") as temporary:
            root = Path(temporary)
            rom = root / "fixture.gba"
            candidate_rom = root / "fixture-candidate.gba"
            expected_path = root / "expected.json"
            build_homebrew_rom(rom)
            scenario = fixture_scenario()

            first = self._capture_or_skip(rom, scenario)
            second = self._capture_or_skip(rom, scenario)
            self.assertEqual(first, second)
            gba_playtest.validate_fingerprint(first, "<captured>")
            self.assertEqual(first["rom"]["title"], "GPTFIXTURE")
            self.assertEqual(first["rom"]["game_code"], "GPT0")
            self.assertEqual(first["rom"]["size"], 0x400)

            released, held, released_again = first["checkpoints"]
            self.assertRegex(
                released["framebuffer_hash"],
                r"^fnv1a64-rgb24:[0-9a-f]{16}$",
            )
            self.assertNotEqual(
                released["framebuffer_hash"], held["framebuffer_hash"]
            )
            self.assertEqual(
                released["framebuffer_hash"],
                released_again["framebuffer_hash"],
            )
            self.assertEqual(released["probes"][0]["value"], "0x000003ff")
            self.assertEqual(held["probes"][0]["value"], "0x000003fe")
            self.assertEqual(released_again["probes"][0]["value"], "0x000003ff")

            expected_path.write_text(
                gba_playtest.serialize_fingerprint(first), encoding="utf-8"
            )
            self.assertEqual(
                gba_playtest.compare_fingerprints(first, second, "exact-rom"), []
            )

            mutated = bytearray(rom.read_bytes())
            mutated[-1] = 1
            candidate_rom.write_bytes(mutated)
            candidate = self._capture_or_skip(candidate_rom, scenario)
            exact_differences = gba_playtest.compare_fingerprints(
                first, candidate, "exact-rom"
            )
            self.assertTrue(
                any(difference.startswith("rom.sha1:") for difference in exact_differences)
            )
            self.assertEqual(
                gba_playtest.compare_fingerprints(first, candidate, "behavior"), []
            )

            captured_stdout = io.StringIO()
            captured_stderr = io.StringIO()
            with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
                exact_rc = gba_playtest.main(
                    [
                        "verify",
                        "--rom",
                        str(candidate_rom),
                        "--scenario",
                        str(root / "scenario.json"),
                        "--expected",
                        str(expected_path),
                    ]
                )
            # main needs an on-disk strict scenario; exercise that path next.
            self.assertEqual(exact_rc, 2)
            self.assertIn("cannot read", captured_stderr.getvalue())

            scenario_data = {
                "schema_version": 1,
                "name": "homebrew-integration",
                "frames": [{"start": 2, "end": 2, "keys": ["A"]}],
                "checkpoints": [
                    {
                        "name": checkpoint.name,
                        "frame": checkpoint.frame,
                        "framebuffer": checkpoint.framebuffer,
                        "probes": [
                            {
                                "address": f"0x{probe.address:08x}",
                                "size": probe.size,
                            }
                            for probe in checkpoint.probes
                        ],
                    }
                    for checkpoint in scenario.checkpoints
                ],
            }
            scenario_path = root / "scenario.json"
            scenario_path.write_text(
                json.dumps(scenario_data, indent=2) + "\n", encoding="utf-8"
            )
            with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
                exact_rc = gba_playtest.main(
                    [
                        "verify",
                        "--rom",
                        str(candidate_rom),
                        "--scenario",
                        str(scenario_path),
                        "--expected",
                        str(expected_path),
                    ]
                )
                behavior_rc = gba_playtest.main(
                    [
                        "verify",
                        "--policy",
                        "behavior",
                        "--rom",
                        str(candidate_rom),
                        "--scenario",
                        str(scenario_path),
                        "--expected",
                        str(expected_path),
                    ]
                )
            self.assertEqual(exact_rc, 1)
            self.assertEqual(behavior_rc, 0)
            self.assertIn("baseline ROM:", captured_stdout.getvalue())
            self.assertIn("candidate ROM:", captured_stdout.getvalue())
            self.assertIn("baseline ROM:", captured_stderr.getvalue())
            self.assertIn("candidate ROM:", captured_stderr.getvalue())

            corrupted = copy.deepcopy(first)
            corrupted["checkpoints"][0][
                "framebuffer_hash"
            ] = "fnv1a64-rgb24:0000000000000000"
            self.assertTrue(
                gba_playtest.compare_fingerprints(corrupted, first, "behavior")
            )

    def test_accepts_full_tas_scale_input_range_count(self):
        with tempfile.TemporaryDirectory(prefix="gba-playtest-test-") as temporary:
            rom = Path(temporary) / "fixture.gba"
            build_homebrew_rom(rom)
            range_count = 10_001
            scenario = gba_playtest.parse_scenario_data(
                {
                    "schema_version": 1,
                    "name": "full-tas-scale-inputs",
                    "frames": [
                        {"start": frame, "end": frame, "keys": ["A"]}
                        for frame in range(1, range_count * 2, 2)
                    ],
                    "checkpoints": [
                        {
                            "name": "after-inputs",
                            "frame": range_count * 2,
                            "framebuffer": True,
                            "probes": [],
                        }
                    ],
                }
            )

            fingerprint = self._capture_or_skip(rom, scenario)
            self.assertEqual(fingerprint["checkpoints"][0]["frame"], range_count * 2)


if __name__ == "__main__":
    unittest.main()
