"""Issue #10 -- the archival lane is vanilla-item-cap-only, enforced by TWO
complementary gates: a parse-time known-goal fast-fail AND a dependency-graph
backstop. (The prior *single* graph gate was safe but not early enough: a real
`make legacy`/`fireemblem8.gba` first churned mgfembp's sub-build and hundreds
of agbcc objects -- all regular prerequisites of $(ROM), updated before an
order-only prerequisite -- and only aborted at the final link. The two-gate
design fixes that without regressing to the old fragile literal MAKECMDGOALS
whitelist that silently let indirect entries through.)

Strategic binding decision (see docs/id_space.md, reports/issue10_closure.md):
item ID *expansion* is a modern-lane-only capability. The archival agbcc lane
deliberately does NOT thread -DFE8_ITEM_ID_CAP into its compile commands, so at
a non-vanilla cap the generator would plan an expanded (up to 207-record)
gItemData[] table while every archival object still compiles
include/id_space.h's built-in ITEM_ID_CONFIGURED_CAP at the vanilla 0xCD: a
silent generated-vs-compiled contract divergence.

How the guard is built (the property these tests pin down):
Two gates, one shared diagnostic ($(GENERATED_DATA_ARCHIVAL_ITEM_CAP_DIAG),
defined once in generated_data.mk so the gates cannot drift):

Gate 1 -- parse-time known-goal fast-fail (Makefile ARCHIVAL_KNOWN_GOALS +
$(MAKECMDGOALS) $(filter ...) + $(error)): when the resolved cap is expanded
and an explicitly-named public archival goal (legacy / the ROM/ELF/MAP /
relocs / objects.lst / shiftcheck family) is on the command line, make aborts
during parse -- before ANY recipe, sub-make, or agbcc compile is even planned.
This is what makes a real `make legacy` fail EARLY, not after churning the
object graph.

Gate 2 -- dependency-graph backstop:
  * generated_data.mk defines ONE .PHONY guard target,
    `generated-data-archival-item-cap-guard`, whose *recipe* body is a make
    $(error) that fires at an expanded cap. Because the assertion is a make
    function in the recipe, make expands (and thus fires) it whenever the guard
    target is pulled into the active build graph -- INCLUDING under `make -n`
    (a dry run still expands recipe text) and even when the archival products
    are already up to date (the guard is .PHONY, always reconsidered).
  * The Makefile attaches that guard as an order-only prerequisite of the
    archival LINK/LIST/ARTIFACT boundary --
    objects.lst / fireemblem8.elf / fireemblem8.gba / fireemblem8.map /
    fireemblem8_relocs.elf. Every archival artifact (incl. the whole shiftcheck
    family) funnels through at least one of these, and NONE of them is built by
    the modern lane or the standalone generated-data checks. So the guard is
    inherited through the graph by any target -- named, indirect, or ADDED
    LATER -- that reaches the archival lane, with no goal list to maintain.

These tests are deterministic and fast. The `make -n` cases fail during
plan/expansion (returncode 2, no recipe, no mgfembp $(MAKE) sub-build). The
real (non -n) cases cover HIGH-PREREQUISITE goals -- `legacy`, `fireemblem8.gba`,
`objects.lst`, `shiftcheck` (each depends on all of $(ALL_OBJECTS)) -- and a
no-prerequisite goal (`fireemblem8.map`); all abort at parse time before any
object assemble, mgfembp sub-build, or link, so they stay fast yet prove the
'don't churn the object graph first' property the map-only case could not.
They never run a real multi-minute agbcc/modern build.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

VANILLA_CAP = "0xCD"
EXPANDED_CAP = "0xCE"

# Direct archival products/alias.
DIRECT_ARCHIVAL_GOALS = [
    "legacy",
    "fireemblem8.gba",
    "fireemblem8.elf",
    "fireemblem8.map",
]
# The shiftability harness: the CI aggregate + every sub-target, all of which
# reach the archival lane through $(ROM)/$(MAP)/$(RELOCS_ELF)/$(OBJECTS_LST).
SHIFTCHECK_GOALS = [
    "shiftcheck",
    "shiftcheck-static",
    "shiftcheck-offsets",
    "shiftcheck-diff",
    "shiftcheck-run",
]
# Other indirect archival entries the prior whitelist silently let through.
RELOCS_GOAL = "fireemblem8_relocs.elf"
OBJECT_LIST_GOAL = "objects.lst"

ALL_ARCHIVAL_GOALS = (
    DIRECT_ARCHIVAL_GOALS + SHIFTCHECK_GOALS + [RELOCS_GOAL, OBJECT_LIST_GOAL]
)


def run_make(args, env_overrides=None, timeout=180, extra_makefile=None):
    env = os.environ.copy()
    env.pop("MAKEFLAGS", None)
    # Clean baseline: the guard must key off the resolved cap only, never a
    # stray ambient FE8_ITEM_ID_CAP leaking in from the caller's shell.
    env.pop("FE8_ITEM_ID_CAP", None)
    if env_overrides:
        for key, value in env_overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
    make_args = ["make"]
    if extra_makefile is not None:
        # -f Makefile keeps the repo's includes; the extra fragment adds an
        # ad-hoc target so we can prove graph-level inheritance.
        make_args += ["-f", "Makefile", "-f", extra_makefile]
    make_args += list(args)
    return subprocess.run(
        make_args,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )


class _GuardAssertions(unittest.TestCase):
    def assert_actionable_block(self, result):
        """A block must be non-zero AND carry the full actionable diagnostic --
        root cause, both caps, and the modern migration path -- not just any
        non-zero text."""
        self.assertNotEqual(
            result.returncode, 0,
            "expected a non-zero parse/plan-time block\n%s" % result.stdout,
        )
        out = result.stdout
        self.assertIn("modern-only", out)
        self.assertIn("expansion-modern-boot-check", out)
        # names the archival-only vanilla cap and the offending resolved value
        self.assertIn("FE8_ITEM_ID_CAP=%s" % VANILLA_CAP, out)
        self.assertIn("resolved to %s" % EXPANDED_CAP, out)
        # explains the *why* (root cause), so the diagnostic is actionable
        self.assertIn("does not thread -DFE8_ITEM_ID_CAP", out)
        # make aborted at the archival link/list boundary, before any archival
        # ELF/ROM/relocs link was reached.
        self.assertIn("Stop.", out)
        # NB: building an archival goal may first (self-heal) regenerate and
        # agbcc-compile the *generated* data table -- that is the allowed data
        # lane, not the blocked archival link -- so we deliberately do NOT
        # assert the absence of a generated-object compile here. The real-build
        # test below pins "before any *link*" on fireemblem8.map (no prereqs).

    def assert_plan_ok(self, result):
        """PASS = the guard does not fire, so goal resolution/dry run succeeds.
        Assert on the guard's *absence* (build-state independent), not on a
        specific compile line -- the archival products may already be up to
        date, so there may be nothing to print."""
        self.assertEqual(
            result.returncode, 0,
            "expected the plan to succeed\n%s" % result.stdout[-3000:],
        )
        self.assertNotIn("modern-only", result.stdout)
        self.assertNotIn("only supports the vanilla item cap", result.stdout)



# Recipe / sub-make / compiler-invocation markers. NB: none of these substrings
# occur in the guard's diagnostic prose (which does say "agbcc"), so asserting
# their absence proves no recipe was planned or run -- not just that some prose
# was printed.
RECIPE_MARKERS = (
    "mgfembp",            # $(MAKE) -C mgfembp ... archival sub-build
    "Entering directory", # any recursive $(MAKE)
    "arm-none-eabi-as",   # archival object assemble
    "arm-none-eabi-ld",   # archival link
    "arm-none-eabi-objcopy",  # ROM objcopy
)


def _assert_no_recipe_ran(testcase, result):
    for marker in RECIPE_MARKERS:
        testcase.assertNotIn(
            marker, result.stdout,
            "expected NO recipe/sub-make before the guard fired, but saw %r\n%s"
            % (marker, result.stdout),
        )


class ExpandedCapBlocksEveryArchivalEntryTests(_GuardAssertions):
    """The reviewer's reproduction: at an expanded cap, EVERY archival entry --
    direct product, alias, relocs, the whole shiftcheck family, and the object
    list -- must fail under `make -n`, via env and via a command-line cap."""

    def test_env_expanded_cap_blocks_every_archival_goal_under_dry_run(self):
        for goal in ALL_ARCHIVAL_GOALS:
            with self.subTest(goal=goal):
                result = run_make(
                    ["-n", goal], env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP}
                )
                self.assert_actionable_block(result)

    def test_command_line_expanded_cap_blocks_every_archival_goal_under_dry_run(self):
        for goal in ALL_ARCHIVAL_GOALS:
            with self.subTest(goal=goal):
                result = run_make(["-n", goal, "FE8_ITEM_ID_CAP=%s" % EXPANDED_CAP])
                self.assert_actionable_block(result)

    def test_shiftcheck_aggregate_and_relocs_are_regression_pinned(self):
        # Explicit named coverage of the exact entries the prior literal-goal
        # whitelist missed (they exit 0 before this fix): the shiftcheck
        # aggregate, a shiftcheck sub-target, and the relocs ELF.
        for goal in ("shiftcheck", "shiftcheck-static", RELOCS_GOAL):
            with self.subTest(goal=goal):
                self.assert_actionable_block(
                    run_make(["-n", goal], env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP})
                )


class CommandLinePrecedenceAndNormalizationTests(_GuardAssertions):
    """CLI beats env in BOTH directions, and the compare is normalized (not a
    fragile raw-string match)."""

    def test_command_line_expanded_wins_over_ambient_vanilla_env(self):
        result = run_make(
            ["-n", "legacy", "FE8_ITEM_ID_CAP=%s" % EXPANDED_CAP],
            env_overrides={"FE8_ITEM_ID_CAP": VANILLA_CAP},
        )
        self.assert_actionable_block(result)

    def test_command_line_vanilla_wins_over_ambient_expanded_env(self):
        result = run_make(
            ["-n", "legacy", "FE8_ITEM_ID_CAP=%s" % VANILLA_CAP],
            env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP},
        )
        self.assert_plan_ok(result)

    def test_legal_equivalent_vanilla_spellings_are_accepted(self):
        # 205 == 0xcd == 0315 must all normalize to the vanilla cap and pass.
        for spelling in ("205", "0xcd", "0o315"):
            with self.subTest(spelling=spelling):
                self.assert_plan_ok(
                    run_make(["-n", "fireemblem8.gba", "FE8_ITEM_ID_CAP=%s" % spelling])
                )

    def test_expanded_equivalent_spellings_are_rejected(self):
        # 206 == 0xce must all normalize to an expanded cap and block.
        for spelling in ("206", "0xce", "0o316"):
            with self.subTest(spelling=spelling):
                self.assert_actionable_block(
                    run_make(["-n", "legacy", "FE8_ITEM_ID_CAP=%s" % spelling])
                )


class VanillaCapArchivalStillReachableTests(_GuardAssertions):
    """The archival lane stays reachable at the vanilla cap; the guard must not
    over-fire on the default or an explicit 0xCD."""

    def test_default_cap_allows_every_archival_goal(self):
        for goal in ALL_ARCHIVAL_GOALS:
            with self.subTest(goal=goal):
                self.assert_plan_ok(run_make(["-n", goal]))

    def test_explicit_vanilla_env_cap_allows_legacy(self):
        self.assert_plan_ok(
            run_make(["-n", "legacy"], env_overrides={"FE8_ITEM_ID_CAP": VANILLA_CAP})
        )


class NonArchivalLanesUnaffectedTests(_GuardAssertions):
    """The guard is scoped to the archival link/list/artifact boundary only;
    the modern + standalone generated-data lanes must keep working at an
    expanded cap (they never depend on those products)."""

    def test_bare_make_stays_modern_even_at_expanded_cap(self):
        result = run_make(["-n"], env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP})
        self.assertEqual(result.returncode, 0, result.stdout[-3000:])
        self.assertIn(
            "make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs",
            result.stdout,
        )
        self.assertNotIn("modern-only", result.stdout)

    def test_modern_boot_check_allowed_at_expanded_cap(self):
        result = run_make(
            ["-n", "expansion-modern-boot-check", "MODERN_CONFIG=release", "MODERN_ABI=aapcs"],
            env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP},
        )
        self.assert_plan_ok(result)

    def test_generated_data_check_not_blocked_at_expanded_cap(self):
        result = run_make(
            ["-n", "generated-data-check"], env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP}
        )
        self.assert_plan_ok(result)

    def test_modern_plan_threads_a_consistent_compiler_define_at_expanded_cap(self):
        # The whole reason the archival lane is blocked: the modern lane DOES
        # flow the same cap into the compile, so its generated table and
        # compiled ITEM_ID_CONFIGURED_CAP agree. Proven via a parse-only
        # `-rR -p` database dump of MODERN_DEFINE_FLAGS.
        result = run_make(
            ["--no-print-directory", "-rR", "-p", "__issue10_modern_define_probe__"],
            env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP},
        )
        line = next(
            (l for l in result.stdout.splitlines() if l.startswith("MODERN_DEFINE_FLAGS")),
            None,
        )
        self.assertIsNotNone(line, result.stdout[:400])
        self.assertIn("-DFE8_ITEM_ID_CAP=%s" % EXPANDED_CAP, line)

    def test_modern_plan_has_no_cap_define_at_default(self):
        result = run_make(
            ["--no-print-directory", "-rR", "-p", "__issue10_modern_define_probe__"],
        )
        line = next(
            (l for l in result.stdout.splitlines() if l.startswith("MODERN_DEFINE_FLAGS")),
            None,
        )
        self.assertIsNotNone(line, result.stdout[:400])
        self.assertNotIn("FE8_ITEM_ID_CAP", line)


class DependencyGraphInheritanceTests(_GuardAssertions):
    """The architectural payoff over a MAKECMDGOALS whitelist: an ad-hoc target
    named NOWHERE in the repo, that merely depends on an archival product,
    still inherits the guard at an expanded cap and stays clear at the vanilla
    cap. A literal-goal whitelist would sail such a future/indirect target
    straight through."""

    def _probe(self, dependency, env_overrides=None):
        fragment = (
            "issue10-future-archival-probe: %s\n"
            "\t@echo unreachable\n"
            ".PHONY: issue10-future-archival-probe\n" % dependency
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".mk", delete=False, dir=str(ROOT)
        ) as fh:
            fh.write(fragment)
            path = fh.name
        try:
            return run_make(
                ["-n", "issue10-future-archival-probe"],
                env_overrides=env_overrides,
                extra_makefile=os.path.basename(path),
            )
        finally:
            os.unlink(path)

    def test_future_target_on_elf_inherits_guard_at_expanded_cap(self):
        self.assert_actionable_block(
            self._probe("$(ELF)", env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP})
        )

    def test_future_target_on_object_list_inherits_guard_at_expanded_cap(self):
        self.assert_actionable_block(
            self._probe("$(OBJECTS_LST)", env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP})
        )

    def test_future_target_on_relocs_inherits_guard_at_expanded_cap(self):
        self.assert_actionable_block(
            self._probe("$(RELOCS_ELF)", env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP})
        )

    def test_future_target_on_elf_is_clear_at_vanilla_cap(self):
        self.assert_plan_ok(self._probe("$(ELF)"))


class RealBuildBlocksBeforeAnyRecipeTests(_GuardAssertions):
    """Not merely a dry-run artifact: a REAL (non -n) archival invocation fails
    at plan/expansion time, before any compile or link. fireemblem8.map has no
    prerequisite except the order-only guard, so this is fast and deterministic
    -- no agbcc/ld runs, no mgfembp $(MAKE) sub-build."""

    def test_real_map_build_blocks_before_any_recipe_at_expanded_cap(self):
        result = run_make(
            ["fireemblem8.map"],
            env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP},
            timeout=60,
        )
        self.assert_actionable_block(result)
        # Prove nothing was actually built: no linker/objcopy invocation.
        self.assertNotIn("arm-none-eabi-ld", result.stdout)
        self.assertNotIn("arm-none-eabi-objcopy", result.stdout)


class ShellInjectionSafetyTests(unittest.TestCase):
    """The resolver forwards FE8_ITEM_ID_CAP into a parse-time $(shell) (GNU
    Make does not export command-line variables into $(shell)). The value must
    be POSIX-single-quote-escaped, so a crafted value with a quote breakout is
    treated as an invalid cap and NEVER executes a shell side effect."""

    def _run_with_payload(self, payload, on_cli):
        marker_dir = tempfile.mkdtemp()
        marker = os.path.join(marker_dir, "pua_pwned")
        # A single-quote breakout that would `touch` the marker if the value
        # were interpolated raw into the shell.
        value = "'; touch %s; echo '" % marker
        try:
            if on_cli:
                result = run_make(["-n", "generated-data-check", "FE8_ITEM_ID_CAP=%s" % value])
            else:
                result = run_make(
                    ["-n", "generated-data-check"],
                    env_overrides={"FE8_ITEM_ID_CAP": value},
                )
            self.assertFalse(
                os.path.exists(marker),
                "SHELL INJECTION: marker file was created -> value reached the shell",
            )
            self.assertNotEqual(result.returncode, 0)
            # The malicious value is rejected as an invalid cap, not executed.
            self.assertIn("is not a valid item ID cap", result.stdout)
        finally:
            if os.path.exists(marker):
                os.unlink(marker)
            os.rmdir(marker_dir)

    def test_env_metacharacter_value_has_no_shell_side_effect(self):
        self._run_with_payload("quote-breakout", on_cli=False)

    def test_command_line_metacharacter_value_has_no_shell_side_effect(self):
        self._run_with_payload("quote-breakout", on_cli=True)



class KnownGoalParseTimeFastFailTests(_GuardAssertions):
    """The reviewer's core finding: for a KNOWN, explicitly-named public
    archival goal, the block must land at Make *parse/plan* time with ZERO
    recipe output -- no mgfembp $(MAKE) sub-build, no arm-none-eabi
    assemble/link -- so `make -n <goal>` cannot be masked by only ever testing
    a no-prerequisite goal. Every whitelisted archival goal (incl. `legacy` and
    `fireemblem8.gba`, which carry hundreds of regular object prerequisites)
    must fail before a single command is planned."""

    def test_every_known_goal_dry_run_emits_no_recipe_before_blocking(self):
        for goal in ALL_ARCHIVAL_GOALS:
            with self.subTest(goal=goal):
                result = run_make(
                    ["-n", goal], env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP}
                )
                self.assert_actionable_block(result)
                _assert_no_recipe_ran(self, result)


class RealArchivalBuildPreemptedBeforeAnyWorkTests(_GuardAssertions):
    """A REAL (non -n) archival invocation of a HIGH-PREREQUISITE goal --
    `legacy` / `fireemblem8.gba` / `objects.lst`, each depending on the entire
    $(ALL_OBJECTS) set -- must abort at parse time before any object is
    assembled, any mgfembp sub-build is entered, or any link runs. This is the
    property the prior map-only real-build test could NOT prove: map has no
    regular prerequisites, so it could never have exercised the 'don't churn
    the whole object graph first' requirement. These are fast (they fail before
    doing work) yet clean-independent (parse-time, so build state is
    irrelevant)."""

    def test_real_legacy_blocks_before_any_object_or_submake(self):
        result = run_make(
            ["legacy"], env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP}, timeout=90
        )
        self.assert_actionable_block(result)
        _assert_no_recipe_ran(self, result)

    def test_real_rom_blocks_before_any_object_or_submake(self):
        result = run_make(
            ["fireemblem8.gba"],
            env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP},
            timeout=90,
        )
        self.assert_actionable_block(result)
        _assert_no_recipe_ran(self, result)

    def test_real_object_list_blocks_before_any_object_or_submake(self):
        result = run_make(
            ["objects.lst"],
            env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP},
            timeout=90,
        )
        self.assert_actionable_block(result)
        _assert_no_recipe_ran(self, result)

    def test_real_shiftcheck_aggregate_blocks_before_any_object_or_submake(self):
        result = run_make(
            ["shiftcheck"],
            env_overrides={"FE8_ITEM_ID_CAP": EXPANDED_CAP},
            timeout=90,
        )
        self.assert_actionable_block(result)
        _assert_no_recipe_ran(self, result)


if __name__ == "__main__":
    unittest.main()
