"""Tests for scripts/release_rehearsal/workflow_guard.py (issue #9)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import workflow_guard as wg

GOOD_WORKFLOW = """\
name: Release Rehearsal
on:
  pull_request:
    branches: [ "master" ]
  workflow_dispatch: {}

permissions:
  contents: read

jobs:
  release-rehearsal:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - run: make release-check
"""


class GoodWorkflowTests(unittest.TestCase):
    def test_no_violations(self):
        self.assertEqual(wg.validate_workflow_text(GOOD_WORKFLOW), [])

    def test_immutable_sha_checkout_ref_accepted(self):
        text = GOOD_WORKFLOW.replace(
            "actions/checkout@v7", "actions/checkout@" + "a" * 40
        )
        self.assertEqual(wg.validate_workflow_text(text), [])


class TriggerViolationTests(unittest.TestCase):
    def test_push_trigger_rejected(self):
        text = GOOD_WORKFLOW.replace(
            'on:\n  pull_request:\n    branches: [ "master" ]\n  workflow_dispatch: {}',
            'on:\n  push:\n    branches: [ "master" ]\n  workflow_dispatch: {}',
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("disallowed trigger" in v for v in violations))


class PermissionViolationTests(unittest.TestCase):
    def test_missing_top_level_permissions(self):
        text = GOOD_WORKFLOW.replace("permissions:\n  contents: read\n\n", "")
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("permissions" in v for v in violations))

    def test_write_permission_rejected(self):
        text = GOOD_WORKFLOW.replace("contents: read", "contents: write")
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("write" in v for v in violations))

    def test_contents_write_anywhere_rejected(self):
        text = GOOD_WORKFLOW + "\n# contents: write (job override attempt)\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("contents: write" in v for v in violations))


class CheckoutViolationTests(unittest.TestCase):
    def test_unpinned_checkout_ref_rejected(self):
        text = GOOD_WORKFLOW.replace("actions/checkout@v7", "actions/checkout@main")
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("not an accepted version" in v for v in violations))

    def test_missing_persist_credentials_false_rejected(self):
        text = GOOD_WORKFLOW.replace("          persist-credentials: false\n", "")
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("persist-credentials" in v for v in violations))


class ForbiddenSubstringTests(unittest.TestCase):
    def test_upload_artifact_rejected(self):
        text = GOOD_WORKFLOW + "\n      - uses: actions/upload-artifact@v4\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("upload-artifact" in v for v in violations))

    def test_gh_release_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: gh release create v1.0.0\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("gh release" in v for v in violations))

    def test_secrets_usage_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: echo ${{ secrets.TOKEN }}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("secrets." in v for v in violations))

    def test_git_tag_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: git tag v1.0.0\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("git tag" in v for v in violations))

    def test_environment_rejected(self):
        text = GOOD_WORKFLOW + "\n    environment: production\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("environment:" in v for v in violations))


class RepositoryStateTests(unittest.TestCase):
    def test_real_release_rehearsal_workflow_is_clean(self):
        path = ROOT / ".github" / "workflows" / "release-rehearsal.yml"
        violations = wg.validate_workflow_text(path.read_text(encoding="utf-8"))
        self.assertEqual(violations, [])

    def test_no_release_publish_workflow_exists(self):
        publish_path = ROOT / ".github" / "workflows" / "release-publish.yml"
        self.assertFalse(publish_path.exists())


if __name__ == "__main__":
    unittest.main()
