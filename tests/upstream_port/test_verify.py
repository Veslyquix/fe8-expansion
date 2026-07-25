import unittest

from scripts.upstream_port import verify as verify_mod


class VerifyGatesTests(unittest.TestCase):
    def test_gate_list_mirrors_ci(self):
        names = [g.name for g in verify_mod.gates()]
        self.assertEqual(
            names,
            [
                "artifact-guard",
                "generated-data-check",
                "modern-linker-check-debug",
                "modern-linker-check-release",
            ],
        )

    def test_artifact_guard_command(self):
        g = verify_mod.gates()[0]
        self.assertEqual(g.command, ["python3", "scripts/artifact_guard.py", "--revision", "HEAD"])

    def test_debug_and_release_configs_differ(self):
        debug_gate, release_gate = verify_mod.gates()[2], verify_mod.gates()[3]
        self.assertIn("MODERN_CONFIG=debug", debug_gate.command)
        self.assertIn("MODERN_CONFIG=release", release_gate.command)

    def test_dry_run_never_executes_subprocess(self):
        results = verify_mod.run_gates("/nonexistent/path/should/not/matter", dry_run=True)
        self.assertEqual(len(results), 4)
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
