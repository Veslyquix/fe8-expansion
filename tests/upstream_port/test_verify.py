import contextlib
import inspect
import io
import os
import re
import shlex
import subprocess
import unittest
from unittest import mock

from scripts.upstream_port import cli, verify as verify_mod

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BUILD_WORKFLOW_PATH = os.path.join(REPO_ROOT, ".github", "workflows", "build.yml")

_STEP_NAME_RE = re.compile(r"^    - name: (.+)$", re.M)
_SINGLE_RUN_RE = re.compile(r"^      run: (?!\|\s*$)(.+)$", re.M)
_MULTI_RUN_RE = re.compile(r"^      run: \|\n((?:        .*\n?)+)", re.M)

# Steps in build.yml that are pure environment setup (checkout, apt/pip
# installs, building host tools) rather than a pass/fail correctness gate
# `verify` needs to reproduce. Everything else in the workflow is expected
# to have a literal, argv-identical counterpart in verify.gates().
_NON_GATE_STEP_NAMES = {
    # host-tests job setup: installs build-essential + libmgba-dev only (no
    # arm-none-eabi toolchain), so it is environment setup, not a gate.
    "Install host-only dependencies (no arm-none-eabi toolchain)",
    # build job setup
    "Install dependencies",
    "Build tools",
}

# Issues #7/#17 remediation: the documentation step is a genuine required
# workflow gate, but it is the sole correctness step deliberately excluded
# from verify.gates(). Its exact commands and position are asserted separately
# below; localization remains part of the current-master 11-gate mirror.
_DOCS_GOVERNANCE_STEP_NAME = "Check documentation (issues #7/#17)"
_LOCALIZATION_HOST_STEP_NAME = "Run localization host test suite (issue #18)"


