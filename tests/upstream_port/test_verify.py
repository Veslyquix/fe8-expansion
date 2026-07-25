import os
import re
import shlex
import unittest

from scripts.upstream_port import verify as verify_mod

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
        self.assertEqual(len(results), 6)
        self.assertTrue(all(r.ran is False for r in results))
        self.assertTrue(all(r.passed is False for r in results))  # not-ran != passed

    def test_selected_filters_gate_subset(self):
        results = verify_mod.run_gates(
            "/nonexistent/path", dry_run=True, selected=["artifact-guard"]
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].gate.name, "artifact-guard")


if __name__ == "__main__":
    unittest.main()
