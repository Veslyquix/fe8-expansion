"""Issue #10 review finding: `expansion-modern-idspace-active-check` must be
hermetic -- it must PASS identically no matter how the *caller* happens to
invoke it, instead of silently inheriting the caller's ambient shell
environment or `make FE8_ITEM_ID_CAP=...` command-line assignment.

Root cause (both closed in modern.mk, not here): FE8_ITEM_ID_CAP is resolved
ONCE per running `make` process, not per recipe line.

  1. `MODERN_CFLAGS` bakes in whatever FE8_ITEM_ID_CAP the gate's OWN
     top-level make process resolved at parse time. The gate's default and
     negative-mismatch compiles must use NO cap define regardless of that
     ambient value -- reusing `$(MODERN_CFLAGS)` as-is would silently fold
     an ambient/CLI cap into every compile in the gate, including the ones
     that are supposed to prove the *absence* of the flag.
  2. Each `$(MAKE)` recursion inside the gate's recipe that regenerates the
     generated item table re-resolves FE8_ITEM_ID_CAP for that CHILD
     process. A plain `FE8_ITEM_ID_CAP=... $(MAKE) ...` shell env-var prefix
     is silently ignored by that child whenever the *gate itself* was
     invoked with a `make ... FE8_ITEM_ID_CAP=...` command-line assignment,
     because GNU Make auto-forwards command-line-origin variables to every
     recursive `$(MAKE)` via MAKEFLAGS, and command-line origin outranks a
     plain environment-variable prefix in the child too.

These are real, slow (compiling) integration tests -- not `make -n` dry runs
-- because the defect is specifically in what the gate's recipe *executes*
(which cap ends up on each of the three `arm-none-eabi-gcc` invocations and
each recursive table regeneration), not in what make merely plans.

Honest scope note: an *invalid* ambient FE8_ITEM_ID_CAP (e.g. a non-integer)
is rejected by generated_data.mk's own GENERATED_DATA_ITEM_CAP resolver at
Makefile PARSE time, for every goal in this repository, before any target's
recipe -- including this gate's -- is ever reached. That parse-time
fast-fail is pre-existing, repo-wide issue #10 resolver behavior (see
generated_data.mk / scripts/generated_data/idspace.py resolve_item_id_cap),
not a property of this specific gate, and is out of this fix's file domain.
This suite pins that boundary down explicitly instead of silently assuming
the gate could ever observe (let alone recover from) an invalid ambient cap.
"""

import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

TARGET = "expansion-modern-idspace-active-check"
EXPANDED_CAP = "0xCE"
OTHER_NONDEFAULT_CAP = "0xD0"
PASS_MARKER = "PASS: %s" % TARGET
NEGATIVE_OK_MARKER = "OK: cap/count divergence is a hard compile error, not a silent truncation"


def _toolchain_available():
    return shutil.which("arm-none-eabi-gcc") is not None


def run_gate(env_overrides=None, cli_vars=None, timeout=240):
    """Runs the real gate target (a genuine compiling integration run, not
    `-n`), with a clean baseline environment (no ambient FE8_ITEM_ID_CAP,
    no inherited MAKEFLAGS) plus whatever env_overrides/cli_vars the test
    asks for -- exactly the three ways a caller can drive FE8_ITEM_ID_CAP."""
    env = os.environ.copy()
    env.pop("MAKEFLAGS", None)
    env.pop("FE8_ITEM_ID_CAP", None)
    if env_overrides:
        for key, value in env_overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
    args = ["make", "--no-print-directory", TARGET]
    if cli_vars:
        for key, value in cli_vars.items():
            args.append("%s=%s" % (key, value))
    return subprocess.run(
        args,
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )


@unittest.skipUnless(_toolchain_available(), "arm-none-eabi-gcc not installed")
class GateHermeticAcrossInvocationStylesTests(unittest.TestCase):
    """The same review-finding repro matrix: ambient unset, ambient env
    FE8_ITEM_ID_CAP=0xCE, and a `make ... FE8_ITEM_ID_CAP=0xCE` command-line
    assignment must all PASS -- not just the clean-ambient case the gate
    happened to be exercised under before this fix."""

    def _assert_gate_passed(self, result):
        self.assertEqual(
            result.returncode, 0,
            "expected the gate to PASS\n%s" % result.stdout[-4000:],
        )
        self.assertIn(PASS_MARKER, result.stdout)
        # The negative-mismatch sub-step must still have actually fired as a
        # real compile failure -- this fix must not weaken/skip that assert
        # to buy the other two cap states their hermeticity.
        self.assertIn(NEGATIVE_OK_MARKER, result.stdout)
        self.assertNotIn("FAIL:", result.stdout)

    def test_ambient_ceiling_unset_passes(self):
        self._assert_gate_passed(run_gate())

    def test_ambient_env_expanded_cap_passes(self):
        self._assert_gate_passed(run_gate(env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP}))

    def test_command_line_expanded_cap_passes(self):
        self._assert_gate_passed(run_gate(cli_vars={"FE8_ITEM_ID_CAP": EXPANDED_CAP}))

    def test_command_line_wins_over_a_conflicting_ambient_env(self):
        # Command-line origin outranks environment origin in GNU Make; the
        # gate must stay hermetic (its own internal per-step overrides win)
        # even when the ambient env and the CLI assignment disagree, and
        # even when neither of them is the vanilla default.
        self._assert_gate_passed(
            run_gate(
                env_overrides={"FE8_ITEM_ID_CAP": OTHER_NONDEFAULT_CAP},
                cli_vars={"FE8_ITEM_ID_CAP": EXPANDED_CAP},
            )
        )

    def test_ambient_env_arbitrary_nondefault_cap_passes(self):
        # Not just 0xCE: any ambient value must not leak into the gate's own
        # explicit per-step cap states.
        self._assert_gate_passed(run_gate(env_overrides={"FE8_ITEM_ID_CAP": OTHER_NONDEFAULT_CAP}))


@unittest.skipUnless(_toolchain_available(), "arm-none-eabi-gcc not installed")
class InvalidAmbientCapScopeBoundaryTests(unittest.TestCase):
    """Honest scope pin: an invalid ambient cap is rejected at Makefile
    parse time by generated_data.mk's own resolver, for this goal exactly
    like every other goal -- it is not, and cannot be, this gate's own
    recipe self-healing an invalid input; the recipe is never reached."""

    def test_invalid_ambient_cap_is_a_repo_wide_parse_time_error_not_a_gate_failure(self):
        result = run_gate(env_overrides={"FE8_ITEM_ID_CAP": "not-a-valid-cap"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is not a valid item ID cap", result.stdout)
        # It aborts before the gate's own recipe ever prints anything.
        self.assertNotIn(PASS_MARKER, result.stdout)
        self.assertNotIn("default cap: generated table", result.stdout)


if __name__ == "__main__":
    unittest.main()
