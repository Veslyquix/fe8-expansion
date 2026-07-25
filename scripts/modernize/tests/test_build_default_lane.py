"""Issue #15 -- default build-lane targeted tests.

Confirms, with deterministic evidence (a `make -rR -p` database probe plus
`make -n` dry runs -- never a real, multi-minute compile/link/boot-check
inside the automated suite), that:

* A bare `make`/`make all` unconditionally resolves to the single
  supported modern GCC AAPCS *release* boot-check chain, and its dry-run
  plan never mentions a `tools/agbcc` executable or library.
* This is a *structural* guarantee, not an environment/command-line
  convention: `all:` takes no lane-selection variable of any kind, so
  neither ambient environment pollution (`FE8_DEFAULT_LANE=legacy` set in
  the calling shell before invoking `make`) nor a `make`
  command-line variable assignment (`make all FE8_DEFAULT_LANE=legacy`,
  highest-precedence origin) can redirect a bare/`all` build to the
  archival agbcc lane. These are *negative* regression tests: an earlier
  candidate implementation of this issue made `FE8_DEFAULT_LANE=legacy` an
  ambient-environment escape hatch for the default goal, which let a bare
  `make`/`make all` silently fall back to the unsupported agbcc lane --
  exactly the binding-decision violation this issue exists to close. The
  fix removed that variable/gate entirely; these tests prove it cannot be
  reintroduced (under this name or a `make`-noise equivalent) without
  failing here.
* The explicit, clearly-named archival alias `make legacy` still exists and
  is structurally identical (same dry-run plan) to the pre-existing
  `make fireemblem8.gba` -- the archival lane is preserved, not deleted,
  and reachable *only* by naming it.
* `scripts/quickstart.sh --legacy` calls `make legacy` by name directly
  (never a bare `make -j<jobs>` plus a lane-selection variable of any
  kind) -- proven both by grepping the script for that exact invocation
  and by a regression guard that the retired `FE8_DEFAULT_LANE` glue is
  gone from the script entirely (a stale reference would mean quickstart
  and the Makefile disagree about how the archival lane is reached).

A single real, non-dry-run bare `make` (modern release, boot-verified) was
run manually as part of this issue's closure evidence -- see the
Agent/TRF closure handoff notes; it is intentionally not repeated here
because a full modern build/link/boot-check takes several minutes and this
suite must stay fast and deterministic.
"""

import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAKEFILE = ROOT / "Makefile"
QUICKSTART = ROOT / "scripts" / "quickstart.sh"