def _parse_workflow_gate_commands(path=BUILD_WORKFLOW_PATH):
    """Read build.yml with stdlib only (no PyYAML) and return the ordered
    list of shell command argv lists for every step that is a correctness
    gate (i.e. not in _NON_GATE_STEP_NAMES).

    This deliberately re-derives the expected gate list from the *current*
    workflow text on every test run, instead of hardcoding a copy of it, so
    the test actually fails when build.yml and verify.py drift apart again.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    step_matches = list(_STEP_NAME_RE.finditer(text))
    assert step_matches, f"no steps found parsing {path}; workflow format changed?"

    commands = []
    for i, m in enumerate(step_matches):
        step_name = m.group(1).strip()
        start = m.end()
        end = step_matches[i + 1].start() if i + 1 < len(step_matches) else len(text)
        block = text[start:end]

        if step_name in _NON_GATE_STEP_NAMES:
            continue

        single_m = _SINGLE_RUN_RE.search(block)
        if single_m:
            lines = [single_m.group(1).strip()]
        else:
            multi_m = _MULTI_RUN_RE.search(block)
            assert multi_m, f"step {step_name!r} has no parseable 'run:' block"
            lines = [line.strip() for line in multi_m.group(1).splitlines() if line.strip()]

        for line in lines:
            commands.append((step_name, shlex.split(line)))

    return commands


class VerifyGatesMirrorWorkflowTests(unittest.TestCase):
    """Assert verify.gates() is a literal, argv-identical, order-preserving
    mirror of the gate steps in .github/workflows/build.yml -- parsed from
    the live workflow file, not a hardcoded copy -- excluding only the
    separately tested standalone documentation-governance step."""

    def test_gate_argv_matches_workflow_commands_in_order(self):
        workflow_commands = [
            (step_name, argv)
            for step_name, argv in _parse_workflow_gate_commands()
            if step_name != _DOCS_GOVERNANCE_STEP_NAME
        ]
        gate_commands = [g.command for g in verify_mod.gates(jobs=2)]

        self.assertEqual(
            len(gate_commands),
            len(workflow_commands),
            f"verify.gates() has {len(gate_commands)} gate(s) but build.yml "
            f"has {len(workflow_commands)} mirrored gate command(s): "
            f"{[c for _, c in workflow_commands]!r}",
        )
        for gate_command, (step_name, workflow_argv) in zip(gate_commands, workflow_commands):
            self.assertEqual(
                gate_command,
                workflow_argv,
                f"gate command {gate_command!r} does not literally match "
                f"build.yml step {step_name!r} command {workflow_argv!r}",
            )

    def test_issue_7_17_docs_governance_is_a_standalone_workflow_step_not_a_verify_gate(self):
        """Docs governance stays outside the current-master 11-gate mirror
        while remaining required, argv-identical, and immediately after the
        artifact guard in build.yml."""
        names = [g.name for g in verify_mod.gates()]
        self.assertNotIn("docs-check-tests", names)
        self.assertNotIn("docs-check", names)

        all_workflow_commands = _parse_workflow_gate_commands()
        docs_commands = [
            argv
            for step_name, argv in all_workflow_commands
            if step_name == _DOCS_GOVERNANCE_STEP_NAME
        ]
        self.assertEqual(
            docs_commands,
            [
                [
                    "python3",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "scripts/docs_check_tests",
                    "-v",
                ],
                ["python3", "scripts/check_docs.py", "--check", "--check-examples"],
            ],
            "build.yml standalone docs-governance step must still run both "
            "commands, argv-identical, even though verify.gates() no longer "
            "mirrors them",
        )

        ordered_unique_steps = []
        for step_name, _ in all_workflow_commands:
            if not ordered_unique_steps or ordered_unique_steps[-1] != step_name:
                ordered_unique_steps.append(step_name)
        docs_index = ordered_unique_steps.index(_DOCS_GOVERNANCE_STEP_NAME)
        self.assertEqual(
            ordered_unique_steps[docs_index - 1],
            "Check tracked artifacts",
            "docs-governance step must immediately follow the artifact-guard step",
        )
        self.assertEqual(
            ordered_unique_steps[docs_index + 1],
            "Check default build lane and quickstart legacy glue (issue #15)",
            "docs-governance step must immediately precede the #15 default-lane step",
        )

    def test_issue_18_localization_host_suite_is_in_mirrored_gate_set(self):
        """The current-master localization host suite is mirrored exactly."""
        names = [g.name for g in verify_mod.gates()]
        self.assertIn("localization-host-suite", names)

        all_workflow_commands = _parse_workflow_gate_commands()
        localization_commands = [
            argv
            for step_name, argv in all_workflow_commands
            if step_name == _LOCALIZATION_HOST_STEP_NAME
        ]
        self.assertEqual(
            localization_commands,
            [[
                "python3", "-m", "unittest", "discover", "-s",
                "scripts/localization/tests", "-p", "test_*.py",
            ]],
        )

        ordered_unique_steps = []
        for step_name, _ in all_workflow_commands:
            if not ordered_unique_steps or ordered_unique_steps[-1] != step_name:
                ordered_unique_steps.append(step_name)
        localization_index = ordered_unique_steps.index(_LOCALIZATION_HOST_STEP_NAME)
        self.assertEqual(
            ordered_unique_steps[localization_index - 1],
            "Run upstream-port tooling test suite",
        )

    def test_issue_15_default_lane_and_quickstart_gates_present(self):
        names = [g.name for g in verify_mod.gates()]
        self.assertIn("default-lane-check", names)
        self.assertIn("quickstart-legacy-check", names)

        by_name = {g.name: g for g in verify_mod.gates()}
        self.assertEqual(
            by_name["default-lane-check"].command,
            [
                "python3",
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/modernize/tests",
                "-p",
                "test_build_default_lane.py",
                "-v",
            ],
        )
        self.assertEqual(
            by_name["quickstart-legacy-check"].command,
            [
                "python3",
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/modernize/tests",
                "-p",
                "test_quickstart.py",
                "-v",
            ],
        )

    def test_gate_list_full_ordered_names(self):
        # All 11 current-master mirrored gates remain; docs governance is
        # deliberately absent and asserted as a standalone workflow step.
        names = [g.name for g in verify_mod.gates()]
        self.assertEqual(
            names,
            [
                "gba-playtest-host-suite",
                "upstream-port-tests",
                "localization-host-suite",
                "artifact-guard",
                "default-lane-check",
                "quickstart-legacy-check",
                "generated-data-check",
                "modern-linker-check-debug",
                "modern-linker-check-release",
                "modern-itemexpansion-check-debug",
                "modern-itemexpansion-check-release",
            ],
        )
        # The merged CI runs the fast `host-tests` lane textually before the
        # ROM `build` job, so the three host-only gates are first. They must
        # stay host-only -- never a ROM/linker `make` build (that belongs
        # solely to the modern-linker gates) -- so the fast host job and the
        # ROM build job never duplicate work.
        for g in verify_mod.gates()[:3]:
            self.assertNotIn("make", g.command)
            self.assertNotIn("expansion-modern-linker-check", g.command)

    def test_artifact_guard_command(self):
        # After the merged host lane, the three host-only gates come first, so
        # the artifact guard (first gate of the ROM `build` job) is index 3.
        g = verify_mod.gates()[3]
        self.assertEqual(g.name, "artifact-guard")
        self.assertEqual(g.command, ["python3", "scripts/artifact_guard.py", "--revision", "HEAD"])

    def test_debug_and_release_configs_differ(self):
        by_name = {g.name: g for g in verify_mod.gates()}
        debug_gate = by_name["modern-linker-check-debug"]
        release_gate = by_name["modern-linker-check-release"]
        self.assertIn("MODERN_CONFIG=debug", debug_gate.command)
        self.assertIn("MODERN_CONFIG=release", release_gate.command)

    def test_dry_run_never_executes_subprocess(self):
        results = verify_mod.run_gates("/nonexistent/path/should/not/matter", dry_run=True)
        self.assertEqual(len(results), 11)
        self.assertTrue(all(r.ran is False for r in results))
        self.assertTrue(all(r.passed is False for r in results))  # not-ran != passed

    def test_dry_run_lists_full_ordered_gate_set_never_a_subset(self):
        """`--dry-run` (verify_mod.run_gates(dry_run=True)) must always list
        every gate the (non-dry-run) real run would perform, in the exact
        same order -- never a partial/filtered preview."""
        dry = [r.gate.name for r in verify_mod.run_gates("/nonexistent/path", dry_run=True)]
        real_names = [g.name for g in verify_mod.gates()]
        self.assertEqual(dry, real_names)
        self.assertEqual(len(dry), 11)


class VerifyGateSelectionRemovedTests(unittest.TestCase):
    """Adversarial coverage for the closure-integrity fix: `verify` (both the
    internal `run_gates` API and the public CLI) must have NO gate
    subset/selection capability at all -- an unknown gate name, a real gate
    name used to select a subset, an empty selection, or a duplicated one
    must all be impossible to express, not merely rejected at runtime. A
    partial/unknown/zero-gate "success" must never be produced."""

    def test_run_gates_has_no_selected_or_gates_parameter(self):
        sig = inspect.signature(verify_mod.run_gates)
        self.assertNotIn("selected", sig.parameters)
        self.assertNotIn("gates", sig.parameters)
        self.assertEqual(set(sig.parameters), {"cwd", "jobs", "dry_run"})

    def test_run_gates_rejects_unexpected_selection_kwarg(self):
        with self.assertRaises(TypeError):
            verify_mod.run_gates(  # type: ignore[call-arg]
                "/nonexistent/path", dry_run=True, selected=["artifact-guard"]
            )

    def test_cli_verify_has_no_gate_flag_at_all(self):
        parser = cli.build_parser()
        # argparse doesn't expose a clean "does this option exist" query,
        # so introspect the verify subparser's registered actions directly.
        verify_subparser = parser._subparsers._group_actions[0].choices["verify"]
        option_strings = set()
        for action in verify_subparser._actions:
            option_strings.update(action.option_strings)
        self.assertNotIn("--gate", option_strings)
        self.assertNotIn("--gates", option_strings)

    def test_cli_verify_gate_flag_is_a_parser_error_not_silently_ignored(self):
        for bad_argv in (
            ["verify", "--gate", "artifact-guard"],
            ["verify", "--gate", "unknown-gate-name"],
            ["verify", "--gate", "artifact-guard", "--gate", "artifact-guard"],
            ["verify", "--gate", ""],
        ):
            with self.subTest(argv=bad_argv):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    with self.assertRaises(SystemExit) as ctx:
                        cli.main(bad_argv)
                # argparse convention: exit code 2 for a CLI usage error.
                self.assertEqual(ctx.exception.code, 2)
                self.assertIn("unrecognized arguments", err.getvalue())

    def test_cli_verify_dry_run_lists_full_ordered_gate_set(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["verify", "--dry-run"])
        self.assertEqual(code, 0)
        printed = out.getvalue()
        for name in [g.name for g in verify_mod.gates()]:
            self.assertIn(name, printed)
        # Every line for a dry-run gate is explicitly marked SKIPPED(dry-run)
        # -- never silently omitted, never marked PASS/FAIL without running.
        self.assertEqual(printed.count("[SKIPPED(dry-run)]"), 11)


class HostOnlyEnvGateMirrorTests(unittest.TestCase):
    """Issue #10/#13 harness fix: the host lane runs the tools/gba-playtest
    suite in explicit host-only mode (GBA_PLAYTEST_HOST_ONLY=1), so its
    result is decided by mode, never by whether a git-ignored ROM happens to
    exist in the worktree while the later ROM gates rebuild it. That env
    assignment must be a literal part of the mirrored gate argv, must be
    applied to that one child process only, and must never reach the ROM
    build gates (which own the live/runtime coverage)."""

    HOST_ONLY_ENV = "GBA_PLAYTEST_HOST_ONLY"

    def test_host_suite_gate_carries_the_literal_env_assignment(self):
        gate = verify_mod.gates()[0]
        self.assertEqual(gate.name, "gba-playtest-host-suite")
        self.assertEqual(
            gate.command,
            [
                "GBA_PLAYTEST_HOST_ONLY=1",
                "python3",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tools/gba-playtest/tests",
                "-v",
            ],
        )

    def test_env_prefix_splits_into_child_env_and_unchanged_argv(self):
        env_overrides, argv = verify_mod._split_env_prefix(verify_mod.gates()[0].command)
        self.assertEqual(env_overrides, {self.HOST_ONLY_ENV: "1"})
        self.assertEqual(argv[0], "python3")
        self.assertNotIn(self.HOST_ONLY_ENV, " ".join(argv))

    def test_no_other_gate_requests_host_only_mode(self):
        for gate in verify_mod.gates()[1:]:
            with self.subTest(gate=gate.name):
                self.assertNotIn(
                    self.HOST_ONLY_ENV,
                    " ".join(gate.command),
                    f"{gate.name} must not inherit or repeat the host-only "
                    f"switch: the ROM/runtime gates own live coverage",
                )

    def test_workflow_sets_host_only_in_the_host_job_only(self):
        with open(BUILD_WORKFLOW_PATH, "r", encoding="utf-8") as handle:
            workflow = handle.read()
        host_job_start = workflow.index("\n  host-tests:\n")
        build_job_start = workflow.index("\n  build:\n")
        self.assertLess(host_job_start, build_job_start)
        host_job = workflow[host_job_start:build_job_start]
        build_job = workflow[build_job_start:]
        self.assertIn(
            "run: GBA_PLAYTEST_HOST_ONLY=1 python3 -m unittest discover "
            "-s tools/gba-playtest/tests -v",
            host_job,
        )
        self.assertNotIn(
            self.HOST_ONLY_ENV,
            build_job,
            "the ROM build job must never inherit host-only mode, or its "
            "runtime scenarios would skip",
        )

    def test_run_gates_injects_host_only_into_that_child_only(self):
        """Concurrency/isolation: with --jobs 2 the host gate and the later
        `make -j2` ROM gates run against the same worktree, so the host-only
        switch must live in exactly one child environment and must not leak
        into any later gate or into this process."""
        seen = []

        def fake_run(argv, cwd=None, env=None, **kwargs):
            seen.append((tuple(argv), None if env is None else dict(env)))
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        parent_env = {key: value for key, value in os.environ.items()}
        parent_env.pop(self.HOST_ONLY_ENV, None)
        with mock.patch.dict(os.environ, parent_env, clear=True):
            with mock.patch.object(verify_mod.subprocess, "run", side_effect=fake_run):
                results = verify_mod.run_gates(".", jobs=2)
            self.assertNotIn(
                self.HOST_ONLY_ENV,
                os.environ,
                "run_gates must not mutate the parent environment",
            )

        self.assertEqual(len(results), 11)
        self.assertTrue(all(result.passed for result in results))
        self.assertEqual(len(seen), 11)

        host_argv, host_env = seen[0]
        self.assertEqual(host_argv[0], "python3")
        self.assertIsNotNone(host_env)
        self.assertEqual(host_env[self.HOST_ONLY_ENV], "1")

        for gate, (argv, env) in zip(verify_mod.gates(jobs=2)[1:], seen[1:]):
            with self.subTest(gate=gate.name):
                self.assertNotIn(
                    self.HOST_ONLY_ENV,
                    {} if env is None else env,
                    f"host-only mode leaked into {gate.name}",
                )


if __name__ == "__main__":
    unittest.main()
