"""Guards for docs/generated_data_tutorial.md.

Two jobs:

* **doc-rot guard** -- every ``--table <name>`` and ``src/data/*.json``
  path the tutorial mentions must actually exist / be registered, so the
  contributor walkthrough can never silently drift from the platform.
* **workflow proof** -- actually run the documented add/modify/diagnostic
  loop through the public CLI on real sources, proving the tutorial's
  commands do what it claims (a clean ``file:line:column`` diagnostic on a
  bad edit, a clean pass on a good one).
"""

import json
import os
import re
import subprocess
import sys
import unittest

from scripts.generated_data import registry  # noqa: F401  (registers schemas)
from scripts.generated_data.schema import REGISTRY
from scripts.generated_data.tests._util import scratch_dir

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TUTORIAL = os.path.join(REPO_ROOT, "docs", "generated_data_tutorial.md")


def _tutorial_text():
    with open(TUTORIAL, "r", encoding="utf-8") as handle:
        return handle.read()


def run_cli(args, cwd=REPO_ROOT):
    result = subprocess.run(
        [sys.executable, "-m", "scripts.generated_data"] + args,
        cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return result.returncode, result.stdout, result.stderr


class TutorialDocRotTests(unittest.TestCase):
    def test_tutorial_exists(self):
        self.assertTrue(os.path.exists(TUTORIAL))

    def test_every_referenced_table_is_registered(self):
        text = _tutorial_text()
        referenced = set(re.findall(r"--table (\w+)", text))
        referenced.discard("<table>")
        self.assertTrue(referenced, "tutorial names no tables?")
        known = set(REGISTRY.all_names())
        unknown = sorted(referenced - known)
        self.assertEqual(unknown, [], "tutorial references unregistered tables")

    def test_every_referenced_source_path_exists(self):
        text = _tutorial_text()
        paths = set(re.findall(r"src/data/[\w./]+\.json", text))
        self.assertTrue(paths, "tutorial names no source paths?")
        missing = sorted(p for p in paths if not os.path.exists(os.path.join(REPO_ROOT, p)))
        self.assertEqual(missing, [], "tutorial references missing source files")

    def test_covers_every_supported_input_type(self):
        text = _tutorial_text().lower()
        for phrase in ("character", "class", "item", "chapter bundle",
                       "unit group", "shop", "trap", "support",
                       "event-list", "event symbol", "escape hatch"):
            self.assertIn(phrase, text, "tutorial omits: {}".format(phrase))


class TutorialWorkflowProofTests(unittest.TestCase):
    """Actually exercise the documented loop end-to-end via the CLI."""

    def test_modify_item_field_validates_clean(self):
        with open(os.path.join(REPO_ROOT, "src/data/items.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        for record in data["items"]:
            if record.get("item") == "ITEM_SWORD_IRON":
                record["might"] = 6  # documented modify example
                break
        with scratch_dir() as work:
            src = os.path.join(work, "items_mod.json")
            with open(src, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            code, out, err = run_cli(["validate", "--table", "items", "--source", src, "--no-roundtrip"])
            self.assertEqual(code, 0, msg=out + err)
            self.assertIn("OK:", out)

    def test_bad_supports_edit_reports_clean_diagnostic_not_traceback(self):
        with open(os.path.join(REPO_ROOT, "src/data/supports.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        # Truncate a parallel array -> documented "mismatched lengths" error.
        data["records"][0]["supportExpGrowth"].pop()
        with scratch_dir() as work:
            src = os.path.join(work, "supports_bad.json")
            with open(src, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            code, out, err = run_cli(["validate", "--table", "supports", "--source", src, "--no-roundtrip"])
            self.assertEqual(code, 1)
            self.assertNotIn("Traceback", err)
            self.assertIn("parallel arrays have mismatched lengths", err)


if __name__ == "__main__":
    unittest.main()
