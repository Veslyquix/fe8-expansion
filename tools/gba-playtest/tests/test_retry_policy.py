"""Issue #13: bounded, explicit, transient-only retry policy.

`--retries` is 0 (a single attempt, no retry) everywhere by default, so
every existing scenario/fingerprint/CI invocation keeps its exact prior
behavior unless it explicitly opts in. Retrying is bounded by
`MAX_RETRIES_CAP` regardless of the caller-supplied value, applies only to
a process time-out (the one condition here that can plausibly be transient
host scheduling/load), and every retried attempt is reported on stderr --
never a silent/default retry that could launder real flake into a false
pass. A non-zero exit code, a malformed-output diagnostic, or a fingerprint
mismatch are deterministic outcomes and are never retried anywhere in this
module.
"""

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gba_playtest


class BoundedRetryCountTests(unittest.TestCase):
    def test_default_is_zero_retries_one_attempt(self):
        self.assertEqual(gba_playtest._bounded_retry_count(0), 0)

    def test_negative_is_clamped_to_zero(self):
        self.assertEqual(gba_playtest._bounded_retry_count(-5), 0)

    def test_value_within_cap_is_unchanged(self):
        self.assertEqual(gba_playtest._bounded_retry_count(3), 3)

    def test_value_above_cap_is_clamped_to_cap(self):
        self.assertEqual(
            gba_playtest._bounded_retry_count(gba_playtest.MAX_RETRIES_CAP + 100),
            gba_playtest.MAX_RETRIES_CAP,
        )


class TransientRetryHelperTests(unittest.TestCase):
    def test_retries_only_on_timeout_and_reports_every_attempt(self):
        calls = {"n": 0}

        def fake_run(*_args, **_kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise subprocess.TimeoutExpired("cmd", 1)
            return subprocess.CompletedProcess(["cmd"], 0, stdout="ok", stderr="")

        stderr = io.StringIO()
        with mock.patch.object(gba_playtest.subprocess, "run", side_effect=fake_run):
            with redirect_stderr(stderr):
                result = gba_playtest._run_transient_retryable(
                    ["cmd"], timeout=1, retries=2, operation="widget-build"
                )
        self.assertEqual(calls["n"], 3)
        self.assertEqual(result.stdout, "ok")
        log = stderr.getvalue()
        self.assertIn("widget-build attempt 1/3 timed out", log)
        self.assertIn("widget-build attempt 2/3 timed out", log)
        # The final, successful attempt is not itself reported as a timeout.
        self.assertNotIn("attempt 3/3 timed out", log)

    def test_retries_are_capped_regardless_of_requested_value(self):
        calls = {"n": 0}

        def always_times_out(*_args, **_kwargs):
            calls["n"] += 1
            raise subprocess.TimeoutExpired("cmd", 1)

        with mock.patch.object(
            gba_playtest.subprocess, "run", side_effect=always_times_out
        ):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(subprocess.TimeoutExpired):
                    gba_playtest._run_transient_retryable(
                        ["cmd"],
                        timeout=1,
                        retries=gba_playtest.MAX_RETRIES_CAP + 50,
                        operation="widget-build",
                    )
        self.assertEqual(calls["n"], gba_playtest.MAX_RETRIES_CAP + 1)

    def test_default_zero_retries_means_exactly_one_attempt(self):
        calls = {"n": 0}

        def always_times_out(*_args, **_kwargs):
            calls["n"] += 1
            raise subprocess.TimeoutExpired("cmd", 1)

        with mock.patch.object(
            gba_playtest.subprocess, "run", side_effect=always_times_out
        ):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(subprocess.TimeoutExpired):
                    gba_playtest._run_transient_retryable(
                        ["cmd"], timeout=1, retries=0, operation="widget-build"
                    )
        self.assertEqual(calls["n"], 1)

    def test_non_zero_exit_is_returned_without_any_retry(self):
        calls = {"n": 0}

        def fails_cleanly(*_args, **_kwargs):
            calls["n"] += 1
            return subprocess.CompletedProcess(["cmd"], 1, stdout="", stderr="boom")

        with mock.patch.object(gba_playtest.subprocess, "run", side_effect=fails_cleanly):
            result = gba_playtest._run_transient_retryable(
                ["cmd"], timeout=1, retries=5, operation="widget-build"
            )
        self.assertEqual(calls["n"], 1)
        self.assertEqual(result.returncode, 1)


class BackendAndCompilerRetryIntegrationTests(unittest.TestCase):
    def test_build_backend_retries_on_timeout_then_succeeds(self):
        calls = {"n": 0}

        def fake_compiler_run(*_args, **_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise subprocess.TimeoutExpired("cc", 60)
            return subprocess.CompletedProcess(["cc"], 0, stdout="", stderr="")

        with mock.patch.object(
            gba_playtest, "_compiler_command", return_value=["cc"]
        ), mock.patch.object(
            gba_playtest.subprocess, "run", side_effect=fake_compiler_run
        ):
            with redirect_stderr(io.StringIO()):
                gba_playtest.build_backend(Path("backend"), retries=1)
        self.assertEqual(calls["n"], 2)

    def test_capture_backend_timeout_names_total_attempts_when_exhausted(self):
        scenario = gba_playtest.parse_scenario_data(
            {
                "schema_version": 1,
                "name": "timeout",
                "frames": [],
                "checkpoints": [
                    {"name": "late", "frame": 600, "framebuffer": True, "probes": []}
                ],
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            rom = Path(temporary) / "fixture.gba"
            data = bytearray(0xB0)
            data[0xA0:0xAC] = b"TIMEOUT".ljust(12, b"\0")
            data[0xAC:0xB0] = b"TMO0"
            rom.write_bytes(data)
            with mock.patch.object(
                gba_playtest, "build_backend"
            ), mock.patch.object(
                gba_playtest.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("backend", 30),
            ):
                with redirect_stderr(io.StringIO()) as stderr:
                    with self.assertRaisesRegex(
                        gba_playtest.PlaytestError,
                        r"attempt 3/3, no attempts remaining",
                    ):
                        gba_playtest.capture(rom, scenario, retries=2)
                self.assertIn("attempt 1/3 timed out", stderr.getvalue())
                self.assertIn("attempt 2/3 timed out", stderr.getvalue())


class CliRetriesFlagTests(unittest.TestCase):
    def test_negative_retries_is_rejected_with_actionable_message(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = gba_playtest.main(
                [
                    "capture",
                    "--rom",
                    "does-not-matter.gba",
                    "--scenario",
                    "does-not-matter.json",
                    "--retries",
                    "-1",
                ]
            )
        self.assertEqual(exit_code, 2)
        self.assertIn("--retries must be a non-negative integer", stderr.getvalue())

    def test_retries_defaults_to_zero_for_every_subcommand(self):
        parser_args = gba_playtest._make_parser().parse_args(
            ["backend-check"]
        )
        self.assertEqual(parser_args.retries, 0)

    def test_retries_above_cap_is_accepted_by_the_parser_and_bounded_later(self):
        # The CLI itself never rejects a large --retries value outright (that
        # would be a confusing surprise for a value that is merely capped,
        # not invalid) -- capping happens once inside
        # _run_transient_retryable/_bounded_retry_count, verified above.
        parser_args = gba_playtest._make_parser().parse_args(
            ["backend-check", "--retries", "999"]
        )
        self.assertEqual(parser_args.retries, 999)


if __name__ == "__main__":
    unittest.main()
