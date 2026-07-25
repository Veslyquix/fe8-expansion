import os
import subprocess
import sys
import unittest

from scripts.generated_data.tests._util import fixture_path, scratch_dir

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def run_cli(args, cwd=REPO_ROOT):
    result = subprocess.run(
        [sys.executable, "-m", "scripts.generated_data"] + args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


class CliValidateTests(unittest.TestCase):
    def test_valid_fixture_passes(self):
        code, out, err = run_cli([
            "validate", "--table", "supports",
            "--source", fixture_path("supports", "valid.json"),
            "--no-roundtrip",
        ])
        self.assertEqual(code, 0, msg=out + err)
        self.assertIn("OK:", out)

    def test_invalid_fixture_fails_with_location(self):
        code, out, err = run_cli([
            "validate", "--table", "supports",
            "--source", fixture_path("supports", "duplicate_owner.json"),
            "--no-roundtrip",
        ])
        self.assertEqual(code, 1)
        self.assertIn("duplicate_owner.json", err)
        self.assertIn("duplicate owner", err)

    def test_real_supports_source_validates_clean(self):
        code, out, err = run_cli(["validate", "--table", "supports"])
        self.assertEqual(code, 0, msg=out + err)

    def test_roundtrip_passes_against_matching_hand_fixture(self):
        code, out, err = run_cli([
            "validate", "--table", "supports",
            "--source", fixture_path("supports", "valid.json"),
            "--hand-source", fixture_path("supports", "valid_hand.c"),
        ])
        self.assertEqual(code, 0, msg=out + err)

    def test_roundtrip_fails_against_mismatched_hand_fixture(self):
        code, out, err = run_cli([
            "validate", "--table", "supports",
            "--source", fixture_path("supports", "valid.json"),
            "--hand-source", fixture_path("supports", "mismatched_hand.c"),
        ])
        self.assertEqual(code, 1)
        self.assertIn("supportExpBase mismatch", err)


class CliGenerateTests(unittest.TestCase):
    def test_generate_writes_c_and_inventory(self):
        with scratch_dir() as tmp:
            out_dir = os.path.join(tmp, "out")
            inventory_path = os.path.join(tmp, "inventory.md")
            code, out, err = run_cli([
                "generate", "--table", "supports",
                "--source", fixture_path("supports", "valid.json"),
                "--out-dir", out_dir,
                "--inventory", inventory_path,
                "--no-roundtrip",
            ])
            self.assertEqual(code, 0, msg=out + err)
            generated_file = os.path.join(out_dir, "data_supports.c")
            self.assertTrue(os.path.exists(generated_file))
            self.assertTrue(os.path.exists(inventory_path))
            with open(generated_file) as f:
                content = f.read()
            self.assertIn("SupportData_Eirika", content)
            with open(inventory_path) as f:
                inventory = f.read()
            self.assertIn("Record count: 3", inventory)

    def test_generate_is_idempotent_write_if_changed(self):
        with scratch_dir() as tmp:
            out_dir = os.path.join(tmp, "out")
            inventory_path = os.path.join(tmp, "inventory.md")
            args = [
                "generate", "--table", "supports",
                "--source", fixture_path("supports", "valid.json"),
                "--out-dir", out_dir,
                "--inventory", inventory_path,
                "--no-roundtrip",
            ]
            run_cli(args)
            generated_file = os.path.join(out_dir, "data_supports.c")
            mtime_before = os.path.getmtime(generated_file)
            code, out, err = run_cli(args)
            self.assertEqual(code, 0)
            self.assertIn("up to date", out)
            self.assertEqual(os.path.getmtime(generated_file), mtime_before)

    def test_generate_fails_for_invalid_source_and_writes_nothing(self):
        with scratch_dir() as tmp:
            out_dir = os.path.join(tmp, "out")
            inventory_path = os.path.join(tmp, "inventory.md")
            code, out, err = run_cli([
                "generate", "--table", "supports",
                "--source", fixture_path("supports", "out_of_range.json"),
                "--out-dir", out_dir,
                "--inventory", inventory_path,
                "--no-roundtrip",
            ])
            self.assertEqual(code, 1)
            self.assertFalse(os.path.exists(os.path.join(out_dir, "data_supports.c")))
            self.assertFalse(os.path.exists(inventory_path))


class CliCheckDriftTests(unittest.TestCase):
    def test_check_passes_immediately_after_generate(self):
        with scratch_dir() as tmp:
            out_dir = os.path.join(tmp, "out")
            inventory_path = os.path.join(tmp, "inventory.md")
            common = [
                "--table", "supports",
                "--source", fixture_path("supports", "valid.json"),
                "--out-dir", out_dir,
                "--inventory", inventory_path,
                "--no-roundtrip",
            ]
            run_cli(["generate"] + common)
            code, out, err = run_cli(["check"] + common)
            self.assertEqual(code, 0, msg=out + err)
            self.assertIn("no drift", out)

    def test_check_detects_injected_drift_in_inventory(self):
        with scratch_dir() as tmp:
            out_dir = os.path.join(tmp, "out")
            inventory_path = os.path.join(tmp, "inventory.md")
            common = [
                "--table", "supports",
                "--source", fixture_path("supports", "valid.json"),
                "--out-dir", out_dir,
                "--inventory", inventory_path,
                "--no-roundtrip",
            ]
            run_cli(["generate"] + common)
            with open(inventory_path, "a") as f:
                f.write("\ntampered line\n")
            code, out, err = run_cli(["check"] + common)
            self.assertEqual(code, 1)
            self.assertIn("DRIFT", err)

    def test_check_self_heals_tampered_build_output(self):
        # build/ output is gitignored/ephemeral: `check` silently
        # regenerates it (write-if-changed) instead of failing, since
        # there is nothing committed to have drifted against.
        with scratch_dir() as tmp:
            out_dir = os.path.join(tmp, "out")
            inventory_path = os.path.join(tmp, "inventory.md")
            common = [
                "--table", "supports",
                "--source", fixture_path("supports", "valid.json"),
                "--out-dir", out_dir,
                "--inventory", inventory_path,
                "--no-roundtrip",
            ]
            run_cli(["generate"] + common)
            generated_file = os.path.join(out_dir, "data_supports.c")
            with open(generated_file, "a") as f:
                f.write("\n/* tampered */\n")
            code, out, err = run_cli(["check"] + common)
            self.assertEqual(code, 0, msg=out + err)
            with open(generated_file) as f:
                self.assertNotIn("tampered", f.read())

    def test_check_fails_on_invalid_source(self):
        with scratch_dir() as tmp:
            out_dir = os.path.join(tmp, "out")
            inventory_path = os.path.join(tmp, "inventory.md")
            code, out, err = run_cli([
                "check", "--table", "supports",
                "--source", fixture_path("supports", "reciprocal_mismatch.json"),
                "--out-dir", out_dir,
                "--inventory", inventory_path,
                "--no-roundtrip",
            ])
            self.assertEqual(code, 1)
            self.assertIn("reciprocal mismatch", err)

    def test_real_supports_table_has_no_drift(self):
        """The committed build/ output + inventory must match `generate`'s
        output exactly -- this is the actual repo-wide drift gate."""
        code, out, err = run_cli(["check", "--table", "supports"])
        self.assertEqual(code, 0, msg=out + err)


class CliManifestTests(unittest.TestCase):
    def test_manifest_writes_report_and_header(self):
        with scratch_dir() as out_dir:
            report_path = os.path.join(out_dir, "manifest.md")
            code, out, err = run_cli([
                "manifest", "--out-dir", out_dir, "--report", report_path,
            ])
            self.assertEqual(code, 0, msg=out + err)
            self.assertTrue(os.path.exists(report_path))
            header_path = os.path.join(out_dir, "generated_data_manifest.h")
            self.assertTrue(os.path.exists(header_path))
            with open(header_path, "r", encoding="utf-8") as handle:
                header = handle.read()
            self.assertIn("#define GENERATED_DATA_TABLE_COUNT", header)
            self.assertNotIn("//", header)

    def test_manifest_check_detects_drift(self):
        with scratch_dir() as out_dir:
            report_path = os.path.join(out_dir, "manifest.md")
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write("stale manifest\n")
            code, out, err = run_cli([
                "manifest", "--check", "--out-dir", out_dir, "--report", report_path,
            ])
            self.assertEqual(code, 1)
            self.assertIn("DRIFT", err)

    def test_committed_manifest_has_no_drift(self):
        code, out, err = run_cli(["manifest", "--check"])
        self.assertEqual(code, 0, msg=out + err)



if __name__ == "__main__":
    unittest.main()
