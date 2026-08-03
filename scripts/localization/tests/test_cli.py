import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def run_cli(args):
    return subprocess.run(
        [sys.executable, "-m", "scripts.localization.cli", *args],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )


class CliTests(unittest.TestCase):
    def test_validate_succeeds_on_real_repository_data(self):
        result = run_cli(["validate"])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout.strip(), "")

    def test_generate_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(["generate", "--out-dir", tmp])
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue((Path(tmp) / "expansion_msg_ids.h").is_file())
            self.assertTrue((Path(tmp) / "expansion_locale_catalog.c").is_file())
            self.assertTrue((Path(tmp) / "budget.json").is_file())

    def test_check_is_generate_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(["check", "--out-dir", tmp])
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue((Path(tmp) / "expansion_locale_catalog.c").is_file())

    def test_budget_prints_json_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(["budget", "--out-dir", tmp])
            self.assertEqual(result.returncode, 0, result.stdout)
            data = json.loads(result.stdout)
            self.assertIn("active_message_count", data)

    def test_validate_fails_on_broken_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reg_path = tmp_path / "registry.json"
            cat_path = tmp_path / "catalog.en.json"
            reg_path.write_text(
                json.dumps({"messages": [{"id": 0, "key": "a", "status": "bogus"}]}),
                encoding="utf-8",
            )
            cat_path.write_text(json.dumps({"locale": "en", "strings": {}}), encoding="utf-8")
            result = run_cli(
                ["validate", "--registry", str(reg_path), "--catalog-en", str(cat_path)]
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("error:", result.stdout)


if __name__ == "__main__":
    unittest.main()
