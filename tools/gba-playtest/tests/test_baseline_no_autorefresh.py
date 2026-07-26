"""Issue #13: `verify` must never write, rewrite, or otherwise refresh the
checked-in baseline fingerprint it was given via `--expected`, whether the
comparison passes or fails. Baseline refresh is exclusively a human,
explicit `capture -o <path>` invocation followed by a normal reviewed
commit -- never something `verify` (or any part of this module reachable
from it) can do on its own, silent or not. This is a black-box, code-level
guarantee: it does not require libmGBA/a compiler, so it always runs (never
skipped) as part of the fast host-only test lane.
"""

import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gba_playtest


_BASELINE_TEXT = gba_playtest.serialize_fingerprint(
    {
        "format_version": 2,
        "scenario": "boot",
        "rom": {
            "sha1": "0" * 40,
            "size": 1024,
            "title": "BASELINE",
            "game_code": "BAS0",
        },
        "checkpoints": [
            {
                "frame": 5,
                "name": "visible",
                "framebuffer_hash": "fnv1a64-rgb24:0000000000000000",
                "probes": [],
            }
        ],
    }
)

_MISMATCHING_CAPTURE = {
    "format_version": 2,
    "scenario": "boot",
    "rom": {
        "sha1": "1" * 40,
        "size": 1024,
        "title": "CANDIDATE",
        "game_code": "CAN0",
    },
    "checkpoints": [
        {
            "frame": 5,
            "name": "visible",
            "framebuffer_hash": "fnv1a64-rgb24:1111111111111111",
            "probes": [],
        }
    ],
}

_MATCHING_CAPTURE = {
    "format_version": 2,
    "scenario": "boot",
    "rom": {
        "sha1": "0" * 40,
        "size": 1024,
        "title": "BASELINE",
        "game_code": "BAS0",
    },
    "checkpoints": [
        {
            "frame": 5,
            "name": "visible",
            "framebuffer_hash": "fnv1a64-rgb24:0000000000000000",
            "probes": [],
        }
    ],
}


class BaselineNoAutoRefreshTests(unittest.TestCase):
    def _run_verify(self, tmp_path: Path, captured: dict) -> int:
        expected_path = tmp_path / "expected.json"
        expected_path.write_text(_BASELINE_TEXT, encoding="utf-8")
        scenario_path = tmp_path / "scenario.json"
        scenario_path.write_text(
            gba_playtest.json.dumps(
                {
                    "schema_version": 1,
                    "name": "boot",
                    "frames": [],
                    "checkpoints": [
                        {
                            "name": "visible",
                            "frame": 5,
                            "framebuffer": True,
                            "probes": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        rom_path = tmp_path / "fixture.gba"
        rom_path.write_bytes(b"\0" * 0xB0)

        before_bytes = expected_path.read_bytes()
        before_mtime_ns = expected_path.stat().st_mtime_ns
        with mock.patch.object(gba_playtest, "capture", return_value=captured):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = gba_playtest.main(
                    [
                        "verify",
                        "--rom",
                        str(rom_path),
                        "--scenario",
                        str(scenario_path),
                        "--expected",
                        str(expected_path),
                    ]
                )
        self.assertEqual(
            expected_path.read_bytes(),
            before_bytes,
            "verify must never modify the --expected baseline file's bytes",
        )
        self.assertEqual(
            expected_path.stat().st_mtime_ns,
            before_mtime_ns,
            "verify must never even rewrite --expected with identical bytes "
            "(mtime must be untouched)",
        )
        return exit_code

    def test_mismatching_verify_leaves_baseline_untouched(self):
        with gba_playtest.tempfile.TemporaryDirectory() as tmp:
            exit_code = self._run_verify(Path(tmp), _MISMATCHING_CAPTURE)
        self.assertEqual(exit_code, 1)

    def test_passing_verify_leaves_baseline_untouched(self):
        with gba_playtest.tempfile.TemporaryDirectory() as tmp:
            exit_code = self._run_verify(Path(tmp), _MATCHING_CAPTURE)
        self.assertEqual(exit_code, 0)

    def test_verify_subcommand_has_no_write_or_refresh_style_flag(self):
        parser = gba_playtest._make_parser()
        verify_actions = {
            action.dest
            for action in parser._subparsers._group_actions[0].choices["verify"]._actions
        }
        # Only capture has an output path; verify must have no flag that
        # could plausibly write back to disk at all (baseline refresh is a
        # separate, human-run `capture -o` command, reviewed like any other
        # source change -- never a `verify` side effect).
        self.assertNotIn("output", verify_actions)
        forbidden_substrings = ("write", "refresh", "update", "regenerate")
        for dest in verify_actions:
            lowered = dest.lower()
            for forbidden in forbidden_substrings:
                self.assertNotIn(
                    forbidden,
                    lowered,
                    f"verify gained a suspicious --{dest} flag; baseline refresh "
                    "must stay an explicit, separate `capture -o` command",
                )


if __name__ == "__main__":
    unittest.main()
