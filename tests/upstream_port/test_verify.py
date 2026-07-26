import contextlib
import inspect
import io
import os
import re
import shlex
import unittest

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
    "Install dependencies",
    "Build tools",
}


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
    mirror of .github/workflows/build.yml's gate steps -- parsed from the
    live workflow file, not a hardcoded copy of it."""

    def test_gate_argv_matches_workflow_commands_in_order(self):
        workflow_commands = _parse_workflow_gate_commands()
        gate_commands = [g.command for g in verify_mod.gates(jobs=2)]

        self.assertEqual(
            len(gate_commands),
            len(workflow_commands),
            f"verify.gates() has {len(gate_commands)} gate(s) but build.yml "
            f"has {len(workflow_commands)} gate command(s): "
            f"{[c for _, c in workflow_commands]!r}",
        )
        for gate_command, (step_name, workflow_argv) in zip(gate_commands, workflow_commands):
            self.assertEqual(
                gate_command,
                workflow_argv,
                f"gate command {gate_command!r} does not literally match "
                f"build.yml step {step_name!r} command {workflow_argv!r}",
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
        names = [g.name for g in verify_mod.gates()]
        self.assertEqual(
            names,
            [
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

    def test_artifact_guard_command(self):
        g = verify_mod.gates()[0]
        self.assertEqual(g.command, ["python3", "scripts/artifact_guard.py", "--revision", "HEAD"])

    def test_debug_and_release_configs_differ(self):
        by_name = {g.name: g for g in verify_mod.gates()}
        debug_gate = by_name["modern-linker-check-debug"]
        release_gate = by_name["modern-linker-check-release"]
        self.assertIn("MODERN_CONFIG=debug", debug_gate.command)
        self.assertIn("MODERN_CONFIG=release", release_gate.command)

    def test_dry_run_never_executes_subprocess(self):
        results = verify_mod.run_gates("/nonexistent/path/should/not/matter", dry_run=True)
        self.assertEqual(len(results), 8)
        self.assertTrue(all(r.ran is False for r in results))
        self.assertTrue(all(r.passed is False for r in results))  # not-ran != passed

    def test_dry_run_lists_full_ordered_gate_set_never_a_subset(self):
        """`--dry-run` (verify_mod.run_gates(dry_run=True)) must always list
        every gate the (non-dry-run) real run would perform, in the exact
        same order -- never a partial/filtered preview."""
        dry = [r.gate.name for r in verify_mod.run_gates("/nonexistent/path", dry_run=True)]
        real_names = [g.name for g in verify_mod.gates()]
        self.assertEqual(dry, real_names)
        self.assertEqual(len(dry), 8)


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
        self.assertEqual(printed.count("[SKIPPED(dry-run)]"), 8)


if __name__ == "__main__":
    unittest.main()