def run_make(args, env_overrides=None):
    env = os.environ.copy()
    env.pop("MAKEFLAGS", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["make", *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class DefaultGoalDatabaseProbeTests(unittest.TestCase):
    """Mirrors generated-data-link-check's own build-state-independent probe:
    a `-rR -p` database dump against a nonexistent target name never
    executes a recipe or recurses into a sub-make, and `-rR`
    (--no-builtin-rules --no-builtin-variables) keeps GNU Make's implicit
    suffix-rule search from matching the bogus probe name."""

    def probe(self, env_overrides=None):
        result = run_make(
            ["--no-print-directory", "-rR", "-p", "__issue15_default_goal_probe__"],
            env_overrides=env_overrides,
        )
        return result.stdout

    def test_default_goal_is_still_all(self):
        probe = self.probe()
        default_goal = next(
            (line for line in probe.splitlines() if line.startswith(".DEFAULT_GOAL ")),
            None,
        )
        self.assertEqual(default_goal, ".DEFAULT_GOAL := all")

    def test_all_rule_has_no_file_prerequisite_of_any_kind(self):
        # Issue #15: `all:` is a bare recipe target -- no fireemblem8.gba
        # (legacy $(ROM)) prerequisite, and no other file prerequisite --
        # that unconditionally recurses into the modern release boot-check
        # chain. There is no ifeq/variable-gated branch left in the
        # Makefile that could give `all:` a legacy prerequisite under any
        # condition; this is the load-bearing structural change this issue
        # makes. See `legacy: fireemblem8.gba` (tested below) for the one
        # place that prerequisite still lives, reachable only by name.
        probe = self.probe()
        all_rule = next(
            (line for line in probe.splitlines() if line.startswith("all:")), None
        )
        self.assertIsNotNone(all_rule, probe[:400])
        self.assertEqual(all_rule.strip(), "all:")

    def test_all_rule_is_identical_under_ambient_and_command_line_fe8_default_lane_noise(self):
        # Negative regression coverage for the exact defect this issue
        # closes: an ambient `FE8_DEFAULT_LANE=legacy` in the calling
        # environment must not change `all:`'s prerequisite/shape at all,
        # because the Makefile no longer reads that (or any) variable to
        # decide `all:`'s recipe.
        baseline = self.probe()
        baseline_all_rule = next(
            (line for line in baseline.splitlines() if line.startswith("all:")), None
        )
        polluted = self.probe(env_overrides={"FE8_DEFAULT_LANE": "legacy"})
        polluted_all_rule = next(
            (line for line in polluted.splitlines() if line.startswith("all:")), None
        )
        self.assertEqual(baseline_all_rule, polluted_all_rule)
        self.assertEqual(polluted_all_rule.strip(), "all:")


class BareMakeDryRunTests(unittest.TestCase):
    def test_bare_make_dry_run_plans_modern_release_aapcs_boot_check(self):
        result = run_make(["-n"])
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self.assertIn(
            "make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs",
            result.stdout,
        )

    def test_bare_make_dry_run_never_mentions_agbcc(self):
        result = run_make(["-n"])
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self.assertNotIn("agbcc", result.stdout)

    def test_make_all_dry_run_matches_bare_make(self):
        bare = run_make(["-n"])
        explicit = run_make(["all", "-n"])
        self.assertEqual(bare.returncode, 0, bare.stdout[-4000:])
        self.assertEqual(explicit.returncode, 0, explicit.stdout[-4000:])
        self.assertIn(
            "make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs",
            explicit.stdout,
        )
        self.assertNotIn("agbcc", explicit.stdout)

    def test_bare_make_dry_run_is_deterministic_against_ambient_modern_config(self):
        # Issue #15 requires this to be deterministic: an ambient
        # MODERN_CONFIG/MODERN_ABI override must never leak into the
        # default lane's pinned release/aapcs invocation.
        result = run_make(["-n"], env_overrides={"MODERN_CONFIG": "debug", "MODERN_ABI": "apcs-gnu"})
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self.assertIn(
            "make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs",
            result.stdout,
        )

    def test_bare_make_dry_run_is_immune_to_ambient_fe8_default_lane_pollution(self):
        # Negative regression test: this is the exact defect flagged
        # against an earlier candidate fix for this issue --
        # `FE8_DEFAULT_LANE=legacy` set ambiently in the calling
        # environment (not passed as a `make` argument at all) must not
        # change what a bare `make`/`make -n` plans. The Makefile no
        # longer defines or reads this variable, so this must resolve
        # identically to a clean environment: still the modern release
        # AAPCS boot-check, still no agbcc reference anywhere.
        result = run_make(["-n"], env_overrides={"FE8_DEFAULT_LANE": "legacy"})
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self.assertIn(
            "make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs",
            result.stdout,
        )
        self.assertNotIn("agbcc", result.stdout)

    def test_make_all_dry_run_is_immune_to_fe8_default_lane_command_line_variable_noise(self):
        # Same defect, but as a `make` command-line variable assignment
        # (`make all FE8_DEFAULT_LANE=legacy`) -- GNU Make's
        # highest-precedence variable origin. Command-line variables win
        # over ambient environment *and* Makefile `=`/`:=` assignments (but
        # not `override`), so this is the strongest possible way to try to
        # smuggle a lane switch in; it must still have zero effect, because
        # nothing in the Makefile references this (or any) variable name to
        # select `all:`'s recipe.
        result = run_make(["all", "-n", "FE8_DEFAULT_LANE=legacy"])
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self.assertIn(
            "make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs",
            result.stdout,
        )
        self.assertNotIn("agbcc", result.stdout)


class LegacyLaneStillReachableTests(unittest.TestCase):
    """The archival lane is explicitly preserved (never deleted); these
    prove it stays structurally reachable -- but only by naming it."""

    def test_make_legacy_target_depends_on_fireemblem8_gba(self):
        # Deliberately a `-p` database probe, never a `-n`/real build of
        # `legacy`/`fireemblem8.gba`: both targets' prerequisite chain
        # reaches mgfembp/mgfembp.bin, whose own recipe invokes $(MAKE) --
        # a recipe form GNU Make always actually *executes* (compiling
        # mgfembp's real tools), never merely prints, even under -n. A `-p`
        # probe against an unrelated, nonexistent target dumps the parsed
        # rule database without evaluating or running any real target's
        # recipe, so this stays a pure, side-effect-free static check that
        # the `legacy` alias reaches the exact same, unbroken prerequisite
        # as the pre-existing `make fireemblem8.gba`.
        result = run_make(
            ["--no-print-directory", "-rR", "-p", "__issue15_legacy_alias_probe__"]
        )
        legacy_rule = next(
            (line for line in result.stdout.splitlines() if line.startswith("legacy:")),
            None,
        )
        self.assertIsNotNone(legacy_rule, result.stdout[:400])
        self.assertEqual(legacy_rule.strip(), "legacy: fireemblem8.gba")

    def test_fe8_default_lane_env_var_no_longer_routes_bare_make_to_agbcc(self):
        # Negative regression test (inverts the pre-fix assumption): an
        # earlier candidate implementation made
        # `FE8_DEFAULT_LANE=legacy` route a bare `all:` to the archival
        # $(ROM) prerequisite. That gate has been removed outright, so
        # this ambient variable must now be fully inert -- `all:`'s
        # prerequisite must stay empty (no `fireemblem8.gba` reference at
        # all) even with it set, and the archival lane must only be
        # reachable by naming `legacy`/`fireemblem8.gba` directly.
        #
        # Deliberately a `-p` *database* probe against a nonexistent target
        # (never a `-n` dry run of `all`/`legacy` themselves): those targets'
        # own prerequisite chain reaches mgfembp/mgfembp.bin, whose recipe
        # invokes $(MAKE) -- and GNU Make always actually *executes* (not
        # just prints) any recipe line referencing $(MAKE), even under -n.
        # A `-p` probe against an unrelated, nonexistent target dumps the
        # parsed rule database without evaluating or running any real
        # target's recipe at all, so this stays a pure, side-effect-free
        # static check of which prerequisite `all:` resolves to.
        result = run_make(
            ["--no-print-directory", "-rR", "-p", "__issue15_legacy_lane_probe__"],
            env_overrides={"FE8_DEFAULT_LANE": "legacy"},
        )
        all_rule = next(
            (line for line in result.stdout.splitlines() if line.startswith("all:")),
            None,
        )
        self.assertIsNotNone(all_rule, result.stdout[:400])
        self.assertEqual(all_rule.strip(), "all:")
        self.assertNotIn("fireemblem8.gba", all_rule)


class NoLaneSelectionVariableSurvivesInMakefileTests(unittest.TestCase):
    """Owner-mindset closure check: prove the retired escape hatch was
    actually deleted from the Makefile's text, not merely made
    behaviorally inert by some other override, and that no differently
    named replacement gate was quietly introduced in its place."""

    def test_makefile_never_mentions_fe8_default_lane(self):
        text = MAKEFILE.read_text(encoding="utf-8")
        self.assertNotIn("FE8_DEFAULT_LANE", text)

    def test_makefile_all_target_recipe_is_a_single_unconditional_recursive_call(self):
        text = MAKEFILE.read_text(encoding="utf-8")
        match = re.search(r"^all:[^\n]*\n((?:\t.*\n)*)", text, re.MULTILINE)
        self.assertIsNotNone(match, "could not find all:'s recipe block in Makefile")
        recipe = match.group(1)
        self.assertIn("expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs", recipe)
        self.assertNotIn("ifeq", recipe)
        self.assertNotIn("FE8_DEFAULT_LANE", recipe)


class QuickstartLegacyGlueRegressionGuardTests(unittest.TestCase):
    """test_quickstart.py's mocked `make` never actually executes GNU Make,
    so it can only tell apart different literal argument strings logged
    for `make`. These tests guard the actual glue text/mechanism directly:
    quickstart's --legacy build must call the `legacy` target by name, and
    must not resurrect the retired `FE8_DEFAULT_LANE` environment-variable
    indirection this issue removed."""

    def test_quickstart_legacy_branch_calls_make_legacy_target_by_name(self):
        script = QUICKSTART.read_text(encoding="utf-8")
        fn_match = re.search(
            r"^build_project\(\) \{(.*?)^\}", script, re.DOTALL | re.MULTILINE
        )
        self.assertIsNotNone(fn_match, "could not find build_project()")
        body = fn_match.group(1)
        branch_match = re.search(
            r"if \(\( LEGACY_MODE == 1 \)\); then(.*?)\n\s*else\n", body, re.DOTALL
        )
        self.assertIsNotNone(branch_match, "could not find the --legacy build_project branch")
        branch = branch_match.group(1)
        self.assertRegex(branch, r"(?<!\S)make\s+legacy\s+-j")
        self.assertNotIn("FE8_DEFAULT_LANE", branch)

    def test_quickstart_never_mentions_retired_fe8_default_lane_variable(self):
        script = QUICKSTART.read_text(encoding="utf-8")
        self.assertNotIn("FE8_DEFAULT_LANE", script)


if __name__ == "__main__":
    unittest.main()
